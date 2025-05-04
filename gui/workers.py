# gui/workers.py
import os
import time
import json
import concurrent.futures
from PySide6.QtCore import QRunnable, Signal, QObject, Slot
from PySide6.QtWidgets import QApplication
from typing import Tuple, Optional, List, Dict, Any, Union, Set, Callable

# 型エイリアス (変更なし)
SettingsDict = Dict[str, Union[float, bool, int, str]]
BlurResultItem = Dict[str, Union[str, float]]
SimilarPair = Tuple[str, str, int]
DuplicateDict = Dict[str, List[str]]
ErrorDict = Dict[str, str]
ScanStateData = Dict[str, Any]
BlurResult = Tuple[Optional[float], Optional[str]]
BlurTaskResult = Tuple[str, Optional[float], Optional[str]]

# --- コアロジックの関数をインポート (変更なし) ---
try:
    from core.blur_detection import calculate_fft_blur_score_v2, calculate_laplacian_variance
    from core.similarity_detection import find_similar_pairs
    from core.duplicate_detection import find_duplicate_files
    FindSimilarResult = Tuple[List[SimilarPair], List[ErrorDict], List[ErrorDict]]
    FindDuplicateResult = Tuple[DuplicateDict, List[ErrorDict]]
except ImportError as e:
    print(f"エラー: core モジュールのインポートに失敗しました。({e}) ダミー関数を使用します。")
    def calculate_fft_blur_score_v2(path: str, ratio: float = 0.05) -> BlurResult: return (0.5, None) if "blur" in path.lower() else (0.9, None)
    def calculate_laplacian_variance(path: str) -> BlurResult: return (150.0, None) if "blur" in path.lower() else (50.0, None)
    def find_similar_pairs(image_paths: List[str], duplicate_paths_set: Set[str], similarity_mode: str = 'phash_orb', signals: Optional[Any] = None, progress_offset: int = 0, progress_range: int = 100, **kwargs: Any) -> FindSimilarResult: return [], [], []
    def find_duplicate_files(image_paths: List[str], signals: Optional[Any] = None, progress_offset: int = 0, progress_range: int = 100, **kwargs: Any) -> FindDuplicateResult: return {}, []

# --- 状態ハンドラ関数をインポート (変更なし) ---
try:
    from utils.results_handler import save_scan_state, load_scan_state, delete_scan_state, get_state_filepath
except ImportError:
    print("エラー: utils.results_handler から状態管理関数のインポートに失敗しました。")
    def save_scan_state(dir_path: str, state_data: ScanStateData) -> bool: print("警告: 状態保存機能が無効"); return False
    def load_scan_state(dir_path: str) -> Tuple[Optional[ScanStateData], Optional[str]]: print("警告: 状態読み込み機能が無効"); return None, "状態読み込み機能が無効です"
    def delete_scan_state(dir_path: str) -> bool: print("警告: 状態削除機能が無効"); return False
    def get_state_filepath(dir_path: str) -> str: return os.path.join(dir_path, ".image_cleaner_scan_state.json")

# --- CacheHandler をインポート (変更なし) ---
try:
    from utils.cache_handler import CacheHandler
except ImportError:
    print("警告: utils.cache_handler のインポートに失敗しました。キャッシュ機能は無効になります。")
    CacheHandler = None

# === バックグラウンド処理用のシグナル定義 ===
class WorkerSignals(QObject):
    """バックグラウンド処理からのシグナルを定義するクラス"""
    status_update = Signal(str)       # 全体的なステータスメッセージ (例: "ブレ検出中 (50/100)")
    progress_update = Signal(int)     # プログレスバーの更新 (0-100)
    # ★★★ 現在処理中のファイル名を通知するシグナルを追加 ★★★
    processing_file = Signal(str)     # 現在処理中のファイル名 (basename)
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
    results_ready = Signal(list, list, dict, list) # (blurry, similar, duplicates, errors)
    error = Signal(str)               # 致命的なエラーメッセージ
    finished = Signal()               # 正常完了
    cancelled = Signal()              # 中断完了

# === バックグラウンド処理実行クラス ===
class ScanWorker(QRunnable):
    """画像のスキャン処理をバックグラウンドで実行するクラス"""
    def __init__(self, directory_path: str, settings: SettingsDict, initial_state: Optional[ScanStateData] = None):
        super().__init__()
        self.directory_path: str = directory_path
        self.settings: SettingsDict = settings
        self.signals: WorkerSignals = WorkerSignals()
        self.file_extensions: Tuple[str, ...] = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.heic', '.heif')
        self._cancellation_requested: bool = False
        self.state_save_interval: int = 100
        self.max_workers: Optional[int] = os.cpu_count()

        self.cache_handler: Optional[CacheHandler] = None
        if CacheHandler:
            try:
                self.cache_handler = CacheHandler(self.directory_path)
                print(f"キャッシュハンドラを初期化しました: {self.cache_handler.cache_dir}")
            except ValueError as e: print(f"警告: キャッシュハンドラの初期化に失敗: {e}")
            except Exception as e: print(f"警告: キャッシュハンドラの初期化中に予期せぬエラー: {e}")

        # --- 状態変数 (変更なし) ---
        self.initial_state: Optional[ScanStateData] = initial_state
        self.all_image_paths: List[str] = []
        self.blurry_results: List[BlurResultItem] = []
        self.duplicate_results: DuplicateDict = {}
        self.similar_pair_results: List[SimilarPair] = []
        self.processing_errors: List[ErrorDict] = []
        self.processed_paths_blur: Set[str] = set()
        self.processed_hashes: Dict[str, str] = {}
        self.compared_pairs_similar: Set[Tuple[str, str]] = set()

        if self.initial_state:
            self._load_state_from_data(self.initial_state)
            print("中断されたスキャン状態をロードしました。")

    def _load_state_from_data(self, state_data: ScanStateData) -> None:
        # (変更なし)
        self.all_image_paths = state_data.get("all_image_paths", [])
        self.blurry_results = state_data.get("blurry_results", [])
        self.duplicate_results = state_data.get("duplicate_results", {})
        self.similar_pair_results = state_data.get("similar_pair_results", [])
        self.processing_errors = state_data.get("processing_errors", [])
        processed_blur = state_data.get("processed_paths_blur")
        self.processed_paths_blur = set(processed_blur) if isinstance(processed_blur, (list, set)) else set()
        processed_hashes = state_data.get("processed_hashes")
        self.processed_hashes = processed_hashes if isinstance(processed_hashes, dict) else {}
        compared_similar = state_data.get("compared_pairs_similar")
        if isinstance(compared_similar, list):
             try: self.compared_pairs_similar = set(tuple(sorted(pair)) for pair in compared_similar if len(pair)==2)
             except TypeError: self.compared_pairs_similar = set()
        else: self.compared_pairs_similar = set()

    def _save_state(self) -> bool:
        # (変更なし)
        state_data: ScanStateData = {
            "target_directory": self.directory_path, "settings_used": self.settings,
            "all_image_paths": self.all_image_paths, "processed_paths_blur": self.processed_paths_blur,
            "processed_hashes": self.processed_hashes, "compared_pairs_similar": self.compared_pairs_similar,
            "blurry_results": self.blurry_results, "duplicate_results": self.duplicate_results,
            "similar_pair_results": self.similar_pair_results, "processing_errors": self.processing_errors
        }
        if self.cache_handler: self.cache_handler.save_all()
        return save_scan_state(self.directory_path, state_data)

    def request_cancellation(self) -> None:
        # (変更なし)
        if not self._cancellation_requested:
            print("スキャン中止要求を受け付けました。状態とキャッシュを保存します...")
            self._cancellation_requested = True
            if self._save_state(): print("状態とキャッシュの保存に成功しました。")
            else: print("警告: 状態またはキャッシュの保存に失敗しました。")

    def _list_image_files(self, scan_subdirs: bool) -> Tuple[List[str], Optional[str]]:
        # (変更なし)
        if self.initial_state and self.all_image_paths:
            print("状態ファイルからファイルリストを復元します。")
            self.signals.status_update.emit(f"ファイルリスト復元完了 ({len(self.all_image_paths)} files)")
            return self.all_image_paths, None
        image_paths: List[str] = []; error_msg: Optional[str] = None; processed_dirs: int = 0
        status_prefix: str = "ファイルリスト作成中"; self.signals.status_update.emit(f"{status_prefix}...")
        try:
            if scan_subdirs:
                for root, dirs, files in os.walk(self.directory_path):
                    if self._cancellation_requested: return [], "処理が中断されました。"
                    processed_dirs += 1
                    if processed_dirs % 10 == 0: self.signals.status_update.emit(f"{status_prefix} ({processed_dirs} Dirs)..."); QApplication.processEvents()
                    for filename in files:
                        if filename.lower().endswith(self.file_extensions):
                            full_path: str = os.path.join(root, filename)
                            if os.path.isfile(full_path): image_paths.append(full_path)
            else:
                for i, filename in enumerate(os.listdir(self.directory_path)):
                    if self._cancellation_requested: return [], "処理が中断されました。"
                    if i % 100 == 0: QApplication.processEvents()
                    if filename.lower().endswith(self.file_extensions):
                        full_path = os.path.join(self.directory_path, filename)
                        if os.path.isfile(full_path) and not os.path.islink(full_path): image_paths.append(full_path)
        except OSError as e: error_msg = f"ディレクトリ読み込みエラー: {e}"
        except Exception as e: error_msg = f"ファイルリスト取得エラー: {e}"
        if not self._cancellation_requested: self.signals.status_update.emit(f"ファイルリスト作成完了 ({len(image_paths)} files)")
        self.all_image_paths = sorted(image_paths)
        return self.all_image_paths, error_msg

    def _process_blur_task(self, img_path: str, blur_detect_func: Callable[[str], BlurResult]) -> BlurTaskResult:
        # ★ 処理開始前にファイル名シグナルを発行 ★
        if hasattr(self.signals, 'processing_file'):
             self.signals.processing_file.emit(os.path.basename(img_path))
        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★
        if self._cancellation_requested: return img_path, None, "処理中断"
        score, error_msg = blur_detect_func(img_path)
        return img_path, score, error_msg

    @Slot()
    def run(self) -> None:
        start_time: float = time.time()
        PROGRESS_FILE_LIST: int = 5; PROGRESS_BLUR_DETECT: int = 25
        PROGRESS_DUPLICATE_DETECT: int = 30; PROGRESS_SIMILAR_DETECT: int = 40
        current_progress: int = 0

        try:
            # --- 0. ファイルリスト取得 (変更なし) ---
            scan_subdirs: bool = bool(self.settings.get('scan_subdirectories', False))
            image_paths: List[str]; list_error: Optional[str]
            image_paths, list_error = self._list_image_files(scan_subdirs)
            if self._cancellation_requested: self.signals.cancelled.emit(); return
            if list_error: self.signals.error.emit(list_error); self.signals.finished.emit(); return
            if not image_paths:
                self.signals.status_update.emit("対象フォルダ（およびサブフォルダ）に画像ファイルが見つかりませんでした。")
                self.signals.results_ready.emit([], [], {}, self.processing_errors)
                delete_scan_state(self.directory_path)
                if self.cache_handler: self.cache_handler.clear_all()
                self.signals.finished.emit(); return

            num_images: int = len(image_paths)
            duplicate_paths_set: Set[str] = set()
            current_progress = PROGRESS_FILE_LIST; self.signals.progress_update.emit(current_progress)

            # --- 1. ブレ検出 (並列化) ---
            blur_algo: str = str(self.settings.get('blur_algorithm', 'fft'))
            blur_threshold: float; threshold_label: str; blur_detect_func: Callable[[str], BlurResult]
            if blur_algo == 'laplacian': blur_threshold = float(self.settings.get('blur_laplacian_threshold', 100)); threshold_label = f"Laplacian閾値: {blur_threshold:.1f}"; blur_detect_func = calculate_laplacian_variance
            else: blur_threshold = float(self.settings.get('blur_threshold', 0.80)); threshold_label = f"FFT閾値: {blur_threshold:.4f}"; blur_detect_func = calculate_fft_blur_score_v2
            print(f"ブレ検出アルゴリズム: {blur_algo.upper()} (閾値={blur_threshold}), Max Workers: {self.max_workers}")
            status_prefix_blur: str = f"ブレ検出中 ({blur_algo.upper()})"; last_blur_emit_time: float = 0.0
            processed_count_blur: int = len(self.processed_paths_blur)
            self.signals.status_update.emit(f"{status_prefix_blur} ({threshold_label}) ({processed_count_blur}/{num_images})")
            tasks_to_run_blur: List[str] = [p for p in image_paths if p not in self.processed_paths_blur]; num_tasks_blur: int = len(tasks_to_run_blur)
            print(f"ブレ検出対象: {num_tasks_blur} ファイル")
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(self._process_blur_task, path, blur_detect_func) for path in tasks_to_run_blur]
                for future in concurrent.futures.as_completed(futures):
                    if self._cancellation_requested:
                        print("ブレ検出中に中断要求あり..."); [f.cancel() for f in futures if not f.done()]; self.signals.cancelled.emit(); return
                    try:
                        img_path, score, error_msg = future.result()
                        self.processed_paths_blur.add(img_path); processed_count_blur += 1
                        if error_msg is not None:
                            if error_msg != "処理中断": self.processing_errors.append({'type': f'ブレ検出({blur_algo})', 'path': os.path.basename(img_path), 'error': error_msg}) # ★ basename を記録 ★
                        elif score is not None and score <= blur_threshold: self.blurry_results.append({"path": img_path, "score": score}) # 結果にはフルパス
                        progress: int = current_progress + int((processed_count_blur / num_images) * PROGRESS_BLUR_DETECT); current_time: float = time.time()
                        if processed_count_blur % 20 == 0: QApplication.processEvents()
                        if processed_count_blur % self.state_save_interval == 0: self._save_state()
                        if processed_count_blur == num_images or current_time - last_blur_emit_time > 0.1:
                             self.signals.progress_update.emit(progress); self.signals.status_update.emit(f"{status_prefix_blur} ({processed_count_blur}/{num_images})"); last_blur_emit_time = current_time
                    except concurrent.futures.CancelledError: print("ブレ検出タスクがキャンセルされました。")
                    except Exception as exc: print(f'ブレ検出タスクで予期せぬ例外が発生: {exc}'); self.processing_errors.append({'type': f'ブレ検出({blur_algo})(致命的)', 'path': '不明', 'error': str(exc)}); processed_count_blur += 1
            # ★ 処理完了後にファイル名表示をクリア ★
            if hasattr(self.signals, 'processing_file'): self.signals.processing_file.emit("")
            current_progress += PROGRESS_BLUR_DETECT; self.signals.progress_update.emit(current_progress)
            if not self._cancellation_requested: self._save_state()
            if self._cancellation_requested: self.signals.cancelled.emit(); return

            # --- 2. 重複ファイル検出 ---
            # ★ find_duplicate_files 内部で processing_file シグナルを発行するように改造が必要 ★
            # ★ (今回は find_duplicate_files は変更しない) ★
            self.signals.status_update.emit("重複ファイル検出中...")
            try:
                dup_results_current, dup_errors_current = find_duplicate_files(
                    image_paths, signals=self.signals,
                    progress_offset=current_progress, progress_range=PROGRESS_DUPLICATE_DETECT,
                    is_cancelled_func=lambda: self._cancellation_requested,
                    cache_handler=self.cache_handler
                )
                if self._cancellation_requested: self.signals.cancelled.emit(); return
                self.duplicate_results = dup_results_current
                # ★ エラーのパスも basename にする (任意) ★
                for err in dup_errors_current:
                    if 'path' in err: err['path'] = os.path.basename(err['path'])
                self.processing_errors.extend(dup_errors_current)
                duplicate_paths_set.clear(); [duplicate_paths_set.update(paths) for paths in self.duplicate_results.values()]
            except Exception as e:
                self.processing_errors.append({'type': '重複検出(致命的)', 'path': self.directory_path, 'error': str(e)})
                print(f"エラー: 重複ファイル検出中に予期せぬエラー: {e}")
            current_progress += PROGRESS_DUPLICATE_DETECT; self.signals.progress_update.emit(current_progress)
            if not self._cancellation_requested:
                 self.signals.status_update.emit(f"重複ファイル検出完了 ({len(self.duplicate_results)}グループ, {len(duplicate_paths_set)}ファイル)")
                 self._save_state()
            if self._cancellation_requested: self.signals.cancelled.emit(); return

            # --- 3. 類似ペア検出 ---
            # ★ find_similar_pairs 内部で processing_file シグナルを発行するように改造が必要 ★
            # ★ (今回は find_similar_pairs は変更しない) ★
            similarity_mode: str = str(self.settings.get('similarity_mode', 'phash_orb'))
            orb_nfeatures: int = int(self.settings.get('orb_nfeatures', 1500)); orb_ratio_threshold: float = float(self.settings.get('orb_ratio_threshold', 0.70))
            min_good_matches: int = int(self.settings.get('min_good_matches', 40)); hash_threshold: int = int(self.settings.get('hash_threshold', 5))
            status_msg: str = f"類似ペア検出中 (モード: {similarity_mode.replace('_', ' ').title()}, 重複除外)"
            self.signals.status_update.emit(status_msg)
            try:
                sim_pairs_current, comp_errors_current, _ = find_similar_pairs(
                    image_paths, duplicate_paths_set=duplicate_paths_set, similarity_mode=similarity_mode,
                    orb_nfeatures=orb_nfeatures, orb_ratio_threshold=orb_ratio_threshold,
                    min_good_matches_threshold=min_good_matches, hash_threshold=hash_threshold,
                    signals=self.signals, progress_offset=current_progress,
                    progress_range=PROGRESS_SIMILAR_DETECT,
                    is_cancelled_func=lambda: self._cancellation_requested,
                    cache_handler=self.cache_handler
                )
                if self._cancellation_requested: self.signals.cancelled.emit(); return
                self.similar_pair_results = sim_pairs_current
                # ★ エラーのパスも basename にする (任意) ★
                for err in comp_errors_current:
                     if 'path' in err and ' vs ' in err['path']: # "file1 vs file2" 形式の場合
                         f1, f2 = err['path'].split(' vs ', 1)
                         err['path'] = f"{os.path.basename(f1)} vs {os.path.basename(f2)}"
                     elif 'path' in err:
                         err['path'] = os.path.basename(err['path'])
                self.processing_errors.extend(comp_errors_current)
            except Exception as e:
                self.processing_errors.append({'type': f'類似ペア検出({similarity_mode})(致命的)', 'path': self.directory_path, 'error': str(e)})
                print(f"エラー: 類似ペア検出 ({similarity_mode}モード) 中に予期せぬエラー: {e}")
            current_progress = 100; self.signals.progress_update.emit(current_progress)
            if not self._cancellation_requested:
                self.signals.status_update.emit(f"類似ペア検出完了 ({len(self.similar_pair_results)}ペア発見)")
                delete_scan_state(self.directory_path)
            if self._cancellation_requested: self.signals.cancelled.emit(); return

            # --- 4. 結果通知 (変更なし) ---
            end_time: float = time.time()
            print(f"スキャン処理完了。所要時間: {end_time - start_time:.2f} 秒")
            self.signals.results_ready.emit(self.blurry_results, self.similar_pair_results, self.duplicate_results, self.processing_errors)

        except Exception as e:
            self.signals.error.emit(f"スキャン中に予期せぬエラーが発生しました: {e}")
        finally:
            # ★ 完了/エラー/中断時に関わらず、ファイル名表示をクリア ★
            if hasattr(self.signals, 'processing_file'):
                self.signals.processing_file.emit("")
            if not self._cancellation_requested:
                self.signals.finished.emit()

