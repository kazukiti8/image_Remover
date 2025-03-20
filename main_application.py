import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QSplitter, QLabel, QPushButton, QTabWidget, QAction, QMenu, 
                           QToolBar, QStatusBar, QFileDialog, QMessageBox, QDockWidget)
from PyQt5.QtCore import Qt, QSize, QSettings, QTimer
from PyQt5.QtGui import QIcon

# 自作モジュールのインポート
from image_cleanup_system import ImageCleanupSystem
from thumbnail_view import ThumbnailGridView
from exif_display import ExifDisplay
from ai_quality_assessment import AIQualityAssessmentWidget
from batch_processor import BatchProcessWidget
from drag_drop_support import DragDropManager, DropArea
from image_zoom_widget import ZoomableImageWidget, MultiViewImageWidget
from settings_manager import SettingsManager, SettingsDialog



class MainApplication(QMainWindow):
    """画像クリーンアップシステムのメインアプリケーション"""
    
    def __init__(self):
        super().__init__()
        self.title = "画像クリーンアップシステム"
        self.directory = None
        self.cleanup_system = None
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.get_all()
        self.initUI()
        self.loadSettings()
        self.setup_drag_drop()
        
    def initUI(self):
        self.setWindowTitle(self.title)
        
        # ウィンドウサイズを設定
        width = self.settings['ui']['window_width']
        height = self.settings['ui']['window_height']
        self.resize(width, height)
        
        # メニューバーの設定
        self.create_menu_bar()
        
        # ツールバーの設定
        self.create_toolbar()
        
        # ステータスバーの設定
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("準備完了")
        
        # セントラルウィジェット
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # メインレイアウト
        main_layout = QVBoxLayout(self.central_widget)
        
        # 分割ウィジェット
        self.splitter = QSplitter(Qt.Horizontal)
        
        # 左側：サムネイルビュー
        self.thumbnail_view = ThumbnailGridView()
        self.thumbnail_view.item_selected.connect(self.on_thumbnail_selected)
        self.thumbnail_view.item_checkbox_toggled.connect(self.on_thumbnail_checkbox_toggled)
        self.splitter.addWidget(self.thumbnail_view)
        
        # 右側：詳細表示
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # プレビュー表示
        self.preview_widget = MultiViewImageWidget()
        right_layout.addWidget(self.preview_widget)
        
        # EXIF情報表示
        self.exif_display = ExifDisplay()
        
        # 詳細情報タブ
        self.detail_tabs = QTabWidget()
        self.detail_tabs.addTab(self.exif_display, "EXIF情報")
        
        # AI画質評価タブ
        self.quality_assessment = AIQualityAssessmentWidget()
        self.quality_assessment.assessment_complete.connect(self.on_quality_assessment_complete)
        self.detail_tabs.addTab(self.quality_assessment, "画質評価")
        
        right_layout.addWidget(self.detail_tabs)
        
        self.splitter.addWidget(right_widget)
        
        # スプリッターの初期サイズ比率を設定
        self.splitter.setSizes([width * 0.4, width * 0.6])
        
        main_layout.addWidget(self.splitter)
        
        # 操作ボタンエリア
        button_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("すべて選択")
        self.select_all_btn.clicked.connect(self.thumbnail_view.check_all)
        button_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("選択解除")
        self.deselect_all_btn.clicked.connect(self.thumbnail_view.uncheck_all)
        button_layout.addWidget(self.deselect_all_btn)
        
        button_layout.addStretch()
        
        self.delete_btn = QPushButton("選択した画像を削除")
        self.delete_btn.setStyleSheet("background-color: #ffaaaa;")
        self.delete_btn.clicked.connect(self.delete_selected_images)
        button_layout.addWidget(self.delete_btn)
        
        self.move_btn = QPushButton("選択した画像を移動...")
        self.move_btn.clicked.connect(self.move_selected_images)
        button_layout.addWidget(self.move_btn)
        
        main_layout.addLayout(button_layout)
        
        # ドックウィジェットの設定
        self.create_dock_widgets()
        
        # UI状態の初期化
        self.update_ui_state()
    
    def create_menu_bar(self):
        """メニューバーを作成"""
        menubar = self.menuBar()
        
        # ファイルメニュー
        file_menu = menubar.addMenu("ファイル")
        
        open_action = QAction("ディレクトリを開く...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_directory)
        file_menu.addAction(open_action)
        
        recent_menu = QMenu("最近使用したディレクトリ", self)
        file_menu.addMenu(recent_menu)
        
        file_menu.addSeparator()
        
        batch_action = QAction("バッチ処理...", self)
        batch_action.triggered.connect(self.show_batch_processor)
        file_menu.addAction(batch_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("終了", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 編集メニュー
        edit_menu = menubar.addMenu("編集")
        
        select_all_action = QAction("すべて選択", self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(self.thumbnail_view.check_all)
        edit_menu.addAction(select_all_action)
        
        deselect_all_action = QAction("選択解除", self)
        deselect_all_action.setShortcut("Ctrl+D")
        deselect_all_action.triggered.connect(self.thumbnail_view.uncheck_all)
        edit_menu.addAction(deselect_all_action)
        
        edit_menu.addSeparator()
        
        settings_action = QAction("設定...", self)
        settings_action.triggered.connect(self.show_settings)
        edit_menu.addAction(settings_action)
        
        # 表示メニュー
        view_menu = menubar.addMenu("表示")
        
        thumbnail_size_menu = QMenu("サムネイルサイズ", self)
        
        for size in [80, 120, 160, 200]:
            size_action = QAction(f"{size}px", self)
            size_action.setCheckable(True)
            if size == self.settings['ui']['thumbnail_size']:
                size_action.setChecked(True)
            size_action.triggered.connect(lambda checked, s=size: self.change_thumbnail_size(s))
            thumbnail_size_menu.addAction(size_action)
        
        view_menu.addMenu(thumbnail_size_menu)
        
        columns_menu = QMenu("列数", self)
        
        for cols in [2, 3, 4, 5, 6]:
            cols_action = QAction(f"{cols}列", self)
            cols_action.setCheckable(True)
            if cols == self.settings['ui']['grid_columns']:
                cols_action.setChecked(True)
            cols_action.triggered.connect(lambda checked, c=cols: self.change_grid_columns(c))
            columns_menu.addAction(cols_action)
        
        view_menu.addMenu(columns_menu)
        
        view_menu.addSeparator()
        
        self.show_exif_action = QAction("EXIF情報の表示", self)
        self.show_exif_action.setCheckable(True)
        self.show_exif_action.setChecked(self.settings['ui']['show_exif'])
        self.show_exif_action.triggered.connect(self.toggle_exif_display)
        view_menu.addAction(self.show_exif_action)
        
        # 検出メニュー
        detect_menu = menubar.addMenu("検出")
        
        detect_blurry_action = QAction("ブレている画像を検出", self)
        detect_blurry_action.triggered.connect(self.detect_blurry_images)
        detect_menu.addAction(detect_blurry_action)
        
        detect_similar_action = QAction("類似画像を検出", self)
        detect_similar_action.triggered.connect(self.detect_similar_images)
        detect_menu.addAction(detect_similar_action)
        
        detect_duplicate_action = QAction("重複画像を検出", self)
        detect_duplicate_action.triggered.connect(self.detect_duplicate_images)
        detect_menu.addAction(detect_duplicate_action)
        
        detect_menu.addSeparator()
        
        detect_all_action = QAction("全ての検出を実行", self)
        detect_all_action.triggered.connect(self.detect_all)
        detect_menu.addAction(detect_all_action)
        
        # 評価メニュー
        assessment_menu = menubar.addMenu("評価")
        
        assess_quality_action = QAction("画質評価を実行", self)
        assess_quality_action.triggered.connect(self.assess_image_quality)
        assessment_menu.addAction(assess_quality_action)
        
        # ヘルプメニュー
        help_menu = menubar.addMenu("ヘルプ")
        
        about_action = QAction("バージョン情報...", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        help_action = QAction("ヘルプ...", self)
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)
    
    def create_toolbar(self):
        """ツールバーを作成"""
        self.toolbar = QToolBar("メインツールバー")
        self.toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(self.toolbar)
        
        # ディレクトリを開くボタン
        open_action = QAction("開く", self)
        open_action.triggered.connect(self.open_directory)
        self.toolbar.addAction(open_action)
        
        self.toolbar.addSeparator()
        
        # 検出ボタン
        detect_blurry_action = QAction("ブレ検出", self)
        detect_blurry_action.triggered.connect(self.detect_blurry_images)
        self.toolbar.addAction(detect_blurry_action)
        
        detect_similar_action = QAction("類似検出", self)
        detect_similar_action.triggered.connect(self.detect_similar_images)
        self.toolbar.addAction(detect_similar_action)
        
        detect_duplicate_action = QAction("重複検出", self)
        detect_duplicate_action.triggered.connect(self.detect_duplicate_images)
        self.toolbar.addAction(detect_duplicate_action)
        
        self.toolbar.addSeparator()
        
        # 画質評価ボタン
        assess_action = QAction("画質評価", self)
        assess_action.triggered.connect(self.assess_image_quality)
        self.toolbar.addAction(assess_action)
        
        self.toolbar.addSeparator()
        
        # 設定ボタン
        settings_action = QAction("設定", self)
        settings_action.triggered.connect(self.show_settings)
        self.toolbar.addAction(settings_action)
    
    def create_dock_widgets(self):
        """ドックウィジェットを作成"""
        # バッチ処理ドック
        self.batch_dock = QDockWidget("バッチ処理", self)
        self.batch_dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable)
        self.batch_processor = BatchProcessWidget()
        self.batch_dock.setWidget(self.batch_processor)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.batch_dock)
        self.batch_dock.hide()
    
    def setup_drag_drop(self):
        """ドラッグ&ドロップのサポートをセットアップ"""
        def handle_drop(items, item_type):
            if item_type == 'directories' and items:
                self.open_directory(items[0])
        
        # メインウィンドウにドラッグ&ドロップサポートを追加
        DragDropManager.add_drag_drop_support(
            self.central_widget,
            handle_drop,
            accept_files=False,
            accept_dirs=True
        )
    
    def loadSettings(self):
        """設定を読み込み、UI状態を更新"""
        # 最後に使用したディレクトリ
        last_dir = self.settings['general']['last_directory']
        if last_dir and os.path.exists(last_dir):
            self.directory = last_dir
        
        # サムネイルサイズと列数
        self.thumbnail_view.thumbnail_size = self.settings['ui']['thumbnail_size']
        self.thumbnail_view.columns = self.settings['ui']['grid_columns']
        
        # EXIFの表示/非表示
        if not self.settings['ui']['show_exif']:
            self.detail_tabs.removeTab(self.detail_tabs.indexOf(self.exif_display))
    
    def saveSettings(self):
        """設定を保存"""
        # ウィンドウサイズを保存
        self.settings['ui']['window_width'] = self.width()
        self.settings['ui']['window_height'] = self.height()
        
        # 最後に使用したディレクトリを保存
        if self.directory:
            self.settings['general']['last_directory'] = self.directory
        
        # 設定を保存
        self.settings_manager.save_settings()
    
    def update_ui_state(self):
        """UI状態を更新"""
        has_directory = self.directory is not None
        
        # 操作ボタンの有効/無効
        self.select_all_btn.setEnabled(has_directory)
        self.deselect_all_btn.setEnabled(has_directory)
        self.delete_btn.setEnabled(has_directory)
        self.move_btn.setEnabled(has_directory)
    
    def open_directory(self, directory=None):
        """ディレクトリを開く"""
        if directory is None or not isinstance(directory, str):
            # ディレクトリ選択ダイアログを表示
            dir_path = QFileDialog.getExistingDirectory(self, "処理するディレクトリを選択")
            if not dir_path:
                return
        else:
            dir_path = directory
        
        self.directory = dir_path
        self.setWindowTitle(f"{self.title} - {os.path.basename(dir_path)}")
        
        # クリーンアップシステムを初期化
        self.cleanup_system = ImageCleanupSystem(
            self.directory,
            None,
            self.settings['cleanup']['similarity_threshold']
        )
        
        # 画像ファイルを取得
        image_files = self.cleanup_system.get_image_files()
        
        # サムネイルビューに表示
        self.thumbnail_view.set_images([str(path) for path in image_files])
        
        # 最後に使用したディレクトリを更新
        self.settings['general']['last_directory'] = self.directory
        self.settings_manager.save_settings()
        
        # UI状態を更新
        self.update_ui_state()
        
        # ステータスバーを更新
        self.statusBar.showMessage(f"{len(image_files)}枚の画像を読み込みました")
    
    def detect_blurry_images(self):
        """ブレている画像を検出"""
        if not self.cleanup_system:
            self.show_no_directory_message()
            return
        
        self.statusBar.showMessage("ブレている画像を検出中...")
        QApplication.processEvents()
        
        # ブレ検出を実行
        threshold = self.settings['cleanup']['blur_threshold']
        blurry_images = self.cleanup_system.detect_blurry_images(threshold)
        
        # 結果表示
        self.show_detection_results("ブレている画像", blurry_images)
    
    def detect_similar_images(self):
        """類似画像を検出"""
        if not self.cleanup_system:
            self.show_no_directory_message()
            return
        
        self.statusBar.showMessage("類似画像を検出中...")
        QApplication.processEvents()
        
        # 類似画像検出を実行
        similar_pairs = self.cleanup_system.detect_similar_images()
        
        # 結果表示
        self.show_detection_results("類似画像", [pair[1] for pair in similar_pairs])
    
    def detect_duplicate_images(self):
        """重複画像を検出"""
        if not self.cleanup_system:
            self.show_no_directory_message()
            return
        
        self.statusBar.showMessage("重複画像を検出中...")
        QApplication.processEvents()
        
        # 重複画像検出を実行
        duplicate_pairs = self.cleanup_system.detect_duplicate_images()
        
        # 結果表示
        self.show_detection_results("重複画像", [pair[1] for pair in duplicate_pairs])
    
    def detect_all(self):
        """全ての検出を実行"""
        if not self.cleanup_system:
            self.show_no_directory_message()
            return
        
        self.statusBar.showMessage("全ての検出を実行中...")
        QApplication.processEvents()
        
        # 全ての検出を実行
        results = self.cleanup_system.process_directory()
        
        # 検出された全ての画像のリストを作成
        all_detected = []
        
        # ブレている画像
        all_detected.extend(results['blurry'])
        
        # 類似画像
        for ref_img, similar_img in results['similar']:
            all_detected.append(similar_img)
        
        # 重複画像
        for ref_img, duplicate_img in results['duplicate']:
            all_detected.append(duplicate_img)
        
        # 結果表示
        self.show_detection_results("全ての検出", all_detected)
    
    def assess_image_quality(self):
        """画質評価を実行"""
        if not self.cleanup_system:
            self.show_no_directory_message()
            return
        
        # 画像ファイルを取得
        image_files = [str(path) for path in self.cleanup_system.get_image_files()]
        
        # 画質評価タブを選択
        self.detail_tabs.setCurrentWidget(self.quality_assessment)
        
        # 画質評価を開始
        self.quality_assessment.start_assessment(image_files)
    
    def on_quality_assessment_complete(self, results):
        """画質評価完了時の処理"""
        # 結果に基づいて低品質の画像を選択する
        low_quality_images = []
        
        for path, result in results.items():
            if 'overall_score' in result and result['overall_score'] < 5.0:
                low_quality_images.append(path)
        
        # 結果表示
        if low_quality_images:
            self.show_detection_results("低品質画像", low_quality_images)
        else:
            QMessageBox.information(
                self,
                "画質評価完了",
                "低品質の画像は見つかりませんでした。"
            )
    
    def on_thumbnail_selected(self, image_path):
        """サムネイルが選択された時の処理"""
        # プレビューに表示
        self.preview_widget.set_images([image_path])
        
        # EXIF情報を表示
        if self.settings['ui']['show_exif']:
            self.exif_display.load_exif(image_path)
        
        # 画質評価結果を表示（既に評価済みの場合）
        if hasattr(self.quality_assessment, 'get_results'):
            results = self.quality_assessment.get_results()
            if image_path in results:
                self.quality_assessment.display_result(image_path)
    
    def on_thumbnail_checkbox_toggled(self, image_path, checked):
        """サムネイルのチェックボックスがトグルされた時の処理"""
        # 選択された画像の数に応じて削除/移動ボタンの表示を更新
        checked_items = self.thumbnail_view.get_checked_items()
        self.delete_btn.setText(f"選択した画像を削除 ({len(checked_items)})")
        self.move_btn.setText(f"選択した画像を移動... ({len(checked_items)})")
        
        self.delete_btn.setEnabled(len(checked_items) > 0)
        self.move_btn.setEnabled(len(checked_items) > 0)
    
    def show_detection_results(self, detection_type, detected_images):
        """検出結果を表示"""
        total = len(detected_images)
        
        if total > 0:
            reply = QMessageBox.question(
                self,
                f"{detection_type}の検出完了",
                f"{total}枚の{detection_type}が検出されました。\n\n検出された画像を選択状態にしますか？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                # 既存の選択をクリア
                self.thumbnail_view.uncheck_all()
                
                # 検出された画像を選択
                for image_path in detected_images:
                    path_str = str(image_path)
                    for i in range(self.thumbnail_view.grid_layout.count()):
                        item = self.thumbnail_view.grid_layout.itemAt(i).widget()
                        if item and hasattr(item, 'image_path') and item.image_path == path_str:
                            item.set_checked(True)
            
            self.statusBar.showMessage(f"{total}枚の{detection_type}が検出されました")
        else:
            QMessageBox.information(
                self,
                f"{detection_type}の検出完了",
                f"{detection_type}は見つかりませんでした。"
            )
            
            self.statusBar.showMessage(f"{detection_type}は見つかりませんでした")
    
    def delete_selected_images(self):
        """選択した画像を削除"""
        checked_items = self.thumbnail_view.get_checked_items()
        total = len(checked_items)
        
        if total == 0:
            return
        
        # 確認ダイアログ
        if self.settings['general']['confirm_deletes']:
            reply = QMessageBox.question(
                self,
                "確認",
                f"選択した {total} 枚の画像を削除しますか？\nこの操作は元に戻せません。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
        
        # 削除処理
        deleted_count = 0
        failed_count = 0
        
        for img_path in checked_items:
            try:
                os.remove(img_path)
                deleted_count += 1
            except Exception as e:
                print(f"削除エラー: {e}")
                failed_count += 1
        
        # サムネイルビューを更新
        self.thumbnail_view.set_images([p for p in self.thumbnail_view.get_checked_items() if os.path.exists(p)])
        
        # 結果を表示
        if failed_count > 0:
            QMessageBox.warning(
                self,
                "処理完了",
                f"{deleted_count} 枚の画像を削除しました。\n{failed_count} 枚の画像は削除できませんでした。"
            )
        else:
            QMessageBox.information(
                self,
                "処理完了",
                f"{deleted_count} 枚の画像を削除しました。"
            )
        
        self.statusBar.showMessage(f"{deleted_count} 枚の画像を削除しました")
    
    def move_selected_images(self):
        """選択した画像を移動"""
        checked_items = self.thumbnail_view.get_checked_items()
        total = len(checked_items)
        
        if total == 0:
            return
        
        # 移動先ディレクトリを選択
        dest_dir = QFileDialog.getExistingDirectory(self, "移動先ディレクトリを選択")
        if not dest_dir:
            return
        
        # 移動処理
        moved_count = 0
        failed_count = 0
        
        import shutil
        import time
        
        for img_path in checked_items:
            try:
                filename = os.path.basename(img_path)
                dest_path = os.path.join(dest_dir, filename)
                
                # 同名ファイルがある場合はリネーム
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(filename)
                    dest_path = os.path.join(dest_dir, f"{base}_{int(time.time())}{ext}")
                
                shutil.move(img_path, dest_path)
                moved_count += 1
            except Exception as e:
                print(f"移動エラー: {e}")
                failed_count += 1
        
        # サムネイルビューを更新
        self.thumbnail_view.set_images([p for p in self.thumbnail_view.get_checked_items() if os.path.exists(p)])
        
        # 結果を表示
        if failed_count > 0:
            QMessageBox.warning(
                self,
                "処理完了",
                f"{moved_count} 枚の画像を移動しました。\n{failed_count} 枚の画像は移動できませんでした。"
            )
        else:
            QMessageBox.information(
                self,
                "処理完了",
                f"{moved_count} 枚の画像を移動しました。"
            )
        
        self.statusBar.showMessage(f"{moved_count} 枚の画像を移動しました")
    
    def show_no_directory_message(self):
        """ディレクトリが選択されていない場合のメッセージを表示"""
        QMessageBox.warning(
            self,
            "ディレクトリが必要",
            "処理を開始するにはディレクトリを選択してください。"
        )
    
    def show_about(self):
        """バージョン情報ダイアログを表示"""
        QMessageBox.about(
            self,
            "バージョン情報",
            f"画像クリーンアップシステム v1.0\n\n"
            f"作成者: ClaudeAI\n"
            f"© 2025 All rights reserved.\n\n"
            f"このアプリケーションは、ブレている画像、類似画像、重複画像を検出して整理するためのツールです。"
        )
    
    def show_help(self):
        """ヘルプダイアログを表示"""
        QMessageBox.about(
            self,
            "ヘルプ",
            "使用方法:\n\n"
            "1. 「ファイル」メニューから「ディレクトリを開く」を選択して処理対象のフォルダを選択します。\n"
            "2. 「検出」メニューから検出したい項目を選択します。\n"
            "   - ブレている画像を検出\n"
            "   - 類似画像を検出\n"
            "   - 重複画像を検出\n"
            "3. 検出された画像のサムネイルが表示されます。\n"
            "4. 画像をクリックすると詳細を確認できます。\n"
            "5. 削除したい画像にチェックを入れて「選択した画像を削除」ボタンをクリックします。\n\n"
            "詳細な操作方法については、[ここに詳細ドキュメントへのリンクを入れる]を参照してください。"
        )
    
    def show_settings(self):
        """設定ダイアログを表示"""
        dialog = SettingsDialog(self.settings_manager, self)
        if dialog.exec_() == dialog.Accepted:
            # 設定が更新された場合、UIを更新
            self.settings = self.settings_manager.get_all()
            self.update_settings_ui()
    
    def update_settings_ui(self):
        """設定の変更を反映してUIを更新"""
        # サムネイルサイズと列数を更新
        if self.thumbnail_view.thumbnail_size != self.settings['ui']['thumbnail_size'] or \
           self.thumbnail_view.columns != self.settings['ui']['grid_columns']:
            self.thumbnail_view.thumbnail_size = self.settings['ui']['thumbnail_size']
            self.thumbnail_view.columns = self.settings['ui']['grid_columns']
            
            # 現在の画像パスを保存
            current_images = []
            for i in range(self.thumbnail_view.grid_layout.count()):
                item = self.thumbnail_view.grid_layout.itemAt(i).widget()
                if item and hasattr(item, 'image_path'):
                    current_images.append(item.image_path)
            
            # サムネイルを再読み込み
            if current_images:
                self.thumbnail_view.set_images(current_images)
        
        # EXIF表示の更新
        self.show_exif_action.setChecked(self.settings['ui']['show_exif'])
        self.toggle_exif_display()
    
    def change_thumbnail_size(self, size):
        """サムネイルサイズを変更"""
        self.settings['ui']['thumbnail_size'] = size
        self.settings_manager.save_settings()
        self.update_settings_ui()
    
    def change_grid_columns(self, columns):
        """グリッド列数を変更"""
        self.settings['ui']['grid_columns'] = columns
        self.settings_manager.save_settings()
        self.update_settings_ui()
    
    def toggle_exif_display(self):
        """EXIF情報表示の切り替え"""
        show_exif = self.show_exif_action.isChecked()
        self.settings['ui']['show_exif'] = show_exif
        
        # タブの有無を更新
        exif_tab_index = self.detail_tabs.indexOf(self.exif_display)
        
        if show_exif and exif_tab_index == -1:
            # EXIFタブを追加
            self.detail_tabs.insertTab(0, self.exif_display, "EXIF情報")
            self.detail_tabs.setCurrentIndex(0)
        elif not show_exif and exif_tab_index != -1:
            # EXIFタブを削除
            self.detail_tabs.removeTab(exif_tab_index)
        
        self.settings_manager.save_settings()
    
    def show_batch_processor(self):
        """バッチ処理ドックを表示"""
        self.batch_dock.show()
    
    def closeEvent(self, event):
        """アプリケーションが閉じる前の処理"""
        # 設定を保存
        self.saveSettings()
        event.accept()


def main():
    """メイン関数"""
    app = QApplication(sys.argv)
    window = MainApplication()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
