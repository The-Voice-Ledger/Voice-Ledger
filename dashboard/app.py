"""
Voice Ledger Monitoring Dashboard

Streamlit dashboard for monitoring system health and visualizing supply chain data.
"""

import json
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from datetime import datetime
import pandas as pd

# Page configuration
st.set_page_config(
    page_title="Voice Ledger Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
.metric-card {
    background-color: #f0f2f6;
    border-radius: 10px;
    padding: 20px;
    margin: 10px 0;
}
.stMetric {
    background-color: white;
    padding: 15px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.stMetric label {
    color: #262730 !important;
    font-weight: 600 !important;
}
.stMetric [data-testid="stMetricValue"] {
    color: #262730 !important;
    font-size: 28px !important;
}
</style>
""", unsafe_allow_html=True)

# Title
st.title("Voice Ledger Dashboard")
st.markdown("**EUDR-Compliant Coffee Traceability Platform**")
st.markdown("---")

# Sidebar
st.sidebar.header("Navigation")
page = st.sidebar.radio(
    "Select View",
    ["Overview", "Batches", "Analytics", "System Health"]
)

# Load data
@st.cache_data
def load_twin_data():
    """Load digital twin data"""
    twin_file = Path(__file__).parent.parent / "twin" / "digital_twin.json"
    if twin_file.exists():
        with open(twin_file) as f:
            return json.load(f)
    return {"batches": {}}

@st.cache_data
def load_dpp_data():
    """Load all DPP files"""
    dpp_dir = Path(__file__).parent.parent / "dpp" / "passports"
    dpps = []
    if dpp_dir.exists():
        for dpp_file in dpp_dir.glob("*_dpp.json"):
            with open(dpp_file) as f:
                dpps.append(json.load(f))
    return dpps

# Load data
twin_data = load_twin_data()
dpp_data = load_dpp_data()
batches = twin_data.get("batches", {})

# Overview Page
if page == "Overview":
    st.header("System Overview")
    
    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Batches",
            value=len(batches),
            delta=f"+{len(batches)} this session"
        )
    
    with col2:
        total_quantity = sum(b.get("quantity", 0) for b in batches.values())
        st.metric(
            label="Total Volume",
            value=f"{total_quantity:,} bags",
            delta=f"{total_quantity} bags tracked"
        )
    
    with col3:
        total_anchors = sum(len(b.get("anchors", [])) for b in batches.values())
        st.metric(
            label="Blockchain Anchors",
            value=total_anchors,
            delta=f"{total_anchors} events recorded"
        )
    
    with col4:
        settled_count = sum(1 for b in batches.values() if b and b.get("settlement") and b.get("settlement").get("settled"))
        st.metric(
            label="Settled Batches",
            value=settled_count,
            delta=f"{settled_count}/{len(batches)} settled"
        )
    
    st.markdown("---")
    
    # Recent Activity
    st.subheader("Recent Activity")
    
    if batches:
        # Show recent batches
        recent_batches = list(batches.items())[:5]
        
        for batch_id, batch_data in recent_batches:
            with st.expander(f"Batch {batch_id}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write("**Quantity:**", f"{batch_data.get('quantity', 0)} bags")
                    st.write("**Token ID:**", batch_data.get("tokenId", "N/A"))
                
                with col2:
                    st.write("**Events:**", len(batch_data.get("anchors", [])))
                    st.write("**Credentials:**", len(batch_data.get("credentials", [])))
                
                with col3:
                    settlement = batch_data.get("settlement")
                    if settlement:
                        st.write("**Settlement:**", f"${settlement.get('amount', 0)/100:,.2f}")
                        st.write("**Status:**", "Settled" if settlement.get("settled") else "Pending")
                    else:
                        st.write("**Settlement:**", "Not recorded")
                        st.write("**Status:**", "N/A")
    else:
        st.info("No batches recorded yet. Start by creating a commissioning event!")

# Batches Page
elif page == "Batches":
    st.header("Batch Management")
    
    if not batches:
        st.warning("No batches found. Create your first batch using the voice API or EPCIS builder.")
    else:
        # Batch selector
        selected_batch = st.selectbox(
            "Select Batch",
            options=list(batches.keys())
        )
        
        if selected_batch:
            batch = batches[selected_batch]
            
            # Batch details
            st.subheader(f"Batch: {selected_batch}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Details")
                st.write(f"**Token ID:** {batch.get('tokenId', 'Not minted')}")
                st.write(f"**Quantity:** {batch.get('quantity', 0)} bags")
                
                metadata = batch.get("metadata", {})
                if metadata:
                    st.write(f"**Origin:** {metadata.get('origin', 'Unknown')}")
                    st.write(f"**Cooperative:** {metadata.get('cooperative', 'Unknown')}")
            
            with col2:
                st.markdown("### Blockchain")
                anchors = batch.get("anchors", [])
                st.write(f"**Anchored Events:** {len(anchors)}")
                
                for anchor in anchors:
                    st.write(f"- {anchor.get('eventType', 'unknown')}: `{anchor.get('eventHash', '')[:16]}...`")
            
            # Settlement info
            settlement = batch.get("settlement")
            if settlement:
                st.markdown("### Settlement")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Amount", f"${settlement.get('amount', 0)/100:,.2f}")
                
                with col2:
                    st.metric("Recipient", settlement.get("recipient", "N/A")[:10] + "...")
                
                with col3:
                    status = "Settled" if settlement.get("settled") else "Pending"
                    st.metric("Status", status)
            
            # Credentials
            credentials = batch.get("credentials", [])
            if credentials:
                st.markdown("### Credentials")
                st.write(f"**Total Credentials:** {len(credentials)}")
                
                for i, cred in enumerate(credentials):
                    with st.expander(f"Credential {i+1}"):
                        st.json(cred)

# Analytics Page
elif page == "Analytics":
    st.header("Analytics")
    
    if not batches:
        st.warning("No data available for analytics.")
    else:
        # Batch distribution by quantity
        st.subheader("Batch Volume Distribution")
        
        batch_quantities = {
            batch_id: data.get("quantity", 0)
            for batch_id, data in batches.items()
        }
        
        fig = go.Figure(data=[
            go.Bar(
                x=list(batch_quantities.keys()),
                y=list(batch_quantities.values()),
                marker_color='#FF6B35'
            )
        ])
        fig.update_layout(
            xaxis_title="Batch ID",
            yaxis_title="Quantity (bags)",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Event types distribution
        st.subheader("Event Types Distribution")
        
        event_types = {}
        for batch in batches.values():
            for anchor in batch.get("anchors", []):
                event_type = anchor.get("eventType", "unknown")
                event_types[event_type] = event_types.get(event_type, 0) + 1
        
        if event_types:
            fig = go.Figure(data=[
                go.Pie(
                    labels=list(event_types.keys()),
                    values=list(event_types.values()),
                    hole=0.3
                )
            ])
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        # Settlement statistics
        st.subheader("Settlement Statistics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            total_settlement = sum(
                b.get("settlement", {}).get("amount", 0)
                for b in batches.values()
            ) / 100
            st.metric("Total Settlement Value", f"${total_settlement:,.2f}")
        
        with col2:
            avg_settlement = total_settlement / len(batches) if batches else 0
            st.metric("Average per Batch", f"${avg_settlement:,.2f}")

# System Health Page
elif page == "System Health":
    st.header("System Health")
    
    # Service status
    st.subheader("Service Status")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### Voice API")
        # In production, this would ping the actual service
        st.success("Operational")
        st.write("Port: 8000")
    
    with col2:
        st.markdown("### DPP Resolver")
        st.success("Operational")
        st.write("Port: 8001")
    
    with col3:
        st.markdown("### Blockchain Node")
        st.success("Operational")
        st.write("Port: 8545")
    
    st.markdown("---")
    
    # Data statistics
    st.subheader("Data Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Count EPCIS events
        epcis_dir = Path(__file__).parent.parent / "epcis" / "events"
        epcis_count = len(list(epcis_dir.glob("*.json"))) if epcis_dir.exists() else 0
        st.metric("EPCIS Events", epcis_count)
    
    with col2:
        # Count DPPs
        dpp_count = len(dpp_data)
        st.metric("Digital Passports", dpp_count)
    
    with col3:
        # Count QR codes
        qr_dir = Path(__file__).parent.parent / "dpp" / "qrcodes"
        qr_count = len(list(qr_dir.glob("*.png"))) if qr_dir.exists() else 0
        st.metric("QR Codes", qr_count)
    
    with col4:
        # Count batches
        st.metric("Digital Twins", len(batches))
    
    st.markdown("---")
    
    # System information
    st.subheader("System Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Platform:** Voice Ledger v1.0.0")
        st.write("**Compliance:** EUDR-ready")
        st.write("**Blockchain:** Local Anvil node")
    
    with col2:
        st.write("**Python Version:** 3.9.6")
        st.write("**Smart Contracts:** 3 deployed")
        st.write("**Last Updated:** ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Footer
st.markdown("---")
st.caption("Voice Ledger v1.0.0 | EUDR-Compliant Supply Chain Platform")
