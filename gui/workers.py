# gui/workers.py
import os
import time
from PySide6.QtCore import QRunnable, Signal, QObject, Slot
from typing import Tuple, Optional, List, Dict, Any, Union

# 型エイリアス (変更なし)
SettingsDict = Dict[str, Union[float, bool, int, str]]
BlurResultItem = Dict[str, Union[str, float]]
SimilarPair = Tuple[str, str, int]
DuplicateDict = Dict[str, List[str]]
ErrorDict = Dict[str, str]

# --- コアロジックの関数をインポート ---
try:
    from core.blur_detection import calculate_fft_blur_score_v2
    from core.similarity_detection import find_similar_pairs
    from core.duplicate_detection import find_duplicate_files
    BlurResult = Tuple[Optional[float], Optional[str]]
    FindSimilarResult = Tuple[List[SimilarPair], List[ErrorDict], List[ErrorDict]]
    FindDuplicateResult = Tuple[DuplicateDict, List[ErrorDict]]
except ImportError as e:
    print(f"エラー: core モジュールのインポートに失敗しました。({e}) ダミー関数を使用します。")
    # (ダミー関数の定義は省略 - 前のバージョンと同じ)
    def calculate_fft_blur_score_v2(path: str, ratio: float = 0.05) -> BlurResult: return (0.5, None) if "blur" in path.lower() else (0.9, None)
    def find_similar_pairs(image_paths: List[str], signals: Optional[Any] = None, progress_offset: int = 0, progress_range: int = 100, **kwargs: Any) -> FindSimilarResult: return [], [], []
    def find_duplicate_files(image_paths: List[str], signals: Optional[Any] = None, progress_offset: int = 0, progress_range: int = 100, **kwargs: Any) -> FindDuplicateResult: return {}, []


# === バックグラウンド処理用のシグナル定義 ===
class WorkerSignals(QObject):
    """バックグラウンド処理からのシグナルを定義するクラス"""
    status_update = Signal(str)
    progress_update = Signal(int)
    results_ready = Signal(list, list, dict, list)
    error = Signal(str)
    finished = Signal()
    cancelled = Signal() # ★ 中止シグナルを追加 ★

# === バックグラウンド処理実行クラス ===
class ScanWorker(QRunnable):
    """画像のスキャン処理をバックグラウンドで実行するクラス"""
    def __init__(self, directory_path: str, settings: SettingsDict):
        super().__init__()
        self.directory_path: str = directory_path
        self.settings: SettingsDict = settings
        self.signals: WorkerSignals = WorkerSignals()
        self.file_extensions: Tuple[str, ...] = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.heic', '.heif')
        # ★ 中断要求フラグを追加 ★
        self._cancellation_requested: bool = False

    # ★ 中断要求を受け付けるメソッドを追加 ★
    def request_cancellation(self) -> None:
        """スキャン処理の中断を要求する"""
        print("スキャン中止要求を受け付けました。")
        self._cancellation_requested = True

    def _list_image_files(self, scan_subdirs: bool) -> Tuple[List[str], Optional[str]]:
        """指定されたディレクトリ内の画像ファイルをリストアップする (サブディレクトリ対応)"""
        image_paths: List[str] = []
        error_msg: Optional[str] = None
        processed_dirs: int = 0
        status_prefix: str = "ファイルリスト作成中"
        self.signals.status_update.emit(f"{status_prefix}...")

        try:
            if scan_subdirs:
                for root, dirs, files in os.walk(self.directory_path):
                    # ★ 中断チェック ★
                    if self._cancellation_requested: return [], "処理が中断されました。"
                    processed_dirs += 1
                    if processed_dirs % 10 == 0: self.signals.status_update.emit(f"{status_prefix} ({processed_dirs} Dirs)...")
                    filename: str
                    for filename in files:
                        if filename.lower().endswith(self.file_extensions):
                            full_path: str = os.path.join(root, filename)
                            if os.path.isfile(full_path): image_paths.append(full_path)
            else:
                filename: str
                for filename in os.listdir(self.directory_path):
                    # ★ 中断チェック ★
                    if self._cancellation_requested: return [], "処理が中断されました。"
                    if filename.lower().endswith(self.file_extensions):
                        full_path = os.path.join(self.directory_path, filename)
                        if os.path.isfile(full_path) and not os.path.islink(full_path): image_paths.append(full_path)
        except OSError as e: error_msg = f"ディレクトリ読み込みエラー: {e}"
        except Exception as e: error_msg = f"ファイルリスト取得エラー: {e}"

        if not self._cancellation_requested: # 中断されていなければ完了メッセージ
            self.signals.status_update.emit(f"ファイルリスト作成完了 ({len(image_paths)} files)")
        return image_paths, error_msg

    @Slot()
    def run(self) -> None:
        processing_errors: List[ErrorDict] = []
        start_time: float = time.time()
        PROGRESS_FILE_LIST: int = 5; PROGRESS_BLUR_DETECT: int = 30; PROGRESS_DUPLICATE_DETECT: int = 20; PROGRESS_SIMILAR_DETECT: int = 45
        current_progress: int = 0

        try:
            # --- 0. ファイルリスト取得 ---
            scan_subdirs: bool = bool(self.settings.get('scan_subdirectories', False))
            image_paths: List[str]; list_error: Optional[str]
            image_paths, list_error = self._list_image_files(scan_subdirs)

            if self._cancellation_requested: # ★ 中断チェック ★
                self.signals.cancelled.emit(); return # 中断シグナル発行
            if list_error:
                self.signals.error.emit(list_error); self.signals.finished.emit(); return

            if not image_paths:
                self.signals.status_update.emit("対象フォルダ（およびサブフォルダ）に画像ファイルが見つかりませんでした。")
                self.signals.results_ready.emit([], [], {}, processing_errors)
                self.signals.finished.emit(); return

            num_images: int = len(image_paths)
            blurry_results: List[BlurResultItem] = []
            similar_pair_results: List[SimilarPair] = []
            duplicate_results: DuplicateDict = {}

            current_progress = PROGRESS_FILE_LIST; self.signals.progress_update.emit(current_progress)

            # --- 1. ブレ検出 ---
            blur_threshold: float = float(self.settings.get('blur_threshold', 0.80))
            status_prefix_blur: str = "ブレ検出中"; last_blur_emit_time: float = 0.0
            self.signals.status_update.emit(f"{status_prefix_blur} (閾値: {blur_threshold:.4f}) (0/{num_images})")
            i: int; img_path: str
            for i, img_path in enumerate(image_paths):
                # ★ 中断チェック ★
                if self._cancellation_requested: self.signals.cancelled.emit(); return

                score: Optional[float]; error_msg: Optional[str]
                score, error_msg = calculate_fft_blur_score_v2(img_path)
                if error_msg is not None: processing_errors.append({'type': 'ブレ検出', 'path': img_path, 'error': error_msg})
                elif score is not None and score <= blur_threshold: blurry_results.append({"path": img_path, "score": score})
                progress: int = current_progress + int(((i + 1) / num_images) * PROGRESS_BLUR_DETECT); current_time: float = time.time()
                if (i + 1) == num_images or current_time - last_blur_emit_time > 0.1:
                     self.signals.progress_update.emit(progress); self.signals.status_update.emit(f"{status_prefix_blur} ({i+1}/{num_images})"); last_blur_emit_time = current_time
            current_progress += PROGRESS_BLUR_DETECT; self.signals.progress_update.emit(current_progress)

            # ★ 中断チェック ★
            if self._cancellation_requested: self.signals.cancelled.emit(); return

            # --- 2. 重複ファイル検出 ---
            self.signals.status_update.emit("重複ファイル検出中...")
            try:
                dup_results: DuplicateDict; dup_errors: List[ErrorDict]
                # ★ find_duplicate_files に中断チェック関数を渡す (lambda) ★
                dup_results, dup_errors = find_duplicate_files(
                    image_paths, signals=self.signals,
                    progress_offset=current_progress, progress_range=PROGRESS_DUPLICATE_DETECT,
                    is_cancelled_func=lambda: self._cancellation_requested # ★ 追加 ★
                )
                if self._cancellation_requested: self.signals.cancelled.emit(); return # find_duplicate_files 内部で中断された場合
                duplicate_results = dup_results
                processing_errors.extend(dup_errors)
            except Exception as e:
                processing_errors.append({'type': '重複検出(致命的)', 'path': self.directory_path, 'error': str(e)})
                print(f"エラー: 重複ファイル検出中に予期せぬエラー: {e}"); duplicate_results = {}
            current_progress += PROGRESS_DUPLICATE_DETECT; self.signals.progress_update.emit(current_progress)
            if not self._cancellation_requested: # 中断されていなければ完了メッセージ
                self.signals.status_update.emit(f"重複ファイル検出完了 ({len(duplicate_results)}グループ)")

            # ★ 中断チェック ★
            if self._cancellation_requested: self.signals.cancelled.emit(); return

            # --- 3. 類似ペア検出 ---
            orb_nfeatures: int = int(self.settings.get('orb_nfeatures', 1500)); orb_ratio_threshold: float = float(self.settings.get('orb_ratio_threshold', 0.70))
            min_good_matches: int = int(self.settings.get('min_good_matches', 40)); hash_threshold: int = int(self.settings.get('hash_threshold', 5))
            use_phash: bool = bool(self.settings.get('use_phash', True)); status_msg: str = f"類似ペア検出中 (pHash={'ON' if use_phash else 'OFF'}, ...)"
            self.signals.status_update.emit(status_msg)
            try:
                sim_pairs: List[SimilarPair]; comp_errors: List[ErrorDict]; _ : List[ErrorDict]
                # ★ find_similar_pairs に中断チェック関数を渡す (lambda) ★
                sim_pairs, comp_errors, _ = find_similar_pairs(
                    image_paths, orb_nfeatures=orb_nfeatures, orb_ratio_threshold=orb_ratio_threshold,
                    min_good_matches_threshold=min_good_matches, hash_threshold=hash_threshold,
                    use_phash=use_phash, signals=self.signals,
                    progress_offset=current_progress, progress_range=PROGRESS_SIMILAR_DETECT,
                    is_cancelled_func=lambda: self._cancellation_requested # ★ 追加 ★
                )
                if self._cancellation_requested: self.signals.cancelled.emit(); return # find_similar_pairs 内部で中断された場合
                similar_pair_results = sim_pairs
                processing_errors.extend(comp_errors)
            except Exception as e: self.signals.error.emit(f"類似ペア検出処理中に致命的なエラー: {e}"); self.signals.finished.emit(); return
            current_progress = 100; self.signals.progress_update.emit(current_progress)
            if not self._cancellation_requested: # 中断されていなければ完了メッセージ
                self.signals.status_update.emit(f"類似ペア検出完了 ({len(similar_pair_results)}ペア発見)")

            # ★ 中断チェック ★
            if self._cancellation_requested: self.signals.cancelled.emit(); return

            # --- 4. 結果通知 ---
            end_time: float = time.time()
            print(f"スキャン処理完了。所要時間: {end_time - start_time:.2f} 秒")
            self.signals.results_ready.emit(blurry_results, similar_pair_results, duplicate_results, processing_errors)

        except Exception as e:
            # 中断要求による例外はここではキャッチしない想定
            self.signals.error.emit(f"スキャン中に予期せぬエラーが発生しました: {e}")
        finally:
            # ★ finished シグナルは中断されなかった場合のみ発行 ★
            if not self._cancellation_requested:
                self.signals.finished.emit()

