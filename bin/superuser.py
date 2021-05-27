import os

from django.contrib.auth import get_user_model

superuser_name = os.environ.get('APPSTORE_DJANGO_USERNAME', 'admin')
superuser_email = ""
superuser_password = os.environ.get('APPSTORE_DJANGO_PASSWORD', 'admin')

user_model = get_user_model()

if not user_model.objects.filter(username=superuser_name).exists():
    user_model.objects.create_superuser(superuser_name, superuser_email, superuser_password)
else:
    print(f'User "{superuser_name}" already exists, not created')
