import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline.shadow_it_filter import TaxonomyKeywordMatcher

matcher = TaxonomyKeywordMatcher()
print('keywords:', len(matcher._patterns))
print('\nKEYWORDS (first 60):')
for index, (keyword, _) in enumerate(matcher._patterns[:60], 1):
    print(f'{index:02d}. {keyword}')
