from src.agents.tower_classifier import TowerClassifier

class Dummy:
    F50_DESC_LIMIT = 150

dummy = Dummy()
rows = [
    {'organization_sub_code':'C1','subprogram_name':'App X','agency_name':'Agency A','program_name':'Program P','description':'Some desc','it_designation':'MITDP','is_it':'TRUE'},
    {'organization_sub_code':'C2','subprogram_name':'Shadow Y','agency_name':'Agency B','program_name':'Program Q','description':'Desc2','shadow_it_reason':'kw=cloud','it_designation':'SHADOW_IT','is_it':'TRUE'},
    {'organization_sub_code':'C3','subprogram_name':'Enriched Z','agency_name':'Agency C','program_name':'Program R','description':'Desc3','it_designation':'ENRICHED','is_it':'TRUE'},
]
print(TowerClassifier._build_records_payload(dummy, rows))
