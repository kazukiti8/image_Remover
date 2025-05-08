# gui/dialogs/settings_dialog.py
import math
import copy
import functools # ★ functools をインポート ★
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QDoubleSpinBox, QSpinBox,
    QDialogButtonBox, QCheckBox, QGroupBox, QWidget, QComboBox,
    QHBoxLayout, QPushButton, QLineEdit, QMessageBox, QInputDialog,
    QToolButton, QStyle # ★ QToolButton, QStyle をインポート ★
)
from PySide6.QtGui import QIcon # ★ QIcon をインポート ★
from PySide6.QtCore import Qt, Slot
from typing import Dict, Any, Union, Optional

# 型エイリアス
SettingsDict = Dict[str, Any] # presets を含むため Any

# ブレ検出アルゴリズムの定義
BLUR_ALGORITHMS: Dict[str, str] = {
    "fft": "FFT (高速フーリエ変換)",
    "laplacian": "Laplacian Variance (ラプラシアン分散)"
}

# 類似度検出モードの定義
SIMILARITY_MODES: Dict[str, str] = {
    "phash_orb": "pHash + ORB (推奨)",
    "phash_only": "pHash のみ (高速)",
    "orb_only": "ORB のみ (低速だが高精度)"
}

# ★★★ ヘルプテキスト定義 ★★★
HELP_TEXTS = {
    "scan_subdirectories": "オンにすると、選択したフォルダ内のサブフォルダも再帰的にスキャン対象とします。",
    "blur_algorithm": "画像のブレ（ボケ）を検出する方法を選択します。\n\n"
                      "- FFT: 画像全体の周波数成分を分析します。比較的大きなボケや全体的なシャープネスの欠如に有効です。\n"
                      "- Laplacian: 画像のエッジ（輪郭）の鋭さを評価します。ピンボケのような細かいボケの検出に向いています。",
    "blur_threshold_fft": "FFTアルゴリズム使用時の閾値です (0-100)。\n"
                          "値が低いほど「ブレている」と判定されやすくなります。\n"
                          "画像内の高周波成分の割合に基づいて計算され、値が低いほど高周波成分が少ない（=ブレている可能性が高い）ことを示します。\n"
                          "デフォルトは80です。",
    "blur_threshold_laplacian": "Laplacianアルゴリズム使用時の閾値です。\n"
                                "値が低いほど「ブレている」と判定されやすくなります。\n"
                                "画像のエッジの分散（ばらつき）を表し、値が低いほどエッジが不明瞭（=ブレている可能性が高い）ことを示します。\n"
                                "デフォルトは100です。",
    "similarity_mode": "類似画像を検出する方法を選択します。\n\n"
                       "- pHash + ORB (推奨): まずpHashで高速に候補を絞り込み、その後ORBで詳細に比較します。速度と精度のバランスが良いです。\n"
                       "- pHash のみ: pHash（知覚ハッシュ）のみで比較します。非常に高速ですが、画像の回転や若干の変形には弱い場合があります。\n"
                       "- ORB のみ: ORB特徴量のみで比較します。回転や拡大縮小、明るさの変化に比較的強いですが、処理速度は遅くなります。",
    "hash_threshold": "pHashモード（pHash+ORB または pHashのみ）で使用するハミング距離の閾値です (0-100)。\n"
                      "2つの画像のpHash間のビット差の数を表します。\n"
                      "値が小さいほど、より厳密に類似している画像のみを検出します。\n"
                      "デフォルトは5です。",
    "orb_features": "ORBモード（pHash+ORB または ORBのみ）で使用する特徴点の最大数です。\n"
                    "値を大きくすると、より多くの特徴点を検出しようとしますが、処理時間が増加します。\n"
                    "デフォルトは1500です。",
    "orb_ratio": "ORBモード（pHash+ORB または ORBのみ）で使用するRatio Testの閾値です (0-100)。\n"
                 "特徴点マッチングの精度を上げるためのパラメータです。\n"
                 "値が小さいほど、より信頼性の高いマッチングのみを採用しますが、検出されるペアが減る可能性があります。\n"
                 "デフォルトは70です。",
    "orb_min_matches": "ORBモード（pHash+ORB または ORBのみ）で「類似している」と判定するために必要な、最低限のマッチした特徴点の数です。\n"
                       "値が大きいほど、より多くの特徴点が一致した場合のみ類似と判定します。\n"
                       "デフォルトは40です。"
}
# ★★★★★★★★★★★★★★★★★★★

class SettingsDialog(QDialog):
    """アプリケーションの設定を行うダイアログ"""
    def __init__(self, current_settings: SettingsDict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setModal(True)
        self.original_settings = copy.deepcopy(current_settings)
        self.current_settings = copy.deepcopy(current_settings)
        self.presets: Dict[str, SettingsDict] = self.current_settings.get('presets', {})

        # ウィジェットの型ヒント (変更なし)
        self.scan_subdirectories_checkbox: QCheckBox
        self.blur_algorithm_label: QLabel; self.blur_algorithm_combobox: QComboBox
        self.blur_threshold_label: QLabel; self.blur_threshold_spinbox: QSpinBox
        self.blur_laplacian_threshold_label: QLabel; self.blur_laplacian_threshold_spinbox: QSpinBox
        self.similarity_mode_label: QLabel; self.similarity_mode_combobox: QComboBox
        self.hash_threshold_label: QLabel; self.hash_threshold_spinbox: QSpinBox
        self.orb_features_label: QLabel; self.orb_features_spinbox: QSpinBox
        self.orb_ratio_label: QLabel; self.orb_ratio_spinbox: QSpinBox
        self.orb_min_matches_label: QLabel; self.orb_min_matches_spinbox: QSpinBox
        self.preset_label: QLabel
        self.preset_combobox: QComboBox
        self.save_preset_button: QPushButton
        self.delete_preset_button: QPushButton
        self.button_box: QDialogButtonBox

        self._setup_ui()
        self._update_blur_threshold_visibility()
        self._update_similarity_options_visibility()
        self._populate_preset_combobox()

    # ★★★ ヘルプボタン付きウィジェット作成関数 ★★★
    def _create_widget_with_help(self, widget: QWidget, help_text: str) -> QWidget:
        """設定ウィジェットとヘルプボタンを横に並べたレイアウトを作成する"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0) # マージンをなくす
        layout.setSpacing(5) # ウィジェットとボタンの間隔

        layout.addWidget(widget, 1) # ウィジェットが伸びるようにする

        help_button = QToolButton(self)
        # 標準のヘルプアイコンを設定
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion)
        if icon.isNull(): # 標準アイコンが取得できない場合のフォールバック
             help_button.setText("?")
        else:
            help_button.setIcon(icon)
        help_button.setToolTip("この設定項目の説明を表示します")
        # functools.partial を使って、クリック時に表示するテキストを渡す
        help_button.clicked.connect(functools.partial(self._show_help_message, help_text))

        layout.addWidget(help_button)

        # レイアウトを含むQWidgetを返す（QFormLayoutにはQWidgetまたはQLayoutを追加できる）
        container = QWidget()
        container.setLayout(layout)
        return container
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

    # ★★★ ヘルプメッセージ表示スロット ★★★
    @Slot(str)
    def _show_help_message(self, message: str):
        """ヘルプボタンがクリックされたときにメッセージボックスを表示する"""
        QMessageBox.information(self, "ヘルプ", message)
    # ★★★★★★★★★★★★★★★★★★★★★★★

    def _setup_ui(self) -> None:
        """UI要素の作成と配置"""
        main_layout = QVBoxLayout(self)

        # --- プリセット管理エリア ---
        preset_group = QGroupBox("プリセット")
        preset_layout = QHBoxLayout(preset_group)
        self.preset_label = QLabel("読み込み:")
        self.preset_combobox = QComboBox()
        self.preset_combobox.setToolTip("保存済みの設定プリセットを選択して読み込みます。")
        self.preset_combobox.addItem("--- 選択してください ---", "")
        self.preset_combobox.currentIndexChanged.connect(self._load_selected_preset)

        self.save_preset_button = QPushButton("現在の設定を保存...")
        self.save_preset_button.setToolTip("現在のダイアログの設定を新しいプリセットとして保存します。")
        self.save_preset_button.clicked.connect(self._save_current_as_preset)

        self.delete_preset_button = QPushButton("選択したプリセットを削除")
        self.delete_preset_button.setToolTip("コンボボックスで選択されているプリセットを削除します。")
        self.delete_preset_button.clicked.connect(self._delete_selected_preset)
        self.delete_preset_button.setEnabled(False)

        preset_layout.addWidget(self.preset_label)
        preset_layout.addWidget(self.preset_combobox, 1)
        preset_layout.addWidget(self.save_preset_button)
        preset_layout.addWidget(self.delete_preset_button)
        main_layout.addWidget(preset_group)
        main_layout.addSpacing(10)

        # --- 一般設定 ---
        general_group = QGroupBox("スキャン設定")
        general_layout = QFormLayout(general_group)
        self.scan_subdirectories_checkbox = QCheckBox("サブディレクトリもスキャンする")
        self.scan_subdirectories_checkbox.setChecked(bool(self.current_settings.get('scan_subdirectories', False)))
        # ★ ヘルプボタン付きで追加 ★
        general_layout.addRow(self._create_widget_with_help(self.scan_subdirectories_checkbox, HELP_TEXTS["scan_subdirectories"]))
        main_layout.addWidget(general_group)

        # --- ブレ検出設定 ---
        blur_group = QGroupBox("ブレ検出")
        blur_layout = QFormLayout(blur_group)
        self.blur_algorithm_label = QLabel("検出アルゴリズム:")
        self.blur_algorithm_combobox = QComboBox()
        current_blur_algo: str = str(self.current_settings.get('blur_algorithm', 'fft'))
        selected_index_blur: int = 0
        for i, (key, name) in enumerate(BLUR_ALGORITHMS.items()):
            self.blur_algorithm_combobox.addItem(name, key)
            if key == current_blur_algo: selected_index_blur = i
        self.blur_algorithm_combobox.setCurrentIndex(selected_index_blur)
        self.blur_algorithm_combobox.currentIndexChanged.connect(self._update_blur_threshold_visibility)
        # ★ ヘルプボタン付きで追加 ★
        blur_layout.addRow(self.blur_algorithm_label, self._create_widget_with_help(self.blur_algorithm_combobox, HELP_TEXTS["blur_algorithm"]))

        self.blur_threshold_label = QLabel("FFT 閾値 (0-100, 低いほどブレ):")
        self.blur_threshold_spinbox = QSpinBox()
        self.blur_threshold_spinbox.setRange(0, 100)
        self.blur_threshold_spinbox.setSingleStep(1)
        default_fft_float = float(self.current_settings.get('blur_threshold', 0.80))
        self.blur_threshold_spinbox.setValue(math.floor(default_fft_float * 100))
        self.blur_threshold_spinbox.setMinimumWidth(120)
        self.blur_threshold_spinbox.setMinimumHeight(25)
        # ★ ヘルプボタン付きで追加 ★
        blur_layout.addRow(self.blur_threshold_label, self._create_widget_with_help(self.blur_threshold_spinbox, HELP_TEXTS["blur_threshold_fft"]))

        self.blur_laplacian_threshold_label = QLabel("Laplacian 閾値 (低いほどブレ):")
        self.blur_laplacian_threshold_spinbox = QSpinBox()
        self.blur_laplacian_threshold_spinbox.setRange(0, 10000)
        self.blur_laplacian_threshold_spinbox.setSingleStep(10)
        self.blur_laplacian_threshold_spinbox.setValue(int(self.current_settings.get('blur_laplacian_threshold', 100)))
        self.blur_laplacian_threshold_spinbox.setMinimumWidth(120)
        self.blur_laplacian_threshold_spinbox.setMinimumHeight(25)
        # ★ ヘルプボタン付きで追加 ★
        blur_layout.addRow(self.blur_laplacian_threshold_label, self._create_widget_with_help(self.blur_laplacian_threshold_spinbox, HELP_TEXTS["blur_threshold_laplacian"]))
        main_layout.addWidget(blur_group)

        # --- 類似ペア検出設定 ---
        similar_group = QGroupBox("類似ペア検出")
        similar_layout = QFormLayout(similar_group)
        self.similarity_mode_label = QLabel("検出モード:")
        self.similarity_mode_combobox = QComboBox()
        current_sim_mode: str = str(self.current_settings.get('similarity_mode', 'phash_orb'))
        selected_index_sim: int = 0
        for i, (key, name) in enumerate(SIMILARITY_MODES.items()):
            self.similarity_mode_combobox.addItem(name, key)
            if key == current_sim_mode: selected_index_sim = i
        self.similarity_mode_combobox.setCurrentIndex(selected_index_sim)
        self.similarity_mode_combobox.currentIndexChanged.connect(self._update_similarity_options_visibility)
        # ★ ヘルプボタン付きで追加 ★
        similar_layout.addRow(self.similarity_mode_label, self._create_widget_with_help(self.similarity_mode_combobox, HELP_TEXTS["similarity_mode"]))

        self.hash_threshold_label = QLabel("pHash ハミング距離閾値 (0-100):")
        self.hash_threshold_spinbox = QSpinBox()
        self.hash_threshold_spinbox.setRange(0, 100)
        self.hash_threshold_spinbox.setSingleStep(1)
        default_phash = int(self.current_settings.get('hash_threshold', 5))
        self.hash_threshold_spinbox.setValue(min(max(default_phash, 0), 100))
        self.hash_threshold_spinbox.setMinimumWidth(120)
        self.hash_threshold_spinbox.setMinimumHeight(25)
        # ★ ヘルプボタン付きで追加 ★
        similar_layout.addRow(self.hash_threshold_label, self._create_widget_with_help(self.hash_threshold_spinbox, HELP_TEXTS["hash_threshold"]))

        similar_layout.addRow(QLabel("-" * 30)) # 区切り線
        self.orb_features_label = QLabel("ORB 特徴点数:")
        self.orb_features_spinbox = QSpinBox()
        self.orb_features_spinbox.setRange(100, 10000); self.orb_features_spinbox.setSingleStep(100); self.orb_features_spinbox.setValue(int(self.current_settings.get('orb_nfeatures', 1500)))
        self.orb_features_spinbox.setMinimumWidth(120)
        self.orb_features_spinbox.setMinimumHeight(25)
        # ★ ヘルプボタン付きで追加 ★
        similar_layout.addRow(self.orb_features_label, self._create_widget_with_help(self.orb_features_spinbox, HELP_TEXTS["orb_features"]))

        self.orb_ratio_label = QLabel("ORB Ratio Test 閾値 (0-100):")
        self.orb_ratio_spinbox = QSpinBox()
        self.orb_ratio_spinbox.setRange(0, 100)
        self.orb_ratio_spinbox.setSingleStep(1)
        default_orb_ratio_float = float(self.current_settings.get('orb_ratio_threshold', 0.70))
        self.orb_ratio_spinbox.setValue(math.floor(default_orb_ratio_float * 100))
        self.orb_ratio_spinbox.setMinimumWidth(120)
        self.orb_ratio_spinbox.setMinimumHeight(25)
        # ★ ヘルプボタン付きで追加 ★
        similar_layout.addRow(self.orb_ratio_label, self._create_widget_with_help(self.orb_ratio_spinbox, HELP_TEXTS["orb_ratio"]))

        self.orb_min_matches_label = QLabel("ORB 最小マッチ数:")
        self.orb_min_matches_spinbox = QSpinBox()
        self.orb_min_matches_spinbox.setRange(5, 500); self.orb_min_matches_spinbox.setSingleStep(1); self.orb_min_matches_spinbox.setValue(int(self.current_settings.get('min_good_matches', 40)))
        self.orb_min_matches_spinbox.setMinimumWidth(120)
        self.orb_min_matches_spinbox.setMinimumHeight(25)
        # ★ ヘルプボタン付きで追加 ★
        similar_layout.addRow(self.orb_min_matches_label, self._create_widget_with_help(self.orb_min_matches_spinbox, HELP_TEXTS["orb_min_matches"]))
        main_layout.addWidget(similar_group)

        # --- OK / Cancel ボタン ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    # --- プリセット関連メソッド (変更なし) ---
    def _populate_preset_combobox(self):
        current_selection = self.preset_combobox.currentData()
        self.preset_combobox.blockSignals(True)
        self.preset_combobox.clear()
        self.preset_combobox.addItem("--- 選択してください ---", "")
        for name in sorted(self.presets.keys()):
            self.preset_combobox.addItem(name, name)
        index_to_select = self.preset_combobox.findData(current_selection)
        if index_to_select != -1:
            self.preset_combobox.setCurrentIndex(index_to_select)
        else:
             self.preset_combobox.setCurrentIndex(0)
             self.delete_preset_button.setEnabled(False)
        self.preset_combobox.blockSignals(False)
        self._update_delete_button_state()

    @Slot(int)
    def _load_selected_preset(self, index: int):
        preset_name = self.preset_combobox.itemData(index)
        if preset_name and preset_name in self.presets:
            preset_settings = self.presets[preset_name]
            print(f"プリセット '{preset_name}' を読み込みます。")
            self._apply_settings_to_ui(preset_settings)
            self.delete_preset_button.setEnabled(True)
        else:
             self.delete_preset_button.setEnabled(False)

    @Slot()
    def _save_current_as_preset(self):
        preset_name, ok = QInputDialog.getText(self, "プリセット保存", "プリセット名を入力してください:")
        if ok and preset_name:
            preset_name = preset_name.strip()
            if not preset_name:
                 QMessageBox.warning(self, "エラー", "プリセット名は空にできません。")
                 return
            if preset_name in self.presets:
                reply = QMessageBox.question(self, "上書き確認", f"プリセット '{preset_name}' は既に存在します。\n上書きしますか？",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                             QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    return

            current_ui_settings = self._get_settings_from_ui()
            if 'presets' in current_ui_settings:
                del current_ui_settings['presets']
            keys_to_exclude = ['last_directory', 'last_save_load_dir']
            preset_data = {k: v for k, v in current_ui_settings.items() if k not in keys_to_exclude}

            self.presets[preset_name] = preset_data
            print(f"プリセット '{preset_name}' を保存しました。")
            self._populate_preset_combobox()
            new_index = self.preset_combobox.findData(preset_name)
            if new_index != -1:
                self.preset_combobox.setCurrentIndex(new_index)

        elif ok and not preset_name.strip():
             QMessageBox.warning(self, "エラー", "プリセット名は空にできません。")


    @Slot()
    def _delete_selected_preset(self):
        current_index = self.preset_combobox.currentIndex()
        if current_index <= 0: return
        preset_name = self.preset_combobox.currentData()
        if preset_name and preset_name in self.presets:
            reply = QMessageBox.question(self, "削除確認", f"プリセット '{preset_name}' を削除しますか？",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                del self.presets[preset_name]
                print(f"プリセット '{preset_name}' を削除しました。")
                self._populate_preset_combobox()

    def _update_delete_button_state(self):
         is_preset_selected = self.preset_combobox.currentIndex() > 0
         self.delete_preset_button.setEnabled(is_preset_selected)

    # --- 設定適用/取得ヘルパー関数 (変更なし) ---
    def _apply_settings_to_ui(self, settings_data: SettingsDict):
        """設定辞書をUIに反映する"""
        self.scan_subdirectories_checkbox.setChecked(bool(settings_data.get('scan_subdirectories', False)))

        blur_algo = str(settings_data.get('blur_algorithm', 'fft'))
        blur_idx = self.blur_algorithm_combobox.findData(blur_algo)
        self.blur_algorithm_combobox.setCurrentIndex(blur_idx if blur_idx != -1 else 0)

        fft_float = float(settings_data.get('blur_threshold', 0.80))
        self.blur_threshold_spinbox.setValue(math.floor(fft_float * 100))

        self.blur_laplacian_threshold_spinbox.setValue(int(settings_data.get('blur_laplacian_threshold', 100)))

        sim_mode = str(settings_data.get('similarity_mode', 'phash_orb'))
        sim_idx = self.similarity_mode_combobox.findData(sim_mode)
        self.similarity_mode_combobox.setCurrentIndex(sim_idx if sim_idx != -1 else 0)

        phash_int = int(settings_data.get('hash_threshold', 5))
        self.hash_threshold_spinbox.setValue(min(max(phash_int, 0), 100))

        self.orb_features_spinbox.setValue(int(settings_data.get('orb_nfeatures', 1500)))

        orb_ratio_float = float(settings_data.get('orb_ratio_threshold', 0.70))
        self.orb_ratio_spinbox.setValue(math.floor(orb_ratio_float * 100))

        self.orb_min_matches_spinbox.setValue(int(settings_data.get('min_good_matches', 40)))

        self._update_blur_threshold_visibility()
        self._update_similarity_options_visibility()

    def _get_settings_from_ui(self) -> SettingsDict:
        """現在のUIの状態から設定辞書を取得する"""
        settings = {}
        settings['scan_subdirectories'] = self.scan_subdirectories_checkbox.isChecked()
        settings['blur_algorithm'] = self.blur_algorithm_combobox.currentData()

        fft_int = self.blur_threshold_spinbox.value()
        settings['blur_threshold'] = float(fft_int / 100.0)

        settings['blur_laplacian_threshold'] = self.blur_laplacian_threshold_spinbox.value()
        settings['similarity_mode'] = self.similarity_mode_combobox.currentData()

        settings['hash_threshold'] = self.hash_threshold_spinbox.value()

        settings['orb_nfeatures'] = self.orb_features_spinbox.value()

        orb_ratio_int = self.orb_ratio_spinbox.value()
        settings['orb_ratio_threshold'] = float(orb_ratio_int / 100.0)

        settings['min_good_matches'] = self.orb_min_matches_spinbox.value()
        return settings

    # --- 既存のスロット (変更なし) ---
    @Slot(int)
    def _update_blur_threshold_visibility(self) -> None:
        selected_algo_key: str = self.blur_algorithm_combobox.currentData()
        is_fft: bool = (selected_algo_key == 'fft'); is_laplacian: bool = (selected_algo_key == 'laplacian')
        self.blur_threshold_label.setVisible(is_fft); self.blur_threshold_spinbox.setVisible(is_fft)
        self.blur_laplacian_threshold_label.setVisible(is_laplacian); self.blur_laplacian_threshold_spinbox.setVisible(is_laplacian)

    @Slot(int)
    def _update_similarity_options_visibility(self) -> None:
        selected_mode_key: str = self.similarity_mode_combobox.currentData()
        use_phash: bool = selected_mode_key in ['phash_orb', 'phash_only']; use_orb: bool = selected_mode_key in ['phash_orb', 'orb_only']
        self.hash_threshold_label.setVisible(use_phash); self.hash_threshold_spinbox.setVisible(use_phash)
        self.orb_features_label.setVisible(use_orb); self.orb_features_spinbox.setVisible(use_orb)
        self.orb_ratio_label.setVisible(use_orb); self.orb_ratio_spinbox.setVisible(use_orb)
        self.orb_min_matches_label.setVisible(use_orb); self.orb_min_matches_spinbox.setVisible(use_orb)

    def accept(self) -> None:
        """OKボタンが押されたときの処理"""
        self.current_settings = self._get_settings_from_ui()
        for key, value in self.original_settings.items():
             if key not in self.current_settings and key != 'presets':
                 self.current_settings[key] = value
        super().accept()

    def get_settings(self) -> SettingsDict:
        """ダイアログで設定された値を返す（プリセット情報も含む）"""
        final_settings = self.current_settings.copy()
        final_settings['presets'] = self.presets
        if 'use_phash' in final_settings: del final_settings['use_phash']
        return final_settings
