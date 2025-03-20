import os
import cv2
import numpy as np
from PIL import Image
import imagehash
from pathlib import Path
import shutil
import argparse
from collections import defaultdict
import threading
import time

class ImageCleanupSystem:
    def __init__(self, directory, move_to=None, similarity_threshold=10):
        """
        初期化関数
        
        Parameters:
        directory (str): 処理対象のディレクトリパス
        move_to (str): 削除する代わりに移動する場合の移動先ディレクトリ
        similarity_threshold (int): 類似画像と判断するハッシュの差分閾値（低いほど厳格）
        """
        self.directory = Path(directory)
        self.move_to = Path(move_to) if move_to else None
        self.similarity_threshold = similarity_threshold
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
        self.blurry_images = []
        self.similar_images = []
        self.duplicate_images = []
        
        # 移動先ディレクトリが指定されている場合は作成
        if self.move_to and not self.move_to.exists():
            os.makedirs(self.move_to / "blurry", exist_ok=True)
            os.makedirs(self.move_to / "similar", exist_ok=True)
            os.makedirs(self.move_to / "duplicate", exist_ok=True)
    
    def get_image_files(self):
        """ディレクトリ内の画像ファイルのリストを取得"""
        image_files = []
        for ext in self.image_extensions:
            image_files.extend(list(self.directory.glob(f"**/*{ext}")))
            image_files.extend(list(self.directory.glob(f"**/*{ext.upper()}")))
        return image_files
    
    def detect_blurry_images(self, threshold=100.0):
        """
        ブレている画像を検出
        
        Parameters:
        threshold (float): ラプラシアン変換の分散値の閾値（低いほどブレていると判断）
        """
        print("ブレている画像を検出中...")
        image_files = self.get_image_files()
        total = len(image_files)
        
        for i, img_path in enumerate(image_files):
            try:
                # ステータス表示
                if i % 10 == 0:
                    print(f"進捗: {i+1}/{total} ({((i+1)/total*100):.1f}%)")
                
                # 画像を読み込み
                img = cv2.imread(str(img_path))
                if img is None:
                    continue
                
                # グレースケールに変換
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
                # ラプラシアン変換を適用
                laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                
                # 分散を計算
                variance = laplacian.var()
                
                # 閾値以下であればブレている画像と判断
                if variance < threshold:
                    self.blurry_images.append(img_path)
                    print(f"ブレている画像を検出: {img_path} (分散値: {variance:.2f})")
            except Exception as e:
                print(f"エラー（{img_path}）: {e}")
        
        print(f"検出されたブレている画像: {len(self.blurry_images)}枚")
        return self.blurry_images
    
    def compute_image_hash(self, img_path):
        """画像のパーセプチャルハッシュを計算"""
        try:
            img = Image.open(img_path)
            # dハッシュを計算（差分ハッシュ）
            hash_value = imagehash.dhash(img)
            return hash_value
        except Exception as e:
            print(f"ハッシュ計算エラー（{img_path}）: {e}")
            return None
    
    def detect_similar_images(self):
        """類似画像を検出"""
        print("類似画像を検出中...")
        image_files = self.get_image_files()
        total = len(image_files)
        
        # 画像ハッシュの辞書を作成
        hash_dict = {}
        for i, img_path in enumerate(image_files):
            # ステータス表示
            if i % 10 == 0:
                print(f"ハッシュ計算中: {i+1}/{total} ({((i+1)/total*100):.1f}%)")
            
            hash_value = self.compute_image_hash(img_path)
            if hash_value:
                hash_dict[img_path] = hash_value
        
        # 類似画像をグループ化
        similar_groups = defaultdict(list)
        processed = set()
        
        total_comparisons = len(hash_dict) * (len(hash_dict) - 1) // 2
        comparison_count = 0
        print(f"画像の類似性を比較中... (全{total_comparisons}件)")
        
        # 進捗表示用スレッド
        stop_thread = False
        def progress_reporter():
            start_time = time.time()
            while not stop_thread:
                elapsed = time.time() - start_time
                if comparison_count > 0 and elapsed > 0:
                    rate = comparison_count / elapsed
                    remaining = (total_comparisons - comparison_count) / rate if rate > 0 else 0
                    print(f"進捗: {comparison_count}/{total_comparisons} "
                          f"({(comparison_count/total_comparisons*100):.1f}%) "
                          f"残り時間: {remaining/60:.1f}分")
                time.sleep(5)
        
        # 進捗レポーターを開始
        if total_comparisons > 1000:
            progress_thread = threading.Thread(target=progress_reporter)
            progress_thread.daemon = True
            progress_thread.start()
        
        # 各画像ペアを比較
        items = list(hash_dict.items())
        for i, (img1, hash1) in enumerate(items):
            if img1 in processed:
                continue
                
            group = [img1]
            for img2, hash2 in items[i+1:]:
                if img2 in processed:
                    continue
                
                comparison_count += 1
                # ハッシュの差異を計算
                hash_diff = hash1 - hash2
                
                # 閾値以下なら類似画像
                if hash_diff <= self.similarity_threshold:
                    group.append(img2)
                    processed.add(img2)
            
            # 2枚以上あるグループのみ記録
            if len(group) > 1:
                # 基準となる画像（最初の画像）
                reference_img = group[0]
                # 類似画像（2番目以降）
                for similar_img in group[1:]:
                    self.similar_images.append((reference_img, similar_img))
        
        # 進捗レポーターを停止
        stop_thread = True
        if total_comparisons > 1000:
            progress_thread.join()
        
        print(f"検出された類似画像ペア: {len(self.similar_images)}組")
        return self.similar_images
    
    def detect_duplicate_images(self):
        """完全な重複画像を検出"""
        print("重複画像を検出中...")
        image_files = self.get_image_files()
        total = len(image_files)
        
        # ファイルサイズとハッシュ値で重複を検出
        size_dict = defaultdict(list)
        
        # まずファイルサイズでグループ化
        for i, img_path in enumerate(image_files):
            if i % 100 == 0:
                print(f"処理中: {i+1}/{total} ({((i+1)/total*100):.1f}%)")
            
            file_size = os.path.getsize(img_path)
            size_dict[file_size].append(img_path)
        
        # 同じサイズのファイルでハッシュを比較
        for size, files in size_dict.items():
            if len(files) < 2:
                continue
            
            hash_dict = defaultdict(list)
            for file_path in files:
                try:
                    with open(file_path, 'rb') as f:
                        file_hash = hash(f.read())
                        hash_dict[file_hash].append(file_path)
                except Exception as e:
                    print(f"ファイル読み込みエラー（{file_path}）: {e}")
            
            # 同じハッシュ値を持つファイルを重複として記録
            for file_hash, duplicate_files in hash_dict.items():
                if len(duplicate_files) > 1:
                    # 基準となる画像（最初の画像）
                    reference_img = duplicate_files[0]
                    # 重複画像（2番目以降）
                    for duplicate_img in duplicate_files[1:]:
                        self.duplicate_images.append((reference_img, duplicate_img))
        
        print(f"検出された重複画像ペア: {len(self.duplicate_images)}組")
        return self.duplicate_images
    
    def process_directory(self):
        """ディレクトリを処理して不要な画像を検出"""
        print(f"ディレクトリの処理を開始: {self.directory}")
        
        # ブレている画像を検出
        self.detect_blurry_images()
        
        # 類似画像を検出
        self.detect_similar_images()
        
        # 重複画像を検出
        self.detect_duplicate_images()
        
        return {
            'blurry': self.blurry_images,
            'similar': self.similar_images,
            'duplicate': self.duplicate_images
        }
    
    def cleanup(self, confirm=True):
        """検出された不要な画像を削除または移動"""
        if not self.blurry_images and not self.similar_images and not self.duplicate_images:
            print("削除対象の画像が見つかりませんでした")
            return
        
        # 削除または移動する画像を表示
        print("\n--- 削除候補の画像 ---")
        
        print("\nブレている画像:")
        for img in self.blurry_images:
            print(f"  {img}")
        
        print("\n類似画像:")
        for ref_img, similar_img in self.similar_images:
            print(f"  基準画像: {ref_img}")
            print(f"  類似画像: {similar_img}")
            print("")
        
        print("\n重複画像:")
        for ref_img, duplicate_img in self.duplicate_images:
            print(f"  基準画像: {ref_img}")
            print(f"  重複画像: {duplicate_img}")
            print("")
        
        # 削除または移動する画像の総数
        total_blurry = len(self.blurry_images)
        total_similar = len([img for _, img in self.similar_images])
        total_duplicate = len([img for _, img in self.duplicate_images])
        total = total_blurry + total_similar + total_duplicate
        
        print(f"\n合計: {total}枚の画像が削除候補です")
        print(f"  ブレている画像: {total_blurry}枚")
        print(f"  類似画像: {total_similar}枚")
        print(f"  重複画像: {total_duplicate}枚")
        
        # 確認が必要な場合
        if confirm:
            response = input("\nこれらの画像を処理しますか？ (y/n): ")
            if response.lower() != 'y':
                print("処理を中止しました")
                return
        
        # 処理（削除または移動）
        processed = 0
        
        # ブレている画像の処理
        for img in self.blurry_images:
            if self.move_to:
                dest = self.move_to / "blurry" / img.name
                shutil.move(img, dest)
                print(f"移動: {img} -> {dest}")
            else:
                os.remove(img)
                print(f"削除: {img}")
            processed += 1
        
        # 類似画像の処理
        for _, similar_img in self.similar_images:
            if self.move_to:
                dest = self.move_to / "similar" / similar_img.name
                shutil.move(similar_img, dest)
                print(f"移動: {similar_img} -> {dest}")
            else:
                os.remove(similar_img)
                print(f"削除: {similar_img}")
            processed += 1
        
        # 重複画像の処理
        for _, duplicate_img in self.duplicate_images:
            if self.move_to:
                dest = self.move_to / "duplicate" / duplicate_img.name
                shutil.move(duplicate_img, dest)
                print(f"移動: {duplicate_img} -> {dest}")
            else:
                os.remove(duplicate_img)
                print(f"削除: {duplicate_img}")
            processed += 1
        
        print(f"\n処理完了: {processed}枚の画像を処理しました")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='画像クリーンアップシステム')
    parser.add_argument('directory', help='処理対象のディレクトリパス')
    parser.add_argument('--move-to', help='削除する代わりに移動する場合の移動先ディレクトリ')
    parser.add_argument('--no-confirm', action='store_true', help='確認なしで処理を実行')
    parser.add_argument('--blur-threshold', type=float, default=100.0, 
                        help='ブレ検出のしきい値（低いほど厳格）')
    parser.add_argument('--similarity-threshold', type=int, default=10, 
                        help='類似画像検出のしきい値（低いほど厳格）')
    
    args = parser.parse_args()
    
    # クリーンアップシステムを初期化
    cleanup_system = ImageCleanupSystem(
        args.directory, 
        args.move_to, 
        args.similarity_threshold
    )
    
    # ディレクトリを処理
    results = cleanup_system.process_directory()
    
    # 不要な画像を処理
    cleanup_system.cleanup(not args.no_confirm)


if __name__ == "__main__":
    main()