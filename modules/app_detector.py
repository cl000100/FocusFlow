import platform

def get_active_app_info():
    os_name = platform.system()
    if os_name == "Darwin":
        return _get_active_app_mac()
    elif os_name == "Windows":
        return _get_active_app_windows()
    return "Unknown", "N/A"

def _get_active_app_mac():
    import Quartz
    try:
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements, 
            Quartz.kCGNullWindowID
        )
        for win in window_list:
            owner = win.get("kCGWindowOwnerName", "")
            title = win.get("kCGWindowName", "")
            layer = win.get("kCGWindowLayer", 0)
            alpha = win.get("kCGWindowAlpha", 1)
            
            system_noise = ["WindowManager", "Dock", "Window Server", "ControlCenter", "NotificationCenter", "loginwindow"]
            
            if owner and layer == 0 and alpha > 0:
                if owner in system_noise: continue
                app_name = owner
                file_path = f"[{app_name}]"
                if title:
                    if ("After Effects" in owner) or ("Premiere" in owner):
                        if ".aep" in title.lower() or ".prproj" in title.lower():
                            file_path = title.split(" - ", 1)[-1].replace("*", "").strip() if " - " in title else title.replace("*", "").strip()
                    elif "Photoshop" in owner:
                        if ".psd" in title.lower() or ".psb" in title.lower():
                            file_path = title.split(" @ ")[0].replace("*", "").strip() if " @ " in title else title.replace("*", "").strip()
                    else:
                        file_path = title.strip()
                return app_name, file_path
        return "Unknown", "N/A"
    except:
        return "Unknown", "N/A"

def _get_active_app_windows():
    try:
        import win32gui
        import win32process
        import psutil
        
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd: 
            print("[DEBUG] No foreground window found")
            return "Unknown", "N/A"
        
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        
        try:
            process = psutil.Process(pid)
            app_name = process.name().replace(".exe", "")
        except psutil.NoSuchProcess:
            print(f"[DEBUG] Process {pid} not found")
            return "Unknown", "N/A"
        
        # 扩展系统噪音列表，排除更多系统进程
        system_noise = ["SearchHost", "ShellExperienceHost", "explorer", "TextInputHost", "StartMenuExperienceHost"]
        if app_name in system_noise: 
            print(f"[DEBUG] Ignoring system process: {app_name}")
            return "Unknown", "N/A"
        
        # 对于 Windows Terminal，使用窗口标题作为文件路径
        file_path = title.strip() if title else f"[{app_name}]"
        
        # 特殊处理专业软件
        if "After Effects" in app_name or "Premiere" in app_name:
            if ".aep" in title.lower() or ".prproj" in title.lower():
                file_path = title.split(" - ", 1)[-1].replace("*", "").strip() if " - " in title else title.replace("*", "").strip()
        elif "Photoshop" in app_name:
            if ".psd" in title.lower() or ".psb" in title.lower():
                file_path = title.split(" @ ")[0].replace("*", "").strip() if " @ " in title else title.replace("*", "").strip()
        
        print(f"[DEBUG] Detected: {app_name} | {file_path}")
        return app_name, file_path
    except Exception as e:
        print(f"[DEBUG] Error in _get_active_app_windows: {e}")
        return "Unknown", "N/A"