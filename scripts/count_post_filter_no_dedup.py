import sys
from pathlib import Path
proj_root = Path(__file__).resolve().parents[1]
sys.path.append(str(proj_root))
import polars as pl
from src.pipeline.data_loader import COLUMN_ALIASES, _CSV_SCHEMA_OVERRIDES

raw = Path('data/raw/budget/2027.csv')
if not raw.exists():
    print('raw missing')
    raise SystemExit(1)

# read with schema overrides similar to data_loader
print('Reading raw CSV (may take a moment)')
df = pl.read_csv(raw, infer_schema_length=10000, schema_overrides=_CSV_SCHEMA_OVERRIDES, ignore_errors=True)
print('raw rows,cols=', df.shape)
# rename
rename_map = {col: COLUMN_ALIASES[col] for col in df.columns if col in COLUMN_ALIASES}
if rename_map:
    df = df.rename(rename_map)

# ensure fiscal_year exists
if 'fiscal_year' in df.columns:
    df = df.filter(pl.col('fiscal_year').cast(pl.Int32, strict=False) >= 2017)
    print('after fiscal_year>=2017 rows=', df.height)
else:
    print('fiscal_year not in columns; skipping fiscal filter')

if 'organization_sub_code' in df.columns:
    print('unique organization_sub_code (raw after fiscal filter)=', df.select(pl.col('organization_sub_code').n_unique()).to_series()[0])
else:
    print('organization_sub_code not in columns')

print('Sample rows:')
print(df.head(5))
