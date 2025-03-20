import os
import piexif
from PIL import Image
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
                           QPushButton, QLabel, QHBoxLayout, QHeaderView, QFileDialog,
                           QMessageBox)
from PyQt5.QtCore import Qt
import csv


class ExifDisplay(QWidget):
    """EXIF情報表示ウィジェット"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_exif = None
        self.current_image_path = None
        self.initUI()
    
    def initUI(self):
        """UIを初期化"""
        layout = QVBoxLayout()
        
        # 画像情報ヘッダー
        self.image_info_label = QLabel("画像情報:")
        layout.addWidget(self.image_info_label)
        
        # EXIF情報テーブル
        self.exif_table = QTableWidget(0, 3)
        self.exif_table.setHorizontalHeaderLabels(["EXIF項目", "値", "説明"])
        self.exif_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.exif_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.exif_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.exif_table)
        
        # ボタンエリア
        button_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("EXIF情報をエクスポート...")
        self.export_btn.clicked.connect(self.export_exif)
        button_layout.addWidget(self.export_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_exif(self, image_path):
        """EXIF情報を読み込み"""
        self.current_image_path = image_path
        self.current_exif = None
        
        if not image_path or not os.path.exists(image_path):
            self.clear_exif()
            return
        
        try:
            # 画像情報を取得
            img_stat = os.stat(image_path)
            file_size = img_stat.st_size / 1024  # KB
            modified_time = datetime.fromtimestamp(img_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            # 画像のサイズを取得
            try:
                with Image.open(image_path) as img:
                    width, height = img.size
                    format_name = img.format
            except:
                width, height = 0, 0
                format_name = "Unknown"
            
            # 画像情報ヘッダーを更新
            self.image_info_label.setText(
                f"画像情報: {os.path.basename(image_path)}\n"
                f"サイズ: {width}x{height} ピクセル\n"
                f"ファイルサイズ: {file_size:.1f} KB\n"
                f"ファイル形式: {format_name}\n"
                f"更新日時: {modified_time}"
            )
            
            # EXIF情報を読み込み
            self.current_exif = self.read_exif(image_path)
            
            # テーブルに表示
            self.display_exif()
            
        except Exception as e:
            self.image_info_label.setText(f"画像情報を読み込めませんでした: {str(e)}")
            self.clear_exif()
    
    def read_exif(self, image_path):
        """EXIF情報を読み込み"""
        exif_data = {}
        
        try:
            # JPEG、TIFF形式の場合はpiexifを使用
            if image_path.lower().endswith(('.jpg', '.jpeg', '.tif', '.tiff')):
                try:
                    exif_dict = piexif.load(image_path)
                    
                    # 0th IFD
                    if "0th" in exif_dict:
                        for tag, value in exif_dict["0th"].items():
                            exif_data[f"0th_{tag}"] = self.format_exif_value(tag, value)
                    
                    # Exif IFD
                    if "Exif" in exif_dict:
                        for tag, value in exif_dict["Exif"].items():
                            exif_data[f"Exif_{tag}"] = self.format_exif_value(tag, value)
                    
                    # GPS IFD
                    if "GPS" in exif_dict:
                        for tag, value in exif_dict["GPS"].items():
                            exif_data[f"GPS_{tag}"] = self.format_exif_value(tag, value)
                    
                    # 1st IFD
                    if "1st" in exif_dict:
                        for tag, value in exif_dict["1st"].items():
                            exif_data[f"1st_{tag}"] = self.format_exif_value(tag, value)
                except:
                    pass
            
            # PILを使用して一般的な情報を取得
            try:
                with Image.open(image_path) as img:
                    # 基本情報
                    exif_data["Format"] = img.format
                    exif_data["Mode"] = img.mode
                    exif_data["Width"] = img.width
                    exif_data["Height"] = img.height
                    
                    # EXIF情報がある場合
                    if hasattr(img, '_getexif') and img._getexif():
                        exif = img._getexif()
                        if exif:
                            for tag_id, value in exif.items():
                                tag_name = piexif.TAGS.get(tag_id, {}).get('name', str(tag_id))
                                exif_data[tag_name] = self.format_exif_value(tag_id, value)
            except:
                pass
            
            return exif_data
            
        except Exception as e:
            print(f"EXIF読み込みエラー: {e}")
            return {}
    
    def format_exif_value(self, tag, value):
        """EXIF値を読みやすい形式に変換"""
        # バイナリデータの場合は16進数に変換
        if isinstance(value, bytes):
            try:
                return value.decode('utf-8')
            except:
                return f"Binary data ({len(value)} bytes)"
        
        # リスト/タプルの場合は文字列に結合
        if isinstance(value, (list, tuple)):
            try:
                return ", ".join(str(v) for v in value)
            except:
                return str(value)
        
        # その他の値はそのまま返す
        return str(value)
    
    def display_exif(self):
        """EXIF情報をテーブルに表示"""
        if not self.current_exif:
            self.clear_exif()
            return
        
        # テーブルをクリア
        self.exif_table.setRowCount(0)
        
        # EXIF情報を整理
        exif_items = []
        
        # カメラメーカー/モデル
        if "0th_271" in self.current_exif:
            exif_items.append(("カメラメーカー", self.current_exif["0th_271"], "機器の製造元"))
        if "0th_272" in self.current_exif:
            exif_items.append(("カメラモデル", self.current_exif["0th_272"], "機器のモデル名"))
        
        # 撮影情報
        if "Exif_36867" in self.current_exif:
            exif_items.append(("撮影日時", self.current_exif["Exif_36867"], "画像が撮影された日時"))
        if "Exif_33434" in self.current_exif:
            exif_items.append(("露出時間", self.current_exif["Exif_33434"], "シャッタースピード"))
        if "Exif_33437" in self.current_exif:
            exif_items.append(("F値", self.current_exif["Exif_33437"], "絞り値"))
        if "Exif_34855" in self.current_exif:
            exif_items.append(("ISO感度", self.current_exif["Exif_34855"], "撮影感度"))
        if "Exif_37386" in self.current_exif:
            exif_items.append(("焦点距離", self.current_exif["Exif_37386"], "レンズの焦点距離"))
        
        # GPSデータ
        has_gps = False
        gps_lat = None
        gps_lon = None
        
        if "GPS_1" in self.current_exif and "GPS_2" in self.current_exif and "GPS_3" in self.current_exif and "GPS_4" in self.current_exif:
            lat_ref = self.current_exif["GPS_1"]
            lat = self.current_exif["GPS_2"]
            lon_ref = self.current_exif["GPS_3"]
            lon = self.current_exif["GPS_4"]
            
            exif_items.append(("GPS情報", f"緯度: {lat} {lat_ref}, 経度: {lon} {lon_ref}", "撮影場所の位置情報"))
            has_gps = True
        
        # 基本画像情報
        if "Width" in self.current_exif and "Height" in self.current_exif:
            exif_items.append(("画像サイズ", f"{self.current_exif['Width']}x{self.current_exif['Height']}", "画像の解像度"))
        if "Mode" in self.current_exif:
            exif_items.append(("カラーモード", self.current_exif["Mode"], "画像のカラーモード"))
        
        # その他のEXIF情報
        for key, value in self.current_exif.items():
            # 既に処理した一般的な項目はスキップ
            if key in ["Width", "Height", "Mode", "Format", 
                      "0th_271", "0th_272", "Exif_36867", "Exif_33434", 
                      "Exif_33437", "Exif_34855", "Exif_37386",
                      "GPS_1", "GPS_2", "GPS_3", "GPS_4"]:
                continue
            
            # キーから説明を取得
            description = self.get_exif_description(key)
            
            # テーブルに追加
            exif_items.append((key, value, description))
        
        # テーブルにEXIF情報を追加
        self.exif_table.setRowCount(len(exif_items))
        
        for i, (key, value, description) in enumerate(exif_items):
            # 項目名
            key_item = QTableWidgetItem(key)
            key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
            self.exif_table.setItem(i, 0, key_item)
            
            # 値
            value_item = QTableWidgetItem(str(value))
            value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
            self.exif_table.setItem(i, 1, value_item)
            
            # 説明
            desc_item = QTableWidgetItem(description)
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemIsEditable)
            self.exif_table.setItem(i, 2, desc_item)
        
        # エクスポートボタンを有効化
        self.export_btn.setEnabled(len(exif_items) > 0)
    
    def get_exif_description(self, key):
        """EXIF項目の説明を取得"""
        # 一般的なEXIF項目の説明
        descriptions = {
            "0th_271": "機器の製造元",
            "0th_272": "機器のモデル名",
            "Exif_36867": "撮影日時",
            "Exif_33434": "露出時間（シャッタースピード）",
            "Exif_33437": "F値（絞り値）",
            "Exif_34855": "ISO感度",
            "Exif_37386": "レンズの焦点距離",
            "GPS_1": "緯度の南北指定",
            "GPS_2": "緯度",
            "GPS_3": "経度の東西指定",
            "GPS_4": "経度",
            "Width": "画像の幅",
            "Height": "画像の高さ",
            "Mode": "カラーモード",
            "Format": "画像形式"
        }
        
        # 説明があれば返す、なければ空文字
        return descriptions.get(key, "")
    
    def clear_exif(self):
        """EXIF情報をクリア"""
        self.exif_table.setRowCount(0)
        self.export_btn.setEnabled(False)
    
    def export_exif(self):
        """EXIF情報をエクスポート"""
        if not self.current_exif:
            return
        
        # ファイル名を取得
        base_name = os.path.basename(self.current_image_path) if self.current_image_path else "exif_data"
        default_name = f"{os.path.splitext(base_name)[0]}_exif.csv"
        
        # 保存先を選択
        file_path, _ = QFileDialog.getSaveFileName(
            self, "EXIF情報を保存", default_name, "CSV files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csv_file:
                writer = csv.writer(csv_file)
                
                # ヘッダー行
                writer.writerow(["項目", "値", "説明"])
                
                # EXIF情報
                for i in range(self.exif_table.rowCount()):
                    key = self.exif_table.item(i, 0).text()
                    value = self.exif_table.item(i, 1).text()
                    description = self.exif_table.item(i, 2).text()
                    writer.writerow([key, value, description])
            
            QMessageBox.information(self, "エクスポート完了", f"EXIF情報を {file_path} に保存しました。")
            
        except Exception as e:
            QMessageBox.critical(self, "エクスポートエラー", f"EXIF情報の保存中にエラーが発生しました:\n{e}")
