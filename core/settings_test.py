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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME":   ":memory:",
    }
}
