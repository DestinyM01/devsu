import json
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from .models import User


class TestHealthCheck(TestCase):
    """Tests for the health check endpoint."""

    def test_health_returns_200(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)

    def test_health_returns_json(self):
        response = self.client.get('/health/')
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'healthy')


class TestUserModel(TestCase):
    """Tests for the User model."""

    def test_create_user(self):
        user = User.objects.create(name='Test', dni='12345678901')
        self.assertEqual(str(user), 'Test')
        self.assertEqual(user.dni, '12345678901')

    def test_unique_dni(self):
        User.objects.create(name='Test1', dni='12345678901')
        with self.assertRaises(Exception):
            User.objects.create(name='Test2', dni='12345678901')


class TestUserView(APITestCase):
    """Tests for the users API endpoints."""

    def setUp(self):
        user = User(name='Test1', dni='09876543210')
        user.save()
        self.url = reverse("users-list")
        self.data = {'name': 'Test2', 'dni': '09876543211'}

    def test_post(self):
        response = self.client.post(self.url, self.data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(json.loads(response.content), {"id": 2, "name": "Test2", "dni": "09876543211"})
        self.assertEqual(User.objects.count(), 2)

    def test_post_duplicate_dni(self):
        response = self.client.post(self.url, {'name': 'Dup', 'dni': '09876543210'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['detail'], 'User already exists')

    def test_post_invalid_data(self):
        response = self.client.post(self.url, {'name': ''}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_get_list(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.content)), 1)

    def test_get(self):
        response = self.client.get(self.url + '1/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"id": 1, "name": "Test1", "dni": "09876543210"})

    def test_get_not_found(self):
        response = self.client.get(self.url + '999/')
        self.assertEqual(response.status_code, 404)

    def test_list_empty(self):
        User.objects.all().delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), [])

    def test_create_multiple_users(self):
        self.client.post(self.url, self.data, format='json')
        response = self.client.get(self.url)
        self.assertEqual(len(json.loads(response.content)), 2)
