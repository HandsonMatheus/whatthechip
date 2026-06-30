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


class KnownPartSpec(BaseModel):
    """Espelha os campos editáveis de `KnownPart`. brand/family/source (FKs) e
    part_number_norm (derivado) vêm do contexto/`save()`, não do YAML.
    (PieceMakers não tem known_parts; stub pronto para as próximas marcas.)"""
    model_config = ConfigDict(extra="forbid")
    part_number: str
    chip_type: str = ""
    subtype: str = ""
    capacity: str = ""
    density_gbit: Optional[int] = None
    density_gb: Optional[float] = None
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
