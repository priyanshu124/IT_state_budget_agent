from pathlib import Path
p = Path('src/agents/prompts/classify_towers.py')
s = p.read_bytes()
print('LEN', len(s))
print(s[-400:])
