
import os
import sys
sys.path.insert(0, os.path.join(os.getcwd(), "crawler-tool"))
from base.database import db

def main():
    # Show all tables
    print("Tables:")
    df = db.execute_query("SHOW TABLES")
    print(df.to_string())
    print("-" * 20)

    # Check tweets_evaluate schema
    print("\nSchema of tweets_evaluate:")
    try:
        df = db.execute_query("DESCRIBE tweets_evaluate")
        print(df.to_string())
    except Exception as e:
        print(f"Error: {e}")

    # Check for user table (guess name)
    tables = [t[0] for t in db.execute_query("SHOW TABLES").values.tolist()]
    user_tables = [t for t in tables if 'user' in t]
    print(f"\nPossible user tables: {user_tables}")

    for t in user_tables:
        print(f"\nSchema of {t}:")
        df = db.execute_query(f"DESCRIBE {t}")
        print(df.to_string())

if __name__ == "__main__":
    main()
