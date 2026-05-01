from pathlib import Path
import sys
from collections import Counter

try:
    import polars as pl
except Exception:
    pl = None


def check_parquet(path):
    p = Path(path)
    if not p.exists():
        print(f"parquet_missing: {path}")
        return
    if not pl:
        print(f"polars_missing_for_parquet: {path}")
        return
    df = pl.read_parquet(p)
    if 'organization_sub_code' not in df.columns:
        print(f"parquet_missing_col: {path} (organization_sub_code)")
        return
    s = df['organization_sub_code'].cast(pl.Utf8)
    vals = s.to_list()
    counts = Counter()
    for v in vals:
        if v is None:
            continue
        vv = v.strip()
        if vv and len(vv) < 13:
            counts[vv] += 1
    uniq = list(counts.keys())
    print(f"parquet: {path} rows={df.height} short_unique={len(uniq)}")
    for code, c in list(counts.items())[:100]:
        print(f"  {code!r}: {c}")


def check_csv(path, col_name):
    p = Path(path)
    if not p.exists():
        print(f"csv_missing: {path}")
        return
    import csv
    with p.open(encoding='utf-8-sig', errors='replace') as f:
        r = csv.DictReader(f)
        if col_name not in (r.fieldnames or []):
            print(f"csv_missing_col: {path} col:{col_name}")
            return
        cnt = Counter()
        total = 0
        for row in r:
            total += 1
            val = (row.get(col_name) or '').strip()
            if len(val) < 13:
                cnt[val] += 1
        print(f"csv: {path} rows={total} short_unique={len(cnt)}")
        for code, c in list(cnt.items())[:100]:
            print(f"  {code!r}: {c}")


if __name__ == '__main__':
    check_parquet('data/processed/2027_cleaned.parquet')
    check_parquet('data/processed/subprograms.parquet')
    check_csv('data/processed/subprograms.csv', 'organization_sub_code')
    check_csv('data/raw/budget/2027.csv', 'Organization Sub Code')
