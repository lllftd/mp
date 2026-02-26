# -*- coding: utf-8 -*-
"""
Quick DB inspection utility:
Print tweets_img for specific tweets_title values.

Usage (Windows):
  .\\env\\Scripts\\python.exe inspect_title_images.py
"""

import os
import sys
import json


def _ensure_path():
    root = os.getcwd()
    sys.path.insert(0, os.path.join(root, "crawler-tool"))


def main():
    _ensure_path()

    from base.database import db  # type: ignore

    titles = ["猪一面屋", "顺德大排档", "潮香四海", "翠湖广东乡下菜", "海底捞"]
    query = """
        SELECT id, tweets_title, tweets_img
        FROM tweets
        WHERE tweets_title IN (:t1, :t2, :t3, :t4, :t5)
        ORDER BY id DESC
    """
    df = db.execute_query(query, {"t1": titles[0], "t2": titles[1], "t3": titles[2], "t4": titles[3], "t5": titles[4]})

    if df.empty:
        print("No rows found for titles:", titles)
        return

    for _, row in df.iterrows():
        tid = row.get("id")
        title = row.get("tweets_title")
        imgs_raw = row.get("tweets_img") or ""
        print("=" * 80)
        print(f"id={tid} title={title}")
        print("tweets_img(raw) =", imgs_raw)
        try:
            imgs = json.loads(imgs_raw) if isinstance(imgs_raw, str) else imgs_raw
        except Exception as e:
            print("tweets_img(json parse failed):", e)
            continue

        if not isinstance(imgs, list):
            imgs = [imgs]
        print(f"images(count)={len(imgs)}")
        for i, u in enumerate(imgs, 1):
            print(f"  {i:02d}. {u}")

    # 额外：有些店名在库里可能带后缀（例如“海底捞火锅(xx店)”），用 LIKE 再查一次
    like_keywords = ["海底捞", "翠湖广东乡下菜"]
    for kw in like_keywords:
        df2 = db.execute_query(
            """
            SELECT id, tweets_title, tweets_img
            FROM tweets
            WHERE tweets_title LIKE :kw
            ORDER BY id DESC
            LIMIT 5
            """,
            {"kw": f"%{kw}%"},
        )
        if df2.empty:
            continue
        print("\n" + "#" * 80)
        print(f"LIKE search: {kw} (top 5)")
        print("#" * 80)
        for _, row in df2.iterrows():
            tid = row.get("id")
            title = row.get("tweets_title")
            imgs_raw = row.get("tweets_img") or ""
            print("-" * 80)
            print(f"id={tid} title={title}")
            print("tweets_img(raw) =", imgs_raw)


if __name__ == "__main__":
    main()


