import sqlite3
import os
import sys
from datetime import datetime
from typing import List, Optional, Dict, Any

def get_base_dir():
    """获取基础目录（支持打包后）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(__file__))

# 不再硬编码 DB_PATH，改用动态获取
# DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tracker.db")


class ProjectNode:
    def __init__(self, id: int, name: str, parent_id: Optional[int] = None, 
                 created_at: Optional[str] = None, is_archived: bool = False):
        self.id = id
        self.name = name
        self.parent_id = parent_id
        self.created_at = created_at
        self.is_archived = is_archived
        self._children: List['ProjectNode'] = []
        self._parent: Optional['ProjectNode'] = None
    
    def add_child(self, child: 'ProjectNode'):
        self._children.append(child)
        child._parent = self
    
    def remove_child(self, child: 'ProjectNode'):
        self._children = [c for c in self._children if c.id != child.id]
        if child._parent == self:
            child._parent = None
    
    def get_children(self) -> List['ProjectNode']:
        return self._children.copy()
    
    def get_ancestors(self) -> List['ProjectNode']:
        ancestors = []
        current = self._parent
        while current:
            ancestors.append(current)
            current = current._parent
        return ancestors
    
    def get_depth(self) -> int:
        return len(self.get_ancestors())
    
    def is_leaf(self) -> bool:
        return len(self._children) == 0
    
    def get_path(self) -> str:
        ancestors = self.get_ancestors()
        ancestors.reverse()
        path_parts = [a.name for a in ancestors] + [self.name]
        return " / ".join(path_parts)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'parent_id': self.parent_id,
            'created_at': self.created_at,
            'is_archived': self.is_archived,
            'path': self.get_path()
        }


class ProjectTree:
    def __init__(self):
        self._nodes: Dict[int, ProjectNode] = {}
        self._root_nodes: List[ProjectNode] = []
    
    def add_node(self, node: ProjectNode):
        self._nodes[node.id] = node
    
    def get_node(self, id: int) -> Optional[ProjectNode]:
        return self._nodes.get(id)
    
    def get_root_nodes(self) -> List[ProjectNode]:
        return self._root_nodes.copy()
    
    def build_tree(self):
        self._root_nodes = []
        for node in self._nodes.values():
            if node.parent_id is None:
                self._root_nodes.append(node)
            elif node.parent_id in self._nodes:
                parent = self._nodes[node.parent_id]
                parent.add_child(node)
    
    def get_all_nodes(self, include_archived: bool = False) -> List[ProjectNode]:
        nodes = []
        for node in self._nodes.values():
            if include_archived or not node.is_archived:
                nodes.append(node)
        return nodes
    
    def find_node_by_path(self, path: str) -> Optional[ProjectNode]:
        path_parts = [p.strip() for p in path.split('/')]
        return self._find_node_recursive(path_parts, self._root_nodes)
    
    def _find_node_recursive(self, path_parts: List[str], nodes: List[ProjectNode]) -> Optional[ProjectNode]:
        if not path_parts:
            return None
        current_name = path_parts[0]
        for node in nodes:
            if node.name == current_name:
                if len(path_parts) == 1:
                    return node
                return self._find_node_recursive(path_parts[1:], node.get_children())
        return None
    
    def find_node_by_name(self, name: str, parent_id: Optional[int] = None) -> Optional[ProjectNode]:
        for node in self._nodes.values():
            if node.name == name and node.parent_id == parent_id:
                return node
        return None
    
    def check_cyclic(self, node_id: int, new_parent_id: Optional[int]) -> bool:
        if new_parent_id is None or node_id == new_parent_id:
            return False
        visited = {node_id}
        current_id = new_parent_id
        while current_id is not None:
            if current_id in visited:
                return True
            visited.add(current_id)
            node = self._nodes.get(current_id)
            if node:
                current_id = node.parent_id
            else:
                break
        return False


def get_connection():
    from core.database import get_db_path
    return sqlite3.connect(get_db_path())


def init_project_tree():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            parent_id INTEGER,
            created_at DATETIME,
            FOREIGN KEY (parent_id) REFERENCES projects(id)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_projects_parent ON projects(parent_id)
    """)
    
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_name_parent 
        ON projects(project_name, parent_id)
    """)
    
    conn.commit()
    conn.close()

def load_project_tree() -> ProjectTree:
    tree = ProjectTree()
    conn = get_connection()
    cursor = conn.cursor()
    
    # 修复：将 pa.project_name 改为 pa.project_id
    cursor.execute("""
        SELECT p.id, p.project_name, p.parent_id, p.created_at,
               CASE WHEN pa.project_id IS NOT NULL THEN 1 ELSE 0 END as is_archived
        FROM projects p
        LEFT JOIN project_archive pa ON p.id = pa.project_id
    """)
    
    for row in cursor.fetchall():
        node = ProjectNode(
            id=row[0],
            name=row[1],
            parent_id=row[2],
            created_at=row[3],
            is_archived=bool(row[4])
        )
        tree.add_node(node)
    
    conn.close()
    tree.build_tree()
    return tree

def create_project(name: str, parent_id: Optional[int] = None) -> Optional[int]:
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO projects (project_name, parent_id, created_at) VALUES (?, ?, ?)",
            (name, parent_id, datetime.now().isoformat())
        )
        conn.commit()
        project_id = cursor.lastrowid
        return project_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def delete_project(project_id: int, delete_children: bool = False) -> bool:
    tree = load_project_tree()
    
    if tree.check_cyclic(project_id, None):
        return False
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if delete_children:
        cursor.execute("DELETE FROM projects WHERE id = ? OR parent_id = ?", (project_id, project_id))
    else:
        children = tree.get_node(project_id).get_children() if tree.get_node(project_id) else []
        if children:
            return False
        cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    
    conn.commit()
    conn.close()
    return True


def move_project(project_id: int, new_parent_id: Optional[int]) -> bool:
    tree = load_project_tree()
    
    if tree.check_cyclic(project_id, new_parent_id):
        return False
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE projects SET parent_id = ? WHERE id = ?",
        (new_parent_id, project_id)
    )
    conn.commit()
    conn.close()
    return True


def archive_project(project_id: int) -> bool:
    tree = load_project_tree()
    node = tree.get_node(project_id)
    
    if not node or not node.is_leaf():
        return False
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO project_archive (project_id, archived_at) VALUES (?, ?)",
        (project_id, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return True


def restore_project(project_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM project_archive WHERE project_id = ?", (project_id,))
    conn.commit()
    conn.close()
    return True

def get_project_stats(project_id: int, include_children: bool = False) -> Dict[str, float]:
    """
    获取项目统计数据（总时长、今日时长）
    
    【性能优化】：使用区间查询替代 DATE() 函数，使索引生效
    """
    from .database import get_connection, get_date_range
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 获取今天的日期范围
    today_start, tomorrow_start = get_date_range(0)
    
    all_ids = [project_id]
    
    if include_children:
        tree = load_project_tree()
        node = tree.get_node(project_id)
        
        def collect_children(node):
            all_ids.extend([c.id for c in node.get_children()])
            for c in node.get_children():
                collect_children(c)
        
        collect_children(node)
        placeholders = ','.join('?' * len(all_ids))
        cursor.execute(f"""
            SELECT 
                COALESCE(SUM(al.duration), 0) as total,
                COALESCE(SUM(CASE WHEN al.timestamp >= ? AND al.timestamp < ? THEN al.duration ELSE 0 END), 0) as today
            FROM activity_log al
            JOIN file_assignment fa ON al.file_path = fa.file_path
            WHERE fa.project_id IN ({placeholders})
        """, [today_start, tomorrow_start] + all_ids)
    else:
        cursor.execute("""
            SELECT 
                COALESCE(SUM(al.duration), 0) as total,
                COALESCE(SUM(CASE WHEN al.timestamp >= ? AND al.timestamp < ? THEN al.duration ELSE 0 END), 0) as today
            FROM activity_log al
            JOIN file_assignment fa ON al.file_path = fa.file_path
            WHERE fa.project_id = ?
        """, (today_start, tomorrow_start, project_id))
    
    row = cursor.fetchone()
    conn.close()
    
    return {
        'total': float(row[0]) if row else 0.0,
        'today': float(row[1]) if row else 0.0
    }


def get_projects_by_depth() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.id, p.project_name, p.parent_id, p.created_at,
               (SELECT COUNT(*) FROM projects p2 WHERE p2.parent_id = p.id) as child_count,
               CASE WHEN pa.project_id IS NOT NULL THEN 1 ELSE 0 END as is_archived
        FROM projects p
        LEFT JOIN project_archive pa ON p.id = pa.project_id
        ORDER BY p.parent_id, p.project_name
    """)
    
    projects = []
    for row in cursor.fetchall():
        projects.append({
            'id': row[0],
            'name': row[1],
            'parent_id': row[2],
            'created_at': row[3],
            'child_count': row[4],
            'is_archived': bool(row[5])
        })
    
    conn.close()
    return projects


def get_project_files(project_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT file_path, assigned_at
        FROM file_assignment
        WHERE project_id = ?
        ORDER BY assigned_at DESC
    """, (project_id,))
    
    files = []
    for row in cursor.fetchall():
        files.append({
            'file_path': row[0],
            'assigned_at': row[1]
        })
    
    conn.close()
    return files


def get_all_projects_flat() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.id, p.project_name, p.parent_id, p.created_at,
               CASE WHEN pa.project_id IS NOT NULL THEN 1 ELSE 0 END as is_archived
        FROM projects p
        LEFT JOIN project_archive pa ON p.id = pa.project_id
        ORDER BY p.parent_id, p.project_name
    """)
    
    projects = []
    for row in cursor.fetchall():
        projects.append({
            'id': row[0],
            'name': row[1],
            'parent_id': row[2],
            'created_at': row[3],
            'is_archived': bool(row[4])
        })
    
    conn.close()
    return projects


def remove_file_assignment(file_path: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM file_assignment WHERE file_path = ?", (file_path,))
    conn.commit()
    conn.close()
