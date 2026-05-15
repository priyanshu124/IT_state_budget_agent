"""
Streamlit chat for the MBTSA Budget Query Agent.
Run: python -m streamlit run chat/app.py --server.port 8501
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pandas.api.types import is_numeric_dtype
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Budget Query", page_icon="💬", layout="wide")

st.markdown("""
<style>
    .stApp { background: #FAFAFA; }
    .data-context {
        background: #E8F0FE; border-left: 4px solid #3B7DD8;
        border-radius: 4px; padding: 8px 14px; margin-bottom: 6px;
        font-size: 0.82rem; font-family: monospace; color: #1A3A6B;
        letter-spacing: 0.01em;
    }
    .narrative {
        background: #F5F0EB; border-left: 4px solid #CE1126;
        border-radius: 4px; padding: 16px 20px; margin: 4px 0 12px 0;
        font-size: 0.92rem; line-height: 1.7; color: #1A1A1A;
    }
</style>
""", unsafe_allow_html=True)

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB = os.path.join(_PROJECT_ROOT, "dbt-sql", "mbtsa_work.duckdb")
DB_PATH = os.getenv("MBTSA_DB", _DEFAULT_DB)
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

COLORS = ["#CE1126", "#FFD100", "#3B7DD8", "#2EAD6B", "#E67E22",
          "#9B59B6", "#1ABC9C", "#E74C3C", "#3498DB", "#F39C12"]
CHART_BG = "#050A17"
CHART_GRID = "#2A3348"
CHART_FONT = "#E6ECF7"
CHART_TOP_N = 15


# ── Formatting helpers ─────────────────────────────────────────

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
        return f"{sign}${abs_val/1e3:,.0f}k"
    return f"{sign}${abs_val:,.0f}"


def escape_html(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("\n\n---\n\n", "<hr style='border-color:#CE1126;opacity:0.3;margin:12px 0;'>")
    text = text.replace("\n\n", "</p><p style='margin-top:12px;'>")
    text = text.replace("\n", "<br>")
    if not text.startswith("<p"):
        text = "<p>" + text + "</p>"
    return text


def render_narrative(narrative: str):
    """Split data-context line from prose and render with distinct styles."""
    if narrative.startswith("Showing:") and "\n\n" in narrative:
        context, prose = narrative.split("\n\n", 1)
        st.markdown(f'<div class="data-context">{escape_html(context)}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="narrative">{escape_html(prose)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="narrative">{escape_html(narrative)}</div>', unsafe_allow_html=True)



def coerce_numeric_columns(df):
    if df is None or df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == "object":
            candidate = pd.to_numeric(out[col], errors="coerce")
            threshold = max(1, int(len(out) * 0.7))
            if candidate.notna().sum() >= threshold:
                out[col] = candidate
    return out


def _is_percent_col(name: str) -> bool:
    n = str(name).lower()
    return any(t in n for t in ("pct", "percent", "ratio", "rate"))


def _is_year_or_id_col(name: str) -> bool:
    n = str(name).lower()
    return "year" in n or n.endswith("_id") or n == "id"


def _is_currency_col(name: str) -> bool:
    return not _is_percent_col(name) and not _is_year_or_id_col(name)


def format_display_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        name = str(col).lower()
        if name == "fiscal_year":
            out[col] = out[col].apply(lambda x: "—" if pd.isna(x) else str(int(x)))
            continue
        if is_numeric_dtype(out[col]):
            if _is_percent_col(col):
                out[col] = out[col].apply(lambda x: "—" if pd.isna(x) else f"{float(x):.1f}%")
            elif _is_currency_col(col):
                out[col] = out[col].apply(fmt)
    return out


# ── Chart layout defaults ──────────────────────────────────────

def _base_layout(title: str = "") -> dict:
    return dict(
        template="plotly_dark",
        height=420,
        margin=dict(l=20, r=20, t=40 if title else 10, b=40),
        plot_bgcolor=CHART_BG,
        paper_bgcolor=CHART_BG,
        font=dict(color=CHART_FONT, size=13),
        showlegend=False,
        title=dict(text=title, font=dict(color=CHART_FONT, size=14)) if title else None,
    )


def _axis_style(tickformat: str = "") -> dict:
    base = dict(showgrid=True, gridcolor=CHART_GRID, zeroline=False,
                tickfont=dict(color=CHART_FONT), title_font=dict(color=CHART_FONT))
    if tickformat:
        base["tickformat"] = tickformat
    return base


def _currency_fmt(col: str) -> str:
    if _is_percent_col(col):
        return ".1f"
    if _is_currency_col(col):
        return "$,.2s"
    return ""


# ── render_chart: QueryPlan-driven, no heuristics ─────────────

def render_chart(df: pd.DataFrame, plan: dict):
    """Render chart from QueryPlan spec. No column-name guessing."""
    if df is None or df.empty:
        return

    chart_type = (plan.get("chart_type") or "none").lower()
    if chart_type == "none":
        return

    df = coerce_numeric_columns(df)

    x = plan.get("chart_x", "")
    y = plan.get("chart_y", "")
    series = plan.get("chart_series")
    title = plan.get("chart_title", "")
    sort_desc = plan.get("chart_sort_desc", True)

    # Validate columns exist
    available = [str(c).lower() for c in df.columns]
    col_map = {str(c).lower(): c for c in df.columns}

    x_col = col_map.get(x.lower()) if x else None
    y_col = col_map.get(y.lower()) if y else None
    series_col = col_map.get(series.lower()) if series else None

    if not x_col or not y_col:
        st.caption(f"Chart skipped: columns '{x}' or '{y}' not found in results {available}")
        return

    fig = None

    if chart_type == "line":
        chart_df = df.sort_values(x_col)
        if series_col:
            fig = px.line(
                chart_df, x=x_col, y=y_col, color=series_col,
                markers=True, color_discrete_sequence=COLORS,
            )
            fig.update_layout(showlegend=True, legend=dict(
                font=dict(color=CHART_FONT), bgcolor="rgba(0,0,0,0)"
            ))
        else:
            fig = px.line(chart_df, x=x_col, y=y_col, markers=True,
                          color_discrete_sequence=COLORS)
        fig.update_xaxes(**_axis_style())
        fig.update_yaxes(**_axis_style(_currency_fmt(y_col)))

    elif chart_type == "bar_h":
        chart_df = df[df[y_col].notna()].copy()
        if sort_desc:
            chart_df = chart_df.sort_values(y_col, ascending=False).head(CHART_TOP_N)
            chart_df = chart_df.iloc[::-1]  # largest at top for horizontal
        fig = px.bar(chart_df, x=y_col, y=x_col, orientation="h",
                     color_discrete_sequence=COLORS)
        fig.update_xaxes(**_axis_style(_currency_fmt(y_col)))
        y_style = _axis_style()
        y_style["automargin"] = True
        y_style["tickfont"] = dict(color=CHART_FONT, size=11)
        fig.update_yaxes(**y_style)

    elif chart_type == "bar_v":
        chart_df = df[df[y_col].notna()].copy()
        if sort_desc:
            chart_df = chart_df.sort_values(y_col, ascending=False).head(CHART_TOP_N)

        # Auto-flip to horizontal when labels are long or many categories and no negatives
        x_vals = chart_df[x_col].astype(str)
        has_negatives = chart_df[y_col].min() < 0
        use_horizontal = not has_negatives and (
            x_vals.str.len().max() > 15 or len(chart_df) > 6
        )

        if use_horizontal:
            chart_df = chart_df.iloc[::-1]
            fig = px.bar(chart_df, x=y_col, y=x_col, orientation="h",
                         color_discrete_sequence=COLORS)
            fig.update_xaxes(**_axis_style(_currency_fmt(y_col)))
            y_style = _axis_style()
            y_style["automargin"] = True
            y_style["tickfont"] = dict(color=CHART_FONT, size=11)
            fig.update_yaxes(**y_style)
        else:
            if has_negatives:
                fig = px.bar(chart_df, x=x_col, y=y_col,
                             color=chart_df[y_col].apply(lambda v: "Increase" if v >= 0 else "Decrease"),
                             color_discrete_map={"Increase": "#2EAD6B", "Decrease": "#CE1126"})
                fig.update_layout(showlegend=True, legend=dict(
                    font=dict(color=CHART_FONT), bgcolor="rgba(0,0,0,0)"
                ))
            else:
                fig = px.bar(chart_df, x=x_col, y=y_col, color_discrete_sequence=COLORS)
            fig.update_xaxes(**_axis_style(), tickangle=-35)
            fig.update_yaxes(**_axis_style(_currency_fmt(y_col)))

    elif chart_type == "stacked_bar":
        if not series_col:
            st.caption("stacked_bar requires chart_series column")
            return
        chart_df = df.sort_values(x_col)
        fig = px.bar(chart_df, x=x_col, y=y_col, color=series_col,
                     barmode="stack", color_discrete_sequence=COLORS)
        fig.update_layout(showlegend=True, legend=dict(
            font=dict(color=CHART_FONT), bgcolor="rgba(0,0,0,0)"
        ))
        fig.update_xaxes(**_axis_style())
        fig.update_yaxes(**_axis_style(_currency_fmt(y_col)))

    elif chart_type == "pie":
        chart_df = df[df[y_col].notna()].sort_values(y_col, ascending=False)
        # Collapse to top N + "Other" to avoid unreadable slices
        if len(chart_df) > 8:
            top = chart_df.head(7).copy()
            other_val = chart_df.iloc[7:][y_col].sum()
            other_row = pd.DataFrame([{x_col: "Other", y_col: other_val}])
            chart_df = pd.concat([top, other_row], ignore_index=True)
        fig = px.pie(chart_df, names=x_col, values=y_col,
                     color_discrete_sequence=COLORS, hole=0.35)
        fig.update_traces(textfont_color=CHART_FONT)
        fig.update_layout(showlegend=True, legend=dict(
            font=dict(color=CHART_FONT), bgcolor="rgba(0,0,0,0)"
        ))

    if fig is None:
        return

    fig.update_layout(**_base_layout(title))
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})


# ── Agent ──────────────────────────────────────────────────────

@st.cache_resource
def get_agent():
    if not API_KEY:
        return None
    try:
        from src.agents.query_agent.agent import BudgetQueryAgent
        return BudgetQueryAgent(api_key=API_KEY, db_path=DB_PATH, model=MODEL)
    except Exception as e:
        st.error(f"Agent init failed: {e}")
        return None


# ── Quick queries ──────────────────────────────────────────────

qcols = st.columns(4)
quick_queries = [
    "Variance for Dept of Health between FY2026 and FY2027?",
    "Which agencies had biggest budget increases?",
    "All programs funded by ARPA",
    "What percentage of budget is federal funds?",
    "How has education budget changed over years?",
    "Top 10 IT programs by budget",
    "Compare MITDP vs ITIF budget",
]
for i, q in enumerate(quick_queries):
    with qcols[i % 4]:
        if st.button(q, use_container_width=True, key=f"q_{i}"):
            st.session_state.quick = q
            st.rerun()

# ── Chat ───────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            render_narrative(msg["narrative"])
            if msg.get("df") is not None and not msg["df"].empty:
                st.dataframe(format_display_df(msg["df"]), use_container_width=True, hide_index=True)
                if msg.get("query_plan"):
                    render_chart(msg["df"], msg["query_plan"])
            with st.expander("SQL"):
                st.code(msg["sql"], language="sql")
            if msg.get("query_plan"):
                qp = msg["query_plan"]
                with st.expander("Query Plan"):
                    st.json({
                        "analysis_type": qp.get("analysis_type"),
                        "output_shape": qp.get("output_shape"),
                        "chart_type": qp.get("chart_type"),
                        "chart_x": qp.get("chart_x"),
                        "chart_y": qp.get("chart_y"),
                        "chart_series": qp.get("chart_series"),
                        "dimensions": qp.get("dimensions"),
                        "filters": qp.get("filters"),
                    })
        else:
            st.write(msg["content"])

prompt = st.chat_input("Ask about Maryland's budget...")
if "quick" in st.session_state:
    prompt = st.session_state.pop("quick")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        agent = get_agent()
        if not agent:
            st.error("Set ANTHROPIC_API_KEY.")
        else:
            with st.spinner("Analyzing..."):
                state = agent.query(prompt)

            narrative = state.get("narrative", "")
            render_narrative(narrative)

            df = pd.DataFrame()
            raw = state.get("raw_results", {})
            if raw.get("rows") and raw.get("columns"):
                df = pd.DataFrame(raw["rows"], columns=raw["columns"])
                df = coerce_numeric_columns(df)
                st.dataframe(format_display_df(df), use_container_width=True, hide_index=True)
                render_chart(df, state.get("query_plan", {}))

            with st.expander("SQL"):
                st.code(state.get("sql", ""), language="sql")

            qp = state.get("query_plan", {})
            if qp:
                with st.expander("Query Plan"):
                    st.json({
                        "analysis_type": qp.get("analysis_type"),
                        "output_shape": qp.get("output_shape"),
                        "chart_type": qp.get("chart_type"),
                        "chart_x": qp.get("chart_x"),
                        "chart_y": qp.get("chart_y"),
                        "chart_series": qp.get("chart_series"),
                        "dimensions": qp.get("dimensions"),
                        "filters": qp.get("filters"),
                    })

            st.session_state.messages.append({
                "role": "assistant",
                "narrative": narrative,
                "df": df,
                "sql": state.get("sql", ""),
                "query_plan": qp,
            })
            st.rerun()