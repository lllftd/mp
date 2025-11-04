# 数据库插入数据格式说明

## 数据库信息

- **IP**: 47.121.133.201
- **端口**: 3306
- **用户名**: root
- **密码**: adminMysql
- **数据库名**: jxwq_end
- **表名**: tweets

## tweets 表结构

```sql
CREATE TABLE `tweets` (
    `id`                 int           NOT NULL AUTO_INCREMENT COMMENT '主键',
    `tweets_type_pid`    int           NOT NULL COMMENT '推文类型 - 父id',
    `tweets_type_cid`    varchar(70)   NOT NULL COMMENT '推文类型 - 子id 可以有多个 逗号隔开',
    `tweets_title`       varchar(120)  NOT NULL COMMENT '推文标题',
    `tweets_user`        varchar(20) COMMENT '推文作者',
    `tweets_describe`    varchar(400)  NOT NULL COMMENT '推文简介',
    `tweets_img`         varchar(300)  NOT NULL COMMENT '推文图片',
    `tweets_content`     varchar(2000) NOT NULL COMMENT '推文内容',
    `like_num`           int         DEFAULT 0 COMMENT '点赞数',
    `collect_num`        int         DEFAULT 0 COMMENT '收藏数',
    `browse_num`         int         DEFAULT 0 COMMENT '浏览数',
    `create_time`        datetime    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time`        datetime    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `create_user`        varchar(10) DEFAULT NULL COMMENT '创建人',
    `client_create_user` varchar(10) DEFAULT NULL COMMENT '小程序创建人',
    `update_user`        varchar(10) DEFAULT NULL COMMENT '修改人',
    PRIMARY KEY (`id`)
) ENGINE = InnoDB
  AUTO_INCREMENT = 1
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci COMMENT ='推文表';
```

## 插入到 `tweets` 表的数据格式

### Python 字典格式（crawler.py 中构建）

```python
tweet = {
    'tweets_title': '转述后的标题',           # 字符串，最大120字符
    'tweets_content': '转述后的完整内容',    # 字符串，最大2000字符
    'tweets_describe': '转述后的描述',        # 字符串，最大400字符（截取前200字符）
    'tweets_img': '["path1.jpg", "path2.jpg"]',  # JSON字符串，最大300字符
    'tweets_type_pid': 5,                    # 整数，父类型ID（美食）
    'tweets_type_cid': '10,42',             # 字符串，子类型ID（逗号分隔）
    'tweets_user': '随机生成的用户名'        # 字符串，最大20字符
}
```

### SQL INSERT 语句格式

实际执行的SQL语句格式（使用参数化查询）：

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

### 示例数据

**示例 INSERT 语句：**
```sql
INSERT INTO `tweets` VALUES (
    1,                              -- id (自增)
    5,                              -- tweets_type_pid (美食)
    '10,42',                        -- tweets_type_cid (潮汕菜, 人均100至200)
    '潮香四海',                      -- tweets_title
    '正正',                          -- tweets_user
    ' 南山大道1112-7号',             -- tweets_describe
    '["图片url1","图片url2"]',       -- tweets_img (JSON数组格式)
    '招牌蚝仔烙，卤水拼盘，五仁嫩豆腐，避风塘炒蟹',  -- tweets_content
    6,                              -- like_num
    0,                              -- collect_num
    9,                              -- browse_num
    '2024-09-21 00:42:45',         -- create_time
    '2025-01-22 06:00:40',          -- update_time
    '1',                            -- create_user
    NULL,                           -- client_create_user
    '1'                             -- update_user
);
```

**Python字典对应示例：**
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

## 字段说明

| 字段名 | 类型 | 必填 | 说明 | 限制 |
|--------|------|------|------|------|
| `id` | INT | ❌ | 主键（自增） | AUTO_INCREMENT |
| `tweets_type_pid` | INT | ✅ | 父类型ID（美食=5） | - |
| `tweets_type_cid` | VARCHAR(70) | ✅ | 子类型ID（逗号分隔） | 最大70字符 |
| `tweets_title` | VARCHAR(120) | ✅ | 标题（AI转述后的） | 最大120字符 |
| `tweets_user` | VARCHAR(20) | ❌ | 用户名（随机生成） | 最大20字符 |
| `tweets_describe` | VARCHAR(400) | ✅ | 描述/简介 | 最大400字符 |
| `tweets_img` | VARCHAR(300) | ✅ | 图片路径（JSON数组） | 最大300字符 |
| `tweets_content` | VARCHAR(2000) | ✅ | 完整内容（AI转述后的） | 最大2000字符 |
| `like_num` | INT | ❌ | 点赞数 | 默认0 |
| `collect_num` | INT | ❌ | 收藏数 | 默认0 |
| `browse_num` | INT | ❌ | 浏览数 | 默认0 |
| `create_time` | DATETIME | ❌ | 创建时间 | 默认CURRENT_TIMESTAMP |
| `update_time` | DATETIME | ❌ | 更新时间 | 默认CURRENT_TIMESTAMP ON UPDATE |
| `create_user` | VARCHAR(10) | ❌ | 创建人 | 最大10字符 |
| `client_create_user` | VARCHAR(10) | ❌ | 小程序创建人 | 最大10字符 |
| `update_user` | VARCHAR(10) | ❌ | 修改人 | 最大10字符 |

## 推文类型说明

### 父类型
- **ID**: 5
- **名称**: 美食

### 子类型（父ID=5）
所有子类型的父ID都是5，包括：
- 6: 川菜
- 8: 淮扬菜
- 9: 杭帮菜
- 10: 潮汕菜
- 11: 烧烤
- 12: 粤菜
- 13: 德国菜
- 14: 日本料理
- 15: 法国菜
- 16: 韩国料理
- 17: 新疆菜
- 18: 湘菜
- 19: 农家菜
- 20: 火锅
- 21: 咖啡厅
- 22: 自助餐
- 23: 鱼鲜
- 24: 东北菜
- 25: 私房菜
- 26: 东南亚菜
- 27: 特色菜
- 28: 创意菜
- 29: 北京菜
- 30: 家常菜
- 31: 茶餐厅
- 32: 小龙虾
- 33: 素食
- 34: 小吃快餐
- 35: 面包甜点
- 36: 面馆
- 37: 大排档
- 38: 西餐
- 39: 云南菜
- 40: 西北菜
- 41: 人均50至100
- 42: 人均100至200
- 43: 人均200至300
- 44: 人均300以上
- 45: 人均50元以内

### 子类型使用示例
- 单个子类型：`'10'` (潮汕菜)
- 多个子类型：`'10,42'` (潮汕菜 + 人均100至200)
- 多个子类型：`'10,12,42'` (潮汕菜 + 粤菜 + 人均100至200)

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

**注意**：
- 必须是有效的JSON数组格式
- 字符串长度不能超过300字符
- 如果图片路径过长，可能会被截断

## 批量插入

爬虫会收集所有数据后，通过 `batch_insert_tweets()` 函数批量插入，每次插入一条，返回插入的ID。

## 默认配置

当前默认配置（可在 `config.py` 或 `.env` 文件中修改）：
- `DEFAULT_TYPE_PID`: 5 (美食)
- `DEFAULT_TYPE_CID`: '10,42' (潮汕菜 + 人均100至200)


