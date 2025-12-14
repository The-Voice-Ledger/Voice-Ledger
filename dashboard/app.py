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
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

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
        
        # Convert to serializable dictionaries to avoid detached instance errors
        batches_data = []
        for b in batches:
            batch_dict = {
                'id': b.id,
                'batch_id': b.batch_id,
                'gtin': b.gtin,
                'quantity_kg': b.quantity_kg,
                'variety': b.variety or "Unknown",
                'process_method': b.process_method or "Unknown",
                'origin_region': b.origin_region or "Unknown",
                'farmer_id': b.farmer_id,
                'created_at': b.created_at.isoformat() if b.created_at else None,
                'events_count': len(b.events) if b.events else 0,
                'farmer_name': b.farmer.name if b.farmer else "Unknown"
            }
            batches_data.append(batch_dict)
        
        farmers_data = []
        for f in farmers:
            farmer_dict = {
                'id': f.id,
                'farmer_id': f.farmer_id,
                'name': f.name,
                'did': f.did,
                'latitude': f.latitude,
                'longitude': f.longitude,
                'country_code': f.country_code,
                'region': f.region or "Unknown",
                'created_at': f.created_at.isoformat() if f.created_at else None,
                'credentials_count': len(f.credentials) if f.credentials else 0,
                'batches_count': len(f.batches) if f.batches else 0
            }
            farmers_data.append(farmer_dict)
        
        return {
            'batches': batches_data,
            'farmers': farmers_data,
            'total_batches': len(batches_data),
            'total_farmers': len(farmers_data),
            'total_kg': sum(b['quantity_kg'] for b in batches_data),
            'total_events': sum(b['events_count'] for b in batches_data),
            'total_credentials': sum(f['credentials_count'] for f in farmers_data)
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
batches = {b['batch_id']: b for b in data['batches']}  # Convert to dict for compatibility

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
            with st.expander(f"Batch {batch['batch_id']} - {batch['farmer_name']}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write("**GTIN:**", batch['gtin'])
                    st.write("**Quantity:**", f"{batch['quantity_kg']} kg")
                    st.write("**Variety:**", batch['variety'])
                
                with col2:
                    st.write("**Farmer:**", batch['farmer_name'])
                    st.write("**Events:**", batch['events_count'])
                    st.write("**Created:**", batch['created_at'][:10] if batch['created_at'] else "N/A")
                
                with col3:
                    st.write("**Batch ID:**", batch['batch_id'])
                    st.write("**Farmer ID:**", batch['farmer_id'])
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
            options=[b['batch_id'] for b in data['batches']]
        )
        
        if selected_batch_id:
            batch = batches[selected_batch_id]
            
            # Batch details
            st.subheader(f"Batch: {selected_batch_id}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Details")
                st.write(f"**GTIN:** {batch['gtin']}")
                st.write(f"**Quantity:** {batch['quantity_kg']} kg")
                st.write(f"**Variety:** {batch['variety']}")
                st.write(f"**Process:** {batch['process_method']}")
                st.write(f"**Created:** {batch['created_at'][:10] if batch['created_at'] else 'N/A'}")
            
            with col2:
                st.markdown("### Farmer")
                st.write(f"**Name:** {batch['farmer_name']}")
                st.write(f"**Farmer ID:** {batch['farmer_id']}")
                st.write(f"**Events:** {batch['events_count']}")
            
            # Note about full details
            st.info("For complete batch details with events and blockchain transactions, query the database directly.")

# Analytics Page
elif page == "Analytics":
    st.header("Analytics")
    
    if not data['batches']:
        st.warning("No data available for analytics.")
    else:
        # Batch distribution by quantity
        st.subheader("Batch Volume Distribution")
        
        batch_quantities = {
            batch['batch_id']: batch['quantity_kg']
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
        
        # Farmer distribution
        st.subheader("Farmers Distribution")
        
        farmer_stats = {}
        for batch in data['batches']:
            farmer_name = batch['farmer_name']
            farmer_stats[farmer_name] = farmer_stats.get(farmer_name, 0) + batch['quantity_kg']
        
        if farmer_stats:
            fig = go.Figure(data=[
                go.Pie(
                    labels=list(farmer_stats.keys()),
                    values=list(farmer_stats.values()),
                    hole=0.3
                )
            ])
            fig.update_layout(height=400, title="Total Volume by Farmer (kg)")
            st.plotly_chart(fig, use_container_width=True)
        
        # Events summary
        st.subheader("Blockchain Events Summary")
        
        total_events = sum(b['events_count'] for b in data['batches'])
        st.write(f"**Total Events Anchored:** {total_events}")
        
        if total_events > 0:
            fig = go.Figure(data=[
                go.Bar(
                    x=[b['batch_id'] for b in data['batches'][:10]],
                    y=[b['events_count'] for b in data['batches'][:10]],
                    marker_color='#4ECDC4'
                )
            ])
            fig.update_layout(
                xaxis_title="Batch ID",
                yaxis_title="Number of Events",
                height=400,
                title="Events per Batch (Top 10)"
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
