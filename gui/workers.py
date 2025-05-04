# gui/workers.py
import os
import time
from PySide6.QtCore import QRunnable, Signal, QObject, Slot
from typing import Tuple, Optional, List, Dict, Any, Union # ★ typing をインポート ★

# ★ 型エイリアス ★
SettingsDict = Dict[str, Union[float, bool, int, str]] # config_handler と合わせる
BlurResultItem = Dict[str, Union[str, float]]
SimilarPair = Tuple[str, str, int]
DuplicateDict = Dict[str, List[str]]
ErrorDict = Dict[str, str]

# --- コアロジックの関数をインポート ---
try:
    from core.blur_detection import calculate_fft_blur_score_v2
    from core.similarity_detection import find_similar_pairs
    from core.duplicate_detection import find_duplicate_files
    # 各関数の戻り値の型も定義しておくと良い (core側で定義されていれば不要)
    BlurResult = Tuple[Optional[float], Optional[str]]
    FindSimilarResult = Tuple[List[SimilarPair], List[ErrorDict], List[ErrorDict]]
    FindDuplicateResult = Tuple[DuplicateDict, List[ErrorDict]]
except ImportError as e:
    print(f"エラー: core モジュールのインポートに失敗しました。({e}) ダミー関数を使用します。")
    # ダミー関数にも型ヒントを付ける
    def calculate_fft_blur_score_v2(path: str, ratio: float = 0.05) -> BlurResult:
        if "error" in path.lower(): return None, "ダミーエラー(ブレ)"
        return (0.5, None) if "blur" in path.lower() else (0.9, None)
    def find_similar_pairs(dir_path: str, signals: Optional[Any] = None, progress_offset: int = 0, progress_range: int = 100, **kwargs: Any) -> FindSimilarResult:
        # (ダミー関数の実装は省略)
        return [], [], []
    def find_duplicate_files(dir_path: str, signals: Optional[Any] = None, progress_offset: int = 0, progress_range: int = 100, **kwargs: Any) -> FindDuplicateResult:
        # (ダミー関数の実装は省略)
        return {}, []


# === バックグラウンド処理用のシグナル定義 ===
class WorkerSignals(QObject):
    """バックグラウンド処理からのシグナルを定義するクラス"""
    status_update = Signal(str)
    progress_update = Signal(int)
    # ★ results_ready シグナルの型ヒントを具体的に ★
    results_ready = Signal(list, list, dict, list) # list[BlurResultItem], list[SimilarPair], DuplicateDict, list[ErrorDict]
    error = Signal(str)
    finished = Signal()

# === バックグラウンド処理実行クラス ===
class ScanWorker(QRunnable):
    """画像のスキャン処理をバックグラウンドで実行するクラス"""
    def __init__(self, directory_path: str, settings: SettingsDict):
        """コンストラクタ"""
        super().__init__()
        self.directory_path: str = directory_path
        self.settings: SettingsDict = settings
        self.signals: WorkerSignals = WorkerSignals()
        self.file_extensions: Tuple[str, ...] = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.heic', '.heif')

    @Slot()
    def run(self) -> None:
        """メインの処理を実行するメソッド"""
        processing_errors: List[ErrorDict] = []
        start_time: float = time.time()

        PROGRESS_FILE_LIST: int = 5; PROGRESS_BLUR_DETECT: int = 30; PROGRESS_DUPLICATE_DETECT: int = 20; PROGRESS_SIMILAR_DETECT: int = 45
        current_progress: int = 0

        try:
            # --- 0. ファイルリスト取得 ---
            self.signals.status_update.emit("ファイルリスト取得中...")
            image_paths: List[str] = []
            try:
                filename: str
                for filename in os.listdir(self.directory_path):
                    if filename.lower().endswith(self.file_extensions):
                        full_path: str = os.path.join(self.directory_path, filename)
                        if os.path.isfile(full_path) and not os.path.islink(full_path): image_paths.append(full_path)
            except OSError as e: self.signals.error.emit(f"ディレクトリ読み込みエラー: {e}"); self.signals.finished.emit(); return
            except Exception as e: self.signals.error.emit(f"ファイルリスト取得エラー: {e}"); self.signals.finished.emit(); return

            if not image_paths:
                self.signals.status_update.emit("対象ディレクトリに画像ファイルが見つかりませんでした。")
                self.signals.results_ready.emit([], [], {}, processing_errors) # 4つの引数
                self.signals.finished.emit(); return

            num_images: int = len(image_paths)
            blurry_results: List[BlurResultItem] = []
            similar_pair_results: List[SimilarPair] = []
            duplicate_results: DuplicateDict = {}

            current_progress = PROGRESS_FILE_LIST; self.signals.progress_update.emit(current_progress)

            # --- 1. ブレ検出 ---
            blur_threshold: float = float(self.settings.get('blur_threshold', 0.80)) # floatであることを明示
            status_prefix_blur: str = "ブレ検出中"
            self.signals.status_update.emit(f"{status_prefix_blur} (閾値: {blur_threshold:.4f}) (0/{num_images})"); last_blur_emit_time: float = 0.0
            i: int; img_path: str
            for i, img_path in enumerate(image_paths):
                score: Optional[float]; error_msg: Optional[str]
                score, error_msg = calculate_fft_blur_score_v2(img_path) # 戻り値の型は BlurResult
                if error_msg is not None: processing_errors.append({'type': 'ブレ検出', 'path': img_path, 'error': error_msg})
                elif score is not None and score <= blur_threshold: blurry_results.append({"path": img_path, "score": score})
                progress: int = current_progress + int(((i + 1) / num_images) * PROGRESS_BLUR_DETECT); current_time: float = time.time()
                if (i + 1) == num_images or current_time - last_blur_emit_time > 0.1:
                     self.signals.progress_update.emit(progress); self.signals.status_update.emit(f"{status_prefix_blur} ({i+1}/{num_images})"); last_blur_emit_time = current_time
            current_progress += PROGRESS_BLUR_DETECT; self.signals.progress_update.emit(current_progress)

            # --- 2. 重複ファイル検出 ---
            self.signals.status_update.emit("重複ファイル検出中...")
            try:
                dup_results: DuplicateDict; dup_errors: List[ErrorDict]
                dup_results, dup_errors = find_duplicate_files(
                    self.directory_path, file_extensions=self.file_extensions, signals=self.signals,
                    progress_offset=current_progress, progress_range=PROGRESS_DUPLICATE_DETECT
                )
                duplicate_results = dup_results # 結果を代入
                processing_errors.extend(dup_errors)
            except Exception as e:
                processing_errors.append({'type': '重複検出(致命的)', 'path': self.directory_path, 'error': str(e)})
                print(f"エラー: 重複ファイル検出中に予期せぬエラー: {e}"); duplicate_results = {}
            current_progress += PROGRESS_DUPLICATE_DETECT; self.signals.progress_update.emit(current_progress)
            self.signals.status_update.emit(f"重複ファイル検出完了 ({len(duplicate_results)}グループ)")

            # --- 3. 類似ペア検出 ---
            orb_nfeatures: int = int(self.settings.get('orb_nfeatures', 1500))
            orb_ratio_threshold: float = float(self.settings.get('orb_ratio_threshold', 0.70))
            min_good_matches: int = int(self.settings.get('min_good_matches', 40))
            hash_threshold: int = int(self.settings.get('hash_threshold', 5))
            use_phash: bool = bool(self.settings.get('use_phash', True))
            status_msg: str = f"類似ペア検出中 (pHash={'ON' if use_phash else 'OFF'}, ...)"
            self.signals.status_update.emit(status_msg)
            try:
                sim_pairs: List[SimilarPair]; comp_errors: List[ErrorDict]; _ : List[ErrorDict] # file_list_errors は無視
                sim_pairs, comp_errors, _ = find_similar_pairs(
                    self.directory_path, orb_nfeatures=orb_nfeatures, orb_ratio_threshold=orb_ratio_threshold,
                    min_good_matches_threshold=min_good_matches, hash_threshold=hash_threshold,
                    use_phash=use_phash, file_extensions=self.file_extensions, signals=self.signals,
                    progress_offset=current_progress, progress_range=PROGRESS_SIMILAR_DETECT
                )
                similar_pair_results = sim_pairs # 結果を代入
                processing_errors.extend(comp_errors)
            except Exception as e: self.signals.error.emit(f"類似ペア検出処理中に致命的なエラー: {e}"); self.signals.finished.emit(); return
            current_progress = 100; self.signals.progress_update.emit(current_progress)
            self.signals.status_update.emit(f"類似ペア検出完了 ({len(similar_pair_results)}ペア発見)")

            # --- 4. 結果通知 ---
            end_time: float = time.time()
            print(f"スキャン処理完了。所要時間: {end_time - start_time:.2f} 秒")
            self.signals.results_ready.emit(blurry_results, similar_pair_results, duplicate_results, processing_errors)

        except Exception as e:
            self.signals.error.emit(f"スキャン中に予期せぬエラーが発生しました: {e}")
        finally:
            self.signals.finished.emit()

