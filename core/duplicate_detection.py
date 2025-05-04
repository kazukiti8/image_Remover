# core/duplicate_detection.py
import os
import hashlib
import time # 進捗表示用

def find_duplicate_files(directory_path,
                          file_extensions=('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.heic', '.heif'),
                          signals=None,
                          progress_offset=0,
                          progress_range=100):
    """
    指定されたディレクトリ内で完全に同一内容のファイル（重複ファイル）を見つけます。
    ファイルサイズとMD5ハッシュで比較します。

    Args:
        directory_path (str): スキャン対象のディレクトリパス。
        file_extensions (tuple): スキャン対象とするファイルの拡張子。
        signals (WorkerSignals, optional): 進捗通知用のシグナルオブジェクト。
        progress_offset (int): 全体進捗におけるこの処理の開始オフセット(0-100)。
        progress_range (int): 全体進捗におけるこの処理が占める範囲(0-100)。

    Returns:
        tuple: (dict, list)
               - duplicates (dict): 重複ファイルの情報。キーがハッシュ値、値が重複ファイルパスのリスト。
                                    例: {'hash1': [path_a, path_b], 'hash2': [path_c, path_d, path_e]}
               - errors (list): 処理中に発生したエラー情報のリスト。
                                [{'type': 'ファイル読込/ハッシュ計算', 'path': path, 'error': msg}, ...]
    """
    errors = []
    duplicates = {} # {hash: [path1, path2, ...]}
    files_by_size = {} # {size: [path1, path2, ...]}

    # --- 進捗通知ヘルパー ---
    last_progress_emit_time = 0
    def emit_progress(current_value, total_value, stage_offset, stage_range, status_prefix):
        nonlocal last_progress_emit_time
        progress = stage_offset
        if total_value > 0:
            progress = stage_offset + int((current_value / total_value) * stage_range)
        status = f"{status_prefix} ({current_value}/{total_value})"
        current_time = time.time()
        if signals and (current_value == total_value or current_time - last_progress_emit_time > 0.1):
             signals.progress_update.emit(progress)
             signals.status_update.emit(status)
             last_progress_emit_time = current_time

    # --- 1. ファイルリストとサイズ取得 ---
    num_files = 0
    status_prefix_scan = "ファイルスキャン中(サイズ取得)"
    # まずディレクトリ内のファイル数を大まかにカウント (正確でなくても良い)
    try:
        total_items = len(os.listdir(directory_path))
    except Exception:
        total_items = 1 # エラー時は仮の値
    emit_progress(0, total_items, progress_offset, progress_range * 0.2, status_prefix_scan) # サイズ取得は20%目安

    processed_files_count = 0
    try:
        for filename in os.listdir(directory_path):
            if filename.lower().endswith(file_extensions):
                full_path = os.path.join(directory_path, filename)
                if os.path.isfile(full_path) and not os.path.islink(full_path):
                    try:
                        file_size = os.path.getsize(full_path)
                        if file_size > 0: # 0バイトファイルは無視
                            if file_size not in files_by_size:
                                files_by_size[file_size] = []
                            files_by_size[file_size].append(full_path)
                            num_files += 1
                    except OSError as e:
                        errors.append({'type': 'ファイルサイズ取得', 'path': full_path, 'error': str(e)})
                    except Exception as e:
                         errors.append({'type': 'ファイルサイズ取得(予期せぬ)', 'path': full_path, 'error': str(e)})
            processed_files_count += 1
            # listdir() の項目数で進捗を更新
            emit_progress(processed_files_count, total_items, progress_offset, progress_range * 0.2, status_prefix_scan)

    except OSError as e:
        print(f"エラー: ディレクトリ読み込み中にエラーが発生しました ({directory_path}): {e}")
        errors.append({'type': 'ディレクトリ読込', 'path': directory_path, 'error': str(e)})
        return {}, errors # ここで終了
    except Exception as e:
        print(f"エラー: ファイルリスト取得中に予期せぬエラーが発生しました ({directory_path}): {e}")
        errors.append({'type': 'ファイルリスト取得', 'path': directory_path, 'error': str(e)})
        return {}, errors

    print(f"{num_files} 個のファイルを検出。重複チェックを開始します...")

    # --- 2. ハッシュ計算と重複検出 ---
    hashes_by_size = {} # {size: {hash: [path1, path2, ...]}}
    files_to_hash_count = 0
    # 同じサイズのファイルが複数あるものだけをカウント
    for size, paths in files_by_size.items():
        if len(paths) > 1:
            files_to_hash_count += len(paths)

    hashed_files_count = 0
    status_prefix_hash = "ハッシュ計算中"
    hash_offset = progress_offset + progress_range * 0.2 # サイズ取得後から開始
    hash_range = progress_range * 0.8 # 残り80%
    emit_progress(0, files_to_hash_count, hash_offset, hash_range, status_prefix_hash)

    # サイズが同じファイルが複数あるグループのみ処理
    for size, paths in files_by_size.items():
        if len(paths) > 1:
            if size not in hashes_by_size:
                hashes_by_size[size] = {}
            for file_path in paths:
                try:
                    # MD5ハッシュを計算 (メモリ効率のためチャンクで読み込み)
                    hasher = hashlib.md5()
                    with open(file_path, 'rb') as file:
                        while True:
                            chunk = file.read(8192) # 8KBずつ読み込み
                            if not chunk:
                                break
                            hasher.update(chunk)
                    file_hash = hasher.hexdigest()

                    # ハッシュ値をキーとしてパスを格納
                    if file_hash not in hashes_by_size[size]:
                        hashes_by_size[size][file_hash] = []
                    hashes_by_size[size][file_hash].append(file_path)

                except OSError as e:
                    errors.append({'type': 'ファイル読込/ハッシュ計算', 'path': file_path, 'error': str(e)})
                except Exception as e:
                     errors.append({'type': 'ハッシュ計算(予期せぬ)', 'path': file_path, 'error': str(e)})

                hashed_files_count += 1
                emit_progress(hashed_files_count, files_to_hash_count, hash_offset, hash_range, status_prefix_hash)

    # --- 3. 重複リスト作成 ---
    # ハッシュが同じファイルが複数あるものを抽出
    for size, hashes in hashes_by_size.items():
        for file_hash, file_list in hashes.items():
            if len(file_list) > 1:
                duplicates[file_hash] = sorted(file_list) # パスをソートして格納

    print(f"重複チェック完了。{len(duplicates)} グループの重複ファイルが見つかりました。")
    # 完了時に最終進捗を送信
    if signals: signals.progress_update.emit(progress_offset + progress_range)
    return duplicates, errors
