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

# --- 新しいウィジェットとワーカーをインポート ---
try:
    from .widgets.preview_widget import PreviewWidget
    from .widgets.results_tabs_widget import ResultsTabsWidget
    from .workers import ScanWorker, WorkerSignals # WorkerSignalsも必要
    # 設定ダイアログ (dialogs ディレクトリに移動した場合)
    # from .dialogs.settings_dialog import SettingsDialog
    # settings_dialog.py が gui 直下にある場合
    from .settings_dialog import SettingsDialog
except ImportError as e:
    print(f"エラー: GUIコンポーネントのインポートに失敗しました ({e})。アプリケーションを起動できません。")
    sys.exit(1) # 致命的エラーとして終了

# --- ユーティリティ関数をインポート ---
try:
    from utils.config_handler import load_settings, save_settings
    from utils.file_operations import delete_files_to_trash, open_file_external
except ImportError as e:
    print(f"エラー: ユーティリティモジュールのインポートに失敗しました ({e})。")
    # ダミー関数を設定 (動作継続は難しい可能性がある)
    def load_settings(): return {}
    def save_settings(s): print("警告: 設定保存機能が無効です。"); return False
    def delete_files_to_trash(fps, p=None): print("警告: 削除機能が無効です。"); return 0, [], set()
    def open_file_external(fp, p=None): print("警告: ファイルを開く機能が無効です。")


class ImageCleanerWindow(QMainWindow):
    """アプリケーションのメインウィンドウクラス"""

    def __init__(self):
        """コンストラクタ"""
        super().__init__()
        self.setWindowTitle("画像クリーナー")
        self.setGeometry(100, 100, 1000, 750) # 初期ウィンドウサイズ

        self.threadpool = QThreadPool() # バックグラウンド処理用スレッドプール
        print(f"最大スレッド数: {self.threadpool.maxThreadCount()}") # デフォルトのスレッド数確認

        self.current_settings = load_settings() # 設定読み込み

        self._setup_ui()          # UI要素の作成と配置
        self._connect_signals()   # シグナルとスロットの接続

    def _setup_ui(self):
        """UIウィジェットの作成とレイアウト"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- フォルダ選択エリア ---
        input_layout = QHBoxLayout()
        self.dir_label = QLabel("対象フォルダ:")
        self.dir_path_edit = QLineEdit()
        self.dir_path_edit.setReadOnly(True)
        self.select_dir_button = QPushButton("フォルダを選択...")
        input_layout.addWidget(self.dir_label)
        input_layout.addWidget(self.dir_path_edit, 1)
        input_layout.addWidget(self.select_dir_button)
        main_layout.addLayout(input_layout)
        main_layout.addSpacing(5)

        # --- 設定ボタン ---
        settings_layout = QHBoxLayout()
        self.settings_button = QPushButton("設定...")
        settings_layout.addWidget(self.settings_button)
        settings_layout.addStretch()
        main_layout.addLayout(settings_layout)
        main_layout.addSpacing(10)

        # --- スキャン実行エリア ---
        proc_layout = QHBoxLayout()
        self.scan_button = QPushButton("スキャン開始")
        self.status_label = QLabel("ステータス: 待機中")
        self.status_label.setWordWrap(True)
        proc_layout.addWidget(self.scan_button)
        proc_layout.addWidget(self.status_label, 1)
        main_layout.addLayout(proc_layout)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.progress_bar)
        main_layout.addSpacing(10)

        # --- プレビューエリア (カスタムウィジェット) ---
        self.preview_widget = PreviewWidget()
        preview_frame = QFrame() # 見た目のためのフレーム (オプション)
        preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        preview_frame_layout = QVBoxLayout(preview_frame) # フレーム内にレイアウト
        preview_frame_layout.setContentsMargins(0,0,0,0)
        preview_frame_layout.addWidget(self.preview_widget)
        preview_frame.setFixedHeight(250) # 高さを固定
        main_layout.addWidget(preview_frame, stretch=0)
        main_layout.addSpacing(10)

        # --- 結果表示タブ (カスタムウィジェット) ---
        self.results_tabs_widget = ResultsTabsWidget()
        main_layout.addWidget(self.results_tabs_widget, stretch=1) # 可変サイズ
        main_layout.addSpacing(10)

        # --- アクションボタンエリア ---
        action_layout = QHBoxLayout()
        self.delete_button = QPushButton("選択した項目をゴミ箱へ移動")
        self.delete_button.setToolTip("ブレ画像タブ: チェックした項目 / 類似ペアタブ: 選択した行のファイル1")
        self.select_all_blurry_button = QPushButton("全選択(ブレ)")
        self.select_all_similar_button = QPushButton("全選択(類似ペア)")
        self.deselect_all_button = QPushButton("全選択解除")

        action_layout.addWidget(self.delete_button)
        action_layout.addStretch()
        action_layout.addWidget(self.select_all_blurry_button)
        action_layout.addWidget(self.select_all_similar_button)
        action_layout.addWidget(self.deselect_all_button)
        main_layout.addLayout(action_layout)

        # 初期状態では一部ボタンを無効化 (フォルダ選択後に有効化)
        self._set_scan_controls_enabled(False)
        self.delete_button.setEnabled(False)
        self.select_all_blurry_button.setEnabled(False)
        self.select_all_similar_button.setEnabled(False)
        self.deselect_all_button.setEnabled(False)

    def _connect_signals(self):
        """ウィジェット間のシグナルとスロットを接続"""
        # ボタンクリック
        self.select_dir_button.clicked.connect(self.select_directory)
        self.settings_button.clicked.connect(self.open_settings)
        self.scan_button.clicked.connect(self.start_scan)
        self.delete_button.clicked.connect(self.delete_selected_items)
        # 全選択/解除ボタンは ResultsTabsWidget のスロットに直接接続
        self.select_all_blurry_button.clicked.connect(self.results_tabs_widget.select_all_blurry)
        self.select_all_similar_button.clicked.connect(self.results_tabs_widget.select_all_similar)
        self.deselect_all_button.clicked.connect(self.results_tabs_widget.deselect_all)

        # 結果タブの選択変更 -> プレビュー更新
        self.results_tabs_widget.selection_changed.connect(self.update_preview_display)

        # プレビュークリック -> ファイル削除要求
        self.preview_widget.left_preview_clicked.connect(self._delete_single_file_from_preview)
        self.preview_widget.right_preview_clicked.connect(self._delete_single_file_from_preview)

    # --- スロット関数 ---
    @Slot()
    def select_directory(self):
        """フォルダ選択ボタンがクリックされたときの処理"""
        last_dir = self.current_settings.get('last_directory', os.path.expanduser("~"))
        dir_path = QFileDialog.getExistingDirectory(self, "フォルダを選択", last_dir)
        if dir_path:
            self.dir_path_edit.setText(dir_path)
            self.current_settings['last_directory'] = dir_path
            self.results_tabs_widget.clear_results() # 結果クリア
            self.preview_widget.clear_previews()   # プレビュークリア
            self.status_label.setText("ステータス: フォルダを選択しました。スキャンを開始してください。")
            self._set_scan_controls_enabled(True) # スキャンボタンなどを有効化
            self.delete_button.setEnabled(False) # 削除関連はスキャン後に有効化
            self.select_all_blurry_button.setEnabled(False)
            self.select_all_similar_button.setEnabled(False)
            self.deselect_all_button.setEnabled(False)

    @Slot()
    def open_settings(self):
        """設定ボタンがクリックされたときの処理"""
        # SettingsDialog が gui/dialogs にある場合
        # from .dialogs.settings_dialog import SettingsDialog
        # gui 直下にある場合
        # from .settings_dialog import SettingsDialog

        if SettingsDialog is None: # インポート失敗時のフォールバック
             QMessageBox.warning(self, "エラー", "設定ダイアログモジュールが見つかりません。")
             return

        dialog = SettingsDialog(self.current_settings, self)
        if dialog.exec():
            self.current_settings = dialog.get_settings()
            print("設定が更新されました:", self.current_settings)
        else:
            print("設定はキャンセルされました。")

    @Slot()
    def start_scan(self):
        """スキャン開始ボタンがクリックされたときの処理"""
        selected_dir = self.dir_path_edit.text()
        if not selected_dir or not os.path.isdir(selected_dir):
             QMessageBox.warning(self, "エラー", "有効なフォルダが選択されていません。")
             self.status_label.setText("ステータス: エラー (フォルダ未選択)")
             return

        # 結果とプレビューをクリア
        self.results_tabs_widget.clear_results()
        self.preview_widget.clear_previews()

        # UIをスキャン中状態に設定
        self.status_label.setText(f"ステータス: スキャン準備中... ({os.path.basename(selected_dir)})")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_scan_controls_enabled(False) # スキャン関連コントロールを無効化
        self.delete_button.setEnabled(False)
        self.select_all_blurry_button.setEnabled(False)
        self.select_all_similar_button.setEnabled(False)
        self.deselect_all_button.setEnabled(False)


        # ScanWorker インスタンスを作成し、シグナルを接続
        worker = ScanWorker(selected_dir, self.current_settings)
        worker.signals.status_update.connect(self.update_status)
        worker.signals.progress_update.connect(self.update_progress_bar)
        # 結果は ResultsTabsWidget のスロットに直接接続
        worker.signals.results_ready.connect(self.results_tabs_widget.populate_results)
        worker.signals.error.connect(self.scan_error) # 致命的エラー処理
        worker.signals.finished.connect(self.scan_finished) # 完了処理

        # スレッドプールでワーカーを実行
        self.threadpool.start(worker)

    @Slot(str)
    def update_status(self, message):
        """ステータスラベルを更新するスロット"""
        self.status_label.setText(f"ステータス: {message}")

    @Slot(int)
    def update_progress_bar(self, value):
        """プログレスバーを更新するスロット"""
        self.progress_bar.setValue(value)

    @Slot(str)
    def scan_error(self, message):
        """致命的なスキャンエラーが発生した場合のスロット"""
        print(f"致命的エラー受信: {message}")
        QMessageBox.critical(self, "スキャンエラー", f"処理中に致命的なエラーが発生しました:\n{message}")
        self.status_label.setText(f"ステータス: 致命的エラー ({message})")
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self._set_scan_controls_enabled(True) # スキャン関連コントロールを有効化
        # 削除関連ボタンは無効のまま or フォルダ選択状態に戻す

    @Slot()
    def scan_finished(self):
        """スキャンが完了したときのスロット"""
        print("スキャン完了シグナル受信")
        # エラータブの件数を取得してステータス表示
        error_count = self.results_tabs_widget.error_table.rowCount()
        if error_count > 0:
            self.status_label.setText(f"ステータス: スキャン完了 ({error_count}件のエラーあり)")
        else:
            self.status_label.setText("ステータス: スキャン完了")

        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self._set_scan_controls_enabled(True) # スキャン関連コントロールを有効化
        # 結果があれば削除関連ボタンも有効化
        if self.results_tabs_widget.blurry_table.rowCount() > 0 or \
           self.results_tabs_widget.similar_table.rowCount() > 0:
            self.delete_button.setEnabled(True)
            self.select_all_blurry_button.setEnabled(True)
            self.select_all_similar_button.setEnabled(True)
            self.deselect_all_button.setEnabled(True)


    @Slot()
    def update_preview_display(self):
        """結果タブの選択が変更されたときにプレビューウィジェットを更新するスロット"""
        # ResultsTabsWidget から現在の選択パスを取得
        primary_path, secondary_path = self.results_tabs_widget.get_current_selection_paths()
        # PreviewWidget のスロットを呼び出して更新
        self.preview_widget.update_previews(primary_path, secondary_path)

    @Slot()
    def delete_selected_items(self):
        """削除ボタンがクリックされたときの処理"""
        files_to_delete = []
        current_tab_index = self.results_tabs_widget.currentIndex()

        if current_tab_index == 0: # ブレ画像タブ
            files_to_delete = self.results_tabs_widget.get_selected_blurry_paths()
            if not files_to_delete:
                QMessageBox.information(self, "情報", "ブレ画像タブで削除する項目がチェックされていません。")
                return
        elif current_tab_index == 1: # 類似ペアタブ
            files_to_delete = self.results_tabs_widget.get_selected_similar_primary_paths()
            if not files_to_delete:
                 QMessageBox.information(self, "情報", "類似ペアタブで削除する行が選択されていません。")
                 return
        elif current_tab_index == 2: # エラータブ
             QMessageBox.information(self, "情報", "エラータブの項目は削除できません。")
             return
        else: return # 不明なタブ

        if not files_to_delete: return # 対象なし

        # ファイル削除処理を実行 (utils 関数呼び出し)
        deleted_count, errors, files_actually_deleted = delete_files_to_trash(files_to_delete, self)

        # 削除が成功した場合、テーブルとプレビューを更新
        if files_actually_deleted:
            # ResultsTabsWidget のメソッドを呼び出してテーブルから削除
            self.results_tabs_widget.remove_items_by_paths(files_actually_deleted)
            # プレビューもクリア (削除されたものが表示されている可能性があるため)
            self.preview_widget.clear_previews()
            # 削除後に結果がなくなったら削除ボタンなどを無効化
            if self.results_tabs_widget.blurry_table.rowCount() == 0 and \
               self.results_tabs_widget.similar_table.rowCount() == 0:
                self.delete_button.setEnabled(False)
                self.select_all_blurry_button.setEnabled(False)
                self.select_all_similar_button.setEnabled(False)
                self.deselect_all_button.setEnabled(False)


    @Slot(str)
    def _delete_single_file_from_preview(self, file_path):
        """プレビュークリックで単一ファイルを削除するスロット"""
        if not file_path: return
        # 確認ダイアログは delete_files_to_trash 内で表示
        deleted_count, errors, files_actually_deleted = delete_files_to_trash([file_path], self)
        if files_actually_deleted:
            self.results_tabs_widget.remove_items_by_paths(files_actually_deleted)
            self.preview_widget.clear_previews() # プレビュークリア
            # 削除後に結果がなくなったらボタン無効化
            if self.results_tabs_widget.blurry_table.rowCount() == 0 and \
               self.results_tabs_widget.similar_table.rowCount() == 0:
                self.delete_button.setEnabled(False)
                self.select_all_blurry_button.setEnabled(False)
                self.select_all_similar_button.setEnabled(False)
                self.deselect_all_button.setEnabled(False)


    # --- ヘルパーメソッド ---
    def _set_scan_controls_enabled(self, enabled: bool):
        """スキャン開始ボタンと設定ボタンの有効/無効を切り替える"""
        self.scan_button.setEnabled(enabled)
        self.settings_button.setEnabled(enabled)
        # フォルダ選択ボタンは常に有効でも良いかも
        # self.select_dir_button.setEnabled(enabled)

    # --- イベントハンドラ ---
    def closeEvent(self, event: QCloseEvent):
        """ウィンドウが閉じられるときのイベント"""
        # スレッドプールがアクティブな場合は警告を出すか、終了を待つ
        if self.threadpool.activeThreadCount() > 0:
             reply = QMessageBox.question(self, "確認",
                                          "スキャン処理が実行中です。終了しますか？",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                          QMessageBox.StandardButton.No)
             if reply == QMessageBox.StandardButton.No:
                 event.ignore() # 閉じるのをキャンセル
                 return
             else:
                 # 強制終了する場合、ワーカーに停止要求を出すなどの処理が必要になる場合がある
                 # ここでは単純に終了を許可
                 pass

        # 設定を保存
        if not save_settings(self.current_settings):
            print("警告: 設定ファイルの保存に失敗しました。")
        event.accept() # ウィンドウを閉じるのを許可

    def keyPressEvent(self, event: QKeyEvent):
        """キーボードショートカット処理"""
        key = event.key()
        # 現在表示中のプレビュー画像のパスを取得
        left_path = self.preview_widget.get_left_image_path()
        right_path = self.preview_widget.get_right_image_path()

        if key == Qt.Key.Key_Q:
            print("'Q' キー: 左プレビュー削除")
            self._delete_single_file_from_preview(left_path)
        elif key == Qt.Key.Key_W:
            print("'W' キー: 右プレビュー削除")
            self._delete_single_file_from_preview(right_path)
        elif key == Qt.Key.Key_A:
            print("'A' キー: 左プレビューを開く")
            if left_path: open_file_external(left_path, self)
        elif key == Qt.Key.Key_S:
            print("'S' キー: 右プレビューを開く")
            if right_path: open_file_external(right_path, self)
        else:
            super().keyPressEvent(event) # デフォルト処理


# --- アプリケーション起動 ---
# main.py で行うため、ここでは実行しない
# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     window = ImageCleanerWindow()
#     window.show()
#     sys.exit(app.exec())
