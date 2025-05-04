# gui/widgets/results_tabs_widget.py
import os
from PySide6.QtWidgets import (QWidget, QTabWidget, QTableWidget, QHeaderView,
                               QAbstractItemView, QTableWidgetItem)
from PySide6.QtCore import Qt, Signal, Slot

# カスタムテーブルアイテムをインポート
try:
    from .table_items import (NumericTableWidgetItem, FileSizeTableWidgetItem,
                             DateTimeTableWidgetItem, ResolutionTableWidgetItem)
except ImportError:
    print("エラー: table_items モジュールのインポートに失敗しました。ソート機能が正しく動作しない可能性があります。")
    # フォールバックとして標準の QTableWidgetItem を使う
    NumericTableWidgetItem = QTableWidgetItem
    FileSizeTableWidgetItem = QTableWidgetItem
    DateTimeTableWidgetItem = QTableWidgetItem
    ResolutionTableWidgetItem = QTableWidgetItem

# ファイル情報取得関数をインポート (utils から)
try:
    from utils.file_operations import get_file_info
except ImportError:
    print("エラー: utils.file_operations モジュールのインポートに失敗しました。ファイル情報が表示されません。")
    def get_file_info(fp): return "N/A", "N/A", "N/A"


class ResultsTabsWidget(QTabWidget):
    """
    結果表示用のタブウィジェット（ブレ画像、類似ペア、エラー）。
    テーブルの作成、データ投入、選択変更シグナル発行などを担当する。
    """
    # シグナル定義: テーブルの選択が変更されたときに通知
    selection_changed = Signal()

    def __init__(self, parent=None):
        """コンストラクタ"""
        super().__init__(parent)
        self._setup_tabs()

    def _setup_tabs(self):
        """タブとテーブルを作成する"""
        # --- ブレ画像タブ ---
        self.blurry_table = self._create_blurry_table()
        self.addTab(self.blurry_table, "ブレ画像 (0)")

        # --- 類似ペアタブ ---
        self.similar_table = self._create_similar_table()
        self.addTab(self.similar_table, "類似ペア (0)")

        # --- エラータブ ---
        self.error_table = self._create_error_table()
        self.addTab(self.error_table, "エラー (0)")

        # タブ切り替え時に選択変更シグナルを発行する (プレビュー更新のため)
        self.currentChanged.connect(self.selection_changed.emit)

    def _create_table_widget(self, column_count, headers, selection_mode, sorting_enabled=True):
        """共通のテーブルウィジェット設定を行うヘルパーメソッド"""
        table = QTableWidget()
        table.setColumnCount(column_count)
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False) # 行番号非表示
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows) # 行選択モード
        table.setSelectionMode(selection_mode) # 選択モード設定
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) # 編集不可
        table.setSortingEnabled(sorting_enabled) # ソート有効/無効
        # 選択が変更されたら selection_changed シグナルを発行
        table.itemSelectionChanged.connect(self.selection_changed.emit)
        return table

    def _create_blurry_table(self):
        """ブレ画像用テーブルを作成"""
        headers = ["", "ファイル名", "サイズ", "更新日時", "解像度", "ブレ度スコア", "パス"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        # カラム幅設定
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # チェックボックス
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # ファイル名
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # サイズ
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # 更新日時
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # 解像度
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # スコア
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch) # パス
        # table.setColumnHidden(6, True) # 必要ならパス列を隠す
        return table

    def _create_similar_table(self):
        """類似ペア用テーブルを作成"""
        headers = ["ファイル名1", "サイズ1", "日時1", "解像度1", "ファイル名2", "類似度(%)", "パス1"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        # カラム幅設定
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # ファイル名1
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # サイズ1
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # 日時1
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # 解像度1
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # ファイル名2
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # 類似度
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch) # パス1
        # table.setColumnHidden(6, True) # 必要ならパス1列を隠す
        return table

    def _create_error_table(self):
        """エラー表示用テーブルを作成"""
        headers = ["タイプ", "ファイル/ペア", "エラー内容"]
        # エラーテーブルは単一選択、ソート有効
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.SingleSelection, sorting_enabled=True)
        # カラム幅設定
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # タイプ
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # ファイル/ペア
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) # エラー内容
        return table

    @Slot(list, list, list) # メインウィンドウから呼び出されるスロット
    def populate_results(self, blurry_results, similar_results, scan_errors):
        """受け取ったデータで各テーブルを更新する"""
        self._populate_blurry_table(blurry_results)
        self._populate_similar_table(similar_results)
        self._populate_error_table(scan_errors)
        # タブの件数表示を更新
        self.setTabText(0, f"ブレ画像 ({self.blurry_table.rowCount()})")
        self.setTabText(1, f"類似ペア ({self.similar_table.rowCount()})")
        self.setTabText(2, f"エラー ({self.error_table.rowCount()})")

    def _populate_blurry_table(self, blurry_results):
        """ブレ画像テーブルにデータを投入"""
        self.blurry_table.setSortingEnabled(False) # 更新中はソート無効
        self.blurry_table.setRowCount(len(blurry_results))
        for row, data in enumerate(blurry_results):
            path = data['path']
            score = data['score']
            file_size, mod_time, dimensions = get_file_info(path)

            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(Qt.CheckState.Unchecked)
            chk_item.setData(Qt.ItemDataRole.UserRole, path) # パスをデータとして保持

            name_item = QTableWidgetItem(os.path.basename(path))
            size_item = FileSizeTableWidgetItem(file_size)
            date_item = DateTimeTableWidgetItem(mod_time)
            dim_item = ResolutionTableWidgetItem(dimensions)
            score_item = NumericTableWidgetItem(f"{score:.4f}")
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            path_item = QTableWidgetItem(path)

            self.blurry_table.setItem(row, 0, chk_item)
            self.blurry_table.setItem(row, 1, name_item)
            self.blurry_table.setItem(row, 2, size_item)
            self.blurry_table.setItem(row, 3, date_item)
            self.blurry_table.setItem(row, 4, dim_item)
            self.blurry_table.setItem(row, 5, score_item)
            self.blurry_table.setItem(row, 6, path_item)
        self.blurry_table.setSortingEnabled(True) # 更新後にソート有効化

    def _populate_similar_table(self, similar_results):
        """類似ペアテーブルにデータを投入"""
        self.similar_table.setSortingEnabled(False)
        self.similar_table.setRowCount(len(similar_results))
        for row, (path1, path2, score) in enumerate(similar_results):
            file_size1, mod_time1, dimensions1 = get_file_info(path1)

            name1_item = QTableWidgetItem(os.path.basename(path1))
            name1_item.setData(Qt.ItemDataRole.UserRole, (path1, path2)) # ペアのパスを保持
            size1_item = FileSizeTableWidgetItem(file_size1)
            date1_item = DateTimeTableWidgetItem(mod_time1)
            dim1_item = ResolutionTableWidgetItem(dimensions1)
            name2_item = QTableWidgetItem(os.path.basename(path2))
            score_item = NumericTableWidgetItem(str(score)) # スコアは整数
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            path1_item = QTableWidgetItem(path1)

            self.similar_table.setItem(row, 0, name1_item)
            self.similar_table.setItem(row, 1, size1_item)
            self.similar_table.setItem(row, 2, date1_item)
            self.similar_table.setItem(row, 3, dim1_item)
            self.similar_table.setItem(row, 4, name2_item)
            self.similar_table.setItem(row, 5, score_item)
            self.similar_table.setItem(row, 6, path1_item)
        self.similar_table.setSortingEnabled(True)

    def _populate_error_table(self, scan_errors):
        """エラーテーブルにデータを投入"""
        self.error_table.setSortingEnabled(False)
        self.error_table.setRowCount(len(scan_errors))
        for row, err_data in enumerate(scan_errors):
            err_type = err_data.get('type', '不明')
            # エラーデータに元のパス情報を含めるように ScanWorker を修正済みと想定
            path_display = err_data.get('path', 'N/A') # 表示用のパス/ペア名
            error_msg = err_data.get('error', '詳細不明')

            type_item = QTableWidgetItem(err_type)
            path_item = QTableWidgetItem(path_display)
            # エラーデータ自体を UserRole に保持しておくと後で利用しやすいかも
            path_item.setData(Qt.ItemDataRole.UserRole, err_data)
            msg_item = QTableWidgetItem(error_msg)
            msg_item.setToolTip(error_msg) # 長いメッセージはツールチップで

            self.error_table.setItem(row, 0, type_item)
            self.error_table.setItem(row, 1, path_item)
            self.error_table.setItem(row, 2, msg_item)
        self.error_table.setSortingEnabled(True)

    @Slot() # メインウィンドウから呼び出されるスロット
    def clear_results(self):
        """すべてのテーブルの内容をクリアし、タブの件数をリセットする"""
        self.blurry_table.setRowCount(0)
        self.similar_table.setRowCount(0)
        self.error_table.setRowCount(0)
        self.setTabText(0, "ブレ画像 (0)")
        self.setTabText(1, "類似ペア (0)")
        self.setTabText(2, "エラー (0)")

    # --- 選択状態を取得するメソッド ---
    def get_selected_blurry_paths(self):
        """ブレ画像タブでチェックされているファイルのパスリストを取得"""
        paths = []
        for row in range(self.blurry_table.rowCount()):
            chk_item = self.blurry_table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                path = chk_item.data(Qt.ItemDataRole.UserRole)
                if path:
                    paths.append(path)
        return paths

    def get_selected_similar_primary_paths(self):
        """類似ペアタブで選択されている行の主ファイル(path1)のパスリストを取得"""
        paths = []
        selected_rows = set(item.row() for item in self.similar_table.selectedItems())
        for row in selected_rows:
            item = self.similar_table.item(row, 0) # ファイル名1列
            if item:
                path_data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(path_data, tuple) and len(path_data) == 2 and path_data[0]:
                    paths.append(path_data[0])
        return paths

    def get_current_selection_paths(self):
        """現在アクティブなタブで選択されているアイテムに関連するパスを取得 (プレビュー用)"""
        primary_path = None
        secondary_path = None
        current_index = self.currentIndex()

        if current_index == 0: # ブレ画像タブ
            table = self.blurry_table
            selected_items = table.selectedItems()
            if selected_items:
                row = selected_items[0].row()
                item = table.item(row, 0) # チェックボックス列
                if item:
                    primary_path = item.data(Qt.ItemDataRole.UserRole)
        elif current_index == 1: # 類似ペアタブ
            table = self.similar_table
            selected_items = table.selectedItems()
            if selected_items:
                row = selected_items[0].row()
                item = table.item(row, 0) # ファイル名1列
                if item:
                    path_data = item.data(Qt.ItemDataRole.UserRole)
                    if isinstance(path_data, tuple) and len(path_data) == 2:
                        primary_path, secondary_path = path_data
        # エラータブではパス情報は取得しない (プレビュー対象外)

        return primary_path, secondary_path

    # --- 全選択/解除メソッド ---
    @Slot()
    def select_all_blurry(self):
        """ブレ画像タブの全チェックボックスをオンにする"""
        self.setCurrentIndex(0) # タブを切り替え
        for row in range(self.blurry_table.rowCount()):
            item = self.blurry_table.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Checked)

    @Slot()
    def select_all_similar(self):
        """類似ペアタブの全行を選択する"""
        self.setCurrentIndex(1) # タブを切り替え
        self.similar_table.selectAll()

    @Slot()
    def deselect_all(self):
        """すべてのタブの選択状態を解除する"""
        # ブレ画像のチェック解除
        for row in range(self.blurry_table.rowCount()):
            item = self.blurry_table.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Unchecked)
        # 類似ペアの選択解除
        self.similar_table.clearSelection()
        # エラーテーブルの選択解除
        self.error_table.clearSelection()
        # 選択解除シグナルを発行 (プレビュークリアのため)
        self.selection_changed.emit()

    # --- テーブルから削除された項目を反映するメソッド ---
    def remove_items_by_paths(self, deleted_paths_set):
        """指定されたパスセットに一致する項目をテーブルから削除"""
        if not deleted_paths_set:
            return

        # ブレ画像テーブル
        rows_to_remove_blurry = []
        for row in range(self.blurry_table.rowCount()):
            chk_item = self.blurry_table.item(row, 0)
            if chk_item:
                path = chk_item.data(Qt.ItemDataRole.UserRole)
                if path and os.path.normpath(path) in deleted_paths_set:
                    rows_to_remove_blurry.append(row)
        for row in sorted(rows_to_remove_blurry, reverse=True):
            self.blurry_table.removeRow(row)

        # 類似ペアテーブル
        rows_to_remove_similar = []
        for row in range(self.similar_table.rowCount()):
            item = self.similar_table.item(row, 0)
            if item:
                path_data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(path_data, tuple) and len(path_data) == 2:
                    p1, p2 = path_data
                    p1_norm = os.path.normpath(p1) if p1 else None
                    p2_norm = os.path.normpath(p2) if p2 else None
                    if (p1_norm and p1_norm in deleted_paths_set) or \
                       (p2_norm and p2_norm in deleted_paths_set):
                        rows_to_remove_similar.append(row)
        for row in sorted(list(set(rows_to_remove_similar)), reverse=True):
            self.similar_table.removeRow(row)

        # エラーテーブル (元のパス情報があれば削除可能)
        rows_to_remove_error = []
        for row in range(self.error_table.rowCount()):
            item = self.error_table.item(row, 1) # ファイル/ペア列
            if item:
                err_data = item.data(Qt.ItemDataRole.UserRole) # UserRoleにエラー辞書を格納想定
                if isinstance(err_data, dict):
                    remove_flag = False
                    # ブレ検出エラーの場合
                    if err_data.get('type') == 'ブレ検出' and 'path' in err_data:
                        err_path_norm = os.path.normpath(err_data['path']) if err_data['path'] else None
                        if err_path_norm and err_path_norm in deleted_paths_set:
                            remove_flag = True
                    # 類似度比較エラーの場合
                    elif err_data.get('type') == '類似度比較' and ('path1' in err_data or 'path2' in err_data):
                        p1_norm = os.path.normpath(err_data['path1']) if err_data.get('path1') else None
                        p2_norm = os.path.normpath(err_data['path2']) if err_data.get('path2') else None
                        if (p1_norm and p1_norm in deleted_paths_set) or \
                           (p2_norm and p2_norm in deleted_paths_set):
                            remove_flag = True
                    if remove_flag:
                        rows_to_remove_error.append(row)

        for row in sorted(rows_to_remove_error, reverse=True):
            self.error_table.removeRow(row)


        # タブの件数表示を更新
        self.setTabText(0, f"ブレ画像 ({self.blurry_table.rowCount()})")
        self.setTabText(1, f"類似ペア ({self.similar_table.rowCount()})")
        self.setTabText(2, f"エラー ({self.error_table.rowCount()})")
