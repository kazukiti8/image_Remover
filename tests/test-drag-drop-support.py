import unittest
import os
from unittest.mock import MagicMock, patch

from PyQt5.QtCore import Qt, QMimeData, QUrl
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from PyQt5.QtWidgets import QApplication, QWidget

# ドラッグ&ドロップサポートモジュールのインポート
from drag_drop_support import DropArea, FilesDropWidget, DirectoriesDropWidget, DragDropManager


class TestDropArea(unittest.TestCase):
    """DropAreaクラスのテスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        # QApplicationを初期化
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()
        
        # テスト対象のインスタンスを作成
        self.drop_area = DropArea(accept_files=True, accept_dirs=True)
        
        # シグナルをモック化
        self.drop_area.files_dropped = MagicMock()
        self.drop_area.directories_dropped = MagicMock()

    def tearDown(self):
        """テスト後のクリーンアップ"""
        self.drop_area.deleteLater()

    def test_init(self):
        """初期化のテスト"""
        self.assertTrue(self.drop_area.acceptDrops())
        self.assertTrue(self.drop_area.accept_files)
        self.assertTrue(self.drop_area.accept_dirs)
        
        # ファイルのみを受け付けるインスタンス
        files_only = DropArea(accept_files=True, accept_dirs=False)
        self.assertTrue(files_only.accept_files)
        self.assertFalse(files_only.accept_dirs)
        files_only.deleteLater()
        
        # ディレクトリのみを受け付けるインスタンス
        dirs_only = DropArea(accept_files=False, accept_dirs=True)
        self.assertFalse(dirs_only.accept_files)
        self.assertTrue(dirs_only.accept_dirs)
        dirs_only.deleteLater()

    def test_set_normal_background(self):
        """通常背景設定のテスト"""
        self.drop_area.set_normal_background()
        palette = self.drop_area.palette()
        self.assertEqual(palette.color(palette.Window).name(), "#f0f0f0")

    def test_set_highlight_background(self):
        """ハイライト背景設定のテスト"""
        self.drop_area.set_highlight_background()
        palette = self.drop_area.palette()
        self.assertEqual(palette.color(palette.Window).name(), "#c8dcff")

    @patch('os.path.isfile')
    @patch('os.path.isdir')
    def test_dragEnterEvent_files(self, mock_isdir, mock_isfile):
        """ファイルのドラッグエンターイベントのテスト"""
        # ファイルパスのモックを設定
        mock_isfile.return_value = True
        mock_isdir.return_value = False
        
        # MimeDataを作成
        mime_data = QMimeData()
        urls = [QUrl.fromLocalFile("/fake/file/path.txt")]
        mime_data.setUrls(urls)
        
        # ドラッグエンターイベントを作成
        event = MagicMock(spec=QDragEnterEvent)
        event.mimeData.return_value = mime_data
        
        # イベントを処理
        self.drop_area.dragEnterEvent(event)
        
        # イベントが受け入れられたことを確認
        event.acceptProposedAction.assert_called_once()

    @patch('os.path.isfile')
    @patch('os.path.isdir')
    def test_dragEnterEvent_dirs(self, mock_isdir, mock_isfile):
        """ディレクトリのドラッグエンターイベントのテスト"""
        # ディレクトリパスのモックを設定
        mock_isfile.return_value = False
        mock_isdir.return_value = True
        
        # MimeDataを作成
        mime_data = QMimeData()
        urls = [QUrl.fromLocalFile("/fake/dir/path")]
        mime_data.setUrls(urls)
        
        # ドラッグエンターイベントを作成
        event = MagicMock(spec=QDragEnterEvent)
        event.mimeData.return_value = mime_data
        
        # イベントを処理
        self.drop_area.dragEnterEvent(event)
        
        # イベントが受け入れられたことを確認
        event.acceptProposedAction.assert_called_once()

    @patch('os.path.isfile')
    @patch('os.path.isdir')
    def test_dragEnterEvent_reject(self, mock_isdir, mock_isfile):
        """非対応アイテムのドラッグエンターイベントのテスト"""
        # ファイルのみ許可するエリアを作成
        files_only = DropArea(accept_files=True, accept_dirs=False)
        
        # ディレクトリパスのモックを設定
        mock_isfile.return_value = False
        mock_isdir.return_value = True
        
        # MimeDataを作成
        mime_data = QMimeData()
        urls = [QUrl.fromLocalFile("/fake/dir/path")]
        mime_data.setUrls(urls)
        
        # ドラッグエンターイベントを作成
        event = MagicMock(spec=QDragEnterEvent)
        event.mimeData.return_value = mime_data
        
        # イベントを処理
        files_only.dragEnterEvent(event)
        
        # イベントが拒否されたことを確認
        event.ignore.assert_called_once()
        
        files_only.deleteLater()

    def test_dragLeaveEvent(self):
        """ドラッグリーブイベントのテスト"""
        # テスト前に背景をハイライト状態に設定
        self.drop_area.set_highlight_background()
        palette_before = self.drop_area.palette()
        
        # イベントを作成して処理
        event = MagicMock()
        self.drop_area.dragLeaveEvent(event)
        
        # 背景が通常状態に戻ったことを確認
        palette_after = self.drop_area.palette()
        self.assertEqual(palette_after.color(palette_after.Window).name(), "#f0f0f0")

    @patch('os.path.isfile')
    @patch('os.path.isdir')
    def test_dropEvent_files(self, mock_isdir, mock_isfile):
        """ファイルのドロップイベントのテスト"""
        # ファイルパスのモックを設定
        mock_isfile.return_value = True
        mock_isdir.return_value = False
        
        # MimeDataを作成
        mime_data = QMimeData()
        urls = [
            QUrl.fromLocalFile("/fake/file/path1.txt"),
            QUrl.fromLocalFile("/fake/file/path2.txt")
        ]
        mime_data.setUrls(urls)
        
        # ドロップイベントを作成
        event = MagicMock(spec=QDropEvent)
        event.mimeData.return_value = mime_data
        
        # イベントを処理
        self.drop_area.dropEvent(event)
        
        # シグナルが発行されたことを確認
        self.drop_area.files_dropped.emit.assert_called_once()
        # 最初の呼び出しの最初の引数をチェック
        args, _ = self.drop_area.files_dropped.emit.call_args
        dropped_files = args[0]
        self.assertEqual(len(dropped_files), 2)
        self.assertEqual(dropped_files[0], "/fake/file/path1.txt")
        self.assertEqual(dropped_files[1], "/fake/file/path2.txt")
        
        # イベントが受け入れられたことを確認
        event.acceptProposedAction.assert_called_once()

    @patch('os.path.isfile')
    @patch('os.path.isdir')
    def test_dropEvent_dirs(self, mock_isdir, mock_isfile):
        """ディレクトリのドロップイベントのテスト"""
        # ディレクトリパスのモックを設定
        mock_isfile.return_value = False
        mock_isdir.return_value = True
        
        # MimeDataを作成
        mime_data = QMimeData()
        urls = [
            QUrl.fromLocalFile("/fake/dir/path1"),
            QUrl.fromLocalFile("/fake/dir/path2")
        ]
        mime_data.setUrls(urls)
        
        # ドロップイベントを作成
        event = MagicMock(spec=QDropEvent)
        event.mimeData.return_value = mime_data
        
        # イベントを処理
        self.drop_area.dropEvent(event)
        
        # シグナルが発行されたことを確認
        self.drop_area.directories_dropped.emit.assert_called_once()
        # 最初の呼び出しの最初の引数をチェック
        args, _ = self.drop_area.directories_dropped.emit.call_args
        dropped_dirs = args[0]
        self.assertEqual(len(dropped_dirs), 2)
        self.assertEqual(dropped_dirs[0], "/fake/dir/path1")
        self.assertEqual(dropped_dirs[1], "/fake/dir/path2")
        
        # イベントが受け入れられたことを確認
        event.acceptProposedAction.assert_called_once()

    def test_set_instruction_text(self):
        """説明テキスト設定のテスト"""
        test_text = "テスト用の説明テキスト"
        self.drop_area.set_instruction_text(test_text)
        self.assertEqual(self.drop_area.label.text(), test_text)


class TestFilesDropWidget(unittest.TestCase):
    """FilesDropWidgetクラスのテスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        # QApplicationを初期化
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()
        
        # テスト対象のインスタンスを作成
        self.accept_extensions = ['.jpg', '.png']
        self.files_drop = FilesDropWidget(accept_extensions=self.accept_extensions)
        
        # シグナルをモック化
        self.files_drop.files_dropped = MagicMock()

    def tearDown(self):
        """テスト後のクリーンアップ"""
        self.files_drop.deleteLater()

    def test_init(self):
        """初期化のテスト"""
        self.assertEqual(self.files_drop.accept_extensions, self.accept_extensions)
        
        # 拡張子が説明テキストに含まれているか
        instruction_text = self.files_drop.drop_area.label.text()
        for ext in self.accept_extensions:
            self.assertIn(ext, instruction_text)

    def test_on_files_dropped_with_filter(self):
        """拡張子フィルタありの場合のファイルドロップテスト"""
        # ドロップされるファイルパス（一部は受け入れられない拡張子）
        file_paths = [
            "/fake/path/image1.jpg",
            "/fake/path/image2.png",
            "/fake/path/document.txt",
            "/fake/path/image3.gif"
        ]
        
        # ファイルドロップを処理
        self.files_drop.on_files_dropped(file_paths)
        
        # シグナルが発行されたことを確認
        self.files_drop.files_dropped.emit.assert_called_once()
        
        # 受け入れられる拡張子のファイルのみが含まれているか
        args, _ = self.files_drop.files_dropped.emit.call_args
        filtered_files = args[0]
        self.assertEqual(len(filtered_files), 2)
        self.assertIn("/fake/path/image1.jpg", filtered_files)
        self.assertIn("/fake/path/image2.png", filtered_files)
        self.assertNotIn("/fake/path/document.txt", filtered_files)
        self.assertNotIn("/fake/path/image3.gif", filtered_files)

    def test_on_files_dropped_without_filter(self):
        """拡張子フィルタなしの場合のファイルドロップテスト"""
        # フィルタなしのインスタンスを作成
        files_drop = FilesDropWidget(accept_extensions=None)
        files_drop.files_dropped = MagicMock()
        
        # ドロップされるファイルパス
        file_paths = [
            "/fake/path/image1.jpg",
            "/fake/path/image2.png",
            "/fake/path/document.txt",
            "/fake/path/image3.gif"
        ]
        
        # ファイルドロップを処理
        files_drop.on_files_dropped(file_paths)
        
        # シグナルが発行されたことを確認
        files_drop.files_dropped.emit.assert_called_once()
        
        # 全てのファイルが含まれているか
        args, _ = files_drop.files_dropped.emit.call_args
        all_files = args[0]
        self.assertEqual(len(all_files), 4)
        
        files_drop.deleteLater()


class TestDirectoriesDropWidget(unittest.TestCase):
    """DirectoriesDropWidgetクラスのテスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        # QApplicationを初期化
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()
        
        # テスト対象のインスタンスを作成
        self.dirs_drop = DirectoriesDropWidget()
        
        # シグナルをモック化
        self.dirs_drop.directories_dropped = MagicMock()

    def tearDown(self):
        """テスト後のクリーンアップ"""
        self.dirs_drop.deleteLater()

    def test_init(self):
        """初期化のテスト"""
        # ドロップエリアがディレクトリのみを受け付けるか
        self.assertFalse(self.dirs_drop.drop_area.accept_files)
        self.assertTrue(self.dirs_drop.drop_area.accept_dirs)
        
        # 説明テキストが設定されているか
        instruction_text = self.dirs_drop.drop_area.label.text()
        self.assertIn("フォルダ", instruction_text)

    def test_directories_dropped_signal_connection(self):
        """シグナル接続のテスト"""
        # テスト用のディレクトリパス
        dir_paths = ["/fake/dir/path1", "/fake/dir/path2"]
        
        # ドロップエリアのシグナルを発行
        self.dirs_drop.drop_area.directories_dropped.emit(dir_paths)
        
        # ウィジェットのシグナルが発行されたことを確認
        self.dirs_drop.directories_dropped.emit.assert_called_once_with(dir_paths)


class TestDragDropManager(unittest.TestCase):
    """DragDropManagerクラスのテスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        # QApplicationを初期化
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()
        
        # テスト用のウィジェットを作成
        self.widget = QWidget()
        
        # テスト用のコールバック
        self.callback = MagicMock()

    def tearDown(self):
        """テスト後のクリーンアップ"""
        self.widget.deleteLater()

    def test_add_drag_drop_support(self):
        """ドラッグ&ドロップサポート追加のテスト"""
        # サポートを追加
        result = DragDropManager.add_drag_drop_support(
            self.widget,
            self.callback,
            accept_files=True,
            accept_dirs=True
        )
        
        # 追加が成功したことを確認
        self.assertTrue(result)
        
        # ウィジェットがドロップを受け入れるようになったことを確認
        self.assertTrue(self.widget.acceptDrops())
        
        # ドラッグ＆ドロップ関連のイベントハンドラが追加されたことを確認
        self.assertTrue(hasattr(self.widget, 'dragEnterEvent'))
        self.assertTrue(hasattr(self.widget, 'dragLeaveEvent'))
        self.assertTrue(hasattr(self.widget, 'dragMoveEvent'))
        self.assertTrue(hasattr(self.widget, 'dropEvent'))

    @patch('os.path.isfile')
    @patch('os.path.isdir')
    def test_widget_drag_enter_event(self, mock_isdir, mock_isfile):
        """ウィジェットのドラッグエンターイベントのテスト"""
        # サポートを追加
        DragDropManager.add_drag_drop_support(
            self.widget,
            self.callback,
            accept_files=True,
            accept_dirs=True
        )
        
        # ファイルパスのモックを設定
        mock_isfile.return_value = True
        mock_isdir.return_value = False
        
        # MimeDataを作成
        mime_data = QMimeData()
        urls = [QUrl.fromLocalFile("/fake/file/path.txt")]
        mime_data.setUrls(urls)
        
        # ドラッグエンターイベントを作成
        event = MagicMock(spec=QDragEnterEvent)
        event.mimeData.return_value = mime_data
        
        # イベントを処理
        self.widget.dragEnterEvent(event)
        
        # イベントが受け入れられたことを確認
        event.acceptProposedAction.assert_called_once()

    @patch('os.path.isfile')
    @patch('os.path.isdir')
    def test_widget_drop_event(self, mock_isdir, mock_isfile):
        """ウィジェットのドロップイベントのテスト"""
        # サポートを追加
        DragDropManager.add_drag_drop_support(
            self.widget,
            self.callback,
            accept_files=True,
            accept_dirs=True
        )
        
        # ファイルパスのモックを設定
        mock_isfile.return_value = True
        mock_isdir.return_value = False
        
        # MimeDataを作成
        mime_data = QMimeData()
        urls = [QUrl.fromLocalFile("/fake/file/path.txt")]
        mime_data.setUrls(urls)
        
        # ドロップイベントを作成
        event = MagicMock(spec=QDropEvent)
        event.mimeData.return_value = mime_data
        
        # イベントを処理
        self.widget.dropEvent(event)
        
        # コールバックが呼ばれたことを確認
        self.callback.assert_called_once()
        args, kwargs = self.callback.call_args
        file_paths, item_type = args
        self.assertEqual(len(file_paths), 1)
        self.assertEqual(file_paths[0], "/fake/file/path.txt")
        self.assertEqual(item_type, 'files')
        
        # イベントが受け入れられたことを確認
        event.acceptProposedAction.assert_called_once()

    def test_add_drag_drop_support_non_widget(self):
        """ウィジェット以外にサポート追加を試みるテスト"""
        # ウィジェットではないオブジェクト
        non_widget = object()
        
        # サポートを追加
        result = DragDropManager.add_drag_drop_support(
            non_widget,
            self.callback,
            accept_files=True,
            accept_dirs=True
        )
        
        # 追加が失敗したことを確認
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
