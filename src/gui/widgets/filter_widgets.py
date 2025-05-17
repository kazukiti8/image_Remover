# gui/widgets/filter_widgets.py
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                              QSlider, QDoubleSpinBox, QPushButton, QCheckBox,
                              QLineEdit, QFormLayout, QComboBox, QGroupBox)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from typing import Optional, Tuple, List, Dict, Any, Union

class BlurryFilterWidget(QWidget):
    """ブレ画像フィルター用ウィジェット"""
    filter_changed = Signal()  # フィルター条件が変更されたときに発火するシグナル
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
        self._timer = QTimer(self)  # 連続スライダー操作時の過剰シグナル防止用
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.filter_changed.emit)
        
    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # フィルターのタイトル
        title_label = QLabel("フィルター条件")
        title_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(title_label)
        
        # ブレスコアのフィルターグループ
        score_group = QGroupBox("ブレスコア")
        score_layout = QVBoxLayout(score_group)
        
        # スコア範囲スライダー
        slider_layout = QHBoxLayout()
        self.min_score_spin = QDoubleSpinBox()
        self.min_score_spin.setRange(0.0, 1.0)
        self.min_score_spin.setSingleStep(0.01)
        self.min_score_spin.setDecimals(2)
        self.min_score_spin.setValue(0.0)
        self.min_score_spin.setMinimumWidth(60)
        
        self.max_score_spin = QDoubleSpinBox()
        self.max_score_spin.setRange(0.0, 1.0)
        self.max_score_spin.setSingleStep(0.01)
        self.max_score_spin.setDecimals(2)
        self.max_score_spin.setValue(1.0)
        self.max_score_spin.setMinimumWidth(60)
        
        slider_layout.addWidget(QLabel("最小:"))
        slider_layout.addWidget(self.min_score_spin)
        slider_layout.addWidget(QLabel("最大:"))
        slider_layout.addWidget(self.max_score_spin)
        
        score_layout.addLayout(slider_layout)
        
        # スライダー（ビジュアル表現）
        range_layout = QHBoxLayout()
        self.min_score_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_score_slider.setRange(0, 100)
        self.min_score_slider.setValue(0)
        
        self.max_score_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_score_slider.setRange(0, 100)
        self.max_score_slider.setValue(100)
        
        range_layout.addWidget(self.min_score_slider)
        range_layout.addWidget(self.max_score_slider)
        
        score_layout.addLayout(range_layout)
        main_layout.addWidget(score_group)
        
        # ファイル名のフィルターグループ
        name_group = QGroupBox("ファイル名")
        name_layout = QVBoxLayout(name_group)
        
        self.filename_filter = QLineEdit()
        self.filename_filter.setPlaceholderText("ファイル名に含まれるテキスト")
        name_layout.addWidget(self.filename_filter)
        
        main_layout.addWidget(name_group)
        
        # リセットボタン
        reset_layout = QHBoxLayout()
        self.reset_button = QPushButton("フィルターをリセット")
        reset_layout.addStretch()
        reset_layout.addWidget(self.reset_button)
        
        main_layout.addLayout(reset_layout)
        main_layout.addStretch()
        
    def _connect_signals(self) -> None:
        # 即時反映せず、値の変更が終わったタイミングでフィルター適用
        self.min_score_spin.editingFinished.connect(self._on_spin_value_changed)
        self.max_score_spin.editingFinished.connect(self._on_spin_value_changed)
        
        # スライダーの値が変わったらスピンボックスに反映
        self.min_score_slider.valueChanged.connect(self._min_slider_changed)
        self.max_score_slider.valueChanged.connect(self._max_slider_changed)
        
        # スライダーのドラッグ完了時にフィルターを適用
        self.min_score_slider.sliderReleased.connect(self._on_slider_released)
        self.max_score_slider.sliderReleased.connect(self._on_slider_released)
        
        # ファイル名フィルターは入力完了時（エンターキー押下時）にフィルター適用
        self.filename_filter.editingFinished.connect(self.filter_changed.emit)
        
        # リセットボタン
        self.reset_button.clicked.connect(self.reset_filters)
    
    @Slot()
    def _on_spin_value_changed(self) -> None:
        # スピンボックスの値をスライダーに反映
        min_value = int(self.min_score_spin.value() * 100)
        max_value = int(self.max_score_spin.value() * 100)
        
        self.min_score_slider.blockSignals(True)
        self.max_score_slider.blockSignals(True)
        
        self.min_score_slider.setValue(min_value)
        self.max_score_slider.setValue(max_value)
        
        self.min_score_slider.blockSignals(False)
        self.max_score_slider.blockSignals(False)
        
        # 値の変更をフィルターに反映
        self.filter_changed.emit()
    
    @Slot(int)
    def _min_slider_changed(self, value: int) -> None:
        # 最小値スライダーが最大値を超えないようにする
        if value > self.max_score_slider.value():
            self.min_score_slider.setValue(self.max_score_slider.value())
            return
        
        # スライダーの値をスピンボックスに反映
        self.min_score_spin.blockSignals(True)
        self.min_score_spin.setValue(value / 100.0)
        self.min_score_spin.blockSignals(False)
        
        # タイマーをリセット（連続操作時の過剰なフィルター適用を防止）
        self._timer.start(300)  # 300ms後にfilter_changedシグナルを発火
    
    @Slot(int)
    def _max_slider_changed(self, value: int) -> None:
        # 最大値スライダーが最小値を下回らないようにする
        if value < self.min_score_slider.value():
            self.max_score_slider.setValue(self.min_score_slider.value())
            return
        
        # スライダーの値をスピンボックスに反映
        self.max_score_spin.blockSignals(True)
        self.max_score_spin.setValue(value / 100.0)
        self.max_score_spin.blockSignals(False)
        
        # タイマーをリセット（連続操作時の過剰なフィルター適用を防止）
        self._timer.start(300)  # 300ms後にfilter_changedシグナルを発火
    
    @Slot()
    def _on_slider_released(self) -> None:
        # スライダーのドラッグが完了したらタイマーをキャンセルして即時フィルター適用
        self._timer.stop()
        self.filter_changed.emit()
    
    @Slot()
    def reset_filters(self) -> None:
        """フィルターをデフォルト値にリセットする"""
        self.min_score_spin.setValue(0.0)
        self.max_score_spin.setValue(1.0)
        self.min_score_slider.setValue(0)
        self.max_score_slider.setValue(100)
        self.filename_filter.clear()
        self.filter_changed.emit()
    
    def get_filter_criteria(self) -> Dict[str, Any]:
        """現在のフィルター条件を辞書として返す"""
        return {
            'min_score': self.min_score_spin.value(),
            'max_score': self.max_score_spin.value(),
            'filename': self.filename_filter.text()
        }
    
    def set_filter_criteria(self, criteria: Dict[str, Any]) -> None:
        """辞書からフィルター条件を設定する"""
        if 'min_score' in criteria:
            min_score = float(criteria['min_score'])
            self.min_score_spin.setValue(min_score)
            self.min_score_slider.setValue(int(min_score * 100))
        
        if 'max_score' in criteria:
            max_score = float(criteria['max_score'])
            self.max_score_spin.setValue(max_score)
            self.max_score_slider.setValue(int(max_score * 100))
        
        if 'filename' in criteria:
            self.filename_filter.setText(str(criteria['filename']))


class SimilarityFilterWidget(QWidget):
    """類似度フィルター用ウィジェット"""
    filter_changed = Signal()  # フィルター条件が変更されたときに発火するシグナル
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
        self._timer = QTimer(self)  # 連続スライダー操作時の過剰シグナル防止用
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.filter_changed.emit)
        
    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # フィルターのタイトル
        title_label = QLabel("フィルター条件")
        title_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(title_label)
        
        # 類似度のフィルターグループ
        score_group = QGroupBox("類似度")
        score_layout = QVBoxLayout(score_group)
        
        # 類似度範囲（パーセント表示）
        slider_layout = QHBoxLayout()
        self.min_similarity_spin = QSpinBox()
        self.min_similarity_spin.setRange(0, 100)
        self.min_similarity_spin.setSingleStep(1)
        self.min_similarity_spin.setValue(0)
        self.min_similarity_spin.setSuffix("%")
        self.min_similarity_spin.setMinimumWidth(60)
        
        self.max_similarity_spin = QSpinBox()
        self.max_similarity_spin.setRange(0, 100)
        self.max_similarity_spin.setSingleStep(1)
        self.max_similarity_spin.setValue(100)
        self.max_similarity_spin.setSuffix("%")
        self.max_similarity_spin.setMinimumWidth(60)
        
        slider_layout.addWidget(QLabel("最小:"))
        slider_layout.addWidget(self.min_similarity_spin)
        slider_layout.addWidget(QLabel("最大:"))
        slider_layout.addWidget(self.max_similarity_spin)
        
        score_layout.addLayout(slider_layout)
        
        # スライダー（ビジュアル表現）
        range_layout = QHBoxLayout()
        self.min_similarity_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_similarity_slider.setRange(0, 100)
        self.min_similarity_slider.setValue(0)
        
        self.max_similarity_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_similarity_slider.setRange(0, 100)
        self.max_similarity_slider.setValue(100)
        
        range_layout.addWidget(self.min_similarity_slider)
        range_layout.addWidget(self.max_similarity_slider)
        
        score_layout.addLayout(range_layout)
        
        # 重複（100%一致）のみ表示するオプション
        duplicates_layout = QHBoxLayout()
        self.duplicates_only_checkbox = QCheckBox("重複（100%一致）のみ表示")
        duplicates_layout.addWidget(self.duplicates_only_checkbox)
        score_layout.addLayout(duplicates_layout)
        
        main_layout.addWidget(score_group)
        
        # ファイル名のフィルターグループ
        name_group = QGroupBox("ファイル名")
        name_layout = QVBoxLayout(name_group)
        
        self.filename_filter = QLineEdit()
        self.filename_filter.setPlaceholderText("ファイル名に含まれるテキスト")
        name_layout.addWidget(self.filename_filter)
        
        main_layout.addWidget(name_group)
        
        # リセットボタン
        reset_layout = QHBoxLayout()
        self.reset_button = QPushButton("フィルターをリセット")
        reset_layout.addStretch()
        reset_layout.addWidget(self.reset_button)
        
        main_layout.addLayout(reset_layout)
        main_layout.addStretch()
        
    def _connect_signals(self) -> None:
        # 即時反映せず、値の変更が終わったタイミングでフィルター適用
        self.min_similarity_spin.editingFinished.connect(self._on_spin_value_changed)
        self.max_similarity_spin.editingFinished.connect(self._on_spin_value_changed)
        
        # スライダーの値が変わったらスピンボックスに反映
        self.min_similarity_slider.valueChanged.connect(self._min_slider_changed)
        self.max_similarity_slider.valueChanged.connect(self._max_slider_changed)
        
        # スライダーのドラッグ完了時にフィルターを適用
        self.min_similarity_slider.sliderReleased.connect(self._on_slider_released)
        self.max_similarity_slider.sliderReleased.connect(self._on_slider_released)
        
        # 重複のみチェックボックスの変更時にフィルター適用
        self.duplicates_only_checkbox.toggled.connect(self._on_duplicates_only_toggled)
        
        # ファイル名フィルターは入力完了時（エンターキー押下時）にフィルター適用
        self.filename_filter.editingFinished.connect(self.filter_changed.emit)
        
        # リセットボタン
        self.reset_button.clicked.connect(self.reset_filters)
    
    @Slot()
    def _on_spin_value_changed(self) -> None:
        # スピンボックスの値をスライダーに反映
        min_value = self.min_similarity_spin.value()
        max_value = self.max_similarity_spin.value()
        
        self.min_similarity_slider.blockSignals(True)
        self.max_similarity_slider.blockSignals(True)
        
        self.min_similarity_slider.setValue(min_value)
        self.max_similarity_slider.setValue(max_value)
        
        self.min_similarity_slider.blockSignals(False)
        self.max_similarity_slider.blockSignals(False)
        
        # 値の変更をフィルターに反映
        self.filter_changed.emit()
    
    @Slot(int)
    def _min_slider_changed(self, value: int) -> None:
        # 最小値スライダーが最大値を超えないようにする
        if value > self.max_similarity_slider.value():
            self.min_similarity_slider.setValue(self.max_similarity_slider.value())
            return
        
        # スライダーの値をスピンボックスに反映
        self.min_similarity_spin.blockSignals(True)
        self.min_similarity_spin.setValue(value)
        self.min_similarity_spin.blockSignals(False)
        
        # タイマーをリセット（連続操作時の過剰なフィルター適用を防止）
        self._timer.start(300)  # 300ms後にfilter_changedシグナルを発火
    
    @Slot(int)
    def _max_slider_changed(self, value: int) -> None:
        # 最大値スライダーが最小値を下回らないようにする
        if value < self.min_similarity_slider.value():
            self.max_similarity_slider.setValue(self.min_similarity_slider.value())
            return
        
        # スライダーの値をスピンボックスに反映
        self.max_similarity_spin.blockSignals(True)
        self.max_similarity_spin.setValue(value)
        self.max_similarity_spin.blockSignals(False)
        
        # タイマーをリセット（連続操作時の過剰なフィルター適用を防止）
        self._timer.start(300)  # 300ms後にfilter_changedシグナルを発火
    
    @Slot()
    def _on_slider_released(self) -> None:
        # スライダーのドラッグが完了したらタイマーをキャンセルして即時フィルター適用
        self._timer.stop()
        self.filter_changed.emit()
    
    @Slot(bool)
    def _on_duplicates_only_toggled(self, checked: bool) -> None:
        # 「重複のみ表示」がオンの場合は、スライダーを100%に固定
        if checked:
            self.min_similarity_spin.blockSignals(True)
            self.max_similarity_spin.blockSignals(True)
            self.min_similarity_slider.blockSignals(True)
            self.max_similarity_slider.blockSignals(True)
            
            self.min_similarity_spin.setValue(100)
            self.max_similarity_spin.setValue(100)
            self.min_similarity_slider.setValue(100)
            self.max_similarity_slider.setValue(100)
            
            self.min_similarity_spin.setEnabled(False)
            self.max_similarity_spin.setEnabled(False)
            self.min_similarity_slider.setEnabled(False)
            self.max_similarity_slider.setEnabled(False)
            
            self.min_similarity_spin.blockSignals(False)
            self.max_similarity_spin.blockSignals(False)
            self.min_similarity_slider.blockSignals(False)
            self.max_similarity_slider.blockSignals(False)
        else:
            # チェックが外れたら、スライダーを再度有効化
            self.min_similarity_spin.setEnabled(True)
            self.max_similarity_spin.setEnabled(True)
            self.min_similarity_slider.setEnabled(True)
            self.max_similarity_slider.setEnabled(True)
        
        self.filter_changed.emit()
    
    @Slot()
    def reset_filters(self) -> None:
        """フィルターをデフォルト値にリセットする"""
        self.min_similarity_spin.blockSignals(True)
        self.max_similarity_spin.blockSignals(True)
        self.min_similarity_slider.blockSignals(True)
        self.max_similarity_slider.blockSignals(True)
        self.duplicates_only_checkbox.blockSignals(True)
        
        self.min_similarity_spin.setValue(0)
        self.max_similarity_spin.setValue(100)
        self.min_similarity_slider.setValue(0)
        self.max_similarity_slider.setValue(100)
        self.duplicates_only_checkbox.setChecked(False)
        self.filename_filter.clear()
        
        self.min_similarity_spin.setEnabled(True)
        self.max_similarity_spin.setEnabled(True)
        self.min_similarity_slider.setEnabled(True)
        self.max_similarity_slider.setEnabled(True)
        
        self.min_similarity_spin.blockSignals(False)
        self.max_similarity_spin.blockSignals(False)
        self.min_similarity_slider.blockSignals(False)
        self.max_similarity_slider.blockSignals(False)
        self.duplicates_only_checkbox.blockSignals(False)
        
        self.filter_changed.emit()
    
    def get_filter_criteria(self) -> Dict[str, Any]:
        """現在のフィルター条件を辞書として返す"""
        return {
            'min_similarity': self.min_similarity_spin.value(),
            'max_similarity': self.max_similarity_spin.value(),
            'duplicates_only': self.duplicates_only_checkbox.isChecked(),
            'filename': self.filename_filter.text()
        }
    
    def set_filter_criteria(self, criteria: Dict[str, Any]) -> None:
        """辞書からフィルター条件を設定する"""
        # フィルター値の設定前にシグナルをブロック
        self.min_similarity_spin.blockSignals(True)
        self.max_similarity_spin.blockSignals(True)
        self.min_similarity_slider.blockSignals(True)
        self.max_similarity_slider.blockSignals(True)
        self.duplicates_only_checkbox.blockSignals(True)
        
        if 'min_similarity' in criteria:
            min_similarity = int(criteria['min_similarity'])
            self.min_similarity_spin.setValue(min_similarity)
            self.min_similarity_slider.setValue(min_similarity)
        
        if 'max_similarity' in criteria:
            max_similarity = int(criteria['max_similarity'])
            self.max_similarity_spin.setValue(max_similarity)
            self.max_similarity_slider.setValue(max_similarity)
        
        if 'duplicates_only' in criteria:
            duplicates_only = bool(criteria['duplicates_only'])
            self.duplicates_only_checkbox.setChecked(duplicates_only)
            
            # 重複のみモードの場合は範囲スライダーを無効化
            if duplicates_only:
                self.min_similarity_spin.setValue(100)
                self.max_similarity_spin.setValue(100)
                self.min_similarity_slider.setValue(100)
                self.max_similarity_slider.setValue(100)
                
                self.min_similarity_spin.setEnabled(False)
                self.max_similarity_spin.setEnabled(False)
                self.min_similarity_slider.setEnabled(False)
                self.max_similarity_slider.setEnabled(False)
        
        if 'filename' in criteria:
            self.filename_filter.setText(str(criteria['filename']))
        
        # シグナルブロックを解除
        self.min_similarity_spin.blockSignals(False)
        self.max_similarity_spin.blockSignals(False)
        self.min_similarity_slider.blockSignals(False)
        self.max_similarity_slider.blockSignals(False)
        self.duplicates_only_checkbox.blockSignals(False)