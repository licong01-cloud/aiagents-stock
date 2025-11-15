import os
from dotenv import load_dotenv
import psycopg2

load_dotenv(override=True)

cfg = dict(
    host=os.getenv('TDX_DB_HOST', 'localhost'),
    port=int(os.getenv('TDX_DB_PORT', '5432')),
    dbname=os.getenv('TDX_DB_NAME', 'aistock'),
    user=os.getenv('TDX_DB_USER', 'postgres'),
    password=os.getenv('TDX_DB_PASSWORD', 'lc78080808'),
)

tables = [
    'app.monitor_tasks',
    'app.ai_decisions',
    'app.trade_records',
    'app.position_monitor',
    'app.notifications',
    'app.system_logs',
]

with psycopg2.connect(**cfg) as conn:
    with conn.cursor() as cur:
        for t in tables:
            cur.execute(f'SELECT COUNT(*) FROM {t}')
            c = int(cur.fetchone()[0])
            print(f'{t}: {c}')
