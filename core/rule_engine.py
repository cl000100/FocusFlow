import re
from datetime import datetime
from .database import get_connection

class RuleEngine:
    """规则提取引擎"""
    
    @staticmethod
    def extract_rules_from_app_name(app_name):
        """
        从应用名称中提取规则
        
        Args:
            app_name: 应用名称，如 "aaa-test-新建页面-Trae CN"
            
        Returns:
            list: 提取的规则列表
        """
        rules = []
        
        # 基于分隔符提取
        if '-' in app_name:
            parts = app_name.split('-')
            # 提取前几个部分作为规则
            for i in range(1, min(3, len(parts))):
                rule = '-'.join(parts[:i])
                if rule.strip():
                    rules.append(rule.strip())
        
        # 提取应用名称的主要部分
        main_part = app_name.split()[0] if app_name.split() else app_name
        if main_part and main_part not in rules:
            rules.append(main_part)
        
        return rules
    
    @staticmethod
    def extract_rules_from_file_path(file_path):
        """
        从文件路径中提取规则
        
        Args:
            file_path: 文件路径，如 "app_detector.py - FocusFlow - Trae CN"
            
        Returns:
            list: 提取的规则列表
        """
        rules = []
        
        # 基于分隔符提取
        if '-' in file_path:
            parts = file_path.split('-')
            # 提取文件名部分
            if parts:
                file_name_part = parts[0].strip()
                if file_name_part:
                    rules.append(file_name_part)
                
                # 提取项目名部分
                if len(parts) > 1:
                    project_part = parts[1].strip()
                    if project_part:
                        rules.append(project_part)
        
        # 提取文件扩展名
        if '.' in file_path:
            ext = file_path.split('.')[-1]
            if ext and ext not in rules:
                rules.append(f".{ext}")
        
        return rules
    
    @staticmethod
    def match_rule(rule, target, rule_type):
        """
        匹配规则
        
        Args:
            rule: 规则模式
            target: 目标字符串
            rule_type: 规则类型
            
        Returns:
            bool: 是否匹配
        """
        if not rule or not target:
            return False
        
        # 文件名匹配
        if rule_type == 'file_name':
            return rule in target
        
        # 应用名匹配
        elif rule_type == 'app_name':
            return rule in target
        
        # 文件路径匹配
        elif rule_type == 'file_path':
            return rule in target
        
        # 组合匹配
        elif rule_type == 'combination':
            # 组合规则格式: "app:规则1,file:规则2"
            parts = rule.split(',')
            for part in parts:
                if ':' in part:
                    type_part, pattern = part.split(':', 1)
                    if type_part == 'app' and pattern not in target.get('app_name', ''):
                        return False
                    elif type_part == 'file' and pattern not in target.get('file_path', ''):
                        return False
            return True
        
        return False
    
    @staticmethod
    def get_matching_files(rule, rule_type, limit=20):
        """
        获取匹配规则的文件列表
        
        Args:
            rule: 规则模式
            rule_type: 规则类型
            limit: 限制返回数量
            
        Returns:
            list: 匹配的文件列表
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        files = []
        
        if rule_type == 'file_name':
            cursor.execute("""
                SELECT DISTINCT file_path, app_name, MAX(timestamp) as last_seen
                FROM activity_log
                WHERE file_path LIKE ?
                GROUP BY file_path, app_name
                ORDER BY last_seen DESC
                LIMIT ?
            """, (f"%{rule}%", limit))
        
        elif rule_type == 'app_name':
            cursor.execute("""
                SELECT DISTINCT file_path, app_name, MAX(timestamp) as last_seen
                FROM activity_log
                WHERE app_name LIKE ?
                GROUP BY file_path, app_name
                ORDER BY last_seen DESC
                LIMIT ?
            """, (f"%{rule}%", limit))
        
        elif rule_type == 'file_path':
            cursor.execute("""
                SELECT DISTINCT file_path, app_name, MAX(timestamp) as last_seen
                FROM activity_log
                WHERE file_path LIKE ?
                GROUP BY file_path, app_name
                ORDER BY last_seen DESC
                LIMIT ?
            """, (f"%{rule}%", limit))
        
        elif rule_type == 'combination':
            # 组合规则需要特殊处理
            parts = rule.split(',')
            app_pattern = None
            file_pattern = None
            
            for part in parts:
                if ':' in part:
                    type_part, pattern = part.split(':', 1)
                    if type_part == 'app':
                        app_pattern = pattern
                    elif type_part == 'file':
                        file_pattern = pattern
            
            if app_pattern and file_pattern:
                cursor.execute("""
                    SELECT DISTINCT file_path, app_name, MAX(timestamp) as last_seen
                    FROM activity_log
                    WHERE app_name LIKE ? AND file_path LIKE ?
                    GROUP BY file_path, app_name
                    ORDER BY last_seen DESC
                    LIMIT ?
                """, (f"%{app_pattern}%", f"%{file_pattern}%", limit))
            elif app_pattern:
                cursor.execute("""
                    SELECT DISTINCT file_path, app_name, MAX(timestamp) as last_seen
                    FROM activity_log
                    WHERE app_name LIKE ?
                    GROUP BY file_path, app_name
                    ORDER BY last_seen DESC
                    LIMIT ?
                """, (f"%{app_pattern}%", limit))
            elif file_pattern:
                cursor.execute("""
                    SELECT DISTINCT file_path, app_name, MAX(timestamp) as last_seen
                    FROM activity_log
                    WHERE file_path LIKE ?
                    GROUP BY file_path, app_name
                    ORDER BY last_seen DESC
                    LIMIT ?
                """, (f"%{file_pattern}%", limit))
        
        rows = cursor.fetchall()
        for row in rows:
            file_path, app_name, last_seen = row
            files.append({
                'file_path': file_path,
                'app_name': app_name,
                'last_seen': last_seen
            })
        
        conn.close()
        return files
    
    @staticmethod
    def save_rule(rule_name, rule_type, match_pattern, project_id):
        """
        保存规则
        
        Args:
            rule_name: 规则名称
            rule_type: 规则类型
            match_pattern: 匹配模式
            project_id: 目标项目ID
            
        Returns:
            int: 规则ID
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO extraction_rules (rule_name, rule_type, match_pattern, project_id, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (rule_name, rule_type, match_pattern, project_id, datetime.now().isoformat()))
        
        rule_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return rule_id
    
    @staticmethod
    def get_rules(project_id=None):
        """
        获取规则列表
        
        Args:
            project_id: 项目ID，None表示获取所有规则
            
        Returns:
            list: 规则列表
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        if project_id:
            cursor.execute("""
                SELECT id, rule_name, rule_type, match_pattern, project_id, priority, created_at
                FROM extraction_rules
                WHERE project_id = ?
                ORDER BY priority DESC, created_at DESC
            """, (project_id,))
        else:
            cursor.execute("""
                SELECT id, rule_name, rule_type, match_pattern, project_id, priority, created_at
                FROM extraction_rules
                ORDER BY priority DESC, created_at DESC
            """)
        
        rules = []
        rows = cursor.fetchall()
        for row in rows:
            rule_id, rule_name, rule_type, match_pattern, project_id, priority, created_at = row
            rules.append({
                'id': rule_id,
                'rule_name': rule_name,
                'rule_type': rule_type,
                'match_pattern': match_pattern,
                'project_id': project_id,
                'priority': priority,
                'created_at': created_at
            })
        
        conn.close()
        return rules
    
    @staticmethod
    def delete_rule(rule_id):
        """
        删除规则
        
        Args:
            rule_id: 规则ID
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM extraction_rules WHERE id = ?", (rule_id,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def update_rule(rule_id, rule_name=None, rule_type=None, match_pattern=None, project_id=None, priority=None):
        """
        更新规则
        
        Args:
            rule_id: 规则ID
            rule_name: 规则名称
            rule_type: 规则类型
            match_pattern: 匹配模式
            project_id: 目标项目ID
            priority: 优先级
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        update_fields = []
        update_values = []
        
        if rule_name is not None:
            update_fields.append("rule_name = ?")
            update_values.append(rule_name)
        if rule_type is not None:
            update_fields.append("rule_type = ?")
            update_values.append(rule_type)
        if match_pattern is not None:
            update_fields.append("match_pattern = ?")
            update_values.append(match_pattern)
        if project_id is not None:
            update_fields.append("project_id = ?")
            update_values.append(project_id)
        if priority is not None:
            update_fields.append("priority = ?")
            update_values.append(priority)
        
        if update_fields:
            update_sql = "UPDATE extraction_rules SET " + ", ".join(update_fields) + " WHERE id = ?"
            update_values.append(rule_id)
            cursor.execute(update_sql, update_values)
            conn.commit()
        
        conn.close()
