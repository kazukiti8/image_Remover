# core/blur_detection.py
import cv2
import numpy as np
import os
from typing import Tuple, Optional, Any

# ★ 型エイリアス ★
NumpyImageType = np.ndarray[Any, Any]
ErrorMsgType = Optional[str]
BlurResult = Tuple[Optional[float], ErrorMsgType] # (スコア or None, エラーメッセージ or None)

# 画像ローダー関数をインポート
try:
    from ..utils.image_loader import load_image_as_numpy
except ImportError:
    try:
        from utils.image_loader import load_image_as_numpy
    except ImportError:
        print("エラー: utils.image_loader のインポートに失敗しました。")
        def load_image_as_numpy(path: str, mode: str = 'gray') -> Tuple[Optional[NumpyImageType], ErrorMsgType]:
            return None, "Image loader not available"

def calculate_fft_blur_score_v2(image_path: str, low_freq_radius_ratio: float = 0.05) -> BlurResult:
    """
    FFTを使用して画像のブレ度合いを評価するスコア(v2)を計算します。
    スコアが高いほどシャープ (1.0に近い)。HEIC/HEIF形式に対応。

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
        return None, "画像データの取得に失敗 (blur_detection FFT)"

    try:
        h, w = img_gray.shape
        crow, ccol = h // 2, w // 2

        img_float32 = np.float32(img_gray)
        dft = cv2.dft(img_float32, flags=cv2.DFT_COMPLEX_OUTPUT)
        dft_shift = np.fft.fftshift(dft)

        magnitude_spectrum = cv2.magnitude(dft_shift[:, :, 0], dft_shift[:, :, 1])

        radius = int(low_freq_radius_ratio * min(h, w))
        radius = max(1, radius)
        mask = np.zeros((h, w), np.uint8)
        cv2.circle(mask, (ccol, crow), radius, 1, thickness=-1)

        total_magnitude_sum = np.sum(magnitude_spectrum)
        # マスク外（高周波成分）の合計を計算
        high_freq_magnitude_sum = np.sum(magnitude_spectrum * (1 - mask))

        if total_magnitude_sum <= 1e-6: # ほぼゼロ除算を避ける
            print(f"警告: FFTマグニチュード合計がほぼゼロです ({os.path.basename(image_path)})")
            return 0.0, None # 真っ黒画像などはスコア0とする

        score = high_freq_magnitude_sum / total_magnitude_sum
        # スコアが負にならないようにクリップ (念のため)
        score = max(0.0, min(1.0, score))

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

# ★★★ Laplacian variance を計算する関数を追加 ★★★
def calculate_laplacian_variance(image_path: str) -> BlurResult:
    """
    Laplacian variance を使用して画像のブレ度合いを評価します。
    スコアが高いほどシャープ。HEIC/HEIF形式に対応。

    Args:
        image_path (str): 評価する画像ファイルのパス。

    Returns:
        BlurResult: (分散値: float or None, エラーメッセージ: str or None)
                     スコアは通常 0 から数千の範囲になる。閾値は別途設定が必要。
    """
    img_gray: Optional[NumpyImageType]
    error_msg: ErrorMsgType
    img_gray, error_msg = load_image_as_numpy(image_path, mode='gray')

    if error_msg:
        return None, error_msg
    if img_gray is None:
        return None, "画像データの取得に失敗 (blur_detection Laplacian)"

    try:
        # Laplacian オペレータを適用し、その分散を計算
        # ksize=3 は一般的な値
        variance_of_laplacian: float = cv2.Laplacian(img_gray, cv2.CV_64F, ksize=3).var()
        return variance_of_laplacian, None

    except cv2.error as e:
        error_msg = f"OpenCVエラー(Laplacian): {e.msg}"
        print(f"エラー: ブレ検出Laplacian処理中にOpenCVエラー ({os.path.basename(image_path)}): {e.msg}")
        return None, error_msg
    except MemoryError:
        error_msg = "メモリ不足エラー(Laplacian)"
        print(f"エラー: ブレ検出Laplacian処理中にメモリ不足 ({os.path.basename(image_path)})")
        return None, error_msg
    except Exception as e:
        error_msg = f"予期せぬエラー(Laplacian): {type(e).__name__}"
        print(f"エラー: ブレ検出Laplacian処理中に予期せぬ例外 ({os.path.basename(image_path)}): {e}")
        return None, error_msg
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

