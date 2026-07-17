import os
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(
    DEBUG=(bool, True),
    CELERY_BROKER_URL=(str, 'redis://localhost:6379/0'),
)
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))
SECRET_KEY = env('SECRET_KEY', default='unsafe-dev-key-change-me')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = ['*']
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'corsheaders',
    'django_vite',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_celery_beat',
    'users.apps.UsersConfig',
    'media.apps.MediaConfig',
    'content.apps.ContentConfig',
    'aggregator.apps.AggregatorConfig',
    'kodik_plugin.apps.KodikPluginConfig',
    'taxonomy.apps.TaxonomyConfig',
    'recommendations.apps.RecommendationsConfig',
]
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.TenantDomainMiddleware',
]
ROOT_URLCONF = 'core.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
WSGI_APPLICATION = 'core.wsgi.application'
DATABASES = {
    'default': env.db('DATABASE_URL', default='sqlite:///db.sqlite3')
}
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
AUTH_USER_MODEL = 'users.User'
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
DJANGO_VITE = {
    "default": {
        "dev_mode": DEBUG,
        "dev_server_host": "127.0.0.1",
        "dev_server_port": 5173,
    }
}
MEDIA_URL = 'media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media_storage')
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

KODIK_API_TOKEN = env('KODIK_API_TOKEN', default='')
KODIK_PLUGIN_ID = env.int('KODIK_PLUGIN_ID', default=1)
KODIK_WEBHOOK_SECRET = env('KODIK_WEBHOOK_SECRET', default='')

PLUGIN_STALE_MINUTES = env.int('PLUGIN_STALE_MINUTES', default=1440)
VIEWING_SESSION_DURATION_MINUTES = 15

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 20,
}
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

CELERY_BEAT_SCHEDULE = {
    'verify-plugins-daily': {
        'task': 'aggregator.tasks.verify_plugin_registry',
        'schedule': crontab(hour=3, minute=22),
    },
    'aggregate-user-profiles': {
        'task': 'recommendations.tasks.aggregate_user_profiles_task',
        'schedule': crontab(minute=0, hour='*/4'),
    },
}

LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'app_file_handler': {
            'level': 'INFO',
            'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
            'filename': LOG_DIR / 'app.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'kodik_file_handler': {
            'level': 'DEBUG',
            'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
            'filename': LOG_DIR / 'kodik_plugin.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'error_file_handler': {
            'level': 'WARNING',
            'class': 'concurrent_log_handler.ConcurrentRotatingFileHandler',
            'filename': LOG_DIR / 'errors.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'app_file_handler'],
            'level': 'INFO',
            'propagate': True,
        },
        'core': {
            'handlers': ['console', 'app_file_handler'],
            'level': 'INFO',
            'propagate': False,
        },
        'content': {
            'handlers': ['console', 'app_file_handler'],
            'level': 'INFO',
            'propagate': False,
        },
        'media': {
            'handlers': ['console', 'app_file_handler'],
            'level': 'INFO',
            'propagate': False,
        },
        'users': {
            'handlers': ['console', 'app_file_handler'],
            'level': 'INFO',
            'propagate': False,
        },
        'aggregator': {
            'handlers': ['console', 'app_file_handler'],
            'level': 'INFO',
            'propagate': False,
        },
        'kodik_plugin': {
            'handlers': ['console', 'kodik_file_handler', 'error_file_handler'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
