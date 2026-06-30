# PRECIFICACAO.md — Sistema de preço de venda (WTC)

> **STATUS: PROPOSTA / DESENHO — NÃO implementado.** Desenho discutido em
> 2026-06-25. Nenhum modelo, migration ou código foi criado ainda. Quando
> implementar, atualize este cabeçalho e mova decisões duradouras pro lugar certo
> (Regra de ouro / HANDOFF). O código continua sendo a fonte da verdade.

---

## 1. Princípio (o PORQUÊ)

O mercado de reciclagem **não tem tabela de preço**. A única âncora honesta é a
árvore de decisão do **comprador**, que precifica nesta ordem:

**marca (rótulo) → tipo → subtipo → capacidade → preço**

O sistema replica essa árvore como uma **chave categórica** — a mesma filosofia da
gramática (`ChipFamily` + `DecodeMap`): a chave **generaliza**, então qualquer
chip que cai na bancada resolve para *algum* preço (mesmo que termine em sucata).
É isso que torna a convenção **universal**.

### Decisões travadas (2026-06-25)
- Moeda: **USD**.
- Preço modelado: **de venda** (o que o comprador paga à eMiner), **por unidade
  (por chip)** — não por peso (peso = sucata = descarte).
- **Condição NÃO é dimensão de preço.** Remarcado / testado / não-testado são
  resolvidos **a montante** (descarte). O preço só roda em chip **RENTÁVEL** (§5).
- **Marca = rótulo** (o que está impresso no chip), não o die.

---

## 2. A separação fundamental: chave estável × cotação volátil

Diferente de `KnownPart` (um PN decodifica pra mesma spec **pra sempre**), **preço
decai com o tempo**. Por isso a chave e o valor são **entidades separadas**:

- **`PriceClass`** — a chave estável. Uma "classe" de chips que cotam igual.
- **`PriceQuote`** — a cotação. Valor **+ data**, série temporal. Preço atual =
  cotação mais recente; histórico preservado.

> ⚠️ Nunca pendure um campo `price` no `KnownPart` — ele nasceria velho. A spec é
> permanente; o preço é uma cotação datada.

### `PriceClass` (a chave)

| campo | tipo | observação |
|---|---|---|
| `brand` | texto | marca do **rótulo** (Samsung, SK Hynix…) |
| `chip_type` | texto | espelha `KnownPart.chip_type` (eMCP, eMMC, UFS, LPDDR4X, RAM…) |
| `subtype` | texto | geração; vazio p/ eMMC/UFS. Normalizar via `canonical_gen` |
| `capacity_token` | texto | token canônico da capacidade (§3) |
| `nand_gb` | float, null | numérico p/ interpolação (§4) |
| `ram_gb` | float, null | numérico p/ interpolação |
| `density_gbit` | float, null | numérico p/ interpolação (DDR) |
| `active` | bool | |
| **único** | — | `(brand, chip_type, subtype, capacity_token)` |

### `PriceQuote` (a cotação)

| campo | tipo | observação |
|---|---|---|
| `price_class` | FK → PriceClass | `related_name="quotes"` |
| `price_usd` | decimal | venda, **por unidade** |
| `quote_date` | data | **a data da cotação** (coração da UX — §6) |
| `source` | texto | quem cotou (comprador / cliente / ref. de mercado) |
| `note` | texto | |
| `created_at` | auto | |

Preço corrente de uma classe = `quotes.order_by("-quote_date").first()`.

---

## 3. A "capacidade" muda de forma por tipo

A capacidade **não é um escalar único** — espelha a convenção de campos do estoque
(`docs/CONVENCAO_MICRON_ESTOQUE.md`):

| tipo | `capacity_token` | numéricos preenchidos |
|---|---|---|
| eMMC / UFS | `"16GB"`, `"128GB"` | `nand_gb` |
| LPDDR avulso | `"4GB"`, `"8GB"` | `ram_gb` |
| eMCP / uMCP | `"16+1"`, `"128+6"` (NAND+RAM) | `nand_gb` + `ram_gb` |
| DDR / GDDR | `"8Gb"`, `"16Gb"` (die) | `density_gbit` |

> O `capacity_token` é a chave **legível** (igual ao que o comprador fala: "16+1");
> os numéricos servem só pra **interpolar** capacidade no fallback (§4).

> ⚠️ **O token da caixa ≠ a chave de preço.** O label de destino ("EMCP16+1")
> colapsa de propósito o subtipo (não mostra LPDDR3 × LPDDR4), e isso **muda o
> preço**. Reuse a *normalização* (`canonical_gen`), mas mantenha os 4 campos
> explícitos na chave.

---

## 4. Resolução — `resolve_price(result)` (escada, igual banco→gramática)

Consome a saída de `classify()`; **só roda se RENTÁVEL**. Monta a chave e tenta,
em ordem:

1. **Exato** — `PriceClass` igual → cotação mais recente. `basis="exato"`.
2. **Interpolado** — mesma `(brand, type, subtype)`, capacidade ausente → vizinho
   mais próximo / interpola pelos numéricos (preço/capacidade **não** é linear).
   `basis="interpolado"`.
3. **Sem-marca** — solta a marca: `(type, subtype, capacity)` → referência média.
   `basis="sem-marca"`. *Solta a marca ANTES da capacidade* — tipo+capacidade é o
   valor intrínseco; marca é só modificador.
4. **Ausente** — nada → `"SEM COTAÇÃO"`; sinaliza pro comprador cotar (fila tipo
   `UnknownChip`, mas de preço). `basis="ausente"`.

Toda saída carrega **`quote_date` (data da última atualização) + `basis`**.

Exemplo no card de busca:
`US$ 3,20 / un — cotado 24/06/2026 — exato`
`≈ US$ 2,80 / un — sem-marca — cotado 10/06/2026`

---

## 5. Lugar no pipeline — a JUSANTE da rentabilidade

```
PN → classify() → assess_profitability ──NÃO RENTÁVEL──▶ descarte (sem preço)
                         │
                      RENTÁVEL
                         ▼
                  resolve_price()  →  preço + data
```

Rentabilidade é o **portão**; preço é a **avaliação dos sobreviventes**. O preço
**não reimplementa** rentabilidade (Regra de ouro #11 — fonte única).

**Caminho futuro (opcional — NÃO implementar agora):** inverter a dependência —
`RENTÁVEL = price_usd > processing_cost_usd + min_margin_usd`. Aí
`assess_profitability` derivaria do preço real em vez de limiares fixos. A chave já
é projetada pra suportar isso (campos no `PriceConfig`).

---

## 6. Data da cotação — `PriceConfig` (singleton, igual `ProfitabilityConfig`)

> **⛔ NÍVEIS COM COR DESCARTADOS pelo dono (2026-06-30) — ver `docs/PLANO_IMPLEMENTACAO_ESCALABILIDADE.md §5`.**
> Os antigos níveis (fresco/envelhecendo/velho, com cor) foram **removidos** — "confundem mais que
> ajudam" e o termo não traduz bem entre idiomas. Fica só a **`quote_date` (data da última
> atualização)** exibida no card. O `PriceConfig` perde `fresh_max_days`/`aging_max_days`. O texto
> abaixo é histórico.

Mostrar a **data** da cotação é o coração da UX: preço sem data é falsa precisão
num mercado volátil. Níveis configuráveis no admin:

| nível | regra (default) | cor |
|---|---|---|
| **Fresco** | ≤ 14 dias | 🟢 verde |
| **Envelhecendo** | 15–45 dias | 🟡 amarelo |
| **Velho** | > 45 dias | 🔴 vermelho — "reconfirmar" |

Campos do `PriceConfig`: `currency="USD"`, `fresh_max_days=14`,
`aging_max_days=45`, `processing_cost_usd`, `min_margin_usd`,
`brand_fallback_enabled`.

---

## 7. Perguntas abertas
- **Entrada do preço:** manual pelo comprador (v1, provável — ele já tem o preço na
  cabeça) vs feed/scraping de mercado.
- **Interpolação de capacidade:** vizinho-mais-próximo (simples, recomendado pra
  começar) vs curva de preço/capacidade.
- **Fila "sem cotação":** modelar agora ou só quando aparecer volume.
- **Subtipo × bins:** LPDDR4 × LPDDR4X já separam pela chave; decidir se a
  velocidade de DDR (ex.: DDR4-2400 × 3200) entra no subtipo/chave quando isso
  passar a mexer no seu preço.
