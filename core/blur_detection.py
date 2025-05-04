# core/blur_detection.py
import cv2
import numpy as np
import os
from typing import Tuple, Optional, Any # ★ typing をインポート ★

# ★ 型エイリアス ★
NumpyImageType = np.ndarray[Any, Any]
ErrorMsgType = Optional[str]
BlurResult = Tuple[Optional[float], ErrorMsgType] # (スコア or None, エラーメッセージ or None)

# 画像ローダー関数をインポート
try:
    # utils パッケージからの相対インポートを試みる
    # (このファイルが core パッケージ内にある前提)
    from ..utils.image_loader import load_image_as_numpy
except ImportError:
    # インポート失敗時のフォールバック (プロジェクト構造に依存)
    try:
        from utils.image_loader import load_image_as_numpy
    except ImportError:
        print("エラー: utils.image_loader のインポートに失敗しました。")
        # ダミー関数
        def load_image_as_numpy(path: str, mode: str = 'gray') -> Tuple[Optional[NumpyImageType], ErrorMsgType]:
            return None, "Image loader not available"

def calculate_fft_blur_score_v2(image_path: str, low_freq_radius_ratio: float = 0.05) -> BlurResult:
    """
    FFTを使用して画像のブレ度合いを評価するスコア(v2)を計算します。
    HEIC/HEIF形式に対応。

    Args:
        image_path (str): 評価する画像ファイルのパス。
        low_freq_radius_ratio (float): 画像中心からの半径の比率。

    Returns:
        BlurResult: (スコア: float or None, エラーメッセージ: str or None)
    """
    img_gray: Optional[NumpyImageType]
    error_msg: ErrorMsgType
    img_gray, error_msg = load_image_as_numpy(image_path, mode='gray')

    if error_msg:
        return None, error_msg
    if img_gray is None:
        return None, "画像データの取得に失敗 (blur_detection)"

    try:
        h: int
        w: int
        h, w = img_gray.shape
        crow: int = h // 2
        ccol: int = w // 2

        # float32に変換
        img_float32: np.ndarray[Any, np.dtype[np.float32]] = np.float32(img_gray)
        dft: np.ndarray[Any, Any] = cv2.dft(img_float32, flags=cv2.DFT_COMPLEX_OUTPUT)
        dft_shift: np.ndarray[Any, Any] = np.fft.fftshift(dft)

        magnitude_spectrum: np.ndarray[Any, Any] = cv2.magnitude(dft_shift[:, :, 0], dft_shift[:, :, 1])

        radius: int = int(low_freq_radius_ratio * min(h, w))
        radius = max(1, radius) # 半径は最低1
        mask: np.ndarray[Any, np.dtype[np.uint8]] = np.zeros((h, w), np.uint8)
        cv2.circle(mask, (ccol, crow), radius, 1, thickness=-1)

        total_magnitude_sum: float = np.sum(magnitude_spectrum)
        low_freq_magnitude_sum: float = np.sum(magnitude_spectrum * mask)

        if total_magnitude_sum <= 0:
            return 0.0, None

        low_freq_magnitude_sum = max(0.0, low_freq_magnitude_sum)
        low_freq_magnitude_sum = min(low_freq_magnitude_sum, total_magnitude_sum)
        high_freq_magnitude_sum: float = total_magnitude_sum - low_freq_magnitude_sum
        score: float = high_freq_magnitude_sum / total_magnitude_sum

        return score, None

    except cv2.error as e:
        error_msg = f"OpenCVエラー(FFT): {e.msg}"
        print(f"エラー: ブレ検出FFT処理中にOpenCVエラー ({os.path.basename(image_path)}): {e.msg}")
        return None, error_msg
    except MemoryError:
        error_msg = "メモリ不足エラー(FFT)"
        print(f"エラー: ブレ検出FFT処理中にメモリ不足 ({os.path.basename(image_path)})")
        return None, error_msg
    except Exception as e:
        error_msg = f"予期せぬエラー(FFT): {type(e).__name__}"
        print(f"エラー: ブレ検出FFT処理中に予期せぬ例外 ({os.path.basename(image_path)}): {e}")
        return None, error_msg
