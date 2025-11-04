# SQL插入格式验证

## 实际插入的数据格式

### 1. Python字典格式（crawler.py构建）

```python
tweet = {
    'tweets_title': 'AI转述后的标题',
    'tweets_content': 'AI转述后的完整内容',
    'tweets_describe': 'AI转述后的描述（前200字符）',
    'tweets_img': '["saved/20251104233911/图片/0000_6874afe200000000170357db_1.jpg"]',
    'tweets_type_pid': 5,  # 从Config.DEFAULT_TYPE_PID读取（必须是环境变量）
    'tweets_type_cid': '10,42',  # 从Config.DEFAULT_TYPE_CID读取（必须是环境变量）
    'tweets_user': '格斯'  # 从随机用户名生成器生成
}
```

### 2. SQL INSERT语句（batch_upload_tweets.py生成）

**动态生成的SQL：**
```sql
INSERT INTO tweets (
    tweets_title, 
    tweets_content, 
    tweets_describe, 
    tweets_img, 
    tweets_type_pid, 
    tweets_type_cid, 
    tweets_user
) VALUES (
    :tweets_title,
    :tweets_content,
    :tweets_describe,
    :tweets_img,
    :tweets_type_pid,
    :tweets_type_cid,
    :tweets_user
)
```

**参数化查询的参数：**
```python
params = {
    'tweets_title': 'AI转述后的标题',
    'tweets_content': 'AI转述后的完整内容',
    'tweets_describe': 'AI转述后的描述（前200字符）',
    'tweets_img': '["saved/20251104233911/图片/0000_6874afe200000000170357db_1.jpg"]',
    'tweets_type_pid': 5,
    'tweets_type_cid': '10,42',
    'tweets_user': '格斯'
}
```

### 3. 实际执行的SQL（参数替换后）

```sql
INSERT INTO tweets (
    tweets_title, 
    tweets_content, 
    tweets_describe, 
    tweets_img, 
    tweets_type_pid, 
    tweets_type_cid, 
    tweets_user
) VALUES (
    'AI转述后的标题',
    'AI转述后的完整内容',
    'AI转述后的描述（前200字符）',
    '["saved/20251104233911/图片/0000_6874afe200000000170357db_1.jpg"]',
    5,
    '10,42',
    '格斯'
);
```

### 4. 字段说明

| 字段 | 值 | 类型 | 说明 |
|------|-----|------|------|
| `tweets_title` | AI转述后的标题 | VARCHAR(120) | 必填 |
| `tweets_content` | AI转述后的完整内容 | VARCHAR(2000) | 必填 |
| `tweets_describe` | AI转述后的描述（前200字符） | VARCHAR(400) | 必填 |
| `tweets_img` | JSON数组字符串 | VARCHAR(300) | 必填 |
| `tweets_type_pid` | 5 | INT | 必填，从环境变量读取 |
| `tweets_type_cid` | '10,42' | VARCHAR(70) | 必填，从环境变量读取 |
| `tweets_user` | 随机生成 | VARCHAR(20) | 可选，随机生成 |

### 5. 重要变化

**配置变化：**
- `DEFAULT_TYPE_PID` 和 `DEFAULT_TYPE_CID` 现在**没有默认值**
- 必须通过环境变量或 `.env` 文件配置
- 如果未配置，值为 `None`，会导致插入失败

**使用方法：**
在 `.env` 文件中必须配置：
```env
DEFAULT_TYPE_PID=5
DEFAULT_TYPE_CID=10,42
```

