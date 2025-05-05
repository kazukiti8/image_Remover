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
DuplicatePair = Dict[str, str] # {'path1': str, 'path2': str, 'group_hash': str}
ErrorDict = Dict[str, str]
ResultsData = Dict[str, Union[List[BlurResultItem], List[SimilarPair], DuplicateDict, List[ErrorDict]]]
SelectionPaths = Tuple[Optional[str], Optional[str]]
FileInfoResult = Tuple[str, str, str, str] # (size, mod_time, dimensions, exif_date)

# カスタムテーブルアイテムをインポート
try:
    from .table_items import (NumericTableWidgetItem, FileSizeTableWidgetItem,
                             DateTimeTableWidgetItem, ResolutionTableWidgetItem,
                             ExifDateTimeTableWidgetItem)
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
    # フォールバック関数
    def get_file_info(fp: str) -> FileInfoResult:
        # この関数はファイルが存在する場合のみ呼ばれる想定になる
        try:
            stat_info = os.stat(fp)
            size = stat_info.st_size
            mod_time = datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y/%m/%d %H:%M')
            return f"{size} B", mod_time, "N/A", "N/A" # 簡易情報
        except Exception:
            return "エラー", "エラー", "エラー", "エラー"

class ResultsTabsWidget(QTabWidget):
    """結果表示用のタブウィジェット"""
    selection_changed = Signal()
    delete_file_requested = Signal(str)
    open_file_requested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.blurry_table: QTableWidget
        self.similar_table: QTableWidget
        self.duplicate_table: QTableWidget
        self.error_table: QTableWidget
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
        self.addTab(self.duplicate_table, "重複ペア (0)")

        self.error_table = self._create_error_table()
        self.addTab(self.error_table, "エラー (0)")

        # シグナル接続
        self.blurry_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.similar_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.duplicate_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.error_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.currentChanged.connect(lambda index: self.selection_changed.emit())

    def _create_table_widget(self, column_count: int, headers: List[str], selection_mode: QAbstractItemView.SelectionMode, sorting_enabled: bool = True) -> QTableWidget:
        table = QTableWidget(); table.setColumnCount(column_count); table.setHorizontalHeaderLabels(headers); table.verticalHeader().setVisible(False); table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); table.setSelectionMode(selection_mode); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); table.setSortingEnabled(sorting_enabled)
        return table

    def _create_blurry_table(self) -> QTableWidget:
        headers = ["", "ファイル名", "サイズ", "更新日時", "撮影日時", "解像度", "ブレ度スコア", "パス"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        return table

    def _create_similar_table(self) -> QTableWidget:
        headers = ["ファイル名1", "サイズ1", "更新日時1", "撮影日時1", "解像度1", "ファイル名2", "類似度(%)", "パス1"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        return table

    def _create_duplicate_table(self) -> QTableWidget:
        headers = ["ファイル名1", "サイズ1", "更新日時1", "撮影日時1", "解像度1", "ファイル名2", "パス1", "パス2"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        return table

    def _create_error_table(self) -> QTableWidget:
        headers = ["タイプ", "ファイル/ペア", "エラー内容"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.SingleSelection, sorting_enabled=True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        return table

    # --- データ投入メソッド ---
    # ★★★ フィルタリング処理を追加 ★★★
    @Slot(list, list, dict, list)
    def populate_results(self, blurry_results: List[BlurResultItem], similar_results: List[SimilarPair], duplicate_results: DuplicateDict, scan_errors: List[ErrorDict]) -> None:
        """結果データをフィルタリングし、テーブルに表示する"""

        # --- フィルタリング ---
        # ブレ画像: path が存在する項目のみ
        filtered_blurry = [item for item in blurry_results if os.path.exists(item['path'])]

        # 類似ペア: path1 と path2 の両方が存在する項目のみ
        filtered_similar = [item for item in similar_results if os.path.exists(str(item[0])) and os.path.exists(str(item[1]))]

        # 重複ペア: path1 と path2 の両方が存在するペアのみ
        # まずペアリストに変換
        duplicate_pairs = self._flatten_duplicates_to_pairs(duplicate_results)
        filtered_duplicates = [pair for pair in duplicate_pairs if os.path.exists(pair['path1']) and os.path.exists(pair['path2'])]

        # エラーリストはそのまま表示
        filtered_errors = scan_errors
        # --------------------

        # フィルタリングされたデータでテーブルを更新
        self._populate_table(self.blurry_table, filtered_blurry, self._create_blurry_row_items)
        self._populate_table(self.similar_table, filtered_similar, self._create_similar_row_items)
        self._populate_table(self.duplicate_table, filtered_duplicates, self._create_duplicate_row_items)
        self._populate_table(self.error_table, filtered_errors, self._create_error_row_items)
        self._update_tab_texts() # タブの件数表示も更新

    def _populate_table(self, table: QTableWidget, data: List[Any], item_creator_func) -> None:
        """指定されたデータでテーブルを更新する"""
        table.setSortingEnabled(False)
        table.setRowCount(len(data))
        for row, row_data in enumerate(data):
            # item_creator_func はファイルが存在するデータに対してのみ呼ばれる
            items: List[QTableWidgetItem] = item_creator_func(row_data)
            for col, item in enumerate(items):
                table.setItem(row, col, item)
        table.setSortingEnabled(True)

    # ★★★ ファイル存在チェックを削除 (呼び出し元でフィルタリング済) ★★★
    def _create_blurry_row_items(self, data: BlurResultItem) -> List[QTableWidgetItem]:
        """ブレ画像データからテーブル行アイテムを作成"""
        path: str = data['path']
        score: float = float(data.get('score', -1.0))
        base_name = os.path.basename(path)
        # ファイルは存在するので get_file_info を呼び出す
        file_size, mod_time, dimensions, exif_date = get_file_info(path)

        chk_item = QTableWidgetItem()
        chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk_item.setCheckState(Qt.CheckState.Unchecked)
        chk_item.setData(Qt.ItemDataRole.UserRole, path)
        name_item = QTableWidgetItem(base_name)
        size_item = FileSizeTableWidgetItem(file_size)
        mod_date_item = DateTimeTableWidgetItem(mod_time)
        exif_date_item = ExifDateTimeTableWidgetItem(exif_date)
        dim_item = ResolutionTableWidgetItem(dimensions)
        score_text = f"{score:.4f}" if score >= 0 else "N/A"
        score_item = NumericTableWidgetItem(score_text)
        score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        path_item = QTableWidgetItem(path) # 通常のパスを表示
        return [chk_item, name_item, size_item, mod_date_item, exif_date_item, dim_item, score_item, path_item]

    # ★★★ ファイル存在チェックを削除 (呼び出し元でフィルタリング済) ★★★
    def _create_similar_row_items(self, data: SimilarPair) -> List[QTableWidgetItem]:
        """類似ペアデータからテーブル行アイテムを作成"""
        path1: str = str(data[0])
        path2: str = str(data[1])
        score: int = int(data[2])
        base_name1 = os.path.basename(path1)
        base_name2 = os.path.basename(path2)
        # ファイルは両方存在するので get_file_info を呼び出す
        file_size1, mod_time1, dimensions1, exif_date1 = get_file_info(path1)

        name1_item = QTableWidgetItem(base_name1)
        name1_item.setData(Qt.ItemDataRole.UserRole, (path1, path2))
        size1_item = FileSizeTableWidgetItem(file_size1)
        mod_date1_item = DateTimeTableWidgetItem(mod_time1)
        exif_date1_item = ExifDateTimeTableWidgetItem(exif_date1)
        dim1_item = ResolutionTableWidgetItem(dimensions1)
        name2_item = QTableWidgetItem(base_name2) # 通常のファイル名2
        score_item = NumericTableWidgetItem(str(score))
        score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        path1_item = QTableWidgetItem(path1) # 通常のパス1
        return [name1_item, size1_item, mod_date1_item, exif_date1_item, dim1_item, name2_item, score_item, path1_item]

    def _flatten_duplicates_to_pairs(self, duplicate_results: DuplicateDict) -> List[DuplicatePair]:
        # (変更なし)
        pair_list: List[DuplicatePair] = []
        sorted_groups = sorted(duplicate_results.items())
        for group_hash, paths in sorted_groups:
            if len(paths) < 2: continue
            sorted_paths = sorted(paths)
            first_path = sorted_paths[0]
            for i in range(1, len(sorted_paths)):
                second_path = sorted_paths[i]
                pair_list.append({'path1': first_path, 'path2': second_path, 'group_hash': group_hash})
        return pair_list

    # ★★★ ファイル存在チェックを削除 (呼び出し元でフィルタリング済) ★★★
    def _create_duplicate_row_items(self, data: DuplicatePair) -> List[QTableWidgetItem]:
        """重複ペアデータからテーブル行アイテムを作成"""
        path1: str = data['path1']
        path2: str = data['path2']
        group_hash: str = data['group_hash']
        base_name1 = os.path.basename(path1)
        base_name2 = os.path.basename(path2)
        # ファイルは両方存在するので get_file_info を呼び出す
        file_size1, mod_time1, dimensions1, exif_date1 = get_file_info(path1)

        name1_item = QTableWidgetItem(base_name1)
        name1_item.setData(Qt.ItemDataRole.UserRole, {'path1': path1, 'path2': path2, 'group_hash': group_hash})
        size1_item = FileSizeTableWidgetItem(file_size1)
        mod_date1_item = DateTimeTableWidgetItem(mod_time1)
        exif_date1_item = ExifDateTimeTableWidgetItem(exif_date1)
        dim1_item = ResolutionTableWidgetItem(dimensions1)
        name2_item = QTableWidgetItem(base_name2) # 通常のファイル名2
        path1_item = QTableWidgetItem(path1) # 通常のパス1
        path2_item = QTableWidgetItem(path2) # 通常のパス2

        return [name1_item, size1_item, mod_date1_item, exif_date1_item, dim1_item, name2_item, path1_item, path2_item]

    def _create_error_row_items(self, data: ErrorDict) -> List[QTableWidgetItem]:
        # (変更なし)
        err_type: str = data.get('type', '不明')
        path_display: str = data.get('path', 'N/A')
        error_msg: str = data.get('error', '詳細不明')
        type_item = QTableWidgetItem(err_type)
        path_item = QTableWidgetItem(path_display)
        path_item.setData(Qt.ItemDataRole.UserRole, data)
        msg_item = QTableWidgetItem(error_msg)
        msg_item.setToolTip(error_msg)
        return [type_item, path_item, msg_item]

    def _update_tab_texts(self) -> None:
        # (変更なし)
        self.setTabText(0, f"ブレ画像 ({self.blurry_table.rowCount()})")
        self.setTabText(1, f"類似ペア ({self.similar_table.rowCount()})")
        self.setTabText(2, f"重複ペア ({self.duplicate_table.rowCount()})")
        self.setTabText(3, f"エラー ({self.error_table.rowCount()})")

    @Slot()
    def clear_results(self) -> None:
        # (変更なし)
        self.blurry_table.setRowCount(0)
        self.similar_table.setRowCount(0)
        self.duplicate_table.setRowCount(0)
        self.error_table.setRowCount(0)
        self._update_tab_texts()

    # --- 選択状態取得メソッド ---
    def get_selected_blurry_paths(self) -> List[str]:
        # (変更なし - 存在チェックは不要になった)
        paths: List[str] = []
        for row in range(self.blurry_table.rowCount()):
            chk_item = self.blurry_table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                path: Optional[str] = chk_item.data(Qt.ItemDataRole.UserRole)
                if path: # パス自体は存在するはず
                    paths.append(path)
        return paths

    def get_selected_similar_primary_paths(self) -> List[str]:
        # (変更なし)
        paths: List[str] = []
        selected_rows: Set[int] = set(item.row() for item in self.similar_table.selectedItems())
        for row in selected_rows:
            item = self.similar_table.item(row, 0)
            path_data: Any = item.data(Qt.ItemDataRole.UserRole) if item else None
            if isinstance(path_data, tuple) and len(path_data) == 2 and path_data[0]:
                paths.append(path_data[0])
        return paths

    def get_selected_duplicate_paths(self) -> List[str]:
        # (変更なし - 存在チェックは不要になった)
        paths: List[str] = []
        selected_rows: Set[int] = set(item.row() for item in self.duplicate_table.selectedItems())
        for row in selected_rows:
            item = self.duplicate_table.item(row, 0)
            data: Any = item.data(Qt.ItemDataRole.UserRole) if item else None
            if isinstance(data, dict) and 'path2' in data:
                path2 = data['path2']
                if path2: # パス自体は存在するはず
                    paths.append(path2)
        return paths

    def get_current_selection_paths(self) -> SelectionPaths:
        # (変更なし)
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
            if isinstance(data, dict) and 'path1' in data and 'path2' in data:
                primary_path = data['path1']
                secondary_path = data['path2']
        return primary_path, secondary_path

    # --- 全選択/解除メソッド ---
    # (select_all_blurry, select_all_similar, select_all_duplicates, deselect_all は変更なし)
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
        self.duplicate_table.selectAll()
    @Slot()
    def deselect_all(self) -> None:
        for row in range(self.blurry_table.rowCount()):
            item = self.blurry_table.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.similar_table.clearSelection()
        self.duplicate_table.clearSelection()
        self.error_table.clearSelection()
        self.selection_changed.emit()

    # --- テーブルから削除された項目を反映するメソッド ---
    # (remove_items_by_paths, _remove_items_from_table, _check_blurry_path, _check_similar_paths, _check_duplicate_pair_paths, _check_error_paths は変更なし)
    def remove_items_by_paths(self, deleted_paths_set: Set[str]) -> None:
        if not deleted_paths_set: return
        self._remove_items_from_table(self.blurry_table, deleted_paths_set, self._check_blurry_path)
        self._remove_items_from_table(self.similar_table, deleted_paths_set, self._check_similar_paths)
        self._remove_items_from_table(self.duplicate_table, deleted_paths_set, self._check_duplicate_pair_paths)
        self._remove_items_from_table(self.error_table, deleted_paths_set, self._check_error_paths)
        self._update_tab_texts()
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
    def _check_duplicate_pair_paths(self, table: QTableWidget, row: int, deleted_paths: Set[str]) -> bool:
        item: Optional[QTableWidgetItem] = table.item(row, 0)
        data: Any = item.data(Qt.ItemDataRole.UserRole) if item else None
        if isinstance(data, dict) and 'path1' in data and 'path2' in data:
            p1n: Optional[str] = os.path.normpath(data['path1']) if data['path1'] else None
            p2n: Optional[str] = os.path.normpath(data['path2']) if data['path2'] else None
            return bool((p1n and p1n in deleted_paths) or (p2n and p2n in deleted_paths))
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
            if et and ('ブレ検出' in et or 'ハッシュ計算' in et or 'ファイルサイズ取得' in et) and ep_norm and ep_norm in deleted_paths: return True
            elif et and ('比較' in et or 'ORB' in et or 'pHash' in et) and ((p1n and p1n in deleted_paths) or (p2n and p2n in deleted_paths)): return True
        return False

    # --- コンテキストメニュー処理 ---
    # (_show_similar_table_context_menu, _show_duplicate_table_context_menu は変更なし)
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
        if row == -1: return; data_item: Optional[QTableWidgetItem] = self.duplicate_table.item(row, 0); data: Any = data_item.data(Qt.ItemDataRole.UserRole) if data_item else None
        if not isinstance(data, dict) or 'path1' not in data or 'path2' not in data: return
        path1: Optional[str] = data.get('path1'); path2: Optional[str] = data.get('path2'); base_name1: str = os.path.basename(path1) if path1 else "N/A"; base_name2: str = os.path.basename(path2) if path2 else "N/A"
        context_menu = QMenu(self); action_delete1 = QAction(f"ファイル1を削除 ({base_name1})", self); action_delete2 = QAction(f"ファイル2を削除 ({base_name2})", self); action_open1 = QAction(f"ファイル1を開く ({base_name1})", self); action_open2 = QAction(f"ファイル2を開く ({base_name2})", self)
        action_delete1.setEnabled(bool(path1 and os.path.exists(path1))); action_delete2.setEnabled(bool(path2 and os.path.exists(path2))); action_open1.setEnabled(bool(path1 and os.path.exists(path1))); action_open2.setEnabled(bool(path2 and os.path.exists(path2)))
        if path1: action_delete1.triggered.connect(lambda checked=False, p=path1: self.delete_file_requested.emit(p)); action_open1.triggered.connect(lambda checked=False, p=path1: self.open_file_requested.emit(p))
        if path2: action_delete2.triggered.connect(lambda checked=False, p=path2: self.delete_file_requested.emit(p)); action_open2.triggered.connect(lambda checked=False, p=path2: self.open_file_requested.emit(p))
        context_menu.addAction(action_delete1); context_menu.addAction(action_delete2); context_menu.addSeparator(); context_menu.addAction(action_open1); context_menu.addAction(action_open2)
        context_menu.exec(self.duplicate_table.mapToGlobal(pos))

    # --- データ取得メソッド ---
    # (get_results_data, _get_blurry_data, _get_similar_data, _get_duplicate_data_from_pairs, _get_error_data は変更なし)
    def get_results_data(self) -> ResultsData:
        return {
            'blurry': self._get_blurry_data(),
            'similar': self._get_similar_data(),
            'duplicates': self._get_duplicate_data_from_pairs(),
            'errors': self._get_error_data()
        }
    def _get_blurry_data(self) -> List[BlurResultItem]:
        data: List[BlurResultItem] = []
        for row in range(self.blurry_table.rowCount()):
            chk_item: Optional[QTableWidgetItem] = self.blurry_table.item(row, 0)
            score_item: Optional[QTableWidgetItem] = self.blurry_table.item(row, 6)
            if chk_item and score_item:
                path: Optional[str] = chk_item.data(Qt.ItemDataRole.UserRole)
                try:
                    score_text = score_item.text()
                    score = float(score_text) if score_text != "N/A" else -1.0
                    if path: data.append({'path': path, 'score': score})
                except (ValueError, TypeError): continue
        return data
    def _get_similar_data(self) -> List[SimilarPair]:
        data: List[SimilarPair] = []
        for row in range(self.similar_table.rowCount()):
            item: Optional[QTableWidgetItem] = self.similar_table.item(row, 0)
            score_item: Optional[QTableWidgetItem] = self.similar_table.item(row, 6)
            if item and score_item:
                path_data: Any = item.data(Qt.ItemDataRole.UserRole)
                try:
                    score: int = int(score_item.text())
                    if isinstance(path_data, tuple) and len(path_data) == 2:
                        p1 = str(path_data[0]) if path_data[0] else ""
                        p2 = str(path_data[1]) if path_data[1] else ""
                        data.append([p1, p2, score])
                except (ValueError, TypeError): continue
        return data
    def _get_duplicate_data_from_pairs(self) -> DuplicateDict:
        data: DuplicateDict = {}
        processed_paths: Set[str] = set()
        for row in range(self.duplicate_table.rowCount()):
            item: Optional[QTableWidgetItem] = self.duplicate_table.item(row, 0)
            if item:
                item_data: Any = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(item_data, dict) and 'path1' in item_data and 'path2' in item_data and 'group_hash' in item_data:
                    group_hash: str = item_data['group_hash']
                    path1: str = item_data['path1']
                    path2: str = item_data['path2']
                    if group_hash not in data: data[group_hash] = []
                    if path1 not in processed_paths: data[group_hash].append(path1); processed_paths.add(path1)
                    if path2 not in processed_paths: data[group_hash].append(path2); processed_paths.add(path2)
        for group_hash in data: data[group_hash].sort()
        return data
    def _get_error_data(self) -> List[ErrorDict]:
        data: List[ErrorDict] = []
        for row in range(self.error_table.rowCount()):
            item: Optional[QTableWidgetItem] = self.error_table.item(row, 1)
            if item:
                err_dict: Any = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(err_dict, dict):
                    error_data_item: ErrorDict = {
                        'type': str(err_dict.get('type', '不明')),
                        'path': str(err_dict.get('path', err_dict.get('path1', 'N/A'))),
                        'error': str(err_dict.get('error', '詳細不明'))
                    }
                    if 'path2' in err_dict: error_data_item['path2'] = str(err_dict['path2'])
                    data.append(error_data_item)
        return data