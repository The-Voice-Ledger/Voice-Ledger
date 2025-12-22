"""
Unit Tests for GPS Photo Verifier

Tests GPS extraction, validation, and EUDR compliance checks.
Part of Phase A - EUDR GPS Photo Verification Implementation.
"""

import os
import pytest
import tempfile
from io import BytesIO
from datetime import datetime, timedelta
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import piexif

from voice.verification.gps_photo_verifier import (
    GPSPhotoVerifier,
    GPSExtractionError,
    is_in_ethiopia
)


class TestGPSPhotoVerifier:
    """Test suite for GPS photo verification functionality."""
    
    @pytest.fixture
    def verifier(self):
        """Create GPSPhotoVerifier instance for testing."""
        return GPSPhotoVerifier()
    
    @pytest.fixture
    def sample_photo_with_gps(self):
        """Create a test photo with GPS EXIF data."""
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        
        # Create EXIF data with GPS
        # Addis Ababa coordinates: 9.0320°N, 38.7469°E
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: b"Apple",
                piexif.ImageIFD.Model: b"iPhone 14 Pro",
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: b"2025:12:22 14:30:00",
            },
            "GPS": {
                piexif.GPSIFD.GPSLatitudeRef: b'N',
                piexif.GPSIFD.GPSLatitude: [(9, 1), (1, 1), (5520, 100)],  # 9°1'55.2" = 9.032°
                piexif.GPSIFD.GPSLongitudeRef: b'E',
                piexif.GPSIFD.GPSLongitude: [(38, 1), (44, 1), (4840, 100)],  # 38°44'48.4" = 38.7469°
                piexif.GPSIFD.GPSAltitude: (2355, 1),  # 2355 meters
                piexif.GPSIFD.GPSTimeStamp: [(14, 1), (30, 1), (0, 1)],
                piexif.GPSIFD.GPSDateStamp: b"2025:12:22",
            }
        }
        
        exif_bytes = piexif.dump(exif_dict)
        
        # Save to BytesIO
        output = BytesIO()
        img.save(output, format='JPEG', exif=exif_bytes)
        output.seek(0)
        
        return output
    
    @pytest.fixture
    def sample_photo_without_gps(self):
        """Create a test photo without GPS EXIF data."""
        img = Image.new('RGB', (100, 100), color='blue')
        
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: b"Canon",
                piexif.ImageIFD.Model: b"EOS 5D",
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: b"2025:12:22 10:00:00",
            }
        }
        
        exif_bytes = piexif.dump(exif_dict)
        output = BytesIO()
        img.save(output, format='JPEG', exif=exif_bytes)
        output.seek(0)
        
        return output
    
    def test_extract_gps_with_valid_data(self, verifier, sample_photo_with_gps):
        """Test GPS extraction from photo with valid GPS EXIF data."""
        gps_data = verifier.extract_gps_data(sample_photo_with_gps)
        
        assert gps_data['has_gps'] is True
        assert 9.0 <= gps_data['latitude'] <= 9.1  # Approximately 9.032
        assert 38.7 <= gps_data['longitude'] <= 38.8  # Approximately 38.7469
        assert gps_data['altitude'] == 2355.0
        assert gps_data['device_make'] == 'Apple'
        assert gps_data['device_model'] == 'iPhone 14 Pro'
        assert gps_data['timestamp'] is not None
    
    def test_extract_gps_without_gps_data(self, verifier, sample_photo_without_gps):
        """Test GPS extraction from photo without GPS data."""
        gps_data = verifier.extract_gps_data(sample_photo_without_gps)
        
        assert gps_data['has_gps'] is False
        assert 'error' in gps_data
        assert gps_data['device_make'] == 'Canon'
        assert gps_data['timestamp'] is not None
    
    def test_extract_gps_from_bytes(self, verifier, sample_photo_with_gps):
        """Test GPS extraction from binary photo data."""
        photo_bytes = sample_photo_with_gps.getvalue()
        gps_data = verifier.extract_gps_data(photo_bytes)
        
        assert gps_data['has_gps'] is True
        assert gps_data['latitude'] is not None
        assert gps_data['longitude'] is not None
    
    def test_extract_gps_from_file_path(self, verifier, sample_photo_with_gps):
        """Test GPS extraction from file path."""
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(sample_photo_with_gps.getvalue())
            tmp_path = tmp.name
        
        try:
            gps_data = verifier.extract_gps_data(tmp_path)
            assert gps_data['has_gps'] is True
        finally:
            os.unlink(tmp_path)
    
    def test_extract_gps_invalid_input(self, verifier):
        """Test GPS extraction with invalid input type."""
        with pytest.raises(GPSExtractionError):
            verifier.extract_gps_data(12345)  # Invalid type
    
    def test_convert_to_decimal_degrees(self, verifier):
        """Test conversion of GPS coordinates to decimal degrees."""
        # 9°1'55.2" should equal 9.032°
        coord = ((9, 1), (1, 1), (5520, 100))
        decimal = verifier._convert_to_decimal_degrees(coord)
        
        assert 9.03 <= decimal <= 9.04
    
    def test_convert_to_decimal_degrees_invalid(self, verifier):
        """Test coordinate conversion with invalid input."""
        with pytest.raises(ValueError):
            verifier._convert_to_decimal_degrees(((9, 1),))  # Only 1 element
    
    def test_compute_photo_hash_sha256(self, verifier, sample_photo_with_gps):
        """Test SHA-256 photo hash computation."""
        hash1 = verifier.compute_photo_hash(sample_photo_with_gps, algorithm='sha256')
        
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA-256 produces 64 hex characters
        
        # Same photo should produce same hash
        sample_photo_with_gps.seek(0)
        hash2 = verifier.compute_photo_hash(sample_photo_with_gps, algorithm='sha256')
        assert hash1 == hash2
    
    def test_compute_photo_hash_md5(self, verifier, sample_photo_with_gps):
        """Test MD5 photo hash computation."""
        hash1 = verifier.compute_photo_hash(sample_photo_with_gps, algorithm='md5')
        
        assert isinstance(hash1, str)
        assert len(hash1) == 32  # MD5 produces 32 hex characters
    
    def test_compute_photo_hash_different_photos(self, verifier, sample_photo_with_gps, sample_photo_without_gps):
        """Test that different photos produce different hashes."""
        hash1 = verifier.compute_photo_hash(sample_photo_with_gps)
        hash2 = verifier.compute_photo_hash(sample_photo_without_gps)
        
        assert hash1 != hash2
    
    def test_haversine_distance_same_location(self, verifier):
        """Test distance calculation for same coordinates."""
        addis_ababa = (9.0320, 38.7469)
        distance = verifier.haversine_distance(addis_ababa, addis_ababa)
        
        assert distance == 0.0
    
    def test_haversine_distance_known_values(self, verifier):
        """Test distance calculation with known distances."""
        # Addis Ababa to Sidama (approximately 245 km)
        addis_ababa = (9.0320, 38.7469)
        sidama = (6.8500, 38.4500)
        
        distance = verifier.haversine_distance(addis_ababa, sidama)
        
        # Allow 10% margin for approximation
        assert 220 <= distance <= 270
    
    def test_haversine_distance_short_distance(self, verifier):
        """Test distance calculation for short distances."""
        # Two points ~1 km apart
        point1 = (9.0320, 38.7469)
        point2 = (9.0410, 38.7469)  # ~1 km north
        
        distance = verifier.haversine_distance(point1, point2)
        
        assert 0.8 <= distance <= 1.2  # Approximately 1 km
    
    def test_validate_location_proximity_valid(self, verifier):
        """Test location proximity validation within acceptable range."""
        photo_coords = (9.0320, 38.7469)
        farm_coords = (9.0410, 38.7469)  # ~1 km apart
        
        result = verifier.validate_location_proximity(
            photo_coords,
            farm_coords,
            max_distance_km=5.0
        )
        
        assert result['valid'] is True
        assert result['distance_km'] < 5.0
        assert 'acceptable' in result['message'].lower()
    
    def test_validate_location_proximity_invalid(self, verifier):
        """Test location proximity validation beyond acceptable range."""
        addis_ababa = (9.0320, 38.7469)
        sidama = (6.8500, 38.4500)  # ~245 km apart
        
        result = verifier.validate_location_proximity(
            addis_ababa,
            sidama,
            max_distance_km=50.0
        )
        
        assert result['valid'] is False
        assert result['distance_km'] > 50.0
        assert 'too far' in result['message'].lower()
    
    def test_validate_ethiopia_bounds_valid_coordinates(self, verifier):
        """Test Ethiopia boundary validation with valid coordinates."""
        # Addis Ababa
        assert verifier.validate_ethiopia_bounds(9.0320, 38.7469) is True
        
        # Dire Dawa
        assert verifier.validate_ethiopia_bounds(9.6011, 41.8661) is True
        
        # Mekelle
        assert verifier.validate_ethiopia_bounds(13.4967, 39.4753) is True
    
    def test_validate_ethiopia_bounds_invalid_coordinates(self, verifier):
        """Test Ethiopia boundary validation with invalid coordinates."""
        # Nairobi, Kenya
        assert verifier.validate_ethiopia_bounds(-1.2921, 36.8219) is False
        
        # Atlantic Ocean
        assert verifier.validate_ethiopia_bounds(0.0, 0.0) is False
        
        # New York
        assert verifier.validate_ethiopia_bounds(40.7128, -74.0060) is False
    
    def test_validate_ethiopia_bounds_edge_cases(self, verifier):
        """Test Ethiopia boundary validation at edges."""
        # Just inside northern border
        assert verifier.validate_ethiopia_bounds(14.9, 38.0) is True
        
        # Just outside northern border
        assert verifier.validate_ethiopia_bounds(15.1, 38.0) is False
        
        # Just inside eastern border
        assert verifier.validate_ethiopia_bounds(9.0, 47.9) is True
        
        # Just outside eastern border
        assert verifier.validate_ethiopia_bounds(9.0, 48.1) is False
    
    def test_is_in_ethiopia_helper(self):
        """Test convenience function for Ethiopia validation."""
        assert is_in_ethiopia(9.0320, 38.7469) is True
        assert is_in_ethiopia(0.0, 0.0) is False
    
    def test_validate_timestamp_recency_recent(self, verifier):
        """Test timestamp validation for recent photo."""
        # Photo taken 2 days ago
        recent_timestamp = (datetime.utcnow() - timedelta(days=2)).isoformat()
        
        result = verifier.validate_timestamp_recency(recent_timestamp, max_age_days=7)
        
        assert result['valid'] is True
        assert result['age_days'] < 7
        assert 'acceptable' in result['message'].lower()
    
    def test_validate_timestamp_recency_old(self, verifier):
        """Test timestamp validation for old photo."""
        # Photo taken 30 days ago
        old_timestamp = (datetime.utcnow() - timedelta(days=30)).isoformat()
        
        result = verifier.validate_timestamp_recency(old_timestamp, max_age_days=7)
        
        assert result['valid'] is False
        assert result['age_days'] > 7
        assert 'exceeds' in result['message'].lower()
    
    def test_validate_timestamp_recency_invalid_format(self, verifier):
        """Test timestamp validation with invalid format."""
        result = verifier.validate_timestamp_recency("not-a-timestamp", max_age_days=7)
        
        assert result['valid'] is False
        assert result['age_days'] is None
        assert 'invalid' in result['message'].lower()
    
    def test_extract_timestamp_from_exif(self, verifier):
        """Test timestamp extraction from EXIF data."""
        exif_data = {
            'DateTimeOriginal': '2025:12:22 14:30:00'
        }
        
        timestamp = verifier._extract_timestamp(exif_data)
        
        assert timestamp is not None
        assert '2025-12-22' in timestamp
        assert '14:30:00' in timestamp
    
    def test_extract_timestamp_fallback(self, verifier):
        """Test timestamp extraction with fallback fields."""
        exif_data = {
            'DateTime': '2025:12:22 10:00:00'  # No DateTimeOriginal
        }
        
        timestamp = verifier._extract_timestamp(exif_data)
        
        assert timestamp is not None
        assert '2025-12-22' in timestamp
    
    def test_extract_timestamp_missing(self, verifier):
        """Test timestamp extraction when no timestamp available."""
        exif_data = {}
        
        timestamp = verifier._extract_timestamp(exif_data)
        
        assert timestamp is None


class TestGPSExtractionIntegration:
    """Integration tests for GPS extraction workflow."""
    
    @pytest.fixture
    def verifier(self):
        return GPSPhotoVerifier()
    
    def test_full_eudr_validation_workflow(self, verifier):
        """Test complete EUDR validation workflow."""
        # Create photo with GPS in Ethiopia
        img = Image.new('RGB', (100, 100), color='green')
        
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: b"Samsung",
                piexif.ImageIFD.Model: b"Galaxy S23",
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: datetime.utcnow().strftime("%Y:%m:%d %H:%M:%S").encode(),
            },
            "GPS": {
                piexif.GPSIFD.GPSLatitudeRef: b'N',
                piexif.GPSIFD.GPSLatitude: [(9, 1), (8, 1), (0, 1)],  # 9.133°
                piexif.GPSIFD.GPSLongitudeRef: b'E',
                piexif.GPSIFD.GPSLongitude: [(40, 1), (28, 1), (0, 1)],  # 40.467°
            }
        }
        
        exif_bytes = piexif.dump(exif_dict)
        output = BytesIO()
        img.save(output, format='JPEG', exif=exif_bytes)
        output.seek(0)
        
        # Step 1: Extract GPS
        gps_data = verifier.extract_gps_data(output)
        assert gps_data['has_gps'] is True
        
        # Step 2: Validate Ethiopia bounds
        in_ethiopia = verifier.validate_ethiopia_bounds(
            gps_data['latitude'],
            gps_data['longitude']
        )
        assert in_ethiopia is True
        
        # Step 3: Validate timestamp recency
        timestamp_result = verifier.validate_timestamp_recency(
            gps_data['timestamp'],
            max_age_days=7
        )
        assert timestamp_result['valid'] is True
        
        # Step 4: Compute hash for duplicate detection
        output.seek(0)
        photo_hash = verifier.compute_photo_hash(output)
        assert len(photo_hash) == 64
        
        # EUDR compliant!
        print(f"\n✅ EUDR Validation Complete:")
        print(f"   GPS: {gps_data['latitude']:.6f}, {gps_data['longitude']:.6f}")
        print(f"   In Ethiopia: {in_ethiopia}")
        print(f"   Photo age: {timestamp_result['age_days']:.1f} days")
        print(f"   Hash: {photo_hash[:16]}...")
    
    def test_eudr_rejection_outside_ethiopia(self, verifier):
        """Test EUDR rejection for coordinates outside Ethiopia."""
        # Create photo with GPS in Kenya
        img = Image.new('RGB', (100, 100), color='red')
        
        exif_dict = {
            "GPS": {
                piexif.GPSIFD.GPSLatitudeRef: b'S',
                piexif.GPSIFD.GPSLatitude: [(1, 1), (17, 1), (0, 1)],  # -1.283° (Nairobi)
                piexif.GPSIFD.GPSLongitudeRef: b'E',
                piexif.GPSIFD.GPSLongitude: [(36, 1), (49, 1), (0, 1)],  # 36.817°
            }
        }
        
        exif_bytes = piexif.dump(exif_dict)
        output = BytesIO()
        img.save(output, format='JPEG', exif=exif_bytes)
        output.seek(0)
        
        gps_data = verifier.extract_gps_data(output)
        in_ethiopia = verifier.validate_ethiopia_bounds(
            gps_data['latitude'],
            gps_data['longitude']
        )
        
        assert in_ethiopia is False
        print("\n❌ EUDR Rejected: Coordinates outside Ethiopia")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
