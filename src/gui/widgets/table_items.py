# gui/widgets/table_items.py
import re
from datetime import datetime
from PySide6.QtWidgets import QTableWidgetItem
from typing import Any, List # ★ List をインポート ★

# === カスタム QTableWidgetItem サブクラス定義 ===

class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other: Any) -> bool:
        try:
            self_text: str = self.text()
            other_text: str = other.text()

            # "完全一致（重複）" のような文字列を特別扱いする
            self_is_special_string = self_text == "完全一致（重複）"
            other_is_special_string = other_text == "完全一致（重複）"

            # 両方とも特別文字列の場合、テキストで比較（同じなので等価）
            if self_is_special_string and other_is_special_string:
                return False # 同じ値なので self < other は False

            # 片方だけが特別文字列の場合の処理 (例: 特別文字列を最大値または最小値として扱う)
            # ここでは例として、特別文字列を数値よりも「大きい」ものとして扱います
            # (ソート順を調整したい場合は、ここのロジックを変更してください)
            if self_is_special_string:
                return False # self が特別文字列なら、other (数値のはず) より小さくはない
            if other_is_special_string:
                return True  # other が特別文字列なら、self (数値のはず) は other より小さい

            # 通常の数値比較
            self_value: float = float(self_text) if self_text and self_text not in ["N/A", "読込エラー", "エラー", "削除済?"] else -float('inf')
            other_value: float = float(other_text) if other_text and other_text not in ["N/A", "読込エラー", "エラー", "削除済?"] else -float('inf')

            if self_value == -float('inf') and other_value == -float('inf'):
                 return self_text < other_text # 両方エラー値ならテキスト比較
            return self_value < other_value
        except (ValueError, TypeError):
            # 型エラーや値エラーが発生した場合 (例: other.text() が予期しない形式)
            if isinstance(other, QTableWidgetItem):
                # ★★★ 修正箇所 ★★★
                return QTableWidgetItem.__lt__(self, other)
            return NotImplemented

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
        else: return -1 # エラーや N/A は最小値扱い

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, FileSizeTableWidgetItem):
            # 両方がエラー値の場合、テキストで比較
            if self.bytes_value == -1 and other.bytes_value == -1:
                return self.text() < other.text()
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
            # 'N/A', 'エラー' など数値以外は最小値扱い
            if not any(c.isdigit() for c in datetime_str):
                 return -float('inf')
            return datetime.strptime(datetime_str, '%Y/%m/%d %H:%M').timestamp()
        except (ValueError, TypeError):
            return -float('inf')

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, DateTimeTableWidgetItem):
             # 両方がエラー値の場合、テキストで比較
            if self.timestamp == -float('inf') and other.timestamp == -float('inf'):
                return self.text() < other.text()
            return self.timestamp < other.timestamp
        elif isinstance(other, QTableWidgetItem):
            return super().__lt__(other)
        return NotImplemented

# ★★★ Exif日時 ('YYYY:MM:DD HH:MM:SS') 用のテーブルアイテム ★★★
class ExifDateTimeTableWidgetItem(QTableWidgetItem):
    """Exif日時文字列 ('YYYY:MM:DD HH:MM:SS') としてソート可能なテーブルアイテム"""
    def __init__(self, text: str):
        super().__init__(text)
        self.timestamp: float = self._parse_exif_datetime(text)

    def _parse_exif_datetime(self, datetime_str: str) -> float:
        """Exif日時文字列をタイムスタンプ (float) に変換"""
        try:
            # 'N/A', 'エラー' など数値以外は最小値扱い
            if not any(c.isdigit() for c in datetime_str):
                 return -float('inf')
            # Exifフォーマットでパース
            return datetime.strptime(datetime_str, '%Y:%m:%d %H:%M:%S').timestamp()
        except (ValueError, TypeError):
            # print(f"デバッグ: Exif日時パースエラー: {datetime_str}")
            return -float('inf') # パース失敗も最小値

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, ExifDateTimeTableWidgetItem):
            # 両方がエラー値の場合、テキストで比較
            if self.timestamp == -float('inf') and other.timestamp == -float('inf'):
                return self.text() < other.text()
            return self.timestamp < other.timestamp
        elif isinstance(other, QTableWidgetItem):
            # 他の型との比較はデフォルトに任せる
            return super().__lt__(other)
        return NotImplemented
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

class ResolutionTableWidgetItem(QTableWidgetItem):
    """解像度文字列 ('WxH') としてソート可能なテーブルアイテム (ピクセル数で比較)"""
    def __init__(self, text: str):
        super().__init__(text)
        self.pixels: int = self._parse_resolution(text)

    def _parse_resolution(self, res_str: str) -> int:
        """解像度文字列を総ピクセル数 (int) に変換"""
        parts: List[str] = res_str.lower().split('x')
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            try:
                return int(parts[0]) * int(parts[1])
            except ValueError:
                return -1 # 大きすぎる数値などでエラーになる場合
        else:
            return -1 # エラーや N/A は最小値扱い

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, ResolutionTableWidgetItem):
             # 両方がエラー値の場合、テキストで比較
            if self.pixels == -1 and other.pixels == -1:
                return self.text() < other.text()
            return self.pixels < other.pixels
        elif isinstance(other, QTableWidgetItem):
            return super().__lt__(other)
        return NotImplemented

