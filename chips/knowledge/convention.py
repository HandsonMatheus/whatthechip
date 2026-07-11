"""
chips/knowledge/convention.py
=============================
FONTE ÚNICA da normalização de convenção de um `known_part`, compartilhada pelo
**portão Pydantic** (`schema.py::KnownPartSpec`) e pelo **modelo** (`KnownPart.clean()`).

Antes (Opção 2), a convenção só era aplicada no caminho do YAML (`load_brands`). Agora
o MESMO normalizador roda no `clean()` do modelo → **todo** caminho de escrita (admin,
bless_base, imports, enrich, restore, API) grava dado convention-clean, não só o yaml.

É **determinístico e não levanta exceção** (só normaliza). A REJEIÇÃO de valor fora do
vocabulário (confidence) e as regras de autoria (proveniência, four-eyes) vivem em quem
chama — `clean()` do modelo e o boundary de submissão —, não aqui.
"""
from __future__ import annotations

import re

# Vocabulário de confiança (CLAUDE.md §8). Só confirmed/manual vencem a gramática.
CONFIDENCE_VOCAB = {"confirmed", "manual", "distributor", "estimated"}

_NONE_STRINGS = {"None", "none", "NONE"}
_CLEAN_FIELDS = ("capacity", "emcp_ram", "emcp_nand", "density_gbit", "density_gb", "interface")

#: Densidade "pelada" em Gigabit: '2G' (convenção da caixa/bless_base) ou '2Gb'.
#: Case-sensitive de propósito — 'GB' é BYTE de pacote, NUNCA densidade (Gb≠GB).
#: Compartilhada com o pricing (fallback de leitura) e o normalize_convention.
RX_DENSITY_BARE = re.compile(r"^(\d+(?:\.\d+)?)\s*G(?:b)?$")

#: Bytes POR DIE ('256MB' — como as famílias DDR sem decode de densidade
#: gravam o capacity). Gb = MB × 8 ÷ 1024. Compartilhado engine + pricing.
RX_DIE_MB = re.compile(r"^(\d+(?:\.\d+)?)\s*MB$")

#: kinds cuja capacidade comercial é DENSIDADE de die em Gb (CLAUDE.md §6:
#: campo `density_gbit`) — DDR/GDDR/SDRAM/RDRAM. Consumido também pelo
#: validate/normalize_convention.
DENSITY_KINDS = ("ddr", "gddr", "sdram", "rdram")


def apply_kp_convention(obj):
    """Normaliza IN-PLACE os campos de convenção de um known_part à forma canônica
    (usa as MESMAS funções do engine: `chip_types.py`/`conventions.py`). Funciona para
    o Pydantic (`KnownPartSpec`) e para o modelo (`KnownPart`) — ambos têm get/setattr.

    1. valores 'None' string (lixo de importador) → '' (o engine já os ignora);
    2. `subtype` → token canônico de geração/célula (exceto categoria 'catalog', cujo
       subtype é descritivo — o chip_type manda);
    3. `interface` NÃO carrega geração de RAM (largura de barramento x8/x16 ou vazio);
    4. DENSIDADE NO LUGAR CERTO (bug do lote 40, 2026-07-11): chip DDR/GDDR/SDRAM/
       RDRAM com `density_gbit` vazio e `capacity` "pelada" em Gbit ('2G'/'2Gb' —
       o que o bless_base grava da caixa) ganha `density_gbit='<n>Gb'`. FILL-ONLY:
       o `capacity` fica como está (snapshot/labels o leem); 'GB' nunca entra
       (byte de pacote ≠ densidade).
    """
    from chips.chip_types import canonical_chip_type, label_kind, spec_for
    from chips.conventions import canonical_gen, is_ram_generation

    for f in _CLEAN_FIELDS:
        if getattr(obj, f, "") in _NONE_STRINGS:
            setattr(obj, f, "")

    sub = getattr(obj, "subtype", "") or ""
    if sub:
        sp = spec_for(getattr(obj, "chip_type", "") or "")
        if not (sp is not None and sp.category == "catalog"):
            setattr(obj, "subtype", canonical_gen(sub, getattr(obj, "chip_type", "") or ""))

    if is_ram_generation(getattr(obj, "interface", "") or ""):
        setattr(obj, "interface", "")

    ct = getattr(obj, "chip_type", "") or ""
    if ct and not (getattr(obj, "density_gbit", "") or "").strip():
        kind = label_kind(canonical_chip_type(ct, getattr(obj, "subtype", "") or ""))
        if kind in DENSITY_KINDS:
            m = RX_DENSITY_BARE.match((getattr(obj, "capacity", "") or "").strip())
            if m:
                setattr(obj, "density_gbit", f"{m.group(1)}Gb")

    return obj
