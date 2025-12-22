"""
Test GPS Photo Verification Flow

Creates a test photo with GPS EXIF data and tests the entire verification pipeline.
"""

import sys
import os
from io import BytesIO
from PIL import Image
import piexif
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice.verification.gps_photo_verifier import GPSPhotoVerifier


def create_test_photo_with_gps(latitude=9.0320, longitude=38.7469, output_path='test_farm_photo.jpg'):
    """
    Create a test photo with GPS EXIF data.
    
    Args:
        latitude: Latitude in decimal degrees (default: Addis Ababa)
        longitude: Longitude in decimal degrees (default: Addis Ababa)
        output_path: Where to save the photo
    """
    print(f"\n📸 Creating test photo with GPS...")
    print(f"   Location: {latitude:.6f}, {longitude:.6f}")
    
    # Create a simple test image (red square)
    img = Image.new('RGB', (800, 600), color='green')
    
    # Convert decimal degrees to DMS format for EXIF
    def decimal_to_dms(decimal):
        """Convert decimal degrees to (degrees, minutes, seconds) format."""
        degrees = int(abs(decimal))
        minutes_decimal = (abs(decimal) - degrees) * 60
        minutes = int(minutes_decimal)
        seconds = (minutes_decimal - minutes) * 60
        
        # EXIF format: [(degrees, 1), (minutes, 1), (seconds*100, 100)]
        return [
            (degrees, 1),
            (minutes, 1),
            (int(seconds * 100), 100)
        ]
    
    lat_dms = decimal_to_dms(latitude)
    lon_dms = decimal_to_dms(longitude)
    
    # Create EXIF data with GPS
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: b"Apple",
            piexif.ImageIFD.Model: b"iPhone 14 Pro",
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: datetime.now().strftime("%Y:%m:%d %H:%M:%S").encode(),
        },
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: b'N' if latitude >= 0 else b'S',
            piexif.GPSIFD.GPSLatitude: lat_dms,
            piexif.GPSIFD.GPSLongitudeRef: b'E' if longitude >= 0 else b'W',
            piexif.GPSIFD.GPSLongitude: lon_dms,
            piexif.GPSIFD.GPSAltitude: (2355, 1),  # 2355 meters
            piexif.GPSIFD.GPSTimeStamp: [(14, 1), (30, 1), (0, 1)],
            piexif.GPSIFD.GPSDateStamp: datetime.now().strftime("%Y:%m:%d").encode(),
        }
    }
    
    exif_bytes = piexif.dump(exif_dict)
    img.save(output_path, format='JPEG', exif=exif_bytes, quality=85)
    
    print(f"✅ Test photo created: {output_path}")
    return output_path


def test_gps_extraction(photo_path):
    """Test GPS extraction from photo."""
    print(f"\n🔍 Testing GPS Extraction...")
    
    verifier = GPSPhotoVerifier()
    gps_data = verifier.extract_gps_data(photo_path)
    
    if gps_data['has_gps']:
        print(f"✅ GPS extraction successful!")
        print(f"   📍 Latitude: {gps_data['latitude']:.6f}")
        print(f"   📍 Longitude: {gps_data['longitude']:.6f}")
        print(f"   📅 Timestamp: {gps_data['timestamp']}")
        print(f"   📱 Device: {gps_data.get('device_make')} {gps_data.get('device_model')}")
    else:
        print(f"❌ GPS extraction failed: {gps_data.get('error')}")
        return False
    
    return gps_data


def test_ethiopia_bounds(gps_data):
    """Test Ethiopia boundary validation."""
    print(f"\n🗺️  Testing Ethiopia Boundary Validation...")
    
    verifier = GPSPhotoVerifier()
    in_ethiopia = verifier.validate_ethiopia_bounds(
        gps_data['latitude'],
        gps_data['longitude']
    )
    
    if in_ethiopia:
        print(f"✅ Location is within Ethiopia")
    else:
        print(f"❌ Location is outside Ethiopia")
    
    return in_ethiopia


def test_proximity_validation(gps_data, farm_lat=9.0410, farm_lon=38.7469):
    """Test proximity validation against farm location."""
    print(f"\n📏 Testing Proximity Validation...")
    print(f"   Farm location: {farm_lat:.6f}, {farm_lon:.6f}")
    
    verifier = GPSPhotoVerifier()
    result = verifier.validate_location_proximity(
        photo_coords=(gps_data['latitude'], gps_data['longitude']),
        reference_coords=(farm_lat, farm_lon),
        max_distance_km=50.0
    )
    
    if result['valid']:
        print(f"✅ Within acceptable range: {result['distance_km']:.2f} km")
    else:
        print(f"❌ Too far: {result['distance_km']:.2f} km (max 50 km)")
    
    return result


def test_timestamp_recency(gps_data):
    """Test timestamp recency validation."""
    print(f"\n⏰ Testing Timestamp Recency...")
    
    verifier = GPSPhotoVerifier()
    result = verifier.validate_timestamp_recency(
        gps_data['timestamp'],
        max_age_days=30
    )
    
    if result['valid']:
        print(f"✅ Photo is recent: {result['age_days']:.1f} days old")
    else:
        print(f"❌ Photo too old: {result['age_days']:.1f} days (max 30)")
    
    return result


def test_photo_hashing(photo_path):
    """Test photo hash computation."""
    print(f"\n🔐 Testing Photo Hashing...")
    
    verifier = GPSPhotoVerifier()
    
    # Test SHA-256
    sha256_hash = verifier.compute_photo_hash(photo_path, algorithm='sha256')
    print(f"✅ SHA-256: {sha256_hash[:32]}...")
    
    # Test MD5
    md5_hash = verifier.compute_photo_hash(photo_path, algorithm='md5')
    print(f"✅ MD5: {md5_hash}")
    
    # Verify consistency
    sha256_hash2 = verifier.compute_photo_hash(photo_path, algorithm='sha256')
    if sha256_hash == sha256_hash2:
        print(f"✅ Hash consistency verified")
    else:
        print(f"❌ Hash mismatch!")
    
    return sha256_hash


def test_eudr_compliance_workflow():
    """Test complete EUDR compliance workflow."""
    print("\n" + "="*70)
    print("EUDR GPS PHOTO VERIFICATION - COMPLETE WORKFLOW TEST")
    print("="*70)
    
    # Test Case 1: Addis Ababa location (within Ethiopia)
    print("\n📋 TEST CASE 1: Farm in Addis Ababa")
    photo_path = create_test_photo_with_gps(
        latitude=9.0320,
        longitude=38.7469,
        output_path='test_addis_farm.jpg'
    )
    
    gps_data = test_gps_extraction(photo_path)
    if not gps_data:
        return False
    
    ethiopia_valid = test_ethiopia_bounds(gps_data)
    proximity_result = test_proximity_validation(gps_data)
    recency_result = test_timestamp_recency(gps_data)
    photo_hash = test_photo_hashing(photo_path)
    
    # Determine compliance status
    print(f"\n📊 COMPLIANCE ASSESSMENT:")
    if ethiopia_valid and proximity_result['valid'] and recency_result['valid']:
        print(f"✅ Status: FULLY_VERIFIED (Gold)")
        print(f"✅ EUDR Article 9: COMPLIANT")
        print(f"✅ Ready for EU export")
    else:
        print(f"⚠️  Status: REQUIRES ATTENTION")
        if not ethiopia_valid:
            print(f"   ❌ Location outside Ethiopia")
        if not proximity_result['valid']:
            print(f"   ❌ Too far from registered farm")
        if not recency_result['valid']:
            print(f"   ❌ Photo too old")
    
    # Test Case 2: Sidama location (different region)
    print("\n" + "="*70)
    print("\n📋 TEST CASE 2: Farm in Sidama (250km away)")
    photo_path2 = create_test_photo_with_gps(
        latitude=6.8500,
        longitude=38.4500,
        output_path='test_sidama_farm.jpg'
    )
    
    gps_data2 = test_gps_extraction(photo_path2)
    ethiopia_valid2 = test_ethiopia_bounds(gps_data2)
    proximity_result2 = test_proximity_validation(gps_data2, farm_lat=9.0320, farm_lon=38.7469)
    
    print(f"\n📊 COMPLIANCE ASSESSMENT:")
    if proximity_result2['valid']:
        print(f"✅ Within 50km threshold")
    else:
        print(f"❌ Beyond 50km threshold: {proximity_result2['distance_km']:.1f} km")
        print(f"⚠️  Photo appears to be from different farm location")
    
    # Test Case 3: Location outside Ethiopia
    print("\n" + "="*70)
    print("\n📋 TEST CASE 3: Location outside Ethiopia (Nairobi, Kenya)")
    photo_path3 = create_test_photo_with_gps(
        latitude=-1.2921,
        longitude=36.8219,
        output_path='test_kenya_farm.jpg'
    )
    
    gps_data3 = test_gps_extraction(photo_path3)
    ethiopia_valid3 = test_ethiopia_bounds(gps_data3)
    
    print(f"\n📊 COMPLIANCE ASSESSMENT:")
    if not ethiopia_valid3:
        print(f"❌ Status: NON_COMPLIANT")
        print(f"❌ Location outside Ethiopia")
        print(f"❌ Cannot be used for Ethiopian coffee EUDR compliance")
    
    # Cleanup
    print("\n🧹 Cleaning up test files...")
    for path in [photo_path, photo_path2, photo_path3]:
        if os.path.exists(path):
            os.remove(path)
            print(f"   Deleted: {path}")
    
    print("\n" + "="*70)
    print("✅ EUDR GPS VERIFICATION WORKFLOW TEST COMPLETE")
    print("="*70)
    
    return True


if __name__ == "__main__":
    try:
        success = test_eudr_compliance_workflow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
