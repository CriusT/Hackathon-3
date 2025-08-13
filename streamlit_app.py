"""
数据标注平台 - Streamlit 原型
支持多种数据类型的标注任务配置和执行
"""

import streamlit as st
import pandas as pd
import json
import base64
from pathlib import Path
import sqlite3
from datetime import datetime
import uuid
from typing import Dict, List, Any, Optional
import os
import hashlib
import hmac

# 页面配置
st.set_page_config(
    page_title="数据标注平台",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 常量配置
PUBLISHER_INVITE_CODE = "qijizhifeng"

# 认证工具函数
def hash_password(password: str) -> str:
    """对密码进行哈希处理"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    return hash_password(password) == hashed

def check_authentication():
    """检查用户是否已登录"""
    if 'user' not in st.session_state:
        return False
    return True

def require_authentication():
    """要求用户登录，如果未登录则显示登录页面"""
    if not check_authentication():
        show_auth_page()
        return False
    return True

def is_publisher():
    """检查当前用户是否为发布者"""
    return check_authentication() and st.session_state.user.get('role') == 'publisher'

def is_annotator():
    """检查当前用户是否为标注者"""
    return check_authentication() and st.session_state.user.get('role') == 'annotator'

def show_auth_page():
    """显示登录/注册页面"""
    st.title("🔐 数据标注平台")
    
    tab1, tab2 = st.tabs(["登录", "注册"])
    
    with tab1:
        show_login_form()
    
    with tab2:
        show_register_form()

def show_login_form():
    """显示登录表单"""
    st.subheader("用户登录")
    
    with st.form("login_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        submit = st.form_submit_button("登录", type="primary")
        
        if submit:
            if not username or not password:
                st.error("请填写用户名和密码")
                return
            
            db = DatabaseManager()
            password_hash = hash_password(password)
            user = db.authenticate_user(username, password_hash)
            
            if user:
                st.session_state.user = user
                st.success(f"欢迎回来，{user['full_name'] or user['username']}！")
                st.rerun()
            else:
                st.error("用户名或密码错误")

def show_register_form():
    """显示注册表单"""
    st.subheader("用户注册")
    
    with st.form("register_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            username = st.text_input("用户名*", help="请输入唯一的用户名")
            password = st.text_input("密码*", type="password")
            confirm_password = st.text_input("确认密码*", type="password")
        
        with col2:
            full_name = st.text_input("姓名*")
            email = st.text_input("邮箱")
            invite_code = st.text_input("发布者邀请码", help="如有邀请码可注册为发布者，否则注册为标注者")
        
        submit = st.form_submit_button("注册", type="primary")
        
        if submit:
            # 验证表单
            if not username or not password or not full_name:
                st.error("请填写所有必填项（*）")
                return
            
            if password != confirm_password:
                st.error("两次输入的密码不一致")
                return
            
            if len(password) < 6:
                st.error("密码长度至少6位")
                return
            
            # 确定用户角色
            role = 'publisher' if invite_code == PUBLISHER_INVITE_CODE else 'annotator'
            
            # 检查用户名是否已存在
            db = DatabaseManager()
            existing_user = db.get_user_by_username(username)
            if existing_user:
                st.error("用户名已存在，请选择其他用户名")
                return
            
            # 创建用户
            try:
                user_data = {
                    'username': username,
                    'password_hash': hash_password(password),
                    'full_name': full_name,
                    'email': email,
                    'role': role
                }
                
                user_id = db.create_user(user_data)
                
                role_text = "发布者" if role == 'publisher' else "标注者"
                st.success(f"注册成功！您已注册为{role_text}账户。请使用用户名和密码登录。")
                
                # 自动登录
                user = db.authenticate_user(username, hash_password(password))
                if user:
                    st.session_state.user = user
                    st.rerun()
                    
            except Exception as e:
                st.error(f"注册失败: {str(e)}")

def logout():
    """登出用户"""
    if 'user' in st.session_state:
        del st.session_state.user
    st.rerun()

# 数据库初始化
def init_database():
    """初始化SQLite数据库"""
    conn = sqlite3.connect('annotation_platform.db')
    cursor = conn.cursor()
    
    # 创建任务表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            config TEXT,
            status TEXT DEFAULT 'created',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_path TEXT
        )
    ''')
    
    # 创建标注表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS annotations (
            id TEXT PRIMARY KEY,
            task_id TEXT,
            data_index INTEGER,
            result TEXT,
            status TEXT DEFAULT 'pending',
            annotator_id TEXT DEFAULT 'user1',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks (id)
        )
    ''')
    
    # 创建用户表 - 先检查是否已存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    users_table_exists = cursor.fetchone() is not None
    
    if not users_table_exists:
        # 创建新的用户表
        cursor.execute('''
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT UNIQUE,
                role TEXT DEFAULT 'annotator',
                full_name TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
    else:
        # 检查并添加缺失的列
        try:
            cursor.execute("SELECT full_name FROM users LIMIT 1")
        except sqlite3.OperationalError:
            # full_name 列不存在，添加它
            cursor.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
        
        try:
            cursor.execute("SELECT password_hash FROM users LIMIT 1")
        except sqlite3.OperationalError:
            # password_hash 列不存在，添加它
            cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        
        try:
            cursor.execute("SELECT email FROM users LIMIT 1")
        except sqlite3.OperationalError:
            # email 列不存在，添加它
            cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
        
        try:
            cursor.execute("SELECT is_active FROM users LIMIT 1")
        except sqlite3.OperationalError:
            # is_active 列不存在，添加它
            cursor.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1")
        
        try:
            cursor.execute("SELECT last_login FROM users LIMIT 1")
        except sqlite3.OperationalError:
            # last_login 列不存在，添加它
            cursor.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP")
    
    # 创建任务分配表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_assignments (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            assigned_to TEXT NOT NULL,
            assigned_by TEXT NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'assigned',
            FOREIGN KEY (task_id) REFERENCES tasks (id),
            FOREIGN KEY (assigned_to) REFERENCES users (id),
            FOREIGN KEY (assigned_by) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# 数据库操作类
class DatabaseManager:
    def __init__(self, db_path='annotation_platform.db'):
        self.db_path = db_path
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def create_task(self, task_data: Dict) -> str:
        """创建标注任务"""
        task_id = str(uuid.uuid4())
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO tasks (id, name, description, config, data_path)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            task_id,
            task_data['name'],
            task_data.get('description', ''),
            json.dumps(task_data.get('config', {})),
            task_data.get('data_path', '')
        ))
        
        conn.commit()
        conn.close()
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'config': json.loads(row[3]) if row[3] else {},
                'status': row[4],
                'created_at': row[5],
                'data_path': row[6]
            }
        return None
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM tasks ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        
        tasks = []
        for row in rows:
            tasks.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'config': json.loads(row[3]) if row[3] else {},
                'status': row[4],
                'created_at': row[5],
                'data_path': row[6]
            })
        return tasks
    
    def save_annotation(self, task_id: str, data_index: int, result: Any):
        """保存标注结果"""
        annotation_id = str(uuid.uuid4())
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 检查是否已存在标注
        cursor.execute('''
            SELECT id FROM annotations 
            WHERE task_id = ? AND data_index = ? AND annotator_id = ?
        ''', (task_id, data_index, 'user1'))
        
        existing = cursor.fetchone()
        
        if existing:
            # 更新现有标注
            cursor.execute('''
                UPDATE annotations 
                SET result = ?, updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ? AND data_index = ? AND annotator_id = ?
            ''', (json.dumps(result), task_id, data_index, 'user1'))
        else:
            # 创建新标注
            cursor.execute('''
                INSERT INTO annotations (id, task_id, data_index, result, annotator_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (annotation_id, task_id, data_index, json.dumps(result), 'user1'))
        
        conn.commit()
        conn.close()
    
    def get_annotation(self, task_id: str, data_index: int) -> Optional[Dict]:
        """获取标注结果"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT result FROM annotations 
            WHERE task_id = ? AND data_index = ? AND annotator_id = ?
        ''', (task_id, data_index, 'user1'))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None
    
    def get_task_progress(self, task_id: str) -> Dict:
        """获取任务进度"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 获取总数据量
        task = self.get_task(task_id)
        if not task or not task.get('data_path'):
            return {'total': 0, 'completed': 0, 'progress': 0, 'unsaved_indices': []}
        
        try:
            with open(task['data_path'], 'r', encoding='utf-8') as f:
                total = len(f.readlines())
        except:
            total = 0
        
        # 获取已完成数量和已保存的索引
        cursor.execute('''
            SELECT data_index FROM annotations 
            WHERE task_id = ? AND annotator_id = ?
        ''', (task_id, 'user1'))
        
        saved_indices = set(row[0] for row in cursor.fetchall())
        completed = len(saved_indices)
        
        # 计算未保存的索引
        all_indices = set(range(total))
        unsaved_indices = sorted(list(all_indices - saved_indices))
        
        conn.close()
        
        progress = (completed / total * 100) if total > 0 else 0
        
        return {
            'total': total,
            'completed': completed,
            'progress': round(progress, 2),
            'unsaved_indices': unsaved_indices
        }
    
    def is_annotation_saved(self, task_id: str, data_index: int) -> bool:
        """检查指定数据是否已保存标注"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id FROM annotations 
            WHERE task_id = ? AND data_index = ? AND annotator_id = ?
        ''', (task_id, data_index, 'user1'))
        
        result = cursor.fetchone() is not None
        conn.close()
        return result
    
    # 用户管理相关方法
    def create_user(self, user_data: Dict) -> str:
        """创建新用户"""
        user_id = str(uuid.uuid4())
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO users (id, username, password_hash, email, role, full_name)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            user_data['username'],
            user_data['password_hash'],
            user_data.get('email', ''),
            user_data.get('role', 'annotator'),
            user_data.get('full_name', '')
        ))
        
        conn.commit()
        conn.close()
        return user_id
    
    def authenticate_user(self, username: str, password_hash: str) -> Optional[Dict]:
        """验证用户登录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT id, username, role, full_name, email
                FROM users 
                WHERE username = ? AND password_hash = ? AND is_active = 1
            ''', (username, password_hash))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'id': row[0],
                    'username': row[1],
                    'role': row[2],
                    'full_name': row[3] if row[3] else '',
                    'email': row[4] if row[4] else ''
                }
            return None
        except sqlite3.OperationalError as e:
            conn.close()
            # 如果遇到列不存在的错误，说明数据库结构不兼容
            if "no such column" in str(e):
                st.error("数据库结构需要更新，请重启应用或联系管理员")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """根据用户名获取用户信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT id, username, role, full_name, email, created_at
                FROM users 
                WHERE username = ? AND is_active = 1
            ''', (username,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'id': row[0],
                    'username': row[1],
                    'role': row[2] if row[2] else 'annotator',
                    'full_name': row[3] if row[3] else '',
                    'email': row[4] if row[4] else '',
                    'created_at': row[5]
                }
            return None
        except sqlite3.OperationalError as e:
            conn.close()
            if "no such column" in str(e):
                # 尝试使用旧版本的查询
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT id, username, role, created_at FROM users WHERE username = ?', (username,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    return {
                        'id': row[0],
                        'username': row[1],
                        'role': row[2] if row[2] else 'annotator',
                        'full_name': '',
                        'email': '',
                        'created_at': row[3]
                    }
            return None
    
    def get_all_annotators(self) -> List[Dict]:
        """获取所有标注者用户"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, full_name, email, created_at
            FROM users 
            WHERE role = 'annotator' AND is_active = 1
            ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        annotators = []
        for row in rows:
            annotators.append({
                'id': row[0],
                'username': row[1],
                'full_name': row[2],
                'email': row[3],
                'created_at': row[4]
            })
        return annotators
    
    def assign_task(self, task_id: str, assigned_to: str, assigned_by: str) -> str:
        """分配任务给标注者"""
        assignment_id = str(uuid.uuid4())
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 删除旧的分配记录
        cursor.execute('DELETE FROM task_assignments WHERE task_id = ?', (task_id,))
        
        # 创建新的分配记录
        cursor.execute('''
            INSERT INTO task_assignments (id, task_id, assigned_to, assigned_by)
            VALUES (?, ?, ?, ?)
        ''', (assignment_id, task_id, assigned_to, assigned_by))
        
        conn.commit()
        conn.close()
        return assignment_id
    
    def get_task_assignment(self, task_id: str) -> Optional[Dict]:
        """获取任务分配信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ta.assigned_to, ta.assigned_by, ta.assigned_at, 
                   u1.username as assigned_to_username, u1.full_name as assigned_to_name,
                   u2.username as assigned_by_username, u2.full_name as assigned_by_name
            FROM task_assignments ta
            JOIN users u1 ON ta.assigned_to = u1.id
            JOIN users u2 ON ta.assigned_by = u2.id
            WHERE ta.task_id = ?
        ''', (task_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'assigned_to': row[0],
                'assigned_by': row[1],
                'assigned_at': row[2],
                'assigned_to_username': row[3],
                'assigned_to_name': row[4],
                'assigned_by_username': row[5],
                'assigned_by_name': row[6]
            }
        return None
    
    def get_user_assigned_tasks(self, user_id: str) -> List[Dict]:
        """获取分配给用户的任务"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.id, t.name, t.description, t.status, t.created_at, ta.assigned_at
            FROM tasks t
            JOIN task_assignments ta ON t.id = ta.task_id
            WHERE ta.assigned_to = ?
            ORDER BY ta.assigned_at DESC
        ''', (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        tasks = []
        for row in rows:
            tasks.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'status': row[3],
                'created_at': row[4],
                'assigned_at': row[5]
            })
        return tasks

# 文件处理类
class FileProcessor:
    @staticmethod
    def load_jsonl(file_content: str) -> List[Dict]:
        """加载JSONL文件"""
        lines = file_content.strip().split('\n')
        data = []
        for i, line in enumerate(lines):
            if line.strip():
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError as e:
                    st.error(f"第 {i+1} 行JSON格式错误: {e}")
                    return []
        return data
    
    @staticmethod
    def save_jsonl(data: List[Dict], file_path: str):
        """保存数据为JSONL文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
    
    @staticmethod
    def validate_file_paths(data: List[Dict], base_path: str = '') -> Dict[str, List[str]]:
        """验证文件路径"""
        issues = {'missing': [], 'invalid': []}
        
        for i, item in enumerate(data):
            for key, value in item.items():
                if isinstance(value, str):
                    # 检查是否为文件路径
                    if any(ext in value.lower() for ext in ['.jpg', '.png', '.pdf', '.jpeg', '.gif']):
                        full_path = os.path.join(base_path, value) if base_path else value
                        if not os.path.exists(full_path):
                            issues['missing'].append(f"第{i+1}条数据的{key}字段: {value}")
        
        return issues

# 数据渲染器
class DataRenderer:
    @staticmethod
    def render_text(data: str, field_name: str):
        """渲染文本数据"""
        st.text_area(f"📄 {field_name}", data, height=100, disabled=True)
    
    @staticmethod
    def render_code(data: str, field_name: str, language: str = 'sql'):
        """渲染代码数据"""
        st.subheader(f"💻 {field_name}")
        st.code(data, language=language)
    
    @staticmethod
    def render_image(file_path: str, field_name: str, base_path: str = ''):
        """渲染图片数据"""
        st.subheader(f"🖼️ {field_name}")
        full_path = os.path.join(base_path, file_path) if base_path else file_path
        
        if os.path.exists(full_path):
            st.image(full_path, caption=file_path, use_column_width=True)
        else:
            st.error(f"图片文件不存在: {full_path}")
    
    @staticmethod
    def render_pdf(file_path: str, field_name: str, base_path: str = ''):
        """渲染PDF数据"""
        st.subheader(f"📄 {field_name}")
        full_path = os.path.join(base_path, file_path) if base_path else file_path
        
        if os.path.exists(full_path):
            st.write(f"PDF文件: {file_path}")
            
            # 提供下载链接
            with open(full_path, "rb") as f:
                bytes_data = f.read()
                st.download_button(
                    label="📥 下载PDF",
                    data=bytes_data,
                    file_name=os.path.basename(file_path),
                    mime="application/pdf"
                )
        else:
            st.error(f"PDF文件不存在: {full_path}")
    
    @staticmethod
    def render_markdown(data: str, field_name: str):
        """渲染Markdown数据"""
        st.subheader(f"📝 {field_name}")
        st.markdown(data)

# 标注表单生成器
class AnnotationFormGenerator:
    @staticmethod
    def render_single_choice(options: List[str], key: str, default_value=None):
        """单选表单"""
        default_index = 0
        if default_value and default_value in options:
            default_index = options.index(default_value)
        
        return st.radio(
            "请选择一个选项:",
            options,
            index=default_index,
            key=key
        )
    
    @staticmethod
    def render_multiple_choice(options: List[str], key: str, default_value=None):
        """多选表单"""
        default_values = default_value if isinstance(default_value, list) else []
        return st.multiselect(
            "请选择多个选项:",
            options,
            default=default_values,
            key=key
        )
    
    @staticmethod
    def render_rating(min_val: int = 1, max_val: int = 10, key: str = None, default_value=None):
        """评分表单"""
        default_val = default_value if default_value is not None else min_val
        return st.slider(
            f"评分 ({min_val}-{max_val}):",
            min_value=min_val,
            max_value=max_val,
            value=default_val,
            key=key
        )
    
    @staticmethod
    def render_text_input(placeholder: str = "请输入标注内容", key: str = None, default_value=None):
        """文本输入表单"""
        default_val = default_value if default_value is not None else ""
        return st.text_area(
            "请输入标注内容:",
            value=default_val,
            placeholder=placeholder,
            key=key
        )

# 主应用
def main():
    # 初始化数据库
    init_database()
    db = DatabaseManager()
    
    # 检查认证状态
    if not require_authentication():
        return
    
    # 显示用户信息和导航
    user = st.session_state.user
    
    # 侧边栏用户信息
    st.sidebar.title("📝 数据标注平台")
    
    with st.sidebar:
        st.write(f"👤 **{user['full_name']}** ({user['username']})")
        role_emoji = "👨‍💼" if user['role'] == 'publisher' else "👨‍💻"
        role_text = "发布者" if user['role'] == 'publisher' else "标注者"
        st.write(f"{role_emoji} {role_text}")
        
        if st.button("🚪 退出登录"):
            logout()
        
        st.divider()
    
    # 根据用户角色显示不同的导航选项
    if user['role'] == 'publisher':
        # 发布者界面
        page = st.sidebar.selectbox(
            "选择功能",
            ["🏠 首页", "⚙️ 任务配置", "📝 数据标注", "📊 进度管理", "📤 结果导出", "👥 任务分配"]
        )
        
        if page == "🏠 首页":
            home_page(db)
        elif page == "⚙️ 任务配置":
            task_config_page(db)
        elif page == "📝 数据标注":
            annotation_page(db)
        elif page == "📊 进度管理":
            progress_page(db)
        elif page == "📤 结果导出":
            export_page(db)
        elif page == "👥 任务分配":
            task_assignment_page(db)
    
    else:
        # 标注者界面（只能看到分配给自己的任务）
        page = st.sidebar.selectbox(
            "选择功能",
            ["🏠 我的任务", "📝 数据标注", "📊 我的进度"]
        )
        
        if page == "🏠 我的任务":
            annotator_home_page(db)
        elif page == "📝 数据标注":
            annotation_page(db, annotator_view=True)
        elif page == "📊 我的进度":
            annotator_progress_page(db)

def task_assignment_page(db: DatabaseManager):
    """任务分配页面（仅发布者可见）"""
    st.title("👥 任务分配管理")
    
    # 获取所有任务和标注者
    tasks = db.get_all_tasks()
    annotators = db.get_all_annotators()
    
    if not tasks:
        st.warning("暂无任务，请先创建任务")
        return
    
    if not annotators:
        st.warning("暂无标注者用户，请等待标注者注册")
        return
    
    st.subheader("📋 任务分配")
    
    # 选择任务
    task_options = {f"{task['name']} (ID: {task['id'][:8]})": task['id'] for task in tasks}
    selected_task_name = st.selectbox("选择要分配的任务", list(task_options.keys()))
    
    if selected_task_name:
        task_id = task_options[selected_task_name]
        task = next(t for t in tasks if t['id'] == task_id)
        
        # 显示任务信息
        st.write(f"**任务名称**: {task['name']}")
        st.write(f"**任务描述**: {task['description']}")
        
        # 显示当前分配状态
        current_assignment = db.get_task_assignment(task_id)
        if current_assignment:
            st.info(f"📌 当前分配给: **{current_assignment['assigned_to_name']}** (@{current_assignment['assigned_to_username']})")
            st.write(f"分配时间: {current_assignment['assigned_at']}")
            st.write(f"分配人: {current_assignment['assigned_by_name']}")
        else:
            st.warning("⚠️ 该任务尚未分配给任何标注者")
        
        st.divider()
        
        # 分配/重新分配
        st.subheader("🎯 分配任务")
        
        # 标注者选择
        annotator_options = {f"{ann['full_name']} (@{ann['username']})": ann['id'] for ann in annotators}
        selected_annotator_name = st.selectbox("选择标注者", list(annotator_options.keys()))
        
        if selected_annotator_name and st.button("📤 分配任务", type="primary"):
            selected_annotator_id = annotator_options[selected_annotator_name]
            current_user_id = st.session_state.user['id']
            
            try:
                assignment_id = db.assign_task(task_id, selected_annotator_id, current_user_id)
                
                selected_annotator = next(ann for ann in annotators if ann['id'] == selected_annotator_id)
                st.success(f"✅ 任务已成功分配给 **{selected_annotator['full_name']}** (@{selected_annotator['username']})")
                st.rerun()
                
            except Exception as e:
                st.error(f"分配失败: {str(e)}")
    
    st.divider()
    
    # 显示所有任务的分配状态
    st.subheader("📊 所有任务分配状态")
    
    for task in tasks:
        assignment = db.get_task_assignment(task['id'])
        progress = db.get_task_progress(task['id'])
        
        with st.expander(f"📝 {task['name']} - {progress['progress']:.1f}% 完成"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**描述**: {task['description']}")
                st.write(f"**创建时间**: {task['created_at']}")
                st.write(f"**数据量**: {progress['total']} 条")
                st.write(f"**完成情况**: {progress['completed']}/{progress['total']} ({progress['progress']:.1f}%)")
                
                if assignment:
                    st.success(f"✅ 已分配给: **{assignment['assigned_to_name']}** (@{assignment['assigned_to_username']})")
                    st.write(f"分配时间: {assignment['assigned_at']}")
                else:
                    st.warning("⚠️ 未分配")
            
            with col2:
                if progress['total'] > 0:
                    st.progress(progress['progress'] / 100)

def annotator_home_page(db: DatabaseManager):
    """标注者首页"""
    st.title("🏠 我的标注任务")
    
    user_id = st.session_state.user['id']
    assigned_tasks = db.get_user_assigned_tasks(user_id)
    
    if not assigned_tasks:
        st.info("📭 您目前没有被分配任何标注任务，请联系发布者分配任务。")
        return
    
    st.write(f"您共有 **{len(assigned_tasks)}** 个分配的任务")
    
    for task in assigned_tasks:
        progress = db.get_task_progress(task['id'])
        
        with st.expander(f"📝 {task['name']} - {progress['progress']:.1f}% 完成"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**描述**: {task['description']}")
                st.write(f"**分配时间**: {task['assigned_at']}")
                st.write(f"**标注进度**: {progress['completed']}/{progress['total']}")
                
                if progress['unsaved_indices']:
                    unsaved_count = len(progress['unsaved_indices'])
                    st.warning(f"⚠️ 还有 {unsaved_count} 条未保存")
                else:
                    st.success("✅ 所有条目已保存")
            
            with col2:
                if progress['total'] > 0:
                    st.progress(progress['progress'] / 100)
                
                if st.button(f"📝 开始标注", key=f"start_{task['id']}"):
                    st.session_state['selected_task_id'] = task['id']
                    st.switch_page("annotation")

def annotator_progress_page(db: DatabaseManager):
    """标注者进度页面"""
    st.title("📊 我的标注进度")
    
    user_id = st.session_state.user['id']
    assigned_tasks = db.get_user_assigned_tasks(user_id)
    
    if not assigned_tasks:
        st.info("您目前没有被分配任何标注任务")
        return
    
    # 总体统计
    total_tasks = len(assigned_tasks)
    completed_tasks = 0
    total_items = 0
    completed_items = 0
    
    for task in assigned_tasks:
        progress = db.get_task_progress(task['id'])
        total_items += progress['total']
        completed_items += progress['completed']
        if progress['progress'] >= 100:
            completed_tasks += 1
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("分配任务", total_tasks)
    with col2:
        st.metric("完成任务", completed_tasks)
    with col3:
        st.metric("总数据量", total_items)
    with col4:
        st.metric("已标注", completed_items)
    
    if total_items > 0:
        overall_progress = (completed_items / total_items) * 100
        st.progress(overall_progress / 100)
        st.write(f"总体完成率: {overall_progress:.1f}%")
    
    st.divider()
    
    # 详细任务进度
    st.subheader("📋 详细任务进度")
    
    for task in assigned_tasks:
        progress = db.get_task_progress(task['id'])
        
        with st.expander(f"📝 {task['name']} - {progress['progress']:.1f}% 完成"):
            st.write(f"**描述**: {task['description']}")
            st.write(f"**分配时间**: {task['assigned_at']}")
            
            if progress['total'] > 0:
                st.progress(progress['progress'] / 100)
                st.write(f"标注进度: {progress['completed']}/{progress['total']}")
                
                if progress['unsaved_indices']:
                    unsaved_count = len(progress['unsaved_indices'])
                    if unsaved_count <= 5:
                        unsaved_display = ', '.join([str(i+1) for i in progress['unsaved_indices']])
                        st.warning(f"⚠️ 未保存: 第 {unsaved_display} 条")
                    else:
                        st.warning(f"⚠️ 还有 {unsaved_count} 条未保存")
                else:
                    st.success("✅ 所有条目已保存")
            else:
                st.write("暂无数据")

def home_page(db: DatabaseManager):
    """首页"""
    st.title("🏠 数据标注平台首页")
    
    st.markdown("""
    ## 欢迎使用数据标注平台！
    
    这是一个支持多种数据类型的标注平台，主要功能包括：
    
    - 📁 **任务配置**: 上传数据文件，配置标注任务
    - 📝 **数据标注**: 进行实际的数据标注工作
    - 📊 **进度管理**: 查看标注进度和统计
    - 📤 **结果导出**: 导出标注结果
    
    ### 支持的数据类型:
    - 📄 文本数据
    - 🖼️ 图片文件 (.jpg, .png, .gif, etc.)
    - 💻 代码块 (SQL, Python, etc.)
    - 📄 PDF文档
    - 📝 Markdown文档
    
    ### 支持的标注形式:
    - 🔘 单选题
    - ☑️ 多选题
    - ⭐ 评分 (1-10分)
    - ✏️ 文本输入
    """)
    
    # 显示系统统计
    st.subheader("📈 系统统计")
    
    tasks = db.get_all_tasks()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("总任务数", len(tasks))
    
    with col2:
        active_tasks = len([t for t in tasks if t['status'] in ['created', 'in_progress']])
        st.metric("进行中任务", active_tasks)
    
    with col3:
        completed_tasks = len([t for t in tasks if t['status'] == 'completed'])
        st.metric("已完成任务", completed_tasks)
    
    # 最近任务
    if tasks:
        st.subheader("📋 最近任务")
        for task in tasks[:5]:
            with st.expander(f"📝 {task['name']} ({task['status']})"):
                st.write(f"**描述**: {task['description']}")
                st.write(f"**创建时间**: {task['created_at']}")
                
                progress = db.get_task_progress(task['id'])
                if progress['total'] > 0:
                    st.progress(progress['progress'] / 100)
                    st.write(f"进度: {progress['completed']}/{progress['total']} ({progress['progress']:.1f}%)")

def task_config_page(db: DatabaseManager):
    """任务配置页面"""
    st.title("⚙️ 任务配置")
    
    # 步骤指示器
    steps = ["上传文件", "字段配置", "标注配置", "任务确认"]
    current_step = st.session_state.get('config_step', 0)
    
    col1, col2, col3, col4 = st.columns(4)
    for i, step in enumerate(steps):
        with [col1, col2, col3, col4][i]:
            if i <= current_step:
                st.success(f"✅ {step}")
            else:
                st.info(f"⏳ {step}")
    
    st.divider()
    
    if current_step == 0:
        upload_file_step(db)
    elif current_step == 1:
        configure_fields_step(db)
    elif current_step == 2:
        configure_annotation_step(db)
    elif current_step == 3:
        confirm_task_step(db)

def upload_file_step(db: DatabaseManager):
    """文件上传步骤"""
    st.subheader("📁 步骤1: 上传数据文件")
    
    uploaded_file = st.file_uploader(
        "请上传JSONL格式的数据文件",
        type=['jsonl'],
        help="JSONL文件每行应包含一个JSON对象，代表一条待标注的数据"
    )
    
    if uploaded_file is not None:
        # 读取文件内容
        content = uploaded_file.read().decode('utf-8')
        data = FileProcessor.load_jsonl(content)
        
        if data:
            st.success(f"✅ 成功加载 {len(data)} 条数据")
            
            # 显示数据预览
            st.subheader("📋 数据预览")
            
            # 显示字段信息
            if data:
                fields = list(data[0].keys())
                st.write(f"**检测到的字段**: {', '.join(fields)}")
                
                # 显示前几条数据 - 转换为字符串避免类型冲突
                preview_data = data[:5]
                try:
                    # 将所有值转换为字符串以避免类型冲突
                    cleaned_data = []
                    for item in preview_data:
                        cleaned_item = {}
                        for key, value in item.items():
                            if isinstance(value, (list, dict)):
                                cleaned_item[key] = str(value)
                            else:
                                cleaned_item[key] = str(value) if value is not None else ""
                        cleaned_data.append(cleaned_item)
                    
                    df = pd.DataFrame(cleaned_data)
                    st.dataframe(df, use_container_width=True)
                except Exception as e:
                    st.warning(f"数据预览遇到问题，但文件解析成功。错误: {str(e)}")
                    # 降级显示：逐条显示原始数据
                    st.write("**原始数据预览（前3条）：**")
                    for i, item in enumerate(preview_data[:3]):
                        with st.expander(f"第 {i+1} 条数据"):
                            st.json(item)
            
            # 文件路径验证
            base_path = st.text_input(
                "数据文件基础路径 (可选)",
                help="如果JSONL中包含相对路径的文件引用，请指定基础路径"
            )
            
            if base_path:
                issues = FileProcessor.validate_file_paths(data, base_path)
                if issues['missing']:
                    st.warning("⚠️ 发现缺失的文件:")
                    for issue in issues['missing'][:10]:  # 只显示前10个
                        st.write(f"- {issue}")
                    if len(issues['missing']) > 10:
                        st.write(f"... 还有 {len(issues['missing']) - 10} 个文件缺失")
            
            # 保存到session state
            st.session_state['upload_data'] = data
            st.session_state['upload_filename'] = uploaded_file.name
            st.session_state['base_path'] = base_path
            
            if st.button("下一步: 配置字段", type="primary"):
                st.session_state['config_step'] = 1
                st.rerun()

def configure_fields_step(db: DatabaseManager):
    """字段配置步骤"""
    st.subheader("🏷️ 步骤2: 配置显示字段")
    
    if 'upload_data' not in st.session_state:
        st.error("请先上传数据文件")
        if st.button("返回上传"):
            st.session_state['config_step'] = 0
            st.rerun()
        return
    
    data = st.session_state['upload_data']
    sample_data = data[0] if data else {}
    
    st.write("请选择要在标注界面显示的字段，并配置每个字段的数据类型:")
    
    all_fields = list(sample_data.keys())
    
    # 字段选择
    selected_fields = st.multiselect(
        "选择要显示的字段",
        all_fields,
        default=all_fields,
        help="选择在标注界面中要显示给标注员的字段"
    )
    
    if not selected_fields:
        st.warning("请至少选择一个字段")
        return
    
    # 字段类型配置
    field_configs = {}
    
    st.write("**字段类型配置**:")
    
    for field in selected_fields:
        col1, col2, col3 = st.columns([2, 2, 3])
        
        with col1:
            st.write(f"**{field}**")
        
        with col2:
            field_type = st.selectbox(
                "数据类型",
                ["text", "image", "code", "pdf", "markdown"],
                key=f"type_{field}",
                help="选择这个字段的数据类型以正确渲染"
            )
        
        with col3:
            if field_type == "code":
                language = st.selectbox(
                    "代码语言",
                    ["sql", "python", "javascript", "json", "text"],
                    key=f"lang_{field}"
                )
                field_configs[field] = {"type": field_type, "language": language}
            else:
                field_configs[field] = {"type": field_type}
    
    # 预览配置效果
    st.subheader("👀 配置预览")
    
    if selected_fields:
        preview_data = sample_data
        base_path = st.session_state.get('base_path', '')
        
        for field in selected_fields:
            if field in preview_data:
                config = field_configs[field]
                value = preview_data[field]
                
                if config["type"] == "text":
                    DataRenderer.render_text(str(value), field)
                elif config["type"] == "code":
                    DataRenderer.render_code(str(value), field, config.get("language", "text"))
                elif config["type"] == "image":
                    DataRenderer.render_image(str(value), field, base_path)
                elif config["type"] == "pdf":
                    DataRenderer.render_pdf(str(value), field, base_path)
                elif config["type"] == "markdown":
                    DataRenderer.render_markdown(str(value), field)
    
    # 保存配置
    st.session_state['field_configs'] = field_configs
    st.session_state['selected_fields'] = selected_fields
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("上一步"):
            st.session_state['config_step'] = 0
            st.rerun()
    
    with col2:
        if st.button("下一步: 配置标注", type="primary"):
            st.session_state['config_step'] = 2
            st.rerun()

def configure_annotation_step(db: DatabaseManager):
    """标注配置步骤"""
    st.subheader("📝 步骤3: 配置标注内容")
    
    if 'field_configs' not in st.session_state:
        st.error("请先完成字段配置")
        return
    
    st.write("请配置标注员需要完成的标注任务:")
    
    # 标注形式选择
    annotation_type = st.selectbox(
        "标注形式",
        ["single_choice", "multiple_choice", "rating", "text_input"],
        format_func=lambda x: {
            "single_choice": "🔘 单选",
            "multiple_choice": "☑️ 多选", 
            "rating": "⭐ 评分",
            "text_input": "✏️ 文本输入"
        }[x]
    )
    
    annotation_config = {"type": annotation_type}
    
    # 根据类型配置参数
    if annotation_type in ["single_choice", "multiple_choice"]:
        st.subheader("选项配置")
        
        options_input = st.text_area(
            "选项列表 (每行一个选项)",
            placeholder="True\nFalse",
            help="每行输入一个选项，支持中英文"
        )
        
        if options_input.strip():
            options = [opt.strip() for opt in options_input.split('\n') if opt.strip()]
            annotation_config["options"] = options
            
            st.write("**选项预览**:")
            for i, opt in enumerate(options, 1):
                st.write(f"{i}. {opt}")
        else:
            st.warning("请输入至少一个选项")
    
    elif annotation_type == "rating":
        st.subheader("评分配置")
        
        col1, col2 = st.columns(2)
        with col1:
            min_val = st.number_input("最小值", value=1, min_value=1)
        with col2:
            max_val = st.number_input("最大值", value=10, min_value=min_val + 1)
        
        annotation_config["min_value"] = int(min_val)
        annotation_config["max_value"] = int(max_val)
        
        st.write(f"**评分范围**: {min_val} - {max_val}")
    
    elif annotation_type == "text_input":
        st.subheader("文本输入配置")
        
        placeholder = st.text_input(
            "输入提示文本",
            value="请输入标注内容",
            help="显示在输入框中的提示文本"
        )
        
        annotation_config["placeholder"] = placeholder
    
    # 标注说明
    instruction = st.text_area(
        "标注说明",
        placeholder="请为标注员提供详细的标注指南和要求...",
        help="这些说明将显示在标注界面中，帮助标注员理解任务要求"
    )
    
    annotation_config["instruction"] = instruction
    
    # 预览标注界面
    st.subheader("📱 标注界面预览")
    
    if instruction:
        st.info(f"📋 **标注说明**: {instruction}")
    
    # 模拟标注表单
    if annotation_type == "single_choice" and annotation_config.get("options"):
        AnnotationFormGenerator.render_single_choice(
            annotation_config["options"], 
            "preview_single"
        )
    elif annotation_type == "multiple_choice" and annotation_config.get("options"):
        AnnotationFormGenerator.render_multiple_choice(
            annotation_config["options"], 
            "preview_multi"
        )
    elif annotation_type == "rating":
        AnnotationFormGenerator.render_rating(
            annotation_config["min_value"], 
            annotation_config["max_value"], 
            "preview_rating"
        )
    elif annotation_type == "text_input":
        AnnotationFormGenerator.render_text_input(
            annotation_config.get("placeholder", ""), 
            "preview_text"
        )
    
    # 保存配置
    st.session_state['annotation_config'] = annotation_config
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("上一步"):
            st.session_state['config_step'] = 1
            st.rerun()
    
    with col2:
        if annotation_type in ["single_choice", "multiple_choice"] and not annotation_config.get("options"):
            st.button("下一步: 确认任务", disabled=True)
            st.warning("请配置选项")
        else:
            if st.button("下一步: 确认任务", type="primary"):
                st.session_state['config_step'] = 3
                st.rerun()

def confirm_task_step(db: DatabaseManager):
    """任务确认步骤"""
    st.subheader("✅ 步骤4: 确认并创建任务")
    
    # 任务基本信息
    st.write("**任务基本信息**:")
    
    task_name = st.text_input(
        "任务名称",
        value=f"标注任务_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        help="为这个标注任务起一个名称"
    )
    
    task_description = st.text_area(
        "任务描述",
        placeholder="请描述这个标注任务的目的和要求...",
        help="详细描述这个任务的背景和目标"
    )
    
    # 配置摘要
    st.subheader("📋 配置摘要")
    
    if 'upload_data' in st.session_state:
        st.write(f"**数据量**: {len(st.session_state['upload_data'])} 条")
    
    if 'selected_fields' in st.session_state:
        st.write(f"**显示字段**: {', '.join(st.session_state['selected_fields'])}")
    
    if 'annotation_config' in st.session_state:
        config = st.session_state['annotation_config']
        type_names = {
            "single_choice": "单选",
            "multiple_choice": "多选", 
            "rating": "评分",
            "text_input": "文本输入"
        }
        st.write(f"**标注类型**: {type_names.get(config['type'], config['type'])}")
        
        if config.get('options'):
            st.write(f"**选项**: {', '.join(config['options'])}")
        elif config['type'] == 'rating':
            st.write(f"**评分范围**: {config['min_value']} - {config['max_value']}")
    
    # 创建任务
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("上一步"):
            st.session_state['config_step'] = 2
            st.rerun()
    
    with col2:
        if st.button("🚀 创建任务", type="primary"):
            if not task_name.strip():
                st.error("请输入任务名称")
                return
            
            try:
                # 保存数据文件
                data_filename = f"task_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
                data_path = os.path.join('data', data_filename)
                
                # 创建data目录
                os.makedirs('data', exist_ok=True)
                
                FileProcessor.save_jsonl(st.session_state['upload_data'], data_path)
                
                # 创建任务
                task_data = {
                    'name': task_name,
                    'description': task_description,
                    'config': {
                        'field_configs': st.session_state['field_configs'],
                        'selected_fields': st.session_state['selected_fields'],
                        'annotation_config': st.session_state['annotation_config'],
                        'base_path': st.session_state.get('base_path', ''),
                        'total_items': len(st.session_state['upload_data'])
                    },
                    'data_path': data_path
                }
                
                task_id = db.create_task(task_data)
                
                st.success(f"✅ 任务创建成功！任务ID: {task_id}")
                
                # 清理session state
                for key in ['upload_data', 'field_configs', 'selected_fields', 'annotation_config', 'config_step', 'base_path']:
                    if key in st.session_state:
                        del st.session_state[key]
                
                st.balloons()
                
                if st.button("开始标注"):
                    st.session_state['selected_task_id'] = task_id
                    st.switch_page("pages/annotation.py")
                
            except Exception as e:
                st.error(f"创建任务失败: {str(e)}")

def annotation_page(db: DatabaseManager, annotator_view=False):
    """标注页面"""
    st.title("📝 数据标注")
    
    user = st.session_state.user
    
    # 根据用户角色获取任务列表
    if annotator_view or user['role'] == 'annotator':
        # 标注者只能看到分配给自己的任务
        assigned_tasks = db.get_user_assigned_tasks(user['id'])
        if not assigned_tasks:
            st.warning("您暂无分配的标注任务，请联系发布者分配任务")
            return
        tasks = assigned_tasks
    else:
        # 发布者可以看到所有任务
        tasks = db.get_all_tasks()
        if not tasks:
            st.warning("暂无可标注的任务，请先创建任务")
            return
    
    # 任务选择器
    task_options = {f"{task['name']} (ID: {task['id'][:8]})": task['id'] for task in tasks}
    
    selected_task_name = st.selectbox(
        "选择要标注的任务",
        list(task_options.keys()),
        help="选择一个任务开始标注"
    )
    
    if not selected_task_name:
        return
    
    task_id = task_options[selected_task_name]
    task = db.get_task(task_id)
    
    if not task:
        st.error("任务不存在")
        return
    
    # 加载任务数据
    try:
        with open(task['data_path'], 'r', encoding='utf-8') as f:
            data = [json.loads(line) for line in f.readlines() if line.strip()]
    except Exception as e:
        st.error(f"加载任务数据失败: {e}")
        return
    
    if not data:
        st.error("任务数据为空")
        return
    
    # 初始化当前索引
    if f'current_index_{task_id}' not in st.session_state:
        st.session_state[f'current_index_{task_id}'] = 0
    
    current_index = st.session_state[f'current_index_{task_id}']
    total_items = len(data)
    
    # 进度显示
    progress = db.get_task_progress(task_id)
    is_current_saved = db.is_annotation_saved(task_id, current_index)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("当前进度", f"{current_index + 1}/{total_items}")
    with col2:
        st.metric("已完成", f"{progress['completed']}/{progress['total']}")
    with col3:
        st.metric("完成率", f"{progress['progress']:.1f}%")
    with col4:
        # 显示当前条目的保存状态
        if is_current_saved:
            st.success("✅ 已保存")
        else:
            st.warning("⚠️ 未保存")
    
    st.progress((current_index + 1) / total_items)
    
    # 显示未保存的条目提示
    if progress['unsaved_indices']:
        unsaved_count = len(progress['unsaved_indices'])
        if unsaved_count <= 10:
            unsaved_display = ', '.join([str(i+1) for i in progress['unsaved_indices']])
            st.info(f"📋 还有 {unsaved_count} 条未保存: 第 {unsaved_display} 条")
        else:
            first_few = ', '.join([str(i+1) for i in progress['unsaved_indices'][:5]])
            st.info(f"📋 还有 {unsaved_count} 条未保存: 第 {first_few} 条等...")
    
    # 任务说明
    annotation_config = task['config']['annotation_config']
    if annotation_config.get('instruction'):
        st.info(f"📋 **标注说明**: {annotation_config['instruction']}")
    
    st.divider()
    
    # 显示当前数据
    current_data = data[current_index]
    field_configs = task['config']['field_configs']
    selected_fields = task['config']['selected_fields']
    base_path = task['config'].get('base_path', '')
    
    # 数据展示区域
    st.subheader(f"📄 数据内容 ({current_index + 1}/{total_items})")
    
    for field in selected_fields:
        if field in current_data:
            config = field_configs[field]
            value = current_data[field]
            
            if config["type"] == "text":
                DataRenderer.render_text(str(value), field)
            elif config["type"] == "code":
                DataRenderer.render_code(str(value), field, config.get("language", "text"))
            elif config["type"] == "image":
                DataRenderer.render_image(str(value), field, base_path)
            elif config["type"] == "pdf":
                DataRenderer.render_pdf(str(value), field, base_path)
            elif config["type"] == "markdown":
                DataRenderer.render_markdown(str(value), field)
    
    st.divider()
    
    # 标注区域
    st.subheader("✏️ 标注内容")
    
    # 加载已有标注
    existing_annotation = db.get_annotation(task_id, current_index)
    
    # 渲染标注表单
    annotation_result = None
    
    if annotation_config['type'] == 'single_choice':
        annotation_result = AnnotationFormGenerator.render_single_choice(
            annotation_config['options'], 
            f"annotation_{task_id}_{current_index}",
            existing_annotation
        )
    elif annotation_config['type'] == 'multiple_choice':
        annotation_result = AnnotationFormGenerator.render_multiple_choice(
            annotation_config['options'], 
            f"annotation_{task_id}_{current_index}",
            existing_annotation
        )
    elif annotation_config['type'] == 'rating':
        annotation_result = AnnotationFormGenerator.render_rating(
            annotation_config['min_value'], 
            annotation_config['max_value'], 
            f"annotation_{task_id}_{current_index}",
            existing_annotation
        )
    elif annotation_config['type'] == 'text_input':
        annotation_result = AnnotationFormGenerator.render_text_input(
            annotation_config.get('placeholder', ''), 
            f"annotation_{task_id}_{current_index}",
            existing_annotation
        )
    
    # 导航和保存按钮
    st.divider()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("⬅️ 上一条", disabled=current_index <= 0):
            st.session_state[f'current_index_{task_id}'] = max(0, current_index - 1)
            st.rerun()
    
    with col2:
        save_button = st.button("💾 保存标注", type="primary")
        if save_button:
            try:
                db.save_annotation(task_id, current_index, annotation_result)
                # 使用session state来显示保存成功消息
                st.session_state[f'save_message_{task_id}_{current_index}'] = {
                    'type': 'success',
                    'message': f"✅ 第 {current_index + 1} 条标注已保存！",
                    'timestamp': pd.Timestamp.now()
                }
                st.rerun()
            except Exception as e:
                st.session_state[f'save_message_{task_id}_{current_index}'] = {
                    'type': 'error', 
                    'message': f"❌ 保存失败: {e}",
                    'timestamp': pd.Timestamp.now()
                }
                st.rerun()
        
        # 显示保存状态消息
        save_msg_key = f'save_message_{task_id}_{current_index}'
        if save_msg_key in st.session_state:
            msg_data = st.session_state[save_msg_key]
            # 检查消息是否是最近3秒内的
            if (pd.Timestamp.now() - msg_data['timestamp']).total_seconds() < 3:
                if msg_data['type'] == 'success':
                    st.success(msg_data['message'])
                else:
                    st.error(msg_data['message'])
            else:
                # 清理过期的消息
                del st.session_state[save_msg_key]
    
    with col3:
        if st.button("➡️ 下一条", disabled=current_index >= total_items - 1):
            st.session_state[f'current_index_{task_id}'] = min(total_items - 1, current_index + 1)
            st.rerun()
    
    with col4:
        st.write("**快速跳转**")
        # 跳转功能
        jump_to = st.number_input(
            "跳转到第几条",
            min_value=1,
            max_value=total_items,
            value=current_index + 1,
            key=f"jump_{task_id}"
        )
        
        col4_1, col4_2 = st.columns(2)
        with col4_1:
            if st.button("🎯 跳转", key=f"jump_btn_{task_id}"):
                st.session_state[f'current_index_{task_id}'] = jump_to - 1
                st.rerun()
        
        with col4_2:
            # 跳转到下一个未保存的条目
            if progress['unsaved_indices'] and st.button("📝 未保存", key=f"next_unsaved_{task_id}"):
                # 找到当前位置之后的第一个未保存条目
                next_unsaved = None
                for idx in progress['unsaved_indices']:
                    if idx > current_index:
                        next_unsaved = idx
                        break
                
                # 如果没有找到后面的，就跳转到第一个未保存的
                if next_unsaved is None and progress['unsaved_indices']:
                    next_unsaved = progress['unsaved_indices'][0]
                
                if next_unsaved is not None:
                    st.session_state[f'current_index_{task_id}'] = next_unsaved
                    st.session_state[f'jump_message_{task_id}'] = f"已跳转到未保存的第 {next_unsaved + 1} 条"
                    st.rerun()
        
        # 显示跳转消息
        jump_msg_key = f'jump_message_{task_id}'
        if jump_msg_key in st.session_state:
            st.info(st.session_state[jump_msg_key])
            del st.session_state[jump_msg_key]

def progress_page(db: DatabaseManager):
    """进度管理页面"""
    st.title("📊 进度管理")
    
    tasks = db.get_all_tasks()
    
    if not tasks:
        st.warning("暂无任务")
        return
    
    # 总体统计
    st.subheader("📈 总体统计")
    
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t['status'] == 'completed'])
    in_progress_tasks = len([t for t in tasks if t['status'] in ['created', 'in_progress']])
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("总任务数", total_tasks)
    with col2:
        st.metric("进行中", in_progress_tasks)
    with col3:
        st.metric("已完成", completed_tasks)
    
    st.divider()
    
    # 任务详细进度
    st.subheader("📋 任务详细进度")
    
    for task in tasks:
        progress = db.get_task_progress(task['id'])
        assignment = db.get_task_assignment(task['id'])
        
        # 标题包含分配信息
        title = f"📝 {task['name']} - {progress['progress']:.1f}% 完成"
        if assignment:
            title += f" (👤 {assignment['assigned_to_name']})"
        
        with st.expander(title):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**描述**: {task['description']}")
                st.write(f"**创建时间**: {task['created_at']}")
                st.write(f"**状态**: {task['status']}")
                
                # 显示分配信息
                if assignment:
                    st.success(f"✅ 已分配给: **{assignment['assigned_to_name']}** (@{assignment['assigned_to_username']})")
                    st.write(f"分配时间: {assignment['assigned_at']}")
                else:
                    st.warning("⚠️ 该任务尚未分配给任何标注者")
                
                if progress['total'] > 0:
                    st.progress(progress['progress'] / 100)
                    st.write(f"标注进度: {progress['completed']}/{progress['total']}")
                    
                    # 显示未保存的条目
                    if progress['unsaved_indices']:
                        unsaved_count = len(progress['unsaved_indices'])
                        if unsaved_count <= 5:
                            unsaved_display = ', '.join([str(i+1) for i in progress['unsaved_indices']])
                            st.warning(f"⚠️ 未保存: 第 {unsaved_display} 条")
                        else:
                            st.warning(f"⚠️ 还有 {unsaved_count} 条未保存")
                    else:
                        st.success("✅ 所有条目已保存")
                else:
                    st.write("暂无数据")
            
            with col2:
                if st.button(f"📝 开始标注", key=f"start_{task['id']}"):
                    st.session_state['selected_task_id'] = task['id']
                    # 这里应该跳转到标注页面
                    st.success("已选择任务，请切换到标注页面")
                
                if progress['completed'] > 0:
                    if st.button(f"📤 导出结果", key=f"export_{task['id']}"):
                        st.session_state['export_task_id'] = task['id']
                        st.success("已选择导出任务，请切换到导出页面")

def export_page(db: DatabaseManager):
    """导出页面"""
    st.title("📤 结果导出")
    
    tasks = db.get_all_tasks()
    
    if not tasks:
        st.warning("暂无任务")
        return
    
    # 任务选择
    task_options = {f"{task['name']} (ID: {task['id'][:8]})": task['id'] for task in tasks}
    
    selected_task_name = st.selectbox(
        "选择要导出的任务",
        list(task_options.keys()),
        help="选择一个任务导出标注结果"
    )
    
    if not selected_task_name:
        return
    
    task_id = task_options[selected_task_name]
    task = db.get_task(task_id)
    
    # 显示任务信息
    progress = db.get_task_progress(task_id)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总数据量", progress['total'])
    with col2:
        st.metric("已标注", progress['completed'])
    with col3:
        st.metric("完成率", f"{progress['progress']:.1f}%")
    
    if progress['completed'] == 0:
        st.warning("该任务还没有标注数据")
        return
    
    st.divider()
    
    # 导出选项
    st.subheader("📋 导出选项")
    
    export_format = st.selectbox(
        "选择导出格式",
        ["json", "jsonl", "csv", "excel"],
        help="选择导出文件的格式"
    )
    
    include_original = st.checkbox(
        "包含原始数据",
        value=True,
        help="是否在导出结果中包含原始待标注数据"
    )
    
    only_completed = st.checkbox(
        "仅导出已完成标注",
        value=False,
        help="只导出已完成标注的数据，未标注的数据将被忽略"
    )
    
    # 预览导出数据
    st.subheader("👀 数据预览")
    
    try:
        # 加载原始数据
        with open(task['data_path'], 'r', encoding='utf-8') as f:
            original_data = [json.loads(line) for line in f.readlines() if line.strip()]
        
        # 获取所有标注
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT data_index, result FROM annotations 
            WHERE task_id = ? AND annotator_id = ?
            ORDER BY data_index
        ''', (task_id, 'user1'))
        
        annotations = {row[0]: json.loads(row[1]) for row in cursor.fetchall()}
        conn.close()
        
        # 构建导出数据
        export_data = []
        
        for i, original_item in enumerate(original_data):
            if only_completed and i not in annotations:
                continue
            
            export_item = {}
            
            if include_original:
                export_item.update(original_item)
            
            export_item['annotation_result'] = annotations.get(i, None)
            export_item['annotation_status'] = 'completed' if i in annotations else 'pending'
            export_item['data_index'] = i
            
            export_data.append(export_item)
        
        # 显示预览
        if export_data:
            st.write(f"**导出数据量**: {len(export_data)} 条")
            
            # 安全地创建预览DataFrame
            try:
                # 清理数据以避免类型冲突
                preview_data = export_data[:10]
                cleaned_preview = []
                for item in preview_data:
                    cleaned_item = {}
                    for key, value in item.items():
                        if isinstance(value, (list, dict)):
                            cleaned_item[key] = str(value)
                        else:
                            cleaned_item[key] = str(value) if value is not None else ""
                    cleaned_preview.append(cleaned_item)
                
                preview_df = pd.DataFrame(cleaned_preview)
                st.dataframe(preview_df, use_container_width=True)
            except Exception as e:
                st.warning(f"数据预览遇到问题: {str(e)}")
                # 降级显示
                st.write("**数据预览（前3条）：**")
                for i, item in enumerate(export_data[:3]):
                    with st.expander(f"第 {i+1} 条数据"):
                        st.json(item)
            
            if len(export_data) > 10:
                st.write(f"... 还有 {len(export_data) - 10} 条数据")
        
        # 导出按钮
        if st.button("📥 下载导出文件", type="primary"):
            if export_format == "json":
                export_content = json.dumps(export_data, ensure_ascii=False, indent=2)
                filename = f"export_{task['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                mime_type = "application/json"
            
            elif export_format == "jsonl":
                export_content = '\n'.join([json.dumps(item, ensure_ascii=False) for item in export_data])
                filename = f"export_{task['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
                mime_type = "application/json"
            
            elif export_format == "csv":
                df = pd.DataFrame(export_data)
                export_content = df.to_csv(index=False, encoding='utf-8')
                filename = f"export_{task['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                mime_type = "text/csv"
            
            elif export_format == "excel":
                df = pd.DataFrame(export_data)
                # 对于Excel，我们需要使用BytesIO
                from io import BytesIO
                buffer = BytesIO()
                df.to_excel(buffer, index=False, engine='openpyxl')
                export_content = buffer.getvalue()
                filename = f"export_{task['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            
            st.download_button(
                label=f"📥 下载 {export_format.upper()} 文件",
                data=export_content,
                file_name=filename,
                mime=mime_type
            )
            
            st.success(f"✅ 导出完成！文件包含 {len(export_data)} 条数据")
    
    except Exception as e:
        st.error(f"导出失败: {str(e)}")

if __name__ == "__main__":
    main()
