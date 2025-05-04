# gui/settings_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QSpinBox,
    QPushButton, QDialogButtonBox, QFormLayout
)
from PySide6.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        """
        設定ダイアログの初期化

        Args:
            current_settings (dict): 現在の設定値を含む辞書
            parent (QWidget, optional): 親ウィジェット. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setModal(True) # モーダルダイアログとして表示 (他のウィンドウを操作不可にする)

        # 現在の設定値を保持
        self.settings = current_settings.copy() # 変更用にコピー

        # --- ウィジェットの作成 ---
        # ブレ検出閾値 (FFTスコア v2 は 0.0~1.0 の範囲を想定)
        self.blur_threshold_label = QLabel("ブレ検出閾値 (低いほどブレと判定):")
        self.blur_threshold_spinbox = QDoubleSpinBox()
        self.blur_threshold_spinbox.setRange(0.0, 1.0) # スコア範囲
        self.blur_threshold_spinbox.setSingleStep(0.01) # 変更ステップ
        self.blur_threshold_spinbox.setDecimals(4) # 小数点以下4桁
        self.blur_threshold_spinbox.setValue(self.settings.get('blur_threshold', 0.80)) # 初期値

        # ORB 特徴点数
        self.orb_features_label = QLabel("ORB 特徴点数:")
        self.orb_features_spinbox = QSpinBox()
        self.orb_features_spinbox.setRange(100, 10000) # 範囲 (適宜調整)
        self.orb_features_spinbox.setSingleStep(100)
        self.orb_features_spinbox.setValue(self.settings.get('orb_nfeatures', 1500))

        # ORB Ratio Test 閾値
        self.orb_ratio_label = QLabel("ORB Ratio Test 閾値:")
        self.orb_ratio_spinbox = QDoubleSpinBox()
        self.orb_ratio_spinbox.setRange(0.1, 0.95) # 範囲 (0.7-0.8が一般的)
        self.orb_ratio_spinbox.setSingleStep(0.01)
        self.orb_ratio_spinbox.setDecimals(2)
        self.orb_ratio_spinbox.setValue(self.settings.get('orb_ratio_threshold', 0.70))

        # ORB 最小マッチ数
        self.orb_min_matches_label = QLabel("類似ペア判定 最小マッチ数:")
        self.orb_min_matches_spinbox = QSpinBox()
        self.orb_min_matches_spinbox.setRange(5, 500) # 範囲 (適宜調整)
        self.orb_min_matches_spinbox.setSingleStep(1)
        self.orb_min_matches_spinbox.setValue(self.settings.get('min_good_matches', 40))

        # OK / Cancel ボタン
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept) # OKボタンが押されたらaccept()を呼ぶ
        self.button_box.rejected.connect(self.reject) # Cancelボタンが押されたらreject()を呼ぶ

        # --- レイアウト ---
        layout = QVBoxLayout(self)
        form_layout = QFormLayout() # ラベルと入力欄をペアで配置しやすいレイアウト

        form_layout.addRow(self.blur_threshold_label, self.blur_threshold_spinbox)
        form_layout.addRow(self.orb_features_label, self.orb_features_spinbox)
        form_layout.addRow(self.orb_ratio_label, self.orb_ratio_spinbox)
        form_layout.addRow(self.orb_min_matches_label, self.orb_min_matches_spinbox)

        layout.addLayout(form_layout)
        layout.addWidget(self.button_box)

    def accept(self):
        """OKボタンが押されたときの処理"""
        # 現在の入力値を設定辞書に保存
        self.settings['blur_threshold'] = self.blur_threshold_spinbox.value()
        self.settings['orb_nfeatures'] = self.orb_features_spinbox.value()
        self.settings['orb_ratio_threshold'] = self.orb_ratio_spinbox.value()
        self.settings['min_good_matches'] = self.orb_min_matches_spinbox.value()
        # ダイアログを閉じる（親ウィジェットに制御が戻る）
        super().accept()

    def get_settings(self):
        """ダイアログで設定された値を返す"""
        return self.settings

# --- テスト用コード ---
if __name__ == '__main__':
    # このファイル単体で実行した場合のテストコード
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    # ダミーの現在設定
    initial_settings = {
        'blur_threshold': 0.75,
        'orb_nfeatures': 2000,
        'orb_ratio_threshold': 0.72,
        'min_good_matches': 50
    }

    dialog = SettingsDialog(initial_settings)
    # dialog.exec() でダイアログを表示し、ユーザー操作を待つ
    if dialog.exec(): # OKが押されたら True を返す
        new_settings = dialog.get_settings()
        print("設定が更新されました:", new_settings)
    else:
        print("設定はキャンセルされました。")

    # sys.exit(app.exec()) # このテストでは不要
# gui/main_window.py
import sys
import os
import time # ファイル日時取得用
import itertools # 追加 (find_similar_pairsから移動または重複)
import cv2      # 画像読み込み用に追加
import numpy as np # cv2 が依存、または画像操作で使用
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QFrame,
    QFileDialog, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox
)
# QtCoreからスレッド関連とシグナル/スロット関連をインポート
from PySide6.QtCore import Qt, QRunnable, QThreadPool, Signal, QObject, Slot
# QtGuiから画像関連をインポート
from PySide6.QtGui import QImage, QPixmap

# --- コアロジックの関数をインポート ---
try:
    from core.blur_detection import calculate_fft_blur_score_v2
    from core.similarity_detection import find_similar_pairs
except ImportError:
    print("エラー: core モジュールが見つかりません。ダミー関数を使用します。")
    # (ダミー関数の定義は省略)
    def calculate_fft_blur_score_v2(path, ratio=0.05): return 0.5 if "blur" in path else 0.9
    def find_similar_pairs(dir_path, **kwargs):
        def _dummy_pair(dir_p, f1, f2, score): p1,p2=os.path.join(dir_p,f1),os.path.join(dir_p,f2); return (p1,p2,score) if os.path.exists(p1) and os.path.exists(p2) else None
        pairs = []; p = _dummy_pair(dir_path, "A.jpg", "B.jpg", 95); p and pairs.append(p); p = _dummy_pair(dir_path, "A.jpg", "C.jpg", 92); p and pairs.append(p); return pairs

# --- 設定ダイアログクラスをインポート ---
try:
    from .settings_dialog import SettingsDialog # 同じguiパッケージ内からインポート
except ImportError:
    print("エラー: settings_dialog モジュールが見つかりません。")
    SettingsDialog = None # ダミーを設定

# (WorkerSignals クラス定義は変更なし)
# ...
class WorkerSignals(QObject):
    progress = Signal(str)
    results_ready = Signal(list, list)
    error = Signal(str)
    finished = Signal()

# === ScanWorker クラスを修正 ===
class ScanWorker(QRunnable):
    """
    バックグラウンドでスキャン処理を実行するWorkerクラス。
    設定値をコンストラクタで受け取るように変更。
    """
    def __init__(self, directory_path, settings): # settings 引数を追加
        super().__init__()
        self.directory_path = directory_path
        self.signals = WorkerSignals()
        # --- 設定値をインスタンス変数に保存 ---
        self.settings = settings
        self.file_extensions=('.jpg', '.jpeg', '.png', '.bmp', '.tiff') # これは固定でも良い

    @Slot()
    def run(self):
        try:
            self.signals.progress.emit("ファイルリスト取得中...")
            image_paths = []
            # (ファイルリスト取得処理 - 変更なし)
            try:
                for filename in os.listdir(self.directory_path):
                    if filename.lower().endswith(self.file_extensions):
                        full_path = os.path.join(self.directory_path, filename)
                        if os.path.isfile(full_path) and not os.path.islink(full_path):
                            image_paths.append(full_path)
            except OSError as e:
                 self.signals.error.emit(f"ディレクトリ読み込みエラー: {e}")
                 self.signals.finished.emit()
                 return

            if not image_paths:
                self.signals.progress.emit("対象ディレクトリに画像ファイルが見つかりませんでした。")
                self.signals.results_ready.emit([], [])
                self.signals.finished.emit()
                return

            num_images = len(image_paths)
            blurry_results = []
            similar_pair_results = []

            # --- ブレ検出 (設定値を使用) ---
            blur_threshold = self.settings.get('blur_threshold', 0.80) # 設定から取得
            self.signals.progress.emit(f"ブレ検出中... (閾値: {blur_threshold:.4f}) (0/{num_images})")
            for i, img_path in enumerate(image_paths):
                score = calculate_fft_blur_score_v2(img_path)
                if score == -1: continue
                if score <= blur_threshold: # 設定値で比較
                    blurry_results.append({"path": img_path, "score": score})
                if (i + 1) % 5 == 0 or (i + 1) == num_images:
                    self.signals.progress.emit(f"ブレ検出中... ({i+1}/{num_images})")

            # --- 類似ペア検出 (設定値を使用) ---
            orb_nfeatures = self.settings.get('orb_nfeatures', 1500)
            orb_ratio_threshold = self.settings.get('orb_ratio_threshold', 0.70)
            min_good_matches = self.settings.get('min_good_matches', 40)
            self.signals.progress.emit(f"類似ペア検出中... (f={orb_nfeatures}, r={orb_ratio_threshold:.2f}, m={min_good_matches})")
            try:
                similar_pair_results = find_similar_pairs(
                    self.directory_path,
                    orb_nfeatures=orb_nfeatures, # 設定値を使用
                    orb_ratio_threshold=orb_ratio_threshold, # 設定値を使用
                    min_good_matches_threshold=min_good_matches, # 設定値を使用
                    file_extensions=self.file_extensions
                )
            except Exception as e:
                 self.signals.error.emit(f"類似ペア検出中にエラー: {e}")
                 similar_pair_results = []

            self.signals.results_ready.emit(blurry_results, similar_pair_results)

        except Exception as e:
            self.signals.error.emit(f"スキャン中に予期せぬエラーが発生しました: {e}")
        finally:
            self.signals.finished.emit()


# === メインウィンドウクラス ===
class ImageCleanerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("画像クリーナー")
        self.setGeometry(100, 100, 900, 700)

        # --- スレッドプールを初期化 ---
        self.threadpool = QThreadPool()

        # --- ★ 設定値を保持する辞書を追加 ★ ---
        self.current_settings = {
            'blur_threshold': 0.80,
            'orb_nfeatures': 1500,
            'orb_ratio_threshold': 0.70,
            'min_good_matches': 40
        }
        # TODO: 設定ファイルからの読み込み/保存機能を追加すると良い

        # --- メインウィジェットとレイアウト ---
        # (変更なし)
        # ... (ウィジェット作成・レイアウト) ...

        # --- ボタンに対応する関数 (スロット) ---
    def select_directory(self):
        # (変更なし)
        dir_path = QFileDialog.getExistingDirectory(self, "フォルダを選択", os.path.expanduser("~"))
        if dir_path:
            self.dir_path_edit.setText(dir_path)
            self.clear_results()

    # === open_settings メソッドを実装 ===
    def open_settings(self):
        """設定ダイアログを開く"""
        if SettingsDialog is None:
            QMessageBox.warning(self, "エラー", "設定ダイアログモジュールが見つかりません。")
            return

        # 現在の設定値を渡してダイアログを作成
        dialog = SettingsDialog(self.current_settings, self)
        # ダイアログを表示し、結果を受け取る
        if dialog.exec(): # OKが押された場合
            self.current_settings = dialog.get_settings() # 更新された設定値を取得・保存
            print("設定が更新されました:", self.current_settings)
        else:
            print("設定はキャンセルされました。")

    # === start_scan メソッドを修正 ===
    def start_scan(self):
        # スキャンを開始する処理
        print("スキャン開始ボタンがクリックされました")
        selected_dir = self.dir_path_edit.text()
        if not selected_dir or not os.path.isdir(selected_dir):
             QMessageBox.warning(self, "エラー", "有効なフォルダが選択されていません。")
             self.status_label.setText("ステータス: エラー (フォルダ未選択)")
             return

        self.clear_results()
        self.status_label.setText(f"ステータス: スキャン準備中... ({os.path.basename(selected_dir)})")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.scan_button.setEnabled(False)
        self.settings_button.setEnabled(False)

        # Workerを作成してスレッドプールで実行 (★ 設定値を渡すように変更 ★)
        worker = ScanWorker(selected_dir, self.current_settings) # ← ここで設定値を渡す
        worker.signals.progress.connect(self.update_status)
        worker.signals.results_ready.connect(self.populate_results)
        worker.signals.error.connect(self.scan_error)
        worker.signals.finished.connect(self.scan_finished)
        self.threadpool.start(worker)

    # --- スロット関数 (Workerからのシグナルを受け取る) ---
    # (update_status, populate_results, scan_error, scan_finished は変更なし)
    # ...

    # --- その他のメソッド ---
    # (update_preview, _display_image_in_preview, _clear_previews, clear_results, populate_dummy_data は変更なし)
    # ...

# --- アプリケーション起動部分はここには書かない (main.py に記述) ---