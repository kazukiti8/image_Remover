# core/similarity_detection.py
import cv2
import numpy as np
import os
import itertools
import time
from PIL import Image
from typing import Tuple, Optional, List, Dict, Any, Union # ★ Any を使用 ★

# ★ 型エイリアス ★
ErrorMsgType = Optional[str]
NumpyImageType = np.ndarray[Any, Any]
ImageType = Image.Image # Pillow Image
HashType = Optional[Any] # imagehash の型 (Anyで代用)
PhashResult = Tuple[HashType, ErrorMsgType]
OrbScoreResult = Tuple[Optional[int], ErrorMsgType] # (スコア or None, エラー or None)
ErrorDict = Dict[str, str] # 処理エラー用
SimilarPair = Tuple[str, str, int] # (path1, path2, score)
FindSimilarResult = Tuple[List[SimilarPair], List[ErrorDict], List[ErrorDict]]

# 画像ローダー関数をインポート
try:
    from ..utils.image_loader import load_image_pil, load_image_as_numpy, HEIF_AVAILABLE
except ImportError:
    try: from utils.image_loader import load_image_pil, load_image_as_numpy, HEIF_AVAILABLE
    except ImportError:
        print("エラー: utils.image_loader のインポートに失敗しました。")
        def load_image_pil(path: str) -> Tuple[Optional[ImageType], ErrorMsgType]: return None, "Image loader not available"
        def load_image_as_numpy(path: str, mode: str = 'gray') -> Tuple[Optional[NumpyImageType], ErrorMsgType]: return None, "Image loader not available"
        HEIF_AVAILABLE = False

# ImageHash ライブラリをインポート
try:
    import imagehash
    IMAGEHASH_AVAILABLE: bool = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
    print("警告: ImageHash ライブラリが見つかりません。")

# --- ★★★ 仮の WorkerSignals クラス定義を削除 ★★★ ---
# class WorkerSignals: ...

def calculate_phash(image_path: str) -> PhashResult:
    """指定された画像の Perceptual Hash (pHash) を計算します。HEIC対応。"""
    if not IMAGEHASH_AVAILABLE: return None, "ImageHashライブラリが利用できません"
    img_pil: Optional[ImageType]; error_msg: ErrorMsgType
    img_pil, error_msg = load_image_pil(image_path)
    if error_msg: return None, error_msg
    if not img_pil: return None, "Pillowイメージの取得に失敗 (pHash)"
    try:
        hash_value: imagehash.ImageHash = imagehash.phash(img_pil)
        return hash_value, None
    except Exception as e: error_msg = f"pHash計算エラー({type(e).__name__}): {e}"; print(f"エラー: pHash計算中にエラー ({os.path.basename(image_path)}): {e}"); return None, error_msg

def calculate_orb_similarity_score(image_path1: str, image_path2: str,
                                   n_features: int = 1000, ratio_threshold: float = 0.75) -> OrbScoreResult:
    """ORB特徴量を用いて類似度スコアを計算します。HEIC対応。"""
    img1_gray: Optional[NumpyImageType]; img2_gray: Optional[NumpyImageType]
    err1: ErrorMsgType; err2: ErrorMsgType
    img1_gray, err1 = load_image_as_numpy(image_path1, mode='gray')
    if err1: return None, f"画像1読込エラー: {err1}"
    img2_gray, err2 = load_image_as_numpy(image_path2, mode='gray')
    if err2: return None, f"画像2読込エラー: {err2}"
    if img1_gray is None or img2_gray is None: return None, "画像データの取得に失敗 (ORB)"
    try:
        orb: cv2.ORB = cv2.ORB_create(nfeatures=n_features)
        kp1: Tuple[cv2.KeyPoint, ...]; des1: Optional[NumpyImageType]
        kp2: Tuple[cv2.KeyPoint, ...]; des2: Optional[NumpyImageType]
        kp1, des1 = orb.detectAndCompute(img1_gray, None)
        kp2, des2 = orb.detectAndCompute(img2_gray, None)
        if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2: return 0, None
        bf: cv2.BFMatcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        matches: List[Tuple[cv2.DMatch, ...]] = bf.knnMatch(des1, des2, k=2)
        good_matches: List[cv2.DMatch] = []
        if matches is not None:
            for match_pair in matches:
                if len(match_pair) == 2:
                    m: cv2.DMatch = match_pair[0]; n: cv2.DMatch = match_pair[1]
                    if m.distance < ratio_threshold * n.distance: good_matches.append(m)
        return len(good_matches), None
    except cv2.error as e: return None, f"OpenCVエラー(ORB): {e.msg}"
    except MemoryError: return None, "メモリ不足エラー(ORB)"
    except Exception as e: return None, f"予期せぬエラー(ORB): {type(e).__name__}"


def find_similar_pairs(directory_path: str,
                       orb_nfeatures: int = 1000,
                       orb_ratio_threshold: float = 0.75,
                       min_good_matches_threshold: int = 30,
                       hash_threshold: int = 5,
                       use_phash: bool = True,
                       file_extensions: Tuple[str, ...] = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.heic', '.heif'),
                       signals: Optional[Any] = None, # ★ 型ヒントを Optional[Any] に変更 ★
                       progress_offset: int = 0,
                       progress_range: int = 100) -> FindSimilarResult:
    """指定されたディレクトリ内の画像を比較し、類似しているペアを見つけます。"""
    processing_errors: List[ErrorDict] = []
    file_list_errors: List[ErrorDict] = []

    last_progress_emit_time: float = 0.0
    # ★ emit_progress 内の signals の型ヒントも Any に ★
    def emit_progress(current_value: int, total_value: int, stage_offset: int, stage_range: float, status_prefix: str) -> None:
        nonlocal last_progress_emit_time
        progress: int = stage_offset
        if total_value > 0: progress = stage_offset + int((current_value / total_value) * stage_range)
        status: str = f"{status_prefix} ({current_value}/{total_value})"
        current_time: float = time.time()
        # signals が None でなく、emit できるオブジェクトかチェック (より安全に)
        if signals and hasattr(signals, 'progress_update') and hasattr(signals, 'status_update') and \
           (current_value == total_value or current_time - last_progress_emit_time > 0.1):
             signals.progress_update.emit(progress) # type: ignore
             signals.status_update.emit(status)     # type: ignore
             last_progress_emit_time = current_time

    if signals and hasattr(signals, 'status_update'): signals.status_update.emit("ファイルリスト取得中...")
    image_paths: List[str] = []
    try:
        filename: str
        for filename in os.listdir(directory_path):
            if filename.lower().endswith(file_extensions):
                full_path: str = os.path.join(directory_path, filename)
                if os.path.isfile(full_path) and not os.path.islink(full_path): image_paths.append(full_path)
    except OSError as e: return [], [{'type': 'ディレクトリ読込', 'path': directory_path, 'error': str(e)}], []
    except Exception as e: return [], [{'type': 'ファイルリスト取得', 'path': directory_path, 'error': str(e)}], []
    if len(image_paths) < 2: return [], [], []

    num_images: int = len(image_paths); print(f"{num_images} 個の画像を検出。類似ペア検出を開始します...")
    candidate_pairs: List[Tuple[str, str]] = []
    similar_pairs: List[SimilarPair] = []

    if use_phash and IMAGEHASH_AVAILABLE:
        phash_calc_range: float = progress_range * 0.10; phash_comp_range: float = progress_range * 0.10
        orb_comp_range: float = progress_range * 0.80; orb_comp_offset: float = progress_offset + phash_calc_range + phash_comp_range
        hashes: Dict[str, Any] = {}; hash_calculation_count: int = 0; status_prefix_phash_calc: str = "pHash計算中"
        emit_progress(0, num_images, int(progress_offset), int(phash_calc_range), status_prefix_phash_calc)
        for i, path in enumerate(image_paths):
            hash_value: HashType; error_msg: ErrorMsgType
            hash_value, error_msg = calculate_phash(path)
            if error_msg: processing_errors.append({'type': 'pHash計算', 'path': path, 'error': error_msg})
            elif hash_value: hashes[path] = hash_value
            hash_calculation_count += 1; emit_progress(hash_calculation_count, num_images, int(progress_offset), int(phash_calc_range), status_prefix_phash_calc)
        print(f"pHash計算完了。{len(hashes)}/{num_images} 個のハッシュを計算しました。")

        hash_paths: List[str] = list(hashes.keys()); hash_comparisons: int = 0; total_hash_comparisons: int = len(hash_paths) * (len(hash_paths) - 1) // 2
        status_prefix_phash_comp: str = "ハッシュ比較中"; phash_comp_offset: float = progress_offset + phash_calc_range
        emit_progress(0, total_hash_comparisons, int(phash_comp_offset), int(phash_comp_range), status_prefix_phash_comp)
        if total_hash_comparisons > 0:
            path1: str; path2: str
            for i, path1 in enumerate(hash_paths):
                for j in range(i + 1, len(hash_paths)):
                    path2 = hash_paths[j]; hash_comparisons += 1
                    try:
                        distance: int = hashes[path1] - hashes[path2]
                        if distance <= hash_threshold: candidate_pairs.append((path1, path2))
                    except Exception as e: processing_errors.append({'type': 'pHash比較', 'path': f"{os.path.basename(path1)} vs {os.path.basename(path2)}", 'path1': path1, 'path2': path2, 'error': f"ハッシュ比較エラー: {e}"})
                    emit_progress(hash_comparisons, total_hash_comparisons, int(phash_comp_offset), int(phash_comp_range), status_prefix_phash_comp)
        emit_progress(total_hash_comparisons, total_hash_comparisons, int(phash_comp_offset), int(phash_comp_range), status_prefix_phash_comp)
        print(f"候補絞り込み完了。{len(candidate_pairs)} 組の候補ペアが見つかりました。")
    else:
        if not use_phash: print("pHashを使用せずにORB比較を行います (総当たり)。")
        elif not IMAGEHASH_AVAILABLE: print("ImageHashライブラリがないため、pHashを使用せずにORB比較を行います (総当たり)。")
        candidate_pairs = list(itertools.combinations(image_paths, 2)); orb_comp_range = float(progress_range); orb_comp_offset = float(progress_offset)
        print(f"{len(candidate_pairs)} 組のペアをORBで比較します。")

    orb_comparisons: int = 0; total_orb_comparisons: int = len(candidate_pairs); status_prefix_orb_comp: str = "ORB比較中"
    emit_progress(0, total_orb_comparisons, int(orb_comp_offset), int(orb_comp_range), status_prefix_orb_comp)
    if total_orb_comparisons > 0:
        path1: str; path2: str
        for path1, path2 in candidate_pairs:
            orb_comparisons += 1
            score: Optional[int]; error_msg: ErrorMsgType
            score, error_msg = calculate_orb_similarity_score(path1, path2, n_features=orb_nfeatures, ratio_threshold=orb_ratio_threshold)
            if error_msg: processing_errors.append({'type': 'ORB比較', 'path': f"{os.path.basename(path1)} vs {os.path.basename(path2)}", 'path1': path1, 'path2': path2, 'error': error_msg})
            elif score is not None and score >= min_good_matches_threshold: similar_pairs.append((path1, path2, score))
            emit_progress(orb_comparisons, total_orb_comparisons, int(orb_comp_offset), int(orb_comp_range), status_prefix_orb_comp)
    emit_progress(total_orb_comparisons, total_orb_comparisons, int(orb_comp_offset), int(orb_comp_range), status_prefix_orb_comp)
    print(f"類似ペア検出完了。{len(similar_pairs)} 組の類似ペアが見つかりました。{len(processing_errors)} 件のエラーが発生しました。")
    # 完了時の最終進捗は emit_progress で送信される
    return similar_pairs, processing_errors, file_list_errors
