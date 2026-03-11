import customtkinter as ctk
import tkinter as tk
import time
from datetime import datetime
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds or 0))
    if seconds < 0:
        seconds = 0
    if seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}分{secs}秒"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if days > 0:
        return f"{days}天{hours}时{minutes}分{secs}秒"
    return f"{hours}时{minutes}分{secs}秒"


class FloatingWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        
        self.title("")
        self.geometry("280x180")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.overrideredirect(True)
        
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        
        self.font_sub = ctk.CTkFont(family="Avenir Next", size=12)
        self.font_stat = ctk.CTkFont(family="Avenir Next", size=18, weight="bold")
        self.font_small = ctk.CTkFont(family="Avenir Next", size=10)
        
        self.last_refresh = time.time()
        
        self._build_ui()
        self._schedule_refresh()
        self._setup_dragging()
    
    def _build_ui(self):
        self.container = ctk.CTkFrame(
            self, 
            fg_color="#2D3748", 
            corner_radius=0, 
            border_width=0
        )
        self.container.pack(fill="both", expand=True, padx=0, pady=0)
        
        self.content = ctk.CTkFrame(self.container, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=14, pady=10)
        
        project_frame = ctk.CTkFrame(self.content, fg_color="#4A5568", corner_radius=0)
        project_frame.pack(fill="x", pady=(0, 8))
        
        self.project_label = ctk.CTkLabel(
            project_frame, 
            text="暂无追踪项目", 
            font=self.font_stat, 
            text_color="#FFFFFF"
        )
        self.project_label.pack(padx=12, pady=8)
        
        info_grid = ctk.CTkFrame(self.content, fg_color="transparent")
        info_grid.pack(fill="x", pady=4)
        
        left_info = ctk.CTkFrame(info_grid, fg_color="transparent")
        left_info.pack(side="left")
        
        ctk.CTkLabel(
            left_info, 
            text="📊 应用:", 
            font=self.font_sub, 
            text_color="#A0AEC0"
        ).pack(anchor="w")
        
        self.app_label = ctk.CTkLabel(
            left_info, 
            text="--", 
            font=self.font_sub, 
            text_color="#90CDF4"
        )
        self.app_label.pack(anchor="w", pady=(2, 0))
        
        right_info = ctk.CTkFrame(info_grid, fg_color="transparent")
        right_info.pack(side="right")
        
        ctk.CTkLabel(
            right_info, 
            text="⏱️ 累计时长:", 
            font=self.font_sub, 
            text_color="#A0AEC0"
        ).pack(anchor="e")
        
        self.duration_label = ctk.CTkLabel(
            right_info, 
            text="0 时 0 分 0 秒", 
            font=self.font_stat, 
            text_color="#68D391"
        )
        self.duration_label.pack(anchor="e", pady=(2, 0))
        
        bottom_frame = ctk.CTkFrame(self.content, fg_color="#1A202C", corner_radius=0)
        bottom_frame.pack(fill="x", pady=(6, 0))
        
        status_row = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        status_row.pack(fill="x", padx=12, pady=8)
        
        self.status_label = ctk.CTkLabel(
            status_row, 
            text="状态：未开始", 
            font=self.font_small, 
            text_color="#F6AD55"
        )
        self.status_label.pack(side="left")
        
        self.idle_label = ctk.CTkLabel(
            status_row, 
            text="空闲：0 秒", 
            font=self.font_small, 
            text_color="#A0AEC0"
        )
        self.idle_label.pack(side="right")
    
    def _setup_dragging(self):
        self.dragging = False
        self.start_x = 0
        self.start_y = 0
        
        def on_press(event):
            self.dragging = True
            self.start_x = event.x
            self.start_y = event.y
        
        def on_motion(event):
            if self.dragging:
                x = self.winfo_x() + (event.x - self.start_x)
                y = self.winfo_y() + (event.y - self.start_y)
                self.geometry(f"+{x}+{y}")
        
        def on_release(event):
            self.dragging = False
        
        self.container.bind("<ButtonPress-1>", on_press)
        self.container.bind("<B1-Motion>", on_motion)
        self.container.bind("<ButtonRelease-1>", on_release)
        
        for widget in self.content.winfo_children():
            widget.bind("<ButtonPress-1>", on_press)
            widget.bind("<B1-Motion>", on_motion)
            widget.bind("<ButtonRelease-1>", on_release)
    
    def _schedule_refresh(self):
        self.after(1000, self._refresh)
    
    def _refresh(self):
        if hasattr(self.parent, "current_tracking_project"):
            project = self.parent.current_tracking_project
            if project:
                self.project_label.configure(text=f"{project}")
            else:
                self.project_label.configure(text="暂无追踪项目")
        
        if hasattr(self.parent, "last_status"):
            status = self.parent.last_status
            if status:
                updated_at, is_idle, idle_seconds, app_name, file_path = status
                state_text = "闲置中" if is_idle else "计时中"
                color = "#F6AD55" if is_idle else "#48BB78"
                
                self.status_label.configure(text=f"状态：{state_text}", text_color=color)
                self.app_label.configure(text=app_name if app_name else "--")
                self.idle_label.configure(text=f"空闲：{format_duration(idle_seconds)}")
            else:
                self.status_label.configure(text="状态：未开始", text_color="#A0AEC0")
                self.app_label.configure(text="--")
                self.idle_label.configure(text="空闲：0 秒")
        
        if hasattr(self.parent, "live_total"):
            total = self.parent.live_total
            self.duration_label.configure(text=f"{format_duration(total)}")
        
        self._schedule_refresh()


if __name__ == "__main__":
    root = ctk.CTk()
    root.title("Test")
    root.geometry("400x300")
    
    def open_floating():
        float_win = FloatingWindow(root)
        float_win.geometry("+100+100")
    
    ctk.CTkButton(root, text="打开悬浮窗", command=open_floating).pack(pady=20)
    root.mainloop()
