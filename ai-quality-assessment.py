import os
import cv2
import numpy as np
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QProgressBar, 
                           QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                           QHeaderView, QTabWidget, QScrollArea, QSizePolicy,
                           QGridLayout, QFrame, QCheckBox, QSlider)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QColor


class ImageQualityAssessor:
    """画像品質評価クラス"""
    
    def __init__(self, settings=None):
        """
        初期化関数
        
        Parameters:
        settings (dict): 評価の設定（重みなど）
        """
        self.settings = settings or {}
        
        # デフォルト設定
        self.default_settings = {
            'blur_threshold': 100.0,
            'exposure_weight': 1.0,
            'contrast_weight': 1.0,
            'noise_weight': 1.0,
            'composition_weight': 1.0,
            'sharpness_weight': 1.5,
            'check_blur': True,
            'check_exposure': True,
            'check_contrast': True,
            'check_noise': True,
            'check_composition': True
        }
        
        # 設定を初期化
        for key, value in self.default_settings.items():
            if key not in self.settings:
                self.settings[key] = value
    
    def assess_image(self, image_path):
        """
        画像の品質を評価
        
        Parameters:
        image_path (str): 評価する画像のパス
        
        Returns:
        dict: 評価結果
        """
        try:
            # 画像を読み込み
            img = cv2.imread(str(image_path))
            if img is None:
                return {"error": "画像を読み込めませんでした"}
            
            # 評価結果
            assessment = {}
            
            # シャープネス評価
            if self.settings['check_blur']:
                sharpness_score, sharpness_info = self.assess_sharpness(img)
                assessment['sharpness'] = {
                    'score': sharpness_score,
                    'info': sharpness_info
                }
            
            # 露出評価
            if self.settings['check_exposure']:
                exposure_score, exposure_info = self.assess_exposure(img)
                assessment['exposure'] = {
                    'score': exposure_score,
                    'info': exposure_info
                }
            
            # コントラスト評価
            if self.settings['check_contrast']:
                contrast_score, contrast_info = self.assess_contrast(img)
                assessment['contrast'] = {
                    'score': contrast_score,
                    'info': contrast_info
                }
            
            # ノイズ評価
            if self.settings['check_noise']:
                noise_score, noise_info = self.assess_noise(img)
                assessment['noise'] = {
                    'score': noise_score,
                    'info': noise_info
                }
            
            # 構図評価
            if self.settings['check_composition']:
                composition_score, composition_info = self.assess_composition(img)
                assessment['composition'] = {
                    'score': composition_score,
                    'info': composition_info
                }
            
            # 総合スコア計算
            overall_score = self.calculate_overall_score(assessment)
            
            # ファイル情報を追加
            file_info = {
                'filename': os.path.basename(image_path),
                'size': os.path.getsize(image_path) / 1024,  # KB
                'dimensions': f"{img.shape[1]}x{img.shape[0]}"
            }
            
            # 結果を返す
            return {
                'file_info': file_info,
                'assessment': assessment,
                'overall_score': overall_score
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def assess_sharpness(self, img):
        """
        シャープネス（ブレのなさ）を評価
        
        Parameters:
        img (numpy.ndarray): OpenCV形式の画像
        
        Returns:
        tuple: (スコア, 情報)
        """
        # グレースケールに変換
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # ラプラシアン変換を適用
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        
        # 分散を計算
        variance = laplacian.var()
        
        # スコアを計算（分散が大きいほどシャープ）
        # 値を0-10のスケールに変換
        threshold = self.settings['blur_threshold']
        score = min(10, variance / threshold * 10)
        
        # 結果の情報
        info = {
            'variance': variance,
            'threshold': threshold,
            'is_blurry': variance < threshold
        }
        
        return score, info
    
    def assess_exposure(self, img):
        """
        露出を評価
        
        Parameters:
        img (numpy.ndarray): OpenCV形式の画像
        
        Returns:
        tuple: (スコア, 情報)
        """
        # 輝度ヒストグラムを計算
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        
        # 正規化
        hist = hist.flatten() / hist.sum()
        
        # 平均輝度
        mean_brightness = np.mean(gray)
        
        # 露出不足/過剰のチェック
        underexposed = np.sum(hist[:50]) > 0.5  # 暗い部分の比率が高い
        overexposed = np.sum(hist[205:]) > 0.5  # 明るい部分の比率が高い
        
        # スコア計算
        # 理想的な輝度は中央値（128）に近いほど良い
        score = 10 - abs(mean_brightness - 128) / 128 * 10
        score = max(0, min(10, score))
        
        # 結果の情報
        info = {
            'mean_brightness': mean_brightness,
            'underexposed': underexposed,
            'overexposed': overexposed
        }
        
        return score, info
    
    def assess_contrast(self, img):
        """
        コントラストを評価
        
        Parameters:
        img (numpy.ndarray): OpenCV形式の画像
        
        Returns:
        tuple: (スコア, 情報)
        """
        # グレースケールに変換
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # ヒストグラムを計算
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / hist.sum()
        
        # ヒストグラムの標準偏差を計算
        std_dev = np.sqrt(np.sum(((np.arange(256) - np.sum(np.arange(256) * hist)) ** 2) * hist))
        
        # コントラストスコアを計算（標準偏差が大きいほどコントラストが高い）
        # 理想的な標準偏差は60-80程度
        if std_dev < 30:
            score = std_dev / 30 * 5  # 低コントラスト
        elif std_dev > 80:
            score = 10 - (std_dev - 80) / 50  # 高コントラスト（減点）
        else:
            score = 5 + (std_dev - 30) / 50 * 5  # 理想的な範囲
        
        score = max(0, min(10, score))
        
        # 結果の情報
        info = {
            'std_dev': std_dev,
            'low_contrast': std_dev < 30,
            'high_contrast': std_dev > 80
        }
        
        return score, info
    
    def assess_noise(self, img):
        """
        ノイズレベルを評価
        
        Parameters:
        img (numpy.ndarray): OpenCV形式の画像
        
        Returns:
        tuple: (スコア, 情報)
        """
        # 画像をグレースケールに変換
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # ブラーフィルタを適用した画像
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 元の画像との差分を計算（ノイズ + エッジ）
        noise_plus_edges = cv2.absdiff(gray, blurred)
        
        # エッジ検出
        edges = cv2.Canny(blurred, 50, 150)
        
        # エッジ部分を除外
        kernel = np.ones((3, 3), np.uint8)
        dilated_edges = cv2.dilate(edges, kernel, iterations=1)
        mask = 255 - dilated_edges
        
        # マスクを適用してエッジを除外したノイズ画像
        masked_noise = cv2.bitwise_and(noise_plus_edges, noise_plus_edges, mask=mask)
        
        # ノイズレベルを計算
        noise_level = np.mean(masked_noise)
        
        # スコアを計算（ノイズが少ないほど高スコア）
        score = 10 - noise_level / 10
        score = max(0, min(10, score))
        
        # 結果の情報
        info = {
            'noise_level': noise_level,
            'is_noisy': noise_level > 5
        }
        
        return score, info
    
    def assess_composition(self, img):
        """
        構図を評価
        
        Parameters:
        img (numpy.ndarray): OpenCV形式の画像
        
        Returns:
        tuple: (スコア, 情報)
        """
        # グレースケールに変換
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 画像の幅と高さ
        height, width = gray.shape
        
        # エッジ検出
        edges = cv2.Canny(gray, 50, 150)
        
        # 三分割法のライン
        h1, h2 = height // 3, height * 2 // 3
        w1, w2 = width // 3, width * 2 // 3
        
        # 各領域のエッジピクセルをカウント
        regions = [
            edges[0:h1, 0:w1],          # 左上
            edges[0:h1, w1:w2],         # 上中央
            edges[0:h1, w2:width],      # 右上
            edges[h1:h2, 0:w1],         # 左中央
            edges[h1:h2, w1:w2],        # 中央
            edges[h1:h2, w2:width],     # 右中央
            edges[h2:height, 0:w1],     # 左下
            edges[h2:height, w1:w2],    # 下中央
            edges[h2:height, w2:width]  # 右下
        ]
        
        region_counts = [np.count_nonzero(region) for region in regions]
        total_edges = sum(region_counts)
        
        if total_edges == 0:
            # エッジが検出されない場合（単色画像など）
            return 5.0, {'rule_of_thirds': 0, 'balanced': False}
        
        # 三分割法のポイント（交点）におけるエッジの集中度
        intersection_regions = [
            edges[h1-10:h1+10, w1-10:w1+10],    # 左上の交点
            edges[h1-10:h1+10, w2-10:w2+10],    # 右上の交点
            edges[h2-10:h2+10, w1-10:w1+10],    # 左下の交点
            edges[h2-10:h2+10, w2-10:w2+10]     # 右下の交点
        ]
        
        intersection_counts = [np.count_nonzero(region) for region in intersection_regions]
        intersection_total = sum(intersection_counts)
        
        # 三分割法のスコア計算
        rule_of_thirds = intersection_total / total_edges * 100
        
        # バランスチェック - 左右と上下のバランス
        left = region_counts[0] + region_counts[3] + region_counts[6]
        right = region_counts[2] + region_counts[5] + region_counts[8]
        top = region_counts[0] + region_counts[1] + region_counts[2]
        bottom = region_counts[6] + region_counts[7] + region_counts[8]
        
        balance_lr = 1 - abs(left - right) / total_edges
        balance_tb = 1 - abs(top - bottom) / total_edges
        balance = (balance_lr + balance_tb) / 2
        
        # スコア計算
        # 三分割法と全体のバランスを考慮
        score = (rule_of_thirds * 0.6 + balance * 100 * 0.4) / 10
        score = max(0, min(10, score))
        
        # 結果の情報
        info = {
            'rule_of_thirds': rule_of_thirds,
            'balance': balance * 100,
            'balanced': balance > 0.7
        }
        
        return score, info
    
    def calculate_overall_score(self, assessment):
        """
        総合スコアを計算
        
        Parameters:
        assessment (dict): 各評価項目の結果
        
        Returns:
        float: 総合スコア（0-10）
        """
        total_score = 0
        total_weight = 0
        
        # 各評価項目のスコアを重み付けして合計
        if 'sharpness' in assessment:
            total_score += assessment['sharpness']['score'] * self.settings['sharpness_weight']
            total_weight += self.settings['sharpness_weight']
        
        if 'exposure' in assessment:
            total_score += assessment['exposure']['score'] * self.settings['exposure_weight']
            total_weight += self.settings['exposure_weight']
        
        if 'contrast' in assessment:
            total_score += assessment['contrast']['score'] * self.settings['contrast_weight']
            total_weight += self.settings['contrast_weight']
        
        if 'noise' in assessment:
            total_score += assessment['noise']['score'] * self.settings['noise_weight']
            total_weight += self.settings['noise_weight']
        
        if 'composition' in assessment:
            total_score += assessment['composition']['score'] * self.settings['composition_weight']
            total_weight += self.settings['composition_weight']
        
        # 合計スコアを計算
        if total_weight > 0:
            overall_score = total_score / total_weight
        else:
            overall_score = 0
        
        return overall_score


class AssessmentThread(QThread):
    """画質評価用スレッド"""
    
    progress_signal = pyqtSignal(int, int)  # 進捗状況更新
    result_signal = pyqtSignal(str, dict)  # 評価結果
    completed_signal = pyqtSignal(dict)  # 全評価完了
    
    def __init__(self, image_paths, settings=None):
        super().__init__()
        self.image_paths = image_paths
        self.settings = settings or {}
        self.canceled = False
        self.results = {}
    
    def run(self):
        """スレッド実行"""
        assessor = ImageQualityAssessor(self.settings)
        total = len(self.image_paths)
        
        for i, img_path in enumerate(self.image_paths):
            if self.canceled:
                break
            
            try:
                # 進捗状況を更新
                self.progress_signal.emit(i + 1, total)
                
                # 画像を評価
                result = assessor.assess_image(img_path)
                
                # 結果を保存
                self.results[img_path] = result
                
                # 結果シグナルを発行
                self.result_signal.emit(img_path, result)
                
            except Exception as e:
                self.results[img_path] = {"error": str(e)}
        
        # 全評価完了シグナルを発行
        self.completed_signal.emit(self.results)
    
    def cancel(self):
        """評価をキャンセル"""
        self.canceled = True


class AIQualityAssessmentWidget(QWidget):
    """AI画質評価ウィジェット"""
    
    assessment_complete = pyqtSignal(dict)  # 評価完了シグナル
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = {
            'exposure_weight': 1.0,
            'contrast_weight': 1.0,
            'noise_weight': 1.0,
            'composition_weight': 1.0,
            'sharpness_weight': 1.5,
            'check_blur': True,
            'check_exposure': True,
            'check_contrast': True,
            'check_noise': True,
            'check_composition': True
        }
        self.assessment_thread = None
        self.results = {}
        self.current_image = None
        self.initUI()
    
    def initUI(self):
        """UIを初期化"""
        layout = QVBoxLayout()
        
        # 評価設定エリア
        settings_frame = QFrame()
        settings_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        settings_layout = QHBoxLayout(settings_frame)
        
        # 評価項目チェックボックス
        check_layout = QVBoxLayout()
        check_layout.addWidget(QLabel("評価項目:"))
        
        self.check_blur = QCheckBox("シャープネス")
        self.check_blur.setChecked(self.settings['check_blur'])
        self.check_blur.toggled.connect(lambda state: self.update_setting('check_blur', state))
        check_layout.addWidget(self.check_blur)
        
        self.check_exposure = QCheckBox("露出")
        self.check_exposure.setChecked(self.settings['check_exposure'])
        self.check_exposure.toggled.connect(lambda state: self.update_setting('check_exposure', state))
        check_layout.addWidget(self.check_exposure)
        
        self.check_contrast = QCheckBox("コントラスト")
        self.check_contrast.setChecked(self.settings['check_contrast'])
        self.check_contrast.toggled.connect(lambda state: self.update_setting('check_contrast', state))
        check_layout.addWidget(self.check_contrast)
        
        self.check_noise = QCheckBox("ノイズ")
        self.check_noise.setChecked(self.settings['check_noise'])
        self.check_noise.toggled.connect(lambda state: self.update_setting('check_noise', state))
        check_layout.addWidget(self.check_noise)
        
        self.check_composition = QCheckBox("構図")
        self.check_composition.setChecked(self.settings['check_composition'])
        self.check_composition.toggled.connect(lambda state: self.update_setting('check_composition', state))
        check_layout.addWidget(self.check_composition)
        
        settings_layout.addLayout(check_layout)
        
        # 重みスライダー
        weights_layout = QGridLayout()
        weights_layout.addWidget(QLabel("重み設定:"), 0, 0, 1, 2)
        
        weights_layout.addWidget(QLabel("シャープネス:"), 1, 0)
        self.sharpness_slider = QSlider(Qt.Horizontal)
        self.sharpness_slider.setRange(5, 30)
        self.sharpness_slider.setValue(int(self.settings['sharpness_weight'] * 10))
        self.sharpness_slider.valueChanged.connect(
            lambda value: self.update_setting('sharpness_weight', value / 10)
        )
        weights_layout.addWidget(self.sharpness_slider, 1, 1)
        
        weights_layout.addWidget(QLabel("露出:"), 2, 0)
        self.exposure_slider = QSlider(Qt.Horizontal)
        self.exposure_slider.setRange(5, 30)
        self.exposure_slider.setValue(int(self.settings['exposure_weight'] * 10))
        self.exposure_slider.valueChanged.connect(
            lambda value: self.update_setting('exposure_weight', value / 10)
        )
        weights_layout.addWidget(self.exposure_slider, 2, 1)
        
        weights_layout.addWidget(QLabel("コントラスト:"), 3, 0)
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(5, 30)
        self.contrast_slider.setValue(int(self.settings['contrast_weight'] * 10))
        self.contrast_slider.valueChanged.connect(
            lambda value: self.update_setting('contrast_weight', value / 10)
        )
        weights_layout.addWidget(self.contrast_slider, 3, 1)
        
        weights_layout.addWidget(QLabel("ノイズ:"), 4, 0)
        self.noise_slider = QSlider(Qt.Horizontal)
        self.noise_slider.setRange(5, 30)
        self.noise_slider.setValue(int(self.settings['noise_weight'] * 10))
        self.noise_slider.valueChanged.connect(
            lambda value: self.update_setting('noise_weight', value / 10)
        )
        weights_layout.addWidget(self.noise_slider, 4, 1)
        
        weights_layout.addWidget(QLabel("構図:"), 5, 0)
        self.composition_slider = QSlider(Qt.Horizontal)
        self.composition_slider.setRange(5, 30)
        self.composition_slider.setValue(int(self.settings['composition_weight'] * 10))
        self.composition_slider.valueChanged.connect(
            lambda value: self.update_setting('composition_weight', value / 10)
        )
        weights_layout.addWidget(self.composition_slider, 5, 1)
        
        settings_layout.addLayout(weights_layout)
        
        # 評価開始ボタン
        self.assess_btn = QPushButton("評価開始")
        self.assess_btn.clicked.connect(self.assess_current_image)
        settings_layout.addWidget(self.assess_btn)
        
        layout.addWidget(settings_frame)
        
        # プログレスエリア
        progress_layout = QHBoxLayout()
        self.progress_label = QLabel("準備完了")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addLayout(progress_layout)
        
        # 評価結果表示エリア
        self.results_tabs = QTabWidget()
        
        # 概要タブ
        self.summary_tab = QWidget()
        summary_layout = QVBoxLayout(self.summary_tab)
        
        # 評価結果サマリーテーブル
        self.summary_table = QTableWidget(0, 3)
        self.summary_table.setHorizontalHeaderLabels(["画像", "総合スコア", "コメント"])
        self.summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.summary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.summary_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        summary_layout.addWidget(self.summary_table)
        
        self.results_tabs.addTab(self.summary_tab, "概要")
        
        # 詳細タブ
        self.details_tab = QWidget()
        details_layout = QVBoxLayout(self.details_tab)
        
        # 現在の画像情報
        self.image_info_label = QLabel("画像が選択されていません")
        details_layout.addWidget(self.image_info_label)
        
        # 評価スコア表示
        self.scores_table = QTableWidget(0, 3)
        self.scores_table.setHorizontalHeaderLabels(["評価項目", "スコア", "詳細"])
        self.scores_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.scores_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.scores_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        details_layout.addWidget(self.scores_table)
        
        self.results_tabs.addTab(self.details_tab, "詳細")
        
        layout.addWidget(self.results_tabs)
        
        self.setLayout(layout)
    
    def update_setting(self, key, value):
        """設定を更新"""
        self.settings[key] = value
    
    def start_assessment(self, image_paths):
        """画質評価を開始"""
        if not image_paths:
            return
        
        # UI状態を更新
        self.progress_bar.setValue(0)
        self.progress_label.setText("評価を開始します...")
        self.assess_btn.setEnabled(False)
        
        # サマリーテーブルをクリア
        self.summary_table.setRowCount(0)
        
        # 評価スレッドを作成して開始
        self.assessment_thread = AssessmentThread(image_paths, self.settings)
        self.assessment_thread.progress_signal.connect(self.update_progress)
        self.assessment_thread.result_signal.connect(self.on_result_received)
        self.assessment_thread.completed_signal.connect(self.on_assessment_completed)
        self.assessment_thread.start()
    
    def assess_current_image(self):
        """現在の画像を評価"""
        if self.current_image:
            self.start_assessment([self.current_image])
    
    def update_progress(self, current, total):
        """進捗状況を更新"""
        self.progress_bar.setValue(int(current / total * 100))
        self.progress_label.setText(f"評価中... ({current}/{total})")
    
    def on_result_received(self, image_path, result):
        """評価結果を受信"""
        # 結果を保存
        self.results[image_path] = result
        
        # サマリーテーブルに結果を追加
        row = self.summary_table.rowCount()
        self.summary_table.insertRow(row)
        
        # 画像名
        file_name = os.path.basename(image_path)
        name_item = QTableWidgetItem(file_name)
        name_item.setData(Qt.UserRole, image_path)  # 画像パスをデータとして保存
        self.summary_table.setItem(row, 0, name_item)
        
        # スコア
        if "error" in result:
            score_item = QTableWidgetItem("エラー")
            self.summary_table.setItem(row, 1, score_item)
            self.summary_table.setItem(row, 2, QTableWidgetItem(result["error"]))
        else:
            score = result.get("overall_score", 0)
            score_item = QTableWidgetItem(f"{score:.1f}")
            
            # スコアに応じて色を設定
            if score < 4.0:
                score_item.setBackground(QColor(255, 150, 150))  # 赤（低評価）
            elif score < 6.0:
                score_item.setBackground(QColor(255, 255, 150))  # 黄（中評価）
            else:
                score_item.setBackground(QColor(150, 255, 150))  # 緑（高評価）
            
            self.summary_table.setItem(row, 1, score_item)
            
            # コメント
            comment = self.generate_comment(result)
            self.summary_table.setItem(row, 2, QTableWidgetItem(comment))
        
        # 現在の画像と一致する場合は詳細を表示
        if image_path == self.current_image:
            self.display_result(image_path)
    
    def on_assessment_completed(self, results):
        """評価完了時の処理"""
        self.progress_label.setText("評価完了")
        self.progress_bar.setValue(100)
        self.assess_btn.setEnabled(True)
        
        # 結果をソート（スコア順）
        sorted_results = []
        for img_path, result in results.items():
            if "error" not in result:
                sorted_results.append((img_path, result.get("overall_score", 0)))
        
        sorted_results.sort(key=lambda x: x[1], reverse=True)
        
        # 結果をサマリーテーブルに反映
        self.summary_table.sortByColumn(1, Qt.DescendingOrder)
        
        # 完了シグナルを発行
        self.assessment_complete.emit(results)
    
    def generate_comment(self, result):
        """評価結果に基づいてコメントを生成"""
        if "error" in result:
            return "エラー: " + result["error"]
        
        score = result.get("overall_score", 0)
        assessment = result.get("assessment", {})
        comments = []
        
        # 全体的な評価
        if score < 4.0:
            comments.append("低品質")
        elif score < 6.0:
            comments.append("普通")
        else:
            comments.append("高品質")
        
        # 個別の項目で問題があればコメント
        if "sharpness" in assessment and assessment["sharpness"]["score"] < 5.0:
            if assessment["sharpness"]["info"].get("is_blurry", False):
                comments.append("ブレている")
        
        if "exposure" in assessment:
            if assessment["exposure"]["info"].get("underexposed", False):
                comments.append("露出不足")
            elif assessment["exposure"]["info"].get("overexposed", False):
                comments.append("露出過剰")
        
        if "contrast" in assessment:
            if assessment["contrast"]["info"].get("low_contrast", False):
                comments.append("コントラスト不足")
            elif assessment["contrast"]["info"].get("high_contrast", False):
                comments.append("コントラスト過剰")
        
        if "noise" in assessment and assessment["noise"]["info"].get("is_noisy", False):
            comments.append("ノイズが多い")
        
        if "composition" in assessment and not assessment["composition"]["info"].get("balanced", True):
            comments.append("構図に問題あり")
        
        return ", ".join(comments)
    
    def display_result(self, image_path):
        """評価結果を表示"""
        if image_path not in self.results:
            return
        
        result = self.results[image_path]
        
        # 現在の画像を設定
        self.current_image = image_path
        
        # 画像情報を更新
        file_info = result.get("file_info", {})
        file_name = file_info.get("filename", os.path.basename(image_path))
        dimensions = file_info.get("dimensions", "不明")
        size_kb = file_info.get("size", 0)
        
        info_text = f"ファイル: {file_name}\n"
        info_text += f"サイズ: {dimensions}, {size_kb:.1f} KB\n"
        
        if "overall_score" in result:
            info_text += f"総合スコア: {result['overall_score']:.1f}/10.0"
        
        self.image_info_label.setText(info_text)
        
        # スコアテーブルをクリア
        self.scores_table.setRowCount(0)
        
        # エラーがある場合
        if "error" in result:
            row = self.scores_table.rowCount()
            self.scores_table.insertRow(row)
            self.scores_table.setItem(row, 0, QTableWidgetItem("エラー"))
            self.scores_table.setItem(row, 1, QTableWidgetItem("--"))
            self.scores_table.setItem(row, 2, QTableWidgetItem(result["error"]))
            return
        
        # 評価結果を表示
        assessment = result.get("assessment", {})
        
        # シャープネス
        if "sharpness" in assessment:
            row = self.scores_table.rowCount()
            self.scores_table.insertRow(row)
            
            score = assessment["sharpness"]["score"]
            info = assessment["sharpness"]["info"]
            
            score_item = QTableWidgetItem(f"{score:.1f}")
            if score < 5.0:
                score_item.setBackground(QColor(255, 150, 150))
            elif score < 7.0:
                score_item.setBackground(QColor(255, 255, 150))
            else:
                score_item.setBackground(QColor(150, 255, 150))
            
            detail = f"分散値: {info.get('variance', 0):.1f}, "
            detail += "ブレている" if info.get('is_blurry', False) else "シャープ"
            
            self.scores_table.setItem(row, 0, QTableWidgetItem("シャープネス"))
            self.scores_table.setItem(row, 1, score_item)
            self.scores_table.setItem(row, 2, QTableWidgetItem(detail))
        
        # 露出
        if "exposure" in assessment:
            row = self.scores_table.rowCount()
            self.scores_table.insertRow(row)
            
            score = assessment["exposure"]["score"]
            info = assessment["exposure"]["info"]
            
            score_item = QTableWidgetItem(f"{score:.1f}")
            if score < 5.0:
                score_item.setBackground(QColor(255, 150, 150))
            elif score < 7.0:
                score_item.setBackground(QColor(255, 255, 150))
            else:
                score_item.setBackground(QColor(150, 255, 150))
            
            detail = f"平均輝度: {info.get('mean_brightness', 0):.1f}, "
            if info.get('underexposed', False):
                detail += "露出不足"
            elif info.get('overexposed', False):
                detail += "露出過剰"
            else:
                detail += "適正露出"
            
            self.scores_table.setItem(row, 0, QTableWidgetItem("露出"))
            self.scores_table.setItem(row, 1, score_item)
            self.scores_table.setItem(row, 2, QTableWidgetItem(detail))
        
        # コントラスト
        if "contrast" in assessment:
            row = self.scores_table.rowCount()
            self.scores_table.insertRow(row)
            
            score = assessment["contrast"]["score"]
            info = assessment["contrast"]["info"]
            
            score_item = QTableWidgetItem(f"{score:.1f}")
            if score < 5.0:
                score_item.setBackground(QColor(255, 150, 150))
            elif score < 7.0:
                score_item.setBackground(QColor(255, 255, 150))
            else:
                score_item.setBackground(QColor(150, 255, 150))
            
            detail = f"標準偏差: {info.get('std_dev', 0):.1f}, "
            if info.get('low_contrast', False):
                detail += "コントラスト不足"
            elif info.get('high_contrast', False):
                detail += "コントラスト過剰"
            else:
                detail += "適正コントラスト"
            
            self.scores_table.setItem(row, 0, QTableWidgetItem("コントラスト"))
            self.scores_table.setItem(row, 1, score_item)
            self.scores_table.setItem(row, 2, QTableWidgetItem(detail))
        
        # ノイズ
        if "noise" in assessment:
            row = self.scores_table.rowCount()
            self.scores_table.insertRow(row)
            
            score = assessment["noise"]["score"]
            info = assessment["noise"]["info"]
            
            score_item = QTableWidgetItem(f"{score:.1f}")
            if score < 5.0:
                score_item.setBackground(QColor(255, 150, 150))
            elif score < 7.0:
                score_item.setBackground(QColor(255, 255, 150))
            else:
                score_item.setBackground(QColor(150, 255, 150))
            
            detail = f"ノイズレベル: {info.get('noise_level', 0):.1f}, "
            detail += "ノイズが多い" if info.get('is_noisy', False) else "ノイズ少"
            
            self.scores_table.setItem(row, 0, QTableWidgetItem("ノイズ"))
            self.scores_table.setItem(row, 1, score_item)
            self.scores_table.setItem(row, 2, QTableWidgetItem(detail))
        
        # 構図
        if "composition" in assessment:
            row = self.scores_table.rowCount()
            self.scores_table.insertRow(row)
            
            score = assessment["composition"]["score"]
            info = assessment["composition"]["info"]
            
            score_item = QTableWidgetItem(f"{score:.1f}")
            if score < 5.0:
                score_item.setBackground(QColor(255, 150, 150))
            elif score < 7.0:
                score_item.setBackground(QColor(255, 255, 150))
            else:
                score_item.setBackground(QColor(150, 255, 150))
            
            detail = f"三分割法スコア: {info.get('rule_of_thirds', 0):.1f}, "
            detail += f"バランス: {info.get('balance', 0):.1f}%, "
            detail += "バランスが良い" if info.get('balanced', False) else "バランスが悪い"
            
            self.scores_table.setItem(row, 0, QTableWidgetItem("構図"))
            self.scores_table.setItem(row, 1, score_item)
            self.scores_table.setItem(row, 2, QTableWidgetItem(detail))
    
    def get_results(self):
        """評価結果を取得"""
        return self.results
