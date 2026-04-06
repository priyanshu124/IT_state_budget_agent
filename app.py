"""
Lightweight Streamlit chat for embedding in Evidence dashboard.
Run: python -m streamlit run chat/app.py --server.port 8501
"""
 
import os
import streamlit as st
import pandas as pd
import plotly.express as px
from pandas.api.types import is_numeric_dtype
from dotenv import load_dotenv
 
load_dotenv()
 
st.set_page_config(page_title="Budget Query", page_icon="💬", layout="wide")
 
# Minimal styling for iframe embed
st.markdown("""
<style>
    .stApp { background: #FAFAFA; }
    .narrative {
        background: #F5F0EB; border-left: 4px solid #CE1126;
        border-radius: 4px; padding: 16px 20px; margin: 12px 0;
        font-size: 0.92rem; line-height: 1.7; color: #1A1A1A;
    }
</style>
""", unsafe_allow_html=True)
 
API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DB_PATH = os.getenv("MBTSA_DB", "mbtsa_work.duckdb")
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
 
COLORS = ["#CE1126", "#FFD100", "#3B7DD8", "#2EAD6B", "#E67E22"]
CHART_TOP_N = 10
CHART_BG = "#050A17"
CHART_GRID = "#2A3348"
CHART_FONT = "#E6ECF7"
 
 
def fmt(val):
    if val is None or pd.isna(val):
        return "—"
    val = float(val)
    sign = "-" if val < 0 else ""
    abs_val = abs(val)
    if abs_val >= 1e9:
        return f"{sign}${abs_val/1e9:,.1f}B"
    if abs_val >= 1e6:
        return f"{sign}${abs_val/1e6:,.1f}M"
    if abs_val >= 1e3:
        return f"{sign}${abs_val/1e3:,.1f}k"
    return f"{sign}${abs_val:,.0f}"
 
 
def escape_html(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("\n\n", "</p><p style='margin-top:12px;'>")
    text = text.replace("\n", "<br>")
    if not text.startswith("<p"): text = "<p>" + text + "</p>"
    return text


def coerce_numeric_columns(df):
    if df is None or df.empty:
        return df

    converted_df = df.copy()
    for col in converted_df.columns:
        if converted_df[col].dtype == "object":
            candidate = pd.to_numeric(converted_df[col], errors="coerce")
            # Convert when most non-null values are numeric-like.
            threshold = max(1, int(len(converted_df) * 0.7))
            if candidate.notna().sum() >= threshold:
                converted_df[col] = candidate
    return converted_df


def _is_percent_column(col_name):
    name = str(col_name).lower()
    return any(term in name for term in ["pct", "percent", "ratio", "rate"])


def _is_year_or_id_column(col_name):
    name = str(col_name).lower()
    return "year" in name or name.endswith("_id") or name == "id"


def _is_currency_column(col_name):
    return not _is_percent_column(col_name) and not _is_year_or_id_column(col_name)


def _find_fiscal_year_column(columns):
    for col in columns:
        if str(col).lower() == "fiscal_year":
            return col
    return None


def _pick_measure_column(num_cols, dimension=None):
    """Pick numeric metric column using explicit priority; never use fiscal_year as metric."""
    candidates = [c for c in num_cols if c != dimension]
    candidates = [c for c in candidates if not _is_year_or_id_column(c)]
    if not candidates:
        return None

    preferred_terms = [
        "total_spend", "total_amount", "spend", "budget", "amount",
        "it_amount", "non_it_amount", "variance_dollars", "yoy_change",
        "change", "value", "count", "rows",
    ]

    lookup = {str(c).lower(): c for c in candidates}
    for term in preferred_terms:
        if term in lookup:
            return lookup[term]

    for col in candidates:
        if _is_currency_column(col):
            return col

    return candidates[0]


def _pick_dimension_column(cat_cols):
    """Pick categorical dimension using human-readable priority."""
    if not cat_cols:
        return None

    preferred_terms = [
        "name", "category", "tower", "program", "agency", "fund", "designation", "type",
    ]

    for term in preferred_terms:
        for col in cat_cols:
            if term in str(col).lower():
                return col

    return cat_cols[0]


def format_display_df(df):
    if df is None or df.empty:
        return df

    display_df = df.copy()
    for col in display_df.columns:
        name = str(col).lower()
        if name == "fiscal_year":
            display_df[col] = display_df[col].apply(lambda x: "—" if pd.isna(x) else str(int(x)))
            continue

        if is_numeric_dtype(display_df[col]):
            if _is_percent_column(col):
                display_df[col] = display_df[col].apply(lambda x: "—" if pd.isna(x) else f"{float(x):.1f}%")
            elif _is_currency_column(col):
                display_df[col] = display_df[col].apply(fmt)

    return display_df
 
 
@st.cache_resource
def get_agent():
    if not API_KEY: return None
    try:
        from src.agents.query_agent.agent import BudgetQueryAgent
        return BudgetQueryAgent(api_key=API_KEY, db_path=DB_PATH, model=MODEL)
    except Exception as e:
        st.error(f"Agent init failed: {e}")
        return None
 
 
def auto_chart(df):
    if df is None or df.empty or len(df.columns) < 2: return
    df = coerce_numeric_columns(df)
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    cat_cols = [c for c in df.columns if c not in num_cols]

    if not num_cols:
        return

    measure = None
    dimension = None
    fiscal_year_col = _find_fiscal_year_column(df.columns)

    # Chart instructions:
    # 1) If fiscal_year + another metric exists -> line chart over fiscal_year.
    # 2) Otherwise use categorical dimension + numeric measure -> horizontal bar chart (top N).
    if fiscal_year_col and len(num_cols) >= 2:
        dimension = fiscal_year_col
        measure = _pick_measure_column(num_cols, dimension=fiscal_year_col)
    elif cat_cols:
        dimension = _pick_dimension_column(cat_cols)
        measure = _pick_measure_column(num_cols, dimension=dimension)

    if not measure or not dimension:
        return

    if str(dimension).lower() == "fiscal_year":
        chart_df = df.sort_values(dimension).tail(CHART_TOP_N)
    else:
        chart_df = df[df[measure].notna()].sort_values(measure, ascending=False).head(CHART_TOP_N)
        chart_df = chart_df.iloc[::-1]  # Draw largest bars at the top for horizontal orientation.

    if chart_df.empty:
        return

    if str(dimension).lower() == "fiscal_year":
        fig = px.line(
            chart_df,
            x=dimension,
            y=measure,
            markers=True,
            color_discrete_sequence=COLORS,
        )
    else:
        fig = px.bar(
            chart_df,
            x=measure,
            y=dimension,
            orientation="h",
            color_discrete_sequence=COLORS,
        )

    fig.update_layout(
        template="plotly_dark",
        height=420,
        margin=dict(l=20, r=20, t=10, b=40),
        plot_bgcolor=CHART_BG,
        paper_bgcolor=CHART_BG,
        font=dict(color=CHART_FONT, size=14),
        showlegend=False,
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor=CHART_GRID,
        zeroline=False,
        tickfont=dict(color=CHART_FONT),
        title_font=dict(color=CHART_FONT),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=CHART_GRID,
        zeroline=False,
        tickfont=dict(color=CHART_FONT),
        title_font=dict(color=CHART_FONT),
    )

    if str(dimension).lower() != "fiscal_year":
        fig.update_yaxes(automargin=True, tickfont=dict(size=11))

    if _is_currency_column(measure):
        if str(dimension).lower() == "fiscal_year":
            fig.update_yaxes(tickformat="$,.2s")
        else:
            fig.update_xaxes(tickformat="$,.2s")
    elif _is_percent_column(measure):
        if str(dimension).lower() == "fiscal_year":
            fig.update_yaxes(tickformat=".1f")
        else:
            fig.update_xaxes(tickformat=".1f")

    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
 
 
# Quick queries
qcols = st.columns(4)
quick_queries = [
    "Variance for Dept of Health between FY2026 and FY2027?",
    "Which agencies had biggest budget increases?",
    "All programs funded by ARPA",
    "Special Funds breakdown by category",
    "What percentage of budget is federal funds?",
    "How has education budget changed over 8 years?",
    "Top 10 IT programs by budget",
    "Compare MITDP vs ITIF budget",
]
for i, q in enumerate(quick_queries):
    with qcols[i % 4]:
        if st.button(q, use_container_width=True, key=f"q_{i}"):
            st.session_state.quick = q
            st.rerun()
 
if "messages" not in st.session_state:
    st.session_state.messages = []
 
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            st.markdown(f'<div class="narrative">{escape_html(msg["narrative"])}</div>', unsafe_allow_html=True)
            if msg.get("df") is not None and not msg["df"].empty:
                st.dataframe(format_display_df(msg["df"]), use_container_width=True, hide_index=True)
                auto_chart(msg["df"])
            with st.expander("SQL"): st.code(msg["sql"], language="sql")
        else:
            st.write(msg["content"])
 
prompt = st.chat_input("Ask about Maryland's budget...")
if "quick" in st.session_state:
    prompt = st.session_state.pop("quick")
 
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.write(prompt)
 
    with st.chat_message("assistant"):
        agent = get_agent()
        if not agent:
            st.error("Set ANTHROPIC_API_KEY.")
        else:
            with st.spinner("Analyzing..."):
                state = agent.query(prompt)
            narrative = state.get("narrative", "")
            st.markdown(f'<div class="narrative">{escape_html(narrative)}</div>', unsafe_allow_html=True)
            df = pd.DataFrame()
            raw = state.get("raw_results", {})
            if raw.get("rows") and raw.get("columns"):
                df = pd.DataFrame(raw["rows"], columns=raw["columns"])
                df = coerce_numeric_columns(df)
                st.dataframe(format_display_df(df), use_container_width=True, hide_index=True)
                auto_chart(df)
            with st.expander("SQL"): st.code(state.get("sql", ""), language="sql")
            st.session_state.messages.append({
                "role": "assistant", "narrative": narrative,
                "df": df, "sql": state.get("sql", ""),
            })
            st.rerun()