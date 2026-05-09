import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from datetime import datetime, date
from pathlib import Path

from src.config import DATA_PATH, OUTPUT_DIR
from src.data_loader import load_invoices
from src.triage import triage_invoices


st.set_page_config(
    page_title="CreditOps Portal",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp { background-color: #ffffff; }
    
    section[data-testid="stSidebar"] {
        background-color: #0f172a !important;
        color: #ffffff;
    }
    
    .kpi-card {
        background-color: #ffffff;
        padding: 16px;
        border-radius: 4px;
        border: 1px solid #e2e8f0;
    }
    .kpi-label {
        color: #64748b;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .kpi-value {
        color: #0f172a;
        font-size: 22px;
        font-weight: 700;
    }
    .kpi-delta {
        font-size: 10px;
        font-weight: 500;
        margin-top: 4px;
    }
    .delta-up { color: #059669; }
    .delta-down { color: #dc2626; }

    .section-title {
        font-size: 14px;
        font-weight: 600;
        color: #0f172a;
        margin-bottom: 12px;
    }

    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Reduce Streamlit default margins */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=30)
def get_data():
    df = load_invoices(DATA_PATH)
    triaged = triage_invoices(df)
    return df, triaged

def get_history():
    reports = sorted(Path(OUTPUT_DIR).glob("run_report_*.json"), key=os.path.getmtime)
    data = []
    for r in reports:
        with open(r, 'r') as f:
            data.append(json.load(f))
    return data

def get_performance_trends(history):
    trends = {"sent": None, "rate": None}
    if len(history) >= 2:
        curr = history[-1]
        prev = history[-2]
        
        diff_sent = curr.get('total_sent', 0) - prev.get('total_sent', 0)
        trends["sent"] = f"{'+' if diff_sent >= 0 else ''}{diff_sent} vs prev"
        
        c_rate = (curr.get('total_sent', 0) / max(curr.get('total_processed', 1), 1)) * 100
        p_rate = (prev.get('total_sent', 0) / max(prev.get('total_processed', 1), 1)) * 100
        diff_rate = c_rate - p_rate
        trends["rate"] = f"{'+' if diff_rate >= 0 else ''}{diff_rate:.1f}% vs prev"
    return trends


def metric_box(label, value, delta=None, delta_type="neutral"):
    color_class = ""
    if delta_type == "pos": color_class = "delta-up"
    elif delta_type == "neg": color_class = "delta-down"
    
    delta_html = f'<div class="kpi-delta {color_class}">{delta}</div>' if delta else ""
    
    st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>
    """, unsafe_allow_html=True)



def main():
    df, triaged_df = get_data()
    history = get_history()
    trends = get_performance_trends(history)

    with st.sidebar:
        st.markdown("<h3 style='color:white;'>CreditOps</h3>", unsafe_allow_html=True)
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div style="position:fixed; bottom:20px; width:220px; border-top:1px solid #334155; padding-top:15px;">
                <div style="color:white; font-size:13px; font-weight:600;">Suresh Jakhar</div>
                <div style="color:#94a3b8; font-size:11px;">Finance Operations</div>
            </div>
        """, unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    
    total_val = df[df['payment_status'] == 'Pending']['invoice_amount'].sum()
    critical_cases = len(triaged_df[triaged_df['urgency_tier'].isin(['stage_4_stern', 'legal_escalation'])])
    recovery_rate = (len(df[df['payment_status'] == 'Paid']) / len(df)) * 100 if len(df) > 0 else 0
    
    with k1:
        metric_box("Actionable Queue", f"{len(triaged_df)}")
    with k2:
        metric_box("Total Exposure", f"${total_val/1000:,.1f}K")
    with k3:
        metric_box("Recovery Rate", f"{recovery_rate:.1f}%")
    with k4:
        metric_box("Critical Flags", f"{critical_cases}", delta_type="neg" if critical_cases > 0 else "neutral")

    st.markdown("<br>", unsafe_allow_html=True)
    c_left, c_right = st.columns([2, 1], gap="medium")

    with c_left:
        st.markdown('<div class="section-title">Aging Pipeline Distribution</div>', unsafe_allow_html=True)
        tier_stats = triaged_df['urgency_tier'].value_counts().reset_index()
        tier_stats.columns = ['Tier', 'Invoices']
        
        label_map = {
            'stage_1_warm': 'Stage 1: Warm (1-7d)',
            'stage_2_firm': 'Stage 2: Firm (8-14d)',
            'stage_3_serious': 'Stage 3: Serious (15-21d)',
            'stage_4_stern': 'Stage 4: Stern (22-30d)',
            'legal_escalation': 'Stage 5: Legal (30d+)'
        }
        tier_stats['DisplayTier'] = tier_stats['Tier'].map(label_map)
        
        category_order = [
            'Stage 1: Warm (1-7d)',
            'Stage 2: Firm (8-14d)',
            'Stage 3: Serious (15-21d)',
            'Stage 4: Stern (22-30d)',
            'Stage 5: Legal (30d+)'
        ]
        
        fig_bar = px.bar(
            tier_stats,
            x='Invoices',
            y='DisplayTier',
            orientation='h',
            color='Tier',
            color_discrete_map={
                'stage_4_stern': '#ef4444',
                'stage_3_serious': '#f59e0b',
                'stage_2_firm': '#3b82f6',
                'stage_1_warm': '#10b981',
                'legal_escalation': '#64748b'
            },
            template="plotly_white"
        )
        fig_bar.update_traces(width=0.4)
        fig_bar.update_layout(
            showlegend=False, 
            height=180, 
            margin=dict(l=0, r=10, t=0, b=0),
            xaxis=dict(showgrid=True, gridcolor='#f1f5f9', title=None, dtick=1),
            yaxis=dict(
                categoryorder='array', 
                categoryarray=category_order,
                title=None
            )
        )
        st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

    with c_right:
        st.markdown('<div class="section-title">Portfolio Mix</div>', unsafe_allow_html=True)
        status_map = df['payment_status'].value_counts()
        fig_donut = go.Figure(data=[go.Pie(
            labels=status_map.index,
            values=status_map.values,
            hole=.8,
            marker_colors=['#3b82f6', '#10b981', '#f59e0b', '#ef4444'],
            textinfo='none'
        )])
        fig_donut.update_layout(
            height=200, 
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=True,
            legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_donut, use_container_width=True, config={'displayModeBar': False})

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">Dispatch Performance</div>', unsafe_allow_html=True)
    if history:
        dp1, dp2, dp3 = st.columns(3)
        with dp1:
            metric_box("Last Batch Sent", f"{history[-1].get('total_sent', 0)}", trends["sent"])
        with dp2:
            yield_val = int(history[-1].get('total_sent', 0)/max(history[-1].get('total_processed', 1), 1)*100)
            metric_box("Automation Yield", f"{yield_val}%", trends["rate"])
        with dp3:
            metric_box("Legal Flags", f"{history[-1].get('total_skipped', 0)}")
    else:
        st.info("No dispatch history available.")

    # Table
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">Action Ledger</div>', unsafe_allow_html=True)
    
    view_df = triaged_df.copy()
    view_df['invoice_amount'] = view_df['invoice_amount'].map('${:,.2f}'.format)
    view_df['due_date'] = view_df['due_date'].dt.strftime('%d %b %Y')
    
    st.dataframe(
        view_df[[
            'invoice_no', 'client_name', 'invoice_amount', 
            'days_overdue', 'followup_count', 'urgency_tier'
        ]],
        use_container_width=True,
        hide_index=True
    )

if __name__ == "__main__":
    main()
