# gui/widgets/table_items.py
import re
from datetime import datetime
from PySide6.QtWidgets import QTableWidgetItem

# === カスタム QTableWidgetItem サブクラス定義 ===
# これらのクラスは、テーブルのソート機能を正しく動作させるために使用します。

class NumericTableWidgetItem(QTableWidgetItem):
    """数値としてソート可能なテーブルアイテム"""
    def __lt__(self, other):
        # テキストをfloatに変換して比較。変換できない場合は負の無限大として扱う。
        try:
            self_value = float(self.text()) if self.text() and self.text() not in ["N/A", "読込エラー", "エラー"] else -float('inf')
            other_value = float(other.text()) if other.text() and other.text() not in ["N/A", "読込エラー", "エラー"] else -float('inf')
            return self_value < other_value
        except (ValueError, TypeError):
            # float変換に失敗した場合はデフォルトの比較 (__lt__) を使用
            return super().__lt__(other)

class FileSizeTableWidgetItem(QTableWidgetItem):
    """ファイルサイズ (KB, MB, GB) としてソート可能なテーブルアイテム"""
    def __init__(self, text):
        super().__init__(text)
        # アイテム作成時にバイト単位の値を計算して保持
        self.bytes_value = self._parse_size(text)

    def _parse_size(self, size_str):
        """ファイルサイズ文字列 (例: "10.5 MB") をバイト単位の数値に変換"""
        size_str = size_str.strip().upper()
        num_part = re.match(r"([\d\.]+)", size_str)
        num = float(num_part.group(1)) if num_part else 0
        if "GB" in size_str:
            return int(num * (1024**3))
        elif "MB" in size_str:
            return int(num * (1024**2))
        elif "KB" in size_str:
            return int(num * 1024)
        elif "B" in size_str:
            return int(num)
        else:
            return 0 # 不明な形式

    def __lt__(self, other):
        # 他のアイテムも FileSizeTableWidgetItem ならバイト値で比較
        if isinstance(other, FileSizeTableWidgetItem):
            return self.bytes_value < other.bytes_value
        else:
            # そうでなければデフォルトの比較
            return super().__lt__(other)

class DateTimeTableWidgetItem(QTableWidgetItem):
    """日時文字列 ('YYYY/MM/DD HH:MM') としてソート可能なテーブルアイテム"""
    def __init__(self, text):
        super().__init__(text)
        # アイテム作成時にタイムスタンプに変換して保持
        self.timestamp = self._parse_datetime(text)

    def _parse_datetime(self, datetime_str):
        """日時文字列をタイムスタンプ (float) に変換"""
        try:
            # 指定されたフォーマットで日時に変換し、タイムスタンプを取得
            return datetime.strptime(datetime_str, '%Y/%m/%d %H:%M').timestamp()
        except (ValueError, TypeError):
            # 変換できない場合は負の無限大として扱う
            return -float('inf')

    def __lt__(self, other):
        # 他のアイテムも DateTimeTableWidgetItem ならタイムスタンプで比較
        if isinstance(other, DateTimeTableWidgetItem):
            return self.timestamp < other.timestamp
        else:
            # そうでなければデフォルトの比較
            return super().__lt__(other)

class ResolutionTableWidgetItem(QTableWidgetItem):
    """解像度文字列 ('WxH') としてソート可能なテーブルアイテム (ピクセル数で比較)"""
    def __init__(self, text):
        super().__init__(text)
        # アイテム作成時に総ピクセル数を計算して保持
        self.pixels = self._parse_resolution(text)

    def _parse_resolution(self, res_str):
        """解像度文字列を総ピクセル数 (int) に変換"""
        # "x" で分割し、両方が数字なら計算
        parts = res_str.lower().split('x')
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]) * int(parts[1])
        else:
            # 変換できない場合は 0 として扱う
            return 0

    def __lt__(self, other):
        # 他のアイテムも ResolutionTableWidgetItem ならピクセル数で比較
        if isinstance(other, ResolutionTableWidgetItem):
            return self.pixels < other.pixels
        else:
            # そうでなければデフォルトの比較
            return super().__lt__(other)
