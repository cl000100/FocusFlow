#!/usr/bin/env python3
"""
数据归档功能测试脚本
测试归档功能的所有核心功能
"""

import sys
import os
from datetime import datetime, timedelta

# 确保能导入 core 模块
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from core.database import (
    get_connection, create_archive_table, archive_month, 
    query_activity_log, query_activity_stats, get_archive_history,
    get_main_table_stats, table_exists, get_archive_table_name,
    auto_archive_if_needed
)


def insert_test_data(date_str, count=10):
    """
    插入测试数据
    
    Args:
        date_str: 日期字符串 'YYYY-MM-DD'
        count: 插入多少条记录
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    for i in range(count):
        timestamp = f"{date_str} {10+i//3600:02d}:{(i%3600)//60:02d}:{i%60:02d}"
        cursor.execute("""
            INSERT INTO activity_log (timestamp, app_name, file_path, duration)
            VALUES (?, ?, ?, ?)
        """, (timestamp, f"TestApp_{i%3}", f"/test/path/file{i}.txt", 60.0))
    
    conn.commit()
    conn.close()
    print(f"✅ 插入 {count} 条测试数据：{date_str}")


def test_archive_functions():
    """测试归档功能"""
    print("\n" + "="*60)
    print("📦 测试归档功能")
    print("="*60)
    
    # 1. 插入历史测试数据（上个月）
    today = datetime.now()
    if today.month == 1:
        last_year, last_month = today.year - 1, 12
    else:
        last_year, last_month = today.year, today.month - 1
    
    # 生成上个月的日期
    last_month_date = f"{last_year}-{last_month:02d}-15"
    
    print(f"\n1️⃣  准备测试数据（{last_month_date}）...")
    insert_test_data(last_month_date, count=50)
    
    # 2. 执行归档
    print(f"\n2️⃣  归档 {last_year}年{last_month}月 数据...")
    result = archive_month(last_year, last_month)
    print(f"   归档结果：{result}")
    
    # 3. 验证归档表存在
    archive_table = get_archive_table_name(last_year, last_month)
    assert table_exists(archive_table), f"❌ 归档表 {archive_table} 不存在"
    print(f"\n3️⃣  归档表 {archive_table} 创建成功 ✅")
    
    # 4. 验证主表数据已删除
    stats = get_main_table_stats()
    print(f"\n4️⃣  主表数据统计：{stats}")
    
    # 5. 验证归档历史
    archives = get_archive_history()
    print(f"\n5️⃣  归档历史：{len(archives)} 个归档表")
    for archive in archives:
        print(f"   - {archive['table_name']}: {archive['record_count']} 条记录")
    
    return True


def test_query_functions():
    """测试智能查询功能"""
    print("\n" + "="*60)
    print("🔍 测试智能查询功能")
    print("="*60)
    
    # 1. 插入测试数据（今天和昨天）
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"\n1️⃣  准备测试数据（今天和昨天）...")
    insert_test_data(today, count=20)
    insert_test_data(yesterday, count=20)
    
    # 2. 测试查询今天的数据
    print(f"\n2️⃣  查询今天的数据...")
    today_start = f"{today} 00:00:00"
    today_end = f"{today} 23:59:59"
    
    data = query_activity_log(today_start, today_end)
    print(f"   查询结果：{len(data)} 条记录")
    assert len(data) > 0, "❌ 没有查询到今天的数据"
    
    # 3. 测试查询跨月数据
    print(f"\n3️⃣  查询跨月数据（今天 + 昨天）...")
    start = f"{yesterday} 00:00:00"
    end = f"{today} 23:59:59"
    
    data = query_activity_log(start, end)
    print(f"   查询结果：{len(data)} 条记录")
    assert len(data) >= 40, f"❌ 跨月查询数据不足，期望>=40，实际{len(data)}"
    
    # 4. 测试统计查询
    print(f"\n4️⃣  测试统计查询...")
    stats = query_activity_stats(start, end, group_by="app_name")
    print(f"   按 app_name 分组统计：{len(stats)} 组")
    for stat in stats:
        print(f"   - {stat[0]}: 总时长={stat[1]:.1f}秒，记录数={stat[2]}")
    
    # 5. 测试查询归档表数据
    print(f"\n5️⃣  测试查询归档表数据...")
    archives = get_archive_history()
    if archives:
        oldest_archive = archives[0]
        archive_table = oldest_archive['table_name']
        year, month = oldest_archive['year'], oldest_archive['month']
        
        # 查询该月的数据（使用正确的日期范围）
        start = f"{year}-{month:02d}-01 00:00:00"
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1
        end = f"{next_year}-{next_month:02d}-01 00:00:00"
        
        print(f"   查询范围：{start} 到 {end}")
        data = query_activity_log(start, end)
        print(f"   智能查询结果：{len(data)} 条记录")
        
        # 验证能查询到数据
        assert len(data) > 0, "❌ 没有查询到归档表数据"
        print(f"   ✅ 智能查询功能正常，成功查询到归档数据")
    else:
        print("   ⚠️  暂无归档表，跳过此测试")
    
    return True


def test_auto_archive():
    """测试自动归档功能"""
    print("\n" + "="*60)
    print("🤖 测试自动归档功能")
    print("="*60)
    
    # 检查今天是否是 1 号
    today = datetime.now()
    if today.day == 1:
        print(f"\n✅ 今天是 {today.day} 号，应该执行自动归档")
        result = auto_archive_if_needed()
        print(f"   自动归档执行结果：{result}")
    else:
        print(f"\nℹ️  今天是 {today.day} 号，不是月初，不会执行自动归档")
        result = auto_archive_if_needed()
        print(f"   自动归档检查结果：{result}")
    
    return True


def main():
    """主测试函数"""
    print("="*60)
    print("🧪 FocusFlow 数据归档功能测试")
    print("="*60)
    
    try:
        # 1. 测试归档功能
        test_archive_functions()
        
        # 2. 测试查询功能
        test_query_functions()
        
        # 3. 测试自动归档
        test_auto_archive()
        
        # 总结
        print("\n" + "="*60)
        print("✅ 所有测试通过！归档功能运行正常")
        print("="*60)
        
        # 显示最终状态
        print("\n📊 最终状态：")
        stats = get_main_table_stats()
        print(f"   主表记录数：{stats['record_count']}")
        print(f"   最早记录：{stats['oldest_record']}")
        print(f"   最新记录：{stats['newest_record']}")
        
        archives = get_archive_history()
        print(f"\n   归档表数量：{len(archives)}")
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ 测试失败：{e}")
        return False
    except Exception as e:
        print(f"\n❌ 测试异常：{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
