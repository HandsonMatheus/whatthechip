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

#: Bytes POR DIE em GB ('1GB' — a MESMA convenção per-die acima, dies ≥ 1GB:
#: HYX_DDR4_CAP tem 8G→'1GB', AG→'2GB'; o próprio tip valida AG=2GB=16Gb).
#: Gb = GB × 8. ⚠ SÓ é seguro DENTRO de escopo kind-DDR (lá capacity é
#: per-die por convenção §6); fora dele '1GB' é PACOTE (LPDDR/eMMC) — por
#: isso este regex nunca entra na regra 4 de escrita cega. Caso H5AN
#: (lote 042, 2026-07-31): confirmado cap='1GB' + dens vazio ficava sem
#: chave de preço enquanto a caixa mostrava 8G.
RX_DIE_GB = re.compile(r"^(\d+(?:\.\d+)?)\s*GB$")

#: ─────────────────────────────────────────────────────────────────────────
#: FORMA DO CAMPO DE MEDIDA (2026-08-26). Endurece o portão que já existe
#: (`KnownPart.clean()` + `KnownPartSpec`) — não é portão novo, é regra nova
#: no mesmo, ao lado do `family_type_conflict`.
#:
#: O invariante NÃO é "casa com um gabarito". É: **o engine tem que extrair UMA
#: medida, e na unidade certa**. Porque `_extract_gib` (engine) e `_extract_gb`
#: (estoque) são `re.search` — pegam o PRIMEIRO que casar. Com duas medidas na
#: string, quem decide a prateleira é a ORDEM DAS PALAVRAS. Medido no
#: KMYFE0B0CA: a mesma informação escrita de três jeitos manda o chip pra
#: EMCP1+1, EMCP8+1 e EMCP2+1 — três prateleiras.
#:
#: ⚠ ESTE REGEX ESPELHA `chips/engine.py::_CAP_RE` DE PROPÓSITO, `re.I`
#: incluído. O portão tem que contar o que o LEITOR conta; se divergirem, o
#: portão aprova o que o engine lê errado. `EspelhoDoLeitorTests` trava isso.
RX_MEDIDA = re.compile(r"(\d+(?:\.\d+)?)\s*([TGMK])(B)", re.I)

#: Campos que guardam BYTE de pacote/parcela. `density_gbit` fica FORA: lá a
#: unidade é BIT por definição ('4Gb' é o valor CERTO).
MEASURE_FIELDS = ("capacity", "emcp_ram", "emcp_nand", "density_gb")

#: Só nestes dois a unidade de BIT é sempre erro. Em `capacity` não dá pra
#: bloquear: '2G'/'2Gb' é a forma LEGÍTIMA da caixa que o `bless_base` grava
#: em família DDR-kind (ver regra 4 acima e RX_DENSITY_BARE).
BYTE_ONLY_FIELDS = ("emcp_ram", "emcp_nand")


def measure_field_problem(field: str, value: str) -> str | None:
    """Devolve mensagem ACIONÁVEL se o campo de medida for AMBÍGUO pro engine;
    senão ``None``. Fonte única — usada pelo `clean()` do modelo, pelo portão
    Pydantic e pelo `audit_campo_forma` (pra auditor e portão não divergirem).

    BLOQUEIA duas coisas, as duas medidas em cima do dado real:

    * **mais de uma medida** — em qualquer campo. É o que muda de prateleira
      conforme a ordem das palavras. Custo medido no seed curado (596
      registros): 4 reprovações, TODAS bug real (`K524G2GAC*` com
      ``capacity='NAND 512MB + mDDR1 256MB'`` e ``emcp_*`` vazios — chip que
      hoje sai com a etiqueta literal 'eMCP', sem número, sem prateleira).
    * **unidade de BIT em `emcp_ram`/`emcp_nand`** — ali é sempre byte de
      pacote, e `_CAP_RE` é `re.I`: '8Gb' entra como 8 GB, o erro de 8× da
      casa entrando por um canal sem vigilância.

    NÃO bloqueia campo preenchido SEM medida ('6', '2G'): em `capacity` essa é
    a forma da caixa em DDR-kind e o `bless_base` depende dela. Isso o
    `audit_campo_forma` reporta como aviso, não como barreira.

    Prosa com UMA medida só ('SDRAM 1GB (pré-LPDDR — ver notes)') PASSA de
    propósito: é feia, mas reescrever as palavras não muda o que o engine lê.
    A regra mira a prosa PERIGOSA, não a bagunçada.
    """
    v = (value or "").strip()
    if not v:
        return None
    achados = RX_MEDIDA.findall(v)
    if len(achados) > 1:
        lidas = ", ".join(f"{n}{u.upper()}{b}" for n, u, b in achados)
        return (f"'{field}' tem {len(achados)} medidas ({lidas}) — o engine lê a "
                f"PRIMEIRA (re.search), então a ordem das palavras decide a caixa. "
                f"Deixe UMA medida no campo e mova o resto pra 'notes'/'tip'.")
    if achados and field in BYTE_ONLY_FIELDS and achados[0][2] == "b":
        n, u, _ = achados[0]
        return (f"'{field}' está em {u.upper()}b (gigaBIT) — este campo é BYTE de "
                f"pacote, e o leitor do engine é case-insensitive: '{n}{u}b' entra "
                f"como {n} {u.upper()}B, 8× a mais. Converta pra byte "
                f"(ex.: 8Gb = 1GB) ou use 'density_gbit', que é o campo de bit.")
    return None


def measure_problems(obj, only_fields=None) -> dict:
    """Roda `measure_field_problem` nos campos de medida de um known_part
    (modelo OU KnownPartSpec). `only_fields` limita ao subconjunto que MUDOU —
    é o grandfather: legado fora da regra continua re-salvável, mas ninguém
    consegue piorá-lo nem introduzir caso novo."""
    campos = MEASURE_FIELDS if only_fields is None else tuple(only_fields)
    fora = {}
    for f in campos:
        msg = measure_field_problem(f, getattr(obj, f, "") or "")
        if msg:
            fora[f] = msg
    return fora


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
