# gui/dialogs/settings_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QDoubleSpinBox, QSpinBox,
    QDialogButtonBox, QCheckBox, QGroupBox, QWidget, QComboBox,
    QHBoxLayout, QPushButton, QLineEdit, QMessageBox, QInputDialog # ★ 追加 ★
)
from PySide6.QtCore import Qt, Slot
from typing import Dict, Any, Union, Optional

# 型エイリアス
SettingsDict = Dict[str, Any] # presets を含むため Any

# ブレ検出アルゴリズムの定義 (変更なし)
BLUR_ALGORITHMS: Dict[str, str] = {
    "fft": "FFT (高速フーリエ変換)",
    "laplacian": "Laplacian Variance (ラプラシアン分散)"
}

# 類似度検出モードの定義 (変更なし)
SIMILARITY_MODES: Dict[str, str] = {
    "phash_orb": "pHash + ORB (推奨)",
    "phash_only": "pHash のみ (高速)",
    "orb_only": "ORB のみ (低速だが高精度)"
}

class SettingsDialog(QDialog):
    """アプリケーションの設定を行うダイアログ"""
    def __init__(self, current_settings: SettingsDict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setModal(True)
        # ★ current_settings は参照渡しになる可能性があるため、深いコピーを行う ★
        import copy
        self.original_settings = copy.deepcopy(current_settings) # 元の設定を保持
        self.current_settings = copy.deepcopy(current_settings) # ダイアログ内で編集する用
        # ★ プリセット辞書を取得 (存在しない場合は空辞書) ★
        self.presets: Dict[str, SettingsDict] = self.current_settings.get('presets', {})

        # ウィジェットの型ヒント
        # ... (既存のウィジェット型ヒント) ...
        self.scan_subdirectories_checkbox: QCheckBox
        self.blur_algorithm_label: QLabel; self.blur_algorithm_combobox: QComboBox
        self.blur_threshold_label: QLabel; self.blur_threshold_spinbox: QDoubleSpinBox
        self.blur_laplacian_threshold_label: QLabel; self.blur_laplacian_threshold_spinbox: QSpinBox
        self.similarity_mode_label: QLabel; self.similarity_mode_combobox: QComboBox
        self.hash_threshold_label: QLabel; self.hash_threshold_spinbox: QSpinBox
        self.orb_features_label: QLabel; self.orb_features_spinbox: QSpinBox
        self.orb_ratio_label: QLabel; self.orb_ratio_spinbox: QDoubleSpinBox
        self.orb_min_matches_label: QLabel; self.orb_min_matches_spinbox: QSpinBox
        # ★ プリセット用ウィジェット ★
        self.preset_label: QLabel
        self.preset_combobox: QComboBox
        self.save_preset_button: QPushButton
        self.delete_preset_button: QPushButton
        # ★★★★★★★★★★★★★★★★★★
        self.button_box: QDialogButtonBox

        self._setup_ui()
        self._update_blur_threshold_visibility()
        self._update_similarity_options_visibility()
        self._populate_preset_combobox() # ★ プリセットコンボボックス初期化 ★

    def _setup_ui(self) -> None:
        """UI要素の作成と配置"""
        main_layout = QVBoxLayout(self)

        # --- プリセット管理エリア ---
        preset_group = QGroupBox("プリセット")
        preset_layout = QHBoxLayout(preset_group) # 横並びにする
        self.preset_label = QLabel("読み込み:")
        self.preset_combobox = QComboBox()
        self.preset_combobox.setToolTip("保存済みの設定プリセットを選択して読み込みます。")
        # ★★★ 73行目の ' C' を削除 ★★★
        self.preset_combobox.addItem("--- 選択してください ---", "") # 初期項目
        # ★★★★★★★★★★★★★★★★★★★★★
        self.preset_combobox.currentIndexChanged.connect(self._load_selected_preset) # ★ スロット接続 ★

        self.save_preset_button = QPushButton("現在の設定を保存...")
        self.save_preset_button.setToolTip("現在のダイアログの設定を新しいプリセットとして保存します。")
        self.save_preset_button.clicked.connect(self._save_current_as_preset) # ★ スロット接続 ★

        self.delete_preset_button = QPushButton("選択したプリセットを削除")
        self.delete_preset_button.setToolTip("コンボボックスで選択されているプリセットを削除します。")
        self.delete_preset_button.clicked.connect(self._delete_selected_preset) # ★ スロット接続 ★
        self.delete_preset_button.setEnabled(False) # 初期状態では無効

        preset_layout.addWidget(self.preset_label)
        preset_layout.addWidget(self.preset_combobox, 1) # コンボボックスが伸びるように
        preset_layout.addWidget(self.save_preset_button)
        preset_layout.addWidget(self.delete_preset_button)
        main_layout.addWidget(preset_group)
        main_layout.addSpacing(10)

        # --- 一般設定 (変更なし) ---
        general_group = QGroupBox("スキャン設定")
        general_layout = QFormLayout(general_group)
        self.scan_subdirectories_checkbox = QCheckBox("サブディレクトリもスキャンする")
        self.scan_subdirectories_checkbox.setChecked(bool(self.current_settings.get('scan_subdirectories', False)))
        general_layout.addRow(self.scan_subdirectories_checkbox)
        main_layout.addWidget(general_group)

        # --- ブレ検出設定 (変更なし) ---
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
        blur_layout.addRow(self.blur_algorithm_label, self.blur_algorithm_combobox)
        self.blur_threshold_label = QLabel("FFT 閾値 (低いほどブレ):")
        self.blur_threshold_spinbox = QDoubleSpinBox(); self.blur_threshold_spinbox.setRange(0.0, 1.0); self.blur_threshold_spinbox.setSingleStep(0.01); self.blur_threshold_spinbox.setDecimals(4); self.blur_threshold_spinbox.setValue(float(self.current_settings.get('blur_threshold', 0.80)))
        blur_layout.addRow(self.blur_threshold_label, self.blur_threshold_spinbox)
        self.blur_laplacian_threshold_label = QLabel("Laplacian 閾値 (低いほどブレ):")
        self.blur_laplacian_threshold_spinbox = QSpinBox(); self.blur_laplacian_threshold_spinbox.setRange(0, 10000); self.blur_laplacian_threshold_spinbox.setSingleStep(10); self.blur_laplacian_threshold_spinbox.setValue(int(self.current_settings.get('blur_laplacian_threshold', 100)))
        blur_layout.addRow(self.blur_laplacian_threshold_label, self.blur_laplacian_threshold_spinbox)
        main_layout.addWidget(blur_group)

        # --- 類似ペア検出設定 (変更なし) ---
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
        similar_layout.addRow(self.similarity_mode_label, self.similarity_mode_combobox)
        self.hash_threshold_label = QLabel("pHash ハミング距離閾値:")
        self.hash_threshold_spinbox = QSpinBox(); self.hash_threshold_spinbox.setRange(0, 64); self.hash_threshold_spinbox.setSingleStep(1); self.hash_threshold_spinbox.setValue(int(self.current_settings.get('hash_threshold', 5)))
        similar_layout.addRow(self.hash_threshold_label, self.hash_threshold_spinbox)
        similar_layout.addRow(QLabel("-" * 30)) # 区切り線
        self.orb_features_label = QLabel("ORB 特徴点数:")
        self.orb_features_spinbox = QSpinBox(); self.orb_features_spinbox.setRange(100, 10000); self.orb_features_spinbox.setSingleStep(100); self.orb_features_spinbox.setValue(int(self.current_settings.get('orb_nfeatures', 1500)))
        self.orb_ratio_label = QLabel("ORB Ratio Test 閾値:")
        self.orb_ratio_spinbox = QDoubleSpinBox(); self.orb_ratio_spinbox.setRange(0.1, 0.95); self.orb_ratio_spinbox.setSingleStep(0.01); self.orb_ratio_spinbox.setDecimals(2); self.orb_ratio_spinbox.setValue(float(self.current_settings.get('orb_ratio_threshold', 0.70)))
        self.orb_min_matches_label = QLabel("ORB 最小マッチ数:")
        self.orb_min_matches_spinbox = QSpinBox(); self.orb_min_matches_spinbox.setRange(5, 500); self.orb_min_matches_spinbox.setSingleStep(1); self.orb_min_matches_spinbox.setValue(int(self.current_settings.get('min_good_matches', 40)))
        similar_layout.addRow(self.orb_features_label, self.orb_features_spinbox)
        similar_layout.addRow(self.orb_ratio_label, self.orb_ratio_spinbox)
        similar_layout.addRow(self.orb_min_matches_label, self.orb_min_matches_spinbox)
        main_layout.addWidget(similar_group)

        # --- OK / Cancel ボタン ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    # ★★★ プリセットコンボボックスを更新する関数 ★★★
    def _populate_preset_combobox(self):
        current_selection = self.preset_combobox.currentData() # 現在選択されているキーを保持
        self.preset_combobox.blockSignals(True) # 更新中のシグナル発行をブロック
        self.preset_combobox.clear()
        self.preset_combobox.addItem("--- 選択してください ---", "") # 初期項目
        # presets 辞書を名前でソートして追加
        for name in sorted(self.presets.keys()):
            self.preset_combobox.addItem(name, name) # 表示名と内部キー(名前)を設定

        # 以前の選択を復元 (存在すれば)
        index_to_select = self.preset_combobox.findData(current_selection)
        if index_to_select != -1:
            self.preset_combobox.setCurrentIndex(index_to_select)
        else:
             self.preset_combobox.setCurrentIndex(0) # デフォルトに戻す
             self.delete_preset_button.setEnabled(False) # 削除ボタン無効化

        self.preset_combobox.blockSignals(False) # シグナル発行を再開
        # 削除ボタンの状態更新
        self._update_delete_button_state()

    # ★★★ 選択されたプリセットを読み込むスロット ★★★
    @Slot(int)
    def _load_selected_preset(self, index: int):
        preset_name = self.preset_combobox.itemData(index)
        if preset_name and preset_name in self.presets:
            preset_settings = self.presets[preset_name]
            print(f"プリセット '{preset_name}' を読み込みます。")
            # 現在のダイアログの設定をプリセット値で更新
            # (プリセットにないキーは現在の値を維持する)
            self._apply_settings_to_ui(preset_settings)
            # 削除ボタンの状態更新
            self.delete_preset_button.setEnabled(True)
        else:
             # "--- 選択してください ---" が選ばれた場合など
             self.delete_preset_button.setEnabled(False)

    # ★★★ 現在の設定を新しいプリセットとして保存するスロット ★★★
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

            # 現在のUIの値から設定辞書を作成
            current_ui_settings = self._get_settings_from_ui()
            # presets キー自体は保存しない
            if 'presets' in current_ui_settings:
                del current_ui_settings['presets']
            # last_directory など、プリセットに含めない方が良い設定を除く (任意)
            keys_to_exclude = ['last_directory', 'last_save_load_dir']
            preset_data = {k: v for k, v in current_ui_settings.items() if k not in keys_to_exclude}


            self.presets[preset_name] = preset_data
            print(f"プリセット '{preset_name}' を保存しました。")
            # コンボボックスを更新して新しいプリセットを表示・選択
            self._populate_preset_combobox()
            new_index = self.preset_combobox.findData(preset_name)
            if new_index != -1:
                self.preset_combobox.setCurrentIndex(new_index)

        elif ok and not preset_name.strip():
             QMessageBox.warning(self, "エラー", "プリセット名は空にできません。")


    # ★★★ 選択されているプリセットを削除するスロット ★★★
    @Slot()
    def _delete_selected_preset(self):
        current_index = self.preset_combobox.currentIndex()
        if current_index <= 0: # "--選択--" は削除不可
            return
        preset_name = self.preset_combobox.currentData()
        if preset_name and preset_name in self.presets:
            reply = QMessageBox.question(self, "削除確認", f"プリセット '{preset_name}' を削除しますか？",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                del self.presets[preset_name]
                print(f"プリセット '{preset_name}' を削除しました。")
                self._populate_preset_combobox() # コンボボックス更新

    # ★★★ 削除ボタンの有効/無効を更新する関数 ★★★
    def _update_delete_button_state(self):
         is_preset_selected = self.preset_combobox.currentIndex() > 0
         self.delete_preset_button.setEnabled(is_preset_selected)

    # ★★★ 設定辞書をUIに反映するヘルパー関数 ★★★
    def _apply_settings_to_ui(self, settings_data: SettingsDict):
        # 各ウィジェットに値を設定
        self.scan_subdirectories_checkbox.setChecked(bool(settings_data.get('scan_subdirectories', False)))

        blur_algo = str(settings_data.get('blur_algorithm', 'fft'))
        blur_idx = self.blur_algorithm_combobox.findData(blur_algo)
        self.blur_algorithm_combobox.setCurrentIndex(blur_idx if blur_idx != -1 else 0)
        self.blur_threshold_spinbox.setValue(float(settings_data.get('blur_threshold', 0.80)))
        self.blur_laplacian_threshold_spinbox.setValue(int(settings_data.get('blur_laplacian_threshold', 100)))

        sim_mode = str(settings_data.get('similarity_mode', 'phash_orb'))
        sim_idx = self.similarity_mode_combobox.findData(sim_mode)
        self.similarity_mode_combobox.setCurrentIndex(sim_idx if sim_idx != -1 else 0)
        self.hash_threshold_spinbox.setValue(int(settings_data.get('hash_threshold', 5)))
        self.orb_features_spinbox.setValue(int(settings_data.get('orb_nfeatures', 1500)))
        self.orb_ratio_spinbox.setValue(float(settings_data.get('orb_ratio_threshold', 0.70)))
        self.orb_min_matches_spinbox.setValue(int(settings_data.get('min_good_matches', 40)))

        # 表示状態も更新
        self._update_blur_threshold_visibility()
        self._update_similarity_options_visibility()

    # ★★★ 現在のUIの状態から設定辞書を取得するヘルパー関数 ★★★
    def _get_settings_from_ui(self) -> SettingsDict:
        settings = {}
        settings['scan_subdirectories'] = self.scan_subdirectories_checkbox.isChecked()
        settings['blur_algorithm'] = self.blur_algorithm_combobox.currentData()
        settings['blur_threshold'] = self.blur_threshold_spinbox.value()
        settings['blur_laplacian_threshold'] = self.blur_laplacian_threshold_spinbox.value()
        settings['similarity_mode'] = self.similarity_mode_combobox.currentData()
        settings['hash_threshold'] = self.hash_threshold_spinbox.value()
        settings['orb_nfeatures'] = self.orb_features_spinbox.value()
        settings['orb_ratio_threshold'] = self.orb_ratio_spinbox.value()
        settings['min_good_matches'] = self.orb_min_matches_spinbox.value()
        # プリセット自体や last_directory などは含めない
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
        # 現在のUIの設定を取得
        self.current_settings = self._get_settings_from_ui()
        # プリセット情報を元の設定に追加（あるいは更新）
        # ★ self.original_settings を直接変更せず、get_settings で返すようにする ★
        # self.original_settings['presets'] = self.presets
        # current_settings にもプリセット以外の元の設定を引き継ぐ
        for key, value in self.original_settings.items():
             if key not in self.current_settings and key != 'presets':
                 self.current_settings[key] = value
        # presets は get_settings() 側で追加する

        super().accept()

    def get_settings(self) -> SettingsDict:
        """ダイアログで設定された値を返す（プリセット情報も含む）"""
        # 最終的な設定にプリセット情報をマージ
        final_settings = self.current_settings.copy()
        final_settings['presets'] = self.presets # 保存されたプリセットを追加
        # 不要になったキーを削除
        if 'use_phash' in final_settings: del final_settings['use_phash']
        return final_settings

