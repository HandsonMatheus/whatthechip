#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# WhatTheChip — Setup de ativação do sistema de classificação de chips
#
# Roda todos os passos necessários para deixar o sistema 100% operacional:
#   1. Migrations do banco
#   2. Importação dos dados do chipid (famílias + PNs)
#   3. Famílias das demais marcas (SK Hynix, Micron, KIOXIA, Nanya, Kingston)
#   4. Vinculação das famílias às páginas de documentação
#
# Uso:
#   cd chipdocs/
#   bash setup.sh
#
# ─────────────────────────────────────────────────────────────────────────────

set -e   # para no primeiro erro

# ── Caminhos do chipid ────────────────────────────────────────────────────────
# Os dados do chipid foram copiados para WhatTheChip/chipid_data/ para não
# depender do local original. Ajuste se você moveu os arquivos.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHIPID_SQLITE="${SCRIPT_DIR}/../chipid_data/db.sqlite3"
CHIPID_STATE="${SCRIPT_DIR}/../chipid_data/state"

# ── Cores ─────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}✅ $1${RESET}"; }
warn() { echo -e "${YELLOW}⚠  $1${RESET}"; }
fail() { echo -e "${RED}❌ $1${RESET}"; exit 1; }
step() { echo -e "\n${YELLOW}━━ $1 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"; }

# ── Verificações iniciais ─────────────────────────────────────────────────────
step "Verificando pré-requisitos"

[ -f "$SCRIPT_DIR/manage.py" ] || fail "manage.py não encontrado — rode este script de dentro de chipdocs/"

if [ ! -f "$CHIPID_SQLITE" ]; then
    warn "db.sqlite3 do chipid não encontrado em: $CHIPID_SQLITE"
    warn "Pulando import_chipid — adicione os dados manualmente depois."
    SKIP_IMPORT=1
else
    ok "chipid db.sqlite3 encontrado"
fi

if [ ! -d "$CHIPID_STATE" ]; then
    warn "Pasta state/ do chipid não encontrada em: $CHIPID_STATE"
    SKIP_IMPORT=1
else
    ok "chipid state/ encontrado"
fi

# ── Passo 1: migrate ──────────────────────────────────────────────────────────
step "1/4 — Rodando migrations"
python manage.py migrate
ok "Migrations aplicadas"

# ── Passo 2: import_chipid ────────────────────────────────────────────────────
step "2/4 — Importando dados do chipid"
if [ "${SKIP_IMPORT}" = "1" ]; then
    warn "Pulado (arquivos não encontrados)"
else
    python manage.py import_chipid \
        --sqlite "$CHIPID_SQLITE" \
        --state-dir "$CHIPID_STATE"
    ok "Dados do chipid importados"
fi

# ── Passo 3: add_chip_families ────────────────────────────────────────────────
step "3/4 — Adicionando famílias SK Hynix, Micron, KIOXIA, Nanya, Kingston"
python manage.py add_chip_families
ok "Famílias adicionadas"

# ── Passo 4: link_doc_pages ───────────────────────────────────────────────────
step "4/4 — Vinculando famílias às páginas de documentação"
python manage.py link_doc_pages
ok "Famílias vinculadas às páginas"

# ── Resumo ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}  WhatTheChip — sistema de classificação ativo!  ${RESET}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo "Próximos passos opcionais:"
echo "  • Enriquecer PNs raw:  cd scripts && python enrich_gemini.py --brand Samsung --limit 50"
echo "  • Coletar novos PNs:   cd scripts && python collect_pns.py --brand 'SK Hynix'"
echo "  • Admin:               python manage.py runserver → /admin/chips/"
echo ""
