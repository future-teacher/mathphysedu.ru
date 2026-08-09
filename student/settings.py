import os
from pathlib import Path
from dotenv import load_dotenv

# ===== ЗАГРУЗКА .env С ЯВНЫМ ПУТЁМ =====
BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / '.env'

if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ .env загружен из: {env_file}")
else:
    print(f"⚠️ .env НЕ НАЙДЕН по пути: {env_file}")
# =========================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-default-key-for-dev')

# SECURITY WARNING: don't run with debug turned on in production!
# Если .env отсутствует — считаем, что это локальная разработка (DEBUG=True).
# В production обязательно создайте .env с DJANGO_DEBUG=False.
if env_file.exists():
    DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'
else:
    DEBUG = True

ALLOWED_HOSTS = ['mathphysedu.ru', 'www.mathphysedu.ru', 'localhost', '127.0.0.1', '77.221.145.35']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'students.apps.StudentsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'student.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'student.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login settings
LOGIN_URL = '/students/login/'
LOGIN_REDIRECT_URL = '/students/dashboard/'
LOGOUT_REDIRECT_URL = '/students/login/'

# File upload settings
# Максимальный размер файла в памяти (50MB) — если файл больше, Django пишет его на диск
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
# Максимальный размер всего тела запроса (200MB) — включает все поля + файлы
DATA_UPLOAD_MAX_MEMORY_SIZE = 209715200  # 200MB
# Максимальное количество полей в форме (для множественной загрузки файлов)
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Security settings for production (disable in development)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ========================
# TELEGRAM BOT SETTINGS
# ========================
# Токен бота — берётся из .env
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

# Включить/выключить уведомления в Telegram
TELEGRAM_BOT_ENABLED = bool(TELEGRAM_BOT_TOKEN)

# Базовый URL сайта для ссылок в уведомлениях
BASE_URL = os.environ.get('BASE_URL', 'https://mathphysedu.ru')

# ========================
# YANDEX SMARTCAPTCHA SETTINGS
# ========================
# Ключи берутся из .env
YANDEX_SMARTCAPTCHA_SITE_KEY = os.environ.get(
    'YANDEX_SMARTCAPTCHA_SITE_KEY',
    'ysc1_placeholder_site_key'
)
YANDEX_SMARTCAPTCHA_SERVER_KEY = os.environ.get(
    'YANDEX_SMARTCAPTCHA_SERVER_KEY',
    'ysc2_placeholder_server_key'
)
