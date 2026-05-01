import polars as pl
from pathlib import Path

candidates = [Path('data/processed/2027_cleaned.parquet'), Path('data/processed/budget_cleaned.parquet'), Path('data/raw/budget/2027.csv')]
for f in candidates:
    if f.exists():
        try:
            if f.suffix == '.parquet':
                df = pl.read_parquet(f)
            else:
                df = pl.read_csv(f)
            print(f"{f}: rows={df.shape[0]}, cols={df.shape[1]}")
        except Exception as e:
            print(f"{f}: error {e}")
    else:
        print(f"{f}: MISSING")

extras = [Path('data/processed/subprograms.csv'), Path('data/processed/subobject_codes.csv'), Path('data/output/final_budget_enriched.csv')]
for f in extras:
    if f.exists():
        df = pl.read_csv(f)
        print(f"{f}: rows={df.shape[0]}, cols={df.shape[1]}")
    else:
        print(f"{f}: MISSING")
