"""
pricing/convention.py — A CONVENÇÃO UNIVERSAL DE CAIXAS (dono, 2026-07-23).

Este arquivo é a FONTE da convenção mundial de códigos de categoria do
WhatTheChip: **fixa, global e eterna** — a mesma tabela em todo deploy, todo
cliente, todo país. É dado PURO (zero import de Django) — modelos, seed e
views leem daqui.

Gramática da convenção (INVIOLÁVEL):

    LETRA-## (## ≥ 01) = categoria comercial — deriva do CHIP (tipo + geração
                         + faixa de capacidade, o que o decoder busca no
                         banco). Existe COM ou SEM preço no grid: "preço até
                         pode ficar sem, categoria não" (dono, 2026-07-23).
    H-00 · HOLD        = fila de conferência — NÃO embarca; aguarda o gestor.
                         (Também exibida p/ aprovado raro SEM categoria
                         derivável: dado incompleto → separar p/ análise.)
    R-00 · REFINO      = reprovado na triagem — sai do comercial, refino.

Regras eternas:
  • Letra é FIXA por tipo (KIND_LETTER) — nunca muda, nunca se reusa.
  • Número é CONGELADO — nunca reordena, nunca se reutiliza; categoria nova
    ganha o PRÓXIMO número livre da letra (append-only). O número NÃO é
    ranking: a tabela fundadora foi embaralhada UMA vez na autoria, de
    propósito (número ordenado por capacidade vazaria a escadinha que a
    máscara F12 esconde).
  • ``00`` é reservado em TODA letra (nunca é categoria).
  • Letras H e R são RESERVADAS (baldes especiais). Tipo novo de chip pega a
    próxima letra livre (G, I, J…).
  • Variantes de tensão/velocidade (L, U, X) SEMPRE dobram na geração-base
    (fold_gen) — inclusive dentro dos combos eMCP/uMCP (dono, 2026-07-23).
  • O código NUNCA traduz (canônico universal, IBM Plex Mono nas telas).

⚠ A TABELA FUNDADORA abaixo é imutável: NÃO edite linhas existentes — só
ANEXE categoria nova (com o próximo número da letra) quando o dono a
oficializar. O seed (`seed_category_codes`) carrega exatamente isto, sem
nenhuma aleatoriedade; o banco de produção é o espelho vivo (categoria nova
nasce no banco via ``CategoryCode.label_for_key`` e deve ser anexada aqui na
sequência, como registro da convenção).
"""

# ── Letra fixa por tipo (definida pelo dono, 2026-07-23 — anti-mnemônica de
#    propósito: D≠DDR, E≠eMMC; o cliente não lê o tipo na letra) ─────────────
KIND_LETTER = {
    'emcp':  'A',
    'emmc':  'B',
    'umcp':  'C',
    'ufs':   'D',
    'ddr':   'E',
    'lpddr': 'F',
}

RESERVED_LETTERS = frozenset({'H', 'R'})   # baldes especiais — nunca categoria
HOLD_LABEL   = 'H-00'                      # fila de conferência / sem categoria
REFINE_LABEL = 'R-00'                      # reprovado → refino

# ── TABELA FUNDADORA v1 da convenção (congelada 2026-07-23) ──────────────────
# (kind, gen, tier_value, tier_unit, code) — 55 categorias vendáveis do grid
# na fundação, números embaralhados na autoria e ETERNOS. Unidades: GB=pacote,
# Gb=die (case-sensitive, regra da casa).
FOUNDING_TABLE = (
    # A — eMCP (gen = geração da RAM, X dobrado; tier = NAND GB)
    ('emcp', 'LPDDR4', '32',   'GB', 1),
    ('emcp', 'LPDDR3', '16',   'GB', 2),
    ('emcp', 'LPDDR3', '64',   'GB', 3),
    ('emcp', 'LPDDR4', '128',  'GB', 4),
    ('emcp', 'LPDDR3', '8',    'GB', 5),
    ('emcp', 'LPDDR4', '64',   'GB', 6),
    ('emcp', 'LPDDR3', '32',   'GB', 7),
    ('emcp', 'LPDDR4', '16',   'GB', 8),
    # B — eMMC
    ('emmc', '', '8',    'GB', 1),
    ('emmc', '', '128',  'GB', 2),
    ('emmc', '', '32',   'GB', 3),
    ('emmc', '', '256',  'GB', 4),
    ('emmc', '', '4',    'GB', 5),
    ('emmc', '', '16',   'GB', 6),
    ('emmc', '', '64',   'GB', 7),
    # C — uMCP (gen = geração da RAM, X dobrado; tier = NAND GB)
    ('umcp', 'LPDDR4', '128', 'GB', 1),
    ('umcp', 'LPDDR5', '128', 'GB', 2),
    ('umcp', 'LPDDR5', '512', 'GB', 3),
    ('umcp', 'LPDDR4', '64',  'GB', 4),
    ('umcp', 'LPDDR5', '256', 'GB', 5),
    ('umcp', 'LPDDR4', '256', 'GB', 6),
    # D — UFS
    ('ufs', '', '64',   'GB', 1),
    ('ufs', '', '256',  'GB', 2),
    ('ufs', '', '1024', 'GB', 3),
    ('ufs', '', '32',   'GB', 4),
    ('ufs', '', '512',  'GB', 5),
    ('ufs', '', '128',  'GB', 6),   # caiu na transcrição da fundação; anexada
                                    # 2026-07-23 (regra de append: nº novo, nada renumera)
    # E — DDR (tier em Gb/die; variantes L/U dobradas)
    ('ddr', 'DDR4', '4',  'Gb', 1),
    ('ddr', 'DDR5', '16', 'Gb', 2),
    ('ddr', 'DDR3', '4',  'Gb', 3),
    ('ddr', 'DDR4', '32', 'Gb', 4),
    ('ddr', 'DDR5', '32', 'Gb', 5),
    ('ddr', 'DDR4', '8',  'Gb', 6),
    ('ddr', 'DDR5', '24', 'Gb', 7),
    ('ddr', 'DDR3', '2',  'Gb', 8),
    ('ddr', 'DDR4', '64', 'Gb', 9),
    ('ddr', 'DDR3', '8',  'Gb', 10),
    ('ddr', 'DDR4', '16', 'Gb', 11),
    # F — LPDDR avulso (X dobrado; tier = pacote GB)
    ('lpddr', 'LPDDR4', '6',  'GB', 1),
    ('lpddr', 'LPDDR3', '4',  'GB', 2),
    ('lpddr', 'LPDDR4', '16', 'GB', 3),
    ('lpddr', 'LPDDR4', '3',  'GB', 4),
    ('lpddr', 'LPDDR3', '2',  'GB', 5),
    ('lpddr', 'LPDDR5', '6',  'GB', 6),
    ('lpddr', 'LPDDR4', '12', 'GB', 7),
    ('lpddr', 'LPDDR5', '16', 'GB', 8),
    ('lpddr', 'LPDDR4', '1',  'GB', 9),
    ('lpddr', 'LPDDR5', '8',  'GB', 10),
    ('lpddr', 'LPDDR4', '4',  'GB', 11),
    ('lpddr', 'LPDDR3', '1',  'GB', 12),
    ('lpddr', 'LPDDR5', '12', 'GB', 13),
    ('lpddr', 'LPDDR4', '8',  'GB', 14),
    ('lpddr', 'LPDDR3', '3',  'GB', 15),
    ('lpddr', 'LPDDR5', '4',  'GB', 16),
    ('lpddr', 'LPDDR4', '2',  'GB', 17),
)
