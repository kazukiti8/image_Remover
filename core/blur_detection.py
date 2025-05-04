# core/blur_detection.py
import cv2
import numpy as np
import os

# ★ 画像ローダー関数をインポート ★
try:
    from utils.image_loader import load_image_as_numpy
except ImportError:
    print("エラー: utils.image_loader のインポートに失敗しました。")
    # ダミー関数 (エラーを返す)
    def load_image_as_numpy(path, mode='gray'):
        return None, "Image loader not available"

def calculate_fft_blur_score_v2(image_path, low_freq_radius_ratio=0.05):
    """
    FFTを使用して画像のブレ度合いを評価するスコア(v2)を計算します。
    HEIC/HEIF形式に対応。
    """
    # ★ 画像をグレースケールで読み込み (NumPy配列) ★
    img_gray, error_msg = load_image_as_numpy(image_path, mode='gray')

    if error_msg:
        # 読み込みエラーメッセージをそのまま返す
        return None, error_msg
    if img_gray is None: # 念のためNoneチェック
        return None, "画像データの取得に失敗 (blur_detection)"

    try:
        # 2. 画像の次元を取得
        h, w = img_gray.shape
        crow, ccol = h // 2 , w // 2

        # 3. FFTを実行 & 中心シフト
        # ★ img_gray は既に NumPy 配列 (float32に変換) ★
        dft = cv2.dft(np.float32(img_gray), flags=cv2.DFT_COMPLEX_OUTPUT)
        dft_shift = np.fft.fftshift(dft)

        # 4. 振幅スペクトルを計算
        magnitude_spectrum = cv2.magnitude(dft_shift[:, :, 0], dft_shift[:, :, 1])

        # 5. 低周波領域マスク
        radius = int(low_freq_radius_ratio * min(h, w)); radius = max(1, radius)
        mask = np.zeros((h, w), np.uint8)
        cv2.circle(mask, (ccol, crow), radius, 1, thickness=-1)

        # 6. エネルギー計算
        total_magnitude_sum = np.sum(magnitude_spectrum)
        low_freq_magnitude_sum = np.sum(magnitude_spectrum * mask)

        # 7. スコア計算
        if total_magnitude_sum <= 0: return 0.0, None
        low_freq_magnitude_sum = max(0, low_freq_magnitude_sum)
        low_freq_magnitude_sum = min(low_freq_magnitude_sum, total_magnitude_sum)
        high_freq_magnitude_sum = total_magnitude_sum - low_freq_magnitude_sum
        score = high_freq_magnitude_sum / total_magnitude_sum

        return score, None # 成功

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
