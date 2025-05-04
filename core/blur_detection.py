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
        float: FFTベースのブレ度スコア(比率)。0.0〜1.0の範囲。
               画像が読み込めない場合やエラー時は -1.0 を返す。
               スコアが高いほどシャープ。
    """
    # ファイル存在チェックは呼び出し元で行う想定でも良い
    if not os.path.exists(image_path):
        # print(f"エラー: 画像ファイルが見つかりません: {image_path}")
        return -1.0

    try:
        # 1. 画像をグレースケールで読み込む
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            # print(f"エラー: 画像ファイルを読み込めません: {image_path}")
            return -1.0

        # 2. 画像の次元を取得
        h, w = img.shape
        # 中心座標
        crow, ccol = h // 2 , w // 2

        # 3. FFTを実行 (2次元DFT) & 中心シフト
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

        # デバッグ用出力 (必要ならコメント解除)
        # print(f"Debug ({os.path.basename(image_path)}): Total={total_magnitude_sum:.2f}, LowFreq={low_freq_magnitude_sum:.2f}, Radius={radius}")

        # 7. スコア計算 (比率)
        if total_magnitude_sum <= 0:
             return 0.0
        # 念のためマイナスにならないように
        if low_freq_magnitude_sum < 0:
             low_freq_magnitude_sum = 0
        if low_freq_magnitude_sum > total_magnitude_sum: # 丸め誤差などで稀に起こる可能性
             low_freq_magnitude_sum = total_magnitude_sum

        high_freq_magnitude_sum = total_magnitude_sum - low_freq_magnitude_sum
        score = high_freq_magnitude_sum / total_magnitude_sum

        return score

    except Exception as e:
        # 実行時エラーが発生した場合
        print(f"エラー: ブレ検出処理中に例外が発生しました ({os.path.basename(image_path)}): {e}")
        return -1.0

# このファイルはモジュールとして使われるため、
# if __name__ == '__main__': ブロックは含めません。