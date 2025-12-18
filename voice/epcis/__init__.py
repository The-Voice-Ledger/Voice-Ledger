"""
EPCIS Event Creation Module

Handles creation of EPCIS 2.0 events for supply chain traceability.
"""

from .commission_events import create_commission_event

__all__ = ['create_commission_event']
