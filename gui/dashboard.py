import customtkinter as ctk
import tkinter as tk
import pandas as pd
import sqlite3
import os
import sys
import time
from datetime import datetime, date

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.database import init_db
from gui.floating_window import FloatingWindow

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tracker.db")


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


class Dashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        init_db()

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.title("FocusFlow - 专业看板")
        self.geometry("1120x720")
        self.minsize(980, 640)

        self.session_start = datetime.now()
        self.last_refresh_at = time.time()
        self.live_total = 0
        self.live_today = 0
        self.live_session = 0
        self.current_tracking_project = None

        self.font_title = ctk.CTkFont(family="Avenir Next", size=22, weight="bold")
        self.font_sub = ctk.CTkFont(family="Avenir Next", size=14)
        self.font_stat = ctk.CTkFont(family="Avenir Next", size=16, weight="bold")
        self.font_label = ctk.CTkFont(family="Avenir Next", size=12)

        self.container = ctk.CTkFrame(self, corner_radius=0)
        self.container.pack(fill="both", expand=True, padx=16, pady=16)

        self._build_header()
        self._build_metrics()
        self._build_main()

        self.refresh_all()
        self._schedule_refresh()
        self._schedule_tick()

    def _build_header(self):
        header = ctk.CTkFrame(self.container, fg_color="#F5F7FB")
        header.pack(fill="x", padx=12, pady=(12, 8))

        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.pack(side="left", padx=12, pady=12, fill="x", expand=True)

        ctk.CTkLabel(title_block, text="FocusFlow", font=self.font_title).pack(anchor="w")
        ctk.CTkLabel(
            title_block,
            text="专业动画/剪辑工时看板 · 自动采集 + 可视化归档",
            font=self.font_sub,
            text_color="#5B6570",
        ).pack(anchor="w", pady=(4, 0))

        action_block = ctk.CTkFrame(header, fg_color="transparent")
        action_block.pack(side="right", padx=12, pady=12)

        self.new_project_entry = ctk.CTkEntry(action_block, width=180, placeholder_text="新建项目名称")
        self.new_project_entry.grid(row=0, column=0, padx=6, pady=2)
        self.new_rule_entry = ctk.CTkEntry(action_block, width=180, placeholder_text="自动归档关键词(可选)")
        self.new_rule_entry.grid(row=0, column=1, padx=6, pady=2)
        ctk.CTkButton(action_block, text="新建项目", command=self.create_project).grid(row=0, column=2, padx=6)
        ctk.CTkButton(action_block, text="刷新", fg_color="#2F3A4A", command=self.refresh_all).grid(row=0, column=3, padx=6)
        ctk.CTkButton(action_block, text="悬浮窗", fg_color="#4A5568", command=self.toggle_floating_window).grid(row=0, column=4, padx=6)

    def _build_metrics(self):
        metrics = ctk.CTkFrame(self.container, fg_color="transparent")
        metrics.pack(fill="x", padx=12, pady=(0, 8))

        project_row = ctk.CTkFrame(metrics, fg_color="transparent")
        project_row.pack(fill="x", pady=(0, 8))

        self.current_project_label = ctk.CTkLabel(project_row, text="当前追踪项目：--", font=self.font_stat)
        self.current_project_label.pack(side="left")

        self.project_select_var = tk.StringVar(value="自动(最近)")
        self.project_selector = ctk.CTkOptionMenu(
            project_row, values=["自动(最近)"], variable=self.project_select_var, width=180, command=self._on_project_change
        )
        self.project_selector.pack(side="left", padx=12)
        self.status_label = ctk.CTkLabel(project_row, text="采集状态：--", font=self.font_sub, text_color="#5B6570")
        self.status_label.pack(side="right")

        cards = ctk.CTkFrame(metrics, fg_color="transparent")
        cards.pack(fill="x")

        self.total_card = self._make_metric_card(cards, "项目总计时", "--")
        self.today_card = self._make_metric_card(cards, "当天计时", "--")
        self.session_card = self._make_metric_card(cards, "本次启动计时", "--")

    def _make_metric_card(self, parent, title, value):
        card = ctk.CTkFrame(parent, fg_color="#F2F4F8", corner_radius=12)
        card.pack(side="left", expand=True, fill="x", padx=6, pady=4)
        title_label = ctk.CTkLabel(card, text=title, font=self.font_label, text_color="#5B6570")
        title_label.pack(anchor="w", padx=12, pady=(10, 0))
        value_label = ctk.CTkLabel(card, text=value, font=self.font_stat)
        value_label.pack(anchor="w", padx=12, pady=(0, 10))
        return value_label

    def _build_main(self):
        main = ctk.CTkFrame(self.container, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=12, pady=8)

        left = ctk.CTkFrame(main, fg_color="#F7F9FC", corner_radius=14)
        right = ctk.CTkFrame(main, fg_color="#F7F9FC", corner_radius=14)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))

        left_header = ctk.CTkFrame(left, fg_color="transparent")
        left_header.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(left_header, text="已分配项目", font=self.font_stat).pack(side="left")
        self.show_archived_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            left_header, text="显示已归档", variable=self.show_archived_var, command=self.refresh_all
        ).pack(side="right")
        ctk.CTkLabel(right, text="待分配任务", font=self.font_stat).pack(anchor="w", padx=16, pady=(16, 8))

        self.assigned_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.assigned_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 12))

        self.unassigned_scroll = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.unassigned_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 12))

    def _schedule_refresh(self):
        self.after(5000, self._auto_refresh)

    def _auto_refresh(self):
        self.refresh_all()
        self._schedule_refresh()

    def _schedule_tick(self):
        self.after(1000, self._tick)

    def _tick(self):
        now = time.time()
        delta = max(0, now - self.last_refresh_at)
        self.last_refresh_at = now

        if self._should_tick():
            self.live_total += delta
            self.live_today += delta
            self.live_session += delta
            self.total_card.configure(text=format_duration(self.live_total))
            self.today_card.configure(text=format_duration(self.live_today))
            self.session_card.configure(text=format_duration(self.live_session))

        self._schedule_tick()

    def _should_tick(self):
        if not getattr(self, "last_status", None):
            return False
        updated_at, is_idle, _, app_name, file_path = self.last_status
        if is_idle:
            return False
        if not (("After Effects" in app_name) or ("Premiere" in app_name)):
            return False
        if file_path in (None, "", "N/A"):
            return False

        selected = self.project_select_var.get()
        if selected == "自动(最近)":
            return self.current_tracking_project is not None
        return selected == self.current_tracking_project

    def _on_project_change(self, _=None):
        self.refresh_all()

    def create_project(self):
        name = self.new_project_entry.get().strip()
        rule = self.new_rule_entry.get().strip()
        if not name:
            return
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR IGNORE INTO projects (project_name, created_at) VALUES (?, ?)", (name, datetime.now().isoformat()))
            if rule:
                conn.execute(
                    "INSERT OR REPLACE INTO project_map (project_name, rule_path) VALUES (?, ?)",
                    (name, rule),
                )
        self.new_project_entry.delete(0, "end")
        self.new_rule_entry.delete(0, "end")
        self.refresh_all()

    def assign_file(self, file_path: str, project_name: str):
        if not project_name:
            return
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR IGNORE INTO projects (project_name, created_at) VALUES (?, ?)", (project_name, datetime.now().isoformat()))
            conn.execute(
                "INSERT OR REPLACE INTO file_assignment (file_path, project_name, assigned_at) VALUES (?, ?, ?)",
                (file_path, project_name, datetime.now().isoformat()),
            )
        self.refresh_all()

    def unassign_file(self, file_path: str):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM file_assignment WHERE file_path = ?", (file_path,))
        self.refresh_all()

    def archive_project(self, project_name: str):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO project_archive (project_name, archived_at) VALUES (?, ?)",
                (project_name, datetime.now().isoformat()),
            )
        self.refresh_all()

    def restore_project(self, project_name: str):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM project_archive WHERE project_name = ?", (project_name,))
        self.refresh_all()

    def _fetch_data(self):
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql("SELECT timestamp, app_name, file_path, duration FROM activity_log", conn)
            rules = conn.execute("SELECT project_name, rule_path FROM project_map").fetchall()
            manual = conn.execute("SELECT file_path, project_name FROM file_assignment").fetchall()
            projects = conn.execute("SELECT project_name FROM projects").fetchall()
            archived = conn.execute("SELECT project_name FROM project_archive").fetchall()
            status = conn.execute(
                "SELECT updated_at, is_idle, idle_seconds, app_name, file_path FROM runtime_status WHERE id = 1"
            ).fetchone()

        manual_map = {fp: proj for fp, proj in manual}
        rule_list = [(p, r) for p, r in rules if r]
        archived_set = {p[0] for p in archived}
        project_names = {p[0] for p in projects}
        project_names.update([p for p, _ in rules])
        project_names.update([p for _, p in manual])

        if df.empty:
            df["timestamp"] = pd.to_datetime(df.get("timestamp", []))
            return df, manual_map, rule_list, sorted(project_names), archived_set, status

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        def match_project(path: str):
            if path in manual_map:
                return manual_map[path]
            for proj_name, rule in rule_list:
                if rule in path:
                    return proj_name
            return None

        df["project"] = df["file_path"].apply(match_project)
        return df, manual_map, rule_list, sorted(project_names), archived_set, status

    def _match_project_for_path(self, file_path, manual_map, rule_list):
        if file_path in manual_map:
            return manual_map[file_path]
        for proj_name, rule in rule_list:
            if rule in file_path:
                return proj_name
        return None

    def refresh_all(self):
        df, manual_map, rule_list, project_names, archived_set, status = self._fetch_data()
        self.last_status = status

        if self.show_archived_var.get():
            selector_projects = project_names
        else:
            selector_projects = [p for p in project_names if p not in archived_set]
        options = ["自动(最近)"] + selector_projects
        current_value = self.project_select_var.get()
        if current_value not in options:
            current_value = "自动(最近)"
            self.project_select_var.set(current_value)
        self.project_selector.configure(values=options)

        if df.empty:
            self.current_project_label.configure(text="当前追踪项目：暂无记录")
            self._update_status(status)
            self.total_card.configure(text="--")
            self.today_card.configure(text="--")
            self.session_card.configure(text="--")
            self._render_assigned([], df, {}, set())
            self._render_unassigned(df, project_names)
            return
        df_today = df[df["timestamp"].dt.date == date.today()]

        latest_row = df.sort_values("timestamp").iloc[-1]
        latest_project = latest_row.get("project")
        latest_file = latest_row.get("file_path", "")
        current_project = latest_project or os.path.basename(latest_file)
        self.current_project_label.configure(text=f"当前追踪项目：{current_project}")
        self._update_status(status)

        selected = self.project_select_var.get()
        if selected == "自动(最近)":
            if latest_project:
                project_total = df[df["project"] == latest_project]["duration"].sum()
                project_today = df_today[df_today["project"] == latest_project]["duration"].sum()
                project_session = df[(df["project"] == latest_project) & (df["timestamp"] >= self.session_start)]["duration"].sum()
            else:
                project_total = df[df["file_path"] == latest_file]["duration"].sum()
                project_today = df_today[df_today["file_path"] == latest_file]["duration"].sum()
                project_session = df[(df["file_path"] == latest_file) & (df["timestamp"] >= self.session_start)]["duration"].sum()
        else:
            project_total = df[df["project"] == selected]["duration"].sum()
            project_today = df_today[df_today["project"] == selected]["duration"].sum()
            project_session = df[(df["project"] == selected) & (df["timestamp"] >= self.session_start)]["duration"].sum()

        self.live_total = float(project_total)
        self.live_today = float(project_today)
        self.live_session = float(project_session)
        self.last_refresh_at = time.time()
        self.total_card.configure(text=format_duration(self.live_total))
        self.today_card.configure(text=format_duration(self.live_today))
        self.session_card.configure(text=format_duration(self.live_session))

        if status and status[4]:
            self.current_tracking_project = self._match_project_for_path(status[4], manual_map, rule_list)
        else:
            self.current_tracking_project = None

        self._render_assigned(project_names, df, manual_map, archived_set)
        self._render_unassigned(df, project_names)

    def _update_status(self, status):
        if not status:
            self.status_label.configure(text="采集状态：--")
            return
        updated_at, is_idle, idle_seconds, app_name, file_path = status
        state_text = "闲置中" if is_idle else "计时中"
        self.status_label.configure(
            text=f"采集状态：{state_text} · 空闲 {format_duration(idle_seconds)} · 应用 {app_name}"
        )

    def _render_assigned(self, project_names, df, manual_map, archived_set):
        for child in self.assigned_scroll.winfo_children():
            child.destroy()

        if df.empty:
            ctk.CTkLabel(self.assigned_scroll, text="暂无数据", font=self.font_label).pack(anchor="w", padx=8, pady=8)
            return

        for project in project_names:
            is_archived = project in archived_set
            if is_archived and not self.show_archived_var.get():
                continue
            project_df = df[df["project"] == project]
            total = project_df["duration"].sum() if not project_df.empty else 0
            today = project_df[project_df["timestamp"].dt.date == date.today()]["duration"].sum() if not project_df.empty else 0
            file_paths = list(project_df["file_path"].dropna().unique())

            card = ctk.CTkFrame(self.assigned_scroll, fg_color="#FFFFFF", corner_radius=12)
            card.pack(fill="x", padx=8, pady=6)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(10, 0))
            title_left = ctk.CTkFrame(top, fg_color="transparent")
            title_left.pack(side="left")
            ctk.CTkLabel(title_left, text=project, font=self.font_stat).pack(side="left")
            if is_archived:
                ctk.CTkLabel(title_left, text="已归档", font=self.font_label, text_color="#7A8592").pack(side="left", padx=6)
            ctk.CTkLabel(
                top,
                text=f"总计 {format_duration(total)} · 今日 {format_duration(today)} · 文件 {len(file_paths)}",
                font=self.font_label,
                text_color="#5B6570",
            ).pack(side="right")

            action_bar = ctk.CTkFrame(card, fg_color="transparent")
            action_bar.pack(fill="x", padx=12, pady=(6, 0))
            if is_archived:
                ctk.CTkButton(action_bar, text="恢复项目", width=90, fg_color="#2F3A4A", command=lambda p=project: self.restore_project(p)).pack(side="right")
            else:
                ctk.CTkButton(action_bar, text="归档项目", width=90, fg_color="#7A8592", command=lambda p=project: self.archive_project(p)).pack(side="right")

            files_area = ctk.CTkFrame(card, fg_color="transparent")
            files_area.pack(fill="x", padx=12, pady=(6, 10))
            if file_paths:
                for fp in file_paths:
                    row = ctk.CTkFrame(files_area, fg_color="transparent")
                    row.pack(fill="x", pady=2)
                    ctk.CTkLabel(row, text=os.path.basename(fp), font=self.font_label).pack(side="left")
                    ctk.CTkLabel(row, text=fp, font=self.font_label, text_color="#7A8592").pack(side="left", padx=8)
                    if fp in manual_map:
                        ctk.CTkButton(
                            row, text="移出", width=60, fg_color="#7A8592", command=lambda p=fp: self.unassign_file(p)
                        ).pack(side="right")
                    else:
                        ctk.CTkLabel(row, text="自动归档", font=self.font_label, text_color="#7A8592").pack(side="right")
            else:
                ctk.CTkLabel(files_area, text="暂无已归档文件", font=self.font_label).pack(anchor="w")

    def _render_unassigned(self, df, all_projects):
        for child in self.unassigned_scroll.winfo_children():
            child.destroy()

        unassigned = df[df["project"].isna()]
        if unassigned.empty:
            ctk.CTkLabel(self.unassigned_scroll, text="暂无待分配任务", font=self.font_label).pack(anchor="w", padx=8, pady=8)
            return

        project_options = all_projects or []

        grouped = unassigned.groupby("file_path")
        for file_path, group in grouped:
            total = group["duration"].sum()
            today = group[group["timestamp"].dt.date == date.today()]["duration"].sum()
            last_seen = group["timestamp"].max()
            latest_app = group.sort_values("timestamp").iloc[-1].get("app_name", "--")

            row = ctk.CTkFrame(self.unassigned_scroll, fg_color="#FFFFFF", corner_radius=12)
            row.pack(fill="x", padx=8, pady=6)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=12, pady=10)
            ctk.CTkLabel(info, text=os.path.basename(file_path), font=self.font_stat).pack(anchor="w")
            ctk.CTkLabel(
                info,
                text=f"应用：{latest_app} · 今日 {format_duration(today)} · 累计 {format_duration(total)}",
                font=self.font_label,
                text_color="#5B6570",
            ).pack(anchor="w", pady=(2, 0))
            ctk.CTkLabel(
                info,
                text=f"路径：{file_path}\n最近活跃：{last_seen}",
                font=self.font_label,
                text_color="#7A8592",
                justify="left",
            ).pack(anchor="w", pady=(4, 0))

            action = ctk.CTkFrame(row, fg_color="transparent")
            action.pack(side="right", padx=12, pady=10)

            if project_options:
                selected = tk.StringVar(value=project_options[0])
                option = ctk.CTkOptionMenu(action, values=project_options, variable=selected, width=160)
                option.pack(pady=(0, 6))
                ctk.CTkButton(
                    action,
                    text="归档到项目",
                    command=lambda p=file_path, var=selected: self.assign_file(p, var.get()),
                ).pack()
            else:
                ctk.CTkLabel(action, text="请先新建项目", font=self.font_label, text_color="#B25D5D").pack()
                
    def toggle_floating_window(self):
        """切换悬浮窗的显示/隐藏状态"""
        if not hasattr(self, "floating_window") or not self.floating_window.winfo_exists():
            # 创建新的悬浮窗
            self.floating_window = FloatingWindow(self)
            # 定位到屏幕右上角
            screen_width = self.winfo_screenwidth()
            self.floating_window.geometry(f"+{screen_width - 320}+20")
            self.floating_window.deiconify()
        else:
            # 切换悬浮窗的显示状态
            if self.floating_window.winfo_viewable():
                self.floating_window.withdraw()
            else:
                self.floating_window.deiconify()


if __name__ == "__main__":
    app = Dashboard()
    app.mainloop()
