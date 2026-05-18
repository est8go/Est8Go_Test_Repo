"""
EST8GO DEMO LISTINGS SEEDER
=============================
Creates 25 realistic Nigerian property listings across:
    - Abuja (Maitama, Asokoro, Gwarinpa, Jabi, Katampe, Wuse 2,
             Garki, Lifecamp, Lugbe, Galadimawa, Kubwa, Apo,
             Gwagwalada)
    - Lagos (Lekki, Victoria Island, Ikoyi, Ajah, Magodo,
             Gbagada, Surulere)
    - Multiple property types: land, house, apartment
    - Trust grades: emerald, gold, silver, bronze
    - 2 images per listing (Unsplash free images)
    - GPS coordinates for every listing
    - Documents uploaded flags set realistically

Run from backend folder:
    python seed_demo_listings.py
"""

from app.models_registry import register_all_models
from app.database.db import get_db
from app.listings.models import Listing, ListingImage
from datetime import datetime, timedelta
from datetime import datetime, timezone

register_all_models()

db = next(get_db())

# ================================================================
# FREE PROPERTY IMAGE URLS (Unsplash — royalty free)
# ================================================================

IMG = {
    "land": [
        "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=800&q=80",
        "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800&q=80",
        "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800&q=80",
        "https://images.unsplash.com/photo-1473448912268-2022ce9509d8?w=800&q=80",
        "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=800&q=80",
        "https://images.unsplash.com/photo-1501854140801-50d01698950b?w=800&q=80",
    ],
    "house": [
        "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800&q=80",
        "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=800&q=80",
        "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?w=800&q=80",
        "https://images.unsplash.com/photo-1523217582562-09d0def993a6?w=800&q=80",
        "https://images.unsplash.com/photo-1531971589569-0d9370cbe1e5?w=800&q=80",
        "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800&q=80",
        "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=800&q=80",
        "https://images.unsplash.com/photo-1549517045-bc93de075e53?w=800&q=80",
    ],
    "apartment": [
        "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=800&q=80",
        "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&q=80",
        "https://images.unsplash.com/photo-1484154218962-a197022b5858?w=800&q=80",
        "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=800&q=80",
        "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800&q=80",
        "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800&q=80",
        "https://images.unsplash.com/photo-1536376072261-38c75010e6c9?w=800&q=80",
        "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&q=80",
    ],
}

# ================================================================
# LISTINGS DATA
# ================================================================

LISTINGS = [
    # ══════════════════════════════════════════════
    # ABUJA — EMERALD GRADE
    # ══════════════════════════════════════════════
    {
        "tenant_id": 1,
        "title": "Premium Residential Land — Maitama District",
        "location": "maitama",
        "description": "Fully documented 600sqm residential land in the heart of Maitama. C of O and survey plan available. Ideal for luxury villa development. Serene environment with excellent road network.",
        "price": 45_000_000,
        "property_type": "land",
        "status": "verified",
        "latitude": 9.0770,
        "longitude": 7.5023,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=5),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=55),
        "trust_score": 88,
        "trust_grade": "emerald",
        "ai_verified_real": True,
        "cof_uploaded": True,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": True,
        "witness_count": 3,
        "nearest_landmark": "Maitama District Hospital",
        "images": [IMG["land"][0], IMG["land"][1]],
    },
    {
        "tenant_id": 1,
        "title": "4 Bedroom Detached Duplex — Asokoro",
        "location": "asokoro",
        "description": "Exquisite 4-bedroom duplex in Asokoro diplomatic zone. BQ, swimming pool, 2-car garage, 24hr power. C of O. Perfect for executives and diplomats.",
        "price": 180_000_000,
        "property_type": "house",
        "status": "verified",
        "latitude": 9.0358,
        "longitude": 7.5186,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=10),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=50),
        "trust_score": 92,
        "trust_grade": "emerald",
        "ai_verified_real": True,
        "cof_uploaded": True,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": True,
        "witness_count": 5,
        "nearest_landmark": "Asokoro District Hospital",
        "images": [IMG["house"][0], IMG["house"][2]],
    },
    {
        "tenant_id": 1,
        "title": "3 Bedroom Apartment — Jabi Lake View",
        "location": "jabi",
        "description": "Luxury 3-bedroom apartment with breathtaking Jabi Lake views. Fitted kitchen, Italian tiles, 24hr power, professional security.",
        "price": 55_000_000,
        "property_type": "apartment",
        "status": "verified",
        "latitude": 9.0650,
        "longitude": 7.4380,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=3),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=57),
        "trust_score": 86,
        "trust_grade": "emerald",
        "ai_verified_real": True,
        "cof_uploaded": True,
        "survey_uploaded": True,
        "deed_uploaded": False,
        "gps_location_match": True,
        "gps_photo_match": True,
        "witness_count": 2,
        "nearest_landmark": "Jabi Lake Mall",
        "images": [IMG["apartment"][0], IMG["apartment"][5]],
    },
    {
        "tenant_id": 1,
        "title": "5 Bedroom Mansion — Katampe Extension",
        "location": "katampe",
        "description": "Ultra-luxury 5-bedroom mansion on 1200sqm. Smart home technology, cinema room, gym, infinity pool. C of O. The pinnacle of Abuja luxury living.",
        "price": 450_000_000,
        "property_type": "house",
        "status": "verified",
        "latitude": 9.0850,
        "longitude": 7.4300,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=7),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=53),
        "trust_score": 94,
        "trust_grade": "emerald",
        "ai_verified_real": True,
        "cof_uploaded": True,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": True,
        "witness_count": 4,
        "nearest_landmark": "Katampe Extension Junction",
        "images": [IMG["house"][6], IMG["house"][3]],
    },
    # ══════════════════════════════════════════════
    # ABUJA — GOLD GRADE
    # ══════════════════════════════════════════════
    {
        "tenant_id": 1,
        "title": "Residential Land — Gwarinpa First Avenue",
        "location": "gwarinpa",
        "description": "600sqm residential plot on First Avenue, Gwarinpa Estate. Gazette available. Excellent road infrastructure and neighbourhood.",
        "price": 28_000_000,
        "property_type": "land",
        "status": "verified",
        "latitude": 9.1098,
        "longitude": 7.4042,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=15),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=45),
        "trust_score": 77,
        "trust_grade": "gold",
        "ai_verified_real": True,
        "cof_uploaded": False,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": False,
        "witness_count": 2,
        "nearest_landmark": "Gwarinpa Shopping Mall",
        "images": [IMG["land"][2], IMG["land"][4]],
    },
    {
        "tenant_id": 1,
        "title": "2 Bedroom Flat — Wuse 2 Business District",
        "location": "wuse 2",
        "description": "Tastefully finished 2-bedroom flat in the commercial heart of Wuse 2. All tiles, POP ceiling, fitted kitchen. Perfect for professionals.",
        "price": 35_000_000,
        "property_type": "apartment",
        "status": "verified",
        "latitude": 9.0580,
        "longitude": 7.4892,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=20),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=40),
        "trust_score": 73,
        "trust_grade": "gold",
        "ai_verified_real": True,
        "cof_uploaded": True,
        "survey_uploaded": False,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": False,
        "witness_count": 1,
        "nearest_landmark": "Wuse Market",
        "images": [IMG["apartment"][2], IMG["apartment"][6]],
    },
    {
        "tenant_id": 1,
        "title": "Commercial Land — Garki Area 11",
        "location": "garki",
        "description": "Prime 900sqm commercial plot on Airport Road, Garki. Approved layout. Perfect for plaza, hotel, or office complex.",
        "price": 120_000_000,
        "property_type": "land",
        "status": "verified",
        "latitude": 9.0411,
        "longitude": 7.4769,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=2),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=58),
        "trust_score": 80,
        "trust_grade": "gold",
        "ai_verified_real": True,
        "cof_uploaded": True,
        "survey_uploaded": True,
        "deed_uploaded": False,
        "gps_location_match": True,
        "gps_photo_match": True,
        "witness_count": 0,
        "nearest_landmark": "Garki International Market",
        "images": [IMG["land"][0], IMG["land"][5]],
    },
    {
        "tenant_id": 1,
        "title": "3 Bedroom Terrace Duplex — Lifecamp",
        "location": "lifecamp",
        "description": "Well-finished 3-bedroom terrace duplex in Lifecamp. Perimeter fence, paved driveway, generator house. Good for family.",
        "price": 42_000_000,
        "property_type": "house",
        "status": "verified",
        "latitude": 9.0912,
        "longitude": 7.4167,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=8),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=52),
        "trust_score": 69,
        "trust_grade": "gold",
        "ai_verified_real": True,
        "cof_uploaded": False,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": False,
        "witness_count": 1,
        "nearest_landmark": "Lifecamp Shopping Centre",
        "images": [IMG["house"][4], IMG["house"][7]],
    },
    {
        "tenant_id": 1,
        "title": "3 Bedroom Semi-Detached — Apo Resettlement",
        "location": "apo",
        "description": "Neat 3-bedroom semi-detached in Apo Resettlement. Tiled throughout, security post, prepaid meter.",
        "price": 38_000_000,
        "property_type": "house",
        "status": "verified",
        "latitude": 8.9967,
        "longitude": 7.5233,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=14),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=46),
        "trust_score": 71,
        "trust_grade": "gold",
        "ai_verified_real": True,
        "cof_uploaded": False,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": False,
        "witness_count": 2,
        "nearest_landmark": "Apo Legislative Quarters",
        "images": [IMG["house"][1], IMG["house"][5]],
    },
    # ══════════════════════════════════════════════
    # ABUJA — SILVER GRADE
    # ══════════════════════════════════════════════
    {
        "tenant_id": 1,
        "title": "Residential Land — Lugbe Federal Housing",
        "location": "lugbe",
        "description": "450sqm plot in Lugbe Federal Housing Estate. R of O available. Serene neighbourhood, close to airport.",
        "price": 15_000_000,
        "property_type": "land",
        "status": "verified",
        "latitude": 8.9856,
        "longitude": 7.3928,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=30),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=30),
        "trust_score": 58,
        "trust_grade": "silver",
        "ai_verified_real": True,
        "cof_uploaded": False,
        "survey_uploaded": True,
        "deed_uploaded": False,
        "gps_location_match": True,
        "gps_photo_match": False,
        "witness_count": 0,
        "nearest_landmark": "Lugbe Market",
        "images": [IMG["land"][1], IMG["land"][3]],
    },
    {
        "tenant_id": 1,
        "title": "1 Bedroom Studio Apartment — Galadimawa",
        "location": "galadimawa",
        "description": "Modern self-contained studio apartment. Ideal for young professionals. 24hr power, water, security.",
        "price": 12_000_000,
        "property_type": "apartment",
        "status": "verified",
        "latitude": 9.0121,
        "longitude": 7.4456,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=12),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=48),
        "trust_score": 62,
        "trust_grade": "silver",
        "ai_verified_real": False,
        "cof_uploaded": False,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": False,
        "witness_count": 1,
        "nearest_landmark": "Galadimawa Roundabout",
        "images": [IMG["apartment"][4], IMG["apartment"][7]],
    },
    {
        "tenant_id": 1,
        "title": "Residential Land — Kubwa Phase 4",
        "location": "kubwa",
        "description": "800sqm plot in Kubwa Phase 4. Gazette available. Close to NNPC station and Federal Housing.",
        "price": 18_000_000,
        "property_type": "land",
        "status": "verified",
        "latitude": 9.1367,
        "longitude": 7.3517,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=25),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=35),
        "trust_score": 55,
        "trust_grade": "silver",
        "ai_verified_real": False,
        "cof_uploaded": False,
        "survey_uploaded": True,
        "deed_uploaded": False,
        "gps_location_match": True,
        "gps_photo_match": False,
        "witness_count": 0,
        "nearest_landmark": "Kubwa General Hospital",
        "images": [IMG["land"][3], IMG["land"][5]],
    },
    {
        "tenant_id": 1,
        "title": "Mixed-Use Land — Gwagwalada Town Centre",
        "location": "gwagwalada",
        "description": "Strategic mixed-use land in Gwagwalada Town Centre. Approved layout. Suitable for commercial or residential development.",
        "price": 8_500_000,
        "property_type": "land",
        "status": "verified",
        "latitude": 8.9408,
        "longitude": 7.0833,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=3),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=57),
        "trust_score": 63,
        "trust_grade": "silver",
        "ai_verified_real": True,
        "cof_uploaded": False,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": False,
        "witness_count": 0,
        "nearest_landmark": "Gwagwalada Area Council Secretariat",
        "images": [IMG["land"][2], IMG["land"][4]],
    },
    # ══════════════════════════════════════════════
    # LAGOS — EMERALD GRADE
    # ══════════════════════════════════════════════
    {
        "tenant_id": 1,
        "title": "4 Bedroom Detached House — Lekki Phase 1",
        "location": "lekki",
        "description": "Spacious 4-bedroom fully detached house in Lekki Phase 1. Boys quarters, swimming pool, 2-car garage. C of O. Prime residential area.",
        "price": 280_000_000,
        "property_type": "house",
        "status": "verified",
        "latitude": 6.4350,
        "longitude": 3.4510,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=4),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=56),
        "trust_score": 90,
        "trust_grade": "emerald",
        "ai_verified_real": True,
        "cof_uploaded": True,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": True,
        "witness_count": 4,
        "nearest_landmark": "Lekki Phase 1 Toll Gate",
        "images": [IMG["house"][0], IMG["house"][6]],
    },
    {
        "tenant_id": 1,
        "title": "Commercial Land — Victoria Island Extension",
        "location": "victoria island",
        "description": "Rare 600sqm commercial/residential land on Victoria Island Extension. Governor's Consent. Surrounded by embassies and corporate headquarters.",
        "price": 350_000_000,
        "property_type": "land",
        "status": "verified",
        "latitude": 6.4281,
        "longitude": 3.4219,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=1),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=59),
        "trust_score": 96,
        "trust_grade": "emerald",
        "ai_verified_real": True,
        "cof_uploaded": True,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": True,
        "witness_count": 6,
        "nearest_landmark": "Bar Beach",
        "images": [IMG["land"][0], IMG["land"][5]],
    },
    {
        "tenant_id": 1,
        "title": "3 Bedroom Penthouse — Ikoyi",
        "location": "ikoyi",
        "description": "Premium 3-bedroom penthouse apartment in Old Ikoyi. Rooftop terrace, swimming pool, gym, concierge service. C of O.",
        "price": 95_000_000,
        "property_type": "apartment",
        "status": "verified",
        "latitude": 6.4550,
        "longitude": 3.4350,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=6),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=54),
        "trust_score": 88,
        "trust_grade": "emerald",
        "ai_verified_real": True,
        "cof_uploaded": True,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": True,
        "witness_count": 3,
        "nearest_landmark": "Ikoyi Club 1938",
        "images": [IMG["apartment"][1], IMG["apartment"][5]],
    },
    # ══════════════════════════════════════════════
    # LAGOS — GOLD GRADE
    # ══════════════════════════════════════════════
    {
        "tenant_id": 1,
        "title": "5 Bedroom Detached — Magodo GRA Phase 2",
        "location": "magodo",
        "description": "Executive 5-bedroom detached house in Magodo GRA Phase 2. Fully tiled, large compound, BQ, generator. C of O.",
        "price": 220_000_000,
        "property_type": "house",
        "status": "verified",
        "latitude": 6.6167,
        "longitude": 3.3833,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=9),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=51),
        "trust_score": 82,
        "trust_grade": "gold",
        "ai_verified_real": True,
        "cof_uploaded": True,
        "survey_uploaded": True,
        "deed_uploaded": False,
        "gps_location_match": True,
        "gps_photo_match": True,
        "witness_count": 2,
        "nearest_landmark": "Magodo Phase 2 Gate",
        "images": [IMG["house"][2], IMG["house"][7]],
    },
    {
        "tenant_id": 1,
        "title": "4 Bedroom Fully Detached — Gbagada Phase 2",
        "location": "gbagada",
        "description": "4-bedroom fully detached in Gbagada Phase 2. C of O. 24hr electricity, borehole, perimeter fence.",
        "price": 145_000_000,
        "property_type": "house",
        "status": "verified",
        "latitude": 6.5500,
        "longitude": 3.3833,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=11),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=49),
        "trust_score": 84,
        "trust_grade": "gold",
        "ai_verified_real": True,
        "cof_uploaded": True,
        "survey_uploaded": True,
        "deed_uploaded": False,
        "gps_location_match": True,
        "gps_photo_match": True,
        "witness_count": 3,
        "nearest_landmark": "Gbagada General Hospital",
        "images": [IMG["house"][3], IMG["house"][5]],
    },
    # ══════════════════════════════════════════════
    # LAGOS — SILVER GRADE
    # ══════════════════════════════════════════════
    {
        "tenant_id": 1,
        "title": "2 Bedroom Apartment — Ajah Gated Estate",
        "location": "ajah",
        "description": "Modern 2-bedroom apartment in a secured gated estate. Good road access, close to Shoprite Sangotedo.",
        "price": 25_000_000,
        "property_type": "apartment",
        "status": "verified",
        "latitude": 6.4674,
        "longitude": 3.5759,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=18),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=42),
        "trust_score": 65,
        "trust_grade": "silver",
        "ai_verified_real": True,
        "cof_uploaded": False,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": False,
        "witness_count": 1,
        "nearest_landmark": "Shoprite Sangotedo",
        "images": [IMG["apartment"][3], IMG["apartment"][6]],
    },
    {
        "tenant_id": 1,
        "title": "2 Bedroom Apartment — Surulere",
        "location": "surulere",
        "description": "Clean 2-bedroom apartment off Bode Thomas Street. Tiled throughout, fitted kitchen, water heater. Safe neighbourhood.",
        "price": 22_000_000,
        "property_type": "apartment",
        "status": "verified",
        "latitude": 6.4969,
        "longitude": 3.3515,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=22),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=38),
        "trust_score": 60,
        "trust_grade": "silver",
        "ai_verified_real": True,
        "cof_uploaded": False,
        "survey_uploaded": False,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": False,
        "witness_count": 1,
        "nearest_landmark": "National Stadium Surulere",
        "images": [IMG["apartment"][0], IMG["apartment"][7]],
    },
    {
        "tenant_id": 1,
        "title": "3 Bedroom Apartment — Ikeja GRA",
        "location": "ikeja",
        "description": "Spacious 3-bedroom apartment in Ikeja GRA. Ground floor unit. Large living room, adequate parking.",
        "price": 48_000_000,
        "property_type": "apartment",
        "status": "verified",
        "latitude": 6.6018,
        "longitude": 3.3515,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=16),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=44),
        "trust_score": 67,
        "trust_grade": "silver",
        "ai_verified_real": True,
        "cof_uploaded": False,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": False,
        "witness_count": 0,
        "nearest_landmark": "Computer Village Ikeja",
        "images": [IMG["apartment"][2], IMG["apartment"][4]],
    },
    # ══════════════════════════════════════════════
    # BONUS — HIGH VALUE LISTINGS
    # ══════════════════════════════════════════════
    {
        "tenant_id": 1,
        "title": "Waterfront Land — Lekki Phase 2",
        "location": "lekki",
        "description": "Rare 1200sqm waterfront land in Lekki Phase 2. Excision document. Direct water frontage. Ideal for boutique hotel or luxury estate.",
        "price": 500_000_000,
        "property_type": "land",
        "status": "verified",
        "latitude": 6.4500,
        "longitude": 3.5200,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=2),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=58),
        "trust_score": 91,
        "trust_grade": "emerald",
        "ai_verified_real": True,
        "cof_uploaded": True,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": True,
        "witness_count": 5,
        "nearest_landmark": "Lekki-Epe Expressway",
        "images": [IMG["land"][4], IMG["land"][0]],
    },
    {
        "tenant_id": 1,
        "title": "6 Bedroom Smart Home — Maitama II",
        "location": "maitama",
        "description": "Bespoke 6-bedroom smart home in Maitama II. Full home automation, solar power, electric car charging. C of O. Built to international standards.",
        "price": 850_000_000,
        "property_type": "house",
        "status": "verified",
        "latitude": 9.0820,
        "longitude": 7.5100,
        "gps_verified_at": datetime.now(timezone.utc) - timedelta(days=1),
        "gps_expires_at": datetime.now(timezone.utc) + timedelta(days=59),
        "trust_score": 97,
        "trust_grade": "emerald",
        "ai_verified_real": True,
        "cof_uploaded": True,
        "survey_uploaded": True,
        "deed_uploaded": True,
        "gps_location_match": True,
        "gps_photo_match": True,
        "witness_count": 7,
        "nearest_landmark": "Maitama II Toll",
        "images": [IMG["house"][6], IMG["house"][2]],
    },
]


# ================================================================
# SEED FUNCTION
# ================================================================


def seed():
    print("\n🚀 EST8GO DEMO LISTINGS SEEDER STARTING...\n")
    created = 0
    skipped = 0
    errors = 0

    for data in LISTINGS:
        try:
            # Check if listing already exists
            existing = (
                db.query(Listing)
                .filter(
                    Listing.title == data["title"],
                    Listing.tenant_id == data["tenant_id"],
                )
                .first()
            )

            if existing:
                print(f"⏭️  Exists: {data['title'][:55]}")
                skipped += 1
                continue

            # Extract images before creating listing
            image_urls = data.pop("images", [])

            # Create listing
            listing = Listing(**data)
            db.add(listing)
            db.flush()  # Get ID without full commit

            # Add images
            for i, url in enumerate(image_urls):
                img = ListingImage(
                    listing_id=listing.id,
                    url=url,
                    is_main=(i == 0),
                )
                db.add(img)

            db.commit()
            created += 1
            print(
                f"✅ {listing.title[:50]:<52} "
                f"₦{listing.price:>15,}  "
                f"{listing.trust_grade.upper():<8} "
                f"({listing.trust_score})"
            )

        except Exception as e:
            db.rollback()
            errors += 1
            print(f"❌ Error on '{data.get('title','?')[:40]}': {e}")

    print(f"\n{'='*65}")
    print(f"  ✅ Created : {created} listings")
    print(f"  ⏭️  Skipped : {skipped} already exist")
    print(f"  ❌ Errors  : {errors}")
    print(f"  📊 Total   : {created + skipped} listings in vault")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    seed()
