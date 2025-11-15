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

print('DB cfg:', cfg)

tables = {
    'app.analysis_records': "SELECT COUNT(*) FROM app.analysis_records",
    'app.monitored_stocks': "SELECT COUNT(*) FROM app.monitored_stocks",
    'app.price_history': "SELECT COUNT(*) FROM app.price_history",
    'app.monitor_tasks': "SELECT COUNT(*) FROM app.monitor_tasks",
    'app.ai_decisions': "SELECT COUNT(*) FROM app.ai_decisions",
    'app.trade_records': "SELECT COUNT(*) FROM app.trade_records",
    'app.position_monitor': "SELECT COUNT(*) FROM app.position_monitor",
    'app.notifications': "SELECT COUNT(*) FROM app.notifications",
    'app.portfolio_stocks': "SELECT COUNT(*) FROM app.portfolio_stocks",
    'app.portfolio_analysis_history': "SELECT COUNT(*) FROM app.portfolio_analysis_history",
    'app.watchlist_categories': "SELECT COUNT(*) FROM app.watchlist_categories",
    'app.watchlist_items': "SELECT COUNT(*) FROM app.watchlist_items",
}

with psycopg2.connect(**cfg) as conn:
    with conn.cursor() as cur:
        for t, q in tables.items():
            try:
                cur.execute(q)
                c = int(cur.fetchone()[0])
            except Exception as e:
                c = f"ERR: {e}"
            print(f"{t}: {c}")
        print('\nTop analysis_records:')
        cur.execute("SELECT id, ts_code, stock_name, analysis_date, period, created_at FROM app.analysis_records ORDER BY created_at DESC LIMIT 3")
        for r in cur.fetchall():
            print('-', r)
        print('\nTop portfolio_stocks:')
        cur.execute("SELECT id, code, name, cost_price, quantity, created_at FROM app.portfolio_stocks ORDER BY created_at DESC LIMIT 5")
        for r in cur.fetchall():
            print('-', r)
        print('\nTop watchlist categories:')
        cur.execute("SELECT id, name, description, created_at FROM app.watchlist_categories ORDER BY id ASC LIMIT 5")
        for r in cur.fetchall():
            print('-', r)
        print('\nTop watchlist items:')
        cur.execute("SELECT id, code, name, category_id, created_at FROM app.watchlist_items ORDER BY created_at DESC LIMIT 5")
        for r in cur.fetchall():
            print('-', r)
