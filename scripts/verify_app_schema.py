import os
from dotenv import load_dotenv
import psycopg2

load_dotenv(override=True)

cfg = dict(
    host=os.getenv("TDX_DB_HOST", "localhost"),
    port=int(os.getenv("TDX_DB_PORT", "5432")),
    dbname=os.getenv("TDX_DB_NAME", "aistock"),
    user=os.getenv("TDX_DB_USER", "postgres"),
    password=os.getenv("TDX_DB_PASSWORD", "lc78080808"),
)

with psycopg2.connect(**cfg) as conn:
    with conn.cursor() as cur:
        cur.execute("select table_name from information_schema.tables where table_schema='app' order by table_name")
        tables = [r[0] for r in cur.fetchall()]
        print("app schema tables:")
        for t in tables:
            print("-", t)
