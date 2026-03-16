# 【新增】：导入 matplotlib 及其与 PySide6 的连接器
import matplotlib
matplotlib.use('QtAgg')  # 告诉 matplotlib 使用 Qt 引擎渲染
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta

import sys
import os
import sqlite3
from datetime import datetime, timedelta
import pandas as pd

# 确保能导入 core 模块
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QSplitter, QTreeView, QHeaderView, QLabel, QPushButton, QMenu,
    QAbstractItemView, QDialog, QComboBox, QDialogButtonBox, QMessageBox, 
    QInputDialog, QSpinBox, QFormLayout, QGroupBox, QCheckBox, QListWidget, QListWidgetItem,QFileDialog, QFrame, QSizePolicy, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QDateEdit
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont, QPainter, QColor, QPen, QBrush, QIcon, QAction, QPixmap
from PySide6.QtCore import Qt, QModelIndex, QTimer, QItemSelectionModel
from PySide6.QtWidgets import QSystemTrayIcon

from core.database import get_connection, init_db, get_db_path, set_db_path, get_config, set_config, get_date_range, get_projects_with_subprojects, get_project_tree, aggregate_project_timeline, build_project_timeline_tree
from core.project_tree import (
    load_project_tree, get_project_stats, get_all_projects_flat, 
    get_project_files, create_project, delete_project, 
    archive_project, restore_project, remove_file_assignment
)
from gui.data_management import DataManagementDialog
from core.database import get_unique_apps, get_unique_projects, query_timeline_data

import sys
import os
import subprocess

# ================= 可折叠分组组件 =================

class ProjectGroupWidget(QWidget):
    """项目分组组件（可折叠）"""
    
    def __init__(self, project_name, total_duration, start_time, end_time, record_count, parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.is_expanded = True
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 分组头
        self.header_btn = QPushButton()
        self.header_btn.setCheckable(True)
        self.header_btn.setChecked(True)
        self.header_btn.clicked.connect(self.toggle_expand)
        
        # 格式化时长
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        duration_str = f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟"
        
        self.header_btn.setText(f"▼ {project_name}  |  总计：{duration_str}  |  {start_time}-{end_time}  |  {record_count}条记录")
        self.header_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #9CDCFE;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 15px;
                border: 1px solid #3E3E3E;
                border-radius: 4px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #3E3E3E;
            }
            QPushButton:checked {
                background-color: #2D2D2D;
                border-bottom-left-radius: 0;
                border-bottom-right-radius: 0;
            }
        """)
        layout.addWidget(self.header_btn)
        
        # 内容区域
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        
        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["开始时间", "结束时间", "时长", "应用", "文件"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setMaximumHeight(600)
        
        self.content_layout.addWidget(self.table)
        layout.addWidget(self.content_widget)
    
    def toggle_expand(self):
        """切换展开/折叠"""
        self.is_expanded = self.header_btn.isChecked()
        self.content_widget.setVisible(self.is_expanded)
    
    def add_record(self, start_time, end_time, duration_str, app, file_path):
        """添加记录"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(start_time))
        self.table.setItem(row, 1, QTableWidgetItem(end_time))
        self.table.setItem(row, 2, QTableWidgetItem(duration_str))
        self.table.setItem(row, 3, QTableWidgetItem(app))
        self.table.setItem(row, 4, QTableWidgetItem(file_path if file_path and not file_path.startswith('[') else '-'))


class SubProjectGroupWidget(QWidget):
    """子项目分组组件（可折叠）"""
    
    def __init__(self, subproject_name, total_duration, record_count, parent=None):
        super().__init__(parent)
        self.subproject_name = subproject_name
        self.is_expanded = True
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)
        
        # 子分组头
        self.header_btn = QPushButton()
        self.header_btn.setCheckable(True)
        self.header_btn.setChecked(True)
        self.header_btn.clicked.connect(self.toggle_expand)
        
        # 格式化时长
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        duration_str = f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟"
        
        self.header_btn.setText(f"▼ {subproject_name}  ({duration_str} | {record_count}条)")
        self.header_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #CCCCCC;
                font-size: 12px;
                padding: 5px 10px;
                border: 1px solid #3E3E3E;
                border-radius: 3px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #3E3E3E;
            }
            QPushButton:checked {
                background-color: #333333;
                border-bottom-left-radius: 0;
                border-bottom-right-radius: 0;
            }
        """)
        layout.addWidget(self.header_btn)
        
        # 内容区域
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["开始时间", "结束时间", "时长", "应用", "文件"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setMaximumHeight(400)
        
        self.content_layout.addWidget(self.table)
        layout.addWidget(self.content_widget)
    
    def toggle_expand(self):
        """切换展开/折叠"""
        self.is_expanded = self.header_btn.isChecked()
        self.content_widget.setVisible(self.is_expanded)
    
    def add_record(self, start_time, end_time, duration_str, app, file_path):
        """添加记录"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(start_time))
        self.table.setItem(row, 1, QTableWidgetItem(end_time))
        self.table.setItem(row, 2, QTableWidgetItem(duration_str))
        self.table.setItem(row, 3, QTableWidgetItem(app))
        self.table.setItem(row, 4, QTableWidgetItem(file_path if file_path and not file_path.startswith('[') else '-'))


class TimeSlotWidget(QWidget):
    """时间段组件（可展开详情）"""
    
    def __init__(self, start_time, end_time, total_duration, apps_used, parent=None):
        super().__init__(parent)
        self.is_expanded = False
        self.start_time = start_time
        self.end_time = end_time
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)
        
        # 时间段头
        self.header_btn = QPushButton()
        self.header_btn.setCheckable(True)
        self.header_btn.setChecked(False)
        self.header_btn.clicked.connect(self.toggle_expand)
        
        # 格式化时长
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        duration_str = f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟"
        
        self.header_btn.setText(f"▶ {start_time} - {end_time}  ({duration_str})  -  {apps_used}")
        self.header_btn.setStyleSheet("""
            QPushButton {
                background-color: #2A2A2A;
                color: #808080;
                font-size: 11px;
                padding: 4px 8px;
                border: 1px solid #3E3E3E;
                border-radius: 3px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #3E3E3E;
            }
            QPushButton:checked {
                background-color: #2A2A2A;
                border-bottom-left-radius: 0;
                border-bottom-right-radius: 0;
            }
        """)
        layout.addWidget(self.header_btn)
        
        # 详情区域
        self.detail_widget = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_widget)
        self.detail_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_layout.setSpacing(0)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["开始时间", "结束时间", "时长", "应用", "文件"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setMaximumHeight(300)
        
        self.detail_layout.addWidget(self.table)
        self.detail_widget.setVisible(False)
        layout.addWidget(self.detail_widget)
    
    def toggle_expand(self):
        """切换展开/折叠"""
        self.is_expanded = self.header_btn.isChecked()
        self.detail_widget.setVisible(self.is_expanded)
    
    def add_record(self, start_time, end_time, duration_str, app, file_path):
        """添加记录"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(start_time))
        self.table.setItem(row, 1, QTableWidgetItem(end_time))
        self.table.setItem(row, 2, QTableWidgetItem(duration_str))
        self.table.setItem(row, 3, QTableWidgetItem(app))
        self.table.setItem(row, 4, QTableWidgetItem(file_path if file_path and not file_path.startswith('[') else '-'))


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds or 0))
    if seconds < 0: return "0秒"
    if seconds < 3600:
        return f"{seconds // 60}分{seconds % 60}秒"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}时{minutes}分"

# ================= 弹窗组件 (保持不变) =================

# ================= 系统托盘管理器 =================
class SystemTrayManager:
    def __init__(self, dashboard):
        self.dashboard = dashboard
        self.tray_icon = None
        self.tray_menu = None
        self.click_timer = None
        
    def setup(self):
        """初始化系统托盘"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("⚠️ 系统托盘不可用")
            return
        
        # 创建托盘图标（字母 F）
        self.tray_icon = QSystemTrayIcon(self.dashboard)
        self.tray_icon.setIcon(self._create_f_icon())
        self.tray_icon.setToolTip("FocusFlow - 自动时间追踪")
        
        # 创建菜单
        self.tray_menu = QMenu()
        
        # 菜单项 1：显示/隐藏主界面
        self.action_dashboard = QAction("显示主界面", self.dashboard)
        self.action_dashboard.triggered.connect(self.toggle_dashboard)
        self.tray_menu.addAction(self.action_dashboard)
        
        # 菜单项 2：显示/隐藏悬浮窗
        self.action_floating = QAction("显示悬浮窗", self.dashboard)
        self.action_floating.triggered.connect(self.toggle_floating)
        self.tray_menu.addAction(self.action_floating)
        
        self.tray_menu.addSeparator()
        
        # 菜单项 3：数据管理
        self.action_data_mgmt = QAction("数据管理", self.dashboard)
        self.action_data_mgmt.triggered.connect(self.show_data_management)
        self.tray_menu.addAction(self.action_data_mgmt)
        
        # 菜单项 4：重启程序
        self.action_restart = QAction("重启程序", self.dashboard)
        self.action_restart.triggered.connect(self.restart_app)
        self.tray_menu.addAction(self.action_restart)
        
        # 菜单项 5：退出程序
        self.action_quit = QAction("退出程序", self.dashboard)
        self.action_quit.triggered.connect(self.quit_app)
        self.tray_menu.addAction(self.action_quit)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        
        # 显示托盘图标
        self.tray_icon.show()
        
        # 更新菜单文本（根据实际窗口状态）
        self.update_menu_texts()
        
        print("✅ 系统托盘已初始化")
    
    def _create_f_icon(self):
        """创建字母 F 图标"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 画蓝色圆形背景
        painter.setBrush(QColor("#4A90D9"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        
        # 画白色字母 F
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(18)
        painter.setFont(font)
        painter.drawText(8, 22, "F")
        
        painter.end()
        return QIcon(pixmap)
    
    def toggle_dashboard(self):
        """切换主界面显示/隐藏"""
        if self.dashboard.isVisible():
            self.dashboard.hide()
        else:
            self.dashboard.show()
            self.dashboard.activateWindow()
            self.dashboard.raise_()
        self.update_menu_texts()
    
    def toggle_floating(self):
        """切换悬浮窗显示/隐藏"""
        floating = self.dashboard.floating_widget
        if floating.isVisible():
            floating.hide()
            set_config("floating_visible", "false")
        else:
            # 恢复位置
            x = get_config("floating_position_x", "100")
            y = get_config("floating_position_y", "200")
            floating.move(int(x), int(y))
            floating.show()
            set_config("floating_visible", "true")
        self.update_menu_texts()
    
    def restart_app(self):
        """重启程序"""
        # 保存当前状态
        floating_visible = "true" if self.dashboard.floating_widget.isVisible() else "false"
        set_config("floating_visible", floating_visible)
        
        # 保存悬浮窗位置
        floating = self.dashboard.floating_widget
        set_config("floating_position_x", str(floating.x()))
        set_config("floating_position_y", str(floating.y()))
        
        # 关闭所有窗口
        self.dashboard.close()
        
        # 重启进程
        if getattr(sys, 'frozen', False):
            # 打包后的环境，重启主可执行文件
            main_exe = sys.executable
            subprocess.Popen([main_exe])
        else:
            # 开发环境，重启脚本
            python = sys.executable
            script = os.path.abspath(__file__)
            subprocess.Popen([python, script])
        
        # 退出当前进程
        sys.exit(0)
    
    def update_menu_texts(self):
        """更新菜单文本"""
        # 主界面
        if self.dashboard.isVisible():
            self.action_dashboard.setText("隐藏主界面")
        else:
            self.action_dashboard.setText("显示主界面")
        
        # 悬浮窗
        if self.dashboard.floating_widget.isVisible():
            self.action_floating.setText("隐藏悬浮窗")
        else:
            self.action_floating.setText("显示悬浮窗")
    
    def show_data_management(self):
        """显示数据管理对话框"""
        dialog = DataManagementDialog(self.dashboard)
        dialog.exec()
    
    def cleanup(self):
        """清理托盘"""
        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon = None
    
    def quit_app(self):
        """退出程序"""
        # 保存悬浮窗状态
        floating = self.dashboard.floating_widget
        set_config("floating_position_x", str(floating.x()))
        set_config("floating_position_y", str(floating.y()))
        set_config("floating_visible", "true" if floating.isVisible() else "false")
        
        # 关闭所有窗口
        self.dashboard.close()
        
        # 退出应用
        QApplication.quit()

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
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        
        # ========== 主题设置 ==========
        group_theme = QGroupBox("界面主题")
        theme_layout = QVBoxLayout(group_theme)
        
        # 获取当前主题设置
        self.current_theme = get_config("app_theme", "dark")
        
        # 主题切换按钮组
        theme_button_layout = QHBoxLayout()
        
        self.btn_dark_theme = QPushButton("🌙 深色模式")
        self.btn_dark_theme.setCheckable(True)
        self.btn_dark_theme.setChecked(self.current_theme == "dark")
        self.btn_dark_theme.clicked.connect(lambda: self.set_theme("dark"))
        theme_button_layout.addWidget(self.btn_dark_theme)
        
        self.btn_light_theme = QPushButton("☀️ 浅色模式")
        self.btn_light_theme.setCheckable(True)
        self.btn_light_theme.setChecked(self.current_theme == "light")
        self.btn_light_theme.clicked.connect(lambda: self.set_theme("light"))
        theme_button_layout.addWidget(self.btn_light_theme)
        
        theme_layout.addLayout(theme_button_layout)
        
        # 提示标签
        self.lbl_theme_hint = QLabel("💡 提示：切换主题后需要重启应用才能完全生效")
        self.lbl_theme_hint.setStyleSheet("color: #888888; font-size: 11px; padding: 5px;")
        theme_layout.addWidget(self.lbl_theme_hint)
        
        layout.addWidget(group_theme)
        
        # ========== 后台采集设置 ==========
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
        
        # ========== 数据库设置 ==========
        group_db = QGroupBox("数据库设置")
        db_layout = QVBoxLayout(group_db)
        
        # 当前数据库路径显示
        db_path_layout = QHBoxLayout()
        self.lbl_db_path = QLabel()
        current_db_path = get_db_path()
        self.lbl_db_path.setText(f"当前数据库：{current_db_path}")
        self.lbl_db_path.setWordWrap(True)
        self.lbl_db_path.setStyleSheet("color: #888888; font-size: 11px; padding: 5px;")
        db_path_layout.addWidget(self.lbl_db_path, 1)
        
        btn_change_db = QPushButton("更改位置")
        btn_change_db.clicked.connect(self.change_database_path)
        db_path_layout.addWidget(btn_change_db)
        
        db_layout.addLayout(db_path_layout)
        
        # 打开数据库目录按钮
        btn_open_db_dir = QPushButton("📁 打开数据库所在目录")
        btn_open_db_dir.clicked.connect(self.open_database_directory)
        db_layout.addWidget(btn_open_db_dir)
        
        layout.addWidget(group_db)
        
        # ========== 危险操作 ==========
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
        
        # ========== 按钮 ==========
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def set_theme(self, theme):
        """设置主题"""
        self.current_theme = theme
        if theme == "dark":
            self.btn_dark_theme.setChecked(True)
            self.btn_light_theme.setChecked(False)
        else:
            self.btn_dark_theme.setChecked(False)
            self.btn_light_theme.setChecked(True)
    def save_settings(self):
        # 保存主题设置
        set_config("app_theme", self.current_theme)
        
        # 保存空闲阈值设置
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
    
    def change_database_path(self):
        """更改数据库路径"""
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择数据库文件位置",
            "",
            "SQLite Database (*.db);;All Files (*)"
        )
        
        if file_path:
            # 确保目录存在
            db_dir = os.path.dirname(file_path)
            os.makedirs(db_dir, exist_ok=True)
            
            try:
                # 备份当前数据库
                current_db = get_db_path()
                if os.path.exists(current_db):
                    import shutil
                    shutil.copy2(current_db, file_path)
                    QMessageBox.information(
                        self, 
                        "成功", 
                        f"数据库已迁移到新位置：\n{file_path}\n\n原数据库保留在：\n{current_db}"
                    )
                else:
                    QMessageBox.information(
                        self, 
                        "成功", 
                        f"新数据库将在首次运行时创建在：\n{file_path}"
                    )
                
                # 保存新路径
                set_db_path(file_path)
                
                # 更新显示
                self.lbl_db_path.setText(f"当前数据库：{file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"迁移失败：{str(e)}")
    
    def open_database_directory(self):
        """打开数据库所在目录"""
        import subprocess
        db_path = get_db_path()
        db_dir = os.path.dirname(db_path)
        
        try:
            if sys.platform == 'win32':
                subprocess.Popen(f'explorer "{db_dir}"')
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', db_dir])
            else:
                subprocess.Popen(['xdg-open', db_dir])
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开目录：{str(e)}")



# ================= 极客时间轴组件 =================
# ================= 桌面置顶悬浮秒表 =================
# ================= 极简苹果风桌面置顶悬浮秒表 =================
# ================= 极简苹果风桌面置顶悬浮秒表 =================
# ================= 极简苹果风桌面置顶悬浮秒表 =================
# ================= macOS 底层窗口穿透工具 =================
# ================= macOS 底层窗口穿透工具 =================
def apply_macos_window_behavior(win_id):
    import sys
    if sys.platform == 'darwin':
        try:
            import objc
            from ctypes import c_void_p
            
            # 1. 把 Qt 的 winId (一个整数) 转成 Objective-C 的指针对象
            view_obj = objc.objc_object(c_void_p=int(win_id))
            
            # 2. 从 QNSView 中顺藤摸瓜获取它所属的真正的 NSWindow
            ns_window = view_obj.window()
            if ns_window is None:
                print("macOS 穿透注入失败: 无法获取到 NSWindow")
                return
                
            # 3. 25 = CanJoinAllSpaces(1) | Stationary(16) | IgnoresExpose(8)
            # 这三个组合拳能彻底免疫台前调度、多桌面切换和 F3 触发的隐藏
            ns_window.setCollectionBehavior_(25)
            
        except Exception as e:
            print(f"macOS 穿透注入失败: {e}")

# ================= 极简苹果风桌面置顶悬浮秒表 =================
class FloatingWidget(QWidget):
    def __init__(self, parent_dashboard):
        super().__init__(None) # 断开父子关系，防最小化隐藏
        self.dashboard = parent_dashboard
        
        flags = Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint
        if sys.platform == 'win32': flags |= Qt.Tool
        
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating) # Mac 防抢焦点
        
        self.resize(220, 60) # 进一步缩小跨度
        self.setup_ui()
        
        # 注入 Mac 灵魂
        apply_macos_window_behavior(self.winId())
        self._is_dragging = False
        
        # 恢复上次的位置和显示状态
        self.restore_state()
    
    def restore_state(self):
        """恢复上次的位置和显示状态"""
        x = get_config("floating_position_x", "100")
        y = get_config("floating_position_y", "200")
        visible = get_config("floating_visible", "false")
        
        self.move(int(x), int(y))
        
        if visible == "true":
            self.show()

    def setup_ui(self):
        self.container = QFrame(self)
        self.container.setStyleSheet("QFrame { background-color: rgba(20, 20, 22, 240); border-radius: 10px; }")
        self.container.setGeometry(0, 0, 220, 60)
        
        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(10, 6, 10, 6)
        
        # --- 工作状态面板 (使用严格的 QGridLayout 50:50 划分) ---
        self.panel_work = QWidget()
        work_layout = QGridLayout(self.panel_work)
        work_layout.setContentsMargins(0, 0, 0, 0)
        work_layout.setHorizontalSpacing(5)
        work_layout.setVerticalSpacing(2)
        work_layout.setColumnStretch(0, 1) # 左侧占 50%
        work_layout.setColumnStretch(1, 1) # 右侧占 50%
        
        # 时间数字强制使用等宽字体，杜绝抖动
        time_font = "font-family: 'Menlo', 'Consolas', monospace; font-size: 12px; font-weight: bold;"
        
        # R0: 项目行
        self.fw_proj_name = QLabel("--")
        self.fw_proj_name.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: bold;")
        self.fw_proj_times = QLabel("00:00  00:00")
        self.fw_proj_times.setStyleSheet(time_font)
        work_layout.addWidget(self.fw_proj_name, 0, 0, Qt.AlignLeft | Qt.AlignVCenter)
        work_layout.addWidget(self.fw_proj_times, 0, 1, Qt.AlignRight | Qt.AlignVCenter)
        
        # R1: 程序行
        self.fw_app_name = QLabel("--")
        self.fw_app_name.setStyleSheet("color: #8E8E93; font-size: 11px;")
        self.fw_app_times = QLabel("00:00  00:00")
        self.fw_app_times.setStyleSheet(time_font)
        work_layout.addWidget(self.fw_app_name, 1, 0, Qt.AlignLeft | Qt.AlignVCenter)
        work_layout.addWidget(self.fw_app_times, 1, 1, Qt.AlignRight | Qt.AlignVCenter)
        
        # --- 闲置面板 ---
        self.panel_idle = QWidget()
        idle_layout = QHBoxLayout(self.panel_idle)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_idle_text = QLabel("休息中")
        self.lbl_idle_text.setStyleSheet("color: #FF9F0A; font-size: 14px; font-weight: bold;")
        self.fw_idle_time = QLabel("00:00:00")
        self.fw_idle_time.setStyleSheet("color: #FF9F0A; font-family: 'Menlo', monospace; font-size: 15px; font-weight: bold;")
        
        idle_layout.addWidget(self.lbl_idle_text)
        idle_layout.addStretch()
        idle_layout.addWidget(self.fw_idle_time)
        
        main_layout.addWidget(self.panel_work)
        main_layout.addWidget(self.panel_idle)
        self.panel_idle.hide()

    def sync_data(self, is_idle, idle_sec, p_name, p_today, p_total, a_name, a_today, session_sec):
        if is_idle:
            self.panel_work.hide()
            self.panel_idle.show()
            h, rem = divmod(int(idle_sec), 3600)
            m, s = divmod(rem, 60)
            self.fw_idle_time.setText(f"{h:02d}:{m:02d}:{s:02d}") # 加上了秒数
        else:
            self.panel_idle.hide()
            self.panel_work.show()
            
            # 严格截断过长文字，防止破坏左右 50:50 结构
            if len(p_name) > 8: p_name = p_name[:7] + ".."
            if len(a_name) > 10: a_name = a_name[:9] + ".."
            self.fw_proj_name.setText(p_name)
            self.fw_app_name.setText(a_name)
            
            def fmt(secs): 
                s = int(float(secs))
                return f"{s//3600:02d}:{s%3600//60:02d}" if s>=3600 else f"{s//60:02d}:{s%60:02d}"
            
            self.fw_proj_times.setText(f"<span style='color:#666666;'>{fmt(p_total)}</span> &nbsp; <span style='color:#FFFFFF;'>{fmt(p_today)}</span>")
            self.fw_app_times.setText(f"<span style='color:#666666;'>{fmt(a_today)}</span> &nbsp; <span style='color:#34C759;'>{fmt(session_sec)}</span>")

    # 拖拽逻辑保持不变
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if self._is_dragging and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            # 保存新位置
            set_config("floating_position_x", str(self.x()))
            set_config("floating_position_y", str(self.y()))
            event.accept()
    
    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        self._drag_pos = None
    
    def hideEvent(self, event):
        """隐藏时保存状态"""
        set_config("floating_visible", "false")
        super().hideEvent(event)
    
    def showEvent(self, event):
        """显示时保存状态"""
        set_config("floating_visible", "true")
        super().showEvent(event)
# ================= 数据可视化大屏 =================

class DataDashboardWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("生产力数据大屏 (本周洞察)")
        self.resize(1200, 800)  # 加宽以容纳时间轴
        self.setMinimumSize(900, 600)
        
        # 读取配置的主题设置
        self.is_dark_mode = get_config("app_theme", "dark") == "dark"
        
        # 强制 Matplotlib 使用 Mac 系统自带的中文字体（防止中文变成小方块）
        import platform
        if platform.system() == "Darwin":
            plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang SC', 'Heiti SC']
        elif platform.system() == "Windows":
            plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
        plt.rcParams['axes.unicode_minus'] = False # 正常显示负号
        
        # 根据主题选择 Matplotlib 样式
        if self.is_dark_mode:
            plt.style.use('dark_background')
        else:
            plt.style.use('default')
        
        # 默认日期为今天
        self.selected_date = datetime.now().strftime('%Y-%m-%d')
        
        self.setup_ui()
        self.load_and_draw_data()
        
        # 加载时间轴数据
        self.refresh_timeline()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 使用配置的主题设置
        is_dark_mode = self.is_dark_mode
        
        # 根据主题设置背景色
        if is_dark_mode:
            # 深色主题样式
            bg_color = "#1E1E1E"
            tab_bg = "#2D2D2D"
            tab_selected = "#1E1E1E"
            text_color = "#CCCCCC"
            selected_text = "#9CDCFE"
            border_color = "#333333"
            hover_color = "#3E3E3E"
            header_color = "#9CDCFE"
        else:
            # 浅色主题样式
            bg_color = "#FFFFFF"
            tab_bg = "#F0F0F0"
            tab_selected = "#FFFFFF"
            text_color = "#333333"
            selected_text = "#0066CC"
            border_color = "#CCCCCC"
            hover_color = "#E0E0E0"
            header_color = "#0066CC"
        
        # 设置整体背景
        self.setStyleSheet(f"""
            QDialog#DataDashboardWindow {{
                background-color: {bg_color};
            }}
            QLabel {{
                color: {text_color};
            }}
            QComboBox, QDateEdit {{
                background-color: {tab_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 3px;
                padding: 4px 8px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                width: 12px;
                height: 12px;
            }}
            QTabWidget::pane {{
                border: 1px solid {border_color};
                background-color: {bg_color};
            }}
            QTabBar::tab {{
                background-color: {tab_bg};
                color: {text_color};
                padding: 8px 20px;
                border: 1px solid {border_color};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background-color: {tab_selected};
                color: {selected_text};
                font-weight: bold;
            }}
            QTabBar::tab:hover {{
                background-color: {hover_color};
            }}
            QPushButton {{
                background-color: {tab_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:checked {{
                background-color: {selected_text};
                color: white;
            }}
        """)
        
        # 顶部标题栏
        header = QLabel("FocusFlow / 每日工作效率分析")
        header.setObjectName("dashboardHeader")
        header.setStyleSheet(f"color: {header_color}; font-size: 18px; font-weight: bold; padding: 10px;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # 日期选择器和筛选器
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(20, 10, 20, 10)
        
        # 日期选择
        filter_layout.addWidget(QLabel("日期:"))
        self.date_edit = QComboBox()
        self.date_edit.setEditable(True)
        self.date_edit.setFixedWidth(150)
        # 填充最近 7 天
        for i in range(6, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            self.date_edit.addItem(date)
        self.date_edit.setCurrentText(self.selected_date)
        self.date_edit.currentTextChanged.connect(self.on_date_changed)
        filter_layout.addWidget(self.date_edit)
        
        # 前一天
        btn_prev = QPushButton("◀ 前一天")
        btn_prev.clicked.connect(self.go_to_prev_day)
        filter_layout.addWidget(btn_prev)
        
        # 后一天
        btn_next = QPushButton("后一天 ▶")
        btn_next.clicked.connect(self.go_to_next_day)
        filter_layout.addWidget(btn_next)
        
        filter_layout.addSpacing(30)
        
        # 应用筛选
        filter_layout.addWidget(QLabel("应用:"))
        self.combo_app = QComboBox()
        self.combo_app.addItem("全部")
        self.combo_app.addItems(get_unique_apps())
        self.combo_app.setFixedWidth(150)
        self.combo_app.currentTextChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.combo_app)
        
        # 项目筛选
        filter_layout.addWidget(QLabel("项目:"))
        self.combo_project = QComboBox()
        self.combo_project.addItem("全部", None)  # (显示文本，项目 ID)
        
        # 添加项目/子项目层级
        projects_data = get_projects_with_subprojects()
        for project_key, project_name in projects_data:
            if project_key == '未分配':
                self.combo_project.addItem(project_name, '未分配')
            else:
                # 提取项目 ID
                project_id = int(project_key.replace('project_', ''))
                self.combo_project.addItem(project_name, project_id)
        
        self.combo_project.setFixedWidth(200)
        self.combo_project.currentTextChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.combo_project)
        
        filter_layout.addStretch()
        
        # 刷新按钮
        btn_refresh = QPushButton("🔄 刷新")
        btn_refresh.clicked.connect(self.refresh_timeline)
        filter_layout.addWidget(btn_refresh)
        
        layout.addLayout(filter_layout)
        
        # 创建标签页容器
        self.tab_widget = QTabWidget()
        # 使用对象名称来区分，样式由全局样式表控制
        self.tab_widget.setObjectName("dashboardTabWidget")
        
        # 第 1 页：时间轴和列表
        page1 = QWidget()
        page1_layout = QVBoxLayout(page1)
        page1_layout.setContentsMargins(0, 0, 0, 0)
        
        # 视图切换按钮
        view_switch_layout = QHBoxLayout()
        view_switch_layout.setContentsMargins(20, 10, 20, 10)
        
        self.btn_timeline_view = QPushButton("时间轴")
        self.btn_timeline_view.setCheckable(True)
        self.btn_timeline_view.setChecked(True)
        self.btn_timeline_view.clicked.connect(self.switch_to_timeline)
        view_switch_layout.addWidget(self.btn_timeline_view)
        
        self.btn_list_view = QPushButton("详细列表")
        self.btn_list_view.setCheckable(True)
        self.btn_list_view.setChecked(False)
        self.btn_list_view.clicked.connect(self.switch_to_list)
        view_switch_layout.addWidget(self.btn_list_view)
        
        self.btn_project_stats = QPushButton("项目统计")
        self.btn_project_stats.setCheckable(True)
        self.btn_project_stats.setChecked(False)
        self.btn_project_stats.clicked.connect(self.switch_to_project_stats)
        view_switch_layout.addWidget(self.btn_project_stats)
        
        view_switch_layout.addSpacing(20)
        
        # 时长阈值筛选（只影响时间轴和列表）
        view_switch_layout.addWidget(QLabel("时长阈值:"))
        self.combo_threshold = QComboBox()
        self.combo_threshold.addItems(["≥0 分钟", "≥1 分钟", "≥5 分钟", "≥10 分钟", "≥30 分钟"])
        self.combo_threshold.setFixedWidth(100)
        self.combo_threshold.currentTextChanged.connect(self.on_filter_changed)
        view_switch_layout.addWidget(self.combo_threshold)
        
        view_switch_layout.addStretch()
        
        # 导出按钮
        self.btn_export = QPushButton("📥 导出 CSV")
        self.btn_export.clicked.connect(self.export_to_csv)
        view_switch_layout.addWidget(self.btn_export)
        
        view_switch_layout.addStretch()
        page1_layout.addLayout(view_switch_layout)
        
        # 时间轴区域
        timeline_label = QLabel(f"{self.selected_date} 时间轴 (滚轮缩放 / 拖拽平移)")
        timeline_label.setStyleSheet("color: #9CDCFE; font-size: 14px; font-weight: bold; padding: 10px 20px;")
        page1_layout.addWidget(timeline_label)
        
        # 时间轴组件
        self.timeline = TimelineWidget()
        self.timeline.setFixedHeight(120)
        self.timeline.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        page1_layout.addWidget(self.timeline)
        
        # 列表视图容器（默认隐藏）
        self.list_view_container = QWidget()
        self.list_view_container.setVisible(False)
        
        list_layout = QVBoxLayout(self.list_view_container)
        list_layout.setContentsMargins(20, 10, 20, 10)
        
        # 创建表格
        self.table_view = QTableWidget()
        self.table_view.setColumnCount(5)
        self.table_view.setHorizontalHeaderLabels(["开始时间", "结束时间", "时长", "应用", "项目"])
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_view.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # 设置列宽
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        
        # 启用排序
        self.table_view.setSortingEnabled(True)
        
        list_layout.addWidget(self.table_view)
        
        # 列表统计信息
        self.lbl_list_stats = QLabel("")
        self.lbl_list_stats.setStyleSheet("color: #888888; font-size: 12px; padding: 5px;")
        self.lbl_list_stats.setAlignment(Qt.AlignCenter)
        list_layout.addWidget(self.lbl_list_stats)
        
        page1_layout.addWidget(self.list_view_container)
        
        # 项目统计视图容器（默认隐藏）
        self.project_stats_container = QWidget()
        self.project_stats_container.setVisible(False)
        
        project_stats_layout = QVBoxLayout(self.project_stats_container)
        project_stats_layout.setContentsMargins(20, 10, 20, 10)
        
        # 项目统计操作按钮
        project_stats_toolbar = QHBoxLayout()
        
        self.btn_expand_all = QPushButton("📖 展开全部")
        self.btn_expand_all.clicked.connect(self.expand_all_groups)
        self.btn_expand_all.setFixedWidth(100)
        project_stats_toolbar.addWidget(self.btn_expand_all)
        
        self.btn_collapse_all = QPushButton("📕 折叠全部")
        self.btn_collapse_all.clicked.connect(self.collapse_all_groups)
        self.btn_collapse_all.setFixedWidth(100)
        project_stats_toolbar.addWidget(self.btn_collapse_all)
        
        project_stats_toolbar.addStretch()
        project_stats_layout.addLayout(project_stats_toolbar)
        
        # 创建可滚动区域用于放置分组
        self.project_stats_scroll = QScrollArea()
        self.project_stats_scroll.setWidgetResizable(True)
        self.project_stats_scroll.setFrameShape(QScrollArea.NoFrame)
        self.project_stats_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 分组容器
        self.project_groups_container = QWidget()
        self.project_groups_layout = QVBoxLayout(self.project_groups_container)
        self.project_groups_layout.setAlignment(Qt.AlignTop)
        self.project_groups_layout.setSpacing(5)
        
        self.project_stats_scroll.setWidget(self.project_groups_container)
        project_stats_layout.addWidget(self.project_stats_scroll)
        
        # 项目统计信息
        self.lbl_project_stats = QLabel("")
        self.lbl_project_stats.setStyleSheet("color: #888888; font-size: 12px; padding: 5px;")
        self.lbl_project_stats.setAlignment(Qt.AlignCenter)
        project_stats_layout.addWidget(self.lbl_project_stats)
        
        # 存储所有分组
        self.project_groups = {}
        
        page1_layout.addWidget(self.project_stats_container)
        
        # 统计信息
        self.lbl_timeline_stats = QLabel("")
        self.lbl_timeline_stats.setStyleSheet("color: #888888; font-size: 12px; padding: 5px 20px;")
        self.lbl_timeline_stats.setAlignment(Qt.AlignCenter)
        page1_layout.addWidget(self.lbl_timeline_stats)
        
        # 添加第 1 页到标签页
        self.tab_widget.addTab(page1, "时间明细")
        
        # 第 2 页：统计分析
        page2 = QWidget()
        page2_layout = QVBoxLayout(page2)
        page2_layout.setContentsMargins(0, 0, 0, 0)
        
        # 图表容器（左右分栏）
        chart_layout = QHBoxLayout()
        chart_layout.setContentsMargins(20, 20, 20, 20)
        
        # 创建两个独立的 Figure 画布
        self.fig_bar = Figure(figsize=(6, 4), dpi=100)
        self.canvas_bar = FigureCanvas(self.fig_bar)
        self.fig_pie = Figure(figsize=(4, 4), dpi=100)
        self.canvas_pie = FigureCanvas(self.fig_pie)
        
        chart_layout.addWidget(self.canvas_bar, stretch=3)
        chart_layout.addWidget(self.canvas_pie, stretch=2)
        
        page2_layout.addLayout(chart_layout)
        
        # 第 3 页：项目时间线
        page3 = QWidget()
        page3_layout = QVBoxLayout(page3)
        page3_layout.setContentsMargins(0, 0, 0, 0)
        
        # 项目时间线工具栏
        timeline_toolbar = QHBoxLayout()
        timeline_toolbar.setContentsMargins(20, 10, 20, 10)
        
        # 阈值选择
        timeline_toolbar.addWidget(QLabel("间隔阈值:"))
        self.project_timeline_threshold = QComboBox()
        self.project_timeline_threshold.addItems(["5 分钟", "10 分钟", "15 分钟", "30 分钟"])
        self.project_timeline_threshold.setCurrentIndex(2)  # 默认 15 分钟
        self.project_timeline_threshold.setFixedWidth(100)
        self.project_timeline_threshold.currentTextChanged.connect(self.load_project_timeline_data)
        timeline_toolbar.addWidget(self.project_timeline_threshold)
        
        timeline_toolbar.addStretch()
        
        # 刷新按钮
        btn_refresh_timeline = QPushButton("🔄 刷新")
        btn_refresh_timeline.clicked.connect(self.load_project_timeline_data)
        timeline_toolbar.addWidget(btn_refresh_timeline)
        
        # 导出按钮
        btn_export_timeline = QPushButton("导出")
        btn_export_timeline.clicked.connect(self.export_project_timeline)
        timeline_toolbar.addWidget(btn_export_timeline)
        
        page3_layout.addLayout(timeline_toolbar)
        
        # 创建滚动区域
        self.project_timeline_scroll = QScrollArea()
        self.project_timeline_scroll.setWidgetResizable(True)
        self.project_timeline_scroll.setFrameShape(QScrollArea.NoFrame)
        self.project_timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 内容容器
        self.project_timeline_content = QWidget()
        self.project_timeline_layout = QVBoxLayout(self.project_timeline_content)
        self.project_timeline_layout.setAlignment(Qt.AlignTop)
        self.project_timeline_layout.setSpacing(5)
        
        self.project_timeline_scroll.setWidget(self.project_timeline_content)
        page3_layout.addWidget(self.project_timeline_scroll)
        
        # 统计信息
        self.lbl_project_timeline_stats = QLabel("")
        self.lbl_project_timeline_stats.setStyleSheet("color: #888888; font-size: 12px; padding: 10px;")
        self.lbl_project_timeline_stats.setAlignment(Qt.AlignCenter)
        page3_layout.addWidget(self.lbl_project_timeline_stats)
        
        # 添加第 2 页到标签页（项目时间线）
        self.tab_widget.addTab(page3, "项目时间线")
        
        # 第 2 页：统计分析
        page2 = QWidget()
        page2_layout = QVBoxLayout(page2)
        page2_layout.setContentsMargins(0, 0, 0, 0)
        
        # 图表容器（左右分栏）
        chart_layout = QHBoxLayout()
        chart_layout.setContentsMargins(20, 20, 20, 20)
        
        # 创建两个独立的 Figure 画布
        self.fig_bar = Figure(figsize=(6, 4), dpi=100)
        self.canvas_bar = FigureCanvas(self.fig_bar)
        self.fig_pie = Figure(figsize=(4, 4), dpi=100)
        self.canvas_pie = FigureCanvas(self.fig_pie)
        
        chart_layout.addWidget(self.canvas_bar, stretch=3)
        chart_layout.addWidget(self.canvas_pie, stretch=2)
        
        page2_layout.addLayout(chart_layout)
        
        # 添加第 3 页到标签页（统计分析）
        self.tab_widget.addTab(page2, "统计分析")
        
        layout.addWidget(self.tab_widget)
        
        # 底部关闭按钮
        btn_close = QPushButton("关闭大屏")
        btn_close.setFixedWidth(150)
        btn_close.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def load_and_draw_data(self):
        conn = get_connection()
        
        # 1. 获取过去 7 天的日期范围
        today = datetime.now()
        start_date = (today - timedelta(days=6)).strftime('%Y-%m-%d')
        
        # --- 图表 1：过去 7 天每日趋势 (柱状图) ---
        # 【性能优化】：使用区间查询替代 DATE(SUBSTR()) 函数，使索引生效
        today = datetime.now()
        start_date = (today - timedelta(days=6)).replace(hour=0, minute=0, second=0)
        end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        query_trend = """
            SELECT DATE(SUBSTR(timestamp, 1, 10)) as work_date, SUM(duration)/3600.0 as hours
            FROM activity_log
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY work_date
            ORDER BY work_date ASC
        """
        df_trend = pd.read_sql_query(query_trend, conn, params=(start_date.strftime('%Y-%m-%d %H:%M:%S'), 
                                                                 end_date.strftime('%Y-%m-%d %H:%M:%S')))
        
        # 补全可能缺失的日期（某天没干活也要显示 0）
        date_list = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]
        df_trend.set_index('work_date', inplace=True)
        df_trend = df_trend.reindex(date_list, fill_value=0.0).reset_index()
        # 把日期简化为 'MM-DD'，X轴更好看
        df_trend['work_date'] = df_trend['work_date'].apply(lambda x: x[5:])
        
        # 开始画柱状图
        ax_bar = self.fig_bar.add_subplot(111)
        ax_bar.clear()
        # 使用极客感的青蓝色
        bars = ax_bar.bar(df_trend['work_date'], df_trend['hours'], color='#0E639C', alpha=0.8, width=0.5)
        ax_bar.set_title("每日总工作时长 (小时)", fontsize=14, color='#CCCCCC', pad=15)
        ax_bar.set_ylabel("小时 (h)", color='#888888')
        ax_bar.grid(axis='y', linestyle='--', alpha=0.3)
        ax_bar.spines['top'].set_visible(False)
        ax_bar.spines['right'].set_visible(False)
        ax_bar.spines['left'].set_color('#555555')
        ax_bar.spines['bottom'].set_color('#555555')
        ax_bar.tick_params(colors='#AAAAAA')
        
        # 在柱子顶端标上数字
        for bar in bars:
            yval = bar.get_height()
            if yval > 0:
                ax_bar.text(bar.get_x() + bar.get_width()/2, yval + 0.1, round(yval, 1), ha='center', va='bottom', color='#FFFFFF', fontsize=10)

        # --- 图表 2：过去 7 天各项目时间占比 (环形饼图) ---
        # 【性能优化】：使用区间查询替代 DATE(SUBSTR()) 函数
        query_pie = """
            SELECT p.project_name, SUM(al.duration) as total_secs
            FROM activity_log al
            JOIN file_assignment fa ON al.file_path = fa.file_path
            JOIN projects p ON fa.project_id = p.id
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY p.project_name
            ORDER BY total_secs DESC
        """
        df_pie = pd.read_sql_query(query_pie, conn, params=(start_date.strftime('%Y-%m-%d %H:%M:%S'),
                                                             end_date.strftime('%Y-%m-%d %H:%M:%S')))
        conn.close()
        
        ax_pie = self.fig_pie.add_subplot(111)
        ax_pie.clear()
        
        if not df_pie.empty and df_pie['total_secs'].sum() > 0:
            # 配色方案（取自你界面的主题色）
            colors = ['#0E639C', '#31A8FF', '#EA77FF', '#FF9A00', '#E87D0D', '#00B4AB']
            # 画一个空心圆环图 (Donut Chart)，比实心饼图看起来更高级
            wedges, texts, autotexts = ax_pie.pie(
                df_pie['total_secs'], 
                labels=df_pie['project_name'], 
                autopct='%1.1f%%', 
                startangle=90, 
                colors=colors,
                wedgeprops=dict(width=0.4, edgecolor='#1E1E1E') # width控制空心粗细，edgecolor描边防粘连
            )
            ax_pie.set_title("本周项目时间精力分配", fontsize=14, color='#CCCCCC', pad=15)
            
            # 美化文字颜色
            for text in texts: text.set_color('#AAAAAA')
            for autotext in autotexts: 
                autotext.set_color('#FFFFFF')
                autotext.set_fontsize(10)
                autotext.set_weight('bold')
        else:
            # 如果这周啥也没干，画个空心灰圈
            ax_pie.pie([1], labels=["暂无数据"], colors=['#333333'], wedgeprops=dict(width=0.4))
            ax_pie.set_title("本周项目精力分配", fontsize=14, color='#555555')
            
        self.fig_bar.tight_layout()
        self.fig_pie.tight_layout()
        
        # 刷新画布显示
        self.canvas_bar.draw()
        self.canvas_pie.draw()
    
    def on_date_changed(self, date):
        """日期改变"""
        try:
            # 验证日期格式
            datetime.strptime(date, '%Y-%m-%d')
            self.selected_date = date
            self.refresh_timeline()
        except ValueError:
            QMessageBox.warning(self, "日期格式错误", "请使用 YYYY-MM-DD 格式")
    
    def go_to_prev_day(self):
        """前一天"""
        current = datetime.strptime(self.selected_date, '%Y-%m-%d')
        prev = current - timedelta(days=1)
        self.selected_date = prev.strftime('%Y-%m-%d')
        self.date_edit.setCurrentText(self.selected_date)
        self.refresh_timeline()
    
    def go_to_next_day(self):
        """后一天"""
        current = datetime.strptime(self.selected_date, '%Y-%m-%d')
        next_day = current + timedelta(days=1)
        
        # 不允许选择未来日期
        if next_day > datetime.now():
            QMessageBox.information(self, "提示", "不能选择未来日期")
            return
        
        self.selected_date = next_day.strftime('%Y-%m-%d')
        self.date_edit.setCurrentText(self.selected_date)
        self.refresh_timeline()
    
    def on_filter_changed(self):
        """筛选条件改变"""
        self.refresh_timeline()
    
    def refresh_timeline(self):
        """刷新时间轴"""
        app_filter = self.combo_app.currentText()
        if app_filter == "全部":
            app_filter = None
        
        # 获取项目筛选（使用 userData）
        project_data = self.combo_project.currentData()
        if project_data is None:  # "全部"选项
            project_filter = None
        elif project_data == '未分配':
            project_filter = '未分配'
        else:
            # 使用项目名称作为筛选
            project_filter = self.combo_project.currentText()
        
        # 获取时长阈值（分钟）
        threshold_minutes = self.combo_threshold.currentText().replace("分钟", "").replace("≥", "").strip()
        try:
            threshold_seconds = int(threshold_minutes) * 60
        except:
            threshold_seconds = 0
        
        # 加载时间轴数据
        self.load_timeline_data(self.selected_date, app_filter, project_filter, threshold_seconds)
        
        # 加载列表数据
        self.load_list_data(self.selected_date, app_filter, project_filter, threshold_seconds)
        
        # 加载项目统计数据
        self.load_project_stats_data(self.selected_date, app_filter, project_filter, threshold_seconds)
        
        # 加载项目时间线数据
        self.load_project_timeline_data(app_filter, project_filter)
    
    def switch_to_timeline(self):
        """切换到时间轴视图"""
        self.btn_timeline_view.setChecked(True)
        self.btn_list_view.setChecked(False)
        self.timeline.setVisible(True)
        self.list_view_container.setVisible(False)
        self.btn_export.setEnabled(False)  # 时间轴视图禁用导出
    
    def switch_to_list(self):
        """切换到列表视图"""
        self.btn_list_view.setChecked(True)
        self.btn_timeline_view.setChecked(False)
        self.btn_project_stats.setChecked(False)
        self.timeline.setVisible(False)
        self.list_view_container.setVisible(True)
        self.project_stats_container.setVisible(False)
        self.btn_export.setEnabled(True)  # 列表视图启用导出
    
    def switch_to_project_stats(self):
        """切换到项目统计视图"""
        self.btn_project_stats.setChecked(True)
        self.btn_timeline_view.setChecked(False)
        self.btn_list_view.setChecked(False)
        self.timeline.setVisible(False)
        self.list_view_container.setVisible(False)
        self.project_stats_container.setVisible(True)
        self.btn_export.setEnabled(False)  # 项目统计禁用导出
        
        # 获取当前筛选参数
        app_filter = self.combo_app.currentText()
        if app_filter == "全部":
            app_filter = None
        
        # 获取项目筛选（使用 userData）
        project_data = self.combo_project.currentData()
        if project_data is None:  # "全部"选项
            project_filter = None
        elif project_data == '未分配':
            project_filter = '未分配'
        else:
            # 使用项目名称作为筛选
            project_filter = self.combo_project.currentText()
        
        # 获取时长阈值（分钟）
        threshold_minutes = self.combo_threshold.currentText().replace("分钟", "").replace("≥", "").strip()
        try:
            threshold_seconds = int(threshold_minutes) * 60
        except:
            threshold_seconds = 0
        
        # 加载项目统计数据
        self.load_project_stats_data(self.selected_date, app_filter, project_filter, threshold_seconds)
    
    def expand_all_groups(self):
        """展开所有分组"""
        for group in self.project_groups.values():
            if not group.header_btn.isChecked():
                group.header_btn.setChecked(True)
                group.toggle_expand()
        self.btn_expand_all.setEnabled(False)
        self.btn_collapse_all.setEnabled(True)
    
    def collapse_all_groups(self):
        """折叠所有分组"""
        for group in self.project_groups.values():
            if group.header_btn.isChecked():
                group.header_btn.setChecked(False)
                group.toggle_expand()
        self.btn_expand_all.setEnabled(True)
        self.btn_collapse_all.setEnabled(False)
    
    def load_project_timeline_data(self, app_filter=None, project_filter=None):
        """
        加载项目时间线数据（3 层结构）
        """
        # 清空旧数据
        for i in reversed(range(self.project_timeline_layout.count())):
            widget = self.project_timeline_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # 使用全局日期
        date = self.selected_date
        
        # 获取项目时间线的阈值
        threshold_text = self.project_timeline_threshold.currentText()
        threshold_minutes = int(threshold_text.replace('分钟', ''))
        
        # 获取聚合数据
        timeline_data = aggregate_project_timeline(date, threshold_minutes)
        
        # 应用筛选
        if app_filter or project_filter:
            timeline_data = self.filter_timeline_data(timeline_data, app_filter, project_filter)
        
        if not timeline_data:
            self.lbl_project_timeline_stats.setText("📭 当天暂无数据")
            return
        
        # 构建树形结构
        tree_data = build_project_timeline_tree(timeline_data)
        
        if not tree_data:
            self.lbl_project_timeline_stats.setText("📭 当天暂无数据")
            return
        
        # 创建树形组件
        total_seconds = 0
        total_projects = 0
        total_time_slots = 0
        total_records = 0
        
        for root_name, root_data in tree_data.items():
            root_widget = ProjectTreeNodeWidget(
                name=root_name,
                level=0,
                total_duration=root_data['total_duration'],
                time_range=root_data['time_range'],
                children=root_data.get('children', {})
            )
            self.project_timeline_layout.addWidget(root_widget)
            
            # 统计
            total_seconds += root_data['total_duration']
            total_projects += 1
            
            # 递归统计子项目
            def count_children(children):
                nonlocal total_time_slots, total_records
                for child_name, child_data in children.items():
                    if 'time_slots' in child_data:
                        # 最底层
                        total_time_slots += len(child_data['time_slots'])
                        total_records += child_data.get('record_count', 0)
                    else:
                        # 还有下一层
                        count_children(child_data.get('children', {}))
            
            count_children(root_data.get('children', {}))
        
        # 更新统计信息
        total_hours = total_seconds // 3600
        total_minutes = (total_seconds % 3600) // 60
        
        self.lbl_project_timeline_stats.setText(
            f" 总计：{total_hours}小时{total_minutes}分钟  |  "
            f"{total_projects} 个项目  |  "
            f"{total_time_slots} 个时间段  |  "
            f"{total_records} 条记录"
        )
    
    def filter_timeline_data(self, data, app_filter, project_filter):
        """
        根据筛选条件过滤项目时间线数据
        
        Args:
            data: aggregate_project_timeline 返回的数据
            app_filter: 应用筛选条件
            project_filter: 项目筛选条件
        
        Returns:
            过滤后的数据
        """
        if not app_filter and not project_filter:
            return data
        
        filtered = {}
        
        for project_path, project_data in data.items():
            # 项目筛选（支持完整层级）
            if project_filter and project_filter != '全部':
                # 检查项目路径是否包含筛选的项目
                if project_filter not in project_path:
                    continue
            
            # 应用筛选（检查该项目的记录是否包含该应用）
            if app_filter and app_filter != '全部':
                has_app = False
                for slot in project_data['time_slots']:
                    if app_filter in slot['apps']:
                        has_app = True
                        break
                if not has_app:
                    continue
            
            filtered[project_path] = project_data
        
        return filtered
    
    def export_project_timeline(self):
        """
        导出项目时间线到 CSV
        """
        from datetime import datetime as dt_module
        import csv
        
        # 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出项目时间线",
            f"项目时间线_{datetime.now().strftime('%Y%m%d')}.csv",
            "CSV 文件 (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            # 获取参数
            date = self.project_timeline_date.date().toString('yyyy-MM-dd')
            threshold_text = self.project_timeline_threshold.currentText()
            threshold_minutes = int(threshold_text.replace('分钟', ''))
            
            # 获取数据
            timeline_data = aggregate_project_timeline(date, threshold_minutes)
            
            if not timeline_data:
                QMessageBox.warning(self, "提示", "没有可导出的数据")
                return
            
            # 写入 CSV
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                # 表头
                writer.writerow([
                    '日期',
                    '第 1 层项目',
                    '第 2 层项目',
                    '第 3 层项目',
                    '开始时间',
                    '结束时间',
                    '时长 (秒)',
                    '时长 (格式)',
                    '应用',
                    '文件路径'
                ])
                
                # 递归写入数据
                for project_path, data in timeline_data.items():
                    for slot in data['time_slots']:
                        # 填充项目路径到 3 层
                        layer1 = project_path[0] if len(project_path) > 0 else ''
                        layer2 = project_path[1] if len(project_path) > 1 else ''
                        layer3 = project_path[2] if len(project_path) > 2 else ''
                        
                        # 收集应用
                        apps = ', '.join(slot['apps']) if isinstance(slot['apps'], set) else str(slot['apps'])
                        
                        # 计算时长
                        duration = slot['end_sec'] - slot['start_sec']
                        
                        # 为每条记录写入一行
                        for log in slot['logs']:
                            # 解析日志时间
                            try:
                                ts = dt_module.fromisoformat(log['timestamp'].split('.')[0])
                                log_start_sec = ts.hour * 3600 + ts.minute * 60 + ts.second
                                log_start = format_time(log_start_sec)
                                log_end = format_time(log_start_sec + log['duration'])
                            except:
                                log_start = "N/A"
                                log_end = "N/A"
                            
                            writer.writerow([
                                date,
                                layer1,
                                layer2,
                                layer3,
                                log_start,
                                log_end,
                                log['duration'],
                                format_duration(log['duration']),
                                log['app_name'],
                                log['file_path'] or ''
                            ])
            
            QMessageBox.information(self, "导出成功", f"项目时间线已导出到：\n{file_path}")
        
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出时发生错误：\n{str(e)}")
    
    def load_project_stats_data(self, date, app_filter=None, project_filter=None, threshold_seconds=0):
        """
        加载项目统计数据（按项目和子项目分组）
        """
        from datetime import datetime as dt_module
        
        # 清空旧分组
        for group in self.project_groups.values():
            group.deleteLater()
        self.project_groups.clear()
        
        conn = get_connection()
        
        # 计算日期范围
        today_start = f"{date} 00:00:00"
        tomorrow_start = f"{dt_module.strptime(date, '%Y-%m-%d').replace(hour=0, minute=0, second=0) + timedelta(days=1)}"
        
        # 查询原始记录
        query = """
            SELECT timestamp, duration, app_name, file_path 
            FROM activity_log 
            WHERE timestamp >= ? AND timestamp < ?
        """
        params = [today_start, tomorrow_start]
        
        # 添加筛选
        if app_filter and app_filter != '全部':
            query += " AND app_name = ?"
            params.append(app_filter)
        
        if project_filter and project_filter != '全部':
            if project_filter == '未分配':
                query += """ AND file_path NOT IN (
                    SELECT file_path FROM file_assignment WHERE project_id IS NOT NULL
                )"""
            else:
                query += """ AND file_path IN (
                    SELECT file_path FROM file_assignment fa
                    JOIN projects p ON fa.project_id = p.id
                    WHERE p.project_name = ?
                )"""
                params.append(project_filter)
        
        query += " ORDER BY timestamp ASC"
        
        logs = conn.execute(query, params).fetchall()
        
        if not logs:
            conn.close()
            self.lbl_project_stats.setText("📭 当天暂无数据")
            return
        
        # 聚合同一应用的连续记录
        blocks = []
        current_block = None
        
        for timestamp_str, duration, app, fpath in logs:
            try:
                dtime = dt_module.fromisoformat(timestamp_str.split('.')[0])
                start_sec = dtime.hour * 3600 + dtime.minute * 60 + dtime.second
                end_sec = start_sec + duration
                
                if current_block is None:
                    current_block = {
                        'start_sec': start_sec,
                        'end_sec': end_sec,
                        'app': app,
                        'file': fpath,
                        'project': None
                    }
                else:
                    if start_sec - current_block['end_sec'] <= 60 and app == current_block['app']:
                        current_block['end_sec'] = end_sec
                    else:
                        blocks.append(current_block)
                        current_block = {
                            'start_sec': start_sec,
                            'end_sec': end_sec,
                            'app': app,
                            'file': fpath,
                            'project': None
                        }
            except:
                continue
        
        if current_block:
            blocks.append(current_block)
        
        # 查询项目信息
        for block in blocks:
            if block['file'] and not block['file'].startswith('['):
                proj_query = """
                    SELECT p.project_name 
                    FROM file_assignment fa
                    JOIN projects p ON fa.project_id = p.id
                    WHERE fa.file_path = ?
                """
                result = conn.execute(proj_query, (block['file'],)).fetchone()
                if result:
                    block['project'] = result[0]
                else:
                    block['project'] = '未分配'
            else:
                block['project'] = '未分配'
        
        conn.close()
        
        # 应用时长阈值过滤
        if threshold_seconds > 0:
            blocks = [b for b in blocks if (b['end_sec'] - b['start_sec']) >= threshold_seconds]
        
        # 按项目分组
        projects_data = {}  # {project: [blocks]}
        
        for block in blocks:
            project = block['project']
            if project not in projects_data:
                projects_data[project] = []
            projects_data[project].append(block)
        
        # 创建分组组件
        total_seconds = 0
        total_records = 0
        
        for project, proj_blocks in sorted(projects_data.items()):
            # 计算项目统计
            proj_total = sum(b['end_sec'] - b['start_sec'] for b in proj_blocks)
            proj_start = min(b['start_sec'] for b in proj_blocks)
            proj_end = max(b['end_sec'] for b in proj_blocks)
            proj_records = len(proj_blocks)
            
            total_seconds += proj_total
            total_records += proj_records
            
            # 格式化时间
            start_time_str = f"{int(proj_start//3600):02d}:{int((proj_start%3600)//60):02d}"
            end_time_str = f"{int(proj_end//3600):02d}:{int((proj_end%3600)//60):02d}"
            
            # 创建项目分组
            group = ProjectGroupWidget(project, proj_total, start_time_str, end_time_str, proj_records)
            
            # 添加记录
            for block in sorted(proj_blocks, key=lambda x: x['start_sec']):
                b_start = f"{int(block['start_sec']//3600):02d}:{int((block['start_sec']%3600)//60):02d}:{int(block['start_sec']%60):02d}"
                b_end = f"{int(block['end_sec']//3600):02d}:{int((block['end_sec']%3600)//60):02d}:{int(block['end_sec']%60):02d}"
                b_duration = format_duration(block['end_sec'] - block['start_sec'])
                
                # 文件路径处理
                file_path = block['file']
                if file_path and not file_path.startswith('['):
                    file_path = os.path.basename(file_path)
                
                group.add_record(b_start, b_end, b_duration, block['app'], file_path or '-')
            
            self.project_groups_layout.addWidget(group)
            self.project_groups[project] = group
        
        # 更新统计
        total_hours = total_seconds // 3600
        total_minutes = (total_seconds % 3600) // 60
        
        unique_projects = len(projects_data)
        unique_apps = len(set(b['app'] for b in blocks))
        
        self.lbl_project_stats.setText(
            f"总计：{total_hours}小时{total_minutes}分钟 | {unique_projects} 个项目 | {unique_apps} 个应用 | {total_records} 条记录"
        )
        
        # 初始化按钮状态
        self.btn_expand_all.setEnabled(True)
        self.btn_collapse_all.setEnabled(True)
    
    def load_list_data(self, date, app_filter=None, project_filter=None, threshold_seconds=0):
        """
        加载列表视图数据
        """
        from datetime import datetime as dt_module
        
        conn = get_connection()
        
        # 计算日期范围
        today_start = f"{date} 00:00:00"
        tomorrow_start = f"{dt_module.strptime(date, '%Y-%m-%d').replace(hour=0, minute=0, second=0) + timedelta(days=1)}"
        
        # 查询原始记录
        query = """
            SELECT timestamp, duration, app_name, file_path 
            FROM activity_log 
            WHERE timestamp >= ? AND timestamp < ?
        """
        params = [today_start, tomorrow_start]
        
        # 添加筛选
        if app_filter and app_filter != '全部':
            query += " AND app_name = ?"
            params.append(app_filter)
        
        if project_filter and project_filter != '全部':
            if project_filter == '未分配':
                query += """ AND file_path NOT IN (
                    SELECT file_path FROM file_assignment WHERE project_id IS NOT NULL
                )"""
            else:
                query += """ AND file_path IN (
                    SELECT file_path FROM file_assignment fa
                    JOIN projects p ON fa.project_id = p.id
                    WHERE p.project_name = ?
                )"""
                params.append(project_filter)
        
        query += " ORDER BY timestamp ASC"
        
        logs = conn.execute(query, params).fetchall()
        
        if not logs:
            conn.close()
            self.table_view.setRowCount(0)
            self.lbl_list_stats.setText("📭 当天暂无数据")
            return
        
        # 聚合同一应用的连续记录
        blocks = []
        current_block = None
        
        for timestamp_str, duration, app, fpath in logs:
            try:
                dtime = dt_module.fromisoformat(timestamp_str.split('.')[0])
                start_sec = dtime.hour * 3600 + dtime.minute * 60 + dtime.second
                end_sec = start_sec + duration
                
                if current_block is None:
                    current_block = {
                        'start_sec': start_sec,
                        'end_sec': end_sec,
                        'app': app,
                        'file': fpath,
                        'project': None
                    }
                else:
                    if start_sec - current_block['end_sec'] <= 60 and app == current_block['app']:
                        current_block['end_sec'] = end_sec
                    else:
                        blocks.append(current_block)
                        current_block = {
                            'start_sec': start_sec,
                            'end_sec': end_sec,
                            'app': app,
                            'file': fpath,
                            'project': None
                        }
            except:
                continue
        
        if current_block:
            blocks.append(current_block)
        
        # 查询项目信息
        for block in blocks:
            if block['file'] and not block['file'].startswith('['):
                proj_query = """
                    SELECT p.project_name 
                    FROM file_assignment fa
                    JOIN projects p ON fa.project_id = p.id
                    WHERE fa.file_path = ?
                """
                result = conn.execute(proj_query, (block['file'],)).fetchone()
                if result:
                    block['project'] = result[0]
                else:
                    block['project'] = '未分配'
            else:
                block['project'] = '未分配'
        
        conn.close()
        
        # 应用时长阈值过滤
        if threshold_seconds > 0:
            blocks = [b for b in blocks if (b['end_sec'] - b['start_sec']) >= threshold_seconds]
        
        # 填充表格
        self.table_view.setRowCount(len(blocks))
        
        total_duration = 0
        apps_set = set()
        
        for i, block in enumerate(blocks):
            start_time = f"{int(block['start_sec']//3600):02d}:{int((block['start_sec']%3600)//60):02d}:{int(block['start_sec']%60):02d}"
            end_time = f"{int(block['end_sec']//3600):02d}:{int((block['end_sec']%3600)//60):02d}:{int(block['end_sec']%60):02d}"
            duration_sec = int(block['end_sec'] - block['start_sec'])
            duration_str = format_duration(duration_sec)
            
            self.table_view.setItem(i, 0, QTableWidgetItem(start_time))
            self.table_view.setItem(i, 1, QTableWidgetItem(end_time))
            self.table_view.setItem(i, 2, QTableWidgetItem(duration_str))
            self.table_view.setItem(i, 3, QTableWidgetItem(block['app']))
            self.table_view.setItem(i, 4, QTableWidgetItem(block['project'] or '-'))
            
            total_duration += duration_sec
            apps_set.add(block['app'])
        
        # 更新统计
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        
        self.lbl_list_stats.setText(
            f"总计：{hours}小时{minutes}分钟 | {len(apps_set)} 个应用 | {len(blocks)} 条记录"
        )
    
    def export_to_csv(self):
        """导出列表数据为 CSV"""
        from PySide6.QtWidgets import QFileDialog
        import csv
        
        # 获取保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 CSV",
            f"时间数据_{self.selected_date}.csv",
            "CSV 文件 (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            # 获取当前表格数据
            row_count = self.table_view.rowCount()
            col_count = self.table_view.columnCount()
            
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                # 写入表头
                headers = [self.table_view.horizontalHeaderItem(i).text() 
                          for i in range(col_count)]
                writer.writerow(headers)
                
                # 写入数据行
                for i in range(row_count):
                    row_data = [self.table_view.item(i, j).text() 
                               for j in range(col_count)]
                    writer.writerow(row_data)
            
            QMessageBox.information(
                self,
                "导出成功",
                f"数据已导出到：\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "导出失败",
                f"导出过程中发生错误：\n{str(e)}"
            )
    
    def load_timeline_data(self, date, app_filter=None, project_filter=None, threshold_seconds=0):
        """
        加载指定日期的时间轴数据（直接查询原始记录并聚合）
        """
        from datetime import datetime as dt_module
        
        conn = get_connection()
        
        # 计算日期范围
        today_start = f"{date} 00:00:00"
        tomorrow_start = f"{dt_module.strptime(date, '%Y-%m-%d').replace(hour=0, minute=0, second=0) + timedelta(days=1)}"
        
        # 查询原始记录
        query = """
            SELECT timestamp, duration, app_name, file_path 
            FROM activity_log 
            WHERE timestamp >= ? AND timestamp < ?
        """
        params = [today_start, tomorrow_start]
        
        # 添加筛选
        if app_filter and app_filter != '全部':
            query += " AND app_name = ?"
            params.append(app_filter)
        
        if project_filter and project_filter != '全部':
            if project_filter == '未分配':
                query += """ AND file_path NOT IN (
                    SELECT file_path FROM file_assignment WHERE project_id IS NOT NULL
                )"""
            else:
                query += """ AND file_path IN (
                    SELECT file_path FROM file_assignment fa
                    JOIN projects p ON fa.project_id = p.id
                    WHERE p.project_name = ?
                )"""
                params.append(project_filter)
        
        query += " ORDER BY timestamp ASC"
        
        logs = conn.execute(query, params).fetchall()
        conn.close()
        
        print(f"🔍 查询 {date} 的数据：找到 {len(logs)} 条原始记录")
        
        if not logs:
            self.timeline.update_data([])
            self.lbl_timeline_stats.setText("📭 当天暂无数据")
            return
        
        # 在 Python 中聚合连续记录（和主界面一样的逻辑）
        blocks = []
        current_block = None
        
        for timestamp_str, duration, app, fpath in logs:
            try:
                dtime = dt_module.fromisoformat(timestamp_str.split('.')[0])
                start_sec = dtime.hour * 3600 + dtime.minute * 60 + dtime.second
                end_sec = start_sec + duration
                
                if current_block is None:
                    current_block = [start_sec, end_sec, app, fpath, False]
                else:
                    # 如果紧挨着且应用相同，聚合
                    if start_sec - current_block[1] <= 60 and app == current_block[2]:
                        current_block[1] = end_sec
                    else:
                        # 添加前一个块
                        blocks.append(current_block)
                        
                        # 添加闲置块（时间间隔>60 秒）
                        if start_sec - current_block[1] > 60:
                            blocks.append([current_block[1], start_sec, "Idle", "", True])
                        
                        current_block = [start_sec, end_sec, app, fpath, False]
            except Exception as e:
                print(f"  ❌ 解析失败：{e}")
                continue
        
        if current_block:
            blocks.append(current_block)
        
        # 应用时长阈值过滤
        if threshold_seconds > 0:
            blocks = [b for b in blocks if (b[1] - b[0]) >= threshold_seconds]
        
        print(f" 聚合后 {len(blocks)} 个时间块")
        
        # 更新的时间轴
        self.timeline.update_data(blocks)
        
        # 更新统计信息
        total_duration = sum(b[1] - b[0] for b in blocks if not b[4])  # 排除闲置
        total_apps = len(set(b[2] for b in blocks if not b[4] and b[2] != "Idle"))
        
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        
        self.lbl_timeline_stats.setText(
            f"总计：{hours}小时{minutes}分钟 | {total_apps} 个应用 | {len(blocks)} 条记录"
        )


# ================= 极客交互式时间轴组件 (可缩放/拖拽) =================

class TimelineWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)  # 固定高度
        self.blocks = []  
        self.setToolTipDuration(0)
        self.setMouseTracking(True)
        
        # --- 镜头系统 (Camera) 状态变量 ---
        self.view_start = 0      # 当前视口左边缘代表的秒数 (0 = 凌晨0点)
        self.view_end = 86400    # 当前视口右边缘代表的秒数 (86400 = 晚上24点)
        
        # --- 拖拽交互状态 ---
        self.is_dragging = False
        self.last_mouse_x = 0

    def update_data(self, blocks):
        self.blocks = blocks
        self.update()

    # --- 数学映射工具 ---
    def pixel_to_time(self, x, width):
        return self.view_start + (x / width) * (self.view_end - self.view_start)

    def time_to_pixel(self, t, width):
        if self.view_end == self.view_start: return 0
        return (t - self.view_start) / (self.view_end - self.view_start) * width

    # --- 交互 1：滚轮丝滑缩放 (Zoom) ---
    # --- 交互 1：滚轮与妙控板丝滑缩放 (Zoom) ---
    def wheelEvent(self, event):
        # 【修复1】：兼容妙控板 (pixelDelta) 和普通鼠标 (angleDelta)
        pixel_y = event.pixelDelta().y()
        angle_y = event.angleDelta().y()
        
        # 优先使用妙控板的高精度像素偏移，没有的话退化为普通鼠标的齿轮偏移
        delta = pixel_y if pixel_y != 0 else angle_y
        if delta == 0: return

        width = self.width()
        x = event.position().x()
        
        # 获取鼠标当前指向的时间点（缩放锚点，保证鼠标指着的地方在缩放时不乱跑）
        t_anchor = self.pixel_to_time(x, width)
        
        span = self.view_end - self.view_start
        
        # 【修复1补充】：为了让妙控板平滑缩放，缩放比例与滑动距离成正比
        # 普通鼠标的 angle_y 一般是 120，妙控板的 pixel_y 可能是个位数
        zoom_factor = abs(delta) * 0.002
        # 防止单次滑动过猛，限制最大缩放比例为 30%
        zoom_factor = min(zoom_factor, 0.3)
        
        if delta > 0: span *= (1 - zoom_factor) # 放大 (视口时间变短)
        else: span *= (1 + zoom_factor)         # 缩小 (视口时间变长)

        # 极限限制：最多放大到看 2 分钟，最退放大到看全天(24小时)
        span = max(120, min(86400, span)) 

        # 根据锚点重新计算左右边界
        new_start = t_anchor - (x / width) * span
        new_end = new_start + span

        # 碰撞检测：不能超出 0 点和 24 点的物理边界
        if new_start < 0:
            new_start = 0
            new_end = span
        if new_end > 86400:
            new_end = 86400
            new_start = 86400 - span

        self.view_start, self.view_end = new_start, new_end
        self.update()

    # --- 交互 2：按住左键拖拽平移 (Pan) ---
    # --- 交互 3：双击显示详情 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 检测是否是双击
            if event.type() == Qt.MouseButtonDblClick:
                # 显示详情
                self.show_block_details(event.position().x())
                return
            
            self.is_dragging = True
            self.last_mouse_x = event.position().x()
            self.setCursor(Qt.ClosedHandCursor) # 鼠标变成小抓手
    
    def show_block_details(self, x):
        """显示点击位置的时间块详情"""
        width = self.width()
        click_sec = self.pixel_to_time(x, width)
        
        # 查找点击位置的时间块
        for (start, end, app, fpath, is_idle) in self.blocks:
            if start <= click_sec <= end:
                # 找到匹配的块
                start_str = f"{int(start//3600):02d}:{int((start%3600)//60):02d}"
                end_str = f"{int(end//3600):02d}:{int((end%3600)//60):02d}"
                duration_sec = int(end - start)
                duration_str = format_duration(duration_sec)
                
                # 创建详情对话框
                from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit
                dialog = QDialog(self.window())
                dialog.setWindowTitle("时间使用详情")
                dialog.setMinimumWidth(500)
                dialog.setMinimumHeight(300)
                
                layout = QVBoxLayout(dialog)
                
                # 标题
                title = QLabel(f"<h3>时间使用详情</h3>")
                layout.addWidget(title)
                
                # 应用信息
                if is_idle:
                    info = QLabel(f"<b>类型：</b> 闲置/休息")
                else:
                    info = QLabel(f"""
                        <b>应用：</b> {app}<br>
                        <b>文件：</b> {fpath if fpath else '未知'}<br>
                        <b>时间：</b> {start_str} - {end_str}<br>
                        <b>时长：</b> {duration_str}
                    """)
                info.setStyleSheet("color: #D4D4D4; font-size: 13px; padding: 10px;")
                layout.addWidget(info)
                
                # 关闭按钮
                btn_close = QPushButton("关闭")
                btn_close.clicked.connect(dialog.accept)
                btn_close.setFixedWidth(100)
                btn_layout = QHBoxLayout()
                btn_layout.addStretch()
                btn_layout.addWidget(btn_close)
                btn_layout.addStretch()
                layout.addLayout(btn_layout)
                
                dialog.exec()
                return
        
        # 没有找到匹配的块
        QMessageBox.information(self.window(), "提示", "点击位置没有活动时间块")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            self.setCursor(Qt.ArrowCursor)

    def mouseMoveEvent(self, event):
        x = event.position().x()
        width = self.width()

        if self.is_dragging:
            # 计算鼠标移动了多少像素，换算成多少秒
            pixel_delta = x - self.last_mouse_x
            time_delta = -(pixel_delta / width) * (self.view_end - self.view_start)

            new_start = self.view_start + time_delta
            new_end = self.view_end + time_delta

            # 碰撞检测：防止拖出全天的边界
            if new_start < 0: time_delta = -self.view_start
            elif new_end > 86400: time_delta = 86400 - self.view_end

            self.view_start += time_delta
            self.view_end += time_delta
            self.last_mouse_x = x
            self.update()
            
        else:
            # 悬停显示详情气泡
            hover_sec = self.pixel_to_time(x, width)
            found = False
            for (start, end, app, fpath, is_idle) in self.blocks:
                if start <= hover_sec <= end:
                    start_str = f"{int(start//3600):02d}:{int((start%3600)//60):02d}"
                    end_str = f"{int(end//3600):02d}:{int((end%3600)//60):02d}"
                    duration_sec = int(end - start)
                    duration_str = format_duration(duration_sec)
                    if is_idle:
                        self.setToolTip(f"闲置 / 休息\n{start_str} - {end_str}\n时长：{duration_str}")
                    else:
                        d_path = fpath if fpath.startswith("[") else os.path.basename(fpath)
                        self.setToolTip(f"{app}\n{d_path}\n{start_str} - {end_str}\n时长：{duration_str}")
                    found = True
                    break
            if not found: self.setToolTip("")

    def _get_app_color(self, app_name, is_idle):
        if is_idle: return QColor("#4A4A4A")
        lower_app = app_name.lower()
        if "after effects" in lower_app: return QColor("#9999FF")
        if "premiere" in lower_app: return QColor("#EA77FF")
        if "photoshop" in lower_app: return QColor("#31A8FF")
        if "illustrator" in lower_app: return QColor("#FF9A00")
        if "blender" in lower_app: return QColor("#E87D0D")
        if "chrome" in lower_app or "safari" in lower_app or "edge" in lower_app: return QColor("#00B4AB")
        h = hash(app_name) % 360
        color = QColor()
        color.setHsv(h, 150, 200)
        return color

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width, height = self.width(), self.height()
        
        # 1. 黑板底色
        painter.fillRect(0, 0, width, height, QColor("#1E1E1E"))
        
        # 2. 动态智能刻度网格 (Zoom In 时显示分钟，Zoom Out 时显示小时)
        span = self.view_end - self.view_start
        if span > 12 * 3600: step = 6 * 3600    # 看全天：每6小时一根线
        elif span > 4 * 3600: step = 3600       # 看半天：每1小时一根线
        elif span > 3600: step = 1800           # 看几小时：每30分钟一根线
        elif span > 600: step = 300             # 看半小时：每5分钟一根线
        else: step = 60                         # 极度放大：每1分钟一根线

        first_line = int(self.view_start // step) * step
        painter.setPen(QPen(QColor("#555555"), 1, Qt.DashLine))
        for t in range(first_line, int(self.view_end) + 1, step):
            if t < 0 or t > 86400: continue
            x = int(self.time_to_pixel(t, width))
            painter.drawLine(x, 0, x, height)
            
            # 画文字刻度
            h, m = t // 3600, (t % 3600) // 60
            text = f"{h}:00" if step >= 3600 else f"{h:02d}:{m:02d}"
            painter.setPen(QColor("#888888"))
            painter.drawText(x + 5, 15, text)
            painter.setPen(QPen(QColor("#555555"), 1, Qt.DashLine))

        # 3. 绘制色块 (具备视口裁剪功能，看不见的就不画，提升性能)
        painter.setPen(Qt.NoPen)
        for (start, end, app, fpath, is_idle) in self.blocks:
            if end < self.view_start or start > self.view_end: continue # 不在视口内，跳过
            
            x_start = self.time_to_pixel(max(start, self.view_start), width)
            x_end = self.time_to_pixel(min(end, self.view_end), width)
            block_w = max(1.5, x_end - x_start) # 最窄 1.5 像素，太细了看不清
            
            color = self._get_app_color(app, is_idle)
            painter.setBrush(QBrush(color))
            painter.drawRect(int(x_start), 20, int(block_w), height - 20)

        # 4. 实时红线 (当前时间)
        now = datetime.now()
        now_sec = now.hour * 3600 + now.minute * 60 + now.second
        if self.view_start <= now_sec <= self.view_end:
            now_x = int(self.time_to_pixel(now_sec, width))
            painter.setPen(QPen(QColor("#FF4500"), 2))
            painter.drawLine(now_x, 0, now_x, height)
# ================= 主窗口 =================

class DashboardV2(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 读取配置的主题设置
        self.is_dark_mode = get_config("app_theme", "dark") == "dark"
        
        init_db()  
        self.setWindowTitle("FocusFlow - Fenghu专业工时看板")
        self.resize(1300, 800)
        
        # 完美状态记录容器
        self.expanded_uids = set()
        self.selected_uid_left = None
        self.selected_path_right = None

        self._current_track_path = None
        self._session_seconds = 0
        
        # 提前实例化悬浮窗（在 setup_ui 之前）
        self.floating_widget = FloatingWidget(self)

        self.setup_ui()
        self.apply_modern_theme()
        
        # 初始化系统托盘
        self.system_tray = SystemTrayManager(self)
        self.system_tray.setup()
        
        # 【macOS】设置应用不在 Dock 中显示
        if sys.platform == 'darwin':
            self._setup_macos_dock_behavior()
        
        # 初始化定时器（每 3 秒刷新一次数据）
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(3000)
        
        # 标记是否正在退出
        self._is_quitting = False
        
        self.refresh_data()
        
        # 窗口显示后，再次更新菜单文本确保状态正确
        QTimer.singleShot(100, self.system_tray.update_menu_texts)
    
    def _setup_macos_dock_behavior(self):
        """设置 macOS 下 Dock 栏行为"""
        try:
            from AppKit import NSApplication, NSApplicationActivationPolicyRegular
            
            # 获取 NSApplication 实例
            app = NSApplication.sharedApplication()
            
            # 设置为 regular 模式（默认，会在 Dock 显示）
            # 后面会在 hideEvent 和 showEvent 中动态切换
            app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
            
            self._macos_app = app
            print("✅ macOS Dock 动态管理已初始化")
        except Exception as e:
            print(f"⚠️ macOS Dock 管理初始化失败：{e}")
            self._macos_app = None
    
    def _update_macos_dock_visibility(self):
        """根据窗口可见性更新 Dock 图标显示"""
        if not hasattr(self, '_macos_app') or self._macos_app is None:
            return
        
        try:
            from AppKit import NSApplicationActivationPolicyRegular, NSApplicationActivationPolicyAccessory
            
            if self.isVisible():
                # 窗口可见 → 在 Dock 显示
                self._macos_app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
            else:
                # 窗口隐藏 → 不在 Dock 显示
                self._macos_app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except Exception as e:
            pass  # 静默失败，不影响主功能

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
        # 数据大屏入口按钮
        self.btn_dashboard = QPushButton("数据大屏")
        self.btn_dashboard.setStyleSheet("background-color: #31A8FF; color: white; font-weight: bold; padding: 4px 12px; border-radius: 4px; margin-left: 15px;")
        self.btn_dashboard.clicked.connect(lambda: DataDashboardWindow(self).exec())
        header_layout.addWidget(self.btn_dashboard)
        # 呼出悬浮秒表（确保 floating_widget 已初始化）
        self.btn_float = QPushButton("悬浮秒表")
        self.btn_float.setStyleSheet("background-color: #4A4A4A; color: white; font-weight: bold; padding: 4px 12px; border-radius: 4px; margin-left: 10px;")
        self.btn_float.clicked.connect(self.floating_widget.show)
        header_layout.addWidget(self.btn_float)
        
        title_label.setObjectName("titleLabel")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.lbl_status = QLabel("状态：等待连接...")
        self.lbl_status.setObjectName("statusLabel")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.lbl_status)
        header_layout.addStretch()
        
        self.btn_blacklist = QPushButton("黑名单")
        self.btn_blacklist.clicked.connect(self.open_blacklist)
        
        # 【新增】：批量导出结算大单按钮
        self.btn_export_all = QPushButton("导出全盘月度总结算单")
        self.btn_export_all.setStyleSheet("background-color: #2E8B57; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        self.btn_export_all.clicked.connect(self.action_export_all_bills)
        
        self.btn_settings = QPushButton("设置")
        self.btn_settings.clicked.connect(self.open_settings)
        
        header_layout.addWidget(self.btn_export_all)
        header_layout.addWidget(self.btn_blacklist)
        header_layout.addWidget(self.btn_settings)
        main_layout.addWidget(header)

        # --- 2. 极致紧凑的项目大盘 (Stats Bar) ---
        # --- 2. 极致紧凑的项目大盘 (Stats Bar - 左右弹簧对齐) ---
        # --- 2. 紧凑型大盘 (QGridLayout 像素级对齐) ---
        self.stats_frame = QFrame()
        self.stats_frame.setObjectName("statsBar")
        self.stats_frame.setStyleSheet("background-color: #2D2D30; border-bottom: 1px solid #333333;")
        self.stats_frame.setFixedHeight(50) # 稍微加高适应两行
        
        stats_layout = QGridLayout(self.stats_frame)
        stats_layout.setContentsMargins(20, 6, 20, 6)
        stats_layout.setHorizontalSpacing(30)
        stats_layout.setVerticalSpacing(2)
        
        font_name = "font-weight: bold; font-size: 13px;"
        font_time = "font-family: 'Menlo', 'Consolas', monospace; font-size: 13px; font-weight: bold;"
        
        # 第一行：项目
        self.lbl_stat_p_name = QLabel("项目：未选中")
        self.lbl_stat_p_name.setStyleSheet(f"color: #D4D4D4; {font_name}")
        self.lbl_stat_p_times = QLabel("累积：00:00:00    今日：00:00:00")
        self.lbl_stat_p_times.setStyleSheet(f"color: #CCCCCC; {font_time}")
        
        # 第二行：程序
        self.lbl_stat_a_name = QLabel("程序：无")
        self.lbl_stat_a_name.setStyleSheet(f"color: #68D391; {font_name}")
        self.lbl_stat_a_times = QLabel("累积：00:00:00    今日：00:00:00    本次连续：00:00:00")
        self.lbl_stat_a_times.setStyleSheet(f"color: #34C759; {font_time}")
        
        stats_layout.addWidget(self.lbl_stat_p_name, 0, 0, Qt.AlignLeft)
        stats_layout.addWidget(self.lbl_stat_p_times, 0, 1, Qt.AlignRight)
        stats_layout.addWidget(self.lbl_stat_a_name, 1, 0, Qt.AlignLeft)
        stats_layout.addWidget(self.lbl_stat_a_times, 1, 1, Qt.AlignRight)
        
        stats_layout.setColumnStretch(0, 1) # 强行左右五五开
        stats_layout.setColumnStretch(1, 1)
        main_layout.addWidget(self.stats_frame)

        # --- 3. 主分栏 ---
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：项目树
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 5, 10)
        left_header = QHBoxLayout()
        left_header.addWidget(QLabel("项目管理", objectName="panelTitle"))
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
        
        # 【新增】Inbox 标题栏（带分组视图切换和时长筛选）
        right_header = QHBoxLayout()
        right_header.addWidget(QLabel("Inbox 待分配 (自动捕获)", objectName="panelTitle"))
        right_header.addStretch()
        self.btn_inbox_group = QCheckBox("分组视图")
        self.btn_inbox_group.setChecked(False)
        self.btn_inbox_group.stateChanged.connect(self.refresh_data)
        right_header.addWidget(self.btn_inbox_group)
        
        # 【新增】时长筛选控件
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("⏱ 忽略<"))
        self.spin_filter_threshold = QSpinBox()
        self.spin_filter_threshold.setRange(0, 3600)  # 0-3600 秒
        self.spin_filter_threshold.setValue(60)  # 默认 60 秒
        self.spin_filter_threshold.setMaximumWidth(80)
        self.spin_filter_threshold.setMinimumWidth(60)
        self.spin_filter_threshold.valueChanged.connect(self.on_filter_threshold_changed)
        filter_layout.addWidget(self.spin_filter_threshold)
        filter_layout.addWidget(QLabel("秒"))
        right_header.addLayout(filter_layout)
        
        right_layout.addLayout(right_header)
        
        self.tree_inbox = QTreeView()
        self.tree_inbox.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree_inbox.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_inbox.setSelectionMode(QAbstractItemView.ExtendedSelection)  # 【新增】支持多选
        self.tree_inbox.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_inbox.customContextMenuRequested.connect(self.show_inbox_menu)
        right_layout.addWidget(self.tree_inbox)
        
        # 【新增】底部操作栏
        inbox_action_bar = QHBoxLayout()
        self.lbl_inbox_selected = QLabel("已选中 0 个文件")
        self.lbl_inbox_selected.setStyleSheet("color: #9CDCFE; font-weight: bold;")
        inbox_action_bar.addWidget(self.lbl_inbox_selected)
        
        inbox_action_bar.addStretch()
        
        self.btn_assign_selected = QPushButton("批量分配")
        self.btn_assign_selected.clicked.connect(self.action_assign_selected_batch)
        self.btn_assign_selected.setEnabled(False)
        inbox_action_bar.addWidget(self.btn_assign_selected)
        
        self.btn_clear_selection = QPushButton("取消选择")
        self.btn_clear_selection.clicked.connect(self.clear_inbox_selection)
        self.btn_clear_selection.setEnabled(False)
        inbox_action_bar.addWidget(self.btn_clear_selection)
        
        self.btn_view_fragments = QPushButton("🗑 查看碎片记录")
        self.btn_view_fragments.clicked.connect(self.show_fragment_dialog)
        inbox_action_bar.addWidget(self.btn_view_fragments)
        
        right_layout.addLayout(inbox_action_bar)

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
        self.model_inbox.setHorizontalHeaderLabels(["文件名", "程序", "路径", "总计", "今日", "最后活跃"])
        self.tree_inbox.setModel(self.model_inbox)
        self.tree_inbox.header().setSectionResizeMode(2, QHeaderView.Stretch)  # 路径列拉伸
        self.tree_inbox.setColumnWidth(0, 200)  # 文件名
        self.tree_inbox.setColumnWidth(1, 100)  # 程序
        self.tree_inbox.setColumnWidth(3, 70)   # 总计
        self.tree_inbox.setColumnWidth(4, 70)   # 今日
        self.tree_inbox.setSortingEnabled(True)         # 允许点击表头排序
        self.model_inbox.setSortRole(Qt.UserRole + 3)   # 告诉它按底层数字大小排，而不是按字符串排
        
        # 【新增】监听选择变化
        self.tree_inbox.selectionModel().selectionChanged.connect(self.on_inbox_selection_changed)
        
        # 【新增】Inbox 分组视图状态管理
        self.inbox_expanded_apps = set()  # 记录展开的程序名
        self.inbox_group_mode = False     # 当前是否分组视图模式
        self.filter_threshold_seconds = 60  # 【新增】时长筛选阈值（默认 60 秒）
        
# --- 5. 【新增】底部时间轴 ---
        self.timeline = TimelineWidget()
        main_layout.addWidget(self.timeline)
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
        
        # 【新增】保存 Inbox 分组展开状态
        if self.inbox_group_mode:
            self.inbox_expanded_apps.clear()
            for i in range(self.model_inbox.rowCount()):
                item = self.model_inbox.item(i, 0)
                if item and item.data(Qt.UserRole + 6):  # 是分组头
                    app_name = item.data(Qt.UserRole + 5)
                    if app_name and self.tree_inbox.isExpanded(self.model_inbox.index(i, 0)):
                        self.inbox_expanded_apps.add(app_name)
            
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
            # 【增强】支持在分组视图模式下恢复选中状态
            if self.inbox_group_mode:
                # 分组模式下，文件在分组头的子项中
                for i in range(self.model_inbox.rowCount()):
                    header_item = self.model_inbox.item(i, 0)
                    if header_item and header_item.data(Qt.UserRole + 6):  # 是分组头
                        for j in range(header_item.rowCount()):
                            file_item = header_item.child(j, 0)
                            if file_item and file_item.data(Qt.UserRole + 1) == self.selected_path_right:
                                self.tree_inbox.selectionModel().select(file_item.index(), QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
                                self.tree_inbox.setCurrentIndex(file_item.index())
                                break
            else:
                # 普通列表模式
                for i in range(self.model_inbox.rowCount()):
                    item = self.model_inbox.item(i, 0)
                    if item and item.data(Qt.UserRole + 1) == self.selected_path_right:
                        self.tree_inbox.selectionModel().select(item.index(), QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
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
    # ================= 核心刷新逻辑 =================
    def refresh_data(self):
        self._auto_assign_from_rules()
        
        # 【修复：左侧项目树智能刷新检测】
        # 计算当前项目的“结构指纹”（只有在新建/删除项目，或者新分配了文件时，指纹才会变）
        conn = get_connection()
        projs = conn.execute("SELECT id, parent_id, project_name FROM projects").fetchall()
        archs = conn.execute("SELECT project_id FROM project_archive").fetchall()
        files = conn.execute("SELECT file_path, project_id FROM file_assignment").fetchall()
        conn.close()
        
        current_tree_hash = hash(str(projs) + str(archs) + str(files) + str(self.chk_archived.isChecked()))
        
        if getattr(self, 'last_tree_hash', None) != current_tree_hash:
            # 结构发生了变化（如新建了项目、刚分配了文件），执行带状态恢复的全量重绘
            self.save_tree_state()
            self.model_projects.removeRows(0, self.model_projects.rowCount())
            
            show_archived = self.chk_archived.isChecked()
            tree = load_project_tree()
            for root in tree.get_root_nodes():
                if not root.is_archived or show_archived:
                    self._build_project_tree_recursive(root, self.model_projects.invisibleRootItem(), show_archived)
                    
            self.restore_tree_state()
            self.last_tree_hash = current_tree_hash
        else:
            # 结构完全没变，仅仅是时间数字在增加！执行极速静默更新，绝对不破坏焦点和层级
            self._update_tree_durations_in_place()

        self._load_inbox_data()
        self._update_top_stats()
        self._update_timeline()  # 【新增】触发时间轴重绘

    def _update_tree_durations_in_place(self, parent_item=None, conn=None):
        # 递归静默更新左侧项目树的时间数字，不动节点结构
        is_root_call = False
        if conn is None:
            conn = get_connection()
            is_root_call = True
            
        if parent_item is None:
            parent_item = self.model_projects.invisibleRootItem()
            
        for i in range(parent_item.rowCount()):
            item_name = parent_item.child(i, 0)
            item_total = parent_item.child(i, 1)
            item_today = parent_item.child(i, 2)
            
            pid = item_name.data(Qt.UserRole + 1)
            fpath = item_name.data(Qt.UserRole + 2)
            
            if pid:
                # 这是一个项目，获取项目最新总时长
                stats = get_project_stats(pid, include_children=False)
                item_total.setText(format_duration(stats['total']))
                item_today.setText(format_duration(stats['today']))
            elif fpath:
                # 这是一个文件，直接用 SQL 极速查出它的最新时长
                # 【性能优化】：使用区间查询替代 DATE() 函数，使索引生效
                today_start, tomorrow_start = get_date_range(0)
                row = conn.execute("""
                    SELECT COALESCE(SUM(duration), 0), 
                           COALESCE(SUM(CASE WHEN timestamp >= ? AND timestamp < ? THEN duration ELSE 0 END), 0) 
                    FROM activity_log WHERE file_path = ?
                """, (today_start, tomorrow_start, fpath)).fetchone()
                if row:
                    item_total.setText(format_duration(row[0]))
                    item_today.setText(format_duration(row[1]))
            
            # 递归更新子节点
            if item_name.hasChildren():
                self._update_tree_durations_in_place(item_name, conn)
                
        if is_root_call:
            conn.close()

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
        latest_log = conn.execute("SELECT app_name, file_path, timestamp FROM activity_log ORDER BY timestamp DESC LIMIT 1").fetchone()
        status_row = conn.execute("SELECT is_idle, idle_seconds, app_name, file_path FROM runtime_status WHERE id=1").fetchone()
        
        active_fpath = None
        is_idle = True
        idle_seconds = 0
        app_name = "未知"
        
        if status_row:
            is_idle, idle_seconds, app_name, active_fpath = status_row
            
        if latest_log:
            l_app, l_path, l_time = latest_log
            try:
                seconds_ago = (datetime.now() - datetime.fromisoformat(l_time)).total_seconds()
                if seconds_ago < 5: 
                    is_idle = False
                    app_name = l_app
                    active_fpath = l_path
            except: pass

        # 1. 核心计算：全局“本次连续时长”
        if is_idle:
            self._session_seconds = 0
            self._current_track_path = None
        else:
            if self._current_track_path == active_fpath:
                self._session_seconds += 3 # 跟着定时器步进
            else:
                self._current_track_path = active_fpath
                self._session_seconds = 3

        # 2. 获取程序和项目的数据
        d_path = "--"
        p_name = "未分配"
        p_today, p_total, a_today, a_total = 0, 0, 0, 0

        if not is_idle and active_fpath:
            d_path = active_fpath if active_fpath.startswith("[") else os.path.basename(active_fpath)
            
            # 程序时长
            # 【性能优化】：使用区间查询替代 DATE(SUBSTR()) 函数，使索引生效
            today_start, tomorrow_start = get_date_range(0)
            row_app = conn.execute("""
                SELECT COALESCE(SUM(duration), 0), 
                       COALESCE(SUM(CASE WHEN timestamp >= ? AND timestamp < ? THEN duration ELSE 0 END), 0)
                FROM activity_log WHERE file_path = ?
            """, (today_start, tomorrow_start, active_fpath)).fetchone()
            if row_app: a_total, a_today = row_app[0], row_app[1]

            # 项目时长
            target_pid = None
            if self.selected_uid_left and self.selected_uid_left.startswith("P_"):
                # 用户手动选择了项目
                target_pid = int(self.selected_uid_left[2:])
            else:
                # 先查 file_assignment 表
                row_pid = conn.execute("SELECT project_id FROM file_assignment WHERE file_path = ?", (active_fpath,)).fetchone()
                if row_pid:
                    target_pid = row_pid[0]
                else:
                    # 如果 file_assignment 没有，查 project_map 自动分配规则
                    rules = conn.execute("""
                        SELECT project_id, rule_path FROM project_map 
                        WHERE rule_path IS NOT NULL AND rule_path != ''
                        ORDER BY id DESC
                    """).fetchall()
                    
                    for pid, rule in rules:
                        if rule and rule.lower() in active_fpath.lower():
                            target_pid = pid
                            break
            
            if target_pid:
                p_name = conn.execute("SELECT project_name FROM projects WHERE id = ?", (target_pid,)).fetchone()[0]
                stats = get_project_stats(target_pid, include_children=True)
                p_today, p_total = stats['today'], stats['total']

        conn.close()

        # 3. 渲染主界面顶部状态
        # 3. 渲染主界面顶部状态
        def fmt_full(secs):
            s = int(float(secs))
            return f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"

        if is_idle:
            self.lbl_status.setText(f"闲置中 ({int(idle_seconds)} 秒)")
            self.lbl_status.setStyleSheet("color: #FF9F0A; font-weight: bold; font-size: 13px;")
            
            self.lbl_stat_p_name.setText("项目：休息中")
            self.lbl_stat_p_times.setText("累积：--:--:--    今日：--:--:--")
            self.lbl_stat_a_name.setText("程序：离开座位")
            self.lbl_stat_a_times.setText("累积：--:--:--    今日：--:--:--    本次：--:--:--")
        else:
            self.lbl_status.setText(f"正在追踪：{app_name} | {d_path}")
            self.lbl_status.setStyleSheet("color: #34C759; font-weight: bold; font-size: 13px;")
            
            self.lbl_stat_p_name.setText(f"项目：{p_name}")
            self.lbl_stat_p_times.setText(f"累积：{fmt_full(p_total)}    今日：{fmt_full(p_today)}")
            self.lbl_stat_a_name.setText(f"程序：{d_path}")
            self.lbl_stat_a_times.setText(f"累积：{fmt_full(a_total)}    今日：{fmt_full(a_today)}    本次：{fmt_full(self._session_seconds)}")

        # 4. 同步分发给悬浮窗 (如果悬浮窗开着)
        if hasattr(self, 'floating_widget') and self.floating_widget.isVisible():
            self.floating_widget.sync_data(
                is_idle, idle_seconds, 
                p_name, p_today, p_total,  # 传入了原生的 p_total 秒数
                d_path, a_today, self._session_seconds
            )
    def _update_timeline(self):
        # 提取今日所有秒级日志，聚合成连续的时间块
        conn = get_connection()
        
        # 【性能优化】：使用区间查询替代 DATE(SUBSTR()) 函数，使索引生效
        today_start, tomorrow_start = get_date_range(0)
        
        # 1. 查出今天的真实工作记录（原始秒级记录，在 Python 中按连续时段聚合后再过滤）
        logs = conn.execute("""
            SELECT timestamp, duration, app_name, file_path 
            FROM activity_log 
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp ASC
        """, (today_start, tomorrow_start)).fetchall()
        
        # 2. 查出今天的闲置记录 (从 runtime_status 衍生，或者由于后台在闲置时根本不记入 activity_log，这里会有时间断层)
        # 我们用“找时间断层”的方法，反推你今天几点在闲置！
        
        blocks = []
        if not logs:
            self.timeline.update_data(blocks)
            conn.close()
            return
            
        current_block = None
        
        for timestamp_str, duration, app, fpath in logs:
            try:
                dt = datetime.fromisoformat(timestamp_str.split('.')[0])
                # 计算该记录发生的时间，属于今天的第几秒
                start_sec = dt.hour * 3600 + dt.minute * 60 + dt.second
                end_sec = start_sec + duration
                
                if current_block is None:
                    current_block = [start_sec, end_sec, app, fpath, False]
                else:
                    # 如果这条记录紧挨着上一条(断层 < 60秒)，并且软件名一样，我们就把它粘合(聚合)成一个大色块
                    if start_sec - current_block[1] <= 60 and app == current_block[2]:
                        current_block[1] = end_sec
                    else:
                        # 如果换了软件，或者发生了长达 1 分钟以上的断层(说明你刚才发呆了或者离开了电脑)
                        blocks.append(current_block)
                        
                        # 把这中间的断层，画成灰色的“闲置色块”
                        if start_sec - current_block[1] > 60:
                            blocks.append([current_block[1], start_sec, "Idle", "", True])
                            
                        current_block = [start_sec, end_sec, app, fpath, False]
            except:
                pass
                
        if current_block:
            blocks.append(current_block)
        
        # 【新增】应用时长筛选：过滤掉总时长 < 阈值的连续活动块
        if self.filter_threshold_seconds > 0:
            blocks = [b for b in blocks if (b[1] - b[0]) >= self.filter_threshold_seconds]
            
        self.timeline.update_data(blocks)
        conn.close()
    def _build_project_tree_recursive(self, node, parent_item, show_archived):
        stats = get_project_stats(node.id, include_children=False)
        prefix = "[归档] " if node.is_archived else ""
        item_name = QStandardItem(f"{prefix}{node.name}")
        item_name.setData(node.id, Qt.UserRole + 1) 
        item_name.setData(node.is_archived, Qt.UserRole + 3)
        
        item_total = QStandardItem(format_duration(stats['total']))
        item_today = QStandardItem(format_duration(stats['today']))
        item_total.setSelectable(False)
        item_today.setSelectable(False)
        parent_item.appendRow([item_name, item_total, item_today])
        
        # 【修复 1：直接用精准 SQL 查本项目的子文件时间，解决时间为 0 的问题】
        conn = get_connection()
        # 【性能优化】：使用区间查询替代 DATE() 函数，使索引生效
        today_start, tomorrow_start = get_date_range(0)
        files = conn.execute("""
            SELECT fa.file_path, MAX(al.app_name), 
                   COALESCE(SUM(al.duration), 0), 
                   COALESCE(SUM(CASE WHEN al.timestamp >= ? AND al.timestamp < ? THEN al.duration ELSE 0 END), 0)
            FROM file_assignment fa
            LEFT JOIN activity_log al ON fa.file_path = al.file_path
            WHERE fa.project_id = ?
            GROUP BY fa.file_path
        """, (today_start, tomorrow_start, node.id)).fetchall()
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
        # 【新增】：同步分组视图模式状态
        new_group_mode = self.btn_inbox_group.isChecked()
        
        # 检测视图模式是否切换
        mode_changed = getattr(self, 'inbox_group_mode', None) != new_group_mode
        self.inbox_group_mode = new_group_mode
        
        conn = get_connection()
        cursor = conn.cursor()
        # 【性能优化】：使用区间查询替代 DATE() 函数，使索引生效
        today_start, tomorrow_start = get_date_range(0)
        cursor.execute("""
            SELECT al.app_name, al.file_path, SUM(al.duration) as total,
                SUM(CASE WHEN al.timestamp >= ? AND al.timestamp < ? THEN al.duration ELSE 0 END) as today,
                MAX(al.timestamp) as last_seen
            FROM activity_log al
            LEFT JOIN file_assignment fa ON al.file_path = fa.file_path
            LEFT JOIN ignore_list il ON al.app_name LIKE '%' || il.keyword || '%' OR al.file_path LIKE '%' || il.keyword || '%'
            WHERE fa.file_path IS NULL AND il.keyword IS NULL
            GROUP BY al.app_name, al.file_path
            HAVING SUM(al.duration) >= ?
            ORDER BY al.app_name, last_seen DESC
        """, (today_start, tomorrow_start, self.filter_threshold_seconds))
        new_data = cursor.fetchall()
        conn.close()
        
        # 【多列显示】：分离文件名、程序、路径
        def parse_file_info(app_name, file_path):
            """解析文件信息，返回 (文件名，程序名，路径)"""
            if file_path.startswith("["):
                # 特殊标记（如网页标签）
                return file_path.strip("[]"), app_name, ""
            
            base_name = os.path.basename(file_path)
            dir_path = os.path.dirname(file_path)
            
            # 简化路径显示
            if dir_path.startswith("/Users/"):
                dir_path = "~" + dir_path[len("/Users/"):]
            
            return base_name, app_name, dir_path
        
        # 【新增】计算 Inbox 结构指纹（只有文件集合变化时才重绘）
        current_inbox_hash = hash(str(sorted([(row[0], row[1]) for row in new_data])))
        
        # 【分组视图模式】
        if self.inbox_group_mode:
            # 视图模式切换或结构变化时，重新绘制
            if mode_changed or getattr(self, 'last_inbox_hash', None) != current_inbox_hash:
                self._render_inbox_group_mode(new_data, parse_file_info)
                self.last_inbox_hash = current_inbox_hash
            else:
                # 结构没变，只更新时间数字（不破坏展开状态）
                self._update_inbox_durations_in_group_mode(new_data, parse_file_info)
        
        # 【普通列表视图模式】
        else:
            existing_paths = {}
            for i in range(self.model_inbox.rowCount()):
                item = self.model_inbox.item(i, 0)
                existing_paths[item.data(Qt.UserRole + 1)] = i

            new_paths_set = {row[1] for row in new_data}
            
            if set(existing_paths.keys()) == new_paths_set:
                # 精准更新时间数字
                for row in new_data:
                    app_name, file_path, total, today, last_seen = row
                    try: time_str = datetime.fromisoformat(last_seen.split('.')[0]).strftime("%m-%d %H:%M")
                    except: time_str = last_seen
                    
                    row_idx = existing_paths[file_path]
                    it_total = self.model_inbox.item(row_idx, 3)
                    it_total.setText(format_duration(total))
                    it_total.setData(total, Qt.UserRole + 3)

                    it_today = self.model_inbox.item(row_idx, 4)
                    it_today.setText(format_duration(today))
                    it_today.setData(today, Qt.UserRole + 3)

                    it_last = self.model_inbox.item(row_idx, 5)
                    it_last.setText(time_str)
                    it_last.setData(last_seen, Qt.UserRole + 3)
            else:
                # 重新排版
                self.model_inbox.removeRows(0, self.model_inbox.rowCount())
                for row in new_data:
                    app_name, file_path, total, today, last_seen = row
                    file_name, prog_name, dir_path = parse_file_info(app_name, file_path)
                    
                    try: time_str = datetime.fromisoformat(last_seen.split('.')[0]).strftime("%m-%d %H:%M")
                    except: time_str = last_seen
                        
                    # 列 0：文件名
                    item_name = QStandardItem(file_name)
                    item_name.setData(file_path, Qt.UserRole + 1)
                    item_name.setData(app_name, Qt.UserRole + 2)
                    item_name.setData(file_name.lower(), Qt.UserRole + 3)
                    item_name.setToolTip(file_path)
                    
                    # 列 1：程序
                    item_prog = QStandardItem(prog_name)
                    item_prog.setData(prog_name.lower(), Qt.UserRole + 3)
                    
                    # 列 2：路径
                    item_dir = QStandardItem(dir_path)
                    item_dir.setData(dir_path.lower(), Qt.UserRole + 3)
                    item_dir.setToolTip(file_path)
                    
                    item_total = QStandardItem(format_duration(total))
                    item_total.setData(total, Qt.UserRole + 3)
                    
                    item_today = QStandardItem(format_duration(today))
                    item_today.setData(today, Qt.UserRole + 3)
                    
                    item_last = QStandardItem(time_str)
                    item_last.setData(last_seen, Qt.UserRole + 3)
                    
                    self.model_inbox.appendRow([item_name, item_prog, item_dir, item_total, item_today, item_last])
    
    # 【新增】分组视图模式：渲染 Inbox（结构变化时调用）
    def _render_inbox_group_mode(self, new_data, parse_file_info):
        from collections import defaultdict
        self.model_inbox.removeRows(0, self.model_inbox.rowCount())
        
        # 按程序名分组数据
        grouped_data = defaultdict(list)
        for row in new_data:
            app_name, file_path, total, today, last_seen = row
            grouped_data[app_name].append(row)
        
        # 为每个程序创建分组头
        for app_name in sorted(grouped_data.keys()):
            files = grouped_data[app_name]
            
            # 创建分组头（不可选中，带文件数）
            header_item = QStandardItem(f"{app_name} ({len(files)}个文件)")
            header_item.setSelectable(False)
            header_item.setData(app_name, Qt.UserRole + 5)  # 标记为程序分组头
            header_item.setData(True, Qt.UserRole + 6)      # 标记是分组头
            
            # 创建占位列
            header_prog = QStandardItem("")
            header_prog.setSelectable(False)
            header_dir = QStandardItem("")
            header_dir.setSelectable(False)
            header_total = QStandardItem("")
            header_total.setSelectable(False)
            header_today = QStandardItem("")
            header_today.setSelectable(False)
            header_last = QStandardItem("")
            header_last.setSelectable(False)
            
            # 添加分组头到模型
            self.model_inbox.appendRow([header_item, header_prog, header_dir, header_total, header_today, header_last])
            header_index = self.model_inbox.rowCount() - 1
            
            # 设置展开/折叠状态
            if app_name in self.inbox_expanded_apps:
                self.tree_inbox.setExpanded(self.model_inbox.index(header_index, 0), True)
            else:
                self.tree_inbox.setExpanded(self.model_inbox.index(header_index, 0), False)
            
            # 为该程序下的每个文件创建子项
            for row in files:
                app_name, file_path, total, today, last_seen = row
                file_name, prog_name, dir_path = parse_file_info(app_name, file_path)
                
                try: time_str = datetime.fromisoformat(last_seen.split('.')[0]).strftime("%m-%d %H:%M")
                except: time_str = last_seen
                
                # 列 0：文件名
                item_name = QStandardItem(file_name)
                item_name.setData(file_path, Qt.UserRole + 1)
                item_name.setData(app_name, Qt.UserRole + 2)
                item_name.setData(file_name.lower(), Qt.UserRole + 3)
                item_name.setToolTip(file_path)
                
                # 列 1：程序
                item_prog = QStandardItem(prog_name)
                item_prog.setData(prog_name.lower(), Qt.UserRole + 3)
                
                # 列 2：路径
                item_dir = QStandardItem(dir_path)
                item_dir.setData(dir_path.lower(), Qt.UserRole + 3)
                item_dir.setToolTip(file_path)
                
                item_total = QStandardItem(format_duration(total))
                item_total.setData(total, Qt.UserRole + 3)
                
                item_today = QStandardItem(format_duration(today))
                item_today.setData(today, Qt.UserRole + 3)
                
                item_last = QStandardItem(time_str)
                item_last.setData(last_seen, Qt.UserRole + 3)
                
                # 添加到分组头下
                header_item.appendRow([item_name, item_prog, item_dir, item_total, item_today, item_last])
    
    # 【新增】分组视图模式：只更新时间数字（保持展开状态）
    def _update_inbox_durations_in_group_mode(self, new_data, parse_file_info):
        # 构建 {file_path: (total, today, last_seen)} 的映射
        data_map = {}
        for row in new_data:
            app_name, file_path, total, today, last_seen = row
            data_map[file_path] = (total, today, last_seen)
        
        # 遍历所有分组头下的子项，精准更新
        for i in range(self.model_inbox.rowCount()):
            header_item = self.model_inbox.item(i, 0)
            if header_item and header_item.data(Qt.UserRole + 6):  # 是分组头
                for j in range(header_item.rowCount()):
                    file_item = header_item.child(j, 0)
                    if file_item:
                        fpath = file_item.data(Qt.UserRole + 1)
                        if fpath in data_map:
                            total, today, last_seen = data_map[fpath]
                            
                            # 更新对应列（列索引：3=总计，4=今日，5=最后活跃）
                            it_total = header_item.child(j, 3)
                            it_today = header_item.child(j, 4)
                            it_last = header_item.child(j, 5)
                            
                            if it_total:
                                it_total.setText(format_duration(total))
                                it_total.setData(total, Qt.UserRole + 3)
                            
                            if it_today:
                                it_today.setText(format_duration(today))
                                it_today.setData(today, Qt.UserRole + 3)
                            
                            if it_last:
                                try: time_str = datetime.fromisoformat(last_seen.split('.')[0]).strftime("%m-%d %H:%M")
                                except: time_str = last_seen
                                it_last.setText(time_str)
                                it_last.setData(last_seen, Qt.UserRole + 3)

    # ================= 右键菜单交互 (保持不变) =================
    def show_project_menu(self, pos):
        index = self.tree_projects.indexAt(pos)
        menu = QMenu(self)
        if not index.isValid():
            menu.addAction("➕ 新建根项目").triggered.connect(lambda: self.action_new_project(None))
            menu.exec(self.tree_projects.viewport().mapToGlobal(pos))
            return

        item_node = self.model_projects.itemFromIndex(index.siblingAtColumn(0))
        project_id = item_node.data(Qt.UserRole + 1)
        file_path = item_node.data(Qt.UserRole + 2)
        is_archived = item_node.data(Qt.UserRole + 3)

        if file_path:
            menu.addAction("↩️ 移出记录 (回 Inbox)").triggered.connect(lambda: self.action_remove_file(file_path))
        elif project_id:
            name_pure = item_node.text().replace("[归档] ", "")
            menu.addAction("➕ 新建子项目").triggered.connect(lambda: self.action_new_project(project_id))
            menu.addAction("✏️ 重命名").triggered.connect(lambda: self.action_rename_project(project_id, name_pure))
            menu.addAction("🤖 编辑自动匹配规则...").triggered.connect(lambda: ProjectRulesDialog(project_id, name_pure, self).exec())
            
            # 【新增】：导出 Excel 账单
            menu.addSeparator()
            action_export = menu.addAction("🧾 导出工时账单 (Excel)...")
            # 使用带图标和特殊颜色的样式，让它更醒目
            action_export.triggered.connect(lambda: self.action_export_bill(project_id, name_pure))
            
            menu.addSeparator()
            if is_archived:
                menu.addAction("取消归档 (恢复)").triggered.connect(lambda: self.action_restore_project(project_id))
            else:
                menu.addAction("归档项目").triggered.connect(lambda: self.action_archive_project(project_id))
            menu.addAction("删除").triggered.connect(lambda: self.action_delete_project(project_id))

        menu.exec_(self.tree_projects.viewport().mapToGlobal(pos))

    def show_inbox_menu(self, pos):
        # 【增强】检查是否有选中的文件
        selected_indexes = self.tree_inbox.selectionModel().selectedRows()
        selected_count = len(selected_indexes)
        
        # 如果有多选，优先显示批量分配菜单
        if selected_count > 1:
            menu = QMenu(self)
            menu.addAction(f"➡️ 批量分配选中的 {selected_count} 个文件到项目...").triggered.connect(
                lambda: self.action_assign_selected_batch()
            )
            menu.addSeparator()
            menu.addAction("取消选择").triggered.connect(self.clear_inbox_selection)
            menu.exec(self.tree_inbox.viewport().mapToGlobal(pos))
            return
        
        # 单选或无选择
        index = self.tree_inbox.indexAt(pos)
        if not index.isValid(): return
        item = self.model_inbox.itemFromIndex(index.siblingAtColumn(0))
        
        # 【新增】判断是否点击在分组头上
        is_header = item.data(Qt.UserRole + 6)
        app_name = item.data(Qt.UserRole + 5)  # 分组头的程序名
        
        if is_header and app_name:
            # 分组头右键菜单：批量分配
            menu = QMenu(self)
            menu.addAction(f"➡️ 批量分配 \"{app_name}\" 的所有文件到项目...").triggered.connect(
                lambda: self.action_assign_app_batch(app_name)
            )
            menu.addSeparator()
            menu.addAction("🚫 永久忽略此程序的所有文件").triggered.connect(
                lambda: self.action_ignore_app(app_name)
            )
        else:
            # 普通文件右键菜单
            f_path = item.data(Qt.UserRole + 1)
            a_name = item.data(Qt.UserRole + 2)
            
            menu = QMenu(self)
            menu.addAction("➡️ 手动分配到项目...").triggered.connect(lambda: self.action_assign_item(f_path))
            menu.addSeparator()
            menu.addAction("🚫 永久忽略 (加黑名单)").triggered.connect(lambda: self.action_ignore_item(a_name))
        
        menu.exec(self.tree_inbox.viewport().mapToGlobal(pos))

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
    def action_export_bill(self, project_id, project_name):
        default_name = f"{project_name}_工时明细_{datetime.now().strftime('%Y%m%d')}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(self, "导出单项目账单", default_name, "Excel Files (*.xlsx)")
        if not file_path: return

        try:
            conn = get_connection()
            tree = load_project_tree()
            node = tree.get_node(project_id)
            if not node: return
            
            # 建立：{project_id: "它的完整路径名称"} 的映射表
            pid_to_path = {}
            def build_paths(n, current_path):
                path = f"{current_path} / {n.name}" if current_path else n.name
                pid_to_path[n.id] = path
                for c in n.get_children(): build_paths(c, path)
            build_paths(node, "")
            
            all_pids = list(pid_to_path.keys())
            placeholders = ','.join('?' * len(all_pids))
            
            # 【性能优化】：使用区间查询替代 DATE() 函数，使索引生效
            # 导出功能需要查询所有历史数据，所以使用全时间范围
            query = f"""
                SELECT 
                    DATE(SUBSTR(timestamp, 1, 10)) as work_date,
                    fa.project_id,
                    al.app_name,
                    al.file_path,
                    al.duration
                FROM activity_log al
                JOIN file_assignment fa ON al.file_path = fa.file_path
                WHERE fa.project_id IN ({placeholders})
                ORDER BY al.timestamp ASC
            """
            import pandas as pd
            df = pd.read_sql_query(query, conn, params=all_pids)
            conn.close()

            if df.empty:
                return QMessageBox.warning(self, "提示", "该项目目前没有任何工时记录。")

            # 【新增：给每一行贴上它属于哪个子项目】
            df['所属项目'] = df['project_id'].map(pid_to_path)
            
            df_grouped = df.groupby(['work_date', '所属项目', 'app_name', 'file_path'])['duration'].sum().reset_index()
            
            def format_dur(secs):
                secs = int(secs)
                return f"{secs//3600}小时 {(secs%3600)//60}分钟" if secs>=3600 else f"{secs//60}分钟"
                
            df_grouped['持续时间'] = df_grouped['duration'].apply(format_dur)
            
            # 调整列的顺序，把“所属项目”放在第二列
            df_final = df_grouped[['work_date', '所属项目', 'app_name', 'file_path', '持续时间']]
            df_final.columns = ['工作日期', '项目/制作阶段', '使用软件', '操作文件 / 窗口', '累计时长']
            df_final = df_final.sort_values(by=['工作日期', '项目/制作阶段'], ascending=[False, True])

            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # 写入明细
                df_final.to_excel(writer, sheet_name='工时明细', index=False)
                
                # 写入总览
                total_seconds = df['duration'].sum()
                pd.DataFrame({
                    '项目名称': [project_name],
                    '导出时间': [datetime.now().strftime('%Y-%m-%d %H:%M')],
                    '总计投入工时': [format_dur(total_seconds)],
                    '总计秒数 (供计算)': [int(total_seconds)]
                }).to_excel(writer, sheet_name='项目总览', index=False)
                
                # 美化列宽
                worksheet = writer.sheets['工时明细']
                for col, width in zip(['A','B','C','D','E'], [15, 25, 20, 50, 15]):
                    worksheet.column_dimensions[col].width = width

            QMessageBox.information(self, "导出成功", f"包含子项目层级的账单已生成！\n\n共 {len(df_final)} 条日结明细记录。")

        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"生成 Excel 时发生错误：\n{str(e)}")

    def action_export_all_bills(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "导出全局总结算单", f"FocusFlow_全局账单_{datetime.now().strftime('%Y%m')}.xlsx", "Excel Files (*.xlsx)")
        if not file_path: return

        try:
            conn = get_connection()
            # 获取所有未归档的根项目
            tree = load_project_tree()
            root_nodes = [n for n in tree.get_root_nodes() if not n.is_archived]
            
            if not root_nodes:
                return QMessageBox.warning(self, "提示", "目前没有活跃的根项目可导出。")

            import pandas as pd
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # 第一页：全局大盘汇总
                global_summary = []
                
                # 遍历每一个根项目，把它生成一个独立的 Sheet
                for root in root_nodes:
                    pid_to_path = {}
                    def build_paths(n, current_path):
                        path = f"{current_path} / {n.name}" if current_path else n.name
                        pid_to_path[n.id] = path
                        for c in n.get_children(): build_paths(c, path)
                    build_paths(root, "")
                    
                    all_pids = list(pid_to_path.keys())
                    placeholders = ','.join('?' * len(all_pids))
                    
                    # 【性能优化】：使用区间查询替代 DATE() 函数，使索引生效
                    query = f"""
                        SELECT DATE(SUBSTR(al.timestamp, 1, 10)) as work_date, fa.project_id, al.app_name, al.file_path, al.duration
                        FROM activity_log al JOIN file_assignment fa ON al.file_path = fa.file_path
                        WHERE fa.project_id IN ({placeholders})
                        ORDER BY al.timestamp ASC
                    """
                    df = pd.read_sql_query(query, conn, params=all_pids)
                    
                    if df.empty: continue # 这个项目没动静就跳过
                    
                    # 生成该项目的明细 Sheet
                    df['所属阶段'] = df['project_id'].map(pid_to_path)
                    df_grouped = df.groupby(['work_date', '所属阶段', 'app_name', 'file_path'])['duration'].sum().reset_index()
                    
                    def format_dur(secs):
                        secs = int(secs)
                        return f"{secs//3600}小时 {(secs%3600)//60}分钟" if secs>=3600 else f"{secs//60}分钟"
                        
                    df_grouped['持续时间'] = df_grouped['duration'].apply(format_dur)
                    
                    df_final = df_grouped[['work_date', '所属阶段', 'app_name', 'file_path', '持续时间']]
                    df_final.columns = ['日期', '制作阶段', '软件', '文件', '耗时']
                    df_final = df_final.sort_values(by=['日期', '制作阶段'], ascending=[False, True])
                    
                    # 为了防止 Sheet 名字过长报错，截取前 25 个字符
                    sheet_name = str(root.name)[:25]
                    df_final.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    # 调整该 Sheet 的列宽
                    worksheet = writer.sheets[sheet_name]
                    for col, width in zip(['A','B','C','D','E'], [15, 20, 20, 50, 15]):
                        worksheet.column_dimensions[col].width = width
                    
                    # 把这个项目的总和存入全局大盘
                    total_seconds = df['duration'].sum()
                    global_summary.append({
                        '项目名称': root.name,
                        '本月/总投入工时': format_dur(total_seconds),
                        '折合小时数': round(total_seconds / 3600, 2)
                    })
                
                # 最后，把全局大盘生成并放在最前面
                if global_summary:
                    df_summary = pd.DataFrame(global_summary)
                    # 添加一行“总计”
                    total_all = sum([float(item['折合小时数']) for item in global_summary])
                    df_summary.loc[len(df_summary)] = ['【所有项目总计】', '--', total_all]
                    
                    df_summary.to_excel(writer, sheet_name='全局财务大盘', index=False)
                    writer.sheets['全局财务大盘'].column_dimensions['A'].width = 30
                    writer.sheets['全局财务大盘'].column_dimensions['B'].width = 25
                    writer.sheets['全局财务大盘'].column_dimensions['C'].width = 15
                    
                    # 将全局大盘移到第一个 Tab
                    sheets = writer.book._sheets
                    summary_sheet = sheets.pop(-1)
                    sheets.insert(0, summary_sheet)

            conn.close()
            QMessageBox.information(self, "导出成功", f"包含所有项目的月度总结算单已生成！\n\n已为您自动整理了各项目独立分页及全局财务大盘。")

        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"生成 Excel 时发生错误：\n{str(e)}")

    def action_assign_item(self, file_path):
        projects = [p for p in get_all_projects_flat() if not p['is_archived']]
        if not projects: return QMessageBox.warning(self, "提示", "请先在左侧新建一个项目！")
        dlg = QDialog(self)
        dlg.setWindowTitle("分配记录")
        layout = QVBoxLayout(dlg)
        combo = QComboBox()
        
        # 添加项目/子项目层级
        projects_data = get_projects_with_subprojects()
        for project_key, project_name in projects_data:
            if project_key != '未分配':
                project_id = int(project_key.replace('project_', ''))
                combo.addItem(project_name, project_id)
        
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
    
    # 【新增】监听 Inbox 选择变化
    def on_inbox_selection_changed(self):
        selected_indexes = self.tree_inbox.selectionModel().selectedRows()
        count = len(selected_indexes)
        
        self.lbl_inbox_selected.setText(f"已选中 {count} 个文件")
        self.btn_assign_selected.setEnabled(count > 0)
        self.btn_clear_selection.setEnabled(count > 0)
    
    # 【新增】取消选择
    def clear_inbox_selection(self):
        self.tree_inbox.selectionModel().clear()
        self.on_inbox_selection_changed()
    
    # 【新增】筛选阈值变化
    def on_filter_threshold_changed(self, value):
        self.filter_threshold_seconds = value
        self.refresh_data()  # 重新加载数据
    
    # 【新增】批量分配选中的文件
    def action_assign_selected_batch(self):
        selected_indexes = self.tree_inbox.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        # 收集所有选中的文件路径
        file_paths = []
        for index in selected_indexes:
            item = self.model_inbox.itemFromIndex(index.siblingAtColumn(0))
            if item:
                fpath = item.data(Qt.UserRole + 1)
                if fpath:  # 有 file_path 说明是文件项，不是分组头
                    file_paths.append(fpath)
        
        if not file_paths:
            return QMessageBox.warning(self, "提示", "没有选中的文件。")
        
        projects = [p for p in get_all_projects_flat() if not p['is_archived']]
        if not projects:
            return QMessageBox.warning(self, "提示", "请先在左侧新建一个项目！")
        
        # 确认对话框
        reply = QMessageBox.question(
            self, "批量分配确认",
            f"确定要将选中的 {len(file_paths)} 个文件分配到同一个项目吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        
        dlg = QDialog(self)
        dlg.setWindowTitle(f"批量分配 ({len(file_paths)} 个文件)")
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(f"选择目标项目："))
        
        combo = QComboBox()
        # 添加项目/子项目层级
        projects_data = get_projects_with_subprojects()
        for project_key, project_name in projects_data:
            if project_key != '未分配':
                project_id = int(project_key.replace('project_', ''))
                combo.addItem(project_name, project_id)
        layout.addWidget(combo)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        
        if dlg.exec() == QDialog.Accepted:
            target_project_id = combo.currentData()
            conn = get_connection()
            
            count = 0
            for file_path in file_paths:
                if file_path:
                    conn.execute(
                        "INSERT OR REPLACE INTO file_assignment (file_path, project_id, assigned_at) VALUES (?, ?, ?)",
                        (file_path, target_project_id, datetime.now().isoformat())
                    )
                    count += 1
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "完成", f"已将 {count} 个文件分配到项目。")
            self.clear_inbox_selection()
            self.refresh_data()
    
    # 【新增】批量分配某程序的所有文件
    def action_assign_app_batch(self, app_name):
        projects = [p for p in get_all_projects_flat() if not p['is_archived']]
        if not projects:
            return QMessageBox.warning(self, "提示", "请先在左侧新建一个项目！")
        
        # 确认对话框
        reply = QMessageBox.question(
            self, "批量分配确认",
            f"确定要将 \"{app_name}\" 的所有待分配文件都分配到同一个项目吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        
        dlg = QDialog(self)
        dlg.setWindowTitle(f"批量分配 - {app_name}")
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(f"选择目标项目："))
        
        combo = QComboBox()
        # 添加项目/子项目层级
        projects_data = get_projects_with_subprojects()
        for project_key, project_name in projects_data:
            if project_key != '未分配':
                project_id = int(project_key.replace('project_', ''))
                combo.addItem(project_name, project_id)
        layout.addWidget(combo)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        
        if dlg.exec() == QDialog.Accepted:
            target_project_id = combo.currentData()
            conn = get_connection()
            
            # 获取该程序所有未分配的文件
            files = conn.execute("""
                SELECT DISTINCT file_path FROM activity_log 
                WHERE app_name = ? 
                AND file_path NOT IN (SELECT file_path FROM file_assignment)
            """, (app_name,)).fetchall()
            
            count = 0
            for (file_path,) in files:
                if file_path:
                    conn.execute(
                        "INSERT OR REPLACE INTO file_assignment (file_path, project_id, assigned_at) VALUES (?, ?, ?)",
                        (file_path, target_project_id, datetime.now().isoformat())
                    )
                    count += 1
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "完成", f"已将 {count} 个文件分配到项目。")
            self.refresh_data()
    
    # 【新增】批量忽略某程序的所有文件
    def action_ignore_app(self, app_name):
        reply = QMessageBox.question(
            self, "批量忽略确认",
            f"确定要将 \"{app_name}\" 加入黑名单吗？\n该程序未来的所有记录都将被忽略。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        
        try:
            conn = get_connection()
            conn.execute("INSERT INTO ignore_list (keyword, created_at) VALUES (?, ?)", 
                        (app_name, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            QMessageBox.information(self, "完成", f"已将 \"{app_name}\" 加入黑名单。")
            self.refresh_data()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "提示", "该程序已在黑名单中。")
    
    # 【新增】查看碎片记录（完整实现）
    def show_fragment_dialog(self):
        conn = get_connection()
        
        # 查询所有碎片记录（总时长 < 阈值的文件）
        fragments = conn.execute("""
            SELECT al.app_name, al.file_path, SUM(al.duration) as total,
                   MIN(al.timestamp) as first_seen, MAX(al.timestamp) as last_seen
            FROM activity_log al
            LEFT JOIN file_assignment fa ON al.file_path = fa.file_path
            WHERE fa.file_path IS NULL
            GROUP BY al.app_name, al.file_path
            HAVING SUM(al.duration) < ?
            ORDER BY total DESC
        """, (self.filter_threshold_seconds,)).fetchall()
        
        conn.close()
        
        if not fragments:
            return QMessageBox.information(
                self, 
                "碎片记录", 
                f"当前没有总时长低于 {self.filter_threshold_seconds} 秒的碎片记录。"
            )
        
        # 计算总时长
        total_seconds = sum(row[2] for row in fragments)
        
        # 创建对话框
        dlg = QDialog(self)
        dlg.setWindowTitle(f"碎片记录 ({len(fragments)} 条)")
        dlg.setMinimumSize(600, 400)
        layout = QVBoxLayout(dlg)
        
        # 顶部信息
        info_label = QLabel(f"共有 {len(fragments)} 条碎片记录，总计 {format_duration(total_seconds)}")
        info_label.setStyleSheet("color: #FFB347; font-weight: bold; font-size: 14px;")
        layout.addWidget(info_label)
        
        layout.addWidget(QLabel("这些记录因为时长太短被过滤，可以选择归档后删除："))
        
        # 文件列表
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["程序", "文件路径", "时长", "首次活跃", "最后活跃"])
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        
        for row in fragments:
            app_name, file_path, total, first_seen, last_seen = row
            row_pos = table.rowCount()
            table.insertRow(row_pos)
            
            table.setItem(row_pos, 0, QTableWidgetItem(app_name))
            
            # 文件路径显示处理
            if file_path.startswith("["):
                display_path = file_path
            else:
                display_path = os.path.basename(file_path)
            item_path = QTableWidgetItem(display_path)
            item_path.setToolTip(file_path)
            table.setItem(row_pos, 1, item_path)
            
            table.setItem(row_pos, 2, QTableWidgetItem(format_duration(total)))
            
            try:
                first_str = datetime.fromisoformat(first_seen.split('.')[0]).strftime("%m-%d %H:%M")
                last_str = datetime.fromisoformat(last_seen.split('.')[0]).strftime("%m-%d %H:%M")
            except:
                first_str = first_seen
                last_str = last_seen
            
            table.setItem(row_pos, 3, QTableWidgetItem(first_str))
            table.setItem(row_pos, 4, QTableWidgetItem(last_str))
        
        layout.addWidget(table)
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(dlg.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_archive = QPushButton("归档并删除选中的记录")
        btn_archive.setStyleSheet("background-color: #FF6B6B; color: white; font-weight: bold;")
        btn_archive.clicked.connect(lambda: self.action_archive_fragments(table, dlg))
        btn_layout.addWidget(btn_archive)
        
        layout.addLayout(btn_layout)
        
        dlg.exec()
    
    # 【新增】归档并删除碎片记录
    def action_archive_fragments(self, table, dialog):
        selected_rows = set()
        for index in table.selectionModel().selectedRows():
            selected_rows.add(index.row())
        
        if not selected_rows:
            # 如果没有选中，默认处理所有
            selected_rows = set(range(table.rowCount()))
        
        if not selected_rows:
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认归档删除",
            f"确定要将选中的 {len(selected_rows)} 条碎片记录归档后删除吗？\n\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        
        conn = get_connection()
        count = 0
        
        for row in selected_rows:
            # 获取文件路径（从 tooltip 中获取完整路径）
            path_item = table.item(row, 1)
            if not path_item:
                continue
            
            file_path = path_item.toolTip()
            app_item = table.item(row, 0)
            app_name = app_item.text() if app_item else "Unknown"
            duration_item = table.item(row, 2)
            
            # 解析时长
            duration_text = duration_item.text() if duration_item else "0"
            try:
                # 从 format_duration 反向解析比较复杂，直接查数据库
                duration = conn.execute("""
                    SELECT SUM(duration) FROM activity_log 
                    WHERE file_path = ? AND app_name = ?
                """, (file_path, app_name)).fetchone()[0] or 0
            except:
                duration = 0
            
            # 1. 归档到 fragment_archive
            conn.execute("""
                INSERT INTO fragment_archive (file_path, app_name, duration, timestamp, archived_at, action)
                SELECT file_path, app_name, duration, timestamp, ?, 'deleted'
                FROM activity_log
                WHERE file_path = ? AND app_name = ?
            """, (datetime.now().isoformat(), file_path, app_name))
            
            # 2. 从 activity_log 删除
            conn.execute("""
                DELETE FROM activity_log WHERE file_path = ? AND app_name = ?
            """, (file_path, app_name))
            
            count += 1
        
        conn.commit()
        conn.close()
        
        QMessageBox.information(
            self,
            "完成",
            f"已归档并删除 {count} 条碎片记录。"
        )
        dialog.accept()
        self.refresh_data()

    def apply_modern_theme(self):
        # 根据主题应用不同样式
        if self.is_dark_mode:
            # 深色主题
            self.setStyleSheet("""
                QMainWindow { background-color: #1E1E1E; }
                QWidget#header { background-color: #252526; }
                QLabel#titleLabel { font-size: 20px; font-weight: bold; color: #FFFFFF; }
                QLabel#statusLabel { color: #CCCCCC; }
                QLabel#statsBar { background-color: #2D2D30; color: #D4D4D4; padding: 0px 20px; font-size: 13px; font-weight: bold; border-bottom: 1px solid #333333; }
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
        else:
            # 浅色主题
            self.setStyleSheet("""
                QMainWindow { background-color: #F5F5F5; }
                QWidget#header { background-color: #FFFFFF; }
                QLabel#titleLabel { font-size: 20px; font-weight: bold; color: #333333; }
                QLabel#statusLabel { color: #666666; }
                QLabel#statsBar { background-color: #E8E8E8; color: #333333; padding: 0px 20px; font-size: 13px; font-weight: bold; border-bottom: 1px solid #CCCCCC; }
                QLabel#panelTitle { color: #0066CC; font-size: 13px; font-weight: bold; padding: 5px; }
                QPushButton { background-color: #0078D4; color: white; border-radius: 4px; padding: 4px 12px; font-weight: bold; }
                QPushButton:hover { background-color: #1084D8; }
                QTreeView { background-color: #FFFFFF; color: #333333; border: 1px solid #CCCCCC; border-radius: 4px; padding: 4px; font-size: 13px; outline: 0;}
                QTreeView::item { padding: 4px; border-radius: 4px; }
                QTreeView::item:hover { background-color: #E8E8E8; }
                QTreeView::item:selected { background-color: #CCE4F7; color: #333333; }
                QHeaderView::section { background-color: #F0F0F0; color: #666666; padding: 4px; border: none; border-right: 1px solid #CCCCCC; border-bottom: 1px solid #CCCCCC; font-weight: bold; font-size: 12px;}
                QMenu { background-color: #FFFFFF; color: #333333; border: 1px solid #CCCCCC; }
                QMenu::item:selected { background-color: #CCE4F7; color: #333333; }
                QListWidget { background-color: #FFFFFF; color: #333333; border: 1px solid #CCCCCC; }
                QListWidget::item:selected { background-color: #CCE4F7; }
                QCheckBox { color: #333333; }
            """)
    
    def closeEvent(self, event):
        """关闭窗口时隐藏到托盘而不是真正关闭"""
        # 如果正在退出，才真正关闭
        if getattr(self, '_is_quitting', False):
            # 保存悬浮窗状态
            if hasattr(self, 'floating_widget'):
                set_config("floating_position_x", str(self.floating_widget.x()))
                set_config("floating_position_y", str(self.floating_widget.y()))
                set_config("floating_visible", "true" if self.floating_widget.isVisible() else "false")
            
            # 清理系统托盘
            if hasattr(self, 'system_tray'):
                self.system_tray.cleanup()
            
            event.accept()
        else:
            # 否则隐藏到托盘
            event.ignore()
            self.hide()
            
            # 保存悬浮窗状态
            if hasattr(self, 'floating_widget'):
                set_config("floating_position_x", str(self.floating_widget.x()))
                set_config("floating_position_y", str(self.floating_widget.y()))
                set_config("floating_visible", "true" if self.floating_widget.isVisible() else "false")
            
            # 更新托盘菜单文本
            if hasattr(self, 'system_tray'):
                self.system_tray.update_menu_texts()
    
    def changeEvent(self, event):
        """处理窗口状态变化（最小化等）"""
        if event.type() == event.Type.WindowStateChange:
            if self.windowState() & Qt.WindowMinimized:
                # 最小化时隐藏到托盘
                self.hide()
                # 更新托盘菜单文本
                if hasattr(self, 'system_tray'):
                    self.system_tray.update_menu_texts()
        super().changeEvent(event)
    
    def hideEvent(self, event):
        """窗口隐藏事件"""
        # 更新 Dock 显示状态
        if sys.platform == 'darwin':
            self._update_macos_dock_visibility()
        super().hideEvent(event)
    
    def showEvent(self, event):
        """窗口显示事件"""
        # 更新 Dock 显示状态
        if sys.platform == 'darwin':
            self._update_macos_dock_visibility()
        super().showEvent(event)


# ============================================================================
# 项目时间线视图组件
# ============================================================================

def format_duration(seconds):
    """格式化时长（秒）为可读字符串"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    
    if hours > 0:
        return f"{hours}小时{minutes}分钟"
    else:
        return f"{minutes}分钟"


def format_time(sec):
    """格式化秒数为 HH:MM 格式"""
    hours = int(sec // 3600)
    minutes = int((sec % 3600) // 60)
    return f"{hours:02d}:{minutes:02d}"


class RecordWidget(QWidget):
    """
    单条活动记录组件
    """
    
    def __init__(self, record):
        super().__init__()
        self.record = record
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(80, 2, 10, 2)
        layout.setSpacing(10)
        
        # 时间
        time_lbl = QLabel(f"{record.get('start_time', 'N/A')} - {record.get('end_time', 'N/A')}")
        time_lbl.setStyleSheet("color: #AAA; font-size: 10px; min-width: 120px;")
        layout.addWidget(time_lbl)
        
        # 应用
        app_lbl = QLabel(f"{record.get('app_name', 'N/A')}")
        app_lbl.setStyleSheet("color: #CCC; font-size: 10px; min-width: 100px;")
        layout.addWidget(app_lbl)
        
        # 文件
        file_path = record.get('file_path', '')
        if file_path:
            file_name = os.path.basename(file_path) if not file_path.startswith('[') else file_path
            file_lbl = QLabel(f"{file_name}")
        else:
            file_lbl = QLabel("-")
        file_lbl.setStyleSheet("color: #888; font-size: 10px;")
        file_lbl.setWordWrap(True)
        layout.addWidget(file_lbl)
        
        layout.addStretch()


class TimeSlotWidget(QWidget):
    """
    时间段组件（最底层）
    显示一个时间段的详细信息
    """
    
    def __init__(self, start_time, end_time, duration, apps_used, records):
        super().__init__()
        self.is_expanded = False
        self.records = records
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 2, 2, 2)
        layout.setSpacing(2)
        
        # 头
        header = QPushButton()
        header.setCheckable(False)
        
        duration_str = format_duration(duration)
        apps_str = ', '.join(apps_used) if isinstance(apps_used, set) else apps_used
        header.setText(f"▶ {start_time} - {end_time}  ({duration_str})  -  {apps_str}")
        header.setStyleSheet("""
            QPushButton {
                background-color: #2A2A2A;
                color: #808080;
                font-size: 11px;
                padding: 4px 8px;
                border: 1px solid #3E3E3E;
                border-radius: 3px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #3E3E3E;
            }
        """)
        header.clicked.connect(self.show_details)
        layout.addWidget(header)
        
        # 记录数标签
        self.lbl_records = QLabel(f"📄 {len(records)} 条记录")
        self.lbl_records.setStyleSheet("color: #888; font-size: 10px; padding-left: 20px;")
        self.lbl_records.mousePressEvent = self.show_details
        layout.addWidget(self.lbl_records)
        
        # 详情（默认隐藏）
        self.detail_widget = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_widget)
        self.detail_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_layout.setSpacing(2)
        self.detail_widget.setVisible(False)
        layout.addWidget(self.detail_widget)
    
    def show_details(self, event=None):
        """展开查看详细记录"""
        if self.detail_widget.isVisible():
            self.detail_widget.setVisible(False)
        else:
            # 清空并重新添加
            for i in reversed(range(self.detail_layout.count())):
                widget = self.detail_layout.itemAt(i).widget()
                if widget:
                    widget.deleteLater()
            
            # 为每条记录创建组件
            for log in self.records:
                record_widget = RecordWidget(log)
                self.detail_layout.addWidget(record_widget)
            
            self.detail_widget.setVisible(True)


class ProjectTreeNodeWidget(QWidget):
    """
    项目树节点组件
    支持 3 层：祖父项目、父项目、子项目
    """
    
    def __init__(self, name, level, total_duration, time_range, children=None, time_slots=None, record_count=0):
        super().__init__()
        self.level = level  # 0, 1, 2
        self.is_expanded = True
        self.children = children or {}
        self.time_slots = time_slots or []
        self.record_count = record_count
        
        # 根据层级设置样式
        if level == 0:
            self.bg_color = "#2A2A2A"  # 深色背景
            self.font_size = 13
            self.icon = ""
            self.prefix = ""
        elif level == 1:
            self.bg_color = "#2F2F2F"
            self.font_size = 12
            self.icon = ""
            self.prefix = "  "
        else:
            self.bg_color = "#343434"
            self.font_size = 11
            self.icon = ""
            self.prefix = "    "
        
        # 创建 UI
        self.setup_ui(name, total_duration, time_range)
    
    def setup_ui(self, name, total_duration, time_range):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 2, 2)
        layout.setSpacing(2)
        
        # 头按钮（可点击展开/折叠）
        header = QPushButton()
        header.setCheckable(True)
        header.setChecked(True)
        
        # 格式化时长
        duration_str = format_duration(total_duration)
        
        # 根据是否有子节点或时间段决定图标
        has_children = len(self.children) > 0 or len(self.time_slots) > 0
        icon = "▼" if has_children else "•"
        
        header.setText(f"{self.prefix}{icon} {self.icon} {name}  |  {duration_str}  |  {time_range}")
        header.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.bg_color};
                color: #CCCCCC;
                font-size: {self.font_size}px;
                padding: 6px 8px;
                border: 1px solid #3E3E3E;
                border-radius: 3px;
                text-align: left;
                font-weight: {'bold' if self.level == 0 else 'normal'};
            }}
            QPushButton:hover {{
                background-color: #3E3E3E;
            }}
            QPushButton:checked {{
                background-color: {self.bg_color};
                border-bottom-left-radius: 0;
                border-bottom-right-radius: 0;
            }}
        """)
        
        header.clicked.connect(self.toggle_expand)
        layout.addWidget(header)
        
        # 子容器
        self.children_container = QWidget()
        self.children_layout = QVBoxLayout(self.children_container)
        self.children_layout.setContentsMargins(0, 0, 0, 0)
        self.children_layout.setSpacing(2)
        layout.addWidget(self.children_container)
        
        # 填充子节点或时间段
        self.populate_children()
    
    def populate_children(self):
        """填充子节点或时间段"""
        # 先添加子项目
        for child_name, child_data in self.children.items():
            if 'children' in child_data:
                # 还有下一层
                child_widget = ProjectTreeNodeWidget(
                    name=child_name,
                    level=self.level + 1,
                    total_duration=child_data['total_duration'],
                    time_range=child_data['time_range'],
                    children=child_data.get('children', {}),
                    time_slots=child_data.get('time_slots', []),
                    record_count=child_data.get('record_count', 0)
                )
                self.children_layout.addWidget(child_widget)
            else:
                # 最底层，添加时间段
                child_widget = ProjectTreeNodeWidget(
                    name=child_name,
                    level=self.level + 1,
                    total_duration=child_data['total_duration'],
                    time_range=child_data['time_range'],
                    time_slots=child_data.get('time_slots', []),
                    record_count=child_data.get('record_count', 0)
                )
                self.children_layout.addWidget(child_widget)
        
        # 添加时间段（如果是最底层）
        if not self.children and self.time_slots:
            for slot in self.time_slots:
                start_time = format_time(slot['start_sec'])
                end_time = format_time(slot['end_sec'])
                duration = slot['end_sec'] - slot['start_sec']
                apps = slot['apps']
                
                # 准备记录数据
                records = []
                for log in slot['logs']:
                    # 解析日志时间
                    from datetime import datetime as dt_module
                    try:
                        ts = dt_module.fromisoformat(log['timestamp'].split('.')[0])
                        log_start = format_time(ts.hour * 3600 + ts.minute * 60 + ts.second)
                        log_end = format_time(log_start.split(':')[0] * 3600 + log_start.split(':')[1] * 60 + log['duration'])
                    except:
                        log_start = "N/A"
                        log_end = "N/A"
                    
                    records.append({
                        'start_time': log_start,
                        'end_time': log_end,
                        'app_name': log['app_name'],
                        'file_path': log['file_path']
                    })
                
                slot_widget = TimeSlotWidget(start_time, end_time, duration, apps, records)
                self.children_layout.addWidget(slot_widget)
    
    def toggle_expand(self):
        self.is_expanded = not self.is_expanded
        self.children_container.setVisible(self.is_expanded)


# ============================================================================
# 主程序入口
# ============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QApplication.font()
    font.setPointSize(11)
    app.setFont(font)
    window = DashboardV2()
    window.show()
    sys.exit(app.exec())