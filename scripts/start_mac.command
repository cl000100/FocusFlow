#!/bin/bash
# FocusFlow macOS 启动脚本
# 双击此文件即可启动（无终端窗口）

# 获取脚本所在目录，并切换到项目根目录
SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"
cd "$PROJECT_ROOT"

# 停止旧进程
pkill -f "service_daemon.py" 2>/dev/null
pkill -f "DashboardV2" 2>/dev/null
sleep 1

# 启动后台服务
./venv/bin/python service_daemon.py > /dev/null 2>&1 &
sleep 2

# 使用 Python 启动 GUI（无终端窗口）
./venv/bin/python scripts/start_gui.py &

echo "FocusFlow 已启动"
