# gui/widgets/preview_widget.py
import os
import cv2 # NumPy変換用に必要
import numpy as np
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QImage, QPixmap, QMouseEvent
from typing import Optional, Tuple, Any # ★ typing をインポート ★

# ★ 型エイリアス ★
NumpyImageType = np.ndarray[Any, Any]
ErrorMsgType = Optional[str]

# 画像ローダー関数をインポート
try:
    from ..utils.image_loader import load_image_as_numpy # 親パッケージの utils から
except ImportError:
    try: from utils.image_loader import load_image_as_numpy # 同じ階層 or PYTHONPATH
    except ImportError:
        print("エラー: utils.image_loader のインポートに失敗しました。")
        def load_image_as_numpy(path: str, mode: str = 'rgb') -> Tuple[Optional[NumpyImageType], ErrorMsgType]: return None, "Image loader not available"


class PreviewWidget(QWidget):
    """左右の画像プレビューエリアを担当するカスタムウィジェット。"""
    left_preview_clicked = Signal(str)
    right_preview_clicked = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None): # ★ 親ウィジェットの型ヒント ★
        super().__init__(parent)
        self.left_image_path: Optional[str] = None
        self.right_image_path: Optional[str] = None
        # UI要素の型ヒント
        self.left_preview_label: QLabel
        self.right_preview_label: QLabel
        self._setup_ui()

    def _setup_ui(self) -> None:
        """UI要素の作成と配置"""
        layout = QHBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(10)
        self.left_preview_label = QLabel("左プレビュー\n(画像選択で表示)"); self.left_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.left_preview_label.setFrameShape(QFrame.Shape.Box); self.left_preview_label.setToolTip("クリックで削除 / Aキーで開く"); self.left_preview_label.mousePressEvent = self._on_left_preview_clicked
        self.right_preview_label = QLabel("右プレビュー\n(類似ペア選択で表示)"); self.right_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.right_preview_label.setFrameShape(QFrame.Shape.Box); self.right_preview_label.setToolTip("クリックで削除 / Sキーで開く"); self.right_preview_label.mousePressEvent = self._on_right_preview_clicked
        layout.addWidget(self.left_preview_label, 1); layout.addWidget(self.right_preview_label, 1)

    def _display_image(self, target_label: QLabel, image_path: Optional[str], label_name: str) -> None:
        """指定されたラベルに画像を表示する内部メソッド (HEIC対応)"""
        target_label.clear(); target_label.setText(f"{label_name}")

        if image_path and os.path.exists(image_path):
            img_rgb: Optional[NumpyImageType]
            error_msg: ErrorMsgType
            img_rgb, error_msg = load_image_as_numpy(image_path, mode='rgb')

            if error_msg: print(f"プレビュー画像読込エラー ({image_path}): {error_msg}"); target_label.setText(f"{label_name}\n(読込エラー)"); return
            if img_rgb is None: target_label.setText(f"{label_name}\n(データなし)"); return

            try:
                qt_image: QImage
                if len(img_rgb.shape) == 3: # カラー
                    h: int; w: int; ch: int
                    h, w, ch = img_rgb.shape; bytes_per_line: int = ch * w
                    qt_image = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                elif len(img_rgb.shape) == 2: # グレースケール
                    h, w = img_rgb.shape; bytes_per_line = w
                    qt_image = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
                else: raise ValueError("未対応の画像チャンネル数です。")

                pixmap: QPixmap = QPixmap.fromImage(qt_image)
                scaled_pixmap: QPixmap = pixmap.scaled(target_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                target_label.setPixmap(scaled_pixmap)
            except Exception as e: print(f"プレビュー画像表示エラー ({image_path}): {e}"); target_label.setText(f"{label_name}\n(表示エラー)")
        elif image_path: target_label.setText(f"{label_name}\n(ファイルなし)")

    @Slot(str, str)
    def update_previews(self, left_path: Optional[str], right_path: Optional[str]) -> None:
        """左右のプレビュー画像を更新する"""
        self.left_image_path = left_path; self.right_image_path = right_path
        self._display_image(self.left_preview_label, self.left_image_path, "左プレビュー")
        self._display_image(self.right_preview_label, self.right_image_path, "右プレビュー")

    @Slot()
    def clear_previews(self) -> None:
        """左右のプレビュー表示をクリアする"""
        self.left_preview_label.clear(); self.left_preview_label.setText("左プレビュー\n(画像選択で表示)")
        self.right_preview_label.clear(); self.right_preview_label.setText("右プレビュー\n(類似ペア選択で表示)")
        self.left_image_path = None; self.right_image_path = None

    def _on_left_preview_clicked(self, event: QMouseEvent) -> None: # ★ イベントハンドラの型ヒント ★
        if event.button() == Qt.MouseButton.LeftButton and self.left_image_path: self.left_preview_clicked.emit(self.left_image_path)
        elif event.button() == Qt.MouseButton.RightButton: print("左プレビュー右クリック")
    def _on_right_preview_clicked(self, event: QMouseEvent) -> None: # ★ イベントハンドラの型ヒント ★
        if event.button() == Qt.MouseButton.LeftButton and self.right_image_path: self.right_preview_clicked.emit(self.right_image_path)
        elif event.button() == Qt.MouseButton.RightButton: print("右プレビュー右クリック")

    def get_left_image_path(self) -> Optional[str]: return self.left_image_path
    def get_right_image_path(self) -> Optional[str]: return self.right_image_path

