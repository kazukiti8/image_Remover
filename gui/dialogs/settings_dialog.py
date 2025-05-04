# gui/dialogs/settings_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QDoubleSpinBox, QSpinBox,
    QDialogButtonBox, QCheckBox, QGroupBox, QWidget, QComboBox
)
from PySide6.QtCore import Qt, Slot
from typing import Dict, Any, Union, Optional

# 型エイリアス
SettingsDict = Dict[str, Union[float, bool, int, str]]

# ブレ検出アルゴリズムの定義 (変更なし)
BLUR_ALGORITHMS: Dict[str, str] = {
    "fft": "FFT (高速フーリエ変換)",
    "laplacian": "Laplacian Variance (ラプラシアン分散)"
}

# ★★★ 類似度検出モードの定義 ★★★
SIMILARITY_MODES: Dict[str, str] = {
    "phash_orb": "pHash + ORB (推奨)",
    "phash_only": "pHash のみ (高速)",
    "orb_only": "ORB のみ (低速だが高精度)"
}
# ★★★★★★★★★★★★★★★★★★★★★★

class SettingsDialog(QDialog):
    """アプリケーションの設定を行うダイアログ"""
    def __init__(self, current_settings: SettingsDict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setModal(True)
        self.settings: SettingsDict = current_settings.copy()

        # ウィジェットの型ヒント
        self.scan_subdirectories_checkbox: QCheckBox
        self.blur_algorithm_label: QLabel
        self.blur_algorithm_combobox: QComboBox
        self.blur_threshold_label: QLabel
        self.blur_threshold_spinbox: QDoubleSpinBox
        self.blur_laplacian_threshold_label: QLabel
        self.blur_laplacian_threshold_spinbox: QSpinBox
        # ★ 類似度モード選択用ウィジェット ★
        self.similarity_mode_label: QLabel
        self.similarity_mode_combobox: QComboBox
        # ★ use_phash_checkbox は削除 ★
        # self.use_phash_checkbox: QCheckBox
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
        self._update_blur_threshold_visibility()
        self._update_similarity_options_visibility() # ★ 追加: 類似度オプション表示更新 ★

    def _setup_ui(self) -> None:
        """UI要素の作成と配置"""
        main_layout = QVBoxLayout(self)

        # --- 一般設定 (変更なし) ---
        general_group = QGroupBox("スキャン設定")
        general_layout = QFormLayout(general_group)
        self.scan_subdirectories_checkbox = QCheckBox("サブディレクトリもスキャンする")
        self.scan_subdirectories_checkbox.setToolTip("有効にすると、指定したフォルダ以下のサブフォルダも再帰的にスキャンします。")
        self.scan_subdirectories_checkbox.setChecked(bool(self.settings.get('scan_subdirectories', False)))
        general_layout.addRow(self.scan_subdirectories_checkbox)
        main_layout.addWidget(general_group)

        # --- ブレ検出設定 (変更なし) ---
        blur_group = QGroupBox("ブレ検出")
        blur_layout = QFormLayout(blur_group)
        self.blur_algorithm_label = QLabel("検出アルゴリズム:")
        self.blur_algorithm_combobox = QComboBox()
        current_blur_algo: str = str(self.settings.get('blur_algorithm', 'fft'))
        selected_index_blur: int = 0
        for i, (key, name) in enumerate(BLUR_ALGORITHMS.items()):
            self.blur_algorithm_combobox.addItem(name, key)
            if key == current_blur_algo:
                selected_index_blur = i
        self.blur_algorithm_combobox.setCurrentIndex(selected_index_blur)
        self.blur_algorithm_combobox.currentIndexChanged.connect(self._update_blur_threshold_visibility)
        blur_layout.addRow(self.blur_algorithm_label, self.blur_algorithm_combobox)
        self.blur_threshold_label = QLabel("FFT 閾値 (低いほどブレ):")
        self.blur_threshold_spinbox = QDoubleSpinBox(); self.blur_threshold_spinbox.setRange(0.0, 1.0); self.blur_threshold_spinbox.setSingleStep(0.01); self.blur_threshold_spinbox.setDecimals(4); self.blur_threshold_spinbox.setValue(float(self.settings.get('blur_threshold', 0.80)))
        blur_layout.addRow(self.blur_threshold_label, self.blur_threshold_spinbox)
        self.blur_laplacian_threshold_label = QLabel("Laplacian 閾値 (低いほどブレ):")
        self.blur_laplacian_threshold_spinbox = QSpinBox(); self.blur_laplacian_threshold_spinbox.setRange(0, 10000); self.blur_laplacian_threshold_spinbox.setSingleStep(10); self.blur_laplacian_threshold_spinbox.setValue(int(self.settings.get('blur_laplacian_threshold', 100)))
        blur_layout.addRow(self.blur_laplacian_threshold_label, self.blur_laplacian_threshold_spinbox)
        main_layout.addWidget(blur_group)

        # --- 類似ペア検出設定 ---
        similar_group = QGroupBox("類似ペア検出")
        similar_layout = QFormLayout(similar_group)

        # ★ モード選択コンボボックスを追加 ★
        self.similarity_mode_label = QLabel("検出モード:")
        self.similarity_mode_combobox = QComboBox()
        current_sim_mode: str = str(self.settings.get('similarity_mode', 'phash_orb')) # デフォルトは phash_orb
        selected_index_sim: int = 0
        for i, (key, name) in enumerate(SIMILARITY_MODES.items()):
            self.similarity_mode_combobox.addItem(name, key)
            if key == current_sim_mode:
                selected_index_sim = i
        self.similarity_mode_combobox.setCurrentIndex(selected_index_sim)
        self.similarity_mode_combobox.currentIndexChanged.connect(self._update_similarity_options_visibility) # ★ スロット接続 ★
        similar_layout.addRow(self.similarity_mode_label, self.similarity_mode_combobox)

        # ★ pHash 閾値 (use_phash_checkbox は削除) ★
        self.hash_threshold_label = QLabel("pHash ハミング距離閾値:")
        self.hash_threshold_spinbox = QSpinBox()
        self.hash_threshold_spinbox.setRange(0, 64)
        self.hash_threshold_spinbox.setSingleStep(1)
        self.hash_threshold_spinbox.setValue(int(self.settings.get('hash_threshold', 5)))
        # 以前の use_phash_checkbox.toggled 接続は不要になる
        similar_layout.addRow(self.hash_threshold_label, self.hash_threshold_spinbox)

        similar_layout.addRow(QLabel("-" * 30)) # 区切り線

        # ★ ORB パラメータ ★
        self.orb_features_label = QLabel("ORB 特徴点数:")
        self.orb_features_spinbox = QSpinBox()
        self.orb_features_spinbox.setRange(100, 10000)
        self.orb_features_spinbox.setSingleStep(100)
        self.orb_features_spinbox.setValue(int(self.settings.get('orb_nfeatures', 1500)))
        self.orb_ratio_label = QLabel("ORB Ratio Test 閾値:")
        self.orb_ratio_spinbox = QDoubleSpinBox()
        self.orb_ratio_spinbox.setRange(0.1, 0.95)
        self.orb_ratio_spinbox.setSingleStep(0.01)
        self.orb_ratio_spinbox.setDecimals(2)
        self.orb_ratio_spinbox.setValue(float(self.settings.get('orb_ratio_threshold', 0.70)))
        self.orb_min_matches_label = QLabel("ORB 最小マッチ数:")
        self.orb_min_matches_spinbox = QSpinBox()
        self.orb_min_matches_spinbox.setRange(5, 500)
        self.orb_min_matches_spinbox.setSingleStep(1)
        self.orb_min_matches_spinbox.setValue(int(self.settings.get('min_good_matches', 40)))
        similar_layout.addRow(self.orb_features_label, self.orb_features_spinbox)
        similar_layout.addRow(self.orb_ratio_label, self.orb_ratio_spinbox)
        similar_layout.addRow(self.orb_min_matches_label, self.orb_min_matches_spinbox)

        main_layout.addWidget(similar_group)

        # --- OK / Cancel ボタン ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    @Slot(int)
    def _update_blur_threshold_visibility(self) -> None:
        """ブレ検出閾値入力欄の表示/非表示を切り替える"""
        selected_algo_key: str = self.blur_algorithm_combobox.currentData()
        is_fft: bool = (selected_algo_key == 'fft')
        is_laplacian: bool = (selected_algo_key == 'laplacian')
        self.blur_threshold_label.setVisible(is_fft)
        self.blur_threshold_spinbox.setVisible(is_fft)
        self.blur_laplacian_threshold_label.setVisible(is_laplacian)
        self.blur_laplacian_threshold_spinbox.setVisible(is_laplacian)

    # ★★★ 類似度検出モードに応じてオプションの表示/非表示を切り替えるスロット ★★★
    @Slot(int)
    def _update_similarity_options_visibility(self) -> None:
        selected_mode_key: str = self.similarity_mode_combobox.currentData()
        use_phash: bool = selected_mode_key in ['phash_orb', 'phash_only']
        use_orb: bool = selected_mode_key in ['phash_orb', 'orb_only']

        # pHash 閾値
        self.hash_threshold_label.setVisible(use_phash)
        self.hash_threshold_spinbox.setVisible(use_phash)

        # ORB パラメータ
        self.orb_features_label.setVisible(use_orb)
        self.orb_features_spinbox.setVisible(use_orb)
        self.orb_ratio_label.setVisible(use_orb)
        self.orb_ratio_spinbox.setVisible(use_orb)
        self.orb_min_matches_label.setVisible(use_orb)
        self.orb_min_matches_spinbox.setVisible(use_orb)
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

    def accept(self) -> None:
        """OKボタンが押されたときの処理"""
        self.settings['scan_subdirectories'] = self.scan_subdirectories_checkbox.isChecked()
        self.settings['blur_algorithm'] = self.blur_algorithm_combobox.currentData()
        self.settings['blur_threshold'] = self.blur_threshold_spinbox.value()
        self.settings['blur_laplacian_threshold'] = self.blur_laplacian_threshold_spinbox.value()
        # ★ 類似度モードと関連パラメータを保存 ★
        self.settings['similarity_mode'] = self.similarity_mode_combobox.currentData()
        self.settings['hash_threshold'] = self.hash_threshold_spinbox.value()
        self.settings['orb_nfeatures'] = self.orb_features_spinbox.value()
        self.settings['orb_ratio_threshold'] = self.orb_ratio_spinbox.value()
        self.settings['min_good_matches'] = self.orb_min_matches_spinbox.value()
        # use_phash は不要になったので削除
        # if 'use_phash' in self.settings: del self.settings['use_phash']
        super().accept()

    def get_settings(self) -> SettingsDict:
        """ダイアログで設定された値を返す"""
        # 不要になったキーを削除しておく (古い設定ファイルからの移行)
        if 'use_phash' in self.settings:
            del self.settings['use_phash']
        return self.settings

