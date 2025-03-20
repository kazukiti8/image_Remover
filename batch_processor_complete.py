import os
import sys
import time
import threading
from pathlib import Path
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                           QProgressBar, QListWidget, QListWidgetItem, QFileDialog,
                           QCheckBox, QGroupBox, QGridLayout, QDialog, QTableWidget,
                           QTableWidgetItem, QHeaderView, QMessageBox, QSplitter,
                           QApplication, QStatusBar, QComboBox, QSpinBox, QDoubleSpinBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QIcon, QFont


class BatchProcessor:
    """バッチ処理の基底クラス"""
    def __init__(self, directories=None):
        self.directories = directories or []
        self.results = {}
        self.canceled = False
        
    def set_directories(self, directories):
        """処理対象のディレクトリを設定"""
        self.directories = directories
        
    def add_directory(self, directory):
        """処理対象のディレクトリを追加"""
        if directory not in self.directories:
            self.directories.append(directory)
            
    def clear_directories(self):
        """ディレクトリリストをクリア"""
        self.directories = []
        
    def get_results(self):
        """処理結果を取得"""
        return self.results
    
    def process_directories(self, progress_callback=None):
        """全てのディレクトリを処理"""
        if not self.directories:
            return {}
            
        self.results = {}
        self.canceled = False
        
        total_dirs = len(self.directories)
        for i, directory in enumerate(self.directories):
            if self.canceled:
                break
                
            # 進捗コールバックがあれば呼び出す
            if progress_callback:
                progress_callback(i, total_dirs, directory)
                
            # ディレクトリを処理
            try:
                result = self.process_directory(directory)
                self.results[directory] = result
            except Exception as e:
                self.results[directory] = {"error": str(e)}
        
        return self.results
    
    def process_directory(self, directory):
        """ディレクトリを処理（サブクラスでオーバーライド）"""
        raise NotImplementedError("サブクラスで実装する必要があります")
    
    def cancel(self):
        """処理をキャンセル"""
        self.canceled = True


class BatchProcessThread(QThread):
    """バッチ処理用のスレッド"""
    directory_started_signal = pyqtSignal(str, int, int)  # ディレクトリ処理開始時 (dir_path, dir_index, total_dirs)
    directory_completed_signal = pyqtSignal(str, dict)    # ディレクトリ処理完了時 (dir_path, results)
    all_completed_signal = pyqtSignal(dict)               # 全処理完了時 (all_results)
    error_signal = pyqtSignal(str, str)                   # エラー発生時 (dir_path, error_message)
    progress_signal = pyqtSignal(int, int)                # 進捗状況更新 (current, total)
    
    def __init__(self, processor_class, directories, settings=None):
        super().__init__()
        self.processor_class = processor_class
        self.directories = directories
        self.settings = settings or {}
        self.canceled = False
        self.all_results = {}
        
    def run(self):
        """スレッド実行"""
        total_dirs = len(self.directories)
        
        for i, directory in enumerate(self.directories):
            if self.canceled:
                break
                
            try:
                # ディレクトリ処理開始を通知
                self.directory_started_signal.emit(directory, i + 1, total_dirs)
                
                # プロセッサインスタンスを作成
                processor = self.processor_class(**self.settings)
                processor.set_directories([directory])
                
                # 処理を実行
                results = self.process_directory(processor, directory)
                
                # 結果を保存
                self.all_results[directory] = results
                
                # ディレクトリ処理完了を通知
                self.directory_completed_signal.emit(directory, results)
                
            except Exception as e:
                self.error_signal.emit(directory, str(e))
        
        # 全処理完了を通知
        self.all_completed_signal.emit(self.all_results)
    
    def process_directory(self, processor, directory):
        """ディレクトリの処理を実行（サブクラスでオーバーライド）"""
        raise NotImplementedError("サブクラスで実装する必要があります")
    
    def cancel(self):
        """処理をキャンセル"""
        self.canceled = True


class CleanupBatchProcessor(BatchProcessor):
    """画像クリーンアップ用バッチ処理クラス"""
    
    def __init__(self, blur_threshold=100.0, similarity_threshold=10, 
                 check_blur=True, check_similar=True, check_duplicate=True,
                 recursive=True, **kwargs):
        super().__init__()
        self.blur_threshold = blur_threshold
        self.similarity_threshold = similarity_threshold
        self.check_blur = check_blur
        self.check_similar = check_similar
        self.check_duplicate = check_duplicate
        self.recursive = recursive
    
    def process_directory(self, directory):
        """ディレクトリ内の画像をクリーンアップ"""
        from image_cleanup_system import ImageCleanupSystem
        
        # クリーンアップシステムを初期化
        cleanup_system = ImageCleanupSystem(
            directory, 
            None, 
            self.similarity_threshold
        )
        
        results = {
            'blurry': [],
            'similar': [],
            'duplicate': []
        }
        
        # ブレ検出
        if self.check_blur:
            blurry_images = cleanup_system.detect_blurry_images(self.blur_threshold)
            results['blurry'] = blurry_images
        
        # 類似画像検出
        if self.check_similar:
            similar_pairs = cleanup_system.detect_similar_images()
            results['similar'] = similar_pairs
        
        # 重複画像検出
        if self.check_duplicate:
            duplicate_pairs = cleanup_system.detect_duplicate_images()
            results['duplicate'] = duplicate_pairs
        
        return results


class CleanupBatchThread(BatchProcessThread):
    """画像クリーンアップ用バッチ処理スレッド"""
    
    def process_directory(self, processor, directory):
        """ディレクトリの処理を実行"""
        # このメソッドでは、ProcessorのProcess_directoryメソッドを呼び出す
        return processor.process_directory(directory)


class QualityAssessmentBatchProcessor(BatchProcessor):
    """画質評価用バッチ処理クラス"""
    
    def __init__(self, blur_threshold=100.0, exposure_weight=1.0, contrast_weight=1.0,
                 noise_weight=1.0, composition_weight=1.0, sharpness_weight=1.5,
                 check_blur=True, check_exposure=True, check_contrast=True,
                 check_noise=True, check_composition=True, recursive=True, **kwargs):
        super().__init__()
        self.settings = {
            'blur_threshold': blur_threshold,
            'exposure_weight': exposure_weight,
            'contrast_weight': contrast_weight,
            'noise_weight': noise_weight,
            'composition_weight': composition_weight,
            'sharpness_weight': sharpness_weight,
            'check_blur': check_blur,
            'check_exposure': check_exposure,
            'check_contrast': check_contrast,
            'check_noise': check_noise,
            'check_composition': check_composition
        }
        self.recursive = recursive
    
    def process_directory(self, directory):
        """ディレクトリ内の画像の品質を評価"""
        from ai_quality_assessment import ImageQualityAssessor
        
        # 画質評価器を初期化
        assessor = ImageQualityAssessor(self.settings)
        
        # 画像ファイルを取得
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
        image_files = []
        
        if self.recursive:
            # 再帰的に全てのサブディレクトリ内の画像を取得
            for ext in image_extensions:
                image_files.extend(list(Path(directory).glob(f"**/*{ext}")))
                image_files.extend(list(Path(directory).glob(f"**/*{ext.upper()}")))
        else:
            # 指定ディレクトリ直下の画像のみ取得
            for ext in image_extensions:
                image_files.extend(list(Path(directory).glob(f"*{ext}")))
                image_files.extend(list(Path(directory).glob(f"*{ext.upper()}")))
        
        # 各画像を評価
        results = {}
        
        for img_path in image_files:
            if self.canceled:
                break
                
            try:
                # 画像を評価
                img_path_str = str(img_path)
                result = assessor.assess_image(img_path_str)
                
                # 結果を保存
                results[img_path_str] = result
                
            except Exception as e:
                print(f"画像評価エラー ({img_path}): {e}")
                results[str(img_path)] = {"error": str(e)}
        
        return results


class QualityAssessmentBatchThread(BatchProcessThread):
    """画質評価用バッチ処理スレッド"""
    assessment_result_signal = pyqtSignal(str, dict)  # 画像評価結果 (image_path, result)
    
    def process_directory(self, processor, directory):
        """ディレクトリの処理を実行"""
        # このメソッドでは、ProcessorのProcess_directoryメソッドを呼び出す
        results = processor.process_directory(directory)
        
        # 個別の評価結果を通知
        for img_path, result in results.items():
            if 'error' not in result:
                self.assessment_result_signal.emit(img_path, result)
            
            # 進捗状況の更新
            self.progress_signal.emit(list(results.keys()).index(img_path) + 1, len(results))
        
        return results


class BatchProcessWidget(QWidget):
    """バッチ処理ウィジェット"""
    
    def __init__(self):
        super().__init__()
        self.directories = []
        self.thread = None
        self.last_results = None
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        # ヘッダー
        self.header_label = QLabel("バッチ処理")
        self.header_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.header_label)
        
        # ディレクトリ選択
        dir_group = QGroupBox("処理対象ディレクトリ")
        dir_layout = QVBoxLayout()
        
        # ディレクトリリスト
        self.dir_list = QListWidget()
        self.dir_list.setSelectionMode(QListWidget.ExtendedSelection)
        dir_layout.addWidget(self.dir_list)
        
        # ディレクトリ操作ボタン
        dir_buttons = QHBoxLayout()
        
        self.add_dir_btn = QPushButton("ディレクトリ追加...")
        self.add_dir_btn.clicked.connect(self.add_directory)
        dir_buttons.addWidget(self.add_dir_btn)
        
        self.remove_dir_btn = QPushButton("選択したディレクトリを削除")
        self.remove_dir_btn.clicked.connect(self.remove_selected_directories)
        dir_buttons.addWidget(self.remove_dir_btn)
        
        self.clear_dirs_btn = QPushButton("すべてクリア")
        self.clear_dirs_btn.clicked.connect(self.clear_directories)
        dir_buttons.addWidget(self.clear_dirs_btn)
        
        dir_layout.addLayout(dir_buttons)
        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)
        
        # 処理タイプ選択
        type_group = QGroupBox("処理タイプ")
        type_layout = QVBoxLayout()
        
        self.cleanup_check = QCheckBox("画像クリーンアップ")
        self.cleanup_check.setChecked(True)
        self.cleanup_check.toggled.connect(self.update_settings_visibility)
        type_layout.addWidget(self.cleanup_check)
        
        self.quality_check = QCheckBox("画質評価")
        self.quality_check.toggled.connect(self.update_settings_visibility)
        type_layout.addWidget(self.quality_check)
        
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # クリーンアップ設定
        self.cleanup_settings_group = QGroupBox("クリーンアップ設定")
        cleanup_settings_layout = QGridLayout()
        
        cleanup_settings_layout.addWidget(QLabel("ブレ検出閾値:"), 0, 0)
        self.blur_threshold_spin = QDoubleSpinBox()
        self.blur_threshold_spin.setRange(10, 500)
        self.blur_threshold_spin.setValue(100.0)
        cleanup_settings_layout.addWidget(self.blur_threshold_spin, 0, 1)
        
        cleanup_settings_layout.addWidget(QLabel("類似画像閾値:"), 1, 0)
        self.similarity_threshold_spin = QSpinBox()
        self.similarity_threshold_spin.setRange(1, 30)
        self.similarity_threshold_spin.setValue(10)
        cleanup_settings_layout.addWidget(self.similarity_threshold_spin, 1, 1)
        
        cleanup_settings_layout.addWidget(QLabel("検出項目:"), 2, 0)
        self.blur_check = QCheckBox("ブレ")
        self.blur_check.setChecked(True)
        cleanup_settings_layout.addWidget(self.blur_check, 2, 1)
        
        self.similar_check = QCheckBox("類似")
        self.similar_check.setChecked(True)
        cleanup_settings_layout.addWidget(self.similar_check, 2, 2)
        
        self.duplicate_check = QCheckBox("重複")
        self.duplicate_check.setChecked(True)
        cleanup_settings_layout.addWidget(self.duplicate_check, 2, 3)
        
        self.cleanup_settings_group.setLayout(cleanup_settings_layout)
        layout.addWidget(self.cleanup_settings_group)
        
        # 画質評価設定
        self.quality_settings_group = QGroupBox("画質評価設定")
        quality_settings_layout = QGridLayout()
        
        quality_settings_layout.addWidget(QLabel("評価項目:"), 0, 0)
        self.quality_blur_check = QCheckBox("シャープネス")
        self.quality_blur_check.setChecked(True)
        quality_settings_layout.addWidget(self.quality_blur_check, 0, 1)
        
        self.quality_exposure_check = QCheckBox("露出")
        self.quality_exposure_check.setChecked(True)
        quality_settings_layout.addWidget(self.quality_exposure_check, 0, 2)
        
        self.quality_contrast_check = QCheckBox("コントラスト")
        self.quality_contrast_check.setChecked(True)
        quality_settings_layout.addWidget(self.quality_contrast_check, 0, 3)
        
        self.quality_noise_check = QCheckBox("ノイズ")
        self.quality_noise_check.setChecked(True)
        quality_settings_layout.addWidget(self.quality_noise_check, 1, 1)
        
        self.quality_composition_check = QCheckBox("構図")
        self.quality_composition_check.setChecked(True)
        quality_settings_layout.addWidget(self.quality_composition_check, 1, 2)
        
        self.quality_settings_group.setLayout(quality_settings_layout)
        layout.addWidget(self.quality_settings_group)
        self.quality_settings_group.hide()  # 初期状態では非表示
        
        # 実行設定
        exec_group = QGroupBox("実行設定")
        exec_layout = QGridLayout()
        
        exec_layout.addWidget(QLabel("サブディレクトリも処理:"), 0, 0)
        self.subdirs_check = QCheckBox()
        self.subdirs_check.setChecked(True)
        exec_layout.addWidget(self.subdirs_check, 0, 1)
        
        exec_layout.addWidget(QLabel("処理完了後に結果を表示:"), 1, 0)
        self.show_results_check = QCheckBox()
        self.show_results_check.setChecked(True)
        exec_layout.addWidget(self.show_results_check, 1, 1)
        
        exec_group.setLayout(exec_layout)
        layout.addWidget(exec_group)
        
        # 進捗表示
        progress_layout = QHBoxLayout()
        self.progress_label = QLabel("準備完了")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addLayout(progress_layout)
        
        # 実行ボタン
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("バッチ処理開始")
        self.start_button.clicked.connect(self.start_batch_process)
        button_layout.addWidget(self.start_button)
        
        self.cancel_button = QPushButton("キャンセル")
        self.cancel_button.clicked.connect(self.cancel_batch_process)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.cancel_button)
        
        self.view_results_button = QPushButton("結果を確認")
        self.view_results_button.clicked.connect(self.view_results)
        self.view_results_button.setEnabled(False)
        button_layout.addWidget(self.view_results_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def update_settings_visibility(self):
        """設定グループの表示/非表示を切り替え"""
        cleanup_checked = self.cleanup_check.isChecked()
        quality_checked = self.quality_check.isChecked()
        
        self.cleanup_settings_group.setVisible(cleanup_checked)
        self.quality_settings_group.setVisible(quality_checked)
    
    def add_directory(self):
        """ディレクトリを追加"""
        dir_path = QFileDialog.getExistingDirectory(self, "処理するディレクトリを選択")
        if dir_path:
            if dir_path not in self.directories:
                self.directories.append(dir_path)
                self.dir_list.addItem(dir_path)
    
    def remove_selected_directories(self):
        """選択したディレクトリを削除"""
        selected_items = self.dir_list.selectedItems()
        for item in selected_items:
            row = self.dir_list.row(item)
            self.dir_list.takeItem(row)
            self.directories.remove(item.text())
    
    def clear_directories(self):
        """全てのディレクトリをクリア"""
        self.dir_list.clear()
        self.directories.clear()
    
    def start_batch_process(self):
        """バッチ処理を開始"""
        if not self.directories:
            QMessageBox.warning(self, "エラー", "処理対象のディレクトリが選択されていません")
            return
            
        if not self.cleanup_check.isChecked() and not self.quality_check.isChecked():
            QMessageBox.warning(self, "エラー", "処理タイプが選択されていません")
            return
        
        # UI状態更新
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.view_results_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("処理を準備中...")
        
        # 処理タイプに応じてスレッドを作成
        if self.cleanup_check.isChecked():
            self.start_cleanup_batch()
        elif self.quality_check.isChecked():
            self.start_quality_batch()
    
    def start_cleanup_batch(self):
        """画像クリーンアップバッチ処理を開始"""
        # 設定を取得
        settings = {
            'blur_threshold': self.blur_threshold_spin.value(),
            'similarity_threshold': self.similarity_threshold_spin.value(),
            'check_blur': self.blur_check.isChecked(),
            'check_similar': self.similar_check.isChecked(),
            'check_duplicate': self.duplicate_check.isChecked(),
            'recursive': self.subdirs_check.isChecked()
        }
        
        # スレッドを作成
        self.thread = CleanupBatchThread(CleanupBatchProcessor, self.directories, settings)
        
        # シグナルを接続
        self.thread.directory_started_signal.connect(self.on_directory_started)
        self.thread.directory_completed_signal.connect(self.on_directory_completed)
        self.thread.all_completed_signal.connect(self.on_batch_completed)
        self.thread.error_signal.connect(self.on_directory_error)
        self.thread.progress_signal.connect(self.on_progress_update)
        
        # スレッドを開始
        self.thread.start()
    
    def start_quality_batch(self):
        """画質評価バッチ処理を開始"""
        # 設定を取得
        settings = {
            'blur_threshold': self.blur_threshold_spin.value(),
            'check_blur': self.quality_blur_check.isChecked(),
            'check_exposure': self.quality_exposure_check.isChecked(),
            'check_contrast': self.quality_contrast_check.isChecked(),
            'check_noise': self.quality_noise_check.isChecked(),
            'check_composition': self.quality_composition_check.isChecked(),
            'recursive': self.subdirs_check.isChecked()
        }
        
        # スレッドを作成
        self.thread = QualityAssessmentBatchThread(QualityAssessmentBatchProcessor, self.directories, settings)
        
        # シグナルを接続
        self.thread.directory_started_signal.connect(self.on_directory_started)
        self.thread.directory_completed_signal.connect(self.on_directory_completed)
        self.thread.all_completed_signal.connect(self.on_batch_completed)
        self.thread.error_signal.connect(self.on_directory_error)
        self.thread.progress_signal.connect(self.on_progress_update)
        
        # 画質評価用の追加シグナル
        if hasattr(self.thread, 'assessment_result_signal'):
            self.thread.assessment_result_signal.connect(self.on_assessment_result)
        
        # スレッドを開始
        self.thread.start()
    
    def cancel_batch_process(self):
        """バッチ処理をキャンセル"""
        if self.thread and self.thread.isRunning():
            self.thread.cancel()
            self.progress_label.setText("キャンセル中...")
    
    def view_results(self):
        """処理結果を表示"""
        if hasattr(self, 'last_results') and self.last_results:
            # 結果表示ダイアログを表示
            dialog = BatchResultDialog(self.last_results, parent=self)
            dialog.exec_()
    
    def on_directory_started(self, directory, current, total):
        """ディレクトリ処理開始時の処理"""
        self.progress_label.setText(f"処理中: {directory} ({current}/{total})")
        self.progress_bar.setValue(int((current - 1) / total * 100))
    
    def on_directory_completed(self, directory, results):
        """ディレクトリ処理完了時の処理"""
        self.progress_label.setText(f"完了: {directory}")
    
    def on_directory_error(self, directory, error):
        """ディレクトリ処理エラー時の処理"""
        self.progress_label.setText(f"エラー: {directory}")
        QMessageBox.warning(self, "処理エラー", f"ディレクトリ '{directory}' の処理中にエラーが発生しました:\n{error}")
    
    def on_progress_update(self, current, total):
        """進捗状況更新時の処理"""
        if total > 0:
            progress = int(current / total * 100)
            self.progress_bar.setValue(progress)
    
    def on_assessment_result(self, image_path, result):
        """画質評価結果受信時の処理"""
        # 必要に応じて実装
        pass
    
    def on_batch_completed(self, all_results):
        """バッチ処理完了時の処理"""
        self.progress_label.setText("バッチ処理完了")
        self.progress_bar.setValue(100)
        
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.view_results_button.setEnabled(True)
        
        # 結果を保存
        self.last_results = all_results
        
        # 成功メッセージを表示
        total_dirs = len(all_results)
        QMessageBox.information(
            self,
            "処理完了",
            f"{total_dirs}個のディレクトリの処理が完了しました。"
        )
        
        # 結果表示が有効な場合は結果を表示
        if self.show_results_check.isChecked():
            self.view_results()


class BatchResultDialog(QDialog):
    """バッチ処理結果表示ダイアログ"""
    
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.results = results
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("バッチ処理結果")
        self.resize(800, 600)
        
        layout = QVBoxLayout()
        
        # ディレクトリ選択
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("ディレクトリ:"))
        
        self.dir_combo = QComboBox()
        for directory in self.results.keys():
            self.dir_combo.addItem(directory)
        self.dir_combo.currentIndexChanged.connect(self.update_result_display)
        dir_layout.addWidget(self.dir_combo)
        
        layout.addLayout(dir_layout)
        
        # 集計情報
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.summary_label)
        
        # 結果表示エリア
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels(["種類", "ファイル", "詳細", "アクション"])
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        
        layout.addWidget(self.result_table)
        
        # ボタンエリア
        button_layout = QHBoxLayout()
        
        self.close_button = QPushButton("閉じる")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        
        self.export_button = QPushButton("結果をエクスポート...")
        self.export_button.clicked.connect(self.export_results)
        button_layout.addWidget(self.export_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # 初期表示
        if self.dir_combo.count() > 0:
            self.update_result_display(0)
    
    def update_result_display(self, index):
        """選択されたディレクトリの結果を表示"""
        if index < 0 or self.dir_combo.count() == 0:
            return
            
        directory = self.dir_combo.itemText(index)
        dir_results = self.results.get(directory, {})
        
        # テーブルをクリア
        self.result_table.setRowCount(0)
        
        # 結果を表示
        if 'blurry' in dir_results or 'similar' in dir_results or 'duplicate' in dir_results:
            self.display_cleanup_results(dir_results)
        else:
            # 画質評価結果の場合
            self.display_quality_results(dir_results)
    
    def display_cleanup_results(self, results):
        """画像クリーンアップ結果を表示"""
        blurry_count = 0
        similar_count = 0
        duplicate_count = 0
        
        # ブレている画像
        if 'blurry' in results:
            for img_path in results['blurry']:
                row = self.result_table.rowCount()
                self.result_table.insertRow(row)
                self.result_table.setItem(row, 0, QTableWidgetItem("ブレ"))
                self.result_table.setItem(row, 1, QTableWidgetItem(str(img_path)))
                self.result_table.setItem(row, 2, QTableWidgetItem("ブレている画像"))
                blurry_count += 1
        
        # 類似画像
        if 'similar' in results:
            for ref_img, similar_img in results['similar']:
                row = self.result_table.rowCount()
                self.result_table.insertRow(row)
                self.result_table.setItem(row, 0, QTableWidgetItem("類似"))
                self.result_table.setItem(row, 1, QTableWidgetItem(str(similar_img)))
                self.result_table.setItem(row, 2, QTableWidgetItem(f"類似画像: {os.path.basename(str(ref_img))}"))
                similar_count += 1
        
        # 重複画像
        if 'duplicate' in results:
            for ref_img, duplicate_img in results['duplicate']:
                row = self.result_table.rowCount()
                self.result_table.insertRow(row)
                self.result_table.setItem(row, 0, QTableWidgetItem("重複"))
                self.result_table.setItem(row, 1, QTableWidgetItem(str(duplicate_img)))
                self.result_table.setItem(row, 2, QTableWidgetItem(f"重複画像: {os.path.basename(str(ref_img))}"))
                duplicate_count += 1
        
        # 集計情報を更新
        total = blurry_count + similar_count + duplicate_count
        self.summary_label.setText(
            f"合計: {total}件の問題が検出されました（ブレ: {blurry_count}, 類似: {similar_count}, 重複: {duplicate_count}）"
        )
    
    def display_quality_results(self, results):
        """画質評価結果を表示"""
        total_images = len(results)
        low_quality_count = 0
        
        for img_path, result in results.items():
            if 'error' in result:
                # エラーがある場合はスキップ
                continue
                
            if 'overall_score' in result:
                overall_score = result['overall_score']
                
                # スコアが低い画像のみ表示
                if overall_score < 6.0:
                    row = self.result_table.rowCount()
                    self.result_table.insertRow(row)
                    
                    # スコアに応じて色を設定
                    score_item = QTableWidgetItem(f"{overall_score:.1f}")
                    if overall_score < 4.0:
                        score_item.setBackground(Qt.red)
                    elif overall_score < 5.0:
                        score_item.setBackground(Qt.yellow)
                    
                    self.result_table.setItem(row, 0, score_item)
                    self.result_table.setItem(row, 1, QTableWidgetItem(str(img_path)))
                    
                    # 詳細情報を生成
                    details = ""
                    if 'assessment' in result:
                        issues = []
                        for aspect, data in result['assessment'].items():
                            if 'score' in data and data['score'] < 5.0:
                                issues.append(f"{aspect}: {data['score']:.1f}")
                        
                        if issues:
                            details = "問題項目: " + ", ".join(issues)
                    
                    self.result_table.setItem(row, 2, QTableWidgetItem(details))
                    low_quality_count += 1
        
        # 集計情報を更新
        self.summary_label.setText(
            f"合計: {total_images}枚の画像を評価、{low_quality_count}枚の低品質画像が検出されました"
        )
    
    def export_results(self):
        """結果をファイルにエクスポート"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "結果を保存", "", "CSV ファイル (*.csv);;テキストファイル (*.txt)"
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # ヘッダー
                f.write("ディレクトリ,種類,ファイル,詳細\n")
                
                # 各ディレクトリの結果を書き出し
                for directory, results in self.results.items():
                    if 'blurry' in results:
                        # クリーンアップ結果
                        
                        # ブレている画像
                        for img_path in results['blurry']:
                            f.write(f'"{directory}","ブレ","{img_path}","ブレている画像"\n')
                        
                        # 類似画像
                        if 'similar' in results:
                            for ref_img, similar_img in results['similar']:
                                f.write(f'"{directory}","類似","{similar_img}","類似画像: {os.path.basename(str(ref_img))}"\n')
                        
                        # 重複画像
                        if 'duplicate' in results:
                            for ref_img, duplicate_img in results['duplicate']:
                                f.write(f'"{directory}","重複","{duplicate_img}","重複画像: {os.path.basename(str(ref_img))}"\n')
                    else:
                        # 画質評価結果
                        for img_path, result in results.items():
                            if 'error' in result:
                                continue
                                
                            if 'overall_score' in result:
                                score = result['overall_score']
                                
                                details = ""
                                if 'assessment' in result:
                                    issues = []
                                    for aspect, data in result['assessment'].items():
                                        if 'score' in data:
                                            issues.append(f"{aspect}: {data['score']:.1f}")
                                    
                                    if issues:
                                        details = ", ".join(issues)
                                
                                f.write(f'"{directory}","{score:.1f}","{img_path}","{details}"\n')
            
            QMessageBox.information(self, "エクスポート完了", f"結果を {file_path} に保存しました。")
            
        except Exception as e:
            QMessageBox.critical(self, "エクスポートエラー", f"結果の保存中にエラーが発生しました:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QWidget()
    layout = QVBoxLayout()
    batch_widget = BatchProcessWidget()
    layout.addWidget(batch_widget)
    window.setLayout(layout)
    window.setWindowTitle("バッチ処理テスト")
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())
