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

        # 右クリックでパン開始
        if event.button() == Qt.MouseButton.RightButton:
            self._is_panning = True
            self._last_pan_point = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor) # パン中はカーソル変更
            event.accept()
        # 左クリックでシグナル発行
        elif event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit() # 左クリックシグナル発行
            event.accept()
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
        # 右クリックリリースでパン終了
        if event.button() == Qt.MouseButton.RightButton and self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor) # カーソルを元に戻す
            event.accept()
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
        self.left_image_path: Optional[str] = None
        self.right_image_path: Optional[str] = None
        self.left_image_size: Optional[Tuple[int, int]] = None
        self.right_image_size: Optional[Tuple[int, int]] = None
        self.left_preview_view: ZoomPanGraphicsView
        self.right_preview_view: ZoomPanGraphicsView
        self.diff_checkbox: QCheckBox
        # self.right_title_label: QLabel # 右側のタイトルラベルを削除
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # # プレビュータイトルレイアウトを削除 (もしくはコメントアウト)
        # title_layout = QHBoxLayout()
        # left_title = QLabel("") # Label text removed
        # left_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # left_title.setStyleSheet("font-weight: bold;")
        # # self.right_title_label = QLabel("") # Label text removed, instance variable # 削除
        # # self.right_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # 削除
        # # self.right_title_label.setStyleSheet("font-weight: bold;") # 削除
        # title_layout.addWidget(left_title)
        # # title_layout.addWidget(self.right_title_label) # Use instance variable # 削除
        # main_layout.addLayout(title_layout) # タイトルレイアウトの追加も削除

        # プレビュー領域
        self.preview_layout = QHBoxLayout() # レイアウトをインスタンス変数にする
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_layout.setSpacing(10)

        # 左プレビュー
        self.left_preview_view = ZoomPanGraphicsView(self)
        self.left_preview_view.initial_label.setText("画像を選択すると\nここに表示されます")
        self.left_preview_view.setToolTip("左クリック → 削除\nAキー → 開く\nホイール → ズーム\n右ドラッグ → 移動")
        self.left_preview_view.clicked.connect(self._on_left_preview_clicked)

        # 右プレビュー
        self.right_preview_view = ZoomPanGraphicsView(self)
        self.right_preview_view.initial_label.setText("類似/重複ペア選択で\nここに表示されます")
        self.right_preview_view.setToolTip("左クリック → 削除\nSキー → 開く\nホイール → ズーム\n右ドラッグ → 移動")
        self.right_preview_view.clicked.connect(self._on_right_preview_clicked)

        # ボーダーと背景色を追加
        for view in [self.left_preview_view, self.right_preview_view]:
            view.setFrameShape(QFrame.Shape.StyledPanel)
            view.setFrameShadow(QFrame.Shadow.Sunken)

        self.preview_layout.addWidget(self.left_preview_view, 1)
        self.preview_layout.addWidget(self.right_preview_view, 1)
        main_layout.addLayout(self.preview_layout, 1) # インスタンス変数を使用

        # 操作ガイド
        guide_layout = QHBoxLayout()
        left_guide = QLabel("Aキー: 開く | クリック: 削除")
        left_guide.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_guide.setStyleSheet("font-size: 9pt; color: #666;")
        right_guide = QLabel("Sキー: 開く | クリック: 削除")
        right_guide.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_guide.setStyleSheet("font-size: 9pt; color: #666;")
        guide_layout.addWidget(left_guide)
        guide_layout.addWidget(right_guide)
        main_layout.addLayout(guide_layout)

        # 差分表示チェックボックス
        self.diff_checkbox = QCheckBox("差分表示（同サイズの画像のみ）")
        self.diff_checkbox.setToolTip("同じサイズの画像間の違いを視覚的に表示します")
        self.diff_checkbox.setEnabled(False)
        self.diff_checkbox.toggled.connect(self._toggle_diff_view)
        main_layout.addWidget(self.diff_checkbox, 0, Qt.AlignmentFlag.AlignCenter)

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

    def _display_image(self, target_view: ZoomPanGraphicsView, image_path: Optional[str], label_name: str) -> None: # label_name is kept for initial_label logic if needed
        target_view.clear_image(); current_size: Optional[Tuple[int, int]] = None
        display_label_name = "" # Default to empty for the main title area (which is now gone)
                                # We'll use this for the initial_label text if an error occurs.

        if image_path and os.path.exists(image_path):
            img_bgr, error_msg, img_size = self._load_image_and_get_size(image_path, mode='bgr')
            if error_msg:
                print(f"プレビュー画像読込エラー: {error_msg}")
                # Use a generic message or the original initial_label text
                target_view.initial_label.setText(f"プレビュー\n(読込エラー)")
                target_view.initial_label.setVisible(True)
            elif img_bgr is not None:
                pixmap = self._numpy_to_pixmap(img_bgr)
                if pixmap:
                    target_view.set_image(pixmap)
                    current_size = img_size
                else:
                    target_view.initial_label.setText(f"プレビュー\n(表示エラー)")
                    target_view.initial_label.setVisible(True)
            else:
                target_view.initial_label.setText(f"プレビュー\n(データなし)")
                target_view.initial_label.setVisible(True)
        elif image_path:
            target_view.initial_label.setText(f"プレビュー\n(ファイルなし)")
            target_view.initial_label.setVisible(True)
        else:
            # Restore default initial_label text based on which view it is
            if target_view == self.left_preview_view:
                target_view.initial_label.setText("画像を選択すると\nここに表示されます")
            elif target_view == self.right_preview_view:
                 target_view.initial_label.setText("類似/重複ペア選択で\nここに表示されます")
            target_view.initial_label.setVisible(True)


        if target_view == self.left_preview_view: self.left_image_size = current_size
        elif target_view == self.right_preview_view: self.right_image_size = current_size

    def _display_difference(self) -> None:
        if not self.left_image_path or not self.right_image_path:
            print("差分表示エラー: パスがありません")
            self.right_preview_view.initial_label.setText("プレビュー\n(差分計算不可)")
            self.right_preview_view.clear_image()
            return

        img1_bgr, err1, size1 = self._load_image_and_get_size(self.left_image_path, mode='bgr')
        img2_bgr, err2, size2 = self._load_image_and_get_size(self.right_image_path, mode='bgr')

        if err1 or err2 or img1_bgr is None or img2_bgr is None:
            print(f"差分表示エラー: 画像読込エラー (左: {err1}, 右: {err2})")
            self.right_preview_view.initial_label.setText("プレビュー\n(差分計算エラー)")
            self.right_preview_view.clear_image()
            return

        diff_img = self._calculate_difference(img1_bgr, img2_bgr)

        if diff_img is not None:
            diff_pixmap = self._numpy_to_pixmap(diff_img)
            if diff_pixmap:
                self.right_preview_view.set_image(diff_pixmap)
                # self.right_title_label.setText("") # Diff title removed # 削除
                self.right_preview_view.initial_label.setVisible(False) # 初期ラベルを非表示に
            else:
                print("差分画像からPixmapへの変換に失敗")
                self.right_preview_view.initial_label.setText("プレビュー\n(差分表示エラー)")
                self.right_preview_view.clear_image()
        else:
            print("差分計算が不可または失敗")
            self.right_preview_view.initial_label.setText("プレビュー\n(差分計算不可)")
            self.right_preview_view.clear_image()
            self.diff_checkbox.setChecked(False)
            self.diff_checkbox.setEnabled(False)


    def _update_diff_checkbox_state(self) -> None:
        """差分表示チェックボックスの有効/無効を更新"""
        right_preview_visible = self.right_preview_view.isVisible()
        both_images_loaded = bool(self.left_image_path and os.path.exists(str(self.left_image_path)) and
                                  self.right_image_path and os.path.exists(str(self.right_image_path)))
        sizes_match = (self.left_image_size is not None and self.right_image_size is not None and
                       self.left_image_size == self.right_image_size)

        can_show_diff = right_preview_visible and both_images_loaded and sizes_match
        self.diff_checkbox.setEnabled(can_show_diff)

        if not can_show_diff and self.diff_checkbox.isChecked():
             self.diff_checkbox.setChecked(False)

    @Slot(bool)
    def _toggle_diff_view(self, checked: bool) -> None:
        """差分表示チェックボックスの状態に応じて表示を切り替える"""
        if self.right_preview_view.isVisible():
            if checked:
                self._display_difference()
            else:
                self._display_image(self.right_preview_view, self.right_image_path, "右プレビュー") # Pass a generic name for error display
                # self.right_title_label.setText("") # Title removed # 削除
        else:
            self.diff_checkbox.setChecked(False)


    @Slot(str, str, str)
    def update_previews(self, left_path: Optional[str], right_path: Optional[str], selection_type: str) -> None:
        self.left_image_path = left_path
        self.right_image_path = right_path

        self._display_image(self.left_preview_view, self.left_image_path, "左プレビュー") # Pass a generic name for error display

        if selection_type == 'blurry':
            self.right_preview_view.clear_image()
            self.right_preview_view.setVisible(False)
            # self.right_title_label.setVisible(False) # タイトルも非表示に # 削除
            self.diff_checkbox.setEnabled(False)
            self.diff_checkbox.setChecked(False)
        else: # 'similar' or 'duplicate'
            self.right_preview_view.setVisible(True)
            # self.right_title_label.setVisible(True) # タイトルも表示に # 削除
            self._display_image(self.right_preview_view, self.right_image_path, "右プレビュー") # Pass a generic name for error display
            # self.right_title_label.setText("") # Title removed # 削除
            self._update_diff_checkbox_state()

    @Slot()
    def clear_previews(self) -> None:
        self.left_preview_view.clear_image()
        self.right_preview_view.clear_image()
        self.left_image_path = None
        self.right_image_path = None
        self.left_image_size = None
        self.right_image_size = None
        self.diff_checkbox.setChecked(False)
        self.diff_checkbox.setEnabled(False)
        self.right_preview_view.setVisible(True)
        # self.right_title_label.setVisible(True) # 削除
        # self.right_title_label.setText("") # Title removed # 削除
        # Restore default initial_label text
        self.left_preview_view.initial_label.setText("画像を選択すると\nここに表示されます")
        self.right_preview_view.initial_label.setText("類似/重複ペア選択で\nここに表示されます")


    @Slot()
    def _on_left_preview_clicked(self) -> None:
        if self.left_image_path:
            print(f"左プレビュークリック検出: {self.left_image_path}")
            self.left_preview_clicked.emit(self.left_image_path)

    @Slot()
    def _on_right_preview_clicked(self) -> None:
        if self.right_preview_view.isVisible() and self.right_image_path:
            print(f"右プレビュークリック検出: {self.right_image_path}")
            self.right_preview_clicked.emit(self.right_image_path)

    def get_left_image_path(self) -> Optional[str]: return self.left_image_path
    def get_right_image_path(self) -> Optional[str]: return self.right_image_path
