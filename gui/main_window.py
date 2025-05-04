# gui/main_window.py
import sys
import os
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QFileDialog, QProgressBar,
    QMessageBox, QMenuBar # QMenuBar はテーマ用
)
from PySide6.QtCore import Qt, QThreadPool, Slot, QDir
from PySide6.QtGui import QCloseEvent, QKeyEvent, QAction, QActionGroup # QAction, QActionGroup はテーマ用
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any, Union, Set

# 型エイリアス (変更なし)
SettingsDict = Dict[str, Any]
BlurResultItem = Dict[str, Union[str, float]]
SimilarPair = List[Union[str, int]]
DuplicateDict = Dict[str, List[str]]
ErrorDict = Dict[str, str]
ResultsData = Dict[str, Union[List[BlurResultItem], List[SimilarPair], DuplicateDict, List[ErrorDict]]]
LoadResult = Tuple[Optional[ResultsData], Optional[str], Optional[SettingsDict], Optional[str]]
DeleteResult = Tuple[int, List[ErrorDict], Set[str]]
ScanStateData = Dict[str, Any]
LoadStateResult = Tuple[Optional[ScanStateData], Optional[str]]

# --- ウィジェット、ワーカー、ダイアログをインポート (変更なし) ---
try:
    from .widgets.preview_widget import PreviewWidget
    from .widgets.results_tabs_widget import ResultsTabsWidget
    from .workers import ScanWorker, WorkerSignals
    from .dialogs.settings_dialog import SettingsDialog
except ImportError as e: print(f"エラー: GUIコンポーネントのインポートに失敗 ({e})"); import traceback; traceback.print_exc(); sys.exit(1)

# --- ユーティリティ関数をインポート (変更なし) ---
try:
    from utils.config_handler import load_settings, save_settings
    from utils.file_operations import delete_files_to_trash, open_file_external
    from utils.results_handler import save_results_to_file, load_results_from_file, load_scan_state, delete_scan_state, get_state_filepath
except ImportError as e:
    print(f"エラー: ユーティリティモジュールのインポートに失敗 ({e})")
    def load_settings() -> SettingsDict: return {'last_directory': os.path.expanduser("~"), 'theme': 'light'}
    def save_settings(s: SettingsDict) -> bool: print("警告: 設定保存機能が無効"); return False
    def delete_files_to_trash(fps: List[str], p: Optional[QWidget] = None) -> DeleteResult: print("警告: 削除機能が無効"); return 0, [], set()
    def open_file_external(fp: str, p: Optional[QWidget] = None) -> None: print("警告: ファイルを開く機能が無効")
    def save_results_to_file(fp: str, res: ResultsData, sdir: str, sets: Optional[SettingsDict] = None) -> bool: print("警告: 結果保存機能が無効"); return False
    def load_results_from_file(fp: str) -> LoadResult: print("警告: 結果読込機能が無効"); return None, None, None, "結果読込機能が無効です"
    def load_scan_state(dir_path: str) -> LoadStateResult: print("警告: 状態読み込み機能が無効"); return None, "状態読み込み機能が無効です"
    def delete_scan_state(dir_path: str) -> bool: print("警告: 状態削除機能が無効"); return False
    def get_state_filepath(dir_path: str) -> str: return os.path.join(dir_path, ".image_cleaner_scan_state.json")


class ImageCleanerWindow(QMainWindow):
    """アプリケーションのメインウィンドウクラス"""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("画像クリーナー")
        self.setGeometry(100, 100, 1000, 750)
        self.threadpool: QThreadPool = QThreadPool()
        self.current_settings: SettingsDict = load_settings()
        # UI要素の型ヒント
        self.dir_label: QLabel; self.dir_path_edit: QLineEdit; self.select_dir_button: QPushButton
        self.settings_button: QPushButton; self.save_results_button: QPushButton; self.load_results_button: QPushButton
        self.scan_button: QPushButton; self.cancel_button: QPushButton
        self.status_label: QLabel; self.current_file_label: QLabel
        self.progress_bar: QProgressBar
        self.preview_widget: PreviewWidget; self.results_tabs_widget: ResultsTabsWidget
        self.delete_button: QPushButton; self.select_all_blurry_button: QPushButton
        # ★★★ select_all_similar_button を削除 ★★★
        # self.select_all_similar_button: QPushButton
        self.select_all_duplicates_button: QPushButton; self.deselect_all_button: QPushButton
        # --- その他のインスタンス変数 (変更なし) ---
        self.current_worker: Optional[ScanWorker] = None
        self.results_saved: bool = True
        self.light_theme_action: Optional[QAction] = None
        self.dark_theme_action: Optional[QAction] = None

        self._setup_ui()
        self._setup_menu()
        self._connect_signals()
        initial_theme = self.current_settings.get('theme', 'light')
        self._apply_theme(initial_theme)
        if initial_theme == 'dark' and self.dark_theme_action: self.dark_theme_action.setChecked(True)
        elif self.light_theme_action: self.light_theme_action.setChecked(True)


    def _setup_ui(self) -> None:
        main_widget = QWidget(); self.setCentralWidget(main_widget); main_layout = QVBoxLayout(main_widget); main_layout.setContentsMargins(10, 10, 10, 10)
        # --- フォルダ選択、設定、スキャン実行エリア (変更なし) ---
        input_layout = QHBoxLayout(); self.dir_label = QLabel("対象フォルダ:"); self.dir_path_edit = QLineEdit(); self.dir_path_edit.setReadOnly(True); self.select_dir_button = QPushButton("フォルダを選択..."); input_layout.addWidget(self.dir_label); input_layout.addWidget(self.dir_path_edit, 1); input_layout.addWidget(self.select_dir_button); main_layout.addLayout(input_layout); main_layout.addSpacing(5)
        config_layout = QHBoxLayout(); self.settings_button = QPushButton("設定..."); self.save_results_button = QPushButton("結果を保存..."); self.load_results_button = QPushButton("結果を読み込み..."); config_layout.addWidget(self.settings_button); config_layout.addWidget(self.save_results_button); config_layout.addWidget(self.load_results_button); config_layout.addStretch(); main_layout.addLayout(config_layout); main_layout.addSpacing(10)
        proc_layout = QHBoxLayout(); self.scan_button = QPushButton("スキャン開始"); self.cancel_button = QPushButton("中止"); self.cancel_button.setVisible(False); self.status_label = QLabel("ステータス: 待機中"); self.status_label.setWordWrap(True); proc_layout.addWidget(self.scan_button); proc_layout.addWidget(self.cancel_button); proc_layout.addWidget(self.status_label, 1); main_layout.addLayout(proc_layout)
        self.current_file_label = QLabel(" "); self.current_file_label.setStyleSheet("QLabel { color: grey; font-size: 9pt; }"); self.current_file_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); main_layout.addWidget(self.current_file_label)
        self.progress_bar = QProgressBar(); self.progress_bar.setVisible(False); self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter); main_layout.addWidget(self.progress_bar); main_layout.addSpacing(10)
        # --- プレビュー、結果タブ (変更なし) ---
        self.preview_widget = PreviewWidget(self); preview_frame = QFrame(); preview_frame.setFrameShape(QFrame.Shape.StyledPanel); preview_frame_layout = QVBoxLayout(preview_frame); preview_frame_layout.setContentsMargins(0,0,0,0); preview_frame_layout.addWidget(self.preview_widget); preview_frame.setFixedHeight(250); main_layout.addWidget(preview_frame, stretch=0); main_layout.addSpacing(10)
        self.results_tabs_widget = ResultsTabsWidget(self); main_layout.addWidget(self.results_tabs_widget, stretch=1); main_layout.addSpacing(10)
        # --- アクションボタンエリア ---
        action_layout = QHBoxLayout()
        self.delete_button = QPushButton("選択した項目をゴミ箱へ移動")
        self.delete_button.setToolTip("現在表示中のタブで選択/チェックされた項目を削除します。\n(重複タブではチェックされたもののみ)")
        self.select_all_blurry_button = QPushButton("全選択(ブレ)")
        # ★★★ select_all_similar_button を削除 ★★★
        # self.select_all_similar_button = QPushButton("全選択(類似ペア)")
        self.select_all_duplicates_button = QPushButton("全選択(重複, 除く先頭)")
        self.deselect_all_button = QPushButton("全選択解除")
        action_layout.addWidget(self.delete_button)
        action_layout.addStretch()
        action_layout.addWidget(self.select_all_blurry_button)
        # ★★★ レイアウトからも削除 ★★★
        # action_layout.addWidget(self.select_all_similar_button)
        action_layout.addWidget(self.select_all_duplicates_button)
        action_layout.addWidget(self.deselect_all_button)
        main_layout.addLayout(action_layout)
        # --- 初期状態設定 ---
        self._set_scan_controls_enabled(False)
        self._set_action_buttons_enabled(False) # ★ 修正 ★
        self.save_results_button.setEnabled(False)
        self.load_results_button.setEnabled(True)

    def _setup_menu(self):
        # (変更なし)
        menu_bar = self.menuBar();
        if menu_bar is None: menu_bar = QMenuBar(self); self.setMenuBar(menu_bar)
        view_menu = menu_bar.addMenu("表示(&V)")
        theme_menu = view_menu.addMenu("テーマ(&T)")
        theme_group = QActionGroup(self); theme_group.setExclusive(True)
        self.light_theme_action = QAction("ライト", self, checkable=True)
        self.light_theme_action.triggered.connect(lambda: self._switch_theme('light'))
        theme_menu.addAction(self.light_theme_action); theme_group.addAction(self.light_theme_action)
        self.dark_theme_action = QAction("ダーク", self, checkable=True)
        self.dark_theme_action.triggered.connect(lambda: self._switch_theme('dark'))
        theme_menu.addAction(self.dark_theme_action); theme_group.addAction(self.dark_theme_action)

    def _load_stylesheet(self, filename: str) -> str:
        # (変更なし)
        basedir = os.path.dirname(__file__); style_path = os.path.join(basedir, "styles", filename)
        if not os.path.exists(style_path) and hasattr(sys, '_MEIPASS'): style_path = os.path.join(sys._MEIPASS, "gui", "styles", filename)
        if os.path.exists(style_path):
            try:
                with open(style_path, "r", encoding="utf-8") as f: return f.read()
            except OSError as e: print(f"警告: スタイルシートの読み込みに失敗 ({filename}): {e}")
        else: print(f"警告: スタイルシートファイルが見つかりません: {style_path}")
        return ""

    def _apply_theme(self, theme_name: str):
        # (変更なし)
        qss_filename = f"{theme_name}.qss"; stylesheet = self._load_stylesheet(qss_filename)
        if stylesheet: QApplication.instance().setStyleSheet(stylesheet); print(f"テーマ '{theme_name}' を適用しました。")
        else: QApplication.instance().setStyleSheet(""); print(f"テーマ '{theme_name}' のスタイルシートが見つかりません。デフォルトスタイルを適用します。")

    @Slot(str)
    def _switch_theme(self, theme_name: str):
        # (変更なし)
        if theme_name != self.current_settings.get('theme'):
            self._apply_theme(theme_name); self.current_settings['theme'] = theme_name; print(f"設定を '{theme_name}' テーマに更新しました。")

    def _connect_signals(self) -> None:
        self.select_dir_button.clicked.connect(self.select_directory)
        self.settings_button.clicked.connect(self.open_settings)
        self.scan_button.clicked.connect(self.start_scan)
        self.cancel_button.clicked.connect(self.request_scan_cancellation)
        self.save_results_button.clicked.connect(self.save_results)
        self.load_results_button.clicked.connect(self.load_results)
        self.delete_button.clicked.connect(self.delete_selected_items)
        self.select_all_blurry_button.clicked.connect(self.results_tabs_widget.select_all_blurry)
        # ★★★ select_all_similar_button の接続を削除 ★★★
        # self.select_all_similar_button.clicked.connect(self.results_tabs_widget.select_all_similar)
        self.select_all_duplicates_button.clicked.connect(self.results_tabs_widget.select_all_duplicates)
        self.deselect_all_button.clicked.connect(self.results_tabs_widget.deselect_all)
        self.results_tabs_widget.selection_changed.connect(self.update_preview_display)
        # ★★★ プレビュークリックのシグナル接続を確認 ★★★
        self.preview_widget.left_preview_clicked.connect(self._delete_single_file_from_preview)
        self.preview_widget.right_preview_clicked.connect(self._delete_single_file_from_preview)
        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
        self.results_tabs_widget.delete_file_requested.connect(self._handle_delete_request)
        self.results_tabs_widget.open_file_requested.connect(self._handle_open_request)
        self.results_tabs_widget.delete_duplicates_requested.connect(self._handle_delete_duplicates_request)

    # --- スロット関数 ---
    @Slot()
    def select_directory(self) -> None:
        # (変更なし)
        last_dir: str = str(self.current_settings.get('last_directory', os.path.expanduser("~")))
        dir_path: str = QFileDialog.getExistingDirectory(self, "フォルダを選択", last_dir)
        if dir_path:
            state_filepath = get_state_filepath(dir_path)
            resume_state: Optional[ScanStateData] = None
            if os.path.exists(state_filepath):
                reply = QMessageBox.question(self, "中断されたスキャン", f"...", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.Yes:
                    loaded_state, error_msg = load_scan_state(dir_path)
                    if error_msg: QMessageBox.warning(self, "状態読み込みエラー", f"..."); delete_scan_state(dir_path)
                    else: resume_state = loaded_state; print("スキャン再開を選択しました。")
                elif reply == QMessageBox.StandardButton.No: print("新規スキャンを選択しました..."); delete_scan_state(dir_path)
                else: print("フォルダ選択をキャンセルしました。"); return
            self.dir_path_edit.setText(dir_path); self.current_settings['last_directory'] = dir_path
            self._clear_all_results(); self._update_ui_state(scan_enabled=True, actions_enabled=False, cancel_enabled=False)
            if resume_state: self.status_label.setText("ステータス: 中断されたスキャンを再開します..."); self.start_scan(initial_state=resume_state)
            else: self.status_label.setText("ステータス: フォルダを選択しました...")

    @Slot()
    def open_settings(self) -> None:
        # (変更なし)
        if SettingsDialog is None: QMessageBox.warning(self, "エラー", "..."); return
        dialog = SettingsDialog(self.current_settings, self);
        if dialog.exec(): self.current_settings = dialog.get_settings(); print("設定が更新されました:", self.current_settings)
        else: print("設定はキャンセルされました。")

    @Slot()
    def start_scan(self, initial_state: Optional[ScanStateData] = None) -> None:
        # (変更なし、シグナル接続はここで)
        selected_dir: str = self.dir_path_edit.text()
        if not self._validate_directory(selected_dir): return
        if initial_state is None and not self._confirm_unsaved_results("新しいスキャンを開始"): return
        if initial_state is None: delete_scan_state(selected_dir)
        self._clear_all_results(); status_msg = f"ステータス: スキャン準備中..."
        if initial_state: status_msg = f"ステータス: スキャン再開中..."
        self.status_label.setText(status_msg); self.current_file_label.setText(" ")
        self._set_progress_bar_visible(True); self._update_ui_state(scan_enabled=False, actions_enabled=False, cancel_enabled=True)
        self.current_worker = ScanWorker(selected_dir, self.current_settings, initial_state=initial_state)
        self.current_worker.signals.status_update.connect(self.update_status)
        self.current_worker.signals.progress_update.connect(self.update_progress_bar)
        if hasattr(self.current_worker.signals, 'processing_file'): self.current_worker.signals.processing_file.connect(self.update_current_file)
        self.current_worker.signals.results_ready.connect(self.populate_results_and_update_state)
        self.current_worker.signals.error.connect(self.handle_scan_error)
        self.current_worker.signals.finished.connect(self.handle_scan_finished)
        self.current_worker.signals.cancelled.connect(self.handle_scan_cancelled)
        self.threadpool.start(self.current_worker)

    @Slot()
    def request_scan_cancellation(self) -> None:
        # (変更なし)
        if self.current_worker: self.status_label.setText("ステータス: 中止処理中..."); self.cancel_button.setEnabled(False); self.current_worker.request_cancellation()
        else: print("警告: 中止対象のワーカースレッドが見つかりません。")
    @Slot(str)
    def update_status(self, message: str) -> None: self.status_label.setText(f"ステータス: {message}")
    @Slot(int)
    def update_progress_bar(self, value: int) -> None: self.progress_bar.setValue(value)
    @Slot(str)
    def update_current_file(self, filename: str) -> None:
        if filename: max_len = 60; filename = ("..." + filename[-(max_len-3):]) if len(filename) > max_len else filename; self.current_file_label.setText(f"処理中: {filename}")
        else: self.current_file_label.setText(" ")
    @Slot(list, list, dict, list)
    def populate_results_and_update_state(self, blurry: List[BlurResultItem], similar: List[SimilarPair], duplicates: DuplicateDict, errors: List[ErrorDict]) -> None:
        # (変更なし)
        self.results_tabs_widget.populate_results(blurry, similar, duplicates, errors); has_results: bool = bool(blurry or similar or duplicates); self._update_ui_state(scan_enabled=True, actions_enabled=has_results, cancel_enabled=False); self.results_saved = False; self.current_worker = None
    @Slot(str)
    def handle_scan_error(self, message: str) -> None:
        # (変更なし)
        print(f"致命的エラー受信: {message}"); QMessageBox.critical(self, "スキャンエラー", f"..."); self.status_label.setText(f"ステータス: 致命的エラー..."); self._set_progress_bar_visible(False); self._update_ui_state(scan_enabled=bool(self.dir_path_edit.text()), actions_enabled=False, cancel_enabled=False); self.current_file_label.setText(" "); self.current_worker = None
    @Slot()
    def handle_scan_finished(self) -> None:
        # (変更なし)
        print("スキャン完了シグナル受信"); error_count: int = self.results_tabs_widget.error_table.rowCount()
        if error_count > 0: self.status_label.setText(f"ステータス: スキャン完了 ({error_count}件のエラーあり)")
        else: self.status_label.setText("ステータス: スキャン完了")
        self._set_progress_bar_visible(False); self._update_ui_state(scan_enabled=True, cancel_enabled=False); self.current_file_label.setText(" ")
        if self.dir_path_edit.text(): delete_scan_state(self.dir_path_edit.text())
        self.current_worker = None
    @Slot()
    def handle_scan_cancelled(self) -> None:
        # (変更なし)
        print("スキャン中止シグナル受信"); self.status_label.setText("ステータス: スキャンが中断されました。"); self._set_progress_bar_visible(False); self._update_ui_state(scan_enabled=True, actions_enabled=False, cancel_enabled=False); self.current_file_label.setText(" "); self.current_worker = None
    @Slot()
    def update_preview_display(self) -> None:
        # (変更なし)
        primary_path, secondary_path = self.results_tabs_widget.get_current_selection_paths(); self.preview_widget.update_previews(primary_path, secondary_path)
    @Slot()
    def delete_selected_items(self) -> None:
        # (変更なし)
        files_to_delete: List[str] = self._get_files_to_delete_from_current_tab();
        if not files_to_delete: return; self._delete_files_and_update_ui(files_to_delete)

    # ★★★ このスロットでプレビュークリックからの削除要求を処理 ★★★
    @Slot(str)
    def _delete_single_file_from_preview(self, file_path: str) -> None:
        print(f"プレビュークリック削除要求受信: {file_path}")
        if not file_path: return
        # 確認ダイアログを表示
        filename = os.path.basename(file_path)
        reply = QMessageBox.question(self, "削除の確認", f"プレビューの画像 '{filename}' をゴミ箱に移動しますか？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._delete_files_and_update_ui([file_path])
        else:
            print("プレビューからの削除はキャンセルされました。")
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

    @Slot(str)
    def _handle_delete_request(self, file_path: str) -> None:
        # コンテキストメニューからの削除要求 (確認は delete_files_to_trash 内で行われる)
        if not file_path: return
        self._delete_files_and_update_ui([file_path])
    @Slot(str)
    def _handle_open_request(self, file_path: str) -> None:
        # (変更なし)
        print(f"オープン要求受信: {file_path}");
        if file_path: open_file_external(file_path, self)
    @Slot(str, list)
    def _handle_delete_duplicates_request(self, keep_path: str, delete_paths: List[str]) -> None:
        # (変更なし)
        if not delete_paths: return; print(f"重複グループ削除要求受信...");
        if self._confirm_duplicate_deletion(keep_path, delete_paths): self._delete_files_and_update_ui(delete_paths)
        else: print("重複グループの削除はキャンセルされました。")
    @Slot()
    def save_results(self) -> None:
        # (変更なし)
        current_dir: str = self.dir_path_edit.text();
        if not self._validate_directory(current_dir, "保存"): return
        filepath: Optional[str] = self._get_save_filepath(current_dir)
        if not filepath: return
        self.current_settings['last_save_load_dir'] = os.path.dirname(filepath); results_data: ResultsData = self.results_tabs_widget.get_results_data(); success: bool = save_results_to_file(filepath, results_data, current_dir, self.current_settings)
        if success: QMessageBox.information(self, "保存完了", f"..."); self.results_saved = True
        else: QMessageBox.critical(self, "保存エラー", "...")
    @Slot()
    def load_results(self) -> None:
        # (変更なし)
        if not self.results_saved:
             if not self._confirm_unsaved_results("結果を読み込み"): return
        filepath: Optional[str] = self._get_load_filepath()
        if not filepath: return
        self.current_settings['last_save_load_dir'] = os.path.dirname(filepath)
        results_data: Optional[ResultsData]; scanned_directory: Optional[str]; settings_used: Optional[SettingsDict]; error_message: Optional[str]
        results_data, scanned_directory, settings_used, error_message = load_results_from_file(filepath)
        if error_message: QMessageBox.critical(self, "読み込みエラー", f"..."); return
        current_target_dir: str = self.dir_path_edit.text()
        if not self._confirm_directory_mismatch(scanned_directory, current_target_dir): return
        if scanned_directory and scanned_directory != current_target_dir: self.dir_path_edit.setText(scanned_directory)
        self._clear_all_results()
        if results_data: self.results_tabs_widget.populate_results(results_data.get('blurry', []), results_data.get('similar', []), results_data.get('duplicates', {}), results_data.get('errors', []))
        if settings_used: print("読み込んだ結果のスキャン時設定:", settings_used)
        self.status_label.setText(f"ステータス: 結果を読み込みました..."); has_results: bool = bool(results_data and (results_data.get('blurry') or results_data.get('similar') or results_data.get('duplicates'))); self._update_ui_state(scan_enabled=True, actions_enabled=has_results, cancel_enabled=False); self.results_saved = True

    # --- ヘルパーメソッド ---
    def _clear_all_results(self) -> None: # (変更なし)
        self.results_tabs_widget.clear_results(); self.preview_widget.clear_previews(); self.results_saved = True; self.current_file_label.setText(" ")
    def _validate_directory(self, dir_path: str, action_name: str = "処理") -> bool: # (変更なし)
        if not dir_path or not os.path.isdir(dir_path): QMessageBox.warning(self, "エラー", f"..."); self.status_label.setText(f"ステータス: エラー..."); return False
        return True
    def _confirm_unsaved_results(self, action_name: str) -> bool: # (変更なし)
        if not self.results_saved: reply = QMessageBox.question(self, "確認", f"...", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No); return reply == QMessageBox.StandardButton.Yes
        return True
    def _confirm_duplicate_deletion(self, keep_path: str, delete_paths: List[str]) -> bool: # (変更なし)
        message: str = f"..."; display_limit: int = 10
        if len(delete_paths) <= display_limit: message += "\n".join([f"- {os.path.basename(f)}" for f in delete_paths])
        else: message += "\n".join([f"- {os.path.basename(f)}" for f in delete_paths[:display_limit]]) + f"\n...他 {len(delete_paths) - display_limit} 個"
        reply = QMessageBox.question(self, "重複ファイルの削除確認", message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No); return reply == QMessageBox.StandardButton.Yes
    def _get_save_filepath(self, current_dir: str) -> Optional[str]: # (変更なし)
        timestamp: str = datetime.now().strftime('%Y%m%d_%H%M%S'); default_filename: str = f"..."; save_dir: str = str(self.current_settings.get('last_save_load_dir', current_dir)); filepath, _ = QFileDialog.getSaveFileName(self, "結果を保存", os.path.join(save_dir, default_filename), "JSON Files (*.json)"); return filepath if filepath else None
    def _get_load_filepath(self) -> Optional[str]: # (変更なし)
        load_dir: str = str(self.current_settings.get('last_save_load_dir', os.path.expanduser("~"))); filepath, _ = QFileDialog.getOpenFileName(self, "結果を読み込み", load_dir, "JSON Files (*.json)"); return filepath if filepath else None
    def _confirm_directory_mismatch(self, loaded_dir: Optional[str], current_dir: str) -> bool: # (変更なし)
        if loaded_dir and loaded_dir != current_dir: reply = QMessageBox.warning(self, "フォルダ不一致", f"...", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No); return reply == QMessageBox.StandardButton.Yes
        return True
    def _get_files_to_delete_from_current_tab(self) -> List[str]: # (変更なし)
        files_to_delete: List[str] = []; current_tab_index: int = self.results_tabs_widget.currentIndex(); msg: str = ""
        if current_tab_index == 0: files_to_delete = self.results_tabs_widget.get_selected_blurry_paths(); msg = "..."
        elif current_tab_index == 1: files_to_delete = self.results_tabs_widget.get_selected_similar_primary_paths(); msg = "..." # このボタンは削除したがロジックは残す
        elif current_tab_index == 2: files_to_delete = self.results_tabs_widget.get_selected_duplicate_paths(); msg = "..."
        elif current_tab_index == 3: QMessageBox.information(self, "情報", "..."); return []
        else: return []
        if not files_to_delete: QMessageBox.information(self, "情報", msg)
        return files_to_delete
    def _delete_files_and_update_ui(self, files_to_delete: List[str]) -> None: # (変更なし)
        if not files_to_delete: return
        deleted_count: int; errors: List[ErrorDict]; files_actually_deleted: Set[str]; deleted_count, errors, files_actually_deleted = delete_files_to_trash(files_to_delete, self)
        if files_actually_deleted: self.results_tabs_widget.remove_items_by_paths(files_actually_deleted); self.preview_widget.clear_previews(); has_results: bool = self.results_tabs_widget.blurry_table.rowCount() > 0 or self.results_tabs_widget.similar_table.rowCount() > 0 or self.results_tabs_widget.duplicate_table.rowCount() > 0; self._update_ui_state(actions_enabled=has_results); self.results_saved = False
    def _set_scan_controls_enabled(self, enabled: bool) -> None: # (変更なし)
        self.scan_button.setEnabled(enabled); self.settings_button.setEnabled(enabled)
    def _set_action_buttons_enabled(self, enabled: bool) -> None:
        # ★★★ select_all_similar_button を削除 ★★★
        self.delete_button.setEnabled(enabled)
        self.select_all_blurry_button.setEnabled(enabled)
        # self.select_all_similar_button.setEnabled(enabled)
        self.select_all_duplicates_button.setEnabled(enabled)
        self.deselect_all_button.setEnabled(enabled)
    def _set_progress_bar_visible(self, visible: bool) -> None: # (変更なし)
        self.progress_bar.setVisible(visible); (not visible) and self.progress_bar.setValue(0)
    def _update_ui_state(self, scan_enabled: Optional[bool] = None, actions_enabled: Optional[bool] = None, cancel_enabled: Optional[bool] = None) -> None: # (変更なし)
        if scan_enabled is not None: self._set_scan_controls_enabled(scan_enabled); self.load_results_button.setEnabled(scan_enabled); self.scan_button.setVisible(not cancel_enabled if cancel_enabled is not None else scan_enabled)
        if actions_enabled is not None: self._set_action_buttons_enabled(actions_enabled); self.save_results_button.setEnabled(actions_enabled)
        if cancel_enabled is not None: self.cancel_button.setVisible(cancel_enabled); self.cancel_button.setEnabled(cancel_enabled)

    # --- イベントハンドラ ---
    def closeEvent(self, event: QCloseEvent) -> None:
        # (変更なし)
        if self.current_worker and not self._cancellation_requested:
             reply = QMessageBox.question(self, "確認", "...", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
             if reply == QMessageBox.StandardButton.Yes: print("終了前にスキャンを中止します..."); self.request_scan_cancellation()
             else: event.ignore(); return
        if not save_settings(self.current_settings): print("警告: 設定ファイルの保存に失敗しました。")
        else: print("アプリケーション終了時に設定を保存しました。")
        event.accept()
    def keyPressEvent(self, event: QKeyEvent) -> None:
        # (変更なし)
        key: int = event.key(); left_path: Optional[str] = self.preview_widget.get_left_image_path(); right_path: Optional[str] = self.preview_widget.get_right_image_path()
        if key == Qt.Key.Key_Q: self._delete_single_file_from_preview(left_path)
        elif key == Qt.Key.Key_W: self._delete_single_file_from_preview(right_path)
        elif key == Qt.Key.Key_A: left_path and self._handle_open_request(left_path)
        elif key == Qt.Key.Key_S: right_path and self._handle_open_request(right_path)
        elif key == Qt.Key.Key_Escape and self.cancel_button.isVisible() and self.cancel_button.isEnabled(): print("Escキー: スキャン中止要求"); self.request_scan_cancellation()
        else: super().keyPressEvent(event)

