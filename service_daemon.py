import time
import datetime
import os
import platform
import sys
import traceback

# 导入 Windows 相关模块
win32api = None
win32gui = None
win32process = None

if platform.system() == "Windows":
    try:
        import win32api
        import win32gui
        import win32process
        print("[DEBUG] Windows modules imported successfully")
    except Exception as e:
        print(f"[ERROR] Failed to import Windows modules: {e}")
        print(traceback.format_exc())
        print("[ERROR] Exiting due to missing Windows dependencies...")
        input("按 Enter 键退出...")
        sys.exit(1)

# 添加调试信息
print(f"[DEBUG] Python version: {sys.version}")
print(f"[DEBUG] Platform: {platform.system()}")
print(f"[DEBUG] Current directory: {os.getcwd()}")
print(f"[DEBUG] sys.path: {sys.path}")

try:
    from core.database import init_db, get_connection
    print("[DEBUG] Successfully imported database modules")
except Exception as e:
    print(f"[ERROR] Failed to import database modules: {e}")
    print(traceback.format_exc())
    sys.exit(1)

try:
    from modules.app_detector import get_active_app_info
    print("[DEBUG] Successfully imported app_detector")
except Exception as e:
    print(f"[ERROR] Failed to import app_detector: {e}")
    print(traceback.format_exc())
    sys.exit(1)

def run_daemon():
    print("🚀 FocusFlow 后台采集引擎已启动 (V2 增强版)...")
    try:
        init_db()  # 初始化数据库和表
        print("[DEBUG] Database initialized successfully")
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")
        print(traceback.format_exc())
        sys.exit(1)
    
    interval = int(os.getenv("FOCUSFLOW_INTERVAL_SECONDS", "1"))
    debug_idle = os.getenv("FOCUSFLOW_DEBUG", "0") == "1"
    idle_source = os.getenv("FOCUSFLOW_IDLE_SOURCE", "combined").lower()
    idle_mode = os.getenv("FOCUSFLOW_IDLE_MODE", "strict").lower()
    
    os_name = platform.system()
    idle_state = None
    if os_name == "Darwin":
        import Quartz
        if idle_source == "hid":
            idle_state = Quartz.kCGEventSourceStateHIDSystemState
        else:
            idle_state = getattr(Quartz, "kCGEventSourceStateCombinedSessionState", Quartz.kCGEventSourceStateHIDSystemState)
            
    last_app = "--"
    last_file = "--"

    try:
        while True:
            # 1. 每次循环等待指定时间（默认 1 秒）
            time.sleep(interval)
            
            # 2. 实时从数据库读取你在界面上设置的“空闲阈值”
            with get_connection() as conn:
                row = conn.execute("SELECT value FROM system_config WHERE key='idle_threshold'").fetchone()
                idle_threshold = int(row[0]) if row else 30
            
            # 3. 检测系统是否闲置
            # 3. 检测系统是否闲置
            idle_time = 0
            if os_name == "Darwin":
                import Quartz
                if idle_mode == "strict":
                    event_types = [
                        Quartz.kCGEventKeyDown, Quartz.kCGEventLeftMouseDown,
                        Quartz.kCGEventRightMouseDown, Quartz.kCGEventOtherMouseDown,
                        Quartz.kCGEventScrollWheel,
                    ]
                    idle_times = [Quartz.CGEventSourceSecondsSinceLastEventType(idle_state, et) for et in event_types]
                    idle_time = min([t for t in idle_times if t is not None], default=None)
                else:
                    idle_time = Quartz.CGEventSourceSecondsSinceLastEventType(idle_state, Quartz.kCGAnyInputEventType)
            elif os_name == "Windows":
                last_input = win32api.GetLastInputInfo()
                current_time = win32api.GetTickCount()
                idle_time = (current_time - last_input) / 1000.0
            if debug_idle:
                print(f"🕒 空闲秒数: {idle_time} (阈值: {idle_threshold})")
            
            # 判定当前是否闲置
            is_idle = idle_time is None or idle_time >= idle_threshold

            # 4. 获取当前前台活跃的窗口和软件
            try:
                app_name, file_path = get_active_app_info()
                print(f"[DEBUG] get_active_app_info returned: {app_name} | {file_path}")
            except Exception as e:
                print(f"[ERROR] Failed to get active app info: {e}")
                print(traceback.format_exc())
                app_name, file_path = "Unknown", "N/A"
            
            # V2 核心修改：移除硬编码！现在所有不是 "N/A" 的路径，只要人没闲置，统统记录！
            can_track = (not is_idle) and (file_path != "N/A")
            print(f"[DEBUG] can_track: {can_track} (is_idle: {is_idle}, file_path: {file_path})")

            if can_track:
                last_app, last_file = app_name, file_path
                try:
                    conn = get_connection()
                    # 将这一秒的时长写入总账本
                    conn.execute(
                        "INSERT INTO activity_log (timestamp, app_name, file_path, duration) VALUES (?, ?, ?, ?)",
                        (datetime.datetime.now().isoformat(), app_name, file_path, interval)
                    )
                    conn.commit()  # 【关键】强制立即写入硬盘！
                    conn.close()
                    
                    # 强制在终端打印日志，让我们看到它到底抓到了什么
                    print(f"✅ 记入数据库 -> 应用: {app_name} | 窗口: {file_path}")
                except Exception as e:
                    print(f"[ERROR] Failed to write to database: {e}")
                    print(traceback.format_exc())
            else:
                if debug_idle and is_idle:
                    print("💤 系统闲置，暂停记录...")

            if debug_idle:
                if is_idle:
                    state = "闲置中"
                elif file_path == "N/A":
                    state = "不计时(未识别窗口)"
                else:
                    state = "记时中"
                print(f"状态: {state} | 应用: {app_name} | 窗口/工程: {file_path}")

            # 5. 更新实时状态板 (用于前端顶部状态栏和悬浮窗显示)
            try:
                with get_connection() as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO runtime_status (id, updated_at, is_idle, idle_seconds, app_name, file_path) "
                        "VALUES (1, ?, ?, ?, ?, ?)",
                        (datetime.datetime.now().isoformat(), 1 if is_idle else 0, float(idle_time or 0), app_name, file_path),
                    )
                    conn.commit()
            except Exception as e:
                print(f"[ERROR] Failed to update runtime status: {e}")
                print(traceback.format_exc())
                
    except KeyboardInterrupt:
        print("\n⏹️ 后台采集引擎已手动停止。")
    except Exception as e:
        print(f"\n❌ 后台引擎发生错误: {e}")
        print(traceback.format_exc())
    finally:
        # 等待用户按键后才关闭窗口，方便查看错误信息
        print("\n" + "=" * 60)
        print("按 Enter 键退出...")
        print("=" * 60)
        input()

if __name__ == "__main__":
    run_daemon()