# core/blur_detection.py
import cv2
import numpy as np
import os
from typing import Tuple, Optional, Any

# ★ 型エイリアス ★
NumpyImageType = np.ndarray[Any, Any]
ErrorMsgType = Optional[str]
BlurResult = Tuple[Optional[float], ErrorMsgType]

# 画像ローダー関数をインポート
try:
    from ..utils.image_loader import load_image_as_numpy
except ImportError:
    try: from utils.image_loader import load_image_as_numpy
    except ImportError:
        print("エラー: utils.image_loader のインポートに失敗しました。")
        def load_image_as_numpy(path: str, mode: str = 'gray') -> Tuple[Optional[NumpyImageType], ErrorMsgType]:
            return None, "Image loader not available"

def calculate_fft_blur_score_v2(image_path: str, low_freq_radius_ratio: float = 0.05) -> BlurResult:
    """
    FFTを使用して画像のブレ度合いを評価するスコア(v2)を計算します。
    エラーハンドリングを詳細化。
    """
    filename = os.path.basename(image_path) # エラーメッセージ用
    img_gray: Optional[NumpyImageType]
    error_msg_load: ErrorMsgType
    img_gray, error_msg_load = load_image_as_numpy(image_path, mode='gray')

    if error_msg_load:
        # ★ 読み込みエラーメッセージをそのまま返す ★
        return None, f"画像読込失敗({error_msg_load}): {filename}"
    if img_gray is None:
        return None, f"画像データ取得失敗(NumPy空): {filename}"

    try:
        h, w = img_gray.shape
        # ★ 画像サイズが小さすぎる場合のチェック (任意) ★
        if h < 4 or w < 4: # FFTにはある程度のサイズが必要
            return None, f"画像サイズが小さすぎます({w}x{h}): {filename}"

        crow, ccol = h // 2, w // 2

        # float32に変換
        img_float32 = np.float32(img_gray)
        # DFT計算
        dft = cv2.dft(img_float32, flags=cv2.DFT_COMPLEX_OUTPUT)
        # エラーチェック (dftがNoneになることは通常ないが念のため)
        if dft is None:
            return None, f"FFT計算結果がNone: {filename}"

        dft_shift = np.fft.fftshift(dft)
        # エラーチェック (fftshiftがNoneになることは通常ない)
        if dft_shift is None:
             return None, f"FFTシフト結果がNone: {filename}"

        # magnitude 計算
        magnitude_spectrum = cv2.magnitude(dft_shift[:, :, 0], dft_shift[:, :, 1])

        # マスク作成
        radius = int(low_freq_radius_ratio * min(h, w))
        radius = max(1, radius)
        mask = np.zeros((h, w), np.uint8)
        cv2.circle(mask, (ccol, crow), radius, 1, thickness=-1)

        # 合計計算
        total_magnitude_sum = np.sum(magnitude_spectrum)
        high_freq_magnitude_sum = np.sum(magnitude_spectrum * (1 - mask))

        if total_magnitude_sum <= 1e-6:
            print(f"情報: FFTマグニチュード合計ほぼゼロ: {filename}")
            return 0.0, None # スコア0とする

        score = high_freq_magnitude_sum / total_magnitude_sum
        score = max(0.0, min(1.0, score)) # 0.0-1.0 の範囲に収める

        return score, None

    except cv2.error as e:
        error_msg = f"OpenCVエラー(FFT {e.funcName}: {e.msg})"
        print(f"エラー: {error_msg} - {filename}")
        return None, error_msg
    except MemoryError:
        error_msg = f"メモリ不足エラー(FFT): {filename}"
        print(f"エラー: {error_msg}")
        return None, error_msg
    except ValueError as e: # 例: np.fftshift などでのエラー
        error_msg = f"値エラー(FFT {e})"
        print(f"エラー: {error_msg} - {filename}")
        return None, error_msg
    except Exception as e:
        error_type = type(e).__name__
        error_msg = f"予期せぬエラー(FFT {error_type}: {e})"
        print(f"エラー: {error_msg} - {filename}")
        return None, error_msg

def calculate_laplacian_variance(image_path: str) -> BlurResult:
    """
    Laplacian variance を使用して画像のブレ度合いを評価します。
    エラーハンドリングを詳細化。
    """
    filename = os.path.basename(image_path) # エラーメッセージ用
    img_gray: Optional[NumpyImageType]
    error_msg_load: ErrorMsgType
    img_gray, error_msg_load = load_image_as_numpy(image_path, mode='gray')

    if error_msg_load:
        return None, f"画像読込失敗({error_msg_load}): {filename}"
    if img_gray is None:
        return None, f"画像データ取得失敗(NumPy空): {filename}"

    try:
        # ★ 画像サイズチェック (任意) ★
        h, w = img_gray.shape
        if h < 3 or w < 3: # Laplacian ksize=3 のため
             return None, f"画像サイズが小さすぎます({w}x{h}): {filename}"

        # Laplacian オペレータを適用し、その分散を計算
        laplacian = cv2.Laplacian(img_gray, cv2.CV_64F, ksize=3)
        if laplacian is None:
            return None, f"Laplacian計算結果がNone: {filename}"

        variance_of_laplacian = laplacian.var()
        return float(variance_of_laplacian), None # floatにキャスト

    except cv2.error as e:
        error_msg = f"OpenCVエラー(Laplacian {e.funcName}: {e.msg})"
        print(f"エラー: {error_msg} - {filename}")
        return None, error_msg
    except MemoryError:
        error_msg = f"メモリ不足エラー(Laplacian): {filename}"
        print(f"エラー: {error_msg}")
        return None, error_msg
    except Exception as e:
        error_type = type(e).__name__
        error_msg = f"予期せぬエラー(Laplacian {error_type}: {e})"
        print(f"エラー: {error_msg} - {filename}")
        return None, error_msg
