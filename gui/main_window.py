# gui/main_window.py
import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QFileDialog, QProgressBar,
    QMessageBox
)
from PySide6.QtCore import Qt, QThreadPool, Slot
from PySide6.QtGui import QCloseEvent, QKeyEvent

# --- ウィジェット、ワーカー、ダイアログをインポート ---
try:
    from .widgets.preview_widget import PreviewWidget
    from .widgets.results_tabs_widget import ResultsTabsWidget
    from .workers import ScanWorker, WorkerSignals
    from .dialogs.settings_dialog import SettingsDialog
except ImportError as e:
    print(f"エラー: GUIコンポーネントのインポートに失敗しました ({e})。アプリケーションを起動できません。")
    import traceback; traceback.print_exc(); sys.exit(1)

# --- ユーティリティ関数をインポート ---
try:
    from utils.config_handler import load_settings, save_settings
    from utils.file_operations import delete_files_to_trash, open_file_external
except ImportError as e:
    print(f"エラー: ユーティリティモジュールのインポートに失敗しました ({e})。")
    def load_settings(): return {'last_directory': os.path.expanduser("~")}
    def save_settings(s): print("警告: 設定保存機能が無効です。"); return False
    def delete_files_to_trash(fps, p=None): print("警告: 削除機能が無効です。"); return 0, [], set()
    def open_file_external(fp, p=None): print("警告: ファイルを開く機能が無効です。")


class ImageCleanerWindow(QMainWindow):
    """アプリケーションのメインウィンドウクラス"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("画像クリーナー")
        self.setGeometry(100, 100, 1000, 750)
        self.threadpool = QThreadPool()
        self.current_settings = load_settings()
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """UIウィジェットの作成とレイアウト"""
        main_widget = QWidget(); self.setCentralWidget(main_widget); main_layout = QVBoxLayout(main_widget); main_layout.setContentsMargins(10, 10, 10, 10)
        input_layout = QHBoxLayout(); self.dir_label = QLabel("対象フォルダ:"); self.dir_path_edit = QLineEdit(); self.dir_path_edit.setReadOnly(True); self.select_dir_button = QPushButton("フォルダを選択..."); input_layout.addWidget(self.dir_label); input_layout.addWidget(self.dir_path_edit, 1); input_layout.addWidget(self.select_dir_button); main_layout.addLayout(input_layout); main_layout.addSpacing(5)
        settings_layout = QHBoxLayout(); self.settings_button = QPushButton("設定..."); settings_layout.addWidget(self.settings_button); settings_layout.addStretch(); main_layout.addLayout(settings_layout); main_layout.addSpacing(10)
        proc_layout = QHBoxLayout(); self.scan_button = QPushButton("スキャン開始"); self.status_label = QLabel("ステータス: 待機中"); self.status_label.setWordWrap(True); proc_layout.addWidget(self.scan_button); proc_layout.addWidget(self.status_label, 1); main_layout.addLayout(proc_layout); self.progress_bar = QProgressBar(); self.progress_bar.setVisible(False); self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter); main_layout.addWidget(self.progress_bar); main_layout.addSpacing(10)
        self.preview_widget = PreviewWidget(); preview_frame = QFrame(); preview_frame.setFrameShape(QFrame.Shape.StyledPanel); preview_frame_layout = QVBoxLayout(preview_frame); preview_frame_layout.setContentsMargins(0,0,0,0); preview_frame_layout.addWidget(self.preview_widget); preview_frame.setFixedHeight(250); main_layout.addWidget(preview_frame, stretch=0); main_layout.addSpacing(10)
        self.results_tabs_widget = ResultsTabsWidget(); main_layout.addWidget(self.results_tabs_widget, stretch=1); main_layout.addSpacing(10)

        # --- アクションボタンエリア ---
        action_layout = QHBoxLayout()
        self.delete_button = QPushButton("選択した項目をゴミ箱へ移動")
        self.delete_button.setToolTip("現在表示中のタブで選択/チェックされた項目を削除します。\n(重複タブではチェックされたもののみ)") # ツールチップ更新
        self.select_all_blurry_button = QPushButton("全選択(ブレ)")
        self.select_all_similar_button = QPushButton("全選択(類似ペア)")
        # ★ 重複ファイル用全選択ボタンを追加 ★
        self.select_all_duplicates_button = QPushButton("全選択(重複, 除く先頭)")
        self.deselect_all_button = QPushButton("全選択解除")

        action_layout.addWidget(self.delete_button)
        action_layout.addStretch()
        action_layout.addWidget(self.select_all_blurry_button)
        action_layout.addWidget(self.select_all_similar_button)
        action_layout.addWidget(self.select_all_duplicates_button) # ★ 追加 ★
        action_layout.addWidget(self.deselect_all_button)
        main_layout.addLayout(action_layout)

        # 初期状態設定
        self._set_scan_controls_enabled(False)
        self._set_action_buttons_enabled(False) # アクションボタン用ヘルパー

    def _connect_signals(self):
        """ウィジェット間のシグナルとスロットを接続"""
        # ボタンクリック
        self.select_dir_button.clicked.connect(self.select_directory)
        self.settings_button.clicked.connect(self.open_settings)
        self.scan_button.clicked.connect(self.start_scan)
        self.delete_button.clicked.connect(self.delete_selected_items)
        # 全選択/解除ボタン
        self.select_all_blurry_button.clicked.connect(self.results_tabs_widget.select_all_blurry)
        self.select_all_similar_button.clicked.connect(self.results_tabs_widget.select_all_similar)
        self.select_all_duplicates_button.clicked.connect(self.results_tabs_widget.select_all_duplicates) # ★ 追加 ★
        self.deselect_all_button.clicked.connect(self.results_tabs_widget.deselect_all)

        # 結果タブの選択変更 -> プレビュー更新
        self.results_tabs_widget.selection_changed.connect(self.update_preview_display)

        # プレビュークリック -> ファイル削除要求
        self.preview_widget.left_preview_clicked.connect(self._delete_single_file_from_preview)
        self.preview_widget.right_preview_clicked.connect(self._delete_single_file_from_preview)

        # ResultsTabsWidget からの削除/オープン/重複削除要求を処理
        self.results_tabs_widget.delete_file_requested.connect(self._handle_delete_request)
        self.results_tabs_widget.open_file_requested.connect(self._handle_open_request)
        self.results_tabs_widget.delete_duplicates_requested.connect(self._handle_delete_duplicates_request) # ★ 追加 ★

    # --- スロット関数 ---
    @Slot()
    def select_directory(self):
        last_dir = self.current_settings.get('last_directory', os.path.expanduser("~"))
        dir_path = QFileDialog.getExistingDirectory(self, "フォルダを選択", last_dir)
        if dir_path:
            self.dir_path_edit.setText(dir_path); self.current_settings['last_directory'] = dir_path
            self.results_tabs_widget.clear_results(); self.preview_widget.clear_previews()
            self.status_label.setText("ステータス: フォルダを選択しました。スキャンを開始してください。")
            self._set_scan_controls_enabled(True); self._set_action_buttons_enabled(False) # アクションボタンは無効
    @Slot()
    def open_settings(self):
        if SettingsDialog is None: QMessageBox.warning(self, "エラー", "設定ダイアログモジュールが見つかりません。"); return
        dialog = SettingsDialog(self.current_settings, self)
        if dialog.exec(): self.current_settings = dialog.get_settings(); print("設定が更新されました:", self.current_settings)
        else: print("設定はキャンセルされました。")
    @Slot()
    def start_scan(self):
        selected_dir = self.dir_path_edit.text()
        if not selected_dir or not os.path.isdir(selected_dir): QMessageBox.warning(self, "エラー", "有効なフォルダが選択されていません。"); self.status_label.setText("ステータス: エラー (フォルダ未選択)"); return
        self.results_tabs_widget.clear_results(); self.preview_widget.clear_previews()
        self.status_label.setText(f"ステータス: スキャン準備中... ({os.path.basename(selected_dir)})"); self.progress_bar.setVisible(True); self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0)
        self._set_scan_controls_enabled(False); self._set_action_buttons_enabled(False) # スキャン中は全アクション無効
        worker = ScanWorker(selected_dir, self.current_settings)
        worker.signals.status_update.connect(self.update_status); worker.signals.progress_update.connect(self.update_progress_bar)
        # ★ results_ready の接続先を populate_results に変更 ★
        worker.signals.results_ready.connect(self.results_tabs_widget.populate_results)
        worker.signals.error.connect(self.scan_error); worker.signals.finished.connect(self.scan_finished)
        self.threadpool.start(worker)

    @Slot(str)
    def update_status(self, message): self.status_label.setText(f"ステータス: {message}")
    @Slot(int)
    def update_progress_bar(self, value): self.progress_bar.setValue(value)
    @Slot(str)
    def scan_error(self, message): print(f"致命的エラー受信: {message}"); QMessageBox.critical(self, "スキャンエラー", f"処理中に致命的なエラーが発生しました:\n{message}"); self.status_label.setText(f"ステータス: 致命的エラー ({message})"); self.progress_bar.setVisible(False); self.progress_bar.setValue(0); self._set_scan_controls_enabled(bool(self.dir_path_edit.text())); self._set_action_buttons_enabled(False)
    @Slot()
    def scan_finished(self):
        print("スキャン完了シグナル受信"); error_count = self.results_tabs_widget.error_table.rowCount()
        if error_count > 0: self.status_label.setText(f"ステータス: スキャン完了 ({error_count}件のエラーあり)")
        else: self.status_label.setText("ステータス: スキャン完了")
        self.progress_bar.setVisible(False); self.progress_bar.setValue(0); self._set_scan_controls_enabled(True)
        # ★ 結果があればアクションボタンを有効化 ★
        has_results = self.results_tabs_widget.blurry_table.rowCount() > 0 or \
                      self.results_tabs_widget.similar_table.rowCount() > 0 or \
                      self.results_tabs_widget.duplicate_table.rowCount() > 0
        self._set_action_buttons_enabled(has_results)

    @Slot()
    def update_preview_display(self):
        primary_path, secondary_path = self.results_tabs_widget.get_current_selection_paths()
        self.preview_widget.update_previews(primary_path, secondary_path)

    @Slot()
    def delete_selected_items(self):
        """メインの削除ボタン（「選択した項目をゴミ箱へ移動」）の処理"""
        files_to_delete = []; current_tab_index = self.results_tabs_widget.currentIndex()
        tab_name = self.results_tabs_widget.tabText(current_tab_index) # デバッグ用

        if current_tab_index == 0: # ブレ画像
            files_to_delete = self.results_tabs_widget.get_selected_blurry_paths()
            if not files_to_delete: QMessageBox.information(self, "情報", "ブレ画像タブで削除する項目がチェックされていません。"); return
        elif current_tab_index == 1: # 類似ペア (ファイル1を削除)
            files_to_delete = self.results_tabs_widget.get_selected_similar_primary_paths()
            if not files_to_delete: QMessageBox.information(self, "情報", "類似ペアタブで削除する行が選択されていません。"); return
        elif current_tab_index == 2: # ★ 重複ファイル ★
            files_to_delete = self.results_tabs_widget.get_selected_duplicate_paths()
            if not files_to_delete: QMessageBox.information(self, "情報", "重複ファイルタブで削除する項目がチェックされていません。"); return
        elif current_tab_index == 3: # エラー
             QMessageBox.information(self, "情報", "エラータブの項目は削除できません。"); return
        else: return # 不明なタブ

        if not files_to_delete: return

        print(f"削除実行 ({tab_name}): {len(files_to_delete)} 件") # デバッグ出力
        # 削除実行
        deleted_count, errors, files_actually_deleted = delete_files_to_trash(files_to_delete, self)
        # 結果反映
        if files_actually_deleted:
            self.results_tabs_widget.remove_items_by_paths(files_actually_deleted)
            self.preview_widget.clear_previews()
            # ボタン状態更新
            has_results = self.results_tabs_widget.blurry_table.rowCount() > 0 or \
                          self.results_tabs_widget.similar_table.rowCount() > 0 or \
                          self.results_tabs_widget.duplicate_table.rowCount() > 0
            self._set_action_buttons_enabled(has_results)

    @Slot(str)
    def _delete_single_file_from_preview(self, file_path):
        """プレビュークリックによる単一ファイル削除"""
        if not file_path: return
        self._handle_delete_request(file_path) # 既存の削除処理を呼ぶ

    @Slot(str)
    def _handle_delete_request(self, file_path):
        """単一ファイルの削除要求を処理 (プレビュー or 右クリック)"""
        print(f"単一削除要求受信: {file_path}")
        if not file_path: return
        deleted_count, errors, files_actually_deleted = delete_files_to_trash([file_path], self)
        if files_actually_deleted:
            self.results_tabs_widget.remove_items_by_paths(files_actually_deleted)
            self.preview_widget.clear_previews()
            has_results = self.results_tabs_widget.blurry_table.rowCount() > 0 or \
                          self.results_tabs_widget.similar_table.rowCount() > 0 or \
                          self.results_tabs_widget.duplicate_table.rowCount() > 0
            self._set_action_buttons_enabled(has_results)

    @Slot(str)
    def _handle_open_request(self, file_path):
        """ファイルを開く要求を処理 (右クリック)"""
        print(f"オープン要求受信: {file_path}")
        if file_path: open_file_external(file_path, self)

    @Slot(str, list)
    def _handle_delete_duplicates_request(self, keep_path, delete_paths):
        """重複グループ内で指定ファイル以外を削除する要求を処理 (右クリック)"""
        if not delete_paths: return
        print(f"重複グループ削除要求受信: Keep='{os.path.basename(keep_path)}', Delete={len(delete_paths)} files")
        # 確認ダイアログを出す (delete_files_to_trash はリスト全体で確認するため個別に出す)
        message = f"以下の {len(delete_paths)} 個の重複ファイルをゴミ箱に移動しますか？\n"
        message += f"(残すファイル: {os.path.basename(keep_path)})\n\n"
        display_limit = 10
        if len(delete_paths) <= display_limit:
             message += "\n".join([f"- {os.path.basename(f)}" for f in delete_paths])
        else:
             message += "\n".join([f"- {os.path.basename(f)}" for f in delete_paths[:display_limit]])
             message += f"\n...他 {len(delete_paths) - display_limit} 個"

        reply = QMessageBox.question(self, "重複ファイルの削除確認", message,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # 削除実行
            deleted_count, errors, files_actually_deleted = delete_files_to_trash(delete_paths, self)
            # 結果反映
            if files_actually_deleted:
                self.results_tabs_widget.remove_items_by_paths(files_actually_deleted)
                self.preview_widget.clear_previews()
                has_results = self.results_tabs_widget.blurry_table.rowCount() > 0 or \
                              self.results_tabs_widget.similar_table.rowCount() > 0 or \
                              self.results_tabs_widget.duplicate_table.rowCount() > 0
                self._set_action_buttons_enabled(has_results)
        else:
            print("重複グループの削除はキャンセルされました。")


    # --- ヘルパーメソッド ---
    def _set_scan_controls_enabled(self, enabled: bool):
        """スキャン開始ボタンと設定ボタンの有効/無効を切り替える"""
        self.scan_button.setEnabled(enabled)
        self.settings_button.setEnabled(enabled)

    def _set_action_buttons_enabled(self, enabled: bool):
        """削除ボタン、全選択/解除ボタンの有効/無効を切り替える"""
        self.delete_button.setEnabled(enabled)
        self.select_all_blurry_button.setEnabled(enabled)
        self.select_all_similar_button.setEnabled(enabled)
        self.select_all_duplicates_button.setEnabled(enabled) # ★ 追加 ★
        self.deselect_all_button.setEnabled(enabled)

    # --- イベントハンドラ ---
    def closeEvent(self, event: QCloseEvent):
        if self.threadpool.activeThreadCount() > 0:
             reply = QMessageBox.question(self, "確認", "スキャン処理が実行中です。終了しますか？\n(処理はバックグラウンドで続行されます)", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
             if reply == QMessageBox.StandardButton.No: event.ignore(); return
             else: print("警告: スキャン処理が完了する前にウィンドウを閉じます。")
        if not save_settings(self.current_settings): print("警告: 設定ファイルの保存に失敗しました。")
        event.accept()
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key(); left_path = self.preview_widget.get_left_image_path(); right_path = self.preview_widget.get_right_image_path()
        if key == Qt.Key.Key_Q: print("'Q' キー: 左プレビュー削除"); self._delete_single_file_from_preview(left_path)
        elif key == Qt.Key.Key_W: print("'W' キー: 右プレビュー削除"); self._delete_single_file_from_preview(right_path) # 右プレビューは重複タブでは使わないが念のため
        elif key == Qt.Key.Key_A: print("'A' キー: 左プレビューを開く"); left_path and open_file_external(left_path, self)
        elif key == Qt.Key.Key_S: print("'S' キー: 右プレビューを開く"); right_path and open_file_external(right_path, self)
        else: super().keyPressEvent(event)
