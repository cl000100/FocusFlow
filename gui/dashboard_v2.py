import sys
import os
import sqlite3
from datetime import datetime

# 【关键点】：这几行必须放在 from core... 的最前面！
# 这样系统才能知道去上一级目录找 core 文件夹
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 引入 PySide6 组件
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTreeView, QHeaderView, QLabel, QPushButton, QMenu,
    QAbstractItemView, QDialog, QComboBox, QDialogButtonBox, QMessageBox, QInputDialog
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction, QFont, QIcon
from PySide6.QtCore import Qt, QModelIndex, QTimer
from PySide6.QtWidgets import QSpinBox, QFormLayout, QGroupBox

# 引入我们自己写的核心库
from core.database import get_connection, init_db
from core.project_tree import (
    load_project_tree, get_project_stats, get_all_projects_flat, 
    get_project_files, create_project, delete_project, 
    archive_project, remove_file_assignment
)
def format_duration(seconds: float) -> str:
    seconds = int(round(seconds or 0))
    if seconds < 0: return "0秒"
    if seconds < 3600:
        return f"{seconds // 60}分{seconds % 60}秒"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}时{minutes}分"


class DashboardV2(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self.setWindowTitle("FocusFlow - 专业工时看板 (PySide6)")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)
        
        # 记录树节点的展开状态和选中状态
        self.expanded_paths = set()
        self.selected_path = None

        self.setup_ui()
        self.apply_modern_theme()
        # 连接设置按钮
        self.btn_settings.clicked.connect(self.open_settings)
        
        # 初次加载数据
        self.refresh_data()
        
        # 【关键】：静默自动刷新引擎，每 3 秒刷新一次界面数据
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(3000) 

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.refresh_data()

    def setup_ui(self):
        # 主控 Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 顶栏 (Header)
        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(60)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        title_label = QLabel("FocusFlow / 生产力控制中心")
        title_label.setObjectName("titleLabel")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # 【新增】：顶部中心的状态指示器（灵动岛）
        self.lbl_status = QLabel("状态：等待连接...")
        self.lbl_status.setObjectName("statusLabel")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.lbl_status)
        
        header_layout.addStretch()
        
        self.btn_refresh = QPushButton("↻ 刷新数据")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_settings = QPushButton("⚙ 设置")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        
        header_layout.addWidget(self.btn_refresh)
        header_layout.addWidget(self.btn_settings)
        
        main_layout.addWidget(header)

        # 主工作区 (左右分栏)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        
        # 左侧：项目树
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 5, 10)
        
        left_title = QLabel("📁 已分配项目")
        left_title.setObjectName("panelTitle")
        left_layout.addWidget(left_title)

        self.tree_projects = QTreeView()
        self.tree_projects.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree_projects.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_projects.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_projects.customContextMenuRequested.connect(self.show_project_menu)
        left_layout.addWidget(self.tree_projects)

        # 右侧：Inbox 待处理
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 10, 10, 10)
        
        right_title = QLabel("📥 Inbox 待分配记录")
        right_title.setObjectName("panelTitle")
        right_layout.addWidget(right_title)

        self.tree_inbox = QTreeView()
        self.tree_inbox.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree_inbox.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_inbox.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_inbox.customContextMenuRequested.connect(self.show_inbox_menu)
        right_layout.addWidget(self.tree_inbox)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800]) # 默认比例 1:2
        
        main_layout.addWidget(splitter)

        # 初始化数据模型
        self.model_projects = QStandardItemModel()
        self.model_projects.setHorizontalHeaderLabels(["项目名称", "总计", "今日"])
        self.tree_projects.setModel(self.model_projects)
        self.tree_projects.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree_projects.setColumnWidth(1, 80)
        self.tree_projects.setColumnWidth(2, 80)

        self.model_inbox = QStandardItemModel()
        self.model_inbox.setHorizontalHeaderLabels(["应用/窗口名", "总计", "今日", "最后活跃"])
        self.tree_inbox.setModel(self.model_inbox)
        self.tree_inbox.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree_inbox.setColumnWidth(1, 80)
        self.tree_inbox.setColumnWidth(2, 80)
        self.tree_inbox.setColumnWidth(3, 140)

    def show_project_menu(self, pos):
        index = self.tree_projects.indexAt(pos)
        menu = QMenu(self)
        
        # 如果点在空白处，弹出新建根项目
        if not index.isValid():
            action_new = menu.addAction("➕ 新建根项目")
            action_new.triggered.connect(lambda: self.action_new_project(None))
            menu.exec_(self.tree_projects.viewport().mapToGlobal(pos))
            return

        # 获取节点藏在底层的数据
        item_node = self.model_projects.itemFromIndex(index.siblingAtColumn(0))
        project_id = item_node.data(Qt.UserRole + 1)
        file_path = item_node.data(Qt.UserRole + 2)

        if file_path:
            # 这是一个具体的文件记录
            action_remove = menu.addAction("↩️ 移出该记录 (退回待分配)")
            action_remove.triggered.connect(lambda: self.action_remove_file(file_path))
        elif project_id:
            # 这是一个项目文件夹
            action_new_sub = menu.addAction("➕ 新建子项目")
            action_new_sub.triggered.connect(lambda: self.action_new_project(project_id))
            
            action_rename = menu.addAction("✏️ 重命名项目")
            action_rename.triggered.connect(lambda: self.action_rename_project(project_id, item_node.text().replace("📁 ", "")))
            
            menu.addSeparator()
            
            action_archive = menu.addAction("📦 归档 (隐藏不统计)")
            action_archive.triggered.connect(lambda: self.action_archive_project(project_id))
            
            action_delete = menu.addAction("❌ 删除项目")
            action_delete.triggered.connect(lambda: self.action_delete_project(project_id))

        menu.exec_(self.tree_projects.viewport().mapToGlobal(pos))

    # ============= 左侧菜单的动作逻辑 =============

    def action_new_project(self, parent_id):
        name, ok = QInputDialog.getText(self, "新建项目", "请输入项目名称：")
        if ok and name.strip():
            create_project(name.strip(), parent_id)
            self.refresh_data()

    def action_rename_project(self, project_id, old_name):
        new_name, ok = QInputDialog.getText(self, "重命名项目", "请输入新名称：", text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            conn = get_connection()
            conn.execute("UPDATE projects SET project_name = ? WHERE id = ?", (new_name.strip(), project_id))
            conn.commit()
            conn.close()
            self.refresh_data()

    def action_remove_file(self, file_path):
        remove_file_assignment(file_path)
        self.refresh_data() # 瞬间刷新，左边消失，右边Inbox出现！

    def action_archive_project(self, project_id):
        if archive_project(project_id):
            self.refresh_data()
        else:
            QMessageBox.warning(self, "归档失败", "只有【没有子项目】的底层节点才能归档。")

    def action_delete_project(self, project_id):
        reply = QMessageBox.question(self, "确认删除", "确定要删除该项目吗？(其绑定的工时记录将被退回 Inbox)", 
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if delete_project(project_id, delete_children=False):
                self.refresh_data()
            else:
                QMessageBox.warning(self, "删除失败", "请先删除它包含的子项目！")

    def show_inbox_menu(self, pos):
        index = self.tree_inbox.indexAt(pos)
        if not index.isValid(): return
        
        # 提取我们在上一步悄悄存进去的数据
        item_name_node = self.model_inbox.itemFromIndex(index.siblingAtColumn(0))
        file_path = item_name_node.data(Qt.UserRole + 1)
        app_name = item_name_node.data(Qt.UserRole + 2)

        menu = QMenu(self)
        
        action_assign = menu.addAction("➡️ 分配到左侧项目...")
        action_assign.triggered.connect(lambda: self.action_assign_item(file_path))
        
        menu.addSeparator()
        
        action_ignore = menu.addAction("🚫 永久忽略 (加入黑名单)")
        action_ignore.triggered.connect(lambda: self.action_ignore_item(app_name, file_path))
        
        menu.exec_(self.tree_inbox.viewport().mapToGlobal(pos))

    def action_assign_item(self, file_path):
        # 1. 获取所有未归档的项目
        projects = [p for p in get_all_projects_flat() if not p['is_archived']]
        if not projects:
            QMessageBox.warning(self, "提示", "请先在左侧新建一个项目！")
            return
            
        # 2. 构造下拉选择弹窗
        dialog = QDialog(self)
        dialog.setWindowTitle("分配记录")
        dialog.setMinimumWidth(300)
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("请选择要分配到的项目："))
        combo = QComboBox()
        for p in projects:
            # userData 存 project_id，显示文字存项目名
            combo.addItem(p['name'], p['id'])
        layout.addWidget(combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        # 3. 如果用户点击确认，写入数据库
        if dialog.exec() == QDialog.Accepted:
            project_id = combo.currentData()
            conn = get_connection()
            conn.execute(
                "INSERT OR REPLACE INTO file_assignment (file_path, project_id, assigned_at) VALUES (?, ?, ?)",
                (file_path, project_id, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            # 瞬间静默刷新界面：右侧消失，左侧时长增加！
            self.refresh_data()

    def action_ignore_item(self, app_name, file_path):
        # 弹出一个输入框，默认填入 app_name。用户可以改写为特定路径，也可以直接确认
        text, ok = QInputDialog.getText(
            self, 
            "添加黑名单", 
            "输入要永久忽略的关键词 (如应用名或窗口名)：\n后续包含该词的记录都不会再出现。",
            text=app_name
        )
        if ok and text.strip():
            keyword = text.strip()
            conn = get_connection()
            try:
                conn.execute("INSERT INTO ignore_list (keyword, created_at) VALUES (?, ?)", (keyword, datetime.now().isoformat()))
                conn.commit()
                QMessageBox.information(self, "成功", f"已将 [{keyword}] 加入黑名单！")
                self.refresh_data() # 瞬间刷新，垃圾记录消失
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "提示", "该关键词已在黑名单中。")
            finally:
                conn.close()

    def save_tree_state(self, tree_view, parent_index=QModelIndex(), current_path=""):
        # 保存展开状态
        model = tree_view.model()
        for i in range(model.rowCount(parent_index)):
            index = model.index(i, 0, parent_index)
            item_name = model.data(index)
            path = f"{current_path}/{item_name}"
            
            if tree_view.isExpanded(index):
                self.expanded_paths.add(path)
            
            if tree_view.selectionModel().isSelected(index):
                self.selected_path = path

            if model.hasChildren(index):
                self.save_tree_state(tree_view, index, path)

    def restore_tree_state(self, tree_view, parent_index=QModelIndex(), current_path=""):
        # 恢复展开状态
        model = tree_view.model()
        for i in range(model.rowCount(parent_index)):
            index = model.index(i, 0, parent_index)
            item_name = model.data(index)
            path = f"{current_path}/{item_name}"
            
            if path in self.expanded_paths:
                tree_view.setExpanded(index, True)
            
            if path == self.selected_path:
                tree_view.selectionModel().select(index, tree_view.selectionModel().ClearAndSelect | tree_view.selectionModel().Rows)

            if model.hasChildren(index):
                self.restore_tree_state(tree_view, index, path)

    def refresh_data(self):
        # --- 【新增】：更新顶部实时状态胶囊 ---
        conn = get_connection()
        status_row = conn.execute("SELECT is_idle, idle_seconds, app_name, file_path FROM runtime_status WHERE id=1").fetchone()
        conn.close()
        
        if status_row:
            is_idle, idle_seconds, app_name, file_path = status_row
            if is_idle:
                self.lbl_status.setText(f"💤 闲置中 (已空闲 {int(idle_seconds)} 秒)")
                # 橙色警告样式
                self.lbl_status.setStyleSheet("color: #F6AD55; background-color: #2D3748; padding: 6px 16px; border-radius: 12px; font-weight: bold; font-size: 13px;")
            else:
                display_path = file_path if file_path.startswith("[") else os.path.basename(file_path)
                if not display_path or display_path == "N/A": display_path = app_name
                self.lbl_status.setText(f"⏱️ 追踪中: {app_name} | {display_path}")
                # 绿色工作样式
                self.lbl_status.setStyleSheet("color: #68D391; background-color: #22543D; padding: 6px 16px; border-radius: 12px; font-weight: bold; font-size: 13px;")
        # ---------------------------------------

        # 1. 记录刷新前的状态
        self.expanded_paths.clear()
        self.save_tree_state(self.tree_projects)
        
        # 2. 清空模型
        self.model_projects.removeRows(0, self.model_projects.rowCount())
        self.model_inbox.removeRows(0, self.model_inbox.rowCount())
        
        # 3. 加载左侧项目树
        tree = load_project_tree()
        for root in tree.get_root_nodes():
            if not root.is_archived:
                self._build_project_tree_recursive(root, self.model_projects.invisibleRootItem())
                
        # 4. 加载右侧 Inbox 待分配
        self._load_inbox_data()

        # 5. 恢复状态
        self.restore_tree_state(self.tree_projects)

    def _build_project_tree_recursive(self, node, parent_item):
        stats = get_project_stats(node.id, include_children=False)
        
        # 1. 挂载项目节点本身
        item_name = QStandardItem(f"📁 {node.name}")
        item_name.setData(node.id, Qt.UserRole + 1) # 【关键】给它打个标记，证明它是个“项目”
        
        item_total = QStandardItem(format_duration(stats['total']))
        item_today = QStandardItem(format_duration(stats['today']))
        item_total.setSelectable(False)
        item_today.setSelectable(False)
        parent_item.appendRow([item_name, item_total, item_today])
        
        # 2. 挂载这个项目底下已经分配的文件/程序记录
        files = get_project_files(node.id)
        # 用集合去重，避免同一路径多次显示
        seen_paths = set()
        for f in files:
            file_path = f.get('file_path', '')
            if not file_path or file_path in seen_paths: continue
            seen_paths.add(file_path)
            
            # 【修复点】：安全获取字段，兼容不同的命名
            app_name = f.get('app_name', '--')
            total_dur = f.get('total_duration', f.get('total', 0))
            today_dur = f.get('today_duration', f.get('today', 0))
            
            # 处理显示名称
            display_name = file_path if file_path.startswith("[") else os.path.basename(file_path)
            if not display_name or display_name == "N/A": 
                display_name = app_name
                
            file_item = QStandardItem(f"📄 {display_name}")
            file_item.setToolTip(f"完整路径: {file_path}\n应用: {app_name}")
            file_item.setData(file_path, Qt.UserRole + 2) # 标记为文件
            
            f_total = QStandardItem(format_duration(total_dur))
            f_today = QStandardItem(format_duration(today_dur))
            f_total.setSelectable(False)
            f_today.setSelectable(False)
            
            item_name.appendRow([file_item, f_total, f_today])

        # 3. 递归挂载子项目
        for child in node.get_children():
            if not child.is_archived:
                self._build_project_tree_recursive(child, item_name)

    def _load_inbox_data(self):
        conn = get_connection()
        cursor = conn.cursor()
        
        # 核心 SQL: 查出所有 activity_log 中，file_path 不在 file_assignment 中，且不在 ignore_list 中的记录
        cursor.execute("""
            SELECT 
                al.app_name, 
                al.file_path,
                SUM(al.duration) as total,
                SUM(CASE WHEN DATE(al.timestamp) = DATE('now', 'localtime') THEN al.duration ELSE 0 END) as today,
                MAX(al.timestamp) as last_seen
            FROM activity_log al
            LEFT JOIN file_assignment fa ON al.file_path = fa.file_path
            LEFT JOIN ignore_list il ON al.app_name LIKE '%' || il.keyword || '%' OR al.file_path LIKE '%' || il.keyword || '%'
            WHERE fa.file_path IS NULL AND il.keyword IS NULL
            GROUP BY al.app_name, al.file_path
            ORDER BY last_seen DESC
        """)
        
        for row in cursor.fetchall():
            app_name, file_path, total, today, last_seen = row
            
            # 如果是浏览器等无具体路径的，就显示窗口名；如果有具体路径，提取文件名
            display_name = file_path if file_path.startswith("[") else os.path.basename(file_path)
            if not display_name or display_name == "N/A":
                display_name = f"[{app_name}] 未知记录"
                
            # 格式化时间戳
            try:
                dt = datetime.fromisoformat(last_seen.split('.')[0])
                time_str = dt.strftime("%m-%d %H:%M")
            except:
                time_str = last_seen
                
            item_name = QStandardItem(f"{display_name}")
            item_name.setToolTip(f"完整路径: {file_path}\n应用: {app_name}")
            item_name.setData(file_path, Qt.UserRole + 1)
            item_name.setData(app_name, Qt.UserRole + 2)
            item_total = QStandardItem(format_duration(total))
            item_today = QStandardItem(format_duration(today))
            item_last = QStandardItem(time_str)
            
            self.model_inbox.appendRow([item_name, item_total, item_today, item_last])
            
        conn.close()

    def apply_modern_theme(self):
        # PySide6 的强大之处：使用类似 CSS 的 QSS 控制极其精细的样式
        qss = """
        QMainWindow {
            background-color: #1E1E1E;
        }
        QWidget#header {
            background-color: #252526;
            border-bottom: 1px solid #333333;
        }
        QLabel#titleLabel {
            color: #CCCCCC;
            font-size: 16px;
            font-weight: bold;
            font-family: "Segoe UI", "Avenir Next", sans-serif;
        }
        QLabel#panelTitle {
            color: #9CDCFE;
            font-size: 14px;
            font-weight: bold;
            padding: 5px;
        }
        QPushButton {
            background-color: #0E639C;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 16px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #1177BB;
        }
        QTreeView {
            background-color: #1E1E1E;
            color: #D4D4D4;
            border: 1px solid #333333;
            border-radius: 6px;
            padding: 4px;
            font-size: 13px;
        }
        QTreeView::item {
            padding: 6px;
            border-radius: 4px;
        }
        QTreeView::item:hover {
            background-color: #2A2D2E;
        }
        QTreeView::item:selected {
            background-color: #37373D;
            color: #FFFFFF;
        }
        QHeaderView::section {
            background-color: #252526;
            color: #999999;
            padding: 6px;
            border: none;
            border-right: 1px solid #333333;
            border-bottom: 1px solid #333333;
            font-weight: bold;
        }
        QSplitter::handle {
            background-color: #333333;
        }
        QMenu {
            background-color: #252526;
            color: #CCCCCC;
            border: 1px solid #333333;
        }
        QMenu::item:selected {
            background-color: #0E639C;
            color: white;
        }
        """
        self.setStyleSheet(qss)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统设置")
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)
        
        # --- 采集设置 ---
        group_gather = QGroupBox("后台采集设置")
        form = QFormLayout(group_gather)
        
        self.spin_idle = QSpinBox()
        self.spin_idle.setRange(10, 300)
        self.spin_idle.setSuffix(" 秒")
        form.addRow("空闲判定阈值:", self.spin_idle)
        
        # 读库获取当前值
        conn = get_connection()
        row = conn.execute("SELECT value FROM system_config WHERE key='idle_threshold'").fetchone()
        if row:
            self.spin_idle.setValue(int(row[0]))
        layout.addWidget(group_gather)
        
        # --- 危险操作区 ---
        group_danger = QGroupBox("危险操作 (Danger Zone)")
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
        
        # --- 底部按钮 ---
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save_settings(self):
        conn = get_connection()
        conn.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES ('idle_threshold', ?)", 
                     (str(self.spin_idle.value()),))
        conn.commit()
        conn.close()
        QMessageBox.information(self, "成功", "设置已保存！后台服务将在几秒内自动应用新阈值。")
        self.accept()

    def clear_logs(self):
        if QMessageBox.question(self, "确认", "确定清空所有工时数据吗？项目结构将保留。") == QMessageBox.Yes:
            conn = get_connection()
            conn.execute("DELETE FROM activity_log")
            conn.execute("DELETE FROM runtime_status")
            conn.commit()
            conn.close()
            QMessageBox.information(self, "完成", "记录已清空！")
            self.accept()

    def factory_reset(self):
        if QMessageBox.question(self, "警告", "这将清空所有项目、文件分配、黑名单和工时，确定吗？", 
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            conn = get_connection()
            for table in ["activity_log", "projects", "file_assignment", "project_map", "project_archive", "ignore_list"]:
                conn.execute(f"DELETE FROM {table}")
            conn.commit()
            conn.close()
            QMessageBox.information(self, "完成", "已恢复出厂设置！")
            self.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 强制所有字体更清晰
    font = QApplication.font()
    font.setPointSize(11)
    app.setFont(font)
    
    window = DashboardV2()
    window.show()
    sys.exit(app.exec())