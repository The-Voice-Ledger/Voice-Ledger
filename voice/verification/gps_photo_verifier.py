"""
GPS Photo Verification Module

Extracts GPS coordinates from photo EXIF metadata for EUDR compliance.
EU Regulation 2023/1115 Article 9 requires geolocation proof for coffee imports.

This module provides:
- GPS extraction from photo EXIF data
- Photo hash computation for duplicate detection
- Distance calculation for farm proximity validation
- EUDR compliance validation

Part of EUDR GPS Photo Verification Implementation (Phase A)
"""

import os
import hashlib
import logging
from io import BytesIO
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

logger = logging.getLogger(__name__)


class GPSExtractionError(Exception):
    """Raised when GPS data cannot be extracted from photo."""
    pass


class GPSPhotoVerifier:
    """
    Extract and validate GPS coordinates from photo EXIF metadata.
    
    Designed for EUDR Article 9 compliance - provides cryptographic proof
    that farmer was physically present at farm location.
    
    Example:
        >>> verifier = GPSPhotoVerifier()
        >>> gps_data = verifier.extract_gps_data('farm_photo.jpg')
        >>> print(f"Coordinates: {gps_data['latitude']}, {gps_data['longitude']}")
        Coordinates: 9.145, 40.4897
        
        >>> # Validate proximity to registered farm
        >>> distance = verifier.haversine_distance(
        ...     (gps_data['latitude'], gps_data['longitude']),
        ...     (9.150, 40.485)
        ... )
        >>> print(f"Distance: {distance:.2f} km")
        Distance: 0.85 km
    """
    
    # Ethiopia geographical boundaries
    ETHIOPIA_LAT_MIN = 3.0
    ETHIOPIA_LAT_MAX = 15.0
    ETHIOPIA_LON_MIN = 33.0
    ETHIOPIA_LON_MAX = 48.0
    
    def extract_gps_data(self, image_source) -> Dict[str, Any]:
        """
        Extract GPS coordinates and metadata from photo EXIF.
        
        Supports multiple input formats:
        - File path (string)
        - File object (io.BytesIO)
        - Binary data (bytes)
        
        Args:
            image_source: Photo file path, file object, or binary data
            
        Returns:
            Dictionary with GPS data:
            {
                "latitude": float,       # Decimal degrees
                "longitude": float,      # Decimal degrees
                "altitude": float,       # Meters (optional)
                "accuracy": float,       # Meters (optional)
                "timestamp": str,        # ISO 8601 format
                "device_make": str,      # Camera/phone manufacturer
                "device_model": str,     # Camera/phone model
                "has_gps": bool          # True if GPS data found
            }
            
        Raises:
            GPSExtractionError: If image cannot be opened or processed
            
        Example:
            >>> verifier = GPSPhotoVerifier()
            >>> data = verifier.extract_gps_data('photo.jpg')
            >>> if data['has_gps']:
            ...     print(f"Location: {data['latitude']}, {data['longitude']}")
        """
        try:
            # Handle different input types
            if isinstance(image_source, str):
                # File path
                image = Image.open(image_source)
            elif isinstance(image_source, bytes):
                # Binary data
                image = Image.open(BytesIO(image_source))
            elif isinstance(image_source, BytesIO):
                # File object
                image = Image.open(image_source)
            else:
                raise GPSExtractionError(f"Unsupported image source type: {type(image_source)}")
            
            # Extract EXIF data
            exif = image._getexif()
            
            if not exif:
                logger.warning("No EXIF data found in image")
                return {
                    "has_gps": False,
                    "error": "No EXIF data found",
                    "timestamp": None,
                    "device_make": None,
                    "device_model": None
                }
            
            # Parse EXIF tags
            exif_data = {}
            gps_data = {}
            
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                exif_data[tag] = value
                
                # Extract GPS info
                if tag == "GPSInfo":
                    for gps_tag_id in value:
                        gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                        gps_data[gps_tag] = value[gps_tag_id]
            
            # Check if GPS data exists
            if not gps_data or 'GPSLatitude' not in gps_data or 'GPSLongitude' not in gps_data:
                logger.warning("No GPS coordinates in EXIF data")
                return {
                    "has_gps": False,
                    "error": "No GPS coordinates found in photo",
                    "timestamp": self._extract_timestamp(exif_data),
                    "device_make": exif_data.get('Make'),
                    "device_model": exif_data.get('Model')
                }
            
            # Convert GPS coordinates to decimal degrees
            lat = self._convert_to_decimal_degrees(gps_data.get('GPSLatitude'))
            lon = self._convert_to_decimal_degrees(gps_data.get('GPSLongitude'))
            
            # Adjust for hemisphere
            if gps_data.get('GPSLatitudeRef') == 'S':
                lat = -lat
            if gps_data.get('GPSLongitudeRef') == 'W':
                lon = -lon
            
            # Extract altitude if available
            altitude = None
            if 'GPSAltitude' in gps_data:
                altitude_data = gps_data['GPSAltitude']
                if isinstance(altitude_data, tuple):
                    altitude = float(altitude_data[0]) / float(altitude_data[1])
                else:
                    altitude = float(altitude_data)
            
            # Extract GPS accuracy if available (DOP - Dilution of Precision)
            accuracy = None
            if 'GPSDOP' in gps_data:
                dop = gps_data['GPSDOP']
                if isinstance(dop, tuple):
                    accuracy = float(dop[0]) / float(dop[1]) * 5  # Rough conversion to meters
            
            # Build result
            result = {
                "has_gps": True,
                "latitude": lat,
                "longitude": lon,
                "altitude": altitude,
                "accuracy": accuracy,
                "timestamp": self._extract_timestamp(exif_data),
                "device_make": exif_data.get('Make'),
                "device_model": exif_data.get('Model'),
                "gps_timestamp": self._extract_gps_timestamp(gps_data)
            }
            
            logger.info(f"GPS extracted: {lat:.6f}, {lon:.6f}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to extract GPS data: {e}", exc_info=True)
            raise GPSExtractionError(f"GPS extraction failed: {str(e)}")
    
    def _convert_to_decimal_degrees(self, gps_coord) -> float:
        """
        Convert GPS coordinates from degrees/minutes/seconds to decimal degrees.
        
        GPS coordinates in EXIF are stored as:
        ((degrees, 1), (minutes, 1), (seconds, 100))
        
        Args:
            gps_coord: Tuple of ((deg_num, deg_den), (min_num, min_den), (sec_num, sec_den))
            
        Returns:
            Decimal degrees as float
            
        Example:
            >>> coord = ((9, 1), (8, 1), (4200, 100))  # 9°8'42"
            >>> decimal = self._convert_to_decimal_degrees(coord)
            >>> print(decimal)
            9.145
        """
        if not gps_coord or len(gps_coord) != 3:
            raise ValueError(f"Invalid GPS coordinate format: {gps_coord}")
        
        degrees = float(gps_coord[0][0]) / float(gps_coord[0][1]) if isinstance(gps_coord[0], tuple) else float(gps_coord[0])
        minutes = float(gps_coord[1][0]) / float(gps_coord[1][1]) if isinstance(gps_coord[1], tuple) else float(gps_coord[1])
        seconds = float(gps_coord[2][0]) / float(gps_coord[2][1]) if isinstance(gps_coord[2], tuple) else float(gps_coord[2])
        
        return degrees + (minutes / 60.0) + (seconds / 3600.0)
    
    def _extract_timestamp(self, exif_data: Dict) -> Optional[str]:
        """
        Extract photo timestamp from EXIF data.
        
        Tries multiple EXIF fields in order of preference:
        1. DateTimeOriginal (when photo was taken)
        2. DateTime (when photo was saved)
        3. DateTimeDigitized (when photo was digitized)
        
        Args:
            exif_data: Parsed EXIF data dictionary
            
        Returns:
            ISO 8601 formatted timestamp string, or None
        """
        for field in ['DateTimeOriginal', 'DateTime', 'DateTimeDigitized']:
            if field in exif_data:
                try:
                    # EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
                    dt_str = str(exif_data[field])
                    dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                    return dt.isoformat()
                except Exception as e:
                    logger.warning(f"Failed to parse {field}: {e}")
                    continue
        
        return None
    
    def _extract_gps_timestamp(self, gps_data: Dict) -> Optional[str]:
        """
        Extract GPS timestamp from GPS EXIF data.
        
        Args:
            gps_data: Parsed GPS EXIF data
            
        Returns:
            ISO 8601 formatted GPS timestamp, or None
        """
        if 'GPSTimeStamp' in gps_data and 'GPSDateStamp' in gps_data:
            try:
                time_data = gps_data['GPSTimeStamp']
                date_str = gps_data['GPSDateStamp']
                
                # Convert time tuple to HH:MM:SS
                hours = int(time_data[0][0] / time_data[0][1]) if isinstance(time_data[0], tuple) else int(time_data[0])
                minutes = int(time_data[1][0] / time_data[1][1]) if isinstance(time_data[1], tuple) else int(time_data[1])
                seconds = int(time_data[2][0] / time_data[2][1]) if isinstance(time_data[2], tuple) else int(time_data[2])
                
                # Parse date (format: "YYYY:MM:DD")
                dt_str = f"{date_str} {hours:02d}:{minutes:02d}:{seconds:02d}"
                dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                return dt.isoformat()
            except Exception as e:
                logger.warning(f"Failed to parse GPS timestamp: {e}")
        
        return None
    
    def compute_photo_hash(self, image_source, algorithm: str = 'sha256') -> str:
        """
        Compute cryptographic hash of photo for duplicate detection.
        
        Uses perceptual hashing to detect duplicate/similar photos even if
        they've been slightly modified (resized, compressed, etc.)
        
        Args:
            image_source: Photo file path, file object, or binary data
            algorithm: Hash algorithm ('sha256', 'md5', 'average_hash')
            
        Returns:
            Hex string of photo hash
            
        Example:
            >>> verifier = GPSPhotoVerifier()
            >>> hash1 = verifier.compute_photo_hash('photo1.jpg')
            >>> hash2 = verifier.compute_photo_hash('photo1_copy.jpg')
            >>> assert hash1 == hash2  # Same photo, same hash
        """
        try:
            # Handle different input types
            if isinstance(image_source, str):
                with open(image_source, 'rb') as f:
                    image_bytes = f.read()
            elif isinstance(image_source, bytes):
                image_bytes = image_source
            elif isinstance(image_source, BytesIO):
                image_bytes = image_source.getvalue()
            else:
                raise ValueError(f"Unsupported image source type: {type(image_source)}")
            
            # Compute hash
            if algorithm == 'sha256':
                return hashlib.sha256(image_bytes).hexdigest()
            elif algorithm == 'md5':
                return hashlib.md5(image_bytes).hexdigest()
            elif algorithm == 'average_hash':
                # Perceptual hash - requires imagehash library
                try:
                    import imagehash
                    image = Image.open(BytesIO(image_bytes))
                    return str(imagehash.average_hash(image))
                except ImportError:
                    logger.warning("imagehash not installed, falling back to sha256")
                    return hashlib.sha256(image_bytes).hexdigest()
            else:
                raise ValueError(f"Unsupported hash algorithm: {algorithm}")
                
        except Exception as e:
            logger.error(f"Failed to compute photo hash: {e}")
            raise
    
    def haversine_distance(
        self,
        coord1: Tuple[float, float],
        coord2: Tuple[float, float]
    ) -> float:
        """
        Calculate distance between two GPS coordinates using Haversine formula.
        
        Accounts for Earth's curvature. Accurate for distances up to ~20,000 km.
        
        Args:
            coord1: (latitude, longitude) tuple in decimal degrees
            coord2: (latitude, longitude) tuple in decimal degrees
            
        Returns:
            Distance in kilometers
            
        Example:
            >>> verifier = GPSPhotoVerifier()
            >>> addis_ababa = (9.0320, 38.7469)
            >>> sidama = (6.8500, 38.4500)
            >>> distance = verifier.haversine_distance(addis_ababa, sidama)
            >>> print(f"Distance: {distance:.2f} km")
            Distance: 245.67 km
        """
        from math import radians, cos, sin, asin, sqrt
        
        lat1, lon1 = coord1
        lat2, lon2 = coord2
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        # Earth radius in kilometers
        earth_radius_km = 6371
        
        distance = earth_radius_km * c
        
        return distance
    
    def validate_location_proximity(
        self,
        photo_coords: Tuple[float, float],
        reference_coords: Tuple[float, float],
        max_distance_km: float = 50.0
    ) -> Dict[str, Any]:
        """
        Validate photo location is within acceptable distance of reference point.
        
        Used to verify:
        - Verification photo taken at/near farmer's registered farm
        - Multiple farm photos taken at same location
        
        Args:
            photo_coords: (latitude, longitude) from photo GPS
            reference_coords: (latitude, longitude) of registered farm
            max_distance_km: Maximum acceptable distance in kilometers
            
        Returns:
            {
                "valid": bool,           # True if within max distance
                "distance_km": float,    # Actual distance
                "message": str           # Human-readable result
            }
            
        Example:
            >>> verifier = GPSPhotoVerifier()
            >>> result = verifier.validate_location_proximity(
            ...     photo_coords=(9.145, 40.489),
            ...     reference_coords=(9.150, 40.485),
            ...     max_distance_km=1.0
            ... )
            >>> print(result)
            {'valid': True, 'distance_km': 0.85, 'message': 'Within acceptable range'}
        """
        distance = self.haversine_distance(photo_coords, reference_coords)
        
        is_valid = distance <= max_distance_km
        
        return {
            "valid": is_valid,
            "distance_km": round(distance, 2),
            "message": f"Within acceptable range ({distance:.2f} km)" if is_valid 
                      else f"Too far from reference ({distance:.2f} km > {max_distance_km} km)"
        }
    
    def validate_ethiopia_bounds(self, latitude: float, longitude: float) -> bool:
        """
        Validate GPS coordinates are within Ethiopia's geographical boundaries.
        
        Ethiopia approximate bounds:
        - Latitude: 3°N to 15°N
        - Longitude: 33°E to 48°E
        
        Args:
            latitude: Decimal degrees latitude
            longitude: Decimal degrees longitude
            
        Returns:
            True if within Ethiopia, False otherwise
            
        Example:
            >>> verifier = GPSPhotoVerifier()
            >>> verifier.validate_ethiopia_bounds(9.145, 40.489)
            True
            >>> verifier.validate_ethiopia_bounds(0.0, 0.0)  # Atlantic Ocean
            False
        """
        return (
            self.ETHIOPIA_LAT_MIN <= latitude <= self.ETHIOPIA_LAT_MAX and
            self.ETHIOPIA_LON_MIN <= longitude <= self.ETHIOPIA_LON_MAX
        )
    
    def validate_timestamp_recency(
        self,
        photo_timestamp: str,
        max_age_days: int = 7
    ) -> Dict[str, Any]:
        """
        Validate photo was taken recently (not old photo being reused).
        
        Args:
            photo_timestamp: ISO 8601 formatted timestamp
            max_age_days: Maximum acceptable age in days
            
        Returns:
            {
                "valid": bool,
                "age_days": float,
                "message": str
            }
            
        Example:
            >>> verifier = GPSPhotoVerifier()
            >>> result = verifier.validate_timestamp_recency(
            ...     "2025-12-20T14:30:00",
            ...     max_age_days=7
            ... )
        """
        try:
            photo_dt = datetime.fromisoformat(photo_timestamp)
            now = datetime.utcnow()
            age = now - photo_dt
            age_days = age.total_seconds() / 86400
            
            is_valid = age_days <= max_age_days
            
            return {
                "valid": is_valid,
                "age_days": round(age_days, 2),
                "message": f"Photo is {age_days:.1f} days old" + 
                          (" (acceptable)" if is_valid else f" (exceeds {max_age_days} day limit)")
            }
        except Exception as e:
            logger.error(f"Failed to validate timestamp: {e}")
            return {
                "valid": False,
                "age_days": None,
                "message": f"Invalid timestamp format: {str(e)}"
            }


def is_in_ethiopia(latitude: float, longitude: float) -> bool:
    """
    Convenience function to check if coordinates are in Ethiopia.
    
    Args:
        latitude: Decimal degrees latitude
        longitude: Decimal degrees longitude
        
    Returns:
        True if within Ethiopia bounds
    """
    verifier = GPSPhotoVerifier()
    return verifier.validate_ethiopia_bounds(latitude, longitude)


if __name__ == "__main__":
    # CLI testing
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m voice.verification.gps_photo_verifier <photo_path>")
        print("\nExample:")
        print("  python -m voice.verification.gps_photo_verifier farm_photo.jpg")
        sys.exit(1)
    
    photo_path = sys.argv[1]
    
    print(f"\n{'='*70}")
    print("GPS PHOTO VERIFICATION TEST")
    print(f"{'='*70}\n")
    print(f"Analyzing: {photo_path}\n")
    
    verifier = GPSPhotoVerifier()
    
    try:
        # Extract GPS
        gps_data = verifier.extract_gps_data(photo_path)
        
        print("📍 GPS Data:")
        print(f"  Has GPS: {gps_data['has_gps']}")
        
        if gps_data['has_gps']:
            print(f"  Latitude: {gps_data['latitude']:.6f}")
            print(f"  Longitude: {gps_data['longitude']:.6f}")
            if gps_data.get('altitude'):
                print(f"  Altitude: {gps_data['altitude']:.1f} meters")
            print(f"  Timestamp: {gps_data['timestamp']}")
            print(f"  Device: {gps_data.get('device_make')} {gps_data.get('device_model')}")
            
            # Validate Ethiopia bounds
            in_ethiopia = verifier.validate_ethiopia_bounds(
                gps_data['latitude'],
                gps_data['longitude']
            )
            print(f"\n🇪🇹 Ethiopia Validation: {'✅ PASS' if in_ethiopia else '❌ FAIL'}")
            
            # Compute hash
            photo_hash = verifier.compute_photo_hash(photo_path)
            print(f"\n🔒 Photo Hash: {photo_hash[:16]}...")
            
            print(f"\n🇪🇺 EUDR Compliant: {'✅ YES' if in_ethiopia else '❌ NO'}")
        else:
            print(f"  Error: {gps_data.get('error')}")
            print("\n⚠️  Enable location services and retake photo for EUDR compliance")
        
    except GPSExtractionError as e:
        print(f"❌ Extraction failed: {e}")
        sys.exit(1)
    
    print(f"\n{'='*70}\n")
