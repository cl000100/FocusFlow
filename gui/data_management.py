#!/usr/bin/env python3
"""
数据管理对话框
提供归档数据查看和管理功能
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QGroupBox, QFormLayout, QListWidget, QListWidgetItem, QMessageBox,
    QProgressBar, QFrame
)
from PySide6.QtCore import Qt
from datetime import datetime

import sys
import os

# 确保能导入 core 模块
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.database import (
    get_main_table_stats, get_archive_history, archive_month,
    query_activity_log, table_exists, get_archive_table_name
)


class DataManagementDialog(QDialog):
    """数据管理对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("数据管理")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self.setup_ui()
        self.refresh_data()
    
    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 1. 主表统计
        main_group = QGroupBox("主表统计 (activity_log)")
        main_layout = QFormLayout()
        
        self.lbl_main_count = QLabel("-")
        self.lbl_main_oldest = QLabel("-")
        self.lbl_main_newest = QLabel("-")
        
        main_layout.addRow("记录总数:", self.lbl_main_count)
        main_layout.addRow("最早记录:", self.lbl_main_oldest)
        main_layout.addRow("最新记录:", self.lbl_main_newest)
        
        main_group.setLayout(main_layout)
        layout.addWidget(main_group)
        
        # 2. 归档历史
        archive_group = QGroupBox("归档历史")
        archive_layout = QVBoxLayout()
        
        self.list_archives = QListWidget()
        self.list_archives.setMinimumHeight(200)
        archive_layout.addWidget(self.list_archives)
        
        # 归档列表底部按钮
        btn_layout = QHBoxLayout()
        
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self.refresh_data)
        btn_layout.addWidget(self.btn_refresh)
        
        self.btn_view = QPushButton("查看数据")
        self.btn_view.clicked.connect(self.view_archive_data)
        btn_layout.addWidget(self.btn_view)
        
        btn_layout.addStretch()
        archive_layout.addLayout(btn_layout)
        
        archive_group.setLayout(archive_layout)
        layout.addWidget(archive_group)
        
        # 3. 手动归档
        manual_group = QGroupBox("手动归档")
        manual_layout = QVBoxLayout()
        
        self.lbl_manual_hint = QLabel("提示：主表保留最近 30 天的数据，旧数据会自动归档到月度表")
        self.lbl_manual_hint.setWordWrap(True)
        manual_layout.addWidget(self.lbl_manual_hint)
        
        btn_manual_layout = QHBoxLayout()
        
        self.btn_archive_now = QPushButton("立即归档上月数据")
        self.btn_archive_now.clicked.connect(self.manual_archive)
        btn_manual_layout.addWidget(self.btn_archive_now)
        
        btn_manual_layout.addStretch()
        manual_layout.addLayout(btn_manual_layout)
        
        manual_group.setLayout(manual_layout)
        layout.addWidget(manual_group)
        
        # 4. 底部按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(self.btn_close)
        
        layout.addLayout(bottom_layout)
        
        self.setLayout(layout)
    
    def refresh_data(self):
        """刷新数据显示"""
        # 1. 刷新主表统计
        stats = get_main_table_stats()
        self.lbl_main_count.setText(f"{stats['record_count']:,}")
        self.lbl_main_oldest.setText(stats['oldest_record'] or "-")
        self.lbl_main_newest.setText(stats['newest_record'] or "-")
        
        # 2. 刷新归档历史
        self.list_archives.clear()
        archives = get_archive_history()
        
        if archives:
            for archive in archives:
                table_name = archive['table_name']
                year_month = f"{archive['year']}-{archive['month']:02d}"
                count = archive['record_count']
                
                item_text = f"{table_name} - {year_month} - {count:,} 条记录"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, archive)
                self.list_archives.addItem(item)
        else:
            item = QListWidgetItem("暂无归档记录")
            item.setFlags(Qt.NoItemFlags)
            self.list_archives.addItem(item)
    
    def view_archive_data(self):
        """查看选中的归档数据"""
        current_item = self.list_archives.currentItem()
        if not current_item:
            QMessageBox.information(self, "提示", "请先选择一个归档表")
            return
        
        archive = current_item.data(Qt.UserRole)
        if not archive:
            return
        
        year = archive['year']
        month = archive['month']
        
        # 查询该月数据
        start = f"{year}-{month:02d}-01 00:00:00"
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1
        end = f"{next_year}-{next_month:02d}-01 00:00:00"
        
        data = query_activity_log(start, end)
        
        if data:
            QMessageBox.information(
                self, 
                "查询结果", 
                f"成功查询到 {len(data)} 条记录\n\n"
                f"时间范围：{start} 到 {end}\n\n"
                f"前 5 条记录:\n" + 
                "\n".join([f"  {i+1}. {record[0]} - {record[1]}" for i, record in enumerate(data[:5])])
            )
        else:
            QMessageBox.warning(self, "警告", "未查询到数据")
    
    def manual_archive(self):
        """手动归档"""
        # 计算上月
        today = datetime.now()
        if today.month == 1:
            last_year, last_month = today.year - 1, 12
        else:
            last_year, last_month = today.year, today.month - 1
        
        # 检查是否已归档
        archive_table = get_archive_table_name(last_year, last_month)
        if table_exists(archive_table):
            QMessageBox.information(
                self, 
                "提示", 
                f"{last_year}年{last_month}月 的数据已经归档"
            )
            return
        
        # 确认归档
        reply = QMessageBox.question(
            self,
            "确认归档",
            f"是否归档 {last_year}年{last_month}月 的数据？\n\n"
            f"归档后数据仍可正常查询，对用户透明。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                result = archive_month(last_year, last_month)
                QMessageBox.information(
                    self,
                    "归档成功",
                    f"成功归档 {result['archived_count']:,} 条记录\n归档表：{result['table_name']}"
                )
                self.refresh_data()
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "归档失败",
                    f"归档过程中发生错误：\n{str(e)}"
                )


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dialog = DataManagementDialog()
    dialog.show()
    sys.exit(app.exec())
