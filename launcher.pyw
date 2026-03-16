#!/usr/bin/env python3
"""
Windows 专用启动器 - 无窗口残留版本
使用方法：双击 launcher.pyw 启动（注意是 .pyw 扩展名）

.pyw 文件在 Windows 上运行不会打开控制台窗口
"""

import subprocess
import sys
import os
import time
import traceback

def main():
    # 设置错误日志文件
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launcher_error.log")
    # 获取项目根目录
    if getattr(sys, 'frozen', False):
        # 如果是打包后的 exe
        PROJECT_ROOT = os.path.dirname(sys.executable)
    else:
        PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    
    os.chdir(PROJECT_ROOT)
    
    # 首次启动检查：确保用户数据目录存在
    from core.database import ensure_user_data_dir, get_db_path, get_user_data_dir
    import sqlite3
    
    try:
        # 确保用户数据目录存在
        user_data_dir = ensure_user_data_dir()
        
        # 检查是否是首次启动（数据库不存在）
        db_path = get_db_path()
        is_first_run = not os.path.exists(db_path)
        
        if is_first_run:
            # 首次启动，显示欢迎消息
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, 
                f"欢迎使用 FocusFlow！\n\n"
                f"这是首次启动，程序将在以下位置创建数据库：\n"
                f"{db_path}\n\n"
                f"你可以在设置中随时更改数据库位置。",
                "FocusFlow 欢迎", 
                64
            )
    except Exception as e:
        # 如果目录创建失败，记录错误但继续（会降级到程序目录）
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"用户目录创建警告：{str(e)}\n")
            f.write("将使用程序目录存储数据\n\n")
    
    # 检查虚拟环境
    venv_python = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        python_exe = venv_python
    else:
        python_exe = sys.executable
    
    # 检查后台服务是否已在运行（防止重复启动）
    import psutil
    service_running = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            # 检查是否是 service_daemon 进程，且不是当前进程
            if ('service_daemon.py' in cmdline or 'service_daemon.exe' in cmdline) and proc.info['pid'] != os.getpid():
                service_running = True
                print(f"ℹ️  后台服务已在运行 (PID: {proc.info['pid']})")
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if not service_running:
        print("🚀 启动后台服务...")
        # 启动后台服务（无窗口）
        if getattr(sys, 'frozen', False):
            # 打包后的环境，启动 service_daemon.exe
            service_exe = os.path.join(PROJECT_ROOT, "service_daemon.exe")
            subprocess.Popen(
                [service_exe],
                creationflags=subprocess.CREATE_NO_WINDOW,
                cwd=PROJECT_ROOT
            )
        else:
            # 开发环境，启动 service_daemon.py
            subprocess.Popen(
                [python_exe, "service_daemon.py"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                cwd=PROJECT_ROOT
            )
        # 等待服务启动
        time.sleep(1)
        print("✅ 后台服务已启动")
    else:
        print("✅ 后台服务已在运行")
    
    # 启动 GUI
    try:
        from gui.dashboard_v2 import DashboardV2
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        
        # 启用高 DPI 支持
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        
        app = QApplication(sys.argv)
        app.setApplicationName("FocusFlow")
        
        # 创建主窗口
        window = DashboardV2()
        window.show()
        
        # 运行事件循环
        sys.exit(app.exec())
    except Exception as e:
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"错误：{str(e)}\n\n")
            f.write(traceback.format_exc())
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, f"启动失败：{str(e)}\n\n详细错误已写入：{log_file}", "FocusFlow 错误", 16)
        raise


if __name__ == "__main__":
    main()
