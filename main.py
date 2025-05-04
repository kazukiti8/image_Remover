# main.py
import sys
from PySide6.QtWidgets import QApplication
# guiパッケージのmain_windowモジュールからImageCleanerWindowクラスをインポート
from gui.main_window import ImageCleanerWindow

if __name__ == '__main__':
    # アプリケーションインスタンスを作成
    app = QApplication(sys.argv)

    # メインウィンドウのインスタンスを作成
    window = ImageCleanerWindow()

    # GUIのテスト用にダミーデータを表示したい場合は、以下のコメントを解除
    # ※ populate_dummy_data 関数が ImageCleanerWindow クラス内に定義されている場合
    # window.populate_dummy_data()

    # ウィンドウを表示
    window.show()

    # アプリケーションのイベントループを開始
    sys.exit(app.exec())