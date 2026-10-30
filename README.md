# Ghorify: Smart House Rental & Property Matching System

A Django web app that connects tenants and landlords in Dhaka. Tenants get homes ranked by a
**match percentage**, see the **real monthly cost** (rent + service charge + bills), compare up to
three homes side by side, book visits and apply to rent. Landlords manage listings, photos and
bills, and answer requests. Admins verify landlords, moderate listings and handle reports.

CSE 302 project, University of Asia Pacific.

## Apps and models

| App | Models | Purpose |
|---|---|---|
| `accounts` | `User`, `TenantProfile`, `LandlordProfile` | Custom user with a role (tenant / landlord / admin), profiles, avatar and verification document uploads |
| `properties` | `Property`, `PropertyImage`, `Utility`, `Amenity` | Listings, photo gallery (media CRUD), utility bills for the monthly cost estimate |
| `search` | `SearchCriteria` | Saved searches and the matching engine (`search/matching.py`) |
| `interactions` | `Favourite`, `Comparison`, `ComparisonItem`, `VisitRequest`, `RentalRequest`, `Review`, `Report` | Everything a tenant does with a property, and the landlord's responses |
| `dashboard` | (no models) | Role-based dashboards and the admin moderation panel |

## Listing details

- Categories: Family, Bachelor, Sublet, Hostel / Mess, Office, Shop
- Location by division → city/district → area, with a "Popular areas" section on the home page
- Gender preference (Anyone / Male only / Female only), allowed only for bachelor, sublet and hostel listings
- Balconies, negotiable rent, a public Property ID (e.g. `GH-00013`) and "last updated" date
- Featured listings (set by an admin) are shown first
- Report reasons that match common rental problems: not available, phone unreachable, location or rent mismatch, wrong photos, fake ad, scam

## Business rules

- New listings start as **pending**. An admin can publish one only after the landlord is **verified**.
- Editing a rejected listing sends it back for review.
- A landlord's phone, email and exact address are shown only after the landlord **approves a visit or rental request** from that tenant.
- A tenant can **review** a property only after an approved visit (date passed) or an approved rental.
- A visit slot that is already approved for another tenant cannot be booked or approved again.
- Approving one rental application marks the property as rented and closes the other pending applications.
- A comparison holds at most **3** properties.

### Match percentage

Each preference the tenant fills in has a weight: budget 30, area 20, bedrooms 15, bathrooms 10,
category 10, amenities 10, keyword 8, gender 8, type 6, parking 5, pets 5, furnished 5. A property earns full,
partial (e.g. up to 10% over budget gives half) or zero points per preference, and
`match % = earned / possible × 100`. Smart mode shows homes with 50% or more; Strict mode shows only
homes that satisfy every preference.

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows  (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env         # macOS/Linux: cp .env.example .env
python manage.py migrate
python manage.py runserver
```

The repository already includes `db.sqlite3` and `media/` with demo data. To rebuild the demo data from
scratch, run `python manage.py seed_demo --reset`.

Open http://127.0.0.1:8000.

Demo accounts (password `ghorify123`): `admin` (platform admin), `rahim` and `nasrin` (verified
landlords), `kamal` (landlord waiting for verification), `tanvir`, `mim` and `sakib` (tenants).

Run the tests with `python manage.py test`.

Demo photos in `static/img/photos` are from [Unsplash](https://unsplash.com) (Unsplash License).

## Requirements

```
Django==6.1.2
pillow==13.0.0
python-dotenv==1.2.4
asgiref==3.13.0
sqlparse==0.6.0
tzdata==2026.6
```
