"""Ghorify property matching engine.

A tenant describes what they want (a SearchCriteria, or the search form data).
Every property is then scored against only the preferences the tenant actually
filled in, so leaving a field empty never lowers a score.

    match % = points earned / points possible * 100

Some preferences give partial points (e.g. a flat that is slightly over budget
or has one bedroom less than asked), which makes results feel more natural than
a plain yes/no filter.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Q

WEIGHTS = {
    'budget': 30,
    'location': 20,
    'bedrooms': 15,
    'bathrooms': 10,
    'category': 10,
    'amenities': 10,
    'keyword': 8,
    'property_type': 6,
    'gender': 8,
    'parking': 5,
    'pet_friendly': 5,
    'furnished': 5,
}

SMART_MATCH_THRESHOLD = 50


@dataclass
class MatchResult:
    property: object
    percentage: int
    reasons: list = field(default_factory=list)  # (label, score 0..1)

    @property
    def level(self):
        if self.percentage >= 85:
            return 'excellent'
        if self.percentage >= 65:
            return 'good'
        return 'fair'


class MatchEngine:
    def __init__(self, prefs):
        """`prefs` is a plain dict (from a form or SearchCriteria.as_preferences())."""
        self.prefs = prefs
        self.amenity_ids = {a.pk if hasattr(a, 'pk') else int(a) for a in prefs.get('amenities') or []}

    # ---------------------------------------------------------------- scoring
    def _budget_score(self, prop):
        max_price, min_price = self.prefs.get('max_price'), self.prefs.get('min_price')
        if not max_price and not min_price:
            return None
        cost = prop.monthly_cost if self.prefs.get('budget_includes_bills') else Decimal(prop.price)
        if min_price and cost < min_price:
            return 0.5  # cheaper than expected; may be lower quality, still relevant
        if not max_price or cost <= max_price:
            return 1.0
        over = float(cost) / float(max_price)
        if over <= 1.10:
            return 0.5
        if over <= 1.20:
            return 0.25
        return 0.0

    def _location_score(self, prop):
        wanted = (self.prefs.get('location') or '').strip().lower()
        if not wanted:
            return None
        area = prop.location.lower()
        if wanted == area or wanted in area or area in wanted:
            return 1.0
        return 0.5 if wanted in prop.address.lower() else 0.0

    def _keyword_score(self, prop):
        keyword = (self.prefs.get('keyword') or '').strip().lower()
        if not keyword:
            return None
        haystack = f'{prop.title} {prop.description} {prop.location}'.lower()
        words = keyword.split()
        hits = sum(1 for word in words if word in haystack)
        return hits / len(words)

    def _at_least_score(self, actual, wanted):
        if not wanted:
            return None
        if actual >= wanted:
            return 1.0
        return 0.5 if actual == wanted - 1 else 0.0

    def _exact_score(self, actual, wanted):
        if not wanted:
            return None
        return 1.0 if actual == wanted else 0.0

    def _required_flag_score(self, actual, required):
        if not required:
            return None
        return 1.0 if actual else 0.0

    def _gender_score(self, prop):
        gender = self.prefs.get('tenant_gender')
        if not gender:
            return None
        return 1.0 if prop.accepts_gender(gender) else 0.0

    def _amenities_score(self, prop):
        if not self.amenity_ids:
            return None
        have = {a.pk for a in prop.amenities.all()}
        return len(self.amenity_ids & have) / len(self.amenity_ids)

    def score(self, prop):
        p = self.prefs
        parts = {
            'budget': ('Within budget', self._budget_score(prop)),
            'location': ('Preferred area', self._location_score(prop)),
            'bedrooms': ('Bedrooms', self._at_least_score(prop.bedrooms, p.get('min_bedrooms'))),
            'bathrooms': ('Bathrooms', self._at_least_score(prop.bathrooms, p.get('min_bathrooms'))),
            'category': ('Category', self._exact_score(prop.category, p.get('category'))),
            'property_type': ('Property type', self._exact_score(prop.property_type, p.get('property_type'))),
            'amenities': ('Amenities', self._amenities_score(prop)),
            'keyword': ('Keyword', self._keyword_score(prop)),
            'gender': ('Allowed for you', self._gender_score(prop)),
            'parking': ('Parking', self._required_flag_score(prop.parking, p.get('needs_parking'))),
            'pet_friendly': ('Pet friendly', self._required_flag_score(prop.pet_friendly, p.get('needs_pet_friendly'))),
            'furnished': ('Furnished', self._required_flag_score(prop.furnished, p.get('needs_furnished'))),
        }
        earned = possible = 0.0
        reasons = []
        for key, (label, value) in parts.items():
            if value is None:
                continue
            earned += WEIGHTS[key] * value
            possible += WEIGHTS[key]
            reasons.append((label, value))
        percentage = round(earned / possible * 100) if possible else 100
        return MatchResult(property=prop, percentage=percentage, reasons=reasons)

    # ---------------------------------------------------------------- search
    def strict_filter(self, queryset):
        """Basic search: every filled preference must be satisfied exactly."""
        p = self.prefs
        if p.get('keyword'):
            kw = p['keyword']
            queryset = queryset.filter(Q(title__icontains=kw) | Q(description__icontains=kw) | Q(location__icontains=kw))
        if p.get('location'):
            queryset = queryset.filter(location__icontains=p['location'])
        if p.get('category'):
            queryset = queryset.filter(category=p['category'])
        if p.get('property_type'):
            queryset = queryset.filter(property_type=p['property_type'])
        if p.get('min_price'):
            queryset = queryset.filter(price__gte=p['min_price'])
        if p.get('min_bedrooms'):
            queryset = queryset.filter(bedrooms__gte=p['min_bedrooms'])
        if p.get('min_bathrooms'):
            queryset = queryset.filter(bathrooms__gte=p['min_bathrooms'])
        if p.get('tenant_gender'):
            queryset = queryset.filter(tenant_gender__in=['any', p['tenant_gender']])
        if p.get('needs_parking'):
            queryset = queryset.filter(parking=True)
        if p.get('needs_pet_friendly'):
            queryset = queryset.filter(pet_friendly=True)
        if p.get('needs_furnished'):
            queryset = queryset.filter(furnished=True)
        for amenity_id in self.amenity_ids:
            queryset = queryset.filter(amenities__id=amenity_id)
        queryset = queryset.distinct()

        results = [self.score(prop) for prop in queryset]
        if p.get('max_price'):
            # Budget may include bills, which is a computed value, so filter in Python.
            results = [r for r in results if self._budget_score(r.property) == 1.0]
        return sorted(results, key=lambda r: r.percentage, reverse=True)

    def smart_match(self, queryset, threshold=SMART_MATCH_THRESHOLD):
        """Score every candidate and keep the ones above the threshold."""
        if self.prefs.get('max_price'):
            # Anything more than 20% over budget can never pass, skip it early.
            queryset = queryset.filter(price__lte=int(self.prefs['max_price'] * 1.2))
        if self.prefs.get('tenant_gender'):
            # A male-only flat can never be right for a female tenant (and vice versa).
            queryset = queryset.filter(tenant_gender__in=['any', self.prefs['tenant_gender']])
        results = [self.score(prop) for prop in queryset]
        results = [r for r in results if r.percentage >= threshold]
        return sorted(results, key=lambda r: (r.percentage, r.property.created_at), reverse=True)
