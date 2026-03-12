import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
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
from core.project_tree import (
    load_project_tree, create_project, delete_project, 
    move_project, archive_project, restore_project, get_project_stats,
    get_all_projects_flat, get_project_files, remove_file_assignment
)
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
        self.selected_project_id = None
        self.expanded_items = set()  # 保存展开的项目项

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

        self.new_project_entry = ctk.CTkEntry(action_block, width=140, placeholder_text="新建项目名称")
        self.new_project_entry.grid(row=0, column=0, padx=6, pady=2)
        self.new_rule_entry = ctk.CTkEntry(action_block, width=140, placeholder_text="自动归档关键词(可选)")
        self.new_rule_entry.grid(row=0, column=1, padx=6, pady=2)
        ctk.CTkButton(action_block, text="新建项目", command=self.create_project).grid(row=0, column=2, padx=6)
        ctk.CTkButton(action_block, text="新建子项目", command=self.create_child_project).grid(row=0, column=3, padx=6)
        ctk.CTkButton(action_block, text="刷新", fg_color="#2F3A4A", command=self.refresh_all).grid(row=0, column=4, padx=6)
        ctk.CTkButton(action_block, text="悬浮窗", fg_color="#4A5568", command=self.toggle_floating_window).grid(row=0, column=5, padx=6)

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

        tree_frame = ctk.CTkFrame(left, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 12))

        self.tree = ttk.Treeview(tree_frame, columns=("total", "today", "children"), show="tree headings", height=20)
        self.tree.pack(side="left", fill="both", expand=True)
        
        self.tree.heading("#0", text="项目名称")
        self.tree.heading("total", text="总计时")
        self.tree.heading("today", text="今日")
        self.tree.heading("children", text="子项目")
        
        self.tree.column("#0", width=200)
        self.tree.column("total", width=100)
        self.tree.column("today", width=80)
        self.tree.column("children", width=80)

        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Button-3>", self._on_tree_right_click)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.unassigned_scroll = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.unassigned_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 12))

        self.project_menu = tk.Menu(self, tearoff=0)
        self.project_menu.add_command(label="新建子项目", command=self._menu_new_child)
        self.project_menu.add_command(label="重命名", command=self._menu_rename)
        self.project_menu.add_command(label="归档/恢复", command=self._menu_archive)
        self.project_menu.add_separator()
        self.project_menu.add_command(label="删除项目", command=self._menu_delete)

    def _schedule_refresh(self):
        self.after(8000, self._auto_refresh)

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
        # 移除了仅仅验证 AE 和 PR 的限制，让所有程序都能触发时长跳动
        
        selected = self.project_select_var.get()
        if selected == "自动(最近)":
            if file_path not in (None, "", "N/A"):
                return True
            return self.current_tracking_project is not None
        else:
            if file_path not in (None, "", "N/A"):
                return True
            return selected == self.current_tracking_project

    def _on_project_change(self, _=None):
        selected = self.project_select_var.get()
        if selected == "自动(最近)":
            self.refresh_all()
        else:
            self._update_metrics_for_selected_project(selected)

    def _update_metrics_for_selected_project(self, project_name):
        df, manual_map, rule_list, project_names, archived_set, status = self._fetch_data()
        self.last_status = status
        
        if df.empty:
            return
        
        df_today = df[df["timestamp"].dt.date == date.today()]
        
        project_total = df[df["project"] == project_name]["duration"].sum()
        project_today = df_today[df_today["project"] == project_name]["duration"].sum()
        project_session = df[(df["project"] == project_name) & (df["timestamp"] >= self.session_start)]["duration"].sum()
        
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

    def create_project(self):
        name = self.new_project_entry.get().strip()
        rule = self.new_rule_entry.get().strip()
        if not name:
            return
        project_id = create_project(name)
        if project_id:
            if rule:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO project_map (project_id, rule_path) VALUES (?, ?)",
                        (project_id, rule),
                    )
        self.new_project_entry.delete(0, "end")
        self.new_rule_entry.delete(0, "end")
        self.refresh_all()

    def create_child_project(self):
        # 优先使用右键菜单选中的项目
        if self.selected_project_id:
            parent_node = load_project_tree().get_node(self.selected_project_id)
            if parent_node:
                self._do_create_child(parent_node)
                return
        
        # 如果没有选中项目，使用下拉框的值
        selected = self.project_select_var.get()
        if selected == "自动(最近)":
            from tkinter import messagebox
            messagebox.showwarning("提示", "请先在左侧树形列表中选择一个父项目，或在下拉框中选择")
            return
        
        tree = load_project_tree()
        parent_node = tree.find_node_by_name(selected)
        if parent_node:
            self._do_create_child(parent_node)
        else:
            from tkinter import messagebox
            messagebox.showerror("错误", f"未找到项目: {selected}")
    
    def _do_create_child(self, parent_node):
        from tkinter import simpledialog
        name = simpledialog.askstring("新建子项目", f"在「{parent_node.name}」下新建子项目名称:", parent=self)
        if name:
            create_project(name, parent_node.id)
            self.refresh_all()

    def assign_file(self, file_path: str, project_name: str):
        if not project_name:
            return
        tree = load_project_tree()
        node = tree.find_node_by_name(project_name)
        project_id = node.id if node else None
        
        if project_id:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO file_assignment (file_path, project_id, assigned_at) VALUES (?, ?, ?)",
                    (file_path, project_id, datetime.now().isoformat()),
                )
        else:
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

    def archive_project(self, project_id: int):
        archive_project(project_id)
        self.refresh_all()

    def restore_project(self, project_id: int):
        restore_project(project_id)
        self.refresh_all()

    def _fetch_data(self):
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql("SELECT timestamp, app_name, file_path, duration FROM activity_log", conn)
            rules = conn.execute("SELECT pm.project_id, pm.rule_path, p.project_name FROM project_map pm LEFT JOIN projects p ON pm.project_id = p.id WHERE pm.rule_path IS NOT NULL").fetchall()
            manual = conn.execute("SELECT fa.file_path, p.project_name FROM file_assignment fa LEFT JOIN projects p ON fa.project_id = p.id").fetchall()
            projects = conn.execute("SELECT project_name FROM projects").fetchall()
            archived = conn.execute("SELECT p.project_name FROM project_archive pa LEFT JOIN projects p ON pa.project_id = p.id").fetchall()
            status = conn.execute(
                "SELECT updated_at, is_idle, idle_seconds, app_name, file_path FROM runtime_status WHERE id = 1"
            ).fetchone()

        manual_map = {fp: proj for fp, proj in manual if fp and proj}
        rule_list = [(pid, r, pn) for pid, r, pn in rules if r and pn]
        archived_set = {p[0] for p in archived if p[0]}
        project_names = {p[0] for p in projects if p[0]}
        project_names.update([pn for _, _, pn in rule_list])
        project_names.update([p for _, p in manual if p])

        if df.empty:
            df["timestamp"] = pd.to_datetime(df.get("timestamp", []))
            return df, manual_map, rule_list, sorted(project_names), archived_set, status

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        def match_project(path: str):
            if path in manual_map:
                return manual_map[path]
            for proj_id, rule, proj_name in rule_list:
                if rule in path:
                    return proj_name
            return None

        df["project"] = df["file_path"].apply(match_project)
        return df, manual_map, rule_list, sorted(project_names), archived_set, status

    def _match_project_for_path(self, file_path, manual_map, rule_list):
        if file_path in manual_map:
            return manual_map[file_path]
        for proj_id, rule, proj_name in rule_list:
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
            self._render_tree([])
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

        self._render_tree(project_names)
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

    def _render_tree(self, project_names):
        # 保存当前展开状态
        for item in self.tree.get_children():
            if self.tree.item(item, "open"):
                item_text = self.tree.item(item, "text")
                self.expanded_items.add(item_text)
            self._collect_expanded_children(item)
        
        # 清空树
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if not project_names:
            return

        tree = load_project_tree()
        
        for root in tree.get_root_nodes():
            if root.name not in project_names:
                continue
            if root.is_archived and not self.show_archived_var.get():
                continue
            
            stats = get_project_stats(root.id, include_children=False)
            child_count = len(root.get_children())
            
            root_id = self.tree.insert("", "end", text=root.name, 
                                       values=(format_duration(stats['total']), 
                                              format_duration(stats['today']),
                                              f"{child_count}个"))
            
            # 恢复展开状态
            if root.name in self.expanded_items:
                self.tree.item(root_id, open=True)
            
            self._insert_children(root, root_id, project_names)

    def _insert_children(self, parent_node, parent_id, project_names):
        for child in parent_node.get_children():
            if child.name not in project_names:
                continue
            if child.is_archived and not self.show_archived_var.get():
                continue
            
            stats = get_project_stats(child.id, include_children=False)
            child_count = len(child.get_children())
            
            child_id = self.tree.insert(parent_id, "end", text=child.name,
                                       values=(format_duration(stats['total']),
                                              format_duration(stats['today']),
                                              f"{child_count}个"))
            
            self._insert_children(child, child_id, project_names)

    def _collect_expanded_children(self, parent_id):
        for child_id in self.tree.get_children(parent_id):
            if self.tree.item(child_id, "open"):
                child_text = self.tree.item(child_id, "text")
                self.expanded_items.add(child_text)
            self._collect_expanded_children(child_id)

    def _on_tree_double_click(self, event):
        item = self.tree.selection()[0] if self.tree.selection() else None
        if item:
            item_text = self.tree.item(item, "text")
            self.project_select_var.set(item_text)

    def _on_tree_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.selected_project_id = self._get_project_id_from_tree_item(item)
            if self.selected_project_id:
                try:
                    self.project_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    self.project_menu.grab_release()

    def _get_project_id_from_tree_item(self, item):
        item_text = self.tree.item(item, "text")
        projects = get_all_projects_flat()
        for p in projects:
            # 修复：移除了 and not p['is_archived']，让程序能正确找到已归档的项目ID
            if p['name'] == item_text:
                return p['id']
        return None

    def _menu_new_child(self):
        if self.selected_project_id:
            from tkinter import simpledialog
            name = simpledialog.askstring("新建子项目", "子项目名称:")
            if name:
                create_project(name, self.selected_project_id)
                self.refresh_all()

    def _menu_rename(self):
        if self.selected_project_id:
            from tkinter import simpledialog
            name = simpledialog.askstring("重命名", "新名称:", initialvalue=self._get_project_name(self.selected_project_id))
            if name:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("UPDATE projects SET project_name = ? WHERE id = ?", (name, self.selected_project_id))
                self.refresh_all()

    def _menu_archive(self):
        if self.selected_project_id:
            tree = load_project_tree()
            node = tree.get_node(self.selected_project_id)
            if node and node.is_archived:
                restore_project(self.selected_project_id)
            else:
                archive_project(self.selected_project_id)

    def _menu_delete(self):
        if self.selected_project_id:
            from tkinter import messagebox
            if messagebox.askyesno("确认删除", "确定要删除这个项目吗?"):
                delete_project(self.selected_project_id, delete_children=False)
                self.refresh_all()

    def _get_project_name(self, project_id):
        projects = get_all_projects_flat()
        for p in projects:
            if p['id'] == project_id:
                return p['name']
        return ""

    def toggle_floating_window(self):
        if not hasattr(self, 'floating_window') or not self.floating_window.winfo_exists():
            self.floating_window = FloatingWindow(self)
        else:
            self.floating_window.lift()

    def _render_unassigned(self, df, all_projects):
        for child in self.unassigned_scroll.winfo_children():
            child.destroy()

        unassigned = df[df["project"].isna()]
        if unassigned.empty:
            ctk.CTkLabel(self.unassigned_scroll, text="暂无待分配任务", font=self.font_label).pack(anchor="w", padx=8, pady=8)
            return

        # 过滤掉"自动(最近)"选项
        project_options = [p for p in all_projects if p and p != "自动(最近)"] if all_projects else []

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

            project_selector = ctk.CTkOptionMenu(action, values=project_options, width=120, dynamic_resizing=False)
            project_selector.pack(side="left", padx=4)
            
            ctk.CTkButton(
                action, text="分配", width=60,
                command=lambda fp=file_path, ps=project_selector: self.assign_file(fp, ps.get())
            ).pack(side="left", padx=4)


if __name__ == "__main__":
    app = Dashboard()
    app.mainloop()
