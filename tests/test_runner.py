#!/usr/bin/env python3
"""
画像クリーンアップシステムのテストランナー
全テストを一括で実行します
"""

import unittest
import sys
import os


def run_all_tests():
    """全テストを実行"""
    # テストディレクトリを作成していない場合はカレントディレクトリを使用
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    # テストを検出して実行
    test_suite = unittest.defaultTestLoader.discover(
        start_dir=test_dir,
        pattern='test_*.py'
    )
    
    # テスト実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 失敗したテストがあれば終了コード1を返す
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
