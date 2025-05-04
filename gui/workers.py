# gui/workers.py
import os
import time
from PySide6.QtCore import QRunnable, Signal, QObject, Slot

# --- コアロジックの関数をインポート ---
try:
    from core.blur_detection import calculate_fft_blur_score_v2
    from core.similarity_detection import find_similar_pairs
    from core.duplicate_detection import find_duplicate_files
except ImportError as e:
    print(f"エラー: core モジュールのインポートに失敗しました。({e}) ダミー関数を使用します。")
    # ダミー関数
    def calculate_fft_blur_score_v2(path, ratio=0.05):
        if "error" in path.lower(): return None, "ダミーエラー(ブレ)"
        return (0.5, None) if "blur" in path.lower() else (0.9, None)
    def find_similar_pairs(dir_path, signals=None, progress_offset=0, progress_range=100, **kwargs):
        hash_threshold = kwargs.get('hash_threshold', 5); use_phash = kwargs.get('use_phash', True)
        print(f"(ダミー) find_similar_pairs: hash_threshold={hash_threshold}, use_phash={use_phash}")
        if signals:
            total_dummy_ops = 50; status_prefix = "類似ペア検出中(ダミー)"
            for i in range(total_dummy_ops + 1):
                time.sleep(0.03); progress = progress_offset + int((i / total_dummy_ops) * progress_range)
                status = f"{status_prefix} ({i}/{total_dummy_ops})"; signals.progress_update.emit(progress); signals.status_update.emit(status)
        def _dummy_pair(dir_p, f1, f2, score): p1,p2=os.path.join(dir_p,f1),os.path.join(dir_p,f2); return (p1,p2,score) if os.path.exists(p1) and os.path.exists(p2) else None
        pairs = []; comp_errors = []; file_errors = []
        p = _dummy_pair(dir_path, "A.jpg", "B.jpg", 95); p and pairs.append(p)
        p = _dummy_pair(dir_path, "A.jpg", "C.jpg", 92); p and pairs.append(p)
        err_p1 = os.path.join(dir_path, "Error1.jpg"); err_p2 = os.path.join(dir_path, "Error2.jpg")
        if os.path.exists(err_p1) and os.path.exists(err_p2): comp_errors.append({'type': 'ORB比較', 'path1': err_p1, 'path2': err_p2, 'error': 'ダミー比較エラー'})
        err_hash = os.path.join(dir_path, "HashError.png");
        if os.path.exists(err_hash): comp_errors.append({'type': 'pHash計算', 'path': err_hash, 'error': 'ダミーpHashエラー'})
        return pairs, comp_errors, file_errors # 戻り値は3つ
    def find_duplicate_files(dir_path, signals=None, progress_offset=0, progress_range=100, **kwargs):
        print("(ダミー) find_duplicate_files")
        if signals:
            total_dummy_ops = 30; status_prefix = "重複ファイル検出中(ダミー)"
            for i in range(total_dummy_ops + 1):
                time.sleep(0.02); progress = progress_offset + int((i / total_dummy_ops) * progress_range)
                status = f"{status_prefix} ({i}/{total_dummy_ops})"; signals.progress_update.emit(progress); signals.status_update.emit(status)
        dup_path1 = os.path.join(dir_path, "Dup1A.jpg"); dup_path2 = os.path.join(dir_path, "Dup1B.jpg")
        dup_path3 = os.path.join(dir_path, "Dup2A.png"); dup_path4 = os.path.join(dir_path, "Dup2B.png")
        duplicates = {}; errors = []
        if os.path.exists(dup_path1) and os.path.exists(dup_path2): duplicates['dummyhash1'] = [dup_path1, dup_path2]
        if os.path.exists(dup_path3) and os.path.exists(dup_path4): duplicates['dummyhash2'] = [dup_path3, dup_path4]
        err_dup = os.path.join(dir_path, "DupError.gif")
        if os.path.exists(err_dup): errors.append({'type': 'ファイル読込/ハッシュ計算', 'path': err_dup, 'error': 'ダミー重複検出エラー'})
        return duplicates, errors # 戻り値は2つ


# === バックグラウンド処理用のシグナル定義 ===
class WorkerSignals(QObject):
    status_update = Signal(str)
    progress_update = Signal(int)
    # ★★★ 修正点: シグナルの定義を確認 ★★★
    # blurry(list), similar(list), duplicates(dict), errors(list) の4つを渡す
    results_ready = Signal(list, list, dict, list)
    error = Signal(str)
    finished = Signal()

# === バックグラウンド処理実行クラス ===
class ScanWorker(QRunnable):
    def __init__(self, directory_path, settings):
        super().__init__()
        self.directory_path = directory_path
        self.settings = settings
        self.signals = WorkerSignals()
        self.file_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.heic', '.heif')

    @Slot()
    def run(self):
        processing_errors = []
        start_time = time.time()
        PROGRESS_FILE_LIST = 5; PROGRESS_BLUR_DETECT = 30; PROGRESS_DUPLICATE_DETECT = 20; PROGRESS_SIMILAR_DETECT = 45
        current_progress = 0

        try:
            # --- 0. ファイルリスト取得 ---
            self.signals.status_update.emit("ファイルリスト取得中...")
            image_paths = []
            try:
                for filename in os.listdir(self.directory_path):
                    if filename.lower().endswith(self.file_extensions):
                        full_path = os.path.join(self.directory_path, filename)
                        if os.path.isfile(full_path) and not os.path.islink(full_path): image_paths.append(full_path)
            except OSError as e: self.signals.error.emit(f"ディレクトリ読み込みエラー: {e}"); self.signals.finished.emit(); return
            except Exception as e: self.signals.error.emit(f"ファイルリスト取得エラー: {e}"); self.signals.finished.emit(); return

            if not image_paths:
                self.signals.status_update.emit("対象ディレクトリに画像ファイルが見つかりませんでした。")
                self.signals.results_ready.emit([], [], {}, processing_errors) # 4つの引数
                self.signals.finished.emit(); return

            num_images = len(image_paths); blurry_results = []; similar_pair_results = []; duplicate_results = {}
            current_progress = PROGRESS_FILE_LIST; self.signals.progress_update.emit(current_progress)

            # --- 1. ブレ検出 ---
            blur_threshold = self.settings.get('blur_threshold', 0.80); status_prefix_blur = "ブレ検出中"
            self.signals.status_update.emit(f"{status_prefix_blur} (閾値: {blur_threshold:.4f}) (0/{num_images})"); last_blur_emit_time = 0
            for i, img_path in enumerate(image_paths):
                score, error_msg = calculate_fft_blur_score_v2(img_path)
                if error_msg is not None: processing_errors.append({'type': 'ブレ検出', 'path': img_path, 'error': error_msg})
                elif score is not None and score <= blur_threshold: blurry_results.append({"path": img_path, "score": score})
                progress = current_progress + int(((i + 1) / num_images) * PROGRESS_BLUR_DETECT); current_time = time.time()
                if (i + 1) == num_images or current_time - last_blur_emit_time > 0.1:
                     self.signals.progress_update.emit(progress); self.signals.status_update.emit(f"{status_prefix_blur} ({i+1}/{num_images})"); last_blur_emit_time = current_time
            current_progress += PROGRESS_BLUR_DETECT; self.signals.progress_update.emit(current_progress)

            # --- 2. 重複ファイル検出 ---
            self.signals.status_update.emit("重複ファイル検出中...")
            try:
                duplicate_results, duplicate_errors = find_duplicate_files(
                    self.directory_path, file_extensions=self.file_extensions, signals=self.signals,
                    progress_offset=current_progress, progress_range=PROGRESS_DUPLICATE_DETECT
                )
                processing_errors.extend(duplicate_errors)
            except Exception as e:
                processing_errors.append({'type': '重複検出(致命的)', 'path': self.directory_path, 'error': str(e)})
                print(f"エラー: 重複ファイル検出中に予期せぬエラー: {e}"); duplicate_results = {}
            current_progress += PROGRESS_DUPLICATE_DETECT; self.signals.progress_update.emit(current_progress)
            self.signals.status_update.emit(f"重複ファイル検出完了 ({len(duplicate_results)}グループ)")

            # --- 3. 類似ペア検出 ---
            orb_nfeatures = self.settings.get('orb_nfeatures', 1500); orb_ratio_threshold = self.settings.get('orb_ratio_threshold', 0.70)
            min_good_matches = self.settings.get('min_good_matches', 40); hash_threshold = self.settings.get('hash_threshold', 5)
            use_phash = self.settings.get('use_phash', True); status_msg = f"類似ペア検出中 (pHash={'ON' if use_phash else 'OFF'}, ...)"
            self.signals.status_update.emit(status_msg)
            try:
                # find_similar_pairs の戻り値は (similar_pairs, comparison_errors, file_list_errors) の3つ
                similar_pair_results, comparison_errors, _ = find_similar_pairs(
                    self.directory_path, orb_nfeatures=orb_nfeatures, orb_ratio_threshold=orb_ratio_threshold,
                    min_good_matches_threshold=min_good_matches, hash_threshold=hash_threshold,
                    use_phash=use_phash, file_extensions=self.file_extensions, signals=self.signals,
                    progress_offset=current_progress, progress_range=PROGRESS_SIMILAR_DETECT
                )
                processing_errors.extend(comparison_errors)
            except Exception as e: self.signals.error.emit(f"類似ペア検出処理中に致命的なエラー: {e}"); self.signals.finished.emit(); return
            current_progress = 100; self.signals.progress_update.emit(current_progress)
            self.signals.status_update.emit(f"類似ペア検出完了 ({len(similar_pair_results)}ペア発見)")

            # --- 4. 結果通知 ---
            end_time = time.time()
            print(f"スキャン処理完了。所要時間: {end_time - start_time:.2f} 秒")
            # ★★★ 修正点: emit する引数の数を確認 ★★★
            # blurry_results(list), similar_pair_results(list), duplicate_results(dict), processing_errors(list) の4つ
            self.signals.results_ready.emit(blurry_results, similar_pair_results, duplicate_results, processing_errors)

        except Exception as e:
            self.signals.error.emit(f"スキャン中に予期せぬエラーが発生しました: {e}")
        finally:
            self.signals.finished.emit()
