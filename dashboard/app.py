"""
Voice Ledger Monitoring Dashboard

Streamlit dashboard for monitoring system health and visualizing supply chain data.

Updated to query Neon PostgreSQL database instead of JSON files.
"""

import json
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from datetime import datetime
import pandas as pd
from database import get_db, get_all_batches, get_all_farmers

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

# Load data from database
@st.cache_data(ttl=60)  # Cache for 60 seconds
def load_dashboard_data():
    """Load real-time data from Neon database"""
    with get_db() as db:
        batches = get_all_batches(db)
        farmers = get_all_farmers(db)
        
        return {
            'batches': batches,
            'farmers': farmers,
            'total_batches': len(batches),
            'total_farmers': len(farmers),
            'total_kg': sum(b.quantity_kg for b in batches),
            'total_events': sum(len(b.events) for b in batches),
            'total_credentials': sum(len(f.credentials) for f in farmers)
        }

@st.cache_data
def load_dpp_data():
    """Load all DPP files (legacy cache)"""
    dpp_dir = Path(__file__).parent.parent / "dpp" / "passports"
    dpps = []
    if dpp_dir.exists():
        for dpp_file in dpp_dir.glob("*_dpp.json"):
            with open(dpp_file) as f:
                dpps.append(json.load(f))
    return dpps

# Load data
data = load_dashboard_data()
dpp_data = load_dpp_data()
batches = {b.batch_id: b for b in data['batches']}  # Convert to dict for compatibility

# Overview Page
if page == "Overview":
    st.header("System Overview")
    
    # Key Metrics from database
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Batches",
            value=data['total_batches'],
            delta=f"{data['total_batches']} tracked"
        )
    
    with col2:
        st.metric(
            label="Total Volume",
            value=f"{data['total_kg']:,.1f} kg",
            delta=f"{data['total_kg']:.1f} kg tracked"
        )
    
    with col3:
        st.metric(
            label="Blockchain Events",
            value=data['total_events'],
            delta=f"{data['total_events']} recorded"
        )
    
    with col4:
        st.metric(
            label="Total Farmers",
            value=data['total_farmers'],
            delta=f"{data['total_farmers']} registered"
        )
    
    st.markdown("---")
    
    # Recent Activity from database
    st.subheader("Recent Activity")
    
    if data['batches']:
        # Show recent batches (last 5)
        recent_batches = data['batches'][:5]
        
        for batch in recent_batches:
            with st.expander(f"Batch {batch.batch_id} - {batch.farmer.name}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write("**GTIN:**", batch.gtin)
                    st.write("**Quantity:**", f"{batch.quantity_kg} kg")
                    st.write("**Token ID:**", batch.token_id or "Not minted")
                
                with col2:
                    st.write("**Origin:**", batch.origin_region)
                    st.write("**Variety:**", batch.variety)
                    st.write("**Events:**", len(batch.events))
                
                with col3:
                    st.write("**Farmer:**", batch.farmer.name)
                    st.write("**DID:**", batch.farmer.did[:20] + "...")
                    st.write("**Credentials:**", len(batch.farmer.credentials))
    else:
        st.info("No batches recorded yet. Start by creating a commissioning event!")

# Batches Page
elif page == "Batches":
    st.header("Batch Management")
    
    if not data['batches']:
        st.warning("No batches found. Create your first batch using the voice API or EPCIS builder.")
    else:
        # Batch selector
        selected_batch_id = st.selectbox(
            "Select Batch",
            options=[b.batch_id for b in data['batches']]
        )
        
        if selected_batch_id:
            batch = batches[selected_batch_id]
            
            # Batch details
            st.subheader(f"Batch: {selected_batch_id}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Details")
                st.write(f"**GTIN:** {batch.gtin}")
                st.write(f"**Token ID:** {batch.token_id or 'Not minted'}")
                st.write(f"**Quantity:** {batch.quantity_kg} kg")
                st.write(f"**Variety:** {batch.variety}")
                st.write(f"**Process:** {batch.process_method}")
                st.write(f"**Grade:** {batch.grade or 'Not graded'}")
            
            with col2:
                st.markdown("### Origin")
                st.write(f"**Country:** {batch.origin_country}")
                st.write(f"**Region:** {batch.origin_region}")
                st.write(f"**Farm:** {batch.farm_name}")
                st.write(f"**Farmer:** {batch.farmer.name}")
                st.write(f"**DID:** {batch.farmer.did[:30]}...")
            
            # Events
            st.markdown("### Blockchain Events")
            events = batch.events
            st.write(f"**Total Events:** {len(events)}")
            
            for event in events:
                anchored = "✅" if event.blockchain_tx_hash else "⏳"
                st.write(f"{anchored} **{event.event_type}** ({event.biz_step}) - {event.event_time.strftime('%Y-%m-%d %H:%M')}")
                if event.blockchain_tx_hash:
                    st.write(f"   TX: `{event.blockchain_tx_hash[:16]}...`")
            
            # Credentials
            credentials = batch.farmer.credentials
            if credentials:
                st.markdown("### Credentials")
                st.write(f"**Total Credentials:** {len(credentials)}")
                
                for cred in credentials:
                    status = "✅ Active" if not cred.revoked else "❌ Revoked"
                    st.write(f"{status} **{cred.credential_type}** - Issued: {cred.issued_at.strftime('%Y-%m-%d')}")
                    if cred.expires_at:
                        st.write(f"   Expires: {cred.expires_at.strftime('%Y-%m-%d')}")

# Analytics Page
elif page == "Analytics":
    st.header("Analytics")
    
    if not data['batches']:
        st.warning("No data available for analytics.")
    else:
        # Batch distribution by quantity
        st.subheader("Batch Volume Distribution")
        
        batch_quantities = {
            batch.batch_id: batch.quantity_kg
            for batch in data['batches']
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
            yaxis_title="Quantity (kg)",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Event types distribution
        st.subheader("Event Types Distribution")
        
        event_types = {}
        for batch in data['batches']:
            for event in batch.events:
                event_type = event.event_type
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
        
        # Region distribution
        st.subheader("Batch Distribution by Region")
        
        regions = {}
        for batch in data['batches']:
            region = batch.origin_region or "Unknown"
            regions[region] = regions.get(region, 0) + 1
        
        if regions:
            fig = go.Figure(data=[
                go.Bar(
                    x=list(regions.keys()),
                    y=list(regions.values()),
                    marker_color='#4ECDC4'
                )
            ])
            fig.update_layout(
                xaxis_title="Region",
                yaxis_title="Number of Batches",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)

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
        # Count events from database
        st.metric("EPCIS Events", data['total_events'])
    
    with col2:
        # Count DPPs (cached files)
        dpp_count = len(dpp_data)
        st.metric("Digital Passports", dpp_count)
    
    with col3:
        # Count credentials from database
        st.metric("Credentials", data['total_credentials'])
    
    with col4:
        # Count batches from database
        st.metric("Batches in DB", data['total_batches'])
    
    st.markdown("---")
    
    # System information
    st.subheader("System Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Platform:** Voice Ledger v1.0.0")
        st.write("**Compliance:** EUDR-ready")
        st.write("**Blockchain:** Local Anvil node")
        st.write("**Database:** Neon PostgreSQL")
    
    with col2:
        st.write("**Python Version:** 3.9.6")
        st.write("**Smart Contracts:** 3 deployed")
        st.write("**ORM:** SQLAlchemy 2.0.23")
        st.write("**Last Updated:** ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Footer
st.markdown("---")
st.caption("Voice Ledger v1.0.0 | EUDR-Compliant Supply Chain Platform")
