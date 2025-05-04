# gui/workers.py
import os
from PySide6.QtCore import QRunnable, Signal, QObject, Slot

# --- コアロジックの関数をインポート ---
# このファイルは core パッケージの外にあるので、絶対パスまたは相対パスで指定
# プロジェクトルートからの相対パスを使う場合が多い
try:
    from core.blur_detection import calculate_fft_blur_score_v2
    from core.similarity_detection import find_similar_pairs
except ImportError as e:
    print(f"エラー: core モジュールのインポートに失敗しました。({e}) ダミー関数を使用します。")
    # ダミー関数 (エラーハンドリング強化版と同じ形式)
    def calculate_fft_blur_score_v2(path, ratio=0.05):
        if "error" in path.lower(): return None, "ダミーエラー(ブレ)"
        return (0.5, None) if "blur" in path.lower() else (0.9, None)
    def find_similar_pairs(dir_path, **kwargs):
        def _dummy_pair(dir_p, f1, f2, score): p1,p2=os.path.join(dir_p,f1),os.path.join(dir_p,f2); return (p1,p2,score) if os.path.exists(p1) and os.path.exists(p2) else None
        pairs = []; comp_errors = []; file_errors = []
        p = _dummy_pair(dir_path, "A.jpg", "B.jpg", 95); p and pairs.append(p)
        p = _dummy_pair(dir_path, "A.jpg", "C.jpg", 92); p and pairs.append(p)
        err_p1 = os.path.join(dir_path, "Error1.jpg")
        err_p2 = os.path.join(dir_path, "Error2.jpg")
        if os.path.exists(err_p1) and os.path.exists(err_p2):
            comp_errors.append({'path1': err_p1, 'path2': err_p2, 'error': 'ダミー比較エラー'})
        return pairs, comp_errors, file_errors


# === バックグラウンド処理用のシグナル定義 ===
class WorkerSignals(QObject):
    """バックグラウンド処理からのシグナルを定義するクラス"""
    status_update = Signal(str)       # ステータス変更通知 (メッセージ)
    progress_update = Signal(int)     # 進捗更新通知 (0-100)
    results_ready = Signal(list, list, list) # 結果通知 (blurry, similar, errors)
    error = Signal(str)               # 致命的エラー通知 (メッセージ)
    finished = Signal()               # 処理完了通知

# === バックグラウンド処理実行クラス ===
class ScanWorker(QRunnable):
    """
    画像のスキャン処理（ブレ検出、類似ペア検出）をバックグラウンドで実行するクラス。
    QThreadPool で使用される。
    """
    def __init__(self, directory_path, settings):
        """
        コンストラクタ

        Args:
            directory_path (str): スキャン対象のディレクトリパス
            settings (dict): スキャンに使用する設定値 (閾値など)
        """
        super().__init__()
        self.directory_path = directory_path
        self.settings = settings
        self.signals = WorkerSignals() # シグナル送出用のインスタンス
        # スキャン対象の拡張子 (小文字)
        self.file_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.heic', '.heif')

    @Slot() # QRunnable の run メソッドは @Slot デコレータが必要
    def run(self):
        """メインの処理を実行するメソッド (スレッドプールから呼び出される)"""
        scan_errors = [] # 個別のファイル処理エラーを格納するリスト
        try:
            self.signals.status_update.emit("ファイルリスト取得中...")
            image_paths = []
            try:
                # ディレクトリ内のファイルをリストアップ
                for filename in os.listdir(self.directory_path):
                    # 指定された拡張子に一致するか (小文字で比較)
                    if filename.lower().endswith(self.file_extensions):
                        full_path = os.path.join(self.directory_path, filename)
                        # ファイルであり、シンボリックリンクでないことを確認
                        if os.path.isfile(full_path) and not os.path.islink(full_path):
                            image_paths.append(full_path)
            except OSError as e:
                 # ディレクトリ読み込み自体のエラーは致命的エラーとして通知
                 self.signals.error.emit(f"ディレクトリ読み込みエラー: {e}")
                 self.signals.finished.emit() # 処理終了を通知
                 return # runメソッドを終了
            except Exception as e:
                 # その他のファイルリスト取得エラーも致命的
                 self.signals.error.emit(f"ファイルリスト取得エラー: {e}")
                 self.signals.finished.emit()
                 return

            # 画像ファイルが見つからない場合
            if not image_paths:
                self.signals.status_update.emit("対象ディレクトリに画像ファイルが見つかりませんでした。")
                # 結果がない場合も正常終了として空リストとエラーリストを渡す
                self.signals.results_ready.emit([], [], scan_errors) # scan_errors は空のはず
                self.signals.finished.emit()
                return

            num_images = len(image_paths)
            blurry_results = []         # ブレ検出結果リスト
            similar_pair_results = []   # 類似ペア検出結果リスト

            # --- 1. ブレ検出 ---
            blur_threshold = self.settings.get('blur_threshold', 0.80) # 設定から閾値取得
            self.signals.status_update.emit(f"ブレ検出中... (閾値: {blur_threshold:.4f}) (0/{num_images})")
            for i, img_path in enumerate(image_paths):
                # ブレ検出関数を呼び出し、結果とエラーメッセージを受け取る
                score, error_msg = calculate_fft_blur_score_v2(img_path)

                if error_msg is not None:
                    # エラー情報を scan_errors に追加
                    scan_errors.append({
                        'type': 'ブレ検出',
                        'path': img_path, # エラー特定用にフルパスを保持
                        'error': error_msg
                    })
                elif score is not None and score <= blur_threshold:
                    # エラーがなく、スコアが閾値以下の場合、結果リストに追加
                    blurry_results.append({"path": img_path, "score": score})

                # 進捗更新 (ブレ検出で全体の50%まで進む)
                progress_value = int(((i + 1) / num_images) * 50)
                self.signals.progress_update.emit(progress_value)
                # ステータス更新 (一定間隔または最後)
                if (i + 1) % 10 == 0 or (i + 1) == num_images:
                    self.signals.status_update.emit(f"ブレ検出中... ({i+1}/{num_images})")

            # --- 2. 類似ペア検出 ---
            orb_nfeatures = self.settings.get('orb_nfeatures', 1500)
            orb_ratio_threshold = self.settings.get('orb_ratio_threshold', 0.70)
            min_good_matches = self.settings.get('min_good_matches', 40)
            self.signals.progress_update.emit(50) # ブレ検出完了時点で50%
            self.signals.status_update.emit(f"類似ペア検出中... (f={orb_nfeatures}, r={orb_ratio_threshold:.2f}, m={min_good_matches})")

            # 類似ペア検出関数を呼び出し、結果リストとエラーリストを受け取る
            try:
                # find_similar_pairs はディレクトリパスを引数に取る仕様
                similar_pair_results, comparison_errors, _ = find_similar_pairs(
                    self.directory_path, # image_paths ではなくディレクトリパスを渡す
                    orb_nfeatures=orb_nfeatures,
                    orb_ratio_threshold=orb_ratio_threshold,
                    min_good_matches_threshold=min_good_matches,
                    file_extensions=self.file_extensions
                )
                # find_similar_pairs から返された比較エラーを scan_errors に追加
                for err in comparison_errors:
                    # エラー情報の形式を統一
                    scan_errors.append({
                        'type': '類似度比較',
                        'path': f"{os.path.basename(err.get('path1','?'))} vs {os.path.basename(err.get('path2','?'))}", # 表示用
                        'path1': err.get('path1'), # 元のパスも保持
                        'path2': err.get('path2'),
                        'error': err.get('error', '不明な比較エラー')
                    })

                # 類似ペア検出の進捗は find_similar_pairs 内で詳細を追うのが難しいため、
                # ここでは完了後に100%にする
                self.signals.progress_update.emit(100)
                self.signals.status_update.emit(f"類似ペア検出完了 ({len(similar_pair_results)}ペア発見)")

            except Exception as e:
                 # find_similar_pairs 自体の予期せぬエラー (通常は起こらないはず)
                 # これは致命的エラーとして通知
                 self.signals.error.emit(f"類似ペア検出処理中に致命的なエラー: {e}")
                 self.signals.finished.emit() # 処理終了
                 return # runメソッド終了

            # --- 3. 結果通知 ---
            # 最終的な結果 (ブレリスト、類似ペアリスト、エラーリスト) をシグナルで通知
            self.signals.results_ready.emit(blurry_results, similar_pair_results, scan_errors)

        except Exception as e:
            # この run メソッド全体の予期せぬエラー
            self.signals.error.emit(f"スキャン中に予期せぬエラーが発生しました: {e}")
        finally:
            # 正常終了でも、エラー発生でも、必ず finished シグナルを通知
            self.signals.finished.emit()
