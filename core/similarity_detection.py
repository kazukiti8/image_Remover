# core/similarity_detection.py
import cv2
import numpy as np
import os
import itertools
import time
from PIL import Image
from typing import Tuple, Optional, List, Dict, Any, Union, Callable, Set

# ★ CacheHandler をインポート ★
try:
    from utils.cache_handler import CacheHandler
except ImportError:
    print("警告: utils.cache_handler のインポートに失敗しました。キャッシュ機能は無効になります。")
    CacheHandler = None

# 型エイリアス (変更なし)
ErrorMsgType = Optional[str]
NumpyImageType = np.ndarray[Any, Any]
ImageType = Image.Image
HashType = Optional[Any]
PhashResult = Tuple[HashType, ErrorMsgType]
OrbScoreResult = Tuple[Optional[int], ErrorMsgType]
ErrorDict = Dict[str, str]
SimilarPair = Tuple[str, str, int]
FindSimilarResult = Tuple[List[SimilarPair], List[ErrorDict], List[ErrorDict]]

# 画像ローダー関数をインポート (変更なし)
try:
    from ..utils.image_loader import load_image_pil, load_image_as_numpy, HEIF_AVAILABLE
except ImportError:
    try: from utils.image_loader import load_image_pil, load_image_as_numpy, HEIF_AVAILABLE
    except ImportError:
        print("エラー: utils.image_loader のインポートに失敗しました。")
        def load_image_pil(path: str) -> Tuple[Optional[ImageType], ErrorMsgType]: return None, "Image loader not available"
        def load_image_as_numpy(path: str, mode: str = 'gray') -> Tuple[Optional[NumpyImageType], ErrorMsgType]: return None, "Image loader not available"
        HEIF_AVAILABLE = False

# ImageHash ライブラリをインポート (変更なし)
try:
    import imagehash
    IMAGEHASH_AVAILABLE: bool = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
    print("警告: ImageHash ライブラリが見つかりません。")

# ★ 関数シグネチャに cache_handler を追加 ★
def calculate_phash(image_path: str, cache_handler: Optional[CacheHandler] = None) -> PhashResult:
    """
    指定された画像の Perceptual Hash (pHash) を計算します。HEIC対応。
    キャッシュを利用します。
    """
    if not IMAGEHASH_AVAILABLE: return None, "ImageHashライブラリが利用できません"

    # ★★★ キャッシュチェック ★★★
    if cache_handler:
        cached_phash_str = cache_handler.get('phash', image_path)
        if cached_phash_str is not None:
            try:
                # キャッシュから復元 (imagehashオブジェクトに変換)
                return imagehash.hex_to_hash(str(cached_phash_str)), None
            except Exception as e:
                print(f"警告: pHashキャッシュの復元に失敗 ({os.path.basename(image_path)}): {e}")
                # エラーの場合はキャッシュを無視して再計算へ
    # ★★★★★★★★★★★★★★★★★★★

    # --- キャッシュがない場合、計算を実行 ---
    img_pil: Optional[ImageType]; error_msg: ErrorMsgType
    img_pil, error_msg = load_image_pil(image_path)
    if error_msg: return None, error_msg
    if not img_pil: return None, "Pillowイメージの取得に失敗 (pHash)"

    try:
        hash_value = imagehash.phash(img_pil) # type: ignore

        # ★★★ 計算結果をキャッシュに保存 ★★★
        if cache_handler and hash_value is not None:
            # imagehashオブジェクトを文字列として保存
            cache_handler.put('phash', image_path, str(hash_value))
        # ★★★★★★★★★★★★★★★★★★★★★★★

        return hash_value, None
    except Exception as e:
        error_msg = f"pHash計算エラー({type(e).__name__}): {e}"
        print(f"エラー: pHash計算中にエラーが発生しました ({os.path.basename(image_path)}): {e}")
        return None, error_msg

# calculate_orb_similarity_score は変更なし (キャッシュ対象外)
def calculate_orb_similarity_score(image_path1: str, image_path2: str,
                                   n_features: int = 1000, ratio_threshold: float = 0.75) -> OrbScoreResult:
    # ... (変更なし) ...
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
        raw_matches: Optional[List[List[cv2.DMatch]]] = bf.knnMatch(des1, des2, k=2)
        good_matches: List[cv2.DMatch] = []
        if raw_matches:
            for match_pair in raw_matches:
                if len(match_pair) == 2:
                    m, n = match_pair
                    if m.distance < ratio_threshold * n.distance: good_matches.append(m)
        return len(good_matches), None
    except cv2.error as e: return None, f"OpenCVエラー(ORB): {e.msg}"
    except MemoryError: return None, "メモリ不足エラー(ORB)"
    except Exception as e: return None, f"予期せぬエラー(ORB): {type(e).__name__} - {e}"


# ★★★ 関数シグネチャに cache_handler を追加 ★★★
def find_similar_pairs(image_paths: List[str],
                       duplicate_paths_set: Set[str],
                       similarity_mode: str = 'phash_orb',
                       orb_nfeatures: int = 1000,
                       orb_ratio_threshold: float = 0.75,
                       min_good_matches_threshold: int = 30,
                       hash_threshold: int = 5,
                       signals: Optional[Any] = None,
                       progress_offset: int = 0,
                       progress_range: int = 100,
                       is_cancelled_func: Optional[Callable[[], bool]] = None,
                       cache_handler: Optional[CacheHandler] = None) -> FindSimilarResult: # ★ cache_handler 追加 ★
    """
    指定された画像パスリスト内の画像を比較し、類似しているペアを見つけます。
    pHashキャッシュを利用します。重複ファイルは比較対象から除外します。中断チェック対応。
    """
    processing_errors: List[ErrorDict] = []
    file_list_errors: List[ErrorDict] = [] # file_list_errors は現状使われていない

    last_progress_emit_time: float = 0.0
    def emit_progress(current_value: int, total_value: int, stage_offset: int, stage_range: float, status_prefix: str) -> None:
        nonlocal last_progress_emit_time; progress: int = stage_offset
        if total_value > 0: progress = stage_offset + int((current_value / total_value) * stage_range)
        status: str = f"{status_prefix} ({current_value}/{total_value})"
        current_time: float = time.time()
        if signals and hasattr(signals, 'progress_update') and hasattr(signals, 'status_update') and \
           (current_value == total_value or current_time - last_progress_emit_time > 0.1):
             signals.progress_update.emit(progress); signals.status_update.emit(status); last_progress_emit_time = current_time

    non_duplicate_paths: List[str] = [p for p in image_paths if p not in duplicate_paths_set]
    num_images_to_compare: int = len(non_duplicate_paths)

    if num_images_to_compare < 2:
        print("重複を除いた結果、比較対象の画像が2枚未満のため類似ペア検出をスキップします。")
        return [], processing_errors, file_list_errors

    print(f"{num_images_to_compare} 個の画像（重複を除く）について類似ペア検出を開始します (モード: {similarity_mode})...")
    candidate_pairs: List[Tuple[str, str]] = []
    similar_pairs: List[SimilarPair] = []

    use_phash_step: bool = similarity_mode in ['phash_orb', 'phash_only']
    use_orb_step: bool = similarity_mode in ['phash_orb', 'orb_only']

    # --- pHash 計算と候補絞り込み (必要な場合) ---
    if use_phash_step:
        if not IMAGEHASH_AVAILABLE:
            processing_errors.append({'type': '設定エラー', 'path': 'N/A', 'error': 'pHashモードが選択されましたが、ImageHashライブラリが見つかりません。'})
            print("警告: ImageHashが見つからないため、ORB Only モードで実行します。")
            use_phash_step = False; use_orb_step = True; similarity_mode = 'orb_only'
        else:
            phash_calc_range: float = progress_range * 0.10 if use_orb_step else progress_range * 0.45
            phash_comp_range: float = progress_range * 0.10 if use_orb_step else progress_range * 0.45
            orb_comp_offset: float = progress_offset + phash_calc_range + phash_comp_range

            hashes: Dict[str, Any] = {}; hash_calculation_count: int = 0; status_prefix_phash_calc: str = "pHash計算中(重複除外)"
            emit_progress(0, num_images_to_compare, int(progress_offset), int(phash_calc_range), status_prefix_phash_calc)
            i: int; path: str
            for i, path in enumerate(non_duplicate_paths):
                if is_cancelled_func and is_cancelled_func():
                    # ★ 中断時にもキャッシュを保存する ★
                    if cache_handler: cache_handler.save_all()
                    return [], processing_errors, []

                # ★★★ calculate_phash に cache_handler を渡す ★★★
                hash_value: HashType; error_msg: ErrorMsgType
                hash_value, error_msg = calculate_phash(path, cache_handler=cache_handler)
                # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

                if error_msg: processing_errors.append({'type': 'pHash計算', 'path': path, 'error': error_msg})
                elif hash_value: hashes[path] = hash_value
                hash_calculation_count += 1; emit_progress(hash_calculation_count, num_images_to_compare, int(progress_offset), int(phash_calc_range), status_prefix_phash_calc)
            print(f"pHash計算完了。{len(hashes)}/{num_images_to_compare} 個のハッシュを取得しました。")

            # pHash 比較 (変更なし、ただし中断時のキャッシュ保存を追加)
            hash_paths: List[str] = list(hashes.keys()); hash_comparisons: int = 0; total_hash_comparisons: int = len(hash_paths) * (len(hash_paths) - 1) // 2
            status_prefix_phash_comp: str = "ハッシュ比較中(重複除外)"; phash_comp_offset: float = progress_offset + phash_calc_range
            emit_progress(0, total_hash_comparisons, int(phash_comp_offset), int(phash_comp_range), status_prefix_phash_comp)
            if total_hash_comparisons > 0:
                path1: str; path2: str
                for i, path1 in enumerate(hash_paths):
                    for j in range(i + 1, len(hash_paths)):
                        if is_cancelled_func and is_cancelled_func():
                            if cache_handler: cache_handler.save_all() # 中断時保存
                            return [], processing_errors, []
                        path2 = hash_paths[j]; hash_comparisons += 1
                        try:
                            # ハッシュオブジェクトが None でないことを確認
                            if hashes.get(path1) is None or hashes.get(path2) is None:
                                continue # ハッシュ計算に失敗したファイルはスキップ
                            distance: int = hashes[path1] - hashes[path2]
                            if distance <= hash_threshold:
                                if similarity_mode == 'phash_only': similar_pairs.append((path1, path2, distance))
                                elif similarity_mode == 'phash_orb': candidate_pairs.append((path1, path2))
                        except Exception as e: processing_errors.append({'type': 'pHash比較', 'path': f"{os.path.basename(path1)} vs {os.path.basename(path2)}", 'path1': path1, 'path2': path2, 'error': f"ハッシュ比較エラー: {e}"})
                        emit_progress(hash_comparisons, total_hash_comparisons, int(phash_comp_offset), int(phash_comp_range), status_prefix_phash_comp)
            emit_progress(total_hash_comparisons, total_hash_comparisons, int(phash_comp_offset), int(phash_comp_range), status_prefix_phash_comp)
            if similarity_mode == 'phash_orb': print(f"pHash候補絞り込み完了。{len(candidate_pairs)} 組の候補ペアが見つかりました。")
            elif similarity_mode == 'phash_only': print(f"pHashによる類似ペア検出完了。{len(similar_pairs)} 組のペアが見つかりました。")

    # --- ORB Only モード (変更なし) ---
    if similarity_mode == 'orb_only':
        candidate_pairs = list(itertools.combinations(non_duplicate_paths, 2))
        orb_comp_range = float(progress_range); orb_comp_offset = float(progress_offset)
        print(f"ORB Only モード: {len(candidate_pairs)} 組のペアを比較します。")
        use_orb_step = True

    # --- ORB 比較 (変更なし、ただし中断時のキャッシュ保存を追加) ---
    if use_orb_step and candidate_pairs:
        orb_comparisons: int = 0; total_orb_comparisons: int = len(candidate_pairs); status_prefix_orb_comp: str = "ORB比較中(重複除外)"
        if not use_phash_step: orb_comp_offset = float(progress_offset); orb_comp_range = float(progress_range)
        else: orb_comp_offset = progress_offset + (progress_range * 0.10) + (progress_range * 0.10); orb_comp_range = progress_range * 0.80
        emit_progress(0, total_orb_comparisons, int(orb_comp_offset), int(orb_comp_range), status_prefix_orb_comp)
        if total_orb_comparisons > 0:
            path1: str; path2: str
            for path1, path2 in candidate_pairs:
                if is_cancelled_func and is_cancelled_func():
                    if cache_handler: cache_handler.save_all() # 中断時保存
                    return similar_pairs, processing_errors, []
                orb_comparisons += 1
                score: Optional[int]; error_msg: ErrorMsgType
                score, error_msg = calculate_orb_similarity_score(path1, path2, n_features=orb_nfeatures, ratio_threshold=orb_ratio_threshold)
                if error_msg: processing_errors.append({'type': 'ORB比較', 'path': f"{os.path.basename(path1)} vs {os.path.basename(path2)}", 'path1': path1, 'path2': path2, 'error': error_msg})
                elif score is not None and score >= min_good_matches_threshold: similar_pairs.append((path1, path2, score))
                emit_progress(orb_comparisons, total_orb_comparisons, int(orb_comp_offset), int(orb_comp_range), status_prefix_orb_comp)
        emit_progress(total_orb_comparisons, total_orb_comparisons, int(orb_comp_offset), int(orb_comp_range), status_prefix_orb_comp)
        print(f"ORB比較完了。")

    # --- 最終結果 ---
    print(f"類似ペア検出完了 (モード: {similarity_mode})。{len(similar_pairs)} 組の類似ペアが見つかりました。{len(processing_errors)} 件のエラーが発生しました。")

    # ★ 処理完了後にキャッシュを保存 ★
    if cache_handler:
        cache_handler.save_all()

    return similar_pairs, processing_errors, []

