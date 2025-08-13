#!/usr/bin/env python3
"""
数据库重置工具
当遇到数据库结构不兼容的问题时，使用此脚本重建数据库
"""

import os
import sqlite3
import shutil
from datetime import datetime

def backup_database():
    """备份现有数据库"""
    db_path = 'annotation_platform.db'
    if os.path.exists(db_path):
        backup_name = f'annotation_platform_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        shutil.copy2(db_path, backup_name)
        print(f"✅ 已备份数据库到: {backup_name}")
        return backup_name
    return None

def reset_database():
    """重置数据库结构"""
    db_path = 'annotation_platform.db'
    
    # 备份现有数据库
    backup_file = backup_database()
    
    # 删除现有数据库
    if os.path.exists(db_path):
        os.remove(db_path)
        print("🗑️ 已删除旧数据库")
    
    # 创建新数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建任务表
    cursor.execute('''
        CREATE TABLE tasks (
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
        CREATE TABLE annotations (
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
    
    # 创建用户表
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
    
    # 创建任务分配表
    cursor.execute('''
        CREATE TABLE task_assignments (
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
    
    print("✅ 新数据库创建完成")
    
    if backup_file:
        print(f"\n📝 注意事项:")
        print(f"   - 原数据库已备份为: {backup_file}")
        print(f"   - 所有用户需要重新注册")
        print(f"   - 所有任务需要重新创建")
        print(f"   - 如需恢复旧数据，请将备份文件重命名为 annotation_platform.db")

if __name__ == "__main__":
    print("🔧 数据库重置工具")
    print("=" * 50)
    
    confirm = input("⚠️  警告: 此操作将删除所有现有数据！\n是否继续? (输入 'yes' 确认): ")
    
    if confirm.lower() == 'yes':
        reset_database()
        print("\n🎉 数据库重置完成！现在可以重新启动应用。")
    else:
        print("❌ 操作已取消")
