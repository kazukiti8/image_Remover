# gui/main_window.py
import sys
import os
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QFileDialog, QProgressBar,
    QMessageBox
)
from PySide6.QtCore import Qt, QThreadPool, Slot
from PySide6.QtGui import QCloseEvent, QKeyEvent
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any, Union, Set # ★ typing をインポート ★

# ★ 型エイリアス ★
SettingsDict = Dict[str, Union[float, bool, int, str]]
BlurResultItem = Dict[str, Union[str, float]]
SimilarPair = List[Union[str, int]]
DuplicateDict = Dict[str, List[str]]
ErrorDict = Dict[str, str]

# --- ウィジェット、ワーカー、ダイアログをインポート ---
try:
    from .widgets.preview_widget import PreviewWidget
    from .widgets.results_tabs_widget import ResultsTabsWidget
    from .workers import ScanWorker, WorkerSignals
    from .dialogs.settings_dialog import SettingsDialog
except ImportError as e: print(f"エラー: GUIコンポーネントのインポートに失敗 ({e})"); import traceback; traceback.print_exc(); sys.exit(1)

# --- ユーティリティ関数をインポート ---
try:
    from utils.config_handler import load_settings, save_settings
    from utils.file_operations import delete_files_to_trash, open_file_external
    from utils.results_handler import save_results_to_file, load_results_from_file
    # 型エイリアスをインポートしても良い
    # from utils.results_handler import ResultsData, LoadResult
except ImportError as e:
    print(f"エラー: ユーティリティモジュールのインポートに失敗 ({e})")
    def load_settings() -> SettingsDict: return {'last_directory': os.path.expanduser("~")}
    def save_settings(s: SettingsDict) -> bool: print("警告: 設定保存機能が無効"); return False
    def delete_files_to_trash(fps: List[str], p: Optional[QWidget] = None) -> Tuple[int, List[ErrorDict], Set[str]]: print("警告: 削除機能が無効"); return 0, [], set()
    def open_file_external(fp: str, p: Optional[QWidget] = None) -> None: print("警告: ファイルを開く機能が無効")
    def save_results_to_file(fp: str, res: Dict[str, Any], sdir: str, sets: Optional[SettingsDict] = None) -> bool: print("警告: 結果保存機能が無効"); return False
    def load_results_from_file(fp: str) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[SettingsDict], Optional[str]]: print("警告: 結果読込機能が無効"); return None, None, None, "結果読込機能が無効です"


class ImageCleanerWindow(QMainWindow):
    """アプリケーションのメインウィンドウクラス"""
    def __init__(self, parent: Optional[QWidget] = None): # ★ 親ウィジェットの型ヒント ★
        super().__init__(parent)
        self.setWindowTitle("画像クリーナー")
        self.setGeometry(100, 100, 1000, 750)
        self.threadpool: QThreadPool = QThreadPool()
        print(f"最大スレッド数: {self.threadpool.maxThreadCount()}")
        self.current_settings: SettingsDict = load_settings()
        # UI要素の型ヒント
        self.dir_label: QLabel
        self.dir_path_edit: QLineEdit
        self.select_dir_button: QPushButton
        self.settings_button: QPushButton
        self.save_results_button: QPushButton
        self.load_results_button: QPushButton
        self.scan_button: QPushButton
        self.status_label: QLabel
        self.progress_bar: QProgressBar
        self.preview_widget: PreviewWidget
        self.results_tabs_widget: ResultsTabsWidget
        self.delete_button: QPushButton
        self.select_all_blurry_button: QPushButton
        self.select_all_similar_button: QPushButton
        self.select_all_duplicates_button: QPushButton
        self.deselect_all_button: QPushButton

        self._setup_ui()
        self._connect_signals()
        self.results_saved: bool = True

    def _setup_ui(self) -> None:
        """UIウィジェットの作成とレイアウト"""
        main_widget = QWidget(); self.setCentralWidget(main_widget); main_layout = QVBoxLayout(main_widget); main_layout.setContentsMargins(10, 10, 10, 10)
        input_layout = QHBoxLayout(); self.dir_label = QLabel("対象フォルダ:"); self.dir_path_edit = QLineEdit(); self.dir_path_edit.setReadOnly(True); self.select_dir_button = QPushButton("フォルダを選択..."); input_layout.addWidget(self.dir_label); input_layout.addWidget(self.dir_path_edit, 1); input_layout.addWidget(self.select_dir_button); main_layout.addLayout(input_layout); main_layout.addSpacing(5)
        config_layout = QHBoxLayout(); self.settings_button = QPushButton("設定..."); self.save_results_button = QPushButton("結果を保存..."); self.load_results_button = QPushButton("結果を読み込み..."); config_layout.addWidget(self.settings_button); config_layout.addWidget(self.save_results_button); config_layout.addWidget(self.load_results_button); config_layout.addStretch(); main_layout.addLayout(config_layout); main_layout.addSpacing(10)
        proc_layout = QHBoxLayout(); self.scan_button = QPushButton("スキャン開始"); self.status_label = QLabel("ステータス: 待機中"); self.status_label.setWordWrap(True); proc_layout.addWidget(self.scan_button); proc_layout.addWidget(self.status_label, 1); main_layout.addLayout(proc_layout); self.progress_bar = QProgressBar(); self.progress_bar.setVisible(False); self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter); main_layout.addWidget(self.progress_bar); main_layout.addSpacing(10)
        self.preview_widget = PreviewWidget(self); preview_frame = QFrame(); preview_frame.setFrameShape(QFrame.Shape.StyledPanel); preview_frame_layout = QVBoxLayout(preview_frame); preview_frame_layout.setContentsMargins(0,0,0,0); preview_frame_layout.addWidget(self.preview_widget); preview_frame.setFixedHeight(250); main_layout.addWidget(preview_frame, stretch=0); main_layout.addSpacing(10)
        self.results_tabs_widget = ResultsTabsWidget(self); main_layout.addWidget(self.results_tabs_widget, stretch=1); main_layout.addSpacing(10)
        action_layout = QHBoxLayout(); self.delete_button = QPushButton("選択した項目をゴミ箱へ移動"); self.delete_button.setToolTip("現在表示中のタブで選択/チェックされた項目を削除します。\n(重複タブではチェックされたもののみ)"); self.select_all_blurry_button = QPushButton("全選択(ブレ)"); self.select_all_similar_button = QPushButton("全選択(類似ペア)"); self.select_all_duplicates_button = QPushButton("全選択(重複, 除く先頭)"); self.deselect_all_button = QPushButton("全選択解除"); action_layout.addWidget(self.delete_button); action_layout.addStretch(); action_layout.addWidget(self.select_all_blurry_button); action_layout.addWidget(self.select_all_similar_button); action_layout.addWidget(self.select_all_duplicates_button); action_layout.addWidget(self.deselect_all_button); main_layout.addLayout(action_layout)
        self._set_scan_controls_enabled(False); self._set_action_buttons_enabled(False); self.save_results_button.setEnabled(False); self.load_results_button.setEnabled(True)

    def _connect_signals(self) -> None:
        """ウィジェット間のシグナルとスロットを接続"""
        self.select_dir_button.clicked.connect(self.select_directory); self.settings_button.clicked.connect(self.open_settings); self.scan_button.clicked.connect(self.start_scan); self.save_results_button.clicked.connect(self.save_results); self.load_results_button.clicked.connect(self.load_results); self.delete_button.clicked.connect(self.delete_selected_items)
        self.select_all_blurry_button.clicked.connect(self.results_tabs_widget.select_all_blurry); self.select_all_similar_button.clicked.connect(self.results_tabs_widget.select_all_similar); self.select_all_duplicates_button.clicked.connect(self.results_tabs_widget.select_all_duplicates); self.deselect_all_button.clicked.connect(self.results_tabs_widget.deselect_all)
        self.results_tabs_widget.selection_changed.connect(self.update_preview_display)
        self.preview_widget.left_preview_clicked.connect(self._delete_single_file_from_preview); self.preview_widget.right_preview_clicked.connect(self._delete_single_file_from_preview)
        self.results_tabs_widget.delete_file_requested.connect(self._handle_delete_request); self.results_tabs_widget.open_file_requested.connect(self._handle_open_request); self.results_tabs_widget.delete_duplicates_requested.connect(self._handle_delete_duplicates_request)

    # --- スロット関数 ---
    @Slot()
    def select_directory(self) -> None:
        last_dir: str = str(self.current_settings.get('last_directory', os.path.expanduser("~")))
        dir_path: str = QFileDialog.getExistingDirectory(self, "フォルダを選択", last_dir)
        if dir_path: self.dir_path_edit.setText(dir_path); self.current_settings['last_directory'] = dir_path; self.results_tabs_widget.clear_results(); self.preview_widget.clear_previews(); self.status_label.setText("ステータス: フォルダを選択しました。スキャンまたは結果の読み込みを行ってください。"); self._set_scan_controls_enabled(True); self._set_action_buttons_enabled(False); self.save_results_button.setEnabled(False); self.results_saved = True
    @Slot()
    def open_settings(self) -> None:
        if SettingsDialog is None: QMessageBox.warning(self, "エラー", "設定ダイアログモジュールが見つかりません。"); return
        dialog = SettingsDialog(self.current_settings, self)
        if dialog.exec(): self.current_settings = dialog.get_settings(); print("設定が更新されました:", self.current_settings)
        else: print("設定はキャンセルされました。")
    @Slot()
    def start_scan(self) -> None:
        selected_dir: str = self.dir_path_edit.text()
        if not selected_dir or not os.path.isdir(selected_dir): QMessageBox.warning(self, "エラー", "有効なフォルダが選択されていません。"); self.status_label.setText("ステータス: エラー (フォルダ未選択)"); return
        if not self.results_saved:
            reply = QMessageBox.question(self, "確認", "未保存のスキャン結果があります。新しいスキャンを開始すると結果は失われますが、よろしいですか？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No: return
        self.results_tabs_widget.clear_results(); self.preview_widget.clear_previews(); self.status_label.setText(f"ステータス: スキャン準備中... ({os.path.basename(selected_dir)})"); self.progress_bar.setVisible(True); self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0); self._set_scan_controls_enabled(False); self._set_action_buttons_enabled(False); self.save_results_button.setEnabled(False)
        worker = ScanWorker(selected_dir, self.current_settings); worker.signals.status_update.connect(self.update_status); worker.signals.progress_update.connect(self.update_progress_bar); worker.signals.results_ready.connect(self.populate_results_and_enable_save); worker.signals.error.connect(self.scan_error); worker.signals.finished.connect(self.scan_finished); self.threadpool.start(worker)
    @Slot(str)
    def update_status(self, message: str) -> None: self.status_label.setText(f"ステータス: {message}")
    @Slot(int)
    def update_progress_bar(self, value: int) -> None: self.progress_bar.setValue(value)
    @Slot(list, list, dict, list)
    def populate_results_and_enable_save(self, blurry: List[BlurResultItem], similar: List[SimilarPair], duplicates: DuplicateDict, errors: List[ErrorDict]) -> None:
        self.results_tabs_widget.populate_results(blurry, similar, duplicates, errors); has_results: bool = bool(blurry or similar or duplicates); self.save_results_button.setEnabled(has_results); self._set_action_buttons_enabled(has_results); self.results_saved = False
    @Slot(str)
    def scan_error(self, message: str) -> None: print(f"致命的エラー受信: {message}"); QMessageBox.critical(self, "スキャンエラー", f"処理中に致命的なエラーが発生しました:\n{message}"); self.status_label.setText(f"ステータス: 致命的エラー ({message})"); self.progress_bar.setVisible(False); self.progress_bar.setValue(0); self._set_scan_controls_enabled(bool(self.dir_path_edit.text())); self._set_action_buttons_enabled(False); self.save_results_button.setEnabled(False)
    @Slot()
    def scan_finished(self) -> None:
        print("スキャン完了シグナル受信"); error_count: int = self.results_tabs_widget.error_table.rowCount()
        if error_count > 0: self.status_label.setText(f"ステータス: スキャン完了 ({error_count}件のエラーあり)")
        else: self.status_label.setText("ステータス: スキャン完了")
        self.progress_bar.setVisible(False); self.progress_bar.setValue(0); self._set_scan_controls_enabled(True)
        # ボタン状態は populate_results_and_enable_save で設定される
    @Slot()
    def update_preview_display(self) -> None: primary_path: Optional[str]; secondary_path: Optional[str]; primary_path, secondary_path = self.results_tabs_widget.get_current_selection_paths(); self.preview_widget.update_previews(primary_path, secondary_path)
    @Slot()
    def delete_selected_items(self) -> None:
        files_to_delete: List[str] = []; current_tab_index: int = self.results_tabs_widget.currentIndex(); msg: str = ""
        if current_tab_index == 0: files_to_delete = self.results_tabs_widget.get_selected_blurry_paths(); msg = "ブレ画像タブで削除する項目がチェックされていません。"
        elif current_tab_index == 1: files_to_delete = self.results_tabs_widget.get_selected_similar_primary_paths(); msg = "類似ペアタブで削除する行が選択されていません。"
        elif current_tab_index == 2: files_to_delete = self.results_tabs_widget.get_selected_duplicate_paths(); msg = "重複ファイルタブで削除する項目がチェックされていません。"
        elif current_tab_index == 3: QMessageBox.information(self, "情報", "エラータブの項目は削除できません。"); return
        else: return
        if not files_to_delete: QMessageBox.information(self, "情報", msg); return
        deleted_count: int; errors: List[ErrorDict]; files_actually_deleted: Set[str]
        deleted_count, errors, files_actually_deleted = delete_files_to_trash(files_to_delete, self)
        if files_actually_deleted: self.results_tabs_widget.remove_items_by_paths(files_actually_deleted); self.preview_widget.clear_previews(); has_results: bool = self.results_tabs_widget.blurry_table.rowCount() > 0 or self.results_tabs_widget.similar_table.rowCount() > 0 or self.results_tabs_widget.duplicate_table.rowCount() > 0; self._set_action_buttons_enabled(has_results); self.save_results_button.setEnabled(has_results); self.results_saved = False
    @Slot(str)
    def _delete_single_file_from_preview(self, file_path: str) -> None: self._handle_delete_request(file_path)
    @Slot(str)
    def _handle_delete_request(self, file_path: str) -> None:
        if not file_path: return
        deleted_count: int; errors: List[ErrorDict]; files_actually_deleted: Set[str]
        deleted_count, errors, files_actually_deleted = delete_files_to_trash([file_path], self)
        if files_actually_deleted: self.results_tabs_widget.remove_items_by_paths(files_actually_deleted); self.preview_widget.clear_previews(); has_results: bool = self.results_tabs_widget.blurry_table.rowCount() > 0 or self.results_tabs_widget.similar_table.rowCount() > 0 or self.results_tabs_widget.duplicate_table.rowCount() > 0; self._set_action_buttons_enabled(has_results); self.save_results_button.setEnabled(has_results); self.results_saved = False
    @Slot(str)
    def _handle_open_request(self, file_path: str) -> None:
        print(f"オープン要求受信: {file_path}")
        if file_path: open_file_external(file_path, self)
    @Slot(str, list)
    def _handle_delete_duplicates_request(self, keep_path: str, delete_paths: List[str]) -> None:
        if not delete_paths: return
        print(f"重複グループ削除要求受信: Keep='{os.path.basename(keep_path)}', Delete={len(delete_paths)} files")
        message: str = f"以下の {len(delete_paths)} 個の重複ファイルをゴミ箱に移動しますか？\n(残すファイル: {os.path.basename(keep_path)})\n\n"; display_limit: int = 10
        if len(delete_paths) <= display_limit: message += "\n".join([f"- {os.path.basename(f)}" for f in delete_paths])
        else: message += "\n".join([f"- {os.path.basename(f)}" for f in delete_paths[:display_limit]]) + f"\n...他 {len(delete_paths) - display_limit} 個"
        reply = QMessageBox.question(self, "重複ファイルの削除確認", message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count: int; errors: List[ErrorDict]; files_actually_deleted: Set[str]
            deleted_count, errors, files_actually_deleted = delete_files_to_trash(delete_paths, self)
            if files_actually_deleted: self.results_tabs_widget.remove_items_by_paths(files_actually_deleted); self.preview_widget.clear_previews(); has_results: bool = self.results_tabs_widget.blurry_table.rowCount() > 0 or self.results_tabs_widget.similar_table.rowCount() > 0 or self.results_tabs_widget.duplicate_table.rowCount() > 0; self._set_action_buttons_enabled(has_results); self.save_results_button.setEnabled(has_results); self.results_saved = False
        else: print("重複グループの削除はキャンセルされました。")
    @Slot()
    def save_results(self) -> None:
        current_dir: str = self.dir_path_edit.text();
        if not current_dir: QMessageBox.warning(self, "保存エラー", "対象フォルダが選択されていません。"); return
        timestamp: str = datetime.now().strftime('%Y%m%d_%H%M%S'); default_filename: str = f"{os.path.basename(current_dir)}_results_{timestamp}.json"; save_dir: str = str(self.current_settings.get('last_save_load_dir', current_dir))
        filepath: str; _: Any
        filepath, _ = QFileDialog.getSaveFileName(self, "結果を保存", os.path.join(save_dir, default_filename), "JSON Files (*.json)")
        if filepath:
            self.current_settings['last_save_load_dir'] = os.path.dirname(filepath)
            results_data: Dict[str, Any] = self.results_tabs_widget.get_results_data()
            success: bool = save_results_to_file(filepath, results_data, current_dir, self.current_settings)
            if success:
                QMessageBox.information(self, "保存完了", f"結果を以下のファイルに保存しました:\n{filepath}")
                self.results_saved = True
            else:
                QMessageBox.critical(self, "保存エラー", "結果ファイルの保存中にエラーが発生しました。")
    @Slot()
    def load_results(self) -> None:
        current_target_dir: str = self.dir_path_edit.text(); load_dir: str = str(self.current_settings.get('last_save_load_dir', os.path.expanduser("~")))
        filepath: str; _: Any
        filepath, _ = QFileDialog.getOpenFileName(self, "結果を読み込み", load_dir, "JSON Files (*.json)")
        if filepath:
            self.current_settings['last_save_load_dir'] = os.path.dirname(filepath)
            results_data: Optional[Dict[str, Any]]; scanned_directory: Optional[str]; settings_used: Optional[SettingsDict]; error_message: Optional[str]
            results_data, scanned_directory, settings_used, error_message = load_results_from_file(filepath)
            if error_message: QMessageBox.critical(self, "読み込みエラー", f"結果ファイルの読み込みに失敗しました:\n{error_message}"); return
            if scanned_directory and scanned_directory != current_target_dir:
                reply = QMessageBox.warning(self, "フォルダ不一致", f"読み込んだ結果はフォルダ:\n{scanned_directory}\nのものです。\n\n現在の対象フォルダ:\n{current_target_dir}\nとは異なります。\n\n結果を表示しますか？ (ファイルパスが無効になっている可能性があります)", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No: return
                self.dir_path_edit.setText(scanned_directory) # フォルダパスも更新
            if results_data is None: results_data = {} # None の場合のフォールバック
            self.results_tabs_widget.clear_results(); self.preview_widget.clear_previews()
            self.results_tabs_widget.populate_results(results_data.get('blurry', []), results_data.get('similar', []), results_data.get('duplicates', {}), results_data.get('errors', []))
            if settings_used: print("読み込んだ結果のスキャン時設定:", settings_used)
            self.status_label.setText(f"ステータス: 結果を読み込みました ({os.path.basename(filepath)})"); has_results: bool = bool(results_data.get('blurry') or results_data.get('similar') or results_data.get('duplicates')); self._set_action_buttons_enabled(has_results); self.save_results_button.setEnabled(has_results); self.results_saved = True; self._set_scan_controls_enabled(True)

    # --- ヘルパーメソッド ---
    def _set_scan_controls_enabled(self, enabled: bool) -> None: self.scan_button.setEnabled(enabled); self.settings_button.setEnabled(enabled)
    def _set_action_buttons_enabled(self, enabled: bool) -> None: self.delete_button.setEnabled(enabled); self.select_all_blurry_button.setEnabled(enabled); self.select_all_similar_button.setEnabled(enabled); self.select_all_duplicates_button.setEnabled(enabled); self.deselect_all_button.setEnabled(enabled)

    # --- イベントハンドラ ---
    def closeEvent(self, event: QCloseEvent) -> None:
        """ウィンドウが閉じられるときのイベント"""
        if not self.results_saved: # 未保存の結果があるか確認
            reply = QMessageBox.question(self, "終了確認", "未保存のスキャン結果があります。保存せずに終了しますか？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            # ★★★ 修正箇所: インデントを修正 ★★★
            if reply == QMessageBox.StandardButton.Save:
                self.save_results() # 保存処理を呼ぶ
                # 保存がキャンセルされた場合などを考慮すると、さらに制御が必要かも
                # ここでは保存を試みたとして終了プロセスに進む
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore() # 終了キャンセル
                return
            # Yes の場合はそのまま終了処理へ
            # ★★★★★★★★★★★★★★★★★★★★

        if self.threadpool.activeThreadCount() > 0:
             reply = QMessageBox.question(self, "確認", "スキャン処理が実行中です。終了しますか？\n(処理はバックグラウンドで続行されます)", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
             if reply == QMessageBox.StandardButton.No: event.ignore(); return
             else: print("警告: スキャン処理が完了する前にウィンドウを閉じます。")
        if not save_settings(self.current_settings): print("警告: 設定ファイルの保存に失敗しました。")
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """キーボードショートカット処理"""
        key: int = event.key(); left_path: Optional[str] = self.preview_widget.get_left_image_path(); right_path: Optional[str] = self.preview_widget.get_right_image_path()
        if key == Qt.Key.Key_Q: self._delete_single_file_from_preview(left_path)
        elif key == Qt.Key.Key_W: self._delete_single_file_from_preview(right_path)
        elif key == Qt.Key.Key_A: left_path and self._handle_open_request(left_path)
        elif key == Qt.Key.Key_S: right_path and self._handle_open_request(right_path)
        else: super().keyPressEvent(event)

