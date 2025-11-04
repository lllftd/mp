# 数据库插入数据格式说明

## 插入到 `tweets` 表的数据格式

### Python 字典格式（crawler.py 中构建）

```python
tweet = {
    'tweets_title': '转述后的标题',           # 字符串，最大120字符
    'tweets_content': '转述后的完整内容',    # 字符串，最大2000字符
    'tweets_describe': '转述后的描述',        # 字符串，最大400字符（截取前200字符）
    'tweets_img': '["path1.jpg", "path2.jpg"]',  # JSON字符串，最大300字符
    'tweets_type_pid': 5,                    # 整数，父类型ID
    'tweets_type_cid': '10,42',             # 字符串，子类型ID（逗号分隔）
    'tweets_user': '随机生成的用户名'        # 字符串，最大20字符（如：格斯、人参、参宿三等）
}
```

### SQL INSERT 语句格式

实际执行的SQL语句格式：

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

### 实际示例

**Python字典示例：**
```python
{
    'tweets_title': '深圳美食探店：这家店的招牌菜太香了！',
    'tweets_content': '今天去了一家很不错的餐厅，他们家的招牌菜真的很棒...',
    'tweets_describe': '今天去了一家很不错的餐厅，他们家的招牌菜真的很棒...',
    'tweets_img': '["saved/20251104233911/图片/0000_6874afe200000000170357db_1.jpg"]',
    'tweets_type_pid': 5,
    'tweets_type_cid': '10,42',
    'tweets_user': '格斯'  # 或 '人参123'、'参宿三'、'白金之星' 等随机生成
}
```

**对应的SQL执行：**
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
    '深圳美食探店：这家店的招牌菜太香了！',
    '今天去了一家很不错的餐厅，他们家的招牌菜真的很棒...',
    '今天去了一家很不错的餐厅，他们家的招牌菜真的很棒...',
    '["saved/20251104233911/图片/0000_6874afe200000000170357db_1.jpg"]',
    5,
    '10,42',
    '格斯'
);
```

## 字段说明

| 字段名 | 类型 | 必填 | 说明 | 限制 |
|--------|------|------|------|------|
| `tweets_title` | VARCHAR | ✅ | 标题（AI转述后的） | 最大120字符 |
| `tweets_content` | TEXT | ✅ | 完整内容（AI转述后的） | 最大2000字符 |
| `tweets_describe` | VARCHAR | ✅ | 描述/简介 | 最大400字符 |
| `tweets_img` | VARCHAR | ✅ | 图片路径（JSON数组） | 最大300字符 |
| `tweets_type_pid` | INT | ✅ | 父类型ID | - |
| `tweets_type_cid` | VARCHAR | ✅ | 子类型ID（逗号分隔） | 最大70字符 |
| `tweets_user` | VARCHAR | ❌ | 用户名（随机生成） | 最大20字符 |

## 用户名生成规则

`tweets_user` 字段会从以下5个类别中随机选择：
- **战锤40k人物名**：如 "格斯"、"格里菲斯"、"但丁"
- **JOJO替身名**：如 "白金之星"、"世界"、"疯狂钻石"
- **中药名**：如 "人参"、"黄芪"、"当归"
- **星体名**：如 "参宿"、"参宿三"、"天狼"
- **剑风传奇角色名**：如 "格斯"、"格里菲斯"、"卡思嘉"

30%概率会添加数字后缀（1-999），例如：`人参123`、`参宿三456`

## 图片字段格式

`tweets_img` 字段存储为 **JSON数组字符串**，例如：
```json
["saved/20251104233911/图片/0000_6874afe200000000170357db_1.jpg", "saved/20251104233911/图片/0000_6874afe200000000170357db_2.jpg"]
```

## 批量插入

爬虫会收集所有数据后，通过 `batch_insert_tweets()` 函数批量插入，每次插入一条，返回插入的ID。

