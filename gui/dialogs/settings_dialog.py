# gui/dialogs/settings_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QDoubleSpinBox, QSpinBox,
    QDialogButtonBox, QCheckBox, QGroupBox, QWidget # QWidget をインポート
)
from PySide6.QtCore import Qt, Slot # Slot をインポート
from typing import Dict, Any, Union, Optional # typing をインポート

# 型エイリアス
SettingsDict = Dict[str, Union[float, bool, int, str]]

class SettingsDialog(QDialog):
    """アプリケーションの設定を行うダイアログ"""
    def __init__(self, current_settings: SettingsDict, parent: Optional[QWidget] = None):
        """コンストラクタ"""
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setModal(True)

        self.settings: SettingsDict = current_settings.copy()

        # --- ウィジェットの型ヒント ---
        self.blur_threshold_label: QLabel
        self.blur_threshold_spinbox: QDoubleSpinBox
        self.use_phash_checkbox: QCheckBox
        self.hash_threshold_label: QLabel
        self.hash_threshold_spinbox: QSpinBox
        self.orb_features_label: QLabel
        self.orb_features_spinbox: QSpinBox
        self.orb_ratio_label: QLabel
        self.orb_ratio_spinbox: QDoubleSpinBox
        self.orb_min_matches_label: QLabel
        self.orb_min_matches_spinbox: QSpinBox
        self.button_box: QDialogButtonBox

        self._setup_ui()

    def _setup_ui(self) -> None:
        """UI要素の作成と配置"""
        main_layout = QVBoxLayout(self)

        # --- ブレ検出設定 ---
        blur_group = QGroupBox("ブレ検出"); blur_layout = QFormLayout(blur_group)
        self.blur_threshold_label = QLabel("ブレ検出閾値 (低いほどブレと判定):"); self.blur_threshold_spinbox = QDoubleSpinBox(); self.blur_threshold_spinbox.setRange(0.0, 1.0); self.blur_threshold_spinbox.setSingleStep(0.01); self.blur_threshold_spinbox.setDecimals(4); self.blur_threshold_spinbox.setValue(float(self.settings.get('blur_threshold', 0.80))) # floatにキャスト
        blur_layout.addRow(self.blur_threshold_label, self.blur_threshold_spinbox); main_layout.addWidget(blur_group)

        # --- 類似ペア検出設定 ---
        similar_group = QGroupBox("類似ペア検出"); similar_layout = QFormLayout(similar_group)
        self.use_phash_checkbox = QCheckBox("pHashによる候補絞り込みを行う"); self.use_phash_checkbox.setToolTip("有効にすると、最初にpHashで候補を絞り込み、処理速度が向上する場合があります。\nImageHashライブラリが必要です。"); self.use_phash_checkbox.setChecked(bool(self.settings.get('use_phash', True))) # boolにキャスト
        self.hash_threshold_label = QLabel("pHash ハミング距離閾値:"); self.hash_threshold_spinbox = QSpinBox(); self.hash_threshold_spinbox.setRange(0, 64); self.hash_threshold_spinbox.setSingleStep(1); self.hash_threshold_spinbox.setValue(int(self.settings.get('hash_threshold', 5))) # intにキャスト
        self.hash_threshold_label.setEnabled(self.use_phash_checkbox.isChecked()); self.hash_threshold_spinbox.setEnabled(self.use_phash_checkbox.isChecked())
        self.use_phash_checkbox.toggled.connect(self.hash_threshold_label.setEnabled); self.use_phash_checkbox.toggled.connect(self.hash_threshold_spinbox.setEnabled)
        similar_layout.addRow(self.use_phash_checkbox); similar_layout.addRow(self.hash_threshold_label, self.hash_threshold_spinbox); similar_layout.addRow(QLabel("-" * 30))
        self.orb_features_label = QLabel("ORB 特徴点数:"); self.orb_features_spinbox = QSpinBox(); self.orb_features_spinbox.setRange(100, 10000); self.orb_features_spinbox.setSingleStep(100); self.orb_features_spinbox.setValue(int(self.settings.get('orb_nfeatures', 1500))) # intにキャスト
        self.orb_ratio_label = QLabel("ORB Ratio Test 閾値:"); self.orb_ratio_spinbox = QDoubleSpinBox(); self.orb_ratio_spinbox.setRange(0.1, 0.95); self.orb_ratio_spinbox.setSingleStep(0.01); self.orb_ratio_spinbox.setDecimals(2); self.orb_ratio_spinbox.setValue(float(self.settings.get('orb_ratio_threshold', 0.70))) # floatにキャスト
        self.orb_min_matches_label = QLabel("類似ペア判定 最小マッチ数:"); self.orb_min_matches_spinbox = QSpinBox(); self.orb_min_matches_spinbox.setRange(5, 500); self.orb_min_matches_spinbox.setSingleStep(1); self.orb_min_matches_spinbox.setValue(int(self.settings.get('min_good_matches', 40))) # intにキャスト
        similar_layout.addRow(self.orb_features_label, self.orb_features_spinbox); similar_layout.addRow(self.orb_ratio_label, self.orb_ratio_spinbox); similar_layout.addRow(self.orb_min_matches_label, self.orb_min_matches_spinbox); main_layout.addWidget(similar_group)

        # --- OK / Cancel ボタン ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def accept(self) -> None: # 戻り値なし
        """OKボタンが押されたときの処理 (オーバーライド)"""
        self.settings['blur_threshold'] = self.blur_threshold_spinbox.value()
        self.settings['use_phash'] = self.use_phash_checkbox.isChecked()
        self.settings['hash_threshold'] = self.hash_threshold_spinbox.value()
        self.settings['orb_nfeatures'] = self.orb_features_spinbox.value()
        self.settings['orb_ratio_threshold'] = self.orb_ratio_spinbox.value()
        self.settings['min_good_matches'] = self.orb_min_matches_spinbox.value()
        super().accept()

    def get_settings(self) -> SettingsDict:
        """ダイアログで設定された値を返すメソッド"""
        return self.settings

