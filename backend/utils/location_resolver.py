"""
Location alias resolution and smart location matching utilities
"""

from sqlalchemy import or_
from ..models import LocationAlias


def resolve_location_aliases(location_text):
    """Resolve location aliases to canonical names and coordinates"""
    if not location_text:
        return None
        
    # First try exact match
    alias = LocationAlias.query.filter(
        or_(
            LocationAlias.alias_name.ilike(location_text),
            LocationAlias.canonical_name.ilike(location_text)
        )
    ).first()
    
    if alias:
        return {
            'canonical_name': alias.canonical_name,
            'lat': alias.lat,
            'lng': alias.lng,
            'city': alias.city,
            'state': alias.state,
            'popularity': alias.popularity
        }
    
    # If no exact match, try partial matches
    partial_matches = LocationAlias.query.filter(
        or_(
            LocationAlias.alias_name.ilike(f"%{location_text}%"),
            LocationAlias.canonical_name.ilike(f"%{location_text}%")
        )
    ).order_by(LocationAlias.popularity.desc()).limit(3).all()
    
    if partial_matches:
        return {
            'canonical_name': partial_matches[0].canonical_name,
            'lat': partial_matches[0].lat,
            'lng': partial_matches[0].lng,
            'city': partial_matches[0].city,
            'state': partial_matches[0].state,
            'popularity': partial_matches[0].popularity,
            'suggestions': [
                {
                    'name': match.canonical_name,
                    'alias': match.alias_name,
                    'lat': match.lat,
                    'lng': match.lng,
                    'city': match.city,
                    'state': match.state,
                    'popularity': match.popularity
                } for match in partial_matches
            ]
        }
    
    return None


def find_similar_locations(location_text, limit=5):
    """Find similar locations based on text similarity"""
    if not location_text:
        return []
        
    # Use PostgreSQL similarity functions if available
    similar_locations = LocationAlias.query.filter(
        or_(
            LocationAlias.alias_name.ilike(f"%{location_text}%"),
            LocationAlias.canonical_name.ilike(f"%{location_text}%")
        )
    ).order_by(
        LocationAlias.popularity.desc()
    ).limit(limit).all()
    
    return [
        {
            'canonical_name': loc.canonical_name,
            'alias_name': loc.alias_name,
            'lat': loc.lat,
            'lng': loc.lng,
            'city': loc.city,
            'state': loc.state,
            'popularity': loc.popularity
        } for loc in similar_locations
    ]


def normalize_location_name(location_text):
    """Normalize location text for consistent matching"""
    if not location_text:
        return ""
        
    # Basic normalization
    normalized = location_text.strip().title()
    
    # Common abbreviation expansions
    abbreviations = {
        'St': 'Street',
        'Ave': 'Avenue', 
        'Blvd': 'Boulevard',
        'Dr': 'Drive',
        'Rd': 'Road',
        'Univ': 'University',
        'Intl': 'International'
    }
    
    words = normalized.split()
    for i, word in enumerate(words):
        if word in abbreviations:
            words[i] = abbreviations[word]
    
    return ' '.join(words)


def extract_location_keywords(location_text):
    """Extract searchable keywords from location text"""
    if not location_text:
        return []
        
    # Remove common stop words for location search
    stop_words = {'the', 'of', 'at', 'in', 'on', 'near', 'by', 'to', 'from'}
    
    words = location_text.lower().split()
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    
    return keywords