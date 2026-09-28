from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'yara-service-key'
DEBUG = True
ALLOWED_HOSTS = ['*']
INSTALLED_APPS = ['scanner']
ROOT_URLCONF = 'yara_service.urls'
MIDDLEWARE = []
DATABASES = {}
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
