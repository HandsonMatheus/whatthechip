#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# WhatTheChip — setup local do sistema de classificação (v1.0.0-beta)
#
# Deixa o app operacional a partir de um banco VAZIO, em 2 passos:
#   1. migrations (cria o schema)
#   2. deploy_catalog (carrega o catálogo das 10 marcas a partir dos
#      chips/knowledge/<marca>.yaml → famílias + decode maps + known_parts,
#      vincula as páginas de doc, sincroniza o índice, e sobe o catalog_version)
#
# Uso:  bash setup.sh   (da raiz do projeto, com o venv ativo e o Postgres no ar)
# ─────────────────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
[ -f manage.py ] || { echo "❌ manage.py não encontrado — rode este script da raiz do projeto"; exit 1; }

echo "━━ 1/2 — Migrations ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python manage.py migrate

echo ""
echo "━━ 2/2 — Catálogo (load_brands das 10 marcas + doc pages + índice + PSG) ━━"
python manage.py deploy_catalog --commit

echo ""
echo "✅ WhatTheChip pronto. Próximos passos:"
echo "   python manage.py createsuperuser   # acesso ao /admin/"
echo "   python manage.py runserver         # http://localhost:8000"
echo ""
echo "   (Catálogo Micron completo via CSV, opcional e local: python manage.py import_micron_catalog *_full-catalog.csv)"
