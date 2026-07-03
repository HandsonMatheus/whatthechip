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

echo "━━ 1/3 — Migrations ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python manage.py migrate

echo ""
echo "━━ 2/3 — GRAMÁTICA (load_brands das 10 marcas + doc pages + índice + PSG) ━━"
# Opção 2: os yamls carregam SÓ a gramática (famílias+mapas). Os known_parts vivem
# no banco (fonte da verdade) — aqui só damos partida num banco VAZIO com o seed curado.
python manage.py deploy_catalog --commit

echo ""
echo "━━ 3/3 — SEED de known_parts (bootstrap de banco vazio; gap-fill, não re-sincroniza) ━━"
# Seed curado (~600 PNs) só pra dev/CI ter dados. Prod NUNCA faz isso — carrega o banco
# existente adiante (backup). É gap-fill: só cria os que faltam, seguro rodar de novo.
python manage.py restore_known_parts seed_known_parts.json --commit

echo ""
echo "✅ WhatTheChip pronto. Próximos passos:"
echo "   python manage.py createsuperuser   # acesso ao /admin/"
echo "   python manage.py runserver         # http://localhost:8000"
echo ""
echo "   (Catálogo Micron completo via CSV, opcional e local: python manage.py import_micron_catalog *_full-catalog.csv)"
