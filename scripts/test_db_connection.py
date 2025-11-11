"""Quick test for PostgreSQL/TimescaleDB availability and market schema status."""
import sys
import psycopg2

CFG = dict(host='localhost', port=5432, user='postgres', password='lc78080808', dbname='aistock')


def try_connect(cfg):
    try:
        conn = psycopg2.connect(**cfg)
        return conn, None
    except Exception as e:
        return None, e


def check_timescaledb(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT installed_version FROM pg_available_extensions WHERE name='timescaledb'")
        row = cur.fetchone()
        available = row is not None
        cur.execute("SELECT extversion FROM pg_extension WHERE extname='timescaledb'")
        row2 = cur.fetchone()
        installed = row2[0] if row2 else None
        return available, installed


def market_overview(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='market'")
        tables = cur.fetchone()[0]
        return tables


def main():
    print(f"[1] Try connect to {CFG['host']}:{CFG['port']} db={CFG['dbname']} as {CFG['user']} ...")
    conn, err = try_connect(CFG)
    if err:
        print(f"  - Failed: {err}")
        print("[1a] Try connect to default 'postgres' database to verify server status ...")
        alt = CFG.copy(); alt['dbname'] = 'postgres'
        conn2, err2 = try_connect(alt)
        if err2:
            print(f"  - Failed: {err2}")
            print("[RESULT] Server not reachable on given host/port. Ensure PostgreSQL/TimescaleDB is running and port open.")
            sys.exit(2)
        else:
            print("  - OK: server reachable, but target database may be missing.")
            conn2.close()
            sys.exit(1)
    print("  - OK: connected")

    try:
        available, installed = check_timescaledb(conn)
        print(f"[2] TimescaleDB available: {available}, installed version: {installed}")
    except Exception as e:
        print(f"[2] TimescaleDB check error: {e}")

    try:
        tables = market_overview(conn)
        print(f"[3] market schema tables: {tables}")
    except Exception as e:
        print(f"[3] market schema check error: {e}")

    conn.close()
    print("[DONE] DB connectivity test finished.")


if __name__ == '__main__':
    main()
