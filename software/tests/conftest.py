"""pytest 配置：让 tests/ 能 import software/ 下的模块。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
