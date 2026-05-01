import yaml

with open('data/output/tower_classifications.yaml') as f:
    data = yaml.safe_load(f)

codes = ['M00_R01_01_U109', 'M00_R01_01_U110', 'M00_R01_01_U111', 'M00_R01_01_U112', 'M00_R01_01_U118', 'M00_R01_01_U120', 'M00_R01_01_U121', 'M00_R01_01_U122', 'M00_R01_01_U123']
for code in codes:
    if code in data['classifications']:
        rec = data['classifications'][code]
        print(f"{code}: {rec['subprogram_name']}")
        print(f"  tower={rec['tower']}, it_designation={rec['it_designation']}")
    else:
        print(f"{code}: NOT FOUND")
