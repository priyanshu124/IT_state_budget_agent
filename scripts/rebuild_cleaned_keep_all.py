import sys
from pathlib import Path
proj_root = Path(__file__).resolve().parents[1]
sys.path.append(str(proj_root))

import polars as pl
from src.pipeline.data_loader import COLUMN_ALIASES, _CSV_SCHEMA_OVERRIDES
from src.pipeline.data_cleaner import _apply_text_cleaning, _apply_abbreviations, _TEXT_FIELDS, _ABBREV_FIELDS, _INT_COLUMNS, _CODE_PAD_WIDTHS
from src.utils.config import DATA_PROCESSED

raw = Path('data/raw/budget/2027.csv')
out = Path(DATA_PROCESSED) / '2027_cleaned_nodedup.parquet'

if not raw.exists():
    print('raw missing')
    raise SystemExit(1)

print('Reading raw CSV...')
df = pl.read_csv(raw, infer_schema_length=10000, schema_overrides=_CSV_SCHEMA_OVERRIDES, ignore_errors=True)
print('raw rows,cols=', df.shape)
# rename
rename_map = {col: COLUMN_ALIASES[col] for col in df.columns if col in COLUMN_ALIASES}
if rename_map:
    df = df.rename(rename_map)

# apply fiscal filter (keep same as clean_df)
if 'fiscal_year' in df.columns:
    df = df.filter(pl.col('fiscal_year').cast(pl.Int32, strict=False) >= 2017)
    print('after fiscal_year>=2017 rows=', df.height)

# 1. Strip whitespace from all string columns
str_cols = [c for c, t in zip(df.columns, df.dtypes) if t in (pl.Utf8, pl.String)]
if str_cols:
    df = df.with_columns([pl.col(c).str.strip_chars() for c in str_cols])

# 2. Mojibake + _x000D_ fix for known text fields
text_cols = [c for c in _TEXT_FIELDS if c in df.columns]
if text_cols:
    df = df.with_columns([
        _apply_text_cleaning(pl.col(c)).alias(c) for c in text_cols
    ])

# 3. Abbreviation expansion for short name values
abbrev_cols = [c for c in _ABBREV_FIELDS if c in df.columns]
if abbrev_cols:
    df = df.with_columns([
        _apply_abbreviations(pl.col(c)).alias(c) for c in abbrev_cols
    ])

# 4. Budget: strip thousands-separator commas, cast, fill null
if 'budget' in df.columns:
    df = df.with_columns(
        pl.col('budget').cast(pl.Utf8).str.replace_all(',', '', literal=True).cast(pl.Float64, strict=False).fill_null(0.0)
    )

# 5. Integer columns: cast and fill null → 0
int_exprs = [pl.col(c).cast(t, strict=False).fill_null(0) for c, t in _INT_COLUMNS.items() if c in df.columns]
if int_exprs:
    df = df.with_columns(int_exprs)

# 6. Code columns: zero-pad
pad_exprs = [pl.col(c).cast(pl.Utf8).str.zfill(w) for c, w in _CODE_PAD_WIDTHS.items() if c in df.columns]
if pad_exprs:
    df = df.with_columns(pad_exprs)

print('final rows,cols=', df.shape)
print('unique organization_sub_code=', df.select(pl.col('organization_sub_code').n_unique()).to_series()[0] if 'organization_sub_code' in df.columns else 'N/A')

print('writing parquet to', out)
out.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(out)
print('done')
