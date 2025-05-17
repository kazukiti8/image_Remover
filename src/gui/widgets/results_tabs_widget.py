# gui/widgets/results_tabs_widget.py
import os
import re
from PySide6.QtWidgets import (QWidget, QTabWidget, QTableWidget, QHeaderView,
                               QAbstractItemView, QTableWidgetItem, QMenu,
                               QStyledItemDelegate, QStyleOptionViewItem, QCheckBox,
                               QVBoxLayout, QHBoxLayout, QPushButton, QSplitter) # 追加のウィジェット
from PySide6.QtCore import Qt, Signal, Slot, QPoint, QModelIndex, QSize
from PySide6.QtGui import QAction, QColor
from typing import List, Dict, Tuple, Optional, Any, Union, Set, Callable
import datetime # get_file_info のフォールバック用

# フィルターウィジェットをインポート
try:
    from .filter_widgets import BlurryFilterWidget, SimilarityFilterWidget
except ImportError:
    print("エラー: filter_widgets モジュールのインポートに失敗しました。フィルター機能は無効化されます。")

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
        try:
            stat_info = os.stat(fp)
            size = stat_info.st_size
            mod_time = datetime.datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y/%m/%d %H:%M')
            # Pillow がない場合、解像度とExifは取得できない
            return f"{size} B", mod_time, "N/A", "N/A"
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
        self.blurry_filter: Optional[BlurryFilterWidget] = None
        self.similarity_filter: Optional[SimilarityFilterWidget] = None
        
        # フィルター関連の変数
        self._full_blurry_data: List[BlurResultItem] = []
        self._full_similar_data: List[SimilarPair] = []
        self._full_duplicate_pairs: List[DuplicatePair] = []
        
        self._setup_tabs()

    def _setup_tabs(self) -> None:
        """タブとテーブルを作成し、シグナルを接続する"""
        # ブレ画像タブのコンテナを作成
        blurry_container = QWidget()
        blurry_layout = QVBoxLayout(blurry_container)
        blurry_layout.setContentsMargins(5, 5, 5, 5)
        
        # ブレ画像テーブルとフィルターウィジェットを横に並べるスプリッタを作成
        blurry_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ブレ画像テーブルを作成
        self.blurry_table = self._create_blurry_table()
        blurry_splitter.addWidget(self.blurry_table)
        
        # フィルターウィジェットの作成と配置
        try:
            self.blurry_filter = BlurryFilterWidget()
            self.blurry_filter.filter_changed.connect(self._apply_blurry_filter)
            blurry_splitter.addWidget(self.blurry_filter)
            # 初期スプリッターの比率設定（テーブル:フィルター = 7:3）
            blurry_splitter.setSizes([700, 300])
        except (NameError, TypeError):
            print("警告: BlurryFilterWidget が使用できないため、フィルター機能は無効化されます。")
        
        blurry_layout.addWidget(blurry_splitter)
        self.addTab(blurry_container, "ブレ画像 (0)")
        
        # 類似/重複ペアタブのコンテナを作成
        similar_container = QWidget()
        similar_layout = QVBoxLayout(similar_container)
        similar_layout.setContentsMargins(5, 5, 5, 5)
        
        # 類似/重複ペアテーブルとフィルターウィジェットを横に並べるスプリッタを作成
        similar_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 類似/重複ペアテーブルを作成
        self.similar_table = self._create_similar_table()
        self.similar_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.similar_table.customContextMenuRequested.connect(self._show_similar_table_context_menu)
        similar_splitter.addWidget(self.similar_table)
        
        # フィルターウィジェットの作成と配置
        try:
            self.similarity_filter = SimilarityFilterWidget()
            self.similarity_filter.filter_changed.connect(self._apply_similarity_filter)
            similar_splitter.addWidget(self.similarity_filter)
            # 初期スプリッターの比率設定（テーブル:フィルター = 7:3）
            similar_splitter.setSizes([700, 300])
        except (NameError, TypeError):
            print("警告: SimilarityFilterWidget が使用できないため、フィルター機能は無効化されます。")
        
        similar_layout.addWidget(similar_splitter)
        self.addTab(similar_container, "類似/重複ペア (0)")

        # 重複ペアタブは廃止し、類似ペアタブに統合（互換性のために属性は維持）
        self.duplicate_table = self.similar_table

        # エラータブは単純なテーブルのまま
        self.error_table = self._create_error_table()
        self.addTab(self.error_table, "エラー (0)")

        # シグナル接続
        self.blurry_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.similar_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.error_table.itemSelectionChanged.connect(self.selection_changed.emit)
        self.currentChanged.connect(lambda index: self.selection_changed.emit())

    def _create_table_widget(self, column_count: int, headers: List[str], selection_mode: QAbstractItemView.SelectionMode, sorting_enabled: bool = True) -> QTableWidget:
        table = QTableWidget(); table.setColumnCount(column_count); table.setHorizontalHeaderLabels(headers); table.verticalHeader().setVisible(False); table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); table.setSelectionMode(selection_mode); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); table.setSortingEnabled(sorting_enabled)
        return table

    def _create_blurry_table(self) -> QTableWidget:
        # (変更なし)
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

    # ★★★ 類似ペアテーブルのヘッダーとカラム数を変更 ★★★
    def _create_similar_table(self) -> QTableWidget:
        """類似ペア表示用のテーブルを作成"""
        headers = [
            "", "ファイル名", "解像度",
            "作成日時", "パス",
            "", "ファイル名", "解像度",
            "作成日時", "パス",
            "類似度"
        ]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        # リサイズモード設定 (新しいカラム数に合わせて調整)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # File1 Checkbox
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # File1 Filename
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # File1 Resolution
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # File1 Creation Date
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)          # File1 Path
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # File2 Checkbox
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)          # File2 Filename
        table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents) # File2 Resolution
        table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents) # File2 Creation Date
        table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)          # File2 Path
        table.horizontalHeader().setSectionResizeMode(10, QHeaderView.ResizeMode.ResizeToContents) # Similarity
        return table

    # ★★★ 重複ペアテーブルのヘッダーとカラム数を変更 ★★★
    def _create_duplicate_table(self) -> QTableWidget:
        """重複ペア表示用のテーブルを作成"""
        headers = [
            "", "ファイル名", "解像度",
            "作成日時", "パス",
            "チェック", "ファイル名", "解像度",
            "作成日時", "パス"
        ]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.ExtendedSelection)
        # リサイズモード設定 (新しいカラム数に合わせて調整)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # File1 Checkbox
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # File1 Filename
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # File1 Resolution
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # File1 Creation Date
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)          # File1 Path
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # File2 Checkbox
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)          # File2 Filename
        table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents) # File2 Resolution
        table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents) # File2 Creation Date
        table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)          # File2 Path
        return table

    def _create_error_table(self) -> QTableWidget:
        # (変更なし)
        headers = ["タイプ", "ファイル/ペア", "エラー内容"]
        table = self._create_table_widget(len(headers), headers, QAbstractItemView.SelectionMode.SingleSelection, sorting_enabled=True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        return table

    # --- データ投入メソッド ---
    @Slot(list, list, dict, list)
    def populate_results(self, blurry_results: List[BlurResultItem], similar_results: List[SimilarPair], duplicate_results: DuplicateDict, scan_errors: List[ErrorDict]) -> None:
        """結果データをフィルタリングし、テーブルに表示する"""
        # フィルタリング（存在するファイルのみ）
        filtered_blurry = [item for item in blurry_results if os.path.exists(item['path'])]
        filtered_similar = [item for item in similar_results if os.path.exists(str(item[0])) and os.path.exists(str(item[1]))]
        
        # 重複ペアを類似ペアに変換（類似度100%として）
        duplicate_pairs = self._flatten_duplicates_to_pairs(duplicate_results)
        duplicate_as_similar = []
        for pair in duplicate_pairs:
            if os.path.exists(pair['path1']) and os.path.exists(pair['path2']):
                # 重複ペアを類似ペアの形式に変換し、類似度を100%とする
                duplicate_as_similar.append([pair['path1'], pair['path2'], 100])
        
        # フィルター適用のためにフルデータを保存
        self._full_blurry_data = filtered_blurry
        self._full_similar_data = filtered_similar + duplicate_as_similar
        self._full_duplicate_pairs = duplicate_pairs
        
        # フィルターを適用（もしフィルターがアクティブなら）
        self._apply_all_filters()
        
        # エラーデータは常にフィルターなしで表示
        self._populate_table(self.error_table, scan_errors, self._create_error_row_items)
        self._update_tab_texts()
    
    def _apply_all_filters(self) -> None:
        """全てのフィルターを適用する"""
        # ブレ画像フィルター適用
        if self.blurry_filter is not None:
            self._apply_blurry_filter()
        else:
            # フィルターがない場合は全データを表示
            self._populate_table(self.blurry_table, self._full_blurry_data, self._create_blurry_row_items)
        
        # 類似度フィルター適用
        if self.similarity_filter is not None:
            self._apply_similarity_filter()
        else:
            # フィルターがない場合は全データを表示
            self._populate_table(self.similar_table, self._full_similar_data, self._create_similar_row_items)
    
    @Slot()
    def _apply_blurry_filter(self) -> None:
        """ブレ画像データにフィルターを適用する"""
        if not self.blurry_filter or not self._full_blurry_data:
            return
        
        # フィルター条件を取得
        criteria = self.blurry_filter.get_filter_criteria()
        min_score = criteria.get('min_score', 0.0)
        max_score = criteria.get('max_score', 1.0)
        filename_filter = criteria.get('filename', '').lower()
        
        # フィルター適用
        filtered_data = []
        for item in self._full_blurry_data:
            # スコアに基づくフィルタリング
            score = float(item.get('score', -1.0))
            if score < 0:  # スコアが無効な場合はスキップ
                continue
                
            if score < min_score or score > max_score:
                continue
            
            # ファイル名に基づくフィルタリング
            if filename_filter:
                path = item.get('path', '')
                filename = os.path.basename(path).lower()
                if filename_filter not in filename:
                    continue
            
            filtered_data.append(item)
        
        # テーブル更新
        self._populate_table(self.blurry_table, filtered_data, self._create_blurry_row_items)
        self._update_tab_texts()
    
    @Slot()
    def _apply_similarity_filter(self) -> None:
        """類似/重複ペアデータにフィルターを適用する"""
        if not self.similarity_filter or not self._full_similar_data:
            return
        
        # フィルター条件を取得
        criteria = self.similarity_filter.get_filter_criteria()
        min_similarity = criteria.get('min_similarity', 0)
        max_similarity = criteria.get('max_similarity', 100)
        duplicates_only = criteria.get('duplicates_only', False)
        filename_filter = criteria.get('filename', '').lower()
        
        # フィルター適用
        filtered_data = []
        for item in self._full_similar_data:
            # 類似度に基づくフィルタリング
            similarity = int(item[2])
            
            if duplicates_only and similarity < 100:
                continue
                
            if similarity < min_similarity or similarity > max_similarity:
                continue
            
            # ファイル名に基づくフィルタリング
            if filename_filter:
                path1 = str(item[0])
                path2 = str(item[1])
                filename1 = os.path.basename(path1).lower()
                filename2 = os.path.basename(path2).lower()
                if filename_filter not in filename1 and filename_filter not in filename2:
                    continue
            
            filtered_data.append(item)
        
        # テーブル更新
        self._populate_table(self.similar_table, filtered_data, self._create_similar_row_items)
        self._update_tab_texts()

    def _populate_table(self, table: QTableWidget, data: List[Any], item_creator_func) -> None:
        # (変更なし)
        table.setSortingEnabled(False)
        table.setRowCount(len(data))
        for row, row_data in enumerate(data):
            items: List[QTableWidgetItem] = item_creator_func(row_data)
            for col, item in enumerate(items):
                # チェックボックスアイテムは直接セット
                if isinstance(item, QTableWidgetItem) and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                     table.setItem(row, col, item)
                else:
                    table.setItem(row, col, item)
        table.setSortingEnabled(True)

    def _create_blurry_row_items(self, data: BlurResultItem) -> List[QTableWidgetItem]:
        # (変更なし)
        path: str = data['path']
        score: float = float(data.get('score', -1.0))
        base_name = os.path.basename(path)
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
        path_item = QTableWidgetItem(path)
        return [chk_item, name_item, size_item, mod_date_item, exif_date_item, dim_item, score_item, path_item]

    # ★★★ 類似ペアの行アイテム生成ロジックを新しいカラムに合わせて修正 ★★★
    def _create_similar_row_items(self, data: SimilarPair) -> List[QTableWidgetItem]:
        """類似ペアデータからテーブル行アイテムを作成"""
        path1: str = str(data[0])
        path2: str = str(data[1])
        score: int = int(data[2])
        base_name1 = os.path.basename(path1)
        base_name2 = os.path.basename(path2)

        # ファイル1の情報取得
        file_size1, mod_time1, dimensions1, exif_date1 = get_file_info(path1)
        # ファイル2の情報取得
        file_size2, mod_time2, dimensions2, exif_date2 = get_file_info(path2)

        # ファイル1のアイテム
        chk1_item = QTableWidgetItem()
        chk1_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk1_item.setCheckState(Qt.CheckState.Unchecked)
        chk1_item.setData(Qt.ItemDataRole.UserRole, path1) # UserRoleにパスを保存
        name1_item = QTableWidgetItem(base_name1)
        dim1_item = ResolutionTableWidgetItem(dimensions1)
        date1_item = ExifDateTimeTableWidgetItem(exif_date1 if exif_date1 != "N/A" else mod_time1) # 撮影日時優先、なければ更新日時
        path1_item = QTableWidgetItem(path1)

        # ファイル2のアイテム
        chk2_item = QTableWidgetItem()
        chk2_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk2_item.setCheckState(Qt.CheckState.Unchecked)
        chk2_item.setData(Qt.ItemDataRole.UserRole, path2) # UserRoleにパスを保存
        name2_item = QTableWidgetItem(base_name2)
        dim2_item = ResolutionTableWidgetItem(dimensions2)
        date2_item = ExifDateTimeTableWidgetItem(exif_date2 if exif_date2 != "N/A" else mod_time2) # 撮影日時優先、なければ更新日時
        path2_item = QTableWidgetItem(path2)

        # 類似度スコア
        # スコアが100の場合は特別な表示に（重複ファイル）
        score_text = "完全一致（重複)" if score == 100 else str(score)
        score_item = NumericTableWidgetItem(score_text)
        score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # 重複ファイルの場合は背景色を変更して目立たせる
        if score == 100:
            # 行全体のアイテムに背景色を設定
            highlight_color = QColor(255, 240, 240)  # 薄い赤色
            for item in [chk1_item, name1_item, dim1_item, date1_item, path1_item,
                        chk2_item, name2_item, dim2_item, date2_item, path2_item, 
                        score_item]:
                item.setBackground(highlight_color)

        # 新しい列順序に合わせてアイテムを返す
        # ["ファイル1 チェック", "ファイル1 ファイル名", "ファイル1 解像度", "ファイル1 作成日時", "ファイル1 パス",
        #  "ファイル2 チェック", "ファイル2 ファイル名", "ファイル2 解像度", "ファイル2 作成日時", "ファイル2 パス",
        #  "類似度"]
        return [
            chk1_item, name1_item, dim1_item, date1_item, path1_item,
            chk2_item, name2_item, dim2_item, date2_item, path2_item,
            score_item
        ]

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

    # ★★★ 重複ペアの行アイテム生成ロジックを新しいカラムに合わせて修正 ★★★
    def _create_duplicate_row_items(self, data: DuplicatePair) -> List[QTableWidgetItem]:
        """重複ペアデータからテーブル行アイテムを作成"""
        path1: str = data['path1']
        path2: str = data['path2']
        group_hash: str = data['group_hash'] # 使用しないがデータとして保持

        # ファイル1の情報取得
        file_size1, mod_time1, dimensions1, exif_date1 = get_file_info(path1)
        # ファイル2の情報取得
        file_size2, mod_time2, dimensions2, exif_date2 = get_file_info(path2)

        # ファイル1のアイテム
        chk1_item = QTableWidgetItem()
        chk1_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk1_item.setCheckState(Qt.CheckState.Unchecked)
        chk1_item.setData(Qt.ItemDataRole.UserRole, path1) # UserRoleにパスを保存
        name1_item = QTableWidgetItem(os.path.basename(path1))
        dim1_item = ResolutionTableWidgetItem(dimensions1)
        date1_item = ExifDateTimeTableWidgetItem(exif_date1 if exif_date1 != "N/A" else mod_time1) # 撮影日時優先、なければ更新日時
        path1_item = QTableWidgetItem(path1)

        # ファイル2のアイテム
        chk2_item = QTableWidgetItem()
        chk2_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk2_item.setCheckState(Qt.CheckState.Unchecked)
        chk2_item.setData(Qt.ItemDataRole.UserRole, path2) # UserRoleにパスを保存
        name2_item = QTableWidgetItem(os.path.basename(path2))
        dim2_item = ResolutionTableWidgetItem(dimensions2)
        date2_item = ExifDateTimeTableWidgetItem(exif_date2 if exif_date2 != "N/A" else mod_time2) # 撮影日時優先、なければ更新日時
        path2_item = QTableWidgetItem(path2)

        # 新しい列順序に合わせてアイテムを返す
        # ["ファイル1 チェック", "ファイル1 ファイル名", "ファイル1 解像度", "ファイル1 作成日時", "ファイル1 パス",
        #  "ファイル2 チェック", "ファイル2 ファイル名", "ファイル2 解像度", "ファイル2 作成日時", "ファイル2 パス"]
        return [
            chk1_item, name1_item, dim1_item, date1_item, path1_item,
            chk2_item, name2_item, dim2_item, date2_item, path2_item
        ]

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
        """タブのテキストを更新（行数を含める）"""
        self.setTabText(0, f"ブレ画像 ({self.blurry_table.rowCount()})")
        self.setTabText(1, f"類似/重複ペア ({self.similar_table.rowCount()})")
        self.setTabText(2, f"エラー ({self.error_table.rowCount()})")

    @Slot()
    def clear_results(self) -> None:
        """すべての結果テーブルをクリアする"""
        self.blurry_table.setRowCount(0)
        self.similar_table.setRowCount(0)
        # duplicate_table は similar_table と同じなので別途クリアする必要はない
        self.error_table.setRowCount(0)
        self._update_tab_texts()
        
        # キャッシュしているデータもクリア
        self._full_blurry_data = []
        self._full_similar_data = []
        self._full_duplicate_pairs = []
        
        # フィルターをリセット
        if self.blurry_filter:
            self.blurry_filter.reset_filters()
        if self.similarity_filter:
            self.similarity_filter.reset_filters()

    # --- 選択状態取得メソッド ---
    # ★★★ 選択状態取得ロジックを新しいカラムに合わせて修正 ★★★
    def get_selected_blurry_paths(self) -> List[str]:
        paths: List[str] = []
        for row in range(self.blurry_table.rowCount()):
            # ブレ画像タブのチェックボックスは0列目
            chk_item = self.blurry_table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                path: Optional[str] = chk_item.data(Qt.ItemDataRole.UserRole)
                if path: paths.append(path)
        return paths

    def get_selected_similar_primary_paths(self) -> List[str]:
        """類似ペアタブでチェックされたファイルパスを取得"""
        paths: Set[str] = set() # 重複を防ぐためにSetを使用
        for row in range(self.similar_table.rowCount()):
            # ファイル1のチェックボックスは0列目
            chk1_item = self.similar_table.item(row, 0)
            if chk1_item and chk1_item.checkState() == Qt.CheckState.Checked:
                path1: Optional[str] = chk1_item.data(Qt.ItemDataRole.UserRole)
                if path1: paths.add(path1)

            # ファイル2のチェックボックスは5列目
            chk2_item = self.similar_table.item(row, 5)
            if chk2_item and chk2_item.checkState() == Qt.CheckState.Checked:
                path2: Optional[str] = chk2_item.data(Qt.ItemDataRole.UserRole)
                if path2: paths.add(path2)

        # 選択行のファイル1パスも取得 (プレビュー表示用)
        selected_rows: Set[int] = set(item.row() for item in self.similar_table.selectedItems())
        for row in selected_rows:
             # ファイル1のパスは4列目
            path1_item = self.similar_table.item(row, 4)
            path1: Optional[str] = path1_item.text() if path1_item else None
            if path1: paths.add(path1)

        return list(paths) # SetをListに変換して返す

    def get_selected_duplicate_paths(self) -> List[str]:
        """重複ペアタブでチェックされたファイルパスを取得"""
        paths: Set[str] = set() # 重複を防ぐためにSetを使用
        for row in range(self.duplicate_table.rowCount()):
            # ファイル1のチェックボックスは0列目
            chk1_item = self.duplicate_table.item(row, 0)
            if chk1_item and chk1_item.checkState() == Qt.CheckState.Checked:
                path1: Optional[str] = chk1_item.data(Qt.ItemDataRole.UserRole)
                if path1: paths.add(path1)

            # ファイル2のチェックボックスは5列目
            chk2_item = self.duplicate_table.item(row, 5)
            if chk2_item and chk2_item.checkState() == Qt.CheckState.Checked:
                path2: Optional[str] = chk2_item.data(Qt.ItemDataRole.UserRole)
                if path2: paths.add(path2)

        # 選択行のファイル1パスも取得 (プレビュー表示用)
        selected_rows: Set[int] = set(item.row() for item in self.duplicate_table.selectedItems())
        for row in selected_rows:
            # ファイル1のパスは4列目
            path1_item = self.duplicate_table.item(row, 4)
            path1: Optional[str] = path1_item.text() if path1_item else None
            if path1: paths.add(path1)

        return list(paths) # SetをListに変換して返す


    def get_current_selection_paths(self) -> SelectionPaths:
        """現在選択されている行のファイルパスを取得"""
        primary_path: Optional[str] = None
        secondary_path: Optional[str] = None
        current_index: int = self.currentIndex()
        table: Optional[QTableWidget] = self.widget(current_index) if isinstance(self.widget(current_index), QTableWidget) else None
        if table is None: return None, None

        selected_items: List[QTableWidgetItem] = table.selectedItems()
        row: int = selected_items[0].row() if selected_items else -1

        if row == -1: return None, None

        if current_index == 0: # Blurry
            # ブレ画像タブのパスは0列目のUserRole
            item = table.item(row, 0)
            primary_path = item.data(Qt.ItemDataRole.UserRole) if item else None
        elif current_index == 1: # Similar
            # 類似ペアタブのファイル1パスは4列目, ファイル2パスは9列目
            item1 = table.item(row, 4)
            item2 = table.item(row, 9)
            primary_path = item1.text() if item1 else None
            secondary_path = item2.text() if item2 else None
        elif current_index == 2: # Duplicate
            # 重複ペアタブのファイル1パスは4列目, ファイル2パスは9列目
            item1 = table.item(row, 4)
            item2 = table.item(row, 9)
            primary_path = item1.text() if item1 else None
            secondary_path = item2.text() if item2 else None

        return primary_path, secondary_path

    # --- 全選択/解除メソッド ---
    # ★★★ 全選択/解除ロジックを新しいカラムに合わせて修正 ★★★
    @Slot()
    def select_all_blurry(self) -> None:
        self.setCurrentIndex(0)
        for row in range(self.blurry_table.rowCount()):
            # ブレ画像タブのチェックボックスは0列目
            item = self.blurry_table.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Checked)

    @Slot()
    def select_all_similar(self) -> None:
        self.setCurrentIndex(1)
        # 類似ペアタブのファイル2（右側）のチェックボックスを全てチェック (5列目)
        for row in range(self.similar_table.rowCount()):
            chk2_item = self.similar_table.item(row, 5)
            if chk2_item and chk2_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                chk2_item.setCheckState(Qt.CheckState.Checked)
        # 従来の行選択も行う (プレビュー表示のため)
        self.similar_table.selectAll()

    @Slot()
    def select_all_duplicates(self) -> None:
        self.setCurrentIndex(2)
         # 重複ペアタブのファイル2（右側）のチェックボックスを全てチェック (5列目)
        for row in range(self.duplicate_table.rowCount()):
            chk2_item = self.duplicate_table.item(row, 5)
            if chk2_item and chk2_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                chk2_item.setCheckState(Qt.CheckState.Checked)
        # 従来の行選択も行う (プレビュー表示のため)
        self.duplicate_table.selectAll()

    @Slot()
    def deselect_all(self) -> None:
        # ブレ画像のチェックボックスをクリア (0列目)
        for row in range(self.blurry_table.rowCount()):
            item = self.blurry_table.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Unchecked)

        # 類似ペアのチェックボックスをクリア (0列目と5列目)
        for row in range(self.similar_table.rowCount()):
            chk1_item = self.similar_table.item(row, 0)
            if chk1_item and chk1_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                chk1_item.setCheckState(Qt.CheckState.Unchecked)

            chk2_item = self.similar_table.item(row, 5)
            if chk2_item and chk2_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                chk2_item.setCheckState(Qt.CheckState.Unchecked)

        # 重複ペアのチェックボックスをクリア (0列目と5列目)
        for row in range(self.duplicate_table.rowCount()):
            chk1_item = self.duplicate_table.item(row, 0)
            if chk1_item and chk1_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                chk1_item.setCheckState(Qt.CheckState.Unchecked)

            chk2_item = self.duplicate_table.item(row, 5)
            if chk2_item and chk2_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                chk2_item.setCheckState(Qt.CheckState.Unchecked)

        # 選択解除
        self.blurry_table.clearSelection()
        self.similar_table.clearSelection()
        self.duplicate_table.clearSelection()
        self.error_table.clearSelection()
        self.selection_changed.emit()

    # --- テーブルから削除された項目を反映するメソッド ---
    # ★★★ 削除項目チェックロジックを新しいカラムに合わせて修正 ★★★
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
        # ブレ画像タブのパスは0列目のUserRole
        item: Optional[QTableWidgetItem] = table.item(row, 0)
        path: Optional[str] = item.data(Qt.ItemDataRole.UserRole) if item else None
        return bool(path and os.path.normpath(path) in deleted_paths)

    def _check_similar_paths(self, table: QTableWidget, row: int, deleted_paths: Set[str]) -> bool:
        # 類似ペアタブのファイル1パスは4列目, ファイル2パスは9列目
        item1: Optional[QTableWidgetItem] = table.item(row, 4)
        item2: Optional[QTableWidgetItem] = table.item(row, 9)
        p1: Optional[str] = item1.text() if item1 else None
        p2: Optional[str] = item2.text() if item2 else None
        p1n: Optional[str] = os.path.normpath(p1) if p1 else None
        p2n: Optional[str] = os.path.normpath(p2) if p2 else None
        return bool((p1n and p1n in deleted_paths) or (p2n and p2n in deleted_paths))

    def _check_duplicate_pair_paths(self, table: QTableWidget, row: int, deleted_paths: Set[str]) -> bool:
         # 重複ペアタブのファイル1パスは4列目, ファイル2パスは9列目
        item1: Optional[QTableWidgetItem] = table.item(row, 4)
        item2: Optional[QTableWidgetItem] = table.item(row, 9)
        p1: Optional[str] = item1.text() if item1 else None
        p2: Optional[str] = item2.text() if item2 else None
        p1n: Optional[str] = os.path.normpath(p1) if p1 else None
        p2n: Optional[str] = os.path.normpath(p2) if p2 else None
        return bool((p1n and p1n in deleted_paths) or (p2n and p2n in deleted_paths))

    def _check_error_paths(self, table: QTableWidget, row: int, deleted_paths: Set[str]) -> bool:
        # エラータブのファイル/ペア列は1列目
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
    # ★★★ コンテキストメニューロジックを新しいカラムに合わせて修正 ★★★
    @Slot(QPoint)
    def _show_similar_table_context_menu(self, pos: QPoint) -> None:
        item: Optional[QTableWidgetItem] = self.similar_table.itemAt(pos)
        row: int = item.row() if item else -1
        if row == -1: return

        # ファイル1とファイル2のパスはそれぞれ4列目と9列目から取得
        item1_path = self.similar_table.item(row, 4)
        item2_path = self.similar_table.item(row, 9)
        path1: Optional[str] = item1_path.text() if item1_path else None
        path2: Optional[str] = item2_path.text() if item2_path else None

        base_name1: str = os.path.basename(path1) if path1 else "N/A"
        base_name2: str = os.path.basename(path2) if path2 else "N/A"

        context_menu = QMenu(self)
        action_delete1 = QAction(f"左画像を削除 ({base_name1})", self)
        action_delete2 = QAction(f"右画像を削除 ({base_name2})", self)
        action_open1 = QAction(f"左画像を開く ({base_name1})", self)
        action_open2 = QAction(f"右画像を開く ({base_name2})", self)

        action_delete1.setEnabled(bool(path1 and os.path.exists(path1)))
        action_delete2.setEnabled(bool(path2 and os.path.exists(path2)))
        action_open1.setEnabled(bool(path1 and os.path.exists(path1)))
        action_open2.setEnabled(bool(path2 and os.path.exists(path2)))

        if path1:
            action_delete1.triggered.connect(lambda checked=False, p=path1: self.delete_file_requested.emit(p))
            action_open1.triggered.connect(lambda checked=False, p=path1: self.open_file_requested.emit(p))
        if path2:
            action_delete2.triggered.connect(lambda checked=False, p=path2: self.delete_file_requested.emit(p))
            action_open2.triggered.connect(lambda checked=False, p=path2: self.open_file_requested.emit(p))

        context_menu.addAction(action_delete1)
        context_menu.addAction(action_delete2)
        context_menu.addSeparator()
        context_menu.addAction(action_open1)
        context_menu.addAction(action_open2)

        context_menu.exec(self.similar_table.mapToGlobal(pos))

    @Slot(QPoint)
    def _show_duplicate_table_context_menu(self, pos: QPoint) -> None:
        item: Optional[QTableWidgetItem] = self.duplicate_table.itemAt(pos)
        row: int = item.row() if item else -1
        if row == -1: return

        # ファイル1とファイル2のパスはそれぞれ4列目と9列目から取得
        item1_path = self.duplicate_table.item(row, 4)
        item2_path = self.duplicate_table.item(row, 9)
        path1: Optional[str] = item1_path.text() if item1_path else None
        path2: Optional[str] = item2_path.text() if item2_path else None

        base_name1: str = os.path.basename(path1) if path1 else "N/A"
        base_name2: str = os.path.basename(path2) if path2 else "N/A"

        context_menu = QMenu(self)
        action_delete1 = QAction(f"左画像を削除 ({base_name1})", self)
        action_delete2 = QAction(f"右画像を削除 ({base_name2})", self)
        action_open1 = QAction(f"左画像を開く ({base_name1})", self)
        action_open2 = QAction(f"右画像を開く ({base_name2})", self)

        action_delete1.setEnabled(bool(path1 and os.path.exists(path1)))
        action_delete2.setEnabled(bool(path2 and os.path.exists(path2)))
        action_open1.setEnabled(bool(path1 and os.path.exists(path1)))
        action_open2.setEnabled(bool(path2 and os.path.exists(path2)))

        if path1:
            action_delete1.triggered.connect(lambda checked=False, p=path1: self.delete_file_requested.emit(p))
            action_open1.triggered.connect(lambda checked=False, p=path1: self.open_file_requested.emit(p))
        if path2:
            action_delete2.triggered.connect(lambda checked=False, p=path2: self.delete_file_requested.emit(p))
            action_open2.triggered.connect(lambda checked=False, p=path2: self.open_file_requested.emit(p))

        context_menu.addAction(action_delete1)
        context_menu.addAction(action_delete2)
        context_menu.addSeparator()
        context_menu.addAction(action_open1)
        context_menu.addAction(action_open2)

        context_menu.exec(self.duplicate_table.mapToGlobal(pos))

    # --- データ取得メソッド ---
    # ★★★ データ取得ロジックを新しいカラムに合わせて修正 ★★★
    def get_results_data(self) -> ResultsData:
        # フィルターがあっても元のフルデータを使用
        # これにより保存されるデータはフィルターの影響を受けない
        return {
            'blurry': self._full_blurry_data if self._full_blurry_data else self._get_blurry_data(),
            'similar': self._get_similar_data(),
            'duplicates': self._get_duplicate_data_from_pairs(),
            'errors': self._get_error_data()
        }
        
    def get_filter_settings(self) -> Dict[str, Dict[str, Any]]:
        """現在のフィルター設定を取得する"""
        filter_settings = {}
        
        if self.blurry_filter:
            filter_settings['blurry'] = self.blurry_filter.get_filter_criteria()
            
        if self.similarity_filter:
            filter_settings['similarity'] = self.similarity_filter.get_filter_criteria()
            
        return filter_settings
        
    def set_filter_settings(self, settings: Dict[str, Dict[str, Any]]) -> None:
        """フィルター設定を適用する"""
        if 'blurry' in settings and self.blurry_filter:
            self.blurry_filter.set_filter_criteria(settings['blurry'])
            
        if 'similarity' in settings and self.similarity_filter:
            self.similarity_filter.set_filter_criteria(settings['similarity'])
            
        # 設定を適用したらフィルターを実行
        self._apply_all_filters()

    def _get_blurry_data(self) -> List[BlurResultItem]:
        data: List[BlurResultItem] = []
        for row in range(self.blurry_table.rowCount()):
            # ブレ画像タブのパスは0列目のUserRole, スコアは6列目
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
            # 類似ペアタブのファイル1パスは4列目, ファイル2パスは9列目, スコアは10列目
            item1_path: Optional[QTableWidgetItem] = self.similar_table.item(row, 4)
            item2_path: Optional[QTableWidgetItem] = self.similar_table.item(row, 9)
            score_item: Optional[QTableWidgetItem] = self.similar_table.item(row, 10)

            if item1_path and item2_path and score_item:
                p1: Optional[str] = item1_path.text()
                p2: Optional[str] = item2_path.text()
                try:
                    score: int = int(score_item.text())
                    if p1 and p2:
                        data.append([p1, p2, score])
                except (ValueError, TypeError): continue
        return data

    def _get_duplicate_data_from_pairs(self) -> DuplicateDict:
        data: DuplicateDict = {}
        # 重複ペアタブにはグループハッシュを直接表示していないため、パスから再構築
        # このメソッドは重複ペアのリストを返す _flatten_duplicates_to_pairs とは異なる
        # ここでは、テーブルの表示内容から重複グループを再構築する
        pairs: List[Tuple[str, str]] = []
        for row in range(self.duplicate_table.rowCount()):
             # 重複ペアタブのファイル1パスは4列目, ファイル2パスは9列目
            item1_path: Optional[QTableWidgetItem] = self.duplicate_table.item(row, 4)
            item2_path: Optional[QTableWidgetItem] = self.duplicate_table.item(row, 9)
            p1: Optional[str] = item1_path.text() if item1_path else None
            p2: Optional[str] = item2_path.text() if item2_path else None
            if p1 and p2:
                pairs.append(tuple(sorted((p1, p2)))) # ペアをソートしてタプルで保存

        # 重複グループを推測 (同じファイルを含むペアは同じグループとみなす)
        groups: Dict[str, List[str]] = {}
        for p1, p2 in pairs:
            found_group = None
            for group_key in groups:
                if p1 in groups[group_key] or p2 in groups[group_key]:
                    found_group = group_key
                    break
            if found_group:
                if p1 not in groups[found_group]: groups[found_group].append(p1)
                if p2 not in groups[found_group]: groups[found_group].append(p2)
            else:
                # 新しいグループを作成 (キーは最初のファイルパスを使用)
                groups[p1] = [p1, p2]

        # グループ内のパスをソート
        for group_key in groups:
            groups[group_key].sort()

        return groups


    def _get_error_data(self) -> List[ErrorDict]:
        data: List[ErrorDict] = []
        for row in range(self.error_table.rowCount()):
            # エラータブのデータは1列目のUserRole
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
