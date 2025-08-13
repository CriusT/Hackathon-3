# 数据标注平台 API 文档

## 概述

本文档描述了Streamlit数据标注平台的内部API接口和数据模型。虽然这是一个单体Streamlit应用，但我们设计了清晰的模块化接口，便于后续扩展为微服务架构。

## 核心模块 API

### 1. DatabaseManager 类

数据库管理类，负责所有数据持久化操作。

#### 1.1 任务管理 API

##### create_task()
```python
def create_task(self, task_data: Dict) -> str
```
**功能**: 创建新的标注任务
**参数**:
- `task_data`: 任务数据字典
  ```python
  {
      "name": "任务名称",
      "description": "任务描述", 
      "config": {
          "field_configs": {...},      # 字段配置
          "selected_fields": [...],    # 选中字段
          "annotation_config": {...},  # 标注配置
          "base_path": "文件基础路径",
          "total_items": 100           # 数据总量
      },
      "data_path": "data/task_data.jsonl"  # 数据文件路径
  }
  ```
**返回**: 任务ID (UUID字符串)
**异常**: 数据库操作异常

##### get_task()
```python
def get_task(self, task_id: str) -> Optional[Dict]
```
**功能**: 获取指定任务信息
**参数**:
- `task_id`: 任务ID
**返回**: 任务信息字典或None
```python
{
    "id": "uuid",
    "name": "任务名称",
    "description": "任务描述",
    "config": {...},
    "status": "created|in_progress|completed",
    "created_at": "2024-01-01 12:00:00",
    "data_path": "data/task_data.jsonl"
}
```

##### get_all_tasks()
```python
def get_all_tasks(self) -> List[Dict]
```
**功能**: 获取所有任务列表
**返回**: 任务信息字典列表（按创建时间倒序）

#### 1.2 标注管理 API

##### save_annotation()
```python
def save_annotation(self, task_id: str, data_index: int, result: Any)
```
**功能**: 保存或更新标注结果
**参数**:
- `task_id`: 任务ID
- `data_index`: 数据条目索引
- `result`: 标注结果（支持任意JSON可序列化类型）

**标注结果格式示例**:
```python
# 单选结果
result = "True"

# 多选结果
result = ["选项1", "选项3"]

# 评分结果
result = 8

# 文本输入结果
result = "这是标注的文本内容"
```

##### get_annotation()
```python
def get_annotation(self, task_id: str, data_index: int) -> Optional[Dict]
```
**功能**: 获取指定数据的标注结果
**参数**:
- `task_id`: 任务ID
- `data_index`: 数据条目索引
**返回**: 标注结果或None

##### get_task_progress()
```python
def get_task_progress(self, task_id: str) -> Dict
```
**功能**: 获取任务标注进度
**返回**: 进度信息字典
```python
{
    "total": 100,        # 总数据量
    "completed": 45,     # 已完成数量
    "progress": 45.0     # 完成百分比
}
```

### 2. FileProcessor 类

文件处理工具类，处理各种文件格式。

#### 2.1 JSONL 处理

##### load_jsonl()
```python
@staticmethod
def load_jsonl(file_content: str) -> List[Dict]
```
**功能**: 解析JSONL格式内容
**参数**:
- `file_content`: JSONL文件内容字符串
**返回**: 数据对象列表
**异常**: JSON格式错误时抛出异常并在UI显示错误信息

##### save_jsonl()
```python
@staticmethod
def save_jsonl(data: List[Dict], file_path: str)
```
**功能**: 保存数据为JSONL格式
**参数**:
- `data`: 数据对象列表
- `file_path`: 保存路径

#### 2.2 文件验证

##### validate_file_paths()
```python
@staticmethod
def validate_file_paths(data: List[Dict], base_path: str = '') -> Dict[str, List[str]]
```
**功能**: 验证数据中的文件路径是否存在
**参数**:
- `data`: 数据对象列表
- `base_path`: 文件基础路径
**返回**: 验证结果
```python
{
    "missing": ["第1条数据的image字段: path/to/missing.jpg"],
    "invalid": []
}
```

### 3. DataRenderer 类

数据渲染器，负责在UI中显示不同类型的数据。

#### 3.1 渲染方法

##### render_text()
```python
@staticmethod
def render_text(data: str, field_name: str)
```
**功能**: 渲染文本数据
**参数**:
- `data`: 文本内容
- `field_name`: 字段名称

##### render_code()
```python
@staticmethod
def render_code(data: str, field_name: str, language: str = 'sql')
```
**功能**: 渲染代码数据（带语法高亮）
**参数**:
- `data`: 代码内容
- `field_name`: 字段名称  
- `language`: 编程语言（sql, python, javascript, json, text）

##### render_image()
```python
@staticmethod
def render_image(file_path: str, field_name: str, base_path: str = '')
```
**功能**: 渲染图片数据
**参数**:
- `file_path`: 图片文件路径
- `field_name`: 字段名称
- `base_path`: 基础路径

##### render_pdf()
```python
@staticmethod
def render_pdf(file_path: str, field_name: str, base_path: str = '')
```
**功能**: 渲染PDF文件（提供下载链接）
**参数**:
- `file_path`: PDF文件路径
- `field_name`: 字段名称
- `base_path`: 基础路径

##### render_markdown()
```python
@staticmethod
def render_markdown(data: str, field_name: str)
```
**功能**: 渲染Markdown数据
**参数**:
- `data`: Markdown内容
- `field_name`: 字段名称

### 4. AnnotationFormGenerator 类

标注表单生成器，根据配置动态生成标注界面。

#### 4.1 表单生成方法

##### render_single_choice()
```python
@staticmethod
def render_single_choice(options: List[str], key: str, default_value=None)
```
**功能**: 生成单选表单
**参数**:
- `options`: 选项列表
- `key`: Streamlit组件唯一标识
- `default_value`: 默认值
**返回**: 选中的选项字符串

##### render_multiple_choice()
```python
@staticmethod
def render_multiple_choice(options: List[str], key: str, default_value=None)
```
**功能**: 生成多选表单
**参数**:
- `options`: 选项列表
- `key`: Streamlit组件唯一标识
- `default_value`: 默认值列表
**返回**: 选中的选项列表

##### render_rating()
```python
@staticmethod
def render_rating(min_val: int = 1, max_val: int = 10, key: str = None, default_value=None)
```
**功能**: 生成评分表单
**参数**:
- `min_val`: 最小值
- `max_val`: 最大值
- `key`: Streamlit组件唯一标识
- `default_value`: 默认值
**返回**: 评分数值

##### render_text_input()
```python
@staticmethod
def render_text_input(placeholder: str = "请输入标注内容", key: str = None, default_value=None)
```
**功能**: 生成文本输入表单
**参数**:
- `placeholder`: 占位符文本
- `key`: Streamlit组件唯一标识
- `default_value`: 默认值
**返回**: 输入的文本字符串

## 数据模型

### 1. 任务配置模型

```python
# 字段配置
field_config = {
    "field_name": {
        "type": "text|image|code|pdf|markdown",
        "language": "sql|python|javascript|json|text"  # 仅code类型需要
    }
}

# 标注配置
annotation_config = {
    "type": "single_choice|multiple_choice|rating|text_input",
    "options": ["选项1", "选项2"],  # 单选/多选时需要
    "min_value": 1,              # 评分时需要
    "max_value": 10,             # 评分时需要
    "placeholder": "输入提示",    # 文本输入时需要
    "instruction": "标注说明"
}
```

### 2. 数据库表结构

#### tasks 表
```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,          -- 任务ID (UUID)
    name TEXT NOT NULL,          -- 任务名称
    description TEXT,            -- 任务描述
    config TEXT,                 -- 任务配置 (JSON)
    status TEXT DEFAULT 'created', -- 任务状态
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_path TEXT               -- 数据文件路径
);
```

#### annotations 表
```sql
CREATE TABLE annotations (
    id TEXT PRIMARY KEY,                    -- 标注ID (UUID)
    task_id TEXT,                          -- 任务ID
    data_index INTEGER,                    -- 数据条目索引
    result TEXT,                           -- 标注结果 (JSON)
    status TEXT DEFAULT 'pending',         -- 标注状态
    annotator_id TEXT DEFAULT 'user1',     -- 标注员ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks (id)
);
```

#### users 表
```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,           -- 用户ID (UUID)
    username TEXT UNIQUE NOT NULL, -- 用户名
    role TEXT DEFAULT 'annotator', -- 用户角色
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 页面路由

### 1. 主要页面

| 页面 | 路径 | 功能描述 |
|------|------|----------|
| 首页 | `/` | 系统概览和统计信息 |
| 任务配置 | `/config` | 创建和配置标注任务 |
| 数据标注 | `/annotation` | 执行标注工作 |
| 进度管理 | `/progress` | 查看标注进度 |
| 结果导出 | `/export` | 导出标注结果 |

### 2. Session State 管理

```python
# 任务配置相关
st.session_state['config_step']          # 配置步骤 (0-3)
st.session_state['upload_data']          # 上传的数据
st.session_state['field_configs']       # 字段配置
st.session_state['annotation_config']   # 标注配置

# 标注相关
st.session_state[f'current_index_{task_id}']  # 当前标注索引
st.session_state['selected_task_id']          # 选中的任务ID

# 其他
st.session_state['base_path']            # 文件基础路径
```

## 错误处理

### 1. 文件处理错误

```python
# JSONL格式错误
try:
    data = json.loads(line)
except json.JSONDecodeError as e:
    st.error(f"第 {i+1} 行JSON格式错误: {e}")
    return []

# 文件不存在错误
if not os.path.exists(full_path):
    st.error(f"文件不存在: {full_path}")
```

### 2. 数据库操作错误

```python
try:
    # 数据库操作
    cursor.execute(sql, params)
    conn.commit()
except Exception as e:
    st.error(f"数据库操作失败: {str(e)}")
    conn.rollback()
finally:
    conn.close()
```

### 3. UI操作错误

```python
# 表单验证
if not task_name.strip():
    st.error("请输入任务名称")
    return

# 数据验证
if not selected_fields:
    st.warning("请至少选择一个字段")
    return
```

## 性能优化

### 1. 数据库优化

- 使用索引加速查询
- 连接池管理
- 批量操作减少I/O

### 2. 文件处理优化

- 大文件分块读取
- 缓存常用文件
- 异步文件操作

### 3. UI渲染优化

- 延迟加载大型文件
- 分页显示大量数据
- 缓存渲染结果

## 扩展接口

为了便于后续扩展为微服务架构，我们预留了以下接口：

### 1. REST API 接口设计

```python
# 任务管理
POST   /api/v1/tasks              # 创建任务
GET    /api/v1/tasks              # 获取任务列表
GET    /api/v1/tasks/{task_id}    # 获取任务详情
PUT    /api/v1/tasks/{task_id}    # 更新任务
DELETE /api/v1/tasks/{task_id}    # 删除任务

# 标注管理
POST   /api/v1/annotations        # 提交标注
GET    /api/v1/annotations        # 获取标注列表
PUT    /api/v1/annotations/{id}   # 更新标注
GET    /api/v1/tasks/{task_id}/progress  # 获取任务进度

# 文件管理
POST   /api/v1/files              # 上传文件
GET    /api/v1/files/{file_id}    # 获取文件信息
GET    /api/v1/files/{file_id}/content  # 获取文件内容

# 导出管理
POST   /api/v1/exports            # 创建导出任务
GET    /api/v1/exports/{export_id}  # 获取导出状态
GET    /api/v1/exports/{export_id}/download  # 下载导出文件
```

### 2. WebSocket 事件接口

```python
# 客户端 -> 服务端
{
    "event": "join_task",
    "data": {"task_id": "uuid"}
}

{
    "event": "annotation_update", 
    "data": {
        "task_id": "uuid",
        "data_index": 1,
        "result": "annotation_result"
    }
}

# 服务端 -> 客户端
{
    "event": "progress_update",
    "data": {
        "task_id": "uuid", 
        "progress": {
            "total": 100,
            "completed": 45,
            "progress": 45.0
        }
    }
}
```

这个API文档为当前的Streamlit原型和未来的微服务架构都提供了清晰的接口规范。
