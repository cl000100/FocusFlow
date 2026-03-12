import Quartz

def get_active_app_info():
    try:
        # 直接让显卡交出当前屏幕上所有窗口的列表（默认按从前到后的层级排序）
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements, 
            Quartz.kCGNullWindowID
        )
        
        for win in window_list:
            owner = win.get("kCGWindowOwnerName", "")
            title = win.get("kCGWindowName", "")
            layer = win.get("kCGWindowLayer", 0)
            alpha = win.get("kCGWindowAlpha", 1)
            
            # 【新增】：系统级噪音黑名单
            system_noise = [
                "WindowManager", "Dock", "Window Server", 
                "ControlCenter", "NotificationCenter", "loginwindow"
            ]
            
            # layer == 0 是普通主窗口。由于列表是从前到后排的，
            if owner and layer == 0 and alpha > 0:
                # 过滤掉系统自带的桌面管理和菜单栏噪音
                if owner in system_noise:
                    continue  # 跳过这个，去抓下面那一层真正的软件！
                    
                
                app_name = owner
                
                # 默认路径名：如果抓不到标题，就用 [软件名] 代替
                file_path = f"[{app_name}]"
                
                if title:
                    # 针对 AE / PR 的提取逻辑
                    if ("After Effects" in owner) or ("Premiere" in owner):
                        if ".aep" in title.lower() or ".prproj" in title.lower():
                            if " - " in title:
                                file_path = title.split(" - ", 1)[-1].replace("*", "").strip()
                            else:
                                file_path = title.replace("*", "").strip()
                                
                    # 针对 Photoshop 的提取逻辑
                    elif "Photoshop" in owner:
                        if ".psd" in title.lower() or ".psb" in title.lower():
                            if " @ " in title:
                                file_path = title.split(" @ ")[0].replace("*", "").strip()
                            else:
                                file_path = title.replace("*", "").strip()
                                
                    # 其他所有普通软件 (如 Chrome, Word 等)，直接拿窗口标题当路径
                    else:
                        file_path = title.strip()
                        
                return app_name, file_path
                
        return "Unknown", "N/A"
    except Exception as e:
        print(f"获取窗口错误: {e}")
        return "Unknown", "N/A"