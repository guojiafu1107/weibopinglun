"""Web 工作台后端 - FastAPI 服务"""
import json
import os
import sqlite3
import threading
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

env_path = find_dotenv()
if env_path:
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

DB_PATH = os.environ.get("DB_PATH", "weibo_brand.db")

app = FastAPI(title="微博生鲜评论工作台")

# 记录流水线状态
pipeline_status = {"running": False, "result": None, "error": None}


def dict_factory(cursor, row):
    """让查询结果返回字典格式"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    return conn


@app.get("/api/posts")
def get_posts(
    keyword: str = Query(None),
    product: str = Query(None),
    only_pending: bool = Query(True),
    limit: int = Query(50, le=200)
):
    """获取帖子列表，支持筛选"""
    conn = get_conn()
    c = conn.cursor()

    conditions = []
    params = []

    if only_pending:
        conditions.append("a.safe_for_brand = 1")
        conditions.append("p.post_id NOT IN (SELECT post_id FROM generated_comments)")

    if keyword:
        conditions.append("p.keyword = ?")
        params.append(keyword)

    if product:
        conditions.append("a.raw_response LIKE ?")
        params.append(f"%{product}%")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT p.*, a.intent, a.emotion, a.safe_for_brand, a.writable_value_type
        FROM weibo_posts p
        LEFT JOIN post_analysis a ON p.post_id = a.post_id
        WHERE {where_clause}
        ORDER BY p.attitudes_count DESC
        LIMIT ?
    """
    params.append(limit)

    c.execute(query, params)
    posts = c.fetchall()
    conn.close()
    return posts


@app.get("/api/posts/unanalyzed")
def get_unanalyzed_posts(limit: int = Query(50, le=200)):
    """获取尚未 AI 分析的帖子"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT p.*
        FROM weibo_posts p
        WHERE p.post_id NOT IN (SELECT post_id FROM post_analysis)
        ORDER BY p.attitudes_count DESC
        LIMIT ?
    """, (limit,))
    posts = c.fetchall()
    conn.close()
    return posts


@app.get("/api/comments/{post_id}")
def get_comments(post_id: str, include_sent: bool = Query(False)):
    """获取某帖子的已生成评论"""
    conn = get_conn()
    c = conn.cursor()
    if include_sent:
        c.execute("SELECT * FROM generated_comments WHERE post_id=?", (post_id,))
    else:
        c.execute("SELECT * FROM generated_comments WHERE post_id=? AND is_sent=0", (post_id,))
    comments = c.fetchall()
    conn.close()
    return comments


@app.post("/api/comments/{comment_id}/sent")
def mark_sent(comment_id: int):
    """标记评论已发送/已使用"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE generated_comments 
        SET is_sent=1, sent_at=CURRENT_TIMESTAMP 
        WHERE id=?
    """, (comment_id,))
    conn.commit()
    affected = c.rowcount
    conn.close()
    if affected == 0:
        raise HTTPException(status_code=404, detail="评论不存在")
    return {"status": "ok", "comment_id": comment_id}


@app.get("/api/stats")
def get_stats():
    """获取统计概览"""
    conn = get_conn()
    c = conn.cursor()

    stats = {}
    c.execute("SELECT COUNT(*) FROM weibo_posts")
    stats["total_posts"] = c.fetchone()["COUNT(*)"]

    c.execute("SELECT COUNT(*) FROM post_analysis")
    stats["analyzed_posts"] = c.fetchone()["COUNT(*)"]

    c.execute("SELECT COUNT(*) FROM post_analysis WHERE safe_for_brand=1")
    stats["safe_posts"] = c.fetchone()["COUNT(*)"]

    c.execute("SELECT COUNT(*) FROM generated_comments")
    stats["total_comments"] = c.fetchone()["COUNT(*)"]

    c.execute("SELECT COUNT(*) FROM generated_comments WHERE is_sent=1")
    stats["sent_comments"] = c.fetchone()["COUNT(*)"]

    conn.close()
    return stats


@app.post("/api/pipeline/run")
def run_pipeline_api():
    """Web 端手动触发全流程"""
    if pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="流水线正在执行中，请稍后")

    def _run():
        try:
            from main import ensure_db, run_pipeline
            ensure_db()
            result = run_pipeline()
            pipeline_status["result"] = result
            pipeline_status["error"] = None
        except Exception as e:
            pipeline_status["result"] = None
            pipeline_status["error"] = str(e)
        finally:
            pipeline_status["running"] = False

    pipeline_status["running"] = True
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started", "message": "流水线已启动，请稍后刷新页面查看结果"}


@app.get("/api/pipeline/status")
def get_pipeline_status():
    """获取流水线执行状态"""
    return {
        "running": pipeline_status["running"],
        "result": pipeline_status["result"],
        "error": pipeline_status["error"]
    }


# 托管静态文件
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
