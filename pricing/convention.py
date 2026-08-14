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
                         ⚠ eMCP/uMCP: SÓ pelo NAND — sem geração de RAM na
                         chave ("unified by cap", planilha v9 do comprador;
                         dono, 2026-07-24).
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
    # SSD BGA/NVMe (dono 2026-07-24 — comprador paga LINEAR ¥/GB). A letra G
    # deixa de ser livre; próximo tipo novo pega I (H/R reservadas).
    'ssd':   'G',
    # K9 — NAND cru TSOP (dono 2026-08-14, HANDOFF_K9): preço FIXO ¥/unidade.
    # ⚠ DESVIO CONSCIENTE da regra "próxima letra livre" (seria I): o dono
    # escolheu K, mnemônica do nome de mercado — aqui não há conhecimento de
    # decode a proteger (o K9 é triado por FORMATO, sem PN; o próprio termo é
    # o rótulo da tela). I e J seguem livres para os próximos tipos.
    'k9':    'K',
}

RESERVED_LETTERS = frozenset({'H', 'R'})   # baldes especiais — nunca categoria
HOLD_LABEL   = 'H-00'                      # fila de conferência / sem categoria
REFINE_LABEL = 'R-00'                      # reprovado → refino

# ── TABELA FUNDADORA v1 da convenção (congelada 2026-07-23) ──────────────────
# (kind, gen, tier_value, tier_unit, code) — 55 categorias vendáveis do grid
# na fundação, números embaralhados na autoria e ETERNOS. Unidades: GB=pacote,
# Gb=die (case-sensitive, regra da casa).
FOUNDING_TABLE = (
    # A — eMCP (v3.1, dono 2026-07-24: SÓ pelo NAND — gen vazio; "unified
    #     by cap" da planilha v9. A renumerou pré-deploy; fundação anterior
    #     por geração foi substituída ANTES de qualquer caixa física.)
    ('emcp', '', '16',  'GB', 1),
    ('emcp', '', '64',  'GB', 2),
    ('emcp', '', '256', 'GB', 3),
    ('emcp', '', '8',   'GB', 4),
    ('emcp', '', '128', 'GB', 5),
    ('emcp', '', '32',  'GB', 6),
    # B — eMMC
    ('emmc', '', '8',    'GB', 1),
    ('emmc', '', '128',  'GB', 2),
    ('emmc', '', '32',   'GB', 3),
    ('emmc', '', '256',  'GB', 4),
    ('emmc', '', '4',    'GB', 5),
    ('emmc', '', '16',   'GB', 6),
    ('emmc', '', '64',   'GB', 7),
    # C — uMCP (v3.1: SÓ pelo NAND — gen vazio; renumerou pré-deploy)
    ('umcp', '', '128', 'GB', 1),
    ('umcp', '', '512', 'GB', 2),
    ('umcp', '', '64',  'GB', 3),
    ('umcp', '', '256', 'GB', 4),
    # D — UFS
    ('ufs', '', '64',   'GB', 1),
    ('ufs', '', '256',  'GB', 2),
    ('ufs', '', '1024', 'GB', 3),
    ('ufs', '', '32',   'GB', 4),
    ('ufs', '', '512',  'GB', 5),
    ('ufs', '', '128',  'GB', 6),   # caiu na transcrição da fundação; anexada
                                    # 2026-07-23 (regra de append: nº novo, nada renumera)
    ('ufs', '', '16',   'GB', 7),   # anexada 2026-07-24 — lastro: THGAF9G7L1LBAB7
                                    # (Kioxia, confirmed) + caixa física antiga
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
    ('ddr', 'DDR4', '2',  'Gb', 12),   # planilha v9 (2026-07-24; rentável ≥1Gb)
    ('ddr', 'DDR4', '1',  'Gb', 13),   # ⚠ suspeita (JEDEC DDR4 mínimo = 2Gb);
                                       # aposentar se o estoque confirmar zero
    ('ddr', 'DDR3', '1',  'Gb', 14),   # anexada 2026-07-24 — dono: "DDR3 é
                                       # rentável sim"; lastro: 173 registros
                                       # (H5TQ1G/K4B1G…). Requer ddr3_min_gbit
                                       # = 1.0 no admin (config, não código).
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
    ('lpddr', 'LPDDR4', '1.5', 'GB', 18),  # anexada 2026-07-24 — chips reais
                                           # (MT53B384M32/192M64 = 12Gb = 1.5GB;
                                           # OV do LOT/043 expôs a lacuna)
    ('lpddr', 'LPDDR3', '1.5', 'GB', 19),  # AUTO-CUNHADA na bancada de PROD
                                           # 2026-07-24 (K4E2E304EA, LPDDR3
                                           # 1.5GB) — registrada aqui a posteriori,
                                           # como manda a regra do append
    # G — SSD BGA/NVMe (2026-07-24): capacidades REAIS descobertas no estoque;
    #     novas capacidades anexam na aprovação (preço é linear ¥/GB — a caixa
    #     separa por capacidade como todo o resto).
    ('ssd', '', '440', 'GB', 1),
    ('ssd', '', '220', 'GB', 2),
    # K — K9 NAND cru TSOP (anexada 2026-08-14, HANDOFF_K9): categoria ÚNICA
    #     e plana — sem geração, sem capacidade; o tier é "1 unidade"
    #     (tier_unit vazio de propósito: GB/Gb não se aplicam). K-01 é a
    #     caixa física inteira do tipo; jamais haverá K-02 por capacidade
    #     (premissa registrada — se o negócio mudar, o tipo é remodelado).
    ('k9', '', '1', '', 1),
)
