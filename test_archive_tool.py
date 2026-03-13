#!/usr/bin/env python3
"""
数据归档测试工具
用于手动测试和查看归档功能
"""

import sys
import os
from datetime import datetime, timedelta

# 确保能导入 core 模块
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from core.database import (
    archive_month, get_archive_history, get_main_table_stats,
    query_activity_log, table_exists, get_archive_table_name,
    auto_archive_if_needed
)


def print_separator(title=""):
    """打印分隔线"""
    print("\n" + "="*60)
    if title:
        print(f"  {title}")
        print("="*60)


def view_main_table_stats():
    """查看主表统计"""
    print_separator("📊 主表统计信息")
    stats = get_main_table_stats()
    print(f"   记录总数：{stats['record_count']:,}")
    print(f"   最早记录：{stats['oldest_record']}")
    print(f"   最新记录：{stats['newest_record']}")
    
    # 估算数据量
    if stats['record_count'] > 10000:
        print(f"   💡 建议：主表数据较多，可以考虑归档旧数据")
    else:
        print(f"   ✅ 主表数据量良好")


def view_archive_history():
    """查看归档历史"""
    print_separator("📦 归档历史")
    archives = get_archive_history()
    
    if not archives:
        print("   暂无归档记录")
        return
    
    print(f"   共有 {len(archives)} 个归档表：\n")
    print(f"   {'表名':<25} {'年月':<12} {'记录数':>10}")
    print("   " + "-"*50)
    
    for archive in archives:
        table_name = archive['table_name']
        year_month = f"{archive['year']}-{archive['month']:02d}"
        count = f"{archive['record_count']:,}"
        print(f"   {table_name:<25} {year_month:<12} {count:>10}")
    
    print("\n   💡 提示：归档数据仍可正常查询，对用户透明")


def test_archive_month():
    """测试归档指定月份"""
    print_separator("🔄 手动归档测试")
    
    # 获取主表中最旧的月份
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MIN(timestamp) FROM activity_log
    """)
    oldest = cursor.fetchone()[0]
    conn.close()
    
    if not oldest:
        print("   主表没有数据")
        return
    
    # 解析最旧记录的年月
    from datetime import datetime
    oldest_date = datetime.fromisoformat(oldest)
    year = oldest_date.year
    month = oldest_date.month
    
    print(f"   主表中最旧的数据：{oldest}")
    print(f"   建议归档：{year}年{month}月")
    print(f"\n   是否执行归档？(y/n): ", end="")
    
    choice = input().strip().lower()
    if choice == 'y':
        try:
            result = archive_month(year, month)
            print(f"\n   ✅ 归档完成：{result['archived_count']} 条记录 → {result['table_name']}")
        except Exception as e:
            print(f"\n   ❌ 归档失败：{e}")
    else:
        print("   已取消")


def test_query_archived_data():
    """测试查询归档数据"""
    print_separator("🔍 查询归档数据测试")
    
    archives = get_archive_history()
    if not archives:
        print("   暂无归档表")
        return
    
    # 选择最旧的归档表
    oldest_archive = archives[-1]
    year = oldest_archive['year']
    month = oldest_archive['month']
    table_name = oldest_archive['table_name']
    
    print(f"   测试查询归档表：{table_name}")
    print(f"   归档时间：{year}年{month}月")
    
    # 查询该月数据
    start = f"{year}-{month:02d}-01 00:00:00"
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    end = f"{next_year}-{next_month:02d}-01 00:00:00"
    
    print(f"\n   查询范围：{start} 到 {end}")
    
    data = query_activity_log(start, end)
    print(f"   查询结果：{len(data)} 条记录")
    
    if data:
        print(f"\n   前 5 条记录：")
        for i, record in enumerate(data[:5], 1):
            timestamp, app, path, duration = record
            print(f"   {i}. {timestamp} - {app} ({duration/60:.1f}分钟)")
        
        print(f"\n   ✅ 查询成功！归档数据可正常访问")
    else:
        print(f"   ⚠️  未查询到数据")


def auto_archive_test():
    """测试自动归档"""
    print_separator("🤖 自动归档测试")
    
    today = datetime.now()
    print(f"   当前日期：{today.strftime('%Y-%m-%d')} ({today.day}号)")
    
    if today.day == 1:
        print(f"   今天是月初，应该执行自动归档...")
        result = auto_archive_if_needed()
        print(f"   执行结果：{'已归档' if result else '无需归档'}")
    else:
        print(f"   不是月初，不会自动归档")
        result = auto_archive_if_needed()
        print(f"   检查结果：{'执行了归档' if result else '未执行'}")


def main():
    """主菜单"""
    from core.database import get_connection
    
    while True:
        print_separator("🗄️  FocusFlow 数据归档测试工具")
        print("   1. 查看主表统计")
        print("   2. 查看归档历史")
        print("   3. 手动归档测试")
        print("   4. 查询归档数据测试")
        print("   5. 自动归档测试")
        print("   0. 退出")
        print("="*60)
        print("   请选择：", end="")
        
        choice = input().strip()
        
        if choice == "1":
            view_main_table_stats()
        elif choice == "2":
            view_archive_history()
        elif choice == "3":
            test_archive_month()
        elif choice == "4":
            test_query_archived_data()
        elif choice == "5":
            auto_archive_test()
        elif choice == "0":
            print("\n   再见！👋")
            break
        else:
            print("   无效选择，请重新输入")
        
        input("\n   按回车键继续...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n   已中断")
        sys.exit(0)
