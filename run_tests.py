#!/usr/bin/env python
import os
import sys
import pytest

if __name__ == "__main__":
    print("テストディレクトリ内のファイル:")
    test_dir = os.path.join(os.path.dirname(__file__), 'tests')
    if os.path.exists(test_dir):
        for file in os.listdir(test_dir):
            print(f"  - {file}")
    else:
        print(f"テストディレクトリが見つかりません: {test_dir}")
    
    print("\nテスト実行開始...")
    sys.exit(pytest.main(["-v", "tests/"]))