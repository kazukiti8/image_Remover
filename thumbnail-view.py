import os
import math
from PyQt5.QtWidgets import (QWidget, QGridLayout, QVBoxLayout, QLabel, QScrollArea, 
                           QCheckBox, QSlider, QComboBox, QHBoxLayout, QSizePolicy)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QThread, QMutex, QWaitCondition

import cv2
import numpy as np


class ThumbnailGenerator(QThread):
    """サムネイル生成用スレッド"""
    thumbnail_generated = pyqtSignal(str, QPixmap)
    
    def __init__(self, image_paths, size):
        super().__init__()
        self.image_paths = image_paths
        self.thumbnail_size = size
        self.canceled = False
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.running = True
    
    def run(self):
        """スレッド実行"""
        for img_path in self.image_paths:
            if self.canceled:
                break
                
            try:
                # 画像を読み込み
                img = cv2.imread(img_path)
                if img is None:
                    continue
                
                # サムネイルサイズにリサイズ
                height, width = img.shape[:2]
                aspect_ratio = width / height
                
                if width > height:
                    new_width = self.thumbnail_size
                    new_height = int(new_width / aspect_ratio)
                else:
                    new_height = self.thumbnail_size
                    new_width = int(new_height * aspect_ratio)
                
                # リサイズ
                thumbnail = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
                
                # OpenCVの画像をQImageに変換 (BGR -> RGB)
                height, width, channels = thumbnail.shape
                bytes_per_line = channels * width
                img_rgb = cv2.cvtColor(thumbnail, cv2.COLOR_BGR2RGB)
                q_img = QImage(img_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)
                
                # QPixmapに変換
                pixmap = QPixmap.fromImage(q_img)
                
                # シグナルを発行
                self.thumbnail_generated.emit(img_path, pixmap)
                
                # スレッドが一時停止されているか確認
                self.mutex.lock()
                if not self.running:
                    self.condition.wait(self.mutex)
                self.mutex.unlock()
                
            except Exception as e:
                print(f"サムネイル生成エラー ({img_path}): {e}")
    
    def cancel(self):
        """生成をキャンセル"""
        self.canceled = True
    
    def pause(self):
        """スレッドを一時停止"""
        self.mutex.lock()
        self.running = False
        self.mutex.unlock()
    
    def resume(self):
        """スレッドを再開"""
        self.mutex.lock()
        self.running = True
        self.condition.wakeAll()
        self.mutex.unlock()


class ThumbnailItem(QWidget):
    """サムネイル項目ウィジェット"""
    clicked = pyqtSignal(str)
    checkbox_toggled = pyqtSignal(str, bool)
    
    def __init__(self, image_path, thumbnail_size=120, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.thumbnail_size = thumbnail_size
        self.is_selected = False
        self.pixmap = None
        self.initUI()
    
    def initUI(self):
        """UIを初期化"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # チェックボックス
        self.checkbox = QCheckBox()
        self.checkbox.stateChanged.connect(self.on_checkbox_toggled)
        layout.addWidget(self.checkbox, 0, Qt.AlignLeft)
        
        # サムネイル画像
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        self.thumbnail_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        layout.addWidget(self.thumbnail_label)
        
        # ファイル名ラベル
        file_name = os.path.basename(self.image_path)
        if len(file_name) > 15:
            file_name = file_name[:12] + "..."
        self.name_label = QLabel(file_name)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setToolTip(self.image_path)
        layout.addWidget(self.name_label)
        
        self.setLayout(layout)
        
        # クリックイベントを接続
        self.mousePressEvent = self.on_mouse_press
    
    def set_thumbnail(self, pixmap):
        """サムネイル画像を設定"""
        if pixmap:
            self.pixmap = pixmap
            scaled_pixmap = pixmap.scaled(
                self.thumbnail_size, 
                self.thumbnail_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.thumbnail_label.setPixmap(scaled_pixmap)
    
    def on_mouse_press(self, event):
        """マウスプレスイベント"""
        # 左クリックのみ処理
        if event.button() == Qt.LeftButton:
            # チェックボックスがクリックされた場合は何もしない
            if self.checkbox.geometry().contains(event.pos()):
                return
                
            # 選択状態を反転
            self.is_selected = not self.is_selected
            
            # 状態を更新
            self.setStyleSheet("background-color: #e0e0ff;" if self.is_selected else "")
            
            # シグナルを発行
            self.clicked.emit(self.image_path)
    
    def on_checkbox_toggled(self, state):
        """チェックボックスがトグルされた時の処理"""
        is_checked = (state == Qt.Checked)
        self.checkbox_toggled.emit(self.image_path, is_checked)
    
    def set_checked(self, checked):
        """チェック状態を設定"""
        self.checkbox.setChecked(checked)
    
    def is_checked(self):
        """チェック状態を取得"""
        return self.checkbox.isChecked()


class ThumbnailGridView(QWidget):
    """サムネイルグリッド表示ウィジェット"""
    item_selected = pyqtSignal(str)
    item_checkbox_toggled = pyqtSignal(str, bool)
    
    def __init__(self, thumbnail_size=120, columns=4, parent=None):
        super().__init__(parent)
        self.thumbnail_size = thumbnail_size
        self.columns = columns
        self.image_paths = []
        self.thumbnail_items = {}
        self.generator_thread = None
        self.initUI()
    
    def initUI(self):
        """UIを初期化"""
        main_layout = QVBoxLayout()
        
        # コントロールエリア
        control_layout = QHBoxLayout()
        
        # 表示サイズスライダー
        control_layout.addWidget(QLabel("サイズ:"))
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(60, 240)
        self.size_slider.setValue(self.thumbnail_size)
        self.size_slider.valueChanged.connect(self.on_size_changed)
        control_layout.addWidget(self.size_slider)
        
        # 列数選択
        control_layout.addWidget(QLabel("列数:"))
        self.columns_combo = QComboBox()
        self.columns_combo.addItems(["2", "3", "4", "5", "6"])
        self.columns_combo.setCurrentIndex(self.columns - 2)  # 2列が最小なので-2
        self.columns_combo.currentIndexChanged.connect(self.on_columns_changed)
        control_layout.addWidget(self.columns_combo)
        
        # 並び替え
        control_layout.addWidget(QLabel("並び替え:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["名前順", "日付順", "サイズ順"])
        self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)
        control_layout.addWidget(self.sort_combo)
        
        main_layout.addLayout(control_layout)
        
        # スクロールエリア
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        # グリッドウィジェット
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(10)
        
        self.scroll_area.setWidget(self.grid_widget)
        main_layout.addWidget(self.scroll_area)
        
        self.setLayout(main_layout)
    
    def set_images(self, image_paths):
        """画像のリストを設定"""
        # 既存のサムネイル生成スレッドをキャンセル
        if self.generator_thread and self.generator_thread.isRunning():
            self.generator_thread.cancel()
            self.generator_thread.wait()
        
        # グリッドをクリア
        self.clear_grid()
        
        # 画像パスを保存
        self.image_paths = image_paths
        
        if not image_paths:
            return
        
        # グリッドレイアウトを設定
        self.setup_grid()
        
        # サムネイル生成スレッドを開始
        self.generator_thread = ThumbnailGenerator(image_paths, self.thumbnail_size)
        self.generator_thread.thumbnail_generated.connect(self.on_thumbnail_generated)
        self.generator_thread.start()
    
    def setup_grid(self):
        """グリッドレイアウトを設定"""
        # 既存のアイテムをクリア
        self.clear_grid()
        
        # サムネイル項目を作成
        row = 0
        col = 0
        
        for img_path in self.image_paths:
            item = ThumbnailItem(img_path, self.thumbnail_size)
            item.clicked.connect(self.on_item_clicked)
            item.checkbox_toggled.connect(self.on_item_checkbox_toggled)
            
            self.grid_layout.addWidget(item, row, col)
            self.thumbnail_items[img_path] = item
            
            col += 1
            if col >= self.columns:
                col = 0
                row += 1
    
    def clear_grid(self):
        """グリッドをクリア"""
        # 全てのウィジェットを削除
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # サムネイル項目の辞書をクリア
        self.thumbnail_items = {}
    
    def on_thumbnail_generated(self, image_path, pixmap):
        """サムネイル生成完了時の処理"""
        if image_path in self.thumbnail_items:
            self.thumbnail_items[image_path].set_thumbnail(pixmap)
    
    def on_item_clicked(self, image_path):
        """サムネイル項目がクリックされた時の処理"""
        # 項目選択シグナルを発行
        self.item_selected.emit(image_path)
    
    def on_item_checkbox_toggled(self, image_path, checked):
        """サムネイル項目のチェックボックスがトグルされた時の処理"""
        # チェックボックストグルシグナルを発行
        self.item_checkbox_toggled.emit(image_path, checked)
    
    def on_size_changed(self, size):
        """サムネイルサイズが変更された時の処理"""
        if size == self.thumbnail_size:
            return
            
        self.thumbnail_size = size
        
        # 画像を再読み込み
        if self.image_paths:
            self.set_images(self.image_paths)
    
    def on_columns_changed(self, index):
        """列数が変更された時の処理"""
        columns = index + 2  # インデックスは0から始まるので+2
        
        if columns == self.columns:
            return
            
        self.columns = columns
        
        # グリッドを再構成
        if self.image_paths:
            self.setup_grid()
            
            # 既存のサムネイルを再設定
            for path, item in self.thumbnail_items.items():
                if hasattr(item, 'pixmap') and item.pixmap:
                    item.set_thumbnail(item.pixmap)
    
    def on_sort_changed(self, index):
        """並び替えが変更された時の処理"""
        if not self.image_paths:
            return
            
        # 並び替え方法に応じて画像パスをソート
        if index == 0:  # 名前順
            sorted_paths = sorted(self.image_paths, key=lambda p: os.path.basename(p).lower())
        elif index == 1:  # 日付順
            sorted_paths = sorted(self.image_paths, key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0)
        elif index == 2:  # サイズ順
            sorted_paths = sorted(self.image_paths, key=lambda p: os.path.getsize(p) if os.path.exists(p) else 0)
        else:
            return
        
        # 画像を並び替えて再表示
        self.set_images(sorted_paths)
    
    def check_all(self):
        """すべての項目をチェック"""
        for item in self.thumbnail_items.values():
            item.set_checked(True)
    
    def uncheck_all(self):
        """すべての項目のチェックを解除"""
        for item in self.thumbnail_items.values():
            item.set_checked(False)
    
    def get_checked_items(self):
        """チェックされた項目のリストを取得"""
        return [path for path, item in self.thumbnail_items.items() if item.is_checked()]
