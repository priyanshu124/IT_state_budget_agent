import csv

with open('data/processed/subprograms.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"Total rows: {len(rows)}")
print(f"Total columns: {len(rows[0]) if rows else 0}")
print(f"\nColumns: {list(rows[0].keys()) if rows else []}")

# Check is_it=false rows have metadata
is_it_false = [r for r in rows if r.get('is_it') == 'false']
print(f"\nRows with is_it=false: {len(is_it_false)}")

# Check sample is_it=false row
if is_it_false:
    sample = is_it_false[0]
    print(f"\nSample is_it=false row:")
    print(f"  organization_sub_code: {sample.get('organization_sub_code')}")
    print(f"  agency_name: {sample.get('agency_name')}")
    print(f"  subprogram_name: {sample.get('subprogram_name')}")
    print(f"  subprogram_code: {sample.get('subprogram_code')}")
    print(f"  tower: {sample.get('tower', 'NULL')}")
    print(f"  is_it: {sample.get('is_it')}")

# Check those trauma codes specifically
print(f"\nTrauma programs (is_it=false):")
codes = ['M00_R01_01_U109', 'M00_R01_01_U110', 'M00_R01_01_U111', 'M00_R01_01_U112']
for row in rows:
    if row.get('organization_sub_code') in codes:
        print(f"  {row['organization_sub_code']}: {row['agency_name']} | {row['subprogram_name']}")
        print(f"    code={row['subprogram_code']}, tower={row.get('tower', 'NULL')}")
