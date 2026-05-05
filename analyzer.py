"""智谱 AI 帖子分析模块：判断帖子意图与植入安全性"""
import json
import sqlite3
import os
import re
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


def analyze_post(text: str) -> str:
    """用 GLM-4-Flash 分析单条帖子"""
    prompt = f"""你是一个微博内容分析助手。请分析以下微博帖子，并以严格的 JSON 格式返回（不要带引号外任何文字）：
{{
  "intent": "求助/吐槽/分享经验/求推荐/晒单/情绪宣泄/其他",
  "emotion": "正面/中性/负面",
  "safe_for_brand": true或false,
  "writable_value_type": "专业知识/情感共鸣/省钱技巧/无",
  "need_product": "鲜肉肠/猪排/均可/无"
}}

规则：
- 如果帖子在求助或求推荐，intent为"求推荐"
- 如果帖子有品牌负面情绪激烈、吵架、涉政敏感，safe_for_brand为false
- 帖子提到烤肠、肉肠、早餐肠，need_product为"鲜肉肠"
- 帖子提到猪排、炸猪排、猪扒，need_product为"猪排"

微博正文：{text[:500]}

JSON 输出："""

    response = client.chat.completions.create(
        model="glm-4-flash",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content


def extract_json(text: str) -> dict:
    """从 LLM 回复中提取 JSON 对象"""
    # 尝试直接解析
    text = text.strip()
    # 如果被代码块包裹，提取代码块内容
    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if code_block_match:
        text = code_block_match.group(1).strip()
    # 尝试找到第一个 { 到最后一个 }
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        text = json_match.group()
    return json.loads(text)


def batch_analyze():
    """批量分析未处理的帖子"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 找出尚未分析的帖子
    c.execute("""
        SELECT post_id, text FROM weibo_posts 
        WHERE post_id NOT IN (SELECT post_id FROM post_analysis)
        LIMIT 50
    """)
    posts = c.fetchall()

    if not posts:
        print("[i] 没有待分析的帖子")
        conn.close()
        return

    print(f"即将分析 {len(posts)} 条帖子...")
    success_count = 0
    for post_id, text in posts:
        try:
            result_str = analyze_post(text)
            result = extract_json(result_str)

            safe_for_brand = 1 if result.get("safe_for_brand") is True else 0

            c.execute("""
                INSERT OR REPLACE INTO post_analysis 
                (post_id, intent, emotion, safe_for_brand, writable_value_type, raw_response)
                VALUES (?,?,?,?,?,?)
            """, (
                post_id,
                result.get("intent", "其他"),
                result.get("emotion", "中性"),
                safe_for_brand,
                result.get("writable_value_type", "无"),
                json.dumps(result, ensure_ascii=False)
            ))
            conn.commit()
            success_count += 1
            print(f"  [OK] 已分析帖子 {post_id} -> intent={result.get('intent')}, safe={safe_for_brand}")
        except Exception as e:
            print(f"  [X] 解析失败 {post_id}: {e}")
            # 保存失败记录以便排查
            c.execute("""
                INSERT OR REPLACE INTO post_analysis 
                (post_id, intent, emotion, safe_for_brand, writable_value_type, raw_response)
                VALUES (?,?,?,?,?,?)
            """, (post_id, "其他", "中性", 0, "无", f"解析失败: {e}"))
            conn.commit()

    conn.close()
    print(f"分析完成，成功 {success_count} / {len(posts)}")
    return success_count


if __name__ == "__main__":
    batch_analyze()
