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

print(f"[DEBUG] Python version: {sys.version}")
print(f"[DEBUG] Platform: {platform.system()}")
print(f"[DEBUG] Current directory: {os.getcwd()}")

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

# 常量
CHECKPOINT_INTERVAL = 60  # 每 60 秒写一次 checkpoint


def write_activity_log(app_name, file_path, duration, timestamp=None):
    """写入一条 activity_log 记录"""
    if duration <= 0:
        return
    if timestamp is None:
        timestamp = datetime.datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO activity_log (timestamp, app_name, file_path, duration) VALUES (?, ?, ?, ?)",
        (timestamp, app_name, file_path, round(duration, 2))
    )
    conn.commit()
    conn.close()
    print(f"✅ 写入 -> {app_name} | {file_path} | {round(duration, 2)}秒")


def load_session_state():
    """从 runtime_status 恢复上次的 session 状态"""
    conn = get_connection()
    row = conn.execute("""
        SELECT session_start, last_checkpoint, accumulated_since_checkpoint,
               last_app_name, last_file_path, updated_at
        FROM runtime_status WHERE id=1
    """).fetchone()
    conn.close()

    if row and row[0]:  # 有 session_start
        session_start, last_checkpoint, accumulated, last_app, last_file, updated_at = row
        # 检查 session 是否过期（超过 5 分钟没更新说明服务重启了）
        if updated_at:
            try:
                last_update = datetime.datetime.fromisoformat(updated_at)
                elapsed = (datetime.datetime.now() - last_update).total_seconds()
                if elapsed < 300:  # 5 分钟内，认为是有效 session
                    print(f"[SESSION] 恢复: app={last_app}, file={last_file}, 累计={accumulated}秒")
                    return {
                        'session_start': session_start,
                        'last_checkpoint': last_checkpoint,
                        'accumulated': accumulated or 0,
                        'last_app': last_app,
                        'last_file': last_file
                    }
            except Exception as e:
                print(f"[WARN] 恢复 session 失败: {e}")
    return None


def save_session_state(app_name, file_path, session_start, last_checkpoint, accumulated, is_idle, idle_time):
    """保存当前 session 状态到 runtime_status"""
    now = datetime.datetime.now().isoformat()
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO runtime_status
        (id, updated_at, is_idle, idle_seconds, app_name, file_path,
         session_start, last_checkpoint, accumulated_since_checkpoint, last_app_name, last_file_path)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (now, 1 if is_idle else 0, float(idle_time or 0), app_name, file_path,
          session_start, last_checkpoint, accumulated, app_name, file_path))
    conn.commit()
    conn.close()


def is_valid_app(app_name, file_path):
    """判断是否有效活动（不是 None，空字符串，或 N/A）"""
    return bool(app_name and app_name != "N/A" and file_path != "N/A")


def run_daemon():
    print("🚀 FocusFlow 后台采集引擎已启动 (V3 优化版 - 状态变化记录)...")

    try:
        init_db()
        print("[DEBUG] Database initialized successfully")
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")
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

    # 恢复上次的 session 状态
    session = load_session_state()
    if session:
        session_start = session['session_start']
        last_checkpoint = session['last_checkpoint']
        accumulated = session['accumulated']
        last_app = session['last_app']
        last_file = session['last_file']
    else:
        now = datetime.datetime.now()
        session_start = now.isoformat()
        last_checkpoint = now.isoformat()
        accumulated = 0
        last_app = None
        last_file = None

    checkpoint_interval = CHECKPOINT_INTERVAL

    try:
        while True:
            time.sleep(interval)

            # 1. 读取空闲阈值
            with get_connection() as conn:
                row = conn.execute("SELECT value FROM system_config WHERE key='idle_threshold'").fetchone()
                idle_threshold = int(row[0]) if row else 30

            # 2. 检测系统空闲
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

            is_idle = idle_time is None or idle_time >= idle_threshold

            # 3. 获取当前活动窗口
            try:
                app_name, file_path = get_active_app_info()
            except Exception as e:
                print(f"[ERROR] get_active_app_info: {e}")
                app_name, file_path = "Unknown", "N/A"

            current_valid = is_valid_app(app_name, file_path)
            last_valid = is_valid_app(last_app, last_file) if last_app else False

            now = datetime.datetime.now()

            if current_valid and not is_idle:
                # ===== 当前是有效活动 =====
                app_changed = (app_name != last_app)
                file_changed = (file_path != last_file)

                if app_changed and last_valid:
                    # app 变化了，写入上一条的累计
                    duration = accumulated
                    write_activity_log(last_app, last_file, duration, session_start)
                    session_start = now.isoformat()
                    accumulated = 0
                    last_checkpoint = now.isoformat()
                elif file_changed and last_valid and accumulated >= 30:
                    # 同一 app 内 file_path 变化，且累计 >= 30秒，拆分记录
                    duration = accumulated
                    write_activity_log(last_app, last_file, duration, session_start)
                    session_start = now.isoformat()
                    accumulated = 0
                    last_checkpoint = now.isoformat()
                elif not last_valid:
                    # 之前没有有效 session，初始化
                    session_start = now.isoformat()
                    last_checkpoint = now.isoformat()

                # 累计时间
                accumulated += interval
                last_app = app_name
                last_file = file_path

                # 检查 checkpoint
                if last_checkpoint:
                    try:
                        last_ck = datetime.datetime.fromisoformat(last_checkpoint)
                        elapsed = (now - last_ck).total_seconds()
                        if elapsed >= checkpoint_interval and accumulated > 0:
                            write_activity_log(app_name, file_path, accumulated, last_checkpoint)
                            last_checkpoint = now.isoformat()
                            accumulated = 0
                            print(f"📍 Checkpoint ({checkpoint_interval}秒周期)")
                    except Exception as e:
                        print(f"[WARN] checkpoint 检查失败: {e}")

            else:
                # ===== 当前是闲置或无效窗口 =====
                if last_valid and accumulated > 0:
                    # 写入最后的累计记录
                    write_activity_log(last_app, last_file, accumulated, session_start)
                    accumulated = 0
                    last_app = None
                    last_file = None
                    session_start = None
                    last_checkpoint = None

            # 4. 更新 runtime_status
            save_session_state(
                app_name or "",
                file_path or "",
                session_start or (now.isoformat() if current_valid else ""),
                last_checkpoint or (now.isoformat() if last_valid else ""),
                accumulated,
                is_idle,
                idle_time
            )

            # 5. 调试输出
            if debug_idle:
                state = "闲置" if is_idle else ("无效窗口" if not current_valid else "记时")
                print(f"[DEBUG] {state} | 累计:{accumulated}s | {app_name} | {file_path}")

    except KeyboardInterrupt:
        print("\n⏹️ 收到停止信号")
        if accumulated > 0 and last_valid:
            write_activity_log(last_app, last_file, accumulated)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print(traceback.format_exc())
    finally:
        print("=" * 50)
        print("服务已停止")
        print("=" * 50)


if __name__ == "__main__":
    run_daemon()