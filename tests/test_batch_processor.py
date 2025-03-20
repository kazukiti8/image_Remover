import unittest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# BatchProcessorのインポート
from batch_processor import (BatchProcessor, CleanupBatchProcessor, 
                             QualityAssessmentBatchProcessor, BatchProcessThread)


class TestBatchProcessor(unittest.TestCase):
    """BatchProcessorクラスのテスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        # テスト用の一時ディレクトリを作成
        self.test_dir1 = tempfile.mkdtemp()
        self.test_dir2 = tempfile.mkdtemp()
        
        # テスト対象のインスタンスを作成
        self.batch_processor = BatchProcessor([self.test_dir1, self.test_dir2])

    def tearDown(self):
        """テスト後のクリーンアップ"""
        # テスト用ディレクトリを削除
        shutil.rmtree(self.test_dir1)
        shutil.rmtree(self.test_dir2)

    def test_init(self):
        """初期化のテスト"""
        self.assertEqual(self.batch_processor.directories, [self.test_dir1, self.test_dir2])
        self.assertEqual(self.batch_processor.results, {})
        self.assertFalse(self.batch_processor.canceled)

    def test_set_directories(self):
        """ディレクトリ設定のテスト"""
        new_dir = tempfile.mkdtemp()
        try:
            self.batch_processor.set_directories([new_dir])
            self.assertEqual(self.batch_processor.directories, [new_dir])
        finally:
            shutil.rmtree(new_dir)

    def test_add_directory(self):
        """ディレクトリ追加のテスト"""
        new_dir = tempfile.mkdtemp()
        try:
            self.batch_processor.add_directory(new_dir)
            self.assertIn(new_dir, self.batch_processor.directories)
            self.assertEqual(len(self.batch_processor.directories), 3)
            
            # 重複して追加してもリストに追加されないことを確認
            self.batch_processor.add_directory(new_dir)
            self.assertEqual(len(self.batch_processor.directories), 3)
        finally:
            shutil.rmtree(new_dir)

    def test_clear_directories(self):
        """ディレクトリクリアのテスト"""
        self.batch_processor.clear_directories()
        self.assertEqual(self.batch_processor.directories, [])

    def test_get_results(self):
        """結果取得のテスト"""
        self.batch_processor.results = {"test": "result"}
        self.assertEqual(self.batch_processor.get_results(), {"test": "result"})

    def test_cancel(self):
        """キャンセルのテスト"""
        self.batch_processor.cancel()
        self.assertTrue(self.batch_processor.canceled)

    def test_process_directories_empty(self):
        """空のディレクトリリストを処理するテスト"""
        self.batch_processor.clear_directories()
        result = self.batch_processor.process_directories()
        self.assertEqual(result, {})

    def test_process_directories(self):
        """ディレクトリリスト処理のテスト"""
        # process_directoryメソッドをモック化
        self.batch_processor.process_directory = MagicMock(return_value={"test": "result"})
        
        # 進捗コールバックをモック化
        progress_callback = MagicMock()
        
        # ディレクトリリストを処理
        result = self.batch_processor.process_directories(progress_callback)
        
        # 結果の確認
        self.assertEqual(len(result), 2)
        self.assertEqual(result[self.test_dir1], {"test": "result"})
        self.assertEqual(result[self.test_dir2], {"test": "result"})
        
        # process_directoryが各ディレクトリに対して呼ばれたか
        self.assertEqual(self.batch_processor.process_directory.call_count, 2)
        
        # progress_callbackが呼ばれたか
        self.assertEqual(progress_callback.call_count, 2)

    def test_process_directory_not_implemented(self):
        """process_directoryが実装されていないことをテスト"""
        with self.assertRaises(NotImplementedError):
            self.batch_processor.process_directory("dummy")


class TestCleanupBatchProcessor(unittest.TestCase):
    """CleanupBatchProcessorクラスのテスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        # テスト用の一時ディレクトリを作成
        self.test_dir = tempfile.mkdtemp()
        
        # テスト対象のインスタンスを作成
        self.cleanup_processor = CleanupBatchProcessor(
            blur_threshold=100.0,
            similarity_threshold=10,
            check_blur=True,
            check_similar=True,
            check_duplicate=True,
            recursive=True
        )
        self.cleanup_processor.set_directories([self.test_dir])

    def tearDown(self):
        """テスト後のクリーンアップ"""
        # テスト用ディレクトリを削除
        shutil.rmtree(self.test_dir)

    def test_init(self):
        """初期化のテスト"""
        self.assertEqual(self.cleanup_processor.blur_threshold, 100.0)
        self.assertEqual(self.cleanup_processor.similarity_threshold, 10)
        self.assertTrue(self.cleanup_processor.check_blur)
        self.assertTrue(self.cleanup_processor.check_similar)
        self.assertTrue(self.cleanup_processor.check_duplicate)
        self.assertTrue(self.cleanup_processor.recursive)

    @patch('image_cleanup_system.ImageCleanupSystem')
    def test_process_directory(self, mock_cleanup_system):
        """ディレクトリ処理のテスト"""
        # ImageCleanupSystemのメソッドをモック化
        instance = mock_cleanup_system.return_value
        instance.detect_blurry_images.return_value = ["blurry1", "blurry2"]
        instance.detect_similar_images.return_value = [("ref1", "similar1"), ("ref2", "similar2")]
        instance.detect_duplicate_images.return_value = [("ref3", "duplicate1"), ("ref4", "duplicate2")]
        
        # ディレクトリ処理を実行
        result = self.cleanup_processor.process_directory(self.test_dir)
        
        # 結果の確認
        self.assertEqual(len(result['blurry']), 2)
        self.assertEqual(len(result['similar']), 2)
        self.assertEqual(len(result['duplicate']), 2)
        
        # 適切なフラグに基づいてメソッドが呼ばれたことを確認
        mock_cleanup_system.assert_called_once()
        instance.detect_blurry_images.assert_called_once_with(100.0)
        instance.detect_similar_images.assert_called_once()
        instance.detect_duplicate_images.assert_called_once()


class TestQualityAssessmentBatchProcessor(unittest.TestCase):
    """QualityAssessmentBatchProcessorクラスのテスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        # テスト用の一時ディレクトリを作成
        self.test_dir = tempfile.mkdtemp()
        
        # テスト対象のインスタンスを作成
        self.quality_processor = QualityAssessmentBatchProcessor(
            blur_threshold=100.0,
            exposure_weight=1.0,
            contrast_weight=1.0,
            noise_weight=1.0,
            composition_weight=1.0,
            sharpness_weight=1.5,
            check_blur=True,
            check_exposure=True,
            check_contrast=True,
            check_noise=True,
            check_composition=True,
            recursive=True
        )
        self.quality_processor.set_directories([self.test_dir])
        
        # テスト用の画像ファイルを作成
        self.image_paths = [
            os.path.join(self.test_dir, "test1.jpg"),
            os.path.join(self.test_dir, "test2.png"),
            os.path.join(self.test_dir, "subfolder", "test3.jpg")
        ]
        
        # サブディレクトリを作成
        os.makedirs(os.path.join(self.test_dir, "subfolder"), exist_ok=True)
        
        # ダミーファイルを作成
        for img_path in self.image_paths:
            os.makedirs(os.path.dirname(img_path), exist_ok=True)
            with open(img_path, 'w') as f:
                f.write("dummy image data")

    def tearDown(self):
        """テスト後のクリーンアップ"""
        # テスト用ディレクトリを削除
        shutil.rmtree(self.test_dir)

    def test_init(self):
        """初期化のテスト"""
        self.assertEqual(self.quality_processor.settings['blur_threshold'], 100.0)
        self.assertEqual(self.quality_processor.settings['exposure_weight'], 1.0)
        self.assertTrue(self.quality_processor.recursive)

    @patch('ai_quality_assessment.ImageQualityAssessor')
    def test_process_directory(self, mock_assessor):
        """ディレクトリ処理のテスト"""
        # ImageQualityAssessorのメソッドをモック化
        instance = mock_assessor.return_value
        instance.assess_image.return_value = {"overall_score": 8.5, "assessment": {"sharpness": 9.0}}
        
        # ディレクトリ処理を実行
        result = self.quality_processor.process_directory(self.test_dir)
        
        # 結果の確認
        self.assertEqual(len(result), 3)  # 3枚の画像に対する結果
        for img_path in self.image_paths:
            self.assertIn(str(img_path), result)
            self.assertEqual(result[str(img_path)]["overall_score"], 8.5)
        
        # モック関数が呼ばれたことを確認
        mock_assessor.assert_called_once_with(self.quality_processor.settings)
        self.assertEqual(instance.assess_image.call_count, 3)

    def test_process_directory_canceled(self):
        """キャンセルされた場合のディレクトリ処理テスト"""
        self.quality_processor.cancel()
        
        with patch('ai_quality_assessment.ImageQualityAssessor') as mock_assessor:
            # ディレクトリ処理を実行
            result = self.quality_processor.process_directory(self.test_dir)
            
            # キャンセルされたので画像評価は行われていないはず
            instance = mock_assessor.return_value
            instance.assess_image.assert_not_called()


@patch('batch_processor.BatchProcessThread.process_directory')
class TestBatchProcessThread(unittest.TestCase):
    """BatchProcessThreadクラスのテスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        # テスト用の一時ディレクトリを作成
        self.test_dir1 = tempfile.mkdtemp()
        self.test_dir2 = tempfile.mkdtemp()
        
        # プロセッサクラスをモック化
        self.processor_class = MagicMock()
        
        # テスト対象のインスタンスを作成
        self.settings = {"setting1": "value1"}
        self.thread = BatchProcessThread(
            self.processor_class,
            [self.test_dir1, self.test_dir2],
            self.settings
        )
        
        # シグナルをモック化
        self.thread.directory_started_signal = MagicMock()
        self.thread.directory_completed_signal = MagicMock()
        self.thread.all_completed_signal = MagicMock()
        self.thread.error_signal = MagicMock()
        self.thread.progress_signal = MagicMock()

    def tearDown(self):
        """テスト後のクリーンアップ"""
        # テスト用ディレクトリを削除
        shutil.rmtree(self.test_dir1)
        shutil.rmtree(self.test_dir2)

    def test_init(self):
        """初期化のテスト"""
        self.assertEqual(self.thread.processor_class, self.processor_class)
        self.assertEqual(self.thread.directories, [self.test_dir1, self.test_dir2])
        self.assertEqual(self.thread.settings, self.settings)
        self.assertFalse(self.thread.canceled)
        self.assertEqual(self.thread.all_results, {})

    def test_run(self, mock_process_directory):
        """スレッド実行のテスト"""
        # process_directoryの戻り値を設定
        mock_process_directory.return_value = {"test": "result"}
        
        # スレッドを実行
        self.thread.run()
        
        # シグナルが発行されたことを確認
        self.assertEqual(self.thread.directory_started_signal.emit.call_count, 2)
        self.assertEqual(self.thread.directory_completed_signal.emit.call_count, 2)
        self.thread.all_completed_signal.emit.assert_called_once_with(self.thread.all_results)
        
        # 各ディレクトリに対してprocess_directoryが呼ばれたことを確認
        self.assertEqual(mock_process_directory.call_count, 2)
        
        # 結果が正しく保存されていることを確認
        self.assertEqual(len(self.thread.all_results), 2)
        self.assertEqual(self.thread.all_results[self.test_dir1], {"test": "result"})
        self.assertEqual(self.thread.all_results[self.test_dir2], {"test": "result"})

    def test_run_canceled(self, mock_process_directory):
        """キャンセルされた場合のスレッド実行テスト"""
        # キャンセルフラグを設定
        self.thread.cancel()
        
        # スレッドを実行
        self.thread.run()
        
        # シグナルが発行されていないことを確認
        self.thread.directory_started_signal.emit.assert_not_called()
        self.thread.directory_completed_signal.emit.assert_not_called()
        self.thread.all_completed_signal.emit.assert_called_once_with({})
        
        # process_directoryが呼ばれていないことを確認
        mock_process_directory.assert_not_called()

    def test_run_error(self, mock_process_directory):
        """エラーが発生した場合のスレッド実行テスト"""
        # process_directoryでエラーを発生させる
        mock_process_directory.side_effect = Exception("Test error")
        
        # スレッドを実行
        self.thread.run()
        
        # エラーシグナルが発行されたことを確認
        self.thread.error_signal.emit.assert_called_with(self.test_dir1, "Test error")
        
        # 全完了シグナルも発行されていることを確認
        self.thread.all_completed_signal.emit.assert_called_once_with({})

    def test_process_directory_not_implemented(self, _):
        """process_directoryが実装されていないことをテスト"""
        with self.assertRaises(NotImplementedError):
            processor = MagicMock()
            self.thread.process_directory(processor, "dummy")


if __name__ == '__main__':
    unittest.main()
