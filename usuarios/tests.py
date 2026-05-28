from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

class VigilarActividadTestCase(TestCase):
    def setUp(self):
        # Crear estudiante normal
        self.student = User.objects.create_user(
            username='student1',
            password='password123',
            email='student1@gmail.com',
            first_name='Juan',
            last_name='Perez',
            numero_documento='10101010',
            telefono='3001234567',
            role='student'
        )
        
        # Crear profesor (staff)
        self.teacher = User.objects.create_user(
            username='teacher1',
            password='password123',
            email='teacher1@gmail.com',
            first_name='Carlos',
            last_name='Gomez',
            numero_documento='20202020',
            telefono='3011234567',
            role='teacher',
            is_staff=True
        )

    def test_anonymous_user_cannot_access(self):
        url = reverse('usuarios:vigilar_actividad')
        response = self.client.get(url)
        # Al no estar autenticado, debe redirigir al login (302)
        self.assertEqual(response.status_code, 302)

    def test_student_cannot_access(self):
        self.client.login(username='student1', password='password123')
        url = reverse('usuarios:vigilar_actividad')
        response = self.client.get(url)
        # Un estudiante autenticado que no cumple la prueba debe redirigir al login (302) o dar 403
        self.assertIn(response.status_code, [302, 403])

    def test_teacher_can_access(self):
        self.client.login(username='teacher1', password='password123')
        url = reverse('usuarios:vigilar_actividad')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_search_student_by_name(self):
        self.client.login(username='teacher1', password='password123')
        url = reverse('usuarios:vigilar_actividad') + '?q=Juan'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Juan')
        self.assertContains(response, 'Perez')

    def test_search_student_by_phone(self):
        self.client.login(username='teacher1', password='password123')
        url = reverse('usuarios:vigilar_actividad') + '?q=3001234567'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Juan')
        self.assertContains(response, '3001234567')
