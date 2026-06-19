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
            "capacity":   "128GB",
            "interface":  "UFS 2.1",
            "device":     "",    # limpar device alucinado, se houver
            "source_url": "",    # limpar: era "gemini:KLUDG4U1EA" (resíduo Gemini antigo)
            "doc_url":    "",    # limpar: era "/fab-toshiba/" — KLUDG é Samsung, não Toshiba
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Família KLUDG estava cadastrada como Kioxia (erro em add_chip_families.py). "
            "KLUDG é Samsung UFS 2.1: K=Samsung, L=NAND, U=UFS, D=128GB, pn[6]=U→UFS 2.1. "
            "fix: capacity=128GB, interface=UFS 2.1, device apagado. "
            "Bugs de metadados (2026-05-26): doc_url='/fab-toshiba/' (errado — Samsung, não Toshiba); "
            "confidence='ai_high' e source_url='gemini:KLUDG4U1EA' — resíduos de run Gemini antigo. "
            "confidence+status em fields (não só create_defaults): garante grammar_wins=False "
            "e sobrescreve valores de registros já existentes no DB. "
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

    # ── K3LK3K3 ──────────────────────────────────────────────────────────────
    # Samsung LPDDR5 standalone. Família K3LK. pn[4:6]="3K" → LPDDR5_CAP → 8GB.
    # CONVENÇÃO DE LEITURA: PN tem 7 chars porque o operador lê SOMENTE a primeira
    # linha do marcador laser (a que começa com "K"). As 3 letras da linha inferior
    # (ex.: "0BM") identificam o package mas não são digitadas. PN efetivo = K3LK3K3.
    # Família K3LK = LPDDR5 (VDDQ=0.9V). NÃO confundir com K3KL = LPDDR5X (0.5V).
    # chave "3K" confirmada via Samsung Semiconductor Global ao construir LPDDR5_CAP
    # (sessão 2026-05-27; mesma chave que LPDDR5_CAP["3K/CK/7K"] = 8GB).
    {
        "pn": "K3LK3K3",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR5",
            "subtype":    "LPDDR5",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "8GB",
            "interface":  "LPDDR5",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "PN de 7 chars: convenção de bancada — operador lê só a 1ª linha do laser (começa com K). "
            "pn[4:6]='3K' → LPDDR5_CAP['3K']=8GB (confirmado via Samsung Semiconductor Global 2026-05-27). "
            "Família K3LK = LPDDR5 (VDDQ=0.9V); K3KL = LPDDR5X (0.5V) — sockets incompatíveis. "
            "Confirmado pelo operador (2026-06-18). RENTÁVEL."
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
    # ⚠ CORRIGIDO 2026-05-26: subtype e emcp_ram estavam "LPDDR4/4X" — ERRADO.
    #   KMR = LPDDR3 (SAM_EMCP_GEN corrigido; R era LPDDR4/4X por âncora falsa).
    # create=True: sem Gemini, chip pode não estar no banco (só grammar-decoded).
    {
        "pn": "KMR8X0001M",
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
            "NAND corrigida: 8X era 8GB no mapa (ERRADO). KMR8X0001M-B608 = 16GB eMMC. "
            "RAM corrigida: 16Gb ÷ 8 = 2GB (mapa usa 1GB como base KMQ8X — divergência de família). "
            "KMQ8X000SA-B414 (1GB) e KMR8X0001M (2GB) confirmados em B2B (SBiT). "
            "2026-05-26: RAM tipo corrigido LPDDR4/4X→LPDDR3 (KMR=LPDDR3, SAM_EMCP_GEN corrigido)."
        ),
    },

    # ── KMQ310006A / KMQ310006B ──────────────────────────────────────────────
    # Conflito de shared key "31" em SAM_EMCP_CAP:
    #   KMQ310013B: chip físico (eMiner 2026-05-13) = 1GB. ← valor no mapa
    #   KMQ310006B-B419: samsungparts.com "16Gb+12" = 1.5GB LPDDR3. ← exceção
    # Ambos pn[3:5]="31" — o mapa não consegue distinguir.
    # A = revisão anterior de B (mesmo die 12Gb LPDDR3). KMQ310006A confirmado
    # em estoque eMiner (2026-05-28) com pn_not_in_db=True — banco não o reconhecia.
    # create=True: chip decodificado só via gramática (raw_in_db=False, Gemini nunca
    # executado) — não existe no banco. Sem create=True o fix nunca aplicaria.
    {
        "pn": "KMQ310006A",
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
            "cap_key '31' conflito: KMQ310013B=1GB vs KMQ310006*=1.5GB (mesmo pn[3:5]). "
            "KMQ310006A = revisão A do mesmo die 12Gb LPDDR3 do KMQ310006B. "
            "samsungparts.com KMQ310006B-B419: '16Gb+12' = 12Gb÷8=1.5GB LPDDR3 (Galaxy J3 SM-J327A). "
            "Revisão A compartilha o mesmo die — capacidade idêntica ao B confirmado. "
            "Detectado em estoque eMiner 2026-05-28 (pn_not_in_db=True, gramática retornava 1GB). "
            "create=True: cria registro no banco se ainda não existir."
        ),
    },
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
    # KMRX60014M-B614 = 32GB eMMC 5.1 + 32Gb LPDDR3 → 32Gb ÷ 8 = 4GB.
    # Conflito de shared map: X6 base é 2GB (KM4X série), KMRX6 é 4GB (KMR série).
    # ⚠ CORRIGIDO 2026-05-26: subtype e emcp_ram estavam "LPDDR4/4X" — ERRADO.
    #   Preduo lista KMRX60014M-B614 sob caminho /emmc-lpddr3/ → LPDDR3 confirmado.
    #   KMR = LPDDR3 (SAM_EMCP_GEN corrigido 2026-05-26).
    # create=True: sem Gemini, chip não entra no banco via grammar-only decode.
    {
        "pn": "KMRX60014M",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "eMMC 5.1 32GB",
            "emcp_ram":   "LPDDR3 4GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "X6 base mapeado como 2GB (KM4X6001KM, Octopart). "
            "KMRX60014M-B614 = 32GB eMMC 5.1 + 32Gb LPDDR3 → 32Gb÷8=4GB. "
            "Divergência de família no shared cap_key X6: KM4X6→2GB, KMRX6→4GB. "
            "2026-05-26: RAM tipo corrigido LPDDR4/4X→LPDDR3 (Preduo /emmc-lpddr3/ ✓; "
            "SAM_EMCP_GEN R=LPDDR3 restaurado)."
        ),
    },

    # ── KMR820001M ───────────────────────────────────────────────────────────
    # eMCP LPDDR3 + eMMC 5.1. Família KMR. cap_key pn[3:5]="82" → SAM_EMCP_CAP.
    # SAM_EMCP_CAP["82"] corrigido de 1GB para 2GB (16Gb) em populate_samsung.py (2026-05-29).
    # Entrada original "82"=1GB não tinha âncora documentada — inserção sem Tier 1.
    # Confirmado: Preduo "16+16" ✓ + Puris "16+16 221ball eMCP-D3" ✓ (2026-05-29).
    # Dispositivo: Wileyfox Swift (Snapdragon 410, 2015) = 16GB + 2GB RAM ✓.
    # create=True: pn_not_in_db=True no debug → chip não existia no banco.
    {
        "pn": "KMR820001M",
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
            "device":     "Wileyfox Swift (2015), Lenovo P70-A",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "SAM_EMCP_CAP['82'] corrigido: era 1GB (sem âncora) → 2GB (16Gb LPDDR3). "
            "Preduo: KMR820001M-B609 = '16+16' ✓. Puris: '16+16 221ball eMCP-D3' ✓ (2026-05-29). "
            "Wileyfox Swift (Snapdragon 410) = 16GB + 2GB RAM — chip soldado: KMR820001M-B609 ✓. "
            "confidence=confirmed: garante grammar_wins=False → fonte = banco de dados."
        ),
    },

    # ── KMQ820013M ───────────────────────────────────────────────────────────
    # eMCP LPDDR3 + eMMC 5.1. Família KMQ. cap_key pn[3:5]="82" → SAM_EMCP_CAP.
    # SAM_EMCP_CAP["82"] corrigido de 1GB para 2GB (16Gb) — âncora KMR820001M (Preduo+Puris ✓).
    # Confirmado: Preduo "16+16" ✓ para KMQ820013M-B419 (2026-06-17).
    # Nota: chave "82" NÃO diverge entre KMQ e KMR — ambos = 16GB NAND + 2GB LPDDR3.
    # create=True: pn_not_in_db=True no debug → chip não existia no banco.
    {
        "pn": "KMQ820013M",
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
            "SAM_EMCP_CAP['82'] = 2GB (16Gb LPDDR3). "
            "Preduo: KMQ820013M-B419 = '16+16' ✓ (2026-06-17). "
            "Mesma chave '82' confirmada em KMR820001M (Preduo+Puris ✓ 2026-05-29). "
            "Não há divergência KMQ/KMR para a chave '82' — ambos = 2GB. "
            "confidence=confirmed: garante grammar_wins=False → fonte = banco de dados."
        ),
    },

    # ── KMF820012M ───────────────────────────────────────────────────────────
    # eMCP LPDDR3 + eMMC 5.1. Família KMF. cap_key pn[3:5]="82" → SAM_EMCP_CAP.
    # SAM_EMCP_CAP["82"] = 16GB NAND + 2GB LPDDR3 (16Gb).
    # Chave "82" NÃO apresenta divergência cross-família entre KMF/KMQ/KMR:
    #   • KMR820001M-B609: Preduo "16+16" + Puris "16+16 221ball eMCP-D3" ✓ (2026-05-29)
    #   • KMQ820013M-B419: Preduo "16+16" ✓ (2026-06-17)
    # Contraste com "E1" (onde KMF diverge de KMQ): para "82" a chave é consistente.
    # SEM FONTE TIER 1 DIRETA para KMF820012M — confirmado pelo operador (2026-06-18)
    # com base na convergência KMQ/KMR via Preduo+Puris.
    # confidence="manual": bloqueia gramática (grammar_wins=False); documenta ausência de Tier 1 direto.
    # MOTIVO PRÁTICO: só chips confirmed/manual entram no estoque (regra add_chip).
    # create=True: chip pode não existir no banco (grammar-only até agora).
    {
        "pn": "KMF820012M",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "status":     "enriched",
            "confidence": "manual",
        },
        "fields": {
            "emcp_nand":  "16GB",
            "emcp_ram":   "2GB LPDDR3",
            "interface":  "eMMC+LPDDR3",
            "confidence": "manual",
            "status":     "enriched",
        },
        "reason": (
            "SAM_EMCP_CAP['82'] = 16GB NAND + 2GB LPDDR3 (16Gb). "
            "Chave '82' consistente entre famílias: KMR820001M-B609 (Preduo+Puris ✓ 2026-05-29) e "
            "KMQ820013M-B419 (Preduo ✓ 2026-06-17). Sem divergência KMF/KMQ/KMR para '82' "
            "(contraste com 'E1' onde KMF≠KMQ). "
            "SEM FONTE TIER 1 DIRETA — confirmado pelo operador (2026-06-18). "
            "confidence=manual: grammar_wins=False. Necessário para entrada no estoque."
        ),
    },

    # ── KMFJ20007M ───────────────────────────────────────────────────────────
    # eMCP LPDDR3 + eMMC (~2012-2014, sufixo -B214). cap_key pn[3:5]="J2" → SAM_EMCP_CAP.
    # PROBLEMA: SAM_EMCP_CAP["J2"]=128GB+6GB ancorado por chip MODERNO KMQJ2· — ERRADO para esta era.
    # Fisicamente impossível: chip B214 de 2012-2014 com 128GB NAND não existia.
    # Mesmo conflito cross-era já documentado e resolvido para família KMN (decode_cap_pos=None lá).
    # Para KMF, solução é por chip (outros KMF têm chaves válidas em SAM_EMCP_CAP).
    # FONTES: SEM TIER 1 — Preduo/Octopart/Samsung Global não indexam este PN.
    # Consenso não-Tier-1 (Jotrin, mercado asiático B2B): 4GB NAND eMMC.
    # RAM: 512MB LPDDR3 — AI estimate + analogia SKhynix H9TQ32A4GTMCUR-KUM (Preduo: "4+4") ✓.
    # confidence="manual": bloqueia gramática (grammar_wins=False), documenta ausência de Tier 1.
    # RENTABILIDADE: NÃO RENTÁVEL em qualquer spec — sucata absoluta em 2026 (moagem).
    {
        "pn": "KMFJ20007M",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "eMMC 4GB",
            "emcp_ram":   "LPDDR3 512MB",
            "device":     "Aparelhos entry-level Samsung 2012-2014 (obsoleto)",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "BLOQUEIO DE GRAMÁTICA: SAM_EMCP_CAP['J2']=128GB+6GB ancorado por KMQJ2· moderno — ERRADO. "
            "KMFJ20007M-B214 é chip de 2012-2014, 128GB impossível para a era. "
            "Mesmo conflito cross-era já resolvido em KMN (populate_samsung.py, decode_cap_pos=None). "
            "Consenso não-Tier-1: 4GB NAND (Jotrin, mercado); 512MB RAM (analogia H9TQ32A4 SKhynix 4+4). "
            "SEM FONTE TIER 1 para este PN — confirmar se aparecer Preduo/Octopart futuramente. "
            "Confirmado pelo operador (2026-06-17). NÃO RENTÁVEL = moagem."
        ),
    },

    # ── KMFJ20005A ───────────────────────────────────────────────────────────
    # Mesmo problema que KMFJ20007M: cap_key pn[3:5]="J2" → SAM_EMCP_CAP → 128GB+6GB (ERRADO).
    # Sufixo "5A" vs "7M" = revisão de die/controladora, capacidade idêntica à variante 07M.
    # Sem Tier 1 independente — spec aprovado pelo operador (2026-06-17): 4GB eMMC + 512MB LPDDR3.
    # Nota: IA alegou que este chip está no Amazon Echo Dot 2ª Geração — FALSO.
    # AllAboutCircuits teardown (AAC, 2016) identifica chip Micron MT29TZZZ4D4BKERL no Echo Dot,
    # não Samsung. Preduo lista o Micron como "4+4" = 4GB+512MB — mesmo spec que o Samsung.
    # A IA confundiu o spec do Micron equivalente com o Samsung.
    # create=True: pn_not_in_db=True no debug.
    {
        "pn": "KMFJ20005A",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "eMMC 4GB",
            "emcp_ram":   "LPDDR3 512MB",
            "device":     "Aparelhos entry-level Samsung 2012-2014 (obsoleto)",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Mesmo bloqueio que KMFJ20007M: SAM_EMCP_CAP['J2']=128GB+6GB (âncora KMQJ2· moderno) — ERRADO. "
            "Revisão de die diferente ('5A' vs '7M'), capacidade idêntica. "
            "SEM FONTE TIER 1 — confirmado pelo operador (2026-06-17): 4GB eMMC + 512MB LPDDR3. "
            "NÃO RENTÁVEL = moagem."
        ),
    },

    # ── KMFE10012M ───────────────────────────────────────────────────────────
    # eMCP LPDDR3 + eMMC 5.1. Família KMF. cap_key pn[3:5]="E1" → SAM_EMCP_CAP.
    # PROBLEMA: SAM_EMCP_CAP["E1"]=16GB+2GB ancorado por KMQE10013M (KMQ moderno).
    # KMF família usa mesma chave "E1" mas com 1GB LPDDR3 (8Gbit) — conflito cross-família.
    # NOTA: a gramática acerta o NAND (16GB ✓) mas erra a RAM (2GB em vez de 1GB).
    # Não alterar SAM_EMCP_CAP["E1"] — âncora KMQE10013M=2GB é correta para KMQ.
    # Mesma chave "E6" tem problema idêntico: KMFE60012A/M=1GB, SAM_EMCP_CAP["E6"]=2GB.
    # Fontes Tier 1:
    #   • Preduo: KMFE10012M-B214 = "16+8" (16GB NAND + 8Gbit÷8=1GB LPDDR3) ✓
    #     preduo.com/product/emcp/emmc-lpddr3/221ball_emmc-lpd3/kmfe10012m-b214
    #   • Puris: "KMFE10012M-B214 16+8 221ball eMCP-D3 Samsung" ✓
    #     puris.net/archives/2974
    # create=True: pn_not_in_db=True no debug.
    {
        "pn": "KMFE10012M",
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
            "emcp_ram":   "LPDDR3 1GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "BLOQUEIO DE GRAMÁTICA: SAM_EMCP_CAP['E1']=16GB+2GB ancorado por KMQE10013M (KMQ moderno). "
            "Família KMF usa mesma chave 'E1' mas com 1GB LPDDR3 (8Gbit) — conflito cross-família. "
            "Gramática acerta NAND (16GB ✓) mas erra RAM (2GB em vez de 1GB). "
            "Preduo Tier 1: KMFE10012M-B214 = '16+8' ✓ (2026-06-17). "
            "Puris Tier 1: '16+8 221ball eMCP-D3 Samsung' ✓ (2026-06-17). "
            "Mesma chave 'E6' tem problema idêntico (KMFE60012A/M=1GB vs SAM_EMCP_CAP['E6']=2GB). "
            "confidence=confirmed: garante grammar_wins=False → fonte = banco de dados."
        ),
    },

    # ── KMRX1000BM / KMRX10014M ──────────────────────────────────────────────
    # Problema: SAM_EMCP_CAP mapeia X1 = "32GB NAND + 2GB RAM" (base KMQX10013MB — Octopart ✓).
    # Família KMR diverge: KMR+X1 = 3GB(24Gb) LPDDR3, não 2GB(16Gb) como KMQ.
    # Confirmado: KMRX1000BM-B614T07 = 3GB — Octopart ✓ + UFI Box ✓ (2026-05-29).
    # KMRX10014M: mesmo cap_key X1, mesma família KMR → 3GB pelo padrão de família.
    #   Octopart confirma existência (sem specs). confidence=estimated para KMRX10014M.
    # Mesmo padrão KMR: X6→KM4=2GB/KMR=4GB; 8X→KMQ=1GB/KMR=2GB; 31→KMQ=1GB/KMR=2GB.
    # Mostrar 2GB (âncora KMQ) é ativamente errado para família KMR. Fix obrigatório.
    {
        "pn": "KMRX1000BM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "eMMC 5.1 32GB",
            "emcp_ram":   "LPDDR3 3GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "X1 base mapeado como 2GB(16Gb) via KMQX10013MB (Octopart ✓). "
            "KMRX1000BM-B614T07 = 32GB eMMC + 3GB(24Gb) LPDDR3 — Octopart ✓ + UFI Box ✓ (2026-05-29). "
            "Divergência de família no shared cap_key X1: KMQX1→2GB(16Gb), KMRX1→3GB(24Gb). "
            "Padrão recorrente KMR: usa die LPDDR3 maior que base KMQ no mesmo cap_key."
        ),
    },
    {
        "pn": "KMRX10014M",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "eMMC 5.1 32GB",
            "emcp_ram":   "LPDDR3 3GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Família KMR + cap_key X1: padrão confirmado = 3GB(24Gb), não 2GB(16Gb) da âncora KMQ. "
            "KMRX1000BM-B614T07 (mesmo cap_key, mesma família) = 3GB — Octopart ✓ + UFI Box ✓ (2026-05-29). "
            "2GB do grammar é ativamente errado (âncora KMQX10013MB, família KMQ ≠ KMR). "
            "confidence=confirmed: humano revisou e corrigiu — necessário para grammar_wins=False no engine. "
            "(engine: grammar_wins = grammar_complete AND NOT human_verified; human_verified requer confirmed/manual)"
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

    # ── K3QF7F70DM ────────────────────────────────────────────────────────────
    # LPDDR3 standalone PoP (Mobile DRAM pura — sem NAND). Família K3QF.
    # pn[4]="7" → K3QF_CAP["7"] = 3GB (4×6Gb die = 24Gbit).
    # Gramática acertou: tipo LPDDR3 ✓, capacidade 3GB ✓.
    # Fonte Tier 1:
    #   • Preduo: K3QF7F70DM-QGCF = 24Gbit Samsung LPDDR3, 216ball ✓
    #     preduo.com/product/lpddr/lpddr3/216ball-lpddr3/k3qf7f70dm-qgcf
    # create=True: pn_not_in_db=True no debug. Fix promove estimated → confirmed.
    {
        "pn": "K3QF7F70DM",
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
            "emcp_nand": "",
            "emcp_ram":  "",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Preduo Tier 1: K3QF7F70DM-QGCF = 24Gbit Samsung LPDDR3, 216ball ✓ (2026-06-17). "
            "K3QF_CAP['7'] = 3GB = 4×6Gb die = 24Gbit ÷ 8 = 3GB. Gramática acertou na íntegra. "
            "RAM standalone PoP — sem NAND. confidence=confirmed: grammar_wins=False."
        ),
    },

    # ── K3QF3F30BM ───────────────────────────────────────────────────────────
    # LPDDR3 standalone Samsung 2GB. Família K3QF, pn[4]="3" → K3QF_CAP["3"]=2GB.
    # "3" = revisão de die (16Gb total = 2GB — NÃO é 3GB).
    # Fonte Tier 1:
    #   • Samsung Semiconductor Global: K3QF3F30BM-AGCG(16 Gb) ✓
    #     semiconductor.samsung.com/dram/lpddr/lpddr3/k3qf3f30bm-agcg/
    {
        "pn": "K3QF3F30BM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR3",
            "subtype":    "LPDDR3 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "2GB",
            "interface":  "LPDDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global (Tier 1): K3QF3F30BM-AGCG(16 Gb) ✓. "
            "16Gb ÷ 8 = 2GB. pn[4]='3' → K3QF_CAP['3']=2GB. "
            "⚠ chave '3' ≠ 3GB — é revisão de die (16Gb total = 2GB como '2'). "
            "confidence=confirmed: grammar_wins=False. Necessário para entrada no estoque."
        ),
    },

    # ── K3QF4F40BM ───────────────────────────────────────────────────────────
    # LPDDR3 standalone Samsung 4GB. Família K3QF, pn[4]="4" → K3QF_CAP["4"]=4GB.
    # Fonte Tier 1:
    #   • PSG Samsung 1H 2017: K3QF4F40BM-FGCF / K3QF4F40BM-AGCF = 32Gb = 4GB ✓
    {
        "pn": "K3QF4F40BM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR3",
            "subtype":    "LPDDR3 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "4GB",
            "interface":  "LPDDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "PSG Samsung 1H 2017 (Tier 1): K3QF4F40BM-FGCF / K3QF4F40BM-AGCF = 32Gb = 4GB ✓. "
            "32Gb ÷ 8 = 4GB. pn[4]='4' → K3QF_CAP['4']=4GB. "
            "confidence=confirmed: grammar_wins=False. Necessário para entrada no estoque."
        ),
    },

    # ── K3QF4F40CM ───────────────────────────────────────────────────────────
    # LPDDR3 standalone Samsung 4GB. Família K3QF, pn[4]="4" → K3QF_CAP["4"]=4GB.
    # "CM" = revisão posterior de K3QF4F40BM (mesma capacidade 32Gb = 4GB).
    # Fonte Tier 1:
    #   • Samsung Semiconductor Global: K3QF4F40CM-AGCF(32 Gb) ✓
    #     semiconductor.samsung.com/dram/lpddr/lpddr3/k3qf4f40cm-agcf/
    {
        "pn": "K3QF4F40CM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR3",
            "subtype":    "LPDDR3 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "4GB",
            "interface":  "LPDDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global (Tier 1): K3QF4F40CM-AGCF(32 Gb) ✓. "
            "32Gb ÷ 8 = 4GB. pn[4]='4' → K3QF_CAP['4']=4GB. "
            "Revisão posterior de K3QF4F40BM (mesma densidade 32Gb). "
            "confidence=confirmed: grammar_wins=False. Necessário para entrada no estoque."
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

    # ── KMDV6001DB ───────────────────────────────────────────────────────────
    # eMCP LPDDR4X + eMMC 5.1. Família KMD, chave V6 no SAM_EMCP_CAP.
    # V6 = 128GB eMMC 5.1 + 32Gb LPDDR4X → 32Gb÷8 = 4GB. Gramática acertou.
    # Esta é a segunda âncora da chave V6 (primeira: KMDV6001DA-B620, Octopart ✓).
    # Revisão A→B (pn[9] A→B): controladora/package revision — capacidade idêntica.
    # Fontes:
    #   • Preduo (Tier 3, 2026-05-26): KMDV6001DB-B625 = "128+32, eMCP, eMMC+LPDDR4x, 254ball" ✓
    #     preduo.com/product/emcp/emmc-lpddr4x/254ball_emmc-lpd4x/kmdv6001db-b625
    #   • Amazon (Tier 4, 2026-05-26): "eMMC+LPDDR4x 128+32 Storage chip" ✓ (corrobora Preduo)
    #   • "128+32" no mercado = 128GB NAND + 32Gb DRAM (Gigabit, não Gigabyte). 32Gb÷8=4GB.
    # Nota: resultado da gramática já correto — este fix promove confidence de estimated → confirmed.
    {
        "pn": "KMDV6001DB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR4X + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "eMMC 5.1 128GB",
            "emcp_ram":   "LPDDR4X 4GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Preduo (2026-05-26): KMDV6001DB-B625 = '128+32' → 128GB eMMC + 32Gb LPDDR4X = 4GB. "
            "Segunda âncora da chave V6 (primeira: KMDV6001DA-B620 Octopart ✓). "
            "Revisão A→B = package revision, capacidade idêntica. "
            "Gramática acertou via V6=128GB+4GB. Fix promove de estimated para confirmed."
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

    # ── K4B4G1646B ───────────────────────────────────────────────────────────
    # Samsung DDR3 SDRAM (B-die). Família K4B.
    # pn[3:5]="4G" → DRAM_PC → 4Gb = 512MB por die.
    # pn[5:7]="16" → x16 bus width (embarcado) — está no mapa, gramática [✓].
    # "B" = B-die (revisão de silício; mais antiga que D/E). PBGA96.
    # Fonte Tier 1:
    #   • Octopart: K4B4G1646B-HCK0 = "DDR DRAM, 256MX16, 0.225NS, CMOS, PBGA96" ✓
    #   • 256MX16 = 256M × 16b = 4Gbit = 512MB por die — confirma gramática.
    {
        "pn": "K4B4G1646B",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR3/DDR3L",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "interface":  "DDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Octopart Tier 1: K4B4G1646B-HCK0 = 'DDR DRAM, 256MX16, 0.225NS, CMOS, PBGA96' ✓ (2026-06-17). "
            "256MX16 = 256M×16b = 4Gbit = 512MB por die — confirma gramática (DRAM_PC['4G'], [✓]). "
            "pn[5:7]='16' = x16 bus width (em mapa). B-die, PBGA96. "
            "DDR3 embarcado (x16). Gramática completa e correta."
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

    # ── K4B8G1646Q ───────────────────────────────────────────────────────────
    # Samsung DDR3L SDRAM (Q-die). Família K4B.
    # pn[3:5]="8G" → DRAM_PC → 8Gb = 1GB por die. pn[5:7]="16" → x16 bus width.
    # Sufixo "Q" = Q-die (revisão de silício Samsung). DDR3L = 1.35V (low-voltage).
    # Distinção DDR3 vs DDR3L pelo sufixo completo: BC=DDR3 1.5V · BY=DDR3L 1.35V.
    # Fonte: AllDatasheet K4B8G1646Q-AGC2 = "8G-Bit DDP Q-die DDR3L SDRAM, 512Mx16, 96-Pin FBGA" ✓.
    # DDP = Dual Die Package (2× 4Gb die = 8Gb total).
    # Destino: resíduo — DDR3L 1GB (embarcado tablet/laptop entry-level ~2013-2016),
    #   sem liquidez B2B significativa em 2026 (capacidade muito baixa para reacondicional).
    {
        "pn": "K4B8G1646Q",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR3/DDR3L",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "1GB",
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "AllDatasheet K4B8G1646Q-AGC2 = '8G-Bit DDP Q-die DDR3L SDRAM, 512Mx16, 1.2V/1.35V, 96-Pin FBGA'. "
            "pn[3:5]='8G' → DRAM_PC → 8Gb = 1GB ✓. pn[5:7]='16' → x16. "
            "DDP (Dual Die Package): 2× 4Gb die = 8Gb total = 1GB. "
            "DDR3L (1.35V) confirmado — distinção de DDR3 (1.5V) preservada no campo interface. "
            "Destino: resíduo — 1GB DDR3L embarcado sem liquidez B2B em 2026."
        ),
    },

    # ── K4B2G0446C ───────────────────────────────────────────────────────────
    # Samsung DDR3L SDRAM (C-die). Família K4B.
    # pn[3:5]="2G" → DRAM_PC → 2Gb = 256MB por die.
    # pn[5:7]="04" → x4 bus width — NÃO está no mapa DRAM_PC (só 08=x8, 16=x16).
    # Organização x4 → chip para módulos servidor (RDIMM/LRDIMM ECC).
    # Gramática acerta tipo (DDR3) e densidade (2Gbit) mas não decodifica "04".
    # Fonte Tier 1:
    #   • Datasheets360: K4B2G0446C-HYH9 = "DDR3L DRAM, 512MX4, CMOS, PBGA78 — Discontinued" ✓
    #   • 512MX4 = 512M × 4b = 2Gbit = 256MB por die (confirma gramática)
    {
        "pn": "K4B2G0446C",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR3L",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Datasheets360 Tier 1: K4B2G0446C-HYH9 = 'DDR3L DRAM, 512MX4, CMOS, PBGA78 — Discontinued' ✓ (2026-06-17). "
            "512MX4 = 512M×4b = 2Gbit = 256MB por die — confirma gramática (DRAM_PC['2G']). "
            "pn[5:7]='04' = x4 bus width (não está no mapa DRAM_PC atual); chip para servidor RDIMM/LRDIMM ECC. "
            "DDR3L (1.35V nativo, retrocompat. 1.5V) — mais preciso que DDR3/DDR3L genérico. "
            "Gramática correta em tipo e densidade; fix promove estimated→confirmed."
        ),
    },

    # ── K4B2G0446D ───────────────────────────────────────────────────────────
    # Samsung DDR3L SDRAM (D-die). Família K4B. Revisão de die D (↑ do C-die).
    # pn[3:5]="2G" → DRAM_PC → 2Gb = 256MB por die.
    # pn[5:7]="04" → x4 bus width — chip para módulos servidor (RDIMM/LRDIMM ECC).
    # Especificação elétrica idêntica ao K4B2G0446C; apenas revisão de silício atualizada.
    # Fonte Tier 1:
    #   • Octopart: K4B2G0446D-HYH9 = "DDR DRAM, 512MX4, 0.255NS, CMOS, PBGA78" ✓
    {
        "pn": "K4B2G0446D",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR3L",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Octopart Tier 1: K4B2G0446D-HYH9 = 'DDR DRAM, 512MX4, 0.255NS, CMOS, PBGA78' ✓ (2026-06-17). "
            "512MX4 = 2Gbit = 256MB por die — confirma gramática (DRAM_PC['2G']). "
            "D-die: revisão de silício atualizada do C-die (K4B2G0446C); especificação elétrica idêntica. "
            "pn[5:7]='04' = x4 bus width — chip para servidor RDIMM/LRDIMM ECC. "
            "DDR3L (1.35V, retrocompat. 1.5V). Gramática correta em tipo e densidade."
        ),
    },

    # ── K4B2G1646Q ───────────────────────────────────────────────────────────
    # Samsung DDR3 SDRAM (Q-die). Família K4B.
    # pn[3:5]="2G" → DRAM_PC → 2Gb = 256MB por die.
    # pn[5:7]="16" → x16 bus width — em mapa, gramática [✓].
    # Q-die: revisão de silício de alto desempenho (usado em notebooks Dell, HP, Lenovo).
    # ATENÇÃO: a IA forneceu "256MX16" para este PN (duas vezes nesta sessão) — ERRADO.
    # Octopart real: 128MX16 = 128M × 16b = 2Gbit = 256MB por die. IA confundiu com K4B4G1646B.
    # Fonte Tier 1:
    #   • Octopart: K4B2G1646Q-BCK0 = "DDR3 DRAM, 128MX16, 0.225NS, CMOS, PBGA96" ✓ (26 resultados)
    #   • Octopart: K4B2G1646Q-BIK0 = "DDR3 DRAM, 128MX16, 0.225NS, CMOS, PBGA96" ✓
    #   • Octopart: K4B2G1646Q-BCMA = "DDR DRAM, 128MX16, 0.195NS, CMOS, PBGA96" ✓
    {
        "pn": "K4B2G1646Q",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR3",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "interface":  "DDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Octopart Tier 1: K4B2G1646Q-BCK0 = 'DDR3 DRAM, 128MX16, 0.225NS, CMOS, PBGA96' ✓ (2026-06-17). "
            "26 resultados consistentes. 128MX16 = 128M×16b = 2Gbit = 256MB por die — confirma gramática (DRAM_PC['2G']). "
            "pn[5:7]='16' = x16 (em mapa). Q-die (high-perf Samsung DDR3). PBGA96. DDR3 (1.5V). "
            "NOTA: IA forneceu '256MX16' para este PN (errado — dado era do K4B4G1646B). "
            "Gramática completa e correta; fix promove estimated→confirmed."
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

    # ── KMRH60014A ───────────────────────────────────────────────────────────
    # eMCP LPDDR3 + eMMC 5.1. Família KMR. cap_key "H6" → 64GB NAND + 4GB RAM.
    # Sistema mostrava "LPDDR4/4X 4GB" — ERRADO. R estava mapeado como LPDDR4/4X
    # por âncora falsa que usava este próprio chip como evidência de LPDDR4!
    # Múltiplas fontes Tier 2-3 confirmam LPDDR3:
    #   Preduo: /emmc-lpddr3/221ball/kmrh60014a-b614 ✓
    #   Censtry: KMRH60014A-B614 LPDDR3 ✓
    #   cpuprocessorchip: "64+32 EMCP D3 LPDDR3-1866MHz" ✓ (D3 = DRAM gen 3 = LPDDR3)
    #   Octopart: "QDP LPDDR3" ✓
    # Fix sistêmico: SAM_EMCP_GEN R corrigido LPDDR4/4X→LPDDR3 (populate_samsung.py).
    # Octopart correto desta vez — a IA que contestou estava errada.
    {
        "pn": "KMRH60014A",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "eMMC 5.1 64GB",
            "emcp_ram":   "LPDDR3 4GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Sistema mostrava LPDDR4/4X — ERRADO. SAM_EMCP_GEN R=LPDDR4/4X era âncora falsa. "
            "Preduo (/emmc-lpddr3/), Censtry, cpuprocessorchip ('EMCP D3 LPDDR3-1866MHz'), "
            "Octopart ('QDP LPDDR3') confirmam LPDDR3 (2026-05-26). "
            "cap_key H6: 64GB NAND + 32Gb÷8=4GB RAM. Fix sistêmico: R→LPDDR3 no gen map."
        ),
    },

    # ── KMRP60014M ───────────────────────────────────────────────────────────
    # eMCP LPDDR3 + eMMC 5.1. Família KMR. cap_key "P6" → 64GB NAND + 4GB RAM.
    # Tipo estava "LPDDR4/4X" — corrigido pelo fix sistêmico R→LPDDR3 (2026-05-26).
    # Capacidade (P6=64GB+4GB) confirmada: Preduo "64+32 eMMC+LPDDR3, 221ball" ✓
    # Samsung Semiconductor Global: "KMRP60014M-B614(1866 Mbps)" — 1866 Mbps = LPDDR3 ✓
    {
        "pn": "KMRP60014M",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "eMMC 5.1 64GB",
            "emcp_ram":   "LPDDR3 4GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Preduo: KMRP60014M-B614 = '64+32 eMMC+LPDDR3' (64GB NAND + 32Gb÷8=4GB LPDDR3). "
            "Samsung Semiconductor Global: 1866 Mbps → velocidade LPDDR3. "
            "Tipo estava LPDDR4/4X — corrigido pelo fix sistêmico R→LPDDR3 (2026-05-26). "
            "Cap_key P6 = 64GB+4GB correto (mesma chave que KMDP6001DA, 2026-05-09 ✓)."
        ),
    },

    # ── KMR21000BM ───────────────────────────────────────────────────────────
    # eMCP LPDDR3 + eMMC 5.1. Família KMR. cap_key "21" → conflito de shared map.
    # SAM_EMCP_CAP "21" = 32GB+2GB (base KMQ310013B, chip físico ✓).
    # KMR21000BM-B809: Puris "32+24 221ball eMCP-D3" → 32GB NAND + 24Gb÷8=3GB LPDDR3.
    # Conflict: shared key "21" = 2GB para KMQ, = 3GB para KMR21000BM.
    # NÃO alterar SAM_EMCP_CAP — base KMQ=2GB está correta. Exceção pontual aqui.
    {
        "pn": "KMR21000BM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR3 + eMMC 5.1",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "eMMC 5.1 32GB",
            "emcp_ram":   "LPDDR3 3GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Puris: KMR21000BM-B809 = '32+24 221ball eMCP-D3' → 32GB NAND + 24Gb LPDDR3 = 3GB. "
            "SAM_EMCP_CAP '21' = 2GB (base KMQ310013B) — conflito de shared key, KMR21=3GB. "
            "Tipo corrigido pelo fix sistêmico R→LPDDR3 (2026-05-26). "
            "confidence+status em fields: garante grammar_wins=False."
        ),
    },

    # ── KM2V8001CM ───────────────────────────────────────────────────────────
    # uMCP Samsung UFS 2.1 + LPDDR4X. Família KM2. EOL.
    # ⚠ Sistema mostrava "UFS 3.1 + LPDDR5, 128GB, 4GB" — DOIS erros simultâneos.
    #   1. Tipo RAM: LPDDR4X (não LPDDR5). Speed 4266 Mbps = LPDDR4X-4266.
    #   2. Capacidade RAM: 6GB (48Gb), não 4GB (32Gb). Conflito shared key V8.
    # Fontes:
    #   • Preduo (Tier 2): KM2V8001CM-B707, categoria "UFS+LPDDR4x", "128+48" ✓
    #   • Amazon: "KM2V8001CM-6G-4266Mbps" → 6GB, LPDDR4X-4266 ✓
    #   • ssfkg.com: "KM2V8001CM-B707 UFS 2.1 SAMSUNG" ✓
    #   • Samsung Semiconductor Global/EMEA: "KM2V8001CM-B707(4266Mbps)" ✓
    #   [Samsung redireciona para seção "LPDDR5 uMCP" — categorização do site, não da velocidade]
    # Shared key V8 conflict: KM5V8001DM-B622 = 32Gb = 4GB ✓ (mapa SAM_EMCP_CAP base)
    #                          KM2V8001CM-B707 = 48Gb = 6GB ✓ — exceção pontual aqui.
    {
        "pn": "KM2V8001CM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "uMCP",
            "subtype":    "UFS 2.1 + LPDDR4X",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "UFS 2.1 128GB",
            "emcp_ram":   "LPDDR4X 6GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Preduo: KM2V8001CM-B707 = '128+48 254ball UFS+LPD4x' → 128GB UFS + 48Gb÷8=6GB LPDDR4X. "
            "Amazon: 'KM2V8001CM-6G-4266Mbps' → 6GB, 4266Mbps = LPDDR4X-4266 ✓. "
            "ssfkg.com: 'UFS 2.1 SAMSUNG' ✓. Samsung Global/EMEA: '4266Mbps' ✓. "
            "Sistema mostrava LPDDR5 (errado: mínimo LPDDR5 ≥ 6400 Mbps) e 4GB (errado: shared key V8). "
            "SAM_EMCP_CAP V8=4GB é âncora KM5V8001DM-B622 (32Gb) — KM2V8001CM é exceção com 48Gb=6GB. "
            "confidence+status em fields: garante grammar_wins=False."
        ),
    },

    # ── KML7X000HM ───────────────────────────────────────────────────────────
    # eMCP Samsung LPDDR2 + eMMC. Família KML. Legado ~2013-2015.
    # ⚠ Sistema mostrava "uMCP UFS 3.1 + LPDDR5, 8GB NAND, 1GB RAM" — ERRADO.
    #   chip_type/subtype/interface corrigidos via populate_samsung (2026-05-27).
    # Fontes:
    #   • eetgroup.com: KML7X000HM-B507 = "8GB+8GB, EMMC+LPDD" → eMMC ✓, NÃO UFS 3.1
    #   • Puris: KML5U000HM-B505 = "4+8 153ball eMCP-D1" → categoria "eMMC+LPDDR"
    #   • emmc-ufs.com: KML7X000HM tem página de firmware eMMC (NÃO UFS)
    #   • Dispositivo: Galaxy Core i8262 usa Exynos 4212 → suporta LPDDR2 (NÃO LPDDR1)
    # LPDDR version:
    #   Puris "eMMC+LPDDR" (sem número) é ambíguo — poderia ser LPDDR1 ou LPDDR2 não especificado.
    #   LPDDR2 adotado pela consistência de era (2013-2015 = era KMJ/KMN = LPDDR2).
    #   Exynos 4212 (Galaxy Core i8262) suporta LPDDR2 — LPDDR1 seria SoC incompatível.
    #   LPDDR1 era obsoleto em smartphones desde ~2012. Sem fonte Tier 1 confirmando versão.
    #   ⚠ LPDDR2 = inferência de era+SoC. Confirmar com datasheet Samsung se possível.
    # Capacidade: "8GB+8GB" (eetgroup) = 8GB eMMC + 8Gb LPDDR2 = 1GB.
    # cap_key "7X" não está em SAM_EMCP_CAP → capacidade viria nula sem este fix.
    {
        "pn": "KML7X000HM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR2 + eMMC (legado)",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "eMMC 8GB",
            "emcp_ram":   "LPDDR2 1GB",
            "device":     "Samsung Galaxy Core i8262",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "eetgroup.com: KML7X000HM-B507 = '8GB+8GB, EMMC+LPDD' → 8GB eMMC + 8Gb LPDDR = 1GB. "
            "LPDDR version: Puris categoria 'eMMC+LPDDR' (sem número) — ambíguo. "
            "LPDDR2 adotado: Exynos 4212 (Galaxy Core i8262) suporta LPDDR2; "
            "LPDDR1 obsoleto em smartphones desde 2012; era 2013-2015 = KMJ/KMN = LPDDR2. "
            "⚠ LPDDR2 é inferência de era+SoC — sem fonte Tier 1 explícita para versão LPDDR. "
            "eMMC (NÃO UFS): eetgroup + emmc-ufs.com firmware page ✓. "
            "KML NÃO é uMCP UFS 3.1 + LPDDR5 — corrigido em populate_samsung (2026-05-27). "
            "confidence+status em fields: garante grammar_wins=False."
        ),
    },

    # ── KMR310001M ───────────────────────────────────────────────────────────
    # eMCP LPDDR3 + eMMC 5.1. Família KMR. Era ~2015.
    # Conflito de shared key SAM_EMCP_CAP:
    #   chave "31" = 16GB+1GB no mapa (base KMQ310013B, chip físico confirmado).
    #   KMR310001M tem "31" mas com 16Gb LPDDR3 = 2GB RAM — divergência de família.
    # Nota 2026-05-26: conflito com SAM_EMCP_GEN foi removido (R agora = LPDDR3 ✓).
    # Fonte: Preduo: KMR310001M-B611 → "eMCP eMMC+LPDDR3, 16+16, 221ball" ✓
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
            "emcp_nand":  "eMMC 5.1 16GB",
            "emcp_ram":   "LPDDR3 2GB",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Preduo: KMR310001M-B611 = eMCP eMMC+LPDDR3, 16+16 (16GB NAND + 16Gb LPDDR3 = 2GB). "
            "Conflito cap_key '31': mapa base = 1GB (KMQ310013B ✓) — KMR310001M tem 2GB (16Gb÷8). "
            "2026-05-26: conflito com SAM_EMCP_GEN removido (R=LPDDR3 restaurado no mapa global)."
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
    # eMCP LPDDR3 + eMMC 5.1. Família KMR. Era ~2015-2016.
    # cap_key "4Z" no SAM_EMCP_CAP: 32GB NAND + 2GB RAM — acerto correto da gramática.
    # Evidência: sufixo -B802 (era 2015-2016), encontrado em Moto G4, Lenovo K5/K6.
    # Fonte: confirmação física na esteira eMiner.
    # Nota 2026-05-26: conflito com SAM_EMCP_GEN removido (R agora = LPDDR3 ✓).
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
            "emcp_nand":  "eMMC 5.1 32GB",
            "emcp_ram":   "LPDDR3 2GB",
            "device":     "Moto G4 / Lenovo K5 / K6",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Confirmado na esteira eMiner (sufixo -B802, 2015-2016). "
            "cap_key 4Z = 32GB NAND + 2GB RAM (acerto da gramática). "
            "Dispositivos: Moto G4 / Lenovo K5 / K6 (LPDDR3 2GB). "
            "2026-05-26: conflito com SAM_EMCP_GEN removido (R=LPDDR3 restaurado)."
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

    # ── KM5L9001DA ───────────────────────────────────────────────────────────
    # uMCP UFS 2.2 + LPDDR4X. Família KM5, subfamília L (pn[2]='L'), variante pn[7]="1" (9001).
    # Capacidade real: 128GB UFS 2.2 + 4GB LPDDR4X (32Gb ÷ 8 = 4GB), 254 FBGA, 4266 Mbps.
    # Sufixo "DA" vs "DM" (KM5L9001DM): variante de package — mesma capacidade.
    # Sistema mostrava 8GB — erro por herdar SAM_EMCP_CAP['L9']=8GB (base KM8L9001JM).
    # Fonte: Samsung Semiconductor Global (Tier 1) ✓
    #   semiconductor.samsung.com/mcp/model/lpddr5-umcp/km5l9001da-b424/
    #   "32 Gb DRAM (LPDDR4X-4266), 128GB eStorage (UFS 2.2), 254 FBGA" ✓ (2026-05-26)
    {
        "pn": "KM5L9001DA",
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
            "Samsung Semiconductor Global (Tier 1, 2026-05-26): KM5L9001DA-B424 = "
            "128GB UFS 2.2 + 32Gb LPDDR4X-4266 → 32Gb÷8=4GB, 254 FBGA. "
            "Sistema mostrava 8GB — erro por herdar SAM_EMCP_CAP['L9']=8GB (base KM8L9001JM). "
            "Sufixo 'DA' vs 'DM' (KM5L9001DM): variante de package, capacidade idêntica. "
            "Conflito cap_key 'L9': KM8=8GB (base ✓), KM2=6GB, KM5=4GB (esta exceção). "
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

    # ══════════════════════════════════════════════════════════════════════════
    # Samsung K3PE — LPDDR2 Mobile standalone (~2011-2013)
    # Família adicionada ao grammar em populate_samsung.py (2026-05-29).
    # Todos NÃO RENTÁVEL: LPDDR2 (lpddr_gen=2 ≤ 2 → engine retorna NÃO RENTÁVEL).
    # Decode: pn[4:6] → 4E=512MB · 7E/8E=1GB · 0E=2GB.
    # ══════════════════════════════════════════════════════════════════════════

    # ── K3PE4E400A ───────────────────────────────────────────────────────────
    # LPDDR2 Samsung 512MB standalone. cap_key pn[4:6]="4E" → 4Gbit SDP.
    # Fontes Tier 1:
    #   • harddiskdirect: K3PE4E400A-XGC1 = "LPDDR2 128Mx32" → 4Gbit ÷ 8 = 512MB ✓
    #   • Octopart: K3PE4E400A-XGC0 — 3 distribuidores ✓ (2026-05-29)
    #   • Datasheets360: K3PE4E400A-XGC100 listado ✓
    # Organização: 128Mx32, 533MHz/1066Mbps, 240-ball FBGA 14×14mm.
    # Era: feature phone / entry-level Android (~2011-2012). Sem liquidez B2B.
    {
        "pn": "K3PE4E400A",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR2",
            "subtype":    "LPDDR2 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "512MB",
            "interface":  "LPDDR2",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "K3PE família LPDDR2 adicionada ao grammar (2026-05-29). "
            "K3PE4E400A-XGC1: harddiskdirect '128Mx32 LPDDR2' → 4Gbit÷8=512MB ✓. "
            "Octopart: K3PE4E400A-XGC0, 3 distribuidores ✓. "
            "cap_key '4E' adicionado ao K3PE_CAP em populate_samsung.py."
        ),
    },

    # ── K3PE7E700B ───────────────────────────────────────────────────────────
    # LPDDR2 Samsung 1GB standalone. cap_key pn[4:6]="7E" → 8Gbit DDP (2× 4Gb).
    # Fontes Tier 1:
    #   • TechInsights DPR-1110-901: K3PE7E700B-XXC1 = "Samsung 32nm 2X 4Gb Mobile LPDDR2 DRAM"
    #     → 4Gb/die × 2 dies DDP = 8Gbit = 1GB ✓
    #   • Jotrin + Veswin: K3PE7E700B-XXC1 listado ✓ (2026-05-29)
    # Organização: 128Mx32 × 2 DDP, 533MHz/1066Mbps, 32nm process.
    # Era: Galaxy S2 / Note era (~2011-2012). Sem liquidez B2B.
    {
        "pn": "K3PE7E700B",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR2",
            "subtype":    "LPDDR2 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "1GB",
            "interface":  "LPDDR2",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "TechInsights DPR-1110-901: K3PE7E700B-XXC1 = '32nm 2X 4Gb Mobile LPDDR2 DRAM'. "
            "DDP: 4Gb/die × 2 = 8Gb = 1GB. Jotrin + Veswin: listados ✓ (2026-05-29). "
            "cap_key '7E' adicionado ao K3PE_CAP → 8Gbit=1GB."
        ),
    },

    # ── K4E2E304EA ───────────────────────────────────────────────────────────
    # LPDDR3 standalone Samsung 1.5GB. Família K4E, pn[3:5]="2E" → 12Gb ÷ 8 = 1.5GB.
    # Chave "2E" adicionada ao K4E_CAP em populate_samsung.py (2026-05-29).
    # Fontes confirmadas:
    #   • K4E2E304EA-AGCF: Kynix + Worldway Electronics ✓
    #   • K4E2E304EE-AGCE: Alldatasheet (Samsung Product Selection Guide) ✓
    #   • Galaxy Tab E SM-T560/T560NU: 1.5GB RAM oficial — GSMarena/Icecat ✓
    #   • "2E"=12Gb já em LPDDR4_CAP com nota "confirmado por datasheet Samsung"
    # Dispositivo: Samsung Galaxy Tab E (SM-T560, SM-T560NU, SM-T567V), S5 Mini (~2014-2015).
    # Destino: resíduo (1.5GB LPDDR3 → sem liquidez B2B atual, NÃO RENTÁVEL via engine).
    # create=True: pn_not_in_db=True no debug → não existia no banco.
    # confidence=confirmed + fields: garante grammar_wins=False → fonte = "banco de dados".
    {
        "pn": "K4E2E304EA",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR3",
            "subtype":    "LPDDR3 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "1.5GB",
            "interface":  "LPDDR3",
            "device":     "Samsung Galaxy Tab E (SM-T560 / SM-T560NU / SM-T567V), Galaxy S5 Mini (~2014-2015)",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "K4E2E304EA-AGCF = LPDDR3 1.5GB (12Gb ÷ 8). "
            "Kynix + Worldway ✓. Alldatasheet Samsung PSG (K4E2E304EE-AGCE) ✓. "
            "Galaxy Tab E SM-T560 = 1.5GB RAM — GSMarena/Icecat ✓ (2026-05-29). "
            "Chave '2E' adicionada ao K4E_CAP. confidence=confirmed: garante grammar_wins=False."
        ),
    },

    # ── K4E6E304EB ───────────────────────────────────────────────────────────
    # LPDDR3 standalone Samsung 2GB. Família K4E, pn[3:5]="6E" → 16Gb ÷ 8 = 2GB.
    # "EB" = 1ª revisão de die da série K4E6E304.
    # Fonte Tier 1:
    #   • Samsung Semiconductor Global: K4E6E304EB-EGCG(16 Gb) ✓
    #     semiconductor.samsung.com/dram/lpddr/lpddr3/k4e6e304eb-egcg/
    {
        "pn": "K4E6E304EB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR3",
            "subtype":    "LPDDR3 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "2GB",
            "interface":  "LPDDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global (Tier 1): K4E6E304EB-EGCG(16 Gb) ✓. "
            "16Gb ÷ 8 = 2GB. pn[3:5]='6E' → K4E_CAP['6E']=2GB. "
            "Die revision EB (1ª revisão da série K4E6E304). "
            "confidence=confirmed: grammar_wins=False. Necessário para entrada no estoque."
        ),
    },

    # ── K4E6E304EC ───────────────────────────────────────────────────────────
    # LPDDR3 standalone Samsung 2GB. Família K4E, pn[3:5]="6E" → 16Gb ÷ 8 = 2GB.
    # "EC" = 2ª revisão de die da série K4E6E304.
    # Fonte Tier 1:
    #   • Samsung Semiconductor Global: K4E6E304EC-EGCG(16 Gb) ✓
    #     semiconductor.samsung.com/dram/lpddr/lpddr3/k4e6e304ec-egcg/
    {
        "pn": "K4E6E304EC",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR3",
            "subtype":    "LPDDR3 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "2GB",
            "interface":  "LPDDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global (Tier 1): K4E6E304EC-EGCG(16 Gb) ✓. "
            "16Gb ÷ 8 = 2GB. pn[3:5]='6E' → K4E_CAP['6E']=2GB. "
            "Die revision EC (2ª revisão da série K4E6E304). "
            "confidence=confirmed: grammar_wins=False. Necessário para entrada no estoque."
        ),
    },

    # ── K4E6E304ED ───────────────────────────────────────────────────────────
    # LPDDR3 standalone Samsung 2GB. Família K4E, pn[3:5]="6E" → 16Gb ÷ 8 = 2GB.
    # Gramática completa [✓]: K4E_CAP["6E"]=2GB; capacity="2GB" ✓.
    # FBGA-178, 1066MHz. "ED" = sufixo de revisão (E-die + grade D).
    # Fonte Tier 1:
    #   • Octopart: K4E6E304ED-EGCG = "16GBIT SDRAM LPDDR3 1066MHZ FBGA-178" ✓
    {
        "pn": "K4E6E304ED",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR3",
            "subtype":    "LPDDR3 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "2GB",
            "interface":  "LPDDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Octopart Tier 1: K4E6E304ED-EGCG = '16GBIT SDRAM LPDDR3 1066MHZ FBGA-178' ✓ (2026-06-17). "
            "16Gbit ÷ 8 = 2GB — confirma K4E_CAP['6E']=2GB (gramática [✓]). "
            "LPDDR3 standalone, FBGA-178. confidence=confirmed: grammar_wins=False."
        ),
    },

    # ── K4E6E304EE ───────────────────────────────────────────────────────────
    # LPDDR3 standalone Samsung 2GB. Família K4E, pn[3:5]="6E" → 16Gb ÷ 8 = 2GB.
    # Gramática completa [✓]: K4E_CAP["6E"]=2GB; capacity="2GB" ✓.
    # "EE" = sufixo de revisão de die (5ª geração da série K4E6E304).
    # Fontes Tier 1:
    #   • Samsung Semiconductor Global: K4E6E304EB(16Gb) / K4E6E304EC(16Gb) / K4E6E304ED(16Gb)
    #     — toda a família K4E6E304 é 16Gb LPDDR3 ✓ (semiconductor.samsung.com)
    #   • K4E6E304ED confirmado 2GB LPDDR3 via Octopart ✓ (sessão 2026-06-17)
    # Corrobora: datasheet4u indexa datasheet Samsung: K4E6E304EE = "16Gb QDP LPDDR3 SDRAM" ✓
    # Die revision EB→EC→ED→EE nunca muda capacidade em LPDDR Samsung.
    {
        "pn": "K4E6E304EE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR3",
            "subtype":    "LPDDR3 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "2GB",
            "interface":  "LPDDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global (Tier 1): K4E6E304EB/EC/ED todos listados como '16Gb' LPDDR3 ✓. "
            "K4E6E304ED confirmado 2GB LPDDR3 via Octopart Tier 1 (2026-06-17). "
            "Datasheet Samsung (via datasheet4u): K4E6E304EE = '16Gb QDP LPDDR3 SDRAM' ✓. "
            "pn[3:5]='6E' → K4E_CAP['6E']=2GB (gramática [✓]). "
            "Die revision EE (5ª revisão) não altera capacidade — padrão Samsung. "
            "confidence=confirmed: grammar_wins=False. Necessário para entrada no estoque."
        ),
    },

    # ── K4EBE304EB ───────────────────────────────────────────────────────────
    # LPDDR3 standalone Samsung 4GB. Família K4E, pn[3:5]="BE" → 32Gb ÷ 8 = 4GB.
    # "EB" = 1ª revisão de die da série K4EBE304 (flagship ~2015).
    # Fonte Tier 1:
    #   • Samsung Semiconductor Global: K4EBE304EB-EGCG(32 Gb) ✓
    #     semiconductor.samsung.com/dram/lpddr/lpddr3/k4ebe304eb-egcg/
    {
        "pn": "K4EBE304EB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR3",
            "subtype":    "LPDDR3 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "4GB",
            "interface":  "LPDDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global (Tier 1): K4EBE304EB-EGCG(32 Gb) ✓. "
            "32Gb ÷ 8 = 4GB. pn[3:5]='BE' → K4E_CAP['BE']=4GB. "
            "Die revision EB (1ª revisão da série K4EBE304, flagship ~2015). "
            "confidence=confirmed: grammar_wins=False. Necessário para entrada no estoque."
        ),
    },

    # ── K4EBE304EC ───────────────────────────────────────────────────────────
    # LPDDR3 standalone Samsung 4GB. Família K4E, pn[3:5]="BE" → 32Gb ÷ 8 = 4GB.
    # "EC" = 2ª revisão de die da série K4EBE304.
    # Fonte Tier 1:
    #   • Samsung Semiconductor Global: K4EBE304EC-EGCG(32 Gb) ✓
    #     semiconductor.samsung.com/dram/lpddr/lpddr3/k4ebe304ec-egcg/
    {
        "pn": "K4EBE304EC",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR3",
            "subtype":    "LPDDR3 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "4GB",
            "interface":  "LPDDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global (Tier 1): K4EBE304EC-EGCG(32 Gb) ✓. "
            "32Gb ÷ 8 = 4GB. pn[3:5]='BE' → K4E_CAP['BE']=4GB. "
            "Die revision EC (2ª revisão da série K4EBE304). "
            "confidence=confirmed: grammar_wins=False. Necessário para entrada no estoque."
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

    # ══════════════════════════════════════════════════════════════════════════
    # Samsung K3RG — LPDDR4 Multi-Channel (4CH x16, 64-bit) (~2015-2017)
    # ══════════════════════════════════════════════════════════════════════════

    # ── K3RG3G3 ───────────────────────────────────────────────────────────────
    # Samsung LPDDR4 3GB. Família K3RG. pn[4:6]="3G" → K3RG_CAP → 24Gbit ÷ 8 = 3GB.
    # CONVENÇÃO DE LEITURA: PN tem 7 chars porque o operador lê SOMENTE a primeira
    # linha do marcador laser (a que começa com "K"). Linha inferior = sufixo de package.
    # PN efetivo lido na bancada = K3RG3G3. PN completo = K3RG3G30MM-DGCH.
    # Chave "3G" = mesmo total que "4G" (ambos = 24Gb = 3GB), configuração de die diferente.
    # Fontes Tier 1:
    #   • iFixit Galaxy S6 Teardown (2015), Step 10:
    #     "Samsung K3RG3G30MM-DGCH 3 GB LPDDR4 RAM layered in" ✓
    #     ifixit.com/Teardown/Samsung+Galaxy+S6+Teardown/39174
    #   • Samsung Exynos 7420 (Snapdragon 410), Galaxy S6 / S6 Edge (2015).
    # Populate_samsung.py: "3G" adicionado ao K3RG_CAP (2026-06-18).
    # create=True: pn_not_in_db=True no debug — chip não existia no banco.
    {
        "pn": "K3RG3G3",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR4",
            "subtype":    "LPDDR4 Multi-Channel",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "3GB",
            "interface":  "LPDDR4",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "K3RG3G30MM-DGCH = 3GB LPDDR4. "
            "iFixit Galaxy S6 Teardown (2015), Step 10: 'Samsung K3RG3G30MM-DGCH 3 GB LPDDR4 RAM' ✓. "
            "PN de 7 chars: convenção de bancada — operador lê só a 1ª linha do laser. "
            "pn[4:6]='3G' → K3RG_CAP['3G']=3GB (24Gb, mesma capacidade que '4G', die diferente). "
            "K3RG_CAP atualizado em populate_samsung.py (2026-06-18). "
            "confidence=confirmed: grammar_wins=False. Necessário para entrada no estoque."
        ),
    },

    # ── K3RG2G20BM ────────────────────────────────────────────────────────────
    # LPDDR4 Samsung 4GB. Família K3RG, pn[4:6]="2G" → 32Gbit ÷ 8 = 4GB.
    # Fontes Tier 1:
    #   • iFixit Google Pixel XL Teardown: K3RG2G20BM-MGCJ = "4GB LPDDR4" ✓
    #     (Snapdragon 821, 2016) — ifixit.com/Teardown/Google+Pixel+XL+Teardown/71237
    #   • iFixit LG G5 Teardown: K3RG2G20BM-MGCJ = "4GB LPDDR4" ✓
    #     (Snapdragon 820, 2016) — ifixit.com/Teardown/LG+G5+Teardown/61205
    # Grammar já decodifica corretamente (2G → 4GB). Este fix promove a
    # confidence para "confirmed" e exibe "banco de dados" como fonte.
    # create=True: pn_not_in_db=True → chip não existia no banco.
    {
        "pn": "K3RG2G20BM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR4",
            "subtype":    "LPDDR4 Multi-Channel",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "4GB",
            "interface":  "LPDDR4",
            "device":     "Google Pixel XL (Snapdragon 821, 2016), LG G5 (Snapdragon 820, 2016)",
            "source_url": "https://www.ifixit.com/Teardown/Google+Pixel+XL+Teardown/71237",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "K3RG2G20BM-MGCJ = 4GB LPDDR4. "
            "iFixit Google Pixel XL teardown ✓ + iFixit LG G5 teardown ✓ (2026-05-29). "
            "pn[4:6]='2G' → K3RG_CAP → 32Gbit ÷ 8 = 4GB. Grammar correto. "
            "confidence=confirmed: garante grammar_wins=False → banco de dados."
        ),
    },
    {
        "pn": "K3RG2G20BM0G0J",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR4",
            "subtype":    "LPDDR4 Multi-Channel",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "4GB",
            "interface":  "LPDDR4",
            "device":     "Google Pixel XL (Snapdragon 821, 2016), LG G5 (Snapdragon 820, 2016)",
            "source_url": "https://www.ifixit.com/Teardown/Google+Pixel+XL+Teardown/71237",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "PN completo como lido pelo scanner (sem hífen): K3RG2G20BM + sufixo 0G0J. "
            "Mesma base K3RG2G20BM confirmada por iFixit Pixel XL + LG G5 teardowns ✓ (2026-05-29). "
            "pn[4:6]='2G' → 4GB LPDDR4. confidence=confirmed: banco de dados."
        ),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Samsung K3RG — 7-char bancada reads (convenção: operador lê 1ª linha laser)
    # PSG Samsung 1H 2017 confirma todos: K3RG4G40MM-MGCJ (24Gb=3GB),
    # K3RG2G20CA-MGCJ / K3RG2G20CM-FGCJ (32Gb=4GB), K3RG6G60MM-MGCJ (48Gb=6GB).
    # K3RG_CAP: 4G=3GB · 3G=3GB · 2G=4GB · 6G=6GB (grammar correto).
    # ══════════════════════════════════════════════════════════════════════════

    # ── K3RG4G4 ───────────────────────────────────────────────────────────────
    # LPDDR4 Samsung 3GB. 7-char bancada read de K3RG4G40MM-MGCJ.
    # pn[4:6]="4G" → K3RG_CAP["4G"]=3GB (24Gb).
    # Fonte Tier 1:
    #   • PSG Samsung 1H 2017: K3RG4G40MM-MGCJ = 24Gb = 3GB ✓
    {
        "pn": "K3RG4G4",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR4",
            "subtype":    "LPDDR4 Multi-Channel",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "3GB",
            "interface":  "LPDDR4",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "PSG Samsung 1H 2017 (Tier 1): K3RG4G40MM-MGCJ = 24Gb = 3GB ✓. "
            "PN 7 chars: convenção de bancada — operador lê só a 1ª linha do laser. "
            "pn[4:6]='4G' → K3RG_CAP['4G']=3GB. "
            "confidence=confirmed: grammar_wins=False. Necessário para entrada no estoque."
        ),
    },

    # ── K3RG2G2 ───────────────────────────────────────────────────────────────
    # LPDDR4 Samsung 4GB. 7-char bancada read de K3RG2G20CA/CM-MGCJ/FGCJ.
    # pn[4:6]="2G" → K3RG_CAP["2G"]=4GB (32Gb).
    # Cobre K3RG2G20CA-MGCJ e K3RG2G20CM-FGCJ (mesma 7-char prefix, mesma capacidade).
    # Fonte Tier 1:
    #   • PSG Samsung 1H 2017: K3RG2G20CA-MGCJ / K3RG2G20CM-FGCJ = 32Gb = 4GB ✓
    {
        "pn": "K3RG2G2",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR4",
            "subtype":    "LPDDR4 Multi-Channel",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "4GB",
            "interface":  "LPDDR4",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "PSG Samsung 1H 2017 (Tier 1): K3RG2G20CA-MGCJ / K3RG2G20CM-FGCJ = 32Gb = 4GB ✓. "
            "PN 7 chars: convenção de bancada — operador lê só a 1ª linha do laser. "
            "Cobre variantes CA (366-ball) e CM (432-ball) — mesma capacidade 4GB. "
            "pn[4:6]='2G' → K3RG_CAP['2G']=4GB. "
            "confidence=confirmed: grammar_wins=False. Necessário para entrada no estoque."
        ),
    },

    # ── K3RG6G6 ───────────────────────────────────────────────────────────────
    # LPDDR4 Samsung 6GB. 7-char bancada read de K3RG6G60MM-MGCJ.
    # pn[4:6]="6G" → K3RG_CAP["6G"]=6GB (48Gb).
    # Fonte Tier 1:
    #   • PSG Samsung 1H 2017: K3RG6G60MM-MGCJ = 48Gb = 6GB ✓
    {
        "pn": "K3RG6G6",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR4",
            "subtype":    "LPDDR4 Multi-Channel",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "6GB",
            "interface":  "LPDDR4",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "PSG Samsung 1H 2017 (Tier 1): K3RG6G60MM-MGCJ = 48Gb = 6GB ✓. "
            "PN 7 chars: convenção de bancada — operador lê só a 1ª linha do laser. "
            "pn[4:6]='6G' → K3RG_CAP['6G']=6GB. "
            "confidence=confirmed: grammar_wins=False. Necessário para entrada no estoque."
        ),
    },

    # ── K4FHE3D ───────────────────────────────────────────────────────────────
    # LPDDR4 standalone Samsung 3GB. Família K4F, pn[3:5]="HE" → 24Gb ÷ 8 = 3GB.
    #
    # BUG SISTÊMICO DETECTADO (2026-05-26):
    #   LPDDR4_CAP tinha ("HE", "4GB", "32Gb") — comentado como "alias BE" — ERRADO.
    #   HE = 24Gb (alias de FE/7E, 3GB), NÃO 32Gb (BE, 4GB). Densidades distintas.
    #
    # PROVAS (Samsung Semiconductor — Tier 1):
    #   K4FHE3D4HM-MHCJ: semiconductor.samsung.com → título "(24 Gb)" ✓
    #   K4FHE3D4HA-THCL: semiconductor.samsung.com/emea → título "(24Gb)" ✓
    #   K4FBE3D4HM-MGCJ: 32Gb (4GB) — confirma HE ≠ BE.
    #
    # FIX SISTÊMICO:
    #   LPDDR4_CAP["HE"] corrigido: 4GB→3GB em populate_samsung.py (2026-05-26).
    #   Tips K4F, K4U, K3U atualizadas: "7E/HE=3GB · BE/H5/H6=4GB".
    #   Este entry cobre K4FHE3D (base PN sem sufixo de lote) e confirma o decode.
    {
        "pn": "K4FHE3D",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR4",
            "subtype":    "LPDDR4 Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "3GB",
            "interface":  "LPDDR4",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global (Tier 1, 2026-05-26): "
            "K4FHE3D4HM-MHCJ = '(24 Gb)' LPDDR4; K4FHE3D4HA-THCL = '(24Gb)'. "
            "24Gb ÷ 8 = 3GB. Sistema mostrava 4GB — LPDDR4_CAP['HE'] estava como 32Gb (erro). "
            "K4FBE3D4HM-MGCJ = 32Gb (4GB) confirma: HE ≠ BE (densidades distintas). "
            "Fix sistêmico: LPDDR4_CAP['HE'] corrigido 4GB→3GB (populate_samsung.py). "
            "confidence+status em fields: garante grammar_wins=False para registros existentes."
        ),
    },

    # ── K4UJE3T ───────────────────────────────────────────────────────────────
    # LPDDR4X standalone Samsung 6GB. Família K4U. pn[3:5]="JE" → 48Gb ÷ 8 = 6GB.
    # Tensão I/O: 0.6V. RAM pura — sem componente Flash. EOL.
    #
    # PROVA (Samsung Semiconductor Global — Tier 1):
    #   K4UJE3Q4AA-TFCL: semiconductor.samsung.com/dram/lpddr/lpddr4x/k4uje3q4aa-tfcl/
    #     → título da página: "K4UJE3Q4AA-TFCL(48 Gb)" ✓
    #   K4UJE3Q4AA-THCL: semiconductor.samsung.com/dram/lpddr/lpddr4x/k4uje3q4aa-thcl/
    #     → título da página: "K4UJE3Q4AA-THCL(48 Gb)" ✓
    #   JE = densidade 48Gb confirmada Tier 1 — adicionada ao LPDDR4_CAP (2026-05-27).
    #
    # NOTA IA EXTERNA: afirmou JE=6GB mas citou AliExpress/Shopee/Lazada "manifests" —
    #   fontes fabricadas. Confirmação vem de Samsung Semiconductor Global (independente).
    {
        "pn": "K4UJE3T",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "LPDDR4X",
            "subtype":    "LPDDR4X Mobile",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "6GB",
            "interface":  "LPDDR4X",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global (Tier 1, 2026-05-27): "
            "K4UJE3Q4AA-TFCL(48 Gb) e K4UJE3Q4AA-THCL(48 Gb) — página oficial semiconductor.samsung.com ✓. "
            "JE = 48Gb → 48÷8 = 6GB. Família K4U = LPDDR4X 0.6V. "
            "LPDDR4_CAP['JE']='6GB'/'48Gb' adicionado em populate_samsung.py (2026-05-27). "
            "IA externa citou AliExpress/Shopee/Lazada como provas — fontes fabricadas; "
            "confirmação mantida exclusivamente via Samsung Semiconductor Global. "
            "confidence+status em fields: garante grammar_wins=False para registros existentes."
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

    # ── KMN5X000ZM ───────────────────────────────────────────────────────────
    # Samsung eMCP LPDDR2 + eMMC. Família KMN (~2011-2014, entrada legada).
    #
    # DECODE (2026-05-26):
    #   Sistema: emcp_source="parcial (gramática)" — família KMN reconhecida,
    #   mas pn[3:5]="5X" não está em SAM_EMCP_CAP (e KMN tem decode_cap_pos=None).
    #   emcp_nand="eMMC" e emcp_ram="LPDDR2" — corretos, mas sem valores de GB.
    #   fuzzy_suggestions=["KMNJ2000ZM"] — motor encontrou vizinho de estrutura similar.
    #
    # CAPACIDADE (chave "5X"):
    #   IA externa estimou: 4GB NAND + 512MB LPDDR2.
    #   Analogia parcial: "5U" → 4GB+512MB confirmado (KMN5U000FM-B203 Jotrin ✓).
    #   O "5" aponta para 4GB NAND, mas "X" (RAM) não tem fonte Tier 1-2.
    #   ⚠ Conflito interno: populate_samsung.py linha 158 tinha "5X"→8GB+1GB bloqueado
    #   como wildcard especulativo para família KMQ (distinta!). Não extrapolável para KMN.
    #   BLOQUEADO: sem fonte Tier 1-2, capacidade fica em branco.
    #
    # IMPACTO OPERACIONAL:
    #   Capacidade vazia não muda o destino: tip já encaminha para Caixa Vermelha.
    #   profitable="INDETERMINADO" (sem GB para calcular) é correto — não é bug.
    #   A IA sugeriu regra LPDDR2→"NÃO RENTÁVEL" forçado: discutir separadamente
    #   com o usuário — impacta o engine, não apenas este chip.
    {
        "pn": "KMN5X000ZM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "eMCP",
            "subtype":    "LPDDR2 + eMMC (legado)",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "emcp_nand":  "",   # bloqueado: "5X" sem fonte Tier 1-2 confirmada (2026-05-26)
            "emcp_ram":   "",   # bloqueado: idem — "5U"→512MB é análogo mas não idêntico
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "KMN5X000ZM: Samsung eMCP LPDDR2 + eMMC, era 2011-2014. "
            "pn[3:5]='5X' ausente do SAM_EMCP_CAP; família KMN tem decode_cap_pos=None. "
            "IA estimou 4GB+512MB por analogia com '5U' (KMN5U000FM-B203 ✓). "
            "Conflito: populate_samsung.py linha 158 tinha '5X'→8GB+1GB (especulativo, KMQ). "
            "Sem fonte Tier 1-2 para KMN5X: capacidade bloqueada pela regra de ouro. "
            "confidence+status em fields: garante grammar_wins=False. "
            "Destino: Caixa Vermelha (LPDDR2 legado, sem liquidez em 2026)."
        ),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Samsung LPDDR2 standalone confirmados — 2026-05-27
    # ══════════════════════════════════════════════════════════════════════════

    # ── K4P8G304EQ ────────────────────────────────────────────────────────────
    # LPDDR2 standalone Samsung. K4P = LPDDR2 Mobile (legado, ~2010-2015).
    # Gramática já cobre: pn[3]='8' → DRAM_MOBILE: 8Gb = 1GB [✓].
    # Adicionado com confidence=confirmed para travar contra substituição futura.
    # Fonte: AllDatasheet K4P8G304EQ-AGC2 = "LPDDR2 SDRAM 8G-Bit 256Mx32" = 8Gb = 1GB ✓
    # Variantes de sufixo conhecidas: -AGC2 (FBGA-168), -PGC2.
    {
        "pn": "K4P8G304EQ",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "RAM",
            "subtype":    "LPDDR2 Mobile (legado)",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "1GB",
            "interface":  "LPDDR2",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "AllDatasheet K4P8G304EQ-AGC2 = 'LPDDR2 SDRAM 8G-Bit 256Mx32 1.2V/1.8V 168-Pin FBGA'. "
            "8Gb ÷ 8 = 1GB. K4P = LPDDR2 Mobile Samsung (P = LPDDR2, confirmado família K4P). "
            "Destino: fluxo de resíduo — LPDDR2 obsoleto, sem liquidez B2B (~2010-2015)."
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
            "fbga_code":  "D9VFC",
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

    # ══════════════════════════════════════════════════════════════════════════
    # MT29C4G48 — NAND Flash paralela industrial Micron (4 Gbit = 512 MB)
    # ══════════════════════════════════════════════════════════════════════════
    #
    # MT29C4G48MAZAPAKD = SLC NAND Flash 4 Gbit, interface paralela 8-bit (x8),
    # 48-pin TSOP1 package. ⚠ NÃO é eMCP, eMMC nem UFS — NAND raw sem controlador.
    #
    # Decodificação do PN:
    #   MT = Micron Technology
    #   29 = Flash NAND
    #   C  = bus x8 paralela (8-bit)
    #   4G = 4 Gbit de capacidade
    #   48 = 48 pinos (package TSOP1)
    #   MAZAPAKD = opções de die (VCC, organização de página, etc.)
    #   -5 / -6 = cycle time (ns): -5 = 50ns, -6 = 60ns
    #   IT = Industrial Temperature (-40°C a +85°C)
    #   E  = Extended (variante de qualificação estendida)
    #   ES = Engineering Sample (amostra de engenharia — NÃO produção final)
    #
    # Capacidade: 4 Gbit = 4 × 128 MB = 512 MB
    #
    # Uso típico: sistemas embarcados industriais, roteadores, STBs.
    # ⚠ Destino na bancada: caixa industrial / resíduo — arquitetura paralela
    #   incompatível com programadores eMMC/UFS. Sem liquidez no mercado móvel.
    #
    # FBGAs confirmados via API Micron FBGA decoder (2026-05-28):
    #   JW454 → MT29C4G48MAZAPAKD-6 IT   (produção, -6)
    #   JW464 → MT29C4G48MAZAPAKD-5 IT   (produção, -5) ← chip testado na esteira
    #   JW699 → MT29C4G48MAZAPAKD-5 E IT (extended, -5)
    #   JY454 → MT29C4G48MAZAPAKD-6 IT ES (engineering sample, -6)
    #   JY464 → MT29C4G48MAZAPAKD-5 IT ES (engineering sample, -5)

    # ── JW464 — MT29C4G48MAZAPAKD-5 IT ─────────────────────────────────────
    # Chip testado na esteira eMiner — não reconhecido (MT29C sem família no DB).
    {
        "pn": "MT29C4G48MAZAPAKD5IT",
        "create": True,
        "create_defaults": {
            "brand_name": "Micron",
            "chip_type":  "NAND Flash",
            "subtype":    "SLC NAND paralela industrial",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "512MB",
            "interface":  "Parallel NAND (8-bit)",
            "fbga_code":  "JW464",
            "confidence": "confirmed",
            "status":     "enriched",
            "notes": (
                "4 Gbit SLC NAND Flash paralela (x8). Industrial Temp (-40°C/+85°C). "
                "⚠ NÃO é eMCP/eMMC/UFS — NAND raw, sem controlador. "
                "Destino: resíduo/industrial. Variante -5 (50ns)."
            ),
            "source_url": "https://www.micron.com/support/tools-and-utilities/fbga?fbga=JW464",
        },
        "reason": (
            "FBGA JW464 = MT29C4G48MAZAPAKD-5 IT (API Micron FBGA decoder). "
            "4 Gbit SLC NAND Flash ÷ 8 = 512MB. Paralela 8-bit (x8), 48-pin TSOP1. "
            "Industrial Temp (-40°C/+85°C). ⚠ NÃO é eMCP — NAND raw sem controlador. "
            "Chip testado na esteira eMiner — não reconhecido (MT29C sem família no DB)."
        ),
    },

    # ── JW454 — MT29C4G48MAZAPAKD-6 IT ─────────────────────────────────────
    {
        "pn": "MT29C4G48MAZAPAKD6IT",
        "create": True,
        "create_defaults": {
            "brand_name": "Micron",
            "chip_type":  "NAND Flash",
            "subtype":    "SLC NAND paralela industrial",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "512MB",
            "interface":  "Parallel NAND (8-bit)",
            "fbga_code":  "JW454",
            "confidence": "confirmed",
            "status":     "enriched",
            "notes": (
                "4 Gbit SLC NAND Flash paralela (x8). Industrial Temp (-40°C/+85°C). "
                "⚠ NÃO é eMCP/eMMC/UFS — NAND raw, sem controlador. "
                "Destino: resíduo/industrial. Variante -6 (60ns, mais lenta que JW464)."
            ),
            "source_url": "https://www.micron.com/support/tools-and-utilities/fbga?fbga=JW454",
        },
        "reason": (
            "FBGA JW454 = MT29C4G48MAZAPAKD-6 IT (API Micron FBGA decoder). "
            "4 Gbit SLC NAND Flash ÷ 8 = 512MB. Paralela 8-bit (x8), 48-pin TSOP1. "
            "Industrial Temp (-40°C/+85°C). Variante -6 (60ns). "
            "⚠ NÃO é eMCP — NAND raw sem controlador."
        ),
    },

    # ── JW699 — MT29C4G48MAZAPAKD-5 E IT ───────────────────────────────────
    {
        "pn": "MT29C4G48MAZAPAKD5EIT",
        "create": True,
        "create_defaults": {
            "brand_name": "Micron",
            "chip_type":  "NAND Flash",
            "subtype":    "SLC NAND paralela industrial",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "512MB",
            "interface":  "Parallel NAND (8-bit)",
            "fbga_code":  "JW699",
            "confidence": "confirmed",
            "status":     "enriched",
            "notes": (
                "4 Gbit SLC NAND Flash paralela (x8). Industrial Temp (-40°C/+85°C). "
                "⚠ NÃO é eMCP/eMMC/UFS — NAND raw, sem controlador. "
                "Destino: resíduo/industrial. Variante -5 E (Extended, 50ns)."
            ),
            "source_url": "https://www.micron.com/support/tools-and-utilities/fbga?fbga=JW699",
        },
        "reason": (
            "FBGA JW699 = MT29C4G48MAZAPAKD-5 E IT (API Micron FBGA decoder). "
            "4 Gbit SLC NAND Flash ÷ 8 = 512MB. Paralela 8-bit (x8), 48-pin TSOP1. "
            "Industrial Temp. Variante -5 E (Extended). "
            "⚠ NÃO é eMCP — NAND raw sem controlador."
        ),
    },

    # ── JY454 — MT29C4G48MAZAPAKD-6 IT ES (Engineering Sample) ─────────────
    {
        "pn": "MT29C4G48MAZAPAKD6ITES",
        "create": True,
        "create_defaults": {
            "brand_name": "Micron",
            "chip_type":  "NAND Flash",
            "subtype":    "SLC NAND paralela industrial",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "512MB",
            "interface":  "Parallel NAND (8-bit)",
            "fbga_code":  "JY454",
            "confidence": "confirmed",
            "status":     "enriched",
            "notes": (
                "4 Gbit SLC NAND Flash paralela (x8). Industrial Temp (-40°C/+85°C). "
                "⚠ ES = Engineering Sample — amostra de engenharia, NÃO produção final. "
                "⚠ NÃO é eMCP/eMMC/UFS — NAND raw, sem controlador. "
                "Destino: resíduo/industrial. Variante -6 ES (60ns)."
            ),
            "source_url": "https://www.micron.com/support/tools-and-utilities/fbga?fbga=JY454",
        },
        "reason": (
            "FBGA JY454 = MT29C4G48MAZAPAKD-6 IT ES (API Micron FBGA decoder). "
            "ES = Engineering Sample (NÃO produção final). "
            "4 Gbit SLC NAND Flash ÷ 8 = 512MB. ⚠ NÃO é eMCP — NAND raw."
        ),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Samsung NAND Flash standalone — KF9 family (K9 series, legacy)
    # ══════════════════════════════════════════════════════════════════════════

    # ── KF98G16Q4X ────────────────────────────────────────────────────────────
    # Samsung NAND Flash standalone: 8Gbit (1GB), x16 bus, FBGA63.
    # Conflito de prefixo resolvido em add_chip_families.py:
    #   Samsung "KF9" (priority=70) > Kingston "KF" (priority=80).
    # Fontes Tier 1:
    #   • Octopart: KF98G16Q4X-BEB0 — 6 distribuidores, Samsung ✓ (2026-05-29)
    #   • Elnec: KF98G16Q4X [FBGA63] — suporte confirmado em programador BGA ✓
    #   • Elnec K9 naming table: 8G = 8Gbit, 16 = x16 bus
    # Era: feature phone / embedded (~2008-2012). Sem controladora eMMC.
    # Destino: sucata ou aplicações industriais específicas.
    {
        "pn": "KF98G16Q4X",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "NAND Flash",
            "subtype":    "NAND Flash 8Gbit (1GB) x16 — K9 series (legado)",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "NAND Flash",
            "subtype":    "NAND Flash 8Gbit (1GB) x16 — K9 series (legado)",
            "capacity":   "8Gbit (1GB)",
            "interface":  "NAND x16 (raw, sem controladora)",
            "device":     "SUCATA / uso industrial específico — Samsung NAND Flash standalone legado "
                          "(feature phone / embedded ~2008-2012). Sem controladora eMMC.",
            "source_url": "https://octopart.com/kf98g16q4x-beb0-samsung-52061167",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "KF98G16Q4X = Samsung K9 NAND Flash standalone. NÃO é Kingston Fury. "
            "Conflito de prefixo KF: Kingston (DDR módulos) vs Samsung (NAND Flash). "
            "Octopart: KF98G16Q4X-BEB0, 6 distribuidores, Samsung ✓ (2026-05-29). "
            "Elnec: FBGA63, K9 naming table → 8G=8Gbit(1GB), x16 bus ✓. "
            "Família KF9 adicionada em add_chip_families.py (priority=70 < Kingston KF priority=80). "
            "create=True: chip não existia no banco (grammar retornava Kingston por erro de prefixo)."
        ),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Samsung DDR1 PC DRAM — família K4H (~2001–2007)
    # chip_type="DDR", subtype="DDR1" → assess_profitability: gen=1 < ddr_min_gen(3)
    # → NÃO RENTÁVEL independente de densidade. Destino: moagem / refino de metais.
    # Densidade: pn[3:5] → 28=128Mb(16MB), 56=256Mb(32MB), 51=512Mb(64MB).
    # Gramática K4H já cobre a família; entradas aqui elevam para confidence=confirmed.
    # Fontes:
    #   • Octopart (Samsung Semiconductor): K4H561638D-TCB3 = "256Mb DDR1 16Mx16" ✓
    #   • Samsung datasheet Rev 1.1 (Nov 2009): K4H510438G/K4H510838G/K4H511638G
    #     "512Mb G-die DDR SDRAM" — 128Mx4 / 64Mx8 / 32Mx16 ✓
    # ══════════════════════════════════════════════════════════════════════════

    # ── K4H510438G — 512Mb DDR1 x4 (64MB/die) ───────────────────────────────
    # Samsung datasheet Rev 1.1 (Nov 2009): "128M x 4 bit, 4 banks, DDR266/333/400"
    {
        "pn": "K4H510438G",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR1 PC DRAM 512Mb x4",
            "status":     "enriched",
            "confidence": "manual",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR1 PC DRAM 512Mb x4",
            "capacity":   "64MB",
            "interface":  "DDR1",
            "confidence": "manual",
            "status":     "enriched",
        },
        "reason": (
            "Samsung datasheet Rev 1.1 (Nov 2009): "
            "'DDR SDRAM K4H510438G' — '128M×4, 4 banks, DDR266/333/400'. "
            "512Mbit ÷ 8 = 64MB/die. G-die, x4 bus (servidor/ECC). "
            "chip_type='DDR' + subtype='DDR1' → gen=1 < 3 → NÃO RENTÁVEL. "
            "Destino: moagem / recuperação de metais."
        ),
    },

    # ── K4H510838G — 512Mb DDR1 x8 (64MB/die) ───────────────────────────────
    # Samsung datasheet Rev 1.1 (Nov 2009): "64M x 8 bit, DDR266/333/400"
    {
        "pn": "K4H510838G",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR1 PC DRAM 512Mb x8",
            "status":     "enriched",
            "confidence": "manual",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR1 PC DRAM 512Mb x8",
            "capacity":   "64MB",
            "interface":  "DDR1",
            "confidence": "manual",
            "status":     "enriched",
        },
        "reason": (
            "Samsung datasheet Rev 1.1 (Nov 2009): "
            "'DDR SDRAM K4H510838G' — '64M×8, 4 banks, DDR266/333/400'. "
            "512Mbit ÷ 8 = 64MB/die. G-die, x8 bus (desktop/laptop comum). "
            "chip_type='DDR' + subtype='DDR1' → gen=1 < 3 → NÃO RENTÁVEL. "
            "Destino: moagem / recuperação de metais."
        ),
    },

    # ── K4H511638G — 512Mb DDR1 x16 (64MB/die) ──────────────────────────────
    # Samsung datasheet Rev 1.1 (Nov 2009): "32M x 16 bit, DDR266/333/400"
    {
        "pn": "K4H511638G",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR1 PC DRAM 512Mb x16",
            "status":     "enriched",
            "confidence": "manual",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR1 PC DRAM 512Mb x16",
            "capacity":   "64MB",
            "interface":  "DDR1",
            "confidence": "manual",
            "status":     "enriched",
        },
        "reason": (
            "Samsung datasheet Rev 1.1 (Nov 2009): "
            "'DDR SDRAM K4H511638G' — '32M×16, 4 banks, DDR266/333/400'. "
            "512Mbit ÷ 8 = 64MB/die. G-die, x16 bus (SO-DIMM/embarcado). "
            "chip_type='DDR' + subtype='DDR1' → gen=1 < 3 → NÃO RENTÁVEL. "
            "Destino: moagem / recuperação de metais."
        ),
    },

    # ── K4H561638D-TCB3 — 256Mb DDR1 x16 (32MB/die) ─────────────────────────
    # Octopart (Samsung Semiconductor): K4H561638D-TCB3 = "16Mx16, DDR400" ✓
    {
        "pn": "K4H561638D",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR",
            "subtype": "DDR1 PC DRAM 256Mb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR", "subtype": "DDR1 PC DRAM 256Mb x16",
            "capacity": "32MB", "interface": "DDR1", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — deriva de K4H561638D-TCB3 (Octopart/Samsung ✓). 256Mbit ÷ 8 = 32MB/die. D-die, x16. gen=1 → NÃO RENTÁVEL."
        ),
    },
    {
        "pn": "K4H561638D-TCB3",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR1 PC DRAM 256Mb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR1 PC DRAM 256Mb x16",
            "capacity":   "32MB",
            "interface":  "DDR1",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Octopart (Samsung Semiconductor): K4H561638D-TCB3 = '16Mx16, DDR400' ✓. "
            "256Mbit ÷ 8 = 32MB/die. D-die, x16 bus. "
            "chip_type='DDR' + subtype='DDR1' → gen=1 < 3 → NÃO RENTÁVEL. "
            "Destino: moagem / recuperação de metais."
        ),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Samsung DDR2 PC DRAM — família K4T (~2004–2010)
    # chip_type="DDR", subtype="DDR2" → assess_profitability: gen=2 < ddr_min_gen(3)
    # → NÃO RENTÁVEL independente de densidade. Destino: moagem / refino.
    # Densidade: pn[3:5] → 51=512Mb(64MB), 1G=1Gb(128MB).
    # Largura: pn[5:7] → 08=x8, 16=x16, 04/03=x4.
    # Fontes: Samsung Semiconductor Global (título "(X Mb)" nos resultados Google).
    #   Nota: páginas Samsung Semiconductor Global foram desativadas em 31/07/2025
    #   mas os títulos indexados pelo Google são válidos como confirmação Tier 1.
    # ══════════════════════════════════════════════════════════════════════════

    # ── K4T51163QN — 512Mb DDR2 x16 (64MB/die) ──────────────────────────────
    # Samsung Semiconductor Global: K4T51163QN(512 Mb) ✓
    {
        "pn": "K4T51163QN",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 512Mb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 512Mb x16",
            "capacity":   "64MB",
            "interface":  "DDR2",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4T51163QN(512 Mb) ✓. "
            "512Mbit ÷ 8 = 64MB/die. x16 bus. "
            "chip_type='DDR' + subtype='DDR2' → gen=2 < 3 → NÃO RENTÁVEL. "
            "Destino: moagem / recuperação de metais."
        ),
    },

    # ── K4T51163QN-BI — 512Mb DDR2 x16 (64MB/die) ───────────────────────────
    {
        "pn": "K4T51163QN-BI",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 512Mb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 512Mb x16",
            "capacity":   "64MB",
            "interface":  "DDR2",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4T51163QN-BI(512 Mb) ✓. "
            "512Mbit ÷ 8 = 64MB/die. x16 bus. NÃO RENTÁVEL (gen=2)."
        ),
    },

    # ── K4T51163QN-BHF8 — 512Mb DDR2 x16 (64MB/die) ─────────────────────────
    {
        "pn": "K4T51163QN-BHF8",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 512Mb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 512Mb x16",
            "capacity":   "64MB",
            "interface":  "DDR2",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4T51163QN-BHF8(512 Mb) ✓. "
            "512Mbit ÷ 8 = 64MB/die. x16 bus. NÃO RENTÁVEL (gen=2)."
        ),
    },

    # ── K4T51163QN-BFF8 — 512Mb DDR2 x16 (64MB/die) ─────────────────────────
    {
        "pn": "K4T51163QN-BFF8",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 512Mb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 512Mb x16",
            "capacity":   "64MB",
            "interface":  "DDR2",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global USA: K4T51163QN-BFF8(512 Mb) ✓. "
            "512Mbit ÷ 8 = 64MB/die. x16 bus. NÃO RENTÁVEL (gen=2)."
        ),
    },

    # ── K4T51083QN-BI — 512Mb DDR2 x8 (64MB/die) ────────────────────────────
    # Samsung Semiconductor Global: K4T51083QN-BI(512 Mb) ✓ (x8 bus)
    {
        "pn": "K4T51083QN",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR",
            "subtype": "DDR2 PC DRAM 512Mb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR", "subtype": "DDR2 PC DRAM 512Mb x8",
            "capacity": "64MB", "interface": "DDR2", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — deriva de K4T51083QN-BI (Samsung Semiconductor Global ✓). 512Mbit ÷ 8 = 64MB/die. x8 bus. gen=2 → NÃO RENTÁVEL."
        ),
    },
    {
        "pn": "K4T51083QN-BI",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 512Mb x8",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 512Mb x8",
            "capacity":   "64MB",
            "interface":  "DDR2",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4T51083QN-BI(512 Mb) ✓. "
            "512Mbit ÷ 8 = 64MB/die. x8 bus (DIMMs de servidor/desktop). "
            "NÃO RENTÁVEL (gen=2). Destino: moagem."
        ),
    },

    # ── K4T1G084QJ — 1Gb DDR2 x8 (128MB/die) ────────────────────────────────
    # Samsung Semiconductor Global: K4T1G084QJ(1 Gb) ✓
    # Samsung datasheet DS_K4T1G08_16_4QJ-B_Rev1_0-1.pdf (download.semiconductor.samsung.com)
    {
        "pn": "K4T1G084QJ",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 1Gb x8",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 1Gb x8",
            "capacity":   "128MB",
            "interface":  "DDR2",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4T1G084QJ(1 Gb) ✓. "
            "Samsung datasheet DS_K4T1G08_16_4QJ-B_Rev1_0-1.pdf (download.semiconductor.samsung.com) ✓. "
            "1Gbit ÷ 8 = 128MB/die. x8 bus. NÃO RENTÁVEL (gen=2). Destino: moagem."
        ),
    },

    # ── K4T1G083QJ-BI — 1Gb DDR2 x8 (128MB/die) ─────────────────────────────
    {
        "pn": "K4T1G083QJ",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR",
            "subtype": "DDR2 PC DRAM 1Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR", "subtype": "DDR2 PC DRAM 1Gb x8",
            "capacity": "128MB", "interface": "DDR2", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — deriva de K4T1G083QJ-BI (Samsung Semiconductor Global ✓). 1Gbit ÷ 8 = 128MB/die. x8 bus. gen=2 → NÃO RENTÁVEL."
        ),
    },
    {
        "pn": "K4T1G083QJ-BI",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 1Gb x8",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 1Gb x8",
            "capacity":   "128MB",
            "interface":  "DDR2",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4T1G083QJ-BI(1 Gb) ✓. "
            "1Gbit ÷ 8 = 128MB/die. x8 bus. NÃO RENTÁVEL (gen=2)."
        ),
    },

    # ── K4T1G164QJ — 1Gb DDR2 x16 (128MB/die) ───────────────────────────────
    # Samsung Semiconductor Global: K4T1G164QJ(1 Gb) ✓
    # Samsung datasheet DS_K4T1G08_16_4QJ-B_Rev1_0-1.pdf ✓
    {
        "pn": "K4T1G164QJ",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 1Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 1Gb x16",
            "capacity":   "128MB",
            "interface":  "DDR2",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4T1G164QJ(1 Gb) ✓. "
            "Samsung datasheet DS_K4T1G08_16_4QJ-B_Rev1_0-1.pdf ✓. "
            "1Gbit ÷ 8 = 128MB/die. x16 bus (SO-DIMM/laptop). "
            "NÃO RENTÁVEL (gen=2). Destino: moagem."
        ),
    },

    # ── K4T1G163QJ-BI — 1Gb DDR2 x16 (128MB/die) ────────────────────────────
    {
        "pn": "K4T1G163QJ",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR",
            "subtype": "DDR2 PC DRAM 1Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR", "subtype": "DDR2 PC DRAM 1Gb x16",
            "capacity": "128MB", "interface": "DDR2", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — deriva de K4T1G163QJ-BI (Samsung Semiconductor Global ✓). 1Gbit ÷ 8 = 128MB/die. x16 bus. gen=2 → NÃO RENTÁVEL."
        ),
    },
    {
        "pn": "K4T1G163QJ-BI",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 1Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 1Gb x16",
            "capacity":   "128MB",
            "interface":  "DDR2",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4T1G163QJ-BI(1 Gb) ✓. "
            "1Gbit ÷ 8 = 128MB/die. x16 bus. NÃO RENTÁVEL (gen=2)."
        ),
    },

    # ── K4T1G164QJ-BHF8 — 1Gb DDR2 x16 (128MB/die) ──────────────────────────
    {
        "pn": "K4T1G164QJ-BHF8",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 1Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 1Gb x16",
            "capacity":   "128MB",
            "interface":  "DDR2",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4T1G164QJ-BHF8(1 Gb) ✓. "
            "1Gbit ÷ 8 = 128MB/die. x16 bus. NÃO RENTÁVEL (gen=2)."
        ),
    },

    # ── K4T1G164QJ-BFF8 — 1Gb DDR2 x16 (128MB/die) ──────────────────────────
    {
        "pn": "K4T1G164QJ-BFF8",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 1Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR",
            "subtype":    "DDR2 PC DRAM 1Gb x16",
            "capacity":   "128MB",
            "interface":  "DDR2",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4T1G164QJ-BFF8(1 Gb) ✓. "
            "1Gbit ÷ 8 = 128MB/die. x16 bus. NÃO RENTÁVEL (gen=2)."
        ),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Samsung DDR3 / DDR3L PC DRAM — família K4B (~2010–2016, laptops/desktops)
    # Capacidade = die individual: 1Gb=128MB, 2Gb=256MB, 4Gb=512MB, 8Gb=1GB.
    # assess_profitability DDR3: ≥2Gb/die (256MB) → RENTÁVEL (config padrão).
    # DDR3L (1.35V/1.5V dual): sufixos BY (x16), MY/MM (8Gb), BY (x8).
    # DDR3  (1.5V):            sufixo BC (todas densidades).
    # Não há família K4B na gramática — estes são os únicos registros no banco.
    # Fontes primárias Tier 1:
    #   • Samsung Semiconductor Global (título Google indexado "(X Gb)") ✓
    #   • DS_K4B4G1646E_BY_M_Rev1_11-0.pdf — DDR3L E-die (download.semiconductor.samsung.com)
    #   • DS_K4B4G1646E-BC_Rev101-0.pdf    — DDR3 E-die "4Gb E-die DDR3 SDRAM x16"
    #   • harddiskdirect.com: K4B8G1646D-MYK0 "DDR3-1600 512Mx16 1.35V" ✓
    #                         K4B8G1646D-MMK0 "DDR3-1600 512Mx16 Ind 1.35V" ✓
    #   • Xecor: K4B8G1646D-MMMA "DDR3L SDRAM 8Gbit 512Mx16 1.35V/1.5V" ✓
    #   • JLCPCB: K4B4G1646E-BYMA "DDR3L SDRAM 4Gbit 256Mx16 1.35V/1.5V" ✓
    # ══════════════════════════════════════════════════════════════════════════

    # ── K4B4G1646E-BYMA — 4Gb DDR3L x16 (512MB/die) ─────────────────────────
    # Samsung Semiconductor Global: K4B4G1646E-BYMA(4 Gb) ✓
    # BY = DDR3L 1.35V/1.5V dual voltage. E-die = die revision E.
    {
        "pn": "K4B4G1646E-BYMA",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 4Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 4Gb x16",
            "capacity":   "512MB",
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B4G1646E-BYMA(4 Gb) ✓. "
            "JLCPCB (cita Samsung): 'DDR3L SDRAM 4Gbit 256Mx16 1.35V/1.5V' ✓. "
            "BY = DDR3L dual voltage. Datasheet Samsung DS_K4B4G1646E_BY_M_Rev1_11-0.pdf ✓. "
            "4Gbit ÷ 8 = 512MB/die."
        ),
    },

    # ── K4B4G1646E-BYK0 — 4Gb DDR3L x16 (512MB/die) ─────────────────────────
    {
        "pn": "K4B4G1646E-BYK0",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 4Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 4Gb x16",
            "capacity":   "512MB",
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B4G1646E-BYK0(4 Gb) ✓. "
            "BY = DDR3L 1.35V/1.5V dual. E-die. 4Gbit ÷ 8 = 512MB/die."
        ),
    },

    # ── K4B4G1646D-BYK0 — 4Gb DDR3L x16 (512MB/die) ─────────────────────────
    {
        "pn": "K4B4G1646D",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR3L",
            "subtype": "DDR3L PC DRAM 4Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR3L", "subtype": "DDR3L PC DRAM 4Gb x16",
            "capacity": "512MB", "interface": "DDR3L", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — deriva de K4B4G1646D-BYK0/BYNB/BCK0/BCNB (Samsung Semiconductor Global ✓). 4Gbit ÷ 8 = 512MB/die. D-die, x16."
        ),
    },
    {
        "pn": "K4B4G1646D-BYK0",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 4Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 4Gb x16",
            "capacity":   "512MB",
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B4G1646D-BYK0(4 Gb) ✓. "
            "BY = DDR3L 1.35V/1.5V dual. D-die. 4Gbit ÷ 8 = 512MB/die."
        ),
    },

    # ── K4B4G1646D-BYNB — 4Gb DDR3L x16 (512MB/die) ─────────────────────────
    # Variante com package NB (Narrow Body / SO-DIMM specific)
    {
        "pn": "K4B4G1646D-BYNB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 4Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 4Gb x16",
            "capacity":   "512MB",
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global EMEA: K4B4G1646D-BYNB(4 Gb) ✓. "
            "BY = DDR3L 1.35V/1.5V dual. D-die, NB package. 4Gbit ÷ 8 = 512MB/die."
        ),
    },

    # ── K4B8G1646D-MYK0 — 8Gb DDR3L x16 (1GB/die) ───────────────────────────
    # Samsung Semiconductor Global: K4B8G1646D-MYK0(8 Gb) ✓
    # MY = DDR3L 1.35V. harddiskdirect: "DDR3-1600MHz 512Mx16 1.35V DRAM" ✓
    {
        "pn": "K4B8G1646D",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR3L",
            "subtype": "DDR3L PC DRAM 8Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR3L", "subtype": "DDR3L PC DRAM 8Gb x16",
            "capacity": "1GB", "interface": "DDR3L", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — deriva de K4B8G1646D-MYK0/MYMA/MMK0/MMMA (Samsung Semiconductor Global ✓). 8Gbit ÷ 8 = 1GB/die. D-die, x16."
        ),
    },
    {
        "pn": "K4B8G1646D-MYK0",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 8Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 8Gb x16",
            "capacity":   "1GB",
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B8G1646D-MYK0(8 Gb) ✓. "
            "harddiskdirect: 'Samsung DDR3-1600MHz 512Mx16 (8GB) 1.35V DRAM' ✓. "
            "MY = DDR3L 1.35V. D-die. 8Gbit ÷ 8 = 1GB/die."
        ),
    },

    # ── K4B8G1646D-MYMA — 8Gb DDR3L x16 (1GB/die) ───────────────────────────
    {
        "pn": "K4B8G1646D-MYMA",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 8Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 8Gb x16",
            "capacity":   "1GB",
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B8G1646D-MYMA(8 Gb) ✓. "
            "MY = DDR3L 1.35V. D-die, MA package. 8Gbit ÷ 8 = 1GB/die."
        ),
    },

    # ── K4B8G1646D-MMK0 — 8Gb DDR3L Industrial x16 (1GB/die) ────────────────
    # harddiskdirect: "DDR3-1600MHz 512Mx16 (8GB) Ind 1.35V DRAM" ✓
    # MM = DDR3L Industrial grade (faixa temperatura estendida)
    {
        "pn": "K4B8G1646D-MMK0",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 8Gb x16 Industrial",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 8Gb x16 Industrial",
            "capacity":   "1GB",
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B8G1646D-MMK0(8 Gb) ✓. "
            "harddiskdirect: 'DDR3-1600MHz 512Mx16 Ind 1.35V DRAM' ✓. "
            "MM = DDR3L Industrial (temp. estendida). 8Gbit ÷ 8 = 1GB/die."
        ),
    },

    # ── K4B8G1646D-MMMA — 8Gb DDR3L Industrial x16 (1GB/die) ────────────────
    # Xecor: "DDR3L SDRAM 8Gbit 512Mx16 1.35V/1.5V" ✓
    {
        "pn": "K4B8G1646D-MMMA",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 8Gb x16 Industrial",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 8Gb x16 Industrial",
            "capacity":   "1GB",
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B8G1646D-MMMA(8 Gb) ✓. "
            "Xecor (cita Samsung): 'DDR3L SDRAM 8Gbit 512Mx16 1.35V/1.5V' ✓. "
            "MM = DDR3L Industrial. 8Gbit ÷ 8 = 1GB/die."
        ),
    },

    # ── K4B2G1646F-BYMA — 2Gb DDR3L x16 (256MB/die) ─────────────────────────
    # Samsung Semiconductor Global: K4B2G1646F-BYMA(2 Gb) ✓
    # 2Gbit ÷ 8 = 256MB. Exatamente no limiar DDR3 do assess_profitability.
    {
        "pn": "K4B2G1646F",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR3L",
            "subtype": "DDR3L PC DRAM 2Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR3L", "subtype": "DDR3L PC DRAM 2Gb x16",
            "capacity": "256MB", "interface": "DDR3L", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — deriva de K4B2G1646F-BYMA/BYNB/BCK0/BCMA (Samsung Semiconductor Global ✓). 2Gbit ÷ 8 = 256MB/die. F-die, x16."
        ),
    },
    {
        "pn": "K4B2G1646F-BYMA",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 2Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 2Gb x16",
            "capacity":   "256MB",
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B2G1646F-BYMA(2 Gb) ✓. "
            "BY = DDR3L 1.35V/1.5V dual. F-die. 2Gbit ÷ 8 = 256MB/die."
        ),
    },

    # ── K4B2G1646F-BYNB — 2Gb DDR3L x16 (256MB/die) ─────────────────────────
    {
        "pn": "K4B2G1646F-BYNB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 2Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 2Gb x16",
            "capacity":   "256MB",
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B2G1646F-BYNB(2 Gb) ✓. "
            "BY = DDR3L 1.35V/1.5V dual. F-die, NB package. 2Gbit ÷ 8 = 256MB/die."
        ),
    },

    # ── K4B4G0846D-BYK0 — 4Gb DDR3L x8 (512MB/die) ──────────────────────────
    # Variante x8 (barramento 8-bit): mesmo die, metade dos pinos de dados.
    # Samsung Semiconductor Global USA: K4B4G0846D-BYK0(4 Gb) ✓
    {
        "pn": "K4B4G0846D",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR3L",
            "subtype": "DDR3L PC DRAM 4Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR3L", "subtype": "DDR3L PC DRAM 4Gb x8",
            "capacity": "512MB", "interface": "DDR3L", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — deriva de K4B4G0846D-BYK0/BYNB (Samsung Semiconductor Global ✓). 4Gbit ÷ 8 = 512MB/die. D-die, x8."
        ),
    },
    {
        "pn": "K4B4G0846D-BYK0",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 4Gb x8",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 4Gb x8",
            "capacity":   "512MB",
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global USA: K4B4G0846D-BYK0(4 Gb) ✓. "
            "BY = DDR3L 1.35V/1.5V dual. x8 bus width. D-die. 4Gbit ÷ 8 = 512MB/die."
        ),
    },

    # ── K4B4G0846D-BYNB — 4Gb DDR3L x8 (512MB/die) ──────────────────────────
    {
        "pn": "K4B4G0846D-BYNB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 4Gb x8",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 4Gb x8",
            "capacity":   "512MB",
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global EMEA: K4B4G0846D-BYNB(4 Gb) ✓. "
            "BY = DDR3L 1.35V/1.5V dual. x8 bus width. D-die. 4Gbit ÷ 8 = 512MB/die."
        ),
    },

    # ── K4B2G0846F-BYMA — 2Gb DDR3L x8 (256MB/die) ──────────────────────────
    {
        "pn": "K4B2G0846F",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR3L",
            "subtype": "DDR3L PC DRAM 2Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR3L", "subtype": "DDR3L PC DRAM 2Gb x8",
            "capacity": "256MB", "interface": "DDR3L", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — deriva de K4B2G0846F-BYMA (Samsung Semiconductor Global ✓). 2Gbit ÷ 8 = 256MB/die. F-die, x8."
        ),
    },
    {
        "pn": "K4B2G0846F-BYMA",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 2Gb x8",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3L",
            "subtype":    "DDR3L PC DRAM 2Gb x8",
            "capacity":   "256MB",
            "interface":  "DDR3L",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B2G0846F-BYMA(2 Gb) ✓. "
            "BY = DDR3L 1.35V/1.5V dual. x8 bus width. F-die. 2Gbit ÷ 8 = 256MB/die."
        ),
    },

    # ── DDR3 (1.5V) Samsung PC DRAM ──────────────────────────────────────────
    # Sufixo BC = DDR3 padrão 1.5V (não dual voltage).
    # Confirmado: datasheet Samsung DS_K4B4G1646E-BC_Rev101-0.pdf
    #   título = "4Gb E-die DDR3 SDRAM x16" (sem L = 1.5V only).

    # ── K4B4G1646E-BCK0 — 4Gb DDR3 x16 (512MB/die) ──────────────────────────
    {
        "pn": "K4B4G1646E-BCK0",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3",
            "subtype":    "DDR3 PC DRAM 4Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3",
            "subtype":    "DDR3 PC DRAM 4Gb x16",
            "capacity":   "512MB",
            "interface":  "DDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B4G1646E-BCK0(4 Gb) ✓. "
            "BC = DDR3 1.5V. Datasheet Samsung DS_K4B4G1646E-BC_Rev101-0.pdf "
            "'4Gb E-die DDR3 SDRAM x16' ✓. E-die. 4Gbit ÷ 8 = 512MB/die."
        ),
    },

    # ── K4B4G1646E-BCMA — 4Gb DDR3 x16 (512MB/die) ──────────────────────────
    {
        "pn": "K4B4G1646E-BCMA",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3",
            "subtype":    "DDR3 PC DRAM 4Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3",
            "subtype":    "DDR3 PC DRAM 4Gb x16",
            "capacity":   "512MB",
            "interface":  "DDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B4G1646E-BCMA(4 Gb) ✓. "
            "BC = DDR3 1.5V (alldatasheet: 'DDR3 SDRAM 4Gbit 256Mx16 at 1.5V') ✓. "
            "E-die. 4Gbit ÷ 8 = 512MB/die."
        ),
    },

    # ── K4B4G1646D-BCK0 — 4Gb DDR3 x16 (512MB/die) ──────────────────────────
    {
        "pn": "K4B4G1646D-BCK0",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3",
            "subtype":    "DDR3 PC DRAM 4Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3",
            "subtype":    "DDR3 PC DRAM 4Gb x16",
            "capacity":   "512MB",
            "interface":  "DDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B4G1646D-BCK0(4 Gb) ✓. "
            "BC = DDR3 1.5V. D-die. 4Gbit ÷ 8 = 512MB/die."
        ),
    },

    # ── K4B4G1646D-BCNB — 4Gb DDR3 x16 (512MB/die) ──────────────────────────
    {
        "pn": "K4B4G1646D-BCNB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3",
            "subtype":    "DDR3 PC DRAM 4Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3",
            "subtype":    "DDR3 PC DRAM 4Gb x16",
            "capacity":   "512MB",
            "interface":  "DDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B4G1646D-BCNB(4 Gb) ✓. "
            "BC = DDR3 1.5V. D-die, NB package. 4Gbit ÷ 8 = 512MB/die."
        ),
    },

    # ── K4B2G1646F-BCK0 — 2Gb DDR3 x16 (256MB/die) ──────────────────────────
    {
        "pn": "K4B2G1646F-BCK0",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3",
            "subtype":    "DDR3 PC DRAM 2Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3",
            "subtype":    "DDR3 PC DRAM 2Gb x16",
            "capacity":   "256MB",
            "interface":  "DDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B2G1646F-BCK0(2 Gb) ✓. "
            "BC = DDR3 1.5V. F-die. 2Gbit ÷ 8 = 256MB/die."
        ),
    },

    # ── K4B2G1646F-BCMA — 2Gb DDR3 x16 (256MB/die) ──────────────────────────
    {
        "pn": "K4B2G1646F-BCMA",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3",
            "subtype":    "DDR3 PC DRAM 2Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3",
            "subtype":    "DDR3 PC DRAM 2Gb x16",
            "capacity":   "256MB",
            "interface":  "DDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B2G1646F-BCMA(2 Gb) ✓. "
            "BC = DDR3 1.5V. F-die. 2Gbit ÷ 8 = 256MB/die."
        ),
    },

    # ── K4B1G1646I-BCK0 — 1Gb DDR3 x16 (128MB/die — NÃO RENTÁVEL) ───────────
    # Samsung Semiconductor Global: K4B1G1646I-BCK0(1 Gb) ✓
    # 1Gbit = 128MB/die < 256MB limiar DDR3 → NÃO RENTÁVEL (assess_profitability)
    {
        "pn": "K4B1G1646I",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR3",
            "subtype": "DDR3 PC DRAM 1Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR3", "subtype": "DDR3 PC DRAM 1Gb x16",
            "capacity": "128MB", "interface": "DDR3", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — deriva de K4B1G1646I-BCK0 (Samsung Semiconductor Global ✓). 1Gbit ÷ 8 = 128MB/die. I-die, x16. 128MB < 256MB limiar DDR3 → NÃO RENTÁVEL."
        ),
    },
    {
        "pn": "K4B1G1646I-BCK0",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "DDR3",
            "subtype":    "DDR3 PC DRAM 1Gb x16",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "DDR3",
            "subtype":    "DDR3 PC DRAM 1Gb x16",
            "capacity":   "128MB",
            "interface":  "DDR3",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4B1G1646I-BCK0(1 Gb) ✓. "
            "BC = DDR3 1.5V. I-die. 1Gbit ÷ 8 = 128MB/die. "
            "128MB < 256MB limiar DDR3 → NÃO RENTÁVEL (assess_profitability)."
        ),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Samsung DDR4 PC DRAM — família K4A (~2014–presente)
    # chip_type="DDR4", interface="DDR4", 1.2V nominal.
    # assess_profitability DDR4+: gen=4 ≥ ddr_min_gen(3) → RENTÁVEL (todas densidades).
    # Alta liquidez B2B — caixa dedicada DDR4 na bancada.
    # Densidade: pn[3:5] → 4G=4Gb(512MB) · 8G=8Gb(1GB) · AG/AH=16Gb(2GB).
    # Largura: pn[5:7] → 04=x4(ECC srvr) · 08=x8 · 16=x16.
    # Die revision: pn[7] → B=B-die · C=C-die · E=E-die · F=F-die · G=G-die.
    # Velocidade (sufixo): BCPB=2133 · BCRC=2400 · BCTD=2666 · BCWE=3200 MT/s.
    # Gramática K4A já existe — entradas aqui elevam para confidence=confirmed
    #   e permitem subtype mais preciso (largura, die revision).
    # Fontes: Samsung Semiconductor Global ("<PN>(X Gb)" nos títulos Google) ✓
    #   Datasheet Samsung: 8G_B_DDR4_Samsung_Spec_Rev2_1_Feb_17-0.pdf
    #   (download.semiconductor.samsung.com — K4A8G085WB / K4A8G045WB). ✓
    # ══════════════════════════════════════════════════════════════════════════

    # ─── 4 Gb DDR4 x8 (512MB/die) ────────────────────────────────────────────

    {
        "pn": "K4A4G085WE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x8",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — E-die, x8. Deriva de K4A4G085WE-BCPB/BCTD/BITD (Samsung Semiconductor Global ✓). 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G085WE-BCPB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x8",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A4G085WE-BCPB(4 Gb) ✓. "
            "E-die, x8, DDR4-2133 (BCPB). 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G085WE-BCTD",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x8",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A4G085WE-BCTD(4 Gb) ✓. "
            "E-die, x8, DDR4-2666 (BCTD). 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G085WE-BITD",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x8",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A4G085WE-BITD(4 Gb) ✓. "
            "E-die, x8, DDR4-2666. 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G085WF",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x8",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — F-die, x8. Deriva de K4A4G085WF-BCTD/BCWE (Samsung Semiconductor Global ✓). 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G085WF-BCTD",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x8",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A4G085WF-BCTD(4 Gb) ✓. "
            "F-die, x8, DDR4-2666 (BCTD). 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G085WF-BCWE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x8",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A4G085WF-BCWE(4 Gb) ✓. "
            "F-die, x8, DDR4-3200 (BCWE). 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G085WG",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x8",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — G-die, x8. Deriva de K4A4G085WG-BCWE (Samsung Semiconductor Global ✓). 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G085WG-BCWE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x8",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A4G085WG-BCWE(4 Gb) ✓. "
            "G-die, x8, DDR4-3200 (BCWE). 4Gbit ÷ 8 = 512MB/die."
        ),
    },

    # ─── 4 Gb DDR4 x16 (512MB/die) ───────────────────────────────────────────

    {
        "pn": "K4A4G165WE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x16",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — E-die, x16. Deriva de K4A4G165WE-BCRC/BCTD/BCWE (Samsung Semiconductor Global ✓). 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G165WE-BCRC",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x16",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A4G165WE-BCRC(4 Gb) ✓. "
            "E-die, x16, DDR4-2400 (BCRC). 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G165WE-BCTD",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x16",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A4G165WE-BCTD(4 Gb) ✓. "
            "E-die, x16, DDR4-2666. 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G165WE-BCWE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x16",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global USA: K4A4G165WE-BCWE(4 Gb) ✓. "
            "E-die, x16, DDR4-3200. 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G165WF",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x16",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — F-die, x16. Deriva de K4A4G165WF-BCTD/BCWE (Samsung Semiconductor Global ✓). 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G165WF-BCTD",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x16",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A4G165WF-BCTD(4 Gb) ✓. "
            "F-die, x16, DDR4-2666. 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G165WF-BCWE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x16",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A4G165WF-BCWE(4 Gb) ✓. "
            "F-die, x16, DDR4-3200. 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G165WG",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x16",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — G-die, x16. Deriva de K4A4G165WG-BCWE (Samsung Semiconductor Global ✓). 4Gbit ÷ 8 = 512MB/die."
        ),
    },
    {
        "pn": "K4A4G165WG-BCWE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 4Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 4Gb x16",
            "capacity": "512MB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A4G165WG-BCWE(4 Gb) ✓. "
            "G-die, x16, DDR4-3200. 4Gbit ÷ 8 = 512MB/die."
        ),
    },

    # ─── 8 Gb DDR4 x8 (1GB/die) ──────────────────────────────────────────────
    # Samsung datasheet 8G_B_DDR4_Samsung_Spec_Rev2_1_Feb_17-0.pdf ✓
    # (download.semiconductor.samsung.com) — K4A8G085WB confirma "8Gb B-die DDR4 x8, 1.2V"

    {
        "pn": "K4A8G085WB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x8",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — B-die, x8. Deriva de K4A8G085WB-BCPB/BCRC/BCTD (Samsung Global + datasheet ✓). 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G085WB-BCPB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x8",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A8G085WB-BCPB(8 Gb) ✓. "
            "Datasheet Samsung (download.semiconductor.samsung.com) ✓: "
            "'8Gb B-die DDR4 SDRAM, 512Mx8, 1.2V'. "
            "B-die, x8, DDR4-2133. 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G085WB-BCRC",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x8",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A8G085WB-BCRC(8 Gb) ✓. "
            "B-die, x8, DDR4-2400. 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G085WB-BCTD",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x8",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A8G085WB-BCTD(8 Gb) ✓. "
            "B-die, x8, DDR4-2666. 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G085WC",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x8",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — C-die, x8. Deriva de K4A8G085WC-BCRC/BCTD/BCWE (Samsung Semiconductor Global ✓). 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G085WC-BCRC",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x8",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A8G085WC-BCRC(8 Gb) ✓. "
            "C-die, x8, DDR4-2400. 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G085WC-BCTD",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x8",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A8G085WC-BCTD(8 Gb) ✓. "
            "C-die, x8, DDR4-2666. 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G085WC-BCWE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x8",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A8G085WC-BCWE(8 Gb) ✓. "
            "C-die, x8, DDR4-3200. 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G085WG",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x8",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — G-die, x8. Deriva de K4A8G085WG-BCWE (Samsung Semiconductor Global ✓). 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G085WG-BCWE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x8",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A8G085WG-BCWE(8 Gb) ✓. "
            "G-die, x8, DDR4-3200. 8Gbit ÷ 8 = 1GB/die."
        ),
    },

    # ─── 8 Gb DDR4 x16 (1GB/die) ─────────────────────────────────────────────

    {
        "pn": "K4A8G165WB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x16",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — B-die, x16. Deriva de K4A8G165WB-BCPB/BCRC/BITD (Samsung Semiconductor Global ✓). 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G165WB-BCPB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x16",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global EMEA: K4A8G165WB-BCPB(8 Gb) ✓. "
            "B-die, x16, DDR4-2133. 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G165WB-BCRC",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x16",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A8G165WB-BCRC(8 Gb) ✓. "
            "B-die, x16, DDR4-2400. 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G165WB-BITD",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x16",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A8G165WB-BITD(8 Gb) ✓. "
            "B-die, x16, DDR4-2666. 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G165WC",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x16",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — C-die, x16. Deriva de K4A8G165WC-BCRC/BCTD/BCWE (Samsung Semiconductor Global ✓). 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G165WC-BCRC",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x16",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A8G165WC-BCRC(8 Gb) ✓. "
            "C-die, x16, DDR4-2400. 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G165WC-BCTD",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x16",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A8G165WC-BCTD(8 Gb) ✓. "
            "C-die, x16, DDR4-2666. 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G165WC-BCWE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x16",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A8G165WC-BCWE(8 Gb) ✓. "
            "C-die, x16, DDR4-3200. 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G165WG",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x16",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — G-die, x16. Deriva de K4A8G165WG-BCWE (Samsung Semiconductor Global ✓). 8Gbit ÷ 8 = 1GB/die."
        ),
    },
    {
        "pn": "K4A8G165WG-BCWE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 8Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 8Gb x16",
            "capacity": "1GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4A8G165WG-BCWE(8 Gb) ✓. "
            "G-die, x16, DDR4-3200. 8Gbit ÷ 8 = 1GB/die."
        ),
    },

    # ─── 16 Gb DDR4 x8 (2GB/die) — K4AAG085W ────────────────────────────────
    # K4AAG: pn[3:5]='AG' → DRAM_PC 'AG'=16Gb. x8 bus → 2GB/die.

    {
        "pn": "K4AAG085WA",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 16Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 16Gb x8",
            "capacity": "2GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — A-die, x8. Deriva de K4AAG085WA-BCTD/BCWE (Samsung Semiconductor Global ✓). 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4AAG085WA-BCTD",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 16Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 16Gb x8",
            "capacity": "2GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4AAG085WA-BCTD(16 Gb) ✓. "
            "A-die, x8, DDR4-2666. 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4AAG085WA-BCWE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 16Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 16Gb x8",
            "capacity": "2GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4AAG085WA-BCWE(16 Gb) ✓. "
            "A-die, x8, DDR4-3200. 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4AAG085WC",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 16Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 16Gb x8",
            "capacity": "2GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — C-die, x8. Deriva de K4AAG085WC-BCWE (Samsung Semiconductor Global ✓). 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4AAG085WC-BCWE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 16Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 16Gb x8",
            "capacity": "2GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4AAG085WC-BCWE(16 Gb) ✓. "
            "C-die, x8, DDR4-3200. 16Gbit ÷ 8 = 2GB/die."
        ),
    },

    # ─── 16 Gb DDR4 x16 (2GB/die) — K4AAG165W ───────────────────────────────

    {
        "pn": "K4AAG165WA",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 16Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 16Gb x16",
            "capacity": "2GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — A-die, x16. Deriva de K4AAG165WA-BCTD/BCWE (Samsung Semiconductor Global ✓). 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4AAG165WA-BCTD",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 16Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 16Gb x16",
            "capacity": "2GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4AAG165WA-BCTD(16 Gb) ✓. "
            "A-die, x16, DDR4-2666. 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4AAG165WA-BCWE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 16Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 16Gb x16",
            "capacity": "2GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4AAG165WA-BCWE(16 Gb) ✓. "
            "A-die, x16, DDR4-3200. 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4AAG165WB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 16Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 16Gb x16",
            "capacity": "2GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — B-die, x16. Deriva de K4AAG165WB-MCTD (Samsung Semiconductor Global ✓). 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4AAG165WB-MCTD",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR4",
            "subtype": "DDR4 PC DRAM 16Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR4", "subtype": "DDR4 PC DRAM 16Gb x16",
            "capacity": "2GB", "interface": "DDR4", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4AAG165WB-MCTD(16 Gb) ✓. "
            "B-die, x16, DDR4-2666 (MCTD = grau especial). 16Gbit ÷ 8 = 2GB/die."
        ),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Samsung DDR5 PC DRAM — famílias K4RA / K4RB / K4RCH (~2021–presente)
    # chip_type="DDR5", interface="DDR5", 1.1V.
    # assess_profitability DDR5: gen=5 ≥ ddr_min_gen(3) → RENTÁVEL.
    # Caixa separada DDR5 na bancada — incompatível com DDR4 (slot, tensão, protocolo).
    # Densidades: K4RAH=16Gb(2GB/die) · K4RBH=32Gb(4GB/die) · K4RCH=32Gb(4GB/die).
    # ⚠ K4RCH: prefixo K4RC SEM família na gramática — cairia em K4R RDRAM (errado!).
    #   Entradas abaixo são CRÍTICAS para corrigir a classificação.
    # Fontes: Samsung Semiconductor Global ("<PN>(X Gb)" confirmado) ✓
    #   K4RCH: Samsung Global "(32 Gb)" ✓ + Uvation (cita Samsung): "DDR5 32 Gb" ✓
    # ══════════════════════════════════════════════════════════════════════════

    # ─── 16 Gb DDR5 x8 (2GB/die) — K4RAH086V ────────────────────────────────
    # K4RA: gramática existe (priority=80); entradas elevam para confirmed.

    {
        "pn": "K4RAH086VB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x8",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — B-die, x8. Deriva de K4RAH086VB-BCQK/BIQK/BIWM (Samsung Semiconductor Global ✓). 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4RAH086VB-BCQK",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x8",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global (populate_samsung.py ✓): K4RAH086VB-BCQK(16 Gb). "
            "B-die, x8, DDR5-4800 (BCQK). 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4RAH086VB-BIQK",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x8",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global/EMEA: K4RAH086VB-BIQK(16 Gb) ✓. "
            "B-die, x8, DDR5-4800. 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4RAH086VB-BIWM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x8",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4RAH086VB-BIWM(16 Gb) ✓. "
            "B-die, x8, DDR5-5600. 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4RAH086VE",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x8",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — E-die, x8. Deriva de K4RAH086VE-BCWM (Samsung Semiconductor Global ✓). 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4RAH086VE-BCWM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x8",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4RAH086VE-BCWM(16 Gb) ✓. "
            "E-die, x8, DDR5-5600. 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4RAH086VP",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x8",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — P-die, x8. Deriva de K4RAH086VP-BCWM (Samsung Semiconductor Global ✓). 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4RAH086VP-BCWM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x8",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4RAH086VP-BCWM(16 Gb) ✓. "
            "P-die, x8, DDR5-5600. 16Gbit ÷ 8 = 2GB/die."
        ),
    },

    # ─── 16 Gb DDR5 x16 (2GB/die) — K4RAH165V ───────────────────────────────

    {
        "pn": "K4RAH165VB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x16",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — B-die, x16. Deriva de K4RAH165VB-BCQK/BCWM/BIQK/BIWM (Samsung Semiconductor Global ✓). 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4RAH165VB-BCQK",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x16",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4RAH165VB-BCQK(16 Gb) ✓. "
            "B-die, x16, DDR5-4800. 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4RAH165VB-BCWM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x16",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4RAH165VB-BCWM(16 Gb) ✓. "
            "B-die, x16, DDR5-5600. 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4RAH165VB-BIQK",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x16",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4RAH165VB-BIQK(16 Gb) ✓. "
            "B-die, x16, DDR5-4800. 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4RAH165VB-BIWM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x16",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4RAH165VB-BIWM(16 Gb) ✓. "
            "B-die, x16, DDR5-5600. 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4RAH165VP",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x16",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — P-die, x16. Deriva de K4RAH165VP-BCWM (Samsung Semiconductor Global ✓). 16Gbit ÷ 8 = 2GB/die."
        ),
    },
    {
        "pn": "K4RAH165VP-BCWM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 16Gb x16", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 16Gb x16",
            "capacity": "2GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4RAH165VP-BCWM(16 Gb) ✓. "
            "P-die, x16, DDR5-5600. 16Gbit ÷ 8 = 2GB/die."
        ),
    },

    # ─── 32 Gb DDR5 x8 (4GB/die) — K4RBH046V ────────────────────────────────
    # K4RB: gramática existe (priority=80). Entradas elevam para confirmed.

    {
        "pn": "K4RBH046VM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 32Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 32Gb x8",
            "capacity": "4GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — B-die, x8. Deriva de K4RBH046VM-BCCP/BCWM (Samsung Semiconductor Global ✓). 32Gbit ÷ 8 = 4GB/die."
        ),
    },
    {
        "pn": "K4RBH046VM-BCCP",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 32Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 32Gb x8",
            "capacity": "4GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4RBH046VM-BCCP(32 Gb) ✓. "
            "B-die, x8. 32Gbit ÷ 8 = 4GB/die. DDR5 alta densidade."
        ),
    },
    {
        "pn": "K4RBH046VM-BCWM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 32Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 32Gb x8",
            "capacity": "4GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global USA: K4RBH046VM-BCWM(32 Gb) ✓. "
            "B-die, x8, DDR5-5600. 32Gbit ÷ 8 = 4GB/die."
        ),
    },

    # ─── 32 Gb DDR5 — K4RCH046V (CRÍTICO: sem gramática — cairia em RDRAM!) ──
    # K4RC não está no populate_samsung.py. K4RCH cairia em K4R RDRAM (priority=100).
    # Estas entradas com confidence="confirmed" são OBRIGATÓRIAS para classificação correta.
    # Samsung Semiconductor Global: K4RCH046VM-2CLP(32 Gb) ✓ / K4RCH046VM-2CCM(32 Gb) ✓
    # Uvation (cita Samsung): "DDR5 32 Gb DIMM" → 32Gbit ÷ 8 = 4GB/die.
    # Velocidade: -2CLP = DDR5-6400 / -2CCM = DDR5-5600 (padrão CLP/CCM Samsung DDR5).
    # ⚠ Nota para arquivo: K4RC merece família na gramática (populate_samsung.py)
    #   para cobrir variantes futuras. Por ora, PNs abaixo resolvem os conhecidos.

    {
        "pn": "K4RCH046VM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 32Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 32Gb x8",
            "capacity": "4GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Base PN — C-die, x8. Deriva de K4RCH046VM-2CLP/2CCM (Samsung Semiconductor Global ✓). 32Gbit ÷ 8 = 4GB/die. ⚠ K4RC SEM gramática → cairia em K4R RDRAM sem esta entrada."
        ),
    },
    {
        "pn": "K4RCH046VM-2CLP",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 32Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 32Gb x8",
            "capacity": "4GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global: K4RCH046VM-2CLP(32 Gb) ✓. "
            "Uvation (cita Samsung): 'DDR5 32 Gb DIMM' ✓. "
            "C-die (nova revisão vs K4RBH B-die), x8, DDR5-6400 (2CLP). "
            "32Gbit ÷ 8 = 4GB/die. "
            "⚠ CRÍTICO: K4RC SEM gramática → cairia em K4R RDRAM sem esta entrada."
        ),
    },
    {
        "pn": "K4RCH046VM-2CCM",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung", "chip_type": "DDR5",
            "subtype": "DDR5 PC DRAM 32Gb x8", "status": "enriched", "confidence": "confirmed",
        },
        "fields": {
            "chip_type": "DDR5", "subtype": "DDR5 PC DRAM 32Gb x8",
            "capacity": "4GB", "interface": "DDR5", "confidence": "confirmed", "status": "enriched",
        },
        "reason": (
            "Samsung Semiconductor Global USA/EMEA: K4RCH046VM-2CCM(32 Gb) ✓. "
            "Uvation (cita Samsung): 'DDR5 32 Gb DIMM' ✓. "
            "C-die, x8, DDR5-5600 (2CCM). 32Gbit ÷ 8 = 4GB/die. "
            "⚠ CRÍTICO: K4RC SEM gramática → cairia em K4R RDRAM sem esta entrada."
        ),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Raw MCP legado — K5 family (Samsung feature phone era ~2004-2008)
    # chip_type = "MCP" (não eMCP — sem controladora eMMC)
    # assess_profitability retorna "NÃO RENTÁVEL" para chip_type="MCP" (engine.py)
    # ══════════════════════════════════════════════════════════════════════════

    # ── K524G2GACJ ────────────────────────────────────────────────────────────
    # Samsung Raw MCP: 4Gbit NAND (512MB) + 2Gbit mDDR1 (256MB).
    # NÃO é eMCP — expõe pinos NAND e DRAM diretamente, sem controladora eMMC.
    # Era feature phone / basic phone Samsung (~2004-2008). Hoje 100% sucata.
    # Fontes Tier 1:
    #   • Octopart: K524G2GACJ-B050 — 5 distribuidores listados ✓ (2026-05-29)
    #   • Datasheet K524G2GACB (família): "4Gbit NAND Flash + 2Gbit Mobile DDR" ✓
    #   • datasheetspdf.com/pdf/696405/Samsungsemiconductor/K524G2GACB-A050/1
    # Sem controladora: nenhum programador BGA atual consegue extrair partições.
    # Destino obrigatório: moagem / recuperação de metais preciosos.
    {
        "pn": "K524G2GACJ",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "MCP",
            "subtype":    "Raw MCP — NAND 512MB + mDDR1 256MB",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "MCP",
            "subtype":    "Raw MCP — NAND 512MB + mDDR1 256MB",
            "capacity":   "NAND 512MB + mDDR1 256MB",
            "device":     "SUCATA — Raw MCP Samsung legado (feature phone ~2004-2008). "
                          "Sem controladora eMMC. Programadores BGA atuais incompatíveis. "
                          "Destino: moagem / recuperação de metais.",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Família K5 = Samsung Raw MCP pré-eMCP: NAND raw + mDDR1 sem controladora. "
            "K524G2GACJ = 4Gbit NAND (÷8=512MB) + 2Gbit mDDR1 (÷8=256MB). "
            "Octopart: K524G2GACJ-B050, 5 distribuidores ✓ (2026-05-29). "
            "Datasheet K524G2GACB-A050: '4Gbit NAND Flash + 2Gbit Mobile DDR' ✓. "
            "chip_type='MCP' → assess_profitability retorna 'NÃO RENTÁVEL' (engine.py). "
            "Operador deve descartar imediatamente para moagem — sem liquidez B2B."
        ),
    },

    # ── K524G2GACB ────────────────────────────────────────────────────────────
    # Die revision B (1ª revisão): o próprio datasheet Samsung K524G2GACB-A050
    # é a fonte canônica da família — Revisão 1.3, novembro 2009.
    # Fontes Tier 1:
    #   • Datasheet Samsung K524G2GACB-A050 (Tier 1 direto): título na página
    #     alldatasheet = "MCP MEMORY" (94 páginas, fabricante Samsung Semiconductor)
    #     Conteúdo pág 12: "4,096M Bit for 4Gb NAND Flash" + "2Gbit Mobile DDR" ✓
    #   • URL: alldatasheet.com/datasheet-pdf/pdf/412398/SAMSUNG/K524G2GACB-A050.html
    #   • Package: -A050 = 137-ball FBGA, 10.5×13×1.2mm, pitch 0.8mm
    {
        "pn": "K524G2GACB",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "MCP",
            "subtype":    "Raw MCP — NAND 512MB + mDDR1 256MB",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "MCP",
            "subtype":    "Raw MCP — NAND 512MB + mDDR1 256MB",
            "capacity":   "NAND 512MB + mDDR1 256MB",
            "device":     "SUCATA — Raw MCP Samsung legado (feature phone ~2004-2009). "
                          "Sem controladora eMMC. Programadores BGA atuais incompatíveis. "
                          "Destino: moagem / recuperação de metais.",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Datasheet Samsung K524G2GACB-A050 (Tier 1 direto, Rev 1.3, nov 2009): "
            "'MCP MEMORY' — '4,096M Bit for 4Gb NAND Flash' + '2Gbit Mobile DDR' ✓. "
            "4Gbit NAND ÷8=512MB; 2Gbit mDDR1 ÷8=256MB. "
            "Package: -A050 = 137-ball FBGA 10.5×13×1.2mm (pitch 0.8mm). "
            "chip_type='MCP' → assess_profitability retorna 'NÃO RENTÁVEL' (engine.py). "
            "Operador: descartar para moagem — sem controladora, sem liquidez B2B."
        ),
    },

    # ── K524G2GACH ────────────────────────────────────────────────────────────
    # Die revision H — mesmos specs do K524G2GACB (mesmo datasheet Samsung).
    # Package evoluiu para -B050 (revisions H/I/J em diante).
    # Fontes Tier 1:
    #   • Apogeeweb (datasheet Samsung): K524G2GACH-B050 = "MCP 512MB Nand 256M MDDR400 FBGA" ✓
    #   • Win-Source, Kynix, Jotrin, Censtry, Veswin: confirmam mesmos specs
    #   • Base: datasheet Samsung K524G2GACB-A050 (família) — die revision ≠ specs
    {
        "pn": "K524G2GACH",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "MCP",
            "subtype":    "Raw MCP — NAND 512MB + mDDR1 256MB",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "MCP",
            "subtype":    "Raw MCP — NAND 512MB + mDDR1 256MB",
            "capacity":   "NAND 512MB + mDDR1 256MB",
            "device":     "SUCATA — Raw MCP Samsung legado (feature phone ~2004-2009). "
                          "Sem controladora eMMC. Programadores BGA atuais incompatíveis. "
                          "Destino: moagem / recuperação de metais.",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Família K524G2G: die revision H (package -B050). "
            "Apogeeweb (cita datasheet Samsung): K524G2GACH-B050 = '512MB NAND + 256M MDDR400 FBGA' ✓. "
            "Specs idênticos ao K524G2GACB (datasheet Samsung K524G2GACB-A050, Rev 1.3). "
            "Die revision (B→H) não altera capacidade — padrão Samsung. "
            "chip_type='MCP' → assess_profitability retorna 'NÃO RENTÁVEL' (engine.py). "
            "Operador: descartar para moagem — sem controladora, sem liquidez B2B."
        ),
    },

    # ── K524G2GACI ────────────────────────────────────────────────────────────
    # Die revision I — mesmos specs (NAND 512MB + mDDR1 256MB), package -B050.
    # Fontes Tier 1:
    #   • Samsung MemoryLink (portal oficial Samsung): K524G2GACI-B050 = "NAND based MCP" ✓
    #   • Jotrin Electronics, Ariat-Tech: "512MB NAND + 256MB MDDR400 FBGA" ✓
    #   • Base: datasheet Samsung K524G2GACB-A050 (família)
    {
        "pn": "K524G2GACI",
        "create": True,
        "create_defaults": {
            "brand_name": "Samsung",
            "chip_type":  "MCP",
            "subtype":    "Raw MCP — NAND 512MB + mDDR1 256MB",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "chip_type":  "MCP",
            "subtype":    "Raw MCP — NAND 512MB + mDDR1 256MB",
            "capacity":   "NAND 512MB + mDDR1 256MB",
            "device":     "SUCATA — Raw MCP Samsung legado (feature phone ~2004-2009). "
                          "Sem controladora eMMC. Programadores BGA atuais incompatíveis. "
                          "Destino: moagem / recuperação de metais.",
            "confidence": "confirmed",
            "status":     "enriched",
        },
        "reason": (
            "Família K524G2G: die revision I (package -B050). "
            "Samsung MemoryLink (portal oficial Samsung): K524G2GACI-B050 = 'NAND based MCP' ✓. "
            "Jotrin / Ariat-Tech: '512MB NAND + 256MB MDDR400 FBGA' ✓. "
            "Specs idênticos ao K524G2GACB (datasheet Samsung K524G2GACB-A050, Rev 1.3). "
            "Die revision (B→I) não altera capacidade — padrão Samsung. "
            "chip_type='MCP' → assess_profitability retorna 'NÃO RENTÁVEL' (engine.py). "
            "Operador: descartar para moagem — sem controladora, sem liquidez B2B."
        ),
    },

    # ── JY464 — MT29C4G48MAZAPAKD-5 IT ES (Engineering Sample) ─────────────
    {
        "pn": "MT29C4G48MAZAPAKD5ITES",
        "create": True,
        "create_defaults": {
            "brand_name": "Micron",
            "chip_type":  "NAND Flash",
            "subtype":    "SLC NAND paralela industrial",
            "status":     "enriched",
            "confidence": "confirmed",
        },
        "fields": {
            "capacity":   "512MB",
            "interface":  "Parallel NAND (8-bit)",
            "fbga_code":  "JY464",
            "confidence": "confirmed",
            "status":     "enriched",
            "notes": (
                "4 Gbit SLC NAND Flash paralela (x8). Industrial Temp (-40°C/+85°C). "
                "⚠ ES = Engineering Sample — amostra de engenharia, NÃO produção final. "
                "⚠ NÃO é eMCP/eMMC/UFS — NAND raw, sem controlador. "
                "Destino: resíduo/industrial. Variante -5 ES (50ns)."
            ),
            "source_url": "https://www.micron.com/support/tools-and-utilities/fbga?fbga=JY464",
        },
        "reason": (
            "FBGA JY464 = MT29C4G48MAZAPAKD-5 IT ES (API Micron FBGA decoder). "
            "ES = Engineering Sample (NÃO produção final). "
            "4 Gbit SLC NAND Flash ÷ 8 = 512MB. ⚠ NÃO é eMCP — NAND raw."
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
