# -*- coding: utf-8 -*-
import os
import sys
import json
import pandas as pd

def _ensure_path():
    root = os.getcwd()
    sys.path.insert(0, os.path.join(root, "crawler-tool"))

def main():
    _ensure_path()
    from base.database import db

    print("=== Database Analysis ===")

    # 1. List Tables
    try:
        tables_df = db.execute_query("SHOW TABLES")
        print("\n[Tables]")
        if not tables_df.empty:
            print(tables_df.to_string(index=False))
            table_names = tables_df.iloc[:, 0].tolist()
        else:
            print("No tables found.")
            return
    except Exception as e:
        print(f"Error listing tables: {e}")
        return

    if "tweets" not in table_names:
        print("\n'tweets' table not found. Skipping tweets analysis.")
        return

    # 2. Schema of 'tweets'
    print("\n[Schema: tweets]")
    try:
        schema_df = db.execute_query("DESCRIBE tweets")
        print(schema_df.to_string())
    except Exception as e:
        print(f"Error describing tweets: {e}")

    # 3. Row Count
    try:
        count_df = db.execute_query("SELECT COUNT(*) as total FROM tweets")
        total_rows = count_df.iloc[0]['total']
        print(f"\n[Total Rows in tweets]: {total_rows}")
    except Exception as e:
        print(f"Error counting rows: {e}")
        return

    if total_rows == 0:
        print("Table is empty.")
        return

    # 4. Null Analysis
    print("\n[Null Value Analysis]")
    columns_to_check = ['tweets_location', 'tweets_user', 'tweets_position', 'tweets_location_code']
    for col in columns_to_check:
        try:
            # Check if column exists first
            col_exists = db.execute_query(f"SHOW COLUMNS FROM tweets LIKE '{col}'")
            if col_exists.empty:
                print(f"  {col}: Column not found")
                continue

            null_count_df = db.execute_query(f"SELECT COUNT(*) as cnt FROM tweets WHERE {col} IS NULL OR {col} = ''")
            null_count = null_count_df.iloc[0]['cnt']
            print(f"  {col}: {null_count} null/empty rows ({null_count/total_rows*100:.2f}%)")
        except Exception as e:
            print(f"  {col}: Error checking nulls - {e}")

    # 4.1 Content vs Describe Analysis
    print("\n[Content vs Describe Analysis (Sample 3)]")
    try:
        sample_df = db.execute_query("SELECT tweets_title, tweets_describe, tweets_content FROM tweets LIMIT 3")
        for _, row in sample_df.iterrows():
            print("-" * 40)
            print(f"Title: {row['tweets_title']}")
            print(f"Describe (len={len(row['tweets_describe'])}): {row['tweets_describe'][:100]}...")
            print(f"Content  (len={len(row['tweets_content'])}): {row['tweets_content'][:100]}...")
    except Exception as e:
        print(f"Error checking content/describe: {e}")

    # 4.2 Position Format Analysis
    print("\n[Position Format Analysis (Sample 10)]")
    try:
        pos_df = db.execute_query("SELECT id, tweets_position, tweets_location FROM tweets WHERE tweets_position IS NOT NULL AND tweets_position != '' LIMIT 10")
        print("Sample positions (and corresponding location):")
        for _, row in pos_df.iterrows():
            print(f"  Pos: {row['tweets_position']} | Loc: {row['tweets_location']}")
    except Exception as e:
        print(f"Error checking positions: {e}")

    # 4.3 Category Analysis
    print("\n[Category Distribution (Top 10)]")
    try:
        cat_df = db.execute_query("SELECT tweets_type_cid, COUNT(*) as cnt FROM tweets GROUP BY tweets_type_cid ORDER BY cnt DESC LIMIT 10")
        print(cat_df.to_string(index=False))
    except Exception as e:
        print(f"Error checking categories: {e}")

    # 5. Duplicate Analysis (Title)
    print("\n[Duplicate Title Analysis]")
    try:
        dup_df = db.execute_query("""
            SELECT tweets_title, COUNT(*) as cnt
            FROM tweets
            GROUP BY tweets_title
            HAVING cnt > 1
            ORDER BY cnt DESC
            LIMIT 10
        """)
        if not dup_df.empty:
            print(f"Found {len(dup_df)} titles with duplicates (showing top 10):")
            print(dup_df.to_string(index=False))
        else:
            print("No duplicate titles found.")
    except Exception as e:
        print(f"Error checking duplicates: {e}")

    # 6. JSON Validity Check (tweets_img)
    print("\n[JSON Validity Check: tweets_img (Sample 100)]")
    try:
        img_sample = db.execute_query("SELECT id, tweets_img FROM tweets WHERE tweets_img IS NOT NULL AND tweets_img != '' LIMIT 100")
        invalid_json_count = 0
        empty_list_count = 0
        for _, row in img_sample.iterrows():
            raw = row['tweets_img']
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    if len(parsed) == 0:
                        empty_list_count += 1
                else:
                    # Valid JSON but not a list?
                    pass 
            except json.JSONDecodeError:
                invalid_json_count += 1
                # print(f"  Invalid JSON at id={row['id']}: {raw[:50]}...")
        
        print(f"  Sampled 100 non-empty rows.")
        print(f"  Invalid JSON format: {invalid_json_count}")
        print(f"  Empty JSON lists []: {empty_list_count}")
        
    except Exception as e:
        print(f"Error checking JSON: {e}")

    # 7. Address Length Analysis
    print("\n[Address Analysis]")
    try:
        addr_df = db.execute_query("SELECT id, tweets_location FROM tweets WHERE tweets_location IS NOT NULL AND tweets_location != '' LIMIT 20")
        print("Sample addresses:")
        for _, row in addr_df.iterrows():
            print(f"  {row['tweets_location']}")
    except Exception as e:
        print(f"Error checking addresses: {e}")

if __name__ == "__main__":
    main()

