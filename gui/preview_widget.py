# gui/widgets/preview_widget.py
import os
import cv2
import numpy as np
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QImage, QPixmap, QMouseEvent

# Pillow があればインポート試行 (画像の向き補正用)
try:
    from PIL import Image, ExifTags
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("警告: Pillow がインストールされていません。画像の向きが正しく表示されない可能性があります。")


class PreviewWidget(QWidget):
    """
    左右の画像プレビューエリアを担当するカスタムウィジェット。
    画像表示、クリックによる削除要求シグナル発行などを行う。
    """
    # シグナル定義: プレビュー画像がクリックされたときにパスを通知
    left_preview_clicked = Signal(str)  # 左プレビュー画像のパス
    right_preview_clicked = Signal(str) # 右プレビュー画像のパス

    def __init__(self, parent=None):
        """コンストラクタ"""
        super().__init__(parent)
        self.left_image_path = None  # 現在表示中の左画像のパス
        self.right_image_path = None # 現在表示中の右画像のパス
        self._setup_ui()

    def _setup_ui(self):
        """UI要素の作成と配置"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # マージンなし
        layout.setSpacing(10) # プレビュー間のスペース

        # 左プレビューラベル
        self.left_preview_label = QLabel("左プレビュー\n(画像選択で表示)")
        self.left_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_preview_label.setFrameShape(QFrame.Shape.Box) # 枠線
        self.left_preview_label.setToolTip("クリックで削除 / Aキーで開く")
        # マウスクリックイベントを処理するメソッドを接続
        self.left_preview_label.mousePressEvent = self._on_left_preview_clicked

        # 右プレビューラベル
        self.right_preview_label = QLabel("右プレビュー\n(類似ペア選択で表示)")
        self.right_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_preview_label.setFrameShape(QFrame.Shape.Box)
        self.right_preview_label.setToolTip("クリックで削除 / Sキーで開く")
        self.right_preview_label.mousePressEvent = self._on_right_preview_clicked

        # レイアウトに追加 (伸縮比率を 1:1 に)
        layout.addWidget(self.left_preview_label, 1)
        layout.addWidget(self.right_preview_label, 1)

    def _display_image(self, target_label: QLabel, image_path: str or None, label_name: str):
        """指定されたラベルに画像を表示する内部メソッド"""
        target_label.clear() # 表示内容をクリア
        target_label.setText(f"{label_name}") # デフォルトテキスト設定

        if image_path and os.path.exists(image_path):
            try:
                img = None
                # Pillowが利用可能で、EXIF情報がありそうな拡張子の場合、向きを補正試行
                if PIL_AVAILABLE and image_path.lower().endswith(('.jpg', '.jpeg', '.tiff', '.heic', '.heif')):
                    try:
                        img_pil = Image.open(image_path)
                        # Orientation タグを探す
                        orientation_tag = None
                        for tag, name in ExifTags.TAGS.items():
                            if name == 'Orientation':
                                orientation_tag = tag
                                break

                        if orientation_tag and hasattr(img_pil, '_getexif'):
                            exif = img_pil._getexif()
                            if exif and orientation_tag in exif:
                                orientation = exif[orientation_tag]
                                # 回転・反転処理
                                if orientation == 2: img_pil = img_pil.transpose(Image.FLIP_LEFT_RIGHT)
                                elif orientation == 3: img_pil = img_pil.rotate(180, expand=True)
                                elif orientation == 4: img_pil = img_pil.transpose(Image.FLIP_TOP_BOTTOM)
                                elif orientation == 5: img_pil = img_pil.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                                elif orientation == 6: img_pil = img_pil.rotate(-90, expand=True) # 270度回転
                                elif orientation == 7: img_pil = img_pil.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                                elif orientation == 8: img_pil = img_pil.rotate(90, expand=True)
                        # Pillow イメージを OpenCV 形式 (NumPy 配列 BGR) に変換
                        # RGBA や P (パレット) モードの場合、RGB に変換
                        if img_pil.mode == 'RGBA':
                            img_pil = img_pil.convert('RGB')
                        elif img_pil.mode == 'P':
                             img_pil = img_pil.convert('RGB')
                        elif img_pil.mode == 'LA':
                             img_pil = img_pil.convert('L') # グレースケールに

                        # グレースケールの場合も考慮
                        if img_pil.mode == 'L':
                             img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_GRAY2BGR)
                        else:
                             img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

                    except (AttributeError, KeyError, IndexError, TypeError, ValueError, SyntaxError) as pil_ex:
                        # EXIF 処理中のエラーは無視して通常の imread にフォールバック
                        print(f"情報: PillowでのEXIF処理中にエラー ({os.path.basename(image_path)}): {pil_ex}. 通常のimreadを使用します。")
                        img = cv2.imread(image_path)
                    except Exception as pil_ex_other:
                        # その他のPillowエラー
                        print(f"警告: Pillowでの画像読み込み中に予期せぬエラー ({os.path.basename(image_path)}): {pil_ex_other}")
                        img = cv2.imread(image_path) # フォールバック
                else:
                    # Pillow がないか、対象外の拡張子の場合は通常の imread
                    img = cv2.imread(image_path)

                # OpenCV で読み込んだ画像データを Qt で表示できる形式に変換
                if img is not None:
                    # BGR から RGB に変換
                    if len(img.shape) == 3: # カラー画像
                        rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        h, w, ch = rgb_image.shape
                        bytes_per_line = ch * w
                        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                    elif len(img.shape) == 2: # グレースケール画像
                         h, w = img.shape
                         bytes_per_line = w
                         qt_image = QImage(img.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
                    else:
                         raise ValueError("未対応の画像チャンネル数です。")

                    pixmap = QPixmap.fromImage(qt_image)
                    # ラベルサイズに合わせてアスペクト比を維持してスケーリング
                    scaled_pixmap = pixmap.scaled(target_label.size(),
                                                  Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation)
                    target_label.setPixmap(scaled_pixmap) # ラベルに設定
                else:
                    # imread が None を返した場合
                    target_label.setText(f"{label_name}\n(画像読込エラー)")
            except Exception as e:
                # 画像処理・表示中の予期せぬエラー
                print(f"プレビュー画像読込/表示エラー ({image_path}): {e}")
                target_label.setText(f"{label_name}\n(表示エラー)")
        elif image_path: # パスはあるがファイルが存在しない場合
            target_label.setText(f"{label_name}\n(ファイルなし)")
        # else: image_path が None の場合はデフォルトテキストのまま

    @Slot(str, str) # メインウィンドウから呼び出されるスロット
    def update_previews(self, left_path: str or None, right_path: str or None):
        """左右のプレビュー画像を更新する"""
        self.left_image_path = left_path
        self.right_image_path = right_path
        self._display_image(self.left_preview_label, self.left_image_path, "左プレビュー")
        self._display_image(self.right_preview_label, self.right_image_path, "右プレビュー")

    @Slot() # メインウィンドウから呼び出されるスロット
    def clear_previews(self):
        """左右のプレビュー表示をクリアする"""
        self.left_preview_label.clear()
        self.left_preview_label.setText("左プレビュー\n(画像選択で表示)")
        self.right_preview_label.clear()
        self.right_preview_label.setText("右プレビュー\n(類似ペア選択で表示)")
        self.left_image_path = None
        self.right_image_path = None

    # --- イベントハンドラ ---
    def _on_left_preview_clicked(self, event: QMouseEvent):
        """左プレビューラベルがクリックされたときの処理"""
        if event.button() == Qt.MouseButton.LeftButton and self.left_image_path:
            # 左クリックされ、画像パスが存在する場合、シグナルを発行
            self.left_preview_clicked.emit(self.left_image_path)
        elif event.button() == Qt.MouseButton.RightButton:
            # 右クリック時の動作（将来的にコンテキストメニューなど）
            print("左プレビュー右クリック")
            pass

    def _on_right_preview_clicked(self, event: QMouseEvent):
        """右プレビューラベルがクリックされたときの処理"""
        if event.button() == Qt.MouseButton.LeftButton and self.right_image_path:
            # 左クリックされ、画像パスが存在する場合、シグナルを発行
            self.right_preview_clicked.emit(self.right_image_path)
        elif event.button() == Qt.MouseButton.RightButton:
            print("右プレビュー右クリック")
            pass

    # --- ゲッターメソッド (必要に応じて) ---
    def get_left_image_path(self):
        return self.left_image_path

    def get_right_image_path(self):
        return self.right_image_path
