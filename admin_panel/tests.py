from rest_framework import status
from rest_framework.test import APITestCase

from pickups.models import Job, PickupRequest
from users.models import AdminProfile, CollectorProfile, User


class AdminRequestEndpointsTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone_number='2348000000200',
            name='Admin User',
            role='ADMIN',
            password='secret123',
            is_active=True,
            is_verified=True,
            is_staff=True,
        )
        AdminProfile.objects.create(
            user=self.admin,
            state='Lagos',
            lga='Ikeja',
            area='Alausa',
        )
        self.collector = User.objects.create_user(
            phone_number='2348000000201',
            name='Collector User',
            role='COLLECTOR',
            password='secret123',
            is_active=True,
            is_verified=True,
        )
        CollectorProfile.objects.create(
            user=self.collector,
            national_id='32345678901',
            vehicle_type='OTHER',
            service_area='Ikeja',
            is_verified=True,
            is_available=True,
        )
        household = User.objects.create_user(
            phone_number='2348000000202',
            name='Household User',
            role='HOUSEHOLD',
            password='secret123',
            is_active=True,
            is_verified=True,
        )
        self.pickup = PickupRequest.objects.create(
            household=household,
            channel=PickupRequest.Channel.APP,
            waste_type=PickupRequest.WasteType.GENERAL,
            notes='Address: 7 Acme Road\nLGA: Ikeja\nArea: Computer Village',
        )
        self.out_of_scope_collector = User.objects.create_user(
            phone_number='2348000000203',
            name='Surulere Collector',
            role='COLLECTOR',
            password='secret123',
            is_active=True,
            is_verified=True,
        )
        CollectorProfile.objects.create(
            user=self.out_of_scope_collector,
            national_id='32345678902',
            vehicle_type='OTHER',
            service_area='Ojuelegba',
            state='Lagos',
            lga='Surulere',
            area='Ojuelegba',
            is_verified=True,
            is_available=True,
        )
        other_household = User.objects.create_user(
            phone_number='2348000000204',
            name='Surulere Household',
            role='HOUSEHOLD',
            password='secret123',
            is_active=True,
            is_verified=True,
        )
        self.out_of_scope_pickup = PickupRequest.objects.create(
            household=other_household,
            channel=PickupRequest.Channel.APP,
            waste_type=PickupRequest.WasteType.GENERAL,
            notes='Address: 11 Bode Thomas\nLGA: Surulere\nArea: Ojuelegba',
        )
        self.client.force_authenticate(user=self.admin)

    def test_admin_can_list_requests(self):
        response = self.client.get('/api/admin/requests/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.pickup.id)

    def test_admin_scope_filters_collectors_and_requests_to_assigned_lga(self):
        collectors_response = self.client.get('/api/admin/collectors/')
        self.assertEqual(collectors_response.status_code, status.HTTP_200_OK)
        collector_ids = [item['id'] for item in collectors_response.data]
        self.assertIn(self.collector.id, collector_ids)
        self.assertNotIn(self.out_of_scope_collector.id, collector_ids)

        requests_response = self.client.get('/api/admin/requests/')
        self.assertEqual(requests_response.status_code, status.HTTP_200_OK)
        request_ids = [item['id'] for item in requests_response.data]
        self.assertIn(self.pickup.id, request_ids)
        self.assertNotIn(self.out_of_scope_pickup.id, request_ids)

    def test_admin_can_assign_request(self):
        response = self.client.post(
            f'/api/admin/requests/{self.pickup.id}/assign/',
            data={'collector_id': self.collector.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.pickup.refresh_from_db()
        self.assertEqual(self.pickup.status, PickupRequest.Status.ASSIGNED)
        self.assertTrue(Job.objects.filter(request=self.pickup, collector=self.collector).exists())

    def test_verify_collector_updates_review_metadata(self):
        response = self.client.post(
            f'/api/admin/collectors/{self.collector.id}/verify/',
            data={'approved': True, 'review_notes': 'All documents checked.'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.collector.refresh_from_db()
        profile = self.collector.collector_profile
        self.assertTrue(profile.is_verified)
        self.assertTrue(profile.is_available)
        self.assertEqual(profile.review_notes, 'All documents checked.')
        self.assertIsNotNone(profile.reviewed_at)

    def test_deactivating_collector_returns_them_to_review(self):
        response = self.client.patch(
            f'/api/admin/collectors/{self.collector.id}/',
            data={'is_available': False, 'review_notes': 'Vehicle details need reconfirmation.'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(
            f'/api/admin/collectors/{self.collector.id}/toggle-status/',
            data={'is_active': False, 'review_notes': 'Route coverage under review.'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.collector.refresh_from_db()
        profile = self.collector.collector_profile
        self.assertFalse(self.collector.is_active)
        self.assertFalse(profile.is_verified)
        self.assertFalse(profile.is_available)
        self.assertEqual(profile.review_notes, 'Route coverage under review.')
