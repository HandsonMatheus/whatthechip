#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# TESTAR_TUDO.sh — a bateria inteira, num comando.
#
#   bash TESTAR_TUDO.sh            # tudo (a suíte usa banco de TESTE descartável;
#                                  #  a bancada simulada LÊ o seu banco de verdade)
#   bash TESTAR_TUDO.sh --rapido   # pula o censo do catálogo (o passo mais lento)
#
# NADA aqui escreve no seu banco. A suíte roda em SQLite descartável; a bancada
# simulada e o verificador rodam em transação revertida.
#
# Contra PRODUÇÃO: exporte o DATABASE_URL do Render antes de rodar — os passos
# 5, 6 e 7 vão medir a produção. Os passos 1-4 continuam em banco de teste.
# ─────────────────────────────────────────────────────────────────────────────
cd "$(dirname "$0")"
RAPIDO=0; [ "${1:-}" = "--rapido" ] && RAPIDO=1
FALHAS=(); PENDENTES=(); PASSOS=0

# Três desfechos, não dois. Saída 2 = "ainda não dá pra testar" (falta migração),
# que NÃO é a mesma coisa que "testei e falhou" — misturar as duas faz você
# procurar bug onde só falta rodar um comando.
passo() {                        # $1 = nome   resto = comando
  local nome="$1"; shift
  PASSOS=$((PASSOS+1))
  echo
  echo "┏━━ [$PASSOS] $nome"
  echo "┃   \$ $*"
  echo "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  "$@"; local rc=$?
  if [ $rc -eq 0 ]; then
    echo "   ✓ [$PASSOS] $nome — OK"
  elif [ $rc -eq 2 ]; then
    echo "   ⏸ [$PASSOS] $nome — PENDENTE (falta migração; veja acima)"
    PENDENTES+=("$nome")
  else
    echo "   ✗ [$PASSOS] $nome — FALHOU"
    FALHAS+=("$nome")
  fi
}

echo "═══════════════════════════════════════════════════════════════════════"
echo " BATERIA WhatTheChip — torneira origem × tipo"
echo " $(date '+%Y-%m-%d %H:%M')"
echo "═══════════════════════════════════════════════════════════════════════"

# ── 1-2: o código carrega e não há migração pendente ────────────────────────
passo "O projeto carrega (system check)" \
  python manage.py check --settings=core.settings_test

passo "Nenhuma migração pendente (o modelo bate com as migrações)" \
  python manage.py makemigrations --check --dry-run --settings=core.settings_test

# ── 3: a suíte do estoque, banco de teste descartável ───────────────────────
passo "Suíte do estoque (240 testes, banco de TESTE descartável)" \
  python manage.py test estoque --settings=core.settings_test

# ── 4: só a torneira, com o nome de cada garantia ───────────────────────────
passo "Só as garantias da torneira, uma a uma" \
  python manage.py test \
    estoque.tests.PoliticaOrigemDeclaracaoTests \
    estoque.tests.PoliticaOrigemRegraTests \
    estoque.tests.PoliticaOrigemBancadaTests \
    estoque.tests.PoliticaOrigemBackstopTests \
    --settings=core.settings_test -v2

# ── 5: a régua instalada no BANCO (read-only) ───────────────────────────────
passo "A régua no banco: 40 linhas e a torneira respondendo (READ-ONLY)" \
  python VERIFICAR_politica_origem.py

# ── 6: a bancada simulada com PN de verdade (read-only) ─────────────────────
passo "Bancada simulada: chips reais, origem por origem (READ-ONLY)" \
  python TESTAR_bancada.py --por-tipo 3

# ── 7: o censo — quanto material cada origem passa a barrar ─────────────────
if [ $RAPIDO -eq 0 ]; then
  passo "Censo do catálogo: quanto cada origem barra (READ-ONLY, demorado)" \
    python TESTAR_bancada.py --censo
else
  echo; echo "   · censo pulado (--rapido)"
fi

# ── veredito ────────────────────────────────────────────────────────────────
echo
echo "═══════════════════════════════════════════════════════════════════════"
if [ ${#FALHAS[@]} -eq 0 ] && [ ${#PENDENTES[@]} -gt 0 ]; then
  echo " ⏸ ${#PENDENTES[@]} passo(s) PENDENTE(S) — nada falhou, falta aplicar a migração:"
  for f in "${PENDENTES[@]}"; do echo "     · $f"; done
  echo
  echo "     python manage.py migrate estoque --plan     # o que vai rodar"
  echo "     python manage.py migrate estoque            # aplica (cria a tabela"
  echo "                                                 #  e semeia as 40 linhas)"
  echo "     bash TESTAR_TUDO.sh                         # e roda tudo de novo"
  exit 2
fi
if [ ${#FALHAS[@]} -eq 0 ]; then
  echo " ✓ TUDO PASSOU — $PASSOS passo(s)."
  echo
  echo " Lembrete do que ficou VERMELHO por motivo alheio a esta feature:"
  echo "   · chips.tests_i18n (2 erros) — 36 strings sem tradução nas telas do"
  echo "     comprador (partner_*), frente de outro chat. Rode"
  echo "     'python manage.py check_translations --settings=core.settings_test'"
  echo "     pra ver a lista; nenhuma delas é da torneira."
  exit 0
fi
echo " ✗ FALHOU em ${#FALHAS[@]} de $PASSOS passo(s):"
for f in "${FALHAS[@]}"; do echo "     · $f"; done
if [ ${#PENDENTES[@]} -gt 0 ]; then
  echo " ⏸ e ${#PENDENTES[@]} pendente(s) por falta de migração:"
  for f in "${PENDENTES[@]}"; do echo "     · $f"; done
fi
echo
echo " Leia a saída do passo que falhou — cada teste diz no docstring O QUE ele"
echo " protege e por quê, então a mensagem já explica o estrago."
exit 1
