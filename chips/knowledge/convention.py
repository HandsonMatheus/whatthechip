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


def family_type_conflict(part_number: str, chip_type: str) -> str | None:
    """Detecta o conflito known_part × FAMÍLIA no eixo ``is_emcp`` — a brecha que deixou o
    ``SD5DH26A4G`` (submetido eMCP, com a capacidade em ``emcp_nand``/``emcp_ram``) cair na
    família eMMC ``SD5DH`` (``is_emcp=False``). O engine tira o ``chip_type`` da FAMÍLIA (não
    do known_part) e, como a família não é eMCP, NUNCA lê ``emcp_nand``/``emcp_ram`` → a
    capacidade some no ``classify``. Nem o Pydantic (valida o known_part isolado) nem o
    ``clean()`` (só convenção/vocabulário) cruzavam known_part × família — esta é a trava.

    Retorna uma mensagem ACIONÁVEL se houver conflito; senão ``None``. FAIL-OPEN de propósito:
      - ``chip_type`` vazio (identity-only) → ``None``: defere à gramática, não há merge quebrado;
      - nenhuma família casa o prefixo → ``None``: a gramática não renderiza, não há merge;
      - ``chip_type`` fora do vocabulário (``spec_for`` = ``None``) → ``None``: outro problema, não deste guard.
    Só dispara quando o ``chip_type`` é um tipo CANÔNICO conhecido cuja "MCP-ness" (eMCP/uMCP)
    DIVERGE do ``is_emcp`` da família — o eixo EXATO em que o merge de ``_result_from_known`` quebra.
    """
    ct = (chip_type or "").strip()
    if not ct:
        return None
    from chips.chip_types import spec_for
    sp = spec_for(ct)
    if sp is None:
        return None

    from chips.engine import _match_family
    from chips.normalize import normalize_pn
    fam = _match_family(normalize_pn(part_number))
    if fam is None or sp.is_emcp == fam.is_emcp:
        return None

    kp_kind  = "eMCP/uMCP (composto NAND+RAM)" if sp.is_emcp else f"NÃO-MCP ('{ct}')"
    fam_kind = "eMCP/uMCP (is_emcp=True)" if fam.is_emcp else "NÃO-MCP (is_emcp=False)"
    return (
        f"conflito de tipo known_part × família: o chip_type '{ct}' é {kp_kind}, mas o PN "
        f"'{part_number}' casa a família '{fam.prefix}', que é {fam_kind}. O engine deriva o "
        f"tipo da FAMÍLIA e ignora o ramo oposto (eMCP↔não-eMCP) no merge, então a capacidade "
        f"some no classify. Corrija o chip_type do known_part OU crie/aponte uma família "
        f"{'eMCP' if sp.is_emcp else 'não-eMCP'} para esse prefixo antes de gravar."
    )
