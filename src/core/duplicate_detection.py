# core/duplicate_detection.py
import os
import hashlib
import time
from typing import Tuple, Optional, List, Dict, Any, Set, Callable

try:
    from utils.cache_handler import CacheHandler
except ImportError:
    print("警告: utils.cache_handler のインポートに失敗しました。キャッシュ機能は無効になります。")
    CacheHandler = None

# 型エイリアス
ErrorDict = Dict[str, str]
DuplicateDict = Dict[str, List[str]]
FindDuplicateResult = Tuple[DuplicateDict, List[ErrorDict]]

def find_duplicate_files(image_paths: List[str],
                          signals: Optional[Any] = None,
                          progress_offset: int = 0,
                          progress_range: int = 100,
                          is_cancelled_func: Optional[Callable[[], bool]] = None,
                          cache_handler: Optional[CacheHandler] = None) -> FindDuplicateResult:
    """
    指定されたファイルパスリスト内で完全に同一内容のファイルを見つけます。
    エラーハンドリングを詳細化。
    """
    errors: List[ErrorDict] = []
    duplicates: DuplicateDict = {}
    files_by_size: Dict[int, List[str]] = {}

    last_progress_emit_time: float = 0.0
    def emit_progress(current_value: int, total_value: int, stage_offset: int, stage_range: float, status_prefix: str) -> None:
        nonlocal last_progress_emit_time; progress: int = stage_offset
        if total_value > 0: progress = stage_offset + int((current_value / total_value) * stage_range)
        status: str = f"{status_prefix} ({current_value}/{total_value})"
        current_time: float = time.time()
        if signals and hasattr(signals, 'progress_update') and hasattr(signals, 'status_update') and \
           (current_value == total_value or current_time - last_progress_emit_time > 0.1):
             signals.progress_update.emit(progress); signals.status_update.emit(status); last_progress_emit_time = current_time

    # --- 1. ファイルサイズでグループ化 ---
    num_files: int = len(image_paths)
    status_prefix_scan: str = "ファイルサイズ取得中"
    emit_progress(0, num_files, progress_offset, progress_range * 0.2, status_prefix_scan)
    processed_files_count: int = 0
    file_path: str
    for file_path in image_paths:
        filename = os.path.basename(file_path) # エラーメッセージ用
        if is_cancelled_func and is_cancelled_func(): return {}, errors
        try:
            # ★ isfile チェックを追加 (シンボリックリンクなどは除外) ★
            if os.path.isfile(file_path) and not os.path.islink(file_path):
                file_size: int = os.path.getsize(file_path)
                if file_size > 0: # 0バイトファイルは無視
                    if file_size not in files_by_size: files_by_size[file_size] = []
                    files_by_size[file_size].append(file_path)
            # else:
                # print(f"デバッグ: ファイルでないかリンクのためスキップ: {filename}")
        except FileNotFoundError:
             errors.append({'type': 'ファイルサイズ取得', 'path': filename, 'error': 'ファイルが見つかりません'})
        except PermissionError:
             errors.append({'type': 'ファイルサイズ取得', 'path': filename, 'error': 'アクセス権がありません'})
        except OSError as e:
            errors.append({'type': 'ファイルサイズ取得', 'path': filename, 'error': f'OSエラー: {e.strerror} (errno {e.errno})'})
        except Exception as e:
            errors.append({'type': 'ファイルサイズ取得(予期せぬ)', 'path': filename, 'error': f'{type(e).__name__}: {e}'})
        processed_files_count += 1
        emit_progress(processed_files_count, num_files, progress_offset, progress_range * 0.2, status_prefix_scan)
    print(f"{num_files} 個のファイルを検出。重複チェックを開始します...")

    # --- 2. ハッシュ計算と重複検出 ---
    hashes_by_size: Dict[int, Dict[str, List[str]]] = {}
    files_to_hash_count: int = sum(len(paths) for paths in files_by_size.values() if len(paths) > 1)
    hashed_files_count: int = 0
    status_prefix_hash: str = "ハッシュ計算中"
    hash_offset: int = progress_offset + int(progress_range * 0.2)
    hash_range: float = progress_range * 0.8
    emit_progress(0, files_to_hash_count, hash_offset, hash_range, status_prefix_hash)

    size: int; paths: List[str]
    for size, paths in files_by_size.items():
        if len(paths) > 1:
            if size not in hashes_by_size: hashes_by_size[size] = {}
            file_path: str
            for file_path in paths:
                filename = os.path.basename(file_path) # エラーメッセージ用
                if is_cancelled_func and is_cancelled_func():
                    if cache_handler: cache_handler.save_all()
                    return {}, errors

                file_hash: Optional[str] = None
                error_calculating = False

                # キャッシュチェック
                if cache_handler:
                    cached_hash = cache_handler.get('md5', file_path)
                    if cached_hash is not None:
                        file_hash = str(cached_hash)

                # キャッシュがない場合のみ計算
                if file_hash is None:
                    try:
                        hasher = hashlib.md5()
                        # ★ with open を使用 ★
                        with open(file_path, 'rb') as file:
                            while True:
                                if is_cancelled_func and is_cancelled_func(): raise InterruptedError("ハッシュ計算中に中断")
                                chunk: bytes = file.read(8192) # 8KBずつ読み込み
                                if not chunk: break
                                hasher.update(chunk)
                        file_hash = hasher.hexdigest()
                        if cache_handler:
                            cache_handler.put('md5', file_path, file_hash)
                    except InterruptedError:
                         print(f"ハッシュ計算が中断されました: {filename}")
                         if cache_handler: cache_handler.save_all()
                         return {}, errors
                    except FileNotFoundError:
                         errors.append({'type': 'ハッシュ計算', 'path': filename, 'error': 'ファイルが見つかりません'})
                         error_calculating = True
                    except PermissionError:
                         errors.append({'type': 'ハッシュ計算', 'path': filename, 'error': 'アクセス権がありません'})
                         error_calculating = True
                    except OSError as e:
                         errors.append({'type': 'ハッシュ計算', 'path': filename, 'error': f'ファイル読込OSエラー: {e.strerror} (errno {e.errno})'})
                         error_calculating = True
                    except MemoryError:
                         errors.append({'type': 'ハッシュ計算', 'path': filename, 'error': 'メモリ不足'})
                         error_calculating = True
                    except Exception as e:
                         errors.append({'type': 'ハッシュ計算(予期せぬ)', 'path': filename, 'error': f'{type(e).__name__}: {e}'})
                         error_calculating = True

                # ハッシュ取得成功時のみ辞書に追加
                if file_hash and not error_calculating:
                    if file_hash not in hashes_by_size[size]: hashes_by_size[size][file_hash] = []
                    hashes_by_size[size][file_hash].append(file_path)

                hashed_files_count += 1
                emit_progress(hashed_files_count, files_to_hash_count, hash_offset, hash_range, status_prefix_hash)

    # --- 3. 重複リスト作成 (変更なし) ---
    size: int; hashes: Dict[str, List[str]]
    for size, hashes in hashes_by_size.items():
        file_hash: str; file_list: List[str]
        for file_hash, file_list in hashes.items():
            if len(file_list) > 1:
                duplicates[file_hash] = sorted(file_list)

    print(f"重複チェック完了。{len(duplicates)} グループの重複ファイルが見つかりました。")
    emit_progress(files_to_hash_count, files_to_hash_count, hash_offset, hash_range, status_prefix_hash)

    if cache_handler:
        cache_handler.save_all()

    return duplicates, errors
