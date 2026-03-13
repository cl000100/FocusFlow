import sqlite3
import os

def get_db_path():
    # 读取配置文件以支持动态热切换数据库
    base_dir = os.path.dirname(os.path.dirname(__file__))
    config_file = os.path.join(base_dir, "data", "active_db.txt")
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            custom_path = f.read().strip()
            if custom_path and os.path.exists(os.path.dirname(custom_path)):
                return custom_path
    return os.path.join(base_dir, "data", "tracker.db")

def set_db_path(new_path):
    # 保存新的数据库路径
    base_dir = os.path.dirname(os.path.dirname(__file__))
    config_file = os.path.join(base_dir, "data", "active_db.txt")
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(new_path)

def get_connection():
    return sqlite3.connect(get_db_path())


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # ================= 性能优化：启用 WAL 模式 =================
    # WAL (Write-Ahead Logging) 允许读写并发，提升性能
    # 必须在其他操作之前执行
    cursor.execute('''PRAGMA journal_mode = WAL''')
    
    # 1. 基础活动日志表
    cursor.execute('''CREATE TABLE IF NOT EXISTS activity_log 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME, app_name TEXT, file_path TEXT, duration REAL)''')
    
    # 2. 项目树表
    cursor.execute('''CREATE TABLE IF NOT EXISTS projects
        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
         project_name TEXT, 
         parent_id INTEGER,
         created_at DATETIME,
         FOREIGN KEY (parent_id) REFERENCES projects(id))''')
         
    # 3. 自动化规则表 (某路径自动归属某项目)
    cursor.execute('''CREATE TABLE IF NOT EXISTS project_map 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
         project_name TEXT, 
         rule_path TEXT,
         project_id INTEGER,
         FOREIGN KEY (project_id) REFERENCES projects(id))''')
    
    # 4. 文件/程序精确分配表
    cursor.execute('''CREATE TABLE IF NOT EXISTS file_assignment
        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
         file_path TEXT, 
         project_name TEXT, 
         assigned_at DATETIME,
         project_id INTEGER,
         FOREIGN KEY (project_id) REFERENCES projects(id))''')
    
    # 5. 归档表 (记录项目归档状态)
    cursor.execute('''CREATE TABLE IF NOT EXISTS project_archive
        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
         project_name TEXT, 
         archived_at DATETIME,
         project_id INTEGER,
         FOREIGN KEY (project_id) REFERENCES projects(id))''')
    
    # 6. 运行时状态 (前端悬浮窗与后台通信用)
    cursor.execute('''CREATE TABLE IF NOT EXISTS runtime_status
        (id INTEGER PRIMARY KEY CHECK (id = 1),
         updated_at DATETIME,
         is_idle INTEGER,
         idle_seconds REAL,
         app_name TEXT,
         file_path TEXT)''')

    # ================= 新增表 =================
    
    # 7. 系统配置表 (如空闲阈值等用户自定义设置)
    cursor.execute('''CREATE TABLE IF NOT EXISTS system_config
        (key TEXT PRIMARY KEY, 
         value TEXT)''')
         
    # 8. 黑/白名单表 (忽略的程序或窗口标题关键字)
    cursor.execute('''CREATE TABLE IF NOT EXISTS ignore_list
        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
         keyword TEXT UNIQUE,
         created_at DATETIME)''')
    
    # 9. 碎片记录归档表（存储被过滤的碎片记录）
    cursor.execute('''CREATE TABLE IF NOT EXISTS fragment_archive
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         file_path TEXT,
         app_name TEXT,
         duration REAL,
         timestamp DATETIME,
         archived_at DATETIME,
         action TEXT)''')  # action: 'deleted' 或 'merged'

    # 初始化默认配置 (如果不存在的话)
    cursor.execute("INSERT OR IGNORE INTO system_config (key, value) VALUES ('idle_threshold', '30')")
    
    # ================= 性能优化：创建索引 =================
    
    # 1. timestamp 索引 - 加速时间范围查询（今日统计、过去 7 天趋势）
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_activity_log_timestamp 
                      ON activity_log(timestamp)''')
    
    # 2. file_path 索引 - 加速路径匹配查询（项目自动分配）
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_activity_log_file_path 
                      ON activity_log(file_path)''')
    
    # 3. app_name 索引 - 加速应用筛选查询
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_activity_log_app_name 
                      ON activity_log(app_name)''')
    
    # 4. 复合索引 - 优化同时使用时间和路径的查询
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_activity_log_timestamp_path 
                      ON activity_log(timestamp, file_path)''')
    
    conn.commit()
    conn.close()


def get_config(key, default=None):
    """读取配置项"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM system_config WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default


def auto_archive_if_needed():
    """
    自动归档检查
    如果是月初，自动归档上月数据
    
    调用时机：
    - 程序启动时
    - 后台服务启动时
    - 每天首次查询时
    
    Returns:
        bool: 是否执行了归档
    """
    from datetime import datetime
    
    today = datetime.now()
    
    # 如果是每月 1 号，归档上月数据
    if today.day == 1:
        # 计算上一年月
        if today.month == 1:
            last_year, last_month = today.year - 1, 12
        else:
            last_year, last_month = today.year, today.month - 1
        
        # 检查是否已归档
        archive_table = get_archive_table_name(last_year, last_month)
        if not table_exists(archive_table):
            print(f"📦 检测到月初，自动归档 {last_year}年{last_month}月 数据...")
            archive_month(last_year, last_month)
            return True
    
    return False


def get_main_table_stats():
    """
    获取主表统计信息
    
    Returns:
        dict: {'record_count': 记录数， 'oldest_record': 最早记录时间， 'newest_record': 最新记录时间}
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as record_count,
            MIN(timestamp) as oldest_record,
            MAX(timestamp) as newest_record
        FROM activity_log
    """)
    
    row = cursor.fetchone()
    conn.close()
    
    return {
        'record_count': row[0] if row[0] else 0,
        'oldest_record': row[1],
        'newest_record': row[2]
    }


def set_config(key, value):
    """写入配置项"""
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)
    """, (key, value))
    conn.commit()
    conn.close()


def get_date_range(days_back=0):
    """
    获取日期范围用于区间查询（替代 DATE() 函数，使索引生效）
    
    Args:
        days_back: 往前推多少天（0 表示今天）
    
    Returns:
        tuple: (start_date_str, end_date_str) 格式：'YYYY-MM-DD HH:MM:SS'
    """
    from datetime import datetime, timedelta
    
    if days_back == 0:
        # 今天：从今天 00:00:00 到明天 00:00:00
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        return today.strftime('%Y-%m-%d %H:%M:%S'), tomorrow.strftime('%Y-%m-%d %H:%M:%S')
    else:
        # 过去 N 天：从 N 天前 00:00:00 到今天 23:59:59
        start_date = datetime.now() - timedelta(days=days_back)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_date.strftime('%Y-%m-%d %H:%M:%S'), end_date.strftime('%Y-%m-%d %H:%M:%S')


# ================= 数据归档功能 =================

def get_archive_table_name(year, month):
    """
    获取归档表名
    
    Args:
        year: 年份（如 2025）
        month: 月份（如 3）
    
    Returns:
        str: 归档表名（如 'activity_2025_03'）
    """
    return f"activity_{year}_{month:02d}"


def is_recent_month(year, month, keep_days=30):
    """
    判断指定月份是否属于"最近 N 天"范围（保留在主表中）
    
    Args:
        year: 年份
        month: 月份
        keep_days: 主表保留的天数（默认 30 天）
    
    Returns:
        bool: True 表示应该保留在主表，False 表示应该归档
    """
    from datetime import datetime, timedelta
    
    # 计算 keep_days 天前的日期
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    
    # 计算指定月份的最后一天
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    
    # 指定月份的最后一天
    last_day_of_month = datetime(next_year, next_month, 1) - timedelta(days=1)
    
    # 如果指定月份的最后一天 < cutoff_date，说明整个月都应该归档
    return last_day_of_month >= cutoff_date


def table_exists(table_name):
    """
    检查表是否存在
    
    Args:
        table_name: 表名
    
    Returns:
        bool: 表是否存在
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM sqlite_master 
        WHERE type='table' AND name=?
    """, (table_name,))
    result = cursor.fetchone()[0]
    conn.close()
    return result > 0


def create_archive_table(year, month):
    """
    创建指定月份的归档表
    
    Args:
        year: 年份
        month: 月份
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    table_name = get_archive_table_name(year, month)
    
    # 创建归档表（结构与 activity_log 相同）
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            app_name TEXT,
            file_path TEXT,
            duration REAL
        )
    """)
    
    # 为归档表创建索引（加速查询）
    cursor.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_{table_name}_timestamp 
        ON {table_name}(timestamp)
    """)
    
    cursor.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_{table_name}_file_path 
        ON {table_name}(file_path)
    """)
    
    conn.commit()
    conn.close()


def archive_month(year, month):
    """
    归档指定月份的数据
    将 activity_log 中该月的数据移动到归档表
    
    Args:
        year: 年份
        month: 月份
    
    Returns:
        dict: 归档统计信息 {'archived_count': 归档条数, 'table_name': 归档表名}
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. 创建归档表（如果不存在）
    table_name = get_archive_table_name(year, month)
    create_archive_table(year, month)
    
    # 2. 计算时间范围
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    
    start_date = f"{year}-{month:02d}-01 00:00:00"
    end_date = f"{next_year}-{next_month:02d}-01 00:00:00"
    
    archived_count = 0
    
    try:
        # 3. 开启事务
        cursor.execute("BEGIN TRANSACTION")
        
        # 4. 统计将要归档的数据量
        cursor.execute("""
            SELECT COUNT(*) FROM activity_log
            WHERE timestamp >= ? AND timestamp < ?
        """, (start_date, end_date))
        archived_count = cursor.fetchone()[0]
        
        if archived_count == 0:
            # 没有数据需要归档
            conn.commit()
            print(f"ℹ️  {year}年{month}月 没有数据需要归档")
            return {'archived_count': 0, 'table_name': table_name}
        
        # 5. 将数据插入归档表（使用 INSERT INTO ... SELECT 提高效率）
        cursor.execute(f"""
            INSERT INTO {table_name} (timestamp, app_name, file_path, duration)
            SELECT timestamp, app_name, file_path, duration
            FROM activity_log
            WHERE timestamp >= ? AND timestamp < ?
        """, (start_date, end_date))
        
        # 6. 删除主表中已归档的数据
        cursor.execute("""
            DELETE FROM activity_log
            WHERE timestamp >= ? AND timestamp < ?
        """, (start_date, end_date))
        
        # 7. 提交事务
        conn.commit()
        
        print(f"✅ 成功归档 {year}年{month}月 的数据：{archived_count} 条记录 → {table_name}")
        
        return {'archived_count': archived_count, 'table_name': table_name}
        
    except Exception as e:
        # 8. 失败回滚
        conn.rollback()
        print(f"❌ 归档失败：{e}")
        raise
    
    finally:
        conn.close()


def get_archive_history():
    """
    获取所有归档表的历史记录
    
    Returns:
        list: [{'table_name': 'activity_2025_01', 'year': 2025, 'month': 1, 'record_count': 1000}, ...]
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 查询所有归档表
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'activity_%'
        ORDER BY name DESC
    """)
    
    archives = []
    for (table_name,) in cursor.fetchall():
        # 跳过主表
        if table_name == 'activity_log':
            continue
        
        # 解析表名获取年月
        parts = table_name.split('_')
        if len(parts) == 3:
            year = int(parts[1])
            month = int(parts[2])
            
            # 统计记录数
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            record_count = cursor.fetchone()[0]
            
            archives.append({
                'table_name': table_name,
                'year': year,
                'month': month,
                'record_count': record_count
            })
    
    conn.close()
    return archives


# ================= 智能查询功能（跨表查询） =================

def query_activity_log(start_date, end_date, columns=None):
    """
    智能查询活动日志（自动跨表查询）
    自动判断数据在主表还是归档表，支持跨月查询
    
    Args:
        start_date: 'YYYY-MM-DD HH:MM:SS'
        end_date: 'YYYY-MM-DD HH:MM:SS'
        columns: 要查询的列，默认 ['timestamp', 'app_name', 'file_path', 'duration']
    
    Returns:
        list: [(timestamp, app_name, file_path, duration), ...]
    """
    from datetime import datetime
    
    if columns is None:
        columns = ['timestamp', 'app_name', 'file_path', 'duration']
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. 解析日期范围
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)
    
    # 2. 收集所有需要查询的表
    tables_to_query = set()
    
    # 遍历时间范围内的所有月份
    current = start_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while current <= end_dt:
        # 总是检查主表和归档表
        # 对于最近的月份，优先查主表
        if is_recent_month(current.year, current.month):
            tables_to_query.add("activity_log")
        
        # 同时检查是否有归档表（即使是最远的月份也可能有归档表）
        archive_table = get_archive_table_name(current.year, current.month)
        if table_exists(archive_table):
            tables_to_query.add(archive_table)
        
        # 下一个月
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    
    # 3. 从所有相关表查询数据
    all_data = []
    columns_str = ', '.join(columns)
    
    for table in sorted(tables_to_query):  # 排序保证顺序一致
        try:
            data = cursor.execute(f"""
                SELECT {columns_str}
                FROM {table}
                WHERE timestamp >= ? AND timestamp < ?
            """, (start_date, end_date)).fetchall()
            all_data.extend(data)
        except sqlite3.OperationalError:
            # 表不存在或其他错误，跳过
            continue
    
    conn.close()
    
    # 4. 按时间排序后返回
    return sorted(all_data, key=lambda x: x[0] if x[0] else '')


def query_activity_stats(start_date, end_date, group_by=None):
    """
    智能查询统计数据（支持跨表聚合）
    
    Args:
        start_date: 'YYYY-MM-DD HH:MM:SS'
        end_date: 'YYYY-MM-DD HH:MM:SS'
        group_by: 分组字段，如 'app_name', 'file_path', 'DATE(SUBSTR(timestamp, 1, 10))'
    
    Returns:
        list: 统计结果
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. 确定需要查询的表（与 query_activity_log 相同逻辑）
    from datetime import datetime
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)
    
    tables_to_query = set()
    current = start_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while current <= end_dt:
        if is_recent_month(current.year, current.month):
            tables_to_query.add("activity_log")
        else:
            archive_table = get_archive_table_name(current.year, current.month)
            if table_exists(archive_table):
                tables_to_query.add(archive_table)
        
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    
    # 2. 构建 UNION ALL 查询（跨表聚合）
    queries = []
    for table in sorted(tables_to_query):
        if group_by:
            query = f"""
                SELECT {group_by}, SUM(duration) as total_duration, COUNT(*) as record_count
                FROM {table}
                WHERE timestamp >= ? AND timestamp < ?
                GROUP BY {group_by}
            """
        else:
            query = f"""
                SELECT SUM(duration), COUNT(*)
                FROM {table}
                WHERE timestamp >= ? AND timestamp < ?
            """
        queries.append(query)
    
    # 3. 使用 UNION ALL 合并所有表的结果
    if not queries:
        conn.close()
        return []
    
    # 如果有分组，需要在外层再次聚合
    if group_by:
        combined_query = " UNION ALL ".join(queries)
        final_query = f"""
            SELECT {group_by}, SUM(total_duration), SUM(record_count)
            FROM ({combined_query})
            GROUP BY {group_by}
        """
    else:
        # 没有分组，直接求和
        combined_query = " UNION ALL ".join(queries)
        final_query = f"""
            SELECT SUM(col1), SUM(col2)
            FROM (
                {combined_query.replace('SUM(duration)', 'col1').replace('COUNT(*)', 'col2')}
            )
        """
    
    # 4. 执行查询
    params = []
    for _ in tables_to_query:
        params.extend([start_date, end_date])
    
    try:
        result = cursor.execute(final_query, params).fetchall()
    except sqlite3.OperationalError:
        result = []
    
    conn.close()
    return result


def init_project_tree():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_projects_parent ON projects(parent_id)
    """)
    
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_name_parent 
        ON projects(project_name, parent_id)
    """)
    
    conn.commit()
    conn.close()
