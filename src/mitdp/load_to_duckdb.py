"""Load MITDP parquet files into DuckDB for Evidence.dev dashboard."""

import duckdb
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
MITDP_DIR = PROJECT_ROOT / "data" / "processed" / "mitdp"
DUCKDB_PATH = PROJECT_ROOT / "dbt-sql" / "mbtsa_work.duckdb"

# Connect
conn = duckdb.connect(str(DUCKDB_PATH))

print(f"Loading MITDP CSV files into {DUCKDB_PATH.name}...")

# Create schema if not exists
conn.execute("CREATE SCHEMA IF NOT EXISTS mitdp")

# Load the three main tables
tables = {
    "projects": {"csv": MITDP_DIR / "projects.csv"},
    "funding": {"csv": MITDP_DIR / "funding.csv"},
    "dev_costs": {"csv": MITDP_DIR / "dev_costs.csv"},
}

for table_name, paths in tables.items():
    parquet_path = paths.get("parquet")
    csv_path = paths.get("csv")
    # Drop existing table if any
    conn.execute(f"DROP TABLE IF EXISTS mitdp.{table_name}")
    if csv_path and csv_path.exists():
        conn.execute(f"CREATE TABLE mitdp.{table_name} AS SELECT * FROM read_csv_auto('{csv_path}')")
        row_count = conn.execute(f"SELECT count(*) FROM mitdp.{table_name}").fetchone()[0]
        print(f"  ✓ Loaded {table_name} from {csv_path.name}: {row_count:,} rows")
    else:
        missing = csv_path.name if csv_path else table_name
        print(f"  ✗ {missing} not found for {table_name}")

# Verify schema for mitdp_projects
print("\nmitdp.projects columns:")
schema = conn.execute("DESCRIBE mitdp.projects").fetchall()
for col_name, col_type, *_ in schema[:10]:
    print(f"  {col_name}: {col_type}")
print(f"  ... +{len(schema) - 10} more")

conn.close()
print(f"\n✓ Complete! All tables loaded into {DUCKDB_PATH.name}")
