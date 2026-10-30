from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from properties.models import Property

from .models import Comparison, RentalRequest, RequestStatus, Review, VisitRequest


class InteractionFlowTests(TestCase):
    def setUp(self):
        self.landlord = User.objects.create_user('ll', 'll@x.com', 'pw', role='landlord', phone='01711111111')
        self.tenant = User.objects.create_user('tt', 'tt@x.com', 'pw', role='tenant')
        self.other = User.objects.create_user('oo', 'oo@x.com', 'pw', role='tenant')
        self.props = [Property.objects.create(
            landlord=self.landlord, title=f'Flat {i}', description='d', location='Mirpur', address='Secret road',
            price=20000, status=Property.Status.APPROVED) for i in range(4)]
        self.prop = self.props[0]
        self.client.force_login(self.tenant)

    def test_comparison_holds_at_most_three(self):
        for p in self.props:
            self.client.post(reverse('interactions:comparison_add', args=[p.pk]))
        comparison = Comparison.objects.get(tenant=self.tenant)
        self.assertEqual(comparison.items.count(), 3)

    def test_contact_hidden_until_visit_approved(self):
        url = self.prop.get_absolute_url()
        self.assertNotContains(self.client.get(url), '01711111111')
        VisitRequest.objects.create(tenant=self.tenant, property=self.prop, preferred_date=timezone.localdate(),
                                    time_slot='morning', status=RequestStatus.APPROVED)
        self.assertContains(self.client.get(url), '01711111111')

    def test_cannot_book_two_active_visits(self):
        data = {'preferred_date': timezone.localdate() + timedelta(days=2), 'time_slot': 'morning'}
        self.client.post(reverse('interactions:visit_create', args=[self.prop.pk]), data)
        self.client.post(reverse('interactions:visit_create', args=[self.prop.pk]), data)
        self.assertEqual(VisitRequest.objects.filter(tenant=self.tenant).count(), 1)

    def test_visit_in_the_past_is_rejected(self):
        data = {'preferred_date': timezone.localdate() - timedelta(days=1), 'time_slot': 'morning'}
        self.client.post(reverse('interactions:visit_create', args=[self.prop.pk]), data)
        self.assertFalse(VisitRequest.objects.exists())

    def test_review_requires_approved_visit(self):
        data = {'rating': 5, 'comment': 'Really lovely flat with good light.'}
        self.client.post(reverse('interactions:review_create', args=[self.prop.pk]), data)
        self.assertFalse(Review.objects.exists())
        VisitRequest.objects.create(tenant=self.tenant, property=self.prop, preferred_date=timezone.localdate(),
                                    time_slot='morning', status=RequestStatus.APPROVED)
        self.client.post(reverse('interactions:review_create', args=[self.prop.pk]), data)
        self.assertEqual(Review.objects.count(), 1)

    def test_approving_rental_closes_other_requests(self):
        mine = RentalRequest.objects.create(tenant=self.tenant, property=self.prop, move_in_date=timezone.localdate())
        theirs = RentalRequest.objects.create(tenant=self.other, property=self.prop, move_in_date=timezone.localdate())
        self.client.force_login(self.landlord)
        self.client.post(reverse('interactions:respond_rental', args=[mine.pk]), {'decision': 'approve'})
        mine.refresh_from_db(); theirs.refresh_from_db(); self.prop.refresh_from_db()
        self.assertEqual(mine.status, RequestStatus.APPROVED)
        self.assertEqual(theirs.status, RequestStatus.REJECTED)
        self.assertFalse(self.prop.is_available)

    def test_landlord_cannot_answer_other_landlords_requests(self):
        stranger = User.objects.create_user('ss', 'ss@x.com', 'pw', role='landlord')
        visit = VisitRequest.objects.create(tenant=self.tenant, property=self.prop,
                                            preferred_date=timezone.localdate(), time_slot='morning')
        self.client.force_login(stranger)
        response = self.client.post(reverse('interactions:respond_visit', args=[visit.pk]), {'decision': 'approve'})
        self.assertEqual(response.status_code, 404)
