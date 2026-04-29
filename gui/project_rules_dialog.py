from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel, QTabWidget, QWidget, QInputDialog, QAbstractItemView
from PySide6.QtCore import Qt
from core.database import get_connection


class ProjectRulesDialog(QDialog):
    """项目规则管理对话框 - 查看和管理项目的自动规则和手动分配"""

    def __init__(self, project_id, project_name, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.project_name = project_name
        self.setWindowTitle(f"管理项目 - {project_name}")
        self.setMinimumSize(700, 500)
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Tab 切换
        self.tabs = QTabWidget()

        # Tab 1: 自动匹配规则
        tab_rules = QWidget()
        tab_rules_layout = QVBoxLayout(tab_rules)

        hint = QLabel("当路径/窗口名包含以下关键词时，自动分配到本项目：")
        hint.setStyleSheet("color: #888;")
        tab_rules_layout.addWidget(hint)

        self.rules_list = QListWidget()
        tab_rules_layout.addWidget(self.rules_list)

        rules_btn_layout = QHBoxLayout()
        btn_add_rule = QPushButton("➕ 添加规则")
        btn_add_rule.clicked.connect(self.add_rule)
        btn_remove_rule = QPushButton("❌ 删除规则")
        btn_remove_rule.clicked.connect(self.remove_rule)
        rules_btn_layout.addWidget(btn_add_rule)
        rules_btn_layout.addWidget(btn_remove_rule)
        rules_btn_layout.addStretch()
        tab_rules_layout.addLayout(rules_btn_layout)

        self.tabs.addTab(tab_rules, "🤖 自动匹配规则")

        # Tab 2: 手动分配的文件
        tab_manual = QWidget()
        tab_manual_layout = QVBoxLayout(tab_manual)

        hint2 = QLabel("通过 Inbox 手动分配到本项目的文件：")
        hint2.setStyleSheet("color: #888;")
        tab_manual_layout.addWidget(hint2)

        self.manual_list = QListWidget()
        self.manual_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        tab_manual_layout.addWidget(self.manual_list)

        manual_btn_layout = QHBoxLayout()
        btn_remove_manual = QPushButton("❌ 从项目中移除（移回 Inbox）")
        btn_remove_manual.clicked.connect(self.remove_manual_assignment)
        manual_btn_layout.addWidget(btn_remove_manual)
        manual_btn_layout.addStretch()
        tab_manual_layout.addLayout(manual_btn_layout)

        self.tabs.addTab(tab_manual, "📁 手动分配文件")

        # Tab 3: 该项目的所有文件（含自动+手动）
        tab_all = QWidget()
        tab_all_layout = QVBoxLayout(tab_all)

        self.all_list = QListWidget()
        tab_all_layout.addWidget(self.all_list)

        self.tabs.addTab(tab_all, "📋 全部文件")

        layout.addWidget(self.tabs)

        # 关闭按钮
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def load_data(self):
        # 加载自动规则
        self.rules_list.clear()
        conn = get_connection()
        for row in conn.execute("SELECT id, rule_path FROM project_map WHERE project_id = ?", (self.project_id,)):
            item = QListWidgetItem(row[1])
            item.setData(Qt.UserRole, row[0])
            self.rules_list.addItem(item)
        conn.close()

        # 加载手动分配的文件（排除规则自动分配的）
        self.manual_list.clear()
        conn = get_connection()
        for row in conn.execute("""
            SELECT fa.id, fa.file_path, fa.assigned_at
            FROM file_assignment fa
            WHERE fa.project_id = ? AND fa.source_rule_id IS NULL
            ORDER BY fa.assigned_at DESC
        """, (self.project_id,)):
            item = QListWidgetItem(row[1])
            item.setData(Qt.UserRole, row[0])
            self.manual_list.addItem(item)
        conn.close()

        # 加载全部文件（通过 project_map 规则匹配 + 手动分配）
        self.all_list.clear()
        conn = get_connection()

        # 手动分配的文件（source_rule_id 为 NULL）
        manual_files = set()
        for row in conn.execute("SELECT file_path FROM file_assignment WHERE project_id = ? AND source_rule_id IS NULL", (self.project_id,)):
            manual_files.add(row[0])
            item = QListWidgetItem(f"[手动] {row[0]}")
            item.setData(Qt.UserRole, row[0])
            self.all_list.addItem(item)

        # 规则自动分配的文件（source_rule_id 有值）
        rule_files = set()
        for row in conn.execute("SELECT file_path, source_rule_id FROM file_assignment WHERE project_id = ? AND source_rule_id IS NOT NULL", (self.project_id,)):
            rule_files.add(row[0])
            # 获取规则名称用于显示
            rule_row = conn.execute("SELECT rule_path FROM project_map WHERE id = ?", (row[1],)).fetchone()
            rule_name = rule_row[0] if rule_row else "未知规则"
            item = QListWidgetItem(f"[规则:{rule_name}] {row[0]}")
            item.setData(Qt.UserRole, row[0])
            self.all_list.addItem(item)

        # 通过规则匹配的文件（来自 activity_log，但尚未在 file_assignment 中）
        for row in conn.execute("SELECT rule_path FROM project_map WHERE project_id = ? AND rule_path IS NOT NULL", (self.project_id,)):
            rule = row[0]
            if not rule:
                continue
            # 从 activity_log 找匹配的文件（大小写不敏感）
            for al_row in conn.execute("""
                SELECT DISTINCT file_path, MAX(timestamp) as last_seen
                FROM activity_log
                WHERE file_path LIKE ? COLLATE NOCASE AND file_path NOT IN (SELECT file_path FROM file_assignment WHERE project_id = ?)
                GROUP BY file_path
                ORDER BY last_seen DESC
                LIMIT 50
            """, (f"%{rule}%", self.project_id)):
                if al_row[0] not in manual_files and al_row[0] not in rule_files:
                    item = QListWidgetItem(f"[待匹配] {al_row[0]}")
                    item.setData(Qt.UserRole, al_row[0])
                    self.all_list.addItem(item)

        conn.close()

    def add_rule(self):
        text, ok = QInputDialog.getText(self, "添加规则", "输入路径/标题匹配关键词：")
        if ok and text.strip():
            conn = get_connection()
            conn.execute(
                "INSERT INTO project_map (project_id, project_name, rule_path) VALUES (?, ?, ?)",
                (self.project_id, self.project_name, text.strip())
            )
            conn.commit()
            conn.close()
            self.load_data()

    def remove_rule(self):
        selected = self.rules_list.currentItem()
        if selected:
            rule_id = selected.data(Qt.UserRole)
            conn = get_connection()
            # 删除该规则对应的 file_assignment 记录（source_rule_id 关联的）
            conn.execute("DELETE FROM file_assignment WHERE source_rule_id = ?", (rule_id,))
            # 删除规则本身
            conn.execute("DELETE FROM project_map WHERE id = ?", (rule_id,))
            conn.commit()
            conn.close()
            self.load_data()

    def remove_manual_assignment(self):
        """从项目中移除文件（删除 file_assignment 记录，文件回到 Inbox）"""
        selected_items = self.manual_list.selectedItems()
        if selected_items:
            conn = get_connection()
            for item in selected_items:
                conn.execute("DELETE FROM file_assignment WHERE id = ?", (item.data(Qt.UserRole),))
            conn.commit()
            conn.close()
            self.load_data()