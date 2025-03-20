import unittest
import os
import tempfile
import shutil
from unittest.mock import MagicMock, patch

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox, QDialog

# MainApplicationクラスをインポート
from main_application import MainApplication


class TestMainApplicationAdvanced(unittest.TestCase):
    """MainApplicationクラスの高度な機能のテスト"""

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

    def test_change_thumbnail_size(self):
        """サムネイルサイズ変更のテスト"""
        # 元のサイズを確認
        original_size = self.main_app.settings['ui']['thumbnail_size']
        
        # サイズを変更
        new_size = 160
        self.main_app.change_thumbnail_size(new_size)
        
        # 設定が更新されたことを確認
        self.assertEqual(self.main_app.settings['ui']['thumbnail_size'], new_size)
        
        # 設定が保存されたことを確認
        self.mock_settings_instance.save_settings.assert_called_once()
        
        # UI更新が呼ばれたことを確認
        self.main_app.update_settings_ui = MagicMock()
        self.main_app.change_thumbnail_size(new_size)
        self.main_app.update_settings_ui.assert_called_once()

    def test_change_grid_columns(self):
        """グリッド列数変更のテスト"""
        # 元の列数を確認
        original_columns = self.main_app.settings['ui']['grid_columns']
        
        # 列数を変更
        new_columns = 6
        self.main_app.change_grid_columns(new_columns)
        
        # 設定が更新されたことを確認
        self.assertEqual(self.main_app.settings['ui']['grid_columns'], new_columns)
        
        # 設定が保存されたことを確認
        self.mock_settings_instance.save_settings.assert_called_once()
        
        # UI更新が呼ばれたことを確認
        self.main_app.update_settings_ui = MagicMock()
        self.main_app.change_grid_columns(new_columns)
        self.main_app.update_settings_ui.assert_called_once()

    def test_on_thumbnail_checkbox_toggled(self):
        """サムネイルチェックボックスのトグル時処理テスト"""
        # モックのチェックアイテムリスト
        checked_items = ["/fake/path/image1.jpg", "/fake/path/image2.png"]
        self.main_app.thumbnail_view.get_checked_items = MagicMock(return_value=checked_items)
        
        # チェックボックスがトグルされた場合の処理
        self.main_app.on_thumbnail_checkbox_toggled("/fake/path/image1.jpg", True)
        
        # 削除/移動ボタンのテキストが更新されたことを確認
        self.assertEqual(self.main_app.delete_btn.text(), f"選択した画像を削除 ({len(checked_items)})")
        self.assertEqual(self.main_app.move_btn.text(), f"選択した画像を移動... ({len(checked_items)})")
        
        # ボタンが有効になっていることを確認
        self.assertTrue(self.main_app.delete_btn.isEnabled())
        self.assertTrue(self.main_app.move_btn.isEnabled())
        
        # チェックアイテムが空の場合
        self.main_app.thumbnail_view.get_checked_items = MagicMock(return_value=[])
        self.main_app.on_thumbnail_checkbox_toggled("/fake/path/image1.jpg", False)
        
        # ボタンが無効になっていることを確認
        self.assertFalse(self.main_app.delete_btn.isEnabled())
        self.assertFalse(self.main_app.move_btn.isEnabled())

    @patch('main_application.ImageCleanupSystem')
    def test_detect_duplicate_images(self, mock_cleanup_system):
        """重複画像検出のテスト"""
        # クリーンアップシステムを設定
        mock_instance = MagicMock()
        duplicate_pairs = [
            ("/fake/path/ref1.jpg", "/fake/path/duplicate1.jpg"),
            ("/fake/path/ref2.png", "/fake/path/duplicate2.png")
        ]
        mock_instance.detect_duplicate_images.return_value = duplicate_pairs
        self.main_app.cleanup_system = mock_instance
        
        # 検出結果表示関数をモック化
        self.main_app.show_detection_results = MagicMock()
        
        # 重複画像検出を実行
        self.main_app.detect_duplicate_images()
        
        # クリーンアップシステムのメソッドが呼ばれたことを確認
        mock_instance.detect_duplicate_images.assert_called_once()
        
        # 検出結果が表示されたことを確認
        self.main_app.show_detection_results.assert_called_once_with(
            "重複画像", 
            [pair[1] for pair in duplicate_pairs]
        )

    @patch('main_application.ImageCleanupSystem')
    def test_detect_all(self, mock_cleanup_system):
        """全ての検出実行テスト"""
        # クリーンアップシステムを設定
        mock_instance = MagicMock()
        results = {
            'blurry': ["/fake/path/blurry1.jpg", "/fake/path/blurry2.png"],
            'similar': [("/fake/path/ref1.jpg", "/fake/path/similar1.jpg")],
            'duplicate': [("/fake/path/ref2.jpg", "/fake/path/duplicate1.jpg")]
        }
        mock_instance.process_directory.return_value = results
        self.main_app.cleanup_system = mock_instance
        
        # 検出結果表示関数をモック化
        self.main_app.show_detection_results = MagicMock()
        
        # 全ての検出を実行
        self.main_app.detect_all()
        
        # クリーンアップシステムのメソッドが呼ばれたことを確認
        mock_instance.process_directory.assert_called_once()
        
        # 検出結果が表示されたことを確認
        expected_detected = results['blurry'] + [pair[1] for pair in results['similar']] + [pair[1] for pair in results['duplicate']]
        self.main_app.show_detection_results.assert_called_once_with("全ての検出", expected_detected)

    @patch('main_application.ImageCleanupSystem')
    def test_assess_image_quality(self, mock_cleanup_system):
        """画質評価実行テスト"""
        # クリーンアップシステムを設定
        mock_instance = MagicMock()
        image_files = ["/fake/path/image1.jpg", "/fake/path/image2.png"]
        mock_instance.get_image_files.return_value = image_files
        self.main_app.cleanup_system = mock_instance
        
        # 画質評価タブをモック化
        self.main_app.quality_assessment = MagicMock()
        
        # 画質評価を実行
        self.main_app.assess_image_quality()
        
        # 画質評価タブが選択されたことを確認
        self.main_app.detail_tabs.setCurrentWidget.assert_called_once_with(self.main_app.quality_assessment)
        
        # 画質評価が開始されたことを確認
        self.main_app.quality_assessment.start_assessment.assert_called_once_with([str(path) for path in image_files])

    def test_on_quality_assessment_complete(self):
        """画質評価完了時の処理テスト"""
        # 評価結果を作成
        results = {
            "/fake/path/good.jpg": {"overall_score": 8.5},
            "/fake/path/bad1.jpg": {"overall_score": 4.5},
            "/fake/path/bad2.png": {"overall_score": 3.8},
            "/fake/path/average.jpg": {"overall_score": 6.2}
        }
        
        # 検出結果表示関数をモック化
        self.main_app.show_detection_results = MagicMock()
        
        # 画質評価完了時の処理を実行
        self.main_app.on_quality_assessment_complete(results)
        
        # 低品質の画像のみが検出結果として表示されることを確認
        low_quality_images = ["/fake/path/bad1.jpg", "/fake/path/bad2.png"]
        self.main_app.show_detection_results.assert_called_once_with("低品質画像", low_quality_images)

    @patch('main_application.QMessageBox')
    def test_on_quality_assessment_complete_no_low_quality(self, mock_message_box):
        """低品質画像がない場合の画質評価完了時の処理テスト"""
        # 全て高品質の評価結果を作成
        results = {
            "/fake/path/good1.jpg": {"overall_score": 8.5},
            "/fake/path/good2.jpg": {"overall_score": 7.2}
        }
        
        # メッセージボックスの情報関数をモック化
        mock_message_box.information = MagicMock()
        
        # 画質評価完了時の処理を実行
        self.main_app.on_quality_assessment_complete(results)
        
        # 情報メッセージが表示されたことを確認
        mock_message_box.information.assert_called_once()
        
        # メッセージの内容を確認
        args, _ = mock_message_box.information.call_args
        self.assertEqual(args[1], "画質評価完了")
        self.assertIn("見つかりませんでした", args[2])

    def test_show_batch_processor(self):
        """バッチ処理ドック表示テスト"""
        # バッチ処理ドックをモック化
        self.main_app.batch_dock = MagicMock()
        
        # バッチ処理ドックを表示
        self.main_app.show_batch_processor()
        
        # ドックが表示されたことを確認
        self.main_app.batch_dock.show.assert_called_once()

    def test_update_settings_ui_thumbnail_size(self):
        """サムネイルサイズ設定変更時のUI更新テスト"""
        # サムネイルビューをモック化
        self.main_app.thumbnail_view = MagicMock()
        self.main_app.thumbnail_view.thumbnail_size = 120
        self.main_app.thumbnail_view.columns = 4
        
        # 設定を変更
        self.main_app.settings['ui']['thumbnail_size'] = 160
        
        # UI更新を実行
        self.main_app.update_settings_ui()
        
        # サムネイルビューの設定が更新されたことを確認
        self.assertEqual(self.main_app.thumbnail_view.thumbnail_size, 160)
        
        # サムネイルが再読み込みされたことを確認
        self.main_app.thumbnail_view.set_images.assert_called_once()

    def test_update_settings_ui_grid_columns(self):
        """グリッド列数設定変更時のUI更新テスト"""
        # サムネイルビューをモック化
        self.main_app.thumbnail_view = MagicMock()
        self.main_app.thumbnail_view.thumbnail_size = 120
        self.main_app.thumbnail_view.columns = 4
        
        # 設定を変更
        self.main_app.settings['ui']['grid_columns'] = 6
        
        # UI更新を実行
        self.main_app.update_settings_ui()
        
        # サムネイルビューの設定が更新されたことを確認
        self.assertEqual(self.main_app.thumbnail_view.columns, 6)
        
        # サムネイルが再読み込みされたことを確認
        self.main_app.thumbnail_view.set_images.assert_called_once()

    def test_update_settings_ui_show_exif(self):
        """EXIF表示設定変更時のUI更新テスト"""
        # show_exif設定とアクションをモック化
        self.main_app.settings['ui']['show_exif'] = True
        self.main_app.show_exif_action = MagicMock()
        self.main_app.toggle_exif_display = MagicMock()
        
        # UI更新を実行
        self.main_app.update_settings_ui()
        
        # アクションがチェックされていることを確認
        self.main_app.show_exif_action.setChecked.assert_called_once_with(True)
        
        # EXIF表示設定が適用されたことを確認
        self.main_app.toggle_exif_display.assert_called_once()


if __name__ == '__main__':
    unittest.main()
