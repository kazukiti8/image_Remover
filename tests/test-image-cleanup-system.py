import unittest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# ImageCleanupSystemのインポート
from image_cleanup_system import ImageCleanupSystem


class TestImageCleanupSystem(unittest.TestCase):
    """ImageCleanupSystemクラスのテスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        # テスト用の一時ディレクトリを作成
        self.test_dir = tempfile.mkdtemp()
        
        # 移動先ディレクトリを作成
        self.move_dir = tempfile.mkdtemp()
        
        # 類似性閾値
        self.similarity_threshold = 10
        
        # テスト対象のインスタンスを作成
        self.cleanup_system = ImageCleanupSystem(
            self.test_dir,
            self.move_dir,
            self.similarity_threshold
        )
        
        # テスト用の画像ファイルパスを作成（実際にはファイルは作成しない）
        self.image_paths = [
            Path(self.test_dir) / "test1.jpg",
            Path(self.test_dir) / "test2.png",
            Path(self.test_dir) / "test3.jpeg",
            Path(self.test_dir) / "test4.gif",
            Path(self.test_dir) / "test5.webp",
            Path(self.test_dir) / "subfolder" / "test6.jpg"
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
        shutil.rmtree(self.move_dir)

    def test_init(self):
        """初期化のテスト"""
        self.assertEqual(self.cleanup_system.directory, Path(self.test_dir))
        self.assertEqual(self.cleanup_system.move_to, Path(self.move_dir))
        self.assertEqual(self.cleanup_system.similarity_threshold, self.similarity_threshold)
        
        # 移動先ディレクトリのサブディレクトリが作成されているか
        self.assertTrue(os.path.exists(os.path.join(self.move_dir, "blurry")))
        self.assertTrue(os.path.exists(os.path.join(self.move_dir, "similar")))
        self.assertTrue(os.path.exists(os.path.join(self.move_dir, "duplicate")))

    def test_get_image_files(self):
        """画像ファイル取得のテスト"""
        image_files = self.cleanup_system.get_image_files()
        
        # 全てのテスト用画像が取得できているか
        self.assertEqual(len(image_files), len(self.image_paths))
        
        # 各ファイルが含まれているか
        for img_path in self.image_paths:
            self.assertIn(img_path, image_files)

    @patch('cv2.imread')
    @patch('cv2.cvtColor')
    @patch('cv2.Laplacian')
    def test_detect_blurry_images(self, mock_laplacian, mock_cvtcolor, mock_imread):
        """ブレている画像検出のテスト"""
        # モックの設定
        mock_imread.return_value = MagicMock()
        mock_cvtcolor.return_value = MagicMock()
        mock_laplacian.return_value = MagicMock()
        
        # 分散値をモック化
        laplacian_mock = MagicMock()
        laplacian_mock.var.return_value = 50.0  # 閾値以下なのでブレていると判断される
        mock_laplacian.return_value = laplacian_mock
        
        # ブレ検出の実行
        threshold = 100.0
        blurry_images = self.cleanup_system.detect_blurry_images(threshold)
        
        # 検出結果の確認
        self.assertEqual(len(blurry_images), len(self.image_paths))
        
        # 各画像に対してcv2関数が呼ばれたか
        self.assertEqual(mock_imread.call_count, len(self.image_paths))
        self.assertEqual(mock_cvtcolor.call_count, len(self.image_paths))
        self.assertEqual(mock_laplacian.call_count, len(self.image_paths))

    @patch('image_cleanup_system.ImageCleanupSystem.compute_image_hash')
    def test_detect_similar_images(self, mock_compute_hash):
        """類似画像検出のテスト"""
        # 画像ハッシュのモックを設定
        class MockHash:
            def __init__(self, value):
                self.value = value
                
            def __sub__(self, other):
                # test1とtest2、test3とtest4が類似していると判断するようにする
                if (self.value == 1 and other.value == 2) or (self.value == 2 and other.value == 1):
                    return 5  # 閾値以下
                elif (self.value == 3 and other.value == 4) or (self.value == 4 and other.value == 3):
                    return 3  # 閾値以下
                else:
                    return 20  # 閾値以上
        
        # 各画像のハッシュを設定
        hashes = {
            self.image_paths[0]: MockHash(1),
            self.image_paths[1]: MockHash(2),
            self.image_paths[2]: MockHash(3),
            self.image_paths[3]: MockHash(4),
            self.image_paths[4]: MockHash(5),
            self.image_paths[5]: MockHash(6)
        }
        
        # ハッシュ計算関数のモックを設定
        mock_compute_hash.side_effect = lambda path: hashes.get(path, None)
        
        # 類似画像検出の実行
        similar_images = self.cleanup_system.detect_similar_images()
        
        # 検出結果の確認（2組の類似画像ペアが検出されるはず）
        self.assertEqual(len(similar_images), 2)
        
        # モック関数が呼ばれたことを確認
        self.assertEqual(mock_compute_hash.call_count, len(self.image_paths))

    def test_detect_duplicate_images(self):
        """重複画像検出のテスト"""
        # ファイルサイズを同じにするため、同じ内容で書き直す
        with open(self.image_paths[0], 'w') as f:
            f.write("duplicate content")
        with open(self.image_paths[1], 'w') as f:
            f.write("duplicate content")
        
        # 重複画像検出の実行
        duplicate_images = self.cleanup_system.detect_duplicate_images()
        
        # 検出結果の確認（1組の重複画像ペアが検出されるはず）
        self.assertEqual(len(duplicate_images), 1)
        
        # 検出されたペアが正しいか
        found_pair = False
        for ref_img, dup_img in duplicate_images:
            if ((ref_img == self.image_paths[0] and dup_img == self.image_paths[1]) or
                (ref_img == self.image_paths[1] and dup_img == self.image_paths[0])):
                found_pair = True
                break
        
        self.assertTrue(found_pair, "正しい重複画像ペアが検出されていません")

    @patch('image_cleanup_system.ImageCleanupSystem.detect_blurry_images')
    @patch('image_cleanup_system.ImageCleanupSystem.detect_similar_images')
    @patch('image_cleanup_system.ImageCleanupSystem.detect_duplicate_images')
    def test_process_directory(self, mock_detect_duplicate, mock_detect_similar, mock_detect_blurry):
        """ディレクトリ処理のテスト"""
        # モックの戻り値を設定
        mock_detect_blurry.return_value = [self.image_paths[0]]
        mock_detect_similar.return_value = [(self.image_paths[1], self.image_paths[2])]
        mock_detect_duplicate.return_value = [(self.image_paths[3], self.image_paths[4])]
        
        # ディレクトリ処理を実行
        results = self.cleanup_system.process_directory()
        
        # 結果の確認
        self.assertEqual(len(results['blurry']), 1)
        self.assertEqual(len(results['similar']), 1)
        self.assertEqual(len(results['duplicate']), 1)
        
        # 各モック関数が呼ばれたことを確認
        mock_detect_blurry.assert_called_once()
        mock_detect_similar.assert_called_once()
        mock_detect_duplicate.assert_called_once()

    @patch('os.remove')
    @patch('shutil.move')
    @patch('builtins.input', return_value='y')
    def test_cleanup_delete(self, mock_input, mock_move, mock_remove):
        """クリーンアップ（削除モード）のテスト"""
        # 移動先なしのシステムを作成
        cleanup_system = ImageCleanupSystem(
            self.test_dir,
            None,
            self.similarity_threshold
        )
        
        # 検出結果を設定
        cleanup_system.blurry_images = [self.image_paths[0]]
        cleanup_system.similar_images = [(self.image_paths[1], self.image_paths[2])]
        cleanup_system.duplicate_images = [(self.image_paths[3], self.image_paths[4])]
        
        # クリーンアップを実行
        cleanup_system.cleanup(confirm=True)
        
        # 削除関数が呼ばれたことを確認
        self.assertEqual(mock_remove.call_count, 3)
        
        # 移動関数は呼ばれていないことを確認
        mock_move.assert_not_called()

    @patch('os.remove')
    @patch('shutil.move')
    @patch('builtins.input', return_value='y')
    def test_cleanup_move(self, mock_input, mock_move, mock_remove):
        """クリーンアップ（移動モード）のテスト"""
        # 検出結果を設定
        self.cleanup_system.blurry_images = [self.image_paths[0]]
        self.cleanup_system.similar_images = [(self.image_paths[1], self.image_paths[2])]
        self.cleanup_system.duplicate_images = [(self.image_paths[3], self.image_paths[4])]
        
        # クリーンアップを実行
        self.cleanup_system.cleanup(confirm=True)
        
        # 移動関数が呼ばれたことを確認
        self.assertEqual(mock_move.call_count, 3)
        
        # 削除関数は呼ばれていないことを確認
        mock_remove.assert_not_called()


if __name__ == '__main__':
    unittest.main()
