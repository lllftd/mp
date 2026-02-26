
import os
import sys
sys.path.insert(0, os.path.join(os.getcwd(), "crawler-tool"))

# Fix Windows console encoding
if os.name == 'nt':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from base.database import db

def main():
    print("Top 20 users in client_user:")
    df = db.execute_query("SELECT id, nick_name, open_id FROM client_user LIMIT 20")
    print(df.to_string())

if __name__ == "__main__":
    main()
