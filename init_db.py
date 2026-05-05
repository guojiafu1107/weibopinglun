"""数据库初始化：建表 + 插入品牌知识"""
import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "weibo_brand.db")


def init_database():
    """初始化 SQLite 数据库，创建所有表"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 帖子表
    c.execute("""
        CREATE TABLE IF NOT EXISTS weibo_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id VARCHAR(32) UNIQUE,
            keyword VARCHAR(50),
            text TEXT,
            user_nickname VARCHAR(100),
            user_followers INT,
            attitudes_count INT,
            comments_count INT,
            reposts_count INT,
            created_at DATETIME,
            fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # AI 分析结果表
    c.execute("""
        CREATE TABLE IF NOT EXISTS post_analysis (
            post_id VARCHAR(32) PRIMARY KEY,
            intent VARCHAR(20),
            emotion VARCHAR(10),
            safe_for_brand BOOLEAN,
            writable_value_type VARCHAR(50),
            raw_response TEXT,
            analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 生成评论表
    c.execute("""
        CREATE TABLE IF NOT EXISTS generated_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id VARCHAR(32),
            comment_text TEXT,
            is_sent BOOLEAN DEFAULT 0,
            sent_at DATETIME,
            performance_score INT DEFAULT 0
        )
    """)

    # 品牌知识库表
    c.execute("""
        CREATE TABLE IF NOT EXISTS brand_knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product VARCHAR(50),
            category VARCHAR(30),
            knowledge_text TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("[OK] 数据库表创建完成")


def seed_brand_knowledge():
    """填充品牌知识数据"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 检查是否已有数据
    c.execute("SELECT COUNT(*) FROM brand_knowledge")
    count = c.fetchone()[0]
    if count > 0:
        print(f"[i] 品牌知识库已有 {count} 条数据，跳过初始化")
        conn.close()
        return

    knowledge_data = [
        # 7小时鲜肉肠
        ("7小时鲜肉肠", "配料", "猪肉含量≥90%，第一位是猪肉，0淀粉、0人工色素、0胶质"),
        ("7小时鲜肉肠", "工艺", "7小时低温慢烘锁汁，保留鲜肉自然口感"),
        ("7小时鲜肉肠", "口感", "煎完能看见鲜肉颗粒，脆弹爆汁，不发干不发柴"),
        ("7小时鲜肉肠", "吃法", "空气炸锅190度10分钟，早上夹面包做快手早餐"),
        # 剔骨猪排
        ("剔骨猪排", "原料", "整块原切猪肉，非拼接，纹理自然清晰"),
        ("剔骨猪排", "厚度", "2cm厚切，外焦里嫩不干柴"),
        ("剔骨猪排", "预处理", "已断筋免拍打，到手直接用，简单腌制即可下锅"),
        ("剔骨猪排", "吃法", "大火每面煎一分半到两分钟，粉嫩多汁，做日式炸猪排更酥脆"),
    ]

    c.executemany(
        "INSERT INTO brand_knowledge (product, category, knowledge_text) VALUES (?,?,?)",
        knowledge_data
    )
    conn.commit()
    conn.close()
    print(f"[OK] 品牌知识库已初始化 {len(knowledge_data)} 条数据")


if __name__ == "__main__":
    init_database()
    seed_brand_knowledge()
    print("数据库初始化完成！")
