import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pipeline.data_cleaner import _normalize_subprogram_code
import polars as pl

rows=[
    {'organization_sub_code':'B75_A01_04_0','subprogram_code':'B75_A01_04_0','fiscal_year':2027},
    {'organization_sub_code':'D17_B01_51_7','subprogram_code':'D17_B01_51_7','fiscal_year':2027},
    {'organization_sub_code':'W00_A01_08_8616','subprogram_code':'W00_A01_08_8616','fiscal_year':2017},
]

df=pl.DataFrame(rows)
print('input')
print(df)
ndf=_normalize_subprogram_code(df)
print('\nnormalized')
print(ndf)
