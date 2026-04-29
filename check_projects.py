import sqlite3
import os
import sys

# 模拟 get_user_data_dir 函数
def get_user_data_dir():
    """获取用户数据目录（跨平台）"""
    if sys.platform == 'win32':
        # Windows: C:\Users\用户名\AppData\Roaming\FocusFlow
        appdata = os.getenv('APPDATA')
        if appdata:
            return os.path.join(appdata, 'FocusFlow')
    elif sys.platform == 'darwin':
        # macOS: ~/Library/Application Support/FocusFlow
        home = os.path.expanduser('~')
        return os.path.join(home, 'Library', 'Application Support', 'FocusFlow')
    else:
        # Linux: ~/.local/share/FocusFlow
        home = os.path.expanduser('~')
        return os.path.join(home, '.local', 'share', 'FocusFlow')

# 模拟 get_base_dir 函数
def get_base_dir():
    """获取程序基础目录"""
    return os.path.dirname(os.path.abspath(__file__))

# 模拟 get_db_path 函数
def get_db_path():
    """获取数据库路径
    
    优先级：
    1. 用户自定义路径（配置文件）
    2. 用户数据目录（推荐）
    3. 程序目录（兼容旧版）
    """
    base_dir = get_base_dir()
    
    # 1. 检查用户自定义路径配置
    config_file = os.path.join(base_dir, "data", "active_db.txt")
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            custom_path = f.read().strip()
            if custom_path and os.path.exists(os.path.dirname(custom_path)):
                return custom_path
    
    # 2. 优先使用用户数据目录
    user_data_dir = get_user_data_dir()
    user_db_path = os.path.join(user_data_dir, "data", "tracker.db")
    
    # 如果用户数据目录的数据库存在，直接使用
    if os.path.exists(user_db_path):
        return user_db_path
    
    # 3. 降级到程序目录（兼容旧版）
    local_db_path = os.path.join(base_dir, "data", "tracker.db")
    if os.path.exists(local_db_path):
        return local_db_path
    
    # 4. 默认使用用户数据目录（首次启动）
    return user_db_path

# 获取数据库路径
db_path = get_db_path()
print(f'数据库路径: {db_path}')

# 连接数据库
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查询项目列表
cursor.execute('SELECT id, project_name, parent_id FROM projects ORDER BY parent_id, project_name ASC')
rows = cursor.fetchall()

print('当前项目列表:')
for row in rows:
    print(f'ID: {row[0]}, 名称: {row[1]}, 父ID: {row[2]}')

conn.close()