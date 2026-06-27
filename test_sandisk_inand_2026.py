#!/usr/bin/env python
"""
test_sandisk_inand_2026.py
==========================
Testa os 59 KnownParts SanDisk iNAND adicionados em 2026-06-26 +
3 novas famílias gramaticais UFS (SDINDDH / SDINEDK / SDINFD) +
correção crítica SDINB (era UFS — agora eMMC 5.1) +
regressão sobre PNs pré-existentes no banco.

Uso (da raiz do projeto, venv ativo, DB populado):
    python test_sandisk_inand_2026.py
    python test_sandisk_inand_2026.py --only-fails
    python test_sandisk_inand_2026.py --section SDINB_CORR
    python test_sandisk_inand_2026.py --section GRAMMAR

Requisito:
    python manage.py fix_known_parts
    python manage.py populate_sandisk --overwrite
    (depois: reiniciar o servidor)

Seções de teste:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SANITY        PNs já existentes no banco (regressão — não podem quebrar)
  SDINB_CORR    Correção crítica: SDINB* deve ser eMMC 5.1, não UFS
  SDIN7DP       §A eMMC 4.51 iNAND Extreme BGA153 (4/8/16/32GB)
  SDIN7DU       §B eMMC 4.41 iNAND Ultra (caps adicionais 16/32GB)
  SDIN8DE       §C+D eMMC 4.51 HS200 BGA153 (8GB-only + alta cap)
  SDIN9DS       §E eMMC 5.0 HS400 BGA153 (8..64GB)
  SDIN9DW       §F eMMC 5.0 cap adicional 64GB
  SDIN5D        §G eMMC 4.41 X3/X2 MLC BGA153 (novas caps)
  SDIN5C1       §H eMMC 4.41 X3 MLC BGA169 (nova família inteira)
  SDINBDG       §I eMMC 5.1 iNAND 7250 (corrigido de UFS)
  SDINBDD       §J eMMC 5.1 iNAND 7350 3D NAND (corrigido de UFS)
  SDINBDA       §K eMMC 5.1 iNAND 7550 SmartSLC (corrigido de UFS)
  SDINDDH       §L UFS 2.1 iNAND 8521 (nova família)
  SDINEDK       §M UFS 3.0 iNAND MC EU511 (nova família)
  SDINFDK       §N UFS 3.1 iNAND MC EU551 (nova família)
  SDINFDO       §O UFS 3.1 iNAND MC EU551 variante (nova família)
  SDINFDQ       §P UFS 3.1 automotivo EU552 (nova família)
  EMCP          §Q+R eMCP LPDDR3/LPDDR4 SanDisk (SDADF / SDADA)
  GRAMMAR       PNs não confirmados no banco → deve acertar chip_type via gramática
  NEGATIVO      PNs que NÃO existem → devem vir NOT_FOUND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import argparse
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from chips.engine import classify  # noqa: E402

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
MAGENTA= "\033[95m"
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

# ─── Definição dos casos ────────────────────────────────────────────────────
#
# Campos:
#   pn            PN normalizado (uppercase, sem hífens/espaços)
#   chip_type     tipo esperado (str)
#   capacity      capacidade esperada — eMMC/UFS; omitir ou "" para eMCP
#   emcp_nand     campo emcp_nand esperado — apenas eMCP
#   emcp_ram      campo emcp_ram esperado  — apenas eMCP
#   interface     interface esperada (opcional; verifica se não vazia)
#   expect_known  True → deve acertar no banco (known_exact=True)
#                 False → gramática only (known_exact pode ser False)
#                 None  → NOT_FOUND esperado (known=False)
#   section       grupo de exibição
#   note          texto livre exibido no terminal
#
CASES = [

    # ═══════════════════════════════════════════════════════════════════════
    # SANITY — PNs já no banco antes desta sessão (regressão básica)
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDIN8DE28G",    chip_type="eMMC",  capacity="8GB",   interface="",        expect_known=True,  section="SANITY",   note="SDIN8DE2 — adicionado sessão anterior"),
    dict(pn="SDIN8DE216G",   chip_type="eMMC",  capacity="16GB",  interface="",        expect_known=True,  section="SANITY",   note="SDIN8DE2 — adicionado sessão anterior"),
    dict(pn="SDIN8DE232G",   chip_type="eMMC",  capacity="32GB",  interface="",        expect_known=True,  section="SANITY",   note="SDIN8DE2 — adicionado sessão anterior"),
    dict(pn="SDIN5C28G",     chip_type="eMMC",  capacity="8GB",   interface="",        expect_known=True,  section="SANITY",   note="SDIN5C2 X2 — adicionado sessão anterior"),
    dict(pn="SDIN5C216G",    chip_type="eMMC",  capacity="16GB",  interface="",        expect_known=True,  section="SANITY",   note="SDIN5C2 X2 — adicionado sessão anterior"),
    dict(pn="SDADB48K16G",   chip_type="eMCP",  capacity="",  emcp_nand="16GB", emcp_ram="LPDDR3 2GB", interface="", expect_known=True, section="SANITY", note="último PN SanDisk pré-sessão — é eMCP (não eMMC)"),

    # ═══════════════════════════════════════════════════════════════════════
    # SDINB_CORR — correção crítica: deve retornar eMMC (não UFS)
    # Antes do fix populate_sandisk + fix_known_parts → viria UFS 2.1/3.0.
    # Após o fix → eMMC 5.1 (DB exato OU gramática corrigida).
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDINBDG48G",    chip_type="eMMC",  capacity="8GB",   interface="eMMC 5.1", expect_known=True,  section="SDINB_CORR", note="iNAND 7250 — BUG CRÍTICO: era UFS"),
    dict(pn="SDINBDG416G",   chip_type="eMMC",  capacity="16GB",  interface="eMMC 5.1", expect_known=True,  section="SDINB_CORR", note="iNAND 7250"),
    dict(pn="SDINBDG432G",   chip_type="eMMC",  capacity="32GB",  interface="eMMC 5.1", expect_known=True,  section="SDINB_CORR", note="iNAND 7250 — Galaxy M20"),
    dict(pn="SDINBDG464G",   chip_type="eMMC",  capacity="64GB",  interface="eMMC 5.1", expect_known=True,  section="SDINB_CORR", note="iNAND 7250"),
    dict(pn="SDINBDD432G",   chip_type="eMMC",  capacity="32GB",  interface="eMMC 5.1", expect_known=True,  section="SDINB_CORR", note="iNAND 7350 3D NAND"),
    dict(pn="SDINBDD464G",   chip_type="eMMC",  capacity="64GB",  interface="eMMC 5.1", expect_known=True,  section="SDINB_CORR", note="iNAND 7350 — Huawei Nova 2s"),
    dict(pn="SDINBDD4128G",  chip_type="eMMC",  capacity="128GB", interface="eMMC 5.1", expect_known=True,  section="SDINB_CORR", note="iNAND 7350 3D NAND"),
    dict(pn="SDINBDD4256G",  chip_type="eMMC",  capacity="256GB", interface="eMMC 5.1", expect_known=True,  section="SDINB_CORR", note="iNAND 7350 flagship"),
    dict(pn="SDINBDA432G",   chip_type="eMMC",  capacity="32GB",  interface="eMMC 5.1", expect_known=True,  section="SDINB_CORR", note="iNAND 7550 SmartSLC"),
    dict(pn="SDINBDA464G",   chip_type="eMMC",  capacity="64GB",  interface="eMMC 5.1", expect_known=True,  section="SDINB_CORR", note="iNAND 7550 SmartSLC"),
    dict(pn="SDINBDA4128G",  chip_type="eMMC",  capacity="128GB", interface="eMMC 5.1", expect_known=True,  section="SDINB_CORR", note="iNAND 7550 — Honor 8X"),
    dict(pn="SDINBDA4256G",  chip_type="eMMC",  capacity="256GB", interface="eMMC 5.1", expect_known=True,  section="SDINB_CORR", note="iNAND 7550 SmartSLC Gen4"),

    # ═══════════════════════════════════════════════════════════════════════
    # §A — SDIN7DP eMMC 4.51 iNAND Extreme (BGA153, doc# 80-36-03494)
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDIN7DP24G",    chip_type="eMMC",  capacity="4GB",   interface="eMMC 4.51", expect_known=True,  section="SDIN7DP", note="Mouser Tier 1"),
    dict(pn="SDIN7DP28G",    chip_type="eMMC",  capacity="8GB",   interface="eMMC 4.51", expect_known=True,  section="SDIN7DP", note="Mouser Tier 1 — DP2 máx"),
    dict(pn="SDIN7DP416G",   chip_type="eMMC",  capacity="16GB",  interface="eMMC 4.51", expect_known=True,  section="SDIN7DP", note="HTC One Max; ⚠ package pendente"),
    dict(pn="SDIN7DP432G",   chip_type="eMMC",  capacity="32GB",  interface="eMMC 4.51", expect_known=True,  section="SDIN7DP", note="Mouser Tier 1"),

    # ═══════════════════════════════════════════════════════════════════════
    # §B — SDIN7DU eMMC 4.41 iNAND Ultra (doc# 80-36-03666)
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDIN7DU216G",   chip_type="eMMC",  capacity="16GB",  interface="eMMC 4.41", expect_known=True,  section="SDIN7DU", note="Mouser Tier 1"),
    dict(pn="SDIN7DU232G",   chip_type="eMMC",  capacity="32GB",  interface="eMMC 4.41", expect_known=True,  section="SDIN7DU", note="Mouser Tier 1"),

    # ═══════════════════════════════════════════════════════════════════════
    # §C+D — SDIN8DE1/4 eMMC 4.51 HS200 BGA153
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDIN8DE18G",    chip_type="eMMC",  capacity="8GB",   interface="eMMC 4.51", expect_known=True,  section="SDIN8DE", note="DE1 8GB-only, Huawei Honor 4X"),
    dict(pn="SDIN8DE18GI",   chip_type="eMMC",  capacity="8GB",   interface="eMMC 4.51", expect_known=True,  section="SDIN8DE", note="DE1 industrial -25..85°C"),
    dict(pn="SDIN8DE432G",   chip_type="eMMC",  capacity="32GB",  interface="eMMC 4.51", expect_known=True,  section="SDIN8DE", note="DE4 HTC One E8"),
    dict(pn="SDIN8DE464G",   chip_type="eMMC",  capacity="64GB",  interface="eMMC 4.51", expect_known=True,  section="SDIN8DE", note="DE4 alta capacidade"),

    # ═══════════════════════════════════════════════════════════════════════
    # §E — SDIN9DS2 eMMC 5.0 HS400 BGA153
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDIN9DS28G",    chip_type="eMMC",  capacity="8GB",   interface="eMMC 5.0", expect_known=True,  section="SDIN9DS", note="Avnet BGA153"),
    dict(pn="SDIN9DS216G",   chip_type="eMMC",  capacity="16GB",  interface="eMMC 5.0", expect_known=True,  section="SDIN9DS", note="HTC Desire 630"),
    dict(pn="SDIN9DS232G",   chip_type="eMMC",  capacity="32GB",  interface="eMMC 5.0", expect_known=True,  section="SDIN9DS", note="Tier 1 product brief"),
    dict(pn="SDIN9DS264G",   chip_type="eMMC",  capacity="64GB",  interface="eMMC 5.0", expect_known=True,  section="SDIN9DS", note="Tier 1 product brief"),

    # ═══════════════════════════════════════════════════════════════════════
    # §F — SDIN9DW4 cap adicional 64GB (doc# 80-36-03680 rev1.11)
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDIN9DW464G",   chip_type="eMMC",  capacity="64GB",  interface="eMMC 5.0", expect_known=True,  section="SDIN9DW", note="datasheet rev1.11 família 16/32/64GB ONLY"),

    # ═══════════════════════════════════════════════════════════════════════
    # §G — SDIN5D1/D2 eMMC 4.41 X3/X2 MLC BGA153 (doc# 80-36-03462)
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDIN5D14G",     chip_type="eMMC",  capacity="4GB",   interface="eMMC 4.41", expect_known=True,  section="SDIN5D", note="X3 MLC BGA153"),
    dict(pn="SDIN5D18G",     chip_type="eMMC",  capacity="8GB",   interface="eMMC 4.41", expect_known=True,  section="SDIN5D", note="X3 MLC BGA153"),
    dict(pn="SDIN5D116G",    chip_type="eMMC",  capacity="16GB",  interface="eMMC 4.41", expect_known=True,  section="SDIN5D", note="X3 MLC BGA153"),
    dict(pn="SDIN5D24G",     chip_type="eMMC",  capacity="4GB",   interface="eMMC 4.41", expect_known=True,  section="SDIN5D", note="X2 MLC BGA153"),
    dict(pn="SDIN5D28G",     chip_type="eMMC",  capacity="8GB",   interface="eMMC 4.41", expect_known=True,  section="SDIN5D", note="X2 MLC BGA153"),
    dict(pn="SDIN5D216G",    chip_type="eMMC",  capacity="16GB",  interface="eMMC 4.41", expect_known=True,  section="SDIN5D", note="X2 MLC BGA153"),

    # ═══════════════════════════════════════════════════════════════════════
    # §H — SDIN5C1 eMMC 4.41 X3 MLC BGA169 (nova família, doc# 80-36-03433)
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDIN5C14G",     chip_type="eMMC",  capacity="4GB",   interface="eMMC 4.41", expect_known=True,  section="SDIN5C1", note="X3 BGA169 — irmã da SDIN5C2 X2"),
    dict(pn="SDIN5C18G",     chip_type="eMMC",  capacity="8GB",   interface="eMMC 4.41", expect_known=True,  section="SDIN5C1", note="X3 BGA169"),
    dict(pn="SDIN5C116G",    chip_type="eMMC",  capacity="16GB",  interface="eMMC 4.41", expect_known=True,  section="SDIN5C1", note="X3 BGA169"),
    dict(pn="SDIN5C132G",    chip_type="eMMC",  capacity="32GB",  interface="eMMC 4.41", expect_known=True,  section="SDIN5C1", note="X3 BGA169"),
    dict(pn="SDIN5C164G",    chip_type="eMMC",  capacity="64GB",  interface="eMMC 4.41", expect_known=True,  section="SDIN5C1", note="X3 BGA169 — maior cap família"),

    # ═══════════════════════════════════════════════════════════════════════
    # §L — SDINDDH UFS 2.1 iNAND 8521 (nova família gramatical)
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDINDDH432G",   chip_type="UFS",   capacity="32GB",  interface="UFS 2.1", expect_known=True,  section="SDINDDH", note="iNAND 8521 PB03 Tier 1"),
    dict(pn="SDINDDH464G",   chip_type="UFS",   capacity="64GB",  interface="UFS 2.1", expect_known=True,  section="SDINDDH", note="iNAND 8521 PB03 Tier 1"),
    dict(pn="SDINDDH4128G",  chip_type="UFS",   capacity="128GB", interface="UFS 2.1", expect_known=True,  section="SDINDDH", note="~500MB/s"),
    dict(pn="SDINDDH4256G",  chip_type="UFS",   capacity="256GB", interface="UFS 2.1", expect_known=True,  section="SDINDDH", note="topo da família consumer"),
    dict(pn="SDINDDH664GI",  chip_type="UFS",   capacity="64GB",  interface="UFS 2.1", expect_known=True,  section="SDINDDH", note="iNAND IX EU312 industrial [distributor]"),

    # ═══════════════════════════════════════════════════════════════════════
    # §M — SDINEDK UFS 3.0 iNAND MC EU511
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDINEDK4128G",  chip_type="UFS",   capacity="128GB", interface="UFS 3.0", expect_known=True,  section="SDINEDK", note="EU511 Gear4 ~800MB/s"),
    dict(pn="SDINEDK4256G",  chip_type="UFS",   capacity="256GB", interface="UFS 3.0", expect_known=True,  section="SDINEDK", note="EU511"),
    dict(pn="SDINEDK4512G",  chip_type="UFS",   capacity="512GB", interface="UFS 3.0", expect_known=True,  section="SDINEDK", note="EU511 [distributor]"),

    # ═══════════════════════════════════════════════════════════════════════
    # §N — SDINFDK UFS 3.1 iNAND MC EU551
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDINFDK4128G",  chip_type="UFS",   capacity="128GB", interface="UFS 3.1", expect_known=True,  section="SDINFDK", note="EU551 WriteBooster"),
    dict(pn="SDINFDK4256G",  chip_type="UFS",   capacity="256GB", interface="UFS 3.1", expect_known=True,  section="SDINFDK", note="EU551"),
    dict(pn="SDINFDK464G",   chip_type="UFS",   capacity="64GB",  interface="UFS 3.1", expect_known=True,  section="SDINFDK", note="EU551 [distributor]"),
    dict(pn="SDINFDK4512G",  chip_type="UFS",   capacity="512GB", interface="UFS 3.1", expect_known=True,  section="SDINFDK", note="EU551 [distributor]"),

    # ═══════════════════════════════════════════════════════════════════════
    # §O — SDINFDO UFS 3.1 iNAND MC EU551 variante
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDINFDO4128G",  chip_type="UFS",   capacity="128GB", interface="UFS 3.1", expect_known=True,  section="SDINFDO", note="EU551 variante PDP"),
    dict(pn="SDINFDO4256G",  chip_type="UFS",   capacity="256GB", interface="UFS 3.1", expect_known=True,  section="SDINFDO", note="EU551 variante PDP"),
    dict(pn="SDINFDO4512G",  chip_type="UFS",   capacity="512GB", interface="UFS 3.1", expect_known=True,  section="SDINFDO", note="EU551 variante PDP"),

    # ═══════════════════════════════════════════════════════════════════════
    # §P — SDINFDQ UFS 3.1 automotivo iNAND AT EU552
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDINFDQ664GXA1",    chip_type="UFS", capacity="64GB",  interface="UFS 3.1", expect_known=True, section="SDINFDQ", note="automotive AEC -XA1 [distributor]"),
    dict(pn="SDINFDQ6128GZA1",   chip_type="UFS", capacity="128GB", interface="UFS 3.1", expect_known=True, section="SDINFDQ", note="automotive AEC -ZA1 [distributor]"),
    dict(pn="SDINFDQ6256GZA1",   chip_type="UFS", capacity="256GB", interface="UFS 3.1", expect_known=True, section="SDINFDQ", note="automotive AEC -ZA1 [distributor]"),
    dict(pn="SDINFDQ6512GZA1",   chip_type="UFS", capacity="512GB", interface="UFS 3.1", expect_known=True, section="SDINFDQ", note="automotive AEC -ZA1 [distributor]"),

    # ═══════════════════════════════════════════════════════════════════════
    # §Q+R — eMCP SanDisk (SDADF LPDDR3 / SDADA LPDDR4)
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDADF4AP16G",   chip_type="eMCP",  capacity="",  emcp_nand="16GB", emcp_ram="LPDDR3 2GB", expect_known=True,  section="EMCP", note="SDADF 16+2 221-ball LPDDR3 [distributor]"),
    dict(pn="SDADA4DR64G",   chip_type="eMCP",  capacity="",  emcp_nand="64GB", emcp_ram="LPDDR4 4GB", expect_known=True,  section="EMCP", note="SDADA 64+4 254-ball LPDDR4 [distributor] ⚠ LP4 provisional"),

    # ═══════════════════════════════════════════════════════════════════════
    # GRAMMAR — PNs NÃO no banco → devem acertar chip_type via gramática
    # ═══════════════════════════════════════════════════════════════════════

    # SDINB grammar corrigida → eMMC (não UFS!)
    dict(pn="SDINBEG4128G",  chip_type="eMMC",  capacity="",  interface="", expect_known=False, section="GRAMMAR", note="SDINBEG4 — não confirmado; gramática SDINB deve dar eMMC"),
    dict(pn="SDINBEG5256G",  chip_type="eMMC",  capacity="",  interface="", expect_known=False, section="GRAMMAR", note="SDINBEG5 — gramática SDINB eMMC 5.1"),

    # Famílias eMMC clássicas (SDIN genérico)
    dict(pn="SDIN7DP464G",   chip_type="eMMC",  capacity="",  interface="", expect_known=False, section="GRAMMAR", note="DP4 64GB — só Tier 3; gramática SDIN → eMMC"),
    dict(pn="SDIN8DE416G",   chip_type="eMMC",  capacity="",  interface="", expect_known=False, section="GRAMMAR", note="DE4 16GB — não confirmado Tier 1; gramática eMMC"),
    dict(pn="SDIN9DS28G",    chip_type="eMMC",  capacity="",  interface="", expect_known=True,  section="GRAMMAR", note="já no banco — redundante mas valida priority"),

    # Novas famílias UFS → deve resolver pelo prefixo exato
    dict(pn="SDINDDH4512G",  chip_type="UFS",   capacity="",  interface="", expect_known=False, section="GRAMMAR", note="DDH 512GB — não no banco; gramática SDINDDH → UFS 2.1"),
    dict(pn="SDINFDK464GI",  chip_type="UFS",   capacity="",  interface="", expect_known=False, section="GRAMMAR", note="SDINFDK industrial variant — gramática SDINFD → UFS 3.1"),

    # SDMAG (família placeholder existente)
    dict(pn="SDMAG4G",       chip_type="eMMC",  capacity="",  interface="", expect_known=False, section="GRAMMAR", note="SDMAG placeholder — gramática eMMC"),

    # ═══════════════════════════════════════════════════════════════════════
    # GRAMMAR_EXCL — PNs excluídos do banco intencionalmente, mas que
    # BATEM na gramática aberta (SDIN → eMMC, SDAD → eMCP).
    # Comportamento CORRETO: engine retorna chip_type via família gramatical.
    # ⚠ NÃO são casos NEGATIVO — a gramática SanDisk é open-ended por design.
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDIN7DU264G",   chip_type="eMMC",  capacity="",  interface="", expect_known=False, section="GRAMMAR_EXCL", note="DU2 64GB (família máx=32GB) — excluído DB; gramática SDIN→eMMC correto"),
    dict(pn="SDIN5D12G",     chip_type="eMMC",  capacity="",  interface="", expect_known=False, section="GRAMMAR_EXCL", note="D1 2GB suspeito (X2 em família X3) — excluído DB; gramática SDIN→eMMC"),
    dict(pn="SDADEP4G",      chip_type="eMCP",  capacity="",  interface="", expect_known=False, section="GRAMMAR_EXCL", note="SDADEP não existe no DB; gramática SDAD→eMCP (família aberta)"),

    # ═══════════════════════════════════════════════════════════════════════
    # NEGATIVO — PNs com prefixo completamente desconhecido.
    # DEVEM retornar known=False (sem gramática, sem DB hit).
    # Usar prefixos fora do namespace SanDisk e de qualquer outra marca.
    # ═══════════════════════════════════════════════════════════════════════
    dict(pn="SDIGTEST128G",  chip_type="",      capacity="",  interface="", expect_known=None,  section="NEGATIVO", note="SDIG* não existe em nenhuma família — NOT_FOUND esperado"),
    dict(pn="FAKEPART4G",    chip_type="",      capacity="",  interface="", expect_known=None,  section="NEGATIVO", note="prefixo completamente desconhecido — NOT_FOUND esperado"),
]


# ─── Helpers ───────────────────────────────────────────────────────────────

def norm_cap(s):
    """Normaliza capacidade: '32 GB' == '32GB' == '32gb'."""
    return (s or "").strip().upper().replace(" ", "")


def fmt_result(r):
    parts = []
    ct = r.get("chip_type") or ""
    if ct:
        parts.append(ct)
    cap = r.get("capacity") or ""
    en  = r.get("emcp_nand") or ""
    er  = r.get("emcp_ram") or ""
    if en:
        parts.append(f"nand={en}")
    if er:
        parts.append(f"ram={er}")
    if cap:
        parts.append(cap)
    iface = r.get("interface") or ""
    if iface:
        parts.append(iface)
    conf = r.get("confidence") or ""
    if conf:
        parts.append(f"[{conf}]")
    if r.get("known_exact"):
        parts.append("via=db_exact")
    elif r.get("known"):
        parts.append("via=db")
    elif not r.get("known"):
        parts.append("via=NOT_FOUND")
    return " | ".join(parts) if parts else "(sem resultado)"


def check(case, result):
    """Retorna lista de problemas (strings). Vazia = OK."""
    issues = []

    known = result.get("known", False)
    known_exact = result.get("known_exact", False)
    expect_known = case.get("expect_known")

    # ── verificar presença no banco ─────────────────────────────────────
    if expect_known is None:
        # caso NEGATIVO: deve ser não encontrado
        if known:
            issues.append(f"esperava NOT_FOUND mas engine retornou known=True (via={'db_exact' if known_exact else 'grammar'})")
        return issues  # não checar mais nada para caso negativo

    if expect_known is True and not known:
        issues.append("esperava hit no banco (known=True) mas engine retornou NOT_FOUND")
        return issues

    # ── chip_type ────────────────────────────────────────────────────────
    exp_ct = (case.get("chip_type") or "").strip().lower()
    got_ct = (result.get("chip_type") or "").strip().lower()
    if exp_ct and got_ct and exp_ct != got_ct:
        issues.append(f"chip_type: esperado={exp_ct!r} engine={got_ct!r}")

    # ── known_exact (só para expect_known=True) ─────────────────────────
    if expect_known is True and not known_exact:
        issues.append(f"esperava known_exact=True (hit DB) mas engine retornou known_exact=False — rode fix_known_parts?")

    # ── capacity (eMMC / UFS) ────────────────────────────────────────────
    exp_cap = norm_cap(case.get("capacity", ""))
    got_cap = norm_cap(result.get("capacity", ""))
    if exp_cap and got_cap and exp_cap != got_cap:
        issues.append(f"capacity: esperado={exp_cap!r} engine={got_cap!r}")

    # ── emcp_nand ────────────────────────────────────────────────────────
    exp_nand = norm_cap(case.get("emcp_nand", ""))
    got_nand = norm_cap(result.get("emcp_nand", ""))
    if exp_nand and got_nand and exp_nand != got_nand:
        issues.append(f"emcp_nand: esperado={exp_nand!r} engine={got_nand!r}")

    # ── emcp_ram ─────────────────────────────────────────────────────────
    exp_ram = (case.get("emcp_ram") or "").strip().lower()
    got_ram = (result.get("emcp_ram") or "").strip().lower()
    if exp_ram and got_ram and exp_ram != got_ram:
        issues.append(f"emcp_ram: esperado={exp_ram!r} engine={got_ram!r}")

    return issues


# ─── Runner ────────────────────────────────────────────────────────────────

SECTION_COLORS = {
    "SANITY":        CYAN,
    "SDINB_CORR":    MAGENTA,
    "GRAMMAR":       YELLOW,
    "GRAMMAR_EXCL":  YELLOW,
    "NEGATIVO":      DIM,
    "EMCP":          CYAN,
}

def section_color(sec):
    return SECTION_COLORS.get(sec, "")


def run(only_fails, section_filter):
    cases = CASES
    if section_filter:
        cases = [c for c in cases if c["section"].upper() == section_filter.upper()]
        if not cases:
            print(f"{RED}Seção não encontrada: {section_filter!r}{RESET}")
            avail = sorted({c["section"] for c in CASES})
            print(f"Disponíveis: {', '.join(avail)}")
            sys.exit(1)

    total = len(cases)
    ok = fail = skip_grammar = 0

    # agrupar por seção para cabeçalho
    sections_seen = []
    for c in cases:
        if c["section"] not in sections_seen:
            sections_seen.append(c["section"])

    print(f"\n{BOLD}{'━'*78}{RESET}")
    print(f"{BOLD}  SanDisk iNAND 2026 — {total} casos  |  seções: {', '.join(sections_seen)}{RESET}")
    print(f"{BOLD}{'━'*78}{RESET}\n")

    current_section = None
    for case in cases:
        sec = case["section"]
        if sec != current_section:
            current_section = sec
            sc = section_color(sec)
            print(f"\n{sc}{BOLD}  ── {sec} {'─'*(60-len(sec))}{RESET}")

        pn   = case["pn"]
        note = case.get("note", "")
        exp_known = case.get("expect_known")

        try:
            result = classify(pn)
        except Exception as e:
            fail += 1
            print(f"{RED}  ✗ {pn:<46}  EXCEPTION: {e}{RESET}")
            continue

        issues = check(case, result)
        fmt = fmt_result(result)

        # caso negativo: verde se NOT_FOUND, vermelho se achou
        if exp_known is None:
            known = result.get("known", False)
            if not known:
                ok += 1
                if not only_fails:
                    print(f"{GREEN}  ✓ {pn:<46}  NOT_FOUND (correto){RESET}")
                    if note:
                        print(f"{DIM}      {note}{RESET}")
            else:
                fail += 1
                print(f"{RED}  ✗ {pn:<46}  {fmt}  ← DEVERIA ser NOT_FOUND!{RESET}")
                if note:
                    print(f"{DIM}      {note}{RESET}")
            continue

        # caso grammar-only (expect_known=False): não exigir known_exact
        if exp_known is False and not result.get("known"):
            skip_grammar += 1
            if not only_fails:
                print(f"{YELLOW}  ○ {pn:<46}  NOT_IN_DB (grammar only, {fmt}){RESET}")
                if note:
                    print(f"{DIM}      {note}{RESET}")
            continue

        if issues:
            fail += 1
            print(f"{RED}  ✗ {pn:<46}  {fmt}{RESET}")
            for iss in issues:
                print(f"{RED}       ↳ {iss}{RESET}")
            if note:
                print(f"{DIM}       ✎ {note}{RESET}")
        else:
            ok += 1
            if not only_fails:
                sc = section_color(sec)
                print(f"{GREEN}  ✓ {pn:<46}  {fmt}{RESET}")
                if note:
                    print(f"{DIM}      {note}{RESET}")

    print(f"\n{BOLD}{'━'*78}{RESET}")
    pct = round(ok / total * 100) if total else 0
    status_color = GREEN if fail == 0 else RED

    print(
        f"{status_color}{BOLD}  RESULTADO: {ok}/{total} OK ({pct}%)  "
        f"|  falhas={fail}  grammar_not_in_db={skip_grammar}{RESET}"
    )

    if fail == 0:
        if skip_grammar > 0:
            print(f"\n{YELLOW}{BOLD}  ⚠ {skip_grammar} PN(s) grammar-only: rode fix_known_parts e re-teste para forçar DB hit.{RESET}")
        else:
            print(f"\n{GREEN}{BOLD}  ✅ TUDO OK — banco e gramática SanDisk alinhados.{RESET}")
    else:
        print(f"\n{RED}{BOLD}  ❌ {fail} falha(s). Revisar seções acima antes de confiar no banco.{RESET}")

    print(f"{BOLD}{'━'*78}{RESET}\n")
    return fail


# ─── Entry-point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Testa expansão SanDisk iNAND 2026 contra o engine WTC."
    )
    parser.add_argument(
        "--only-fails",
        action="store_true",
        help="Exibir só falhas (suprime linhas ✓)",
    )
    parser.add_argument(
        "--section",
        metavar="NOME",
        default="",
        help="Filtrar por seção (ex: SDINB_CORR, GRAMMAR, EMCP, etc.)",
    )
    args = parser.parse_args()

    fail_count = run(
        only_fails=args.only_fails,
        section_filter=args.section,
    )
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
