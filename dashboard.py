import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
from datetime import datetime
from pathlib import Path

from src.config import DATA_PATH, OUTPUT_DIR
from src.data_loader import load_invoices
from src.triage import triage_invoices

st.set_page_config(
    page_title="Credit Operations Center",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    /* Main Background */
    .stApp {
        background-color: #0f172a;
        color: #f1f5f9;
    }
    
    /* Global Card Style */
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        padding: 24px;
        border-radius: 8px;
        text-align: center;
        transition: transform 0.2s;
    }
    .metric-card:hover {
        border-color: #475569;
        transform: translateY(-2px);
    }
    .metric-value {
        font-size: 32px;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 4px;
    }
    .metric-label {
        font-size: 12px;
        font-weight: 500;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    
    /* Header & Typography */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        font-weight: 700 !important;
    }
    .main-title {
        font-size: 36px;
        margin-bottom: 8px;
    }
    .sub-title {
        color: #94a3b8;
        margin-bottom: 32px;
    }
    
    /* Status Pills */
    .status-pill {
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }
    
    /* Fix Streamlit Table for Dark Mode */
    .stDataFrame {
        border: 1px solid #334155;
        border-radius: 8px;
    }
    
    /* Hide Default Streamlit Elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)


@st.cache_data(ttl=60)
def get_dashboard_data():
    df = load_invoices(DATA_PATH)
    triaged_df = triage_invoices(df)
    return df, triaged_df

def get_latest_run():
    reports = list(Path(OUTPUT_DIR).glob("run_report_*.json"))
    if not reports:
        return None
    latest = max(reports, key=os.path.getmtime)
    with open(latest, 'r') as f:
        return json.load(f), latest.name


def render_metric(label, value, col):
    with col:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{value}</div>
                <div class="metric-label">{label}</div>
            </div>
        """, unsafe_allow_html=True)


def main():
    st.markdown('<div class="main-title">Credit Operations Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Intelligence-driven accounts receivable management and automated recovery.</div>', unsafe_allow_html=True)
    
    df, triaged_df = get_dashboard_data()
    report, report_name = get_latest_run() or (None, None)

    m1, m2, m3, m4 = st.columns(4)
    
    pending_count = len(df[df['payment_status'] == 'Pending'])
    actionable = len(triaged_df)
    urgent = len(triaged_df[triaged_df['urgency_tier'].isin(['stage_4_stern', 'stage_3_serious', 'legal_escalation'])])
    total_val = df[df['payment_status'] == 'Pending']['invoice_amount'].sum()
    
    render_metric("Total Pending", pending_count, m1)
    render_metric("Actionable Queue", actionable, m2)
    render_metric("Critical Priority", urgent, m3)
    render_metric("Recievable Value", f"${total_val:,.2f}", m4)

    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.subheader("Queue Distribution")
        tier_data = triaged_df['urgency_tier'].value_counts().reset_index()
        tier_data.columns = ['Tier', 'Invoices']
        
        colors = {
            'stage_4_stern': '#e11d48',   
            'stage_3_serious': '#f59e0b',      
            'stage_2_firm': '#3b82f6', 
            'stage_1_warm': '#10b981', 
            'legal_escalation': '#64748b'        
        }
        
        fig = px.bar(
            tier_data,
            x='Invoices',
            y='Tier',
            orientation='h',
            color='Tier',
            color_discrete_map=colors,
            template="plotly_dark"
        )
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=0, b=0),
            height=300,
            showlegend=False,
            xaxis=dict(showgrid=False, zeroline=False),
            yaxis=dict(showgrid=False, categoryorder='total ascending')
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_right:
        st.subheader("Latest Dispatch Performance")
        if report:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"**Processed**<br><span style='font-size:24px'>{report.get('total_processed', 0)}</span>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"**Dispatched**<br><span style='font-size:24px; color:#10b981'>{report.get('total_sent', 0)}</span>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"**Failed**<br><span style='font-size:24px; color:#e11d48'>{report.get('total_errors', 0)}</span>", unsafe_allow_html=True)
            
            success_pct = (report.get('total_sent', 0) / max(report.get('total_processed', 1), 1))
            st.markdown("<br>", unsafe_allow_html=True)
            st.progress(min(success_pct, 1.0))
            st.caption(f"Last update: {report_name.split('_')[-1].split('Z')[0]}")
        else:
            st.info("No active dispatch reports found.")

    st.markdown("<br>", unsafe_allow_html=True
    st.subheader("Invoice Action Queue")
    
    f1, f2 = st.columns([1, 2])
    with f1:
        tier_filter = st.multiselect("Filter by Tier", options=triaged_df['urgency_tier'].unique())
    with f2:
        search = st.text_input("Search Client or Invoice")

    view_df = triaged_df.copy()
    if tier_filter:
        view_df = view_df[view_df['urgency_tier'].isin(tier_filter)]
    if search:
        view_df = view_df[
            view_df['client_name'].str.contains(search, case=False) | 
            view_df['invoice_no'].str.contains(search, case=False)
        ]

    view_df['invoice_amount'] = view_df['invoice_amount'].map('${:,.2f}'.format)
    view_df['due_date'] = view_df['due_date'].dt.strftime('%Y-%m-%d')
    
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
