"""
Streamlit chat — iframe embed mode for Evidence dashboard.
Run: python -m streamlit run chat/chat_embed.py --server.port 8501

Differences from app.py:
  - No page header, no quick-query buttons
  - Compact layout sized for a sidebar/drawer panel
  - CORS headers set via server config (see .streamlit/config.toml)
  - ?page= query param accepted so the agent knows which dashboard page it's on
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
from pandas.api.types import is_numeric_dtype
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Budget Assistant",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Inject viewport meta so Streamlit renders at iframe width, not 1200px
st.markdown(
    '''<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">''',
    unsafe_allow_html=True,
)

st.markdown("""
<style>
    #MainMenu, footer, header { visibility: hidden; }

    /* Root containers — no horizontal overflow */
    html, body { overflow-x: hidden !important; }
    .stApp {
        background: #F8F6F2;
        overflow-x: hidden !important;
    }
    .block-container {
        padding: 0.75rem 0.75rem 1rem 0.75rem !important;
        max-width: 100% !important;
        width: 100% !important;
        box-sizing: border-box !important;
        overflow-x: hidden !important;
    }

    /* Streamlit internal layout containers */
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    [data-testid="stVerticalBlock"],
    [data-testid="stHorizontalBlock"] {
        max-width: 100% !important;
        overflow-x: hidden !important;
        box-sizing: border-box !important;
    }

    /* Chat messages and all children */
    [data-testid="stChatMessage"],
    [data-testid="stChatMessage"] * {
        max-width: 100% !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        white-space: normal !important;
        box-sizing: border-box !important;
    }
    [data-testid="stChatMessage"] { padding: 0.35rem 0; }

    /* Markdown text inside messages */
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] div {
        max-width: 100% !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        white-space: normal !important;
    }

    /* Dataframe — scroll within its box only */
    [data-testid="stDataFrame"] { overflow-x: auto !important; max-width: 100% !important; }
    .stChatMessage { padding: 0.35rem 0; }

    .data-context {
        background: #EEF3FB; border-left: 3px solid #3B7DD8;
        border-radius: 3px; padding: 6px 10px; margin-bottom: 4px;
        font-size: 0.74rem; font-family: monospace; color: #1A3A6B;
        word-wrap: break-word; overflow-wrap: break-word;
        max-width: 100%; box-sizing: border-box;
    }
    .narrative {
        background: #FDF8F5; border-left: 3px solid #C8122C;
        border-radius: 3px; padding: 10px 12px; margin: 4px 0 8px 0;
        font-size: 0.83rem; line-height: 1.6; color: #1A1A1A;
        word-wrap: break-word; overflow-wrap: break-word;
        max-width: 100%; box-sizing: border-box;
    }
    .narrative p { margin: 0 0 8px 0; }
</style>
""", unsafe_allow_html=True)

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB = os.path.join(_PROJECT_ROOT, "dbt-sql", "mbtsa_work.duckdb")
DB_PATH = os.getenv("MBTSA_DB", _DEFAULT_DB)
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

COLORS = ["#C8122C", "#3B7DD8", "#2EAD6B", "#E67E22",
          "#9B59B6", "#1ABC9C", "#F39C12", "#E74C3C", "#3498DB", "#FFD100"]
CHART_BG = "#FFFFFF"
CHART_GRID = "#E5E7EB"
CHART_FONT = "#374151"
CHART_TOP_N = 10


# ── Helpers (same as app.py) ───────────────────────────────────

def fmt(val):
    if val is None or pd.isna(val):
        return "—"
    val = float(val)
    sign = "-" if val < 0 else ""
    a = abs(val)
    if a >= 1e9: return f"{sign}${a/1e9:,.1f}B"
    if a >= 1e6: return f"{sign}${a/1e6:,.1f}M"
    if a >= 1e3: return f"{sign}${a/1e3:,.0f}k"
    return f"{sign}${a:,.0f}"


def escape_html(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("\n\n---\n\n", "<hr style='border-color:#CE1126;opacity:0.3;margin:8px 0;'>")
    text = text.replace("\n\n", "</p><p style='margin-top:8px;'>")
    text = text.replace("\n", "<br>")
    if not text.startswith("<p"):
        text = "<p>" + text + "</p>"
    return text


def coerce_numeric_columns(df):
    if df is None or df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == "object":
            c = pd.to_numeric(out[col], errors="coerce")
            if c.notna().sum() >= max(1, int(len(out) * 0.7)):
                out[col] = c
    return out


def _is_percent_col(n): return any(t in str(n).lower() for t in ("pct","percent","ratio","rate"))
def _is_year_or_id_col(n): n=str(n).lower(); return "year" in n or n.endswith("_id") or n=="id"
def _is_currency_col(n): return not _is_percent_col(n) and not _is_year_or_id_col(n)


def format_display_df(df):
    if df is None or df.empty: return df
    out = df.copy()
    for col in out.columns:
        if str(col).lower() == "fiscal_year":
            out[col] = out[col].apply(lambda x: "—" if pd.isna(x) else str(int(x)))
        elif is_numeric_dtype(out[col]):
            if _is_percent_col(col):
                out[col] = out[col].apply(lambda x: "—" if pd.isna(x) else f"{float(x):.1f}%")
            elif _is_currency_col(col):
                out[col] = out[col].apply(fmt)
    return out


def render_narrative(narrative: str):
    if narrative.startswith("Showing:") and "\n\n" in narrative:
        ctx, prose = narrative.split("\n\n", 1)
        st.markdown(f'<div class="data-context">{escape_html(ctx)}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="narrative">{escape_html(prose)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="narrative">{escape_html(narrative)}</div>', unsafe_allow_html=True)


def _currency_fmt(col):
    if _is_percent_col(col): return ".1f"
    if _is_currency_col(col): return "$,.2s"
    return ""


def _axis_style(tickformat=""):
    base = dict(showgrid=True, gridcolor=CHART_GRID, zeroline=False,
                tickfont=dict(color=CHART_FONT), title_font=dict(color=CHART_FONT),
                linecolor="#D1D5DB", linewidth=1)
    if tickformat: base["tickformat"] = tickformat
    return base


def _base_layout(title=""):
    return dict(
        template="plotly_white", height=300,
        margin=dict(l=10, r=10, t=30 if title else 8, b=30),
        plot_bgcolor=CHART_BG, paper_bgcolor=CHART_BG,
        font=dict(color=CHART_FONT, size=11), showlegend=False,
        title=dict(text=title, font=dict(color="#111827", size=12)) if title else None,
    )


def render_chart(df, plan):
    """Same logic as app.py render_chart, compact height for iframe."""
    if df is None or df.empty: return
    chart_type = (plan.get("chart_type") or "none").lower()
    if chart_type == "none": return

    df = coerce_numeric_columns(df)
    x, y = plan.get("chart_x",""), plan.get("chart_y","")
    series, title = plan.get("chart_series"), plan.get("chart_title","")
    sort_desc = plan.get("chart_sort_desc", True)

    col_map = {str(c).lower(): c for c in df.columns}
    x_col = col_map.get(x.lower()) if x else None
    y_col = col_map.get(y.lower()) if y else None
    series_col = col_map.get(series.lower()) if series else None

    if not x_col or not y_col:
        return

    # Auto-correct swapped x/y: y must be the numeric axis
    if not is_numeric_dtype(df[y_col]) and is_numeric_dtype(df[x_col]):
        x_col, y_col = y_col, x_col

    fig = None

    if chart_type == "line":
        chart_df = df.sort_values(x_col)
        if series_col:
            fig = px.line(chart_df, x=x_col, y=y_col, color=series_col,
                          markers=True, color_discrete_sequence=COLORS)
            fig.update_layout(showlegend=True, legend=dict(font=dict(color=CHART_FONT, size=10),
                                                           bgcolor="rgba(0,0,0,0)"))
        else:
            fig = px.line(chart_df, x=x_col, y=y_col, markers=True,
                          color_discrete_sequence=COLORS)
        fig.update_xaxes(**_axis_style())
        fig.update_yaxes(**_axis_style(_currency_fmt(y_col)))

    elif chart_type in ("bar_h", "bar_v"):
        chart_df = df[df[y_col].notna()].copy()
        if chart_df.empty:
            return
        chart_df[y_col] = pd.to_numeric(chart_df[y_col], errors="coerce")
        chart_df = chart_df[chart_df[y_col].notna()]
        if chart_df.empty:
            return
        has_negatives = chart_df[y_col].min() < 0
        use_horizontal = not has_negatives and (
            chart_df[x_col].astype(str).str.len().max() > 12 or len(chart_df) > 5
        )
        if sort_desc:
            chart_df = chart_df.sort_values(y_col, ascending=False).head(CHART_TOP_N)
        if use_horizontal:
            chart_df = chart_df.iloc[::-1]
            fig = px.bar(chart_df, x=y_col, y=x_col, orientation="h",
                         color_discrete_sequence=COLORS)
            fig.update_xaxes(**_axis_style(_currency_fmt(y_col)))
            ys = _axis_style(); ys["automargin"] = True; ys["tickfont"] = dict(color=CHART_FONT, size=9)
            fig.update_yaxes(**ys)
        else:
            if has_negatives:
                fig = px.bar(chart_df, x=x_col, y=y_col,
                             color=chart_df[y_col].apply(lambda v: "▲" if v>=0 else "▼"),
                             color_discrete_map={"▲":"#2EAD6B","▼":"#CE1126"})
                fig.update_layout(showlegend=True)
            else:
                fig = px.bar(chart_df, x=x_col, y=y_col, color_discrete_sequence=COLORS)
            fig.update_xaxes(**_axis_style(), tickangle=-30)
            fig.update_yaxes(**_axis_style(_currency_fmt(y_col)))

    elif chart_type == "stacked_bar":
        if not series_col: return
        fig = px.bar(df.sort_values(x_col), x=x_col, y=y_col, color=series_col,
                     barmode="stack", color_discrete_sequence=COLORS)
        fig.update_layout(showlegend=True, legend=dict(font=dict(color=CHART_FONT, size=10),
                                                       bgcolor="rgba(0,0,0,0)"))
        fig.update_xaxes(**_axis_style())
        fig.update_yaxes(**_axis_style(_currency_fmt(y_col)))

    elif chart_type == "pie":
        chart_df = df[df[y_col].notna()].sort_values(y_col, ascending=False)
        if len(chart_df) > 7:
            top = chart_df.head(6).copy()
            other = pd.DataFrame([{x_col: "Other", y_col: chart_df.iloc[6:][y_col].sum()}])
            chart_df = pd.concat([top, other], ignore_index=True)
        fig = px.pie(chart_df, names=x_col, values=y_col,
                     color_discrete_sequence=COLORS, hole=0.3)
        fig.update_traces(textfont_color=CHART_FONT)
        fig.update_layout(showlegend=True, legend=dict(font=dict(color=CHART_FONT, size=10),
                                                       bgcolor="rgba(0,0,0,0)"))

    if fig is None: return
    fig.update_layout(**_base_layout(title))
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})


# ── Agent ──────────────────────────────────────────────────────

@st.cache_resource
def get_agent():
    if not API_KEY: return None
    try:
        from src.agents.query_agent.agent import BudgetQueryAgent
        return BudgetQueryAgent(api_key=API_KEY, db_path=DB_PATH, model=MODEL)
    except Exception as e:
        st.error(f"Agent init failed: {e}")
        return None


# ── Page context from query param ─────────────────────────────
# Evidence can pass ?page=variance-analysis so the agent knows context
page_ctx = st.query_params.get("page", "")
if page_ctx:
    st.caption(f"📊 Context: {page_ctx.replace('-', ' ').title()}")


# ── Chat ───────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            render_narrative(msg["narrative"])
            if msg.get("df") is not None and not msg["df"].empty:
                st.dataframe(format_display_df(msg["df"]),
                             use_container_width=True, hide_index=True, height=180)
                if msg.get("query_plan"):
                    render_chart(msg["df"], msg["query_plan"])
            with st.expander("SQL", expanded=False):
                st.code(msg["sql"], language="sql")
        else:
            st.write(msg["content"])

prompt = st.chat_input("Ask about Maryland's budget…")

if prompt:
    # Prepend page context so agent knows which page user is on
    full_prompt = f"[Page: {page_ctx}] {prompt}" if page_ctx else prompt

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        agent = get_agent()
        if not agent:
            st.error("Set ANTHROPIC_API_KEY.")
        else:
            with st.spinner("Analyzing…"):
                state = agent.query(full_prompt)

            render_narrative(state.get("narrative", ""))

            df = pd.DataFrame()
            raw = state.get("raw_results", {})
            if raw.get("rows") and raw.get("columns"):
                df = pd.DataFrame(raw["rows"], columns=raw["columns"])
                df = coerce_numeric_columns(df)
                st.dataframe(format_display_df(df),
                             use_container_width=True, hide_index=True, height=180)
                render_chart(df, state.get("query_plan", {}))

            with st.expander("SQL", expanded=False):
                st.code(state.get("sql", ""), language="sql")

            st.session_state.messages.append({
                "role": "assistant",
                "narrative": state.get("narrative", ""),
                "df": df,
                "sql": state.get("sql", ""),
                "query_plan": state.get("query_plan", {}),
            })
            st.rerun()