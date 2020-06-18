from django.contrib.auth.models import User
from django.test import TestCase


class AdminAccessTest(TestCase):
    def setUp(self):
        """Test for creating user"""
        self.user = User.objects.create(username='non_admin', email='')
        self.user.set_password('pass')
        self.user.save()
        """ Create SuperUser """
        self.superuser = User.objects.create_superuser(username='admin', email="admin@admin.com", password='admin')

    def test_non_admin_aceess(self):
        credentials = {'username': 'non_admin', 'password': 'pass'}
        self.client.login(**credentials)
        response = self.client.get('/admin/auth/')
        self.assertEqual(response.status_code, 302)

    def test_admin_access(self):
        credentials = {'username': 'admin', 'password': 'admin'}
        self.client.login(**credentials)
        response = self.client.get('/admin/auth/')
        self.assertEqual(response.status_code, 200)
