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


def is_ram_generation(text: str) -> bool:
    """True se `text` é PURAMENTE um token de geração de RAM (DDR4, LPDDR4X, GDDR5,
    SDRAM…) — nada mais. Usado pelo portão do load_brands (passo 4) para barrar a
    geração no campo `interface` (que deve ser largura de barramento x8/x16 ou vazio).
    'x16' → False; 'DDR4' → True; 'eMMC 5.1' → False; 'DDR4 x16' → False (não é puro)."""
    t = (text or "").strip()
    return bool(t) and bool(_RAM_GEN_RE.fullmatch(t))


# ─────────────────────────────────────────────────────────────────────────
# LARGURA DE BARRAMENTO (bus_width) — vocabulário fechado, FONTE ÚNICA
# ─────────────────────────────────────────────────────────────────────────
# Separada de `interface` em 2026-09 (PLANO_BUS_WIDTH.md): `interface` é VERSÃO
# DE PROTOCOLO (eMMC 5.1, UFS 3.1) e `bus_width` é a LARGURA DO BARRAMENTO DE
# DADOS do dispositivo. Os dois são ortogonais — NAND paralela tem os dois.
#
# ⚠ NINGUÉM escreve esta lista em outro lugar. Constraint do banco, portão
# Pydantic, censo e coletor TODOS importam daqui. É a lição das quatro quebras
# da origem do lote (CLAUDE.md §7): vocabulário fechado tem UM dono.
BUS_WIDTH_VOCAB = ("x4", "x8", "x16", "x32", "x64")

# Classe de largura — o eixo COMERCIAL (o comprador paga por classe, não por
# largura exata): x4/x8 = 'narrow' (78 bolas) · x16 = 'wide' (96 bolas).
# Mora aqui por ora para que o schema do lote (F1) tenha uma fonte única; na
# Parte 2 o `pricing/convention.py` importa daqui em vez de redeclarar.
WIDTH_CLASS_VOCAB = ("", "narrow", "wide")

# De ONDE veio a largura que o resultado mostra. Vale ouro no diagnóstico:
# separa "o datasheet disse" de "a gramática deduziu" — e é o que impede a
# circularidade do coletor de passar despercebida.
BUS_WIDTH_SOURCE_VOCAB = ("", "banco", "familia", "gramatica", "revisao")

_BUS_WIDTH_RE = re.compile(r"x(4|8|16|32|64)", re.I)


def width_class_of(bus_width: str) -> str:
    """Classe COMERCIAL da largura: x4/x8 → 'narrow' (78 bolas) · x16 → 'wide'
    (96 bolas) · resto (x32/x64/vazio/lixo) → '' (desconhecida/não se aplica).

    O comprador paga por CLASSE, não por largura exata: ele conta as bolas do
    encapsulamento e não lê part number. x32/x64 devolvem '' porque não existem
    no mercado deste catálogo em DDR discreta (GDDR é sucata por tipo, LPDDR tem
    kind próprio) — dar classe a eles seria inventar mercado.

    ⚠ '' significa DESCONHECIDA no lote, distinto de 'wide'. Na Parte 2 o eixo do
    preço/caixa usa outro vocabulário, mais estreito, porque lá '' quer dizer
    "o que sempre foi" (código de caixa é eterno) — são dois vocabulários de
    propósito.
    """
    bw = (bus_width or "").strip().lower()
    if bw in ("x4", "x8"):
        return "narrow"
    if bw == "x16":
        return "wide"
    return ""


def is_bus_width(text: str) -> bool:
    """True se `text` é PURAMENTE um token de largura de barramento.

    `fullmatch` contra lista fechada, nunca `search` — é a regra que este
    projeto pagou três vezes para aprender (CLAUDE.md §7): para DECIDIR se uma
    string é um token de vocabulário, `fullmatch`; `search` só serve para
    EXTRAIR de string já validada. 'x8' → True · 'x8 @ 800MHz' → False ·
    'x2' → False · 'DDR4' → False.

    Tolerante a caixa e espaço na LEITURA ('  X8 ' → True) porque a regra 5 do
    `apply_kp_convention` normaliza para 'x8' antes de gravar; o banco só
    aceita a forma canônica (CheckConstraint).
    """
    t = (text or "").strip()
    return bool(t) and bool(_BUS_WIDTH_RE.fullmatch(t))


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
