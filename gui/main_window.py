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
from typing import List, Dict, Tuple, Optional, Any, Union, Set

# 型エイリアス
SettingsDict = Dict[str, Union[float, bool, int, str]]
BlurResultItem = Dict[str, Union[str, float]]
SimilarPair = List[Union[str, int]]
DuplicateDict = Dict[str, List[str]]
ErrorDict = Dict[str, str]
ResultsData = Dict[str, Union[List[BlurResultItem], List[SimilarPair], DuplicateDict, List[ErrorDict]]]
LoadResult = Tuple[Optional[ResultsData], Optional[str], Optional[SettingsDict], Optional[str]]
DeleteResult = Tuple[int, List[ErrorDict], Set[str]]

# --- ウィジェット、ワーカー、ダイアログをインポート ---
try:
    from .widgets.preview_widget import PreviewWidget
    from .widgets.results_tabs_widget import ResultsTabsWidget
    from .workers import ScanWorker, WorkerSignals # ScanWorker をインポート
    from .dialogs.settings_dialog import SettingsDialog
except ImportError as e: print(f"エラー: GUIコンポーネントのインポートに失敗 ({e})"); import traceback; traceback.print_exc(); sys.exit(1)

# --- ユーティリティ関数をインポート ---
try:
    from utils.config_handler import load_settings, save_settings
    from utils.file_operations import delete_files_to_trash, open_file_external
    from utils.results_handler import save_results_to_file, load_results_from_file
except ImportError as e:
    print(f"エラー: ユーティリティモジュールのインポートに失敗 ({e})")
    def load_settings() -> SettingsDict: return {'last_directory': os.path.expanduser("~")}
    def save_settings(s: SettingsDict) -> bool: print("警告: 設定保存機能が無効"); return False
    def delete_files_to_trash(fps: List[str], p: Optional[QWidget] = None) -> DeleteResult: print("警告: 削除機能が無効"); return 0, [], set()
    def open_file_external(fp: str, p: Optional[QWidget] = None) -> None: print("警告: ファイルを開く機能が無効")
    def save_results_to_file(fp: str, res: ResultsData, sdir: str, sets: Optional[SettingsDict] = None) -> bool: print("警告: 結果保存機能が無効"); return False
    def load_results_from_file(fp: str) -> LoadResult: print("警告: 結果読込機能が無効"); return None, None, None, "結果読込機能が無効です"


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
        self.scan_button: QPushButton; self.cancel_button: QPushButton # ★ 中止ボタン追加 ★
        self.status_label: QLabel; self.progress_bar: QProgressBar
        self.preview_widget: PreviewWidget; self.results_tabs_widget: ResultsTabsWidget
        self.delete_button: QPushButton; self.select_all_blurry_button: QPushButton; self.select_all_similar_button: QPushButton; self.select_all_duplicates_button: QPushButton; self.deselect_all_button: QPushButton
        # ★ 実行中のワーカーへの参照 ★
        self.current_worker: Optional[ScanWorker] = None

        self._setup_ui()
        self._connect_signals()
        self.results_saved: bool = True

    def _setup_ui(self) -> None:
        main_widget = QWidget(); self.setCentralWidget(main_widget); main_layout = QVBoxLayout(main_widget); main_layout.setContentsMargins(10, 10, 10, 10)
        input_layout = QHBoxLayout(); self.dir_label = QLabel("対象フォルダ:"); self.dir_path_edit = QLineEdit(); self.dir_path_edit.setReadOnly(True); self.select_dir_button = QPushButton("フォルダを選択..."); input_layout.addWidget(self.dir_label); input_layout.addWidget(self.dir_path_edit, 1); input_layout.addWidget(self.select_dir_button); main_layout.addLayout(input_layout); main_layout.addSpacing(5)
        config_layout = QHBoxLayout(); self.settings_button = QPushButton("設定..."); self.save_results_button = QPushButton("結果を保存..."); self.load_results_button = QPushButton("結果を読み込み..."); config_layout.addWidget(self.settings_button); config_layout.addWidget(self.save_results_button); config_layout.addWidget(self.load_results_button); config_layout.addStretch(); main_layout.addLayout(config_layout); main_layout.addSpacing(10)
        # --- スキャン実行エリア (中止ボタン追加) ---
        proc_layout = QHBoxLayout()
        self.scan_button = QPushButton("スキャン開始")
        self.cancel_button = QPushButton("中止") # ★ 中止ボタン作成 ★
        self.cancel_button.setVisible(False) # ★ 初期状態は非表示 ★
        self.status_label = QLabel("ステータス: 待機中"); self.status_label.setWordWrap(True)
        proc_layout.addWidget(self.scan_button)
        proc_layout.addWidget(self.cancel_button) # ★ 中止ボタンを追加 ★
        proc_layout.addWidget(self.status_label, 1)
        main_layout.addLayout(proc_layout)
        self.progress_bar = QProgressBar(); self.progress_bar.setVisible(False); self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter); main_layout.addWidget(self.progress_bar); main_layout.addSpacing(10)
        # --- (プレビュー、結果タブ、アクションボタンは変更なし) ---
        self.preview_widget = PreviewWidget(self); preview_frame = QFrame(); preview_frame.setFrameShape(QFrame.Shape.StyledPanel); preview_frame_layout = QVBoxLayout(preview_frame); preview_frame_layout.setContentsMargins(0,0,0,0); preview_frame_layout.addWidget(self.preview_widget); preview_frame.setFixedHeight(250); main_layout.addWidget(preview_frame, stretch=0); main_layout.addSpacing(10)
        self.results_tabs_widget = ResultsTabsWidget(self); main_layout.addWidget(self.results_tabs_widget, stretch=1); main_layout.addSpacing(10)
        action_layout = QHBoxLayout(); self.delete_button = QPushButton("選択した項目をゴミ箱へ移動"); self.delete_button.setToolTip("現在表示中のタブで選択/チェックされた項目を削除します。\n(重複タブではチェックされたもののみ)"); self.select_all_blurry_button = QPushButton("全選択(ブレ)"); self.select_all_similar_button = QPushButton("全選択(類似ペア)"); self.select_all_duplicates_button = QPushButton("全選択(重複, 除く先頭)"); self.deselect_all_button = QPushButton("全選択解除"); action_layout.addWidget(self.delete_button); action_layout.addStretch(); action_layout.addWidget(self.select_all_blurry_button); action_layout.addWidget(self.select_all_similar_button); action_layout.addWidget(self.select_all_duplicates_button); action_layout.addWidget(self.deselect_all_button); main_layout.addLayout(action_layout)
        self._set_scan_controls_enabled(False); self._set_action_buttons_enabled(False); self.save_results_button.setEnabled(False); self.load_results_button.setEnabled(True)

    def _connect_signals(self) -> None:
        self.select_dir_button.clicked.connect(self.select_directory); self.settings_button.clicked.connect(self.open_settings); self.scan_button.clicked.connect(self.start_scan)
        # ★ 中止ボタンのシグナル接続 ★
        self.cancel_button.clicked.connect(self.request_scan_cancellation)
        self.save_results_button.clicked.connect(self.save_results); self.load_results_button.clicked.connect(self.load_results); self.delete_button.clicked.connect(self.delete_selected_items)
        self.select_all_blurry_button.clicked.connect(self.results_tabs_widget.select_all_blurry); self.select_all_similar_button.clicked.connect(self.results_tabs_widget.select_all_similar); self.select_all_duplicates_button.clicked.connect(self.results_tabs_widget.select_all_duplicates); self.deselect_all_button.clicked.connect(self.results_tabs_widget.deselect_all)
        self.results_tabs_widget.selection_changed.connect(self.update_preview_display)
        self.preview_widget.left_preview_clicked.connect(self._delete_single_file_from_preview); self.preview_widget.right_preview_clicked.connect(self._delete_single_file_from_preview)
        self.results_tabs_widget.delete_file_requested.connect(self._handle_delete_request); self.results_tabs_widget.open_file_requested.connect(self._handle_open_request); self.results_tabs_widget.delete_duplicates_requested.connect(self._handle_delete_duplicates_request)

    # --- スロット関数 ---
    @Slot()
    def select_directory(self) -> None:
        last_dir: str = str(self.current_settings.get('last_directory', os.path.expanduser("~"))); dir_path: str = QFileDialog.getExistingDirectory(self, "フォルダを選択", last_dir)
        if dir_path: self.dir_path_edit.setText(dir_path); self.current_settings['last_directory'] = dir_path; self._clear_all_results(); self.status_label.setText("ステータス: フォルダを選択しました。スキャンまたは結果の読み込みを行ってください。"); self._update_ui_state(scan_enabled=True, actions_enabled=False, cancel_enabled=False) # UI状態更新

    @Slot()
    def open_settings(self) -> None:
        if SettingsDialog is None: QMessageBox.warning(self, "エラー", "設定ダイアログモジュールが見つかりません。"); return
        dialog = SettingsDialog(self.current_settings, self);
        if dialog.exec(): self.current_settings = dialog.get_settings(); print("設定が更新されました:", self.current_settings)
        else: print("設定はキャンセルされました。")

    @Slot()
    def start_scan(self) -> None:
        selected_dir: str = self.dir_path_edit.text()
        if not self._validate_directory(selected_dir): return
        if not self._confirm_unsaved_results("新しいスキャンを開始"): return

        self._clear_all_results()
        self.status_label.setText(f"ステータス: スキャン準備中... ({os.path.basename(selected_dir)})")
        self._set_progress_bar_visible(True)
        self._update_ui_state(scan_enabled=False, actions_enabled=False, cancel_enabled=True) # ★ 中止ボタン有効化 ★

        # ★ ワーカーインスタンスを保持 ★
        self.current_worker = ScanWorker(selected_dir, self.current_settings)
        self.current_worker.signals.status_update.connect(self.update_status)
        self.current_worker.signals.progress_update.connect(self.update_progress_bar)
        self.current_worker.signals.results_ready.connect(self.populate_results_and_update_state)
        self.current_worker.signals.error.connect(self.handle_scan_error)
        self.current_worker.signals.finished.connect(self.handle_scan_finished)
        # ★ 中止シグナルを接続 ★
        self.current_worker.signals.cancelled.connect(self.handle_scan_cancelled)
        self.threadpool.start(self.current_worker)

    @Slot()
    def request_scan_cancellation(self) -> None:
        """中止ボタンがクリックされたときの処理"""
        if self.current_worker:
            self.status_label.setText("ステータス: 中止処理中...")
            self.cancel_button.setEnabled(False) # 中止ボタンを無効化
            self.current_worker.request_cancellation()
        else:
            print("警告: 中止対象のワーカースレッドが見つかりません。")

    @Slot(str)
    def update_status(self, message: str) -> None: self.status_label.setText(f"ステータス: {message}")
    @Slot(int)
    def update_progress_bar(self, value: int) -> None: self.progress_bar.setValue(value)
    @Slot(list, list, dict, list)
    def populate_results_and_update_state(self, blurry: List[BlurResultItem], similar: List[SimilarPair], duplicates: DuplicateDict, errors: List[ErrorDict]) -> None:
        self.results_tabs_widget.populate_results(blurry, similar, duplicates, errors); has_results: bool = bool(blurry or similar or duplicates); self._update_ui_state(scan_enabled=True, actions_enabled=has_results, cancel_enabled=False); self.results_saved = False
        self.current_worker = None # 処理完了したので参照をクリア

    @Slot(str)
    def handle_scan_error(self, message: str) -> None:
        print(f"致命的エラー受信: {message}"); QMessageBox.critical(self, "スキャンエラー", f"処理中に致命的なエラーが発生しました:\n{message}"); self.status_label.setText(f"ステータス: 致命的エラー ({message})"); self._set_progress_bar_visible(False); self._update_ui_state(scan_enabled=bool(self.dir_path_edit.text()), actions_enabled=False, cancel_enabled=False)
        self.current_worker = None # 処理完了したので参照をクリア

    @Slot()
    def handle_scan_finished(self) -> None:
        print("スキャン完了シグナル受信"); error_count: int = self.results_tabs_widget.error_table.rowCount()
        if error_count > 0: self.status_label.setText(f"ステータス: スキャン完了 ({error_count}件のエラーあり)")
        else: self.status_label.setText("ステータス: スキャン完了")
        self._set_progress_bar_visible(False); self._update_ui_state(scan_enabled=True, cancel_enabled=False) # アクションボタンの状態は populate で更新
        self.current_worker = None # 処理完了したので参照をクリア

    @Slot()
    def handle_scan_cancelled(self) -> None:
        """スキャンが中止されたときの処理"""
        print("スキャン中止シグナル受信")
        self.status_label.setText("ステータス: スキャンが中断されました。")
        self._set_progress_bar_visible(False)
        self._update_ui_state(scan_enabled=True, actions_enabled=False, cancel_enabled=False) # ボタン状態をリセット
        self.current_worker = None # 処理完了したので参照をクリア

    @Slot()
    def update_preview_display(self) -> None: primary_path: Optional[str]; secondary_path: Optional[str]; primary_path, secondary_path = self.results_tabs_widget.get_current_selection_paths(); self.preview_widget.update_previews(primary_path, secondary_path)
    @Slot()
    def delete_selected_items(self) -> None:
        files_to_delete: List[str] = self._get_files_to_delete_from_current_tab()
        if not files_to_delete: return
        self._delete_files_and_update_ui(files_to_delete)
    @Slot(str)
    def _delete_single_file_from_preview(self, file_path: str) -> None: self._handle_delete_request(file_path)
    @Slot(str)
    def _handle_delete_request(self, file_path: str) -> None:
        if not file_path: return
        self._delete_files_and_update_ui([file_path])
    @Slot(str)
    def _handle_open_request(self, file_path: str) -> None:
        print(f"オープン要求受信: {file_path}");
        if file_path: open_file_external(file_path, self)
    @Slot(str, list)
    def _handle_delete_duplicates_request(self, keep_path: str, delete_paths: List[str]) -> None:
        if not delete_paths: return
        print(f"重複グループ削除要求受信: Keep='{os.path.basename(keep_path)}', Delete={len(delete_paths)} files")
        if self._confirm_duplicate_deletion(keep_path, delete_paths): self._delete_files_and_update_ui(delete_paths)
        else: print("重複グループの削除はキャンセルされました。")
    @Slot()
    def save_results(self) -> None:
        current_dir: str = self.dir_path_edit.text();
        if not self._validate_directory(current_dir, "保存"): return
        filepath: Optional[str] = self._get_save_filepath(current_dir)
        if not filepath: return
        self.current_settings['last_save_load_dir'] = os.path.dirname(filepath); results_data: ResultsData = self.results_tabs_widget.get_results_data(); success: bool = save_results_to_file(filepath, results_data, current_dir, self.current_settings)
        if success: QMessageBox.information(self, "保存完了", f"結果を以下のファイルに保存しました:\n{filepath}"); self.results_saved = True
        else: QMessageBox.critical(self, "保存エラー", "結果ファイルの保存中にエラーが発生しました。")
    @Slot()
    def load_results(self) -> None:
        if not self.results_saved:
             if not self._confirm_unsaved_results("結果を読み込み"): return
        filepath: Optional[str] = self._get_load_filepath()
        if not filepath: return
        self.current_settings['last_save_load_dir'] = os.path.dirname(filepath)
        results_data: Optional[ResultsData]; scanned_directory: Optional[str]; settings_used: Optional[SettingsDict]; error_message: Optional[str]
        results_data, scanned_directory, settings_used, error_message = load_results_from_file(filepath)
        if error_message: QMessageBox.critical(self, "読み込みエラー", f"結果ファイルの読み込みに失敗しました:\n{error_message}"); return
        current_target_dir: str = self.dir_path_edit.text()
        if not self._confirm_directory_mismatch(scanned_directory, current_target_dir): return
        if scanned_directory and scanned_directory != current_target_dir: self.dir_path_edit.setText(scanned_directory)
        self._clear_all_results()
        if results_data: self.results_tabs_widget.populate_results(results_data.get('blurry', []), results_data.get('similar', []), results_data.get('duplicates', {}), results_data.get('errors', []))
        if settings_used: print("読み込んだ結果のスキャン時設定:", settings_used)
        self.status_label.setText(f"ステータス: 結果を読み込みました ({os.path.basename(filepath)})"); has_results: bool = bool(results_data and (results_data.get('blurry') or results_data.get('similar') or results_data.get('duplicates'))); self._update_ui_state(scan_enabled=True, actions_enabled=has_results, cancel_enabled=False); self.results_saved = True

    # --- ヘルパーメソッド ---
    def _clear_all_results(self) -> None: self.results_tabs_widget.clear_results(); self.preview_widget.clear_previews(); self.results_saved = True # クリアしたら保存済み扱い
    def _validate_directory(self, dir_path: str, action_name: str = "処理") -> bool:
        if not dir_path or not os.path.isdir(dir_path): QMessageBox.warning(self, "エラー", f"有効なフォルダが選択されていません。\n{action_name}を実行できません。"); self.status_label.setText(f"ステータス: エラー ({action_name} - フォルダ未選択)"); return False
        return True
    def _confirm_unsaved_results(self, action_name: str) -> bool:
        if not self.results_saved: reply = QMessageBox.question(self, "確認", f"未保存のスキャン結果があります。\n{action_name}を開始すると結果は失われますが、よろしいですか？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No); return reply == QMessageBox.StandardButton.Yes
        return True
    def _confirm_duplicate_deletion(self, keep_path: str, delete_paths: List[str]) -> bool:
        message: str = f"以下の {len(delete_paths)} 個の重複ファイルをゴミ箱に移動しますか？\n(残すファイル: {os.path.basename(keep_path)})\n\n"; display_limit: int = 10
        if len(delete_paths) <= display_limit: message += "\n".join([f"- {os.path.basename(f)}" for f in delete_paths])
        else: message += "\n".join([f"- {os.path.basename(f)}" for f in delete_paths[:display_limit]]) + f"\n...他 {len(delete_paths) - display_limit} 個"
        reply = QMessageBox.question(self, "重複ファイルの削除確認", message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No); return reply == QMessageBox.StandardButton.Yes
    def _get_save_filepath(self, current_dir: str) -> Optional[str]:
        timestamp: str = datetime.now().strftime('%Y%m%d_%H%M%S'); default_filename: str = f"{os.path.basename(current_dir)}_results_{timestamp}.json"; save_dir: str = str(self.current_settings.get('last_save_load_dir', current_dir)); filepath, _ = QFileDialog.getSaveFileName(self, "結果を保存", os.path.join(save_dir, default_filename), "JSON Files (*.json)"); return filepath if filepath else None
    def _get_load_filepath(self) -> Optional[str]:
        load_dir: str = str(self.current_settings.get('last_save_load_dir', os.path.expanduser("~"))); filepath, _ = QFileDialog.getOpenFileName(self, "結果を読み込み", load_dir, "JSON Files (*.json)"); return filepath if filepath else None
    def _confirm_directory_mismatch(self, loaded_dir: Optional[str], current_dir: str) -> bool:
        if loaded_dir and loaded_dir != current_dir: reply = QMessageBox.warning(self, "フォルダ不一致", f"読み込んだ結果はフォルダ:\n{loaded_dir}\nのものです。\n\n現在の対象フォルダ:\n{current_dir}\nとは異なります。\n\n結果を表示しますか？ (ファイルパスが無効になっている可能性があります)", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No); return reply == QMessageBox.StandardButton.Yes
        return True
    def _get_files_to_delete_from_current_tab(self) -> List[str]:
        files_to_delete: List[str] = []; current_tab_index: int = self.results_tabs_widget.currentIndex(); msg: str = ""
        if current_tab_index == 0: files_to_delete = self.results_tabs_widget.get_selected_blurry_paths(); msg = "ブレ画像タブで削除する項目がチェックされていません。"
        elif current_tab_index == 1: files_to_delete = self.results_tabs_widget.get_selected_similar_primary_paths(); msg = "類似ペアタブで削除する行が選択されていません。"
        elif current_tab_index == 2: files_to_delete = self.results_tabs_widget.get_selected_duplicate_paths(); msg = "重複ファイルタブで削除する項目がチェックされていません。"
        elif current_tab_index == 3: QMessageBox.information(self, "情報", "エラータブの項目は削除できません。"); return []
        else: return []
        if not files_to_delete: QMessageBox.information(self, "情報", msg)
        return files_to_delete
    def _delete_files_and_update_ui(self, files_to_delete: List[str]) -> None:
        if not files_to_delete: return
        deleted_count: int; errors: List[ErrorDict]; files_actually_deleted: Set[str]; deleted_count, errors, files_actually_deleted = delete_files_to_trash(files_to_delete, self)
        if files_actually_deleted: self.results_tabs_widget.remove_items_by_paths(files_actually_deleted); self.preview_widget.clear_previews(); has_results: bool = self.results_tabs_widget.blurry_table.rowCount() > 0 or self.results_tabs_widget.similar_table.rowCount() > 0 or self.results_tabs_widget.duplicate_table.rowCount() > 0; self._update_ui_state(actions_enabled=has_results); self.results_saved = False
    def _set_scan_controls_enabled(self, enabled: bool) -> None: self.scan_button.setEnabled(enabled); self.settings_button.setEnabled(enabled)
    def _set_action_buttons_enabled(self, enabled: bool) -> None: self.delete_button.setEnabled(enabled); self.select_all_blurry_button.setEnabled(enabled); self.select_all_similar_button.setEnabled(enabled); self.select_all_duplicates_button.setEnabled(enabled); self.deselect_all_button.setEnabled(enabled)
    def _set_progress_bar_visible(self, visible: bool) -> None: self.progress_bar.setVisible(visible); (not visible) and self.progress_bar.setValue(0)
    # ★ UI状態更新ヘルパーを修正 ★
    def _update_ui_state(self, scan_enabled: Optional[bool] = None, actions_enabled: Optional[bool] = None, cancel_enabled: Optional[bool] = None) -> None:
        """UIの主要なコントロールの有効/無効状態を一括で更新"""
        if scan_enabled is not None:
            self._set_scan_controls_enabled(scan_enabled)
            self.load_results_button.setEnabled(scan_enabled) # スキャン中は読み込み不可
            self.scan_button.setVisible(not cancel_enabled if cancel_enabled is not None else scan_enabled) # スキャンボタン表示制御
        if actions_enabled is not None:
            self._set_action_buttons_enabled(actions_enabled)
            self.save_results_button.setEnabled(actions_enabled) # 結果がないと保存不可
        if cancel_enabled is not None:
            self.cancel_button.setVisible(cancel_enabled)
            self.cancel_button.setEnabled(cancel_enabled)

    # --- イベントハンドラ ---
    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirm_unsaved_results("アプリケーションを終了"): event.ignore(); return
        if self.threadpool.activeThreadCount() > 0:
             reply = QMessageBox.question(self, "確認", "スキャン処理が実行中です。終了しますか？\n(処理はバックグラウンドで続行されます)", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
             if reply == QMessageBox.StandardButton.No: event.ignore(); return
             else: print("警告: スキャン処理が完了する前にウィンドウを閉じます。"); self.current_worker and self.current_worker.request_cancellation() # 終了時に中止要求
        if not save_settings(self.current_settings): print("警告: 設定ファイルの保存に失敗しました。")
        event.accept()
    def keyPressEvent(self, event: QKeyEvent) -> None:
        key: int = event.key(); left_path: Optional[str] = self.preview_widget.get_left_image_path(); right_path: Optional[str] = self.preview_widget.get_right_image_path()
        if key == Qt.Key.Key_Q: self._delete_single_file_from_preview(left_path)
        elif key == Qt.Key.Key_W: self._delete_single_file_from_preview(right_path)
        elif key == Qt.Key.Key_A: left_path and self._handle_open_request(left_path)
        elif key == Qt.Key.Key_S: right_path and self._handle_open_request(right_path)
        # Esc キーでスキャン中止 (オプション)
        elif key == Qt.Key.Key_Escape and self.cancel_button.isVisible() and self.cancel_button.isEnabled():
             print("Escキー: スキャン中止要求")
             self.request_scan_cancellation()
        else: super().keyPressEvent(event)

