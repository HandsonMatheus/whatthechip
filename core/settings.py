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

# Domínio próprio: whatthechip.app (registrado 2026-08-05, Hostinger). Localhost
# para dev. O Render injeta RENDER_EXTERNAL_HOSTNAME automaticamente — mantido
# como ROTA DE FUGA: se o DNS do domínio novo quebrar, <serviço>.onrender.com
# continua atendendo. Só remover depois que o domínio estiver validado por dias.
#
# ⚠ ORDEM DE OPERAÇÃO: host que não está nesta lista devolve 400 (DisallowedHost).
# Por isso ESTE deploy tem que ir ao ar ANTES de apontar o DNS na Hostinger —
# caso contrário o domínio resolve, a Render entrega, e o Django recusa.
ALLOWED_HOSTS = [
    'localhost', '127.0.0.1',
    'whatthechip.app', 'www.whatthechip.app',
]
_render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if _render_host:
    ALLOWED_HOSTS.append(_render_host)

# CSRF com domínio novo (Django 4+): o check compara o header Origin da request
# com o host servido. Sem declarar o origin aqui, TODO POST quebra com 403 CSRF
# verification failed — login, seletor de idioma, fechar lote, OV, aprovar fila.
# O host .onrender.com não precisa entrar: ele bate por igualdade com o próprio
# host da request (é a lista que cobre os nomes NOVOS).
CSRF_TRUSTED_ORIGINS = [
    'https://whatthechip.app',
    'https://www.whatthechip.app',
]

# TLS termina na BORDA da Render, não no gunicorn: a conexão que chega no Django
# é http. Sem este header request.is_secure() é False, o CSRF monta a origem
# esperada como "http://whatthechip.app" e compara com o Origin real
# "https://whatthechip.app" → não bate → 403 em todo POST.
# Só é seguro porque a Render SEMPRE sobrescreve X-Forwarded-Proto na borda
# (proxy confiável); num servidor exposto direto isto seria spoofável.
# ⚠ .app está na lista HSTS preload dos navegadores: não existe acesso http a
# whatthechip.app: ou o certificado está emitido, ou a página não abre.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Cookie de sessão e de CSRF só trafegam por HTTPS em produção
# (`check --deploy` W012/W016). Atrelado ao DEBUG porque o dev local roda em
# http://localhost — com True fixo o login não gruda na máquina do dono.
# É flag de BROWSER (não depende do Django saber o esquema): a Render e o
# whatthechip.app são 100% https, então em prod não há cenário de lockout.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE    = not DEBUG

# ── T7 (E2 — PLANO_MULTITENANT §17.3): subdomínio por cliente, ENV-DRIVEN ────
# WTC_TENANT_DOMAIN (ex.: "whatthechip.app") LIGA o modo multi-host:
#   · ALLOWED_HOSTS ganha ".domínio" (o ponto cobre apex E subdomínios);
#   · CSRF_TRUSTED_ORIGINS ganha https://*.domínio;
#   · cookies de sessão/CSRF viram domain-wide (B5) — só fora de DEBUG;
#   · o HostTenantMiddleware (tenancy) passa a resolver o host (§10.2/B1/B2/B6).
# SEM a env var, NADA muda — o deploy da E2 é INERTE até a E3 setar
# WTC_TENANT_DOMAIN na Render ANTES do DNS wildcard (settings-first — a
# armadilha do 400 DisallowedHost, memória wtc-dominio-whatthechip-app).
# Smoke local: WTC_TENANT_DOMAIN=localhost no .env (Chrome resolve
# eminer.localhost → 127.0.0.1 sozinho, sem tocar /etc/hosts).
WTC_TENANT_DOMAIN = os.environ.get('WTC_TENANT_DOMAIN', '').strip().lower()
if WTC_TENANT_DOMAIN:
    ALLOWED_HOSTS.append('.' + WTC_TENANT_DOMAIN)
    CSRF_TRUSTED_ORIGINS.append('https://*.' + WTC_TENANT_DOMAIN)
    if not DEBUG:
        # B5: o "login no apex → segue logado no subdomínio" exige o cookie no
        # domínio-PAI. É seguro AQUI porque o host só AFIRMA (§10.2): a empresa
        # continua vindo do Membership; host ≠ vínculo = 403 no middleware.
        # Em DEBUG fica host-only (cookie de domínio quebraria o login em
        # http://localhost puro — mesma razão do SESSION_COOKIE_SECURE acima).
        SESSION_COOKIE_DOMAIN = '.' + WTC_TENANT_DOMAIN
        CSRF_COOKIE_DOMAIN    = '.' + WTC_TENANT_DOMAIN

# Os outros 4 avisos do `check --deploy` foram avaliados e NO-OP de propósito:
#   W009 SECRET_KEY / W018 DEBUG — falso positivo do run LOCAL: em prod as env
#       vars DJANGO_SECRET_KEY e DEBUG=False do Render sobrescrevem o fallback.
#   W008 SECURE_SSL_REDIRECT — a borda da Render já redireciona http→https;
#       ligar aqui só acrescenta um salto extra dentro do gunicorn.
#   W004 SECURE_HSTS_SECONDS — redundante neste domínio: o TLD .app INTEIRO
#       está na lista HSTS preload dos navegadores, então o http já é recusado
#       antes de sair da máquina do usuário. Emitir o header não compra nada e
#       max-age longo é irreversível se um dia precisar de http em algum host.

INSTALLED_APPS = [
    # i18n do CMS (superfície 3 — I18N.md §9): colunas por idioma no pages.Page
    # (title_es, content_zh_hans…), fallback automático pro pt-br. ANTES do
    # admin (exigência do pacote: patcheia o ModelAdmin).
    'modeltranslation',
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
    # Sistema de preços (PRECIFICACAO.md, F2): Buyer/PriceList/Price por-empresa
    # (Buyer.company; RLS na pricing/0002) + PricingConfig global (singleton).
    'pricing',
    # Vendas (PRECIFICACAO §12.19, F11.2): Cotação → OV por lote (padrão Odoo);
    # tudo por-empresa (RLS na vendas/0002); menu admin-only.
    'vendas',
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
    # T7 (§10.2): resolve o HOST — "o host AFIRMA, o Membership CONCEDE".
    # DEPOIS do TenancyMiddleware (compara o host com request.company).
    # INERTE sem WTC_TENANT_DOMAIN. www → 301 apex (B6); slug desconhecido/
    # reservado/empresa inativa → 302 canônico; host de tenant troca a
    # URLconf pra core.urls_tenant (B1/B2) e host≠vínculo → 403.
    'tenancy.middleware.HostTenantMiddleware',
    # i18n: aplica a PREFERÊNCIA DE IDIOMA salva do usuário (tenancy.UserLanguage)
    # por CIMA da detecção do LocaleMiddleware. Cadeia final de resolução:
    # preferência no banco > cookie django_language > Accept-Language (região do
    # navegador) > pt-br. DEPOIS do AuthenticationMiddleware (precisa do user).
    # Ver I18N.md §3.
    'tenancy.middleware.UserLanguageMiddleware',
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
                # Câmbio vigente no header (PLANO_FX — dono 2026-08-01).
                'pricing.context_processors.fx',
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
    ('pt-br',   _('Português')),
    ('es',      _('Español')),
    ('en',      _('English')),
    ('zh-hans', _('中文')),      # chinês simplificado (locale/zh_Hans/)
]

# Onde o Django procura os catálogos .mo compilados (além dos de cada app).
LOCALE_PATHS = [BASE_DIR / 'locale']

# Cookie do seletor de idioma (set_language): persistente por 1 ano — a escolha
# do operador anônimo/da bancada sobrevive ao fechamento do navegador. O default
# do Django (None) expiraria na sessão do browser. Ver I18N.md §3 (cadeia).
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365

# modeltranslation (CMS): pt-br é a coluna-base e o fallback universal — página
# sem tradução aparece em PT (nunca em branco). Ver I18N.md §9.
MODELTRANSLATION_DEFAULT_LANGUAGE = 'pt-br'
MODELTRANSLATION_FALLBACK_LANGUAGES = ('pt-br',)

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
