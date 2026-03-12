import sys
import os
import sqlite3
from datetime import datetime

# 确保能导入 core 模块
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTreeView, QHeaderView, QLabel, QPushButton, QMenu,
    QAbstractItemView, QDialog, QComboBox, QDialogButtonBox, QMessageBox, 
    QInputDialog, QSpinBox, QFormLayout, QGroupBox, QCheckBox, QListWidget, QListWidgetItem
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont
from PySide6.QtCore import Qt, QModelIndex, QTimer, QItemSelectionModel

from core.database import get_connection, init_db
from core.project_tree import (
    load_project_tree, get_project_stats, get_all_projects_flat, 
    get_project_files, create_project, delete_project, 
    archive_project, restore_project, remove_file_assignment
)

def format_duration(seconds: float) -> str:
    seconds = int(round(seconds or 0))
    if seconds < 0: return "0秒"
    if seconds < 3600:
        return f"{seconds // 60}分{seconds % 60}秒"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}时{minutes}分"

# ================= 弹窗组件 (保持不变) =================
class BlacklistDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🚫 黑名单管理")
        self.setMinimumSize(400, 300)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("包含以下关键词的窗口/程序将被彻底忽略："))
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        btn_layout = QHBoxLayout()
        btn_remove = QPushButton("移出黑名单")
        btn_remove.clicked.connect(self.remove_selected)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_remove)
        layout.addLayout(btn_layout)
        self.load_data()
    def load_data(self):
        self.list_widget.clear()
        conn = get_connection()
        for row in conn.execute("SELECT id, keyword FROM ignore_list"):
            item = QListWidgetItem(row[1])
            item.setData(Qt.UserRole, row[0])
            self.list_widget.addItem(item)
        conn.close()
    def remove_selected(self):
        selected = self.list_widget.currentItem()
        if selected:
            conn = get_connection()
            conn.execute("DELETE FROM ignore_list WHERE id = ?", (selected.data(Qt.UserRole),))
            conn.commit()
            conn.close()
            self.load_data()

class ProjectRulesDialog(QDialog):
    def __init__(self, project_id, project_name, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.setWindowTitle(f"编辑规则 - {project_name}")
        self.setMinimumSize(400, 300)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("当路径/窗口名包含以下关键词时，自动分配到本项目："))
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 添加规则")
        btn_add.clicked.connect(self.add_rule)
        btn_remove = QPushButton("❌ 删除规则")
        btn_remove.clicked.connect(self.remove_rule)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        layout.addLayout(btn_layout)
        self.load_data()
    def load_data(self):
        self.list_widget.clear()
        conn = get_connection()
        for row in conn.execute("SELECT id, rule_path FROM project_map WHERE project_id = ?", (self.project_id,)):
            item = QListWidgetItem(row[1])
            item.setData(Qt.UserRole, row[0])
            self.list_widget.addItem(item)
        conn.close()
    def add_rule(self):
        text, ok = QInputDialog.getText(self, "添加规则", "输入路径/标题匹配关键词：")
        if ok and text.strip():
            conn = get_connection()
            conn.execute("INSERT INTO project_map (project_id, rule_path) VALUES (?, ?)", (self.project_id, text.strip()))
            conn.commit()
            conn.close()
            self.load_data()
    def remove_rule(self):
        selected = self.list_widget.currentItem()
        if selected:
            conn = get_connection()
            conn.execute("DELETE FROM project_map WHERE id = ?", (selected.data(Qt.UserRole),))
            conn.commit()
            conn.close()
            self.load_data()

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统设置")
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)
        group_gather = QGroupBox("后台采集设置")
        form = QFormLayout(group_gather)
        self.spin_idle = QSpinBox()
        self.spin_idle.setRange(10, 300)
        self.spin_idle.setSuffix(" 秒")
        form.addRow("空闲判定阈值:", self.spin_idle)
        conn = get_connection()
        row = conn.execute("SELECT value FROM system_config WHERE key='idle_threshold'").fetchone()
        if row: self.spin_idle.setValue(int(row[0]))
        layout.addWidget(group_gather)
        group_danger = QGroupBox("危险操作")
        v_danger = QVBoxLayout(group_danger)
        btn_clear_log = QPushButton("🗑️ 清空所有工时记录 (保留项目)")
        btn_clear_log.setStyleSheet("background-color: #A31515;")
        btn_clear_log.clicked.connect(self.clear_logs)
        v_danger.addWidget(btn_clear_log)
        btn_factory = QPushButton("⚠️ 恢复出厂设置 (清空所有)")
        btn_factory.setStyleSheet("background-color: #800000;")
        btn_factory.clicked.connect(self.factory_reset)
        v_danger.addWidget(btn_factory)
        layout.addWidget(group_danger)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def save_settings(self):
        conn = get_connection()
        conn.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES ('idle_threshold', ?)", (str(self.spin_idle.value()),))
        conn.commit()
        conn.close()
        self.accept()
    def clear_logs(self):
        if QMessageBox.question(self, "确认", "确定清空工时数据吗？") == QMessageBox.Yes:
            conn = get_connection()
            conn.execute("DELETE FROM activity_log")
            conn.execute("DELETE FROM runtime_status")
            conn.commit()
            conn.close()
            self.accept()
    def factory_reset(self):
        if QMessageBox.question(self, "警告", "这将清空所有项目和配置，确定吗？", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            conn = get_connection()
            for table in ["activity_log", "projects", "file_assignment", "project_map", "project_archive", "ignore_list"]:
                conn.execute(f"DELETE FROM {table}")
            conn.commit()
            conn.close()
            self.accept()

# ================= 主窗口 =================

class DashboardV2(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()  
        self.setWindowTitle("FocusFlow - 专业工时看板")
        self.resize(1300, 800)
        
        # 完美状态记录容器
        self.expanded_uids = set()
        self.selected_uid_left = None
        self.selected_path_right = None

        self.setup_ui()
        self.apply_modern_theme()
        
        self.refresh_data()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(3000)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. 紧凑型顶栏 (Header) ---
        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(50)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 0, 15, 0)
        
        title_label = QLabel("FocusFlow")
        title_label.setObjectName("titleLabel")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.lbl_status = QLabel("状态：等待连接...")
        self.lbl_status.setObjectName("statusLabel")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.lbl_status)
        header_layout.addStretch()
        
        self.btn_blacklist = QPushButton("🚫 黑名单")
        self.btn_blacklist.clicked.connect(self.open_blacklist)
        self.btn_settings = QPushButton("⚙ 设置")
        self.btn_settings.clicked.connect(self.open_settings)
        header_layout.addWidget(self.btn_blacklist)
        header_layout.addWidget(self.btn_settings)
        main_layout.addWidget(header)

        # --- 2. 极致紧凑的项目大盘 (Stats Bar) ---
        self.lbl_stats_bar = QLabel("📊 当前关注项目: 未选中   |   今日累积: 0分0秒   |   历史总计: 0分0秒")
        self.lbl_stats_bar.setObjectName("statsBar")
        self.lbl_stats_bar.setFixedHeight(35)
        main_layout.addWidget(self.lbl_stats_bar)

        # --- 3. 主分栏 ---
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：项目树
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 5, 10)
        left_header = QHBoxLayout()
        left_header.addWidget(QLabel("📁 项目管理", objectName="panelTitle"))
        self.chk_archived = QCheckBox("显示归档")
        self.chk_archived.stateChanged.connect(self.refresh_data)
        left_header.addWidget(self.chk_archived)
        left_layout.addLayout(left_header)

        self.tree_projects = QTreeView()
        self.tree_projects.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree_projects.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_projects.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_projects.customContextMenuRequested.connect(self.show_project_menu)
        left_layout.addWidget(self.tree_projects)

        # 右侧：Inbox
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 10, 10, 10)
        right_layout.addWidget(QLabel("📥 Inbox 待分配 (自动捕获)", objectName="panelTitle"))
        
        self.tree_inbox = QTreeView()
        self.tree_inbox.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree_inbox.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_inbox.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_inbox.customContextMenuRequested.connect(self.show_inbox_menu)
        right_layout.addWidget(self.tree_inbox)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([450, 850])
        main_layout.addWidget(splitter)

        # --- 4. 配置模型列 ---
        self.model_projects = QStandardItemModel()
        self.model_projects.setHorizontalHeaderLabels(["名称", "总计", "今日"])
        self.tree_projects.setModel(self.model_projects)
        self.tree_projects.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree_projects.setColumnWidth(1, 80)
        self.tree_projects.setColumnWidth(2, 80)

        self.model_inbox = QStandardItemModel()
        self.model_inbox.setHorizontalHeaderLabels(["窗口/文件名", "所在目录 / 应用", "总计", "今日", "最后活跃"])
        self.tree_inbox.setModel(self.model_inbox)
        self.tree_inbox.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree_inbox.setColumnWidth(0, 220)
        self.tree_inbox.setColumnWidth(2, 70)
        self.tree_inbox.setColumnWidth(3, 70)
        self.tree_inbox.setColumnWidth(4, 110)

    def open_settings(self):
        if SettingsDialog(self).exec(): self.refresh_data()

    def open_blacklist(self):
        BlacklistDialog(self).exec()
        self.refresh_data()

    # ================= 完美保存/恢复状态引擎 =================
    def save_tree_state(self):
        # 左侧状态
        self.expanded_uids.clear()
        self.selected_uid_left = None
        self._save_left_recursive(QModelIndex())
        
        # 右侧状态 (安全获取当前选中路径)
        self.selected_path_right = None
        idx = self.tree_inbox.selectionModel().currentIndex()
        if idx.isValid():
            item = self.model_inbox.itemFromIndex(idx.siblingAtColumn(0))
            if item:
                self.selected_path_right = item.data(Qt.UserRole + 1)
            
        # 记录滚动条位置
        self.scroll_l = self.tree_projects.verticalScrollBar().value()
        self.scroll_r = self.tree_inbox.verticalScrollBar().value()

    def _save_left_recursive(self, parent_index):
        model = self.tree_projects.model()
        for i in range(model.rowCount(parent_index)):
            index = model.index(i, 0, parent_index)
            pid = model.data(index, Qt.UserRole + 1)
            fpath = model.data(index, Qt.UserRole + 2)
            uid = f"P_{pid}" if pid else f"F_{fpath}"
            
            if self.tree_projects.isExpanded(index): self.expanded_uids.add(uid)
            if self.tree_projects.selectionModel().isSelected(index): self.selected_uid_left = uid
            if model.hasChildren(index): self._save_left_recursive(index)

    def restore_tree_state(self):
        # 恢复左侧
        self._restore_left_recursive(QModelIndex())
        
        # 恢复右侧选中状态
        if self.selected_path_right:
            for i in range(self.model_inbox.rowCount()):
                item = self.model_inbox.item(i, 0)
                if item and item.data(Qt.UserRole + 1) == self.selected_path_right:
                    # 重新高亮这一行
                    self.tree_inbox.selectionModel().select(item.index(), QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
                    # 把焦点指回去，防止键盘下滚失效
                    self.tree_inbox.setCurrentIndex(item.index())
                    break
                    
        # 恢复滚动条位置
        self.tree_projects.verticalScrollBar().setValue(getattr(self, 'scroll_l', 0))
        self.tree_inbox.verticalScrollBar().setValue(getattr(self, 'scroll_r', 0))

    def _restore_left_recursive(self, parent_index):
        model = self.tree_projects.model()
        for i in range(model.rowCount(parent_index)):
            index = model.index(i, 0, parent_index)
            pid = model.data(index, Qt.UserRole + 1)
            fpath = model.data(index, Qt.UserRole + 2)
            uid = f"P_{pid}" if pid else f"F_{fpath}"
            
            if uid in self.expanded_uids: self.tree_projects.setExpanded(index, True)
            if uid == self.selected_uid_left:
                self.tree_projects.selectionModel().select(index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
                self.tree_projects.setCurrentIndex(index)
            if model.hasChildren(index): self._restore_left_recursive(index)

    # ================= 核心刷新逻辑 =================
    def refresh_data(self):
        self._auto_assign_from_rules()
        self.save_tree_state()
        
        # 【修改点3】：为了保证右侧完美不跳跃，采用“智能更新”而不是全删全建
        self.model_projects.removeRows(0, self.model_projects.rowCount())
        
        show_archived = self.chk_archived.isChecked()
        tree = load_project_tree()
        for root in tree.get_root_nodes():
            if not root.is_archived or show_archived:
                self._build_project_tree_recursive(root, self.model_projects.invisibleRootItem(), show_archived)
                
        self._load_inbox_data()
        self.restore_tree_state()
        self._update_top_stats()

    def _auto_assign_from_rules(self):
        conn = get_connection()
        rules = conn.execute("SELECT project_id, rule_path FROM project_map WHERE rule_path IS NOT NULL AND rule_path != ''").fetchall()
        if rules:
            unassigned = conn.execute("SELECT DISTINCT file_path FROM activity_log WHERE file_path NOT IN (SELECT file_path FROM file_assignment)").fetchall()
            for (fpath,) in unassigned:
                if not fpath: continue
                for pid, rule in rules:
                    if rule and rule in fpath:
                        conn.execute("INSERT OR IGNORE INTO file_assignment (file_path, project_id, assigned_at) VALUES (?, ?, ?)", 
                                     (fpath, pid, datetime.now().isoformat()))
                        break
        conn.commit()
        conn.close()

    def _update_top_stats(self):
        conn = get_connection()
        status_row = conn.execute("SELECT is_idle, idle_seconds, app_name, file_path FROM runtime_status WHERE id=1").fetchone()
        
        active_fpath = None
        if status_row:
            is_idle, idle_seconds, app_name, active_fpath = status_row
            if is_idle:
                self.lbl_status.setText(f"💤 闲置中 ({int(idle_seconds)} 秒)")
                self.lbl_status.setStyleSheet("color: #F6AD55; font-weight: bold; font-size: 13px;")
            else:
                # 【修改点2】：顶部标题优化。如果是带有括号的虚拟路径，说明它本身就是个网页或软件标题，直接全展示，别截取！
                if active_fpath.startswith("["):
                    display_title = active_fpath
                else:
                    # 如果是一个真的路径（如 C:/xx/xx.aep），就只展示文件名
                    display_title = os.path.basename(active_fpath)
                    
                self.lbl_status.setText(f"⏱️ 正在追踪: {app_name} | {display_title}")
                self.lbl_status.setStyleSheet("color: #68D391; font-weight: bold; font-size: 13px;")
        
        target_pid = None
        if self.selected_uid_left and self.selected_uid_left.startswith("P_"):
            target_pid = int(self.selected_uid_left[2:])
        elif active_fpath:
            row = conn.execute("SELECT project_id FROM file_assignment WHERE file_path = ?", (active_fpath,)).fetchone()
            if row: target_pid = row[0]
            
        if target_pid:
            p_name = conn.execute("SELECT project_name FROM projects WHERE id = ?", (target_pid,)).fetchone()[0]
            stats = get_project_stats(target_pid, include_children=True)
            self.lbl_stats_bar.setText(f"📊 当前关注项目:  {p_name}    |    今日累积:  {format_duration(stats['today'])}    |    历史总计:  {format_duration(stats['total'])}")
        else:
            self.lbl_stats_bar.setText("📊 当前关注项目:  未选中 / 无归属    |    今日累积:  0分0秒    |    历史总计:  0分0秒")
        conn.close()

    def _build_project_tree_recursive(self, node, parent_item, show_archived):
        stats = get_project_stats(node.id, include_children=False)
        prefix = "📦 [归档] " if node.is_archived else "📁 "
        item_name = QStandardItem(f"{prefix}{node.name}")
        item_name.setData(node.id, Qt.UserRole + 1) 
        item_name.setData(node.is_archived, Qt.UserRole + 3)
        
        item_total = QStandardItem(format_duration(stats['total']))
        item_today = QStandardItem(format_duration(stats['today']))
        item_total.setSelectable(False)
        item_today.setSelectable(False)
        parent_item.appendRow([item_name, item_total, item_today])
        
        # 【修复1：直接用精准 SQL 查本项目的子文件时间，解决时间为 0 的问题】
        conn = get_connection()
        files = conn.execute("""
            SELECT fa.file_path, MAX(al.app_name), 
                   COALESCE(SUM(al.duration), 0), 
                   COALESCE(SUM(CASE WHEN DATE(al.timestamp) = DATE('now', 'localtime') THEN al.duration ELSE 0 END), 0)
            FROM file_assignment fa
            LEFT JOIN activity_log al ON fa.file_path = al.file_path
            WHERE fa.project_id = ?
            GROUP BY fa.file_path
        """, (node.id,)).fetchall()
        conn.close()

        for fpath, app_name, f_total_dur, f_today_dur in files:
            if not fpath: continue
            d_name = fpath if fpath.startswith("[") else os.path.basename(fpath)
            
            file_item = QStandardItem(f"📄 {d_name}")
            file_item.setData(fpath, Qt.UserRole + 2)
            
            f_total = QStandardItem(format_duration(f_total_dur))
            f_today = QStandardItem(format_duration(f_today_dur))
            f_total.setSelectable(False)
            f_today.setSelectable(False)
            
            item_name.appendRow([file_item, f_total, f_today])

        for child in node.get_children():
            if not child.is_archived or show_archived:
                self._build_project_tree_recursive(child, item_name, show_archived)

        

    def _load_inbox_data(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT al.app_name, al.file_path, SUM(al.duration) as total,
                SUM(CASE WHEN DATE(al.timestamp) = DATE('now', 'localtime') THEN al.duration ELSE 0 END) as today,
                MAX(al.timestamp) as last_seen
            FROM activity_log al
            LEFT JOIN file_assignment fa ON al.file_path = fa.file_path
            LEFT JOIN ignore_list il ON al.app_name LIKE '%' || il.keyword || '%' OR al.file_path LIKE '%' || il.keyword || '%'
            WHERE fa.file_path IS NULL AND il.keyword IS NULL
            GROUP BY al.app_name, al.file_path
            ORDER BY last_seen DESC
        """)
        new_data = cursor.fetchall()
        conn.close()
        
        # 提取现有模型里的 file_path 集合，记住它们的真实行号
        existing_paths = {}
        for i in range(self.model_inbox.rowCount()):
            item = self.model_inbox.item(i, 0)
            existing_paths[item.data(Qt.UserRole + 1)] = i

        new_paths_set = {row[1] for row in new_data}
        
        # 【修复2 & 3：只要列表里的程序数量和种类没变，就绝对不重构列表！只精准更新时间的数字】
        if set(existing_paths.keys()) == new_paths_set:
            for row in new_data:
                app_name, file_path, total, today, last_seen = row
                try: time_str = datetime.fromisoformat(last_seen.split('.')[0]).strftime("%m-%d %H:%M")
                except: time_str = last_seen
                
                # 找到它在界面的真实行号，精准更新（杜绝张冠李戴！）
                row_idx = existing_paths[file_path]
                self.model_inbox.item(row_idx, 2).setText(format_duration(total))
                self.model_inbox.item(row_idx, 3).setText(format_duration(today))
                self.model_inbox.item(row_idx, 4).setText(time_str)
        else:
            # 只有当有全新的程序第一次加进来，或者被分配移出时，才重新排版
            self.model_inbox.removeRows(0, self.model_inbox.rowCount())
            for row in new_data:
                app_name, file_path, total, today, last_seen = row
                if file_path.startswith("["):
                    d_name, d_dir = file_path, app_name
                else:
                    d_name, d_dir = os.path.basename(file_path), os.path.dirname(file_path)
                    
                try: time_str = datetime.fromisoformat(last_seen.split('.')[0]).strftime("%m-%d %H:%M")
                except: time_str = last_seen
                    
                item_name = QStandardItem(d_name)
                item_name.setData(file_path, Qt.UserRole + 1)
                item_name.setData(app_name, Qt.UserRole + 2)
                item_name.setToolTip(file_path)
                
                item_dir = QStandardItem(d_dir)
                item_dir.setToolTip(file_path)
                
                self.model_inbox.appendRow([item_name, item_dir, QStandardItem(format_duration(total)), QStandardItem(format_duration(today)), QStandardItem(time_str)])

    # ================= 右键菜单交互 (保持不变) =================
    def show_project_menu(self, pos):
        index = self.tree_projects.indexAt(pos)
        menu = QMenu(self)
        if not index.isValid():
            menu.addAction("➕ 新建根项目").triggered.connect(lambda: self.action_new_project(None))
            menu.exec_(self.tree_projects.viewport().mapToGlobal(pos))
            return

        item_node = self.model_projects.itemFromIndex(index.siblingAtColumn(0))
        project_id = item_node.data(Qt.UserRole + 1)
        file_path = item_node.data(Qt.UserRole + 2)
        is_archived = item_node.data(Qt.UserRole + 3)

        if file_path:
            menu.addAction("↩️ 移出记录 (回 Inbox)").triggered.connect(lambda: self.action_remove_file(file_path))
        elif project_id:
            name_pure = item_node.text().replace("📁 ", "").replace("📦 [归档] ", "")
            menu.addAction("➕ 新建子项目").triggered.connect(lambda: self.action_new_project(project_id))
            menu.addAction("✏️ 重命名").triggered.connect(lambda: self.action_rename_project(project_id, name_pure))
            menu.addAction("🤖 编辑自动匹配规则...").triggered.connect(lambda: ProjectRulesDialog(project_id, name_pure, self).exec())
            menu.addSeparator()
            if is_archived:
                menu.addAction("🔄 取消归档 (恢复)").triggered.connect(lambda: self.action_restore_project(project_id))
            else:
                menu.addAction("📦 归档项目").triggered.connect(lambda: self.action_archive_project(project_id))
            menu.addAction("❌ 删除").triggered.connect(lambda: self.action_delete_project(project_id))

        menu.exec_(self.tree_projects.viewport().mapToGlobal(pos))

    def show_inbox_menu(self, pos):
        index = self.tree_inbox.indexAt(pos)
        if not index.isValid(): return
        item = self.model_inbox.itemFromIndex(index.siblingAtColumn(0))
        f_path = item.data(Qt.UserRole + 1)
        a_name = item.data(Qt.UserRole + 2)

        menu = QMenu(self)
        menu.addAction("➡️ 手动分配到项目...").triggered.connect(lambda: self.action_assign_item(f_path))
        menu.addSeparator()
        menu.addAction("🚫 永久忽略 (加黑名单)").triggered.connect(lambda: self.action_ignore_item(a_name))
        menu.exec_(self.tree_inbox.viewport().mapToGlobal(pos))

    # --- 动作实现 (保持不变) ---
    def action_new_project(self, parent_id):
        name, ok = QInputDialog.getText(self, "新建项目", "请输入项目名称：")
        if ok and name.strip():
            create_project(name.strip(), parent_id)
            self.refresh_data()
    def action_rename_project(self, project_id, old_name):
        new_name, ok = QInputDialog.getText(self, "重命名项目", "新名称：", text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            conn = get_connection()
            conn.execute("UPDATE projects SET project_name = ? WHERE id = ?", (new_name.strip(), project_id))
            conn.commit()
            conn.close()
            self.refresh_data()
    def action_remove_file(self, file_path):
        remove_file_assignment(file_path)
        self.refresh_data()
    def action_archive_project(self, project_id):
        if archive_project(project_id): self.refresh_data()
        else: QMessageBox.warning(self, "归档失败", "只有【没有子文件夹】的最底层项目才能归档哦。")
    def action_restore_project(self, project_id):
        restore_project(project_id)
        self.refresh_data()
    def action_delete_project(self, project_id):
        if QMessageBox.question(self, "确认删除", "确定要删除该项目吗？绑定的文件将被退回Inbox。") == QMessageBox.Yes:
            if delete_project(project_id, delete_children=False): self.refresh_data()
            else: QMessageBox.warning(self, "删除失败", "请先删除它包含的子项目！")
    def action_assign_item(self, file_path):
        projects = [p for p in get_all_projects_flat() if not p['is_archived']]
        if not projects: return QMessageBox.warning(self, "提示", "请先在左侧新建一个项目！")
        dlg = QDialog(self)
        dlg.setWindowTitle("分配记录")
        layout = QVBoxLayout(dlg)
        combo = QComboBox()
        for p in projects: combo.addItem(p['name'], p['id'])
        layout.addWidget(combo)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        if dlg.exec() == QDialog.Accepted:
            conn = get_connection()
            conn.execute("INSERT OR REPLACE INTO file_assignment (file_path, project_id, assigned_at) VALUES (?, ?, ?)", 
                         (file_path, combo.currentData(), datetime.now().isoformat()))
            conn.commit()
            conn.close()
            self.refresh_data()
    def action_ignore_item(self, app_name):
        text, ok = QInputDialog.getText(self, "添加黑名单", "输入要忽略的关键词：", text=app_name)
        if ok and text.strip():
            try:
                conn = get_connection()
                conn.execute("INSERT INTO ignore_list (keyword, created_at) VALUES (?, ?)", (text.strip(), datetime.now().isoformat()))
                conn.commit()
                conn.close()
                self.refresh_data()
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "提示", "该关键词已在黑名单中。")

    def apply_modern_theme(self):
        self.setStyleSheet("""
        QMainWindow { background-color: #1E1E1E; }
        QWidget#header { background-color: #252526; }
        QLabel#statsBar { background-color: #2D2D30; color: #D4D4D4; padding: 0px 20px; font-size: 13px; font-weight: bold; border-bottom: 1px solid #333333; }
        QLabel#titleLabel { color: #CCCCCC; font-size: 15px; font-weight: bold; }
        QLabel#panelTitle { color: #9CDCFE; font-size: 13px; font-weight: bold; padding: 5px; }
        QPushButton { background-color: #0E639C; color: white; border-radius: 4px; padding: 4px 12px; font-weight: bold; }
        QPushButton:hover { background-color: #1177BB; }
        QTreeView { background-color: #1E1E1E; color: #D4D4D4; border: 1px solid #333333; border-radius: 4px; padding: 4px; font-size: 13px; outline: 0;}
        QTreeView::item { padding: 4px; border-radius: 4px; }
        QTreeView::item:hover { background-color: #2A2D2E; }
        QTreeView::item:selected { background-color: #37373D; color: #FFFFFF; }
        QHeaderView::section { background-color: #252526; color: #999999; padding: 4px; border: none; border-right: 1px solid #333333; border-bottom: 1px solid #333333; font-weight: bold; font-size: 12px;}
        QMenu { background-color: #252526; color: #CCCCCC; border: 1px solid #333333; }
        QMenu::item:selected { background-color: #0E639C; color: white; }
        QListWidget { background-color: #1E1E1E; color: #D4D4D4; border: 1px solid #333333; }
        QListWidget::item:selected { background-color: #37373D; }
        QCheckBox { color: #D4D4D4; }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QApplication.font()
    font.setPointSize(11)
    app.setFont(font)
    window = DashboardV2()
    window.show()
    sys.exit(app.exec())