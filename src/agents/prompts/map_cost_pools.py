"""
Prompt templates for Agent 2: Cost Pool Mapper (v2).

Root cause of v1 errors: _build_slim_taxonomy stripped descriptions from
the taxonomy YAML before injecting into the prompt. The model received only
pool/sub-pool names — no definitions — and fell back on its own priors:
  - "Hardware" matched any physical equipment (vehicles, medical equipment, etc.)
  - "Data Center Facilities" matched all utilities and buildings
  - "Outside Services" matched anything going to an external party, including grants

Fix: _build_slim_taxonomy must be replaced with _build_full_taxonomy (below)
to include the description field for every pool and sub-pool from the YAML.
The model then maps against actual TBM definitions, not name pattern-matching.
"""


def build_full_taxonomy(taxonomy_data: dict) -> str:
    """
    Build a taxonomy string that includes pool and sub-pool descriptions.
    Replace _build_slim_taxonomy in CostPoolMapper with this.

    Args:
        taxonomy_data: Parsed YAML dict from tbm_taxonomy_v5.yaml

    Returns:
        Multi-line string injected as {taxonomy} in USER_PROMPT
    """
    lines = []
    for cp in taxonomy_data["cost_pools"]:
        lines.append(f"COST POOL: {cp['name']}")
        lines.append(f"  Definition: {cp.get('description', '')}")
        for sp in cp.get("opex_sub_pools", []):
            lines.append(f"  SUB-POOL: {sp['name']}")
            lines.append(f"    Definition: {sp.get('description', '')}")
        for sp in cp.get("capex_sub_pools", []):
            lines.append(f"  SUB-POOL (CapEx): {sp['name']}")
            lines.append(f"    Definition: {sp.get('description', '')}")
        lines.append("")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are a government finance analyst mapping Maryland state \
accounting subobject codes to TBM (Technology Business Management) cost pools.

You will receive:
1. The TBM cost pool taxonomy with the name AND full definition of every pool \
and sub-pool. These definitions are the authoritative source of truth. \
Map each code based on what the definition says the pool covers — \
do not rely on the pool name alone or your own understanding of TBM.
2. Subobject codes in pipe-delimited format: code|name|parent_object_name

For EVERY code return exactly one pipe-delimited line:
  code|cost_pool|cost_sub_pool

Rules:
- Map EVERY code. Do not skip any.
- Use EXACT cost pool and sub-pool names from the taxonomy provided.
- Every code gets exactly ONE cost pool and ONE sub-pool.
- The parent_object_name provides important context \
(e.g. "Grants, Subsidies, and Contributions", "Motor Vehicle Operation and Maintenance", \
"Equipment - Replacement").

Decision rules for the hardest cases — apply these before anything else:

GRANTS (parent_object_name = "Grants, Subsidies, and Contributions"):
  Map to the Grants cost pool. This includes all Object 12 codes: aid to \
political subdivisions, educational grants, health grants, public assistance \
payments, contributions to non-governmental entities, inmate payments, \
pension grants. These are government transfer payments, not procured services.

VEHICLES (parent_object_name = "Motor Vehicle Operation and Maintenance"):
  All vehicle codes map to Misc Costs / Other Operating. Vehicles are not \
IT hardware. This includes purchase, gas/oil, maintenance, insurance, garage \
rent for cars, trucks, aircraft, watercraft, and other land vehicles.

HARDWARE boundary — IT hardware vs. physical assets:
  Map to Hardware only if the subobject name contains one of: \
Data Processing, DP, Computer, Mainframe, Minicomputer, Microcomputer, \
Workstation, Terminal, Teleprocessing, DASD, Peripheral, Imaging System, \
Word Processing, Memory, Storage Device, Disk, Tape Device, Data Entry Device.
  All other physical equipment (agricultural, medical, dental, laundry, \
cleaning, laboratory, recreational, veterinary, household, audio-visual, \
power plant, office equipment, building equipment) maps to Misc Costs.

DATA CENTER FACILITIES boundary:
  Only map to Data Center Facilities if the subobject explicitly describes \
IT infrastructure — data center air conditioning (DP Air Conditioning), \
data center flooring (DP Computer Flooring), or capital costs for \
constructing server rooms. General utilities (electricity, water, gas, \
steam, MES charges, energy loans), general rent, land, roads, and \
building construction are NOT data center costs — map those to Misc Costs.

TRAVEL (parent_object_name = "Travel"):
  Map to Misc Costs / Other Operating. Travel is a discretionary operating \
expense, not a labor cost.

RETURN ONLY the pipe-delimited lines. No headers, no explanation, no markdown."""


USER_PROMPT = """TBM Cost Pools and Sub-Pools — full definitions from the taxonomy:
{taxonomy}

---

Map each subobject code below to a cost_pool and cost_sub_pool.
Input format: code|subobject_name|parent_object_name
Output format: code|cost_pool|cost_sub_pool

{codes}"""