"""智谱 AI 评论生成模块：基于分析结果生成植入评论"""
import json
import sqlite3
import os
from dotenv import load_dotenv, find_dotenv
from zhipuai import ZhipuAI

# 确保 .env 被加载
env_path = find_dotenv()
if env_path:
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

DB_PATH = os.environ.get("DB_PATH", "weibo_brand.db")
api_key = os.environ.get("ZHIPU_API_KEY", "")
client = ZhipuAI(api_key=api_key) if api_key else ZhipuAI()

# 产品名称映射（need_product → 品牌表产品名）
PRODUCT_MAP = {
    "鲜肉肠": "7小时鲜肉肠",
    "猪排": "剔骨猪排",
}


def get_brand_knowledge(product_type: str):
    """获取指定产品的知识点列表"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT category, knowledge_text FROM brand_knowledge WHERE product=?",
        (product_type,)
    )
    rows = c.fetchall()
    conn.close()
    return [f"{cat}: {txt}" for cat, txt in rows]


def generate_comment(post_text: str, post_intent: str, product_type: str) -> list:
    """为单条帖子生成 3 条评论"""
    knowledge = get_brand_knowledge(product_type)
    knowledge_str = "\n".join(knowledge)

    # 根据意图选择价值方向
    value_map = {
        "求助": f"教用户如何挑选{product_type}的专业知识+个人经验",
        "求推荐": f"分享{product_type}挑选心得，自然提及品牌",
        "分享经验": "补充一个同类经验/小技巧，顺带品牌",
        "晒单": "夸奖并补充产品优点，自然引出同品牌另一产品",
        "吐槽": "先共情，再给出解决方案，带出品牌",
        "情绪宣泄": "先共情理解，再温和提供建议",
        "其他": "补充有用信息"
    }
    value_direction = value_map.get(post_intent, "补充有用信息")

    prompt = f"""你是一个爱做饭、喜欢研究食材的微博美食博主。请根据以下信息写一条评论。

【原微博内容】：{post_text[:300]}

【你要提供的价值方向】：{value_direction}

【品牌可用知识点】：
{knowledge_str}

【生成要求】：
1. 先给有用信息/知识，再自然提到{product_type}
2. 80-130字，语气像热心网友在分享，可加1-2个emoji
3. 品牌名只出现一次，绝不使用"必买""全网第一""绝对"
4. 输出纯文本评论，不带任何符号包裹

评论："""

    comments = []
    for i in range(3):
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7 + i * 0.15,
        )
        comment = response.choices[0].message.content.strip()
        if comment and comment not in comments:
            comments.append(comment)

    return comments


def batch_generate():
    """批量生成评论，存入数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 找到 safe_for_brand=true 且还没生成评论的帖子
    c.execute("""
        SELECT p.post_id, p.text, a.intent, a.raw_response
        FROM weibo_posts p
        JOIN post_analysis a ON p.post_id = a.post_id
        WHERE a.safe_for_brand = 1
        AND p.post_id NOT IN (SELECT post_id FROM generated_comments)
        LIMIT 20
    """)
    posts = c.fetchall()

    if not posts:
        print("[i] 没有待生成评论的帖子")
        conn.close()
        return

    print(f"即将为 {len(posts)} 条帖子生成评论...")
    success_count = 0
    for post_id, text, intent, raw_resp in posts:
        try:
            # 解析分析结果中的产品类型
            analysis = json.loads(raw_resp)
            need_product_key = analysis.get("need_product", "均可")

            if need_product_key == "均可" or need_product_key not in PRODUCT_MAP:
                product_type = "7小时鲜肉肠"  # 默认推鲜肉肠
            else:
                product_type = PRODUCT_MAP[need_product_key]

            comments = generate_comment(text, intent, product_type)
            for comment in comments:
                c.execute("""
                    INSERT INTO generated_comments (post_id, comment_text)
                    VALUES (?,?)
                """, (post_id, comment))
            conn.commit()
            success_count += 1
            print(f"  [OK] 已为 {post_id} 生成 {len(comments)} 条评论 (产品: {product_type})")
        except Exception as e:
            print(f"  [X] 生成失败 {post_id}: {e}")

    conn.close()
    print(f"生成完成，成功 {success_count} / {len(posts)}")
    return success_count


if __name__ == "__main__":
    batch_generate()
