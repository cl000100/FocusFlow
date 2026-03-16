#!/usr/bin/env python3
"""
测试脚本：检查 service_daemon 在新环境中是否能正常运行
"""

import sys
import os
import traceback

print("=" * 60)
print("FocusFlow 服务测试脚本")
print("=" * 60)

# 测试 1: 检查 Python 版本
print(f"\n[TEST 1] Python 版本: {sys.version}")

# 测试 2: 检查平台
import platform
print(f"[TEST 2] 平台: {platform.system()}")

# 测试 3: 检查当前目录
print(f"[TEST 3] 当前目录: {os.getcwd()}")

# 测试 4: 检查 sys.path
print(f"[TEST 4] sys.path: {sys.path}")

# 测试 5: 导入数据库模块
print("\n[TEST 5] 导入数据库模块...")
try:
    from core.database import init_db, get_connection
    print("✅ 数据库模块导入成功")
except Exception as e:
    print(f"❌ 数据库模块导入失败: {e}")
    print(traceback.format_exc())
    sys.exit(1)

# 测试 6: 初始化数据库
print("\n[TEST 6] 初始化数据库...")
try:
    init_db()
    print("✅ 数据库初始化成功")
except Exception as e:
    print(f"❌ 数据库初始化失败: {e}")
    print(traceback.format_exc())
    sys.exit(1)

# 测试 7: 导入 app_detector
print("\n[TEST 7] 导入 app_detector...")
try:
    from modules.app_detector import get_active_app_info
    print("✅ app_detector 导入成功")
except Exception as e:
    print(f"❌ app_detector 导入失败: {e}")
    print(traceback.format_exc())
    sys.exit(1)

# 测试 8: 检测当前活动窗口
print("\n[TEST 8] 检测当前活动窗口...")
try:
    app_name, file_path = get_active_app_info()
    print(f"✅ 检测到: {app_name} | {file_path}")
except Exception as e:
    print(f"❌ 检测失败: {e}")
    print(traceback.format_exc())

# 测试 9: 检查 Windows 特定依赖
if platform.system() == "Windows":
    print("\n[TEST 9] 检查 Windows 依赖...")
    try:
        import win32gui
        print("✅ win32gui 导入成功")
    except Exception as e:
        print(f"❌ win32gui 导入失败: {e}")
    
    try:
        import win32process
        print("✅ win32process 导入成功")
    except Exception as e:
        print(f"❌ win32process 导入失败: {e}")
    
    try:
        import win32api
        print("✅ win32api 导入成功")
    except Exception as e:
        print(f"❌ win32api 导入失败: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
