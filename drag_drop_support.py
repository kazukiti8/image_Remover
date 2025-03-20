import os
from PyQt5.QtWidgets import QLabel, QFrame, QWidget, QVBoxLayout, QHBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QPalette, QColor


class DropArea(QFrame):
    """ファイルやフォルダのドロップを受け付けるエリア"""
    # ドロップ時に発行されるシグナル
    files_dropped = pyqtSignal(list)  # ファイルパスのリスト
    directories_dropped = pyqtSignal(list)  # ディレクトリパスのリスト
    
    def __init__(self, accept_files=True, accept_dirs=True, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.accept_files = accept_files
        self.accept_dirs = accept_dirs
        
        # 見た目の設定
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.setLineWidth(2)
        self.setMinimumHeight(100)
        self.setMinimumWidth(200)
        
        # 初期状態の色
        self.setAutoFillBackground(True)
        self.set_normal_background()
        
        # レイアウト
        layout = QVBoxLayout()
        
        # ドロップ用の説明ラベル
        self.label = QLabel("ここにファイルやフォルダをドラッグ＆ドロップしてください")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        
        self.setLayout(layout)
    
    def set_normal_background(self):
        """通常時の背景色を設定"""
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        self.setPalette(palette)
    
    def set_highlight_background(self):
        """ドラッグオーバー時の背景色を設定"""
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(200, 220, 255))
        self.setPalette(palette)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """ドラッグされたアイテムがエリアに入った時"""
        mime_data = event.mimeData()
        
        # URLがあるかチェック（ファイルやディレクトリ）
        if mime_data.hasUrls():
            urls = mime_data.urls()
            valid_items = False
            
            for url in urls:
                # ローカルファイルパスに変換
                file_path = url.toLocalFile()
                
                # ファイルかディレクトリか判定
                if os.path.isfile(file_path) and self.accept_files:
                    valid_items = True
                    break
                elif os.path.isdir(file_path) and self.accept_dirs:
                    valid_items = True
                    break
            
            if valid_items:
                # 有効なアイテムがあればドロップを受け入れる
                event.acceptProposedAction()
                self.set_highlight_background()
                return
        
        # 受け入れられないアイテムの場合
        event.ignore()
    
    def dragLeaveEvent(self, event):
        """ドラッグされたアイテムがエリアから出た時"""
        self.set_normal_background()
    
    def dragMoveEvent(self, event):
        """ドラッグされたアイテムがエリア内を移動している時"""
        event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """アイテムがドロップされた時"""
        self.set_normal_background()
        
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            urls = mime_data.urls()
            file_paths = []
            dir_paths = []
            
            for url in urls:
                file_path = url.toLocalFile()
                
                if os.path.isfile(file_path) and self.accept_files:
                    file_paths.append(file_path)
                elif os.path.isdir(file_path) and self.accept_dirs:
                    dir_paths.append(file_path)
            
            # シグナルを発行
            if file_paths:
                self.files_dropped.emit(file_paths)
            if dir_paths:
                self.directories_dropped.emit(dir_paths)
            
            event.acceptProposedAction()
    
    def set_instruction_text(self, text):
        """説明テキストを設定"""
        self.label.setText(text)


class FilesDropWidget(QWidget):
    """ファイルドロップ用ウィジェット"""
    files_dropped = pyqtSignal(list)  # ファイルパスのリスト
    
    def __init__(self, accept_extensions=None, parent=None):
        super().__init__(parent)
        self.accept_extensions = accept_extensions or []  # 受け入れる拡張子のリスト
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        # ドロップエリア
        self.drop_area = DropArea(accept_files=True, accept_dirs=False)
        self.drop_area.files_dropped.connect(self.on_files_dropped)
        
        # 説明テキストを設定
        if self.accept_extensions:
            exts_str = ", ".join(self.accept_extensions)
            self.drop_area.set_instruction_text(f"ここに{exts_str}ファイルをドラッグ＆ドロップしてください")
        
        layout.addWidget(self.drop_area)
        
        self.setLayout(layout)
    
    def on_files_dropped(self, file_paths):
        """ファイルがドロップされた時の処理"""
        # 拡張子フィルタが設定されている場合は絞り込む
        if self.accept_extensions:
            filtered_paths = []
            for path in file_paths:
                ext = os.path.splitext(path)[1].lower()
                if ext in self.accept_extensions:
                    filtered_paths.append(path)
            
            if filtered_paths:
                self.files_dropped.emit(filtered_paths)
        else:
            # フィルタなしの場合はそのまま通知
            self.files_dropped.emit(file_paths)


class DirectoriesDropWidget(QWidget):
    """ディレクトリドロップ用ウィジェット"""
    directories_dropped = pyqtSignal(list)  # ディレクトリパスのリスト
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        # ドロップエリア
        self.drop_area = DropArea(accept_files=False, accept_dirs=True)
        self.drop_area.directories_dropped.connect(self.directories_dropped)
        self.drop_area.set_instruction_text("ここにフォルダをドラッグ＆ドロップしてください")
        
        layout.addWidget(self.drop_area)
        
        self.setLayout(layout)


class DragDropManager:
    """アプリケーション全体のドラッグ&ドロップを管理するクラス"""
    
    @staticmethod
    def add_drag_drop_support(widget, callback, accept_files=True, accept_dirs=True):
        """既存のウィジェットにドラッグ&ドロップサポートを追加"""
        # QWidget継承クラスにのみ有効
        if not isinstance(widget, QWidget):
            return False
        
        # ドロップを受け入れるように設定
        widget.setAcceptDrops(True)
        
        # 元のイベントハンドラを保存
        original_dragEnterEvent = widget.dragEnterEvent if hasattr(widget, 'dragEnterEvent') else None
        original_dragLeaveEvent = widget.dragLeaveEvent if hasattr(widget, 'dragLeaveEvent') else None
        original_dragMoveEvent = widget.dragMoveEvent if hasattr(widget, 'dragMoveEvent') else None
        original_dropEvent = widget.dropEvent if hasattr(widget, 'dropEvent') else None
        
        # イベントハンドラをオーバーライド
        def new_dragEnterEvent(self, event):
            mime_data = event.mimeData()
            
            if mime_data.hasUrls():
                urls = mime_data.urls()
                valid_items = False
                
                for url in urls:
                    file_path = url.toLocalFile()
                    
                    if os.path.isfile(file_path) and accept_files:
                        valid_items = True
                        break
                    elif os.path.isdir(file_path) and accept_dirs:
                        valid_items = True
                        break
                
                if valid_items:
                    event.acceptProposedAction()
                    return
            
            # 元のイベントハンドラがあれば呼び出す
            if original_dragEnterEvent:
                original_dragEnterEvent(event)
            else:
                event.ignore()
        
        def new_dragLeaveEvent(self, event):
            # 元のイベントハンドラがあれば呼び出す
            if original_dragLeaveEvent:
                original_dragLeaveEvent(event)
        
        def new_dragMoveEvent(self, event):
            # 元のイベントハンドラがあれば呼び出す
            if original_dragMoveEvent:
                original_dragMoveEvent(event)
            else:
                event.acceptProposedAction()
        
        def new_dropEvent(self, event):
            mime_data = event.mimeData()
            if mime_data.hasUrls():
                urls = mime_data.urls()
                file_paths = []
                dir_paths = []
                
                for url in urls:
                    file_path = url.toLocalFile()
                    
                    if os.path.isfile(file_path) and accept_files:
                        file_paths.append(file_path)
                    elif os.path.isdir(file_path) and accept_dirs:
                        dir_paths.append(file_path)
                
                # コールバックを呼び出す
                if file_paths and accept_files:
                    callback(file_paths, 'files')
                if dir_paths and accept_dirs:
                    callback(dir_paths, 'directories')
                
                event.acceptProposedAction()
                return
            
            # 元のイベントハンドラがあれば呼び出す
            if original_dropEvent:
                original_dropEvent(event)
            else:
                event.ignore()
        
        # イベントハンドラをモンキーパッチ
        widget.dragEnterEvent = lambda event: new_dragEnterEvent(widget, event)
        widget.dragLeaveEvent = lambda event: new_dragLeaveEvent(widget, event)
        widget.dragMoveEvent = lambda event: new_dragMoveEvent(widget, event)
        widget.dropEvent = lambda event: new_dropEvent(widget, event)
        
        return True
