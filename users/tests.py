from rest_framework import status
from rest_framework.test import APITestCase

from users.models import AdminProfile, User


class AdminRegistrationScopeTests(APITestCase):
    def setUp(self):
        self.active_admin = User.objects.create_user(
            phone_number='+2348000000300',
            name='Existing Admin',
            role='ADMIN',
            password='secret123',
            is_active=True,
            is_verified=True,
            is_staff=True,
        )
        AdminProfile.objects.create(
            user=self.active_admin,
            state='Lagos',
            lga='Ikeja',
            area='Alausa',
        )

    def test_cannot_register_second_active_admin_for_same_lga(self):
        response = self.client.post(
            '/api/auth/register/',
            data={
                'name': 'New Admin',
                'email': 'new-admin@cleanlinka.com',
                'phone_number': '+2348000000301',
                'password': 'secret123',
                'role': 'ADMIN',
                'state': 'Lagos',
                'lga': 'Ikeja',
                'area': 'Computer Village',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('lga', response.data)

    def test_can_register_admin_for_different_lga(self):
        response = self.client.post(
            '/api/auth/register/',
            data={
                'name': 'Surulere Admin',
                'email': 'surulere-admin@cleanlinka.com',
                'phone_number': '+2348000000302',
                'password': 'secret123',
                'role': 'ADMIN',
                'state': 'Lagos',
                'lga': 'Surulere',
                'area': 'Ojuelegba',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
