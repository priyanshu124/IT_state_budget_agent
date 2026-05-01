from pathlib import Path
import csv
import sys
from pathlib import Path as _P

# Ensure project root is on sys.path so `src` imports work when running scripts.
sys.path.insert(0, str(_P(__file__).resolve().parents[1]))

from src.agents.tower_classifier import TowerClassifier

# Read subprograms and pick confirmed IT rows
p = Path('data/processed/subprograms.csv')
if not p.exists():
    print('Subprograms CSV not found:', p)
    raise SystemExit(1)

with p.open(encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# Filter confirmed IT rows using same logic as classifier
it_rows = [r for r in rows if str(r.get('is_it','')).strip().upper() == 'TRUE']

print(f'Loaded {len(rows)} total rows, {len(it_rows)} confirmed IT rows (showing up to 20)')

# Use an unbound call to _build_records_payload with a dummy self
class Dummy:
    F50_DESC_LIMIT = 150

dummy = Dummy()

payload = TowerClassifier._build_records_payload(dummy, it_rows[:20])

print('\n=== First 20 payload lines ===\n')
print('\n'.join(payload.splitlines()[:20]))
