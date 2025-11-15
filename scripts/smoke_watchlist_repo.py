import os
import sys
from datetime import datetime

# ensure project root is importable
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pg_watchlist_repo import watchlist_repo


def main():
    print("== Smoke: Watchlist Repo ==")

    # Ensure default category exists
    cats = watchlist_repo.list_categories()
    print("Categories:", cats)
    default = next((c for c in cats if c["name"] == "默认"), None)
    if not default:
        cid = watchlist_repo.create_category("默认", "默认分类")
        print("Created default category id:", cid)
        default = {"id": cid, "name": "默认"}

    # Create a temp category
    temp_cat_id = watchlist_repo.create_category("测试分类", "用于冒烟测试")
    print("Created test category id:", temp_cat_id)

    # Add single item (primary mapping = temp_cat_id)
    sid = watchlist_repo.add_item("000001.SZ", "平安银行", temp_cat_id)
    print("Added item id:", sid)

    # Add bulk (with move)
    result = watchlist_repo.add_items_bulk(["000002.SZ", "000001.SZ"], temp_cat_id, on_conflict="ignore")
    print("Bulk result:", result)

    # List items (sorted by updated_at desc)
    lst = watchlist_repo.list_items(page=1, page_size=10, sort_by="updated_at", sort_dir="desc")
    print("List total:", lst["total"])
    for item in lst["items"]:
        print("-", item["code"], item["name"], item.get("category_names"), item.get("last_analysis_time"))

    # Move category for items
    ids = [it["id"] for it in lst["items"] if it["code"] in ("000001.SZ", "000002.SZ")]
    moved = watchlist_repo.update_item_category(ids, default["id"])  # replace all mappings with default
    print("Replaced categories for items count:", moved)

    # Add categories to items (multi)
    added_maps = watchlist_repo.add_categories_to_items(ids, [temp_cat_id])
    print("Add extra category mappings:", added_maps)

    # Remove categories from items
    removed = watchlist_repo.remove_categories_from_items(ids, [temp_cat_id])
    print("Removed category mappings:", removed)

    # Delete items
    deleted = watchlist_repo.delete_items(ids)
    print("Deleted items count:", deleted)

    # Cleanup: delete temp category (should be empty now)
    ok = watchlist_repo.delete_category(temp_cat_id)
    print("Delete test category:", ok)


if __name__ == "__main__":
    main()
