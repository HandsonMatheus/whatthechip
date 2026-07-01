"""
chips/knowledge/schema.py
=========================
**PASSO 4** do `docs/PLANO_IMPLEMENTACAO_ESCALABILIDADE.md`: o schema Pydantic do
conhecimento por marca. É o **PORTÃO** que valida cada `chips/knowledge/<marca>.yaml`
ANTES de tocar o banco — as **regras de ouro do CLAUDE.md viram validadores
executáveis**, então um erro de catálogo vira mensagem clara em vez de bug silencioso
no engine.

Mapeamento YAML → modelos:
    brand:        → Brand          (BrandSpec)
    maps:         → DecodeMap       (Dict[nome_do_mapa, lista de [char, primary, secondary]])
    families:     → ChipFamily      (FamilySpec — espelha os campos do modelo)
    known_parts:  → KnownPart       (KnownPartSpec — opcional; PieceMakers não tem)

`extra="forbid"` em tudo: um campo escrito errado (ex.: `decode_capp_pos`) é um ERRO,
não um silêncio. O loader (`load_brands`) chama `BrandFile(**yaml)` e converte os
`ValidationError` do Pydantic numa mensagem de uma linha por problema.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

# Vocabulário de confiança (CLAUDE.md §8). Só confirmed/manual vencem a gramática;
# os de IA (ai_*) foram removidos com o Gemini.
_CONFIDENCE = {"confirmed", "manual", "distributor", "estimated"}


class BrandSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    code: str
    notes: str = ""


class DecodeEntry(BaseModel):
    """Uma linha de DecodeMap. No YAML é uma lista curta: ``[char, primary, secondary?]``
    (ex.: ``['11', '256MB', '']``). O secondary é opcional."""
    model_config = ConfigDict(extra="forbid")
    char_key: str
    val_primary: str
    val_secondary: str = ""

    @model_validator(mode="before")
    @classmethod
    def _from_seq(cls, v):
        if isinstance(v, (list, tuple)):
            if not (2 <= len(v) <= 3):
                raise ValueError(
                    f"entrada de mapa deve ser [char, primary, secondary?] "
                    f"(2 ou 3 itens), recebi {v!r}")
            return {
                "char_key": str(v[0]),
                "val_primary": str(v[1]),
                "val_secondary": str(v[2]) if len(v) > 2 else "",
            }
        return v


class FamilySpec(BaseModel):
    """Espelha os campos de `ChipFamily`. A `brand` (FK) vem do contexto do arquivo,
    não do YAML da família."""
    model_config = ConfigDict(extra="forbid")
    prefix: str
    chip_type: str
    subtype: str = ""
    interface: str = ""
    is_emcp: bool = False
    active: bool = True
    priority: int = 100
    pn_length: Optional[int] = None
    decode_cap_pos: Optional[int] = None
    decode_cap_len: int = 1
    decode_cap_map: str = ""
    decode_gen_pos: Optional[int] = None
    decode_gen_map: str = ""
    decode_gen_len: int = 1
    decode_density_type: str = ""
    suffix_rules: str = ""
    tip: str = ""
    reasoning: str = ""

    @model_validator(mode="after")
    def _regras_de_ouro(self):
        # Armadilha do CLAUDE.md: decode_density_type e decode_cap_map são
        # MUTUAMENTE EXCLUSIVOS (K4F/K4U/K3U devem ter density_type vazio).
        if self.decode_density_type and self.decode_cap_map:
            raise ValueError(
                f"família '{self.prefix}': decode_density_type "
                f"('{self.decode_density_type}') e decode_cap_map "
                f"('{self.decode_cap_map}') são mutuamente exclusivos — use um OU outro.")
        # Regra de ouro #5: famílias KM com DÍGITO na 3ª posição (KM1/2/4/5/8…)
        # precisam de decode_gen_pos = nulo, senão o engine produz texto Frankenstein.
        if (self.prefix[:2] == "KM" and len(self.prefix) >= 3
                and self.prefix[2].isdigit() and self.decode_gen_pos is not None):
            raise ValueError(
                f"família '{self.prefix}' (KM com dígito na 3ª posição): "
                f"decode_gen_pos deve ser nulo (regra de ouro #5).")
        return self

    @model_validator(mode="after")
    def _convencao_de_campos(self):
        """PORTÃO DA CONVENÇÃO (passo 4) — o data contract que impede marca de sujar
        o dado. Normaliza os campos usando AS MESMAS funções canônicas do engine
        (`chip_types.py`/`conventions.py` = fonte única), então o dado ARMAZENADO fica
        igual ao que o engine mostra (mata a divergência stored≠output por construção),
        e REJEITA o ambíguo com erro acionável (não tolera silenciosamente — crítica ao
        princípio de Postel). As `_convencao_de_campos` mecânicas são reversíveis/audit-
        áveis via pghistory (passo 3b)."""
        from chips.chip_types import GENERIC_TYPES, canonical_chip_type, spec_for
        from chips.conventions import canonical_gen, is_ram_generation

        # 1. chip_type → token canônico. Se ATIVA e não resolver a um tipo específico
        #    (fica genérico 'RAM'/'DDR' ou desconhecido) → REJEITA (força a correção).
        canon = canonical_chip_type(self.chip_type, self.subtype)
        if self.active and (canon in GENERIC_TYPES or spec_for(canon) is None):
            raise ValueError(
                f"família '{self.prefix}': chip_type '{self.chip_type}' não resolve a um "
                f"tipo/geração canônico (subtype '{self.subtype}'). Ponha a geração "
                f"(DDR3/LPDDR4X/eMMC/eMCP/UFS/NAND Flash…) no chip_type ou no subtype. "
                f"(Módulo/tipo-lixo? marque active=false.)")
        if spec_for(canon) is not None and canon not in GENERIC_TYPES:
            self.chip_type = canon   # ex.: ('RAM','DDR3 SDRAM') → 'DDR3'

        # 2. subtype → token canônico (só a geração/célula; sem 'standalone', '+ eMMC',
        #    'SDRAM', qualificadores). Ex.: 'LPDDR3 + eMMC'→'LPDDR3'; 'DDR4 SDRAM'→'DDR4'.
        #    EXCEÇÃO: categoria 'catalog' (NOR/OneNAND/MCP/ePoP/SoC/PMIC/SRAM/…) tem subtype
        #    DESCRITIVO — o chip_type MANDA (chip_types.py::_TYPE_WINS_CATS). Normalizar
        #    mutilaria a descrição (MCP 'NOR Flash + SDRAM'→'SDRAM'; ePoP 'eMMC + LPDDR
        #    Empilhado'→'LPDDR') sem ganho: o label dessas não usa o subtype. Então pula.
        _spec = spec_for(self.chip_type)
        _descritivo = _spec is not None and _spec.category == "catalog"
        if self.subtype and not _descritivo:
            self.subtype = canonical_gen(self.subtype, self.chip_type)

        # 3. interface NÃO carrega geração de RAM (é largura de barramento x8/x16 ou vazio).
        if is_ram_generation(self.interface):
            self.interface = ""

        return self


class KnownPartSpec(BaseModel):
    """Espelha os campos editáveis de `KnownPart`. brand/family/source (FKs) e
    part_number_norm (derivado) vêm do contexto/`save()`, não do YAML.
    (PieceMakers não tem known_parts; stub pronto para as próximas marcas.)"""
    model_config = ConfigDict(extra="forbid")
    part_number: str
    chip_type: str = ""
    subtype: str = ""
    capacity: str = ""
    density_gbit: str = ""   # TextField no modelo (ex.: "4Gb"), NOT NULL default="" — não Optional[int]
    density_gb: str = ""     # idem (ex.: "512MB")
    emcp_ram: str = ""
    emcp_nand: str = ""
    interface: str = ""
    fbga_code: str = ""
    device: str = ""
    notes: str = ""
    source_url: str = ""
    confidence: str = "confirmed"

    @field_validator("confidence")
    @classmethod
    def _confidence_no_vocabulario(cls, v):
        if v not in _CONFIDENCE:
            raise ValueError(
                f"confidence '{v}' inválido — use um de {sorted(_CONFIDENCE)}.")
        return v

    @model_validator(mode="after")
    def _convencao_kp(self):
        """PORTÃO DA CONVENÇÃO nos known_parts (fase 1b) — o MESMO data contract da
        gramática, aplicado à autoridade: subtype/interface canônicos + limpa o lixo
        'None'. NÃO rejeita (known_part é ponto de dado, não família com active). O
        chip_type do known_part não entra no classify (vem da família no merge), então
        não mexe nele. Mantém a autoridade convention-clean, consistente com as famílias."""
        from chips.chip_types import spec_for
        from chips.conventions import canonical_gen, is_ram_generation
        # 1. valores 'None' string (lixo de importador) → vazio (o engine já os ignora)
        for f in ("capacity", "emcp_ram", "emcp_nand", "density_gbit", "density_gb", "interface"):
            if getattr(self, f) in ("None", "none", "NONE"):
                setattr(self, f, "")
        # 2. subtype → token canônico (exceto catalog, cujo subtype é descritivo)
        _sp = spec_for(self.chip_type)
        if self.subtype and not (_sp is not None and _sp.category == "catalog"):
            self.subtype = canonical_gen(self.subtype, self.chip_type)
        # 3. interface NÃO carrega geração de RAM (largura de barramento ou vazio)
        if is_ram_generation(self.interface):
            self.interface = ""
        return self


class BrandFile(BaseModel):
    """O arquivo inteiro de uma marca: `chips/knowledge/<marca>.yaml`."""
    model_config = ConfigDict(extra="forbid")
    brand: BrandSpec
    maps: Dict[str, List[DecodeEntry]] = {}
    families: List[FamilySpec] = []
    known_parts: List[KnownPartSpec] = []

    @model_validator(mode="after")
    def _refs_de_mapa_existem(self):
        # Uma família não pode referenciar um mapa que não está definido em `maps`.
        nomes = set(self.maps)
        for f in self.families:
            for ref in (f.decode_cap_map, f.decode_gen_map):
                if ref and ref not in nomes:
                    raise ValueError(
                        f"família '{f.prefix}' referencia o mapa '{ref}', que não está "
                        f"definido em 'maps' (definidos: {sorted(nomes) or 'nenhum'}).")
        return self
