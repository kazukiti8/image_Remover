# gui/widgets/preview_widget.py
import os
import cv2
import numpy as np
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QGraphicsView,
                               QGraphicsScene, QGraphicsPixmapItem, QSizePolicy,
                               QGraphicsSceneMouseEvent, QRubberBand, QCheckBox)
from PySide6.QtCore import Qt, Signal, Slot, QRectF, QPointF, QPoint
from PySide6.QtGui import QImage, QPixmap, QMouseEvent, QWheelEvent, QPainter, QTransform
from typing import Optional, Tuple, Any

NumpyImageType = np.ndarray[Any, Any]
ErrorMsgType = Optional[str]
LoadResult = Tuple[Optional[NumpyImageType], ErrorMsgType, Optional[Tuple[int, int]]]

try:
    from ..utils.image_loader import load_image_as_numpy, get_image_dimensions
except ImportError:
    try: from utils.image_loader import load_image_as_numpy, get_image_dimensions
    except ImportError:
        print("エラー: utils.image_loader のインポートに失敗しました。")
        def load_image_as_numpy(path: str, mode: str = 'rgb') -> Tuple[Optional[NumpyImageType], ErrorMsgType]: return None, "Image loader not available"
        def get_image_dimensions(path: str) -> Tuple[Optional[int], Optional[int]]: return None, None

class ZoomPanGraphicsView(QGraphicsView):
    clicked = Signal() # 左クリック時に発行されるシグナル

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._is_panning: bool = False
        self._last_pan_point: QPoint = QPoint()
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.Box)
        self.setBackgroundBrush(self.palette().window())
        self.initial_label = QLabel("プレビュー\n(画像選択で表示)", self)
        self.initial_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.initial_label.setStyleSheet("QLabel { color: grey; }")
        self.initial_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.initial_label.lower()

    def set_image(self, pixmap: Optional[QPixmap]) -> None:
        self._scene.clear(); self.pixmap_item = None
        if pixmap and not pixmap.isNull():
            self.pixmap_item = self._scene.addPixmap(pixmap)
            self.setSceneRect(QRectF(pixmap.rect()))
            self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self.initial_label.setVisible(False)
        else:
            self.resetTransform(); self.setSceneRect(self.rect().adjusted(0,0,-2,-2))
            self.initial_label.setVisible(True); self.initial_label.setGeometry(self.rect().adjusted(2,2,-2,-2))

    def clear_image(self) -> None: self.set_image(None)
    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.pixmap_item is None: super().wheelEvent(event); return
        zoom_in_factor = 1.15; zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0: self.scale(zoom_in_factor, zoom_in_factor)
        else: self.scale(zoom_out_factor, zoom_out_factor)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.pixmap_item is None: super().mousePressEvent(event); return

        # ★★★ 右クリックでパン開始 ★★★
        if event.button() == Qt.MouseButton.RightButton:
            self._is_panning = True
            self._last_pan_point = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor) # パン中はカーソル変更
            event.accept()
        # ★★★ 左クリックでシグナル発行 ★★★
        elif event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit() # 左クリックシグナル発行
            # パンは開始しないのでカーソル変更やフラグ設定はしない
            event.accept()
        # ★★★★★★★★★★★★★★★★★★★★★★
        else:
            super().mousePressEvent(event) # 他のボタン（中ボタンなど）の処理

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        # パン中の移動処理 (変更なし、_is_panning フラグで制御)
        if self._is_panning:
            delta: QPoint = event.pos() - self._last_pan_point
            hs = self.horizontalScrollBar(); vs = self.verticalScrollBar()
            hs.setValue(hs.value() - delta.x()); vs.setValue(vs.value() - delta.y())
            self._last_pan_point = event.pos(); event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        # ★★★ 右クリックリリースでパン終了 ★★★
        if event.button() == Qt.MouseButton.RightButton and self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor) # カーソルを元に戻す
            event.accept()
        # ★★★★★★★★★★★★★★★★★★★★★★★
        else:
            super().mouseReleaseEvent(event) # 他のボタンリリースの処理

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.initial_label.isVisible(): self.initial_label.setGeometry(self.rect().adjusted(2,2,-2,-2))

class PreviewWidget(QWidget):
    left_preview_clicked = Signal(str)
    right_preview_clicked = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.left_image_path: Optional[str] = None; self.right_image_path: Optional[str] = None
        self.left_image_size: Optional[Tuple[int, int]] = None; self.right_image_size: Optional[Tuple[int, int]] = None
        self.left_preview_view: ZoomPanGraphicsView; self.right_preview_view: ZoomPanGraphicsView
        self.diff_checkbox: QCheckBox
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(5)
        preview_layout = QHBoxLayout(); preview_layout.setContentsMargins(0, 0, 0, 0); preview_layout.setSpacing(10)
        self.left_preview_view = ZoomPanGraphicsView(self)
        self.left_preview_view.initial_label.setText("左プレビュー\n(画像選択で表示)")
        # ★★★ ツールチップ修正 ★★★
        self.left_preview_view.setToolTip("左クリックで削除 / Aキーで開く\nホイールでズーム、右ドラッグでパン")
        # ★★★★★★★★★★★★★★★★
        self.left_preview_view.clicked.connect(self._on_left_preview_clicked)
        self.right_preview_view = ZoomPanGraphicsView(self)
        self.right_preview_view.initial_label.setText("右プレビュー\n(類似ペア選択で表示)")
        # ★★★ ツールチップ修正 ★★★
        self.right_preview_view.setToolTip("左クリックで削除 / Sキーで開く\nホイールでズーム、右ドラッグでパン")
        # ★★★★★★★★★★★★★★★★
        self.right_preview_view.clicked.connect(self._on_right_preview_clicked)
        preview_layout.addWidget(self.left_preview_view, 1); preview_layout.addWidget(self.right_preview_view, 1)
        main_layout.addLayout(preview_layout, 1)
        self.diff_checkbox = QCheckBox("差分表示 (右側に表示、同サイズのみ)")
        self.diff_checkbox.setToolTip("..."); self.diff_checkbox.setEnabled(False)
        self.diff_checkbox.toggled.connect(self._toggle_diff_view)
        main_layout.addWidget(self.diff_checkbox)

    # ... (他のメソッドは変更なし) ...
    def _load_image_and_get_size(self, image_path: str, mode: str = 'rgb') -> LoadResult:
        img_np, error_msg = load_image_as_numpy(image_path, mode=mode)
        if img_np is not None and error_msg is None:
            try: h, w = img_np.shape[:2]; return img_np, None, (w, h)
            except Exception as e: return None, f"サイズ取得エラー: {e}", None
        return img_np, error_msg, None
    def _calculate_difference(self, img1_bgr: NumpyImageType, img2_bgr: NumpyImageType) -> Optional[NumpyImageType]:
        if img1_bgr.shape != img2_bgr.shape: print("差分計算スキップ..."); return None
        try: diff = cv2.absdiff(img1_bgr, img2_bgr); return diff
        except cv2.error as e: print(f"差分計算エラー (OpenCV): {e}"); return None
        except Exception as e: print(f"差分計算エラー: {e}"); return None
    def _numpy_to_pixmap(self, img_np: NumpyImageType) -> Optional[QPixmap]:
        if img_np is None: return None
        try:
            qt_image: QImage
            if len(img_np.shape) == 3: h, w, ch = img_np.shape; bytes_per_line = ch * w; qt_image = QImage(cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB).data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
            elif len(img_np.shape) == 2: h, w = img_np.shape; bytes_per_line = w; qt_image = QImage(img_np.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8).copy()
            else: print("未対応のNumpy配列形式です。"); return None
            return QPixmap.fromImage(qt_image)
        except Exception as e: print(f"NumPyからPixmapへの変換エラー: {e}"); return None
    def _display_image(self, target_view: ZoomPanGraphicsView, image_path: Optional[str], label_name: str) -> None:
        target_view.clear_image(); current_size: Optional[Tuple[int, int]] = None
        if image_path and os.path.exists(image_path):
            img_bgr, error_msg, img_size = self._load_image_and_get_size(image_path, mode='bgr')
            if error_msg: print(f"プレビュー画像読込エラー..."); target_view.initial_label.setText(f"{label_name}\n(読込エラー)"); target_view.initial_label.setVisible(True)
            elif img_bgr is not None:
                pixmap = self._numpy_to_pixmap(img_bgr)
                if pixmap: target_view.set_image(pixmap); current_size = img_size
                else: target_view.initial_label.setText(f"{label_name}\n(表示エラー)"); target_view.initial_label.setVisible(True)
            else: target_view.initial_label.setText(f"{label_name}\n(データなし)"); target_view.initial_label.setVisible(True)
        elif image_path: target_view.initial_label.setText(f"{label_name}\n(ファイルなし)"); target_view.initial_label.setVisible(True)
        else: target_view.initial_label.setText(f"{label_name}"); target_view.initial_label.setVisible(True)
        if target_view == self.left_preview_view: self.left_image_size = current_size
        elif target_view == self.right_preview_view: self.right_image_size = current_size
        self._update_diff_checkbox_state()
    def _display_difference(self) -> None:
        if not self.left_image_path or not self.right_image_path: print("差分表示エラー..."); return
        img1_bgr, err1, size1 = self._load_image_and_get_size(self.left_image_path, mode='bgr')
        img2_bgr, err2, size2 = self._load_image_and_get_size(self.right_image_path, mode='bgr')
        if err1 or err2 or img1_bgr is None or img2_bgr is None: print("差分表示エラー..."); self.right_preview_view.initial_label.setText("右プレビュー\n(差分計算エラー)"); self.right_preview_view.clear_image(); return
        diff_img = self._calculate_difference(img1_bgr, img2_bgr)
        if diff_img is not None:
            diff_pixmap = self._numpy_to_pixmap(diff_img)
            if diff_pixmap: self.right_preview_view.set_image(diff_pixmap); self.right_preview_view.initial_label.setText("差分画像")
            else: self.right_preview_view.initial_label.setText("右プレビュー\n(差分表示エラー)"); self.right_preview_view.clear_image()
        else: self.right_preview_view.initial_label.setText("右プレビュー\n(差分計算不可)"); self.right_preview_view.clear_image(); self.diff_checkbox.setChecked(False); self.diff_checkbox.setEnabled(False)
    def _update_diff_checkbox_state(self) -> None:
        both_images_loaded: bool = bool(self.left_image_path and self.right_image_path)
        sizes_match: bool = (self.left_image_size is not None and self.right_image_size is not None and self.left_image_size == self.right_image_size)
        can_show_diff: bool = both_images_loaded and sizes_match
        self.diff_checkbox.setEnabled(bool(can_show_diff))
        if not can_show_diff: self.diff_checkbox.setChecked(False)
    @Slot(bool)
    def _toggle_diff_view(self, checked: bool) -> None:
        if checked: self._display_difference()
        else: self._display_image(self.right_preview_view, self.right_image_path, "右プレビュー")
    @Slot(str, str)
    def update_previews(self, left_path: Optional[str], right_path: Optional[str]) -> None:
        left_changed = self.left_image_path != left_path; right_changed = self.right_image_path != right_path
        self.left_image_path = left_path; self.right_image_path = right_path
        self._display_image(self.left_preview_view, self.left_image_path, "左プレビュー")
        self._display_image(self.right_preview_view, self.right_image_path, "右プレビュー")
        self._update_diff_checkbox_state()
        if self.diff_checkbox.isChecked() and self.diff_checkbox.isEnabled(): self._display_difference()
    @Slot()
    def clear_previews(self) -> None:
        self.left_preview_view.clear_image(); self.right_preview_view.clear_image()
        self.left_image_path = None; self.right_image_path = None
        self.left_image_size = None; self.right_image_size = None
        self.diff_checkbox.setChecked(False); self.diff_checkbox.setEnabled(False)
    @Slot()
    def _on_left_preview_clicked(self) -> None:
        if self.left_image_path:
            print(f"左プレビュークリック検出: {self.left_image_path}")
            self.left_preview_clicked.emit(self.left_image_path)
    @Slot()
    def _on_right_preview_clicked(self) -> None:
        if self.right_image_path:
            print(f"右プレビュークリック検出: {self.right_image_path}")
            self.right_preview_clicked.emit(self.right_image_path)
    def get_left_image_path(self) -> Optional[str]: return self.left_image_path
    def get_right_image_path(self) -> Optional[str]: return self.right_image_path

