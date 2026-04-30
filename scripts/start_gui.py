#!/usr/bin/env python3
# FocusFlow GUI 启动器（无终端窗口）
import subprocess
import os
import sys

os.environ['QT_QPA_PLATFORM'] = 'cocoa'

gui_code = '''
import sys
import os
os.environ['QT_QPA_PLATFORM'] = 'cocoa'
from PySide6.QtWidgets import QApplication
from gui.dashboard_v2 import DashboardV2
app = QApplication(sys.argv)
w = DashboardV2()
w.show()
sys.exit(app.exec())
'''

# 获取脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)

subprocess.Popen(
    [sys.executable, '-c', gui_code],
    cwd=project_root,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True
)
