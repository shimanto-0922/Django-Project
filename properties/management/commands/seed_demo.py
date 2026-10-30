"""Fill the database with realistic demo data for presentations.

    python manage.py seed_demo          # add demo data
    python manage.py seed_demo --reset  # wipe demo users first

Every demo account uses the password: ghorify123
Listing photos come from static/img/photos (Unsplash License).
"""
import io
import random
from datetime import time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from accounts.models import LandlordProfile, User
from interactions.models import Comparison, Favourite, RentalRequest, Report, RequestStatus, Review, VisitRequest
from properties.models import Amenity, Property, PropertyImage, Utility
from search.models import SearchCriteria

PASSWORD = 'ghorify123'
PHOTO_DIR = Path(settings.BASE_DIR) / 'static' / 'img' / 'photos'

AMENITIES = [
    ('Lift', 'bi-arrow-down-up'), ('Generator backup', 'bi-lightning-charge'), ('Gas line', 'bi-fire'),
    ('WiFi ready', 'bi-wifi'), ('24/7 security', 'bi-shield-check'), ('CCTV', 'bi-camera-video'),
    ('Rooftop access', 'bi-building-up'), ('Water filter', 'bi-droplet-half'), ('Near school', 'bi-backpack'),
    ('Near hospital', 'bi-hospital'), ('Prayer space', 'bi-moon-stars'), ('Meal service', 'bi-cup-hot'),
]

# Which photos fit which kind of listing (files in static/img/photos).
PHOTO_SETS = {
    'flat': [['building_4', 'living_1', 'kitchen_1', 'bedroom_1'], ['building_1', 'living_4', 'bedroom_2', 'kitchen_1'],
             ['building_3', 'living_6', 'bedroom_1'], ['building_2', 'living_2', 'bedroom_2', 'kitchen_1'],
             ['living_5', 'living_3', 'bedroom_1', 'kitchen_1']],
    'house': [['house_1', 'living_7', 'bedroom_2', 'kitchen_1'], ['house_2', 'living_3', 'bedroom_1'],
              ['house_3', 'living_7', 'living_5', 'bedroom_2'], ['house_4', 'living_6', 'bedroom_1']],
    'room': [['room_1', 'bedroom_2', 'kitchen_1'], ['room_3', 'room_2', 'bedroom_1'], ['bedroom_1', 'room_1', 'living_2']],
    'office': [['office_1', 'building_2', 'living_5'], ['building_3', 'office_1']],
}

# title, division, city, area, type, category, rent, service, beds, baths, balconies, floor, size,
# furnished, pets, parking, gender, negotiable, featured, photo set
LISTINGS = [
    ('Sunny 3-bed family flat near Dhanmondi Lake', 'dhaka', 'Dhaka', 'Dhanmondi', 'apartment', 'family', 35000, 3000, 3, 3, 2, 5, 1450, False, False, True, 'any', False, True, 'flat'),
    ('Furnished 3-bed apartment with lake view', 'dhaka', 'Dhaka', 'Gulshan', 'apartment', 'family', 85000, 8000, 3, 4, 3, 9, 2100, True, True, True, 'any', True, True, 'flat'),
    ('Single room for working bachelor', 'dhaka', 'Dhaka', 'Banani', 'room', 'bachelor', 12000, 1000, 1, 1, 1, 4, 220, True, False, False, 'male', True, False, 'room'),
    ('Spacious duplex with private rooftop', 'dhaka', 'Dhaka', 'Uttara', 'duplex', 'family', 60000, 4000, 4, 4, 3, 6, 2800, False, True, True, 'any', True, True, 'house'),
    ('Affordable 2-bed flat in Mirpur 10', 'dhaka', 'Dhaka', 'Mirpur', 'apartment', 'family', 18000, 1500, 2, 2, 1, 3, 950, False, False, False, 'any', True, False, 'flat'),
    ('Mess seat near Dhaka University', 'dhaka', 'Dhaka', 'Mohammadpur', 'seat', 'hostel', 4500, 300, 1, 1, 0, 2, 120, True, False, False, 'male', False, False, 'room'),
    ('Female hostel seat with meals', 'dhaka', 'Dhaka', 'Farmgate', 'seat', 'hostel', 6500, 0, 1, 1, 1, 5, 140, True, False, False, 'female', False, True, 'room'),
    ('Sublet room in quiet family home', 'dhaka', 'Dhaka', 'Lalmatia', 'room', 'sublet', 9000, 0, 1, 1, 1, 3, 200, True, False, False, 'female', True, False, 'room'),
    ('New 3-bed apartment in Bashundhara R/A', 'dhaka', 'Dhaka', 'Bashundhara', 'apartment', 'family', 32000, 3500, 3, 3, 2, 7, 1550, False, True, True, 'any', False, False, 'flat'),
    ('Shared bachelor flat, 2 rooms available', 'dhaka', 'Dhaka', 'Badda', 'apartment', 'bachelor', 14000, 1000, 2, 2, 1, 5, 900, False, False, False, 'male', True, False, 'flat'),
    ('Office floor on main road, 1800 sqft', 'dhaka', 'Dhaka', 'Banani', 'commercial', 'office', 120000, 10000, 0, 2, 0, 8, 1800, False, False, True, 'any', True, True, 'office'),
    ('Ground floor shop facing the main road', 'dhaka', 'Dhaka', 'Mirpur', 'commercial', 'shop', 28000, 2000, 0, 1, 0, 0, 350, False, False, False, 'any', True, False, 'office'),
    ('Full house with garden in Baridhara', 'dhaka', 'Dhaka', 'Baridhara', 'house', 'family', 150000, 10000, 5, 5, 4, 0, 4200, True, True, True, 'any', False, False, 'house'),
    ('Family flat near GEC Circle', 'chattogram', 'Chattogram', 'Nasirabad', 'apartment', 'family', 25000, 2000, 3, 2, 2, 4, 1300, False, False, True, 'any', True, True, 'flat'),
    ('2-bed apartment in Agrabad commercial area', 'chattogram', 'Chattogram', 'Agrabad', 'apartment', 'family', 20000, 1500, 2, 2, 1, 6, 1050, False, False, False, 'any', False, False, 'flat'),
    ('Bachelor room near Zindabazar', 'sylhet', 'Sylhet', 'Zindabazar', 'room', 'bachelor', 7000, 500, 1, 1, 1, 3, 180, False, False, False, 'male', True, False, 'room'),
]

DESCRIPTION = {
    'family': ('A well-kept {kind} in {area} with plenty of natural light and good cross-ventilation. The building has '
               'a caretaker, and shops, pharmacies and public transport are a short walk away.\n\n'
               'Recently repainted. Kitchen has space for a fridge and the bathrooms have hot water lines. '
               'Ideal for a family looking for a calm neighbourhood.'),
    'bachelor': ('Clean {kind} in {area}, suitable for students and job holders. Close to bus stops and food shops. '
                 'Current tenants are working professionals.\n\nRent includes a share of the caretaker and '
                 'cleaning costs. Gas is a shared line.'),
    'sublet': ('A furnished room inside our family flat in {area}. You get your own bed, table and wardrobe, and '
               'share the kitchen with a small family.\n\nPerfect for a working woman or a student.'),
    'hostel': ('Seat in a clean, secure hostel in {area}. Two to three seats per room, with a reading table, '
               'wardrobe and fan for each person.\n\nWiFi and water are included. Meals are available on request.'),
    'office': ('Ready office space in {area} on a busy commercial road. Open floor that can be partitioned, '
               'with washrooms on the floor and a generator for the lift and common areas.\n\nSuits a startup or a branch office.'),
    'shop': ('Ground-floor shop in {area} facing the main road with heavy foot traffic. Shutter front, '
             'electricity meter installed, and space for a small store room.\n\nGood for a pharmacy, mobile shop or cafe.'),
}
RULES = {
    'family': 'No loud music after 11 PM.\nVisitors should inform the caretaker.\nNo smoking in common areas.',
    'bachelor': 'Guests allowed until 10 PM.\nKeep the shared kitchen clean.\nNo smoking inside rooms.',
    'sublet': 'Guests must leave by 9 PM.\nShared kitchen with the host family.\nKeep noise low after 10 PM.',
    'hostel': 'Gate closes at 10 PM.\nNo outside guests in rooms.\nMeal list must be given a day before.',
    'office': 'Office hours 8 AM - 10 PM.\nNo cooking on the floor.',
    'shop': 'Trade licence required.\nNo hazardous goods.',
}


def photo_file(name):
    return ContentFile((PHOTO_DIR / f'{name}.jpg').read_bytes(), name=f'{name}.jpg')


def make_document(text):
    """A simple fake NID scan so the verification screen has something to open."""
    img = Image.new('RGB', (900, 560), (236, 246, 243))
    d = ImageDraw.Draw(img)
    d.rectangle((20, 20, 880, 540), outline=(15, 118, 110), width=6)
    d.rectangle((60, 120, 300, 420), fill=(205, 235, 229))
    d.text((340, 120), 'GOVERNMENT OF THE PEOPLE\'S REPUBLIC OF BANGLADESH', fill=(15, 23, 42))
    d.text((340, 160), 'NATIONAL ID CARD  (DEMO)', fill=(15, 118, 110))
    d.text((340, 220), text, fill=(15, 23, 42))
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=80)
    return ContentFile(buf.getvalue(), name='nid.jpg')


class Command(BaseCommand):
    help = 'Create demo users, listings, photos and interactions.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete existing demo data first.')

    def user(self, username, first, last, role, **extra):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'first_name': first, 'last_name': last, 'role': role,
                      'email': f'{username}@ghorify.test', **extra},
        )
        if created:
            user.set_password(PASSWORD)
            user.save()
        return user

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts['reset']:
            for image in PropertyImage.objects.filter(property__landlord__email__endswith='@ghorify.test'):
                image.delete()
            User.objects.filter(email__endswith='@ghorify.test').delete()
            Amenity.objects.all().delete()
            self.stdout.write('Old demo data removed.')

        amenities = {n: Amenity.objects.get_or_create(name=n, defaults={'icon': i})[0] for n, i in AMENITIES}

        admin = self.user('admin', 'Ghorify', 'Admin', User.Role.ADMIN, is_staff=True, is_superuser=True)
        landlords = [
            self.user('rahim', 'Rahim', 'Uddin', User.Role.LANDLORD, phone='01711000001'),
            self.user('nasrin', 'Nasrin', 'Akter', User.Role.LANDLORD, phone='01811000002'),
            self.user('kamal', 'Kamal', 'Hossain', User.Role.LANDLORD, phone='01911000003'),
        ]
        for i, landlord in enumerate(landlords):
            profile = landlord.landlord_profile
            profile.nid_number = f'1990{i}26845123'
            if not profile.verification_docs:
                profile.verification_docs.save(f'nid_{landlord.username}.jpg',
                                               make_document(f'Name: {landlord.get_full_name()}'), save=False)
            profile.save()
            if i < 2:
                profile.mark_verified(admin)
            else:
                profile.status = LandlordProfile.Status.PENDING
                profile.save()

        tenants = [
            self.user('tanvir', 'Tanvir', 'Ahmed', User.Role.TENANT, phone='01611000004'),
            self.user('mim', 'Mim', 'Rahman', User.Role.TENANT, phone='01511000005'),
            self.user('sakib', 'Sakib', 'Hasan', User.Role.TENANT, phone='01311000006'),
        ]
        prefs = [('Dhanmondi', 40000, 'professional', 4), ('Lalmatia', 10000, 'student', 1), ('Uttara', 65000, 'business', 5)]
        for tenant, (loc, budget, occ, fam) in zip(tenants, prefs):
            tp = tenant.tenant_profile
            tp.preferred_location, tp.monthly_budget, tp.occupation, tp.family_size = loc, budget, occ, fam
            tp.save()

        if Property.objects.filter(landlord__in=landlords).exists():
            self.stdout.write(self.style.WARNING('Demo listings already exist. Use --reset to rebuild.'))
            return

        today = timezone.localdate()
        rnd = random.Random(7)
        used_sets = {key: 0 for key in PHOTO_SETS}
        properties = []
        for idx, row in enumerate(LISTINGS):
            (title, division, city, area, ptype, cat, rent, service, beds, baths, balconies, floor, size,
             furn, pets, park, gender, nego, featured, photo_kind) = row
            # The unverified landlord (kamal) gets a couple of listings that stay pending.
            landlord = landlords[2] if idx in (4, 9) else landlords[idx % 2]
            prop = Property.objects.create(
                landlord=landlord, title=title, property_type=ptype, category=cat, tenant_gender=gender,
                description=DESCRIPTION[cat].format(kind=dict(Property.PropertyType.choices)[ptype].lower(), area=area),
                division=division, city=city, location=area,
                address=f'House {10 + idx}, Road {2 + idx % 9}, {area}, {city}',
                price=rent, is_negotiable=nego, service_charge=service, advance_months=2 if rent < 50000 else 3,
                bedrooms=beds, bathrooms=baths, balconies=balconies, floor=floor, size=size,
                furnished=furn, pet_friendly=pets, parking=park,
                house_rules=RULES[cat], gate_closing_time=time(23, 0) if cat == 'family' else time(22, 0),
                available_from=today + timedelta(days=idx % 4 * 7),
                status=Property.Status.APPROVED if landlord.landlord_profile.is_verified else Property.Status.PENDING,
                is_featured=featured, view_count=rnd.randint(25, 480),
            )
            pool = list(amenities.values())
            if cat == 'hostel':
                prop.amenities.set([amenities['Meal service'], amenities['WiFi ready'], amenities['24/7 security'], amenities['Water filter']])
            else:
                prop.amenities.set(rnd.sample(pool[:11], k=4 + idx % 4))

            sets = PHOTO_SETS[photo_kind]
            photos = sets[used_sets[photo_kind] % len(sets)]
            used_sets[photo_kind] += 1
            captions = {'building': 'Building front', 'house': 'Front view', 'living': 'Living room', 'kitchen': 'Kitchen',
                        'bedroom': 'Bedroom', 'room': 'Room', 'office': 'Office floor'}
            for v, name in enumerate(photos):
                PropertyImage.objects.create(property=prop, image=photo_file(name), is_primary=(v == 0),
                                             caption=captions[name.split('_')[0]])

            if cat in ('hostel',):
                Utility.objects.create(property=prop, name='electricity', amount=500)
                Utility.objects.create(property=prop, name='internet', amount=300, included_in_rent=True)
            else:
                Utility.objects.create(property=prop, name='electricity', amount=1500 + beds * 700)
                if cat not in ('office', 'shop'):
                    Utility.objects.create(property=prop, name='gas', amount=1080, included_in_rent=(cat == 'sublet'))
                Utility.objects.create(property=prop, name='water', amount=400 + beds * 100)
                if idx % 2 == 0:
                    Utility.objects.create(property=prop, name='internet', amount=1000, note='40 Mbps line')
            properties.append(prop)

        live = [p for p in properties if p.is_published]
        tanvir, mim, sakib = tenants
        by_title = {p.title: p for p in properties}
        dhanmondi = by_title['Sunny 3-bed family flat near Dhanmondi Lake']
        sublet = by_title['Sublet room in quiet family home']

        for p in live[:4]:
            Favourite.objects.create(tenant=tanvir, property=p)
        comparison = Comparison.objects.create(tenant=tanvir, name='Dhanmondi vs Bashundhara')
        for title in ('Sunny 3-bed family flat near Dhanmondi Lake', 'New 3-bed apartment in Bashundhara R/A',
                      'Spacious duplex with private rooftop'):
            comparison.add(by_title[title])

        VisitRequest.objects.create(tenant=tanvir, property=dhanmondi, preferred_date=today - timedelta(days=3),
                                    time_slot='evening', status=RequestStatus.APPROVED, responded_at=timezone.now(),
                                    landlord_note='Ask for the caretaker at the gate.')
        VisitRequest.objects.create(tenant=mim, property=dhanmondi, preferred_date=today + timedelta(days=2),
                                    time_slot='morning', message='Can I bring my sister along?')
        VisitRequest.objects.create(tenant=sakib, property=by_title['Spacious duplex with private rooftop'],
                                    preferred_date=today + timedelta(days=5), time_slot='afternoon')
        VisitRequest.objects.create(tenant=mim, property=sublet, preferred_date=today - timedelta(days=6),
                                    time_slot='afternoon', status=RequestStatus.APPROVED, responded_at=timezone.now())
        RentalRequest.objects.create(tenant=tanvir, property=dhanmondi, move_in_date=today + timedelta(days=20),
                                     duration_months=12, occupants=4, message='Family of four, I work at a bank in Motijheel.')
        RentalRequest.objects.create(tenant=sakib, property=by_title['Furnished 3-bed apartment with lake view'],
                                     move_in_date=today + timedelta(days=30), duration_months=24, occupants=5)

        Review.objects.create(tenant=tanvir, property=dhanmondi, rating=5, landlord_rating=4,
                              comment='Very bright flat and the lake is a five minute walk. Landlord was polite and answered every question.')
        Review.objects.create(tenant=mim, property=sublet, rating=4, landlord_rating=5,
                              comment='The family is very kind and the room is clean. A bit far from the main road but very safe.')
        Report.objects.create(reporter=sakib, property=by_title['Full house with garden in Baridhara'],
                              reason=Report.Reason.RENT,
                              details='The rent shown here is lower than what the caretaker told me on the phone.')

        SearchCriteria.objects.create(tenant=tanvir, name='Family flat near work', location='Dhanmondi',
                                      category='family', max_price=40000, min_bedrooms=3, needs_parking=True)
        SearchCriteria.objects.create(tenant=mim, name='Room near campus', location='Lalmatia', tenant_gender='female',
                                      max_price=10000, budget_includes_bills=True)

        self.stdout.write(self.style.SUCCESS(
            f'Demo ready: {len(properties)} listings ({len(live)} live). '
            f'Log in as admin / rahim / tanvir (password: {PASSWORD}).'))
