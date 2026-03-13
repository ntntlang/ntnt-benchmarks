import os
SECRET_KEY = 'benchmark-not-for-production'
DEBUG = False
ALLOWED_HOSTS = ['*']
INSTALLED_APPS = ['django.contrib.contenttypes']
MIDDLEWARE = []
ROOT_URLCONF = 'bench.urls'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'benchmarks',
        'USER': 'ntnt',
        'PASSWORD': os.environ.get('DB_PASSWORD', 'changeme'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': '5432',
    }
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
