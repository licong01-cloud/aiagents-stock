import csv
from pathlib import Path


def audit_file(path: Path, name: str) -> None:
    print(f"=== FILE: {name} ===")
    with path.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)

        # 确定单位列
        unit_col = None
        for cand in ("单位", "来源单位"):
            if cand in header:
                unit_col = cand
                break
        if unit_col is None:
            print("  [WARN] 未找到单位列")
            return

        unit_idx = header.index(unit_col)
        ds_idx = header.index("数据集") if "数据集" in header else 0
        field_idx = header.index("规范字段名") if "规范字段名" in header else 1
        zh_idx = header.index("中文字段名") if "中文字段名" in header else None

        empty_rows = []
        for lineno, row in enumerate(reader, start=2):
            if len(row) <= unit_idx:
                continue
            if row[unit_idx].strip() == "":
                ds = row[ds_idx] if len(row) > ds_idx else ""
                fld = row[field_idx] if len(row) > field_idx else ""
                zh = row[zh_idx] if zh_idx is not None and len(row) > zh_idx else ""
                empty_rows.append((lineno, ds, fld, zh))

        print(f"  EMPTY unit rows: {len(empty_rows)}")
        for lineno, ds, fld, zh in empty_rows[:30]:
            print(f"  line {lineno}: {ds}.{fld}  zh={zh!r}")
        if len(empty_rows) > 30:
            print(f"  ... and {len(empty_rows) - 30} more")
    print()


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    docs_dir = repo_root / "docs"

    files = [
        (docs_dir / "data_schema_fields.csv", "data_schema_fields.csv"),
        (docs_dir / "data_schema_source_mapping.csv", "data_schema_source_mapping.csv"),
    ]

    for path, name in files:
        if not path.exists():
            print(f"[WARN] 文件不存在: {path}")
            continue
        audit_file(path, name)


if __name__ == "__main__":
    main()
