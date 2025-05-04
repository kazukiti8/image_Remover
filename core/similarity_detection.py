# core/similarity_detection.py
import cv2
import numpy as np
import os
import itertools # ペア生成に使用

def calculate_orb_similarity_score(image_path1, image_path2, n_features=1000, ratio_threshold=0.75):
    """
    ORB特徴量を用いて2つの画像の類似度スコア(良いマッチング数)を計算します。

    Args:
        image_path1 (str): 比較する画像1のパス。
        image_path2 (str): 比較する画像2のパス。
        n_features (int): 検出するORB特徴量の最大数。
        ratio_threshold (float): 良いマッチングを選別するためのRatio Testの閾値。

    Returns:
        tuple: (int or None, str or None)
               成功時は (良いマッチング数, None)。
               失敗時は (None, エラーメッセージ)。
               ファイルが見つからない、読み込めない場合もエラーとして扱う。
    """
    # ファイル存在チェック
    if not os.path.exists(image_path1):
        return None, f"ファイル1が見つかりません: {os.path.basename(image_path1)}"
    if not os.path.exists(image_path2):
        return None, f"ファイル2が見つかりません: {os.path.basename(image_path2)}"

    try:
        # 画像をグレースケールで読み込み
        img1 = cv2.imread(image_path1, cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imread(image_path2, cv2.IMREAD_GRAYSCALE)

        # 画像読み込みチェック
        if img1 is None:
            return None, f"画像1を読み込めません(形式/破損?): {os.path.basename(image_path1)}"
        if img2 is None:
            return None, f"画像2を読み込めません(形式/破損?): {os.path.basename(image_path2)}"

        # 1. ORB検出器の初期化
        orb = cv2.ORB_create(nfeatures=n_features)

        # 2. キーポイントと記述子の検出
        kp1, des1 = orb.detectAndCompute(img1, None)
        kp2, des2 = orb.detectAndCompute(img2, None)

        # 記述子がない場合、または少なすぎる場合はマッチング不可
        if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2:
            # 特徴点が検出できないのはエラーではなく、マッチ数0とする
            return 0, None

        # 3. BFMatcherの初期化 (ハミング距離)
        # crossCheck=False の方が knnMatch と組み合わせる際に一般的
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

        # 4. knnマッチング (k=2)
        # 記述子 des1, des2 が空でないことは上でチェック済み
        matches = bf.knnMatch(des1, des2, k=2)

        # 5. Ratio Test を適用して良いマッチングを選別
        good_matches = []
        # knnMatchがNoneを返したり、内部のペアが1つしかない場合を考慮
        if matches is not None:
            for match_pair in matches:
                # マッチペアの長さが2であることを確認 (k=2で呼んでいるので通常は満たすはず)
                if len(match_pair) == 2:
                    m, n = match_pair
                    # Ratio Test: 1番目のマッチ m の距離が、2番目のマッチ n の距離の ratio_threshold 倍より小さいか
                    if m.distance < ratio_threshold * n.distance:
                        good_matches.append(m)
                # else:
                    # k=2 で knnMatch を呼んでいるので、通常ここは通らないはずだが念のため
                    # print(f"警告: マッチペアの長さが不正です ({len(match_pair)}) - {os.path.basename(image_path1)} vs {os.path.basename(image_path2)}")

        # 6. 良いマッチング数を返す
        return len(good_matches), None # 成功

    except cv2.error as e:
        # OpenCV固有のエラー (メモリ不足、不正な引数など)
        error_msg = f"OpenCVエラー: {e.msg}"
        print(f"エラー: ORB類似度計算中にOpenCVエラー ({os.path.basename(image_path1)}, {os.path.basename(image_path2)}): {e.msg}")
        return None, error_msg
    except MemoryError:
        # メモリ不足エラー
        error_msg = "メモリ不足エラー"
        print(f"エラー: ORB類似度計算中にメモリ不足 ({os.path.basename(image_path1)}, {os.path.basename(image_path2)})")
        return None, error_msg
    except Exception as e:
        # その他の予期せぬエラー
        error_msg = f"予期せぬエラー: {type(e).__name__}"
        print(f"エラー: ORB類似度計算中に予期せぬエラー ({os.path.basename(image_path1)}, {os.path.basename(image_path2)}): {e}")
        return None, error_msg

def find_similar_pairs(directory_path, orb_nfeatures=1000, orb_ratio_threshold=0.75, min_good_matches_threshold=30, file_extensions=('.jpg', '.jpeg', '.png', '.bmp', '.tiff')):
    """
    指定されたディレクトリ内の画像を比較し、類似しているペアを見つけます。
    エラーが発生した比較も記録します。

    Args:
        directory_path (str): 画像が格納されているディレクトリのパス。
        orb_nfeatures (int): ORB特徴量の最大数。
        orb_ratio_threshold (float): ORBのRatio Test閾値。
        min_good_matches_threshold (int): 類似ペアと判断するための最低限の良いマッチング数。
        file_extensions (tuple): スキャン対象とする画像の拡張子。

    Returns:
        tuple: (list, list, list)
               - similar_pairs: 類似ペアのリスト [(image_path1, image_path2, score), ...]
               - comparison_errors: 比較中にエラーが発生したペアの情報リスト
                                    [{'path1': path1, 'path2': path2, 'error': msg}, ...]
               - file_list_errors: ファイルリスト取得時のエラー情報リスト (現状は未使用だが将来用)
    """
    comparison_errors = []
    file_list_errors = [] # 将来的にファイルリスト取得エラーも返す可能性

    if not os.path.isdir(directory_path):
        # ディレクトリが存在しない場合はエラー情報を返す
        print(f"エラー: ディレクトリが見つかりません: {directory_path}")
        # このエラーは呼び出し元 (ScanWorker) で処理される想定だが、ここでも情報を生成
        return [], [{'path1': 'N/A', 'path2': 'N/A', 'error': f"ディレクトリが見つかりません: {directory_path}"}], []

    image_paths = []
    try:
        # ファイル一覧取得とフィルタリング
        for filename in os.listdir(directory_path):
            # 拡張子を小文字にして比較
            if filename.lower().endswith(file_extensions):
                full_path = os.path.join(directory_path, filename)
                # ファイルであり、シンボリックリンクでないことを確認
                if os.path.isfile(full_path) and not os.path.islink(full_path):
                    image_paths.append(full_path)
    except OSError as e:
        # ディレクトリ読み込み自体のエラー (アクセス権など)
        print(f"エラー: ディレクトリ読み込み中にエラーが発生しました ({directory_path}): {e}")
        # エラー情報を生成して返す
        return [], [{'path1': 'N/A', 'path2': 'N/A', 'error': f"ディレクトリ読込エラー: {e}"}], []
    except Exception as e:
        # その他の予期せぬエラー
        print(f"エラー: ファイルリスト取得中に予期せぬエラーが発生しました ({directory_path}): {e}")
        return [], [{'path1': 'N/A', 'path2': 'N/A', 'error': f"ファイルリスト取得エラー: {e}"}], []


    if len(image_paths) < 2:
        # 比較対象が2枚未満の場合は正常終了 (空リストを返す)
        # print("比較対象の画像が2枚未満です。")
        return [], [], [] # エラーではない

    similar_pairs = []
    total_comparisons = len(image_paths) * (len(image_paths) - 1) // 2
    processed_count = 0

    print(f"{len(image_paths)} 個の画像を検出。約 {total_comparisons} 組のペア比較を開始します...")

    # 全てのユニークなペアについて処理 (itertools.combinations を使うとより Pythonic)
    # for path1, path2 in itertools.combinations(image_paths, 2):
    #     processed_count += 1
    #     # ... (以下の処理)

    # itertools.combinations を使わない場合 (現在の実装)
    for i, path1 in enumerate(image_paths):
        for path2 in image_paths[i+1:]: # i+1 から始めることで重複比較 (path1 vs path2 と path2 vs path1) を避ける
            processed_count += 1
            # 進捗表示は呼び出し元 (ScanWorker) で行う想定

            # 類似度計算を実行し、結果とエラーメッセージを受け取る
            score, error_msg = calculate_orb_similarity_score(
                path1, path2,
                n_features=orb_nfeatures,
                ratio_threshold=orb_ratio_threshold
            )

            if error_msg is not None:
                # エラーが発生した場合、エラーリストに追加
                comparison_errors.append({
                    'path1': path1, # エラー特定のためにフルパスを保持
                    'path2': path2,
                    'error': error_msg
                })
            elif score is not None and score >= min_good_matches_threshold:
                # エラーがなく、スコアが閾値以上の場合、類似ペアリストに追加
                # print(f"  類似ペア発見: {os.path.basename(path1)} - {os.path.basename(path2)} (スコア: {score})")
                similar_pairs.append((path1, path2, score))
            # score is None で error_msg も None というケースは基本的にないはず
            # score が閾値未満の場合は何もしない (類似ペアではない)

    print(f"ペア比較完了。{len(similar_pairs)} 組の類似ペアが見つかりました。{len(comparison_errors)} 件のエラーが発生しました。")
    # 結果のリストとエラーリストを返す
    return similar_pairs, comparison_errors, file_list_errors

# このファイルはモジュールとして使われるため、
# if __name__ == '__main__': ブロックは含めません。
