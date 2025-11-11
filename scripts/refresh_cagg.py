import psycopg2

CFG = dict(host='localhost', port=5432, dbname='aistock', user='postgres', password='lc78080808')

SQLS = [
    "CALL refresh_continuous_aggregate('market.kline_5m', now() - interval '2 days', now())",
    "CALL refresh_continuous_aggregate('market.kline_15m', now() - interval '3 days', now())",
    "CALL refresh_continuous_aggregate('market.kline_60m', now() - interval '7 days', now())",
]

def main():
    conn = psycopg2.connect(**CFG)
    try:
        conn.set_session(autocommit=True)
        with conn.cursor() as cur:
            for s in SQLS:
                cur.execute(s)
    finally:
        conn.close()
    print('CAGG refresh done')

if __name__ == '__main__':
    main()
