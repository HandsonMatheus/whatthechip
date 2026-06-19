"""
chips/conventions.py
=====================
Convenção de EXIBIÇÃO de campos — FONTE ÚNICA.

`subtype` em WhatTheChip serve a dois papéis: (a) dado real em alguns fluxos
(ex.: a geração de RAM de um eMCP que o engine extrai) e (b) token de exibição
impresso no label da caixa física pelo gateway de estoque.

A regra de negócio (CLAUDE.md §6; SAMSUNG.md / MICRON.md / SK_HYNIX.md §2) diz que
o label só pode conter a GERAÇÃO/CÉLULA — `"LPDDR4"`, `"DDR3L"`, `"SLC NAND"` — e
nunca qualificadores verbosos (`"Mobile"`, `"Multi-Channel"`, `"PC DRAM"`,
`"paralela industrial"`), densidade (`"8Gb"`), barramento (`"x16"`), tensão
(`"1.35V"`) ou capacidade (`"8GB"`). Qualquer ruído além da geração vaza para a
etiqueta e trunca o display na esteira.

Historicamente isso era "consertado" reescrevendo o dado no banco (dezenas de
entradas em fix_known_parts.py, por-marca, por-PN). Isso não escala e não cobre a
gramática: `_result_from_family` (engine) copia `ChipFamily.subtype` LITERALMENTE
para toda a cauda longa de PNs não confirmados.

`canonical_gen` resolve no PONTO DE CONSUMO: reduz qualquer subtype ao seu token
canônico por WHITELIST (extrai o que É geração; descarta o resto). Whitelist é
melhor que blacklist — ruído novo cai fora sozinho, sem precisar enumerá-lo.

É PURA (sem dependência de Django) de propósito, para ser reusável no gateway de
estoque, no engine e, se desejado, no write-time dos importers. NÃO altera
classificação nem rentabilidade: `assess_profitability` casa por substring e
tolera subtype verboso — o label é o único consumidor que quebra com ele.
"""

import re

# Tokens de geração de RAM, do MAIS específico para o menos específico.
# A ordem das alternativas importa: LPDDR e GDDR vêm ANTES de DDR, senão o "DDR"
# casaria dentro de "LPDDR4" / "GDDR5". `DDR\d+L?` captura o sufixo "L" (DDR3L);
# o `X?` opcional captura LPDDR4X / LPDDR5X / GDDR6X.
_RAM_GEN_RE = re.compile(
    r"(LPDDR\d+X?|GDDR\d+X?|DDR\d+L?|SDRAM|RDRAM)",
    re.I,
)

# Célula NAND: "SLC/MLC/TLC/QLC NAND". "NAND" sozinho fica como fallback.
_NAND_CELL_RE = re.compile(r"(SLC|MLC|TLC|QLC)\s*NAND", re.I)


def canonical_gen(subtype: str, chip_type: str = "") -> str:
    """
    Reduz `subtype` ao token canônico de geração/célula para o label da caixa.

    Exemplos:
        canonical_gen("LPDDR4 Mobile")                 -> "LPDDR4"
        canonical_gen("LPDDR4X Multi-Channel")         -> "LPDDR4X"
        canonical_gen("LPDDR5 8GB")                    -> "LPDDR5"
        canonical_gen("DDR3 SDRAM")                    -> "DDR3"
        canonical_gen("DDR3L 1.35V")                   -> "DDR3L"
        canonical_gen("GDDR3 Graphics")                -> "GDDR3"
        canonical_gen("SDRAM")                         -> "SDRAM"
        canonical_gen("SLC NAND paralela industrial",
                      "NAND Flash")                    -> "SLC NAND"
        canonical_gen("")                              -> ""

    Fail-open: subtype sem nenhum token reconhecido volta trimmado — nunca apaga
    o label de um tipo genuinamente desconhecido. NÃO altera specs; só o texto
    exibido na etiqueta.
    """
    s = (subtype or "").strip()
    if not s:
        return ""

    ct = (chip_type or "").lower()

    # NAND: a célula (SLC/MLC/TLC/QLC) tem prioridade quando o tipo é NAND.
    if "nand" in ct or _NAND_CELL_RE.search(s):
        m = _NAND_CELL_RE.search(s)
        if m:
            return f"{m.group(1).upper()} NAND"
        if "nand" in ct:
            return s  # "NAND" sem célula reconhecida — devolve como está.

    m = _RAM_GEN_RE.search(s)
    if m:
        return m.group(1).upper()

    # Nada reconhecido → original trimmado (fail-open).
    return s
