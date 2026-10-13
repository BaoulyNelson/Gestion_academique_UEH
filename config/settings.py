import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TRUE_VALUES = {"1", "true", "yes"}


def env_bool(name, default="0"):
    return os.getenv(name, default).lower() in TRUE_VALUES


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
DEBUG = env_bool("DJANGO_DEBUG", "0")  # sécurisé par défaut : mettre DJANGO_DEBUG=1 en local

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "Définissez DJANGO_SECRET_KEY dans le fichier .env avant un lancement hors mode debug."
        )
    SECRET_KEY = "cle-locale-reservee-au-developpement"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # Remplace django.contrib.admin (AdminConfig personnalisé de GP7)
    "config.apps.AdministrationGP7Config",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Tiers (venant de l'admission)
    "rest_framework",
    "drf_spectacular",
    "allauth",
    "allauth.account",
    # GP7
    "applications.comptes.apps.ComptesConfig",
    "applications.referentiels.apps.ReferentielsConfig",
    "applications.inscriptions.apps.InscriptionsConfig",
    "applications.notes.apps.NotesConfig",
    "applications.rapports.apps.RapportsConfig",
    "applications.audit.apps.AuditConfig",
    "applications.contact.apps.ContactConfig",
    # Admission
    "applications.candidats.apps.CandidatsConfig",
    "applications.entites.apps.EntitesConfig",
    "applications.programmes.apps.ProgrammesConfig",
    "applications.documents.apps.DocumentsConfig",
    "applications.candidatures.apps.CandidaturesConfig",
    "applications.resultats.apps.ResultatsConfig",
    "applications.notifications.apps.NotificationsConfig",
    "applications.tableau_bord.apps.TableauBordConfig",
    "applications.administration.apps.AdministrationConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "csp.middleware.CSPMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "applications.administration.middleware.ProtectionAdministrationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "applications.comptes.context_processors.site_config",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Base de données (une seule base pour le projet fusionné)
# Variables DB_* (GP7) avec repli sur MYSQL_* (ancienne admission)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME", os.getenv("MYSQL_DATABASE", "config_web")),
        "USER": os.getenv("DB_USER", os.getenv("MYSQL_USER", "root")),
        "PASSWORD": os.getenv("DB_PASSWORD", os.getenv("MYSQL_PASSWORD", "")),
        "HOST": os.getenv("DB_HOST", os.getenv("MYSQL_HOST", "127.0.0.1")),
        "PORT": os.getenv("DB_PORT", os.getenv("MYSQL_PORT", "3306")),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# ---------------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "comptes.Utilisateur"
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "applications.comptes.auth_backend.EmailOrUsernameBackend",  # GP7
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",  # admission
]

# allauth (admission)
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_SIGNUP_FORM_CLASS = "applications.comptes.forms.FormulaireInscription"
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = "account_login"
ACCOUNT_ADAPTER = "applications.comptes.adapters.AdaptateurCompteAdmission"
# Le modèle Utilisateur partagé conserve le champ username de Django.
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"
ACCOUNT_USERNAME_REQUIRED = False

# Redirections : valeurs de GP7 (portail principal).
# Pour l'admission, utiliser plutôt :
#   LOGIN_URL = "account_login"
#   LOGIN_REDIRECT_URL = "tableau_bord:mes_inscriptions"
#   LOGOUT_REDIRECT_URL = "tableau_bord:accueil"
LOGIN_URL = "comptes:connexion"
LOGIN_REDIRECT_URL = "comptes:tableau_de_bord"
LOGOUT_REDIRECT_URL = "comptes:landing"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",  # garde les anciens mots de passe valides
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "America/Port-au-Prince"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Fichiers statiques et médias
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

DATA_UPLOAD_MAX_MEMORY_SIZE = 7 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

PDF_SIGNATURE_PATH = Path(
    os.getenv(
        "PDF_SIGNATURE_PATH",
        str(BASE_DIR / "static" / "images" / "directeur.png"),
    )
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# E-mail
# ---------------------------------------------------------------------------
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    (
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", "1")
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", "0")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "GP7 <noreply@ueh.edu.ht>")
EMAIL_TIMEOUT = 10

# ---------------------------------------------------------------------------
# Celery / cache (admission)
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", "0")

if DEBUG:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "gp7-local",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.getenv("REDIS_CACHE_URL", "redis://127.0.0.1:6379/1"),
        }
    }

# ---------------------------------------------------------------------------
# API (admission)
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
SPECTACULAR_SETTINGS = {
    "TITLE": "API GP7 – Admission UEH",
    "DESCRIPTION": "Services de gestion académique et des admissions universitaires.",
    "VERSION": "1.0.0",
}

# ---------------------------------------------------------------------------
# Sécurité
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# CSP : s'applique maintenant à TOUT le site (GP7 compris).
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "https://cdn.jsdelivr.net")
CSP_STYLE_SRC = ("'self'", "https://cdn.jsdelivr.net", "https://fonts.googleapis.com")
CSP_FONT_SRC = ("'self'", "https://cdn.jsdelivr.net", "https://fonts.gstatic.com")
CSP_IMG_SRC = ("'self'", "data:")

RATELIMIT_ENABLE = True

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", "0" if DEBUG else "1")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = int(
    os.getenv("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG