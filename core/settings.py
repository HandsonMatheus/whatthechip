from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega variáveis do .env se existir
try:
    from dotenv import load_dotenv
    _env_path = BASE_DIR / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'wtc-dev-secret-key-troque-em-producao')

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# Localhost para dev; em produção o Render injeta RENDER_EXTERNAL_HOSTNAME
ALLOWED_HOSTS = ['localhost', '127.0.0.1']
_render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if _render_host:
    ALLOWED_HOSTS.append(_render_host)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Auditoria do catálogo (passo 3): registra no banco quem mudou o quê nas
    # tabelas de catálogo (gatilhos Postgres via pgtrigger). No SQLite dos testes
    # os gatilhos são no-op (pgtrigger checa connection.vendor) — não quebra.
    'pgtrigger',
    'pghistory',
    # Multi-empresa (PLANO_MULTITENANT.md, T1): Company/Branch/Membership,
    # escopo por request (contextvar) e gates de papel. Antes de chips/estoque
    # porque eles ganham FKs para tenancy (SearchLog.company etc.).
    'tenancy',
    'pages',
    'chips',
    'estoque',
]

# ── Autenticação ──────────────────────────────────────────────
LOGIN_URL          = '/login/'
LOGIN_REDIRECT_URL = '/painel/'   # lançadeira pós-login (UX 2026-07-06); o
                                  # trabalho continua em /estoque/, 1 clique
LOGOUT_REDIRECT_URL = '/'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # ← serve static em produção
    'django.contrib.sessions.middleware.SessionMiddleware',
    # i18n: resolve o idioma da request (sessão → cookie django_language →
    # Accept-Language → LANGUAGE_CODE). DEPOIS do SessionMiddleware e ANTES do
    # CommonMiddleware (exigência do Django). Ativa gettext por request. Ver I18N.md.
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # Captura o usuário autenticado no contexto do evento pghistory (o "quem"
    # das mudanças via admin/web). Precisa vir DEPOIS do AuthenticationMiddleware.
    'pghistory.middleware.HistoryMiddleware',
    # Resolve o Membership do usuário → request.company/role + contextvar de
    # escopo (tenancy/scope.py). DEPOIS do AuthenticationMiddleware. Na T4
    # este middleware passa a abrir a transação da request e emitir SET LOCAL.
    'tenancy.middleware.TenancyMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                # i18n nos templates: LANGUAGE_CODE, LANGUAGES e o idioma ativo
                # ({% get_current_language %}) — alimenta o seletor de idioma.
                'django.template.context_processors.i18n',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Papel/empresa nos templates (wtc_is_manager etc.) — navegação
                # por papel (§9 do plano). A barreira real é o gate da view.
                'tenancy.context_processors.tenancy',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Em produção o Render fornece DATABASE_URL automaticamente.
# Localmente usa as variáveis individuais (ou o banco local padrão).
import dj_database_url as _dj_db_url

_DATABASE_URL = os.environ.get('DATABASE_URL')
if _DATABASE_URL:
    DATABASES = {'default': _dj_db_url.config(default=_DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'whatthechip'),
            'USER': os.environ.get('DB_USER', 'raphaelsilvabastos'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }

# ── Internacionalização (i18n) ────────────────────────────────
# Português é o idioma-fonte (msgid) e o fallback. Os demais vivem em
# locale/<código>/LC_MESSAGES/django.po (versionados no git). Adicionar um
# idioma = incluir aqui + gerar/traduzir o .po. Detalhes: I18N.md.
from django.utils.translation import gettext_lazy as _  # noqa: E402

LANGUAGE_CODE = 'pt-br'          # fallback + idioma-fonte das strings (msgid)

LANGUAGES = [
    ('pt-br', _('Português')),
    ('es',    _('Español')),
    # ('en', _('English')),   # em breve — descomentar quando o .po estiver pronto
    # ('zh-hans', _('中文')),  # em breve
]

# Onde o Django procura os catálogos .mo compilados (além dos de cada app).
LOCALE_PATHS = [BASE_DIR / 'locale']

TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True                  # liga o motor de tradução por request
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Gemini removido (jun/2026): o engine de classificação usa apenas o banco de
# PNs confirmados (confidence ∈ confirmed/manual) + a gramática das famílias.
# Não há mais fallback de IA nem enriquecimento automático.

# CKEditor removido — pages/admin.py usa Textarea monospace simples.
