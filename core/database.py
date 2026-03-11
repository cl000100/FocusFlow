import sqlite3
import os

# 确保数据库路径固定在 data 文件夹下
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tracker.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_connection() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS activity_log 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME, app_name TEXT, file_path TEXT, duration REAL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS project_map 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, project_name TEXT UNIQUE, rule_path TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS projects
            (id INTEGER PRIMARY KEY AUTOINCREMENT, project_name TEXT UNIQUE, created_at DATETIME)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS file_assignment
            (id INTEGER PRIMARY KEY AUTOINCREMENT, file_path TEXT UNIQUE, project_name TEXT, assigned_at DATETIME)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS project_archive
            (id INTEGER PRIMARY KEY AUTOINCREMENT, project_name TEXT UNIQUE, archived_at DATETIME)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS runtime_status
            (id INTEGER PRIMARY KEY CHECK (id = 1),
             updated_at DATETIME,
             is_idle INTEGER,
             idle_seconds REAL,
             app_name TEXT,
             file_path TEXT)''')
