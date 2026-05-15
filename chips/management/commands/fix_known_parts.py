"""
fix_known_parts.py
===================
Corrige registros KnownPart com dados sujos vindos de distribuidores externos.

Cada entrada em CORRECTIONS define o part_number a corrigir e os campos a
atualizar. Campos com valor None são limpos (string vazia no banco).

Idempotente: pode ser rodado múltiplas vezes sem efeitos colaterais.

Uso:
    python manage.py fix_known_parts
    python manage.py fix_known_parts --dry-run    # mostra mudanças sem salvar
    python manage.py fix_known_parts --pn KMDP6001DA  # corrige só um PN
"""

from django.core.management.base import BaseCommand
from django.db import transaction


# ── Tabela de correções ───────────────────────────────────────────────────────
#
# Formato de cada entrada:
#   {
#     "pn":      "<part number exato>",
#     "fields":  { "<campo>": "<novo valor>" },   # None = limpar o campo
#     "reason":  "<explicação da correção>",
#   }
#
# Campos suportados: emcp_ram, emcp_nand, device, confidence, status
# ─────────────────────────────────────────────────────────────────────────────

CORRECTIONS = [

    # ── KMDP6001DA ────────────────────────────────────────────────────────────
    # Problema: banco continha dados do distribuidor Censtry (lixo).
    #   emcp_ram = "LPDDR4X 6GB"  → ERRADO. Datasheet: 32Gb ÷ 8 = 4GB.
    #   device   = "Galaxy MX6432" → ERRADO. Não existe esse celular.
    #              MX6432 é código interno Samsung do encapsulamento
    #              (64 = 64GB eMMC, 32 = 32Gb RAM). Fontes reais de uso:
    #              tablets e mid-range de terceiros (Oppo, Vivo, etc).
    # Correção: P6 agora mapeado no SAM_EMCP_CAP (populate_samsung.py).
    #           Este fix limpa o registro sujo para que a gramática vença
    #           na próxima classificação sem herdar a capacidade errada do DB.
    {
        "pn": "KMDP6001DA",
        "fields": {
            "emcp_ram": "LPDDR4X 4GB",
            "device":   "",             # limpar — "Galaxy MX6432" não existe
        },
        "reason": (
            "RAM corrigida: 32Gb ÷ 8 = 4GB (era 6GB do distribuidor Censtry). "
            "Device apagado: 'Galaxy MX6432' é código interno Samsung, não celular."
        ),
    },

    # ── KMQD60013M ───────────────────────────────────────────────────────────
    # Chip físico confirmado na esteira (eMiner 2026-05-13).
    # D6 = 32GB eMMC 5.1 + 3GB LPDDR3.
    # create=True: raw_in_db=False no debug → pode não existir no banco ainda.
    {
        "pn": "KMQD60013M",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 5.1 32GB",
            "emcp_ram":  "LPDDR3 3GB",
        },
        "reason": (
            "Chip físico confirmado na esteira (eMiner 2026-05-13). "
            "D6 = 32GB eMMC 5.1 + 3GB LPDDR3. "
            "create=True: cria registro confirmado se ainda não existir no banco."
        ),
    },

    # ── KMRNW0001M ───────────────────────────────────────────────────────────
    # Problema: banco continha resultado alucinado pelo Gemini (confidence=ai_high).
    #   emcp_nand = "eMMC 5.1 64GB" → ERRADO. NW = 8GB NAND (chip entry-level).
    #   emcp_ram  = "LPDDR4/4X 4GB" → ERRADO. NW = 1GB RAM.
    # NW é cap_key de chip entry-level (Galaxy A budget 2018-2019), destino resíduo.
    # Após adicionar NW ao SAM_EMCP_CAP, a gramática vence sozinha (grammar_wins=True).
    # Este fix limpa o registro alucinado para consistência histórica no banco.
    {
        "pn": "KMRNW0001M",
        "fields": {
            "emcp_nand": "eMMC 5.1 8GB",
            "emcp_ram":  "LPDDR4/4X 1GB",
            "device":    "",
        },
        "reason": (
            "Gemini alucinado: dizia eMMC 5.1 64GB + LPDDR4/4X 4GB. "
            "Correto: NW = 8GB NAND + 1GB RAM (chip entry-level, resíduo). "
            "NW adicionado ao SAM_EMCP_CAP — gramática resolve diretamente."
        ),
    },

    # ── KLUDG4U1EA ───────────────────────────────────────────────────────────
    # Problema: banco continha resultado alucinado pelo Gemini (confidence=ai_high)
    # com brand classificado como Kioxia (família KLUDG estava cadastrada errado
    # em add_chip_families.py como Kioxia). KLUDG é Samsung UFS 2.1.
    # Decodificação correta pela gramática:
    #   K=Samsung, L=NAND standalone, U=UFS, D=128GB (SAM_FLASH_CAP), G=TLC NAND,
    #   pn[6]='U' → UFS 2.1/3.0 → capacity = 128GB, interface = UFS 2.1.
    # Após populate_samsung --overwrite, a família KLUDG é migrada para brand=Samsung.
    # Este fix limpa campos que o Gemini pode ter preenchido incorretamente.
    {
        "pn": "KLUDG4U1EA",
        "fields": {
            "capacity": "128GB",
            "interface": "UFS 2.1",
            "device":    "",   # limpar device alucinado, se houver
        },
        "reason": (
            "Família KLUDG estava cadastrada como Kioxia (erro em add_chip_families.py). "
            "KLUDG é Samsung UFS 2.1: K=Samsung, L=NAND, U=UFS, D=128GB, pn[6]=U→UFS 2.1. "
            "fix: capacity=128GB, interface=UFS 2.1, device apagado. "
            "Família corrigida via populate_samsung --overwrite."
        ),
    },

    # ── K3KL9L90DMMGCU ───────────────────────────────────────────────────────
    # Problema: Gemini gravou capacity="16Gbit" (em Gbit, não GB — causaria
    # confusão de inventário: operador leria "16" e catalogaria como 16GB).
    # Octopart confirma: 512M × 32bits = 16Gb = 2GB.
    # Após adicionar 9L ao LPDDR5_CAP, a gramática resolve diretamente.
    {
        "pn": "K3KL9L90DMMGCU",
        "fields": {
            "capacity": "2GB",
        },
        "reason": (
            "capacity corrigido: Gemini gravou '16Gbit' (Gbit em vez de GB). "
            "Octopart: 512MX32 = 16Gb = 2GB. "
            "9L adicionado ao LPDDR5_CAP — gramática resolve diretamente."
        ),
    },

    # ── KM8V8001JM ───────────────────────────────────────────────────────────
    # Problema: cap_key V8 estava mapeado como 128GB+8GB no SAM_EMCP_CAP
    # (fonte: AI externa, sem confirmação de fabricante).
    # Fabricante confirma via KM5V8001DM-B622: V8 = 128GB UFS + 32Gb LPDDR4X.
    # 32Gb ÷ 8 = 4GB. Cap_key compartilhado → KM8V8001JM também é 4GB.
    # SAM_EMCP_CAP corrigido: V8 = "128GB" + "4GB".
    {
        "pn": "KM8V8001JM",
        "fields": {
            "emcp_nand": "UFS 128GB",
            "emcp_ram":  "LPDDR4X 4GB",
        },
        "reason": (
            "V8 corrigido: era 128GB+8GB (AI sem confirmação). "
            "Fabricante (KM5V8001DM-B622): 32Gb LPDDR4X ÷ 8 = 4GB. "
            "Cap_key V8 compartilhado no SAM_EMCP_CAP — ambos os chips são 4GB."
        ),
    },

    # ── KMGD6001BM ───────────────────────────────────────────────────────────
    # ⚠ REVERSAL 2026-05-09: a correção anterior estava ERRADA.
    #
    # Histórico:
    #   Distribuidor Jotrin tinha: emcp_nand="eMMC 32GB", emcp_ram="LPDDR3 3GB"
    #   Fix anterior "corrigiu" para: emcp_nand="UFS 3.1 32GB", emcp_ram="LPDDR4X 3GB"
    #   Razão do fix anterior: acreditava-se que KMG = uMCP UFS 3.1 + LPDDR4X.
    #
    # O que a evidência mostra agora:
    #   Datasheet KMGP6001BM confirma: KMG = eMCP eMMC 5.1 + LPDDR3.
    #   O distribuidor Jotrin estava CERTO no tipo (eMMC + LPDDR3).
    #   Família KMG corrigida em populate_samsung.py: chip_type=eMCP, decode_gen_pos=None.
    #   G em EMCP_RAM_TYPES = "LPDDR3" — confirma a família corretamente.
    #
    # D6 no SAM_EMCP_CAP = 32GB + 3GB (confirmado). Valores corretos abaixo.
    {
        "pn": "KMGD6001BM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 5.1 32GB",
            "emcp_ram":  "LPDDR3 3GB",
            "device":    "",
        },
        "reason": (
            "Chip físico confirmado na esteira (eMiner 2026-05-13). "
            "KMG = eMCP eMMC 5.1 + LPDDR3 (datasheet KMGP6001BM confirma). "
            "D6 = 32GB + 3GB LPDDR3. "
            "create=True: raw_in_db=False no debug — não existia no banco."
        ),
    },

    # ── KMR8X0001M ───────────────────────────────────────────────────────────
    # Problema: SAM_EMCP_CAP tinha 8X = "8GB NAND + 1GB RAM" (ERRADO).
    # Confirmado 2026-05-09: KMR8X0001M-B608 = 16GB eMMC + 16Gb (2GB) LPDDR3.
    # Correção do mapa: 8X NAND corrigida de 8GB → 16GB.
    # RAM do mapa: 1GB (base KMQ8X). KMR8X tem 2GB — conflito de shared map.
    # create=True: sem Gemini, chip pode não estar no banco (só grammar-decoded).
    {
        "pn": "KMR8X0001M",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR4/4X + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 5.1 16GB",
            "emcp_ram":  "LPDDR4/4X 2GB",
        },
        "reason": (
            "NAND corrigida: 8X era 8GB no mapa (ERRADO). KMR8X0001M-B608 = 16GB eMMC. "
            "RAM corrigida: 16Gb ÷ 8 = 2GB (mapa usa 1GB como base KMQ8X — divergência de família). "
            "KMQ8X000SA-B414 (1GB) e KMR8X0001M (2GB) confirmados em B2B (SBiT)."
        ),
    },

    # ── KMQ310006B ───────────────────────────────────────────────────────────
    # Conflito de shared key "31" em SAM_EMCP_CAP:
    #   KMQ310013B: chip físico (eMiner 2026-05-13) = 1GB. ← valor no mapa
    #   KMQ310006B-B419: samsungparts.com "16Gb+12" = 1.5GB LPDDR3. ← exceção
    # Ambos pn[3:5]="31" — o mapa não consegue distinguir.
    # create=True: chip decodificado só via gramática (raw_in_db=False, Gemini nunca
    # executado) — não existe no banco. Sem create=True o fix nunca aplicaria.
    {
        "pn": "KMQ310006B",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 5.1 16GB",
            "emcp_ram":  "LPDDR3 1.5GB",
            "device":    "Samsung Galaxy J3 (SM-J327A)",
        },
        "reason": (
            "cap_key '31' conflito: KMQ310013B=1GB vs KMQ310006B=1.5GB (mesmo pn[3:5]). "
            "samsungparts.com KMQ310006B-B419: '16Gb+12' = 12Gb÷8=1.5GB LPDDR3. "
            "Galaxy J3 SM-J327A service manual confirma 1.5GB. Fonte fabricante ✓. "
            "create=True: cria registro no banco se ainda não existir."
        ),
    },

    # ── KMGP6001BM ───────────────────────────────────────────────────────────
    # Problema: SAM_EMCP_CAP["P6"] = 4GB (base KMDP6001DA-B425, família KMD/LPDDR4X).
    # KMG é família LPDDR3 — para KMG, P6 = 64GB eMMC + 24Gb LPDDR3 → 24Gb÷8 = 3GB.
    # Mesma divergência de shared cap_key que KMRX60014M (X6 base KM4=2GB vs KMR=4GB).
    # Datasheet KMGP6001BM confirma KMG = eMCP eMMC 5.1 + LPDDR3 ✓
    # create=True: chip grammar-decoded com 4GB errado (debug raw_in_db=False confirmado).
    {
        "pn": "KMGP6001BM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 5.1 64GB",
            "emcp_ram":  "LPDDR3 3GB",
        },
        "reason": (
            "P6 no SAM_EMCP_CAP = 4GB (base KMDP6001DA-B425, família KMD/LPDDR4X). "
            "KMG é LPDDR3: P6 para KMG = 64GB eMMC + 24Gb LPDDR3 → 24Gb÷8=3GB. "
            "Datasheet KMGP6001BM confirma. create=True: sem Gemini, chip não entra no banco sozinho."
        ),
    },

    # ── KMRX60014M ───────────────────────────────────────────────────────────
    # Problema: SAM_EMCP_CAP mapeia X6 = "32GB NAND + 2GB RAM" (base KM4X6001KM).
    # KMRX60014M-B614 = 32GB eMMC 5.1 + 32Gb LPDDR4/4X → 32Gb ÷ 8 = 4GB.
    # Conflito de shared map: X6 base é 2GB (KM4X série), KMRX6 é 4GB (KMR série).
    # create=True: sem Gemini, chip não entra no banco via grammar-only decode.
    {
        "pn": "KMRX60014M",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR4/4X + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 5.1 32GB",
            "emcp_ram":  "LPDDR4/4X 4GB",
        },
        "reason": (
            "X6 base mapeado como 2GB (KM4X6001KM, Octopart). "
            "KMRX60014M-B614 = 32GB eMMC 5.1 + 32Gb LPDDR4/4X → 32Gb÷8=4GB. "
            "Divergência de família no shared cap_key X6: KM4X6→2GB, KMRX6→4GB."
        ),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Chips confirmados fisicamente na esteira eMiner — 2026-05-13
    # Todos com create=True: raw_in_db=False no debug → não existiam no banco.
    # ══════════════════════════════════════════════════════════════════════════

    # ── K3QF5F50MM ────────────────────────────────────────────────────────────
    # LPDDR3 standalone PoP (Mobile DRAM pura — sem NAND).
    # Família K3QF, chave "5" adicionada ao K3QF_CAP: 12Gb = 2×6Gb die = 1.5GB.
    # Dispositivo: Samsung Galaxy S5 Mini (SM-G800F/H, Exynos 3470).
    # ⚠ NÃO é eMCP. Arquitetura PoP — incompatível com sockets BGA de eMCP.
    {
        "pn": "K3QF5F50MM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR3",
            "subtype":    "LPDDR3 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":  "1.5GB",
            "interface": "LPDDR3",
            "emcp_nand": "",
            "emcp_ram":  "",
            "device":    "Samsung Galaxy S5 Mini (SM-G800F/H, Exynos 3470)",
        },
        "reason": (
            "Chip físico confirmado na esteira (eMiner 2026-05-13). "
            "K3QF5: 12Gb = 2×6Gb die = 1.5GB LPDDR3. Chave '5' adicionada ao K3QF_CAP. "
            "RAM standalone PoP — sem NAND. Destino: resíduo (baixo valor B2B)."
        ),
    },

    # ── KMDC6001DM ────────────────────────────────────────────────────────────
    # eMCP LPDDR4X + eMMC 5.1. Família KMD, chave C6 adicionada ao SAM_EMCP_CAP.
    # C6 = 64GB eMMC 5.1 + 3GB LPDDR4X (24Gb). IA + padrão C*=64GB.
    # Aparelhos prováveis: Galaxy A20s / Moto G8 Play (pendente confirmação física).
    {
        "pn": "KMDC6001DM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR4X + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 5.1 64GB",
            "emcp_ram":  "LPDDR4X 3GB",
        },
        "reason": (
            "Chip físico confirmado na esteira (eMiner 2026-05-13). "
            "C6 adicionado ao SAM_EMCP_CAP: 64GB eMMC 5.1 + 24Gb LPDDR4X = 3GB. "
            "Padrão C*=64GB consistente com C1 e C7 (ambos 64GB, confirmados)."
        ),
    },

    # ── KMQN10006B ────────────────────────────────────────────────────────────
    # eMCP LPDDR3 + eMMC 5.1. Família KMQ, chave N1 já existia no SAM_EMCP_CAP.
    # N1 = 8GB eMMC 5.1 + 1GB LPDDR3 (8Gb). Segunda confirmação física da chave.
    {
        "pn": "KMQN10006B",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 5.1 8GB",
            "emcp_ram":  "LPDDR3 1GB",
        },
        "reason": (
            "Chip físico confirmado na esteira (eMiner 2026-05-13). "
            "N1 = 8GB eMMC 5.1 + 1GB LPDDR3. Segunda confirmação física (KMFN10012A-B214 era a primeira)."
        ),
    },

    # ── KMQ7X000SA ────────────────────────────────────────────────────────────
    # eMCP LPDDR3 + eMMC 5.1. Família KMQ, chave 7X adicionada ao SAM_EMCP_CAP.
    # 7X = 8GB eMMC 5.1 + 1.5GB LPDDR3 (12Gb = 2×6Gb die).
    # Mesmo padrão de die de 6Gb que KMQ310006B (Galaxy J3, 1.5GB confirmado).
    {
        "pn": "KMQ7X000SA",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 5.1 8GB",
            "emcp_ram":  "LPDDR3 1.5GB",
        },
        "reason": (
            "Chip físico confirmado na esteira (eMiner 2026-05-13). "
            "7X adicionado ao SAM_EMCP_CAP: 8GB eMMC 5.1 + 12Gb LPDDR3 = 1.5GB. "
            "12Gb = 2×6Gb die — mesmo padrão de KMQ310006B (Galaxy J3, fonte fabricante ✓)."
        ),
    },

    # ── KMV3W000LW ───────────────────────────────────────────────────────────
    # eMCP LPDDR2 + eMMC legado (~2010-2013). Família KMV.
    # pn[3:5]="3W" adicionado ao SAM_EMCP_CAP: 16GB NAND + 512MB LPDDR2.
    # ⚠ KMV3 = eMCP legado Galaxy S4 era — NÃO confundir com KM3V (uMCP flagship).
    # Destino: Caixa Vermelha (resíduo — LPDDR2 sem liquidez em 2026).
    {
        "pn": "KMV3W000LW",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR2 + eMMC (legado)",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 16GB",
            "emcp_ram":  "LPDDR2 512MB",
        },
        "reason": (
            "Chip físico confirmado na esteira (eMiner 2026-05-13). "
            "3W adicionado ao SAM_EMCP_CAP: 16GB eMMC + 4Gbit LPDDR2 = 512MB. "
            "KMV3 = eMCP legado Galaxy S4 era. Tip corrigido: KMV2/KMV3 não são flagship."
        ),
    },

    # ── K5W1G12ACM ───────────────────────────────────────────────────────────
    # MCP Samsung NOR Flash 1Gb (128MB) + Mobile SDRAM. Família K5W.
    # pn[3:5]="1G" → DRAM_PC → 1Gb = 128MB NOR. SDRAM não decodificável pelo PN.
    # Fontes: Censtry (K5W1G12ACM-BL60TNO) + Ciiva (K5W1G12ACM-BL60000) ✓.
    # Aparelhos: Nokia, Sony-Ericsson, feature phones ~2006-2010.
    # Destino: Caixa Vermelha (resíduo — sem liquidez B2B em 2026).
    {
        "pn": "K5W1G12ACM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "MCP",
            "subtype":    "NOR Flash + Mobile SDRAM (legado)",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "128MB",
            "interface":  "NOR (async) + SDRAM",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "MCP K5W: NOR Flash 1Gb (128MB) + Mobile SDRAM. "
            "pn[3:5]='1G' → DRAM_PC → 1Gb = 128MB NOR. "
            "Censtry + Ciiva confirmam chip real. Feature phone ~2006-2010. "
            "Destino: resíduo — sem liquidez B2B."
        ),
    },

    # ── KMR310001M ───────────────────────────────────────────────────────────
    # eMCP LPDDR3 + eMMC 5.1. Família KMR.
    # Conflito duplo de shared key:
    #   (1) SAM_EMCP_GEN: R = "LPDDR4/4X" no mapa global (confirmado KMRH60014A-B614,
    #       Galaxy A7 2017). KMR310001M é exceção da era anterior (~2015) com LPDDR3.
    #   (2) SAM_EMCP_CAP: chave "31" = 16GB+1GB no mapa (base KMQ310013B, chip físico
    #       confirmado). KMR310001M tem "31" mas com 16Gb LPDDR3 = 2GB RAM.
    # Fonte: Preduo (preduo.com): KMR310001M-B611 → "eMCP eMMC+LPDDR3, 16+16, 221ball" ✓
    # NÃO alterar SAM_EMCP_GEN nem SAM_EMCP_CAP — ambas as chaves base estão corretas
    # para a maioria dos chips. Este chip é correção pontual via fix_known_parts.
    {
        "pn": "KMR310001M",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 5.1 16GB",
            "emcp_ram":  "LPDDR3 2GB",
        },
        "reason": (
            "Preduo: KMR310001M-B611 = eMCP eMMC+LPDDR3, 16+16 (16GB NAND + 16Gb LPDDR3 = 2GB). "
            "Conflito duplo: mapa R=LPDDR4/4X (base KMRH60014A-B614 ✓) e chave '31'=1GB (base KMQ310013B ✓). "
            "KMR310001M é chip mais antigo (~2015) com LPDDR3 — exceção pontual, mapa global preservado."
        ),
    },

    # ── KM3V6001CM ───────────────────────────────────────────────────────────
    # eMCP LPDDR4X + eMMC 5.1. Família genérica "KM" (prefixo KM3V não cadastrado).
    # 48Gb LPDDR4X ÷ 8 = 6GB RAM. 128GB eMMC 5.1 (V6 NAND correto no SAM_EMCP_CAP).
    # Problema: SAM_EMCP_CAP["V6"] val_secondary=4GB (errado para este chip).
    #           SAM_EMCP_GEN não mapeia "3" (dígito na pos 2) → "RAM não mapeada".
    #           Resultado da gramática: grammar_complete=True mas tipo e cap RAM errados.
    # Fonte: catálogos ECtronics/Ovaga, lote KM3V6001CM-B705/-B075:
    #   "128 GB, eMMC 5.1, 48Gb, LPDDR4X, 254FBGA, 3733 Mbps"
    # NÃO alterar SAM_EMCP_CAP V6 — afeta outros chips; tratar como exceção pontual.
    {
        "pn": "KM3V6001CM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR4X + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 5.1 128GB",
            "emcp_ram":  "LPDDR4X 6GB",
        },
        "reason": (
            "Catálogos ECtronics/Ovaga (lote B705/B075): 48Gb LPDDR4X ÷ 8 = 6GB, 128GB eMMC 5.1. "
            "SAM_EMCP_CAP V6 val_secondary=4GB (base outro chip) — exceção pontual. "
            "SAM_EMCP_GEN não mapeia dígitos (pos 2='3') → gramática produz 'RAM não mapeada'. "
            "Família KM3V não cadastrada; pego pelo fallback genérico KM."
        ),
    },

    # ── KMR4Z0001M ───────────────────────────────────────────────────────────
    # eMCP LPDDR3 + eMMC 5.1. Família KMR — exceção da era anterior (~2015-2016).
    # Mesmo conflito do KMR310001M: SAM_EMCP_GEN mapeia R → LPDDR4/4X (correto
    # para série moderna), mas este chip pré-data a padronização LPDDR4/4X da família.
    # cap_key "4Z" no SAM_EMCP_CAP: 32GB NAND + 2GB RAM — acerto correto da gramática.
    # Evidência: sufixo -B802 (era 2015-2016), encontrado em Moto G4, Lenovo K5/K6.
    # Fonte: confirmação física na esteira eMiner.
    # NÃO alterar SAM_EMCP_GEN — R = LPDDR4/4X é correto para a maioria dos KMR.
    # Destino: Caixa Vermelha (LPDDR3 2GB sem viabilidade de recondicionamento em 2026).
    {
        "pn": "KMR4Z0001M",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 5.1 32GB",
            "emcp_ram":  "LPDDR3 2GB",
            "device":    "Moto G4 / Lenovo K5 / K6",
        },
        "reason": (
            "Exceção de família KMR: chip era 2015-2016 (sufixo -B802) usa LPDDR3, "
            "não LPDDR4/4X. SAM_EMCP_GEN R→LPDDR4/4X correto para série moderna. "
            "cap_key 4Z = 32GB NAND + 2GB RAM (acerto da gramática preservado). "
            "Confirmado na esteira eMiner. Destino: Caixa Vermelha (LPDDR3 sem liquidez)."
        ),
    },

    # ── KMKLL000UN ────────────────────────────────────────────────────────────
    # eMCP LPDDR2 + eMMC legado (~2011-2012). Família KMK.
    # pn[3:5]="LL" adicionado ao SAM_EMCP_CAP: 4GB eMMC + 1GB LPDDR2.
    # Fonte: teardown oficial GlobalSpec/Electronics360 (Agosto 2011) do HTC EVO 3D.
    #   Documentado: "MCP Samsung KMKLL000UM-B406 — 4GB eMMC NAND + 1GB Mobile DDR".
    # KMKLL000UN é variante do mesmo chip (sufixo de lote diferente, mesmo PN base).
    # ⚠ Destino: Caixa Vermelha (LPDDR2 legado, sem liquidez em 2026).
    {
        "pn": "KMKLL000UN",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR2 + eMMC (legado)",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 4GB",
            "emcp_ram":  "LPDDR2 1GB",
            "device":    "HTC EVO 3D (2011)",
        },
        "reason": (
            "Teardown GlobalSpec/Electronics360 (Ago/2011) HTC EVO 3D: "
            "KMKLL000UM-B406 documentado como '4GB eMMC NAND + 1GB Mobile DDR'. "
            "KMKLL000UN = variante de lote do mesmo chip base. "
            "LL adicionado ao SAM_EMCP_CAP com 4GB+1GB. Destino: resíduo."
        ),
    },

    # ── KMMLL000QM ────────────────────────────────────────────────────────────
    # eMCP LPDDR2 + eMMC legado (~2011). Família KMM (não cadastrada na gramática).
    # Mesma chave LL do SAM_EMCP_CAP mas RAM diferente: 768MB em vez de 1GB.
    # Samsung fabricou die de 6Gb LPDDR2 (768MB) sob encomenda para HTC Sensation.
    # Confirmado: Samsung Newsroom/Design-Reuse declara produção de eMCP com
    #   "4GB eMMC + escolha de 256MB, 512MB ou 768MB LPDDR2 em 30nm".
    # KMM não é família gramatical ativa — chip só entra via fix_known_parts.
    # ⚠ Conflito de shared key: mapa base LL=1GB (KMK, teardown verificado);
    #    este chip usa override manual (create=True) para registrar 768MB correto.
    # ⚠ Destino: Caixa Vermelha (LPDDR2 legado, sem liquidez em 2026).
    {
        "pn": "KMMLL000QM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR2 + eMMC (legado)",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 4GB",
            "emcp_ram":  "LPDDR2 768MB",
            "device":    "HTC Sensation (2011)",
        },
        "reason": (
            "Samsung fabricou eMCP 4GB + 768MB LPDDR2 (6Gb die, 30nm) para HTC Sensation. "
            "Fonte: Samsung/Design-Reuse: '256MB, 512MB ou 768MB LPDDR2' explicitamente listados. "
            "Chave LL compartilhada com KMK (1GB) — conflito de shared key. "
            "KMM sem família gramatical ativa: create=True obrigatório."
        ),
    },

    # ── H9TQ64AAETAC ─────────────────────────────────────────────────────────
    # SK Hynix eMCP LPDDR3 + eMMC 5.1. Família H9TQ.
    # pn[4:6]="64" → HYX_EMCP_NAND_CAP = 8GB eMMC.
    # pn[6:8]="AA" → HYX_H9TQ_RAM_CAP = LPDDR3 2GB (16Gb).
    # AA já estava mapeado com este PN como âncora no populate_hynix.
    {
        "pn": "H9TQ64AAETAC",
        "create": True,
        "create_defaults": {
            "brand_name": "SK Hynix",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 5.1 8GB",
            "emcp_ram":  "LPDDR3 2GB",
        },
        "reason": (
            "Chip físico confirmado na esteira (eMiner 2026-05-13). "
            "H9TQ64: 64=8GB NAND (HYX_EMCP_NAND_CAP ✓). AA=LPDDR3 2GB (HYX_H9TQ_RAM_CAP ✓). "
            "PN já era âncora da chave AA no populate_hynix — agora com confirmação física."
        ),
    },

]


# ─────────────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Corrige registros KnownPart com dados sujos de distribuidores."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Exibe as correções sem salvar no banco.",
        )
        parser.add_argument(
            "--pn",
            type=str,
            default=None,
            help="Corrige apenas o part number informado.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        target_pn = options["pn"]

        if dry:
            self.stdout.write(self.style.WARNING("⚠  DRY RUN — nenhuma alteração será salva.\n"))

        corrections = CORRECTIONS
        if target_pn:
            corrections = [c for c in CORRECTIONS if c["pn"] == target_pn]
            if not corrections:
                self.stdout.write(self.style.ERROR(f"PN '{target_pn}' não encontrado na tabela de correções."))
                return

        fixed = skipped = not_found = created_count = 0

        for entry in corrections:
            pn          = entry["pn"]
            fields      = entry["fields"]
            reason      = entry.get("reason", "")
            do_create   = entry.get("create", False)

            from chips.models import KnownPart, Brand
            obj = None
            was_created = False

            try:
                obj = KnownPart.objects.get(part_number=pn)
            except KnownPart.DoesNotExist:
                if do_create:
                    # ── Criar registro novo ──────────────────────────────────
                    defaults  = dict(entry.get("create_defaults", {}))
                    brand_name = defaults.pop("brand_name", "Samsung")
                    try:
                        brand = Brand.objects.get(name=brand_name)
                    except Brand.DoesNotExist:
                        self.stdout.write(self.style.ERROR(
                            f"  ✗ Brand '{brand_name}' não encontrada — pulando {pn}."
                        ))
                        not_found += 1
                        continue
                    if not dry:
                        obj = KnownPart(part_number=pn, brand=brand, **defaults)
                        # aplica os campos do fix antes de salvar
                        for field, val in fields.items():
                            setattr(obj, field, val if val is not None else "")
                        try:
                            with transaction.atomic():
                                obj.save()
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"  ✗ Erro ao criar {pn}: {e}"))
                            continue
                        was_created = True
                    prefix = "[DRY] " if dry else ""
                    self.stdout.write(self.style.SUCCESS(
                        f"  {prefix}✚ {pn} — registro CRIADO com {len(fields)} campo(s):"
                    ))
                    for field, val in fields.items():
                        self.stdout.write(f"      {field}: → {repr(val)}")
                    if reason:
                        self.stdout.write(f"      Motivo: {reason}")
                    created_count += 1
                    continue
                else:
                    self.stdout.write(self.style.WARNING(f"  ⚠ Não encontrado no banco: {pn}"))
                    not_found += 1
                    continue

            changed_fields = []
            for field, new_val in fields.items():
                old_val = getattr(obj, field, None)
                resolved = new_val if new_val is not None else ""
                if old_val != resolved:
                    changed_fields.append((field, old_val, resolved))
                    if not dry:
                        setattr(obj, field, resolved)

            # Quando a entrada tem create_defaults (chips confirmados manualmente),
            # garante que status e confidence sejam promovidos mesmo se o registro
            # já existia como raw ou estimated.
            #
            # Cenário típico sem Gemini:
            #   1. PN buscado antes do fix existir → cria registro raw (via fila de revisão)
            #   2. fix_known_parts roda → encontra o raw → atualiza só os fields
            #   3. status permanece "raw" → engine filtra status="enriched" → nunca usa o banco
            #
            # Sem este bloco, confidence fica em create_defaults (só usado na criação)
            # e nunca é aplicado no update. O engine exige status=enriched para Camada 1.
            if do_create:
                create_defs   = entry.get("create_defaults", {})
                target_conf   = create_defs.get("confidence", "confirmed")
                if obj.status != "enriched":
                    changed_fields.append(("status", obj.status, "enriched"))
                    if not dry:
                        obj.status = "enriched"
                if obj.confidence != target_conf:
                    changed_fields.append(("confidence", obj.confidence, target_conf))
                    if not dry:
                        obj.confidence = target_conf

            if not changed_fields:
                self.stdout.write(f"  — {pn}: já correto, sem alterações.")
                skipped += 1
                continue

            if not dry:
                try:
                    with transaction.atomic():
                        obj.save()
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  ✗ Erro ao salvar {pn}: {e}"))
                    continue

            prefix = "[DRY] " if dry else ""
            self.stdout.write(self.style.SUCCESS(f"  {prefix}✚ {pn} — {len(changed_fields)} campo(s) corrigido(s):"))
            for field, old, new in changed_fields:
                self.stdout.write(f"      {field}: {repr(old)} → {repr(new)}")
            if reason:
                self.stdout.write(f"      Motivo: {reason}")
            fixed += 1

        self.stdout.write(
            f"\n{'[DRY] ' if dry else ''}Resultado: {fixed} corrigido(s), "
            f"{created_count} criado(s), "
            f"{skipped} já correto(s), {not_found} não encontrado(s) no banco."
        )
        if not dry and fixed:
            self.stdout.write(self.style.SUCCESS("\n✅  Correções aplicadas com sucesso."))
