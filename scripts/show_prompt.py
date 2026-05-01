import sys
from pathlib import Path
import csv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.tbm_reference import build_tower_reference_text

# Paths
subprograms = Path('data/processed/subprograms.csv')
towers = Path('data/raw/tbm/it_towers.csv')

if not subprograms.exists():
    print('Subprograms file not found:', subprograms)
    raise SystemExit(1)
if not towers.exists():
    print('Towers file not found:', towers)
    raise SystemExit(1)

# Load first 50 confirmed IT rows
with subprograms.open(encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

it_rows = [r for r in rows if str(r.get('is_it','')).strip().upper() == 'TRUE']
print(f'Loaded {len(rows)} rows, {len(it_rows)} confirmed IT rows; using first {min(50, len(it_rows))} for payload')

# Build taxonomy
taxonomy_str = build_tower_reference_text(towers)

# Read prompt file and extract SYSTEM_PROMPT and USER_PROMPT blocks without importing
prompt_path = Path('src/agents/prompts/classify_towers.py')
text = prompt_path.read_text(encoding='utf-8')

def extract_triple(name: str, text: str) -> str:
    token = f"{name}\s*=\s*""""
    # fallback: search for name = """
    start = text.find(name + " = \"\"\"")
    if start == -1:
        start = text.find(name + "=\"\"\"")
    if start == -1:
        # try simple search
        token_start = text.find(name)
        if token_start == -1:
            raise ValueError(f"Prompt variable {name} not found")
        # find the first triple-quote after name
        tq = text.find('"""', token_start)
        if tq == -1:
            raise ValueError(f"Opening triple quotes not found for {name}")
        start_idx = tq + 3
    else:
        # find opening triple quotes after start
        tq = text.find('"""', start)
        if tq == -1:
            raise ValueError(f"Opening triple quotes not found for {name}")
        start_idx = tq + 3

    end_idx = text.find('"""', start_idx)
    if end_idx == -1:
        raise ValueError(f"Closing triple quotes not found for {name}")
    return text[start_idx:end_idx]

SYSTEM_PROMPT = extract_triple('SYSTEM_PROMPT', text)
USER_PROMPT = extract_triple('USER_PROMPT', text)

# Build records payload similarly to TowerClassifier._build_records_payload
def _designation_format(designation: str) -> str:
    if not designation:
        return 'enriched'
    normalized = str(designation).strip().upper()
    if normalized in {'MITDP', 'ITIF'}:
        return 'slim'
    if normalized == 'SHADOW_IT':
        return 'shadow_it'
    return 'enriched'

def _clean_field(value: object) -> str:
    text = str(value or '')
    return text.replace('|', ' /').replace('\n', ' ').replace('\r', ' ').strip()

lines = []
for r in it_rows[:50]:
    code = str(r.get('organization_sub_code','')).strip()
    name = _clean_field(r.get('subprogram_name'))
    agency = _clean_field(r.get('agency_name'))
    unit = _clean_field(r.get('unit_name',''))
    program = _clean_field(r.get('program_name',''))
    reason = _clean_field(r.get('shadow_it_reason',''))
    desig = _designation_format(r.get('it_designation',''))
    if desig == 'slim':
        lines.append(f"{code}|{name}|{agency}|{unit}|{program}")
    elif desig == 'shadow_it':
        lines.append(f"{code}|{name}|{agency}|{unit}|{program}|{reason}")
    else:
        lines.append(f"{code}|{name}|{agency}|{unit}|{program}")

records_str = '\n'.join(lines)

# Print prompts
print('\n' + '='*80)
print('SYSTEM PROMPT')
print('='*80)
print(SYSTEM_PROMPT)
print('\n' + '='*80)
print('USER PROMPT')
print('='*80)
print(USER_PROMPT.format(taxonomy=taxonomy_str, records=records_str))
