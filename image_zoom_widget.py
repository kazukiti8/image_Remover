import os
import cv2
import numpy as np
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                           QScrollArea, QSizePolicy, QSlider, QFrame, QToolBar, 
                           QAction, QToolButton, QSpinBox, QComboBox)
from PyQt5.QtGui import QPixmap, QImage, QCursor, QIcon, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QSize, QRect, QPoint, pyqtSignal


class ZoomableImageWidget(QWidget):
    """ズーム可能な画像表示ウィジェット"""
    
    # マウス操作イベントシグナル
    image_clicked = pyqtSignal(QPoint)  # 画像上でクリックされた座標
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_path = None
        self.pixmap = None
        self.original_pixmap = None
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        self.zoom_step = 0.1
        self.drag_start_pos = None
        self.drag_mode = False
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # スクロールエリア
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        
        # 画像ラベル
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.image_label.setScaledContents(True)
        self.image_label.setMinimumSize(1, 1)
        self.image_label.mousePressEvent = self.label_mouse_press_event
        self.image_label.mouseMoveEvent = self.label_mouse_move_event
        self.image_label.mouseReleaseEvent = self.label_mouse_release_event
        self.image_label.wheelEvent = self.label_wheel_event
        
        # スクロールエリアにラベルを設定
        self.scroll_area.setWidget(self.image_label)
        
        # コントロールツールバー
        self.toolbar = QToolBar()
        
        # ズームインボタン
        self.zoom_in_btn = QToolButton()
        self.zoom_in_btn.setText("+")
        self.zoom_in_btn.setToolTip("拡大")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.toolbar.addWidget(self.zoom_in_btn)
        
        # ズームアウトボタン
        self.zoom_out_btn = QToolButton()
        self.zoom_out_btn.setText("-")
        self.zoom_out_btn.setToolTip("縮小")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.toolbar.addWidget(self.zoom_out_btn)
        
        # ズーム値表示
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(60)
        self.toolbar.addWidget(self.zoom_label)
        
        # ズーム値スライダー
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(int(self.min_zoom * 100), int(self.max_zoom * 100))
        self.zoom_slider.setValue(int(self.zoom_factor * 100))
        self.zoom_slider.valueChanged.connect(self.on_slider_value_changed)
        self.toolbar.addWidget(self.zoom_slider)
        
        # フィット表示ボタン
        self.fit_btn = QToolButton()
        self.fit_btn.setText("フィット")
        self.fit_btn.setToolTip("画面に合わせる")
        self.fit_btn.clicked.connect(self.fit_to_window)
        self.toolbar.addWidget(self.fit_btn)
        
        # 原寸表示ボタン
        self.original_btn = QToolButton()
        self.original_btn.setText("原寸")
        self.original_btn.setToolTip("原寸大で表示")
        self.original_btn.clicked.connect(self.show_original_size)
        self.toolbar.addWidget(self.original_btn)
        
        # レイアウトに追加
        layout.addWidget(self.toolbar)
        layout.addWidget(self.scroll_area)
        
        self.setLayout(layout)
    
    def set_image(self, image_path):
        """画像を設定"""
        self.image_path = image_path
        
        if not image_path or not os.path.exists(image_path):
            self.clear_image()
            return False
        
        try:
            # 画像を読み込み
            img = cv2.imread(str(image_path))
            if img is None:
                self.clear_image()
                return False
            
            # OpenCVの画像をQImageに変換 (BGR -> RGB)
            height, width, channels = img.shape
            bytes_per_line = channels * width
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            q_img = QImage(img_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)
            
            # QPixmapに変換して保存
            self.original_pixmap = QPixmap.fromImage(q_img)
            self.pixmap = self.original_pixmap.copy()
            
            # 画像を表示
            self.image_label.setPixmap(self.pixmap)
            self.image_label.adjustSize()
            
            # 初期表示時にフィットさせる
            self.fit_to_window()
            
            return True
            
        except Exception as e:
            print(f"画像読み込みエラー ({image_path}): {e}")
            self.clear_image()
            return False
    
    def clear_image(self):
        """画像をクリア"""
        self.image_path = None
        self.pixmap = None
        self.original_pixmap = None
        self.image_label.clear()
        self.image_label.adjustSize()
        self.zoom_factor = 1.0
        self.update_zoom_display()
    
    def zoom_in(self):
        """拡大"""
        if not self.pixmap:
            return
        
        self.set_zoom(self.zoom_factor + self.zoom_step)
    
    def zoom_out(self):
        """縮小"""
        if not self.pixmap:
            return
        
        self.set_zoom(self.zoom_factor - self.zoom_step)
    
    def set_zoom(self, factor):
        """ズーム率を設定"""
        if not self.pixmap:
            return
        
        # ズーム範囲を制限
        factor = max(self.min_zoom, min(self.max_zoom, factor))
        
        # 現在のズーム率と同じなら何もしない
        if self.zoom_factor == factor:
            return
        
        # ズーム率を更新
        self.zoom_factor = factor
        
        # ラベルの中心座標を取得
        scroll_h = self.scroll_area.horizontalScrollBar()
        scroll_v = self.scroll_area.verticalScrollBar()
        center_x = scroll_h.value() + self.scroll_area.width() / 2
        center_y = scroll_v.value() + self.scroll_area.height() / 2
        
        # ズーム前の中心座標の相対位置を計算
        rel_x = center_x / self.image_label.width() if self.image_label.width() > 0 else 0.5
        rel_y = center_y / self.image_label.height() if self.image_label.height() > 0 else 0.5
        
        # ズームを適用
        new_width = int(self.original_pixmap.width() * self.zoom_factor)
        new_height = int(self.original_pixmap.height() * self.zoom_factor)
        
        # サイズ変更
        self.image_label.setFixedSize(new_width, new_height)
        
        # 画像を更新
        self.update_zoom_display()
        
        # スクロール位置を調整
        QScrollArea.update(self.scroll_area)
        new_center_x = int(new_width * rel_x - self.scroll_area.width() / 2)
        new_center_y = int(new_height * rel_y - self.scroll_area.height() / 2)
        scroll_h.setValue(max(0, new_center_x))
        scroll_v.setValue(max(0, new_center_y))
    
    def update_zoom_display(self):
        """ズーム表示を更新"""
        # ラベルを更新
        zoom_percent = int(self.zoom_factor * 100)
        self.zoom_label.setText(f"{zoom_percent}%")
        
        # スライダーを更新（シグナルの再帰呼び出しを防ぐ）
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(zoom_percent)
        self.zoom_slider.blockSignals(False)
        
        # ピクセルデータを更新
        if self.original_pixmap:
            # 拡大・縮小した画像を作成
            scaled_pixmap = self.original_pixmap.scaled(
                int(self.original_pixmap.width() * self.zoom_factor),
                int(self.original_pixmap.height() * self.zoom_factor),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
    
    def on_slider_value_changed(self, value):
        """スライダーの値が変更された時"""
        zoom_factor = value / 100.0
        self.set_zoom(zoom_factor)
    
    def fit_to_window(self):
        """ウィンドウに合わせる"""
        if not self.original_pixmap:
            return
        
        # スクロールエリアのサイズを取得
        viewport_width = self.scroll_area.width() - 2  # 枠線の分を引く
        viewport_height = self.scroll_area.height() - 2
        
        # 画像のサイズを取得
        pixmap_width = self.original_pixmap.width()
        pixmap_height = self.original_pixmap.height()
        
        # 縦横比を維持したまま、ビューポートに収まるようなズーム率を計算
        width_ratio = viewport_width / pixmap_width
        height_ratio = viewport_height / pixmap_height
        
        # 小さい方の比率を使用
        zoom_factor = min(width_ratio, height_ratio)
        
        # ズームを適用
        self.set_zoom(zoom_factor)
    
    def show_original_size(self):
        """原寸大で表示"""
        if not self.original_pixmap:
            return
        
        self.set_zoom(1.0)
    
    def label_mouse_press_event(self, event):
        """画像ラベル上でのマウスプレスイベント"""
        if event.button() == Qt.LeftButton:
            # 左クリックでドラッグモード開始
            self.drag_mode = True
            self.drag_start_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def label_mouse_move_event(self, event):
        """画像ラベル上でのマウス移動イベント"""
        if self.drag_mode and self.drag_start_pos:
            # ドラッグ中はスクロール位置を調整
            delta = event.pos() - self.drag_start_pos
            
            scroll_h = self.scroll_area.horizontalScrollBar()
            scroll_v = self.scroll_area.verticalScrollBar()
            
            scroll_h.setValue(scroll_h.value() - delta.x())
            scroll_v.setValue(scroll_v.value() - delta.y())
            
            self.drag_start_pos = event.pos()
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def label_mouse_release_event(self, event):
        """画像ラベル上でのマウスリリースイベント"""
        if event.button() == Qt.LeftButton and self.drag_mode:
            # ドラッグモード終了
            self.drag_mode = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            
            # クリックイベントをエミット（ドラッグでなければ）
            if (event.pos() - self.drag_start_pos).manhattanLength() < 5:
                self.image_clicked.emit(event.pos())
        else:
            super().mouseReleaseEvent(event)
    
    def label_wheel_event(self, event):
        """画像ラベル上でのマウスホイールイベント"""
        # ホイール回転でズーム
        delta = event.angleDelta().y()
        
        if delta > 0:
            # 上回転で拡大
            self.zoom_in()
        elif delta < 0:
            # 下回転で縮小
            self.zoom_out()
        
        event.accept()


class MultiViewImageWidget(QWidget):
    """マルチビュー画像表示ウィジェット"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_mode = "normal"  # normal, split, grid
        self.images = []
        self.current_index = -1
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        # ツールバー
        toolbar = QToolBar()
        
        # 表示モード選択
        self.view_mode_combo = QComboBox()
        self.view_mode_combo.addItems(["標準表示", "分割表示", "グリッド表示"])
        self.view_mode_combo.currentIndexChanged.connect(self.change_view_mode)
        toolbar.addWidget(QLabel("表示モード:"))
        toolbar.addWidget(self.view_mode_combo)
        
        # 先頭へボタン
        self.first_btn = QToolButton()
        self.first_btn.setText("<<")
        self.first_btn.setToolTip("先頭へ")
        self.first_btn.clicked.connect(self.go_to_first)
        toolbar.addWidget(self.first_btn)
        
        # 前へボタン
        self.prev_btn = QToolButton()
        self.prev_btn.setText("<")
        self.prev_btn.setToolTip("前へ")
        self.prev_btn.clicked.connect(self.go_to_prev)
        toolbar.addWidget(self.prev_btn)
        
        # 画像インデックス表示
        self.index_label = QLabel("0/0")
        self.index_label.setMinimumWidth(60)
        self.index_label.setAlignment(Qt.AlignCenter)
        toolbar.addWidget(self.index_label)
        
        # 次へボタン
        self.next_btn = QToolButton()
        self.next_btn.setText(">")
        self.next_btn.setToolTip("次へ")
        self.next_btn.clicked.connect(self.go_to_next)
        toolbar.addWidget(self.next_btn)
        
        # 最後へボタン
        self.last_btn = QToolButton()
        self.last_btn.setText(">>")
        self.last_btn.setToolTip("最後へ")
        self.last_btn.clicked.connect(self.go_to_last)
        toolbar.addWidget(self.last_btn)
        
        layout.addWidget(toolbar)
        
        # メイン表示エリア
        self.stack_layout = QVBoxLayout()
        
        # 標準表示（1枚表示）
        self.normal_widget = ZoomableImageWidget()
        self.stack_layout.addWidget(self.normal_widget)
        
        # 分割表示（2枚表示）
        self.split_widget = QWidget()
        split_layout = QHBoxLayout(self.split_widget)
        self.left_image = ZoomableImageWidget()
        self.right_image = ZoomableImageWidget()
        split_layout.addWidget(self.left_image)
        split_layout.addWidget(self.right_image)
        self.split_widget.setLayout(split_layout)
        self.split_widget.hide()
        self.stack_layout.addWidget(self.split_widget)
        
        # グリッド表示は必要に応じて動的に作成
        
        layout.addLayout(self.stack_layout)
        
        self.setLayout(layout)
        
        # 初期状態ではボタンを無効化
        self.update_navigation_buttons()
    
    def set_images(self, image_paths):
        """表示する画像のリストを設定"""
        self.images = image_paths
        self.current_index = 0 if image_paths else -1
        
        # ナビゲーションを更新
        self.update_navigation_buttons()
        self.update_index_display()
        
        # 現在の表示モードに応じて画像を表示
        self.update_current_view()
    
    def update_navigation_buttons(self):
        """ナビゲーションボタンの有効/無効を更新"""
        has_images = len(self.images) > 0
        has_prev = self.current_index > 0
        has_next = self.current_index < len(self.images) - 1
        
        self.first_btn.setEnabled(has_prev)
        self.prev_btn.setEnabled(has_prev)
        self.next_btn.setEnabled(has_next)
        self.last_btn.setEnabled(has_next)
    
    def update_index_display(self):
        """インデックス表示を更新"""
        if len(self.images) > 0 and self.current_index >= 0:
            self.index_label.setText(f"{self.current_index + 1}/{len(self.images)}")
        else:
            self.index_label.setText("0/0")
    
    def update_current_view(self):
        """現在の表示モードに応じて画像を表示"""
        if self.current_mode == "normal":
            self.update_normal_view()
        elif self.current_mode == "split":
            self.update_split_view()
        elif self.current_mode == "grid":
            self.update_grid_view()
    
    def update_normal_view(self):
        """通常表示を更新"""
        # 他のビューを非表示
        self.split_widget.hide()
        self.normal_widget.show()
        
        # 画像を表示
        if len(self.images) > 0 and self.current_index >= 0:
            self.normal_widget.set_image(self.images[self.current_index])
        else:
            self.normal_widget.clear_image()
    
    def update_split_view(self):
        """分割表示を更新"""
        # 他のビューを非表示
        self.normal_widget.hide()
        self.split_widget.show()
        
        # 左側の画像（現在の画像）
        if len(self.images) > 0 and self.current_index >= 0:
            self.left_image.set_image(self.images[self.current_index])
        else:
            self.left_image.clear_image()
        
        # 右側の画像（次の画像）
        next_index = self.current_index + 1
        if len(self.images) > next_index and next_index >= 0:
            self.right_image.set_image(self.images[next_index])
        else:
            self.right_image.clear_image()
    
    def update_grid_view(self):
        """グリッド表示を更新"""
        # 現在は未実装
        # 必要に応じて実装する
        pass
    
    def change_view_mode(self, index):
        """表示モードを変更"""
        modes = ["normal", "split", "grid"]
        if index < len(modes):
            self.current_mode = modes[index]
            self.update_current_view()
    
    def go_to_first(self):
        """先頭の画像へ移動"""
        if len(self.images) > 0:
            self.current_index = 0
            self.update_navigation_buttons()
            self.update_index_display()
            self.update_current_view()
    
    def go_to_prev(self):
        """前の画像へ移動"""
        if self.current_index > 0:
            self.current_index -= 1
            self.update_navigation_buttons()
            self.update_index_display()
            self.update_current_view()
    
    def go_to_next(self):
        """次の画像へ移動"""
        if self.current_index < len(self.images) - 1:
            self.current_index += 1
            self.update_navigation_buttons()
            self.update_index_display()
            self.update_current_view()
    
    def go_to_last(self):
        """最後の画像へ移動"""
        if len(self.images) > 0:
            self.current_index = len(self.images) - 1
            self.update_navigation_buttons()
            self.update_index_display()
            self.update_current_view()
    
    def set_current_index(self, index):
        """表示する画像のインデックスを設定"""
        if 0 <= index < len(self.images):
            self.current_index = index
            self.update_navigation_buttons()
            self.update_index_display()
            self.update_current_view()
            return True
        return False
