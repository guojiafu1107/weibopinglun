"""微博爬虫模块：基于移动端 API 搜索帖子"""
import os
import re
import httpx
import sqlite3
import time
from dotenv import load_dotenv, find_dotenv

env_path = find_dotenv()
if env_path:
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

DB_PATH = os.environ.get("DB_PATH", "weibo_brand.db")
WEIBO_COOKIE = os.environ.get("WEIBO_COOKIE", "your_cookie_here")

# 默认搜索关键词
KEYWORDS = ["烤肠推荐", "猪排怎么做", "纯肉肠测评", "快手早餐"]


def clean_html(text):
    """清理微博文本中的 HTML 标签"""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text.strip()


def search_weibo(keyword: str, page: int = 1):
    """通过微博移动端 API 搜索帖子"""
    url = "https://m.weibo.cn/api/container/getIndex"
    params = {
        "containerid": f"100103type=1&q={keyword}",
        "page": page
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Cookie": WEIBO_COOKIE,
        "Referer": "https://m.weibo.cn/",
        "X-Requested-With": "XMLHttpRequest"
    }

    resp = httpx.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    posts = []
    for card in data.get("data", {}).get("cards", []):
        card_group = card.get("card_group", [card])
        for item in card_group:
            if item.get("card_type") == 9:
                mblog = item.get("mblog", {})
                if not mblog:
                    continue
                posts.append({
                    "post_id": mblog.get("id", ""),
                    "text": clean_html(mblog.get("text", "")),
                    "user_nickname": mblog.get("user", {}).get("screen_name", "未知"),
                    "user_followers": mblog.get("user", {}).get("followers_count", 0),
                    "attitudes_count": mblog.get("attitudes_count", 0),
                    "comments_count": mblog.get("comments_count", 0),
                    "reposts_count": mblog.get("reposts_count", 0),
                    "created_at": mblog.get("created_at", "")
                })
    return posts


def save_posts_to_db(posts, keyword):
    """将帖子存入数据库，自动去重"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    saved = 0
    for post in posts:
        try:
            c.execute("""
                INSERT OR IGNORE INTO weibo_posts 
                (post_id, keyword, text, user_nickname, user_followers,
                 attitudes_count, comments_count, reposts_count, created_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                post["post_id"], keyword, post["text"], post["user_nickname"],
                post["user_followers"], post["attitudes_count"],
                post["comments_count"], post["reposts_count"],
                post["created_at"]
            ))
            if c.rowcount > 0:
                saved += 1
        except Exception as e:
            print(f"  保存失败 {post['post_id']}: {e}")
    conn.commit()
    conn.close()
    return saved


def run_crawler():
    """主调度：遍历关键词抓取帖子"""
    print("=" * 40)
    print("开始抓取微博帖子")
    print("=" * 40)
    total_saved = 0
    for kw in KEYWORDS:
        print(f"\n正在抓取关键词: {kw}")
        try:
            posts = search_weibo(kw, page=1)
            # 过滤低互动帖子（点赞 < 30 跳过）
            filtered = [p for p in posts if p["attitudes_count"] >= 30]
            saved = save_posts_to_db(filtered, kw)
            total_saved += saved
            print(f"  抓取 {len(posts)} 条，过滤后保存 {saved} 条")
            time.sleep(5)  # 控制频率，避免被封
        except Exception as e:
            print(f"  [X] 关键词 '{kw}' 抓取失败: {e}")

    print(f"\n本次共保存 {total_saved} 条新帖子 (注意: 未设置Cookie将使用默认值, 可能抓取失败)")
    return total_saved


if __name__ == "__main__":
    run_crawler()
