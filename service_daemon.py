import time
import datetime
import os
from core.database import init_db, get_connection
from modules.app_detector import get_active_app_info
import Quartz

def run_daemon():
    print("🚀 FocusFlow 后台采集引擎已启动...")
    init_db()  # 初始化数据库和表
    
    idle_threshold = int(os.getenv("FOCUSFLOW_IDLE_SECONDS", "30"))
    interval = int(os.getenv("FOCUSFLOW_INTERVAL_SECONDS", "5"))
    debug_idle = os.getenv("FOCUSFLOW_DEBUG", "0") == "1"
    idle_source = os.getenv("FOCUSFLOW_IDLE_SOURCE", "combined").lower()
    idle_mode = os.getenv("FOCUSFLOW_IDLE_MODE", "strict").lower()
    if idle_source == "hid":
        idle_state = Quartz.kCGEventSourceStateHIDSystemState
    else:
        idle_state = getattr(Quartz, "kCGEventSourceStateCombinedSessionState", Quartz.kCGEventSourceStateHIDSystemState)
    
    last_app = "--"
    last_file = "--"

    try:
        while True:
            # 1. 每次循环等待
            time.sleep(interval)
            
            # 2. 检测系统是否闲置
            if idle_mode == "strict":
                # Ignore mouse-move/hover; only count deliberate input events
                event_types = [
                    Quartz.kCGEventKeyDown,
                    Quartz.kCGEventLeftMouseDown,
                    Quartz.kCGEventRightMouseDown,
                    Quartz.kCGEventOtherMouseDown,
                    Quartz.kCGEventScrollWheel,
                ]
                idle_times = [
                    Quartz.CGEventSourceSecondsSinceLastEventType(idle_state, et)
                    for et in event_types
                ]
                idle_time = min([t for t in idle_times if t is not None], default=None)
            else:
                idle_time = Quartz.CGEventSourceSecondsSinceLastEventType(
                    idle_state,
                    Quartz.kCGAnyInputEventType
                )
            if debug_idle:
                print(f"🕒 Idle seconds: {idle_time}")
            
            is_idle = idle_time is None or idle_time >= idle_threshold

            app_name, file_path = get_active_app_info()
            is_target_app = ("After Effects" in app_name) or ("Adobe Premiere Pro" in app_name)
            can_track = (not is_idle) and is_target_app and (file_path != "N/A")

            if can_track:
                    last_app, last_file = app_name, file_path
                    with get_connection() as conn:
                        conn.execute(
                            "INSERT INTO activity_log (timestamp, app_name, file_path, duration) VALUES (?, ?, ?, ?)",
                            (datetime.datetime.now().isoformat(), app_name, file_path, interval)
                        )
                    if debug_idle:
                        print(f"✅ 记录: {app_name} | {file_path}")
            else:
                if debug_idle and is_idle:
                    print("💤 系统闲置，暂停记录...")

            if debug_idle:
                if is_idle:
                    state = "闲置中"
                elif not is_target_app:
                    state = "不计时(非目标应用)"
                elif file_path == "N/A":
                    state = "不计时(未识别工程)"
                else:
                    state = "记时中"
                print(f"状态: {state} | 应用: {app_name} | 工程: {file_path}")

            with get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO runtime_status (id, updated_at, is_idle, idle_seconds, app_name, file_path) "
                    "VALUES (1, ?, ?, ?, ?, ?)",
                    (datetime.datetime.now().isoformat(), 1 if is_idle else 0, float(idle_time or 0), app_name, file_path),
                )
                
    except KeyboardInterrupt:
        print("\n⏹️ 后台采集引擎已停止。")

if __name__ == "__main__":
    run_daemon()
