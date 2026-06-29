"""
chips/chip_types.py
===================
FONTE ÚNICA da convenção de tipos de chip (WhatTheChip).

Declara, para CADA tipo canônico de `chip_type`, tudo que os consumidores
precisam saber — em UM lugar só. Consumidores que leem daqui:

  • estoque/views.py::_compute_destination  → `label_kind` decide o formato do label
  • chips/engine.py::assess_profitability    → `profit_family` decide o branch de rentab.
  • management/commands/validate_convention   → vocabulário fechado + flags
  • management/commands/populate_*/normalize_ → forma canônica no write-time

Adicionar um tipo novo (CPU, DDR6, UFS 4.x, …) = adicionar UMA entrada em
`CHIP_TYPES`. É a propriedade de escala: o vocabulário é declarado uma vez,
validado no write-time e lido em todo lugar do mesmo sítio.

Convenção (decisão "opção 1", 2026-06-29):
  • DRAM discreta (DDR/LPDDR/GDDR/SDRAM/RDRAM): a GERAÇÃO mora no `chip_type`
    (`DDR3`, `LPDDR4X`, `GDDR5`), espelhada no `subtype`. Sobrevive à linha salva
    do estoque e ao Excel (que persistem `chip_type`, não `subtype`).
  • Memória gerenciada (eMMC/UFS/eMCP/uMCP/NAND): `chip_type` como hoje; `subtype`
    limpo (geração LPDDR p/ eMCP/uMCP; célula p/ NAND; vazio p/ eMMC/UFS).
  • Unidade inviolável: die em `Gb`, pacote em `GB`. 1 GB = 8 Gb.

PURA (sem Django): só depende de `re` (via conventions). Reutilizável no engine,
no gateway, nos comandos e nos testes unitários (SimpleTestCase).
"""

import re

from dataclasses import dataclass, field

from .conventions import canonical_gen


@dataclass(frozen=True)
class ChipTypeSpec:
    """Espec de um `chip_type` canônico — o contrato que todos os consumidores leem."""
    category: str            # managed_nand | managed_mcp | nand_raw | dram_pc |
                             # dram_mobile | dram_gpu | dram_legacy | catalog
    label_kind: str          # emmc|ufs|emcp|umcp|nand|ddr|lpddr|gddr|sdram|rdram|none
    profit_family: str       # emcp|emmc|ufs|ddr|lpddr|gddr|dead|indeterminado
    commercial: bool = True          # tem caixa física / é roteado no estoque?
    carries_generation: bool = False # o próprio chip_type É a geração (DRAM discreta)?
    is_emcp: bool = False            # composto NAND+RAM (eMCP/uMCP)?
    generic: bool = False            # token genérico transicional (validador sinaliza)?
    aliases: tuple = field(default_factory=tuple)  # formas cruas que normalizam p/ cá


# ─────────────────────────────────────────────────────────────────────────────
# O REGISTRO — vocabulário fechado. Chave = token canônico de chip_type.
# ─────────────────────────────────────────────────────────────────────────────
CHIP_TYPES: dict[str, ChipTypeSpec] = {
    # ── Memória gerenciada — geração NÃO vai no chip_type ────────────────────
    "eMMC": ChipTypeSpec("managed_nand", "emmc", "emmc", aliases=("emmc",)),
    "UFS":  ChipTypeSpec("managed_nand", "ufs",  "ufs",  aliases=("ufs",)),
    "eMCP": ChipTypeSpec("managed_mcp",  "emcp", "emcp", is_emcp=True, aliases=("emcp",)),
    "uMCP": ChipTypeSpec("managed_mcp",  "umcp", "emcp", is_emcp=True, aliases=("umcp",)),
    "NAND Flash": ChipTypeSpec("nand_raw", "nand", "dead", aliases=("nand flash", "nand")),

    # ── DRAM de PC (die em Gb) — geração no chip_type + espelho no subtype ────
    "DDR1":  ChipTypeSpec("dram_pc", "ddr", "ddr", carries_generation=True),
    "DDR2":  ChipTypeSpec("dram_pc", "ddr", "ddr", carries_generation=True),
    "DDR3":  ChipTypeSpec("dram_pc", "ddr", "ddr", carries_generation=True),
    "DDR3L": ChipTypeSpec("dram_pc", "ddr", "ddr", carries_generation=True),
    "DDR4":  ChipTypeSpec("dram_pc", "ddr", "ddr", carries_generation=True),
    "DDR5":  ChipTypeSpec("dram_pc", "ddr", "ddr", carries_generation=True),

    # ── DRAM móvel (pacote em GB) ────────────────────────────────────────────
    "LPDDR1":  ChipTypeSpec("dram_mobile", "lpddr", "lpddr", carries_generation=True),
    "LPDDR2":  ChipTypeSpec("dram_mobile", "lpddr", "lpddr", carries_generation=True),
    "LPDDR3":  ChipTypeSpec("dram_mobile", "lpddr", "lpddr", carries_generation=True),
    "LPDDR4":  ChipTypeSpec("dram_mobile", "lpddr", "lpddr", carries_generation=True),
    "LPDDR4X": ChipTypeSpec("dram_mobile", "lpddr", "lpddr", carries_generation=True),
    "LPDDR5":  ChipTypeSpec("dram_mobile", "lpddr", "lpddr", carries_generation=True),
    "LPDDR5X": ChipTypeSpec("dram_mobile", "lpddr", "lpddr", carries_generation=True),

    # ── DRAM de GPU (die em Gb) ──────────────────────────────────────────────
    "GDDR2":  ChipTypeSpec("dram_gpu", "gddr", "gddr", carries_generation=True),
    "GDDR3":  ChipTypeSpec("dram_gpu", "gddr", "gddr", carries_generation=True),
    "GDDR4":  ChipTypeSpec("dram_gpu", "gddr", "gddr", carries_generation=True),
    "GDDR5":  ChipTypeSpec("dram_gpu", "gddr", "gddr", carries_generation=True),
    "GDDR6":  ChipTypeSpec("dram_gpu", "gddr", "gddr", carries_generation=True),
    "GDDR6X": ChipTypeSpec("dram_gpu", "gddr", "gddr", carries_generation=True),

    # ── DRAM legada — sucata por tipo (decisão 2026-06-29: anterior ao DDR1) ──
    "SDRAM":    ChipTypeSpec("dram_legacy", "sdram", "dead", aliases=("sdr sdram", "sdr")),
    "RDRAM":    ChipTypeSpec("dram_legacy", "rdram", "dead", commercial=False, aliases=("rambus",)),
    "EDO DRAM": ChipTypeSpec("dram_legacy", "none",  "dead", commercial=False, aliases=("edo",)),

    # ── Catálogo — sem caixa comercial; classificação/documentação ───────────
    "NOR Flash": ChipTypeSpec("catalog", "none", "dead", commercial=False, aliases=("nor flash", "nor", "spi nor")),
    "OneNAND":   ChipTypeSpec("catalog", "none", "indeterminado", commercial=False),
    "MCP":       ChipTypeSpec("catalog", "none", "dead", commercial=False),
    "ePoP":      ChipTypeSpec("catalog", "none", "dead", commercial=False, aliases=("epop", "e-pop")),
    "SoC":       ChipTypeSpec("catalog", "none", "indeterminado", commercial=False),
    "PMIC":      ChipTypeSpec("catalog", "none", "indeterminado", commercial=False),
    "Sensor":    ChipTypeSpec("catalog", "none", "indeterminado", commercial=False, aliases=("isocell",)),
    "SRAM":      ChipTypeSpec("catalog", "none", "indeterminado", commercial=False),
    "Mask ROM":  ChipTypeSpec("catalog", "none", "indeterminado", commercial=False),
    "NVMe SSD":  ChipTypeSpec("catalog", "none", "indeterminado", commercial=False, aliases=("nvme ssd", "nvme")),
    "BGA SSD":   ChipTypeSpec("catalog", "none", "indeterminado", commercial=False, aliases=("bga ssd",)),

    # ── Genéricos transicionais — VÁLIDOS mas o validador SINALIZA ───────────
    # Só para famílias genuinamente multi-geração (Samsung K3, SanDisk SDEM) até a
    # confirmação por PN. Meta: zero no fim, exceto ambíguos. canonical_chip_type
    # tenta resolvê-los para uma geração específica antes de cair aqui.
    "DDR":   ChipTypeSpec("dram_pc",      "ddr",   "ddr",           carries_generation=True, generic=True),
    "LPDDR": ChipTypeSpec("dram_mobile",  "lpddr", "lpddr",         carries_generation=True, generic=True),
    "GDDR":  ChipTypeSpec("dram_gpu",     "gddr",  "gddr",          carries_generation=True, generic=True),
    "RAM":   ChipTypeSpec("dram_unknown", "none",  "indeterminado", generic=True),
    "DRAM":  ChipTypeSpec("dram_unknown", "none",  "indeterminado", generic=True),
}


# ── Índices derivados (construídos uma vez) ──────────────────────────────────
# alias minúsculo  →  token canônico. Inclui o próprio token em minúsculas.
_ALIAS_INDEX: dict[str, str] = {}
for _tok, _spec in CHIP_TYPES.items():
    _ALIAS_INDEX[_tok.lower()] = _tok
    for _a in _spec.aliases:
        _ALIAS_INDEX[_a.lower()] = _tok

CANONICAL_TYPES = frozenset(t for t, s in CHIP_TYPES.items() if not s.generic)
GENERIC_TYPES   = frozenset(t for t, s in CHIP_TYPES.items() if s.generic)
DEAD_TYPES      = frozenset(t for t, s in CHIP_TYPES.items() if s.profit_family == "dead")
COMMERCIAL_TYPES = frozenset(t for t, s in CHIP_TYPES.items() if s.commercial)


# ── API pública ──────────────────────────────────────────────────────────────

def spec_for(chip_type: str) -> ChipTypeSpec | None:
    """Espec do token canônico (ou None). Aceita variações de caixa/alias."""
    if not chip_type:
        return None
    if chip_type in CHIP_TYPES:
        return CHIP_TYPES[chip_type]
    tok = _ALIAS_INDEX.get(chip_type.strip().lower())
    return CHIP_TYPES.get(tok) if tok else None


# Categorias NÃO-DRAM onde o chip_type MANDA: gerenciada (subtype=geração LPDDR),
# NAND (subtype=célula) e catálogo (subtype é DESCRITIVO — ex.: NOR Flash com
# subtype "Raw MCP — NAND 512MB + mDDR1 256MB", onde "mDDR1" NÃO é o tipo). Só para
# DRAM (pc/mobile/gpu/legacy/unknown) a geração do subtype vence, corrigindo um
# chip_type errado (ex.: RDRAM+DDR5 → DDR5).
_TYPE_WINS_CATS = frozenset({"managed_nand", "managed_mcp", "nand_raw", "catalog"})

# Família "nua" (sem número): LPDDR/GDDR antes de DDR (senão "DDR" casa em "GDDR").
_BARE_FAMILY_RE = re.compile(r"(LPDDR|GDDR|DDR)", re.I)
_BARE_FAMILY = {"lpddr": "LPDDR", "gddr": "GDDR", "ddr": "DDR"}


def _token_of(ct: str) -> str:
    """Token canônico para um ct que já se sabe ter spec (direto ou alias)."""
    return ct if ct in CHIP_TYPES else _ALIAS_INDEX.get(ct.lower(), ct)


def _bare_family(text: str) -> str:
    """Token genérico de família p/ texto com DDR/LPDDR/GDDR sem número."""
    m = _BARE_FAMILY_RE.search(text or "")
    return _BARE_FAMILY[m.group(1).lower()] if m else ""


def canonical_chip_type(raw_chip_type: str, subtype: str = "") -> str:
    """
    Normaliza qualquer `chip_type` cru ao token canônico da convenção.

    Ordem (preserva o comportamento histórico do despacho por substring):
      1. Gerenciada / NAND (eMCP/uMCP/eMMC/UFS/NAND): o chip_type MANDA — o subtype
         carrega a geração LPDDR ou a célula, não o tipo.
      2. DRAM: a GERAÇÃO específica do subtype (depois do chip_type) vence — resolve
         conflito como chip_type="RDRAM" + subtype="DDR5" → "DDR5" (subtype é o sinal
         mais confiável; o validador sinaliza a inconsistência p/ correção).
         Ex.: ("RAM","DDR3 SDRAM")→"DDR3"; ("LPDDR","LPDDR4X Mobile")→"LPDDR4X".
      3. chip_type canônico específico direto (ex.: "SDRAM"/"RDRAM" sem conflito).
      4. Família "nua" no texto (DDR/LPDDR/GDDR sem número) → token genérico
         sinalizado — ex.: ("RAM","DDR — módulo")→"DDR" (preserva DDR-sem-número
         como família DDR, que a rentabilidade trata como DDR1).
      5. Alias/caixa (genérico como último recurso) e fail-open.

    NÃO altera specs nem rentabilidade — só resolve o token do tipo.
    """
    ct = (raw_chip_type or "").strip()
    if not ct:
        return ""

    spec = spec_for(ct)

    # 1. gerenciada / NAND — o chip_type manda
    if spec and not spec.generic and spec.category in _TYPE_WINS_CATS:
        return _token_of(ct)

    # 2. geração específica via subtype, depois chip_type
    for src in (subtype, raw_chip_type):
        g = canonical_gen(src or "", raw_chip_type)
        if not g:
            continue
        gt = g if g in CHIP_TYPES else _ALIAS_INDEX.get(g.lower())
        if gt and not CHIP_TYPES[gt].generic:
            return gt

    # 3. chip_type canônico específico direto
    if spec and not spec.generic:
        return _token_of(ct)

    # 4. família "nua" (DDR/LPDDR/GDDR sem número) no texto
    fam = _bare_family(f"{subtype} {ct}")
    if fam:
        return fam

    # 5. alias / genérico / fail-open
    return _ALIAS_INDEX.get(ct.lower(), ct)


def profit_family(chip_type: str) -> str:
    """Família de rentabilidade do tipo (default 'indeterminado')."""
    s = spec_for(chip_type)
    return s.profit_family if s else "indeterminado"


def label_kind(chip_type: str) -> str:
    """Formatador de label da caixa para o tipo (default 'none')."""
    s = spec_for(chip_type)
    return s.label_kind if s else "none"


def generation_of(chip_type: str, subtype: str = "") -> str:
    """
    Token de GERAÇÃO canônico para o label (ex.: "DDR3", "LPDDR4X") quando a geração
    mora no chip_type — ou "" se o tipo for genérico/sem geração/gerenciado.

    Usado como fallback no gateway: `canonical_gen(subtype) or generation_of(...)`,
    para a geração sobreviver ao label mesmo se o subtype esvaziar (req. #1), SEM
    poluir genéricos ("RAM"→"") nem gerenciados ("eMMC"→"").
    """
    canon = canonical_chip_type(chip_type, subtype)
    s = CHIP_TYPES.get(canon)
    return canon if (s and s.carries_generation and not s.generic) else ""


def is_commercial(chip_type: str) -> bool:
    """True se o tipo tem caixa física / é roteado no estoque."""
    s = spec_for(chip_type)
    return bool(s and s.commercial)


def is_generic(chip_type: str) -> bool:
    """True se é um token genérico transicional (geração ausente)."""
    s = spec_for(chip_type)
    return bool(s and s.generic)


def is_known(chip_type: str) -> bool:
    """True se o tipo (ou um alias) está no vocabulário fechado."""
    return spec_for(chip_type) is not None


def is_dead(chip_type: str) -> bool:
    """True se o tipo é sempre NÃO RENTÁVEL por tipo (sucata)."""
    return profit_family(chip_type) == "dead"
