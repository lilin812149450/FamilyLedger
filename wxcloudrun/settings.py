"""
Django settings for wxcloudrun project.
基于微信云托管官方 Django 模板（wxcloudrun-django）改造。
"""
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

# 本地开发：项目根目录下的 .env 按键值注入环境变量（已存在的环境变量优先，不覆盖）。
# 线上由云托管注入环境变量，不依赖这个文件；.env 不要提交到仓库。
_env_file = BASE_DIR / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        _line = _line.strip()
        if not _line or _line.startswith('#') or '=' not in _line:
            continue
        _key, _, _value = _line.partition('=')
        os.environ.setdefault(_key.strip(), _value.strip().strip('"').strip("'"))

# SECURITY WARNING: keep the secret key used in production secret!
# 线上通过云托管环境变量 DJANGO_SECRET_KEY 注入，不写死在代码里
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'wxcloudrun-family-ledger-dev-only')

# SECURITY WARNING: don't run with debug turned on in production!
# 模板默认 True 会把完整堆栈暴露给线上，这里默认关闭
DEBUG = os.environ.get('DJANGO_DEBUG', 'false').lower() == 'true'

ALLOWED_HOSTS = ['*']

# 小程序接口不带结尾斜杠。若为 True，CommonMiddleware 会对 /api/login 发 301 重定向，
# POST 的 body 会在跳转中丢掉。
APPEND_SLASH = False

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'wxcloudrun',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'wxcloudrun.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'wxcloudrun.wsgi.application'

# ===== 数据库：云托管 MySQL =====
# 两种配置方式，凭据一律只走环境变量 / .env，不写进代码：
#   1) MYSQL_URL  整串连接串，形如 mysql://user:pass@host:port/dbname
#   2) MYSQL_ADDRESS / MYSQL_USERNAME / MYSQL_PASSWORD / MYSQL_DATABASE
#      云托管绑定 MySQL 后会自动注入这四个分段变量
# 注意：模板原来直接 os.environ.get("MYSQL_ADDRESS").split(':')，没绑定 MySQL 时会
# 因 NoneType 直接崩，这里全部给了兜底。
_db_url = os.environ.get('MYSQL_URL', '').strip()

if _db_url:
    _parsed = urlparse(_db_url)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': unquote(_parsed.path.lstrip('/')) or 'ledger',
            'USER': unquote(_parsed.username or ''),
            'PASSWORD': unquote(_parsed.password or ''),
            'HOST': _parsed.hostname or '127.0.0.1',
            'PORT': str(_parsed.port or 3306),
            'CONN_MAX_AGE': 60,
            'OPTIONS': {'charset': 'utf8mb4'},
        }
    }
else:
    _address = os.environ.get('MYSQL_ADDRESS', '127.0.0.1:3306')
    _host, _, _port = _address.partition(':')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('MYSQL_DATABASE', 'ledger'),
            'USER': os.environ.get('MYSQL_USERNAME', 'root'),
            'PASSWORD': os.environ.get('MYSQL_PASSWORD', ''),
            'HOST': _host or '127.0.0.1',
            'PORT': _port or '3306',
            'CONN_MAX_AGE': 60,
            'OPTIONS': {'charset': 'utf8mb4'},
        }
    }

# Password validation

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

# 日志直接输出到 stdout，便于在云托管「日志」里排查。
# 模板原来是写 logs/ 目录下的轮转文件，容器里既占空间又看不到。
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(asctime)s] [%(name)s:%(lineno)d] [%(levelname)s] %(message)s',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'log': {'handlers': ['console'], 'level': 'INFO', 'propagate': True},
    },
}

# Internationalization

LANGUAGE_CODE = 'zh-hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = False

USE_TZ = False

# Static files (CSS, JavaScript, Images)

STATIC_URL = '/static/'

# Default primary key field type

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
