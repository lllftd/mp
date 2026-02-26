# -*- coding: utf-8 -*-
import os
import sys


def main():
    sys.path.insert(0, os.path.join(os.getcwd(), "crawler-tool"))
    from base.database import db  # noqa

    df = db.execute_query("SHOW COLUMNS FROM tweets LIKE 'tweets_img'")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()




