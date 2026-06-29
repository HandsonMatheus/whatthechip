"""
Management command: add_chip_families
======================================
Popula ChipFamily para SK Hynix, Micron, KIOXIA/Toshiba, Nanya e Kingston.

As famílias Samsung são importadas via import_chipid (vêm do chipid_project).
Este comando cobre as demais marcas com os prefixos mais comuns no mercado
de refurbishing e reciclagem eletrônica.

Nota sobre decode rules:
    Os campos decode_cap_pos / decode_cap_map ficam vazios por enquanto.
    Sem essas regras, o engine passa para Gemini usando chip_type + subtype
    como contexto — muito melhor que uma busca Gemini sem hint nenhum.
    As regras de decodificação podem ser adicionadas incrementalmente pelo
    admin (/admin/chips/chipfamily/) conforme a documentação for crescendo.

Uso:
    python manage.py add_chip_families
    python manage.py add_chip_families --dry-run
    python manage.py add_chip_families --overwrite   # atualiza registros existentes
"""

from django.core.management.base import BaseCommand
from chips.models import Brand, ChipFamily


# ── Dados das famílias ────────────────────────────────────────────────────────
#
# Campos obrigatórios: brand_name, prefix, chip_type
# Campos opcionais:    subtype, interface, is_emcp, tip, priority
#
# priority: menor número = maior prioridade no match de prefixo mais longo.
# Use 50 para famílias bem definidas, 100 (default) para genéricas.

FAMILIES = [

    # ── SK Hynix ──────────────────────────────────────────────────────────────

    {
        'brand_name': 'SK Hynix',
        'prefix':     'H9TQ',
        'chip_type':  'eMCP',
        'subtype':    'LPDDR3 + eMMC',
        'interface':  'eMMC 4.5 / 5.0',
        'is_emcp':    True,
        'priority':   50,
        'tip': (
            'eMCP SK Hynix com LPDDR3 (RAM) + eMMC (NAND). '
            'Muito comum em smartphones Samsung de entrada e médio (2015–2020). '
            'Ex: H9TQ64A8MDAC-RD = 64Gb NAND + 8Gb RAM.'
        ),
    },
    {
        'brand_name': 'SK Hynix',
        'prefix':     'H9TP',
        'chip_type':  'eMCP',
        'subtype':    'eMCP LPDDR2',
        'interface':  'eMMC 4.x + LPDDR2',
        'is_emcp':    True,
        'priority':   40,  # < H9TQ (50) — prefixo específico, não conflitar
        'tip': (
            'eMCP SK Hynix com LPDDR2 (H9TP). Chip combinado eMMC + RAM, geração ANTERIOR ao H9TQ. '
            'pn[4:6] = capacidade NAND: 32=4GB · 64=8GB. '
            'pn[6:8] = capacidade RAM: A4=512MB · A8=1GB · AB=2GB. '
            '⚠ H9TP usa LPDDR2, NÃO LPDDR4 — subtype "LPDDR4" em fontes antigas é erro histórico. '
            'Ex: H9TP32A4GDCC = 4GB NAND + 512MB LPDDR2 ✓ (absunshine). '
            'Ex: H9TP64A8JDAC = 8GB NAND + 1GB LPDDR2 ✓ (Elnec). '
            'Destino: bancada eMCP legado — peça obsoleta, baixo valor comercial.'
        ),
    },
    {
        'brand_name': 'SK Hynix',
        'prefix':     'H5AN',
        'chip_type':  'DDR4',
        'subtype':    'DDR4 SDRAM',
        'interface':  'DDR4',
        'is_emcp':    False,
        'priority':   50,
        'tip': (
            'DDR4 SDRAM SK Hynix para desktops e notebooks. '
            'H5 = SK Hynix DRAM, AN = DDR4. Ex: H5AN8G6NAFR-UHC = 8Gb DDR4.'
        ),
    },
    {
        'brand_name': 'SK Hynix',
        'prefix':     'H5TC',
        'chip_type':  'DDR3L',
        'subtype':    'DDR3L SDRAM',
        'interface':  'DDR3L',
        'is_emcp':    False,
        'priority':   50,
        'tip': 'DDR3L SDRAM SK Hynix. Comum em notebooks e chromebooks.',
    },
    {
        'brand_name': 'SK Hynix',
        'prefix':     'H54G',
        'chip_type':  'LPDDR4',
        'subtype':    'LPDDR4 SDRAM',
        'interface':  'LPDDR4',
        'is_emcp':    False,
        'priority':   50,
        'tip': 'LPDDR4 mobile SK Hynix. Encontrado em smartphones e tablets mid-range.',
    },
    {
        'brand_name': 'SK Hynix',
        'prefix':     'H26M',
        'chip_type':  'eMMC',
        'subtype':    'eMMC standalone',
        'interface':  'eMMC 5.1',
        'is_emcp':    False,
        'priority':   50,
        'tip': 'eMMC standalone SK Hynix. Encontrado em tablets, TVs e dispositivos IoT.',
    },
    {
        'brand_name': 'SK Hynix',
        'prefix':     'HKMAG',
        'chip_type':  'UFS',
        'subtype':    'UFS 2.1',
        'interface':  'UFS 2.1',
        'is_emcp':    False,
        'priority':   50,
        'tip': 'UFS 2.1 SK Hynix. Encontrado em smartphones premium a partir de 2018.',
    },
    {
        'brand_name': 'SK Hynix',
        'prefix':     'H9HCN',
        'chip_type':  'LPDDR4X',
        'subtype':    'LPDDR4X standalone',
        'interface':  'LPDDR4X',
        'is_emcp':    False,
        'priority':   40,  # < 55 (H9HC) para bater primeiro no prefixo mais longo
        'tip': (
            'LPDDR4X standalone SK Hynix, Era 1 (H9HCN — prefixo 5 chars). RAM pura, zero NAND. '
            'Anatomia: H9H=Mobile DRAM · C=LPDDR4X bus (VDDQ 0.6V, NÃO é capacidade) · NNN=sem NAND · pn[7]=densidade. '
            'pn[7]: 4=512MB · 8=1GB · B=2GB · D=3GB · C=4GB · E=6GB · F=8GB. '
            '⚠ NÃO é UFS — protocolo RAM volátil, incompatível com soquete de armazenamento. '
            'Destino: bancada LPDDR4X — silício de alto valor, isolamento ESD obrigatório.'
        ),
    },

    # ── Micron ────────────────────────────────────────────────────────────────

    {
        'brand_name': 'Micron',
        'prefix':     'MTFC',
        'chip_type':  'eMMC',
        'subtype':    'eMMC standalone',
        'interface':  'eMMC 5.1',
        'is_emcp':    False,
        'priority':   50,
        'tip': (
            'eMMC standalone Micron. '
            'MT = Micron Technology, FC = Flash Controller. '
            'Ex: MTFC4GACAAAM-1M = 4GB eMMC.'
        ),
    },
    {
        'brand_name': 'Micron',
        'prefix':     'MT40A',
        'chip_type':  'DDR4',
        'subtype':    'DDR4 SDRAM',
        'interface':  'DDR4',
        'is_emcp':    False,
        'priority':   50,
        'tip': (
            'DDR4 SDRAM Micron para desktops/servidores. '
            'Ex: MT40A512M16TB-062E = 512M×16bit = 8Gb.'
        ),
    },
    {
        'brand_name': 'Micron',
        'prefix':     'MT41K',
        'chip_type':  'DDR3L',
        'subtype':    'DDR3L SDRAM',
        'interface':  'DDR3L',
        'is_emcp':    False,
        'priority':   50,
        'tip': 'DDR3L SDRAM Micron. Geração anterior ao MT40A.',
    },
    {
        'brand_name': 'Micron',
        'prefix':     'MT52L',
        'chip_type':  'LPDDR3',
        'subtype':    'LPDDR3',
        'interface':  'LPDDR3',
        'is_emcp':    False,
        'priority':   50,
        'decode_density_type': 'micron',   # fórmula depth×width no engine (sem dies)
        'tip': (
            'LPDDR3 mobile Micron (nomenclatura: "52" = LPDDR3, atestado tier-1). '
            'Decode: profundidade × largura ÷ 8 = GB (o sufixo D{N} = dies NÃO multiplica). '
            'Ex: MT52L512M32D2PF-107 = 512M×32bit = 16Gb ÷ 8 = 2GB.'
        ),
    },
    {
        'brand_name': 'Micron',
        'prefix':     'MT29F',
        'chip_type':  'NAND Flash',
        'subtype':    'Raw NAND Flash',
        'interface':  'Async/ONFI',
        'is_emcp':    False,
        'priority':   50,
        'tip': (
            'NAND Flash raw Micron. '
            'Encontrado em SSDs, cartões de memória e equipamentos industriais.'
        ),
    },
    {
        'brand_name': 'Micron',
        'prefix':     'MT53B',
        'chip_type':  'LPDDR4',
        'subtype':    'LPDDR4',
        'interface':  'LPDDR4',
        'is_emcp':    False,
        'priority':   50,
        'decode_density_type': 'micron',   # fórmula depth×width no engine (sem dies)
        'tip': (
            'LPDDR4 standalone Micron (MT53B — VDDQ 1.1V). RAM pura, zero NAND. '
            '⚠ Diferente do MT53E (LPDDR4X, 0.6V) — tensão incompatível entre os dois. '
            'Decode: bloco [Profundidade][Largura] após o prefixo — multiplicar ÷ 8 = GB '
            '(o sufixo D{N} = dies NÃO multiplica). '
            'Ex: MT53B512M64D4TX → 512M×64bit = 32Gb ÷ 8 = 4GB LPDDR4. '
            'FBGA code D9VFC. '
            'Isolamento ESD obrigatório — chip de alto valor.'
        ),
    },
    {
        'brand_name': 'Micron',
        'prefix':     'MT53E',
        'chip_type':  'LPDDR4X',
        'subtype':    'LPDDR4X',
        'interface':  'LPDDR4X',
        'is_emcp':    False,
        'priority':   50,
        'decode_density_type': 'micron',   # fórmula depth×width no engine (sem dies)
        'tip': (
            'LPDDR4X standalone Micron. RAM pura, zero NAND. '
            'Decode: bloco [Profundidade][Largura] no PN — Profundidade × Largura bits ÷ 8 = GB '
            '(o sufixo D{N} = dies NÃO multiplica). '
            'Ex: MT53E1G32D4NQ → 1G×32bit = 32Gb ÷ 8 = 4GB; MT53E768M32D4DT → 768M×32 = 24Gb ÷ 8 = 3GB. '
            'Isolamento ESD obrigatório — chip de alto valor.'
        ),
    },
    {
        'brand_name': 'Micron',
        'prefix':     'MT53D',
        'chip_type':  'LPDDR4',
        'subtype':    'LPDDR4',
        'interface':  'LPDDR4',
        'is_emcp':    False,
        'priority':   50,
        'decode_density_type': 'micron',   # fórmula depth×width no engine (sem dies)
        'tip': (
            'LPDDR4 standalone Micron. RAM pura, zero NAND. '
            'Decode: bloco [Profundidade][Largura], ÷ 8 = GB (o sufixo D{N} = dies NÃO multiplica). '
            'Ex: MT53D768M32D4BD → 768M×32bit = 24Gb ÷ 8 = 3GB; MT53D384M32D2NQ → 384M×32 = 12Gb ÷ 8 = 1.5GB.'
        ),
    },
    {
        'brand_name': 'Micron',
        'prefix':     'MT29T',
        'chip_type':  'eMCP',
        'subtype':    'eMCP (eMMC + LPDDR)',
        'interface':  'eMMC + LPDDR',
        'is_emcp':    True,
        'priority':   50,
        'tip': (
            'eMCP Micron série MT29T. NAND + RAM no mesmo encapsulamento. '
            'Decode: bloco após "ZZZ" — 1° char=NAND, 3° char=DRAM (em Gbit). '
            'Ex: MT29TZZZ8D5BKFAH → 8=64Gb NAND (8GB) / 5=8Gb DRAM (1GB). '
            'Destino: bancada eMCP.'
        ),
    },
    {
        'brand_name': 'Micron',
        'prefix':     'MT29P',
        'chip_type':  'eMCP',
        'subtype':    'eMCP (eMMC + LPDDR)',
        'interface':  'eMMC + LPDDR',
        'is_emcp':    True,
        'priority':   50,
        'tip': (
            'eMCP Micron série MT29P. Mesmo esquema de decode do MT29T. '
            'Bloco após "ZZZ": 1° char=NAND Gbit, 3° char=DRAM Gbit. '
            'Ex: MT29PZZZ4D4BKESK → 4=32Gb NAND (4GB) / 4=4Gb DRAM (512MB). '
            'Destino: bancada eMCP.'
        ),
    },

    # ── KIOXIA / Toshiba ──────────────────────────────────────────────────────

    {
        'brand_name': 'KIOXIA',
        'prefix':     'THGBMHG',
        'chip_type':  'eMMC',
        'subtype':    'eMMC (Toshiba/KIOXIA)',
        'interface':  'eMMC 5.1',
        'is_emcp':    False,
        'priority':   50,
        'tip': (
            'eMMC Toshiba/KIOXIA série THGBMHG (BiCS NAND). '
            'THG = Toshiba NAND Group. '
            'Decode: par alfanumérico após THGBM = [geração][densidade]. '
            'Mapa de densidade: G7=128Gb=16GB · G8=256Gb=32GB. '
            'Ex: THGBMHG8C4LBAIR → G8 = 256Gb = 32GB eMMC 5.1 ✓ (SK Hynix PN Guide + manifesto). '
            'Destino: bancada eMMC.'
        ),
    },
    {
        'brand_name': 'KIOXIA',
        'prefix':     'THGBMFG',
        'chip_type':  'eMMC',
        'subtype':    'eMMC (Toshiba/KIOXIA)',
        'interface':  'eMMC 5.1',
        'is_emcp':    False,
        'priority':   50,
        'tip': (
            'eMMC Toshiba/KIOXIA série THGBMFG (geração anterior ao MHG). '
            'Mesmo esquema de decode: par após THGBM = [geração][densidade]. '
            'G7=128Gb=16GB. '
            'Ex: THGBMFG7C2L → G7 = 128Gb = 16GB eMMC ✓ (Toshiba PN Guide). '
            'Destino: bancada eMMC.'
        ),
    },
    {
        'brand_name': 'KIOXIA',
        'prefix':     'THGJFBT',
        'chip_type':  'eMMC',
        'subtype':    'eMMC (Toshiba)',
        'interface':  'eMMC 5.1',
        'is_emcp':    False,
        'priority':   50,
        'tip': 'eMMC Toshiba — geração BG NAND. Encontrado em tablets e smartphones mid-range.',
    },
    {
        'brand_name': 'KIOXIA',
        'prefix':     'KMEYH',
        'chip_type':  'eMMC',
        'subtype':    'eMMC (KIOXIA)',
        'interface':  'eMMC 5.1',
        'is_emcp':    False,
        'priority':   50,
        'tip': 'eMMC com branding KIOXIA (pós-2019). Substitui a linha THGB em produtos mais recentes.',
    },
    # KLUDG removido: KLU é Samsung (não Kioxia).
    # K=Samsung, L=NAND standalone, U=UFS — Samsung produz a linha KLU.
    # KLUDG agora gerenciado por populate_samsung.py com brand=Samsung.
    {
        'brand_name': 'KIOXIA',
        'prefix':     'TH58',
        'chip_type':  'NAND Flash',
        'subtype':    'Raw NAND Flash (Toshiba)',
        'interface':  'Async/ONFI',
        'is_emcp':    False,
        'priority':   80,
        'tip': 'NAND Flash raw Toshiba. Prefixo TH58 cobre várias gerações (SLC, MLC, TLC).',
    },

    # ── Nanya ─────────────────────────────────────────────────────────────────

    {
        'brand_name': 'Nanya',
        'prefix':     'NT5CC',
        'chip_type':  'DDR3',
        'subtype':    'DDR3',
        'interface':  'DDR3',
        'is_emcp':    False,
        'priority':   50,
        'tip': (
            'DDR3 SDRAM Nanya. '
            'NT5CC = Nanya DDR3. '
            'Ex: NT5CC256M16DP-DI = 256M×16bit = 4Gb DDR3.'
        ),
    },
    {
        'brand_name': 'Nanya',
        'prefix':     'NT5AD',
        'chip_type':  'DDR4',
        'subtype':    'DDR4',
        'interface':  'DDR4',
        'is_emcp':    False,
        'priority':   50,
        'tip': 'DDR4 SDRAM Nanya. Geração posterior ao NT5CC.',
    },
    {
        'brand_name': 'Nanya',
        'prefix':     'NT5PA',
        'chip_type':  'DDR3L',
        'subtype':    'DDR3L',
        'interface':  'DDR3L',
        'is_emcp':    False,
        'priority':   50,
        'tip': 'DDR3L Nanya, variante low-voltage do NT5CC. Comum em notebooks.',
    },

    # ── Kingston ──────────────────────────────────────────────────────────────
    # Kingston comercializa módulos (não chips bare), então os PNs são de módulos.
    # As famílias abaixo cobrem os códigos de produto Kingston mais comuns
    # que chegam ao mercado de refurbishing em forma de módulos desmontados.

    {
        'brand_name': 'Kingston',
        'prefix':     'KVR',
        'chip_type':  'RAM',
        'active':     False,  # Kingston ValueRAM = modulos DIMM, nao chip — bogus (ver memoria)
        'subtype':    'DDR',
        'interface':  'DDR / DDR2 / DDR3 / DDR4',
        'is_emcp':    False,
        'priority':   80,
        'tip': (
            'Módulo ValueRAM Kingston. '
            'KVR[velocidade][latência][largura]x[capacidade]. '
            'Ex: KVR32N22S8/8 = DDR4-3200, CL22, SO-DIMM, 8GB.'
        ),
    },
    # ── Samsung KF9* NAND Flash (priority 70 < Kingston KF priority 80) ──────
    # Conflito de prefixo: Samsung usa KF9* para NAND Flash (K9-series);
    # Kingston usa KF* para módulos Fury DDR4/DDR5.
    # Solução: KF9 com priority=70 é verificado ANTES de KF Kingston (priority=80).
    # Motor: order_by("priority", "-prefix_len") → KF9 (len=3, p=70) vence KF (len=2, p=80).
    # Confirmado: KF98G16Q4X-BEB0 = Samsung 8Gbit NAND Flash — Octopart ✓ + Elnec ✓ (2026-05-29).
    {
        'brand_name': 'Samsung',
        'prefix':     'KF9',
        'chip_type':  'NAND Flash',
        'subtype':    'NAND Flash — K9 series (legado, standalone)',
        'interface':  'NAND (raw)',
        'is_emcp':    False,
        'priority':   70,
        'tip': (
            'Samsung NAND Flash standalone — série K9 (legacy). '
            'KF9 = Samsung, família NAND Flash pré-eMMC. '
            'Densidade: 8G=8Gbit(1GB), 4G=4Gbit(512MB). '
            'Barramento: 16=x16. Sem controladora eMMC. '
            'Era: feature phone / embedded (~2005-2012). '
            '⚠ NÃO É Kingston Fury (que usa KF+DDR com "/" no PN). '
            'Destino: sucata / aplicações industriais específicas.'
        ),
    },
    {
        'brand_name': 'Kingston',
        'prefix':     'KF',
        'chip_type':  'RAM',
        'active':     False,  # Kingston nao faz DRAM avulsa — KF e misread de Samsung (ver memoria)
        'subtype':    'DDR',
        'interface':  'DDR4 / DDR5',
        'is_emcp':    False,
        'priority':   80,
        'tip': (
            'Módulo Kingston Fury (linha gaming). '
            'KF = Kingston Fury. '
            'Ex: KF436C16BB/8 = Fury Black DDR4-3600, CL16, 8GB.'
        ),
    },
    {
        'brand_name': 'Kingston',
        'prefix':     'ACR',
        'chip_type':  'RAM',
        'active':     False,  # marking de modulo Kingston, nao chip avulso — bogus (ver memoria)
        'subtype':    'DDR',
        'interface':  'DDR3 / DDR4',
        'is_emcp':    False,
        'priority':   80,
        'tip': 'Módulo RAM Kingston série Action (mercado OEM/notebook). Prefixo ACR.',
    },
    {
        'brand_name': 'Kingston',
        'prefix':     'EMCP',
        'chip_type':  'eMCP',
        'subtype':    'eMCP (Kingston)',
        'interface':  'eMMC + LPDDR',
        'is_emcp':    True,
        'priority':   50,
        'tip': (
            'eMCP Kingston. Chip combinado eMMC + RAM. '
            'Decode direto: prefixo numérico = capacidade eMMC em GB. '
            'Dígitos após "EMCP" = RAM em Gbit → dividir por 8 para GB. '
            'Ex: 16EMCP08-NL3DTB28 → 16GB eMMC + 08Gb÷8=1GB RAM. '
            'Ex: 04EMCP04-NL2AS100 → 4GB eMMC + 04Gb÷8=512MB RAM. '
            'Destino: bancada eMCP.'
        ),
    },

    # ── SanDisk ───────────────────────────────────────────────────────────────
    # Famílias SanDisk migradas para populate_sandisk.py (2026-05).
    # Rodar: python manage.py populate_sandisk --overwrite
    # A entrada SD7DP abaixo foi removida — populate_sandisk.py é a fonte de verdade.

    # ── Samsung NAND Flash (K9x) ───────────────────────────────────────────────
    # Chips muito comuns em TVs, eletrodomésticos, impressoras e dispositivos IoT.
    # A anatomia Samsung NAND segue: K9[tipo][densidade][barramento][geração][sufixo]
    # Pos 2 = tipo (F=SLC, G=MLC, H=MLC high-density, K=SLC large, L=MLC large, W=SLC 3V)
    # Pos 3 = densidade: 8→1Gb, G→2Gb, H→4Gb, J→8Gb, K→16Gb, L→32Gb, M→64Gb, N→128Gb
    # Pos 4 = largura do barramento: 0=x8 (1 die), 1=x16 (2 die)
    # Ex: K9F2G08U0C = SLC, 2Gb=256MB, x8, 3.3V, geração C

    {
        'brand_name': 'Samsung',
        'prefix':     'K9F',
        'chip_type':  'NAND Flash',
        'subtype':    'SLC NAND',
        'interface':  'NAND (x8/x16)',
        'is_emcp':    False,
        'priority':   50,
        'tip': (
            'NAND Flash Samsung SLC (Single-Level Cell). '
            'Alta durabilidade, comum em TVs, impressoras e equipamentos industriais. '
            'Pos 3 = densidade: 8=1Gb, G=2Gb, H=4Gb, J=8Gb, K=16Gb. '
            'Ex: K9F2G08U0C = 2Gb/256MB SLC x8.'
        ),
    },
    {
        'brand_name': 'Samsung',
        'prefix':     'K9G',
        'chip_type':  'NAND Flash',
        'subtype':    'MLC NAND',
        'interface':  'NAND (x8/x16)',
        'is_emcp':    False,
        'priority':   50,
        'tip': (
            'NAND Flash Samsung MLC (Multi-Level Cell). '
            'Maior densidade que SLC, comum em TVs e set-top boxes. '
            'Ex: K9GAG08U0M = 16Gb/2GB MLC x8.'
        ),
    },
    {
        'brand_name': 'Samsung',
        'prefix':     'K9K',
        'chip_type':  'NAND Flash',
        'subtype':    'SLC NAND (alta densidade)',
        'interface':  'NAND (x8)',
        'is_emcp':    False,
        'priority':   50,
        'tip': (
            'NAND Flash Samsung SLC de alta densidade. '
            'Usado em equipamentos com requisito alto de endurance. '
            'Ex: K9K8G08U0M = 8Gb/1GB SLC.'
        ),
    },
    {
        'brand_name': 'Samsung',
        'prefix':     'K9L',
        'chip_type':  'NAND Flash',
        'subtype':    'MLC NAND (alta densidade)',
        'interface':  'NAND (x8)',
        'is_emcp':    False,
        'priority':   50,
        'tip': 'NAND Flash Samsung MLC de alta densidade (série L). Ex: K9LBG08U0M = 32Gb/4GB.',
    },
    {
        'brand_name': 'Samsung',
        'prefix':     'K9W',
        'chip_type':  'NAND Flash',
        'subtype':    'SLC NAND (3.3V)',
        'interface':  'NAND (x8)',
        'is_emcp':    False,
        'priority':   50,
        'tip': 'NAND Flash Samsung SLC série W, tensão 3.3V. Comum em equipamentos legados.',
    },
    {
        'brand_name': 'Samsung',
        'prefix':     'K9C',
        'chip_type':  'NAND Flash',
        'subtype':    'SLC NAND (1.8V)',
        'interface':  'NAND (x8/x16)',
        'is_emcp':    False,
        'priority':   50,
        'tip': 'NAND Flash Samsung SLC série C, tensão 1.8V. Usado em câmeras e PDAs.',
    },
    {
        'brand_name': 'Samsung',
        'prefix':     'K9HDG',
        'chip_type':  'NAND Flash',
        'subtype':    'MLC NAND (série HD)',
        'interface':  'NAND (x8)',
        'is_emcp':    False,
        'priority':   40,   # prefixo mais longo → maior prioridade
        'tip': (
            'NAND Flash Samsung série HD (alta densidade, MLC). '
            'Ex: K9HDG08U5M-LCB0 = 16GB MLC NAND, pacote LGA. '
            'Usado em TVs Samsung e monitores.'
        ),
    },
    {
        'brand_name': 'Samsung',
        'prefix':     'K9H',
        'chip_type':  'NAND Flash',
        'subtype':    'MLC NAND (série H)',
        'interface':  'NAND (x8)',
        'is_emcp':    False,
        'priority':   50,
        'tip': 'NAND Flash Samsung MLC série H. Comum em TVs e monitores Samsung.',
    },
]


class Command(BaseCommand):
    help = 'Adiciona ChipFamilies básicas para SK Hynix, Micron, KIOXIA, Nanya e Kingston'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true', default=False,
            help='Mostra o que seria criado/atualizado sem salvar'
        )
        parser.add_argument(
            '--overwrite', action='store_true', default=False,
            help='Atualiza registros existentes (por padrão, pula se já existir)'
        )

    def handle(self, *args, **options):
        dry_run  = options['dry_run']
        overwrite = options['overwrite']

        if dry_run:
            self.stdout.write(self.style.WARNING('⚠ DRY RUN — nada será salvo\n'))

        # Pré-carrega brands
        brands = {b.name.lower(): b for b in Brand.objects.all()}

        created = updated = skipped = missing_brand = 0

        for fam in FAMILIES:
            brand_key  = fam['brand_name'].lower()
            brand      = brands.get(brand_key)

            if not brand:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠ Marca '{fam['brand_name']}' não encontrada no banco "
                        f"(família {fam['prefix']}) — crie via admin ou import_chipid"
                    )
                )
                missing_brand += 1
                continue

            exists = ChipFamily.objects.filter(
                brand=brand, prefix=fam['prefix']
            ).first()

            if exists and not overwrite:
                skipped += 1
                continue

            self.stdout.write(
                f"  {'ATUALIZA' if exists else 'CRIA    '} "
                f"{fam['prefix']:14s} ({fam['brand_name']}) — {fam['chip_type']}"
                + (f" / {fam['subtype']}" if fam.get('subtype') else '')
            )

            if not dry_run:
                defaults = {
                    'chip_type':   fam.get('chip_type', ''),
                    'subtype':     fam.get('subtype', ''),
                    'interface':   fam.get('interface', ''),
                    'is_emcp':     fam.get('is_emcp', False),
                    'tip':         fam.get('tip', ''),
                    'priority':    fam.get('priority', 100),
                    'active':      fam.get('active', True),
                    # decode_density_type ('pc'/'mobile'/'micron'): ativa o decode de
                    # densidade/capacidade DRAM no engine. Default '' = sem decode.
                    'decode_density_type': fam.get('decode_density_type', ''),
                }
                if exists:
                    for k, v in defaults.items():
                        setattr(exists, k, v)
                    exists.save()
                    updated += 1
                else:
                    ChipFamily.objects.create(brand=brand, prefix=fam['prefix'], **defaults)
                    created += 1
            else:
                if exists:
                    updated += 1
                else:
                    created += 1

        self.stdout.write('')
        if created:
            self.stdout.write(self.style.SUCCESS(
                f"{'Seriam criadas' if dry_run else 'Criadas'}: {created} famílias"
            ))
        if updated:
            self.stdout.write(self.style.SUCCESS(
                f"{'Seriam atualizadas' if dry_run else 'Atualizadas'}: {updated} famílias"
            ))
        if skipped:
            self.stdout.write(f"Já existiam (puladas): {skipped}")
        if missing_brand:
            self.stdout.write(self.style.WARNING(
                f"Marcas não encontradas: {missing_brand} — rode import_chipid antes"
            ))

        if not dry_run and (created + updated) > 0:
            self.stdout.write(self.style.SUCCESS(
                '\n✅ Famílias adicionadas. '
                'O engine agora reconhece esses prefixos e usa Gemini para decodificar '
                'os detalhes quando não estiverem no banco.\n'
                'Dica: adicione as regras de decode (decode_cap_pos/map) pelo admin '
                'para reduzir chamadas ao Gemini.'
            ))
