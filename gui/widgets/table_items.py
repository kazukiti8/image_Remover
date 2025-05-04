# gui/widgets/table_items.py
import re
from datetime import datetime
from PySide6.QtWidgets import QTableWidgetItem
from typing import Any # ★ typing をインポート ★

# === カスタム QTableWidgetItem サブクラス定義 ===

class NumericTableWidgetItem(QTableWidgetItem):
    """数値としてソート可能なテーブルアイテム"""
    def __lt__(self, other: Any) -> bool: # other は QTableWidgetItem 相当だが Any で受ける
        # テキストをfloatに変換して比較。変換できない場合は負の無限大として扱う。
        try:
            # self.text() と other.text() の戻り値は str
            self_text: str = self.text()
            other_text: str = other.text()
            # isdigit() などで数値かチェックする方がより安全
            self_value: float = float(self_text) if self_text and self_text not in ["N/A", "読込エラー", "エラー"] else -float('inf')
            other_value: float = float(other_text) if other_text and other_text not in ["N/A", "読込エラー", "エラー"] else -float('inf')
            return self_value < other_value
        except (ValueError, TypeError):
            # float変換に失敗した場合はデフォルトの比較 (__lt__) を使用
            # other が QTableWidgetItem であることを期待
            if isinstance(other, QTableWidgetItem):
                return super().__lt__(other)
            return NotImplemented # 比較できない場合

class FileSizeTableWidgetItem(QTableWidgetItem):
    """ファイルサイズ (KB, MB, GB) としてソート可能なテーブルアイテム"""
    def __init__(self, text: str):
        super().__init__(text)
        self.bytes_value: int = self._parse_size(text)

    def _parse_size(self, size_str: str) -> int:
        """ファイルサイズ文字列をバイト単位の数値に変換"""
        size_str = size_str.strip().upper()
        num_part = re.match(r"([\d\.]+)", size_str)
        num: float = float(num_part.group(1)) if num_part else 0.0
        if "GB" in size_str: return int(num * (1024**3))
        elif "MB" in size_str: return int(num * (1024**2))
        elif "KB" in size_str: return int(num * 1024)
        elif "B" in size_str: return int(num)
        else: return 0

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, FileSizeTableWidgetItem):
            return self.bytes_value < other.bytes_value
        elif isinstance(other, QTableWidgetItem):
            return super().__lt__(other)
        return NotImplemented

class DateTimeTableWidgetItem(QTableWidgetItem):
    """日時文字列 ('YYYY/MM/DD HH:MM') としてソート可能なテーブルアイテム"""
    def __init__(self, text: str):
        super().__init__(text)
        self.timestamp: float = self._parse_datetime(text)

    def _parse_datetime(self, datetime_str: str) -> float:
        """日時文字列をタイムスタンプ (float) に変換"""
        try:
            return datetime.strptime(datetime_str, '%Y/%m/%d %H:%M').timestamp()
        except (ValueError, TypeError):
            return -float('inf') # 比較のために最小値に近い値を返す

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, DateTimeTableWidgetItem):
            return self.timestamp < other.timestamp
        elif isinstance(other, QTableWidgetItem):
            return super().__lt__(other)
        return NotImplemented

class ResolutionTableWidgetItem(QTableWidgetItem):
    """解像度文字列 ('WxH') としてソート可能なテーブルアイテム (ピクセル数で比較)"""
    def __init__(self, text: str):
        super().__init__(text)
        self.pixels: int = self._parse_resolution(text)

    def _parse_resolution(self, res_str: str) -> int:
        """解像度文字列を総ピクセル数 (int) に変換"""
        parts: List[str] = res_str.lower().split('x')
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]) * int(parts[1])
        else:
            return 0

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, ResolutionTableWidgetItem):
            return self.pixels < other.pixels
        elif isinstance(other, QTableWidgetItem):
            return super().__lt__(other)
        return NotImplemented

# 型ヒントのために List をインポート
from typing import List
