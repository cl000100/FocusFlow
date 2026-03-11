import Quartz
from AppKit import NSWorkspace

def get_active_app_info():
    try:
        file_path = "N/A"

        # 优先用窗口列表的最前台可见窗口判定（更贴近真实前台）
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
        )
        for win in window_list:
            owner = win.get("kCGWindowOwnerName", "")
            title = win.get("kCGWindowName", "")
            layer = win.get("kCGWindowLayer", 0)
            alpha = win.get("kCGWindowAlpha", 1)
            if not owner or layer != 0 or alpha == 0:
                continue
            app_name = owner
            # 识别 AE / PR 工程路径
            if ("After Effects" in owner) or ("Premiere" in owner):
                if title and (".aep" in title.lower() or ".prproj" in title.lower()):
                    if " - " in title:
                        file_path = title.split(" - ", 1)[-1].replace("*", "").strip()
            return app_name, file_path

        # 回退：用 NSWorkspace 判定前台应用
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        app_name = app.localizedName() or "Unknown"
        bundle_id = app.bundleIdentifier() or ""

        # 多软件识别逻辑（同时用应用名与 bundle id 判定）
        is_ae = ("After Effects" in app_name) or (bundle_id == "com.adobe.AfterEffects")
        is_pr = ("Premiere Pro" in app_name) or (bundle_id == "com.adobe.PremierePro")
        if is_ae or is_pr:
            for win in window_list:
                owner = win.get('kCGWindowOwnerName', '')
                # 更稳健的匹配：前台应用名和窗口 owner 名互包含即可
                if owner == app_name or owner in app_name or app_name in owner:
                    title = win.get('kCGWindowName', '')
                    # 识别 .aep 或 .prproj
                    if '.aep' in title.lower() or '.prproj' in title.lower():
                        if " - " in title:
                            file_path = title.split(" - ", 1)[-1].replace('*', '').strip()
        return app_name, file_path
    except:
        return "Unknown", "N/A"
