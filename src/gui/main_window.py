# gui/main_window.py
import sys
import os
import json
import traceback # エラー時のトレースバック表示用
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QFileDialog, QProgressBar,
    QMessageBox, QMenuBar, QTableWidget, QAbstractItemView
)
from PySide6.QtCore import Qt, QThreadPool, Slot, QDir
from PySide6.QtGui import QCloseEvent, QKeyEvent, QAction, QActionGroup
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any, Union, Set

# --- 型エイリアス ---
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

# --- ウィジェット、ワーカー、ダイアログをインポート ---
try:
    from .widgets.preview_widget import PreviewWidget
    from .widgets.results_tabs_widget import ResultsTabsWidget
    from .workers import ScanWorker, WorkerSignals
    from .dialogs.settings_dialog import SettingsDialog
except ImportError as e:
    print(f"エラー: GUIコンポーネントのインポートに失敗 ({e})")
    traceback.print_exc()
    sys.exit(1)

# --- ユーティリティ関数をインポート ---
try:
    from utils.config_handler import load_settings, save_settings
    from utils.file_operations import delete_files_to_trash, open_file_external, rename_images_to_sequence
    from utils.results_handler import save_results_to_file, load_results_from_file, load_scan_state, delete_scan_state, get_state_filepath
except ImportError as e:
    print(f"エラー: ユーティリティモジュールのインポートに失敗 ({e})")
    # フォールバック関数
    def load_settings() -> SettingsDict: return {'last_directory': os.path.expanduser("~"), 'theme': 'light', 'last_save_load_dir': os.path.expanduser("~"), 'presets': {}}
    def save_settings(s: SettingsDict) -> bool: print("警告: 設定保存機能が無効"); return False
    def delete_files_to_trash(fps: List[str], p: Optional[QWidget] = None) -> DeleteResult: print("警告: 削除機能が無効"); return 0, [{'path': 'N/A', 'error': '削除機能が無効'}], set()
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
        self.setGeometry(100, 100, 1200, 800)
        self.threadpool: QThreadPool = QThreadPool()
        self.current_settings: SettingsDict = load_settings()
        # UI要素の型ヒント
        self.dir_label: QLabel
        self.dir_path_edit: QLineEdit
        self.select_dir_button: QPushButton
        self.settings_button: QPushButton
        self.save_results_button: QPushButton
        self.load_results_button: QPushButton
        self.scan_button: QPushButton
        self.cancel_button: QPushButton
        self.status_label: QLabel
        self.current_file_label: QLabel
        self.progress_bar: QProgressBar
        self.preview_widget: PreviewWidget
        self.results_tabs_widget: ResultsTabsWidget
        self.delete_button: QPushButton
        self.select_all_blurry_button: QPushButton
        self.select_all_duplicates_button: QPushButton
        self.deselect_all_button: QPushButton
        # --- その他のインスタンス変数 ---
        self.current_worker: Optional[ScanWorker] = None
        self.results_saved: bool = True
        self.light_theme_action: Optional[QAction] = None
        self.dark_theme_action: Optional[QAction] = None
        self._cancellation_requested: bool = False # 中止要求フラグを追加

        self._setup_ui()
        self._setup_menu()
        self._connect_signals()
        initial_theme = self.current_settings.get('theme', 'light')
        self._apply_theme(initial_theme)
        if initial_theme == 'dark' and self.dark_theme_action:
            self.dark_theme_action.setChecked(True)
        elif self.light_theme_action:
            self.light_theme_action.setChecked(True)
        initial_dir = self.current_settings.get('last_directory', '')
        if initial_dir and os.path.isdir(initial_dir):
            self.dir_path_edit.setText(initial_dir)
            self._set_scan_controls_enabled(True)
        else:
            self._set_scan_controls_enabled(False)


    def _setup_ui(self) -> None:
        """UI要素の作成と配置"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- 上部エリア: フォルダ選択とスキャンボタン ---
        top_area = QFrame()
        top_area.setFrameShape(QFrame.Shape.StyledPanel)
        top_layout = QVBoxLayout(top_area)
        top_layout.setContentsMargins(15, 15, 15, 15)
        top_layout.setSpacing(12)

        # フォルダ選択行
        folder_frame = QFrame()
        folder_frame.setFrameShape(QFrame.Shape.StyledPanel)
        folder_layout = QHBoxLayout(folder_frame)
        folder_layout.setContentsMargins(10, 10, 10, 10)

        self.dir_label = QLabel("対象フォルダ:")
        self.dir_path_edit = QLineEdit()
        self.dir_path_edit.setReadOnly(True)
        self.dir_path_edit.setMinimumHeight(30)
        self.select_dir_button = QPushButton("フォルダ選択")
        self.select_dir_button.setMinimumHeight(30)

        folder_layout.addWidget(self.dir_label)
        folder_layout.addWidget(self.dir_path_edit, 1)
        folder_layout.addWidget(self.select_dir_button)
        top_layout.addWidget(folder_frame)

        # スキャンボタンと設定ボタン
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        # メインアクションボタン
        action_frame = QFrame()
        action_frame.setFrameShape(QFrame.Shape.StyledPanel)
        action_layout = QHBoxLayout(action_frame)
        action_layout.setContentsMargins(10, 10, 10, 10)

        self.scan_button = QPushButton("スキャン開始")
        self.scan_button.setObjectName("scan_button")
        self.scan_button.setMinimumHeight(40)
        self.scan_button.setMinimumWidth(150)
        self.scan_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_MediaPlay))

        self.cancel_button = QPushButton("中止")
        self.cancel_button.setObjectName("cancel_button")
        self.cancel_button.setMinimumHeight(40)
        self.cancel_button.setMinimumWidth(150)
        self.cancel_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_MediaStop))
        self.cancel_button.setVisible(False)

        action_layout.addWidget(self.scan_button)
        action_layout.addWidget(self.cancel_button)
        button_layout.addWidget(action_frame)

        # ユーティリティエリア（プログレスバーとステータス表示用）
        util_frame = QFrame()
        util_frame.setFrameShape(QFrame.Shape.StyledPanel)
        util_layout = QVBoxLayout(util_frame)
        util_layout.setContentsMargins(10, 10, 10, 10)
        util_layout.setSpacing(5)
        
        # ステータス表示をこちらに移動
        self.status_label = QLabel("フォルダを選択してください")
        self.status_label.setWordWrap(True)
        util_layout.addWidget(self.status_label)
        
        self.current_file_label = QLabel(" ") # 現在処理中のファイル名表示ラベル
        self.current_file_label.setStyleSheet("font-size: 9pt; color: #666;")
        util_layout.addWidget(self.current_file_label)
        
        # プログレスバーをこちらに移動
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self._set_progress_bar_visible(False) # 初期状態では非表示
        util_layout.addWidget(self.progress_bar)

        button_layout.addWidget(util_frame, 1)  # 右側を広く
        top_layout.addLayout(button_layout)

        main_layout.addWidget(top_area)

        # --- 中央エリア: 結果とプレビュー ---
        central_area = QFrame()
        central_area.setFrameShape(QFrame.Shape.StyledPanel)
        central_layout = QVBoxLayout(central_area)
        central_layout.setContentsMargins(15, 15, 15, 15)
        central_layout.setSpacing(12)

        # 操作ボタン
        action_frame = QFrame()
        action_frame.setFrameShape(QFrame.Shape.StyledPanel)
        action_layout = QHBoxLayout(action_frame)
        action_layout.setContentsMargins(10, 10, 10, 10)

        self.delete_button = QPushButton("選択項目を削除")
        self.delete_button.setObjectName("delete_button")
        self.delete_button.setToolTip("現在表示中のタブで選択されている項目をゴミ箱に移動します")
        self.delete_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_TrashIcon))
        self.delete_button.setMinimumHeight(36)

        # 選択ボタンはアイコンつきに
        self.select_all_blurry_button = QPushButton("ブレ画像選択")
        self.select_all_blurry_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogApplyButton))

        self.select_all_duplicates_button = QPushButton("重複選択")
        self.select_all_duplicates_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogApplyButton))

        self.deselect_all_button = QPushButton("選択解除")
        self.deselect_all_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogCancelButton))

        action_layout.addWidget(self.delete_button)
        action_layout.addStretch()
        action_layout.addWidget(self.select_all_blurry_button)
        action_layout.addWidget(self.select_all_duplicates_button)
        action_layout.addWidget(self.deselect_all_button)

        central_layout.addWidget(action_frame)

        # プレビューと結果を水平に並べるレイアウト
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)

        # プレビュー
        preview_area = QFrame()
        preview_area.setFrameShape(QFrame.Shape.StyledPanel)
        preview_layout = QVBoxLayout(preview_area)
        preview_layout.setContentsMargins(8, 8, 8, 8)

        self.preview_widget = PreviewWidget(self)
        preview_layout.addWidget(self.preview_widget)

        # 幅を固定にして、縦に伸ばす
        preview_area.setFixedWidth(600)  # プレビュー幅を拡大
        content_layout.addWidget(preview_area)

        # 結果タブ
        results_frame = QFrame()
        results_frame.setFrameShape(QFrame.Shape.StyledPanel)
        results_layout = QVBoxLayout(results_frame)
        results_layout.setContentsMargins(8, 8, 8, 8)

        self.results_tabs_widget = ResultsTabsWidget(self)
        results_layout.addWidget(self.results_tabs_widget)

        content_layout.addWidget(results_frame, 1)  # 横方向に伸ばす

        central_layout.addLayout(content_layout, 1)  # 縦方向に伸ばす
        main_layout.addWidget(central_area, 1)

        # --- 初期状態設定 ---
        self._set_scan_controls_enabled(False)
        self._set_action_buttons_enabled(False)
        
        # メニューアクションの初期状態設定
        if hasattr(self, 'save_results_action'):
            self.save_results_action.setEnabled(False)
        if hasattr(self, 'load_results_action'):
            self.load_results_action.setEnabled(True)

    def _setup_menu(self):
        """メニューバーとテーマ切り替えメニューを作成"""
        menu_bar = self.menuBar()
        if menu_bar is None:
            menu_bar = QMenuBar(self)
            self.setMenuBar(menu_bar)

        # 機能メニューを追加
        func_menu = menu_bar.addMenu("機能(&F)")
        
        # 設定アクション
        self.settings_action = QAction("設定...", self)
        self.settings_action.triggered.connect(self.open_settings)
        self.settings_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogDetailedView))
        func_menu.addAction(self.settings_action)
        
        # セパレータ
        func_menu.addSeparator()
        
        # 結果保存アクション
        self.save_results_action = QAction("結果保存...", self)
        self.save_results_action.triggered.connect(self.save_results)
        self.save_results_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogSaveButton))
        func_menu.addAction(self.save_results_action)
        
        # 結果読込アクション
        self.load_results_action = QAction("結果読込...", self)
        self.load_results_action.triggered.connect(self.load_results)
        self.load_results_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogOpenButton))
        func_menu.addAction(self.load_results_action)
        
        # セパレータ
        func_menu.addSeparator()
        
        # 画像連番リネームアクション
        self.rename_images_action = QAction("画像を連番にリネーム...", self)
        self.rename_images_action.triggered.connect(self.rename_images_to_sequential)
        self.rename_images_action.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogListView))
        self.rename_images_action.setToolTip("選択したフォルダ内の画像ファイルを1, 2, 3...のように連番にリネームします")
        func_menu.addAction(self.rename_images_action)
        
        # 表示メニュー
        view_menu = menu_bar.addMenu("表示(&V)")
        theme_menu = view_menu.addMenu("テーマ(&T)")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        self.light_theme_action = QAction("ライト", self, checkable=True)
        self.light_theme_action.triggered.connect(lambda: self._switch_theme('light'))
        theme_menu.addAction(self.light_theme_action)
        theme_group.addAction(self.light_theme_action)

        self.dark_theme_action = QAction("ダーク", self, checkable=True)
        self.dark_theme_action.triggered.connect(lambda: self._switch_theme('dark'))
        theme_menu.addAction(self.dark_theme_action)
        theme_group.addAction(self.dark_theme_action)

    def _load_stylesheet(self, filename: str) -> str:
        """指定されたファイル名のスタイルシートを読み込む"""
        basedir = os.path.dirname(__file__)
        style_path = os.path.join(basedir, "styles", filename)
        if not os.path.exists(style_path) and hasattr(sys, '_MEIPASS'):
             style_path = os.path.join(sys._MEIPASS, "gui", "styles", filename)
        if os.path.exists(style_path):
            try:
                with open(style_path, "r", encoding="utf-8") as f:
                    return f.read()
            except OSError as e:
                print(f"警告: スタイルシートの読み込みに失敗 ({filename}): {e}")
        else:
            print(f"警告: スタイルシートファイルが見つかりません: {style_path}")
        return ""

    def _apply_theme(self, theme_name: str):
        """指定されたテーマ名のスタイルシートを適用する"""
        qss_filename = f"{theme_name}.qss"
        stylesheet = self._load_stylesheet(qss_filename)
        app_instance = QApplication.instance()
        if app_instance:
            if stylesheet:
                app_instance.setStyleSheet(stylesheet)
                print(f"テーマ '{theme_name}' を適用しました。")
            else:
                app_instance.setStyleSheet("")
                print(f"テーマ '{theme_name}' のスタイルシートが見つかりません。デフォルトスタイルを適用します。")

    @Slot(str)
    def _switch_theme(self, theme_name: str):
        """テーマ切り替えメニューから呼び出されるスロット"""
        if theme_name != self.current_settings.get('theme'):
            self._apply_theme(theme_name)
            self.current_settings['theme'] = theme_name
            print(f"設定を '{theme_name}' テーマに更新しました。")

    def _connect_signals(self) -> None:
        """UI要素のシグナルとスロットを接続"""
        self.select_dir_button.clicked.connect(self.select_directory)
        self.scan_button.clicked.connect(self.start_scan)
        self.cancel_button.clicked.connect(self.request_scan_cancellation)

        # アクションボタン
        self.delete_button.clicked.connect(self.delete_selected_items)
        self.select_all_blurry_button.clicked.connect(self.results_tabs_widget.select_all_blurry)
        self.select_all_duplicates_button.clicked.connect(self.results_tabs_widget.select_all_duplicates)
        self.deselect_all_button.clicked.connect(self.results_tabs_widget.deselect_all)

        # 結果タブとプレビューの連携
        self.results_tabs_widget.selection_changed.connect(self.update_preview_display)
        self.preview_widget.left_preview_clicked.connect(self._delete_single_file_from_preview)
        self.preview_widget.right_preview_clicked.connect(self._delete_single_file_from_preview)

        # 結果タブからのリクエスト処理
        self.results_tabs_widget.delete_file_requested.connect(self._handle_delete_request)
        self.results_tabs_widget.open_file_requested.connect(self._handle_open_request)

    # --- スロット関数 ---
    @Slot()
    def select_directory(self) -> None:
        """「フォルダを選択...」ボタンがクリックされたときの処理"""
        last_dir: str = str(self.current_settings.get('last_directory', os.path.expanduser("~")))
        dir_path: str = QFileDialog.getExistingDirectory(self, "フォルダを選択", last_dir)

        if dir_path:
            state_filepath = get_state_filepath(dir_path)
            resume_state: Optional[ScanStateData] = None

            if os.path.exists(state_filepath):
                reply = QMessageBox.question(
                    self, "中断されたスキャン",
                    f"選択されたフォルダには中断されたスキャンデータが存在します。\n({os.path.basename(state_filepath)})\n\nスキャンを再開しますか？\n\n「いいえ」を選択すると、中断データは削除され、新しいスキャンが開始されます。",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes
                )
                if reply == QMessageBox.StandardButton.Yes:
                    loaded_state, error_msg = load_scan_state(dir_path)
                    if error_msg:
                        QMessageBox.warning(self, "状態読み込みエラー", f"中断データの読み込みに失敗しました:\n{error_msg}\n\n中断データは削除されます。")
                        delete_scan_state(dir_path)
                    else:
                        resume_state = loaded_state
                        print("スキャン再開を選択しました。")
                elif reply == QMessageBox.StandardButton.No:
                    print("新規スキャンを選択しました。中断データを削除します...")
                    delete_scan_state(dir_path)
                else:
                    print("フォルダ選択をキャンセルしました。")
                    return

            self.dir_path_edit.setText(dir_path)
            self.current_settings['last_directory'] = dir_path
            self._clear_all_results()
            self._update_ui_state(scan_enabled=True, actions_enabled=False, cancel_enabled=False)

            if resume_state:
                self.status_label.setText("中断されたスキャンを再開します...")
                self.start_scan(initial_state=resume_state)
            else:
                self.status_label.setText("フォルダを選択しました。スキャンを開始してください。")

    @Slot()
    def open_settings(self) -> None:
        """「設定...」ボタンがクリックされたときの処理"""
        if SettingsDialog is None:
            QMessageBox.warning(self, "エラー", "設定ダイアログを開けませんでした。")
            return

        dialog = SettingsDialog(self.current_settings, self)
        if dialog.exec():
            self.current_settings = dialog.get_settings()
            print("設定が更新されました:", self.current_settings)
        else:
            print("設定はキャンセルされました。")

    @Slot()
    def start_scan(self, initial_state: Optional[ScanStateData] = None) -> None:
        """「スキャン開始」ボタンがクリックされたときの処理、または再開処理"""
        selected_dir: str = self.dir_path_edit.text()
        if not self._validate_directory(selected_dir):
            return

        if initial_state is None and not self._confirm_unsaved_results("新しいスキャンを開始"):
            return

        if initial_state is None:
            delete_scan_state(selected_dir)

        self._clear_all_results()
        status_msg = "スキャン準備中..."
        if initial_state:
            status_msg = "スキャン再開中..."
        self.status_label.setText(status_msg)
        self.current_file_label.setText(" ")
        self._set_progress_bar_visible(True)
        self._update_ui_state(scan_enabled=False, actions_enabled=False, cancel_enabled=True)
        self._cancellation_requested = False # スキャン開始時にフラグをリセット

        self.current_worker = ScanWorker(selected_dir, self.current_settings, initial_state=initial_state)
        self.current_worker.signals.status_update.connect(self.update_status)
        self.current_worker.signals.progress_update.connect(self.update_progress_bar)
        if hasattr(self.current_worker.signals, 'processing_file'):
            self.current_worker.signals.processing_file.connect(self.update_current_file)
        self.current_worker.signals.results_ready.connect(self.populate_results_and_update_state)
        self.current_worker.signals.error.connect(self.handle_scan_error)
        self.current_worker.signals.finished.connect(self.handle_scan_finished)
        self.current_worker.signals.cancelled.connect(self.handle_scan_cancelled)

        self.threadpool.start(self.current_worker)

    @Slot()
    def request_scan_cancellation(self) -> None:
        """「中止」ボタンがクリックされたときの処理"""
        if self.current_worker:
            self.status_label.setText("ステータス: 中止処理中...")
            self.cancel_button.setEnabled(False)
            self._cancellation_requested = True # 中止要求フラグをセット
            self.current_worker.request_cancellation()
        else:
            print("警告: 中止対象のワーカースレッドが見つかりません。")

    @Slot(str)
    def update_status(self, message: str) -> None:
        """ScanWorkerからのステータス更新シグナルを受け取るスロット"""
        self.status_label.setText(message)

    @Slot(int)
    def update_progress_bar(self, value: int) -> None:
        """ScanWorkerからのプログレス更新シグナルを受け取るスロット"""
        self.progress_bar.setValue(value)

    @Slot(str)
    def update_current_file(self, filename: str) -> None:
        """ScanWorkerからの現在処理中ファイル名更新シグナルを受け取るスロット"""
        if filename:
            max_len = 60
            display_name = ("..." + filename[-(max_len-3):]) if len(filename) > max_len else filename
            self.current_file_label.setText(f"処理中: {display_name}")
        else:
            self.current_file_label.setText(" ")

    @Slot(list, list, dict, list)
    def populate_results_and_update_state(self, blurry: List[BlurResultItem], similar: List[SimilarPair], duplicates: DuplicateDict, errors: List[ErrorDict]) -> None:
        """ScanWorkerからの結果準備完了シグナルを受け取るスロット"""
        print("結果受信: Blurry={}, Similar={}, Duplicates={}, Errors={}".format(len(blurry), len(similar), len(duplicates), len(errors)))
        self.results_tabs_widget.populate_results(blurry, similar, duplicates, errors)
        has_results: bool = (self.results_tabs_widget.blurry_table.rowCount() > 0 or
                             self.results_tabs_widget.similar_table.rowCount() > 0 or
                             self.results_tabs_widget.duplicate_table.rowCount() > 0)
        self._update_ui_state(scan_enabled=True, actions_enabled=has_results, cancel_enabled=False)
        self.results_saved = False
        self.current_worker = None
        self._cancellation_requested = False # 完了時はフラグをリセット

    @Slot(str)
    def handle_scan_error(self, message: str) -> None:
        """ScanWorkerからの致命的エラーシグナルを受け取るスロット"""
        print(f"致命的エラー受信: {message}")
        QMessageBox.critical(self, "スキャンエラー", f"スキャン中に致命的なエラーが発生しました:\n{message}")
        self.status_label.setText(f"ステータス: 致命的エラー発生")
        self._set_progress_bar_visible(False)
        self._update_ui_state(scan_enabled=bool(self.dir_path_edit.text()), actions_enabled=False, cancel_enabled=False)
        self.current_file_label.setText(" ")
        self.current_worker = None
        self._cancellation_requested = False # エラー時はフラグをリセット

    @Slot()
    def handle_scan_finished(self) -> None:
        """ScanWorkerからの正常完了シグナルを受け取るスロット"""
        print("スキャン完了シグナル受信")
        error_count: int = self.results_tabs_widget.error_table.rowCount()
        if error_count > 0:
            self.status_label.setText(f"ステータス: スキャン完了 ({error_count}件のエラーあり)")
        else:
            self.status_label.setText("ステータス: スキャン完了")
        self._set_progress_bar_visible(False)
        has_results: bool = (self.results_tabs_widget.blurry_table.rowCount() > 0 or
                             self.results_tabs_widget.similar_table.rowCount() > 0 or
                             self.results_tabs_widget.duplicate_table.rowCount() > 0)
        self._update_ui_state(scan_enabled=True, actions_enabled=has_results, cancel_enabled=False)
        self.current_file_label.setText(" ")
        if self.dir_path_edit.text():
            delete_scan_state(self.dir_path_edit.text())
        self.current_worker = None
        self._cancellation_requested = False # 完了時はフラグをリセット

    @Slot()
    def handle_scan_cancelled(self) -> None:
        """ScanWorkerからの中断完了シグナルを受け取るスロット"""
        print("スキャン中止シグナル受信")
        self.status_label.setText("ステータス: スキャンが中断されました。")
        self._set_progress_bar_visible(False)
        self._update_ui_state(scan_enabled=True, actions_enabled=False, cancel_enabled=False)
        self.current_file_label.setText(" ")
        self.current_worker = None
        self._cancellation_requested = False # 中止時はフラグをリセット

    # ★★★ プレビュー表示更新ロジックを修正 ★★★
    @Slot()
    def update_preview_display(self) -> None:
        """結果タブの選択が変更されたときにプレビューを更新するスロット"""
        primary_path, secondary_path = self.results_tabs_widget.get_current_selection_paths()
        current_tab_index = self.results_tabs_widget.currentIndex()

        selection_type: str
        if current_tab_index == 0:
            selection_type = 'blurry'
        elif current_tab_index == 1:
            selection_type = 'similar'
        elif current_tab_index == 2:
            selection_type = 'duplicate'
        else:
            selection_type = 'error' # エラータブの場合

        # PreviewWidgetのupdate_previewsメソッドに選択タイプを渡す
        self.preview_widget.update_previews(primary_path, secondary_path, selection_type)


    @Slot()
    def delete_selected_items(self) -> None:
        """「選択した項目をゴミ箱へ移動」ボタンがクリックされたときの処理"""
        files_to_delete: List[str] = self._get_files_to_delete_from_current_tab()
        if not files_to_delete:
            return

        print(f"Attempting to delete {len(files_to_delete)} selected items...")
        self.status_label.setText(f"ステータス: 選択された {len(files_to_delete)} 項目を削除中...")
        QApplication.processEvents()

        errors_occurred: List[ErrorDict] = self._delete_files_and_update_ui(files_to_delete)

        has_results_after_delete: bool = (self.results_tabs_widget.blurry_table.rowCount() > 0 or
                                          self.results_tabs_widget.similar_table.rowCount() > 0 or
                                          self.results_tabs_widget.duplicate_table.rowCount() > 0)

        if not self.results_saved:
            if errors_occurred:
                self.status_label.setText(f"ステータス: 削除処理中にエラーが発生しました ({len(errors_occurred)}件)。")
            else:
                 deleted_count = len(files_to_delete) - len(errors_occurred)
                 if deleted_count > 0:
                     self.status_label.setText(f"ステータス: {deleted_count} 個の項目をゴミ箱に移動しました。")
                 else:
                     self.status_label.setText(f"ステータス: 削除処理が完了しましたが、ファイルは移動されませんでした。")
        else:
             self.status_label.setText(f"ステータス: 削除処理完了 (UI変更なし)。")

        self._update_ui_state(actions_enabled=has_results_after_delete)
        print("Deletion process finished.")


    @Slot(str)
    def _delete_single_file_from_preview(self, file_path: str) -> None:
        """プレビュー画像がクリックされたときに呼び出されるスロット (削除と再選択処理)"""
        print(f"プレビュークリック削除要求受信: {file_path}")
        if not file_path:
            return

        # 削除前に現在のテーブルと行インデックスを取得
        current_tab_index = self.results_tabs_widget.currentIndex()
        current_table: Optional[QTableWidget] = self.results_tabs_widget.widget(current_tab_index)
        if not isinstance(current_table, QTableWidget):
            print("警告: アクティブなテーブルが見つかりません。")
            return

        original_row_index = self._find_row_index_by_path(current_table, file_path)
        # if original_row_index == -1:
        #     print(f"警告: 削除対象のファイルパス {file_path} が現在のテーブルに見つかりません。")
            # 見つからなくても削除確認は行う

        # 確認ダイアログを表示
        filename = os.path.basename(file_path)
        reply = QMessageBox.question(self, "削除の確認",
                                     f"プレビューの画像 '{filename}' をゴミ箱に移動しますか？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # ファイル削除とUI更新を実行
            errors_occurred = self._delete_files_and_update_ui([file_path])

            # 削除成功後に再選択処理
            deletion_successful = not errors_occurred and not self.results_saved

            if deletion_successful:
                # 再度アクティブなテーブルを取得
                current_table_after_delete: Optional[QTableWidget] = self.results_tabs_widget.widget(self.results_tabs_widget.currentIndex())
                if isinstance(current_table_after_delete, QTableWidget):
                    new_row_count = current_table_after_delete.rowCount()
                    if new_row_count > 0:
                        # 削除された行のインデックス、または最後の行を選択
                        next_row_index = min(original_row_index if original_row_index != -1 else new_row_count -1, new_row_count - 1)
                        next_row_index = max(0, next_row_index)

                        print(f"削除後、行 {next_row_index} を選択します。")
                        current_table_after_delete.clearSelection()
                        # ブレ画像タブの場合はチェックボックスを操作できないので selectRow
                        if current_tab_index == 0:
                             current_table_after_delete.selectRow(next_row_index)
                        else: # 類似・重複ペアタブは行選択
                             current_table_after_delete.selectRow(next_row_index)

                        # 選択した行が表示されるようにスクロール
                        item_to_scroll = current_table_after_delete.item(next_row_index, 0)
                        if item_to_scroll:
                            current_table_after_delete.scrollToItem(item_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)
                        # プレビューを更新 (選択状態が変わったシグナルが飛ぶはずだが念のため)
                        self.update_preview_display()
                    else:
                        print("テーブルが空になったため、再選択は行いません。")
                        self.preview_widget.clear_previews()

            # ステータスバー等の更新
            has_results_after_delete: bool = (self.results_tabs_widget.blurry_table.rowCount() > 0 or
                                              self.results_tabs_widget.similar_table.rowCount() > 0 or
                                              self.results_tabs_widget.duplicate_table.rowCount() > 0)
            if not self.results_saved:
                if errors_occurred:
                    self.status_label.setText(f"ステータス: '{filename}' の削除中にエラーが発生しました。")
                else:
                    self.status_label.setText(f"ステータス: '{filename}' をゴミ箱に移動しました。")
            else:
                 self.status_label.setText(f"ステータス: '{filename}' 削除処理完了 (ファイル移動なし)。")
            self._update_ui_state(actions_enabled=has_results_after_delete)
        else:
            print("プレビューからの削除はキャンセルされました。")

    @Slot(str)
    def _handle_delete_request(self, file_path: str) -> None:
        """結果タブのコンテキストメニューからの削除要求を処理するスロット"""
        if not file_path:
            return

        # 削除前に現在のテーブルと行インデックスを取得
        current_tab_index = self.results_tabs_widget.currentIndex()
        current_table: Optional[QTableWidget] = self.results_tabs_widget.widget(current_tab_index)
        if not isinstance(current_table, QTableWidget): return

        original_row_index = self._find_row_index_by_path(current_table, file_path)

        # 削除処理（確認はdelete_files_to_trash内）
        errors_occurred = self._delete_files_and_update_ui([file_path])

        # 削除成功後に再選択処理
        deletion_successful = not errors_occurred and not self.results_saved
        if deletion_successful:
             current_table_after_delete: Optional[QTableWidget] = self.results_tabs_widget.widget(self.results_tabs_widget.currentIndex())
             if isinstance(current_table_after_delete, QTableWidget):
                 new_row_count = current_table_after_delete.rowCount()
                 if new_row_count > 0:
                     next_row_index = min(original_row_index if original_row_index != -1 else new_row_count -1, new_row_count - 1)
                     next_row_index = max(0, next_row_index)
                     print(f"コンテキストメニュー削除後、行 {next_row_index} を選択します。")
                     current_table_after_delete.clearSelection()
                     current_table_after_delete.selectRow(next_row_index)
                     item_to_scroll = current_table_after_delete.item(next_row_index, 0)
                     if item_to_scroll:
                         current_table_after_delete.scrollToItem(item_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)
                     self.update_preview_display()
                 else:
                     self.preview_widget.clear_previews()

        # ステータス更新
        has_results_after_delete: bool = (self.results_tabs_widget.blurry_table.rowCount() > 0 or
                                          self.results_tabs_widget.similar_table.rowCount() > 0 or
                                          self.results_tabs_widget.duplicate_table.rowCount() > 0)
        filename = os.path.basename(file_path)
        if not self.results_saved:
            if errors_occurred:
                self.status_label.setText(f"ステータス: '{filename}' の削除中にエラーが発生しました。")
            else:
                self.status_label.setText(f"ステータス: '{filename}' をゴミ箱に移動しました。")
        else:
            self.status_label.setText(f"ステータス: '{filename}' 削除処理完了 (ファイル移動なし)。")
        self._update_ui_state(actions_enabled=has_results_after_delete)

    @Slot(str)
    def _handle_open_request(self, file_path: str) -> None:
        """結果タブのコンテキストメニューからのファイルを開く要求を処理するスロット"""
        print(f"オープン要求受信: {file_path}")
        if file_path:
            open_file_external(file_path, self)
            
    @Slot()
    def rename_images_to_sequential(self) -> None:
        """画像ファイルを連番にリネームする機能"""
        current_dir: str = self.dir_path_edit.text()
        if not self._validate_directory(current_dir, "画像リネーム"):
            return

        # 進捗表示を更新
        self.status_label.setText(f"ステータス: 画像ファイルの連番リネームを準備中...")
        self._set_progress_bar_visible(True)
        self.progress_bar.setValue(10)
        QApplication.processEvents()

        # リネーム処理を実行
        self.status_label.setText(f"ステータス: リネーム処理を実行中...")
        self.progress_bar.setValue(50)
        QApplication.processEvents()
        
        renamed_count, errors = rename_images_to_sequence(current_dir, self)
        
        # 進捗表示を完了に設定
        self.progress_bar.setValue(100)
        QApplication.processEvents()
        
        # 処理完了後、プログレスバーを非表示に
        self._set_progress_bar_visible(False)
        
        # 結果をステータスに表示
        if renamed_count > 0:
            self.status_label.setText(f"ステータス: {renamed_count} 個のファイルを連番にリネームしました。")
        else:
            if not errors:
                self.status_label.setText(f"ステータス: リネーム処理はキャンセルされたか、対象ファイルがありませんでした。")
            else:
                self.status_label.setText(f"ステータス: リネーム処理中にエラーが発生しました。")

    @Slot()
    def save_results(self) -> None:
        """「結果を保存...」ボタンがクリックされたときの処理"""
        current_dir: str = self.dir_path_edit.text()
        if not self._validate_directory(current_dir, "結果の保存"):
            return

        filepath: Optional[str] = self._get_save_filepath(current_dir)
        if not filepath:
            return

        # 保存開始時にUI状態を更新
        self.status_label.setText(f"ステータス: 結果を '{os.path.basename(filepath)}' に保存準備中...")
        self._set_progress_bar_visible(True)
        self.progress_bar.setValue(10)  # 初期進捗表示
        QApplication.processEvents()  # UIを更新

        self.current_settings['last_save_load_dir'] = os.path.dirname(filepath)

        # 進捗表示を更新
        self.status_label.setText(f"ステータス: 結果データを収集中...")
        self.progress_bar.setValue(30)
        QApplication.processEvents()

        results_data: ResultsData = self.results_tabs_widget.get_results_data()

        # 進捗表示を更新
        self.status_label.setText(f"ステータス: 結果をファイルに書き込み中...")
        self.progress_bar.setValue(70)
        QApplication.processEvents()

        success: bool = save_results_to_file(filepath, results_data, current_dir, self.current_settings)

        # 進捗表示を完了に設定
        self.progress_bar.setValue(100)
        QApplication.processEvents()

        # 結果に応じたメッセージを表示
        if success:
            self.status_label.setText(f"ステータス: 結果をファイルに保存しました: {os.path.basename(filepath)}")
            QMessageBox.information(self, "保存完了", f"結果をファイルに保存しました:\n{filepath}")
            self.results_saved = True
        else:
            self.status_label.setText(f"ステータス: 保存中にエラーが発生しました")
            QMessageBox.critical(self, "保存エラー", "結果のファイルへの保存中にエラーが発生しました。")
        
        # 処理完了後、プログレスバーを非表示に
        self._set_progress_bar_visible(False)

    @Slot()
    def load_results(self) -> None:
        """「結果を読み込み...」ボタンがクリックされたときの処理"""
        if not self.results_saved:
             if not self._confirm_unsaved_results("結果を読み込み"):
                 return

        filepath: Optional[str] = self._get_load_filepath()
        if not filepath:
            return

        # 読み込み開始時にUI状態を更新
        self.status_label.setText(f"ステータス: 結果ファイル '{os.path.basename(filepath)}' を読み込み中...")
        self._set_progress_bar_visible(True)
        self.progress_bar.setValue(10)  # 初期進捗表示
        QApplication.processEvents()  # UIを更新

        self.current_settings['last_save_load_dir'] = os.path.dirname(filepath)

        # 進捗表示を更新
        self.status_label.setText(f"ステータス: ファイルからデータを読み込み中...")
        self.progress_bar.setValue(30)
        QApplication.processEvents()

        results_data: Optional[ResultsData]
        scanned_directory: Optional[str]
        settings_used: Optional[SettingsDict]
        error_message: Optional[str]
        results_data, scanned_directory, settings_used, error_message = load_results_from_file(filepath)

        # エラー処理
        if error_message:
            self._set_progress_bar_visible(False)
            self.status_label.setText(f"ステータス: 読み込みエラー - {error_message}")
            QMessageBox.critical(self, "読み込みエラー", f"結果ファイルの読み込み中にエラーが発生しました:\n{error_message}")
            return

        # 進捗表示を更新
        self.status_label.setText(f"ステータス: 対象ディレクトリを確認中...")
        self.progress_bar.setValue(50)
        QApplication.processEvents()

        current_target_dir: str = self.dir_path_edit.text()
        if not self._confirm_directory_mismatch(scanned_directory, current_target_dir):
            self._set_progress_bar_visible(False)
            self.status_label.setText("ステータス: 読み込みがキャンセルされました")
            return

        if scanned_directory and scanned_directory != current_target_dir:
            self.dir_path_edit.setText(scanned_directory)
            self.current_settings['last_directory'] = scanned_directory

        # 進捗表示を更新
        self.status_label.setText(f"ステータス: 結果をクリアして新しいデータを準備中...")
        self.progress_bar.setValue(70)
        QApplication.processEvents()

        self._clear_all_results()
        
        # 進捗表示を更新
        self.status_label.setText(f"ステータス: 結果データを表示用に処理中...")
        self.progress_bar.setValue(80)
        QApplication.processEvents()
        
        if results_data:
            # populate_results 内で存在しないファイルはフィルタリングされる
            self.results_tabs_widget.populate_results(
                results_data.get('blurry', []),
                results_data.get('similar', []),
                results_data.get('duplicates', {}),
                results_data.get('errors', [])
            )

        if settings_used:
            print("読み込んだ結果のスキャン時設定:", settings_used)

        # 進捗表示を完了に設定
        self.progress_bar.setValue(100)
        QApplication.processEvents()
        
        # 完了メッセージの表示
        self.status_label.setText(f"ステータス: 結果を読み込みました: {os.path.basename(filepath)}")
        
        # プログレスバーを非表示に
        self._set_progress_bar_visible(False)
        
        has_results: bool = (self.results_tabs_widget.blurry_table.rowCount() > 0 or
                             self.results_tabs_widget.similar_table.rowCount() > 0 or
                             self.results_tabs_widget.duplicate_table.rowCount() > 0)
        self._update_ui_state(scan_enabled=True, actions_enabled=has_results, cancel_enabled=False)
        self.results_saved = True

    # --- ヘルパーメソッド ---
    def _find_row_index_by_path(self, table: QTableWidget, file_path: str) -> int:
        """指定されたテーブル内で、特定のファイルパスを持つ行のインデックスを返す"""
        normalized_path_to_find = os.path.normpath(file_path)
        current_tab_index = self.results_tabs_widget.indexOf(table)

        for row in range(table.rowCount()):
            item_data: Any = None
            if current_tab_index == 0: # ブレ画像タブ
                item = table.item(row, 0)
                item_data = item.data(Qt.ItemDataRole.UserRole) if item else None
                if isinstance(item_data, str) and os.path.normpath(item_data) == normalized_path_to_find:
                    return row
            elif current_tab_index == 1: # 類似ペアタブ
                # 類似ペアタブでは、ファイル1のパスは4列目、ファイル2のパスは9列目
                item1_path_item = table.item(row, 4)
                item2_path_item = table.item(row, 9)
                path1: Optional[str] = item1_path_item.text() if item1_path_item else None
                path2: Optional[str] = item2_path_item.text() if item2_path_item else None

                if (path1 and os.path.normpath(path1) == normalized_path_to_find) or \
                   (path2 and os.path.normpath(path2) == normalized_path_to_find):
                    return row
            elif current_tab_index == 2: # 重複ペアタブ
                 # 重複ペアタブでは、ファイル1のパスは4列目、ファイル2のパスは9列目
                item1_path_item = table.item(row, 4)
                item2_path_item = table.item(row, 9)
                path1: Optional[str] = item1_path_item.text() if item1_path_item else None
                path2: Optional[str] = item2_path_item.text() if item2_path_item else None

                if (path1 and os.path.normpath(path1) == normalized_path_to_find) or \
                   (path2 and os.path.normpath(path2) == normalized_path_to_find):
                    return row
        return -1


    def _clear_all_results(self) -> None:
        """結果表示エリアとプレビューをクリアする"""
        self.results_tabs_widget.clear_results()
        self.preview_widget.clear_previews()
        self.results_saved = True

    def _validate_directory(self, dir_path: str, action_name: str = "処理") -> bool:
        """指定されたディレクトリパスが有効か検証する"""
        if not dir_path or not os.path.isdir(dir_path):
            QMessageBox.warning(self, "エラー", f"有効なフォルダが選択されていません。\n{action_name}を実行できません。")
            self.status_label.setText(f"ステータス: エラー - フォルダ未選択")
            return False
        return True

    def _confirm_unsaved_results(self, action_name: str) -> bool:
        """未保存の結果がある場合にユーザーに確認する"""
        if not self.results_saved:
            reply = QMessageBox.question(
                self, "確認",
                f"現在の結果は保存されていません。\n{action_name}を実行すると、現在の結果は失われます。\n\n続行しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            return reply == QMessageBox.StandardButton.Yes
        return True

    def _get_save_filepath(self, current_dir: str) -> Optional[str]:
        """結果保存用のファイルパスをユーザーに選択させる"""
        timestamp: str = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_filename: str = f"image_cleaner_results_{timestamp}.json"
        save_dir: str = str(self.current_settings.get('last_save_load_dir', current_dir))
        filepath, _ = QFileDialog.getSaveFileName(
            self, "結果を保存", os.path.join(save_dir, default_filename), "JSON Files (*.json)"
        )
        return filepath if filepath else None

    def _get_load_filepath(self) -> Optional[str]:
        """結果読み込み用のファイルパスをユーザーに選択させる"""
        load_dir: str = str(self.current_settings.get('last_save_load_dir', os.path.expanduser("~")))
        filepath, _ = QFileDialog.getOpenFileName(
            self, "結果を読み込み", load_dir, "JSON Files (*.json)"
        )
        return filepath if filepath else None

    def _confirm_directory_mismatch(self, loaded_dir: Optional[str], current_dir: str) -> bool:
        """結果ファイルと現在の対象フォルダが異なる場合に確認する"""
        if loaded_dir and loaded_dir != current_dir:
            reply = QMessageBox.warning(
                self, "フォルダ不一致",
                f"読み込もうとしている結果は、現在の対象フォルダとは異なるフォルダでスキャンされたものです。\n\n読み込み元: {loaded_dir}\n現在: {current_dir}\n\n読み込みを続行し、対象フォルダを読み込み元に合わせますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            return reply == QMessageBox.StandardButton.Yes
        return True

    def _get_files_to_delete_from_current_tab(self) -> List[str]:
        """現在アクティブなタブから削除対象のファイルパスリストを取得する"""
        files_to_delete: List[str] = []
        current_tab_index: int = self.results_tabs_widget.currentIndex()
        msg: str = ""

        if current_tab_index == 0: # ブレ画像タブ
            files_to_delete = self.results_tabs_widget.get_selected_blurry_paths()
            msg = "削除対象のブレ画像がチェックされていません。"
        elif current_tab_index == 1: # 類似ペアタブ
            # チェックボックスで選択されたファイルを取得
            for row in range(self.results_tabs_widget.similar_table.rowCount()):
                # チェックボックス1（ファイル1）のチェック状態を確認 - インデックス0
                chk1_item = self.results_tabs_widget.similar_table.item(row, 0)
                if chk1_item and chk1_item.checkState() == Qt.CheckState.Checked:
                    path1: Optional[str] = chk1_item.data(Qt.ItemDataRole.UserRole)
                    if path1:
                        files_to_delete.append(path1)

                # チェックボックス2（ファイル2）のチェック状態を確認 - インデックス5
                chk2_item = self.results_tabs_widget.similar_table.item(row, 5)
                if chk2_item and chk2_item.checkState() == Qt.CheckState.Checked:
                    path2: Optional[str] = chk2_item.data(Qt.ItemDataRole.UserRole)
                    if path2:
                        files_to_delete.append(path2)

            # 行選択されている場合はファイル2を追加（後方互換性のため）
            # この部分はチェックボックス選択が主になったため、必要に応じて調整または削除
            if not files_to_delete: # チェックボックスで何も選択されていない場合のみ
                 selected_rows: Set[int] = set(item.row() for item in self.results_tabs_widget.similar_table.selectedItems())
                 for row in selected_rows:
                     # ファイル2のパスは9列目
                     path2_item = self.results_tabs_widget.similar_table.item(row, 9)
                     path2: Optional[str] = path2_item.text() if path2_item else None
                     if path2:
                         files_to_delete.append(path2)


            msg = "削除対象の類似ペアが選択されていません。"
        elif current_tab_index == 2: # 重複ペアタブ
             # チェックボックスで選択されたファイルを取得
            for row in range(self.results_tabs_widget.duplicate_table.rowCount()):
                # チェックボックス1（ファイル1）のチェック状態を確認 - インデックス0
                chk1_item = self.results_tabs_widget.duplicate_table.item(row, 0)
                if chk1_item and chk1_item.checkState() == Qt.CheckState.Checked:
                    path1: Optional[str] = chk1_item.data(Qt.ItemDataRole.UserRole)
                    if path1:
                        files_to_delete.append(path1)

                # チェックボックス2（ファイル2）のチェック状態を確認 - インデックス5
                chk2_item = self.results_tabs_widget.duplicate_table.item(row, 5)
                if chk2_item and chk2_item.checkState() == Qt.CheckState.Checked:
                    path2: Optional[str] = chk2_item.data(Qt.ItemDataRole.UserRole)
                    if path2:
                        files_to_delete.append(path2)

            # 行選択されている場合はファイル2を追加（後方互換性のため）
            # この部分はチェックボックス選択が主になったため、必要に応じて調整または削除
            if not files_to_delete: # チェックボックスで何も選択されていない場合のみ
                selected_rows: Set[int] = set(item.row() for item in self.results_tabs_widget.duplicate_table.selectedItems())
                for row in selected_rows:
                     # ファイル2のパスは9列目
                    path2_item = self.results_tabs_widget.duplicate_table.item(row, 9)
                    path2: Optional[str] = path2_item.text() if path2_item else None
                    if path2:
                        files_to_delete.append(path2)

            msg = "削除対象の重複ペアが選択されていません。"
        elif current_tab_index == 3: # エラータブ
            QMessageBox.information(self, "情報", "エラータブからは直接削除できません。")
            return []
        else:
            return []

        # 重複を排除
        files_to_delete = list(set(files_to_delete))

        if not files_to_delete:
            QMessageBox.information(self, "情報", msg)
        return files_to_delete


    def _delete_files_and_update_ui(self, files_to_delete: List[str]) -> List[ErrorDict]:
        """指定されたファイルリストをゴミ箱に移動し、UIを更新する"""
        if not files_to_delete:
            return []
        deleted_count: int; errors: List[ErrorDict]; files_actually_deleted: Set[str]
        deleted_count, errors, files_actually_deleted = delete_files_to_trash(files_to_delete, self)
        if files_actually_deleted:
            print(f"UI Update: Removing {len(files_actually_deleted)} items from tables.")
            self.results_tabs_widget.remove_items_by_paths(files_actually_deleted)
            self.results_saved = False
        return errors

    def _set_scan_controls_enabled(self, enabled: bool) -> None:
        """スキャン関連のボタンの有効/無効を設定"""
        self.scan_button.setEnabled(enabled)
        
        # メニューアクションの状態も更新
        if hasattr(self, 'settings_action'):
            self.settings_action.setEnabled(enabled)

    def _set_action_buttons_enabled(self, enabled: bool) -> None:
        """結果に対するアクションボタンの有効/無効を設定"""
        self.delete_button.setEnabled(enabled)
        # ブレ画像タブの選択ボタンは常に有効でも良いかもしれないが、ここでは結果がある場合のみ有効にする
        self.select_all_blurry_button.setEnabled(enabled)
        self.select_all_duplicates_button.setEnabled(enabled)
        self.deselect_all_button.setEnabled(enabled)
        
        # メニューアクションの状態も更新
        if hasattr(self, 'save_results_action'):
            self.save_results_action.setEnabled(enabled)
        if hasattr(self, 'load_results_action'):
            # 結果読込は常に有効
            self.load_results_action.setEnabled(True)

    def _set_progress_bar_visible(self, visible: bool) -> None:
        """プログレスバーの表示/非表示を設定"""
        self.progress_bar.setVisible(visible)
        if not visible:
            self.progress_bar.setValue(0)

    def _update_ui_state(self, scan_enabled: Optional[bool] = None, actions_enabled: Optional[bool] = None, cancel_enabled: Optional[bool] = None) -> None:
        """UIの各コントロールの有効/無効、表示/非表示を一括で更新する"""
        if scan_enabled is not None:
            self._set_scan_controls_enabled(scan_enabled)
            if cancel_enabled is not None:
                self.scan_button.setVisible(not cancel_enabled)
            else:
                self.scan_button.setVisible(scan_enabled)
        if actions_enabled is not None:
            self._set_action_buttons_enabled(actions_enabled)
        if cancel_enabled is not None:
            self.cancel_button.setVisible(cancel_enabled)
            self.cancel_button.setEnabled(cancel_enabled)

    # --- イベントハンドラ ---
    def closeEvent(self, event: QCloseEvent) -> None:
        """ウィンドウが閉じられるときのイベント"""
        if self.current_worker and not self._cancellation_requested: # 中止要求フラグも確認
             reply = QMessageBox.question(
                 self, "確認", "スキャン処理が実行中です。\nアプリケーションを終了すると、現在のスキャンは中断されます。\n\n終了しますか？",
                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
             )
             if reply == QMessageBox.StandardButton.Yes:
                 print("終了前にスキャンを中止します...")
                 self.request_scan_cancellation()
                 # 中止完了を待つためにイベント処理を保留
                 event.ignore()
                 return
             else:
                 event.ignore()
                 return

        if not self._confirm_unsaved_results("アプリケーションを終了"):
            event.ignore()
            return

        if not save_settings(self.current_settings):
            print("警告: 設定ファイルの保存に失敗しました。")
        else:
            print("アプリケーション終了時に設定を保存しました。")

        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """キーボードショートカットの処理"""
        key: int = event.key()
        left_path: Optional[str] = self.preview_widget.get_left_image_path()
        right_path: Optional[str] = self.preview_widget.get_right_image_path()

        # 現在表示中のタブに応じて削除対象を決定
        current_tab_index = self.results_tabs_widget.currentIndex()
        can_delete_left = False
        can_delete_right = False

        if current_tab_index == 0 and left_path: # ブレ画像タブ
            can_delete_left = True
        elif current_tab_index in [1, 2]: # 類似・重複ペアタブ
            if left_path: can_delete_left = True
            if right_path: can_delete_right = True


        if key == Qt.Key.Key_Q and can_delete_left:
            print("Qキー: 左プレビュー削除要求")
            self._delete_single_file_from_preview(left_path)
        elif key == Qt.Key.Key_W and can_delete_right:
            print("Wキー: 右プレビュー削除要求")
            self._delete_single_file_from_preview(right_path)
        elif key == Qt.Key.Key_A and left_path:
            print("Aキー: 左プレビューを開く要求")
            self._handle_open_request(left_path)
        elif key == Qt.Key.Key_S and right_path:
            print("Sキー: 右プレビューを開く要求")
            self._handle_open_request(right_path)
        elif key == Qt.Key.Key_Escape and self.cancel_button.isVisible() and self.cancel_button.isEnabled():
            print("Escキー: スキャン中止要求")
            self.request_scan_cancellation()
        else:
            super().keyPressEvent(event)

# アプリケーション実行部分
if __name__ == '__main__':
    app = QApplication(sys.argv)
    settings = load_settings()
    initial_theme = settings.get('theme', 'light')
    def load_stylesheet_local(filename: str) -> str:
        basedir = os.path.dirname(__file__)
        style_path = os.path.join(basedir, "styles", filename)
        if not os.path.exists(style_path) and hasattr(sys, '_MEIPASS'):
            style_path = os.path.join(sys._MEIPASS, "gui", "styles", filename)
        if os.path.exists(style_path):
            try:
                with open(style_path, "r", encoding="utf-8") as f: return f.read()
            except OSError as e: print(f"警告: スタイルシート読み込み失敗 ({filename}): {e}")
        else: print(f"警告: スタイルシートファイルが見つかりません: {style_path}")
        return ""
    stylesheet = load_stylesheet_local(f"{initial_theme}.qss")
    if stylesheet:
        app.setStyleSheet(stylesheet)

    window = ImageCleanerWindow()
    window.show()
    sys.exit(app.exec())
