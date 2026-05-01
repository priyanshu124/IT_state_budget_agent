import polars as pl
from pathlib import Path

sub_path = Path("data/processed/subobject_codes.csv")
map_path = Path("data/output/cost_pool_classifications.csv")

sub_df = pl.read_csv(sub_path)
map_df = pl.read_csv(map_path)

key = "comptroller_subobject_code"

def normalize(df: pl.DataFrame, key_col: str) -> pl.DataFrame:
    return df.with_columns(
        pl.when(pl.col(key_col).is_null())
        .then(None)
        .otherwise(
            pl.col(key_col)
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.replace(r"\\.0$", "")
            .str.pad_start(4, "0")
        )
        .alias(key_col)
    )

sub_df = normalize(sub_df, key)
map_df = normalize(map_df, key)

# Keep original file metadata columns; refresh only cost pool columns.
existing = [c for c in ["cost_pool", "cost_sub_pool"] if c in sub_df.columns]
if existing:
    sub_df = sub_df.drop(existing)

map_df = map_df.select([key, "cost_pool", "cost_sub_pool"]).unique(subset=[key], keep="first")
result = sub_df.join(map_df, on=key, how="left")

result.write_csv(sub_path)

matched = result.filter(pl.col("cost_pool").is_not_null()).height if "cost_pool" in result.columns else 0
print(f"Updated {sub_path} | rows={result.height} cols={result.width} matched={matched}")
