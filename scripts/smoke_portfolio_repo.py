import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pg_portfolio_db import portfolio_db


def main():
    print("Adding test stock...")
    stock_id = portfolio_db.add_stock(
        code="ZZTEST",
        name="测试股票",
        cost_price=1.23,
        quantity=100,
        note="smoke",
        auto_monitor=True,
    )
    print("Added id:", stock_id)

    all_stocks = portfolio_db.get_all_stocks()
    print("Total stocks after add:", len(all_stocks))
    found = [s for s in all_stocks if s["id"] == stock_id]
    print("Found just added:", len(found) == 1)

    print("Deleting test stock...")
    deleted = portfolio_db.delete_stock(stock_id)
    print("Deleted:", deleted)

    all_after = portfolio_db.get_all_stocks()
    print("Total stocks after delete:", len(all_after))


if __name__ == "__main__":
    main()
