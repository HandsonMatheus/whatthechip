# Resposta — Pendências Samsung

> Responde ao `docs/PENDENCIAS_SAMSUNG.md`. Data: 2026-06-29.
> Regras de ouro: 0 invenção, só Tier 1.

---

## Item 1 — `DA97`

**Veredicto: REMOVER do banco.**

`DA97` não é um chip de memória. É o prefixo Samsung para **peças de reposição de
linha branca** (refrigeradores, ar-condicionado). O formato real é `DA97-XXXXXYZ`
(ex.: `DA97-17376A` = sensor de temperatura de geladeira). Com apenas 4 caracteres,
nunca corresponde a um PN de chip completo.

A entrada veio de `confidence="ai_high"` (palpite antigo do Gemini — nível removido em
jun/2026). Não há ocorrência de `DA97` em nenhum CSV, `populate_*.py` ou
`fix_known_parts.py`.

**Ação:** remover via admin Django ou `KnownPart.objects.filter(part_number="DA97").delete()`.

| PN/família | `chip_type` | `subtype` | `density` (Gb/die) | `capacity` (GB) | posição do código de capacidade | obs |
|---|---|---|---|---|---|---|
| `DA97` | — | — | — | — | — | **NÃO É CHIP.** Prefixo de peça de reposição Samsung linha branca. Entrou via `ai_high` (Gemini). **REMOVER.** |

---

## Item 2 — `K4RCH046VM` — Anatomia e família `K4RC`

### Fontes Tier 1

| PN | Fonte | Dado confirmado |
|---|---|---|
| `K4RCH046VM-2CLP` | Samsung Semiconductor Global | 32 Gb, DDR5-6400 ✓ |
| `K4RCH046VM-2CCM` | Samsung Semiconductor Global | 32 Gb, DDR5-5600 ✓ |
| `K4RCH046VM` | `fix_known_parts.py` (entrada existente) | DDR5, 4 GB, `confirmed` ✓ |

> ⚠ Os três PNs **já estão** em `fix_known_parts.py` com `confidence="confirmed"`.
> O problema é exclusivamente de gramática: sem a família `K4RC` no
> `populate_samsung.py`, eles caem no fallback `K4R` (RDRAM, priority=100) e recebem
> classificação errada.

### Anatomia do PN

```
 K 4 R C H  0  4  6  V  M  [- 2  C  L  P]
 │ │ │ │ │  └──┬──┘  │  │    └──┴──┴──┴── sufixo de velocidade
 │ │ │ │ │     │     │  └── package (M = FBGA 96-pin mobile)
 │ │ │ │ │     │     └── variante de processo/stepping
 │ │ │ │ │     └── código de largura de I/O (04 ≈ x4 — campo auxiliar, não mapeado)
 │ │ │ │ └── H = largura de I/O (H = x8)
 │ │ │ └── C = C-die (revisão de nó de processo; A=K4RA, B=K4RB, C=K4RC)
 │ │ └── R = família DDR5 (K4R*)
 │ └── 4 = DRAM
 └── K = Samsung

pn[3:5] = "CH"  ←  código de capacidade
                    decode_cap_pos=3, decode_cap_len=2, mapa DRAM_PC
```

**Correspondência de die dentro da série K4R DDR5:**

| pn[3:5] | die | Gb/die | GB/die | família |
|---|---|---|---|---|
| `AH` | A-die | 16 Gb | 2 GB | K4RA |
| `BH` | B-die | 32 Gb | 4 GB | K4RB |
| `CH` | C-die | 32 Gb | 4 GB | **K4RC ← novo** |

> Mesmo nó de densidade (32 Gb) que o B-die, mas em revisão de processo mais recente.

### Tabela de classificação (formato §3)

| PN/família | `chip_type` | `subtype` | `density` (Gb/die) | `capacity` (GB) | posição do código de capacidade | obs |
|---|---|---|---|---|---|---|
| `K4RC` (família) | `DDR5` | `DDR5` | 32 Gb | 4 GB | `pn[3:5]`, len=2, mapa `DRAM_PC` | C-die. Decode idêntico a K4RA/K4RB (mesmo pos/len/map). Priority=80 (vence fallback RDRAM K4R). |
| `K4RCH046VM` | `DDR5` | `DDR5` | 32 Gb | 4 GB | `pn[3:5]`=`"CH"` | Já em `fix_known_parts.py` (`confirmed`). FBGA96 mobile. |
| `K4RCH046VM-2CLP` | `DDR5` | `DDR5` | 32 Gb | 4 GB | `pn[3:5]`=`"CH"` | Já em `fix_known_parts.py` (`confirmed`). DDR5-6400. |
| `K4RCH046VM-2CCM` | `DDR5` | `DDR5` | 32 Gb | 4 GB | `pn[3:5]`=`"CH"` | Já em `fix_known_parts.py` (`confirmed`). DDR5-5600. |

### Outras variantes K4RC com capacidade diferente?

Nenhuma evidência Tier 1 de K4RC com densidade diferente de 32 Gb. Mapear apenas
`("CH", "32Gb", "4GB")` por ora — regra de ouro: sem invenção de dados.

---

## Ações em código

### 1. `populate_samsung.py` — DRAM_PC: adicionar chave `"CH"`

No bloco `DRAM_PC`, após a linha `("BH", "32Gb", "4GB")`:

```python
("CH",  "32Gb",  "4GB"),   # DDR5: K4RCH046VM (32Gb C-die) — Samsung semiconductor.com ✓
```

### 2. `populate_samsung.py` — família `K4RC`

Após o `dict(prefix="K4RB", ...)` e antes do bloco RDRAM `dict(prefix="K4R", ...)`:

```python
dict(
    prefix="K4RC", chip_type="DDR5", subtype="DDR5",
    interface="DDR5", decode_density_type="pc",
    is_emcp=False, active=True, priority=80,
    decode_cap_pos=3, decode_cap_len=2, decode_cap_map="DRAM_PC",
    tip=(
        "DDR5 Samsung 32Gb C-die (2024+). "
        "K4RC: pn[3:5]=CH → 32Gb (4GB por die). "
        "PNs confirmados: K4RCH046VM, K4RCH046VM-2CLP (DDR5-6400), "
        "K4RCH046VM-2CCM (DDR5-5600) — Samsung semiconductor.com ✓. "
        "⚠ INCOMPATÍVEL com DDR4 — slot, tensão e protocolo diferentes. "
        "NÃO misturar com K4RA (A-die 16Gb) ou K4RB (B-die 32Gb) na bancada. "
        "Destino: bancada reacondicional DDR5 (caixa separada — C-die)."
    ),
),
```

### 3. Após `populate_samsung --overwrite`: reiniciar o servidor

Regra de ouro #3 — `lru_cache` não expira; sem reinício o engine serve gramática antiga.

---

## Resumo de ações

| Item | Ação | Arquivo | Executor |
|---|---|---|---|
| `DA97` | Deletar do banco | Admin / shell Django | Usuário |
| DRAM_PC `"CH"` | Adicionar linha no mapa | `populate_samsung.py` | Claude (editar) |
| Família `K4RC` | Adicionar `dict(prefix="K4RC",...)` | `populate_samsung.py` | Claude (editar) |
| Reiniciar servidor | Após `populate_samsung --overwrite` | — | Usuário |
