import os
import sqlite3
from dotenv import load_dotenv
import psycopg2

load_dotenv(override=True)

SQLITE_PATH = os.path.join(os.path.dirname(__file__), '..', 'stock_analysis.db')
SQLITE_PATH = os.path.abspath(SQLITE_PATH)

pg_cfg = dict(
    host=os.getenv('TDX_DB_HOST', 'localhost'),
    port=int(os.getenv('TDX_DB_PORT', '5432')),
    dbname=os.getenv('TDX_DB_NAME', 'aistock'),
    user=os.getenv('TDX_DB_USER', 'postgres'),
    password=os.getenv('TDX_DB_PASSWORD', 'lc78080808'),
)

src = 0
if os.path.exists(SQLITE_PATH):
    with sqlite3.connect(SQLITE_PATH) as conn:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM analysis_records')
        src = int(cur.fetchone()[0])

with psycopg2.connect(**pg_cfg) as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM app.analysis_records')
        dst = int(cur.fetchone()[0])
        cur.execute('SELECT id, ts_code, stock_name, analysis_date, period FROM app.analysis_records ORDER BY created_at DESC LIMIT 3')
        sample = cur.fetchall()

print('SQLite count:', src)
print('TimescaleDB count:', dst)
print('Top 3 rows:')
for r in sample:
    print('-', r)
