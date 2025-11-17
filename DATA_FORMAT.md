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
    `tweets_title`       text          NOT NULL COMMENT '推文标题（餐厅名称）',
    `tweets_user`        varchar(20) COMMENT '推文作者',
    `tweets_describe`    text          NOT NULL COMMENT '推文简介（餐厅地址）',
    `tweets_img`         varchar(300)  NOT NULL COMMENT '推文图片（JSON数组）',
    `tweets_content`     text          NOT NULL COMMENT '推文内容（转述后的描述）',
    `tweets_location`     varchar(50)  DEFAULT NULL COMMENT '城市名称（如：深圳、上海）',
    `tweets_location_code` varchar(20) DEFAULT NULL COMMENT '城市代码（可选）',
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
    'tweets_title': '餐厅名称',                    # 字符串，无长度限制（餐厅名）
    'tweets_content': '转述后的完整内容',          # 字符串，无长度限制（小红书转述后的描述）
    'tweets_describe': '餐厅地址',                 # 字符串，无长度限制（高德API返回的地址）
    'tweets_img': '["path1.jpg", "path2.jpg"]',    # JSON字符串，最大300字符（图片URL数组）
    'tweets_type_pid': 5,                          # 整数，父类型ID（美食）
    'tweets_type_cid': '10,42',                    # 字符串，子类型ID（逗号分隔）
    'tweets_user': '随机生成的用户名',              # 字符串，最大20字符
    'tweets_location': '深圳',                      # 字符串，最大50字符（城市名称，可选）
    'like_num': 50,                                 # 整数，点赞数（随机生成）
    'collect_num': 10,                              # 整数，收藏数（随机生成）
    'browse_num': 200                               # 整数，浏览数（随机生成）
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
    tweets_user,
    tweets_location,
    like_num,
    collect_num,
    browse_num
) VALUES (
    :tweets_title,
    :tweets_content,
    :tweets_describe,
    :tweets_img,
    :tweets_type_pid,
    :tweets_type_cid,
    :tweets_user,
    :tweets_location,
    :like_num,
    :collect_num,
    :browse_num
)
```

### 示例数据

**示例 INSERT 语句：**
```sql
INSERT INTO `tweets` (
    `tweets_type_pid`,
    `tweets_type_cid`,
    `tweets_title`,
    `tweets_user`,
    `tweets_describe`,
    `tweets_img`,
    `tweets_content`,
    `tweets_location`,
    `like_num`,
    `collect_num`,
    `browse_num`
) VALUES (
    5,                              -- tweets_type_pid (美食)
    '10,42',                        -- tweets_type_cid (潮汕菜, 人均100至200)
    '潮香四海',                      -- tweets_title (餐厅名称)
    '正正',                          -- tweets_user (随机生成)
    '广东省深圳市南山区南山大道1112-7号',  -- tweets_describe (高德API地址)
    '["https://sns-img-qc.xhscdn.com/xxx.jpg"]',  -- tweets_img (JSON数组格式)
    '招牌蚝仔烙，卤水拼盘，五仁嫩豆腐，避风塘炒蟹',  -- tweets_content (转述后的描述)
    '深圳',                          -- tweets_location (城市名称)
    50,                             -- like_num (随机生成)
    10,                             -- collect_num (随机生成)
    200                             -- browse_num (随机生成)
);
```

**Python字典对应示例：**
```python
{
    'tweets_title': '潮香四海',                                    # 餐厅名称（来自AI提取或高德API）
    'tweets_content': '招牌蚝仔烙，卤水拼盘，五仁嫩豆腐，避风塘炒蟹',  # 转述后的描述（小红书内容）
    'tweets_describe': '广东省深圳市南山区南山大道1112-7号',      # 餐厅地址（高德API返回的完整地址）
    'tweets_img': '["https://sns-img-qc.xhscdn.com/xxx.jpg"]',    # 图片URL（小红书原帖图片）
    'tweets_type_pid': 5,                                          # 父类型ID（美食）
    'tweets_type_cid': '10,42',                                    # 子类型ID（潮汕菜, 人均100至200）
    'tweets_user': '格斯',                                         # 随机生成的用户名
    'tweets_location': '深圳',                                     # 城市名称（从高德API或地址中提取）
    'like_num': 50,                                                # 点赞数（随机生成：5-100）
    'collect_num': 10,                                             # 收藏数（随机生成：2-50）
    'browse_num': 200                                              # 浏览数（随机生成：50-500）
}
```

## 字段说明

| 字段名 | 类型 | 必填 | 说明 | 限制 |
|--------|------|------|------|------|
| `id` | INT | ❌ | 主键（自增） | AUTO_INCREMENT |
| `tweets_type_pid` | INT | ✅ | 父类型ID（美食=5） | - |
| `tweets_type_cid` | VARCHAR(70) | ✅ | 子类型ID（逗号分隔，如：10,42） | 最大70字符 |
| `tweets_title` | TEXT | ✅ | 标题（餐厅名称） | 无长度限制 |
| `tweets_user` | VARCHAR(20) | ❌ | 用户名（随机生成） | 最大20字符 |
| `tweets_describe` | TEXT | ✅ | 简介（餐厅地址，高德API返回） | 无长度限制 |
| `tweets_img` | VARCHAR(300) | ✅ | 图片（JSON数组格式，小红书原帖图片URL） | 最大300字符 |
| `tweets_content` | TEXT | ✅ | 内容（转述后的描述，小红书内容） | 无长度限制 |
| `tweets_location` | VARCHAR(50) | ❌ | 城市名称（如：深圳、上海） | 最大50字符 |
| `tweets_location_code` | VARCHAR(20) | ❌ | 城市代码（可选，暂未使用） | 最大20字符 |
| `like_num` | INT | ❌ | 点赞数（随机生成：5-100） | 默认0 |
| `collect_num` | INT | ❌ | 收藏数（随机生成：2-50） | 默认0 |
| `browse_num` | INT | ❌ | 浏览数（随机生成：50-500） | 默认0 |
| `create_time` | DATETIME | ❌ | 创建时间 | 默认CURRENT_TIMESTAMP |
| `update_time` | DATETIME | ❌ | 更新时间 | 默认CURRENT_TIMESTAMP ON UPDATE |
| `create_user` | VARCHAR(10) | ❌ | 创建人 | 最大10字符 |
| `client_create_user` | VARCHAR(10) | ❌ | 小程序创建人 | 最大10字符 |
| `update_user` | VARCHAR(10) | ❌ | 修改人 | 最大10字符 |

### 字段映射说明

- **`tweets_title`**: 餐厅名称（来自AI提取或高德API）
- **`tweets_content`**: 小红书转述后的描述（使用AI对小红书帖子内容进行转述）
- **`tweets_describe`**: 餐厅地址（优先使用高德API返回的完整地址，格式：省+市+区县+详细地址）
- **`tweets_location`**: 城市名称（优先使用高德API返回的`cityname`字段，如"深圳市"→"深圳"；如果API未返回，则从地址中提取；如果无法提取，则使用默认城市）
- **`tweets_img`**: 图片URL（直接使用小红书原帖图片，JSON数组格式）

## 推文类型说明

### 父类型
- **ID**: 5
- **名称**: 美食

### 子类型（父ID=5）

所有子类型的父ID都是5（美食），共114个子类型。

#### 菜系分类（ID: 6-40）

| ID | 名称 | ID | 名称 |
|----|------|-----|------|
| 6 | 川菜 | 23 | 鱼鲜 |
| 8 | 淮扬菜 | 24 | 东北菜 |
| 9 | 杭帮菜 | 25 | 私房菜 |
| 10 | 潮汕菜 | 26 | 东南亚菜 |
| 11 | 烧烤 | 27 | 特色菜 |
| 12 | 粤菜 | 28 | 创意菜 |
| 13 | 德国菜 | 29 | 北京菜 |
| 14 | 日本料理 | 30 | 家常菜 |
| 15 | 法国菜 | 31 | 茶餐厅 |
| 16 | 韩国料理 | 32 | 小龙虾 |
| 17 | 新疆菜 | 33 | 素食 |
| 18 | 湘菜 | 34 | 小吃快餐 |
| 19 | 农家菜 | 35 | 面包甜点 |
| 20 | 火锅 | 36 | 面馆 |
| 21 | 咖啡厅 | 37 | 大排档 |
| 22 | 自助餐 | 38 | 西餐 |
| - | - | 39 | 云南菜 |
| - | - | 40 | 西北菜 |

#### 补充菜系（ID: 46-64）

| ID | 名称 | ID | 名称 |
|----|------|-----|------|
| 46 | 意大利菜 | 56 | 鲁菜 |
| 47 | 泰国菜 | 57 | 闽菜 |
| 48 | 越南菜 | 58 | 豫菜 |
| 49 | 印度菜 | 59 | 赣菜 |
| 50 | 墨西哥菜 | 60 | 鄂菜 |
| 51 | 西班牙菜 | 61 | 桂菜 |
| 52 | 土耳其菜 | 62 | 琼菜 |
| 53 | 希腊菜 | 63 | 贵菜 |
| 54 | 巴西菜 | 64 | 藏菜 |
| 55 | 徽菜 | - | - |

#### 价格区间分类（ID: 41-45）

价格区间可以与其他菜系分类组合使用（用逗号分隔）。

| ID | 名称 | 说明 |
|----|------|------|
| 41 | 人均50至100 | 中等价位 |
| 42 | 人均100至200 | 中高价位 |
| 43 | 人均200至300 | 高价位 |
| 44 | 人均300以上 | 超高价 |
| 45 | 人均50元以内 | 低价位 |

#### 用餐场景分类（ID: 65-74）

| ID | 名称 | ID | 名称 |
|----|------|-----|------|
| 65 | 早餐 | 70 | 商务宴请 |
| 66 | 午餐 | 71 | 情侣约会 |
| 67 | 晚餐 | 72 | 家庭聚餐 |
| 68 | 夜宵 | 73 | 朋友聚会 |
| 69 | 下午茶 | 74 | 生日聚会 |

#### 餐厅特色分类（ID: 75-83）

| ID | 名称 | ID | 名称 |
|----|------|-----|------|
| 75 | 网红餐厅 | 80 | 人气餐厅 |
| 76 | 老字号 | 81 | 新店开业 |
| 77 | 米其林 | 82 | 连锁品牌 |
| 78 | 黑珍珠 | 83 | 独立小店 |
| 79 | 必吃榜 | - | - |

#### 服务类型分类（ID: 84-89）

| ID | 名称 | ID | 名称 |
|----|------|-----|------|
| 84 | 外卖 | 87 | 自助 |
| 85 | 堂食 | 88 | 套餐 |
| 86 | 外带 | 89 | 单点 |

#### 环境特色分类（ID: 90-96）

| ID | 名称 | ID | 名称 |
|----|------|-----|------|
| 90 | 露天 | 94 | 音乐餐厅 |
| 91 | 包间 | 95 | 酒吧 |
| 92 | 景观 | 96 | 无烟 |
| 93 | 主题餐厅 | - | - |

#### 特殊需求分类（ID: 97-103）

| ID | 名称 | ID | 名称 |
|----|------|-----|------|
| 97 | 清真 | 101 | 宠物友好 |
| 98 | 无糖 | 102 | 无障碍 |
| 99 | 低卡 | 103 | 停车方便 |
| 100 | 儿童友好 | - | - |

**注意**：素食（ID: 33）已在菜系分类中。

#### 时间特色分类（ID: 104-107）

| ID | 名称 |
|----|------|
| 104 | 24小时 |
| 105 | 深夜食堂 |
| 106 | 早市 |
| 107 | 夜市 |

#### 其他分类（ID: 108-114）

| ID | 名称 | ID | 名称 |
|----|------|-----|------|
| 108 | 地方特色 | 112 | 快餐 |
| 109 | 国际美食 | 113 | 甜品店 |
| 110 | 融合菜 | 114 | 饮品店 |
| 111 | 健康餐 | - | - |

### 子类型使用示例

- **单个子类型**：`'10'` (潮汕菜)
- **菜系 + 价格区间**：`'10,42'` (潮汕菜 + 人均100至200)
- **多个分类组合**：`'10,12,42'` (潮汕菜 + 粤菜 + 人均100至200)
- **菜系 + 价格 + 场景**：`'46,42,71'` (意大利菜 + 人均100至200 + 情侣约会)
- **菜系 + 特色 + 价格**：`'10,76,42'` (潮汕菜 + 老字号 + 人均100至200)
- **场景 + 特色 + 价格**：`'70,77,43'` (商务宴请 + 米其林 + 人均200至300)

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

## 数据来源说明

### 字段数据来源优先级

1. **餐厅名称 (`tweets_title`)**
   - 优先：AI从小红书帖子中提取
   - 其次：高德API返回的`name`字段

2. **餐厅地址 (`tweets_describe`)**
   - 优先：高德地图API返回的完整地址（省+市+区县+详细地址）
   - 其次：AI从小红书帖子中提取的地址
   - 最后：AI联网搜索补充的地址

3. **城市名称 (`tweets_location`)**
   - 优先：高德API返回的`cityname`字段（如"深圳市"→"深圳"）
   - 其次：从完整地址中提取城市名（使用正则表达式）
   - 最后：从笔记标题/描述中提取的默认城市

4. **转述内容 (`tweets_content`)**
   - 来源：AI对小红书帖子内容进行转述和改写

5. **图片 (`tweets_img`)**
   - 来源：小红书原帖图片URL（直接使用，不下载）

6. **子类型ID (`tweets_type_cid`)**
   - 来源：AI分类结果（包含餐厅类型和价格区间）
   - 价格区间子类型ID映射：
     - 45: 人均50元以内
     - 41: 人均50至100
     - 42: 人均100至200
     - 43: 人均200至300
     - 44: 人均300以上

## 批量插入

爬虫会收集所有数据后，通过 `batch_insert_tweets()` 函数批量插入，每次插入一条，返回插入的ID。

## 默认配置

当前默认配置（可在 `config.py` 或 `.env` 文件中修改）：
- `DEFAULT_TYPE_PID`: 5 (美食)
- `DEFAULT_TYPE_CID`: '10,42' (潮汕菜 + 人均100至200)

## 类目统计

### 类目总数
- **一级类目（父类型）**: 1个（美食，ID=5）
- **二级类目（子类型）**: 114个

### 子类型分类统计

| 分类 | 数量 | ID范围 |
|------|------|--------|
| 菜系分类 | 35个 | 6-40 |
| 补充菜系 | 19个 | 46-64 |
| 价格区间 | 5个 | 41-45 |
| 用餐场景 | 10个 | 65-74 |
| 餐厅特色 | 9个 | 75-83 |
| 服务类型 | 6个 | 84-89 |
| 环境特色 | 7个 | 90-96 |
| 特殊需求 | 7个 | 97-103 |
| 时间特色 | 4个 | 104-107 |
| 其他分类 | 7个 | 108-114 |
| **总计** | **114个** | - |

### 添加新类目

如需添加新的类目，可以使用以下工具：

```bash
# 添加单个类目
python3 app/add_tweet_type.py --child "新类目名称" --parent-id 5

# 列出所有类目
python3 app/add_tweet_type.py --list
```

添加新类目后，需要更新 `app/ai_paraphrase.py` 中的 `get_type_cid_mapping()` 方法以支持AI分类。
