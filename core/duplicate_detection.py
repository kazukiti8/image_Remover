# core/duplicate_detection.py
import os
import hashlib
import time
from typing import Tuple, Optional, List, Dict, Any, Set # ★ Any を使用 ★

# ★ 型エイリアス ★
ErrorDict = Dict[str, str]
DuplicateDict = Dict[str, List[str]] # {hash: [path1, path2, ...]}
FindDuplicateResult = Tuple[DuplicateDict, List[ErrorDict]]

# --- ★★★ 仮の WorkerSignals クラス定義を削除 ★★★ ---
# class WorkerSignals: ...

def find_duplicate_files(directory_path: str,
                          file_extensions: Tuple[str, ...] = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.heic', '.heif'),
                          signals: Optional[Any] = None, # ★ 型ヒントを Optional[Any] に変更 ★
                          progress_offset: int = 0,
                          progress_range: int = 100) -> FindDuplicateResult:
    """
    指定されたディレクトリ内で完全に同一内容のファイル（重複ファイル）を見つけます。
    """
    errors: List[ErrorDict] = []
    duplicates: DuplicateDict = {}
    files_by_size: Dict[int, List[str]] = {}

    last_progress_emit_time: float = 0.0
    # ★ emit_progress 内の signals の型ヒントも Any に ★
    def emit_progress(current_value: int, total_value: int, stage_offset: int, stage_range: float, status_prefix: str) -> None:
        nonlocal last_progress_emit_time
        progress: int = stage_offset
        if total_value > 0: progress = stage_offset + int((current_value / total_value) * stage_range)
        status: str = f"{status_prefix} ({current_value}/{total_value})"
        current_time: float = time.time()
        # signals が None でなく、emit できるオブジェクトかチェック
        if signals and hasattr(signals, 'progress_update') and hasattr(signals, 'status_update') and \
           (current_value == total_value or current_time - last_progress_emit_time > 0.1):
             signals.progress_update.emit(progress) # type: ignore
             signals.status_update.emit(status)     # type: ignore
             last_progress_emit_time = current_time

    # --- 1. ファイルリストとサイズ取得 ---
    num_files: int = 0
    status_prefix_scan: str = "ファイルスキャン中(サイズ取得)"
    total_items: int = 1
    try: total_items = len(os.listdir(directory_path))
    except Exception: pass
    emit_progress(0, total_items, progress_offset, progress_range * 0.2, status_prefix_scan)

    processed_files_count: int = 0
    try:
        filename: str
        for filename in os.listdir(directory_path):
            if filename.lower().endswith(file_extensions):
                full_path: str = os.path.join(directory_path, filename)
                if os.path.isfile(full_path) and not os.path.islink(full_path):
                    try:
                        file_size: int = os.path.getsize(full_path)
                        if file_size > 0:
                            if file_size not in files_by_size: files_by_size[file_size] = []
                            files_by_size[file_size].append(full_path); num_files += 1
                    except OSError as e: errors.append({'type': 'ファイルサイズ取得', 'path': full_path, 'error': str(e)})
                    except Exception as e: errors.append({'type': 'ファイルサイズ取得(予期せぬ)', 'path': full_path, 'error': str(e)})
            processed_files_count += 1
            emit_progress(processed_files_count, total_items, progress_offset, progress_range * 0.2, status_prefix_scan)
    except OSError as e: print(f"エラー: ディレクトリ読み込み中にエラー ({directory_path}): {e}"); errors.append({'type': 'ディレクトリ読込', 'path': directory_path, 'error': str(e)}); return {}, errors
    except Exception as e: print(f"エラー: ファイルリスト取得中に予期せぬエラー ({directory_path}): {e}"); errors.append({'type': 'ファイルリスト取得', 'path': directory_path, 'error': str(e)}); return {}, errors

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
                try:
                    hasher = hashlib.md5()
                    with open(file_path, 'rb') as file:
                        while True:
                            chunk: bytes = file.read(8192)
                            if not chunk: break
                            hasher.update(chunk)
                    file_hash: str = hasher.hexdigest()
                    if file_hash not in hashes_by_size[size]: hashes_by_size[size][file_hash] = []
                    hashes_by_size[size][file_hash].append(file_path)
                except OSError as e: errors.append({'type': 'ファイル読込/ハッシュ計算', 'path': file_path, 'error': str(e)})
                except Exception as e: errors.append({'type': 'ハッシュ計算(予期せぬ)', 'path': file_path, 'error': str(e)})
                hashed_files_count += 1
                emit_progress(hashed_files_count, files_to_hash_count, hash_offset, hash_range, status_prefix_hash)

    # --- 3. 重複リスト作成 ---
    size: int; hashes: Dict[str, List[str]]
    for size, hashes in hashes_by_size.items():
        file_hash: str; file_list: List[str]
        for file_hash, file_list in hashes.items():
            if len(file_list) > 1:
                duplicates[file_hash] = sorted(file_list)

    print(f"重複チェック完了。{len(duplicates)} グループの重複ファイルが見つかりました。")
    # 完了時の最終進捗は emit_progress で送信される
    emit_progress(files_to_hash_count, files_to_hash_count, hash_offset, hash_range, status_prefix_hash)
    # if signals: signals.progress_update.emit(progress_offset + int(progress_range)) # 不要かも
    return duplicates, errors
