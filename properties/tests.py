import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import User

from .models import Property, PropertyImage, Utility

TEMP_MEDIA = tempfile.mkdtemp()


def fake_image(name='photo.jpg'):
    buf = io.BytesIO()
    Image.new('RGB', (40, 30), (200, 100, 50)).save(buf, 'JPEG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class PropertyCrudTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.landlord = User.objects.create_user('ll', 'll@x.com', 'pw', role='landlord')
        self.client.force_login(self.landlord)
        self.data = {
            'title': 'Test flat', 'property_type': 'apartment', 'category': 'family', 'description': 'desc',
            'location': 'Uttara', 'address': 'Road 3', 'price': 25000, 'service_charge': 1000, 'advance_months': 2,
            'bedrooms': 2, 'bathrooms': 2, 'floor': 3, 'is_available': 'on',
            'division': 'dhaka', 'city': 'Dhaka', 'tenant_gender': 'any', 'balconies': 1,
        }

    def test_gender_preference_only_for_shared_categories(self):
        self.data['tenant_gender'] = 'male'
        response = self.client.post(reverse('properties:create'), self.data)
        self.assertFalse(Property.objects.exists())
        self.assertContains(response, 'Gender preference can only be set')
        self.data['category'] = 'bachelor'
        self.client.post(reverse('properties:create'), self.data)
        self.assertEqual(Property.objects.get().tenant_gender, 'male')

    def test_create_with_photos_starts_pending(self):
        self.data['photos'] = [fake_image('a.jpg'), fake_image('b.jpg')]
        self.client.post(reverse('properties:create'), self.data)
        prop = Property.objects.get()
        self.assertEqual(prop.status, Property.Status.PENDING)
        self.assertEqual(prop.images.count(), 2)
        self.assertEqual(prop.images.filter(is_primary=True).count(), 1)

    def test_pending_listing_hidden_from_public(self):
        self.client.post(reverse('properties:create'), self.data)
        prop = Property.objects.get()
        self.client.logout()
        self.assertEqual(self.client.get(prop.get_absolute_url()).status_code, 404)

    def test_editing_rejected_listing_resubmits_it(self):
        self.client.post(reverse('properties:create'), self.data)
        prop = Property.objects.get()
        prop.status = Property.Status.REJECTED
        prop.save()
        self.data['title'] = 'Fixed title'
        self.client.post(reverse('properties:update', args=[prop.pk]), self.data)
        prop.refresh_from_db()
        self.assertEqual((prop.title, prop.status), ('Fixed title', Property.Status.PENDING))

    def test_other_landlord_cannot_edit_or_delete(self):
        self.client.post(reverse('properties:create'), self.data)
        prop = Property.objects.get()
        intruder = User.objects.create_user('xx', 'xx@x.com', 'pw', role='landlord')
        self.client.force_login(intruder)
        self.assertEqual(self.client.get(reverse('properties:update', args=[prop.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('properties:delete', args=[prop.pk])).status_code, 404)

    def test_deleting_cover_photo_promotes_next(self):
        self.data['photos'] = [fake_image('a.jpg'), fake_image('b.jpg')]
        self.client.post(reverse('properties:create'), self.data)
        prop = Property.objects.get()
        cover = prop.images.get(is_primary=True)
        self.client.post(reverse('properties:image_delete', args=[prop.pk, cover.pk]))
        self.assertTrue(PropertyImage.objects.get().is_primary)

    def test_monthly_cost_includes_only_separate_bills(self):
        self.client.post(reverse('properties:create'), self.data)
        prop = Property.objects.get()
        Utility.objects.create(property=prop, name='electricity', amount=2000)
        Utility.objects.create(property=prop, name='gas', amount=1080, included_in_rent=True)
        Utility.objects.create(property=prop, name='internet', amount=12000, billing_period='yearly')
        self.assertEqual(prop.monthly_cost, 25000 + 1000 + 2000 + 1000)

    def test_tenant_cannot_open_landlord_pages(self):
        tenant = User.objects.create_user('tt', 'tt@x.com', 'pw', role='tenant')
        self.client.force_login(tenant)
        self.assertRedirects(self.client.get(reverse('properties:create')), reverse('dashboard:home'),
                             fetch_redirect_response=False)
