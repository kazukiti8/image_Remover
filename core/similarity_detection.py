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
        int: 良いマッチングの数。エラー時は -1 を返す。
    """
    # ファイル存在チェックや読み込みエラーは呼び出し元(find_similar_pairs)で
    # ハンドリングする方が効率的な場合もある
    try:
        img1 = cv2.imread(image_path1, cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imread(image_path2, cv2.IMREAD_GRAYSCALE)

        if img1 is None or img2 is None:
            # print(f"エラー: 画像ファイルを読み込めません: {image_path1} or {image_path2}")
            return -1 # 読み込み失敗を示す

        # 1. ORB検出器の初期化
        orb = cv2.ORB_create(nfeatures=n_features)

        # 2. キーポイントと記述子の検出
        kp1, des1 = orb.detectAndCompute(img1, None)
        kp2, des2 = orb.detectAndCompute(img2, None)

        # 記述子がない場合、または少なすぎる場合はマッチング不可
        if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2:
            return 0 # マッチ数0

        # 3. BFMatcherの初期化 (ハミング距離)
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

        # 4. knnマッチング (k=2)
        matches = bf.knnMatch(des1, des2, k=2)

        # 5. Ratio Test
        good_matches = []
        # knnMatchがNoneを返したり、内部のペアが1つしかない場合を考慮
        if matches is not None:
            for match_pair in matches:
                if len(match_pair) == 2:
                    m, n = match_pair
                    if m.distance < ratio_threshold * n.distance:
                        good_matches.append(m)

        # 6. 良いマッチング数を返す
        return len(good_matches)

    except Exception as e:
        print(f"エラー: ORB類似度計算中に例外 ({os.path.basename(image_path1)}, {os.path.basename(image_path2)}): {e}")
        return -1 # エラー発生を示す

def find_similar_pairs(directory_path, orb_nfeatures=1000, orb_ratio_threshold=0.75, min_good_matches_threshold=30, file_extensions=('.jpg', '.jpeg', '.png', '.bmp', '.tiff')):
    """
    指定されたディレクトリ内の画像を比較し、類似しているペアを見つけます。

    Args:
        directory_path (str): 画像が格納されているディレクトリのパス。
        orb_nfeatures (int): ORB特徴量の最大数。
        orb_ratio_threshold (float): ORBのRatio Test閾値。
        min_good_matches_threshold (int): 類似ペアと判断するための最低限の良いマッチング数。
        file_extensions (tuple): スキャン対象とする画像の拡張子。

    Returns:
        list: 類似ペアのリスト。各要素は (image_path1, image_path2, score) のタプル。
              エラー発生時は空リストを返す。
    """
    if not os.path.isdir(directory_path):
        print(f"エラー: ディレクトリが見つかりません: {directory_path}")
        return []

    image_paths = []
    try:
        # ファイル一覧取得とフィルタリング
        for filename in os.listdir(directory_path):
            # 拡張子を小文字にして比較
            if filename.lower().endswith(file_extensions):
                full_path = os.path.join(directory_path, filename)
                # ファイルかどうかをチェック
                if os.path.isfile(full_path):
                    image_paths.append(full_path)
    except Exception as e:
        print(f"エラー: ディレクトリ読み込み中にエラーが発生しました ({directory_path}): {e}")
        return []

    if len(image_paths) < 2:
        # print("比較対象の画像が2枚未満です。")
        return []

    similar_pairs = []
    total_comparisons = len(image_paths) * (len(image_paths) - 1) // 2
    processed_count = 0

    print(f"{len(image_paths)} 個の画像を検出。約 {total_comparisons} 組のペア比較を開始します...")

    # 全てのユニークなペアについて処理 (itertools.combinations がメモリ効率良い場合も)
    for i, path1 in enumerate(image_paths):
        for path2 in image_paths[i+1:]: # i+1 から始めることで重複比較を避ける
            processed_count += 1
            # 進捗表示（GUI側でより洗練された方法を実装するべき）
            # if processed_count % 100 == 0 or processed_count == total_comparisons:
            #      print(f"  比較中: {processed_count}/{total_comparisons}...")

            score = calculate_orb_similarity_score(path1, path2, n_features=orb_nfeatures, ratio_threshold=orb_ratio_threshold)

            # スコアが閾値以上であればペアとして記録
            if score != -1 and score >= min_good_matches_threshold:
                # print(f"  類似ペア発見: {os.path.basename(path1)} - {os.path.basename(path2)} (スコア: {score})")
                similar_pairs.append((path1, path2, score))

    print(f"ペア比較完了。{len(similar_pairs)} 組の類似ペアが見つかりました。")
    return similar_pairs

# このファイルはモジュールとして使われるため、
# if __name__ == '__main__': ブロックは含めません。