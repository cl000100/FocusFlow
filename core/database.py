import sqlite3
import os

# 确保数据库路径固定在 data 文件夹下
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tracker.db")


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
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

    # 初始化默认配置 (如果不存在的话)
    cursor.execute("INSERT OR IGNORE INTO system_config (key, value) VALUES ('idle_threshold', '30')")
    
    conn.commit()
    conn.close()


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
