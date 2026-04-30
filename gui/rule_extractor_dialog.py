import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem, QComboBox, QCheckBox, QGroupBox, QMessageBox, QInputDialog
from PySide6.QtCore import Qt
from core.database import get_connection
from datetime import datetime


class RuleExtractorDialog(QDialog):
    """智能提取规则对话框 - 分析选中文件的路径特征，生成 project_map 规则"""

    def __init__(self, selected_files, parent=None):
        super().__init__(parent)
        self.selected_files = selected_files
        self.setWindowTitle("智能提取规则")
        self.setMinimumSize(600, 450)
        self.setup_ui()
        self.analyze_files()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 说明
        info = QLabel(f"已选 {len(self.selected_files)} 个文件，系统将分析路径和应用特征，生成规则候选。")
        info.setStyleSheet("color: #888; padding: 5px;")
        layout.addWidget(info)

        # 规则候选列表
        rule_group = QGroupBox("检测到的规则候选（勾选要生成的规则）")
        rule_layout = QVBoxLayout()
        self.rule_list = QListWidget()
        self.rule_list.setMinimumHeight(200)
        rule_layout.addWidget(self.rule_list)
        rule_group.setLayout(rule_layout)
        layout.addWidget(rule_group)

        # 目标项目选择
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("分配到项目:"))
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(200)
        self.load_projects()
        target_layout.addWidget(self.project_combo)
        btn_new_project = QPushButton("➕ 新建项目")
        btn_new_project.clicked.connect(self.create_new_project)
        target_layout.addWidget(btn_new_project)
        target_layout.addStretch()
        layout.addLayout(target_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        self.btn_generate = QPushButton("生成规则")
        self.btn_generate.clicked.connect(self.generate_rules)
        self.btn_generate.setEnabled(False)
        btn_layout.addWidget(self.btn_generate)
        layout.addLayout(btn_layout)

    def load_projects(self):
        from core.database import get_connection
        from core.project_tree import load_project_tree

        self.project_combo.clear()
        seen = set()

        # 使用父窗口的"显示归档"复选框状态，默认显示已归档项目
        parent_dashboard = self.parent()
        show_archived = parent_dashboard.chk_archived.isChecked() if parent_dashboard and hasattr(parent_dashboard, 'chk_archived') else True

        tree = load_project_tree()
        for node in tree.get_all_nodes(include_archived=True):
            if node.is_archived and not show_archived:
                continue
            prefix = "[归档] " if node.is_archived else ""
            display_name = prefix + node.name
            if display_name not in seen:
                self.project_combo.addItem(display_name, node.id)
                seen.add(display_name)

    def create_new_project(self):
        """创建新项目"""
        text, ok = QInputDialog.getText(self, "新建项目", "输入项目名称:")
        if ok and text.strip():
            conn = get_connection()
            try:
                cursor = conn.execute(
                    "INSERT INTO projects (project_name, created_at) VALUES (?, ?)",
                    (text.strip(), datetime.now().isoformat())
                )
                new_id = cursor.lastrowid
                conn.commit()
                self.project_combo.addItem(text.strip(), new_id)
                self.project_combo.setCurrentIndex(self.project_combo.count() - 1)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"创建项目失败: {e}")
            finally:
                conn.close()

    def analyze_files(self):
        """分析选中文件，提取规则候选"""
        self.rule_list.clear()
        self.candidates = []

        # 1. 提取路径规则 - 找共同父目录
        file_paths = [f['file_path'] for f in self.selected_files]
        common_prefix = self.find_common_prefix(file_paths)

        if common_prefix and len(common_prefix) > 5:
            # 检查是否所有文件都在这个路径下
            matching = sum(1 for fp in file_paths if fp.startswith(common_prefix))
            if matching >= 1:
                item = QListWidgetItem(f"📁 路径规则: {common_prefix}")
                item.setCheckState(Qt.Unchecked)
                item.setData(Qt.UserRole, ('path', common_prefix))
                self.rule_list.addItem(item)
                self.candidates.append({'type': 'path', 'pattern': common_prefix, 'count': matching})

        # 2. 按 app_name 分组
        app_groups = {}
        for f in self.selected_files:
            app = f.get('app_name', '') or 'Unknown'
            if app not in app_groups:
                app_groups[app] = []
            app_groups[app].append(f)

        for app, files in app_groups.items():
            if len(files) >= 1 and app != 'Unknown':
                item = QListWidgetItem(f"📱 应用规则: {app} (匹配 {len(files)} 个)")
                item.setCheckState(Qt.Unchecked)
                item.setData(Qt.UserRole, ('app', app))
                self.rule_list.addItem(item)
                self.candidates.append({'type': 'app', 'pattern': app, 'count': len(files)})

        # 3. 提取文件名关键词
        filenames = [os.path.basename(fp) for fp in file_paths]
        keywords = self.extract_common_keywords(filenames)
        for kw in keywords:
            if len(kw) >= 3:
                matching = sum(1 for fn in filenames if kw.lower() in fn.lower())
                if matching >= 2:
                    item = QListWidgetItem(f"🏷️ 关键词: {kw} (匹配 {matching} 个)")
                    item.setCheckState(Qt.Unchecked)
                    item.setData(Qt.UserRole, ('keyword', kw))
                    self.rule_list.addItem(item)
                    self.candidates.append({'type': 'keyword', 'pattern': kw, 'count': matching})

        self.rule_list.itemChanged.connect(self.on_item_checked)

    def find_common_prefix(self, paths):
        """找多个路径的共同前缀"""
        if not paths:
            return ""
        common = os.path.commonpath(paths) if len(paths) > 1 else os.path.dirname(paths[0])
        return common.rstrip('/')

    def extract_common_keywords(self, filenames):
        """从文件名中提取共同关键词"""
        import re
        # 去掉扩展名
        names = [re.sub(r'\.[^.]+$', '', fn) for fn in filenames]
        # 去掉日期和序号
        names = [re.sub(r'\d{4,}[-_]\d{2,}[-_]\d{2,}[-_]?', '', n) for n in names]
        names = [re.sub(r'\d{2,}[-_]?', '', n) for n in names]

        # 找所有单词
        words = set()
        for n in names:
            parts = re.split(r'[-_ ]+', n)
            words.update([p.lower() for p in parts if len(p) >= 3])

        # 统计词频
        word_count = {}
        for n in names:
            n_lower = n.lower()
            for w in words:
                if w in n_lower:
                    word_count[w] = word_count.get(w, 0) + 1

        # 返回出现次数多的词
        sorted_words = sorted(word_count.items(), key=lambda x: -x[1])
        return [w for w, c in sorted_words[:5] if c >= 2]

    def on_item_checked(self, item):
        """检查是否有勾选的项目"""
        has_checked = any(
            self.rule_list.item(i).checkState() == Qt.Checked
            for i in range(self.rule_list.count())
        )
        self.btn_generate.setEnabled(has_checked)

    def generate_rules(self):
        """生成选中的规则"""
        project_id = self.project_combo.currentData()
        project_name = self.project_combo.currentText()

        if not project_id:
            QMessageBox.warning(self, "提示", "请先选择目标项目")
            return

        conn = get_connection()
        rules_added = 0

        for i in range(self.rule_list.count()):
            item = self.rule_list.item(i)
            if item.checkState() == Qt.Checked:
                rule_type, pattern = item.data(Qt.UserRole)
                # 写入 project_map
                conn.execute("""
                    INSERT INTO project_map (project_id, project_name, rule_path)
                    VALUES (?, ?, ?)
                """, (project_id, project_name, pattern))
                rules_added += 1

        conn.commit()
        conn.close()

        QMessageBox.information(self, "完成", f"已生成 {rules_added} 条规则，规则将自动匹配文件。")
        self.accept()