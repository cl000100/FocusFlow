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
    QInputDialog, QSpinBox, QFormLayout, QGroupBox, QCheckBox, QListWidget, QListWidgetItem,QFileDialog, QFrame
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont, QPainter, QColor, QPen, QBrush
from PySide6.QtCore import Qt, QModelIndex, QTimer, QItemSelectionModel

from core.database import get_connection, init_db, get_db_path, set_db_path
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

class DatabaseManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🗄️ 数据库管理")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("当前正在使用的数据库："))
        self.lbl_current_db = QLabel(get_db_path())
        self.lbl_current_db.setStyleSheet("color: #9CDCFE; font-weight: bold; word-break: break-all;")
        layout.addWidget(self.lbl_current_db)

        btn_layout = QHBoxLayout()
        btn_new = QPushButton("➕ 新建空数据库")
        btn_new.clicked.connect(self.create_new_db)
        btn_load = QPushButton("📂 载入已有数据库")
        btn_load.clicked.connect(self.load_existing_db)

        btn_layout.addWidget(btn_new)
        btn_layout.addWidget(btn_load)
        layout.addLayout(btn_layout)

    def create_new_db(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "新建数据库", "", "SQLite Database (*.db)")
        if file_path:
            if not file_path.endswith('.db'): file_path += '.db'
            set_db_path(file_path)
            init_db()  # 初始化新库的表结构
            QMessageBox.information(self, "成功", "已创建并切换到新数据库！\n后台进程将自动跟随切换。")
            self.accept()

    def load_existing_db(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "载入数据库", "", "SQLite Database (*.db)")
        if file_path:
            set_db_path(file_path)
            QMessageBox.information(self, "成功", "已切换到目标数据库！\n后台进程将自动跟随切换。")
            self.accept()

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
            event.accept()
    def mouseReleaseEvent(self, event):
        self._is_dragging = False
# ================= 数据可视化大屏 =================

class DataDashboardWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📊 生产力数据大屏 (本周洞察)")
        self.resize(1000, 600)  # 给图表足够的空间
        self.setMinimumSize(800, 500)
        
        # 强制 Matplotlib 使用 Mac 系统自带的中文字体（防止中文变成小方块）
        import platform
        if platform.system() == "Darwin":
            plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang SC', 'Heiti SC']
        elif platform.system() == "Windows":
            plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
        plt.rcParams['axes.unicode_minus'] = False # 正常显示负号
        
        # 采用深色酷炫主题
        plt.style.use('dark_background')
        
        self.setup_ui()
        self.load_and_draw_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 顶部标题栏
        header = QLabel("FocusFlow / 过去 7 天生产力洞察")
        header.setStyleSheet("color: #9CDCFE; font-size: 18px; font-weight: bold; padding: 10px;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # 图表容器（左右分栏）
        chart_layout = QHBoxLayout()
        
        # 创建两个独立的 Figure 画布
        self.fig_bar = Figure(figsize=(6, 4), dpi=100)
        self.canvas_bar = FigureCanvas(self.fig_bar)
        self.fig_pie = Figure(figsize=(4, 4), dpi=100)
        self.canvas_pie = FigureCanvas(self.fig_pie)
        
        chart_layout.addWidget(self.canvas_bar, stretch=3) # 柱状图占 3 份宽
        chart_layout.addWidget(self.canvas_pie, stretch=2) # 饼图占 2 份宽
        
        layout.addLayout(chart_layout)
        
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
        query_trend = """
            SELECT DATE(SUBSTR(timestamp, 1, 10)) as work_date, SUM(duration)/3600.0 as hours
            FROM activity_log
            WHERE DATE(SUBSTR(timestamp, 1, 10)) >= ?
            GROUP BY work_date
            ORDER BY work_date ASC
        """
        df_trend = pd.read_sql_query(query_trend, conn, params=(start_date,))
        
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
        query_pie = """
            SELECT p.project_name, SUM(al.duration) as total_secs
            FROM activity_log al
            JOIN file_assignment fa ON al.file_path = fa.file_path
            JOIN projects p ON fa.project_id = p.id
            WHERE DATE(SUBSTR(al.timestamp, 1, 10)) >= ?
            GROUP BY p.project_name
            ORDER BY total_secs DESC
        """
        df_pie = pd.read_sql_query(query_pie, conn, params=(start_date,))
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
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.last_mouse_x = event.position().x()
            self.setCursor(Qt.ClosedHandCursor) # 鼠标变成小抓手

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
                    if is_idle:
                        self.setToolTip(f"💤 闲置 / 休息\n{start_str} - {end_str}")
                    else:
                        d_path = fpath if fpath.startswith("[") else os.path.basename(fpath)
                        self.setToolTip(f"⏱️ {app}\n📄 {d_path}\n{start_str} - {end_str}")
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
        init_db()  
        self.setWindowTitle("FocusFlow - 专业工时看板")
        self.resize(1300, 800)
        
        # 完美状态记录容器
        self.expanded_uids = set()
        self.selected_uid_left = None
        self.selected_path_right = None

        self._current_track_path = None
        self._session_seconds = 0


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
        # 【新增】：数据大屏入口按钮
        self.btn_dashboard = QPushButton("📊 数据大屏")
        self.btn_dashboard.setStyleSheet("background-color: #31A8FF; color: white; font-weight: bold; padding: 4px 12px; border-radius: 4px; margin-left: 15px;")
        self.btn_dashboard.clicked.connect(lambda: DataDashboardWindow(self).exec())
        header_layout.addWidget(self.btn_dashboard)
        # 【新增】：呼出悬浮秒表
        self.floating_widget = FloatingWidget(self) # 实例化悬浮窗，藏在后台
        self.btn_float = QPushButton("📌 悬浮秒表")
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
        
        self.btn_blacklist = QPushButton("🚫 黑名单")
        self.btn_blacklist.clicked.connect(self.open_blacklist)
        self.btn_db = QPushButton("🗄️ 数据库")
        self.btn_db.clicked.connect(self.open_database_manager)
        
        # 【新增】：批量导出结算大单按钮
        self.btn_export_all = QPushButton("💰 导出全盘月度总结算单")
        self.btn_export_all.setStyleSheet("background-color: #2E8B57; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        self.btn_export_all.clicked.connect(self.action_export_all_bills)
        
        self.btn_settings = QPushButton("⚙ 设置")
        self.btn_settings.clicked.connect(self.open_settings)
        
        header_layout.addWidget(self.btn_export_all)
        header_layout.addWidget(self.btn_db)
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
        self.lbl_stat_p_name = QLabel("📊 项目: 未选中")
        self.lbl_stat_p_name.setStyleSheet(f"color: #D4D4D4; {font_name}")
        self.lbl_stat_p_times = QLabel("累积: 00:00:00    今日: 00:00:00")
        self.lbl_stat_p_times.setStyleSheet(f"color: #CCCCCC; {font_time}")
        
        # 第二行：程序
        self.lbl_stat_a_name = QLabel("🎯 程序: 无")
        self.lbl_stat_a_name.setStyleSheet(f"color: #68D391; {font_name}")
        self.lbl_stat_a_times = QLabel("累积: 00:00:00    今日: 00:00:00    本次连续: 00:00:00")
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
        self.tree_inbox.setSortingEnabled(True)         # 允许点击表头排序
        self.model_inbox.setSortRole(Qt.UserRole + 3)   # 告诉它按底层数字大小排，而不是按字符串排
# --- 5. 【新增】底部时间轴 ---
        self.timeline = TimelineWidget()
        main_layout.addWidget(self.timeline)
    def open_database_manager(self):
        if DatabaseManagerDialog(self).exec():
            # 切换数据库后，强制清空旧的展开状态，重新加载
            self.expanded_uids.clear()
            self.selected_uid_left = None
            self.selected_path_right = None
            self.refresh_data()

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
                row = conn.execute("""
                    SELECT COALESCE(SUM(duration), 0), 
                           COALESCE(SUM(CASE WHEN DATE(timestamp) = DATE('now', 'localtime') THEN duration ELSE 0 END), 0) 
                    FROM activity_log WHERE file_path = ?
                """, (fpath,)).fetchone()
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
            row_app = conn.execute("""
                SELECT COALESCE(SUM(duration), 0), 
                       COALESCE(SUM(CASE WHEN DATE(SUBSTR(timestamp, 1, 10)) = ? THEN duration ELSE 0 END), 0)
                FROM activity_log WHERE file_path = ?
            """, (datetime.now().strftime('%Y-%m-%d'), active_fpath)).fetchone()
            if row_app: a_total, a_today = row_app[0], row_app[1]

            # 项目时长
            target_pid = None
            if self.selected_uid_left and self.selected_uid_left.startswith("P_"):
                target_pid = int(self.selected_uid_left[2:])
            else:
                row_pid = conn.execute("SELECT project_id FROM file_assignment WHERE file_path = ?", (active_fpath,)).fetchone()
                if row_pid: target_pid = row_pid[0]
                
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
            self.lbl_status.setText(f"💤 闲置中 ({int(idle_seconds)} 秒)")
            self.lbl_status.setStyleSheet("color: #FF9F0A; font-weight: bold; font-size: 13px;")
            
            self.lbl_stat_p_name.setText("📊 项目: 休息中")
            self.lbl_stat_p_times.setText("累积: --:--:--    今日: --:--:--")
            self.lbl_stat_a_name.setText("🎯 程序: 离开座位")
            self.lbl_stat_a_times.setText("累积: --:--:--    今日: --:--:--    本次: --:--:--")
        else:
            self.lbl_status.setText(f"🟢 正在追踪: {app_name} | {d_path}")
            self.lbl_status.setStyleSheet("color: #34C759; font-weight: bold; font-size: 13px;")
            
            self.lbl_stat_p_name.setText(f"📊 项目: {p_name}")
            self.lbl_stat_p_times.setText(f"累积: {fmt_full(p_total)}    今日: {fmt_full(p_today)}")
            self.lbl_stat_a_name.setText(f"🎯 程序: {d_path}")
            self.lbl_stat_a_times.setText(f"累积: {fmt_full(a_total)}    今日: {fmt_full(a_today)}    本次: {fmt_full(self._session_seconds)}")

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
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        # 1. 查出今天的真实工作记录
        # 1. 查出今天的真实工作记录
        # 【修复2】：去掉 'localtime' 修饰符，因为存入数据库的 datetime.now().isoformat() 本身就已经是本地时间了！
        # 如果再次加 'localtime' 会导致 SQLite 进行二次时区转换，从而把昨天半夜 23 点错认为今天。
        logs = conn.execute("""
            SELECT timestamp, duration, app_name, file_path 
            FROM activity_log 
            WHERE DATE(SUBSTR(timestamp, 1, 10)) = ?
            ORDER BY timestamp ASC
        """, (today_str,)).fetchall()
        
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
            
        self.timeline.update_data(blocks)
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
                
                # 【修正】：统一使用 row_idx
                it_total = self.model_inbox.item(row_idx, 2)
                it_total.setText(format_duration(total))
                it_total.setData(total, Qt.UserRole + 3)

                it_today = self.model_inbox.item(row_idx, 3)
                it_today.setText(format_duration(today))
                it_today.setData(today, Qt.UserRole + 3)

                it_last = self.model_inbox.item(row_idx, 4)
                it_last.setText(time_str)
                it_last.setData(last_seen, Qt.UserRole + 3)
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
                # 【新增】：给第 1 列埋入用于排序的纯文本（小写，保证字母表顺序准确）
                item_name.setData(d_name.lower(), Qt.UserRole + 3)
                item_name.setToolTip(file_path)
                
                item_dir = QStandardItem(d_dir)
                # 【新增】：给第 2 列埋入用于排序的纯文本
                item_dir.setData(d_dir.lower(), Qt.UserRole + 3)
                item_dir.setToolTip(file_path)
                
                # 【新增】：给单元格底部埋入真实秒数/时间戳，用于数学排序
                item_total = QStandardItem(format_duration(total))
                item_total.setData(total, Qt.UserRole + 3)
                
                item_today = QStandardItem(format_duration(today))
                item_today.setData(today, Qt.UserRole + 3)
                
                item_last = QStandardItem(time_str)
                item_last.setData(last_seen, Qt.UserRole + 3)
                
                self.model_inbox.appendRow([item_name, item_dir, item_total, item_today, item_last])

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
            name_pure = item_node.text().replace("📁 ", "").replace("📦 [归档] ", "")
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
            
            query = f"""
                SELECT 
                    DATE(al.timestamp, 'localtime') as work_date,
                    fa.project_id,
                    al.app_name,
                    al.file_path,
                    al.duration
                FROM activity_log al
                JOIN file_assignment fa ON al.file_path = fa.file_path
                WHERE fa.project_id IN ({placeholders})
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
                    
                    query = f"""
                        SELECT DATE(al.timestamp, 'localtime') as work_date, fa.project_id, al.app_name, al.file_path, al.duration
                        FROM activity_log al JOIN file_assignment fa ON al.file_path = fa.file_path
                        WHERE fa.project_id IN ({placeholders})
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