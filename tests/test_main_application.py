import unittest
import os
import tempfile
import shutil
from unittest.mock import MagicMock, patch

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox, QDialog

# メインアプリケーションのインポート
from main_application import MainApplication


class TestMainApplication(unittest.TestCase):
    """MainApplicationクラスのテスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        # QApplicationを初期化
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()
        
        # 設定マネージャーをモック化
        self.settings_patcher = patch('main_application.SettingsManager')
        self.mock_settings_manager = self.settings_patcher.start()
        
        # モックの設定マネージャーの設定
        self.mock_settings_instance = MagicMock()
        self.mock_settings_instance.get_all.return_value = {
            "general": {
                "last_directory": "",
                "auto_fit_preview": True,
                "theme": "system",
                "language": "ja",
                "confirm_deletes": True
            },
            "cleanup": {
                "blur_threshold": 100.0,
                "similarity_threshold": 10,
                "duplicate_check_enabled": True,
                "similar_check_enabled": True,
                "blur_check_enabled": True
            },
            "quality": {
                "exposure_weight": 1.0,
                "contrast_weight": 1.0,
                "noise_weight": 1.0,
                "composition_weight": 1.0,
                "sharpness_weight": 1.5
            },
            "ui": {
                "thumbnail_size": 120,
                "grid_columns": 4,
                "show_exif": True,
                "show_preview": True,
                "window_width": 1200,
                "window_height": 800
            }
        }
        self.mock_settings_manager.return_value = self.mock_settings_instance
        
        # テスト用のインスタンスを作成
        self.main_app = MainApplication()
        
        # テスト用の一時ディレクトリを作成
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """テスト後のクリーンアップ"""
        self.settings_patcher.stop()
        self.main_app.close()
        
        # テスト用ディレクトリを削除
        if hasattr(self, 'test_dir') and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_init(self):
        """初期化のテスト"""
        self.assertEqual(self.main_app.title, "画像クリーンアップシステム")
        self.assertIsNone(self.main_app.directory)
        self.assertIsNone(self.main_app.cleanup_system)
        self.assertEqual(self.main_app.settings_manager, self.mock_settings_instance)
        self.assertEqual(self.main_app.settings, self.mock_settings_instance.get_all())

    def test_create_menu_bar(self):
        """メニューバー作成のテスト"""
        # メニューバーが作成されたことを確認
        menubar = self.main_app.menuBar()
        self.assertIsNotNone(menubar)
        
        # 主要なメニューが存在するか
        menus = [menubar.actions()[i].text() for i in range(menubar.actions().count())]
        self.assertIn("ファイル", menus)
        self.assertIn("編集", menus)
        self.assertIn("表示", menus)
        self.assertIn("検出", menus)
        self.assertIn("評価", menus)
        self.assertIn("ヘルプ", menus)

    def test_create_toolbar(self):
        """ツールバー作成のテスト"""
        # ツールバーが作成されたことを確認
        self.assertIsNotNone(self.main_app.toolbar)
        
        # ツールバーのアクションが存在するか
        actions = [self.main_app.toolbar.actions()[i].text() for i in range(self.main_app.toolbar.actions().count())]
        self.assertIn("開く", actions)
        self.assertIn("ブレ検出", actions)
        self.assertIn("類似検出", actions)
        self.assertIn("重複検出", actions)
        self.assertIn("画質評価", actions)
        self.assertIn("設定", actions)

    def test_update_ui_state(self):
        """UI状態更新のテスト"""
        # ディレクトリがない場合
        self.main_app.directory = None
        self.main_app.update_ui_state()
        
        # 操作ボタンが無効になっているか
        self.assertFalse(self.main_app.select_all_btn.isEnabled())
        self.assertFalse(self.main_app.deselect_all_btn.isEnabled())
        self.assertFalse(self.main_app.delete_btn.isEnabled())
        self.assertFalse(self.main_app.move_btn.isEnabled())
        
        # ディレクトリがある場合
        self.main_app.directory = self.test_dir
        self.main_app.update_ui_state()
        
        # 操作ボタンが有効になっているか
        self.assertTrue(self.main_app.select_all_btn.isEnabled())
        self.assertTrue(self.main_app.deselect_all_btn.isEnabled())
        self.assertTrue(self.main_app.delete_btn.isEnabled())
        self.assertTrue(self.main_app.move_btn.isEnabled())

    @patch('main_application.QFileDialog.getExistingDirectory')
    @patch('main_application.ImageCleanupSystem')
    def test_open_directory(self, mock_cleanup_system, mock_get_dir):
        """ディレクトリを開くテスト"""
        # ダイアログの戻り値を設定
        mock_get_dir.return_value = self.test_dir
        
        # ImageCleanupSystemのモック設定
        mock_instance = MagicMock()
        mock_instance.get_image_files.return_value = ["/fake/path/image1.jpg", "/fake/path/image2.png"]
        mock_cleanup_system.return_value = mock_instance
        
        # ディレクトリを開く
        self.main_app.open_directory()
        
        # ダイアログが表示されたことを確認
        mock_get_dir.assert_called_once()
        
        # ImageCleanupSystemが作成されたことを確認
        mock_cleanup_system.assert_called_once_with(
            self.test_dir,
            None,
            self.main_app.settings['cleanup']['similarity_threshold']
        )
        
        # ディレクトリが設定されたことを確認
        self.assertEqual(self.main_app.directory, self.test_dir)
        
        # 画像ファイルが取得されたことを確認
        mock_instance.get_image_files.assert_called_once()
        
        # サムネイルビューに画像が設定されたことを確認
        self.main_app.thumbnail_view.set_images.assert_called_once()
        
        # 設定が更新されたことを確認
        self.assertEqual(self.main_app.settings['general']['last_directory'], self.test_dir)
        self.mock_settings_instance.save_settings.assert_called_once()

    @patch('main_application.QMessageBox')
    def test_show_no_directory_message(self, mock_message_box):
        """ディレクトリ未選択メッセージのテスト"""
        # メッセージボックスのインスタンスを作成
        mock_instance = MagicMock()
        mock_message_box.warning.return_value = mock_instance
        
        # メッセージを表示
        self.main_app.show_no_directory_message()
        
        # 警告メッセージが表示されたことを確認
        mock_message_box.warning.assert_called_once()
        
        # 警告メッセージの内容を確認
        args, _ = mock_message_box.warning.call_args
        self.assertIn("ディレクトリが必要", args[1])

    @patch('main_application.QMessageBox')
    @patch('main_application.QFileDialog.getExistingDirectory')
    @patch('os.path.exists')
    @patch('os.remove')
    def test_delete_selected_images(self, mock_remove, mock_exists, mock_get_dir, mock_message_box):
        """選択画像の削除テスト"""
        # 確認メッセージボックスの戻り値を設定
        mock_message_box.question.return_value = QMessageBox.Yes
        
        # 画像のパスをモック化
        mock_exists.return_value = True
        image_paths = [
            "/fake/path/image1.jpg",
            "/fake/path/image2.png",
            "/fake/path/image3.gif"
        ]
        
        # サムネイルビューの選択画像を設定
        self.main_app.thumbnail_view.get_checked_items = MagicMock(return_value=image_paths)
        
        # 削除を実行
        self.main_app.delete_selected_images()
        
        # 確認メッセージが表示されたことを確認
        mock_message_box.question.assert_called_once()
        
        # 各画像が削除されたことを確認
        self.assertEqual(mock_remove.call_count, len(image_paths))
        for i, path in enumerate(image_paths):
            mock_remove.assert_any_call(path)
        
        # 削除完了メッセージが表示されたことを確認
        mock_message_box.information.assert_called_once()

    @patch('main_application.QMessageBox')
    @patch('main_application.QFileDialog.getExistingDirectory')
    @patch('os.path.exists')
    @patch('shutil.move')
    def test_move_selected_images(self, mock_move, mock_exists, mock_get_dir, mock_message_box):
        """選択画像の移動テスト"""
        # 移動先ディレクトリのダイアログの戻り値を設定
        dest_dir = os.path.join(self.test_dir, "dest")
        mock_get_dir.return_value = dest_dir
        
        # 画像のパスをモック化
        mock_exists.return_value = False  # 同名ファイルは存在しない
        image_paths = [
            "/fake/path/image1.jpg",
            "/fake/path/image2.png",
            "/fake/path/image3.gif"
        ]
        
        # サムネイルビューの選択画像を設定
        self.main_app.thumbnail_view.get_checked_items = MagicMock(return_value=image_paths)
        
        # 移動を実行
        self.main_app.move_selected_images()
        
        # 移動先選択ダイアログが表示されたことを確認
        mock_get_dir.assert_called_once()
        
        # 各画像が移動されたことを確認
        self.assertEqual(mock_move.call_count, len(image_paths))
        for i, path in enumerate(image_paths):
            mock_move.assert_any_call(path, os.path.join(dest_dir, os.path.basename(path)))
        
        # 移動完了メッセージが表示されたことを確認
        mock_message_box.information.assert_called_once()

    @patch('main_application.ImageCleanupSystem')
    def test_detect_blurry_images(self, mock_cleanup_system):
        """ブレ画像検出のテスト"""
        # クリーンアップシステムを設定
        mock_instance = MagicMock()
        blurry_images = ["/fake/path/blurry1.jpg", "/fake/path/blurry2.png"]
        mock_instance.detect_blurry_images.return_value = blurry_images
        self.main_app.cleanup_system = mock_instance
        
        # 検出結果表示関数をモック化
        self.main_app.show_detection_results = MagicMock()
        
        # ブレ画像検出を実行
        self.main_app.detect_blurry_images()
        
        # クリーンアップシステムのメソッドが呼ばれたことを確認
        mock_instance.detect_blurry_images.assert_called_once_with(
            self.main_app.settings['cleanup']['blur_threshold']
        )
        
        # 検出結果が表示されたことを確認
        self.main_app.show_detection_results.assert_called_once_with("ブレている画像", blurry_images)

    @patch('main_application.ImageCleanupSystem')
    def test_detect_similar_images(self, mock_cleanup_system):
        """類似画像検出のテスト"""
        # クリーンアップシステムを設定
        mock_instance = MagicMock()
        similar_pairs = [
            ("/fake/path/ref1.jpg", "/fake/path/similar1.jpg"),
            ("/fake/path/ref2.png", "/fake/path/similar2.png")
        ]
        mock_instance.detect_similar_images.return_value = similar_pairs
        self.main_app.cleanup_system = mock_instance
        
        # 検出結果表示関数をモック化
        self.main_app.show_detection_results = MagicMock()
        
        # 類似画像検出を実行
        self.main_app.detect_similar_images()
        
        # クリーンアップシステムのメソッドが呼ばれたことを確認
        mock_instance.detect_similar_images.assert_called_once()
        
        # 検出結果が表示されたことを確認
        self.main_app.show_detection_results.assert_called_once_with(
            "類似画像", 
            [pair[1] for pair in similar_pairs]
        )

    @patch('main_application.QMessageBox')
    def test_show_detection_results_with_items(self, mock_message_box):
        """検出結果表示のテスト（検出あり）"""
        # メッセージボックスの戻り値を設定
        mock_message_box.question.return_value = QMessageBox.Yes
        
        # サムネイルビューをモック化
        self.main_app.thumbnail_view.uncheck_all = MagicMock()
        
        # 検出結果と検出タイプ
        detection_type = "テスト検出"
        detected_images = ["/fake/path/detected1.jpg", "/fake/path/detected2.png"]
        
        # 検出結果を表示
        self.main_app.show_detection_results(detection_type, detected_images)
        
        # 確認メッセージが表示されたことを確認
        mock_message_box.question.assert_called_once()
        
        # 選択状態がクリアされたことを確認
        self.main_app.thumbnail_view.uncheck_all.assert_called_once()

    @patch('main_application.QMessageBox')
    def test_show_detection_results_without_items(self, mock_message_box):
        """検出結果表示のテスト（検出なし）"""
        # 検出結果と検出タイプ
        detection_type = "テスト検出"
        detected_images = []
        
        # 検出結果を表示
        self.main_app.show_detection_results(detection_type, detected_images)
        
        # 情報メッセージが表示されたことを確認
        mock_message_box.information.assert_called_once()
        
        # メッセージの内容を確認
        args, _ = mock_message_box.information.call_args
        self.assertEqual(args[1], f"{detection_type}の検出完了")
        self.assertIn("見つかりませんでした", args[2])

    @patch('main_application.SettingsDialog')
    def test_show_settings(self, mock_dialog):
        """設定ダイアログ表示のテスト"""
        # ダイアログの戻り値を設定
        mock_instance = MagicMock()
        mock_instance.exec_.return_value = QDialog.Accepted
        mock_dialog.return_value = mock_instance
        
        # 設定ダイアログを表示
        self.main_app.show_settings()
        
        # ダイアログが作成されたことを確認
        mock_dialog.assert_called_once_with(self.main_app.settings_manager, self.main_app)
        
        # ダイアログが表示されたことを確認
        mock_instance.exec_.assert_called_once()
        
        # 設定が更新されたことを確認
        self.assertEqual(self.main_app.settings, self.mock_settings_instance.get_all())

    @patch('main_application.QMessageBox')
    def test_show_about(self, mock_message_box):
        """バージョン情報ダイアログ表示のテスト"""
        # about関数をモック化
        mock_message_box.about = MagicMock()
        
        # バージョン情報を表示
        self.main_app.show_about()
        
        # aboutが呼ばれたことを確認
        mock_message_box.about.assert_called_once()
        
        # メッセージの内容を確認
        args, _ = mock_message_box.about.call_args
        self.assertEqual(args[1], "バージョン情報")
        self.assertIn("画像クリーンアップシステム", args[2])

    @patch('main_application.QMessageBox')
    def test_show_help(self, mock_message_box):
        """ヘルプダイアログ表示のテスト"""
        # about関数をモック化
        mock_message_box.about = MagicMock()
        
        # ヘルプを表示
        self.main_app.show_help()
        
        # aboutが呼ばれたことを確認
        mock_message_box.about.assert_called_once()
        
        # メッセージの内容を確認
        args, _ = mock_message_box.about.call_args
        self.assertEqual(args[1], "ヘルプ")
        self.assertIn("使用方法", args[2])

    def test_on_thumbnail_selected(self):
        """サムネイル選択時の処理テスト"""
        # 選択された画像パス
        image_path = "/fake/path/selected.jpg"
        
        # サムネイル選択を処理
        self.main_app.on_thumbnail_selected(image_path)
        
        # プレビューに表示されたことを確認
        self.main_app.preview_widget.set_images.assert_called_once_with([image_path])
        
        # EXIF情報が表示されたことを確認（show_exifがTrueの場合）
        if self.main_app.settings['ui']['show_exif']:
            self.main_app.exif_display.load_exif.assert_called_once_with(image_path)

    def test_toggle_exif_display(self):
        """EXIF表示切替のテスト"""
        # show_exifをTrue/Falseで切り替え
        original_value = self.main_app.settings['ui']['show_exif']
        self.main_app.show_exif_action.setChecked(not original_value)
        
        # トグル処理を実行
        self.main_app.toggle_exif_display()
        
        # 設定が更新されたことを確認
        self.assertEqual(self.main_app.settings['ui']['show_exif'], not original_value)
        
        # 設定が保存されたことを確認
        self.mock_settings_instance.save_settings.assert_called()

    def test_saveSettings(self):
        """設定保存のテスト"""
        # ウィンドウサイズを変更
        self.main_app.resize(1000, 700)
        
        # ディレクトリを設定
        self.main_app.directory = self.test_dir
        
        # 設定を保存
        self.main_app.saveSettings()
        
        # ウィンドウサイズが保存されたことを確認
        self.assertEqual(self.main_app.settings['ui']['window_width'], 1000)
        self.assertEqual(self.main_app.settings['ui']['window_height'], 700)
        
        # ディレクトリが保存されたことを確認
        self.assertEqual(self.main_app.settings['general']['last_directory'], self.test_dir)
        
        # 設定が保存されたことを確認
        self.mock_settings_instance.save_settings.assert_called_once()


if __name__ == '__main__':
    unittest.main()
