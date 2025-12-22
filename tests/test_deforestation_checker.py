"""
Tests for Deforestation Checker - EUDR Article 10 Compliance

Tests satellite imagery integration for verifying deforestation-free status.

Author: Voice Ledger Team
Date: December 22, 2025
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice.verification.deforestation_checker import (
    DeforestationChecker,
    DeforestationResult,
    validate_farm_eudr_compliance
)


class TestDeforestationChecker(unittest.TestCase):
    """Test deforestation checking functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.checker = DeforestationChecker()
        
        # Test coordinates (Yirgacheffe, Ethiopia)
        self.test_lat = 6.1667
        self.test_lon = 38.2167
    
    @patch('requests.post')
    @patch('requests.get')
    def test_no_deforestation_detected(self, mock_get, mock_post):
        """Test scenario: No tree cover loss detected (EUDR compliant)"""
        
        # Mock geostore creation response
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "data": {
                    "id": "test-geostore-123"
                }
            }
        )
        mock_post.return_value.raise_for_status = Mock()
        
        # Mock tree cover loss query response (no loss)
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "data": []  # No records = no tree loss
            }
        )
        mock_get.return_value.raise_for_status = Mock()
        
        # Run check
        result = self.checker.check_deforestation(self.test_lat, self.test_lon)
        
        # Assertions
        self.assertTrue(result.compliant, "Should be EUDR compliant with no tree loss")
        self.assertEqual(result.risk_level, "LOW")
        self.assertFalse(result.deforestation_detected)
        self.assertEqual(result.tree_cover_loss_hectares, 0.0)
        self.assertGreater(result.confidence_score, 0.9)
        self.assertIn("No significant deforestation", result.details["recommendation"])
    
    @patch('requests.post')
    @patch('requests.get')
    def test_minor_tree_loss_compliant(self, mock_get, mock_post):
        """Test scenario: Minor tree loss < 0.5ha (still compliant, likely noise)"""
        
        # Mock geostore creation
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"data": {"id": "test-geostore-456"}}
        )
        mock_post.return_value.raise_for_status = Mock()
        
        # Mock tree cover loss: 0.3 hectares in 2022
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "data": [
                    {
                        "year": 2022,
                        "tree_loss_ha": 0.3,
                        "loss_area_ha": 0.3
                    }
                ]
            }
        )
        mock_get.return_value.raise_for_status = Mock()
        
        result = self.checker.check_deforestation(self.test_lat, self.test_lon)
        
        # Should still be compliant (below 0.5ha threshold)
        self.assertTrue(result.compliant, "Minor loss < 0.5ha should be compliant")
        self.assertEqual(result.risk_level, "LOW")
        self.assertFalse(result.deforestation_detected)
        self.assertEqual(result.tree_cover_loss_hectares, 0.3)
        self.assertIn(2022, result.details["loss_by_year"])
    
    @patch('requests.post')
    @patch('requests.get')
    def test_moderate_tree_loss_review_required(self, mock_get, mock_post):
        """Test scenario: Moderate tree loss 0.5-2.0ha (review required)"""
        
        # Mock responses
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"data": {"id": "test-geostore-789"}}
        )
        mock_post.return_value.raise_for_status = Mock()
        
        # Mock tree cover loss: 1.2 hectares spread over 2021-2022
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "data": [
                    {"year": 2021, "tree_loss_ha": 0.7, "loss_area_ha": 0.7},
                    {"year": 2022, "tree_loss_ha": 0.5, "loss_area_ha": 0.5}
                ]
            }
        )
        mock_get.return_value.raise_for_status = Mock()
        
        result = self.checker.check_deforestation(self.test_lat, self.test_lon)
        
        # Should be non-compliant, MEDIUM risk
        self.assertFalse(result.compliant, "1.2ha loss should be non-compliant")
        self.assertEqual(result.risk_level, "MEDIUM")
        self.assertTrue(result.deforestation_detected)
        self.assertEqual(result.tree_cover_loss_hectares, 1.2)
        self.assertIn("Manual review required", result.details["recommendation"])
    
    @patch('requests.post')
    @patch('requests.get')
    def test_high_tree_loss_violation(self, mock_get, mock_post):
        """Test scenario: High tree loss > 2.0ha (EUDR violation)"""
        
        # Mock responses
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"data": {"id": "test-geostore-999"}}
        )
        mock_post.return_value.raise_for_status = Mock()
        
        # Mock tree cover loss: 3.5 hectares in 2021
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "data": [
                    {"year": 2021, "tree_loss_ha": 3.5, "loss_area_ha": 3.5}
                ]
            }
        )
        mock_get.return_value.raise_for_status = Mock()
        
        result = self.checker.check_deforestation(self.test_lat, self.test_lon)
        
        # Should be non-compliant, HIGH risk
        self.assertFalse(result.compliant, "3.5ha loss should be EUDR violation")
        self.assertEqual(result.risk_level, "HIGH")
        self.assertTrue(result.deforestation_detected)
        self.assertEqual(result.tree_cover_loss_hectares, 3.5)
        self.assertIn("violation likely", result.details["recommendation"].lower())
    
    @patch('voice.verification.deforestation_checker.requests.post')
    def test_api_failure_handling(self, mock_post):
        """Test scenario: Global Forest Watch API unavailable"""
        
        # Mock API failure
        mock_post.side_effect = Exception("API connection timeout")
        
        result = self.checker.check_deforestation(self.test_lat, self.test_lon)
        
        # Should return UNKNOWN risk
        self.assertFalse(result.compliant, "Should be non-compliant if check fails")
        self.assertEqual(result.risk_level, "UNKNOWN")
        self.assertEqual(result.tree_cover_loss_hectares, 0.0)
        self.assertEqual(result.confidence_score, 0.0)
        self.assertIn("API connection timeout", result.details["error"])
    
    @patch('requests.post')
    @patch('requests.get')
    def test_multiple_years_aggregation(self, mock_get, mock_post):
        """Test scenario: Tree loss across multiple years after EUDR cutoff"""
        
        # Mock responses
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"data": {"id": "test-geostore-multi"}}
        )
        mock_post.return_value.raise_for_status = Mock()
        
        # Mock tree cover loss: Multiple years (2021-2024)
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "data": [
                    {"year": 2021, "tree_loss_ha": 0.3, "loss_area_ha": 0.3},
                    {"year": 2022, "tree_loss_ha": 0.4, "loss_area_ha": 0.4},
                    {"year": 2023, "tree_loss_ha": 0.2, "loss_area_ha": 0.2},
                    {"year": 2024, "tree_loss_ha": 0.8, "loss_area_ha": 0.8}
                ]
            }
        )
        mock_get.return_value.raise_for_status = Mock()
        
        result = self.checker.check_deforestation(self.test_lat, self.test_lon)
        
        # Total loss = 1.7 hectares (MEDIUM risk)
        self.assertEqual(result.tree_cover_loss_hectares, 1.7)
        self.assertEqual(result.risk_level, "MEDIUM")
        self.assertFalse(result.compliant)
        self.assertEqual(len(result.details["loss_by_year"]), 4)
        self.assertIn(2021, result.details["loss_by_year"])
        self.assertIn(2024, result.details["loss_by_year"])
    
    @patch('requests.post')
    @patch('requests.get')
    def test_ignores_pre_eudr_cutoff_loss(self, mock_get, mock_post):
        """Test scenario: Should ignore tree loss before Dec 31, 2020"""
        
        # Mock responses
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"data": {"id": "test-geostore-cutoff"}}
        )
        mock_post.return_value.raise_for_status = Mock()
        
        # Mock tree cover loss: Mix of pre-2021 and post-2020
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "data": [
                    {"year": 2019, "tree_loss_ha": 5.0, "loss_area_ha": 5.0},  # Before cutoff
                    {"year": 2020, "tree_loss_ha": 3.0, "loss_area_ha": 3.0},  # Cutoff year (ignored)
                    {"year": 2022, "tree_loss_ha": 0.3, "loss_area_ha": 0.3}   # After cutoff
                ]
            }
        )
        mock_get.return_value.raise_for_status = Mock()
        
        result = self.checker.check_deforestation(self.test_lat, self.test_lon)
        
        # Should only count 2022 loss (0.3ha)
        self.assertEqual(result.tree_cover_loss_hectares, 0.3)
        self.assertTrue(result.compliant, "Pre-2021 loss should be ignored")
        self.assertEqual(result.risk_level, "LOW")
        self.assertNotIn(2019, result.details["loss_by_year"])
        self.assertNotIn(2020, result.details["loss_by_year"])
        self.assertIn(2022, result.details["loss_by_year"])
    
    def test_result_dataclass_structure(self):
        """Test DeforestationResult dataclass structure"""
        
        result = DeforestationResult(
            compliant=True,
            risk_level="LOW",
            tree_cover_loss_hectares=0.1,
            deforestation_detected=False,
            check_date=datetime.utcnow(),
            data_source="Global Forest Watch - UMD",
            methodology="Satellite imagery analysis",
            confidence_score=0.95,
            details={"test": "data"}
        )
        
        # Verify all fields accessible
        self.assertTrue(result.compliant)
        self.assertEqual(result.risk_level, "LOW")
        self.assertEqual(result.tree_cover_loss_hectares, 0.1)
        self.assertFalse(result.deforestation_detected)
        self.assertIsInstance(result.check_date, datetime)
        self.assertEqual(result.data_source, "Global Forest Watch - UMD")
        self.assertEqual(result.confidence_score, 0.95)
        self.assertIn("test", result.details)
    
    @patch('requests.post')
    @patch('requests.get')
    def test_custom_radius(self, mock_get, mock_post):
        """Test deforestation check with custom radius"""
        
        # Mock responses
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"data": {"id": "test-geostore-radius"}}
        )
        mock_post.return_value.raise_for_status = Mock()
        
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {"data": []}
        )
        mock_get.return_value.raise_for_status = Mock()
        
        # Check with 500m radius
        result = self.checker.check_deforestation(
            self.test_lat,
            self.test_lon,
            radius_meters=500
        )
        
        # Verify POST was called with correct buffer
        post_call_args = mock_post.call_args
        geojson = post_call_args[1]['json']
        self.assertEqual(geojson['properties']['buffer'], 500)
        
        self.assertTrue(result.compliant)
    
    @patch('voice.verification.deforestation_checker.DeforestationChecker.check_deforestation')
    def test_utility_function(self, mock_check):
        """Test validate_farm_eudr_compliance utility function"""
        
        # Mock result
        mock_result = DeforestationResult(
            compliant=True,
            risk_level="LOW",
            tree_cover_loss_hectares=0.0,
            deforestation_detected=False,
            check_date=datetime.utcnow(),
            data_source="Test",
            methodology="Test method",
            confidence_score=0.95,
            details={"recommendation": "All clear"}
        )
        mock_check.return_value = mock_result
        
        # Call utility function
        result = validate_farm_eudr_compliance(self.test_lat, self.test_lon)
        
        # Verify simplified response
        self.assertIn("eudr_compliant", result)
        self.assertTrue(result["eudr_compliant"])
        self.assertEqual(result["risk_level"], "LOW")
        self.assertEqual(result["tree_cover_loss_hectares"], 0.0)
        self.assertFalse(result["deforestation_detected"])
        self.assertEqual(result["confidence"], 0.95)
        self.assertIn("checked_at", result)


class TestDeforestationMultipleLocations(unittest.TestCase):
    """Test batch checking of multiple locations"""
    
    def setUp(self):
        self.checker = DeforestationChecker()
    
    @patch('voice.verification.deforestation_checker.DeforestationChecker.check_deforestation')
    def test_check_multiple_locations(self, mock_check):
        """Test checking multiple farm locations"""
        
        # Mock results for different locations
        def mock_check_side_effect(lat, lon, radius):
            return DeforestationResult(
                compliant=(lat > 6.0),  # Different results based on lat
                risk_level="LOW" if lat > 6.0 else "HIGH",
                tree_cover_loss_hectares=0.0 if lat > 6.0 else 5.0,
                deforestation_detected=(lat <= 6.0),
                check_date=datetime.utcnow(),
                data_source="Test",
                methodology="Test",
                confidence_score=0.9,
                details={}
            )
        
        mock_check.side_effect = mock_check_side_effect
        
        # Test coordinates
        coords = [
            (6.1667, 38.2167),  # Yirgacheffe (should be compliant)
            (5.5000, 37.0000),  # Lower location (should be non-compliant)
            (7.0000, 39.0000),  # Northern location (should be compliant)
        ]
        
        results = self.checker.check_multiple_locations(coords)
        
        # Verify results
        self.assertEqual(len(results), 3)
        self.assertTrue(results[(6.1667, 38.2167)].compliant)
        self.assertFalse(results[(5.5000, 37.0000)].compliant)
        self.assertTrue(results[(7.0000, 39.0000)].compliant)
    
    def test_compliance_summary(self):
        """Test compliance summary generation"""
        
        # Create mock results
        results = [
            DeforestationResult(
                compliant=True,
                risk_level="LOW",
                tree_cover_loss_hectares=0.1,
                deforestation_detected=False,
                check_date=datetime.utcnow(),
                data_source="Test",
                methodology="Test",
                confidence_score=0.95,
                details={}
            ),
            DeforestationResult(
                compliant=True,
                risk_level="LOW",
                tree_cover_loss_hectares=0.0,
                deforestation_detected=False,
                check_date=datetime.utcnow(),
                data_source="Test",
                methodology="Test",
                confidence_score=0.90,
                details={}
            ),
            DeforestationResult(
                compliant=False,
                risk_level="HIGH",
                tree_cover_loss_hectares=3.5,
                deforestation_detected=True,
                check_date=datetime.utcnow(),
                data_source="Test",
                methodology="Test",
                confidence_score=0.85,
                details={}
            )
        ]
        
        summary = self.checker.get_compliance_summary(results)
        
        # Verify summary
        self.assertEqual(summary["total_locations_checked"], 3)
        self.assertEqual(summary["compliant_count"], 2)
        self.assertEqual(summary["non_compliant_count"], 1)
        self.assertEqual(summary["compliance_rate"], 66.67)
        self.assertEqual(summary["total_tree_loss_hectares"], 3.6)
        self.assertAlmostEqual(summary["average_confidence"], 0.9, places=2)
        self.assertEqual(summary["risk_distribution"]["LOW"], 2)
        self.assertEqual(summary["risk_distribution"]["HIGH"], 1)
        self.assertIn("Manual review required", summary["recommendation"])


if __name__ == "__main__":
    print("🌳 Running Deforestation Checker Tests")
    print("=" * 70)
    print("Testing EUDR Article 10 compliance - satellite imagery integration")
    print("=" * 70)
    print()
    
    # Run tests
    unittest.main(verbosity=2)
