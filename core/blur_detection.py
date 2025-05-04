# core/blur_detection.py
import cv2
import numpy as np
import os

def calculate_fft_blur_score_v2(image_path, low_freq_radius_ratio=0.05):
    """
    FFTを使用して画像のブレ度合いを評価するスコア(v2)を計算します。
    スコアは高周波成分エネルギーの総エネルギーに対する比率です (0.0〜1.0)。
    スコアが高い(1.0に近い)ほどシャープであると推定されます。

    Args:
        image_path (str): 評価する画像ファイルのパス。
        low_freq_radius_ratio (float): 画像中心からの半径の比率。
                                       この半径内を低周波領域とみなす。
                                       デフォルトは0.05 (画像幅・高さの小さい方の5%)。

    Returns:
        tuple: (float or None, str or None)
               成功時は (スコア, None)。スコアは 0.0〜1.0。
               失敗時は (None, エラーメッセージ)。
    """
    if not os.path.exists(image_path):
        # ファイルが存在しない場合はエラーメッセージを返す
        return None, f"ファイルが見つかりません: {os.path.basename(image_path)}"

    try:
        # 1. 画像をグレースケールで読み込む
        # Note: imreadはファイルが存在しない場合Noneを返し、エラーは発生させないことが多い
        # しかし、ファイル破損や非対応フォーマットの場合にエラーを出す可能性がある
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            # 読み込み自体は成功したが、画像データが得られなかった場合
            # (例: サポートされていないフォーマット、ファイルが0バイトなど)
            return None, f"画像を読み込めません(形式/破損?): {os.path.basename(image_path)}"

        # 2. 画像の次元を取得
        h, w = img.shape
        # 中心座標
        crow, ccol = h // 2 , w // 2

        # 3. FFTを実行 (2次元DFT) & 中心シフト
        # メモリ不足などのエラーが発生する可能性
        dft = cv2.dft(np.float32(img), flags=cv2.DFT_COMPLEX_OUTPUT)
        dft_shift = np.fft.fftshift(dft)

        # 4. 振幅スペクトルを計算
        magnitude_spectrum = cv2.magnitude(dft_shift[:, :, 0], dft_shift[:, :, 1])

        # 5. 低周波領域をマスクするための準備 (円形マスク)
        radius = int(low_freq_radius_ratio * min(h, w))
        if radius <= 0:
             radius = 1 # 半径は最低1

        mask = np.zeros((h, w), np.uint8)
        # 中心(ccol, crow)に半径radiusの円を描画(塗りつぶし)
        cv2.circle(mask, (ccol, crow), radius, 1, thickness=-1)

        # 6. エネルギー(振幅の合計)を計算
        total_magnitude_sum = np.sum(magnitude_spectrum)
        # マスク(円内部が1, それ以外が0)を掛けて低周波領域のエネルギーを計算
        low_freq_magnitude_sum = np.sum(magnitude_spectrum * mask)

        # 7. スコア計算 (比率)
        if total_magnitude_sum <= 0:
             # 通常、真っ黒な画像などで発生しうるが、エラーとは断定しにくい
             return 0.0, None # スコア0として扱う

        # 念のためマイナスにならないように
        if low_freq_magnitude_sum < 0:
             low_freq_magnitude_sum = 0
        if low_freq_magnitude_sum > total_magnitude_sum: # 丸め誤差などで稀に起こる可能性
             low_freq_magnitude_sum = total_magnitude_sum

        high_freq_magnitude_sum = total_magnitude_sum - low_freq_magnitude_sum
        score = high_freq_magnitude_sum / total_magnitude_sum

        return score, None # 成功

    except cv2.error as e:
        # OpenCV固有のエラー (メモリ不足、不正な引数など)
        error_msg = f"OpenCVエラー: {e.msg}"
        print(f"エラー: ブレ検出処理中にOpenCVエラーが発生しました ({os.path.basename(image_path)}): {e.msg}")
        return None, error_msg
    except MemoryError:
        # メモリ不足エラー
        error_msg = "メモリ不足エラー"
        print(f"エラー: ブレ検出処理中にメモリ不足が発生しました ({os.path.basename(image_path)})")
        return None, error_msg
    except Exception as e:
        # その他の予期せぬエラー
        error_msg = f"予期せぬエラー: {type(e).__name__}"
        print(f"エラー: ブレ検出処理中に予期せぬ例外が発生しました ({os.path.basename(image_path)}): {e}")
        return None, error_msg

# このファイルはモジュールとして使われるため、
# if __name__ == '__main__': ブロックは含めません。
