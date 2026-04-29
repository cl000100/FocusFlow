import sqlite3
import sys
import os

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

# 检查表是否存在
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='extraction_rules'")
if cursor.fetchone():
    print("extraction_rules 表存在")
    
    # 查询所有规则
    cursor.execute("SELECT id, rule_name, rule_type, match_pattern, project_id, priority, created_at FROM extraction_rules ORDER BY created_at DESC")
    rules = cursor.fetchall()
    
    if rules:
        print(f"\n共有 {len(rules)} 条规则:\n")
        for rule in rules:
            rule_id, rule_name, rule_type, match_pattern, project_id, priority, created_at = rule
            print(f"ID: {rule_id}")
            print(f"  规则名称: {rule_name}")
            print(f"  规则类型: {rule_type}")
            print(f"  匹配模式: {match_pattern}")
            print(f"  项目ID: {project_id}")
            print(f"  优先级: {priority}")
            print(f"  创建时间: {created_at}")
            print("-" * 50)
    else:
        print("\n暂无规则")
else:
    print("extraction_rules 表不存在")

conn.close()
