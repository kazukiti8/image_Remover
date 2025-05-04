# gui/widgets/results_tabs_widget.py
import os
from PySide6.QtWidgets import (QWidget, QTabWidget, QTableWidget, QHeaderView,
                               QAbstractItemView, QTableWidgetItem, QMenu,
                               QStyledItemDelegate, QStyleOptionViewItem)
from PySide6.QtCore import Qt, Signal, Slot, QPoint, QModelIndex
from PySide6.QtGui import QAction, QColor
from typing import List, Dict, Tuple, Optional, Any, Union, Set # ★ typing をインポート ★

# ★★★ 修正点: 型エイリアスをクラス定義の前に移動 ★★★
BlurResultItem = Dict[str, Union[str, float]]
SimilarPair = List[Union[str, int]] # [path1: str, path2: str, score: int]
DuplicateDict = Dict[str, List[str]] # {hash: [path1, path2, ...]}
ErrorDict = Dict[str, str] # {'type': str, 'path': str, 'error': str, ...}
# ResultsData 型: get_results_data の戻り値の型
ResultsData = Dict[
    str,
    Union[List[BlurResultItem], List[SimilarPair], DuplicateDict, List[ErrorDict]]
]
SelectionPaths = Tuple[Optional[str], Optional[str]] # (primary_path, secondary_path)
FileInfoResult = Tuple[str, str, str] # file_operations からの戻り値型 (仮)
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

# カスタムテーブルアイテムをインポート
try:
    from .table_items import (NumericTableWidgetItem, FileSizeTableWidgetItem,
                             DateTimeTableWidgetItem, ResolutionTableWidgetItem)
except ImportError:
    print("エラー: table_items モジュールのインポートに失敗しました。")
    NumericTableWidgetItem = QTableWidgetItem; FileSizeTableWidgetItem = QTableWidgetItem
    DateTimeTableWidgetItem = QTableWidgetItem; ResolutionTableWidgetItem = QTableWidgetItem

# ファイル情報取得関数をインポート
try:
    from utils.file_operations import get_file_info
except ImportError:
    print("エラー: utils.file_operations モジュールのインポートに失敗しました。")
    def get_file_info(fp: str) -> FileInfoResult: return "N/A", "N/A", "N/A"


class AlternatingRowColorDelegate(QStyledItemDelegate):
    """テーブルの行の背景色を交互に変えるデリゲート"""
    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        super().initStyleOption(option, index)
        if index.row() % 2 == 0:
            option.backgroundBrush = QColor(Qt.GlobalColor.lightGray).lighter(130)


class ResultsTabsWidget(QTabWidget):
    """結果表示用のタブウィジェット"""
    selection_changed = Signal()
    delete_file_requested = Signal(str)
    open_file_requested = Signal(str)
    delete_duplicates_requested = Signal(str, list) # keep_path: str, delete_paths: List[str]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.blurry_table: QTableWidget
        self.similar_table: QTableWidget
        self.duplicate_table: QTableWidget
        self.error_table: QTableWidget
        self._setup_tabs()

    def _setup_tabs(self) -> None:
        """タブとテーブルを作成し、シグナルを接続する"""
        self.blurry_table = self._create_blurry_table(); self.addTab(self.blurry_table, "ブレ画像 (0)")
        self.similar_table = self._create_similar_table(); self.similar_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.similar_table.customContextMenuRequested.connect(self._show_similar_table_context_menu); self.addTab(self.similar_table, "類似ペア (0)")
        self.duplicate_table = self._create_duplicate_table(); self.duplicate_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.duplicate_table.customContextMenuRequested.connect(self._show_duplicate_table_context_menu); self.addTab(self.duplicate_table, "重複ファイル (0)")
        self.error_table = self._create_error_table(); self.addTab(self.error_table, "エラー (0)")
        self.blurry_table.itemSelectionChanged.connect(self.selection_changed.emit); self.similar_table.itemSelectionChanged.connect(self.selection_changed.emit); self.duplicate_table.itemSelectionChanged.connect(self.selection_changed.emit); self.error_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.currentChanged.connect(lambda index: self.selection_changed.emit())

    def _create_table_widget(self, column_count: int, headers: List[str], selection_mode: QAbstractItemView.SelectionMode, sorting_enabled: bool = True) -> QTableWidget:
        table = QTableWidget(); table.setColumnCount(column_count); table.setHorizontalHeaderLabels(headers); table.verticalHeader().setVisible(False); table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); table.setSelectionMode(selection_mode); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); table.setSortingEnabled(sorting_enabled)
        return table
    def _create_blurry_table(self) -> QTableWidget:
        headers = ["", "ファイル名", "サイズ", "更新日時", "解像度", "ブレ度スコア", "パス"]; table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch); table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        return table
    def _create_similar_table(self) -> QTableWidget:
        headers = ["ファイル名1", "サイズ1", "日時1", "解像度1", "ファイル名2", "類似度(%)", "パス1"]; table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch); table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch); table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        return table
    def _create_duplicate_table(self) -> QTableWidget:
        headers = ["", "ファイル名", "サイズ", "更新日時", "グループID", "パス"]; table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch); table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        return table
    def _create_error_table(self) -> QTableWidget:
        headers = ["タイプ", "ファイル/ペア", "エラー内容"]; table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.SingleSelection, sorting_enabled=True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch); table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        return table

    # --- データ投入メソッド ---
    @Slot(list, list, dict, list)
    def populate_results(self, blurry_results: List[BlurResultItem], similar_results: List[SimilarPair], duplicate_results: DuplicateDict, scan_errors: List[ErrorDict]) -> None:
        self._populate_blurry_table(blurry_results); self._populate_similar_table(similar_results); self._populate_duplicate_table(duplicate_results); self._populate_error_table(scan_errors)
        self.setTabText(0, f"ブレ画像 ({self.blurry_table.rowCount()})"); self.setTabText(1, f"類似ペア ({self.similar_table.rowCount()})"); self.setTabText(2, f"重複ファイル ({self.duplicate_table.rowCount()})"); self.setTabText(3, f"エラー ({self.error_table.rowCount()})")

    def _populate_blurry_table(self, blurry_results: List[BlurResultItem]) -> None:
        self.blurry_table.setSortingEnabled(False); self.blurry_table.setRowCount(len(blurry_results))
        row: int; data: BlurResultItem
        for row, data in enumerate(blurry_results):
            path: str = data['path']; score: float = float(data['score'])
            file_size: str; mod_time: str; dimensions: str; file_size, mod_time, dimensions = get_file_info(path)
            chk_item = QTableWidgetItem(); chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled); chk_item.setCheckState(Qt.CheckState.Unchecked); chk_item.setData(Qt.ItemDataRole.UserRole, path)
            name_item = QTableWidgetItem(os.path.basename(path)); size_item = FileSizeTableWidgetItem(file_size); date_item = DateTimeTableWidgetItem(mod_time); dim_item = ResolutionTableWidgetItem(dimensions); score_item = NumericTableWidgetItem(f"{score:.4f}"); score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); path_item = QTableWidgetItem(path)
            self.blurry_table.setItem(row, 0, chk_item); self.blurry_table.setItem(row, 1, name_item); self.blurry_table.setItem(row, 2, size_item); self.blurry_table.setItem(row, 3, date_item); self.blurry_table.setItem(row, 4, dim_item); self.blurry_table.setItem(row, 5, score_item); self.blurry_table.setItem(row, 6, path_item)
        self.blurry_table.setSortingEnabled(True)
    def _populate_similar_table(self, similar_results: List[SimilarPair]) -> None:
        self.similar_table.setSortingEnabled(False); self.similar_table.setRowCount(len(similar_results))
        row: int; path1: str; path2: str; score: int
        for row, (path1, path2, score) in enumerate(similar_results):
            file_size1: str; mod_time1: str; dimensions1: str; file_size1, mod_time1, dimensions1 = get_file_info(path1)
            name1_item = QTableWidgetItem(os.path.basename(path1)); name1_item.setData(Qt.ItemDataRole.UserRole, (path1, path2))
            size1_item = FileSizeTableWidgetItem(file_size1); date1_item = DateTimeTableWidgetItem(mod_time1); dim1_item = ResolutionTableWidgetItem(dimensions1); name2_item = QTableWidgetItem(os.path.basename(path2)); score_item = NumericTableWidgetItem(str(score)); score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); path1_item = QTableWidgetItem(path1)
            self.similar_table.setItem(row, 0, name1_item); self.similar_table.setItem(row, 1, size1_item); self.similar_table.setItem(row, 2, date1_item); self.similar_table.setItem(row, 3, dim1_item); self.similar_table.setItem(row, 4, name2_item); self.similar_table.setItem(row, 5, score_item); self.similar_table.setItem(row, 6, path1_item)
        self.similar_table.setSortingEnabled(True)
    def _populate_duplicate_table(self, duplicate_results: DuplicateDict) -> None:
        self.duplicate_table.setSortingEnabled(False); self.duplicate_table.setRowCount(0); current_row: int = 0; group_id_counter: int = 1
        group_hash: str; paths: List[str]
        for group_hash, paths in duplicate_results.items():
            if len(paths) < 2: continue
            display_group_id: str = f"G{group_id_counter}"
            i: int; path: str
            for i, path in enumerate(paths):
                file_size: str; mod_time: str; dimensions: str; file_size, mod_time, dimensions = get_file_info(path)
                chk_item = QTableWidgetItem(); chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled); chk_item.setCheckState(Qt.CheckState.Checked if i > 0 else Qt.CheckState.Unchecked); chk_item.setData(Qt.ItemDataRole.UserRole, {'path': path, 'group_hash': group_hash})
                name_item = QTableWidgetItem(os.path.basename(path)); size_item = FileSizeTableWidgetItem(file_size); date_item = DateTimeTableWidgetItem(mod_time); group_item = QTableWidgetItem(display_group_id); group_item.setData(Qt.ItemDataRole.UserRole+1, group_hash); path_item = QTableWidgetItem(path)
                self.duplicate_table.insertRow(current_row); self.duplicate_table.setItem(current_row, 0, chk_item); self.duplicate_table.setItem(current_row, 1, name_item); self.duplicate_table.setItem(current_row, 2, size_item); self.duplicate_table.setItem(current_row, 3, date_item); self.duplicate_table.setItem(current_row, 4, group_item); self.duplicate_table.setItem(current_row, 5, path_item); current_row += 1
            group_id_counter += 1
        self.duplicate_table.setSortingEnabled(True)
    def _populate_error_table(self, scan_errors: List[ErrorDict]) -> None:
        self.error_table.setSortingEnabled(False); self.error_table.setRowCount(len(scan_errors))
        row: int; err_data: ErrorDict
        for row, err_data in enumerate(scan_errors):
            err_type: str = err_data.get('type', '不明'); path_display: str = err_data.get('path', 'N/A'); error_msg: str = err_data.get('error', '詳細不明')
            type_item = QTableWidgetItem(err_type); path_item = QTableWidgetItem(path_display); path_item.setData(Qt.ItemDataRole.UserRole, err_data); msg_item = QTableWidgetItem(error_msg); msg_item.setToolTip(error_msg)
            self.error_table.setItem(row, 0, type_item); self.error_table.setItem(row, 1, path_item); self.error_table.setItem(row, 2, msg_item)
        self.error_table.setSortingEnabled(True)

    @Slot()
    def clear_results(self) -> None:
        self.blurry_table.setRowCount(0); self.similar_table.setRowCount(0); self.duplicate_table.setRowCount(0); self.error_table.setRowCount(0)
        self.setTabText(0, "ブレ画像 (0)"); self.setTabText(1, "類似ペア (0)"); self.setTabText(2, "重複ファイル (0)"); self.setTabText(3, "エラー (0)")

    # --- 選択状態取得メソッド ---
    def get_selected_blurry_paths(self) -> List[str]:
        paths: List[str] = []; row: int
        for row in range(self.blurry_table.rowCount()): chk_item = self.blurry_table.item(row, 0); path: Optional[str] = chk_item.data(Qt.ItemDataRole.UserRole) if chk_item and chk_item.checkState() == Qt.CheckState.Checked else None; path and paths.append(path)
        return paths
    def get_selected_similar_primary_paths(self) -> List[str]:
        paths: List[str] = []; selected_rows: Set[int] = set(item.row() for item in self.similar_table.selectedItems()); row: int
        for row in selected_rows: item = self.similar_table.item(row, 0); path_data: Any = item.data(Qt.ItemDataRole.UserRole) if item else None; isinstance(path_data, tuple) and len(path_data) == 2 and path_data[0] and paths.append(path_data[0])
        return paths
    def get_selected_duplicate_paths(self) -> List[str]:
        paths: List[str] = []; row: int
        for row in range(self.duplicate_table.rowCount()): chk_item = self.duplicate_table.item(row, 0); data: Any = chk_item.data(Qt.ItemDataRole.UserRole) if chk_item and chk_item.checkState() == Qt.CheckState.Checked else None; isinstance(data, dict) and 'path' in data and paths.append(data['path'])
        return paths
    def get_current_selection_paths(self) -> SelectionPaths:
        primary_path: Optional[str] = None; secondary_path: Optional[str] = None; current_index: int = self.currentIndex()
        table: QTableWidget; selected_items: List[QTableWidgetItem]; row: int; item: Optional[QTableWidgetItem]
        if current_index == 0: table = self.blurry_table; selected_items = table.selectedItems(); row = selected_items[0].row() if selected_items else -1; item = table.item(row, 0) if row != -1 else None; primary_path = item.data(Qt.ItemDataRole.UserRole) if item else None
        elif current_index == 1: table = self.similar_table; selected_items = table.selectedItems(); row = selected_items[0].row() if selected_items else -1; item = table.item(row, 0) if row != -1 else None; path_data: Any = item.data(Qt.ItemDataRole.UserRole) if item else None; isinstance(path_data, tuple) and len(path_data) == 2 and (primary_path := path_data[0], secondary_path := path_data[1])
        elif current_index == 2: table = self.duplicate_table; selected_items = table.selectedItems(); row = selected_items[0].row() if selected_items else -1; item = table.item(row, 0) if row != -1 else None; data: Any = item.data(Qt.ItemDataRole.UserRole) if item else None; isinstance(data, dict) and 'path' in data and (primary_path := data['path'])
        return primary_path, secondary_path

    # --- 全選択/解除メソッド ---
    @Slot()
    def select_all_blurry(self) -> None: self.setCurrentIndex(0); [item.setCheckState(Qt.CheckState.Checked) for row in range(self.blurry_table.rowCount()) if (item := self.blurry_table.item(row, 0)) and item.flags() & Qt.ItemFlag.ItemIsUserCheckable]
    @Slot()
    def select_all_similar(self) -> None: self.setCurrentIndex(1); self.similar_table.selectAll()
    @Slot()
    def select_all_duplicates(self) -> None:
        self.setCurrentIndex(2); current_group_hash: Optional[str] = None; is_first_in_group: bool = True; row: int
        for row in range(self.duplicate_table.rowCount()):
            chk_item: Optional[QTableWidgetItem] = self.duplicate_table.item(row, 0); group_item: Optional[QTableWidgetItem] = self.duplicate_table.item(row, 4)
            if chk_item and group_item and chk_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                data: Any = chk_item.data(Qt.ItemDataRole.UserRole); group_hash: Optional[str] = data.get('group_hash') if isinstance(data, dict) else None
                if group_hash != current_group_hash: current_group_hash = group_hash; is_first_in_group = True
                else: is_first_in_group = False
                chk_item.setCheckState(Qt.CheckState.Checked if not is_first_in_group else Qt.CheckState.Unchecked)
    @Slot()
    def deselect_all(self) -> None:
        row: int; item: Optional[QTableWidgetItem]
        for row in range(self.blurry_table.rowCount()): item = self.blurry_table.item(row, 0); item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable and item.setCheckState(Qt.CheckState.Unchecked)
        self.similar_table.clearSelection()
        for row in range(self.duplicate_table.rowCount()): item = self.duplicate_table.item(row, 0); item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable and item.setCheckState(Qt.CheckState.Unchecked)
        self.error_table.clearSelection(); self.selection_changed.emit()

    # --- テーブルから削除された項目を反映するメソッド ---
    def remove_items_by_paths(self, deleted_paths_set: Set[str]) -> None: # 引数の型を Set[str] に
        if not deleted_paths_set: return
        row: int; item: Optional[QTableWidgetItem]; path: Optional[str]; path_data: Any; data: Any; err_data: Any; p1n: Optional[str]; p2n: Optional[str]; err_path_norm: Optional[str]; et: Optional[str]; ep: Optional[str]
        rows_to_remove_blurry: List[int] = [row for row in range(self.blurry_table.rowCount()) if (item := self.blurry_table.item(row, 0)) and (path := item.data(Qt.ItemDataRole.UserRole)) and os.path.normpath(path) in deleted_paths_set]; [self.blurry_table.removeRow(row) for row in sorted(rows_to_remove_blurry, reverse=True)]
        rows_to_remove_similar: List[int] = [row for row in range(self.similar_table.rowCount()) if (item := self.similar_table.item(row, 0)) and (path_data := item.data(Qt.ItemDataRole.UserRole)) and isinstance(path_data, tuple) and len(path_data) == 2 and ((p1n := os.path.normpath(path_data[0]) if path_data[0] else None) and p1n in deleted_paths_set or (p2n := os.path.normpath(path_data[1]) if path_data[1] else None) and p2n in deleted_paths_set)]; [self.similar_table.removeRow(row) for row in sorted(list(set(rows_to_remove_similar)), reverse=True)]
        rows_to_remove_duplicate: List[int] = [row for row in range(self.duplicate_table.rowCount()) if (item := self.duplicate_table.item(row, 0)) and (data := item.data(Qt.ItemDataRole.UserRole)) and isinstance(data, dict) and (path := data.get('path')) and os.path.normpath(path) in deleted_paths_set]; [self.duplicate_table.removeRow(row) for row in sorted(rows_to_remove_duplicate, reverse=True)]
        rows_to_remove_error: List[int] = [row for row in range(self.error_table.rowCount()) if (item := self.error_table.item(row, 1)) and (err_data := item.data(Qt.ItemDataRole.UserRole)) and isinstance(err_data, dict) and (((et := err_data.get('type')) in ['ブレ検出', 'pHash計算', 'ファイル読込/ハッシュ計算', 'ファイルサイズ取得'] and (ep := err_data.get('path')) and os.path.normpath(ep) in deleted_paths_set) or (et in ['ORB比較', 'pHash比較'] and ((p1n := os.path.normpath(err_data['path1']) if err_data.get('path1') else None) and p1n in deleted_paths_set or (p2n := os.path.normpath(err_data['path2']) if err_data.get('path2') else None) and p2n in deleted_paths_set)))]; [self.error_table.removeRow(row) for row in sorted(rows_to_remove_error, reverse=True)]
        self.setTabText(0, f"ブレ画像 ({self.blurry_table.rowCount()})"); self.setTabText(1, f"類似ペア ({self.similar_table.rowCount()})"); self.setTabText(2, f"重複ファイル ({self.duplicate_table.rowCount()})"); self.setTabText(3, f"エラー ({self.error_table.rowCount()})")

    # --- コンテキストメニュー処理 ---
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
        group_paths: List[str] = [d.get('path') for r in range(self.duplicate_table.rowCount()) if (item0 := self.duplicate_table.item(r, 0)) and (d := item0.data(Qt.ItemDataRole.UserRole)) and isinstance(d, dict) and d.get('group_hash') == group_hash and d.get('path')]
        context_menu = QMenu(self); action_delete_this = QAction(f"このファイルを削除 ({base_name})", self); action_keep_this = QAction(f"これ以外を削除 ({len(group_paths)-1}個)", self); action_open_this = QAction(f"このファイルを開く ({base_name})", self)
        action_delete_this.setEnabled(bool(clicked_path and os.path.exists(clicked_path))); action_keep_this.setEnabled(len(group_paths) > 1); action_open_this.setEnabled(bool(clicked_path and os.path.exists(clicked_path)))
        if clicked_path: action_delete_this.triggered.connect(lambda checked=False, p=clicked_path: self.delete_file_requested.emit(p)); action_open_this.triggered.connect(lambda checked=False, p=clicked_path: self.open_file_requested.emit(p))
        if len(group_paths) > 1: paths_to_delete: List[str] = [p for p in group_paths if p != clicked_path]; action_keep_this.triggered.connect(lambda checked=False, keep=clicked_path, delete_list=paths_to_delete: self.delete_duplicates_requested.emit(keep, delete_list))
        context_menu.addAction(action_delete_this); context_menu.addAction(action_keep_this); context_menu.addSeparator(); context_menu.addAction(action_open_this)
        context_menu.exec(self.duplicate_table.mapToGlobal(pos))

    # ★★★ データ取得メソッドを追加 ★★★
    def get_results_data(self) -> ResultsData: # 戻り値の型ヒント
        """現在のテーブルデータを辞書形式で取得する"""
        blurry_data: List[BlurResultItem] = []
        row: int
        for row in range(self.blurry_table.rowCount()):
            chk_item: Optional[QTableWidgetItem] = self.blurry_table.item(row, 0)
            score_item: Optional[QTableWidgetItem] = self.blurry_table.item(row, 5)
            if chk_item and score_item:
                path: Optional[str] = chk_item.data(Qt.ItemDataRole.UserRole)
                try: score: float = float(score_item.text())
                except (ValueError, TypeError): print(f"警告: ブレテーブルスコア変換エラー (行 {row})"); continue
                if path: blurry_data.append({'path': path, 'score': score})

        similar_data: List[SimilarPair] = []
        for row in range(self.similar_table.rowCount()):
            item: Optional[QTableWidgetItem] = self.similar_table.item(row, 0)
            score_item: Optional[QTableWidgetItem] = self.similar_table.item(row, 5)
            if item and score_item:
                path_data: Any = item.data(Qt.ItemDataRole.UserRole)
                try: score: int = int(score_item.text())
                except (ValueError, TypeError): print(f"警告: 類似ペアスコア変換エラー (行 {row})"); continue
                if isinstance(path_data, tuple) and len(path_data) == 2:
                    similar_data.append([str(path_data[0]), str(path_data[1]), score])

        duplicate_data: DuplicateDict = {}
        for row in range(self.duplicate_table.rowCount()):
            chk_item: Optional[QTableWidgetItem] = self.duplicate_table.item(row, 0)
            if chk_item:
                data: Any = chk_item.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, dict) and 'path' in data and 'group_hash' in data:
                    group_hash: str = data['group_hash']; path: str = data['path']
                    if group_hash not in duplicate_data: duplicate_data[group_hash] = []
                    duplicate_data[group_hash].append(path)

        error_data: List[ErrorDict] = []
        for row in range(self.error_table.rowCount()):
            item: Optional[QTableWidgetItem] = self.error_table.item(row, 1)
            if item:
                err_dict: Any = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(err_dict, dict):
                    # 型チェックをより厳密にする場合はここで行う
                    error_data.append(err_dict) # type: ignore

        return {'blurry': blurry_data, 'similar': similar_data, 'duplicates': duplicate_data, 'errors': error_data}

