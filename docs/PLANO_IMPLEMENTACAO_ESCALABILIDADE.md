# Plano de implementação — escalabilidade do WTC

> **O que é.** O passo a passo executável da `docs/PROPOSTA_ESCALABILIDADE.md` (já decidida e
> alinhada). Cada passo diz: **o que faz**, **o que eu crio/edito**, **o que você roda**, **como
> provamos que não quebrou**, e **como desfazer**.
>
> **Regras que valem para o plano inteiro:**
> - **Eu edito arquivos; você roda os comandos.** Todo comando que escreve no banco é **dry-run por
>   padrão** e só grava com `--commit`. Você roda no **Render Shell** (mesma região do banco → rápido).
> - **Toda mudança que toca o engine é provada pela rede de regressão** (passo 0): rodar
>   `characterize_baseline --diff` antes/depois e exigir que só apareçam as mudanças **esperadas**.
> - **Um passo por vez.** Cada passo é independente e *shippable* — dá para parar entre qualquer um.
> - **É evolução, não reescrita.** O `classify()` não muda; mudamos *de onde* ele é alimentado e
>   *como* o resultado é cacheado/exibido.

---

## Visão geral

| # | Passo | Objetivo (1 linha) | Risco | Tam. | Depende de |
|---|---|---|---|---|---|
| **0** | `characterize_baseline` | A rede de regressão reutilizável — protege todo o resto | 🟢 baixo | P | — |
| **1A** | `normalize_pn` + unicidade | Acaba a classe de bug de PN duplicado (56% do banco) | 🟡 médio | M | 0 |
| **1B** | `catalog_version` + cache | Acaba a regra "reinicie após populate" | 🟢 baixo | M | 0 |
| **1C** | Trava de banco + `bulk_update` + limpeza | Impede o acidente localhost×prod; 20 min → seg; tira resíduos | 🟢 baixo | P | 0 |
| **2** | Frescor do estoque | Estoque deixa de defasar; mostra o atual; histórico interno | 🟡 médio | M | 1B |
| **3** | `deploy_catalog` + `pghistory` | 13 passos → 1 comando seguro; auditoria no banco | 🟡 médio | M | 1B, 1C |
| **4** | Conhecimento → YAML | Tira a gramática do código (a alavanca grande) | 🔴 alto | G | 0, 1A, 1B |
| **5** | Sistema de preço | Preço por categoria, editável pelo comprador | 🟡 médio | G | 4 |
| **6** | Enriquecimento | Funil de curadoria (futuro) | — | — | depois |

*Tam. = tamanho relativo (P/M/G). Não são estimativas de horas.*

---

## O loop de cada passo (o mesmo sempre)

1. **Eu** crio/edito os arquivos (código, models, migrations, comando) e te explico o que mudou.
2. **Você** roda a migração/comando em **`--dry-run`** no Render Shell e me manda a saída.
3. Conferimos o **dry-run** (o que vai mudar). Se estiver certo, **você** roda com **`--commit`**.
4. **Você** roda `characterize_baseline --diff` → confirmamos que só mudou o **esperado**.
5. Se algo saiu errado: **`--revert`** (ou reverter a migração). Só então seguimos para o próximo.

---

## PASSO 0 — `characterize_baseline` (a rede de regressão)

> **✅ IMPLEMENTADO e verificado (2026-06-30).** Comando em
> `chips/management/commands/characterize_baseline.py`. Verificado no sandbox (SQLite carregado do
> `prod_data.json`): snapshot grava o baseline; `--diff` contra si mesma dá **IDÊNTICO**
> (determinístico); ao corromper 1 campo de propósito, detecta exatamente 1 alterado. O run completo
> dos 6571 PNs leva ~9 min (o fuzzy é o gargalo) → rodar no **Render Shell** (sem timeout). Read-only
> garantido por transação revertida (desfaz as escritas de `SearchLog`/`UnknownChip` do `classify`).
> *(Achado lateral: a família `prefix=16EMCP` tem `reasoning` com JSON inválido — resíduo de dado,
> candidato à limpeza do passo 1C; não bloqueia.)*

**Por quê primeiro.** Tudo que toca o engine precisa de uma rede: rodar o banco inteiro pelo
`classify()` **antes** e **depois** e exigir saída idêntica (salvo o que a mudança deveria afetar).
O método já existe (`docs/CARACTERIZACAO_BASELINE.md`) mas foi rodado avulso — vamos torná-lo um
**comando commitado e reutilizável**.

**Eu crio:**
- `chips/management/commands/characterize_baseline.py` — **read-only**, não toca produção:
  - `--snapshot baseline.json` → carrega o banco (de `prod_data.json` **ou** lê o banco conectado),
    roda para cada PN o pipeline real (`classify` → `_compute_destination` → `assess_profitability`
    → `is_dead_by_generation`) e grava **1 linha por PN** com os campos de saída (tipo, capacidade,
    subtipo, emcp_*, label de destino, rentável, is_dead).
  - `--diff baseline.json` → roda de novo e **compara**: lista cada PN cujo qualquer campo mudou.
  - Carga num **SQLite descartável** (sem populate/migrate/log), como o baseline original.

**Você roda:**
```
# dump fresco da produção (Render Shell), se quiser atualizar o snapshot
python manage.py dumpdata chips > prod_data.json
python manage.py characterize_baseline --snapshot baseline_antes.json
```

**Verificação:** rodar `--snapshot` duas vezes seguidas → o `--diff` entre elas deve dar **zero**.

**Rollback:** nenhum (não escreve nada).

---

## PASSO 1 — Encanamento (1A + 1B + 1C)

> O bloco de **risco quase zero** que conserta dor já sentida (cache velho, acidente de banco,
> migração de 20 min, duplicatas). As três peças são independentes; ordem sugerida: 1B → 1C → 1A.

### 1A — `normalize_pn` + coluna normalizada + unicidade

**Por quê.** 3898 PNs (56%) têm `:`/`.` não canonizados; **1908 caem em "tipo vazio" na bancada**
(o dado tem tipo, é a *busca* que erra — `docs/CARACTERIZACAO_BASELINE.md §4.1`). E o engine hoje
"salta silencioso" quando dois PNs normalizam igual.

**Eu crio/edito:**
- `chips/normalize.py` → `normalize_pn(value)`: `NFKC` → remove `-` espaço `:` `.` → `.upper()`.
- `KnownPart`: coluna **`part_number_norm`** + `UniqueConstraint(fields=["part_number_norm"])`.
  (Mantém `part_number` cru para exibição.)
- Migração em ordem segura: add coluna (anulável) → **backfill** em massa → **dedupe** (sobrevive o
  de maior `confidence`; reaponta FKs de estoque/submissões; registra o merge numa tabela de
  auditoria) → `NOT NULL` → `AddConstraint` (índice `CONCURRENTLY`, migração não-atômica).
- `dedupe_known_parts` (comando dry-run + `--commit` + `--revert`) para o passo de fusão (precisa
  de revisão humana).
- `engine.py`: lookup por `part_number_norm`; **remover** o handler `MultipleObjectsReturned`.

**Você roda:** `dedupe_known_parts --dry-run` (mostra colisões + plano de fusão) → revisa → `--commit`;
depois a migração aplica a restrição.

**Verificação:** `characterize_baseline --diff` → os 1908 que falhavam **passam a resolver** (diff
**esperado**, desejado); o resto idêntico. + testes unitários de `normalize_pn`.

**Rollback:** `dedupe_known_parts --revert` + reverter a migração.

### 1B — `catalog_version` + cache por versão

> **✅ IMPLEMENTADO e verificado (2026-06-30, branch `escalabilidade`).** Arquivos: `chips/models.py`
> (model `CatalogVersion` singleton), `chips/engine.py` (cache keyed em `_catalog_version()`),
> `chips/apps.py` (sinais `post_save`/`post_delete` em `ChipFamily`/`DecodeMap`/`ProfitabilityConfig`
> → `bump()`), migração `0013_catalogversion`, testes em `chips/tests.py`. **Verificação:** regressão
> `characterize_baseline --diff` = **IDÊNTICO** (800 PNs); 2 testes novos (mudar família sobe a versão
> e o engine recarrega **sem** restart); **suíte `chips` = 81 testes OK**. *Pendente p/ o deploy:*
> atualizar a regra de ouro #3 do `CLAUDE.md` + as mensagens "reinicie o servidor" dos `populate_*`
> (ficam obsoletas quando subir à `main`). Bump explícito nos comandos de escrita em massa entra no
> passo 4; KnownPart→bump entra no passo 2.

**Por quê.** O `_get_all_families()` é cacheado **sem chave de versão** → após `populate`, o servidor
serve gramática velha até reiniciar (regra de ouro #3). Cada worker do gunicorn tem seu cache.

**Eu crio/edito:**
- Model **`CatalogVersion`** (singleton, `version` inteiro) com `.current()` e `.bump()`.
- `engine.py`: `_load_catalog(version)` keyed na versão; `get_catalog()` lê `CatalogVersion.current()`
  (1 SELECT barato). Substitui `_get_all_families`/`_load_decode_map`.
- **Sinais** `post_save`/`post_delete` em `ChipFamily`, `DecodeMap`, `ProfitabilityConfig` → `bump()`
  (pega edições no admin também). + `bump()` explícito no fim de `populate_*`/`import_*`/`fix_*`.

**Você roda:** migração + **um último restart** (o último por esse motivo). Depois, populates se
refletem sozinhos.

**Verificação:** `characterize_baseline --diff` → **idêntico** (cache não muda saída). + teste:
`bump()` → próximo `classify()` recarrega.

**Rollback:** reverter a migração (volta ao `lru_cache` antigo).

### 1C — Trava de banco + `bulk_update` + limpeza de resíduos

**Por quê.** Sem `DATABASE_URL`, o `dj_database_url` **cai em silêncio** no localhost (foi o acidente).
O `normalize_convention` roda linha-a-linha (~20 min). Há resíduos (`ai_high`, "usa Gemini", `status`).

**Eu crio/edito:**
- `core/settings.py`: `env.db()` **sem default** → quebra alto se faltar `DATABASE_URL`.
- Mixin `SafeWriteCommand` (todos os comandos que escrevem herdam): imprime **banner** `host`+`name`
  antes de gravar; em modo interativo **exige digitar o nome do banco**; `--dry-run`/`--commit`.
- `normalize_convention` (e outros loops) → **`bulk_update`** (lotes de ~500).
- Limpeza: comando dry-run→commit que zera os **21 `ai_high`** e tipos-lixo (`docs/CARACTERIZACAO_BASELINE.md §4.4`);
  remover a msg "usa Gemini" do `add_chip_families`; tirar `status` dos docs.

**Você roda:** a troca do `settings` é automática no deploy; o banner aparece em todo comando de
escrita; a limpeza de `ai_high` é um comando dry-run→commit.

**Verificação:** rodar um comando de escrita **sem** `DATABASE_URL` → **crasha** (bom). `--diff` para
a limpeza (os 21 `ai_high` mudam de `confidence` — diff esperado).

**Rollback:** `--revert` da limpeza; o resto é config/reversível.

---

## PASSO 2 — Frescor do estoque

**Por quê.** O `InventoryEntry` guarda um snapshot que **defasa** quando o engine melhora (Micron
48GB→6GB). **Decisão do dono:** o frontend mostra o **valor atual**; o histórico fica interno.

**Eu crio/edito:**
- `InventoryEntry`: campos **`intake_at`** + **`intake_catalog_version`** (carimbados no lançamento,
  **imutáveis**). O snapshot de hoje vira o "snapshot de entrada".
- **On-read (frontend):** a lista do estoque calcula a classificação **atual** via
  `_snapshot(classify(pn))` **só para as linhas visíveis** (paginadas), com atalho: se
  `intake_catalog_version == catalog_version`, nem recalcula. Mostra o **atual** (opção *b*).
- **`resnapshot_lote`** (comando): re-roda `_snapshot(classify(pn))` sobre um lote, **gated por
  `catalog_version`** (só as entradas atrasadas), `bulk_update`, dry-run + `--commit` + `--revert`
  (revert em **`var/reverts/`**, não na raiz). É o caminho **principal** (o on-read é fallback do
  visível) — a tela nunca dispara N `classify()` síncronos.
- Histórico de mudanças = `django-pghistory` na `InventoryEntry` (vem no passo 3).

**Você roda:** migração (campos de intake); **backfill proativo** dos lotes existentes via
`resnapshot_lote --dry-run` → `--commit` no Render Shell (para o 1º leitor não pagar o pico).

**Verificação:** abrir um lote e conferir os valores atuais; teste do atalho de versão. (O
`characterize_baseline` cobre o engine; aqui o foco é o estoque ler certo.)

**Rollback:** `resnapshot_lote --revert`; reverter a migração dos campos de intake.

---

## PASSO 3 — `deploy_catalog` num comando + `django-pghistory`

**Por quê.** O deploy de catálogo é uma cerimônia de 13+ comandos. E queremos **auditoria** (quem
mudou o quê) no banco, não `*_revert.json` na raiz.

**Eu crio/edito:**
- **`deploy_catalog`** (comando): encadeia os sub-passos do catálogo via `call_command`, cada um
  **idempotente** + **bulk** + seu próprio `atomic()`; imprime o **banner** de banco; `--dry-run`
  padrão + `--commit`; **bumpa `catalog_version`** no fim. *(Inicialmente embrulha os `populate_*`;
  após o passo 4, embrulha o `load_brands` — troca trivial.)*
- **`django-pghistory`**: adicionar ao `requirements`; registrar as tabelas do **catálogo**
  (`ChipFamily`, `DecodeMap`, `KnownPart`, `ProfitabilityConfig`) para rastreio; migração cria as
  tabelas/gatilhos de evento. *(Preço não precisa — `PriceQuote` datado já é histórico.)*
- `render.yaml`: `preDeployCommand: migrate` (schema aplica sozinho no deploy; comandos destrutivos
  **não** vão no pre-deploy — são Render Shell).

**Você roda:** `deploy_catalog --commit` no Render Shell (lê o banner, acompanha **um** log).

**Verificação:** `characterize_baseline --diff` após um `deploy_catalog` (idêntico se não mudou
catálogo). pghistory: editar um registro no admin → ver o evento registrado.

**Rollback:** pghistory é aditivo (reverter a migração o remove); `deploy_catalog` é idempotente
(re-rodar).

---

## PASSO 4 — Conhecimento por marca → YAML (a alavanca grande)

**Por quê.** Tirar a gramática de dentro do Python (607 KB de `fix_known_parts`, 148 KB de
`populate_samsung`, a duplicação `add_chip_families`). **PoC = PieceMakers** (3 registros, limpo).

**Eu crio/edito:**
- **Schema Pydantic** (`chips/knowledge/schema.py`) espelhando `ChipFamily`/`DecodeMap`, com as
  **regras de ouro como validadores**: exclusividade `decode_density_type`×`decode_cap_map`;
  famílias KM (3ª posição → `decode_gen_pos=None`); ordem `val_primary`/`val_secondary` em eMCP;
  `confidence` no vocabulário.
- **`load_brands`** (comando): lê `chips/knowledge/<marca>.yaml` (gramática) + `<marca>.csv`
  (correções), **valida com Pydantic** (erro claro), expande `shared_maps`/`$ref` **inline por
  padrão**, faz upsert em `ChipFamily`/`DecodeMap`/`KnownPart` via `bulk_create(update_conflicts)`,
  **recusa prefixo duplicado**, bumpa `catalog_version`. Flags: `--dry-run`/`--commit`, `--report`
  (completude), `--price-skeleton` (para o passo 5).
- **PoC:** `chips/knowledge/piecemakers.yaml` (migrado do `populate_piecemakers.py`).
- Conforme cada marca migra, **aposenta** o `populate_<marca>` correspondente; ao fim, aposenta o
  `add_chip_families` e o `fix_known_parts`.

**Você roda (por marca, PieceMakers primeiro):**
```
python manage.py load_brands --brand piecemakers --dry-run    # valida + mostra o diff
python manage.py load_brands --brand piecemakers --commit
python manage.py characterize_baseline --diff baseline_antes.json
```

**Verificação (o trilho de segurança crítico):**
- `characterize_baseline --diff` → **idêntico** para os registros existentes da marca.
- **+ amostragem manual de PNs inéditos** (que NÃO estão no banco) — a regressão não cobre a cauda
  longa que a gramática generaliza (caveat do chat de arquitetura). Eu gero uma amostra de PNs novos
  por família; você/eu conferimos contra datasheet.
- Só depois de PieceMakers passar 100%, seguimos marca a marca (**Samsung por último** — dona dos
  `shared_maps`).

**Rollback:** o `load_brands` não apaga os `populate_*` até a marca estar validada; reverter = não
aposentar o `populate_*` e reverter a carga (idempotente).

---

## PASSO 5 — Sistema de preço por categoria

**Por quê.** Preço por **categoria** (marca×tipo×subtipo×capacidade), editável pelo comprador, a
jusante da rentabilidade. Desenho-base: `PRECIFICACAO.md`.

**Eu crio/edito:**
- Models: **`PriceClass`** (`brand`, `chip_type`, `subtype`, `capacity_token`, numéricos, `active`),
  **`PriceQuote`** (FK, `price_usd`, `quote_date` = **data da última modificação**, `source`, `note`),
  **`PriceConfig`** (singleton: só **moeda** = USD; *opcional futuro:* custo de processamento + margem).
  > **Sem "frescor" (decisão do dono, 2026-06-30):** descartamos os níveis fresco/envelhecendo/velho
  > (com cor) do `PRECIFICACAO §6` — confunde mais que ajuda. Fica **só a data de última modificação**
  > do preço, exibida no card. `PriceConfig` perde os campos de frescor (`fresh_max_days`/`aging_max_days`).
- **`price_key(result)`** — **uma** função canônica que monta o `capacity_token` (eMCP `"16+1"`,
  DDR `"8Gb"`) a partir do resultado do engine, reusando os helpers de `chip_types`/`_snapshot`
  (**não** o label da caixa).
- **`resolve_price(result)`** — roda **só se RENTÁVEL**; **exato → senão "sem cotação"** (decisão do
  dono: **sem interpolação**). Saída: `price_usd` + `quote_date` (última modificação) — **sem** nível
  de frescor.
- **Admin do comprador:** um painel com **TODOS os `PriceClass`** (com e sem preço juntos), edição
  in-place, permissão por grupo. **Sem fila separada.**
- **`load_brands --price-skeleton`** — gera a lista completa de `PriceClass` do catálogo (todas as
  combinações marca×tipo×subtipo×capacidade).
- **Bulk-import** da sua planilha (CSV) → `PriceQuote`. `catalog_version` bumpa com
  `PriceQuote`/`PriceConfig`.
- Liga o `resolve_price` no card de busca + estoque (a jusante de `assess_profitability`).

**Você roda:** migração; `load_brands --price-skeleton` (cria as categorias); importa a planilha; o
comprador preenche no admin.

**Verificação:** baseline de preço (1 linha por categoria) + conferência do painel. O `classify()`/
`assess_profitability` **não muda** (preço é aditivo).

**Rollback:** modelos/admin são aditivos (reverter migração os remove).

---

### 5.1 — Catálogo de tipos de preço (7 marcas principais) — para conferência

Extraído da sua planilha (`WTC_chip_price_sheet`). São as categorias que viram `PriceClass` — **cada
capacidade = uma linha = uma linha do `--price-skeleton`**. **Total: 269 categorias** (Samsung 82 ·
SK Hynix 74 · Micron 59 · SanDisk 16 · Nanya 14 · Kingston 12 · Toshiba/Kioxia 12).

**Convenção aplicada (OPÇÃO 1 — é assim que monto o `chip_type`):** para **DRAM discreta**
(LPDDR/DDR/GDDR) a planilha põe a família no "Tipo" e a geração no "Subtipo"; no banco a **geração vira
o `chip_type`** (subtype = espelho). Ex.: planilha `LPDDR / LPDDR4` → `chip_type="LPDDR4"`; `DDR / DDR3`
→ `"DDR3"`; `GDDR / GDDR5` → `"GDDR5"`. Memória **gerenciada** (eMMC/UFS/eMCP/uMCP) mantém o tipo, com
subtype = geração LPDDR (eMCP/uMCP) ou vazio (eMMC/UFS). **Capacidade (`capacity_token`):** eMMC/UFS/LPDDR
em **GB** (pacote); eMCP/uMCP em **NAND+RAM** (`16+2`); DDR/GDDR em **Gb** (die). *(A planilha já lista só
faixas rentáveis — sem LPDDR1/2, DDR1/2, GDDR2, DDR3<2Gb, eMMC<4GB etc. — então toda categoria aqui é, por
construção, RENTÁVEL.)*

#### Samsung (82)
| `chip_type` | `subtype` | `capacity_token` |
|---|---|---|
| eMMC | — | 4GB · 8GB · 16GB · 32GB · 64GB · 128GB · 256GB |
| UFS | — | 32GB · 64GB · 128GB · 256GB · 512GB · 1TB |
| eMCP | LPDDR3 | 8+1 · 16+1 · 16+2 · 32+2 · 32+3 · 64+3 · 64+4 |
| eMCP | LPDDR4 | 16+2 · 32+3 · 32+4 · 64+4 |
| eMCP | LPDDR4X | 32+3 · 64+4 · 128+4 · 128+6 · 128+8 |
| uMCP | LPDDR4X | 64+4 · 128+4 · 128+6 · 128+8 |
| uMCP | LPDDR5 | 128+6 · 128+8 · 256+8 |
| uMCP | LPDDR5X | 128+8 · 256+8 · 256+12 · 512+12 |
| LPDDR3 | espelho | 1GB · 2GB · 3GB · 4GB |
| LPDDR4 | espelho | 2GB · 3GB · 4GB · 6GB · 8GB |
| LPDDR4X | espelho | 2GB · 3GB · 4GB · 6GB · 8GB · 12GB · 16GB |
| LPDDR5 | espelho | 4GB · 6GB · 8GB · 12GB · 16GB |
| LPDDR5X | espelho | 6GB · 8GB · 12GB · 16GB |
| DDR3 | espelho | 2Gb · 4Gb · 8Gb |
| DDR3L | espelho | 2Gb · 4Gb · 8Gb |
| DDR4 | espelho | 4Gb · 8Gb · 16Gb |
| DDR5 | espelho | 16Gb · 24Gb |
| GDDR3 ¹ | espelho | 1Gb · 2Gb |
| GDDR5 ¹ | espelho | 4Gb · 8Gb |
| GDDR6 ¹ | espelho | 8Gb · 16Gb |

> ¹ As linhas GDDR da Samsung estão marcadas **"NO"** na coluna de preço da planilha. **Confirme:** GDDR
> Samsung deve virar categoria (com `active=False` até ter preço) ou ficar **de fora**?

#### SK Hynix (74)
| `chip_type` | `subtype` | `capacity_token` |
|---|---|---|
| eMMC | — | 4GB · 8GB · 16GB · 32GB · 64GB · 128GB |
| UFS | — | 32GB · 64GB · 128GB · 256GB · 512GB · 1TB |
| eMCP | LPDDR3 | 16+1 · 16+2 · 32+3 · 32+4 · 64+4 |
| eMCP | LPDDR4X | 32+3 · 64+4 · 64+6 · 128+6 · 128+8 |
| uMCP | LPDDR4X | 64+4 · 128+4 · 128+6 · 128+8 · 256+8 |
| uMCP | LPDDR5 | 128+8 · 256+8 · 256+12 · 512+12 · 512+16 |
| LPDDR3 | espelho | 1GB · 2GB · 3GB · 4GB |
| LPDDR4 | espelho | 2GB · 3GB · 4GB · 6GB · 8GB |
| LPDDR4X | espelho | 2GB · 3GB · 4GB · 6GB · 8GB |
| LPDDR5 | espelho | 4GB · 6GB · 8GB · 12GB · 16GB |
| LPDDR5X | espelho | 8GB · 12GB · 16GB |
| DDR3 | espelho | 2Gb · 4Gb · 8Gb |
| DDR3L | espelho | 2Gb · 4Gb · 8Gb |
| DDR4 | espelho | 4Gb · 8Gb · 16Gb · 32Gb · 64Gb |
| DDR5 | espelho | 16Gb · 24Gb · 32Gb |
| GDDR3 | espelho | 1Gb · 2Gb |
| GDDR5 | espelho | 4Gb · 8Gb |
| GDDR6 | espelho | 8Gb · 16Gb |

#### Micron (59)
| `chip_type` | `subtype` | `capacity_token` |
|---|---|---|
| eMMC | — | 4GB · 8GB · 16GB · 32GB · 64GB · 128GB · 256GB |
| UFS | — | 32GB · 64GB · 128GB · 256GB · 512GB |
| eMCP | LPDDR3 | 8+1 · 16+1 · 16+2 |
| eMCP | LPDDR4 | 16+2 · 32+3 · 64+4 · 128+4 |
| uMCP | LPDDR4 | 64+4 · 128+4 · 128+6 |
| uMCP | LPDDR5 | 128+6 · 128+8 · 256+8 · 256+12 |
| LPDDR4 | espelho | 2GB · 3GB · 4GB · 6GB · 8GB |
| LPDDR4X | espelho | 2GB · 3GB · 4GB · 6GB · 8GB |
| LPDDR5 | espelho | 4GB · 6GB · 8GB · 12GB · 16GB |
| DDR3 | espelho | 2Gb · 4Gb · 8Gb |
| DDR3L | espelho | 2Gb · 4Gb · 8Gb |
| DDR4 | espelho | 4Gb · 8Gb · 16Gb |
| DDR5 | espelho | 16Gb · 24Gb · 32Gb |
| GDDR5 | espelho | 4Gb · 8Gb |
| GDDR6 | espelho | 8Gb · 16Gb |
| GDDR6X | espelho | 8Gb · 16Gb |

#### Kingston (12)
| `chip_type` | `subtype` | `capacity_token` |
|---|---|---|
| eMMC | — | 4GB · 8GB · 16GB · 32GB · 64GB · 128GB |
| eMCP | LPDDR3 | 8+1 · 16+1 · 16+2 · 32+2 |
| eMCP | LPDDR4 | 32+3 · 64+4 |

#### Toshiba/Kioxia (12)
| `chip_type` | `subtype` | `capacity_token` |
|---|---|---|
| eMMC | — | 4GB · 8GB · 16GB · 32GB · 64GB · 128GB |
| UFS | — | 32GB · 64GB · 128GB · 256GB · 512GB · 1TB |

#### SanDisk (16)
| `chip_type` | `subtype` | `capacity_token` |
|---|---|---|
| eMMC | — | 4GB · 8GB · 16GB · 32GB · 64GB · 128GB |
| UFS | — | 32GB · 64GB · 128GB · 256GB · 512GB |
| eMCP | LPDDR3 | 8+1 · 16+1 · 16+2 |
| eMCP | LPDDR4 | 32+3 · 64+4 |

#### Nanya (14) — só DRAM
| `chip_type` | `subtype` | `capacity_token` |
|---|---|---|
| LPDDR4 | espelho | 2GB · 3GB · 4GB · 6GB · 8GB |
| DDR3 | espelho | 2Gb · 4Gb · 8Gb |
| DDR3L | espelho | 2Gb · 4Gb · 8Gb |
| DDR4 | espelho | 4Gb · 8Gb · 16Gb |

> **Como conferir:** cada célula de `capacity_token` é uma lista de categorias `PriceClass` daquela
> `(marca, chip_type, subtype)`. Se algum tipo/capacidade estiver faltando, errado ou a mais, me aponte
> a linha — eu corrijo antes de gerar o `--price-skeleton`. *(Marcas como GigaDevice/ESMT/Winbond/ISSI/
> PieceMakers caem em "Other" na sua planilha — fora desta tabela das 7 principais, mas o `--price-skeleton`
> as cobre quando você quiser.)*

---

## PASSO 6 — Pipeline de enriquecimento (futuro)

Quando houver volume. Acréscimos baratos sobre o que já existe (`PendingEntry`/`ChipSubmission`/
`SearchLog`/`UnknownChip`): `demand_score` (priorizar desconhecidos mais buscados × rentáveis),
nota/fonte obrigatória no confirmar/rejeitar. IA, se voltar, **só propõe para a fila** (nunca
autoritativa). Detalhe no §5 da proposta.

---

## Dependências (mini-mapa)

```
0 (baseline)
├─ 1A normalize_pn ─────────────┐
├─ 1B catalog_version ──┬─ 2 estoque
│                       ├─ 3 deploy_catalog + pghistory
│                       └─ 4 YAML (PieceMakers→…→Samsung) ─ 5 preço
└─ 1C trava + bulk + limpeza ── 3
                                                            6 enriquecimento (depois)
```

**Caminho mais curto até valor:** 0 → 1B → 1C → 1A (encanamento) já conserta as dores sentidas.
Depois 2 (estoque) e 4 (YAML, devagar). 5 (preço) fecha o que você vai construir em seguida.

---

## Princípio de "pronto" (Definition of Done por passo)

> **Convenção de testes do dono (2026-06-30):** testar **TUDO** durante e ao fim de cada passo —
> provar que nada quebrou, que os chips classificam certo e o output está correto **em TODAS as
> marcas** — e **entregar ao dono um conjunto de testes** para ele rodar no **frontend/terminal**.

Um passo só está **pronto** quando: (1) o dry-run foi revisado; (2) o `--commit` rodou no banco
certo (banner conferido); (3) **`characterize_baseline --diff` (regressão de TODAS as marcas) mostra
só o esperado**, + unit tests passando; (4) o rollback está testado (sabemos desfazer); (5) os docs
afetados (`CLAUDE.md`, bíblias) foram atualizados; (6) **entreguei ao dono os testes de frontend/
terminal** do passo. Sem os seis, não passamos para o próximo.

---

> **Resumo de uma linha:** *seis passos, de risco crescente, cada um shippable e provado pela rede
> de regressão. Começa pelo encanamento que conserta dor real (0→1), termina na alavanca grande
> (YAML, devagar) e no preço. Eu edito; você roda dry-run→commit no Render Shell; o engine não muda.*
