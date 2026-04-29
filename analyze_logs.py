import sqlite3
import os
import sys

# 获取数据库路径
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(__file__))

def get_user_data_dir():
    if sys.platform == 'win32':
        appdata = os.getenv('APPDATA')
        if appdata:
            return os.path.join(appdata, 'FocusFlow')
    elif sys.platform == 'darwin':
        home = os.path.expanduser('~')
        return os.path.join(home, 'Library', 'Application Support', 'FocusFlow')
    else:
        home = os.path.expanduser('~')
        return os.path.join(home, '.local', 'share', 'FocusFlow')
    return get_base_dir()

def get_db_path():
    base_dir = get_base_dir()
    config_file = os.path.join(base_dir, "data", "active_db.txt")
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            custom_path = f.read().strip()
            if custom_path and os.path.exists(os.path.dirname(custom_path)):
                return custom_path
    user_data_dir = get_user_data_dir()
    user_db_path = os.path.join(user_data_dir, "data", "tracker.db")
    if os.path.exists(user_db_path):
        return user_db_path
    local_db_path = os.path.join(base_dir, "data", "tracker.db")
    if os.path.exists(local_db_path):
        return local_db_path
    return user_db_path

# 连接数据库
conn = sqlite3.connect(get_db_path())
cursor = conn.cursor()

# 查询最近的活动日志
print("最近的活动日志:")
cursor.execute("""
    SELECT app_name, file_path, timestamp, duration
    FROM activity_log
    ORDER BY timestamp DESC
    LIMIT 20
""")

rows = cursor.fetchall()
for row in rows:
    app_name, file_path, timestamp, duration = row
    print(f"App: {app_name}")
    print(f"File: {file_path}")
    print(f"Time: {timestamp}")
    print(f"Duration: {duration}")
    print("-" * 50)

# 查询唯一的应用名称
print("\n唯一的应用名称:")
cursor.execute("""
    SELECT DISTINCT app_name
    FROM activity_log
    ORDER BY app_name ASC
    LIMIT 10
""")

apps = cursor.fetchall()
for app in apps:
    print(f"- {app[0]}")

# 分析文件路径格式
print("\n文件路径格式分析:")
cursor.execute("""
    SELECT file_path
    FROM activity_log
    WHERE file_path IS NOT NULL AND file_path != ''
    ORDER BY RANDOM()
    LIMIT 10
""")

paths = cursor.fetchall()
for path in paths:
    file_path = path[0]
    print(f"- {file_path}")

# 分析应用名称格式
print("\n应用名称格式分析:")
cursor.execute("""
    SELECT app_name
    FROM activity_log
    WHERE app_name IS NOT NULL AND app_name != ''
    ORDER BY RANDOM()
    LIMIT 10
""")

app_names = cursor.fetchall()
for app_name in app_names:
    name = app_name[0]
    print(f"- {name}")

# 关闭数据库连接
conn.close()
