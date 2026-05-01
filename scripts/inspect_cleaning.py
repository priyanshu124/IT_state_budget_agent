import polars as pl
from pathlib import Path

raw = Path('data/raw/budget/2027.csv')
cleaned = Path('data/processed/2027_cleaned.parquet')

print('RAW EXISTS:', raw.exists())
if raw.exists():
    # count lines without loading full CSV to memory via streaming
    with raw.open('rb') as f:
        lines = sum(1 for _ in f)
    print(f'{raw}: lines={lines}')
else:
    print(f'{raw}: MISSING')

print('CLEANED EXISTS:', cleaned.exists())
if cleaned.exists():
    df = pl.read_parquet(cleaned)
    print(f'{cleaned}: rows={df.height}, cols={df.width}')
    if 'organization_sub_code' in df.columns:
        uniq = df.select(pl.col('organization_sub_code').n_unique()).to_series()[0]
        print('cleaned unique organization_sub_code:', uniq)
        # show duplicates in cleaned (should be unique after dedup)
        counts = df.group_by('organization_sub_code').agg(pl.count()).filter(pl.col('count')>1)
        print('duplicate groups in cleaned (should be 0):', counts.height)
    else:
        print('organization_sub_code not present in cleaned')
else:
    print(f'{cleaned}: MISSING')

# Inspect raw CSV for organization_sub_code unique values sample (streaming first 200k rows)
if raw.exists():
    # read in chunks to avoid huge memory; but polars can scan_csv with n_rows
    try:
        sample = pl.read_csv(raw, n_rows=200000)
        if 'Organization Sub Code' in sample.columns:
            sample = sample.rename({'Organization Sub Code':'organization_sub_code'})
        elif 'organization_sub_code' not in sample.columns:
            print('organization_sub_code not found in raw sample columns:', sample.columns)
        if 'organization_sub_code' in sample.columns:
            print('raw sample rows=', sample.height)
            print('raw sample unique organization_sub_code=', sample.select(pl.col('organization_sub_code').n_unique()).to_series()[0])
    except Exception as e:
        print('Error reading raw sample:', e)
