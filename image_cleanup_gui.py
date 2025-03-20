import sys
import os
import cv2
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QProgressBar, QTabWidget, 
                             QSlider, QSpinBox, QDoubleSpinBox, QCheckBox, QListWidget, 
                             QListWidgetItem, QSplitter, QFrame, QScrollArea, QMessageBox,
                             QGridLayout, QGroupBox)
from PyQt5.QtGui import QPixmap, QImage, QCursor
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from pathlib import Path
import numpy as np
import threading
import time

# 既存の画像クリーンアップシステムをインポート
from image_cleanup_system import ImageCleanupSystem

class WorkerThread(QThread):
    """バックグラウンドで画像処理を行うためのスレッド"""
    progress_signal = pyqtSignal(str, int, int)
    result_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    
    def __init__(self, directory, blur_threshold, similarity_threshold):
        super().__init__()
        self.directory = directory
        self.blur_threshold = blur_threshold
        self.similarity_threshold = similarity_threshold
        self.canceled = False
        
    def run(self):
        try:
            # クリーンアップシステムを初期化
            self.cleanup_system = ImageCleanupSystem(
                self.directory, 
                None, 
                self.similarity_threshold
            )
            
            # ブレている画像を検出
            self.progress_signal.emit("ブレ検出中...", 0, 1)
            self.cleanup_system.detect_blurry_images(self.blur_threshold)
            if self.canceled:
                return
            
            # 類似画像を検出
            self.progress_signal.emit("類似画像検出中...", 1, 2)
            self.cleanup_system.detect_similar_images()
            if self.canceled:
                return
            
            # 重複画像を検出
            self.progress_signal.emit("重複画像検出中...", 2, 3)
            self.cleanup_system.detect_duplicate_images()
            if self.canceled:
                return
            
            # 結果を返す
            results = {
                'blurry': self.cleanup_system.blurry_images,
                'similar': self.cleanup_system.similar_images,
                'duplicate': self.cleanup_system.duplicate_images
            }
            self.result_signal.emit(results)
            
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            self.finished_signal.emit()
    
    def cancel(self):
        self.canceled = True


class ImagePreviewWidget(QWidget):
    """画像のプレビューを表示するウィジェット"""
    def __init__(self, title="画像プレビュー"):
        super().__init__()
        self.title = title
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        # タイトル
        self.title_label = QLabel(self.title)
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        # 画像表示エリア
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(300, 300)
        self.image_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        
        # スクロールエリア
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.image_label)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        # ファイル情報
        self.info_label = QLabel()
        layout.addWidget(self.info_label)
        
        self.setLayout(layout)
    
    def set_image(self, image_path):
        if not image_path or not os.path.exists(image_path):
            self.image_label.clear()
            self.info_label.setText("")
            return
            
        try:
            # 画像を読み込み
            img = cv2.imread(str(image_path))
            if img is None:
                self.image_label.setText("画像の読み込みに失敗しました")
                return
                
            # OpenCVの画像をQImageに変換 (BGR -> RGB)
            height, width, channels = img.shape
            bytes_per_line = channels * width
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            q_img = QImage(img_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)
            
            # 表示サイズを計算（アスペクト比を維持）
            pixmap = QPixmap.fromImage(q_img)
            
            # 画像を表示
            self.image_label.setPixmap(pixmap)
            
            # ファイル情報を表示
            file_size = os.path.getsize(image_path) / 1024  # KB
            self.info_label.setText(f"ファイル: {os.path.basename(image_path)}\n"
                                   f"サイズ: {width}x{height}\n"
                                   f"ファイルサイズ: {file_size:.1f} KB")
            
        except Exception as e:
            self.image_label.setText(f"エラー: {str(e)}")


class ImagePairWidget(QWidget):
    """画像ペアを比較表示するウィジェット"""
    def __init__(self, title="画像比較"):
        super().__init__()
        self.title = title
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        # タイトル
        self.title_label = QLabel(self.title)
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        # 画像比較エリア
        compare_layout = QHBoxLayout()
        
        # 左側（元画像）
        self.left_preview = ImagePreviewWidget("基準画像")
        compare_layout.addWidget(self.left_preview)
        
        # 右側（比較対象画像）
        self.right_preview = ImagePreviewWidget("対象画像")
        compare_layout.addWidget(self.right_preview)
        
        layout.addLayout(compare_layout)
        self.setLayout(layout)
    
    def set_image_pair(self, ref_image_path, compare_image_path):
        self.left_preview.set_image(ref_image_path)
        self.right_preview.set_image(compare_image_path)


class MainWindow(QMainWindow):
    """メインウィンドウ"""
    def __init__(self):
        super().__init__()
        self.title = "画像クリーンアップシステム"
        self.directory = None
        self.worker_thread = None
        self.results = None
        self.selected_items = {'blurry': set(), 'similar': set(), 'duplicate': set()}  # 選択された項目を保存
        
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(100, 100, 1200, 800)
        
        # メインレイアウト
        main_layout = QVBoxLayout()
        
        # 上部：ディレクトリ選択と実行ボタン
        top_layout = QHBoxLayout()
        
        self.dir_label = QLabel("ディレクトリ: 未選択")
        top_layout.addWidget(self.dir_label)
        
        self.browse_btn = QPushButton("ディレクトリ選択...")
        self.browse_btn.clicked.connect(self.browse_directory)
        top_layout.addWidget(self.browse_btn)
        
        self.process_btn = QPushButton("検出開始")
        self.process_btn.clicked.connect(self.start_processing)
        self.process_btn.setEnabled(False)
        top_layout.addWidget(self.process_btn)
        
        self.cancel_btn = QPushButton("キャンセル")
        self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False)
        top_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(top_layout)
        
        # 設定エリア
        settings_group = QGroupBox("検出設定")
        settings_layout = QGridLayout()
        
        # ブレ検出設定
        settings_layout.addWidget(QLabel("ブレ検出閾値:"), 0, 0)
        self.blur_slider = QSlider(Qt.Horizontal)
        self.blur_slider.setRange(10, 500)
        self.blur_slider.setValue(100)
        self.blur_slider.valueChanged.connect(self.update_blur_value)
        settings_layout.addWidget(self.blur_slider, 0, 1)
        
        self.blur_spin = QDoubleSpinBox()
        self.blur_spin.setRange(10, 500)
        self.blur_spin.setValue(100)
        self.blur_spin.valueChanged.connect(self.blur_slider.setValue)
        settings_layout.addWidget(self.blur_spin, 0, 2)
        settings_layout.addWidget(QLabel("小さいほど厳格（ブレと判定されやすい）"), 0, 3)
        
        # 類似画像検出設定
        settings_layout.addWidget(QLabel("類似画像閾値:"), 1, 0)
        self.similarity_slider = QSlider(Qt.Horizontal)
        self.similarity_slider.setRange(1, 30)
        self.similarity_slider.setValue(10)
        self.similarity_slider.valueChanged.connect(self.update_similarity_value)
        settings_layout.addWidget(self.similarity_slider, 1, 1)
        
        self.similarity_spin = QSpinBox()
        self.similarity_spin.setRange(1, 30)
        self.similarity_spin.setValue(10)
        self.similarity_spin.valueChanged.connect(self.similarity_slider.setValue)
        settings_layout.addWidget(self.similarity_spin, 1, 2)
        settings_layout.addWidget(QLabel("小さいほど厳格（類似と判定されにくい）"), 1, 3)
        
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)
        
        # プログレスバー
        self.progress_layout = QHBoxLayout()
        self.progress_label = QLabel("待機中")
        self.progress_layout.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_layout.addWidget(self.progress_bar)
        main_layout.addLayout(self.progress_layout)
        
        # タブウィジェット
        self.tabs = QTabWidget()
        self.tabs.setEnabled(False)
        
        # ブレ検出タブ
        self.blurry_tab = QWidget()
        blurry_layout = QHBoxLayout()
        
        # 左側：リスト
        self.blurry_list = QListWidget()
        self.blurry_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.blurry_list.itemSelectionChanged.connect(self.update_blurry_preview)
        blurry_layout.addWidget(self.blurry_list, 1)
        
        # 右側：プレビュー
        self.blurry_preview = ImagePreviewWidget("ブレている画像のプレビュー")
        blurry_layout.addWidget(self.blurry_preview, 2)
        
        self.blurry_tab.setLayout(blurry_layout)
        self.tabs.addTab(self.blurry_tab, "ブレている画像")
        
        # 類似画像タブ
        self.similar_tab = QWidget()
        similar_layout = QHBoxLayout()
        
        # 左側：リスト
        self.similar_list = QListWidget()
        self.similar_list.itemSelectionChanged.connect(self.update_similar_preview)
        similar_layout.addWidget(self.similar_list, 1)
        
        # 右側：プレビュー
        self.similar_preview = ImagePairWidget("類似画像の比較")
        similar_layout.addWidget(self.similar_preview, 2)
        
        self.similar_tab.setLayout(similar_layout)
        self.tabs.addTab(self.similar_tab, "類似画像")
        
        # 重複画像タブ
        self.duplicate_tab = QWidget()
        duplicate_layout = QHBoxLayout()
        
        # 左側：リスト
        self.duplicate_list = QListWidget()
        self.duplicate_list.itemSelectionChanged.connect(self.update_duplicate_preview)
        duplicate_layout.addWidget(self.duplicate_list, 1)
        
        # 右側：プレビュー
        self.duplicate_preview = ImagePairWidget("重複画像の比較")
        duplicate_layout.addWidget(self.duplicate_preview, 2)
        
        self.duplicate_tab.setLayout(duplicate_layout)
        self.tabs.addTab(self.duplicate_tab, "重複画像")
        
        main_layout.addWidget(self.tabs)
        
        # 操作ボタン
        action_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("すべて選択")
        self.select_all_btn.clicked.connect(self.select_all_items)
        action_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("選択解除")
        self.deselect_all_btn.clicked.connect(self.deselect_all_items)
        action_layout.addWidget(self.deselect_all_btn)
        
        self.delete_btn = QPushButton("選択した画像を削除")
        self.delete_btn.setStyleSheet("background-color: #ffaaaa;")
        self.delete_btn.clicked.connect(self.delete_selected)
        action_layout.addWidget(self.delete_btn)
        
        self.move_btn = QPushButton("選択した画像を移動...")
        self.move_btn.clicked.connect(self.move_selected)
        action_layout.addWidget(self.move_btn)
        
        main_layout.addLayout(action_layout)
        
        # メインウィジェットを設定
        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # 初期状態で操作ボタンを無効化
        self.update_action_buttons()
    
    def update_blur_value(self, value):
        self.blur_spin.setValue(value)
    
    def update_similarity_value(self, value):
        self.similarity_spin.setValue(value)
        
    def browse_directory(self):
        """ディレクトリ選択ダイアログを表示"""
        dir_path = QFileDialog.getExistingDirectory(self, "処理するディレクトリを選択")
        if dir_path:
            self.directory = dir_path
            self.dir_label.setText(f"ディレクトリ: {dir_path}")
            self.process_btn.setEnabled(True)
            
    def start_processing(self):
        """画像処理を開始"""
        if not self.directory:
            return
            
        # UI状態を更新
        self.process_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.browse_btn.setEnabled(False)
        self.tabs.setEnabled(False)
        
        # リストをクリア
        self.blurry_list.clear()
        self.similar_list.clear()
        self.duplicate_list.clear()
        self.selected_items = {'blurry': set(), 'similar': set(), 'duplicate': set()}
        
        # プログレスバーをリセット
        self.progress_bar.setValue(0)
        self.progress_label.setText("処理を開始...")
        
        # ワーカースレッドを作成して開始
        self.worker_thread = WorkerThread(
            self.directory,
            self.blur_spin.value(),
            self.similarity_spin.value()
        )
        self.worker_thread.progress_signal.connect(self.update_progress)
        self.worker_thread.result_signal.connect(self.process_results)
        self.worker_thread.finished_signal.connect(self.processing_finished)
        self.worker_thread.error_signal.connect(self.show_error)
        self.worker_thread.start()
        
    def cancel_processing(self):
        """処理をキャンセル"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.cancel()
            self.progress_label.setText("キャンセル中...")
            
    def update_progress(self, message, current, total):
        """進捗状況を更新"""
        self.progress_label.setText(message)
        self.progress_bar.setValue(int((current / total) * 100))
        
    def process_results(self, results):
        """処理結果を表示"""
        self.results = results
        
        # ブレている画像を表示
        for img_path in results['blurry']:
            item = QListWidgetItem(os.path.basename(str(img_path)))
            item.setData(Qt.UserRole, str(img_path))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.blurry_list.addItem(item)
            
        # 類似画像を表示
        for ref_img, similar_img in results['similar']:
            item = QListWidgetItem(f"{os.path.basename(str(similar_img))} ← {os.path.basename(str(ref_img))}")
            item.setData(Qt.UserRole, (str(ref_img), str(similar_img)))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.similar_list.addItem(item)
            
        # 重複画像を表示
        for ref_img, duplicate_img in results['duplicate']:
            item = QListWidgetItem(f"{os.path.basename(str(duplicate_img))} ← {os.path.basename(str(ref_img))}")
            item.setData(Qt.UserRole, (str(ref_img), str(duplicate_img)))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.duplicate_list.addItem(item)
            
        # タブのタイトルを更新
        self.tabs.setTabText(0, f"ブレている画像 ({self.blurry_list.count()})")
        self.tabs.setTabText(1, f"類似画像 ({self.similar_list.count()})")
        self.tabs.setTabText(2, f"重複画像 ({self.duplicate_list.count()})")
        
        # タブを有効化
        self.tabs.setEnabled(True)
        
    def processing_finished(self):
        """処理完了時の処理"""
        self.progress_label.setText("処理完了")
        self.progress_bar.setValue(100)
        
        self.process_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.browse_btn.setEnabled(True)
        
        # 検出された画像の総数を表示
        total_blurry = self.blurry_list.count()
        total_similar = self.similar_list.count()
        total_duplicate = self.duplicate_list.count()
        total = total_blurry + total_similar + total_duplicate
        
        # 結果のメッセージボックスを表示
        if total > 0:
            QMessageBox.information(
                self,
                "検出完了",
                f"合計 {total} 枚の画像が検出されました。\n\n"
                f"ブレている画像: {total_blurry} 枚\n"
                f"類似画像: {total_similar} 枚\n"
                f"重複画像: {total_duplicate} 枚\n\n"
                "各タブで内容を確認して、不要な画像を選択して削除または移動できます。"
            )
        else:
            QMessageBox.information(
                self,
                "検出完了",
                "該当する画像は見つかりませんでした。"
            )
        
    def show_error(self, error_message):
        """エラーメッセージを表示"""
        QMessageBox.critical(self, "エラー", f"処理中にエラーが発生しました：\n{error_message}")
        self.processing_finished()
        
    def update_blurry_preview(self):
        """ブレている画像のプレビュー更新"""
        selected_items = self.blurry_list.selectedItems()
        if len(selected_items) == 1:
            img_path = selected_items[0].data(Qt.UserRole)
            self.blurry_preview.set_image(img_path)
        else:
            self.blurry_preview.set_image(None)
        
        # チェックボックス状態を追跡
        self.selected_items['blurry'] = set()
        for i in range(self.blurry_list.count()):
            item = self.blurry_list.item(i)
            if item.checkState() == Qt.Checked:
                self.selected_items['blurry'].add(item.data(Qt.UserRole))
        
        self.update_action_buttons()
        
    def update_similar_preview(self):
        """類似画像のプレビュー更新"""
        selected_items = self.similar_list.selectedItems()
        if len(selected_items) == 1:
            ref_img, similar_img = selected_items[0].data(Qt.UserRole)
            self.similar_preview.set_image_pair(ref_img, similar_img)
        else:
            self.similar_preview.set_image_pair(None, None)
        
        # チェックボックス状態を追跡
        self.selected_items['similar'] = set()
        for i in range(self.similar_list.count()):
            item = self.similar_list.item(i)
            if item.checkState() == Qt.Checked:
                _, similar_img = item.data(Qt.UserRole)
                self.selected_items['similar'].add(similar_img)
        
        self.update_action_buttons()
        
    def update_duplicate_preview(self):
        """重複画像のプレビュー更新"""
        selected_items = self.duplicate_list.selectedItems()
        if len(selected_items) == 1:
            ref_img, duplicate_img = selected_items[0].data(Qt.UserRole)
            self.duplicate_preview.set_image_pair(ref_img, duplicate_img)
        else:
            self.duplicate_preview.set_image_pair(None, None)
        
        # チェックボックス状態を追跡
        self.selected_items['duplicate'] = set()
        for i in range(self.duplicate_list.count()):
            item = self.duplicate_list.item(i)
            if item.checkState() == Qt.Checked:
                _, duplicate_img = item.data(Qt.UserRole)
                self.selected_items['duplicate'].add(duplicate_img)
        
        self.update_action_buttons()
    
    def select_all_items(self):
        """現在のタブのすべての項目を選択"""
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:  # ブレている画像
            for i in range(self.blurry_list.count()):
                self.blurry_list.item(i).setCheckState(Qt.Checked)
            self.update_blurry_preview()
        elif current_tab == 1:  # 類似画像
            for i in range(self.similar_list.count()):
                self.similar_list.item(i).setCheckState(Qt.Checked)
            self.update_similar_preview()
        elif current_tab == 2:  # 重複画像
            for i in range(self.duplicate_list.count()):
                self.duplicate_list.item(i).setCheckState(Qt.Checked)
            self.update_duplicate_preview()
    
    def deselect_all_items(self):
        """現在のタブのすべての選択を解除"""
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:  # ブレている画像
            for i in range(self.blurry_list.count()):
                self.blurry_list.item(i).setCheckState(Qt.Unchecked)
            self.update_blurry_preview()
        elif current_tab == 1:  # 類似画像
            for i in range(self.similar_list.count()):
                self.similar_list.item(i).setCheckState(Qt.Unchecked)
            self.update_similar_preview()
        elif current_tab == 2:  # 重複画像
            for i in range(self.duplicate_list.count()):
                self.duplicate_list.item(i).setCheckState(Qt.Unchecked)
            self.update_duplicate_preview()
    
    def update_action_buttons(self):
        """操作ボタンの有効/無効を更新"""
        total_selected = (len(self.selected_items['blurry']) + 
                         len(self.selected_items['similar']) + 
                         len(self.selected_items['duplicate']))
        
        # ボタンの有効/無効を設定
        self.delete_btn.setEnabled(total_selected > 0)
        self.move_btn.setEnabled(total_selected > 0)
        
        # ボタンのテキストを更新
        self.delete_btn.setText(f"選択した画像を削除 ({total_selected})")
        self.move_btn.setText(f"選択した画像を移動... ({total_selected})")
    
    def delete_selected(self):
        """選択した画像を削除"""
        total_selected = (len(self.selected_items['blurry']) + 
                         len(self.selected_items['similar']) + 
                         len(self.selected_items['duplicate']))
        
        if total_selected == 0:
            return
            
        # 確認ダイアログ
        reply = QMessageBox.question(
            self,
            "確認",
            f"選択した {total_selected} 枚の画像を削除しますか？\nこの操作は元に戻せません。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # 削除処理
        deleted_count = 0
        failed_count = 0
        
        # ブレている画像を削除
        for img_path in self.selected_items['blurry']:
            try:
                os.remove(img_path)
                deleted_count += 1
            except Exception as e:
                print(f"削除エラー: {e}")
                failed_count += 1
        
        # 類似画像を削除
        for img_path in self.selected_items['similar']:
            try:
                os.remove(img_path)
                deleted_count += 1
            except Exception as e:
                print(f"削除エラー: {e}")
                failed_count += 1
        
        # 重複画像を削除
        for img_path in self.selected_items['duplicate']:
            try:
                os.remove(img_path)
                deleted_count += 1
            except Exception as e:
                print(f"削除エラー: {e}")
                failed_count += 1
        
        # 削除した項目をリストから削除
        self.remove_processed_items()
        
        # 結果を表示
        if failed_count > 0:
            QMessageBox.warning(
                self,
                "処理完了",
                f"{deleted_count} 枚の画像を削除しました。\n{failed_count} 枚の画像は削除できませんでした。"
            )
        else:
            QMessageBox.information(
                self,
                "処理完了",
                f"{deleted_count} 枚の画像を削除しました。"
            )
        
    def move_selected(self):
        """選択した画像を移動"""
        total_selected = (len(self.selected_items['blurry']) + 
                         len(self.selected_items['similar']) + 
                         len(self.selected_items['duplicate']))
        
        if total_selected == 0:
            return
            
        # 移動先ディレクトリを選択
        dest_dir = QFileDialog.getExistingDirectory(self, "移動先ディレクトリを選択")
        if not dest_dir:
            return
            
        # 移動先サブディレクトリを作成
        blurry_dir = os.path.join(dest_dir, "blurry")
        similar_dir = os.path.join(dest_dir, "similar")
        duplicate_dir = os.path.join(dest_dir, "duplicate")
        
        os.makedirs(blurry_dir, exist_ok=True)
        os.makedirs(similar_dir, exist_ok=True)
        os.makedirs(duplicate_dir, exist_ok=True)
        
        # 移動処理
        moved_count = 0
        failed_count = 0
        
        # ブレている画像を移動
        for img_path in self.selected_items['blurry']:
            try:
                filename = os.path.basename(img_path)
                dest_path = os.path.join(blurry_dir, filename)
                # 同名ファイルがある場合はリネーム
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(filename)
                    dest_path = os.path.join(blurry_dir, f"{base}_{int(time.time())}{ext}")
                shutil.move(img_path, dest_path)
                moved_count += 1
            except Exception as e:
                print(f"移動エラー: {e}")
                failed_count += 1
        
        # 類似画像を移動
        for img_path in self.selected_items['similar']:
            try:
                filename = os.path.basename(img_path)
                dest_path = os.path.join(similar_dir, filename)
                # 同名ファイルがある場合はリネーム
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(filename)
                    dest_path = os.path.join(similar_dir, f"{base}_{int(time.time())}{ext}")
                shutil.move(img_path, dest_path)
                moved_count += 1
            except Exception as e:
                print(f"移動エラー: {e}")
                failed_count += 1
        
        # 重複画像を移動
        for img_path in self.selected_items['duplicate']:
            try:
                filename = os.path.basename(img_path)
                dest_path = os.path.join(duplicate_dir, filename)
                # 同名ファイルがある場合はリネーム
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(filename)
                    dest_path = os.path.join(duplicate_dir, f"{base}_{int(time.time())}{ext}")
                shutil.move(img_path, dest_path)
                moved_count += 1
            except Exception as e:
                print(f"移動エラー: {e}")
                failed_count += 1
        
        # 移動した項目をリストから削除
        self.remove_processed_items()
        
        # 結果を表示
        if failed_count > 0:
            QMessageBox.warning(
                self,
                "処理完了",
                f"{moved_count} 枚の画像を移動しました。\n{failed_count} 枚の画像は移動できませんでした。"
            )
        else:
            QMessageBox.information(
                self,
                "処理完了",
                f"{moved_count} 枚の画像を移動しました。"
            )
    
    def remove_processed_items(self):
        """処理済みの項目をリストから削除"""
        # ブレている画像
        for i in range(self.blurry_list.count() - 1, -1, -1):
            item = self.blurry_list.item(i)
            img_path = item.data(Qt.UserRole)
            if img_path in self.selected_items['blurry'] and not os.path.exists(img_path):
                self.blurry_list.takeItem(i)
        
        # 類似画像
        for i in range(self.similar_list.count() - 1, -1, -1):
            item = self.similar_list.item(i)
            ref_img, similar_img = item.data(Qt.UserRole)
            if similar_img in self.selected_items['similar'] and not os.path.exists(similar_img):
                self.similar_list.takeItem(i)
        
        # 重複画像
        for i in range(self.duplicate_list.count() - 1, -1, -1):
            item = self.duplicate_list.item(i)
            ref_img, duplicate_img = item.data(Qt.UserRole)
            if duplicate_img in self.selected_items['duplicate'] and not os.path.exists(duplicate_img):
                self.duplicate_list.takeItem(i)
        
        # 選択項目をクリア
        self.selected_items = {'blurry': set(), 'similar': set(), 'duplicate': set()}
        
        # タブのタイトルを更新
        self.tabs.setTabText(0, f"ブレている画像 ({self.blurry_list.count()})")
        self.tabs.setTabText(1, f"類似画像 ({self.similar_list.count()})")
        self.tabs.setTabText(2, f"重複画像 ({self.duplicate_list.count()})")
        
        # ボタンの状態を更新
        self.update_action_buttons()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()