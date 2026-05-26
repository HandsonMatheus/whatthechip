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

    # ── KMQ310013M ───────────────────────────────────────────────────────────
    # Conflito de shared key "31" em SAM_EMCP_CAP (terceiro caso documentado):
    #   KMQ310013B: chip físico (eMiner 2026-05-13) = 1GB. ← valor base no mapa
    #   KMQ310006B: samsungparts.com = 1.5GB. ← fix_known_parts ✓
    #   KMQ310013M: Alibaba "16gb+16gb 32dram LPDDR3" = 16Gb÷8 = 2GB. ← este fix
    # Todos pn[3:5]="31" — mapa não consegue distinguir. Exceções via fix_known_parts.
    # Fonte: Alibaba (distribuidor). Marcado confirmed para grammar_wins=False —
    # sem isso a gramática (1GB) sobrescreve o banco mesmo após o fix.
    # ⚠ Aguardando confirmação B2B (Preduo/ssfkg/samsungparts) para validação extra.
    # Não alterar SAM_EMCP_CAP["31"].
    {
        "pn": "KMQ310013M",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "eMMC 5.1 16GB",
            "emcp_ram":   "LPDDR3 2GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "cap_key '31' conflito (terceiro caso): KMQ310013B=1GB (físico), "
            "KMQ310006B=1.5GB (fabricante ✓), KMQ310013M=2GB (Alibaba: '16gb+16gb 32dram LPDDR3'). "
            "16Gb LPDDR3 ÷ 8 = 2GB. Mesmo padrão de KMR310001M (16Gb LPDDR3 = 2GB, Preduo ✓). "
            "confidence+status em fields: necessário para atualizar registros existentes e "
            "garantir grammar_wins=False (gramática daria 1GB — errado)."
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
    # eMCP LPDDR4X + eMMC 5.1. Família KMD, chave C6 no SAM_EMCP_CAP.
    # CORRIGIDO 2026-05-25: estava 3GB (24Gb) — baseado em IA+padrão (errado).
    # Samsung Semiconductor oficial confirma: KMDC6001DM-B625 = 32Gb LPDDR4X = 4GB.
    # semiconductor.samsung.com/mcp/model/lpddr5-umcp/kmdc6001dm-b625/ ✓
    # SAM_EMCP_CAP["C6"] também corrigido para 4GB em populate_samsung.py.
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
            "emcp_nand":  "eMMC 5.1 64GB",
            "emcp_ram":   "LPDDR4X 4GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor oficial (2026-05-25): KMDC6001DM-B625 = 32Gb LPDDR4X = 4GB. "
            "Corrigido de 3GB (24Gb) — valor anterior baseado em IA+padrão, sem fonte primária. "
            "C6 corrigido para 4GB no SAM_EMCP_CAP. confidence+status em fields: "
            "garante grammar_wins=False para registros já existentes no banco."
        ),
    },

    # ── KMDH6001DM ────────────────────────────────────────────────────────────
    # eMCP LPDDR4X + eMMC 5.1. Família KMD, chave H6 no SAM_EMCP_CAP.
    # Octopart: KMDH6001DM-B422 = "eMCP 64GB eMMC v5.1 + 32Gb(4GB) LPDDR4X-3733" ✓
    # Segunda âncora da chave H6 (primeira: KMRH60014A, Galaxy A7 2017, KMR).
    {
        "pn": "KMDH6001DM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR4X + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "eMMC 5.1 64GB",
            "emcp_ram":   "LPDDR4X 4GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Octopart: KMDH6001DM-B422 = 64GB eMMC v5.1 + 32Gb(4GB) LPDDR4X-3733. "
            "H6=4GB consistente com SAM_EMCP_CAP (segunda âncora da chave, após KMRH60014A ✓). "
            "confidence+status em fields: garante grammar_wins=False para registros existentes."
        ),
    },

    # ── KMDX60018M ────────────────────────────────────────────────────────────
    # eMCP LPDDR4X + eMMC 5.1. Família KMD, chave X6 no SAM_EMCP_CAP.
    # Shared key conflict: SAM_EMCP_CAP["X6"] = 32GB+2GB (base KM4X6001KM, Octopart ✓).
    # KMDX60018M é exceção: Octopart confirma 24Gb LPDDR4X = 3GB.
    # Padrão recorrente: mesma cap_key codifica RAM diferente em famílias distintas
    # (P6: KMG=3GB vs KMD=4GB; X6: KM4=2GB vs KMD=3GB).
    # Não alterar SAM_EMCP_CAP["X6"] — base KM4 permanece correta.
    {
        "pn": "KMDX60018M",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR4X + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "eMMC 5.1 32GB",
            "emcp_ram":   "LPDDR4X 3GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Octopart: KMDX60018M-B425 = 32GB eMMC 5.1 + 24Gb LPDDR4X-4266 → 24Gb÷8=3GB. "
            "Conflito shared key X6: SAM_EMCP_CAP base=2GB (KM4X6001KM ✓), KMD=3GB (exceção). "
            "Mesmo padrão de P6 (KMG=3GB vs KMD=4GB) — cap_key compartilhada, RAM diferente por família. "
            "confidence+status em fields: garante grammar_wins=False para registros existentes."
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
    # eMCP LPDDR3 + eMMC 5.1. Família KMQ, chave 7X no SAM_EMCP_CAP.
    # CORRIGIDO 2026-05-25: estava 1.5GB (12Gb) por analogia com die 6Gb de
    # KMQ310006B — analogia ERRADA. Preduo B2B confirma "8+8" = 8Gb LPDDR3 = 1GB.
    # Alibaba corrobora: "8gb+8gb 32dram" (32dram = barramento 32-bit, não 32Gb).
    # SAM_EMCP_CAP["7X"] também corrigido para 1GB em populate_samsung.py.
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
            "emcp_nand":  "eMMC 5.1 8GB",
            "emcp_ram":   "LPDDR3 1GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Preduo B2B (2026-05-25): KMQ7X000SA-B315 = '8+8' → 8GB NAND + 8Gb LPDDR3 = 1GB. "
            "Corrigido de 1.5GB — valor anterior era inferência de die 6Gb (KMQ310006B), sem verificação. "
            "confidence+status em fields: atualiza registro existente e garante grammar_wins=False."
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

    # ── K4B4G1646E ───────────────────────────────────────────────────────────
    # Samsung DDR3 SDRAM. Família K4B.
    # pn[3:5]="4G" → DRAM_PC → 4Gb = 512MB por die.
    # pn[5:7]="16" → x16 bus width (embarcado/mobile).
    # Sufixo "46E" = speed grade / revisão.
    # Chip físico confirmado na esteira (eMiner 2026-05-14).
    {
        "pn": "K4B4G1646E",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR3/DDR3L",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "512MB",
            "interface":  "DDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Chip físico confirmado na esteira (eMiner 2026-05-14). "
            "K4B: DDR3. pn[3:5]='4G' → 4Gb = 512MB por die. pn[5:7]='16' → x16."
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

    # ── KM2L9001CM ───────────────────────────────────────────────────────────
    # uMCP UFS 2.2 + LPDDR4X. Subfamília KM2L (pn[2]='L').
    # Capacidade real: 128GB UFS 2.2 (armazenamento) + 6GB LPDDR4X (48Gb ÷ 8 = 6GB).
    # Conflito de shared key: SAM_EMCP_CAP["L9"] = 8GB RAM (base KM8L9001JM — 8GB correto).
    #   KM2L9001CM usa 48Gb LPDDR4X (6GB) — die diferente, mesma chave.
    # NÃO alterar SAM_EMCP_CAP["L9"] — KM8L9001JM com 8GB é a maioria.
    # Fontes:
    #   • Octopart: KM2L9001CM-B518 = "uMCP 128GB UFS2.2+ 48Gb LPDDR4X-4266" ✓ (2026-05-25)
    #   • Preduo: KM2L9001CM-B518 → categoria "UFS+LPDDR4x", Density "128+6"
    # Destino: bancada reacondicional uMCP (intermediário/alta liquidez).
    {
        "pn": "KM2L9001CM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "uMCP",
            "subtype":    "UFS 2.2 + LPDDR4X",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "UFS 2.2 128GB",
            "emcp_ram":   "LPDDR4X 6GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Octopart (2026-05-25): KM2L9001CM-B518 = 128GB UFS2.2 + 48Gb LPDDR4X-4266 → 48Gb÷8=6GB. "
            "Subfamília KM2L (pn[2]='L') = UFS 2.2 + LPDDR4X — NÃO UFS 3.1/LPDDR5. "
            "Conflito cap_key 'L9': SAM_EMCP_CAP mapeia 8GB (base KM8L9001JM) — override pontual. "
            "confidence+status em fields: garante grammar_wins=False para registros existentes no banco."
        ),
    },

    # ── KM5L9000CM ───────────────────────────────────────────────────────────
    # uMCP UFS 2.2 + LPDDR4X. Família KM5, variante pn[7]="0" (9000).
    # Capacidade real: 128GB UFS 2.2 + 6GB LPDDR4X (48Gb ÷ 8 = 6GB).
    # Conflito profundo de shared key: SAM_EMCP_CAP["L9"] = 8GB (base KM8L9001JM).
    # Mesmo dentro da família KM5, o cap_key "L9" (pn[3:5]) é insuficiente:
    #   KM5L9000CM (pn[7]="0") = 48Gb = 6GB — esta exceção
    #   KM5L9001DM (pn[7]="1") = 32Gb = 4GB — exceção separada em fix_known_parts
    # O decode 2-char não distingue variantes KM5L90xx — cada PN é exceção pontual.
    # Fonte: Samsung Semiconductor Global (Tier 1) ✓
    #   semiconductor.samsung.com/mcp/model/lpddr5-umcp/km5l9000cm-b424/
    #   "128GB eStorage (UFS2.2), 48Gb DRAM (LPDDR4X-4266), 254FBGA" ✓ (2026-05-25)
    {
        "pn": "KM5L9000CM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "uMCP",
            "subtype":    "UFS 2.2 + LPDDR4X",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "UFS 2.2 128GB",
            "emcp_ram":   "LPDDR4X 6GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global (Tier 1, 2026-05-25): KM5L9000CM-B424 = "
            "128GB UFS 2.2 + 48Gb LPDDR4X-4266 → 48Gb÷8=6GB. "
            "Sistema mostrava 8GB — erro por herdar SAM_EMCP_CAP['L9']=8GB (base KM8L9001JM). "
            "Conflito profundo: mesmo cap_key 'L9' na família KM5 dá RAM diferente por variante: "
            "KM5L9000CM (pn[7]='0') = 6GB; KM5L9001DM (pn[7]='1') = 4GB. "
            "Decode 2-char pn[3:5] insuficiente para família KM5L9 — cada PN é exceção pontual. "
            "confidence+status em fields: garante grammar_wins=False para registros existentes."
        ),
    },

    # ── KM5L9001DM ───────────────────────────────────────────────────────────
    # uMCP UFS 2.2 + LPDDR4X. Subfamília KM5L (pn[2]='L').
    # Capacidade real: 128GB UFS 2.2 + 4GB LPDDR4X (32Gb ÷ 8 = 4GB).
    # Sistema mostrava 8GB — ERRADO. Causa: SAM_EMCP_CAP["L9"] base = 8GB
    #   (âncora KM8L9001JM-B624 = 64Gb÷8=8GB, confirmado Samsung Electronics ✓).
    #   KM5 usa die de 32Gb LPDDR4X (4GB) — RAM menor que KM8 na mesma chave.
    # Mesmo padrão recorrente de conflito de shared key por família:
    #   SAM_EMCP_CAP["L9"]: KM8=8GB (base), KM2=6GB (exceção), KM5=4GB (exceção).
    # NÃO alterar SAM_EMCP_CAP["L9"] — base KM8=8GB permanece correta.
    # Fonte: Samsung Semiconductor Global (Tier 1) — CONFIRMADO
    #   semiconductor.samsung.com/mcp/model/lpddr5-umcp/km5l9001dm-b424/
    #   "128GB eStorage (UFS2.2), 32Gb DRAM (LPDDR4X-4266), 254FBGA" ✓ (2026-05-25)
    # Destino: bancada reacondicional uMCP (Premium).
    {
        "pn": "KM5L9001DM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "uMCP",
            "subtype":    "UFS 2.2 + LPDDR4X",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "UFS 2.2 128GB",
            "emcp_ram":   "LPDDR4X 4GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global (Tier 1, 2026-05-25): KM5L9001DM-B424 = "
            "128GB UFS 2.2 + 32Gb LPDDR4X-4266 → 32Gb÷8=4GB. "
            "Sistema mostrava 8GB — erro por herdar SAM_EMCP_CAP['L9']=8GB (base KM8L9001JM). "
            "Conflito cap_key 'L9': KM8=8GB (base ✓), KM2=6GB (exceção ✓), KM5=4GB (esta exceção). "
            "NÃO alterar SAM_EMCP_CAP — base KM8=8GB está correta. "
            "confidence+status em fields: garante grammar_wins=False para registros existentes."
        ),
    },

    # ── KLUBG4G1BD ───────────────────────────────────────────────────────────
    # UFS 2.0 Samsung, 32GB. Primeira geração UFS — Galaxy S6 / S6 Edge / S6 Edge Plus (2015).
    # Problema: família KLUBG não existia no populate_samsung.py. Engine caía para KLU
    #   genérico (interface="UFS 3.1") — ERRADO para esta geração.
    # Fix sistêmico: família KLUBG adicionada ao populate_samsung.py (interface="UFS 2.0").
    # Fix pontual: chip adicionado aqui para corrigir interface e registrar device.
    # Fontes (múltiplas Tier 2+):
    #   • Samsung Semiconductor Global: KLUBG4G1CE-B0B1 listado sob "UFS 2.0" ✓ (mesmo prefixo)
    #   • eBay: "KLUBG4G1BD-B0B1 BGA153balls UFS 2.0 32GB" ✓
    #   • Blog confirmado: "Samsung's 32GB UFS chip in Galaxy S6 = KLUBG4G1BD-E0B1" ✓
    #   • AnandTech: Galaxy S6 = primeiro smartphone UFS 2.0 da história
    #   • GSM Forum: "UFS KLUBG4G1BD from Samsung Galaxy S6 Edge Plus" ✓
    # Destino: bancada reacondicional Flash UFS (lote legacy, valor comercial reduzido).
    {
        "pn": "KLUBG4G1BD",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "UFS",
            "subtype":    "UFS 2.0 Samsung",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "32GB",
            "interface":  "UFS 2.0",
            "device":     "Samsung Galaxy S6 / S6 Edge / S6 Edge Plus (2015)",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "UFS 2.0 confirmado por Samsung Semiconductor Global (KLUBG4G1CE-B0B1 = UFS 2.0) "
            "e múltiplas fontes Tier 2: eBay (BGA153, UFS 2.0), AnandTech (S6 = primeiro UFS 2.0). "
            "Sistema mostrava UFS 3.1 — erro por ausência da família KLUBG (caía para KLU genérico). "
            "KLUBG adicionado ao populate_samsung.py. "
            "Device confirmado: Galaxy S6 / S6 Edge / S6 Edge Plus (2015). "
            "confidence+status em fields: garante grammar_wins=False para registros existentes."
        ),
    },

    # ── K3UH5H50AM ───────────────────────────────────────────────────────────
    # LPDDR4X Multi-Channel Samsung. Família K3U, pn[3:5]="H5" → 32Gb ÷ 8 = 4GB.
    # H5 não estava no mapa → grammar_complete=false → capacity=null.
    # Após populate_samsung --overwrite, gramática passa a decodificar corretamente.
    # Fontes:
    #   • Samsung Semiconductor oficial: K3UH5H50AM-JGCL(32 Gb) — título da página ✓
    #   • ssfkg.com: K3UH5H50AM-AGCL "Density: 32Gb LPDDR4X, 556FBGA" ✓
    # ⚠ A IA sugeriu inicialmente H5=2GB (16Gb) — ERRADO. Corrigido por fontes primárias.
    {
        "pn": "K3UH5H50AM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR4X",
            "subtype":    "LPDDR4X Multi-Channel",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":  "4GB",
            "interface": "LPDDR4X",
        },
        "reason": (
            "Samsung Semiconductor + ssfkg: K3UH5H50AM = 32Gb LPDDR4X (556FBGA). "
            "32Gb ÷ 8 = 4GB. H5 adicionado ao LPDDR4_CAP como alias de BE/HE/H6. "
            "IA inicialmente afirmou 2GB (16Gb) — refutado por fontes primárias."
        ),
    },

    # ── K4EHE304EC ───────────────────────────────────────────────────────────
    # LPDDR3 standalone Samsung 3GB. Família K4E, pn[3:5]="HE" → 24Gb ÷ 8 = 3GB.
    # "HE" é alias de "FE" (mesmo densidade 24Gb, die alternativo) — padrão Samsung.
    # Fonte: Puris B2B (puris.net): K4EHE304EC-AGCF = "24Gbit 168ball LPD3" ✓
    # Dispositivo: Samsung Galaxy Tab A SM-P585 (Exynos 7870, 2016) — 3GB RAM.
    # Fix promove confidence de estimated → confirmed após decode_map corrigido.
    {
        "pn": "K4EHE304EC",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR3",
            "subtype":    "LPDDR3 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":  "3GB",
            "interface": "LPDDR3",
            "device":    "Samsung Galaxy Tab A SM-P585 (2016)",
        },
        "reason": (
            "Puris B2B: K4EHE304EC-AGCF = 24Gbit LPDDR3 (168ball) → 24Gb÷8=3GB. "
            "HE = alias de FE no mapa K4E_CAP (mesmo 24Gb, die alternativo). "
            "Dispositivo: Galaxy Tab A SM-P585 / Exynos 7870."
        ),
    },

    # ── K3QF2F20DA ────────────────────────────────────────────────────────────
    # LPDDR3 standalone Samsung. Família K3QF, pn[4]='2' → 16Gb ÷ 8 = 2GB.
    # Gramática já acerta — este fix promove confidence para "confirmed".
    # Confirmado via distribuidores globais (Win Source, Veswin) com sufixo -QGCF.
    # Chip era 2013-2015 (Galaxy S4/S5). Destino: reacondicional seletivo.
    {
        "pn": "K3QF2F20DA",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR3",
            "subtype":    "LPDDR3 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":  "2GB",
            "interface": "LPDDR3",
        },
        "reason": (
            "Gramática correta (K3QF, pn[4]='2'=16Gb÷8=2GB). "
            "Confirmado por distribuidores globais Win Source e Veswin (sufixo -QGCF). "
            "Fix promove de estimated para confirmed, retira da fila de revisão."
        ),
    },

    # ── KLMBG2JENB ────────────────────────────────────────────────────────────
    # eMMC 5.1 standalone Samsung 32GB. Família KLM.
    # Gramática acertou: pn[3]='B'=32GB, pn[6]='J'=eMMC 5.1 — fix só promove confidence.
    # Samsung Semiconductor Global (Tier 1): KLMBG2JENB-B041 = 32GB eMMC 5.1, 153FBGA, MLC.
    # semiconductor.samsung.com/estorage/emmc/emmc-5-1/klmbg2jenb-b041/ ✓
    {
        "pn": "KLMBG2JENB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Samsung",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "32GB",
            "interface":  "eMMC 5.1",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global (Tier 1): KLMBG2JENB-B041 = 32GB eMMC 5.1, 153FBGA, MLC. "
            "Gramática correta: pn[3]=B=32GB, pn[6]=J=eMMC 5.1. "
            "Fix promove de estimated para confirmed, retira da fila de revisão."
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

    # ══════════════════════════════════════════════════════════════════════════
    # SanDisk eMMC puro (iNAND standalone) — verificados em Preduo + Octopart
    # ══════════════════════════════════════════════════════════════════════════

    # ── SDIN9DW416G ──────────────────────────────────────────────────────────
    # SanDisk iNAND eMMC 5.0, 16GB. PN normalizado sem hífen (engine strip).
    # ⚠ ZERO RAM — armazenamento puro, NÃO eMCP. Não confundir com série SDAD.
    #
    # Verificação independente (2026-05-25):
    #   • Preduo.com (catálogo reciclagem, nível 4):
    #       SDIN9DW4-16G → categoria /emmc/emmc-5-0/ → "eMMC 5.0, 16GB, BGA, SanDisk" ✓
    #       URL canônica: preduo.com/product/emmc/emmc-5-0/sdin9dw4-16g
    #   • Octopart (nível 2 da hierarquia):
    #       SDIN9DW4-16G confirmado com 7 distribuidores ativos.
    #       Categoria "Flash" — sem RAM na ficha.
    #   • Mouser (distribuidor tier-1): listagem ativa confirmada na pesquisa.
    #   • Família SDIN9DW4 completa no Octopart: -16G, -32G, -64G, -128G.
    #       Todos eMMC puro — nenhuma variante com RAM.
    #
    # Nível de confiança: "distributor" (Preduo + Octopart = nível 2-4 ✓).
    # WD oficial não consultado diretamente → não usar "confirmed".
    #
    # Nota arquitetural:
    #   O engine vai identificar o prefixo SDIN corretamente (família registrada
    #   em populate_sandisk.py), mas decode_cap_pos=None → capacity=null sem este fix.
    #   create=True garante que SDIN9DW416G entre no banco enriched antes que
    #   Gemini ou scraper criem um registro raw com dados potencialmente errados.
    {
        "pn": "SDIN9DW416G",
        "create": True,
        "create_defaults": {
            "brand_name": "SanDisk",
            "chip_type":  "eMMC",
            "subtype":    "eMMC iNAND (iNAND 7 Series)",
            "status":     "enriched",
            "confidence": "distributor",
        },
        "fields": {
            "capacity":  "16GB",
            "interface": "eMMC 5.0",
        },
        "reason": (
            "Preduo: SDIN9DW4-16G → categoria eMMC 5.0, 16GB, BGA, SanDisk ✓. "
            "Octopart: 7 distribuidores ativos, categoria Flash (sem RAM). "
            "Mouser: listagem ativa (tier-1). "
            "Família SDIN9DW4 todas sem RAM (-16G, -32G, -64G, -128G). "
            "WD oficial não consultado diretamente → confidence=distributor."
        ),
    },

    # ── SDIN9DW432G ──────────────────────────────────────────────────────────
    # SanDisk iNAND eMMC 5.0, 32GB. Variante -32G da família SDIN9DW4.
    # Mesma família de SDIN9DW4-16G (eMMC 5.0 confirmado). Package 153FBGA 11.5×13×1.
    # Octopart: confirmado pelo usuário via link direto.
    # Preduo: apareceu como /emmc/emmc-5-0/sdin9dw4-32g na busca de SDIN9DW4-16G.
    {
        "pn": "SDIN9DW432G",
        "create": True,
        "create_defaults": {
            "brand_name": "SanDisk",
            "chip_type":  "eMMC",
            "subtype":    "eMMC iNAND (iNAND 7 Series)",
            "status":     "enriched",
            "confidence": "distributor",
        },
        "fields": {
            "capacity":  "32GB",
            "interface": "eMMC 5.0",
        },
        "reason": (
            "Mesma família SDIN9DW4 de SDIN9DW4-16G (eMMC 5.0 Preduo+Octopart ✓). "
            "Octopart: link direto do usuário. "
            "Preduo: /emmc/emmc-5-0/sdin9dw4-32g ✓. "
            "Package: 153FBGA 11.5×13×1. Sufixo -32G = 32GB. Zero RAM."
        ),
    },

    # ── SDIN7DU28G ───────────────────────────────────────────────────────────
    # SanDisk iNAND Ultra eMMC 4.41, 8GB. PN normalizado sem hífen (engine strip).
    # ⚠ ZERO RAM — armazenamento puro (iNAND standalone). NÃO eMCP.
    #
    # Verificação independente (2026-05-25):
    #   • Octopart (nível 2): SDIN7DU2-8G confirmado com 11 distribuidores ativos.
    #   • Datasheet oficial SanDisk via Octopart (nível fabricante):
    #       "Ultra e.MMC 4.41 I/F Released Data Sheet 80-36-03666 V1.2 May 2012"
    #       → eMMC versão 4.41 confirmada em documento oficial (doc# 80-36-03666).
    #   • Octopart direto: usuário confirmou PN via link pessoal.
    #   • Família SDIN7DU2 completa: -8G, -16G, -32G. Todas eMMC puro.
    #   • Package: 153-Pin TFBGA (BGA 153), mesmo footprint da série iNAND clássica.
    #   • Descrição técnica: "Managed NAND Flash Serial e-MMC 3.3V 64G-bit
    #     64G/16G/8G x 1/4-bit/8-bit 153-Pin TFBGA" — sem RAM mencionada.
    #
    # Nota: chip de 2012 (era Galaxy S3/Note 2). Destino: resíduo ou reacondicional
    # seletivo em aparelhos de baixo custo (eMMC 4.41 ainda com liquidez limitada).
    {
        "pn": "SDIN7DU28G",
        "create": True,
        "create_defaults": {
            "brand_name": "SanDisk",
            "chip_type":  "eMMC",
            "subtype":    "eMMC iNAND Ultra",
            "status":     "enriched",
            "confidence": "distributor",
        },
        "fields": {
            "capacity":  "8GB",
            "interface": "eMMC 4.41",
        },
        "reason": (
            "Octopart: 11 distribuidores ativos. "
            "Datasheet SanDisk oficial (doc# 80-36-03666): "
            "'Ultra e.MMC 4.41 I/F Released Data Sheet V1.2 May 2012' → eMMC 4.41 ✓. "
            "Package: 153-Pin TFBGA. Capacidade -8G = 8GB (64Gbit ÷ 8). Zero RAM."
        ),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # SanDisk eMCP — verificados em fontes B2B (2026-05)
    # ══════════════════════════════════════════════════════════════════════════

    # ── SDADB48K16G ──────────────────────────────────────────────────────────
    # SanDisk eMCP 16GB eMMC + 2GB LPDDR3. PN normalizado sem hífen (engine strip).
    #
    # Verificação independente (2026-05-25):
    #   • yoycart.com / chinahao.com (B2B wholesale): listagem explícita
    #     "SDADF4AP-16G SDADB48K-16G SanDisk 16 2 16G EMCP 221 ball 3rd gen"
    #     → "16+2" no mercado de reciclagem = 16GB NAND + 2GB RAM (ambos em GB).
    #   • eBay B2B: "1pcs SDADF4AP-16G 16+2 16G EMCP 221balls new"
    #     → segunda fonte independente, mesmo spec.
    #   • Octopart: SDADF4AP-16G (PN irmão) confirmado como WD/SanDisk real
    #     (3 distribuidores listados) → família SDAD existe e é real.
    #   • Preduo (preduo.com) — taxonomia 221ball:
    #     Categoria "221ball eMMC+LPD3" contém EXCLUSIVAMENTE eMCPs com LPDDR3.
    #     SanDisk SD9DS28K-8G listado na mesma categoria → 221-ball SanDisk = LPDDR3.
    #
    # Nível de confiança atingido: "distributor" (acima de "IA externa" ✓).
    # WD/SanDisk oficial não encontrado — NÃO usar "confirmed".
    #
    # ⚠ "16G" no final do PN normalizado: sufixo de capacidade declarativa
    #   (-16G → 16G após strip do hífen). O engine concatena o sufixo ao corpo;
    #   create=True garante que o registro exato SDADB48K16G entre no banco
    #   antes que o Gemini ou o scraper criem algo inconsistente.
    #
    # Destino: bancada Smart POS / módulos telemetria (LPDDR3 2GB ainda viável).
    {
        "pn": "SDADB48K16G",
        "create": True,
        "create_defaults": {
            "brand_name": "SanDisk",
            "chip_type":  "eMCP",
            "subtype":    "eMCP (eMMC + LPDDR3)",
            "status":     "enriched",
            "confidence": "distributor",
        },
        "fields": {
            "emcp_nand": "eMMC 16GB",
            "emcp_ram":  "LPDDR3 2GB",
        },
        "reason": (
            "B2B wholesale (yoycart, chinahao, eBay): SDADB48K-16G = 16+2 EMCP 221ball SanDisk. "
            "Octopart: SDADF4AP-16G (PN irmão) confirmado como WD/SanDisk real. "
            "Preduo 221ball = exclusivamente eMMC+LPDDR3 → RAM é LPDDR3 (não LPDDR4). "
            "WD oficial não encontrado → confidence=distributor (não confirmed)."
        ),
    },

    # ── 16EMCP08-NL3DTB28 ────────────────────────────────────────────────────
    # eMCP Kingston. Chip físico confirmado na esteira (eMiner 2026-05-25).
    #
    # Verificação (hierarquia de fontes):
    #   Puris.net (distribuidor B2B rastreável, nível 4): tabela oficial Kingston eMCP
    #   confirma "16EMCP08-NL3DTB28 → 16GB eMMC 5.1 (HS400) + 8Gb LPDDR3 → 1GB RAM"
    #   Package: 221ball FBGA, 11.5×13×1.0mm.
    #
    # Anatomia do PN (padrão declarativo literal Kingston):
    #   [0:2]  "16"   = 16GB eMMC (capacidade NAND em GB, declaração direta)
    #   [2:6]  "EMCP" = identificador de encapsulamento combinado
    #   [6:8]  "08"   = 8Gbit RAM ÷ 8 = 1GB LPDDR3
    #   [9:12] "NL3"  = LPDDR3 (NL2=LPDDR2, NL3=LPDDR3 — verificado em 6 PNs da família)
    #   "DTB28"        = revisão/lotação do die
    #
    # ⚠ ERRO DA IA DOCUMENTADO: a IA de referência citou o PN comparativo
    #   "32EMCP16-NL3DTB29" como PN real da família. O PN correto é
    #   "32EMCP16-EL3GTB29" (sufixo EL3GTB29, não NL3DTB29). Capacidade estava
    #   correta (32GB+2GB), mas o PN foi alucinado — regra de ouro aplicada.
    #
    # ⚠ ALERTA ARQUITETURAL: o prefixo "EMCP" em add_chip_families.py NÃO casa
    #   com este PN via pn.startswith("EMCP"), pois o PN começa com "16".
    #   Família gramatical ativa depende de populate_kingston.py com prefixos
    #   corretos: "04EMCP", "08EMCP", "16EMCP", "32EMCP", "64EMCP".
    #   Este fix garante classificação correta independente da gramática.
    #
    # Destino: Caixa Vermelha — LPDDR3 1GB sem liquidez B2B em 2026.
    {
        "pn": "16EMCP08-NL3DTB28",
        "create": True,
        "create_defaults": {
            "brand_name": "Kingston",
            "chip_type":  "eMCP",
            "subtype":    "eMCP Kingston",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand": "eMMC 5.1 16GB",
            "emcp_ram":  "LPDDR3 1GB",
        },
        "reason": (
            "Chip físico confirmado na esteira (eMiner 2026-05-25). "
            "Puris.net B2B: 16EMCP08-NL3DTB28 = 16GB eMMC 5.1 (HS400) + 8Gb LPDDR3 → 1GB. "
            "NL3=LPDDR3 verificado em 6 PNs cruzados da família Kingston eMCP. "
            "IA errou PN comparativo: '32EMCP16-NL3DTB29' não existe (real: EL3GTB29). "
            "Alerta arquitetural: prefixo 'EMCP' não casa via startswith — "
            "populate_kingston.py deve usar prefixos '16EMCP', '08EMCP' etc."
        ),
    },

    # ── THGBMFG7C1LBAIL ──────────────────────────────────────────────────────
    # Toshiba / Kioxia eMMC 5.0, 16GB. Package BGA153 (153-Pin FBGA).
    # Chip chegou na esteira — gramática já decoda correto (7C1=16GB, F=eMMC 5.0).
    # Este create=True promove confidence de "estimated" → "confirmed".
    #
    # Attestation (2026-05-26) — regra de ouro aplicada:
    #
    # CONFIRMADO:
    #   • 16GB eMMC: Octopart (Tier 2, 11 distribuidores): "128G-bit 153-Pin FBGA"
    #     → 128Gbit ÷ 8 = 16GB ✓. Mouser / Kioxia America (Tier 1): listagem ativa ✓.
    #   • eMMC 5.0: pn[5]='F' → THGBM_GEN = "eMMC 5.0" (confirmado em sessão anterior
    #     via THGBMFG7C2LBAIL, Puris /emmc-5-0/ ✓).
    #   • Package BGA153: Octopart + Mouser: "153-Pin FBGA" ✓.
    #   • Chave 7C1 = 16GB: âncora promovida de Tier 3 → Tier 1+2 com este PN.
    #
    # REFUTADO (IA externa):
    #   • "profitable=RENTÁVEL está errado" → FALSO. Regra atual: eMMC ≥ 8GB = RENTÁVEL.
    #     A regra não distingue versão (5.0 vs 5.1). Motor correto, nenhuma mudança.
    #
    # Nota: confidence="confirmed" (Tier 1 Mouser/Kioxia America + Tier 2 Octopart).
    {
        "pn": "THGBMFG7C1LBAIL",
        "create": True,
        "create_defaults": {
            "brand_name": "Toshiba",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Toshiba/Kioxia MLC/TLC",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "16GB",
            "interface":  "eMMC 5.0",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Toshiba / Kioxia eMMC 5.0, 16GB, BGA153. "
            "Mouser / Kioxia America (Tier 1): listagem ativa ✓. "
            "Octopart (Tier 2, 11 distribuidores): '128G-bit 153-Pin FBGA' → 128Gb÷8=16GB ✓. "
            "pn[5]='F' → eMMC 5.0 (confirmado via THGBMFG7C2LBAIL, Puris /emmc-5-0/ ✓). "
            "Grammar já decoda corretamente — create=True promove estimated→confirmed. "
            "IA externa alegou profitable=RENTÁVEL errado — REFUTADO: regra atual = eMMC ≥ 8GB, sem distinção de versão."
        ),
    },

    # ── THGBMHG8C4LBAIR ──────────────────────────────────────────────────────
    # Toshiba / Kioxia eMMC 5.1, 32GB. Package BGA153 (153-Pin VFBGA).
    # Chip chegou na esteira — engine mostrou "chip desconhecido".
    #
    # Causa raiz do "desconhecido":
    #   A família THGBMHG (sub-prefixo len=7) ainda existia no banco com
    #   interface='eMMC 5.1' hardcoded mas SEM decode maps. O engine ordena
    #   por prefix_len DESC: THGBMHG (7) intercepta antes de THGBM (5).
    #   Com THGBMHG sem decode maps → capacity=None → grammar_complete=False
    #   → Gemini falhou ou não retornou specs → chip caiu em "desconhecido".
    #
    #   Fix estrutural: rodar `python manage.py populate_toshiba --overwrite`
    #   (THGBMHG está em OBSOLETE_FAMILY_PREFIXES → é deletado; 8C4+H já
    #   existem nos mapas do script). Este create=True adiciona entrada direta
    #   como KnownPart (Layer 1) que garante classificação mesmo antes do --overwrite.
    #
    # Attestation independente (2026-05-26) — regra de ouro aplicada:
    #
    # CONFIRMADO:
    #   • 32GB eMMC: Octopart (Tier 2): "Flash Card 32G-byte 3.3V Embedded MMC
    #     153-Pin VFBGA" — PN exato THGBMHG8C4LBAIR ✓ (32G-byte = 32GB ✓).
    #   • eMMC 5.1: pn[5]='H' → THGBM_GEN = "eMMC 5.1". Confirmado via âncora
    #     Lisleapex (Tier 3) + chip físico na esteira.
    #   • Chave 8C4 = 32GB: pn[7:10]='8C4' → THGBM_CAP = "32GB". Âncora
    #     original: Lisleapex (Tier 3). Promovida a Tier 2 com este PN via Octopart.
    #   • Package BGA153: Octopart "153-Pin VFBGA" ✓ (VFBGA = Very Fine-pitch BGA,
    #     mesmo package que BGA153 nos outros THGBM*).
    #
    # REFUTADO:
    #   • IA externa alegou que sufixo 'R' (pn[14]) causou o "desconhecido" →
    #     ERRADO. O decoder THGBM só lê pn[5] (GEN) e pn[7:10] (CAP). pn[14]
    #     é variante de bin/temperatura (R/L/7/8) e não interfere no decode.
    #     Causa real: sub-prefixo THGBMHG interceptando antes de THGBM.
    #
    # Nota: confidence="confirmed" (Tier 2 Octopart com PN exato).
    {
        "pn": "THGBMHG8C4LBAIR",
        "create": True,
        "create_defaults": {
            "brand_name": "Toshiba",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Toshiba/Kioxia MLC/TLC",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "32GB",
            "interface":  "eMMC 5.1",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Toshiba / Kioxia eMMC 5.1, 32GB, BGA153 (VFBGA). "
            "Octopart (Tier 2, PN exato): 'Flash Card 32G-byte 3.3V Embedded MMC 153-Pin VFBGA' → 32GB ✓. "
            "pn[5]='H' → THGBM_GEN = eMMC 5.1 (âncora Lisleapex Tier 3 + chip físico). "
            "pn[7:10]='8C4' → THGBM_CAP = 32GB (âncora Lisleapex Tier 3, promovida Tier 2 com este PN). "
            "Causa do 'desconhecido': sub-prefixo THGBMHG (len=7) interceptava THGBM (len=5) sem decode maps. "
            "Fix estrutural: `manage.py populate_toshiba --overwrite` (deleta THGBMHG). "
            "IA externa alegou sufixo R causou falha — REFUTADO: decoder só lê pn[5] e pn[7:10]."
        ),
    },

    # ── TYC0FH121638RA ───────────────────────────────────────────────────────
    # Toshiba eMCP — 4GB eMMC + 512MB LPDDR2. Package BGA-162.
    # Chip chegou na esteira sem classificação (engine não reconhece prefixo TYC).
    #
    # Attestation independente (2026-05-25) — regra de ouro aplicada:
    #
    # CONFIRMADO:
    #   • Chip real e Toshiba: Octopart, Jotrin, YIC Electronics, gsmbdshop.
    #   • 4GB eMMC: gsmbdshop "4GB EMMC GOOD NAND"; Octopart "4GB EMCP device" ✓
    #   • 512MB LPDDR2: Octopart "4Gb LPDDR2 + 4GB EMCP device" (4Gb ÷ 8 = 512MB) ✓
    #   • BGA-162: código produto TUSHIBA-004GE0-162; Martview BGA162 = LPDDR2 ✓
    #   • eMMC versão 4.5/4.51: Octopart confirma "MMC v4.5 and v4.51" — NÃO 4.41 ✓
    #
    # REFUTADO:
    #   • IA externa alegou "eMMC 4.41" → ERRADO. Octopart confirma MMC v4.5/v4.51.
    #   • IA alegou TYC0GH121654RA como PN irmão → NÃO confirmado; só
    #     TYC0GH131619RA encontrado como related part (sufixo diferente).
    #   • IA alegou "LPDDR3" para variante TYC0GH → provável erro: prefixo TYC
    #     corresponde a geração BGA-162 (LPDDR2), não BGA-221 (LPDDR3).
    #     TYD prefix = LPDDR3/BGA-221; TYC prefix = LPDDR2/BGA-162.
    #
    # NÃO VERIFICÁVEL:
    #   • "Usado em Micromax/Alcatel" — nenhuma fonte Tier 1-3 encontrada.
    #
    # Nota arquitetural: engine não tem ChipFamily TYC registrada.
    #   Família TYC (Toshiba eMCP LPDDR2) requer sessão separada para confirmar
    #   estrutura posicional do PN antes de adicionar ao banco.
    #   Este create=True garante classificação manual enquanto a família não existe.
    {
        "pn": "TYC0FH121638RA",
        "create": True,
        "create_defaults": {
            "brand_name": "Toshiba",
            "chip_type":  "eMCP",
            "subtype":    "eMCP Toshiba (eMMC + LPDDR2)",
            "status":     "enriched",
            "confidence": "distributor",
        },
        "fields": {
            "emcp_nand": "eMMC 4.5 4GB",
            "emcp_ram":  "LPDDR2 512MB",
        },
        "reason": (
            "Toshiba eMCP BGA-162. "
            "Octopart: '4Gb LPDDR2 + 4GB EMCP device' → 4GB eMMC + 512MB LPDDR2 (4Gb÷8). "
            "gsmbdshop: '4GB EMMC GOOD NAND'. Jotrin + YIC Electronics: chip real ✓. "
            "eMMC: MMC v4.5/v4.51 (Octopart). IA externa alegou v4.41 — ERRADO, refutado. "
            "Família TYC sem ChipFamily gramatical — create=True garante classificação manual."
        ),
    },

    # ── TYC0FH121626RA ───────────────────────────────────────────────────────
    # Toshiba eMCP — 4GB eMMC 4.5/4.51 + 512MB LPDDR2. Package BGA-162.
    # Variante de lote de TYC0FH121638RA (posições 10-11 diferem: 26 vs 38).
    #
    # Attestation independente (2026-05-25) — regra de ouro aplicada:
    #
    # CONFIRMADO:
    #   • Chip real e Toshiba: Octopart (4 distribuidores), YIC Electronics,
    #     Allelco — todos listam como "TOSHIBA BGA, Specialized ICs, TAEC Product".
    #   • 4GB NAND: título da página mehrinfo.net = "Toshiba TYCOFH121626RA 4G" ✓
    #     Decode estrutural: 0F = 4GB (TYC0GH = 8GB, contraste confirmado na sessão
    #     anterior com TYC0GH131619RA).
    #   • 512MB LPDDR2: confirmado via âncora TYC0FH121638RA (Octopart, Tier 2:
    #     "4Gb LPDDR2 + 4GB EMCP device" → 4Gb÷8=512MB). Mesma posição H12 em ambos.
    #   • eMMC 4.5/4.51: âncora TYC0FH121638RA (Octopart: "MMC v4.5/v4.51").
    #   • BGA-162: âncora TYC0FH121638RA (BGA-162 confirmado na sessão anterior);
    #     múltiplas fontes listam 1626RA como "BGA".
    #   • Variante de lote: TYC0FH12[lote]RA — cluster de irmãos confirmado
    #     (TYC0FH121597RA, 1626RA, 1638RA, 1642RA, 1645RA, 1660RA — todos BGA,
    #     Specialized ICs, TAEC Product no YIC e Allelco).
    #
    # Âncora principal: TYC0FH121638RA (Octopart Tier 2, entrada 39 acima).
    # Nota arquitetural: engine não tem ChipFamily TYC registrada.
    #   create=True garante classificação manual enquanto a família não existe.
    {
        "pn": "TYC0FH121626RA",
        "create": True,
        "create_defaults": {
            "brand_name": "Toshiba",
            "chip_type":  "eMCP",
            "subtype":    "eMCP Toshiba (eMMC + LPDDR2)",
            "status":     "enriched",
            "confidence": "distributor",
        },
        "fields": {
            "emcp_nand": "eMMC 4.5 4GB",
            "emcp_ram":  "LPDDR2 512MB",
        },
        "reason": (
            "Toshiba eMCP BGA-162, variante de lote de TYC0FH121638RA (posições 10-11: 26 vs 38). "
            "Âncora: TYC0FH121638RA (Octopart Tier 2): '4Gb LPDDR2 + 4GB EMCP device, MMC v4.5/v4.51'. "
            "mehrinfo.net (título): 'Toshiba TYCOFH121626RA 4G' — 4GB confirmado para este PN. "
            "Cluster de lote: TYC0FH121597/1626/1638/1642/1645/1660RA todos BGA Specialized ICs (YIC+Allelco ✓). "
            "Família TYC sem ChipFamily gramatical — create=True garante classificação manual."
        ),
    },

    # ── TY890A111229KC ───────────────────────────────────────────────────────
    # Toshiba Mobile SDR SDRAM. Package BGA.
    # Chip chegou na esteira sem classificação (engine não reconhece prefixo TY890A).
    #
    # Attestation independente (2026-05-25) — regra de ouro aplicada:
    #
    # CONFIRMADO:
    #   • Família TY890A = Toshiba Mobile SDR SDRAM: iFixit PS Vita Teardown (2012)
    #     Step 11 identifica TY890A111222KA como "Mobile SDR SDRAM" na placa do
    #     modem 3G Qualcomm MDM6200. Fonte Tier 2 de alta confiabilidade.
    #   • Package BGA: confirmado por OMO Electronic, IC-Components, Kynix, Utsource.
    #   • Chip é DRAM (RAM), NÃO eMMC, NÃO eMCP.
    #
    # REFUTADO:
    #   • IA externa alegou "Provável eMCP" → ERRADO. TY890A é SDRAM, não package
    #     combinado. Confusão provavelmente causada pelo prefixo "TY" (compartilhado
    #     com família eMCP TYC/TYD) e pelo package BGA.
    #
    # NÃO CONFIRMADO:
    #   • Capacidade exata da variante 111229KC: o decode posicional de "29" vs "22"
    #     (PS Vita) não foi encontrado em nenhuma fonte Tier 1-2. BLOQUEADO.
    #
    # Nota arquitetural: engine não tem ChipFamily TY890A registrada.
    #   Família requer sessão separada para confirmar estrutura posicional do PN.
    #   Este create=True garante classificação manual enquanto a família não existe.
    {
        "pn": "TY890A111229KC",
        "create": True,
        "create_defaults": {
            "brand_name": "Toshiba",
            "chip_type":  "DRAM",
            "subtype":    "Mobile SDR SDRAM (Toshiba)",
            "status":     "enriched",
            "confidence": "distributor",
        },
        "fields": {},
        "reason": (
            "Toshiba Mobile SDR SDRAM, BGA. "
            "Família TY890A confirmada por iFixit PS Vita Teardown (2012, Step 11): "
            "TY890A111222KA identificada como 'Mobile SDR SDRAM' no modem 3G do PS Vita. "
            "NÃO é eMMC nem eMCP — IA externa errou ao classificar como 'Provável eMCP'. "
            "Capacidade da variante 111229KC não confirmada em fonte Tier 2 — campo vazio."
        ),
    },

    # ── KLM8G1WEMB ───────────────────────────────────────────────────────────
    # Samsung eMMC 5.0 standalone, 8GB. Família KLM.
    # pn[3]='8' → SAM_FLASH_CAP = 8GB ✓ (distribuidor confirma "64Gbit ÷ 8 = 8GB").
    # pn[6]='W' → NÃO estava no SAM_EMMC_GEN → interface ficava "eMMC" (sem versão).
    # Fix sistêmico: 'W' adicionado ao SAM_EMMC_GEN como "eMMC 5.0" em populate_samsung.py.
    # ⚠ IA externa afirmou "W = eMMC 5.0 capaz de HS400" — PARCIALMENTE ERRADO.
    #   W = eMMC 5.0 CORRETO. Mas HS400 é eMMC 5.1, não 5.0. eMMC 5.0 usa HS200 (200MHz DDR).
    #   O datasheet confirma "200MHz DDR – up to 400MBps" — isso é HS200 DDR, não HS400.
    # Fontes:
    #   • Datasheet Samsung oficial (Tier 1 via repositório):
    #     Alldatasheet + datasheet4u: KLM8G1WEMB-B031 — "e.MMC 5.0 Specification compatibility"
    #     Rev. 1.0, Agosto 2013. Explícito no título do documento ✓ (2026-05-26)
    #   • Distribuidor: "Managed NAND Flash Serial e-MMC 64Gbit" → 64Gbit ÷ 8 = 8GB ✓
    # Destino: bancada reacondicional eMMC 5.0 (liquidez média — separar de 5.1).
    {
        "pn": "KLM8G1WEMB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Samsung",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "8GB",
            "interface":  "eMMC 5.0",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Datasheet Samsung oficial (Alldatasheet/datasheet4u, 2026-05-26): "
            "KLM8G1WEMB-B031 = 'e.MMC 5.0 Specification compatibility', 64Gbit = 8GB. "
            "pn[6]='W' não mapeado → interface=eMMC genérico — incompleto. "
            "Fix sistêmico: 'W' adicionado ao SAM_EMMC_GEN como eMMC 5.0. "
            "IA afirmou HS400 — ERRADO: W=eMMC 5.0 usa HS200 (não HS400 que é 5.1). "
            "confidence+status em fields: garante grammar_wins=False para registros existentes."
        ),
    },

    # ── KLMCG2KCTA ───────────────────────────────────────────────────────────
    # Samsung eMMC 5.1 standalone, 64GB. Família KLM.
    # pn[3]='C' → SAM_FLASH_CAP = 64GB ✓.
    # pn[6]='K' → NÃO estava no SAM_EMMC_GEN → interface ficava "eMMC" (sem versão) — INCOMPLETO.
    # Fix sistêmico: 'K' adicionado ao SAM_EMMC_GEN como "eMMC 5.1" em populate_samsung.py.
    # Fontes:
    #   • Samsung Semiconductor Global (Tier 1): "KLMCG2KCTA-B041(eMMC 5.1)" ✓
    #     semiconductor.samsung.com/estorage/emmc/emmc-5-1/klmcg2kcta-b041/ (2026-05-25)
    #   • Preduo (Tier 3): "eMMC 5.1, 64GB, Samsung, BGA" ✓
    #   • Octopart (Tier 2): 6 distribuidores ativos ✓
    # Destino: bancada reacondicional Flash eMMC 5.1 (alta liquidez — 64GB bom volume).
    {
        "pn": "KLMCG2KCTA",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Samsung",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "64GB",
            "interface":  "eMMC 5.1",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global (Tier 1, 2026-05-25): KLMCG2KCTA-B041 = eMMC 5.1, 64GB. "
            "pn[3]='C'=64GB correto. pn[6]='K' não mapeado → interface=eMMC (sem versão) — incompleto. "
            "Fix sistêmico: 'K' adicionado ao SAM_EMMC_GEN como eMMC 5.1. "
            "confidence+status em fields: garante grammar_wins=False para registros existentes."
        ),
    },

    # ── KMNJ2000ZM ───────────────────────────────────────────────────────────
    # Samsung eMCP LPDDR2 + eMMC. Família KMN (~2011-2014, entrada legada).
    #
    # PROBLEMA DETECTADO (2026-05-25):
    #   Sistema mostrava "eMMC 128GB + LPDDR2 6GB" — FISICAMENTE IMPOSSÍVEL.
    #   Chips LPDDR2 de 2011-2014 nunca chegaram a 128GB NAND + 6GB RAM.
    #
    # CAUSA RAIZ:
    #   Família KMN usa decode_cap_pos=3, decode_cap_map=SAM_EMCP_CAP.
    #   pn[3:5] = "J2" → SAM_EMCP_CAP["J2"] = 128GB+6GB (âncora KMQJ2·, moderna).
    #   Para a era KMN (LPDDR2, 2011-2014), a mesma posição pn[3:5]="J2" tem
    #   codificação completamente diferente — as densidades eram muito menores.
    #
    # FIX SISTÊMICO (populate_samsung.py):
    #   Família KMN corrigida: decode_cap_pos=None — sem decode de capacidade.
    #   Todos os chips KMN param de decodificar valores impossíveis.
    #   Capacidades específicas verificadas → via fix_known_parts (este arquivo).
    #
    # CAPACIDADE DESTE CHIP (KMNJ2000ZM):
    #   IA externa estimou: 8GB eMMC + 1GB LPDDR2 (Galaxy S Advance / S III mini).
    #   Sem fonte Tier 1 ou Tier 2 confirmada após múltiplas buscas (2026-05-25).
    #   BLOQUEADO: não registrar capacidade sem atestação (regra de ouro).
    #   Campos emcp_nand e emcp_ram deixados em branco até fonte verificada.
    #
    # IMPACTO OPERACIONAL:
    #   Destino sempre foi "Caixa Vermelha" (família KMN legada, LPDDR2 sem liquidez).
    #   Omitir capacidade não muda a rota — o tipo e a instrução de segregação
    #   são suficientes para o operador encaminhar corretamente.
    {
        "pn": "KMNJ2000ZM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR2 + eMMC (legado)",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "",   # bloqueado: sem fonte Tier 1-2 confirmada (2026-05-25)
            "emcp_ram":   "",   # bloqueado: idem
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Sistema mostrava 'eMMC 128GB + LPDDR2 6GB' — fisicamente impossível para 2011-2014. "
            "Causa: KMN decode pn[3:5]='J2' → SAM_EMCP_CAP moderna (128GB+6GB âncora KMQJ2·). "
            "Fix sistêmico: família KMN agora com decode_cap_pos=None (populate_samsung.py). "
            "Capacidade não confirmada em fonte Tier 1-2 após busca (2026-05-25) — bloqueada. "
            "IA estimou 8GB+1GB (Galaxy S Advance / S III mini era), mas sem atestação. "
            "confidence+status em fields: garante grammar_wins=False — evita decode errado no banco. "
            "Destino: Caixa Vermelha (LPDDR2 legado, sem liquidez em 2026)."
        ),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Chips Micron confirmados — 2026-05-26
    # ══════════════════════════════════════════════════════════════════════════

    # ── MT53B512M64D4TX ───────────────────────────────────────────────────────
    # LPDDR4 standalone Micron. FBGA code D9VFC.
    # Prefix MT53B = LPDDR4 nativo (VDDQ 1.1V) — ≠ MT53E (LPDDR4X 0.6V).
    # ⚠ NÃO misturar com MT53E: tensão incompatível pode causar colapso térmico.
    # Matemática: 512M × 64bit = 32.768 Mbit = 32Gb ÷ 8 = 4GB.
    # Octopart: MT53B512M64D4TX-053 WT:C TR = "32Gb 512M×64 1.1V 1866MHz" ✓
    # Família MT53B adicionada em add_chip_families.py (prefixo novo, 2026-05-26).
    # create=True: prefixo novo → chip nunca esteve no banco.
    {
        "pn": "MT53B512M64D4TX",
        "create": True,
        "create_defaults": {
            "brand_name": "Micron",
            "chip_type":  "RAM",
            "subtype":    "LPDDR4 standalone",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "4GB",
            "interface":  "LPDDR4",
            "confidence": "confirmed",
            "status":     "enriched",
            "source_url": "https://octopart.com/mt53b512m64d4tx-053+wt%3ac+tr-micron-122342782",
        },
        "reason": (
            "FBGA D9VFC (Micron cross-reference) = MT53B512M64D4TX. "
            "Octopart: 32Gb 512M×64bit ÷ 8 = 4GB LPDDR4. VDDQ 1.1V (≠ MT53E LPDDR4X 0.6V). "
            "Família MT53B adicionada em add_chip_families.py. "
            "Chip obsoleto, comum em flagships Android 2017-2019 (velocidade 1866MHz / 3733MT/s)."
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
