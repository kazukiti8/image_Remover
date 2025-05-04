# gui/main_window.py
import sys
import os
import time
import itertools
import cv2
import numpy as np
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QFrame,
    QFileDialog, QProgressBar, QTableWidget, QTableWidgetItem, # ★ QTableWidgetItem をインポート ★
    QHeaderView, QAbstractItemView, QMessageBox
)
from PySide6.QtCore import Qt, QRunnable, QThreadPool, Signal, QObject, Slot
from PySide6.QtGui import QImage, QPixmap, QCloseEvent, QKeyEvent, QMouseEvent

# --- send2trash をインポート ---
try:
    import send2trash
except ImportError:
    print("エラー: send2trash ライブラリが見つかりません。`pip install Send2Trash` を実行してください。")
    send2trash = None

# --- コアロジックの関数をインポート ---
try:
    from core.blur_detection import calculate_fft_blur_score_v2
    from core.similarity_detection import find_similar_pairs
except ImportError:
    print("エラー: core モジュールが見つかりません。ダミー関数を使用します。")
    # (ダミー関数の定義は省略)
    def calculate_fft_blur_score_v2(path, ratio=0.05): return 0.5 if "blur" in path else 0.9
    def find_similar_pairs(dir_path, **kwargs):
        def _dummy_pair(dir_p, f1, f2, score): p1,p2=os.path.join(dir_p,f1),os.path.join(dir_p,f2); return (p1,p2,score) if os.path.exists(p1) and os.path.exists(p2) else None
        pairs = []; p = _dummy_pair(dir_path, "A.jpg", "B.jpg", 95); p and pairs.append(p); p = _dummy_pair(dir_path, "A.jpg", "C.jpg", 92); p and pairs.append(p); return pairs

# --- 設定ダイアログクラスをインポート ---
try:
    from .settings_dialog import SettingsDialog
except ImportError:
    print("エラー: settings_dialog モジュールが見つかりません。")
    SettingsDialog = None

# === ★ 数値ソート用 QTableWidgetItem サブクラス定義 ★ ===
class NumericTableWidgetItem(QTableWidgetItem):
    """数値を正しくソートするための QTableWidgetItem サブクラス"""
    def __lt__(self, other):
        # アイテムのテキストを数値（浮動小数点数）に変換して比較
        try:
            # 空白やエラー文字列を考慮
            self_value = float(self.text()) if self.text() else -float('inf')
            other_value = float(other.text()) if other.text() else -float('inf')
            return self_value < other_value
        except (ValueError, TypeError):
            # 数値に変換できない場合は、デフォルトの文字列比較にフォールバック
            return super().__lt__(other)

# === バックグラウンド処理用のクラス定義 (変更なし) ===
class WorkerSignals(QObject):
    progress = Signal(str)
    results_ready = Signal(list, list)
    error = Signal(str)
    finished = Signal()

class ScanWorker(QRunnable):
    def __init__(self, directory_path, settings):
        super().__init__()
        self.directory_path = directory_path
        self.signals = WorkerSignals()
        self.settings = settings
        self.file_extensions=('.jpg', '.jpeg', '.png', '.bmp', '.tiff')

    @Slot()
    def run(self):
        # (ScanWorker.run の中身は変更なし)
        try:
            self.signals.progress.emit("ファイルリスト取得中...")
            image_paths = []
            try:
                for filename in os.listdir(self.directory_path):
                    if filename.lower().endswith(self.file_extensions):
                        full_path = os.path.join(self.directory_path, filename)
                        if os.path.isfile(full_path) and not os.path.islink(full_path):
                            image_paths.append(full_path)
            except OSError as e:
                 self.signals.error.emit(f"ディレクトリ読み込みエラー: {e}")
                 self.signals.finished.emit()
                 return

            if not image_paths:
                self.signals.progress.emit("対象ディレクトリに画像ファイルが見つかりませんでした。")
                self.signals.results_ready.emit([], [])
                self.signals.finished.emit()
                return

            num_images = len(image_paths)
            blurry_results = []
            similar_pair_results = []

            # --- ブレ検出 ---
            blur_threshold = self.settings.get('blur_threshold', 0.80)
            self.signals.progress.emit(f"ブレ検出中... (閾値: {blur_threshold:.4f}) (0/{num_images})")
            for i, img_path in enumerate(image_paths):
                score = calculate_fft_blur_score_v2(img_path)
                if score == -1: continue
                if score <= blur_threshold:
                    blurry_results.append({"path": img_path, "score": score})
                if (i + 1) % 5 == 0 or (i + 1) == num_images:
                    self.signals.progress.emit(f"ブレ検出中... ({i+1}/{num_images})")

            # --- 類似ペア検出 ---
            orb_nfeatures = self.settings.get('orb_nfeatures', 1500)
            orb_ratio_threshold = self.settings.get('orb_ratio_threshold', 0.70)
            min_good_matches = self.settings.get('min_good_matches', 40)
            self.signals.progress.emit(f"類似ペア検出中... (f={orb_nfeatures}, r={orb_ratio_threshold:.2f}, m={min_good_matches})")
            try:
                similar_pair_results = find_similar_pairs(
                    self.directory_path,
                    orb_nfeatures=orb_nfeatures,
                    orb_ratio_threshold=orb_ratio_threshold,
                    min_good_matches_threshold=min_good_matches,
                    file_extensions=self.file_extensions
                )
            except Exception as e:
                 self.signals.error.emit(f"類似ペア検出中にエラー: {e}")
                 similar_pair_results = []

            self.signals.results_ready.emit(blurry_results, similar_pair_results)

        except Exception as e:
            self.signals.error.emit(f"スキャン中に予期せぬエラーが発生しました: {e}")
        finally:
            self.signals.finished.emit()


# === メインウィンドウクラス ===
class ImageCleanerWindow(QMainWindow):
    SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".image_cleaner_settings.json")

    def __init__(self):
        super().__init__()
        self.setWindowTitle("画像クリーナー")
        self.setGeometry(100, 100, 950, 700)

        self.threadpool = QThreadPool()
        self.default_settings = {
            'blur_threshold': 0.80,
            'orb_nfeatures': 1500,
            'orb_ratio_threshold': 0.70,
            'min_good_matches': 40
        }
        self.current_settings = self.default_settings.copy()
        self.left_preview_path = None
        self.right_preview_path = None
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """UIウィジェットの作成とレイアウトを行う"""
        # (変更なし - 前回の応答と同じコード)
        main_widget = QWidget(); self.setCentralWidget(main_widget); self.main_layout = QVBoxLayout(main_widget)
        input_layout = QHBoxLayout(); self.dir_label = QLabel("対象フォルダ:"); self.dir_path_edit = QLineEdit(); self.dir_path_edit.setReadOnly(True); self.select_dir_button = QPushButton("フォルダを選択..."); self.select_dir_button.clicked.connect(self.select_directory); input_layout.addWidget(self.dir_label); input_layout.addWidget(self.dir_path_edit); input_layout.addWidget(self.select_dir_button); self.main_layout.addLayout(input_layout)
        settings_layout = QHBoxLayout(); self.settings_button = QPushButton("設定..."); self.settings_button.clicked.connect(self.open_settings); settings_layout.addWidget(self.settings_button); settings_layout.addStretch(); self.main_layout.addLayout(settings_layout)
        proc_layout = QHBoxLayout(); self.scan_button = QPushButton("スキャン開始"); self.scan_button.clicked.connect(self.start_scan); self.status_label = QLabel("ステータス: 待機中"); self.progress_bar = QProgressBar(); self.progress_bar.setVisible(False); proc_layout.addWidget(self.scan_button); proc_layout.addWidget(self.status_label); proc_layout.addStretch(); self.main_layout.addLayout(proc_layout); self.main_layout.addWidget(self.progress_bar)
        preview_area = QFrame(); preview_area.setFrameShape(QFrame.Shape.StyledPanel); preview_area.setFixedHeight(200); preview_layout = QHBoxLayout(preview_area); self.left_preview = QLabel("左プレビュー\n(画像選択で表示)"); self.left_preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.left_preview.setFrameShape(QFrame.Shape.Box); self.left_preview.mousePressEvent = self.on_left_preview_clicked; self.right_preview = QLabel("右プレビュー\n(類似ペア選択で表示)"); self.right_preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.right_preview.setFrameShape(QFrame.Shape.Box); self.right_preview.mousePressEvent = self.on_right_preview_clicked; preview_layout.addWidget(self.left_preview, 1); preview_layout.addWidget(self.right_preview, 1); self.main_layout.addWidget(preview_area, stretch=0)
        self.results_tabs = QTabWidget()
        self.blurry_table = QTableWidget(); self.blurry_table.setColumnCount(6); self.blurry_table.setHorizontalHeaderLabels(["", "Thumb", "ファイル名", "パス", "解像度", "ブレ度スコア"]); self.blurry_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents); self.blurry_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents); self.blurry_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch); self.blurry_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch); self.blurry_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents); self.blurry_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents); self.blurry_table.verticalHeader().setVisible(False); self.blurry_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.blurry_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self.blurry_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.blurry_table.setSortingEnabled(True); self.blurry_table.itemSelectionChanged.connect(self.update_preview)
        self.similar_table = QTableWidget(); self.similar_table.setColumnCount(7); self.similar_table.setHorizontalHeaderLabels(["Thumb", "ファイル名", "サイズ", "更新日時", "解像度", "類似ファイル", "類似度(%)"]); self.similar_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents); self.similar_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch); self.similar_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents); self.similar_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents); self.similar_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents); self.similar_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch); self.similar_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents); self.similar_table.verticalHeader().setVisible(False); self.similar_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.similar_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self.similar_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.similar_table.setSortingEnabled(True); self.similar_table.itemSelectionChanged.connect(self.update_preview)
        self.results_tabs.addTab(self.blurry_table, "ブレ画像 (0)"); self.results_tabs.addTab(self.similar_table, "類似ペア (0)"); self.main_layout.addWidget(self.results_tabs, stretch=1)
        action_layout = QHBoxLayout(); self.delete_button = QPushButton("選択した項目をゴミ箱へ移動"); self.delete_button.clicked.connect(self.delete_selected_items); self.select_all_blurry_button = QPushButton("全選択(ブレ)"); self.select_all_blurry_button.clicked.connect(self.select_all_blurry); self.select_all_similar_button = QPushButton("全選択(類似ペア)"); self.select_all_similar_button.clicked.connect(self.select_all_similar); self.deselect_all_button = QPushButton("全選択解除"); self.deselect_all_button.clicked.connect(self.deselect_all); action_layout.addWidget(self.delete_button); action_layout.addStretch(); action_layout.addWidget(self.select_all_blurry_button); action_layout.addWidget(self.select_all_similar_button); action_layout.addWidget(self.deselect_all_button); self.main_layout.addLayout(action_layout)


    # --- 設定読み込み/保存メソッド (変更なし) ---
    def _load_settings(self):
        # (変更なし - 前回の応答と同じコード)
        if os.path.exists(self.SETTINGS_FILE):
            try:
                with open(self.SETTINGS_FILE, 'r', encoding='utf-8') as f: loaded_settings = json.load(f)
                for key in self.default_settings:
                    if key in loaded_settings:
                        if isinstance(loaded_settings[key], type(self.default_settings[key])): self.current_settings[key] = loaded_settings[key]
                        else: print(f"警告: 設定ファイルの値の型が不正です ({key})。デフォルト値を使用します。")
                print(f"設定ファイルを読み込みました: {self.SETTINGS_FILE}")
            except (json.JSONDecodeError, TypeError, ValueError, OSError) as e: print(f"警告: 設定ファイルの読み込みに失敗しました ({e})。デフォルト設定を使用します。"); self.current_settings = self.default_settings.copy()
        else: print("設定ファイルが見つかりません。デフォルト設定を使用します。")

    def _save_settings(self):
        # (変更なし - 前回の応答と同じコード)
        try:
            with open(self.SETTINGS_FILE, 'w', encoding='utf-8') as f: json.dump(self.current_settings, f, ensure_ascii=False, indent=4)
            print(f"設定を保存しました: {self.SETTINGS_FILE}")
        except OSError as e: print(f"警告: 設定ファイルの保存に失敗しました ({e})。"); QMessageBox.warning(self, "保存エラー", f"設定ファイルの保存に失敗しました。\n{e}")

    def closeEvent(self, event: QCloseEvent):
        # (変更なし)
        self._save_settings()
        event.accept()

    # --- ボタンに対応する関数 (スロット) ---
    def select_directory(self):
        # (変更なし)
        dir_path = QFileDialog.getExistingDirectory(self, "フォルダを選択", os.path.expanduser("~"))
        if dir_path: self.dir_path_edit.setText(dir_path); self.clear_results()

    def open_settings(self):
        # (変更なし)
        if SettingsDialog is None: QMessageBox.warning(self, "エラー", "設定ダイアログモジュールが見つかりません。"); return
        dialog = SettingsDialog(self.current_settings, self)
        if dialog.exec(): self.current_settings = dialog.get_settings(); print("設定が更新されました:", self.current_settings)
        else: print("設定はキャンセルされました。")

    def start_scan(self):
        # (変更なし)
        print("スキャン開始ボタンがクリックされました"); selected_dir = self.dir_path_edit.text()
        if not selected_dir or not os.path.isdir(selected_dir): QMessageBox.warning(self, "エラー", "有効なフォルダが選択されていません。"); self.status_label.setText("ステータス: エラー (フォルダ未選択)"); return
        self.clear_results(); self.status_label.setText(f"ステータス: スキャン準備中... ({os.path.basename(selected_dir)})"); self.progress_bar.setVisible(True); self.progress_bar.setRange(0, 0); self.scan_button.setEnabled(False); self.settings_button.setEnabled(False)
        worker = ScanWorker(selected_dir, self.current_settings); worker.signals.progress.connect(self.update_status); worker.signals.results_ready.connect(self.populate_results); worker.signals.error.connect(self.scan_error); worker.signals.finished.connect(self.scan_finished); self.threadpool.start(worker)

    # --- スロット関数 (Workerからのシグナルを受け取る) ---
    @Slot(str)
    def update_status(self, message): self.status_label.setText(f"ステータス: {message}")

    @Slot(list, list)
    def populate_results(self, blurry_results, similar_results):
        """結果を受け取り、テーブルを更新するスロット (数値ソート対応)"""
        print(f"結果受信: ブレ画像={len(blurry_results)}, 類似ペア={len(similar_results)}")

        # --- ブレ画像テーブルの更新 (★スコア列に NumericTableWidgetItem を使用★) ---
        self.blurry_table.setSortingEnabled(False)
        self.blurry_table.setRowCount(len(blurry_results))
        for row, data in enumerate(blurry_results):
            path = data['path']
            score = data['score']
            dimensions = "N/A"
            try: img = cv2.imread(path); (img is not None) and (h := img.shape[0], w := img.shape[1], dimensions := f"{w}x{h}")
            except Exception as e: print(f"警告: ブレ画像の解像度取得エラー ({path}): {e}")

            chk_item = QTableWidgetItem(); chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled); chk_item.setCheckState(Qt.CheckState.Unchecked); chk_item.setData(Qt.ItemDataRole.UserRole, path)
            thumb_item = QTableWidgetItem("[T]")
            name_item = QTableWidgetItem(os.path.basename(path))
            path_item = QTableWidgetItem(path)
            dim_item = QTableWidgetItem(dimensions)
            # ★ スコアアイテムを NumericTableWidgetItem で作成 ★
            score_item = NumericTableWidgetItem(f"{score:.4f}")
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            self.blurry_table.setItem(row, 0, chk_item)
            self.blurry_table.setItem(row, 1, thumb_item)
            self.blurry_table.setItem(row, 2, name_item)
            self.blurry_table.setItem(row, 3, path_item)
            self.blurry_table.setItem(row, 4, dim_item)
            self.blurry_table.setItem(row, 5, score_item) # ★ ここで設定 ★
        self.blurry_table.setSortingEnabled(True)

        # --- 類似ペアテーブルの更新 (★類似度列に NumericTableWidgetItem を使用★) ---
        self.similar_table.setSortingEnabled(False)
        display_data = []; processed_pairs = set()
        for p1, p2, score in similar_results: pair_key = tuple(sorted((p1, p2))); (pair_key not in processed_pairs) and (display_data.append({'primary_path': p1, 'similar_path': p2, 'score': score}), processed_pairs.add(pair_key))
        self.similar_table.setRowCount(len(display_data))
        for row, data in enumerate(display_data):
            primary_path = data['primary_path']; similar_path = data['similar_path']; score = data['score']
            file_size = "N/A"; mod_time = "N/A"; dimensions = "N/A"
            try:
                stat_info = os.stat(primary_path); fb = stat_info.st_size; file_size = f"{fb} B" if fb < 1024 else f"{fb/1024:.1f} KB" if fb < 1024**2 else f"{fb/(1024**2):.1f} MB"; mod_time = time.strftime('%Y/%m/%d %H:%M', time.localtime(stat_info.st_mtime))
                img = cv2.imread(primary_path); (img is not None) and (h := img.shape[0], w := img.shape[1], dimensions := f"{w}x{h}")
            except Exception as e: print(f"警告: ファイル情報/解像度取得エラー ({primary_path}): {e}")

            thumb_item = QTableWidgetItem("[T]"); thumb_item.setData(Qt.ItemDataRole.UserRole, (primary_path, similar_path))
            name_item = QTableWidgetItem(os.path.basename(primary_path))
            size_item = QTableWidgetItem(file_size) # サイズも数値ソートしたい場合は Numeric にする（要単位変換）
            date_item = QTableWidgetItem(mod_time) # 日時もソート可能にするには工夫が必要
            dim_item = QTableWidgetItem(dimensions)
            sim_name_item = QTableWidgetItem(os.path.basename(similar_path))
            # ★ 類似度アイテムを NumericTableWidgetItem で作成 ★
            score_item = NumericTableWidgetItem(str(score)) # ORBスコアは整数
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            self.similar_table.setItem(row, 0, thumb_item)
            self.similar_table.setItem(row, 1, name_item)
            self.similar_table.setItem(row, 2, size_item)
            self.similar_table.setItem(row, 3, date_item)
            self.similar_table.setItem(row, 4, dim_item)
            self.similar_table.setItem(row, 5, sim_name_item)
            self.similar_table.setItem(row, 6, score_item) # ★ ここで設定 ★
        self.similar_table.setSortingEnabled(True)

        # タブの件数表示を更新
        self.results_tabs.setTabText(0, f"ブレ画像 ({self.blurry_table.rowCount()})"); self.results_tabs.setTabText(1, f"類似ペア ({len(similar_results)})")

    @Slot(str)
    def scan_error(self, message):
        # (変更なし)
        print(f"エラー受信: {message}"); QMessageBox.critical(self, "スキャンエラー", message); self.status_label.setText("ステータス: エラー発生"); self.progress_bar.setVisible(False); self.scan_button.setEnabled(True); self.settings_button.setEnabled(True)
    @Slot()
    def scan_finished(self):
        # (変更なし)
        print("スキャン完了シグナル受信"); self.status_label.setText("ステータス: スキャン完了"); self.progress_bar.setVisible(False); self.scan_button.setEnabled(True); self.settings_button.setEnabled(True)

    # --- その他のメソッド ---
    @Slot()
    def update_preview(self):
        # (変更なし - 前回の応答と同じコード)
        self.left_preview_path = None; self.right_preview_path = None # パス初期化
        current_tab_index = self.results_tabs.currentIndex()
        if current_tab_index == 0: table = self.blurry_table; is_similar_tab = False
        elif current_tab_index == 1: table = self.similar_table; is_similar_tab = True
        else: self._clear_previews(); return
        selected_items = table.selectedItems(); primary_path = None; secondary_path = None
        if selected_items:
            selected_rows = set(item.row() for item in selected_items)
            if len(selected_rows) == 1:
                selected_row = selected_rows.pop()
                if selected_row >= 0:
                    if is_similar_tab:
                        item_with_data = table.item(selected_row, 0)
                        if item_with_data: path_data = item_with_data.data(Qt.ItemDataRole.UserRole); isinstance(path_data, tuple) and len(path_data) == 2 and (primary_path := path_data[0], secondary_path := path_data[1])
                    else:
                        item_with_data = table.item(selected_row, 0)
                        if item_with_data: primary_path = item_with_data.data(Qt.ItemDataRole.UserRole)
        self.left_preview_path = primary_path # パスを保持
        self.right_preview_path = secondary_path if is_similar_tab else None # パスを保持
        self._display_image_in_preview(self.left_preview, self.left_preview_path, "左プレビュー")
        if is_similar_tab: self._display_image_in_preview(self.right_preview, self.right_preview_path, "右プレビュー")
        else: self.right_preview.clear(); self.right_preview.setText("右プレビュー")

    def _display_image_in_preview(self, target_label, image_path, label_name):
        # (変更なし - 前回の応答と同じコード)
        target_label.clear(); target_label.setText(f"{label_name}")
        if image_path and os.path.exists(image_path):
            try:
                img = cv2.imread(image_path)
                if img is not None:
                    rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB); h, w, ch = rgb_image.shape; bytes_per_line = ch * w
                    qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qt_image)
                    scaled_pixmap = pixmap.scaled(target_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    target_label.setPixmap(scaled_pixmap)
                else: target_label.setText(f"{label_name}\n(画像読込エラー)")
            except Exception as e: print(f"プレビュー画像読込エラー ({image_path}): {e}"); target_label.setText(f"{label_name}\n(読込エラー)")
        elif image_path: target_label.setText(f"{label_name}\n(ファイルなし)")

    def _clear_previews(self):
        # (変更なし)
        self.left_preview.clear(); self.left_preview.setText("左プレビュー\n(画像選択で表示)")
        self.right_preview.clear(); self.right_preview.setText("右プレビュー\n(類似ペア選択で表示)")
        self.left_preview_path = None; self.right_preview_path = None

    def clear_results(self):
        # (変更なし)
        self.blurry_table.setRowCount(0); self.similar_table.setRowCount(0)
        self.results_tabs.setTabText(0, "ブレ画像 (0)"); self.results_tabs.setTabText(1, "類似ペア (0)")
        self._clear_previews(); print("結果をクリアしました")

    def populate_dummy_data(self):
        # (★ スコアアイテムを NumericTableWidgetItem に変更 ★)
        self.clear_results()
        dummy_blurry = [(False, "[T]", "blurry_1.jpg", "D:/test/blurry_1.jpg", "1920x1080", 12.34),(False, "[T]", "blurry_2.png", "D:/test/subdir/blurry_2.png", "1280x720", 45.67)]
        self.blurry_table.setRowCount(len(dummy_blurry))
        for row, data in enumerate(dummy_blurry): checked, thumb, name, path, dims, score = data; chk_item = QTableWidgetItem(); chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled); chk_item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked); chk_item.setData(Qt.ItemDataRole.UserRole, path); thumb_item = QTableWidgetItem(thumb); name_item = QTableWidgetItem(name); path_item = QTableWidgetItem(path); dim_item = QTableWidgetItem(dims);
        score_item = NumericTableWidgetItem(f"{score:.4f}"); # ★ 変更 ★
        score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); self.blurry_table.setItem(row, 0, chk_item); self.blurry_table.setItem(row, 1, thumb_item); self.blurry_table.setItem(row, 2, name_item); self.blurry_table.setItem(row, 3, path_item); self.blurry_table.setItem(row, 4, dim_item); self.blurry_table.setItem(row, 5, score_item)
        self.results_tabs.setTabText(0, f"ブレ画像 ({self.blurry_table.rowCount()})")
        test_dir = self.dir_path_edit.text() if self.dir_path_edit.text() else "."; path_a = os.path.join(test_dir, "A.jpg"); path_b = os.path.join(test_dir, "B.jpg"); path_c = os.path.join(test_dir, "C.jpg"); dummy_similar_pairs = []
        if os.path.exists(path_a) and os.path.exists(path_b): dummy_similar_pairs.append((path_a, path_b, 95))
        if os.path.exists(path_a) and os.path.exists(path_c): dummy_similar_pairs.append((path_a, path_c, 92))
        display_data = []; processed_pairs = set()
        for p1, p2, score in dummy_similar_pairs: pair_key = tuple(sorted((p1, p2))); (pair_key not in processed_pairs) and (display_data.append({'primary_path': p1, 'similar_path': p2, 'score': score}), processed_pairs.add(pair_key))
        self.similar_table.setRowCount(len(display_data))
        for row, data in enumerate(display_data):
            primary_path = data['primary_path']; similar_path = data['similar_path']; score = data['score']; file_size = "N/A"; mod_time = "N/A"; dimensions = "N/A"
            try: stat_info = os.stat(primary_path); fb = stat_info.st_size; file_size = f"{fb} B" if fb < 1024 else f"{fb/1024:.1f} KB" if fb < 1024**2 else f"{fb/(1024**2):.1f} MB"; mod_time = time.strftime('%Y/%m/%d %H:%M', time.localtime(stat_info.st_mtime)); img = cv2.imread(primary_path); (img is not None) and (h := img.shape[0], w := img.shape[1], dimensions := f"{w}x{h}")
            except: pass
            thumb_item = QTableWidgetItem("[T]"); thumb_item.setData(Qt.ItemDataRole.UserRole, (primary_path, similar_path)); name_item = QTableWidgetItem(os.path.basename(primary_path)); size_item = QTableWidgetItem(file_size); date_item = QTableWidgetItem(mod_time); dim_item = QTableWidgetItem(dimensions); sim_name_item = QTableWidgetItem(os.path.basename(similar_path));
            score_item = NumericTableWidgetItem(str(score)); # ★ 変更 ★
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); self.similar_table.setItem(row, 0, thumb_item); self.similar_table.setItem(row, 1, name_item); self.similar_table.setItem(row, 2, size_item); self.similar_table.setItem(row, 3, date_item); self.similar_table.setItem(row, 4, dim_item); self.similar_table.setItem(row, 5, sim_name_item); self.similar_table.setItem(row, 6, score_item)
        self.results_tabs.setTabText(1, f"類似ペア ({self.similar_table.rowCount()})")

    @Slot()
    def delete_selected_items(self):
        # (変更なし - 前回の応答と同じコード)
        if send2trash is None: QMessageBox.critical(self, "エラー", "send2trash ライブラリが見つかりません。\n削除機能を使用できません。"); return
        files_to_delete = []
        for row in range(self.blurry_table.rowCount()): chk_item = self.blurry_table.item(row, 0); (chk_item and chk_item.checkState() == Qt.CheckState.Checked) and (file_path := chk_item.data(Qt.ItemDataRole.UserRole)) and files_to_delete.append(file_path) # Python 3.8+
        selected_rows = set(item.row() for item in self.similar_table.selectedItems())
        for row in selected_rows: item_with_data = self.similar_table.item(row, 0); (item_with_data and (path_data := item_with_data.data(Qt.ItemDataRole.UserRole)) and isinstance(path_data, tuple) and len(path_data) == 2) and (primary_path := path_data[0]) and files_to_delete.append(primary_path) # Python 3.8+
        unique_files_to_delete = sorted(list(set(files_to_delete)))
        if not unique_files_to_delete: QMessageBox.information(self, "情報", "削除対象のファイルが選択されていません。"); return
        num_files = len(unique_files_to_delete); message = f"{num_files} 個のファイルを選択しました。\nこれらのファイルをゴミ箱に移動しますか？\n\n"; display_limit = 10; message += "\n".join([os.path.basename(f) for f in unique_files_to_delete[:display_limit]]) + (f"\n...他 {num_files - display_limit} 個" if num_files > display_limit else "")
        reply = QMessageBox.question(self, "削除の確認", message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            print(f"{num_files} 個のファイルをゴミ箱へ移動します..."); deleted_count = 0; errors = []; files_actually_deleted = set()
            for file_path in unique_files_to_delete:
                try:
                    normalized_path = os.path.normpath(file_path)
                    if os.path.exists(normalized_path): send2trash.send2trash(normalized_path); print(f"  削除成功: {normalized_path}"); deleted_count += 1; files_actually_deleted.add(normalized_path)
                    else: print(f"  削除スキップ: ファイルが見つかりません {normalized_path}"); errors.append(f"{os.path.basename(normalized_path)}: ファイルが見つかりません")
                except Exception as e: print(f"  削除エラー: {file_path} - {e}"); errors.append(f"{os.path.basename(file_path)}: {e}")
            if errors: QMessageBox.warning(self, "削除エラー", f"{len(errors)} 個のファイルの削除中にエラーが発生しました:\n" + "\n".join(errors))
            if deleted_count > 0: QMessageBox.information(self, "削除完了", f"{deleted_count} 個のファイルをゴミ箱に移動しました。")
            if files_actually_deleted: self._remove_deleted_items_from_table(files_actually_deleted)

    def _remove_deleted_items_from_table(self, deleted_file_paths_set):
        # (変更なし - 前回の応答と同じコード)
        if not deleted_file_paths_set: return
        rows_to_remove_blurry = [row for row in range(self.blurry_table.rowCount()) if (chk_item := self.blurry_table.item(row, 0)) and (file_path := chk_item.data(Qt.ItemDataRole.UserRole)) and os.path.normpath(file_path) in deleted_file_paths_set]
        for row in sorted(rows_to_remove_blurry, reverse=True): self.blurry_table.removeRow(row)
        rows_to_remove_similar = [row for row in range(self.similar_table.rowCount()) if (item := self.similar_table.item(row, 0)) and (path_data := item.data(Qt.ItemDataRole.UserRole)) and isinstance(path_data, tuple) and len(path_data) == 2 and ((p1n := os.path.normpath(path_data[0]) if path_data[0] else None) and p1n in deleted_file_paths_set or (p2n := os.path.normpath(path_data[1]) if path_data[1] else None) and p2n in deleted_file_paths_set)] # Python 3.8+
        for row in sorted(list(set(rows_to_remove_similar)), reverse=True): self.similar_table.removeRow(row)
        self.results_tabs.setTabText(0, f"ブレ画像 ({self.blurry_table.rowCount()})"); self.results_tabs.setTabText(1, f"類似ペア ({self.similar_table.rowCount()})"); self._clear_previews()

    def _open_file_external(self, file_path):
        # (変更なし - 前回の応答と同じコード)
        if not file_path or not os.path.exists(file_path): print(f"ファイルが見つかりません: {file_path}"); QMessageBox.warning(self, "エラー", f"ファイルが見つかりません:\n{file_path}"); return
        try: os.startfile(os.path.normpath(file_path)); print(f"ファイルを開きました: {file_path}")
        except Exception as e: print(f"ファイルを開けませんでした ({file_path}): {e}"); QMessageBox.critical(self, "エラー", f"ファイルを開けませんでした:\n{file_path}\n\n{e}")

    def keyPressEvent(self, event: QKeyEvent):
        # (変更なし - 前回の応答と同じコード)
        key = event.key()
        if key == Qt.Key.Key_Q: print("'Q' キーが押されました (左プレビュー削除)"); self.left_preview_path and self._delete_single_file(self.left_preview_path)
        elif key == Qt.Key.Key_W: print("'W' キーが押されました (右プレビュー削除)"); self.right_preview_path and self._delete_single_file(self.right_preview_path)
        elif key == Qt.Key.Key_A: print("'A' キーが押されました (左プレビューを開く)"); self.left_preview_path and self._open_file_external(self.left_preview_path)
        elif key == Qt.Key.Key_S: print("'S' キーが押されました (右プレビューを開く)"); self.right_preview_path and self._open_file_external(self.right_preview_path)
        else: super().keyPressEvent(event)

    def on_left_preview_clicked(self, event: QMouseEvent):
        # (変更なし - 前回の応答と同じコード)
        if event.button() == Qt.MouseButton.LeftButton: print("左プレビューがクリックされました (削除)"); self.left_preview_path and self._delete_single_file(self.left_preview_path)
    def on_right_preview_clicked(self, event: QMouseEvent):
        # (変更なし - 前回の応答と同じコード)
        if event.button() == Qt.MouseButton.LeftButton: print("右プレビューがクリックされました (削除)"); self.right_preview_path and self._delete_single_file(self.right_preview_path)

    @Slot()
    def select_all_blurry(self):
        # (変更なし)
        print("全選択(ブレ)クリック"); [self.blurry_table.item(row, 0).setCheckState(Qt.CheckState.Checked) for row in range(self.blurry_table.rowCount()) if (item := self.blurry_table.item(row, 0)) and item.flags() & Qt.ItemFlag.ItemIsUserCheckable]
    @Slot()
    def select_all_similar(self):
        # (変更なし)
        print("全選択(類似ペア)クリック"); self.similar_table.selectAll()
    @Slot()
    def deselect_all(self):
        # (変更なし)
        print("全選択解除クリック"); [self.blurry_table.item(row, 0).setCheckState(Qt.CheckState.Unchecked) for row in range(self.blurry_table.rowCount()) if (item := self.blurry_table.item(row, 0)) and item.flags() & Qt.ItemFlag.ItemIsUserCheckable]; self.similar_table.clearSelection(); self._clear_previews()

# --- アプリケーション起動部分はここには書かない (main.py に記述) ---