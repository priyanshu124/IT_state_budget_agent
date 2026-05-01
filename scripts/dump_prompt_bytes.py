p = 'src/agents/prompts/classify_towers.py'
with open(p, 'rb') as f:
    b = f.read()
print('Length:', len(b))
# show bytes around 80-140 (1-based lines approx)
start = 0
for i in range(1, 140):
    if i*10 > len(b):
        break
    chunk = b[i*10:(i+1)*10]
    print(i*10, repr(chunk))
print('\nFull tail (last 300 bytes):')
print(repr(b[-300:]))
