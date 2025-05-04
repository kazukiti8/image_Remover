# core/duplicate_detection.py
import os
import hashlib
import time
from typing import Tuple, Optional, List, Dict, Any, Set, Callable # ★ Callable をインポート ★

# 型エイリアス
ErrorDict = Dict[str, str]
DuplicateDict = Dict[str, List[str]]
FindDuplicateResult = Tuple[DuplicateDict, List[ErrorDict]]

# WorkerSignals は削除済み

def find_duplicate_files(image_paths: List[str],
                          file_extensions: Optional[Tuple[str, ...]] = None,
                          signals: Optional[Any] = None,
                          progress_offset: int = 0,
                          progress_range: int = 100,
                          is_cancelled_func: Optional[Callable[[], bool]] = None) -> FindDuplicateResult: # ★ is_cancelled_func を追加 ★
    """
    指定されたファイルパスリスト内で完全に同一内容のファイルを見つけます。
    中断チェックに対応。
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
        # ★ 中断チェック ★
        if is_cancelled_func and is_cancelled_func(): return {}, errors # 中断時は空の結果とエラーを返す

        try:
            if os.path.isfile(file_path):
                file_size: int = os.path.getsize(file_path)
                if file_size > 0:
                    if file_size not in files_by_size: files_by_size[file_size] = []
                    files_by_size[file_size].append(file_path)
        except OSError as e: errors.append({'type': 'ファイルサイズ取得', 'path': file_path, 'error': str(e)})
        except Exception as e: errors.append({'type': 'ファイルサイズ取得(予期せぬ)', 'path': file_path, 'error': str(e)})
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
                # ★ 中断チェック ★
                if is_cancelled_func and is_cancelled_func(): return {}, errors

                try:
                    hasher = hashlib.md5()
                    with open(file_path, 'rb') as file:
                        while True:
                            # ★ 中断チェック (ファイル読み込み中) ★
                            if is_cancelled_func and is_cancelled_func(): raise InterruptedError("ハッシュ計算中に中断")
                            chunk: bytes = file.read(8192)
                            if not chunk: break
                            hasher.update(chunk)
                    file_hash: str = hasher.hexdigest()
                    if file_hash not in hashes_by_size[size]: hashes_by_size[size][file_hash] = []
                    hashes_by_size[size][file_hash].append(file_path)
                except InterruptedError: # ★ 中断例外をキャッチ ★
                     print(f"ハッシュ計算が中断されました: {file_path}")
                     return {}, errors # 中断時はエラーリストだけ返す
                except OSError as e: errors.append({'type': 'ファイル読込/ハッシュ計算', 'path': file_path, 'error': str(e)})
                except Exception as e: errors.append({'type': 'ハッシュ計算(予期せぬ)', 'path': file_path, 'error': str(e)})

                hashed_files_count += 1
                # 進捗は中断チェック後に行う
                emit_progress(hashed_files_count, files_to_hash_count, hash_offset, hash_range, status_prefix_hash)

    # --- 3. 重複リスト作成 ---
    size: int; hashes: Dict[str, List[str]]
    for size, hashes in hashes_by_size.items():
        file_hash: str; file_list: List[str]
        for file_hash, file_list in hashes.items():
            if len(file_list) > 1:
                duplicates[file_hash] = sorted(file_list)

    print(f"重複チェック完了。{len(duplicates)} グループの重複ファイルが見つかりました。")
    emit_progress(files_to_hash_count, files_to_hash_count, hash_offset, hash_range, status_prefix_hash)
    return duplicates, errors
