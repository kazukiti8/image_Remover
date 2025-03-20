import os
import json
import configparser
from PyQt5.QtCore import QSettings, QDir
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                           QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
                           QTabWidget, QFormLayout, QGroupBox, QFileDialog, QDialog,
                           QDialogButtonBox, QMessageBox)


class SettingsManager:
    """設定管理クラス"""
    
    def __init__(self, app_name="ImageCleanupSystem", org_name="ImageTools"):
        """
        初期化関数
        
        Parameters:
        app_name (str): アプリケーション名
        org_name (str): 組織名
        """
        self.app_name = app_name
        self.org_name = org_name
        
        # QSettings インスタンスを作成
        self.qsettings = QSettings(self.org_name, self.app_name)
        
        # 設定ファイルのパス
        self.settings_dir = os.path.join(QDir.homePath(), f".{self.app_name.lower()}")
        self.settings_file = os.path.join(self.settings_dir, "settings.json")
        
        # デフォルト設定
        self.default_settings = {
            "general": {
                "last_directory": "",
                "auto_fit_preview": True,
                "theme": "system",
                "language": "ja",
                "confirm_deletes": True
            },
            "cleanup": {
                "blur_threshold": 100.0,
                "similarity_threshold": 10,
                "duplicate_check_enabled": True,
                "similar_check_enabled": True,
                "blur_check_enabled": True
            },
            "quality": {
                "exposure_weight": 1.0,
                "contrast_weight": 1.0,
                "noise_weight": 1.0,
                "composition_weight": 1.0,
                "sharpness_weight": 1.5
            },
            "ui": {
                "thumbnail_size": 120,
                "grid_columns": 4,
                "show_exif": True,
                "show_preview": True,
                "window_width": 1200,
                "window_height": 800
            }
        }
        
        # 保存されている設定をロード
        self.settings = self.load_settings()
    
    def load_settings(self):
        """設定をロード"""
        settings = {}
        
        # まずはQSettingsからロード
        self.load_from_qsettings(settings)
        
        # 次にJSONファイルからロード（存在する場合）
        self.load_from_json(settings)
        
        # 欠けている設定にはデフォルト値を使用
        self.merge_with_defaults(settings)
        
        return settings
    
    def load_from_qsettings(self, settings):
        """QSettingsから設定をロード"""
        for group_name in self.default_settings.keys():
            self.qsettings.beginGroup(group_name)
            settings[group_name] = {}
            
            for key in self.default_settings[group_name].keys():
                if self.qsettings.contains(key):
                    value = self.qsettings.value(key)
                    
                    # 型変換（QSettingsの値は文字列になっている場合があるため）
                    default_value = self.default_settings[group_name][key]
                    if isinstance(default_value, bool):
                        if isinstance(value, str):
                            value = value.lower() in ("true", "1", "yes")
                        else:
                            value = bool(value)
                    elif isinstance(default_value, int):
                        value = int(value)
                    elif isinstance(default_value, float):
                        value = float(value)
                    
                    settings[group_name][key] = value
            
            self.qsettings.endGroup()
    
    def load_from_json(self, settings):
        """JSONファイルから設定をロード"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    json_settings = json.load(f)
                
                # 既存の設定に結合
                for group_name, group_settings in json_settings.items():
                    if group_name not in settings:
                        settings[group_name] = {}
                    
                    for key, value in group_settings.items():
                        settings[group_name][key] = value
            except Exception as e:
                print(f"設定ファイルの読み込みエラー: {e}")
    
    def merge_with_defaults(self, settings):
        """デフォルト設定と結合"""
        for group_name, group_defaults in self.default_settings.items():
            if group_name not in settings:
                settings[group_name] = {}
            
            for key, default_value in group_defaults.items():
                if key not in settings[group_name]:
                    settings[group_name][key] = default_value
    
    def save_settings(self):
        """設定を保存"""
        # QSettingsに保存
        for group_name, group_settings in self.settings.items():
            self.qsettings.beginGroup(group_name)
            
            for key, value in group_settings.items():
                self.qsettings.setValue(key, value)
            
            self.qsettings.endGroup()
        
        # JSONファイルに保存
        self.save_to_json()
    
    def save_to_json(self):
        """設定をJSONファイルに保存"""
        try:
            # 設定ディレクトリが存在しない場合は作成
            if not os.path.exists(self.settings_dir):
                os.makedirs(self.settings_dir)
            
            # 設定をJSON形式で保存
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"設定ファイルの保存エラー: {e}")
            return False
    
    def get(self, group, key, default=None):
        """
        設定値を取得
        
        Parameters:
        group (str): 設定グループ
        key (str): 設定キー
        default: デフォルト値
        
        Returns:
        設定値
        """
        if group in self.settings and key in self.settings[group]:
            return self.settings[group][key]
        return default
    
    def set(self, group, key, value):
        """
        設定値を設定
        
        Parameters:
        group (str): 設定グループ
        key (str): 設定キー
        value: 設定値
        """
        if group not in self.settings:
            self.settings[group] = {}
        
        self.settings[group][key] = value
    
    def get_all(self):
        """全ての設定を取得"""
        return self.settings
    
    def reset(self):
        """設定をデフォルトに戻す"""
        self.settings = self.default_settings.copy()
        self.save_settings()
    
    def export_settings(self, filepath):
        """設定をファイルにエクスポート"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"設定のエクスポートエラー: {e}")
            return False
    
    def import_settings(self, filepath):
        """設定をファイルからインポート"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                imported_settings = json.load(f)
            
            # インポートした設定を検証
            for group_name, group_defaults in self.default_settings.items():
                if group_name in imported_settings:
                    for key, default_value in group_defaults.items():
                        if key in imported_settings[group_name]:
                            value = imported_settings[group_name][key]
                            
                            # 値の型チェック
                            if not isinstance(value, type(default_value)):
                                # 型変換を試みる
                                try:
                                    if isinstance(default_value, bool):
                                        if isinstance(value, str):
                                            value = value.lower() in ("true", "1", "yes")
                                        else:
                                            value = bool(value)
                                    elif isinstance(default_value, int):
                                        value = int(value)
                                    elif isinstance(default_value, float):
                                        value = float(value)
                                    
                                    imported_settings[group_name][key] = value
                                except:
                                    # 変換できなければデフォルト値を使用
                                    imported_settings[group_name][key] = default_value
            
            # 設定を更新
            self.settings.update(imported_settings)
            
            # 保存
            self.save_settings()
            
            return True
        except Exception as e:
            print(f"設定のインポートエラー: {e}")
            return False


class SettingsDialog(QDialog):
    """設定ダイアログ"""
    
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.settings = settings_manager.get_all()
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle("設定")
        self.resize(600, 500)
        
        layout = QVBoxLayout()
        
        # タブウィジェット
        self.tabs = QTabWidget()
        
        # 一般設定タブ
        general_tab = self.create_general_tab()
        self.tabs.addTab(general_tab, "一般")
        
        # クリーンアップ設定タブ
        cleanup_tab = self.create_cleanup_tab()
        self.tabs.addTab(cleanup_tab, "クリーンアップ")
        
        # 画質設定タブ
        quality_tab = self.create_quality_tab()
        self.tabs.addTab(quality_tab, "画質評価")
        
        # UI設定タブ
        ui_tab = self.create_ui_tab()
        self.tabs.addTab(ui_tab, "表示")
        
        layout.addWidget(self.tabs)
        
        # ボタン
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply | QDialogButtonBox.Reset)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.Apply).clicked.connect(self.apply_settings)
        button_box.button(QDialogButtonBox.Reset).clicked.connect(self.reset_settings)
        
        # インポート・エクスポートボタン
        buttons_layout = QHBoxLayout()
        
        import_btn = QPushButton("インポート...")
        import_btn.clicked.connect(self.import_settings)
        buttons_layout.addWidget(import_btn)
        
        export_btn = QPushButton("エクスポート...")
        export_btn.clicked.connect(self.export_settings)
        buttons_layout.addWidget(export_btn)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(button_box)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def create_general_tab(self):
        """一般設定タブを作成"""
        tab = QWidget()
        layout = QFormLayout()
        
        # 最後に使用したディレクトリ
        self.last_dir_edit = QLineEdit()
        self.last_dir_edit.setText(self.settings["general"]["last_directory"])
        browse_btn = QPushButton("参照...")
        browse_btn.clicked.connect(self.browse_directory)
        
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.last_dir_edit)
        dir_layout.addWidget(browse_btn)
        
        layout.addRow("最後に使用したディレクトリ:", dir_layout)
        
        # プレビュー自動フィット
        self.auto_fit_check = QCheckBox()
        self.auto_fit_check.setChecked(self.settings["general"]["auto_fit_preview"])
        layout.addRow("プレビューを自動的にフィット:", self.auto_fit_check)
        
        # テーマ
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["システム", "ライト", "ダーク"])
        theme = self.settings["general"]["theme"]
        if theme == "light":
            self.theme_combo.setCurrentIndex(1)
        elif theme == "dark":
            self.theme_combo.setCurrentIndex(2)
        else:
            self.theme_combo.setCurrentIndex(0)
        layout.addRow("テーマ:", self.theme_combo)
        
        # 言語
        self.language_combo = QComboBox()
        self.language_combo.addItems(["日本語", "English"])
        if self.settings["general"]["language"] == "en":
            self.language_combo.setCurrentIndex(1)
        else:
            self.language_combo.setCurrentIndex(0)
        layout.addRow("言語:", self.language_combo)
        
        # 削除確認
        self.confirm_delete_check = QCheckBox()
        self.confirm_delete_check.setChecked(self.settings["general"]["confirm_deletes"])
        layout.addRow("削除時に確認:", self.confirm_delete_check)
        
        tab.setLayout(layout)
        return tab
    
    def create_cleanup_tab(self):
        """クリーンアップ設定タブを作成"""
        tab = QWidget()
        layout = QFormLayout()
        
        # ブレ検出閾値
        self.blur_threshold_spin = QDoubleSpinBox()
        self.blur_threshold_spin.setRange(10, 500)
        self.blur_threshold_spin.setSingleStep(5)
        self.blur_threshold_spin.setValue(self.settings["cleanup"]["blur_threshold"])
        layout.addRow("ブレ検出閾値:", self.blur_threshold_spin)
        
        # 類似画像閾値
        self.similarity_threshold_spin = QSpinBox()
        self.similarity_threshold_spin.setRange(1, 30)
        self.similarity_threshold_spin.setValue(self.settings["cleanup"]["similarity_threshold"])
        layout.addRow("類似画像閾値:", self.similarity_threshold_spin)
        
        # 有効/無効設定
        self.duplicate_check = QCheckBox()
        self.duplicate_check.setChecked(self.settings["cleanup"]["duplicate_check_enabled"])
        layout.addRow("重複画像チェックを有効:", self.duplicate_check)
        
        self.similar_check = QCheckBox()
        self.similar_check.setChecked(self.settings["cleanup"]["similar_check_enabled"])
        layout.addRow("類似画像チェックを有効:", self.similar_check)
        
        self.blur_check = QCheckBox()
        self.blur_check.setChecked(self.settings["cleanup"]["blur_check_enabled"])
        layout.addRow("ブレ画像チェックを有効:", self.blur_check)
        
        tab.setLayout(layout)
        return tab
    
    def create_quality_tab(self):
        """画質評価設定タブを作成"""
        tab = QWidget()
        layout = QFormLayout()
        
        # 各評価項目の重み
        self.exposure_weight_spin = QDoubleSpinBox()
        self.exposure_weight_spin.setRange(0.5, 3.0)
        self.exposure_weight_spin.setSingleStep(0.1)
        self.exposure_weight_spin.setValue(self.settings["quality"]["exposure_weight"])
        layout.addRow("露出評価の重み:", self.exposure_weight_spin)
        
        self.contrast_weight_spin = QDoubleSpinBox()
        self.contrast_weight_spin.setRange(0.5, 3.0)
        self.contrast_weight_spin.setSingleStep(0.1)
        self.contrast_weight_spin.setValue(self.settings["quality"]["contrast_weight"])
        layout.addRow("コントラスト評価の重み:", self.contrast_weight_spin)
        
        self.noise_weight_spin = QDoubleSpinBox()
        self.noise_weight_spin.setRange(0.5, 3.0)
        self.noise_weight_spin.setSingleStep(0.1)
        self.noise_weight_spin.setValue(self.settings["quality"]["noise_weight"])
        layout.addRow("ノイズ評価の重み:", self.noise_weight_spin)
        
        self.composition_weight_spin = QDoubleSpinBox()
        self.composition_weight_spin.setRange(0.5, 3.0)
        self.composition_weight_spin.setSingleStep(0.1)
        self.composition_weight_spin.setValue(self.settings["quality"]["composition_weight"])
        layout.addRow("構図評価の重み:", self.composition_weight_spin)
        
        self.sharpness_weight_spin = QDoubleSpinBox()
        self.sharpness_weight_spin.setRange(0.5, 3.0)
        self.sharpness_weight_spin.setSingleStep(0.1)
        self.sharpness_weight_spin.setValue(self.settings["quality"]["sharpness_weight"])
        layout.addRow("シャープネス評価の重み:", self.sharpness_weight_spin)
        
        tab.setLayout(layout)
        return tab
    
    def create_ui_tab(self):
        """UI設定タブを作成"""
        tab = QWidget()
        layout = QFormLayout()
        
        # サムネイルサイズ
        self.thumbnail_size_spin = QSpinBox()
        self.thumbnail_size_spin.setRange(60, 240)
        self.thumbnail_size_spin.setValue(self.settings["ui"]["thumbnail_size"])
        layout.addRow("サムネイルサイズ:", self.thumbnail_size_spin)
        
        # グリッド列数
        self.grid_columns_spin = QSpinBox()
        self.grid_columns_spin.setRange(1, 10)
        self.grid_columns_spin.setValue(self.settings["ui"]["grid_columns"])
        layout.addRow("グリッド列数:", self.grid_columns_spin)
        
        # EXIF表示
        self.show_exif_check = QCheckBox()
        self.show_exif_check.setChecked(self.settings["ui"]["show_exif"])
        layout.addRow("EXIFを表示:", self.show_exif_check)
        
        # プレビュー表示
        self.show_preview_check = QCheckBox()
        self.show_preview_check.setChecked(self.settings["ui"]["show_preview"])
        layout.addRow("プレビューを表示:", self.show_preview_check)
        
        # ウィンドウサイズ
        size_layout = QHBoxLayout()
        
        self.window_width_spin = QSpinBox()
        self.window_width_spin.setRange(800, 3840)
        self.window_width_spin.setValue(self.settings["ui"]["window_width"])
        size_layout.addWidget(self.window_width_spin)
        
        size_layout.addWidget(QLabel("×"))
        
        self.window_height_spin = QSpinBox()
        self.window_height_spin.setRange(600, 2160)
        self.window_height_spin.setValue(self.settings["ui"]["window_height"])
        size_layout.addWidget(self.window_height_spin)
        
        layout.addRow("ウィンドウサイズ:", size_layout)
        
        tab.setLayout(layout)
        return tab
    
    def browse_directory(self):
        """ディレクトリ選択ダイアログを表示"""
        dir_path = QFileDialog.getExistingDirectory(self, "ディレクトリを選択")
        if dir_path:
            self.last_dir_edit.setText(dir_path)
    
    def apply_settings(self):
        """設定を適用"""
        # 一般設定
        self.settings["general"]["last_directory"] = self.last_dir_edit.text()
        self.settings["general"]["auto_fit_preview"] = self.auto_fit_check.isChecked()
        self.settings["general"]["confirm_deletes"] = self.confirm_delete_check.isChecked()
        
        # テーマ
        theme_index = self.theme_combo.currentIndex()
        if theme_index == 1:
            self.settings["general"]["theme"] = "light"
        elif theme_index == 2:
            self.settings["general"]["theme"] = "dark"
        else:
            self.settings["general"]["theme"] = "system"
        
        # 言語
        language_index = self.language_combo.currentIndex()
        if language_index == 1:
            self.settings["general"]["language"] = "en"
        else:
            self.settings["general"]["language"] = "ja"
        
        # クリーンアップ設定
        self.settings["cleanup"]["blur_threshold"] = self.blur_threshold_spin.value()
        self.settings["cleanup"]["similarity_threshold"] = self.similarity_threshold_spin.value()
        self.settings["cleanup"]["duplicate_check_enabled"] = self.duplicate_check.isChecked()
        self.settings["cleanup"]["similar_check_enabled"] = self.similar_check.isChecked()
        self.settings["cleanup"]["blur_check_enabled"] = self.blur_check.isChecked()
        
        # 画質設定
        self.settings["quality"]["exposure_weight"] = self.exposure_weight_spin.value()
        self.settings["quality"]["contrast_weight"] = self.contrast_weight_spin.value()
        self.settings["quality"]["noise_weight"] = self.noise_weight_spin.value()
        self.settings["quality"]["composition_weight"] = self.composition_weight_spin.value()
        self.settings["quality"]["sharpness_weight"] = self.sharpness_weight_spin.value()
        
        # UI設定
        self.settings["ui"]["thumbnail_size"] = self.thumbnail_size_spin.value()
        self.settings["ui"]["grid_columns"] = self.grid_columns_spin.value()
        self.settings["ui"]["show_exif"] = self.show_exif_check.isChecked()
        self.settings["ui"]["show_preview"] = self.show_preview_check.isChecked()
        self.settings["ui"]["window_width"] = self.window_width_spin.value()
        self.settings["ui"]["window_height"] = self.window_height_spin.value()
        
        # 設定を保存
        self.settings_manager.save_settings()
    
    def reset_settings(self):
        """設定をリセット"""
        reply = QMessageBox.question(
            self,
            "設定のリセット",
            "全ての設定をデフォルトに戻しますか？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.settings_manager.reset()
            self.settings = self.settings_manager.get_all()
            
            # UIを更新
            self.update_ui_from_settings()
    
    def update_ui_from_settings(self):
        """設定からUIを更新"""
        # 一般設定
        self.last_dir_edit.setText(self.settings["general"]["last_directory"])
        self.auto_fit_check.setChecked(self.settings["general"]["auto_fit_preview"])
        self.confirm_delete_check.setChecked(self.settings["general"]["confirm_deletes"])
        
        # テーマ
        theme = self.settings["general"]["theme"]
        if theme == "light":
            self.theme_combo.setCurrentIndex(1)
        elif theme == "dark":
            self.theme_combo.setCurrentIndex(2)
        else:
            self.theme_combo.setCurrentIndex(0)
        
        # 言語
        if self.settings["general"]["language"] == "en":
            self.language_combo.setCurrentIndex(1)
        else:
            self.language_combo.setCurrentIndex(0)
        
        # クリーンアップ設定
        self.blur_threshold_spin.setValue(self.settings["cleanup"]["blur_threshold"])
        self.similarity_threshold_spin.setValue(self.settings["cleanup"]["similarity_threshold"])
        self.duplicate_check.setChecked(self.settings["cleanup"]["duplicate_check_enabled"])
        self.similar_check.setChecked(self.settings["cleanup"]["similar_check_enabled"])
        self.blur_check.setChecked(self.settings["cleanup"]["blur_check_enabled"])
        
        # 画質設定
        self.exposure_weight_spin.setValue(self.settings["quality"]["exposure_weight"])
        self.contrast_weight_spin.setValue(self.settings["quality"]["contrast_weight"])
        self.noise_weight_spin.setValue(self.settings["quality"]["noise_weight"])
        self.composition_weight_spin.setValue(self.settings["quality"]["composition_weight"])
        self.sharpness_weight_spin.setValue(self.settings["quality"]["sharpness_weight"])
        
        # UI設定
        self.thumbnail_size_spin.setValue(self.settings["ui"]["thumbnail_size"])
        self.grid_columns_spin.setValue(self.settings["ui"]["grid_columns"])
        self.show_exif_check.setChecked(self.settings["ui"]["show_exif"])
        self.show_preview_check.setChecked(self.settings["ui"]["show_preview"])
        self.window_width_spin.setValue(self.settings["ui"]["window_width"])
        self.window_height_spin.setValue(self.settings["ui"]["window_height"])
    
    def export_settings(self):
        """設定をエクスポート"""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "設定をエクスポート",
            "",
            "JSON ファイル (*.json)"
        )
        
        if filepath:
            # 現在のダイアログ上の設定を適用
            self.apply_settings()
            
            # 設定をエクスポート
            if self.settings_manager.export_settings(filepath):
                QMessageBox.information(self, "エクスポート完了", f"設定を {filepath} にエクスポートしました。")
            else:
                QMessageBox.critical(self, "エクスポートエラー", "設定のエクスポート中にエラーが発生しました。")
    
    def import_settings(self):
        """設定をインポート"""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "設定をインポート",
            "",
            "JSON ファイル (*.json)"
        )
        
        if filepath:
            reply = QMessageBox.question(
                self,
                "設定のインポート",
                "現在の設定がインポートした設定で上書きされます。続行しますか？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                if self.settings_manager.import_settings(filepath):
                    self.settings = self.settings_manager.get_all()
                    self.update_ui_from_settings()
                    QMessageBox.information(self, "インポート完了", "設定をインポートしました。")
                else:
                    QMessageBox.critical(self, "インポートエラー", "設定のインポート中にエラーが発生しました。")
    
    def accept(self):
        """OKボタンが押された時"""
        self.apply_settings()
        super().accept()
