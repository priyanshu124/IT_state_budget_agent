import csv
import yaml
from pathlib import Path

src = Path('configs/cost_pool_mappings.yaml')
out = Path('data/output/cost_pool_classifications.csv')

data = yaml.safe_load(src.read_text(encoding='utf-8')) or {}
mappings = data.get('mappings', {})

out.parent.mkdir(parents=True, exist_ok=True)
with out.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(
        f,
        fieldnames=['comptroller_subobject_code', 'cost_pool', 'cost_sub_pool'],
    )
    w.writeheader()
    for code, payload in mappings.items():
        w.writerow({
            'comptroller_subobject_code': str(code),
            'cost_pool': payload.get('cost_pool', ''),
            'cost_sub_pool': payload.get('cost_sub_pool', ''),
        })

print(f'Wrote {len(mappings)} rows to {out}')
