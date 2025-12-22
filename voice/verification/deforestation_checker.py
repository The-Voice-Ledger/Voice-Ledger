"""
Deforestation Checker - EUDR Article 10 Compliance

Validates that coffee farm plots have NOT experienced deforestation
after December 31, 2020 (EUDR cutoff date) using satellite imagery data.

Uses Global Forest Watch API (free) to query UMD tree cover loss dataset.

EUDR Requirements:
- Article 10: Commodities must be deforestation-free
- Deforestation = Forest conversion after Dec 31, 2020
- Must provide verifiable evidence to EU customs

Author: Voice Ledger Team
Date: December 22, 2025
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DeforestationResult:
    """Result of deforestation check"""
    compliant: bool
    risk_level: str  # LOW, MEDIUM, HIGH
    tree_cover_loss_hectares: float
    deforestation_detected: bool
    check_date: datetime
    data_source: str
    methodology: str
    confidence_score: float  # 0.0 to 1.0
    details: Dict


class DeforestationChecker:
    """
    Check farm plots for deforestation using satellite imagery.
    
    Data Source: Global Forest Watch - UMD Tree Cover Loss
    Coverage: Global, yearly updates
    Resolution: 30m x 30m pixels
    Timeframe: 2001-present
    
    EUDR Cutoff: December 31, 2020
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize deforestation checker.
        
        Args:
            api_key: Optional API key for Global Forest Watch
                    (not required for basic queries, but recommended for production)
        """
        self.api_key = api_key
        self.base_url = "https://data-api.globalforestwatch.org"
        self.eudr_cutoff_year = 2020
        
        # API endpoints
        self.geostore_url = f"{self.base_url}/geostore"
        self.dataset_url = f"{self.base_url}/dataset/umd_tree_cover_loss/latest/query"
    
    def check_deforestation(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 1000,
        confidence_threshold: float = 0.7
    ) -> DeforestationResult:
        """
        Check if deforestation occurred at farm location after EUDR cutoff.
        
        Args:
            latitude: Farm latitude (decimal degrees)
            longitude: Farm longitude (decimal degrees)
            radius_meters: Radius around point to check (default 1km)
            confidence_threshold: Minimum confidence for detection (0.0-1.0)
        
        Returns:
            DeforestationResult with compliance status and details
        
        Raises:
            requests.RequestException: If API request fails
        """
        try:
            logger.info(f"Checking deforestation at {latitude}, {longitude} (radius: {radius_meters}m)")
            
            # Step 1: Create geostore (area of interest)
            geostore_id = self._create_geostore(latitude, longitude, radius_meters)
            
            # Step 2: Query tree cover loss for years 2021+
            tree_loss_data = self._query_tree_cover_loss(geostore_id)
            
            # Step 3: Analyze results
            return self._analyze_deforestation(tree_loss_data, latitude, longitude)
            
        except Exception as e:
            logger.error(f"Deforestation check failed: {str(e)}")
            # Return cautious result if API fails
            return DeforestationResult(
                compliant=False,
                risk_level="UNKNOWN",
                tree_cover_loss_hectares=0.0,
                deforestation_detected=False,
                check_date=datetime.utcnow(),
                data_source="Global Forest Watch (API Error)",
                methodology="Satellite imagery analysis failed",
                confidence_score=0.0,
                details={"error": str(e), "status": "api_unavailable"}
            )
    
    def _create_geostore(self, latitude: float, longitude: float, radius_meters: int) -> str:
        """
        Create geostore (geographic area) around farm point.
        
        Returns geostore_id for subsequent queries.
        """
        # Create circular buffer around point
        # GFW expects GeoJSON format
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [longitude, latitude]  # GeoJSON uses [lon, lat]
            },
            "properties": {
                "buffer": radius_meters  # Buffer in meters
            }
        }
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        
        response = requests.post(
            self.geostore_url,
            json=geojson,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        geostore_id = data['data']['id']
        
        logger.info(f"Created geostore: {geostore_id}")
        return geostore_id
    
    def _query_tree_cover_loss(self, geostore_id: str) -> Dict:
        """
        Query UMD tree cover loss dataset for years after EUDR cutoff.
        
        Returns tree loss statistics by year.
        """
        # SQL query to get tree cover loss after 2020
        sql_query = (
            "SELECT umd_tree_cover_loss__year as year, "
            "SUM(area__ha) as loss_area_ha, "
            "SUM(umd_tree_cover_loss__ha) as tree_loss_ha "
            "FROM data "
            f"WHERE umd_tree_cover_loss__year > {self.eudr_cutoff_year} "
            "GROUP BY year "
            "ORDER BY year"
        )
        
        params = {
            "sql": sql_query,
            "geostore_id": geostore_id
        }
        
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        
        response = requests.get(
            self.dataset_url,
            params=params,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Tree cover loss query returned {len(data.get('data', []))} records")
        
        return data
    
    def _analyze_deforestation(
        self,
        tree_loss_data: Dict,
        latitude: float,
        longitude: float
    ) -> DeforestationResult:
        """
        Analyze tree cover loss data and determine EUDR compliance.
        
        Risk Levels:
        - LOW: < 0.5 hectares lost (likely natural variation or noise)
        - MEDIUM: 0.5 - 2.0 hectares lost (review required)
        - HIGH: > 2.0 hectares lost (likely deforestation violation)
        """
        records = tree_loss_data.get('data', [])
        
        # Calculate total tree loss after EUDR cutoff
        total_loss_ha = 0.0
        loss_by_year = {}
        
        for record in records:
            year = record.get('year')
            loss_ha = record.get('tree_loss_ha', 0.0) or record.get('loss_area_ha', 0.0)
            
            if year and year > self.eudr_cutoff_year:
                total_loss_ha += loss_ha
                loss_by_year[year] = loss_ha
        
        # Determine compliance and risk level
        if total_loss_ha == 0.0:
            # No tree cover loss detected
            compliant = True
            risk_level = "LOW"
            deforestation_detected = False
            confidence = 0.95
            
        elif total_loss_ha < 0.5:
            # Minor loss (likely noise or natural variation)
            compliant = True
            risk_level = "LOW"
            deforestation_detected = False
            confidence = 0.85
            
        elif total_loss_ha < 2.0:
            # Moderate loss - requires manual review
            compliant = False
            risk_level = "MEDIUM"
            deforestation_detected = True
            confidence = 0.75
            
        else:
            # Significant loss - likely EUDR violation
            compliant = False
            risk_level = "HIGH"
            deforestation_detected = True
            confidence = 0.90
        
        # Build detailed result
        details = {
            "total_loss_hectares": round(total_loss_ha, 4),
            "loss_by_year": loss_by_year,
            "eudr_cutoff_year": self.eudr_cutoff_year,
            "check_coordinates": {"latitude": latitude, "longitude": longitude},
            "analysis_date": datetime.utcnow().isoformat(),
            "recommendation": self._get_recommendation(risk_level, total_loss_ha)
        }
        
        return DeforestationResult(
            compliant=compliant,
            risk_level=risk_level,
            tree_cover_loss_hectares=round(total_loss_ha, 4),
            deforestation_detected=deforestation_detected,
            check_date=datetime.utcnow(),
            data_source="Global Forest Watch - UMD Tree Cover Loss",
            methodology="Satellite imagery analysis (Landsat 30m resolution) comparing tree cover loss after Dec 31, 2020",
            confidence_score=confidence,
            details=details
        )
    
    def _get_recommendation(self, risk_level: str, loss_ha: float) -> str:
        """Generate recommendation based on risk level"""
        if risk_level == "LOW":
            return "EUDR compliant - No significant deforestation detected. Batch approved for EU export."
        elif risk_level == "MEDIUM":
            return f"Manual review required - {loss_ha:.2f} hectares tree cover loss detected. Verify with field assessment."
        else:  # HIGH
            return f"EUDR violation likely - {loss_ha:.2f} hectares tree cover loss detected. Reject batch or require additional evidence."
    
    def check_multiple_locations(
        self,
        coordinates: list[Tuple[float, float]],
        radius_meters: int = 1000
    ) -> Dict[Tuple[float, float], DeforestationResult]:
        """
        Check deforestation for multiple farm locations.
        
        Args:
            coordinates: List of (latitude, longitude) tuples
            radius_meters: Radius around each point
        
        Returns:
            Dictionary mapping coordinates to DeforestationResult
        """
        results = {}
        
        for lat, lon in coordinates:
            try:
                result = self.check_deforestation(lat, lon, radius_meters)
                results[(lat, lon)] = result
            except Exception as e:
                logger.error(f"Failed to check {lat}, {lon}: {str(e)}")
                results[(lat, lon)] = None
        
        return results
    
    def get_compliance_summary(self, results: list[DeforestationResult]) -> Dict:
        """
        Generate summary statistics for multiple deforestation checks.
        
        Returns overall compliance rate, average risk, etc.
        """
        total = len(results)
        if total == 0:
            return {"error": "No results to summarize"}
        
        compliant_count = sum(1 for r in results if r.compliant)
        total_loss = sum(r.tree_cover_loss_hectares for r in results)
        avg_confidence = sum(r.confidence_score for r in results) / total
        
        risk_distribution = {
            "LOW": sum(1 for r in results if r.risk_level == "LOW"),
            "MEDIUM": sum(1 for r in results if r.risk_level == "MEDIUM"),
            "HIGH": sum(1 for r in results if r.risk_level == "HIGH"),
            "UNKNOWN": sum(1 for r in results if r.risk_level == "UNKNOWN")
        }
        
        return {
            "total_locations_checked": total,
            "compliant_count": compliant_count,
            "non_compliant_count": total - compliant_count,
            "compliance_rate": round(compliant_count / total * 100, 2),
            "total_tree_loss_hectares": round(total_loss, 4),
            "average_confidence": round(avg_confidence, 3),
            "risk_distribution": risk_distribution,
            "recommendation": "All batches approved" if compliant_count == total else "Manual review required for non-compliant batches"
        }


# Utility functions for standalone usage

def validate_farm_eudr_compliance(
    latitude: float,
    longitude: float,
    radius_meters: int = 1000
) -> Dict:
    """
    Quick validation function for EUDR compliance.
    
    Returns simple compliance status for API/UI usage.
    """
    checker = DeforestationChecker()
    result = checker.check_deforestation(latitude, longitude, radius_meters)
    
    return {
        "eudr_compliant": result.compliant,
        "risk_level": result.risk_level,
        "tree_cover_loss_hectares": result.tree_cover_loss_hectares,
        "deforestation_detected": result.deforestation_detected,
        "confidence": result.confidence_score,
        "recommendation": result.details.get("recommendation"),
        "checked_at": result.check_date.isoformat()
    }


if __name__ == "__main__":
    # Example usage
    print("🌳 Deforestation Checker - EUDR Compliance")
    print("=" * 60)
    
    # Example: Check coffee farm in Yirgacheffe, Ethiopia
    checker = DeforestationChecker()
    
    # Test coordinates (Yirgacheffe region)
    test_lat, test_lon = 6.1667, 38.2167
    
    print(f"\n📍 Checking location: {test_lat}, {test_lon}")
    print(f"   Region: Yirgacheffe, Sidama, Ethiopia")
    print(f"   Radius: 1000m (1km)")
    print(f"   EUDR Cutoff: December 31, 2020\n")
    
    result = checker.check_deforestation(test_lat, test_lon, radius_meters=1000)
    
    print(f"✅ EUDR Compliant: {result.compliant}")
    print(f"⚠️  Risk Level: {result.risk_level}")
    print(f"🌲 Tree Cover Loss: {result.tree_cover_loss_hectares} hectares")
    print(f"🔍 Deforestation Detected: {result.deforestation_detected}")
    print(f"📊 Confidence: {result.confidence_score * 100:.1f}%")
    print(f"📅 Checked: {result.check_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📖 Data Source: {result.data_source}")
    print(f"\n💡 Recommendation:")
    print(f"   {result.details['recommendation']}")
    
    print("\n" + "=" * 60)
    print("✨ Check complete!")
