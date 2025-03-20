import unittest
import os
import tempfile
import json
import shutil
from unittest.mock import MagicMock, patch

# SettingsManagerのインポート
from settings_manager import SettingsManager


class TestSettingsManager(unittest.TestCase):
    """SettingsManagerクラスのテスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        # QSettingsをモック化
        self.qsettings_patcher = patch('settings_manager.QSettings')
        self.mock_qsettings = self.qsettings_patcher.start()
        self.mock_qsettings_instance = MagicMock()
        self.mock_qsettings.return_value = self.mock_qsettings_instance
        
        # QDirをモック化
        self.qdir_patcher = patch('settings_manager.QDir')
        self.mock_qdir = self.qdir_patcher.start()
        self.mock_qdir.homePath.return_value = tempfile.gettempdir()
        
        # テスト用のインスタンスを作成
        self.app_name = "TestApp"
        self.org_name = "TestOrg"
        self.settings_manager = SettingsManager(self.app_name, self.org_name)
        
        # テスト用の設定データ
        self.test_settings = {
            "general": {
                "last_directory": "/test/path",
                "auto_fit_preview": True,
                "theme": "dark",
                "language": "ja",
                "confirm_deletes": True
            },
            "cleanup": {
                "blur_threshold": 120.0,
                "similarity_threshold": 15
            }
        }

    def tearDown(self):
        """テスト後のクリーンアップ"""
        # モックを停止
        self.qsettings_patcher.stop()
        self.qdir_patcher.stop()
        
        # 設定ファイルが作成されていたら削除
        if hasattr(self, 'temp_settings_file') and os.path.exists(self.temp_settings_file):
            os.remove(self.temp_settings_file)

    def test_init(self):
        """初期化のテスト"""
        self.assertEqual(self.settings_manager.app_name, self.app_name)
        self.assertEqual(self.settings_manager.org_name, self.org_name)
        self.assertEqual(self.settings_manager.qsettings, self.mock_qsettings_instance)
        
        # デフォルト設定が正しく設定されているか
        self.assertIn("general", self.settings_manager.default_settings)
        self.assertIn("cleanup", self.settings_manager.default_settings)
        self.assertIn("quality", self.settings_manager.default_settings)
        self.assertIn("ui", self.settings_manager.default_settings)

    @patch('os.path.exists', return_value=False)
    def test_load_settings_no_file(self, mock_exists):
        """設定ファイルが存在しない場合のロードテスト"""
        # QSettingsが空の場合のテスト
        self.mock_qsettings_instance.contains.return_value = False
        
        # 設定をロード
        settings = self.settings_manager.load_settings()
        
        # デフォルト設定と同じ内容が返されるはず
        for group_name, group_settings in self.settings_manager.default_settings.items():
            self.assertIn(group_name, settings)
            for key, value in group_settings.items():
                self.assertIn(key, settings[group_name])
                self.assertEqual(settings[group_name][key], value)

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open')
    @patch('json.load')
    def test_load_settings_from_json(self, mock_json_load, mock_open, mock_exists):
        """JSONファイルからの設定ロードテスト"""
        # JSONのモック戻り値を設定
        mock_json_load.return_value = self.test_settings
        
        # 設定をロード
        settings = self.settings_manager.load_settings()
        
        # JSONからロードした内容が含まれているか
        for group_name, group_settings in self.test_settings.items():
            self.assertIn(group_name, settings)
            for key, value in group_settings.items():
                self.assertIn(key, settings[group_name])
                self.assertEqual(settings[group_name][key], value)
        
        # JSONファイルが開かれたことを確認
        mock_open.assert_called_once()
        mock_json_load.assert_called_once()

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open')
    @patch('json.load')
    def test_load_settings_merge_with_defaults(self, mock_json_load, mock_open, mock_exists):
        """JSONの不完全な設定とデフォルト設定のマージテスト"""
        # 不完全な設定をJSONから返す
        incomplete_settings = {
            "general": {
                "last_directory": "/test/path"
            }
        }
        mock_json_load.return_value = incomplete_settings
        
        # 設定をロード
        settings = self.settings_manager.load_settings()
        
        # JSONからロードした内容が含まれているか
        self.assertEqual(settings["general"]["last_directory"], "/test/path")
        
        # デフォルト値でマージされているか
        self.assertEqual(settings["general"]["theme"], self.settings_manager.default_settings["general"]["theme"])
        self.assertEqual(settings["cleanup"]["blur_threshold"], self.settings_manager.default_settings["cleanup"]["blur_threshold"])

    def test_get(self):
        """設定取得のテスト"""
        # テスト用の設定を設定
        self.settings_manager.settings = self.test_settings
        
        # 存在する設定を取得
        self.assertEqual(self.settings_manager.get("general", "last_directory"), "/test/path")
        self.assertEqual(self.settings_manager.get("cleanup", "blur_threshold"), 120.0)
        
        # 存在しない設定を取得（デフォルト値が返される）
        self.assertEqual(self.settings_manager.get("nonexistent", "key", "default"), "default")
        self.assertEqual(self.settings_manager.get("general", "nonexistent", "default"), "default")

    def test_set(self):
        """設定設定のテスト"""
        # 設定を設定
        self.settings_manager.set("general", "last_directory", "/new/path")
        self.settings_manager.set("new_group", "new_key", "new_value")
        
        # 設定が正しく設定されたか
        self.assertEqual(self.settings_manager.settings["general"]["last_directory"], "/new/path")
        self.assertEqual(self.settings_manager.settings["new_group"]["new_key"], "new_value")

    def test_get_all(self):
        """全設定取得のテスト"""
        # テスト用の設定を設定
        self.settings_manager.settings = self.test_settings
        
        # 全設定を取得
        all_settings = self.settings_manager.get_all()
        
        # 設定が正しく取得できたか
        self.assertEqual(all_settings, self.test_settings)

    @patch('os.makedirs')
    @patch('builtins.open')
    @patch('json.dump')
    def test_save_to_json(self, mock_json_dump, mock_open, mock_makedirs):
        """JSONファイルへの設定保存テスト"""
        # テスト用の設定を設定
        self.settings_manager.settings = self.test_settings
        
        # 設定を保存
        result = self.settings_manager.save_to_json()
        
        # 結果が成功を示しているか
        self.assertTrue(result)
        
        # ディレクトリが作成されたことを確認
        mock_makedirs.assert_called_once()
        
        # ファイルが開かれたことを確認
        mock_open.assert_called_once()
        
        # JSONに書き込まれたことを確認
        mock_json_dump.assert_called_once_with(
            self.test_settings, 
            mock_open.return_value.__enter__.return_value, 
            indent=4, 
            ensure_ascii=False
        )

    @patch('settings_manager.SettingsManager.save_to_json')
    def test_save_settings(self, mock_save_to_json):
        """設定保存のテスト"""
        # テスト用の設定を設定
        self.settings_manager.settings = self.test_settings
        
        # 設定を保存
        self.settings_manager.save_settings()
        
        # QSettingsの各グループと値が設定されたことを確認
        for group_name, group_settings in self.test_settings.items():
            self.mock_qsettings_instance.beginGroup.assert_any_call(group_name)
            for key, value in group_settings.items():
                self.mock_qsettings_instance.setValue.assert_any_call(key, value)
            self.mock_qsettings_instance.endGroup.assert_called()
        
        # JSONファイルにも保存されたことを確認
        mock_save_to_json.assert_called_once()

    def test_reset(self):
        """設定リセットのテスト"""
        # テスト用の設定を設定（デフォルトと異なる値）
        self.settings_manager.settings = self.test_settings
        
        # 設定をリセット
        with patch('settings_manager.SettingsManager.save_settings') as mock_save:
            self.settings_manager.reset()
            
            # 設定がデフォルト値にリセットされたか
            for group_name, group_settings in self.settings_manager.default_settings.items():
                self.assertIn(group_name, self.settings_manager.settings)
                for key, value in group_settings.items():
                    self.assertIn(key, self.settings_manager.settings[group_name])
                    self.assertEqual(self.settings_manager.settings[group_name][key], value)
            
            # 保存が呼ばれたことを確認
            mock_save.assert_called_once()

    @patch('builtins.open')
    @patch('json.dump')
    def test_export_settings(self, mock_json_dump, mock_open):
        """設定エクスポートのテスト"""
        # テスト用の設定を設定
        self.settings_manager.settings = self.test_settings
        
        # 設定をエクスポート
        temp_file = tempfile.mktemp(suffix='.json')
        result = self.settings_manager.export_settings(temp_file)
        
        # 結果が成功を示しているか
        self.assertTrue(result)
        
        # ファイルが開かれたことを確認
        mock_open.assert_called_once_with(temp_file, 'w', encoding='utf-8')
        
        # JSONに書き込まれたことを確認
        mock_json_dump.assert_called_once_with(
            self.test_settings, 
            mock_open.return_value.__enter__.return_value, 
            indent=4, 
            ensure_ascii=False
        )

    @patch('builtins.open')
    @patch('json.load')
    @patch('settings_manager.SettingsManager.save_settings')
    def test_import_settings(self, mock_save, mock_json_load, mock_open):
        """設定インポートのテスト"""
        # インポートする設定を準備
        import_settings = {
            "general": {
                "last_directory": "/imported/path",
                "theme": "light"
            },
            "new_group": {
                "new_key": "new_value"
            }
        }
        mock_json_load.return_value = import_settings
        
        # 初期設定を設定
        initial_settings = self.settings_manager.settings.copy()
        
        # 設定をインポート
        temp_file = tempfile.mktemp(suffix='.json')
        result = self.settings_manager.import_settings(temp_file)
        
        # 結果が成功を示しているか
        self.assertTrue(result)
        
        # ファイルが開かれたことを確認
        mock_open.assert_called_once_with(temp_file, 'r', encoding='utf-8')
        
        # JSONからロードされたことを確認
        mock_json_load.assert_called_once()
        
        # 設定が更新されたことを確認
        self.assertEqual(self.settings_manager.settings["general"]["last_directory"], "/imported/path")
        self.assertEqual(self.settings_manager.settings["general"]["theme"], "light")
        
        # 新しいグループと設定も追加されているか
        self.assertIn("new_group", self.settings_manager.settings)
        self.assertEqual(self.settings_manager.settings["new_group"]["new_key"], "new_value")
        
        # 元の設定の他の値は保持されているか
        for group_name, group_settings in initial_settings.items():
            if group_name not in import_settings:
                self.assertIn(group_name, self.settings_manager.settings)
                for key, value in group_settings.items():
                    self.assertIn(key, self.settings_manager.settings[group_name])
                    self.assertEqual(self.settings_manager.settings[group_name][key], value)
        
        # 保存が呼ばれたことを確認
        mock_save.assert_called_once()

    @patch('builtins.open')
    @patch('json.load')
    def test_import_settings_type_conversion(self, mock_json_load, mock_open):
        """インポートした設定の型変換テスト"""
        # 型が異なる設定をインポート
        import_settings = {
            "general": {
                "auto_fit_preview": "true",  # 文字列のbool値
                "confirm_deletes": 1  # 数値のbool値
            },
            "cleanup": {
                "blur_threshold": "150",  # 文字列の数値
                "similarity_threshold": 12.5  # floatの数値（intであるべき）
            }
        }
        mock_json_load.return_value = import_settings
        
        # 設定をインポート
        with patch('settings_manager.SettingsManager.save_settings'):
            temp_file = tempfile.mktemp(suffix='.json')
            self.settings_manager.import_settings(temp_file)
        
        # 型変換が行われているか
        self.assertIsInstance(self.settings_manager.settings["general"]["auto_fit_preview"], bool)
        self.assertTrue(self.settings_manager.settings["general"]["auto_fit_preview"])
        
        self.assertIsInstance(self.settings_manager.settings["general"]["confirm_deletes"], bool)
        self.assertTrue(self.settings_manager.settings["general"]["confirm_deletes"])
        
        self.assertIsInstance(self.settings_manager.settings["cleanup"]["blur_threshold"], float)
        self.assertEqual(self.settings_manager.settings["cleanup"]["blur_threshold"], 150.0)
        
        self.assertIsInstance(self.settings_manager.settings["cleanup"]["similarity_threshold"], int)
        self.assertEqual(self.settings_manager.settings["cleanup"]["similarity_threshold"], 12)


if __name__ == '__main__':
    unittest.main()
