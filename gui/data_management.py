#!/usr/bin/env python3
"""
数据管理对话框 - 完整版
提供数据清理、导出、备份/恢复功能
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QGroupBox, QFormLayout, QListWidget, QListWidgetItem, QMessageBox,
    QProgressBar, QFrame, QTabWidget, QWidget, QDateEdit, QComboBox,
    QFileDialog, QSpinBox, QCheckBox
)
from PySide6.QtCore import Qt, QDate
from datetime import datetime, timedelta

import sys
import os

# 确保能导入 core 模块
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.database import (
    get_main_table_stats, get_archive_history, archive_month,
    query_activity_log, table_exists, get_archive_table_name,
    delete_data_by_range, delete_data_by_app, delete_data_by_file,
    delete_archive_table, vacuum_database, get_storage_stats,
    backup_database, restore_database, list_backups, get_connection
)
from core.export import export_to_csv, export_to_excel, export_summary_report


class DataManagementDialog(QDialog):
    """数据管理对话框 - 完整版"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("数据管理")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        
        self.setup_ui()
        self.refresh_data()
    
    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 创建选项卡
        self.tabs = QTabWidget()
        
        # 选项卡 1：概览
        self.tab_overview = self.create_overview_tab()
        self.tabs.addTab(self.tab_overview, "概览")
        
        # 选项卡 2：数据清理
        self.tab_cleanup = self.create_cleanup_tab()
        self.tabs.addTab(self.tab_cleanup, "数据清理")
        
        # 选项卡 3：数据导出
        self.tab_export = self.create_export_tab()
        self.tabs.addTab(self.tab_export, "数据导出")
        
        # 选项卡 4：备份/恢复
        self.tab_backup = self.create_backup_tab()
        self.tabs.addTab(self.tab_backup, "备份/恢复")
        
        layout.addWidget(self.tabs)
        
        # 底部按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(self.btn_close)
        
        layout.addLayout(bottom_layout)
        
        self.setLayout(layout)
    
    def create_overview_tab(self):
        """创建概览选项卡"""
        widget = QWidget()
        layout = QVBoxLayout()
        
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
        
        # 2. 存储空间
        storage_group = QGroupBox("存储空间")
        storage_layout = QFormLayout()
        
        self.lbl_storage_total = QLabel("-")
        self.lbl_storage_main = QLabel("-")
        self.lbl_storage_archive = QLabel("-")
        self.lbl_archive_count = QLabel("-")
        
        storage_layout.addRow("数据库总大小:", self.lbl_storage_total)
        storage_layout.addRow("主表大小:", self.lbl_storage_main)
        storage_layout.addRow("归档表总大小:", self.lbl_storage_archive)
        storage_layout.addRow("归档表数量:", self.lbl_archive_count)
        
        storage_group.setLayout(storage_layout)
        layout.addWidget(storage_group)
        
        # 3. 归档历史
        archive_group = QGroupBox("归档历史")
        archive_layout = QVBoxLayout()
        
        self.list_archives = QListWidget()
        self.list_archives.setMinimumHeight(150)
        archive_layout.addWidget(self.list_archives)
        
        # 归档列表底部按钮
        btn_layout = QHBoxLayout()
        
        self.btn_refresh_overview = QPushButton("刷新")
        self.btn_refresh_overview.clicked.connect(self.refresh_data)
        btn_layout.addWidget(self.btn_refresh_overview)
        
        self.btn_view_archive = QPushButton("查看数据")
        self.btn_view_archive.clicked.connect(self.view_archive_data)
        btn_layout.addWidget(self.btn_view_archive)
        
        btn_layout.addStretch()
        archive_layout.addLayout(btn_layout)
        
        archive_group.setLayout(archive_layout)
        layout.addWidget(archive_group)
        
        widget.setLayout(layout)
        return widget
    
    def create_cleanup_tab(self):
        """创建数据清理选项卡"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 1. 按时间范围删除
        range_group = QGroupBox("按时间范围删除")
        range_layout = QFormLayout()
        
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addMonths(-1))
        self.date_start.setDisplayFormat("yyyy-MM-dd")
        
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        self.date_end.setDisplayFormat("yyyy-MM-dd")
        
        range_layout.addRow("开始日期:", self.date_start)
        range_layout.addRow("结束日期:", self.date_end)
        
        self.btn_delete_range = QPushButton("删除选定范围的数据")
        self.btn_delete_range.clicked.connect(self.delete_by_range)
        range_layout.addRow(self.btn_delete_range)
        
        range_group.setLayout(range_layout)
        layout.addWidget(range_group)
        
        # 2. 按应用删除
        app_group = QGroupBox("按应用删除")
        app_layout = QVBoxLayout()
        
        app_hint = QLabel("提示：输入应用名称，删除该应用的所有记录")
        app_hint.setWordWrap(True)
        app_layout.addWidget(app_hint)
        
        self.combo_apps = QComboBox()
        self.combo_apps.setEditable(True)
        self.combo_apps.setMinimumWidth(300)
        app_layout.addWidget(self.combo_apps)
        
        self.btn_delete_app = QPushButton("删除该应用的所有记录")
        self.btn_delete_app.clicked.connect(self.delete_by_app)
        app_layout.addWidget(self.btn_delete_app)
        
        app_group.setLayout(app_layout)
        layout.addWidget(app_group)
        
        # 3. 删除归档表
        archive_del_group = QGroupBox("删除归档表")
        archive_del_layout = QVBoxLayout()
        
        archive_hint = QLabel("选择一个归档表并删除（此操作不可恢复）")
        archive_hint.setWordWrap(True)
        archive_del_layout.addWidget(archive_hint)
        
        self.list_archives_delete = QListWidget()
        self.list_archives_delete.setMinimumHeight(100)
        archive_del_layout.addWidget(self.list_archives_delete)
        
        self.btn_delete_archive = QPushButton("删除选中的归档表")
        self.btn_delete_archive.clicked.connect(self.delete_archive)
        archive_del_layout.addWidget(self.btn_delete_archive)
        
        archive_del_group.setLayout(archive_del_layout)
        layout.addWidget(archive_del_group)
        
        # 4. 回收空间
        vacuum_group = QGroupBox("回收数据库空间")
        vacuum_layout = QVBoxLayout()
        
        vacuum_hint = QLabel("在大量删除数据后，执行此操作可以减小数据库文件大小")
        vacuum_hint.setWordWrap(True)
        vacuum_layout.addWidget(vacuum_hint)
        
        self.btn_vacuum = QPushButton("立即回收空间")
        self.btn_vacuum.clicked.connect(self.vacuum_db)
        vacuum_layout.addWidget(self.btn_vacuum)
        
        vacuum_group.setLayout(vacuum_layout)
        layout.addWidget(vacuum_group)
        
        widget.setLayout(layout)
        return widget
    
    def create_export_tab(self):
        """创建数据导出选项卡"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 1. 时间范围
        range_group = QGroupBox("导出时间范围")
        range_layout = QFormLayout()
        
        self.export_start = QDateEdit()
        self.export_start.setCalendarPopup(True)
        self.export_start.setDate(QDate.currentDate().addMonths(-1))
        self.export_start.setDisplayFormat("yyyy-MM-dd")
        
        self.export_end = QDateEdit()
        self.export_end.setCalendarPopup(True)
        self.export_end.setDate(QDate.currentDate())
        self.export_end.setDisplayFormat("yyyy-MM-dd")
        
        range_layout.addRow("开始日期:", self.export_start)
        range_layout.addRow("结束日期:", self.export_end)
        
        range_group.setLayout(range_layout)
        layout.addWidget(range_group)
        
        # 2. 导出格式
        format_group = QGroupBox("导出格式")
        format_layout = QVBoxLayout()
        
        self.export_csv = QCheckBox("CSV 格式（适合导入 Excel）")
        self.export_csv.setChecked(True)
        format_layout.addWidget(self.export_csv)
        
        self.export_excel = QCheckBox("Excel 格式（带统计报表）")
        format_layout.addWidget(self.export_excel)
        
        self.export_txt = QCheckBox("文本报告（简要统计）")
        format_layout.addWidget(self.export_txt)
        
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        # 3. 导出按钮
        self.btn_export = QPushButton("导出数据")
        self.btn_export.clicked.connect(self.export_data)
        layout.addWidget(self.btn_export)
        
        widget.setLayout(layout)
        return widget
    
    def create_backup_tab(self):
        """创建备份/恢复选项卡"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 1. 备份
        backup_group = QGroupBox("备份数据库")
        backup_layout = QVBoxLayout()
        
        backup_hint = QLabel("创建数据库的完整备份，建议定期执行")
        backup_hint.setWordWrap(True)
        backup_layout.addWidget(backup_hint)
        
        self.btn_backup = QPushButton("立即备份")
        self.btn_backup.clicked.connect(self.do_backup)
        backup_layout.addWidget(self.btn_backup)
        
        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)
        
        # 2. 恢复
        restore_group = QGroupBox("恢复数据库")
        restore_layout = QVBoxLayout()
        
        restore_hint = QLabel("从备份文件恢复数据库（此操作会覆盖当前数据）")
        restore_hint.setWordWrap(True)
        restore_layout.addWidget(restore_hint)
        
        self.list_backups = QListWidget()
        self.list_backups.setMinimumHeight(100)
        restore_layout.addWidget(self.list_backups)
        
        btn_layout = QHBoxLayout()
        
        self.btn_refresh_backups = QPushButton("刷新备份列表")
        self.btn_refresh_backups.clicked.connect(self.refresh_backups)
        btn_layout.addWidget(self.btn_refresh_backups)
        
        self.btn_restore = QPushButton("恢复选中的备份")
        self.btn_restore.clicked.connect(self.do_restore)
        btn_layout.addWidget(self.btn_restore)
        
        btn_layout.addStretch()
        restore_layout.addLayout(btn_layout)
        
        restore_group.setLayout(restore_layout)
        layout.addWidget(restore_group)
        
        widget.setLayout(layout)
        return widget
    
    def refresh_data(self):
        """刷新所有数据"""
        # 1. 刷新主表统计
        stats = get_main_table_stats()
        self.lbl_main_count.setText(f"{stats['record_count']:,}")
        self.lbl_main_oldest.setText(stats['oldest_record'] or "-")
        self.lbl_main_newest.setText(stats['newest_record'] or "-")
        
        # 2. 刷新存储空间
        storage = get_storage_stats()
        self.lbl_storage_total.setText(f"{storage['total_size']/1024/1024:.2f} MB")
        self.lbl_storage_main.setText(f"{storage['main_table_size']/1024/1024:.2f} MB")
        self.lbl_storage_archive.setText(f"{storage['archive_tables_size']/1024/1024:.2f} MB")
        self.lbl_archive_count.setText(f"{storage['archive_count']}")
        
        # 3. 刷新归档历史
        self.list_archives.clear()
        self.list_archives_delete.clear()
        archives = get_archive_history()
        
        if archives:
            for archive in archives:
                table_name = archive['table_name']
                year_month = f"{archive['year']}-{archive['month']:02d}"
                count = f"{archive['record_count']:,}"
                
                item_text = f"{table_name} - {year_month} - {count} 条记录"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, archive)
                self.list_archives.addItem(item)
                
                item2 = QListWidgetItem(item_text)
                item2.setData(Qt.UserRole, archive)
                self.list_archives_delete.addItem(item2)
        else:
            item = QListWidgetItem("暂无归档记录")
            item.setFlags(Qt.NoItemFlags)
            self.list_archives.addItem(item)
        
        # 4. 刷新应用列表
        self.refresh_app_list()
        
        # 5. 刷新备份列表
        self.refresh_backups()
    
    def refresh_app_list(self):
        """刷新应用列表"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT app_name FROM activity_log
            ORDER BY app_name
        """)
        apps = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        self.combo_apps.clear()
        self.combo_apps.addItems(apps)
    
    def refresh_backups(self):
        """刷新备份列表"""
        self.list_backups.clear()
        backups = list_backups()
        
        if backups:
            for backup in backups:
                date_str = backup['date']
                size_mb = backup['size'] / 1024 / 1024
                item_text = f"{date_str} - {size_mb:.2f} MB"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, backup['path'])
                self.list_backups.addItem(item)
        else:
            item = QListWidgetItem("暂无备份文件")
            item.setFlags(Qt.NoItemFlags)
            self.list_backups.addItem(item)
    
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
    
    def delete_by_range(self):
        """按时间范围删除"""
        start_date = self.date_start.date().toString("yyyy-MM-dd") + " 00:00:00"
        end_date = self.date_end.date().toString("yyyy-MM-dd") + " 23:59:59"
        
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除 {start_date[:10]} 至 {end_date[:10]} 的数据吗？\n\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            result = delete_data_by_range(start_date, end_date)
            QMessageBox.information(
                self, "删除完成",
                f"成功删除 {result['deleted_count']} 条记录\n影响的表：{', '.join(result['affected_tables'])}"
            )
            self.refresh_data()
    
    def delete_by_app(self):
        """按应用删除"""
        app_name = self.combo_apps.currentText()
        if not app_name:
            QMessageBox.warning(self, "警告", "请输入应用名称")
            return
        
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除应用 '{app_name}' 的所有记录吗？\n\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            result = delete_data_by_app(app_name)
            QMessageBox.information(
                self, "删除完成",
                f"成功删除 {result['deleted_count']} 条记录"
            )
            self.refresh_data()
    
    def delete_archive(self):
        """删除归档表"""
        current_item = self.list_archives_delete.currentItem()
        if not current_item:
            QMessageBox.information(self, "提示", "请先选择一个归档表")
            return
        
        archive = current_item.data(Qt.UserRole)
        if not archive:
            return
        
        table_name = archive['table_name']
        record_count = archive['record_count']
        
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除归档表 {table_name} 吗？\n\n将删除 {record_count} 条记录，此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            result = delete_archive_table(table_name)
            if result['success']:
                QMessageBox.information(
                    self, "删除完成",
                    f"成功删除归档表 {table_name}\n共 {result['record_count']} 条记录"
                )
                self.refresh_data()
            else:
                QMessageBox.critical(self, "删除失败", result.get('error', '未知错误'))
    
    def vacuum_db(self):
        """回收数据库空间"""
        reply = QMessageBox.question(
            self, "确认回收",
            "回收数据库空间可能需要一些时间，确定要继续吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success = vacuum_database()
            if success:
                QMessageBox.information(self, "完成", "数据库空间回收完成")
                self.refresh_data()
            else:
                QMessageBox.critical(self, "失败", "数据库空间回收失败")
    
    def export_data(self):
        """导出数据"""
        start_date = self.export_start.date().toString("yyyy-MM-dd") + " 00:00:00"
        end_date = self.export_end.date().toString("yyyy-MM-dd") + " 23:59:59"
        
        # 选择保存目录
        save_dir = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if not save_dir:
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        success_count = 0
        
        # CSV 导出
        if self.export_csv.isChecked():
            csv_path = os.path.join(save_dir, f"focusflow_export_{timestamp}.csv")
            result = export_to_csv(start_date, end_date, csv_path)
            if result['success']:
                success_count += 1
        
        # Excel 导出
        if self.export_excel.isChecked():
            excel_path = os.path.join(save_dir, f"focusflow_report_{timestamp}.xlsx")
            result = export_to_excel(start_date, end_date, excel_path)
            if result['success']:
                success_count += 1
        
        # 文本报告
        if self.export_txt.isChecked():
            txt_path = os.path.join(save_dir, f"focusflow_summary_{timestamp}.txt")
            result = export_summary_report(start_date, end_date, txt_path)
            if result['success']:
                success_count += 1
        
        if success_count > 0:
            QMessageBox.information(
                self, "导出完成",
                f"成功导出 {success_count} 个文件到:\n{save_dir}"
            )
        else:
            QMessageBox.warning(self, "导出失败", "没有成功导出任何文件")
    
    def do_backup(self):
        """执行备份"""
        result = backup_database()
        if result['success']:
            size_mb = result['size'] / 1024 / 1024
            QMessageBox.information(
                self, "备份成功",
                f"数据库已备份到:\n{result['backup_path']}\n大小：{size_mb:.2f} MB"
            )
            self.refresh_backups()
        else:
            QMessageBox.critical(self, "备份失败", result.get('error', '未知错误'))
    
    def do_restore(self):
        """执行恢复"""
        current_item = self.list_backups.currentItem()
        if not current_item:
            QMessageBox.information(self, "提示", "请先选择一个备份文件")
            return
        
        backup_path = current_item.data(Qt.UserRole)
        
        reply = QMessageBox.question(
            self, "确认恢复",
            f"确定要从备份恢复吗？\n\n{backup_path}\n\n当前数据将被覆盖，此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            result = restore_database(backup_path)
            if result['success']:
                QMessageBox.information(self, "恢复成功", result['message'])
            else:
                QMessageBox.critical(self, "恢复失败", result['message'])


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dialog = DataManagementDialog()
    dialog.show()
    sys.exit(app.exec())
