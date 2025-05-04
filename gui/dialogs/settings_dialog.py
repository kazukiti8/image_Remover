# gui/dialogs/settings_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QDoubleSpinBox, QSpinBox,
    QDialogButtonBox
)
from PySide6.QtCore import Qt

class SettingsDialog(QDialog):
    """アプリケーションの設定を行うダイアログ"""
    def __init__(self, current_settings, parent=None):
        """
        コンストラクタ

        Args:
            current_settings (dict): 現在の設定値を含む辞書
            parent (QWidget, optional): 親ウィジェット. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setModal(True) # モーダルダイアログとして表示

        # 現在の設定値を保持 (変更用にコピー)
        self.settings = current_settings.copy()

        # --- ウィジェットの作成 ---
        # ブレ検出閾値
        self.blur_threshold_label = QLabel("ブレ検出閾値 (低いほどブレと判定):")
        self.blur_threshold_spinbox = QDoubleSpinBox()
        self.blur_threshold_spinbox.setRange(0.0, 1.0)    # スコア範囲 0.0 - 1.0
        self.blur_threshold_spinbox.setSingleStep(0.01)   # 変更ステップ
        self.blur_threshold_spinbox.setDecimals(4)        # 小数点以下4桁表示
        self.blur_threshold_spinbox.setValue(self.settings.get('blur_threshold', 0.80)) # 初期値

        # ORB 特徴点数
        self.orb_features_label = QLabel("ORB 特徴点数:")
        self.orb_features_spinbox = QSpinBox()
        self.orb_features_spinbox.setRange(100, 10000)    # 適切な範囲に設定
        self.orb_features_spinbox.setSingleStep(100)      # 変更ステップ
        self.orb_features_spinbox.setValue(self.settings.get('orb_nfeatures', 1500)) # 初期値

        # ORB Ratio Test 閾値
        self.orb_ratio_label = QLabel("ORB Ratio Test 閾値:")
        self.orb_ratio_spinbox = QDoubleSpinBox()
        self.orb_ratio_spinbox.setRange(0.1, 0.95)        # 適切な範囲 (0.7-0.8が一般的)
        self.orb_ratio_spinbox.setSingleStep(0.01)
        self.orb_ratio_spinbox.setDecimals(2)             # 小数点以下2桁表示
        self.orb_ratio_spinbox.setValue(self.settings.get('orb_ratio_threshold', 0.70)) # 初期値

        # ORB 最小マッチ数 (類似ペア判定)
        self.orb_min_matches_label = QLabel("類似ペア判定 最小マッチ数:")
        self.orb_min_matches_spinbox = QSpinBox()
        self.orb_min_matches_spinbox.setRange(5, 500)      # 適切な範囲に設定
        self.orb_min_matches_spinbox.setSingleStep(1)       # 変更ステップ
        self.orb_min_matches_spinbox.setValue(self.settings.get('min_good_matches', 40)) # 初期値

        # OK / Cancel ボタン
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                          QDialogButtonBox.StandardButton.Cancel)
        # ボタンのシグナルをダイアログの accept/reject スロットに接続
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        # --- レイアウト ---
        layout = QVBoxLayout(self)
        form_layout = QFormLayout() # ラベルと入力欄をペアで配置

        form_layout.addRow(self.blur_threshold_label, self.blur_threshold_spinbox)
        form_layout.addRow(self.orb_features_label, self.orb_features_spinbox)
        form_layout.addRow(self.orb_ratio_label, self.orb_ratio_spinbox)
        form_layout.addRow(self.orb_min_matches_label, self.orb_min_matches_spinbox)

        layout.addLayout(form_layout)
        layout.addWidget(self.button_box) # OK/Cancelボタンを追加

    def accept(self):
        """OKボタンが押されたときの処理 (オーバーライド)"""
        # 現在の入力値を設定辞書に反映
        self.settings['blur_threshold'] = self.blur_threshold_spinbox.value()
        self.settings['orb_nfeatures'] = self.orb_features_spinbox.value()
        self.settings['orb_ratio_threshold'] = self.orb_ratio_spinbox.value()
        self.settings['min_good_matches'] = self.orb_min_matches_spinbox.value()
        # 親クラスの accept() を呼び出してダイアログを閉じる (Accepted シグナルが発行される)
        super().accept()

    # reject() はオーバーライド不要 (デフォルトでダイアログが閉じる)

    def get_settings(self):
        """ダイアログで設定された値を返すメソッド"""
        # accept() で self.settings が更新されているので、それを返す
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
    # 戻り値は QDialog.Accepted (1) または QDialog.Rejected (0)
    if dialog.exec(): # OKが押されたら Accepted (True相当) を返す
        new_settings = dialog.get_settings()
        print("設定が更新されました:", new_settings)
    else:
        print("設定はキャンセルされました。")

    # sys.exit(app.exec()) # このテストではイベントループは不要
