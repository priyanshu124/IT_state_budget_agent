"""
Appendix K — Major IT Development Projects extractor.
Outputs:
  appendix_k_projects.csv   : one row per project
  appendix_k_funding.csv    : IT Project Funding table rows
  appendix_k_dev_costs.csv  : IT Development Costs table rows
  appendix_k_summary.csv    : agency-level summary tables (pages 193-196)
"""

import re, csv, json
from pathlib import Path
import pdfplumber

# Resolve paths relative to project root
PROJECT_ROOT  = Path(__file__).parent.parent.parent
PDF_PATH      = PROJECT_ROOT / "data" / "raw" / "highlights" / "2027.pdf"
OUT_DIR       = PROJECT_ROOT / "data" / "processed" / "mitdp"
APP_K_START   = 133
SUMMARY_START = 193
APP_K_END     = 196

TBD_RE = re.compile(r"\bTBD\b")
RANGE_RE = re.compile(r'\$[\d]+M\s*[-–]\s*\$[\d]+M')

def clean(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()

def parse_number(s):
    s = clean(s).replace(',','').replace('$','').replace(' ','')
    if s in ('','-','–','TBD','N/A'):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None

def parse_header(text):
    """
    Parse the structured header block at the top of each project page.
    Layout (from raw text inspection):
      line 0: 'Estimated Cost to Complete Project'
      line 1: '[title part 1 OR 'Project Title: <title>'] Estimated Cost'
      line 2: '[title part 2 OR 'Estimated Total Cost']'
      line 3: 'Remaining to'
      line 4: 'Appropriation Code: <code>  at Completion'
      line 5: 'Complete'
      line 6: 'Sub-Program Code: <code> $XM - $YM $XM - $YM'
    """
    lines = text.split('\n')

    # ── title ──────────────────────────────────────────────────────────
    title = ''
    for i, line in enumerate(lines):
        if 'Project Title:' in line:
            # title on same line after label, strip trailing noise
            after = re.sub(r'Estimated Cost.*$', '', line.replace('Project Title:', '')).strip()
            # check if previous line contains wrapped title fragment
            if i > 0:
                prev = clean(lines[i-1])
                noise = {'Estimated Cost to Complete Project','Project Summary:',
                         'IT Project Funding','IT Development Costs',''}
                if prev not in noise and not prev.startswith(('Sub-','Appropriation','Remaining','Complete')):
                    after = f"{prev} {after}".strip() if after else prev
            # check if next line has continuation (e.g. "(PRRMS)" or "replacement")
            if i+1 < len(lines):
                nxt = clean(lines[i+1])
                noise2 = {'Estimated Total Cost','Remaining to','at Completion',
                          'Complete','Project Summary:'}
                if nxt not in noise2 and not nxt.startswith(('Sub-','Appropriation')) \
                   and not RANGE_RE.search(nxt) and nxt:
                    after = f"{after} {nxt}".strip()
            title = clean(after)
            break

    # ── appropriation code ─────────────────────────────────────────────
    approp = ''
    m = re.search(r'Appropriation Code:\s*([^\n]+)', text)
    if m:
        approp = re.sub(r'\s*(at Completion|Remaining|Complete).*$', '', m.group(1)).strip()

    # ── sub-program code and cost ranges ──────────────────────────────
    subprog = ''
    cost_remaining = ''
    cost_total = ''
    m = re.search(r'Sub-Program Code:\s*([^\n]+)', text)
    if m:
        raw = m.group(1).strip()
        ranges = RANGE_RE.findall(raw)
        # strip cost ranges and TBD tokens to get just the code
        subprog = RANGE_RE.sub('', raw).strip()
        subprog = re.sub(r'\bTBD\b', '', subprog).strip()
        if len(ranges) >= 2:
            cost_remaining, cost_total = ranges[0], ranges[1]
        elif len(ranges) == 1:
            cost_remaining = cost_total = ranges[0]
        else:
            # check for TBD TBD pattern
            tdbs = re.findall(r'\bTBD\b', raw)
            if len(tdbs) >= 2:
                cost_remaining, cost_total = 'TBD', 'TBD'
            elif len(tdbs) == 1:
                cost_remaining = cost_total = 'TBD'

    # ── project summary ────────────────────────────────────────────────
    m = re.search(r'Project Summary:\s*\n(.*?)(?=\nIT Project Funding|\nIT Development|\Z)',
                  text, re.DOTALL)
    summary = clean(m.group(1)) if m else ''

    return title, approp, subprog, cost_remaining, cost_total, summary


def parse_tables(page, proj_id, title, mitdp_id=''):
    """Extract funding and dev cost table rows from page."""
    funding_rows  = []
    dev_cost_rows = []

    tables = page.extract_tables()
    for t in tables:
        if not t:
            continue
        flat = ' '.join(str(c or '') for row in t for c in row)

        # IT Project Funding
        if 'Annual Appropriation' in flat and 'Total Funding' in flat:
            skip = {'Funding Type','Prior to','FY 2025','FY 2026','FY 2027',
                    'Actual','Appropriation','Allowance','Total Funding',
                    'to Date','Project Funding',''}
            cols = ['prior_to_fy2025','actual_fy2025','appropriation_fy2026',
                    'allowance_fy2027','total_funding_to_date']
            for row in t:
                cells = [clean(c or '') for c in row]
                if not cells[0] or cells[0] in skip:
                    continue
                vals = [c for c in cells[1:] if c != '']
                rec = {'project_id': proj_id, 'mitdp_id': mitdp_id, 'project_title': title,
                       'funding_type': cells[0]}
                for ci, cn in enumerate(cols):
                    rec[cn] = parse_number(vals[ci]) if ci < len(vals) else None
                funding_rows.append(rec)

        # IT Development Costs
        elif 'Spend Plan' in flat and ('ITIF' in flat or 'Agency Funds' in flat):
            skip = {'Funding Type','Prior to','FY 2025','FY 2026','FY 2027',
                    'Actual','Spend Plan','Projected','Outyears',
                    'Project Costs',''}
            cols = ['prior_to_fy2025','actual_fy2025','spend_plan_fy2026',
                    'spend_plan_fy2027','projected_outyears']
            for row in t:
                cells = [clean(c or '') for c in row]
                if not cells[0] or cells[0] in skip:
                    continue
                vals = [c for c in cells[1:] if c != '']
                rec = {'project_id': proj_id, 'mitdp_id': mitdp_id, 'project_title': title,
                       'funding_type': cells[0]}
                for ci, cn in enumerate(cols):
                    rec[cn] = parse_number(vals[ci]) if ci < len(vals) else None
                dev_cost_rows.append(rec)

    return funding_rows, dev_cost_rows


# ── main ───────────────────────────────────────────────────────────────────────

# Load MITDP IDs from doit_project.json
DOIT_JSON = PROJECT_ROOT / "src" / "mitdp" / "doit_project.json"
mitdp_ids = {}
json_data_by_idx = {}
EXCLUDE_FIELDS = {
    "EAC",
    "FY25 Forecasted Spend",
    "FY25 Actual Spend",
    "FY26 Project Funding",
    "FY26 Forecasted Spend",
    "Project Summary",
}

if DOIT_JSON.exists():
    with open(DOIT_JSON) as f:
        doit_projects = json.load(f)
        for idx, proj in enumerate(doit_projects):
            mitdp_ids[idx] = proj.get("MITDP ID", "")
            # Store JSON fields excluding specified ones
            json_data_by_idx[idx] = {k: v for k, v in proj.items() 
                                      if k not in EXCLUDE_FIELDS and k != "MITDP ID"}

projects, funding, dev_costs, summaries = [], [], [], []
project_count = 0

with pdfplumber.open(PDF_PATH) as pdf:
    # project pages
    for pg in range(APP_K_START, SUMMARY_START):
        page = pdf.pages[pg - 1]
        text = page.extract_text() or ''
        if 'Project Title:' not in text:
            continue

        proj_id = f"pg{pg}"
        title, approp, subprog, cost_rem, cost_tot, summary = parse_header(text)
        mitdp_id = mitdp_ids.get(project_count, "")

        rec = {
            'page':                          pg,
            'project_id':                    proj_id,
            'mitdp_id':                      mitdp_id,
            'project_title':                 title,
            'appropriation_code':            approp,
            'sub_program_code':              subprog,
            'est_cost_remaining':            cost_rem,
            'est_total_cost_at_completion':  cost_tot,
            'project_summary':               summary,
        }
        
        # Merge JSON fields
        if project_count in json_data_by_idx:
            rec.update(json_data_by_idx[project_count])
        
        projects.append(rec)

        f_rows, d_rows = parse_tables(page, proj_id, title, mitdp_id)
        funding.extend(f_rows)
        dev_costs.extend(d_rows)
        project_count += 1

    # summary pages 193-196
    for pg in range(SUMMARY_START, APP_K_END + 1):
        page = pdf.pages[pg - 1]
        text = page.extract_text() or ''
        table_title = clean(text.split('\n')[0]) if text else f'page_{pg}'
        for t in page.extract_tables():
            if not t:
                continue
            for row in t:
                cells = [clean(c or '') for c in row]
                if not any(cells):
                    continue
                summaries.append({
                    'page': pg, 'table_title': table_title,
                    **{f'col{i+1}': cells[i] if i < len(cells) else ''
                       for i in range(6)}
                })

# ── write ──────────────────────────────────────────────────────────────────────

def write_csv(path, rows, fields=None):
    """Write CSV with optional dynamic field detection."""
    if not rows:
        return
    # If fields not specified, use all keys from all rows
    if fields is None:
        fields = list(dict.fromkeys([k for row in rows for k in row.keys()]))
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print(f"  {path.name}: {len(rows)} rows")

# Write projects with all fields (extracted + JSON)
write_csv(OUT_DIR / 'projects.csv', projects)

# Write funding and dev_costs with specified fields
write_csv(OUT_DIR / 'funding.csv', funding, [
    'project_id','mitdp_id','project_title','funding_type',
    'prior_to_fy2025','actual_fy2025','appropriation_fy2026',
    'allowance_fy2027','total_funding_to_date'])

write_csv(OUT_DIR / 'dev_costs.csv', dev_costs, [
    'project_id','mitdp_id','project_title','funding_type',
    'prior_to_fy2025','actual_fy2025','spend_plan_fy2026',
    'spend_plan_fy2027','projected_outyears'])

write_csv(OUT_DIR / 'summary.csv', summaries, [
    'page','table_title','col1','col2','col3','col4','col5','col6'])

print(f"\nTotal: {len(projects)} projects | {len(funding)} funding rows | "
      f"{len(dev_costs)} dev cost rows | {len(summaries)} summary rows")
