"""一键调度脚本：爬取 → 分析 → 生成评论"""
import os
import sys
import time
from dotenv import load_dotenv, find_dotenv

env_path = find_dotenv()
if env_path:
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)


def check_env():
    """检查关键环境变量，缺失时打印警告但不退出（Web端调用不会崩溃）"""
    ok = True
    if not os.environ.get("ZHIPU_API_KEY"):
        print("[!] 未设置 ZHIPU_API_KEY 环境变量")
        ok = False
    if not os.environ.get("WEIBO_COOKIE") or os.environ.get("WEIBO_COOKIE") == "your_cookie_here":
        print("[!] 未设置 WEIBO_COOKIE 环境变量")
        ok = False
    return ok


def ensure_db():
    """确保数据库已初始化"""
    from init_db import init_database, seed_brand_knowledge
    init_database()
    seed_brand_knowledge()


def run_pipeline():
    """执行完整流水线"""
    if not check_env():
        raise RuntimeError("环境变量不完整，请检查 ZHIPU_API_KEY 和 WEIBO_COOKIE 配置")
    from crawler import run_crawler
    from analyzer import batch_analyze
    from generator import batch_generate

    print("=" * 50)
    print("  [>>>] 微博生鲜评论工具 - 全流程执行")
    print("=" * 50)

    # 步骤1：抓取帖子
    print("\n[1/3] 抓取微博帖子...")
    crawled = run_crawler()
    time.sleep(2)

    # 步骤2：AI 分析帖子
    print("\n[2/3] AI 分析帖子意图...")
    analyzed = batch_analyze()
    time.sleep(2)

    # 步骤3：生成评论
    print("\n[3/3] 生成评论建议...")
    generated = batch_generate()

    print("\n" + "=" * 50)
    print(f"  本轮完成！")
    print(f"  抓取: {crawled} 条新帖子")
    print(f"  分析: {analyzed or 0} 条")
    print(f"  生成: {generated or 0} 条评论")
    print("=" * 50)
    print("\n[提示] 打开工作台查看：http://localhost:8000")

    return {
        "crawled": crawled,
        "analyzed": analyzed or 0,
        "generated": generated or 0
    }


if __name__ == "__main__":
    ensure_db()
    run_pipeline()
