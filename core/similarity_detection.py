# core/similarity_detection.py
import cv2
import numpy as np
import os
import itertools
import time
from PIL import Image

# ★ 画像ローダー関数をインポート ★
try:
    # pillow-heif 登録のために image_loader をインポートしておく
    from utils.image_loader import load_image_pil, load_image_as_numpy, HEIF_AVAILABLE
except ImportError:
    print("エラー: utils.image_loader のインポートに失敗しました。")
    def load_image_pil(path): return None, "Image loader not available"
    def load_image_as_numpy(path, mode='gray'): return None, "Image loader not available"
    HEIF_AVAILABLE = False # 利用不可として扱う

try:
    import imagehash
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
    print("警告: ImageHash ライブラリが見つかりません。")


def calculate_phash(image_path):
    """指定された画像の Perceptual Hash (pHash) を計算します。HEIC対応。"""
    if not IMAGEHASH_AVAILABLE: return None, "ImageHashライブラリが利用できません"

    # ★ Pillow ローダーを使用 ★
    img_pil, error_msg = load_image_pil(image_path)
    if error_msg: return None, error_msg
    if not img_pil: return None, "Pillowイメージの取得に失敗 (pHash)"

    try:
        hash_value = imagehash.phash(img_pil)
        return hash_value, None
    except Exception as e:
        error_msg = f"pHash計算エラー({type(e).__name__}): {e}"
        print(f"エラー: pHash計算中にエラーが発生しました ({os.path.basename(image_path)}): {e}")
        return None, error_msg

def calculate_orb_similarity_score(image_path1, image_path2, n_features=1000, ratio_threshold=0.75):
    """ORB特徴量を用いて類似度スコアを計算します。HEIC対応。"""
    # ★ 画像ローダーでグレースケール画像を読み込み ★
    img1_gray, err1 = load_image_as_numpy(image_path1, mode='gray')
    if err1: return None, f"画像1読込エラー: {err1}"
    img2_gray, err2 = load_image_as_numpy(image_path2, mode='gray')
    if err2: return None, f"画像2読込エラー: {err2}"

    if img1_gray is None or img2_gray is None:
        return None, "画像データの取得に失敗 (ORB)"

    try:
        orb = cv2.ORB_create(nfeatures=n_features)
        # ★ 既にグレースケールなのでそのまま渡す ★
        kp1, des1 = orb.detectAndCompute(img1_gray, None)
        kp2, des2 = orb.detectAndCompute(img2_gray, None)

        if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2: return 0, None

        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        matches = bf.knnMatch(des1, des2, k=2)
        good_matches = []
        if matches is not None:
            for match_pair in matches:
                if len(match_pair) == 2:
                    m, n = match_pair
                    if m.distance < ratio_threshold * n.distance: good_matches.append(m)
        return len(good_matches), None

    except cv2.error as e: return None, f"OpenCVエラー(ORB): {e.msg}"
    except MemoryError: return None, "メモリ不足エラー(ORB)"
    except Exception as e: return None, f"予期せぬエラー(ORB): {type(e).__name__}"


# find_similar_pairs 関数は画像読み込みを直接行わないので変更不要
def find_similar_pairs(directory_path,
                       orb_nfeatures=1000,
                       orb_ratio_threshold=0.75,
                       min_good_matches_threshold=30,
                       hash_threshold=5,
                       use_phash=True,
                       file_extensions=('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.heic', '.heif'),
                       signals=None,
                       progress_offset=0,
                       progress_range=100):
    """指定されたディレクトリ内の画像を比較し、類似しているペアを見つけます。"""
    processing_errors = []
    file_list_errors = []

    last_progress_emit_time = 0
    def emit_progress(current_value, total_value, stage_offset, stage_range, status_prefix):
        nonlocal last_progress_emit_time; progress = stage_offset
        if total_value > 0: progress = stage_offset + int((current_value / total_value) * stage_range)
        status = f"{status_prefix} ({current_value}/{total_value})"; current_time = time.time()
        if signals and (current_value == total_value or current_time - last_progress_emit_time > 0.1):
             signals.progress_update.emit(progress); signals.status_update.emit(status); last_progress_emit_time = current_time

    if signals: signals.status_update.emit("ファイルリスト取得中...")
    image_paths = []
    try:
        for filename in os.listdir(directory_path):
            if filename.lower().endswith(file_extensions):
                full_path = os.path.join(directory_path, filename)
                if os.path.isfile(full_path) and not os.path.islink(full_path): image_paths.append(full_path)
    except OSError as e: return [], [{'type': 'ディレクトリ読込', 'path': directory_path, 'error': str(e)}], []
    except Exception as e: return [], [{'type': 'ファイルリスト取得', 'path': directory_path, 'error': str(e)}], []
    if len(image_paths) < 2: return [], [], []

    num_images = len(image_paths); print(f"{num_images} 個の画像を検出。類似ペア検出を開始します...")
    candidate_pairs = []; similar_pairs = []

    if use_phash and IMAGEHASH_AVAILABLE:
        phash_calc_range = progress_range * 0.10; phash_comp_range = progress_range * 0.10
        orb_comp_range = progress_range * 0.80; orb_comp_offset = progress_offset + phash_calc_range + phash_comp_range
        hashes = {}; hash_calculation_count = 0; status_prefix_phash_calc = "pHash計算中"
        emit_progress(0, num_images, progress_offset, phash_calc_range, status_prefix_phash_calc)
        for i, path in enumerate(image_paths):
            hash_value, error_msg = calculate_phash(path) # calculate_phash が HEIC 対応済み
            if error_msg: processing_errors.append({'type': 'pHash計算', 'path': path, 'error': error_msg})
            elif hash_value: hashes[path] = hash_value
            hash_calculation_count += 1; emit_progress(hash_calculation_count, num_images, progress_offset, phash_calc_range, status_prefix_phash_calc)
        print(f"pHash計算完了。{len(hashes)}/{num_images} 個のハッシュを計算しました。")

        hash_paths = list(hashes.keys()); hash_comparisons = 0; total_hash_comparisons = len(hash_paths) * (len(hash_paths) - 1) // 2
        status_prefix_phash_comp = "ハッシュ比較中"; phash_comp_offset = progress_offset + phash_calc_range
        emit_progress(0, total_hash_comparisons, phash_comp_offset, phash_comp_range, status_prefix_phash_comp)
        if total_hash_comparisons > 0:
            for i, path1 in enumerate(hash_paths):
                for j in range(i + 1, len(hash_paths)):
                    path2 = hash_paths[j]; hash_comparisons += 1
                    try:
                        distance = hashes[path1] - hashes[path2]
                        if distance <= hash_threshold: candidate_pairs.append((path1, path2))
                    except Exception as e: processing_errors.append({'type': 'pHash比較', 'path': f"{os.path.basename(path1)} vs {os.path.basename(path2)}", 'path1': path1, 'path2': path2, 'error': f"ハッシュ比較エラー: {e}"})
                    emit_progress(hash_comparisons, total_hash_comparisons, phash_comp_offset, phash_comp_range, status_prefix_phash_comp)
        emit_progress(total_hash_comparisons, total_hash_comparisons, phash_comp_offset, phash_comp_range, status_prefix_phash_comp)
        print(f"候補絞り込み完了。{len(candidate_pairs)} 組の候補ペアが見つかりました。")
    else:
        if not use_phash: print("pHashを使用せずにORB比較を行います (総当たり)。")
        elif not IMAGEHASH_AVAILABLE: print("ImageHashライブラリがないため、pHashを使用せずにORB比較を行います (総当たり)。")
        candidate_pairs = list(itertools.combinations(image_paths, 2)); orb_comp_range = progress_range; orb_comp_offset = progress_offset
        print(f"{len(candidate_pairs)} 組のペアをORBで比較します。")

    orb_comparisons = 0; total_orb_comparisons = len(candidate_pairs); status_prefix_orb_comp = "ORB比較中"
    emit_progress(0, total_orb_comparisons, orb_comp_offset, orb_comp_range, status_prefix_orb_comp)
    if total_orb_comparisons > 0:
        for path1, path2 in candidate_pairs:
            orb_comparisons += 1
            # calculate_orb_similarity_score が HEIC 対応済み
            score, error_msg = calculate_orb_similarity_score(path1, path2, n_features=orb_nfeatures, ratio_threshold=orb_ratio_threshold)
            if error_msg: processing_errors.append({'type': 'ORB比較', 'path': f"{os.path.basename(path1)} vs {os.path.basename(path2)}", 'path1': path1, 'path2': path2, 'error': error_msg})
            elif score is not None and score >= min_good_matches_threshold: similar_pairs.append((path1, path2, score))
            emit_progress(orb_comparisons, total_orb_comparisons, orb_comp_offset, orb_comp_range, status_prefix_orb_comp)
    emit_progress(total_orb_comparisons, total_orb_comparisons, orb_comp_offset, orb_comp_range, status_prefix_orb_comp)
    print(f"類似ペア検出完了。{len(similar_pairs)} 組の類似ペアが見つかりました。{len(processing_errors)} 件のエラーが発生しました。")
    return similar_pairs, processing_errors, file_list_errors
