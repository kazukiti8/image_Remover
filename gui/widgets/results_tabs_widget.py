# gui/widgets/results_tabs_widget.py
import os
from PySide6.QtWidgets import (QWidget, QTabWidget, QTableWidget, QHeaderView,
                               QAbstractItemView, QTableWidgetItem, QMenu,
                               QStyledItemDelegate, QStyleOptionViewItem)
from PySide6.QtCore import Qt, Signal, Slot, QPoint, QModelIndex
from PySide6.QtGui import QAction, QColor
from typing import List, Dict, Tuple, Optional, Any, Union, Set

# 型エイリアス
BlurResultItem = Dict[str, Union[str, float]]
SimilarPair = List[Union[str, int]]
DuplicateDict = Dict[str, List[str]]
ErrorDict = Dict[str, str]
ResultsData = Dict[str, Union[List[BlurResultItem], List[SimilarPair], DuplicateDict, List[ErrorDict]]]
SelectionPaths = Tuple[Optional[str], Optional[str]]
# ★ FileInfoResult の型ヒントを更新 ★
FileInfoResult = Tuple[str, str, str, str] # (size, mod_time, dimensions, exif_date)

# カスタムテーブルアイテムをインポート
try:
    from .table_items import (NumericTableWidgetItem, FileSizeTableWidgetItem,
                             DateTimeTableWidgetItem, ResolutionTableWidgetItem,
                             ExifDateTimeTableWidgetItem) # ★ ExifDateTimeTableWidgetItem をインポート ★
except ImportError:
    print("エラー: table_items モジュールのインポートに失敗しました。")
    NumericTableWidgetItem = QTableWidgetItem; FileSizeTableWidgetItem = QTableWidgetItem
    DateTimeTableWidgetItem = QTableWidgetItem; ResolutionTableWidgetItem = QTableWidgetItem
    ExifDateTimeTableWidgetItem = QTableWidgetItem # フォールバック

# ファイル情報取得関数をインポート
try:
    from utils.file_operations import get_file_info
except ImportError:
    print("エラー: utils.file_operations モジュールのインポートに失敗しました。")
    def get_file_info(fp: str) -> FileInfoResult: return "N/A", "N/A", "N/A", "N/A" # ★ 戻り値に N/A を追加 ★


class AlternatingGroupColorDelegate(QStyledItemDelegate):
    """テーブルの行の背景色をグループごとに交互に変えるデリゲート"""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._group_colors: Dict[str, QColor] = {}
        self._color1 = QColor(Qt.GlobalColor.white)
        self._color2 = QColor(Qt.GlobalColor.lightGray).lighter(130)
        self._last_group_hash: Optional[str] = None
        self._last_color_index: int = 0
        self._group_id_column = 5 # ★ グループID列のインデックスを更新 (撮影日時列挿入のため) ★

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        super().initStyleOption(option, index)
        # ★ グループID列のインデックスを self._group_id_column に変更 ★
        group_hash_data: Any = index.model().sibling(index.row(), self._group_id_column, index).data(Qt.ItemDataRole.UserRole+1)
        group_hash: Optional[str] = str(group_hash_data) if group_hash_data is not None else None

        if group_hash:
            if group_hash not in self._group_colors:
                self._last_color_index = 1 - self._last_color_index
                current_color = self._color1 if self._last_color_index == 0 else self._color2
                self._group_colors[group_hash] = current_color
                self._last_group_hash = group_hash
            # QBrush を使う方が推奨される
            option.backgroundBrush = QColor(self._group_colors[group_hash]) # QBrush の代わりに QColor を直接使う (互換性のため)

    def reset_colors(self) -> None:
        """テーブル更新時に色情報をリセットする"""
        self._group_colors = {}
        self._last_group_hash = None
        self._last_color_index = 0

    # ★ グループID列のインデックスを設定するメソッドを追加 ★
    def set_group_id_column(self, column_index: int):
        self._group_id_column = column_index


class ResultsTabsWidget(QTabWidget):
    """結果表示用のタブウィジェット"""
    selection_changed = Signal()
    delete_file_requested = Signal(str)
    open_file_requested = Signal(str)
    delete_duplicates_requested = Signal(str, list)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.blurry_table: QTableWidget
        self.similar_table: QTableWidget
        self.duplicate_table: QTableWidget
        self.error_table: QTableWidget
        self.duplicate_delegate = AlternatingGroupColorDelegate(self)
        self._setup_tabs()

    def _setup_tabs(self) -> None:
        """タブとテーブルを作成し、シグナルを接続する"""
        self.blurry_table = self._create_blurry_table()
        self.addTab(self.blurry_table, "ブレ画像 (0)")

        self.similar_table = self._create_similar_table()
        self.similar_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.similar_table.customContextMenuRequested.connect(self._show_similar_table_context_menu)
        self.addTab(self.similar_table, "類似ペア (0)")

        self.duplicate_table = self._create_duplicate_table()
        self.duplicate_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.duplicate_table.customContextMenuRequested.connect(self._show_duplicate_table_context_menu)
        self.duplicate_table.setItemDelegate(self.duplicate_delegate)
        # ★ デリゲートにグループID列のインデックスを設定 ★
        self.duplicate_delegate.set_group_id_column(5) # "グループID" 列はインデックス 5 になる
        self.addTab(self.duplicate_table, "重複ファイル (0)")

        self.error_table = self._create_error_table()
        self.addTab(self.error_table, "エラー (0)")

        # シグナル接続 (変更なし)
        self.blurry_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.similar_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.duplicate_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.error_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.currentChanged.connect(lambda index: self.selection_changed.emit())

    def _create_table_widget(self, column_count: int, headers: List[str], selection_mode: QAbstractItemView.SelectionMode, sorting_enabled: bool = True) -> QTableWidget:
        table = QTableWidget(); table.setColumnCount(column_count); table.setHorizontalHeaderLabels(headers); table.verticalHeader().setVisible(False); table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); table.setSelectionMode(selection_mode); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); table.setSortingEnabled(sorting_enabled)
        # フォントサイズ調整 (任意)
        # font = table.font(); font.setPointSize(9); table.setFont(font)
        # table.horizontalHeader().setFont(font)
        return table

    def _create_blurry_table(self) -> QTableWidget:
        # ★ ヘッダーに「撮影日時」を追加 ★
        headers = ["", "ファイル名", "サイズ", "更新日時", "撮影日時", "解像度", "ブレ度スコア", "パス"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        # リサイズモード設定 (インデックス調整)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # Checkbox
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # Filename
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Size
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Mod Time
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Exif Date ★
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # Resolution
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents) # Score
        table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)          # Path
        return table

    def _create_similar_table(self) -> QTableWidget:
        # ★ ヘッダーに「撮影日時1」を追加 ★
        headers = ["ファイル名1", "サイズ1", "更新日時1", "撮影日時1", "解像度1", "ファイル名2", "類似度(%)", "パス1"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        # リサイズモード設定 (インデックス調整)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)          # Filename1
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # Size1
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Mod Time 1
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Exif Date 1 ★
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Resolution 1
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)          # Filename2
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents) # Score
        table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)          # Path1
        return table

    def _create_duplicate_table(self) -> QTableWidget:
        # ★ ヘッダーに「撮影日時」を追加 ★
        headers = ["", "ファイル名", "サイズ", "更新日時", "撮影日時", "グループID", "パス"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        # リサイズモード設定 (インデックス調整)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # Checkbox
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # Filename
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Size
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Mod Time
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Exif Date ★
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # Group ID
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)          # Path
        return table

    def _create_error_table(self) -> QTableWidget:
        # エラーテーブルは変更なし
        headers = ["タイプ", "ファイル/ペア", "エラー内容"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.SingleSelection, sorting_enabled=True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        return table

    # --- データ投入メソッド ---
    @Slot(list, list, dict, list)
    def populate_results(self, blurry_results: List[BlurResultItem], similar_results: List[SimilarPair], duplicate_results: DuplicateDict, scan_errors: List[ErrorDict]) -> None:
        self.duplicate_delegate.reset_colors()
        self._populate_table(self.blurry_table, blurry_results, self._create_blurry_row_items)
        self._populate_table(self.similar_table, similar_results, self._create_similar_row_items)
        self._populate_table(self.duplicate_table, self._flatten_duplicates(duplicate_results), self._create_duplicate_row_items)
        self._populate_table(self.error_table, scan_errors, self._create_error_row_items)
        self._update_tab_texts()

    def _populate_table(self, table: QTableWidget, data: List[Any], item_creator_func) -> None:
        table.setSortingEnabled(False)
        table.setRowCount(len(data))
        for row, row_data in enumerate(data):
            items: List[QTableWidgetItem] = item_creator_func(row_data)
            for col, item in enumerate(items):
                table.setItem(row, col, item)
        table.setSortingEnabled(True)
        # table.resizeColumnsToContents() # 必要であれば

    def _create_blurry_row_items(self, data: BlurResultItem) -> List[QTableWidgetItem]:
        path: str = data['path']
        score: float = float(data['score']) # スコアは必須とする
        # ★ get_file_info の戻り値に exif_date を追加 ★
        file_size, mod_time, dimensions, exif_date = get_file_info(path)
        chk_item = QTableWidgetItem()
        chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk_item.setCheckState(Qt.CheckState.Unchecked)
        chk_item.setData(Qt.ItemDataRole.UserRole, path)
        name_item = QTableWidgetItem(os.path.basename(path))
        size_item = FileSizeTableWidgetItem(file_size)
        mod_date_item = DateTimeTableWidgetItem(mod_time)
        # ★ Exif日時アイテムを追加 ★
        exif_date_item = ExifDateTimeTableWidgetItem(exif_date)
        dim_item = ResolutionTableWidgetItem(dimensions)
        score_item = NumericTableWidgetItem(f"{score:.4f}") # ブレ画像はスコア表示
        score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        path_item = QTableWidgetItem(path)
        # ★ リストに exif_date_item を追加 ★
        return [chk_item, name_item, size_item, mod_date_item, exif_date_item, dim_item, score_item, path_item]

    def _create_similar_row_items(self, data: SimilarPair) -> List[QTableWidgetItem]:
        path1: str = str(data[0])
        path2: str = str(data[1])
        score: int = int(data[2]) # スコアは pHash距離 or ORBマッチ数
        # ★ get_file_info の戻り値に exif_date を追加 ★
        file_size1, mod_time1, dimensions1, exif_date1 = get_file_info(path1)
        # ファイル2の情報は表示しない（必要なら追加）
        # file_size2, mod_time2, dimensions2, exif_date2 = get_file_info(path2)

        name1_item = QTableWidgetItem(os.path.basename(path1))
        # UserRole には両方のパスを保持
        name1_item.setData(Qt.ItemDataRole.UserRole, (path1, path2))
        size1_item = FileSizeTableWidgetItem(file_size1)
        mod_date1_item = DateTimeTableWidgetItem(mod_time1)
        # ★ Exif日時アイテムを追加 ★
        exif_date1_item = ExifDateTimeTableWidgetItem(exif_date1)
        dim1_item = ResolutionTableWidgetItem(dimensions1)
        name2_item = QTableWidgetItem(os.path.basename(path2))
        score_item = NumericTableWidgetItem(str(score)) # スコア表示
        score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        path1_item = QTableWidgetItem(path1) # パス1のみ表示
        # ★ リストに exif_date1_item を追加 ★
        return [name1_item, size1_item, mod_date1_item, exif_date1_item, dim1_item, name2_item, score_item, path1_item]

    def _flatten_duplicates(self, duplicate_results: DuplicateDict) -> List[Dict[str, Any]]:
        # 変更なし
        flat_list: List[Dict[str, Any]] = []
        group_id_counter: int = 1
        sorted_groups = sorted(duplicate_results.items(), key=lambda item: item[1][0] if item[1] else "")
        for group_hash, paths in sorted_groups:
            if len(paths) < 2: continue
            display_group_id: str = f"G{group_id_counter}"
            sorted_paths = sorted(paths)
            for i, path in enumerate(sorted_paths):
                flat_list.append({'path': path, 'group_hash': group_hash, 'display_group_id': display_group_id, 'is_first': i == 0})
            group_id_counter += 1
        return flat_list

    def _create_duplicate_row_items(self, data: Dict[str, Any]) -> List[QTableWidgetItem]:
        path: str = data['path']
        group_hash: str = data['group_hash']
        display_group_id: str = data['display_group_id']
        is_first: bool = data['is_first']
        # ★ get_file_info の戻り値に exif_date を追加 ★
        file_size, mod_time, dimensions, exif_date = get_file_info(path)
        chk_item = QTableWidgetItem()
        chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk_item.setCheckState(Qt.CheckState.Unchecked if is_first else Qt.CheckState.Checked)
        chk_item.setData(Qt.ItemDataRole.UserRole, {'path': path, 'group_hash': group_hash})
        name_item = QTableWidgetItem(os.path.basename(path))
        size_item = FileSizeTableWidgetItem(file_size)
        mod_date_item = DateTimeTableWidgetItem(mod_time)
        # ★ Exif日時アイテムを追加 ★
        exif_date_item = ExifDateTimeTableWidgetItem(exif_date)
        group_item = QTableWidgetItem(display_group_id)
        group_item.setData(Qt.ItemDataRole.UserRole+1, group_hash) # グループ識別のためのデータ
        path_item = QTableWidgetItem(path)
        # ★ リストに exif_date_item を追加 ★
        return [chk_item, name_item, size_item, mod_date_item, exif_date_item, group_item, path_item]

    def _create_error_row_items(self, data: ErrorDict) -> List[QTableWidgetItem]:
        # 変更なし
        err_type: str = data.get('type', '不明')
        path_display: str = data.get('path', 'N/A')
        error_msg: str = data.get('error', '詳細不明')
        type_item = QTableWidgetItem(err_type)
        path_item = QTableWidgetItem(path_display)
        path_item.setData(Qt.ItemDataRole.UserRole, data) # エラー詳細を保持
        msg_item = QTableWidgetItem(error_msg)
        msg_item.setToolTip(error_msg) # ツールチップで全文表示
        return [type_item, path_item, msg_item]

    def _update_tab_texts(self) -> None:
        # 変更なし
        self.setTabText(0, f"ブレ画像 ({self.blurry_table.rowCount()})")
        self.setTabText(1, f"類似ペア ({self.similar_table.rowCount()})")
        self.setTabText(2, f"重複ファイル ({self.duplicate_table.rowCount()})")
        self.setTabText(3, f"エラー ({self.error_table.rowCount()})")

    @Slot()
    def clear_results(self) -> None:
        # 変更なし
        self.blurry_table.setRowCount(0)
        self.similar_table.setRowCount(0)
        self.duplicate_table.setRowCount(0)
        self.error_table.setRowCount(0)
        self._update_tab_texts()
        self.duplicate_delegate.reset_colors()

    # --- 選択状態取得メソッド (変更なし) ---
    def get_selected_blurry_paths(self) -> List[str]:
        paths: List[str] = []
        for row in range(self.blurry_table.rowCount()):
            chk_item = self.blurry_table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                path: Optional[str] = chk_item.data(Qt.ItemDataRole.UserRole)
                if path: paths.append(path)
        return paths
    def get_selected_similar_primary_paths(self) -> List[str]:
        paths: List[str] = []
        selected_rows: Set[int] = set(item.row() for item in self.similar_table.selectedItems())
        for row in selected_rows:
            item = self.similar_table.item(row, 0)
            path_data: Any = item.data(Qt.ItemDataRole.UserRole) if item else None
            if isinstance(path_data, tuple) and len(path_data) == 2 and path_data[0]:
                paths.append(path_data[0])
        return paths
    def get_selected_duplicate_paths(self) -> List[str]:
        paths: List[str] = []
        for row in range(self.duplicate_table.rowCount()):
            chk_item = self.duplicate_table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                data: Any = chk_item.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, dict) and 'path' in data:
                    paths.append(data['path'])
        return paths
    def get_current_selection_paths(self) -> SelectionPaths:
        # 変更なし
        primary_path: Optional[str] = None; secondary_path: Optional[str] = None
        current_index: int = self.currentIndex()
        table: Optional[QTableWidget] = self.widget(current_index) if isinstance(self.widget(current_index), QTableWidget) else None
        if table is None: return None, None

        selected_items: List[QTableWidgetItem] = table.selectedItems()
        row: int = selected_items[0].row() if selected_items else -1
        if row == -1: return None, None

        if current_index == 0: # Blurry
            item = table.item(row, 0)
            primary_path = item.data(Qt.ItemDataRole.UserRole) if item else None
        elif current_index == 1: # Similar
            item = table.item(row, 0)
            path_data: Any = item.data(Qt.ItemDataRole.UserRole) if item else None
            if isinstance(path_data, tuple) and len(path_data) == 2:
                primary_path, secondary_path = path_data
        elif current_index == 2: # Duplicate
            item = table.item(row, 0)
            data: Any = item.data(Qt.ItemDataRole.UserRole) if item else None
            if isinstance(data, dict) and 'path' in data:
                primary_path = data['path']
        # Error tab selection is not handled here for paths

        return primary_path, secondary_path

    # --- 全選択/解除メソッド (変更なし) ---
    @Slot()
    def select_all_blurry(self) -> None:
        self.setCurrentIndex(0)
        for row in range(self.blurry_table.rowCount()):
            item = self.blurry_table.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Checked)
    @Slot()
    def select_all_similar(self) -> None:
        self.setCurrentIndex(1)
        self.similar_table.selectAll()
    @Slot()
    def select_all_duplicates(self) -> None:
        self.setCurrentIndex(2)
        current_group_hash: Optional[str] = None
        is_first_in_group: bool = True
        for row in range(self.duplicate_table.rowCount()):
            chk_item: Optional[QTableWidgetItem] = self.duplicate_table.item(row, 0)
            # ★ グループID列のインデックスを修正 ★
            group_item: Optional[QTableWidgetItem] = self.duplicate_table.item(row, 5)
            if chk_item and group_item and chk_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                data: Any = chk_item.data(Qt.ItemDataRole.UserRole)
                group_hash: Optional[str] = data.get('group_hash') if isinstance(data, dict) else None
                if group_hash != current_group_hash:
                    current_group_hash = group_hash
                    is_first_in_group = True
                else:
                    is_first_in_group = False
                chk_item.setCheckState(Qt.CheckState.Checked if not is_first_in_group else Qt.CheckState.Unchecked)
    @Slot()
    def deselect_all(self) -> None:
        for row in range(self.blurry_table.rowCount()):
            item = self.blurry_table.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.similar_table.clearSelection()
        for row in range(self.duplicate_table.rowCount()):
            item = self.duplicate_table.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.error_table.clearSelection()
        self.selection_changed.emit()

    # --- テーブルから削除された項目を反映するメソッド (変更なし) ---
    def remove_items_by_paths(self, deleted_paths_set: Set[str]) -> None:
        if not deleted_paths_set: return
        self._remove_items_from_table(self.blurry_table, deleted_paths_set, self._check_blurry_path)
        self._remove_items_from_table(self.similar_table, deleted_paths_set, self._check_similar_paths)
        self._remove_items_from_table(self.duplicate_table, deleted_paths_set, self._check_duplicate_path)
        self._remove_items_from_table(self.error_table, deleted_paths_set, self._check_error_paths)
        self._update_tab_texts()
        self.duplicate_delegate.reset_colors()

    def _remove_items_from_table(self, table: QTableWidget, deleted_paths: Set[str], check_func) -> None:
        rows_to_remove: List[int] = []
        for row in range(table.rowCount()):
            if check_func(table, row, deleted_paths):
                rows_to_remove.append(row)
        for row in sorted(rows_to_remove, reverse=True):
            table.removeRow(row)

    def _check_blurry_path(self, table: QTableWidget, row: int, deleted_paths: Set[str]) -> bool:
        item: Optional[QTableWidgetItem] = table.item(row, 0)
        path: Optional[str] = item.data(Qt.ItemDataRole.UserRole) if item else None
        return bool(path and os.path.normpath(path) in deleted_paths)
    def _check_similar_paths(self, table: QTableWidget, row: int, deleted_paths: Set[str]) -> bool:
        item: Optional[QTableWidgetItem] = table.item(row, 0)
        path_data: Any = item.data(Qt.ItemDataRole.UserRole) if item else None
        if isinstance(path_data, tuple) and len(path_data) == 2:
            p1n: Optional[str] = os.path.normpath(path_data[0]) if path_data[0] else None
            p2n: Optional[str] = os.path.normpath(path_data[1]) if path_data[1] else None
            return bool((p1n and p1n in deleted_paths) or (p2n and p2n in deleted_paths))
        return False
    def _check_duplicate_path(self, table: QTableWidget, row: int, deleted_paths: Set[str]) -> bool:
        item: Optional[QTableWidgetItem] = table.item(row, 0)
        data: Any = item.data(Qt.ItemDataRole.UserRole) if item else None
        if isinstance(data, dict) and 'path' in data:
            path: Optional[str] = data.get('path')
            return bool(path and os.path.normpath(path) in deleted_paths)
        return False
    def _check_error_paths(self, table: QTableWidget, row: int, deleted_paths: Set[str]) -> bool:
        item: Optional[QTableWidgetItem] = table.item(row, 1)
        err_data: Any = item.data(Qt.ItemDataRole.UserRole) if item else None
        if isinstance(err_data, dict):
            et: Optional[str] = err_data.get('type')
            ep: Optional[str] = err_data.get('path')
            ep1: Optional[str] = err_data.get('path1')
            ep2: Optional[str] = err_data.get('path2')
            ep_norm: Optional[str] = os.path.normpath(ep) if ep else None
            p1n: Optional[str] = os.path.normpath(ep1) if ep1 else None
            p2n: Optional[str] = os.path.normpath(ep2) if ep2 else None
            if et and 'ブレ検出' in et and ep_norm and ep_norm in deleted_paths: return True # ブレ検出エラー
            elif et and 'ハッシュ計算' in et and ep_norm and ep_norm in deleted_paths: return True # ハッシュ計算エラー
            elif et and 'ファイルサイズ取得' in et and ep_norm and ep_norm in deleted_paths: return True # サイズ取得エラー
            elif et and ('比較' in et or 'ORB' in et or 'pHash' in et) and ((p1n and p1n in deleted_paths) or (p2n and p2n in deleted_paths)): return True # 比較系エラー
        return False

    # --- コンテキストメニュー処理 (変更なし) ---
    @Slot(QPoint)
    def _show_similar_table_context_menu(self, pos: QPoint) -> None:
        item: Optional[QTableWidgetItem] = self.similar_table.itemAt(pos); row: int = item.row() if item else -1;
        if row == -1: return; data_item: Optional[QTableWidgetItem] = self.similar_table.item(row, 0); path_data: Any = data_item.data(Qt.ItemDataRole.UserRole) if data_item else None
        if not isinstance(path_data, tuple) or len(path_data) != 2: return; path1: Optional[str] = path_data[0]; path2: Optional[str] = path_data[1]; base_name1: str = os.path.basename(path1) if path1 else "N/A"; base_name2: str = os.path.basename(path2) if path2 else "N/A"
        context_menu = QMenu(self); action_delete1 = QAction(f"ファイル1を削除 ({base_name1})", self); action_delete2 = QAction(f"ファイル2を削除 ({base_name2})", self); action_open1 = QAction(f"ファイル1を開く ({base_name1})", self); action_open2 = QAction(f"ファイル2を開く ({base_name2})", self)
        action_delete1.setEnabled(bool(path1 and os.path.exists(path1))); action_delete2.setEnabled(bool(path2 and os.path.exists(path2))); action_open1.setEnabled(bool(path1 and os.path.exists(path1))); action_open2.setEnabled(bool(path2 and os.path.exists(path2)))
        if path1: action_delete1.triggered.connect(lambda checked=False, p=path1: self.delete_file_requested.emit(p)); action_open1.triggered.connect(lambda checked=False, p=path1: self.open_file_requested.emit(p))
        if path2: action_delete2.triggered.connect(lambda checked=False, p=path2: self.delete_file_requested.emit(p)); action_open2.triggered.connect(lambda checked=False, p=path2: self.open_file_requested.emit(p))
        context_menu.addAction(action_delete1); context_menu.addAction(action_delete2); context_menu.addSeparator(); context_menu.addAction(action_open1); context_menu.addAction(action_open2)
        context_menu.exec(self.similar_table.mapToGlobal(pos))

    @Slot(QPoint)
    def _show_duplicate_table_context_menu(self, pos: QPoint) -> None:
        item: Optional[QTableWidgetItem] = self.duplicate_table.itemAt(pos); row: int = item.row() if item else -1
        if row == -1: return; chk_item: Optional[QTableWidgetItem] = self.duplicate_table.item(row, 0); data: Any = chk_item.data(Qt.ItemDataRole.UserRole) if chk_item else None
        if not isinstance(data, dict) or 'path' not in data or 'group_hash' not in data: return; clicked_path: str = data['path']; group_hash: str = data['group_hash']; base_name: str = os.path.basename(clicked_path)
        # ★ グループID列のインデックスを修正 ★
        group_paths: List[str] = [d.get('path') for r in range(self.duplicate_table.rowCount()) if (item0 := self.duplicate_table.item(r, 0)) and (d := item0.data(Qt.ItemDataRole.UserRole)) and isinstance(d, dict) and d.get('group_hash') == group_hash and d.get('path')]
        context_menu = QMenu(self); action_delete_this = QAction(f"このファイルを削除 ({base_name})", self); action_keep_this = QAction(f"これ以外を削除 ({len(group_paths)-1}個)", self); action_open_this = QAction(f"このファイルを開く ({base_name})", self)
        action_delete_this.setEnabled(bool(clicked_path and os.path.exists(clicked_path))); action_keep_this.setEnabled(len(group_paths) > 1); action_open_this.setEnabled(bool(clicked_path and os.path.exists(clicked_path)))
        if clicked_path: action_delete_this.triggered.connect(lambda checked=False, p=clicked_path: self.delete_file_requested.emit(p)); action_open_this.triggered.connect(lambda checked=False, p=clicked_path: self.open_file_requested.emit(p))
        if len(group_paths) > 1: paths_to_delete: List[str] = [p for p in group_paths if p != clicked_path]; action_keep_this.triggered.connect(lambda checked=False, keep=clicked_path, delete_list=paths_to_delete: self.delete_duplicates_requested.emit(keep, delete_list))
        context_menu.addAction(action_delete_this); context_menu.addAction(action_keep_this); context_menu.addSeparator(); context_menu.addAction(action_open_this)
        context_menu.exec(self.duplicate_table.mapToGlobal(pos))

    # --- データ取得メソッド (変更なし) ---
    def get_results_data(self) -> ResultsData:
        """現在のテーブルデータを辞書形式で取得する"""
        return {
            'blurry': self._get_blurry_data(),
            'similar': self._get_similar_data(),
            'duplicates': self._get_duplicate_data(),
            'errors': self._get_error_data()
        }

    def _get_blurry_data(self) -> List[BlurResultItem]:
        """ブレ画像テーブルからデータを取得"""
        data: List[BlurResultItem] = []
        for row in range(self.blurry_table.rowCount()):
            chk_item: Optional[QTableWidgetItem] = self.blurry_table.item(row, 0)
            # ★ スコア列のインデックスを修正 ★
            score_item: Optional[QTableWidgetItem] = self.blurry_table.item(row, 6)
            if chk_item and score_item:
                path: Optional[str] = chk_item.data(Qt.ItemDataRole.UserRole)
                try:
                    score: float = float(score_item.text())
                    if path:
                        data.append({'path': path, 'score': score})
                except (ValueError, TypeError):
                    print(f"警告: ブレテーブルスコア変換エラー (行 {row})")
                    continue
        return data

    def _get_similar_data(self) -> List[SimilarPair]:
        """類似ペアテーブルからデータを取得"""
        data: List[SimilarPair] = []
        for row in range(self.similar_table.rowCount()):
            item: Optional[QTableWidgetItem] = self.similar_table.item(row, 0)
            # ★ スコア列のインデックスを修正 ★
            score_item: Optional[QTableWidgetItem] = self.similar_table.item(row, 6)
            if item and score_item:
                path_data: Any = item.data(Qt.ItemDataRole.UserRole)
                try:
                    score: int = int(score_item.text())
                    if isinstance(path_data, tuple) and len(path_data) == 2:
                        p1 = str(path_data[0]) if path_data[0] else ""
                        p2 = str(path_data[1]) if path_data[1] else ""
                        data.append([p1, p2, score])
                except (ValueError, TypeError):
                     print(f"警告: 類似ペアスコア変換エラー (行 {row})")
                     continue
        return data

    def _get_duplicate_data(self) -> DuplicateDict:
        """重複ファイルテーブルからデータを取得"""
        data: DuplicateDict = {}
        for row in range(self.duplicate_table.rowCount()):
            chk_item: Optional[QTableWidgetItem] = self.duplicate_table.item(row, 0)
            if chk_item:
                item_data: Any = chk_item.data(Qt.ItemDataRole.UserRole)
                if isinstance(item_data, dict) and 'path' in item_data and 'group_hash' in item_data:
                    group_hash: str = item_data['group_hash']
                    path: str = item_data['path']
                    if group_hash not in data: data[group_hash] = []
                    data[group_hash].append(path)
        return data

    def _get_error_data(self) -> List[ErrorDict]:
        """エラーテーブルからデータを取得"""
        data: List[ErrorDict] = []
        for row in range(self.error_table.rowCount()):
            item: Optional[QTableWidgetItem] = self.error_table.item(row, 1) # Path/Pair 列
            if item:
                err_dict: Any = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(err_dict, dict):
                    # 簡単な型変換とキーの存在確認
                    error_data_item: ErrorDict = {
                        'type': str(err_dict.get('type', '不明')),
                        'path': str(err_dict.get('path', err_dict.get('path1', 'N/A'))), # path優先、なければpath1
                        'error': str(err_dict.get('error', '詳細不明'))
                    }
                    # path2 があれば追加 (オプション)
                    if 'path2' in err_dict:
                        error_data_item['path2'] = str(err_dict['path2'])
                    data.append(error_data_item)
        return data

