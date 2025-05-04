# gui/widgets/results_tabs_widget.py
import os
from PySide6.QtWidgets import (QWidget, QTabWidget, QTableWidget, QHeaderView,
                               QAbstractItemView, QTableWidgetItem, QMenu,
                               QStyledItemDelegate, QStyleOptionViewItem) # Delegate用
from PySide6.QtCore import Qt, Signal, Slot, QPoint, QModelIndex # Delegate用
from PySide6.QtGui import QAction, QColor # Delegate用

# カスタムテーブルアイテムをインポート
try:
    from .table_items import (NumericTableWidgetItem, FileSizeTableWidgetItem,
                             DateTimeTableWidgetItem, ResolutionTableWidgetItem)
except ImportError:
    print("エラー: table_items モジュールのインポートに失敗しました。ソート機能が正しく動作しない可能性があります。")
    NumericTableWidgetItem = QTableWidgetItem
    FileSizeTableWidgetItem = QTableWidgetItem
    DateTimeTableWidgetItem = QTableWidgetItem
    ResolutionTableWidgetItem = QTableWidgetItem

# ファイル情報取得関数をインポート
try:
    from utils.file_operations import get_file_info
except ImportError:
    print("エラー: utils.file_operations モジュールのインポートに失敗しました。ファイル情報が表示されません。")
    def get_file_info(fp): return "N/A", "N/A", "N/A"


# ★★★ 重複グループの視覚的区別のためのデリゲート ★★★
class AlternatingRowColorDelegate(QStyledItemDelegate):
    """テーブルの行の背景色を交互に変えるデリゲート"""
    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex):
        super().initStyleOption(option, index)
        # グループID (例: ハッシュ値) を UserRole+1 あたりに格納しておき、
        # それが変わるごと、または偶数/奇数行で色を変える
        # ここでは単純に行番号の偶奇で色分け
        if index.row() % 2 == 0:
            option.backgroundBrush = QColor(Qt.GlobalColor.lightGray).lighter(130) # 少し明るいグレー
        # else: デフォルトの色


class ResultsTabsWidget(QTabWidget):
    """
    結果表示用のタブウィジェット（ブレ画像、類似ペア、重複ファイル、エラー）。
    """
    selection_changed = Signal()
    delete_file_requested = Signal(str) # 単一ファイル削除要求
    open_file_requested = Signal(str)   # 単一ファイルオープン要求
    # ★ 重複グループ内での削除アクション用シグナル ★
    delete_duplicates_requested = Signal(str, list) # (keep_path, delete_paths_list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_tabs()

    def _setup_tabs(self):
        """タブとテーブルを作成し、シグナルを接続する"""
        # --- ブレ画像タブ ---
        self.blurry_table = self._create_blurry_table()
        self.addTab(self.blurry_table, "ブレ画像 (0)")

        # --- 類似ペアタブ ---
        self.similar_table = self._create_similar_table()
        self.similar_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.similar_table.customContextMenuRequested.connect(self._show_similar_table_context_menu)
        self.addTab(self.similar_table, "類似ペア (0)")

        # --- ★ 重複ファイルタブを追加 ★ ---
        self.duplicate_table = self._create_duplicate_table()
        self.duplicate_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.duplicate_table.customContextMenuRequested.connect(self._show_duplicate_table_context_menu)
        # 行の色分け用デリゲートを設定
        # self.duplicate_table.setItemDelegate(AlternatingRowColorDelegate(self)) # オプション
        self.addTab(self.duplicate_table, "重複ファイル (0)")

        # --- エラータブ ---
        self.error_table = self._create_error_table()
        self.addTab(self.error_table, "エラー (0)")

        # --- シグナル接続 ---
        self.blurry_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.similar_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.duplicate_table.itemSelectionChanged.connect(self.selection_changed.emit) # ★ 追加 ★
        self.error_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.currentChanged.connect(lambda index: self.selection_changed.emit())

    # --- テーブル作成メソッド ---
    def _create_table_widget(self, column_count, headers, selection_mode, sorting_enabled=True):
        table = QTableWidget(); table.setColumnCount(column_count); table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False); table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(selection_mode); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(sorting_enabled)
        return table

    def _create_blurry_table(self):
        headers = ["", "ファイル名", "サイズ", "更新日時", "解像度", "ブレ度スコア", "パス"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch); table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        return table

    def _create_similar_table(self):
        headers = ["ファイル名1", "サイズ1", "日時1", "解像度1", "ファイル名2", "類似度(%)", "パス1"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch); table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch); table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        return table

    def _create_duplicate_table(self):
        """★ 重複ファイル用テーブルを作成 ★"""
        headers = ["", "ファイル名", "サイズ", "更新日時", "グループID", "パス"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        # カラム幅設定
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # チェックボックス
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)       # ファイル名
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # サイズ
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # 更新日時
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # グループID (ハッシュの一部など)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)       # パス
        # table.setColumnHidden(4, True) # グループIDは隠しても良いかも
        return table

    def _create_error_table(self):
        headers = ["タイプ", "ファイル/ペア", "エラー内容"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.SingleSelection, sorting_enabled=True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch); table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        return table

    # --- データ投入メソッド ---
    # ★ populate_results のシグネチャを変更 ★
    @Slot(list, list, dict, list)
    def populate_results(self, blurry_results, similar_results, duplicate_results, scan_errors):
        """受け取ったデータで各テーブルを更新する"""
        self._populate_blurry_table(blurry_results)
        self._populate_similar_table(similar_results)
        self._populate_duplicate_table(duplicate_results) # ★ 追加 ★
        self._populate_error_table(scan_errors)
        # タブの件数表示を更新
        self.setTabText(0, f"ブレ画像 ({self.blurry_table.rowCount()})")
        self.setTabText(1, f"類似ペア ({self.similar_table.rowCount()})")
        self.setTabText(2, f"重複ファイル ({self.duplicate_table.rowCount()})") # ★ 更新 ★
        self.setTabText(3, f"エラー ({self.error_table.rowCount()})") # ★ インデックス更新 ★

    def _populate_blurry_table(self, blurry_results):
        self.blurry_table.setSortingEnabled(False); self.blurry_table.setRowCount(len(blurry_results))
        for row, data in enumerate(blurry_results):
            path = data['path']; score = data['score']; file_size, mod_time, dimensions = get_file_info(path)
            chk_item = QTableWidgetItem(); chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled); chk_item.setCheckState(Qt.CheckState.Unchecked); chk_item.setData(Qt.ItemDataRole.UserRole, path)
            name_item = QTableWidgetItem(os.path.basename(path)); size_item = FileSizeTableWidgetItem(file_size); date_item = DateTimeTableWidgetItem(mod_time); dim_item = ResolutionTableWidgetItem(dimensions); score_item = NumericTableWidgetItem(f"{score:.4f}"); score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); path_item = QTableWidgetItem(path)
            self.blurry_table.setItem(row, 0, chk_item); self.blurry_table.setItem(row, 1, name_item); self.blurry_table.setItem(row, 2, size_item); self.blurry_table.setItem(row, 3, date_item); self.blurry_table.setItem(row, 4, dim_item); self.blurry_table.setItem(row, 5, score_item); self.blurry_table.setItem(row, 6, path_item)
        self.blurry_table.setSortingEnabled(True)

    def _populate_similar_table(self, similar_results):
        self.similar_table.setSortingEnabled(False); self.similar_table.setRowCount(len(similar_results))
        for row, (path1, path2, score) in enumerate(similar_results):
            file_size1, mod_time1, dimensions1 = get_file_info(path1)
            name1_item = QTableWidgetItem(os.path.basename(path1)); name1_item.setData(Qt.ItemDataRole.UserRole, (path1, path2))
            size1_item = FileSizeTableWidgetItem(file_size1); date1_item = DateTimeTableWidgetItem(mod_time1); dim1_item = ResolutionTableWidgetItem(dimensions1); name2_item = QTableWidgetItem(os.path.basename(path2)); score_item = NumericTableWidgetItem(str(score)); score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); path1_item = QTableWidgetItem(path1)
            self.similar_table.setItem(row, 0, name1_item); self.similar_table.setItem(row, 1, size1_item); self.similar_table.setItem(row, 2, date1_item); self.similar_table.setItem(row, 3, dim1_item); self.similar_table.setItem(row, 4, name2_item); self.similar_table.setItem(row, 5, score_item); self.similar_table.setItem(row, 6, path1_item)
        self.similar_table.setSortingEnabled(True)

    def _populate_duplicate_table(self, duplicate_results):
        """★ 重複ファイルテーブルにデータを投入 ★"""
        self.duplicate_table.setSortingEnabled(False)
        self.duplicate_table.setRowCount(0) # 一旦クリア
        current_row = 0
        group_id_counter = 1 # グループを区別するための連番
        # duplicate_results は {hash: [path1, path2, ...]} 形式
        for group_hash, paths in duplicate_results.items():
            if len(paths) < 2: continue # 念のため (重複は2つ以上のはず)
            # グループID (ハッシュの一部など、または連番)
            display_group_id = f"G{group_id_counter}" # 例: G1, G2, ...
            # display_group_id = group_hash[:8] # ハッシュの先頭8文字など

            # グループ内の各ファイルを行として追加
            for i, path in enumerate(paths):
                file_size, mod_time, dimensions = get_file_info(path) # 解像度は表示しないが取得はしておく

                # チェックボックスアイテム
                chk_item = QTableWidgetItem()
                chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                # ★ デフォルトでは最初のファイル以外をチェック状態にする (オプション) ★
                chk_item.setCheckState(Qt.CheckState.Checked if i > 0 else Qt.CheckState.Unchecked)
                # UserRole にファイルパスとグループハッシュを格納
                chk_item.setData(Qt.ItemDataRole.UserRole, {'path': path, 'group_hash': group_hash})

                name_item = QTableWidgetItem(os.path.basename(path))
                size_item = FileSizeTableWidgetItem(file_size)
                date_item = DateTimeTableWidgetItem(mod_time)
                group_item = QTableWidgetItem(display_group_id)
                group_item.setData(Qt.ItemDataRole.UserRole+1, group_hash) # ソート用にハッシュ全体も保持
                path_item = QTableWidgetItem(path)

                # 行を追加してアイテムを設定
                self.duplicate_table.insertRow(current_row)
                self.duplicate_table.setItem(current_row, 0, chk_item)
                self.duplicate_table.setItem(current_row, 1, name_item)
                self.duplicate_table.setItem(current_row, 2, size_item)
                self.duplicate_table.setItem(current_row, 3, date_item)
                self.duplicate_table.setItem(current_row, 4, group_item)
                self.duplicate_table.setItem(current_row, 5, path_item)
                current_row += 1

            group_id_counter += 1
        self.duplicate_table.setSortingEnabled(True)

    def _populate_error_table(self, scan_errors):
        self.error_table.setSortingEnabled(False); self.error_table.setRowCount(len(scan_errors))
        for row, err_data in enumerate(scan_errors):
            err_type = err_data.get('type', '不明'); path_display = err_data.get('path', 'N/A'); error_msg = err_data.get('error', '詳細不明')
            type_item = QTableWidgetItem(err_type); path_item = QTableWidgetItem(path_display); path_item.setData(Qt.ItemDataRole.UserRole, err_data); msg_item = QTableWidgetItem(error_msg); msg_item.setToolTip(error_msg)
            self.error_table.setItem(row, 0, type_item); self.error_table.setItem(row, 1, path_item); self.error_table.setItem(row, 2, msg_item)
        self.error_table.setSortingEnabled(True)

    @Slot()
    def clear_results(self):
        """すべてのテーブルの内容をクリアし、タブの件数をリセットする"""
        self.blurry_table.setRowCount(0); self.similar_table.setRowCount(0)
        self.duplicate_table.setRowCount(0); self.error_table.setRowCount(0) # ★ 追加 ★
        self.setTabText(0, "ブレ画像 (0)"); self.setTabText(1, "類似ペア (0)")
        self.setTabText(2, "重複ファイル (0)"); self.setTabText(3, "エラー (0)") # ★ 更新 ★

    # --- 選択状態取得メソッド ---
    def get_selected_blurry_paths(self):
        paths = [];
        for row in range(self.blurry_table.rowCount()):
            chk_item = self.blurry_table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                path = chk_item.data(Qt.ItemDataRole.UserRole); path and paths.append(path)
        return paths

    def get_selected_similar_primary_paths(self):
        paths = []; selected_rows = set(item.row() for item in self.similar_table.selectedItems())
        for row in selected_rows:
            item = self.similar_table.item(row, 0)
            if item: path_data = item.data(Qt.ItemDataRole.UserRole); isinstance(path_data, tuple) and len(path_data) == 2 and path_data[0] and paths.append(path_data[0])
        return paths

    def get_selected_duplicate_paths(self):
        """★ 重複ファイルタブでチェックされているファイルのパスリストを取得 ★"""
        paths = []
        for row in range(self.duplicate_table.rowCount()):
            chk_item = self.duplicate_table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                # UserRole に {'path': ..., 'group_hash': ...} が格納されている想定
                data = chk_item.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, dict) and 'path' in data:
                    paths.append(data['path'])
        return paths

    def get_current_selection_paths(self):
        """現在アクティブなタブで選択されているアイテムに関連するパスを取得 (プレビュー用)"""
        primary_path, secondary_path = None, None
        current_index = self.currentIndex()
        if current_index == 0: # ブレ画像
            table = self.blurry_table; selected_items = table.selectedItems()
            if selected_items: row = selected_items[0].row(); item = table.item(row, 0); item and (primary_path := item.data(Qt.ItemDataRole.UserRole))
        elif current_index == 1: # 類似ペア
            table = self.similar_table; selected_items = table.selectedItems()
            if selected_items:
                row = selected_items[0].row(); item = table.item(row, 0)
                if item: path_data = item.data(Qt.ItemDataRole.UserRole); isinstance(path_data, tuple) and len(path_data) == 2 and (primary_path := path_data[0], secondary_path := path_data[1])
        elif current_index == 2: # ★ 重複ファイル ★
             table = self.duplicate_table; selected_items = table.selectedItems()
             if selected_items:
                 row = selected_items[0].row(); item = table.item(row, 0) # チェックボックス列
                 if item: data = item.data(Qt.ItemDataRole.UserRole); isinstance(data, dict) and 'path' in data and (primary_path := data['path'])
                 # 重複ファイルタブでは右プレビューは使わない
                 secondary_path = None
        # エラータブはプレビュー対象外
        return primary_path, secondary_path

    # --- 全選択/解除メソッド ---
    @Slot()
    def select_all_blurry(self): self.setCurrentIndex(0); [item.setCheckState(Qt.CheckState.Checked) for row in range(self.blurry_table.rowCount()) if (item := self.blurry_table.item(row, 0)) and item.flags() & Qt.ItemFlag.ItemIsUserCheckable]
    @Slot()
    def select_all_similar(self): self.setCurrentIndex(1); self.similar_table.selectAll()
    @Slot()
    def select_all_duplicates(self):
        """★ 重複ファイルタブの全チェックボックスをオンにする (最初のファイルを除くオプション付き) ★"""
        self.setCurrentIndex(2) # 重複タブに切り替え
        current_group_hash = None
        is_first_in_group = True
        for row in range(self.duplicate_table.rowCount()):
            chk_item = self.duplicate_table.item(row, 0)
            group_item = self.duplicate_table.item(row, 4) # グループID列
            if chk_item and group_item and chk_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                data = chk_item.data(Qt.ItemDataRole.UserRole)
                group_hash = data.get('group_hash') if isinstance(data, dict) else None

                if group_hash != current_group_hash:
                    current_group_hash = group_hash
                    is_first_in_group = True
                else:
                    is_first_in_group = False

                # 最初のファイル以外をチェックする (または全部チェックするならこの if を外す)
                if not is_first_in_group:
                     chk_item.setCheckState(Qt.CheckState.Checked)
                else:
                     chk_item.setCheckState(Qt.CheckState.Unchecked) # 最初のファイルはチェックしない

    @Slot()
    def deselect_all(self):
        """すべてのタブの選択状態を解除する"""
        for row in range(self.blurry_table.rowCount()): item = self.blurry_table.item(row, 0); item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable and item.setCheckState(Qt.CheckState.Unchecked)
        self.similar_table.clearSelection()
        # ★ 重複タブのチェックも解除 ★
        for row in range(self.duplicate_table.rowCount()): item = self.duplicate_table.item(row, 0); item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable and item.setCheckState(Qt.CheckState.Unchecked)
        self.error_table.clearSelection()
        self.selection_changed.emit()

    # --- テーブルから削除された項目を反映するメソッド ---
    def remove_items_by_paths(self, deleted_paths_set):
        """指定されたパスセットに一致する項目をテーブルから削除"""
        if not deleted_paths_set: return

        # ブレ画像テーブル
        rows_to_remove_blurry = [row for row in range(self.blurry_table.rowCount()) if (chk_item := self.blurry_table.item(row, 0)) and (path := chk_item.data(Qt.ItemDataRole.UserRole)) and os.path.normpath(path) in deleted_paths_set]; [self.blurry_table.removeRow(row) for row in sorted(rows_to_remove_blurry, reverse=True)]
        # 類似ペアテーブル
        rows_to_remove_similar = [row for row in range(self.similar_table.rowCount()) if (item := self.similar_table.item(row, 0)) and (path_data := item.data(Qt.ItemDataRole.UserRole)) and isinstance(path_data, tuple) and len(path_data) == 2 and ((p1n := os.path.normpath(path_data[0]) if path_data[0] else None) and p1n in deleted_paths_set or (p2n := os.path.normpath(path_data[1]) if path_data[1] else None) and p2n in deleted_paths_set)]; [self.similar_table.removeRow(row) for row in sorted(list(set(rows_to_remove_similar)), reverse=True)]
        # ★ 重複ファイルテーブル ★
        rows_to_remove_duplicate = [row for row in range(self.duplicate_table.rowCount()) if (chk_item := self.duplicate_table.item(row, 0)) and (data := chk_item.data(Qt.ItemDataRole.UserRole)) and isinstance(data, dict) and (path := data.get('path')) and os.path.normpath(path) in deleted_paths_set]
        for row in sorted(rows_to_remove_duplicate, reverse=True): self.duplicate_table.removeRow(row)
        # エラーテーブル
        rows_to_remove_error = [row for row in range(self.error_table.rowCount()) if (item := self.error_table.item(row, 1)) and (err_data := item.data(Qt.ItemDataRole.UserRole)) and isinstance(err_data, dict) and (((et := err_data.get('type')) == 'ブレ検出' and (ep := err_data.get('path')) and os.path.normpath(ep) in deleted_paths_set) or (et in ['pHash計算', 'ORB比較', 'pHash比較', 'ファイル読込/ハッシュ計算', 'ファイルサイズ取得'] and (ep := err_data.get('path')) and os.path.normpath(ep) in deleted_paths_set) or (et in ['ORB比較', 'pHash比較'] and ((p1n := os.path.normpath(err_data['path1']) if err_data.get('path1') else None) and p1n in deleted_paths_set or (p2n := os.path.normpath(err_data['path2']) if err_data.get('path2') else None) and p2n in deleted_paths_set)))]; [self.error_table.removeRow(row) for row in sorted(rows_to_remove_error, reverse=True)]

        # タブの件数表示を更新
        self.setTabText(0, f"ブレ画像 ({self.blurry_table.rowCount()})")
        self.setTabText(1, f"類似ペア ({self.similar_table.rowCount()})")
        self.setTabText(2, f"重複ファイル ({self.duplicate_table.rowCount()})") # ★ 更新 ★
        self.setTabText(3, f"エラー ({self.error_table.rowCount()})") # ★ 更新 ★


    # --- コンテキストメニュー処理 ---
    @Slot(QPoint)
    def _show_similar_table_context_menu(self, pos: QPoint):
        item = self.similar_table.itemAt(pos); row = item.row() if item else -1
        if row == -1: return
        data_item = self.similar_table.item(row, 0); path_data = data_item.data(Qt.ItemDataRole.UserRole) if data_item else None
        if not isinstance(path_data, tuple) or len(path_data) != 2: return
        path1, path2 = path_data; base_name1 = os.path.basename(path1) if path1 else "N/A"; base_name2 = os.path.basename(path2) if path2 else "N/A"
        context_menu = QMenu(self); action_delete1 = QAction(f"ファイル1を削除 ({base_name1})", self); action_delete2 = QAction(f"ファイル2を削除 ({base_name2})", self); action_open1 = QAction(f"ファイル1を開く ({base_name1})", self); action_open2 = QAction(f"ファイル2を開く ({base_name2})", self)
        action_delete1.setEnabled(bool(path1 and os.path.exists(path1))); action_delete2.setEnabled(bool(path2 and os.path.exists(path2))); action_open1.setEnabled(bool(path1 and os.path.exists(path1))); action_open2.setEnabled(bool(path2 and os.path.exists(path2)))
        if path1: action_delete1.triggered.connect(lambda checked=False, p=path1: self.delete_file_requested.emit(p)); action_open1.triggered.connect(lambda checked=False, p=path1: self.open_file_requested.emit(p))
        if path2: action_delete2.triggered.connect(lambda checked=False, p=path2: self.delete_file_requested.emit(p)); action_open2.triggered.connect(lambda checked=False, p=path2: self.open_file_requested.emit(p))
        context_menu.addAction(action_delete1); context_menu.addAction(action_delete2); context_menu.addSeparator(); context_menu.addAction(action_open1); context_menu.addAction(action_open2)
        context_menu.exec(self.similar_table.mapToGlobal(pos))

    @Slot(QPoint)
    def _show_duplicate_table_context_menu(self, pos: QPoint):
        """★ 重複ファイルテーブルのコンテキストメニュー ★"""
        item = self.duplicate_table.itemAt(pos)
        if not item: return
        row = item.row()
        chk_item = self.duplicate_table.item(row, 0) # チェックボックス列からデータを取得
        if not chk_item: return
        data = chk_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict) or 'path' not in data or 'group_hash' not in data: return

        clicked_path = data['path']
        group_hash = data['group_hash']
        base_name = os.path.basename(clicked_path)

        # 同じグループの他のファイルを探す
        group_paths = []
        for r in range(self.duplicate_table.rowCount()):
            item0 = self.duplicate_table.item(r, 0)
            if item0:
                d = item0.data(Qt.ItemDataRole.UserRole)
                if isinstance(d, dict) and d.get('group_hash') == group_hash:
                    group_paths.append(d.get('path'))

        context_menu = QMenu(self)
        action_delete_this = QAction(f"このファイルを削除 ({base_name})", self)
        action_keep_this = QAction(f"これ以外を削除 ({len(group_paths)-1}個)", self)
        action_open_this = QAction(f"このファイルを開く ({base_name})", self)

        action_delete_this.setEnabled(bool(clicked_path and os.path.exists(clicked_path)))
        # グループに複数ファイルがある場合のみ「これ以外を削除」を有効化
        action_keep_this.setEnabled(len(group_paths) > 1)
        action_open_this.setEnabled(bool(clicked_path and os.path.exists(clicked_path)))

        # シグナル発行
        if clicked_path:
            action_delete_this.triggered.connect(lambda checked=False, p=clicked_path: self.delete_file_requested.emit(p))
            action_open_this.triggered.connect(lambda checked=False, p=clicked_path: self.open_file_requested.emit(p))
        # 「これ以外を削除」のアクション
        if len(group_paths) > 1:
            paths_to_delete = [p for p in group_paths if p != clicked_path]
            action_keep_this.triggered.connect(lambda checked=False, keep=clicked_path, delete_list=paths_to_delete: self.delete_duplicates_requested.emit(keep, delete_list))


        context_menu.addAction(action_delete_this)
        context_menu.addAction(action_keep_this)
        context_menu.addSeparator()
        context_menu.addAction(action_open_this)
        context_menu.exec(self.duplicate_table.mapToGlobal(pos))

