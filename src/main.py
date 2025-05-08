# main.py
import sys
import os # ★ os モジュールをインポート ★
from PySide6.QtWidgets import QApplication
from gui.main_window import ImageCleanerWindow
from utils.config_handler import load_settings # ★ 設定読み込み関数をインポート ★

# ★ スタイルシート読み込み関数 (main_window から移動/コピー) ★
def load_stylesheet(filename: str) -> str:
    """指定されたファイル名のスタイルシートを読み込む"""
    # スタイルシートファイルのパスを決定 (main.py基準)
    basedir = os.path.dirname(__file__) # main.py があるディレクトリ
    style_path = os.path.join(basedir, "gui", "styles", filename)
    # PyInstaller 対応 (オプション)
    if not os.path.exists(style_path) and hasattr(sys, '_MEIPASS'):
         style_path = os.path.join(sys._MEIPASS, "gui", "styles", filename)

    if os.path.exists(style_path):
        try:
            with open(style_path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            print(f"警告: スタイルシートの読み込みに失敗 ({filename}): {e}")
    else:
        print(f"警告: スタイルシートファイルが見つかりません: {style_path}")
    return ""

# ★ アプリケーション起動関数 (任意) ★
def run_app():
    app = QApplication(sys.argv)

    # --- 設定を読み込み、初期テーマを適用 ---
    settings = load_settings()
    initial_theme = settings.get('theme', 'light') # デフォルトは light
    qss_filename = f"{initial_theme}.qss"
    stylesheet = load_stylesheet(qss_filename)
    if stylesheet:
        app.setStyleSheet(stylesheet)
        print(f"初期テーマ '{initial_theme}' を適用しました。")
    else:
        print(f"初期テーマ '{initial_theme}' のスタイルシートが見つかりません。デフォルトスタイルを使用します。")
    # ------------------------------------

    window = ImageCleanerWindow() # 設定はウィンドウ内で再度読み込まれる
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    run_app() # アプリケーション起動関数を呼び出す
