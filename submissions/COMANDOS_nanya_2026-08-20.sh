#!/bin/bash
# Comandos Nanya — 20/08/2026 — 7 submissions, 25 known_parts, ZERO mudança de gramática
# Rode a partir da raiz do projeto (com venv ativo e DATABASE_URL apontando pro banco certo).

set -e

echo "=== 1/7 — NT5CC256M8GN (256M8, 2Gb, 4 PN) ==="
python manage.py submit_known_parts submissions/nanya_nt5cc_256m8_2026-08-20.yaml
python manage.py submit_known_parts submissions/nanya_nt5cc_256m8_2026-08-20.yaml --commit

echo "=== 2/7 — NT5CC256M16EREK (256M16, 4Gb, 4 PN) ==="
python manage.py submit_known_parts submissions/nanya_nt5cc_256m16_2026-08-20.yaml
python manage.py submit_known_parts submissions/nanya_nt5cc_256m16_2026-08-20.yaml --commit

echo "=== 3/7 — NT5CC64M16GPD1 (64M16 die G, 1Gb, 4 PN) ==="
python manage.py submit_known_parts submissions/nanya_nt5cc_64m16g_2026-08-20.yaml
python manage.py submit_known_parts submissions/nanya_nt5cc_64m16g_2026-08-20.yaml --commit

echo "=== 4/7 — NT5CB128M8CN (128M8, 1Gb, 4 PN) ==="
python manage.py submit_known_parts submissions/nanya_nt5cb_128m8_2026-08-20.yaml
python manage.py submit_known_parts submissions/nanya_nt5cb_128m8_2026-08-20.yaml --commit

echo "=== 5/7 — NT5CB128M16IPEK (128M16, 2Gb, 4 PN) ==="
python manage.py submit_known_parts submissions/nanya_nt5cb_128m16i_2026-08-20.yaml
python manage.py submit_known_parts submissions/nanya_nt5cb_128m16i_2026-08-20.yaml --commit

echo "=== 6/7 — NT5CB512M8BN (512M8, 4Gb, 2 PN — die real, organizacao corrigida do debug M4) ==="
python manage.py submit_known_parts submissions/nanya_nt5cb_512m8bn_2026-08-20.yaml
python manage.py submit_known_parts submissions/nanya_nt5cb_512m8bn_2026-08-20.yaml --commit

echo "=== 7/7 — NT5CB512M4BN (512M4, 2Gb, 3 PN — override Tier-2 autorizado por voce) ==="
python manage.py submit_known_parts submissions/nanya_nt5cb_512m4bn_2026-08-20.yaml
python manage.py submit_known_parts submissions/nanya_nt5cb_512m4bn_2026-08-20.yaml --commit

echo ""
echo "=== TUDO SUBMETIDO COMO 'submitted'. Falta: ==="
echo "1) Aprovar em /admin/chips/knownpart/ (filtro review_status -> Submetido)"
echo "2) Depois de aprovar, rodar:"
echo "   python manage.py guard_catalog"
