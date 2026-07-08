"""
settings_test.py — Configurações para rodar os testes sem PostgreSQL.

Usa SQLite em memória para que os testes funcionem em qualquer máquina
sem precisar de um servidor de banco de dados.

Como usar:
    python manage.py test chips --settings=core.settings_test
    # ou defina a variável de ambiente:
    DJANGO_SETTINGS_MODULE=core.settings_test python manage.py test chips
"""

from .settings import *  # noqa: F401, F403 — herda tudo

# Isola a cache do engine (lru_cache por catalog_version) entre testes: em prod a
# versão é monotônica, mas o banco de teste reinicia e os números colidem entre
# casos → suíte instável por ORDEM. O runner limpa a cache antes de cada teste.
# Ver core/test_runner.py. (Só testes; produção nunca usa este settings.)
TEST_RUNNER = "core.test_runner.EngineCacheIsolationRunner"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME":   ":memory:",
    }
}

# pghistory/pgtrigger (passo 3): os gatilhos são Postgres-only. No SQLite dos
# testes, tanto o patch do schema editor do pgtrigger quanto o middleware de
# contexto do pghistory chamam um método do psycopg (get_transaction_status) que
# o SQLite não tem → erro. Como o SQLite não tem gatilho pra consumir nada disso,
# desligamos os dois SÓ nos testes. Produção (Postgres) mantém tudo ligado.
#   1) o patch do schema editor (doc oficial recomenda False quando dá erro):
PGTRIGGER_SCHEMA_EDITOR = False
#   2) o middleware HistoryMiddleware (injeta o "quem" p/ os gatilhos capturarem):
MIDDLEWARE = [m for m in MIDDLEWARE if "pghistory" not in m]  # noqa: F405
