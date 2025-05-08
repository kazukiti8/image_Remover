# utils/cache_handler.py
import os
import json
import time
from typing import Dict, Any, Optional, Tuple

CACHE_DIR_NAME = ".image_cleaner_cache"
MD5_CACHE_FILENAME = "md5_cache.json"
PHASH_CACHE_FILENAME = "phash_cache.json"

# キャッシュエントリーの型: (value, modification_time)
CacheEntry = Tuple[Any, float]
# キャッシュ全体の型: { file_path: CacheEntry }
CacheData = Dict[str, CacheEntry]

class CacheHandler:
    """
    ファイルベースのシンプルなキャッシュ（MD5, pHashなど）を管理するクラス。
    キャッシュはスキャン対象ディレクトリ内の隠しフォルダに保存される。
    """
    def __init__(self, target_directory: str):
        """
        Args:
            target_directory (str): スキャン対象のディレクトリパス。
        """
        if not os.path.isdir(target_directory):
            raise ValueError(f"指定されたディレクトリが存在しません: {target_directory}")
        self.cache_dir = os.path.join(target_directory, CACHE_DIR_NAME)
        self.md5_cache_path = os.path.join(self.cache_dir, MD5_CACHE_FILENAME)
        self.phash_cache_path = os.path.join(self.cache_dir, PHASH_CACHE_FILENAME)
        self._md5_cache: Optional[CacheData] = None
        self._phash_cache: Optional[CacheData] = None
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        """キャッシュディレクトリが存在することを確認・作成する"""
        try:
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir)
                # Windowsで隠し属性を設定 (任意)
                if os.name == 'nt':
                    try:
                        import ctypes
                        FILE_ATTRIBUTE_HIDDEN = 0x02
                        ctypes.windll.kernel32.SetFileAttributesW(self.cache_dir, FILE_ATTRIBUTE_HIDDEN)
                    except Exception as e:
                        print(f"情報: キャッシュディレクトリの隠し属性設定に失敗: {e}")
        except OSError as e:
            print(f"警告: キャッシュディレクトリの作成に失敗しました: {e}")
            # キャッシュディレクトリが作成できない場合、キャッシュ機能は無効になる

    def _load_cache(self, cache_path: str) -> CacheData:
        """指定されたパスからキャッシュデータを読み込む"""
        if not os.path.exists(cache_path):
            return {}
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # 簡単な形式チェック (値がリスト/タプルで長さ2か)
                    valid_data = {k: tuple(v) for k, v in data.items() if isinstance(v, (list, tuple)) and len(v) == 2}
                    return valid_data
                else:
                    print(f"警告: キャッシュファイル形式が無効です (非dict): {cache_path}")
                    return {}
        except json.JSONDecodeError as e:
            print(f"警告: キャッシュファイルの読み込みに失敗 (JSONDecodeError: {e}): {cache_path}")
            return {}
        except OSError as e:
            print(f"警告: キャッシュファイルの読み込みに失敗 (OSError: {e}): {cache_path}")
            return {}
        except Exception as e:
            print(f"警告: キャッシュファイルの読み込み中に予期せぬエラー ({type(e).__name__}: {e}): {cache_path}")
            return {}

    def _save_cache(self, cache_path: str, cache_data: CacheData) -> bool:
        """指定されたパスにキャッシュデータを保存する"""
        if not os.path.exists(self.cache_dir):
            print("警告: キャッシュディレクトリが存在しないため、キャッシュを保存できません。")
            return False
        try:
            # CacheEntry のタプルをリストに変換して保存 (JSON互換性)
            data_to_save = {k: list(v) for k, v in cache_data.items()}
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            return True
        except OSError as e:
            print(f"警告: キャッシュファイルの保存に失敗 (OSError: {e}): {cache_path}")
            return False
        except TypeError as e:
            print(f"警告: キャッシュデータのJSONシリアライズ失敗 (TypeError: {e}): {cache_path}")
            return False
        except Exception as e:
            print(f"警告: キャッシュファイル保存中に予期せぬエラー ({type(e).__name__}: {e}): {cache_path}")
            return False

    def _get_cache(self, cache_type: str) -> CacheData:
        """指定されたタイプのキャッシュデータをロード（またはメモリから取得）"""
        if cache_type == 'md5':
            if self._md5_cache is None:
                self._md5_cache = self._load_cache(self.md5_cache_path)
            return self._md5_cache
        elif cache_type == 'phash':
            if self._phash_cache is None:
                self._phash_cache = self._load_cache(self.phash_cache_path)
            return self._phash_cache
        else:
            raise ValueError(f"未対応のキャッシュタイプ: {cache_type}")

    def _save_cache_data(self, cache_type: str):
        """指定されたタイプのキャッシュデータをファイルに保存"""
        if cache_type == 'md5' and self._md5_cache is not None:
            self._save_cache(self.md5_cache_path, self._md5_cache)
        elif cache_type == 'phash' and self._phash_cache is not None:
            self._save_cache(self.phash_cache_path, self._phash_cache)

    def get(self, cache_type: str, file_path: str) -> Optional[Any]:
        """
        キャッシュから値を取得する。ファイルの最終更新日時をチェックする。

        Args:
            cache_type (str): 'md5' または 'phash'.
            file_path (str): 対象ファイルのパス。

        Returns:
            Optional[Any]: キャッシュされた値 (有効な場合)。無効または存在しない場合は None。
        """
        try:
            current_mtime = os.path.getmtime(file_path)
            cache = self._get_cache(cache_type)
            if file_path in cache:
                cached_value, cached_mtime = cache[file_path]
                # 更新日時が一致すれば有効なキャッシュとみなす
                if abs(current_mtime - cached_mtime) < 1e-6: # float比較の許容誤差
                    return cached_value
                else:
                    # 更新日時が異なる場合はキャッシュを削除
                    del cache[file_path]
                    print(f"キャッシュ無効 (更新日時不一致): {os.path.basename(file_path)}")
        except FileNotFoundError:
            # ファイルが存在しない場合はキャッシュも無効
            cache = self._get_cache(cache_type)
            if file_path in cache:
                del cache[file_path]
            return None
        except Exception as e:
            print(f"警告: キャッシュ取得中にエラー ({type(e).__name__}: {e}): {file_path}")
        return None

    def put(self, cache_type: str, file_path: str, value: Any):
        """
        計算結果をキャッシュに保存する。ファイルの最終更新日時も記録する。

        Args:
            cache_type (str): 'md5' または 'phash'.
            file_path (str): 対象ファイルのパス。
            value (Any): キャッシュする値。
        """
        try:
            current_mtime = os.path.getmtime(file_path)
            cache = self._get_cache(cache_type)
            cache[file_path] = (value, current_mtime)
        except FileNotFoundError:
            print(f"警告: キャッシュ保存中にファイルが見つかりません: {file_path}")
        except Exception as e:
            print(f"警告: キャッシュ保存中にエラー ({type(e).__name__}: {e}): {file_path}")

    def save_all(self):
        """メモリ上の全てのキャッシュデータをファイルに保存する"""
        print("キャッシュデータをファイルに保存中...")
        self._save_cache_data('md5')
        self._save_cache_data('phash')
        print("キャッシュデータの保存完了。")

    def clear_all(self):
        """メモリ上のキャッシュをクリアし、キャッシュファイルを削除する"""
        print("全てのキャッシュをクリアしています...")
        self._md5_cache = {}
        self._phash_cache = {}
        try:
            if os.path.exists(self.md5_cache_path):
                os.remove(self.md5_cache_path)
            if os.path.exists(self.phash_cache_path):
                os.remove(self.phash_cache_path)
            # ディレクトリが空なら削除 (任意)
            if os.path.exists(self.cache_dir) and not os.listdir(self.cache_dir):
                os.rmdir(self.cache_dir)
            print("キャッシュのクリア完了。")
        except OSError as e:
            print(f"警告: キャッシュファイルの削除中にエラー: {e}")

