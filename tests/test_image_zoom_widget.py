import unittest
import os
import tempfile
from unittest.mock import MagicMock, patch

from PyQt5.QtCore import Qt, QSize, QPoint
from PyQt5.QtWidgets import QApplication, QLabel
from PyQt5.QtGui import QPixmap, QWheelEvent, QMouseEvent

# 画像ズームウィジェットのインポート
from image_zoom_widget import ZoomableImageWidget, MultiViewImageWidget


class TestZoomableImageWidget(unittest.TestCase):
    """ZoomableImageWidgetクラスのテスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        # QApplicationを初期化
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()
        
        # テスト対象のインスタンスを作成
        self.zoom_widget = ZoomableImageWidget()
        
        # シグナルをモック化
        self.zoom_widget.image_clicked = MagicMock()
        
        # テスト用の一時画像ファイルを作成
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        self.temp_file.write(b'dummy image data')
        self.temp_file.close()

    def tearDown(self):
        """テスト後のクリーンアップ"""
        self.zoom_widget.deleteLater()
        
        # テスト用画像ファイルを削除
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_init(self):
        """初期化のテスト"""
        self.assertIsNone(self.zoom_widget.image_path)
        self.assertIsNone(self.zoom_widget.pixmap)
        self.assertIsNone(self.zoom_widget.original_pixmap)
        self.assertEqual(self.zoom_widget.zoom_factor, 1.0)
        self.assertEqual(self.zoom_widget.min_zoom, 0.1)
        self.assertEqual(self.zoom_widget.max_zoom, 5.0)
        self.assertEqual(self.zoom_widget.zoom_step, 0.1)
        self.assertIsNone(self.zoom_widget.drag_start_pos)
        self.assertFalse(self.zoom_widget.drag_mode)

    @patch('cv2.imread')
    @patch('cv2.cvtColor')
    def test_set_image_valid(self, mock_cvtcolor, mock_imread):
        """有効な画像設定のテスト"""
        # 画像読み込みのモックを設定
        mock_img = MagicMock()
        mock_img.shape = (100, 200, 3)
        mock_imread.return_value = mock_img
        
        # cvtColorの戻り値は何でもよい
        mock_cvtcolor.return_value = mock_img
        
        # QImageとQPixmapをモック化
        with patch('image_zoom_widget.QImage') as mock_qimage, \
             patch('image_zoom_widget.QPixmap') as mock_pixmap:
            
            # QImageのモックを設定
            qimage_instance = MagicMock()
            mock_qimage.return_value = qimage_instance
            
            # QPixmapのモックを設定
            pixmap_instance = MagicMock()
            mock_pixmap.fromImage.return_value = pixmap_instance
            
            # 画像を設定
            result = self.zoom_widget.set_image(self.temp_file.name)
            
            # 結果が成功を示すことを確認
            self.assertTrue(result)
            
            # 画像パスが設定されたことを確認
            self.assertEqual(self.zoom_widget.image_path, self.temp_file.name)
            
            # ピクスマップが設定されたことを確認
            self.assertEqual(self.zoom_widget.original_pixmap, pixmap_instance)
            self.assertEqual(self.zoom_widget.pixmap, pixmap_instance.copy())
            
            # 画像ラベルにピクスマップが設定されたことを確認
            self.zoom_widget.image_label.setPixmap.assert_called_once_with(pixmap_instance)
            
            # fit_to_windowが呼ばれたことを確認
            self.zoom_widget.fit_to_window = MagicMock()
            self.zoom_widget.set_image(self.temp_file.name)
            self.zoom_widget.fit_to_window.assert_called_once()

    def test_set_image_invalid(self):
        """無効な画像設定のテスト"""
        # 存在しないファイルパス
        non_existent_path = "/non/existent/path.jpg"
        
        # clear_imageメソッドをモック化
        self.zoom_widget.clear_image = MagicMock()
        
        # 画像を設定（失敗するはず）
        result = self.zoom_widget.set_image(non_existent_path)
        
        # 結果が失敗を示すことを確認
        self.assertFalse(result)
        
        # clear_imageが呼ばれたことを確認
        self.zoom_widget.clear_image.assert_called_once()

    def test_clear_image(self):
        """画像クリアのテスト"""
        # 初期状態を設定
        self.zoom_widget.image_path = "dummy_path"
        self.zoom_widget.pixmap = MagicMock()
        self.zoom_widget.original_pixmap = MagicMock()
        self.zoom_widget.zoom_factor = 2.0
        
        # 画像をクリア
        self.zoom_widget.clear_image()
        
        # 状態がリセットされたことを確認
        self.assertIsNone(self.zoom_widget.image_path)
        self.assertIsNone(self.zoom_widget.pixmap)
        self.assertIsNone(self.zoom_widget.original_pixmap)
        self.assertEqual(self.zoom_widget.zoom_factor, 1.0)
        
        # ラベルがクリアされたことを確認
        self.zoom_widget.image_label.clear.assert_called_once()

    def test_zoom_in(self):
        """ズームインのテスト"""
        # 初期状態を設定
        self.zoom_widget.pixmap = MagicMock()
        self.zoom_widget.zoom_factor = 1.0
        self.zoom_widget.set_zoom = MagicMock()
        
        # ズームイン
        self.zoom_widget.zoom_in()
        
        # set_zoomが正しいズーム率で呼ばれたことを確認
        self.zoom_widget.set_zoom.assert_called_once_with(1.0 + self.zoom_widget.zoom_step)

    def test_zoom_out(self):
        """ズームアウトのテスト"""
        # 初期状態を設定
        self.zoom_widget.pixmap = MagicMock()
        self.zoom_widget.zoom_factor = 1.0
        self.zoom_widget.set_zoom = MagicMock()
        
        # ズームアウト
        self.zoom_widget.zoom_out()
        
        # set_zoomが正しいズーム率で呼ばれたことを確認
        self.zoom_widget.set_zoom.assert_called_once_with(1.0 - self.zoom_widget.zoom_step)

    def test_set_zoom(self):
        """ズーム率設定のテスト"""
        # 初期状態を設定
        self.zoom_widget.pixmap = MagicMock()  # ピクスマップがないとメソッドは早期に戻る
        self.zoom_widget.original_pixmap = MagicMock()
        self.zoom_widget.original_pixmap.width.return_value = 200
        self.zoom_widget.original_pixmap.height.return_value = 100
        self.zoom_widget.zoom_factor = 1.0
        
        # update_zoom_displayをモック化
        self.zoom_widget.update_zoom_display = MagicMock()
        
        # ズーム率を設定
        self.zoom_widget.set_zoom(2.0)
        
        # ズーム率が更新されたことを確認
        self.assertEqual(self.zoom_widget.zoom_factor, 2.0)
        
        # ラベルのサイズが更新されたことを確認
        self.zoom_widget.image_label.setFixedSize.assert_called_once_with(400, 200)
        
        # update_zoom_displayが呼ばれたことを確認
        self.zoom_widget.update_zoom_display.assert_called_once()

    def test_set_zoom_clamps_values(self):
        """ズーム率の上下限クランプのテスト"""
        # 初期設定
        self.zoom_widget.pixmap = MagicMock()
        self.zoom_widget.original_pixmap = MagicMock()
        self.zoom_widget.update_zoom_display = MagicMock()
        
        # 下限以下の値を設定
        self.zoom_widget.set_zoom(0.05)
        self.assertEqual(self.zoom_widget.zoom_factor, self.zoom_widget.min_zoom)
        
        # 上限以上の値を設定
        self.zoom_widget.set_zoom(6.0)
        self.assertEqual(self.zoom_widget.zoom_factor, self.zoom_widget.max_zoom)

    def test_update_zoom_display(self):
        """ズーム表示更新のテスト"""
        # 初期設定
        self.zoom_widget.zoom_factor = 1.5
        self.zoom_widget.original_pixmap = MagicMock()
        scaled_pixmap = MagicMock()
        self.zoom_widget.original_pixmap.scaled.return_value = scaled_pixmap
        
        # ズーム表示を更新
        self.zoom_widget.update_zoom_display()
        
        # ズームラベルが更新されたことを確認
        self.assertEqual(self.zoom_widget.zoom_label.text(), "150%")
        
        # スライダーが更新されたことを確認
        self.zoom_widget.zoom_slider.setValue.assert_called_once_with(150)
        
        # ピクスマップが更新されたことを確認
        self.zoom_widget.image_label.setPixmap.assert_called_once_with(scaled_pixmap)

    def test_on_slider_value_changed(self):
        """スライダー値変更時の処理テスト"""
        # set_zoomをモック化
        self.zoom_widget.set_zoom = MagicMock()
        
        # スライダー値変更時の処理を実行
        self.zoom_widget.on_slider_value_changed(200)
        
        # 正しいズーム率でset_zoomが呼ばれたことを確認
        self.zoom_widget.set_zoom.assert_called_once_with(2.0)

    def test_fit_to_window(self):
        """ウィンドウフィット表示のテスト"""
        # スクロールエリアとピクスマップのサイズを設定
        self.zoom_widget.scroll_area.width.return_value = 400
        self.zoom_widget.scroll_area.height.return_value = 300
        
        self.zoom_widget.original_pixmap = MagicMock()
        self.zoom_widget.original_pixmap.width.return_value = 800
        self.zoom_widget.original_pixmap.height.return_value = 600
        
        # set_zoomをモック化
        self.zoom_widget.set_zoom = MagicMock()
        
        # ウィンドウにフィット
        self.zoom_widget.fit_to_window()
        
        # 正しいズーム率でset_zoomが呼ばれたことを確認
        self.zoom_widget.set_zoom.assert_called_once_with(0.5)  # 400/800 = 0.5

    def test_show_original_size(self):
        """原寸表示のテスト"""
        # 初期設定
        self.zoom_widget.original_pixmap = MagicMock()
        self.zoom_widget.set_zoom = MagicMock()
        
        # 原寸表示
        self.zoom_widget.show_original_size()
        
        # 1.0のズーム率でset_zoomが呼ばれたことを確認
        self.zoom_widget.set_zoom.assert_called_once_with(1.0)

    def test_label_mouse_press_event(self):
        """マウスプレスイベントのテスト"""
        # 左クリックのマウスイベントを作成
        event = MagicMock()
        event.button.return_value = Qt.LeftButton
        event.pos.return_value = QPoint(100, 100)
        
        # イベント処理
        self.zoom_widget.label_mouse_press_event(event)
        
        # ドラッグモードがアクティブになったことを確認
        self.assertTrue(self.zoom_widget.drag_mode)
        self.assertEqual(self.zoom_widget.drag_start_pos, QPoint(100, 100))
        
        # カーソルが変更されたことを確認
        self.zoom_widget.setCursor.assert_called_once_with(Qt.ClosedHandCursor)
        
        # イベントが受け付けられたことを確認
        event.accept.assert_called_once()

    def test_label_mouse_release_event(self):
        """マウスリリースイベントのテスト"""
        # 初期状態を設定
        self.zoom_widget.drag_mode = True
        self.zoom_widget.drag_start_pos = QPoint(100, 100)
        
        # 左クリックのマウスイベントを作成
        event = MagicMock()
        event.button.return_value = Qt.LeftButton
        event.pos.return_value = QPoint(101, 101)  # ほぼ同じ位置（クリックとみなされる）
        
        # イベント処理
        self.zoom_widget.label_mouse_release_event(event)
        
        # ドラッグモードが非アクティブになったことを確認
        self.assertFalse(self.zoom_widget.drag_mode)
        
        # カーソルが戻されたことを確認
        self.zoom_widget.setCursor.assert_called_once_with(Qt.ArrowCursor)
        
        # クリックシグナルが発行されたことを確認
        self.zoom_widget.image_clicked.emit.assert_called_once_with(QPoint(101, 101))
        
        # イベントが受け付けられたことを確認
        event.accept.assert_called_once()

    def test_label_wheel_event(self):
        """マウスホイールイベントのテスト"""
        # ホイールイベントを作成
        event = MagicMock()
        
        # zoom_in と zoom_out をモック化
        self.zoom_widget.zoom_in = MagicMock()
        self.zoom_widget.zoom_out = MagicMock()
        
        # 上回転のホイールイベント（ズームイン）
        event.angleDelta().y.return_value = 120
        self.zoom_widget.label_wheel_event(event)
        self.zoom_widget.zoom_in.assert_called_once()
        self.zoom_widget.zoom_out.assert_not_called()
        
        # zoom_inのモックをリセット
        self.zoom_widget.zoom_in.reset_mock()
        
        # 下回転のホイールイベント（ズームアウト）
        event.angleDelta().y.return_value = -120
        self.zoom_widget.label_wheel_event(event)
        self.zoom_widget.zoom_in.assert_not_called()
        self.zoom_widget.zoom_out.assert_called_once()
        
        # イベントが受け付けられたことを確認
        event.accept.assert_called()


class TestMultiViewImageWidget(unittest.TestCase):
    """MultiViewImageWidgetクラスのテスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        # QApplicationを初期化
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()
        
        # テスト対象のインスタンスを作成
        self.multi_view = MultiViewImageWidget()
        
        # テスト用の画像パスのリスト
        self.image_paths = [
            "/fake/path/image1.jpg",
            "/fake/path/image2.png",
            "/fake/path/image3.gif"
        ]

    def tearDown(self):
        """テスト後のクリーンアップ"""
        self.multi_view.deleteLater()

    def test_init(self):
        """初期化のテスト"""
        self.assertEqual(self.multi_view.current_mode, "normal")
        self.assertEqual(self.multi_view.images, [])
        self.assertEqual(self.multi_view.current_index, -1)
        
        # 通常表示モードがアクティブかを確認
        self.assertTrue(self.multi_view.normal_widget.isVisible())
        self.assertFalse(self.multi_view.split_widget.isVisible())

    def test_set_images(self):
        """画像リスト設定のテスト"""
        # update_navigation_buttons, update_index_display, update_current_viewをモック化
        self.multi_view.update_navigation_buttons = MagicMock()
        self.multi_view.update_index_display = MagicMock()
        self.multi_view.update_current_view = MagicMock()
        
        # 画像リストを設定
        self.multi_view.set_images(self.image_paths)
        
        # 画像リストが設定されたことを確認
        self.assertEqual(self.multi_view.images, self.image_paths)
        self.assertEqual(self.multi_view.current_index, 0)
        
        # 各更新メソッドが呼ばれたことを確認
        self.multi_view.update_navigation_buttons.assert_called_once()
        self.multi_view.update_index_display.assert_called_once()
        self.multi_view.update_current_view.assert_called_once()
        
        # 空リストを設定した場合
        self.multi_view.set_images([])
        self.assertEqual(self.multi_view.images, [])
        self.assertEqual(self.multi_view.current_index, -1)

    def test_update_navigation_buttons(self):
        """ナビゲーションボタン更新のテスト"""
        # 初期設定
        self.multi_view.images = self.image_paths
        self.multi_view.current_index = 1  # 真ん中の画像
        
        # ナビゲーションボタンを更新
        self.multi_view.update_navigation_buttons()
        
        # 前後の画像があるのでボタンは有効になるはず
        self.assertTrue(self.multi_view.first_btn.isEnabled())
        self.assertTrue(self.multi_view.prev_btn.isEnabled())
        self.assertTrue(self.multi_view.next_btn.isEnabled())
        self.assertTrue(self.multi_view.last_btn.isEnabled())
        
        # 最初の画像の場合
        self.multi_view.current_index = 0
        self.multi_view.update_navigation_buttons()
        self.assertFalse(self.multi_view.first_btn.isEnabled())
        self.assertFalse(self.multi_view.prev_btn.isEnabled())
        self.assertTrue(self.multi_view.next_btn.isEnabled())
        self.assertTrue(self.multi_view.last_btn.isEnabled())
        
        # 最後の画像の場合
        self.multi_view.current_index = len(self.image_paths) - 1
        self.multi_view.update_navigation_buttons()
        self.assertTrue(self.multi_view.first_btn.isEnabled())
        self.assertTrue(self.multi_view.prev_btn.isEnabled())
        self.assertFalse(self.multi_view.next_btn.isEnabled())
        self.assertFalse(self.multi_view.last_btn.isEnabled())
        
        # 画像がない場合
        self.multi_view.images = []
        self.multi_view.current_index = -1
        self.multi_view.update_navigation_buttons()
        self.assertFalse(self.multi_view.first_btn.isEnabled())
        self.assertFalse(self.multi_view.prev_btn.isEnabled())
        self.assertFalse(self.multi_view.next_btn.isEnabled())
        self.assertFalse(self.multi_view.last_btn.isEnabled())

    def test_update_index_display(self):
        """インデックス表示更新のテスト"""
        # 初期設定
        self.multi_view.images = self.image_paths
        self.multi_view.current_index = 1  # 真ん中の画像
        
        # インデックス表示を更新
        self.multi_view.update_index_display()
        
        # 表示が更新されたことを確認
        self.assertEqual(self.multi_view.index_label.text(), f"2/{len(self.image_paths)}")
        
        # 画像がない場合
        self.multi_view.images = []
        self.multi_view.current_index = -1
        self.multi_view.update_index_display()
        self.assertEqual(self.multi_view.index_label.text(), "0/0")

    def test_update_current_view(self):
        """現在の表示モード更新のテスト"""
        # モードごとの更新メソッドをモック化
        self.multi_view.update_normal_view = MagicMock()
        self.multi_view.update_split_view = MagicMock()
        self.multi_view.update_grid_view = MagicMock()
        
        # 通常モードの場合
        self.multi_view.current_mode = "normal"
        self.multi_view.update_current_view()
        self.multi_view.update_normal_view.assert_called_once()
        self.multi_view.update_split_view.assert_not_called()
        self.multi_view.update_grid_view.assert_not_called()
        
        # モックをリセット
        self.multi_view.update_normal_view.reset_mock()
        
        # 分割モードの場合
        self.multi_view.current_mode = "split"
        self.multi_view.update_current_view()
        self.multi_view.update_normal_view.assert_not_called()
        self.multi_view.update_split_view.assert_called_once()
        self.multi_view.update_grid_view.assert_not_called()
        
        # モックをリセット
        self.multi_view.update_split_view.reset_mock()
        
        # グリッドモードの場合
        self.multi_view.current_mode = "grid"
        self.multi_view.update_current_view()
        self.multi_view.update_normal_view.assert_not_called()
        self.multi_view.update_split_view.assert_not_called()
        self.multi_view.update_grid_view.assert_called_once()

    def test_update_normal_view(self):
        """通常表示更新のテスト"""
        # 初期設定
        self.multi_view.split_widget = MagicMock()
        self.multi_view.normal_widget = MagicMock()
        self.multi_view.images = self.image_paths
        self.multi_view.current_index = 1
        
        # 通常表示を更新
        self.multi_view.update_normal_view()
        
        # 正しいウィジェットが表示/非表示になっていることを確認
        self.multi_view.split_widget.hide.assert_called_once()
        self.multi_view.normal_widget.show.assert_called_once()
        
        # 正しい画像が設定されたことを確認
        self.multi_view.normal_widget.set_image.assert_called_once_with(self.image_paths[1])
        
        # 画像がない場合
        self.multi_view.images = []
        self.multi_view.current_index = -1
        self.multi_view.update_normal_view()
        self.multi_view.normal_widget.clear_image.assert_called_once()

    def test_update_split_view(self):
        """分割表示更新のテスト"""
        # 初期設定
        self.multi_view.normal_widget = MagicMock()
        self.multi_view.split_widget = MagicMock()
        self.multi_view.left_image = MagicMock()
        self.multi_view.right_image = MagicMock()
        self.multi_view.images = self.image_paths
        self.multi_view.current_index = 0
        
        # 分割表示を更新
        self.multi_view.update_split_view()
        
        # 正しいウィジェットが表示/非表示になっていることを確認
        self.multi_view.normal_widget.hide.assert_called_once()
        self.multi_view.split_widget.show.assert_called_once()
        
        # 左側の画像が設定されたことを確認
        self.multi_view.left_image.set_image.assert_called_once_with(self.image_paths[0])
        
        # 右側の画像（次の画像）が設定されたことを確認
        self.multi_view.right_image.set_image.assert_called_once_with(self.image_paths[1])
        
        # 最後の画像が選択されている場合
        self.multi_view.current_index = len(self.image_paths) - 1
        self.multi_view.left_image.reset_mock()
        self.multi_view.right_image.reset_mock()
        self.multi_view.update_split_view()
        self.multi_view.left_image.set_image.assert_called_once_with(self.image_paths[-1])
        self.multi_view.right_image.clear_image.assert_called_once()

    def test_change_view_mode(self):
        """表示モード変更のテスト"""
        # 更新メソッドをモック化
        self.multi_view.update_current_view = MagicMock()
        
        # 通常モードに変更
        self.multi_view.change_view_mode(0)
        self.assertEqual(self.multi_view.current_mode, "normal")
        self.multi_view.update_current_view.assert_called_once()
        
        # モックをリセット
        self.multi_view.update_current_view.reset_mock()
        
        # 分割モードに変更
        self.multi_view.change_view_mode(1)
        self.assertEqual(self.multi_view.current_mode, "split")
        self.multi_view.update_current_view.assert_called_once()
        
        # モックをリセット
        self.multi_view.update_current_view.reset_mock()
        
        # グリッドモードに変更
        self.multi_view.change_view_mode(2)
        self.assertEqual(self.multi_view.current_mode, "grid")
        self.multi_view.update_current_view.assert_called_once()

    def test_navigation_methods(self):
        """ナビゲーションメソッドのテスト"""
        # 初期設定
        self.multi_view.images = self.image_paths
        self.multi_view.current_index = 1
        
        # 更新メソッドをモック化
        self.multi_view.update_navigation_buttons = MagicMock()
        self.multi_view.update_index_display = MagicMock()
        self.multi_view.update_current_view = MagicMock()
        
        # 先頭へ移動
        self.multi_view.go_to_first()
        self.assertEqual(self.multi_view.current_index, 0)
        self.multi_view.update_navigation_buttons.assert_called_once()
        self.multi_view.update_index_display.assert_called_once()
        self.multi_view.update_current_view.assert_called_once()
        
        # モックをリセット
        self.multi_view.update_navigation_buttons.reset_mock()
        self.multi_view.update_index_display.reset_mock()
        self.multi_view.update_current_view.reset_mock()
        
        # 現在のインデックスを再設定
        self.multi_view.current_index = 1
        
        # 前へ移動
        self.multi_view.go_to_prev()
        self.assertEqual(self.multi_view.current_index, 0)
        self.multi_view.update_navigation_buttons.assert_called_once()
        self.multi_view.update_index_display.assert_called_once()
        self.multi_view.update_current_view.assert_called_once()
        
        # モックをリセット
        self.multi_view.update_navigation_buttons.reset_mock()
        self.multi_view.update_index_display.reset_mock()
        self.multi_view.update_current_view.reset_mock()
        
        # 次へ移動
        self.multi_view.go_to_next()
        self.assertEqual(self.multi_view.current_index, 1)
        self.multi_view.update_navigation_buttons.assert_called_once()
        self.multi_view.update_index_display.assert_called_once()
        self.multi_view.update_current_view.assert_called_once()
        
        # モックをリセット
        self.multi_view.update_navigation_buttons.reset_mock()
        self.multi_view.update_index_display.reset_mock()
        self.multi_view.update_current_view.reset_mock()
        
        # 最後へ移動
        self.multi_view.go_to_last()
        self.assertEqual(self.multi_view.current_index, len(self.image_paths) - 1)
        self.multi_view.update_navigation_buttons.assert_called_once()
        self.multi_view.update_index_display.assert_called_once()
        self.multi_view.update_current_view.assert_called_once()

    def test_set_current_index(self):
        """現在のインデックス設定のテスト"""
        # 初期設定
        self.multi_view.images = self.image_paths
        
        # 更新メソッドをモック化
        self.multi_view.update_navigation_buttons = MagicMock()
        self.multi_view.update_index_display = MagicMock()
        self.multi_view.update_current_view = MagicMock()
        
        # 有効なインデックスを設定
        result = self.multi_view.set_current_index(1)
        self.assertTrue(result)
        self.assertEqual(self.multi_view.current_index, 1)
        self.multi_view.update_navigation_buttons.assert_called_once()
        self.multi_view.update_index_display.assert_called_once()
        self.multi_view.update_current_view.assert_called_once()
        
        # モックをリセット
        self.multi_view.update_navigation_buttons.reset_mock()
        self.multi_view.update_index_display.reset_mock()
        self.multi_view.update_current_view.reset_mock()
        
        # 無効なインデックスを設定（範囲外）
        result = self.multi_view.set_current_index(10)
        self.assertFalse(result)
        self.assertEqual(self.multi_view.current_index, 1)  # 変わらない
        self.multi_view.update_navigation_buttons.assert_not_called()
        self.multi_view.update_index_display.assert_not_called()
        self.multi_view.update_current_view.assert_not_called()
        
        # 無効なインデックスを設定（負の値）
        result = self.multi_view.set_current_index(-1)
        self.assertFalse(result)
        self.assertEqual(self.multi_view.current_index, 1)  # 変わらない
        self.multi_view.update_navigation_buttons.assert_not_called()
        self.multi_view.update_index_display.assert_not_called()
        self.multi_view.update_current_view.assert_not_called()


if __name__ == '__main__':
    unittest.main()
