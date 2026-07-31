# CLAUDE.md — WhatTheChip (WTC)

> Onboarding para qualquer agente (Claude) que trabalhe neste repositório.
> Leia este arquivo inteiro antes de editar qualquer coisa. Ele substitui a
> necessidade de "reler o projeto" a cada conversa.
>
> **Como usar:** este arquivo cobre o essencial e universal. Para detalhes de
> um tópico específico, ele aponta para documentos profundos (seção
> *Documentação profunda*) — leia-os **sob demanda**, só quando a tarefa exigir.

---

## 1. Visão geral e contexto de negócio (o PORQUÊ)

**WhatTheChip** é uma aplicação Django que **classifica Part Numbers (PNs) de
chips de memória** para o mercado de **reciclagem / refurbishing** de
eletrônicos. Operado pela **eMiner (Paraguai)**. A ambição é ser o **"Google dos
chips"**: a base de classificação de chips mais ampla e precisa do mundo.

**Quem usa:** um **operador de bancada** que lê o código gravado a laser num chip
recuperado e digita na busca. O sistema devolve, em tempo real:

- **Tipo e specs** — eMCP / uMCP / eMMC / UFS / LPDDR / DDR / etc., capacidade,
  densidade, interface;
- **Destino comercial** — para qual caixa/bancada o chip vai, e se é
  **RENTÁVEL / NÃO RENTÁVEL / INDETERMINADO** (recondicionar vs. sucata/moagem).

Ou seja: o produto é ao mesmo tempo **classificador** e **ferramenta de triagem
de rentabilidade**.

### As duas fontes de conhecimento — e a prioridade entre elas

1. **Banco de PNs confirmados (`KnownPart`)** — a **fonte da verdade**. A meta do
   negócio é ter cada PN confirmado por fonte humana/oficial. PNs com
   `confidence` = `confirmed` ou `manual` **sempre vencem** qualquer decode.
2. **Gramática (`ChipFamily` + `DecodeMap`)** — a **válvula de escape** que cobre
   a cauda longa: decodifica posicionalmente qualquer PN que ainda **não** está
   confirmado no banco. É a prioridade de *cobertura* porque generaliza —
   corrigir a regra de uma família conserta **todos** os chips dela de uma vez,
   sem reenriquecer registro por registro.

> Mentalidade: **confirmar PNs no banco** é o objetivo; **a gramática segura o
> mundo** enquanto o banco não cobre tudo.

### Valor diferenciado

- **Crescimento colaborativo:** quando um PN não é encontrado, o usuário pode
  enviá-lo (com foto) via "Adicionar chip" (`ChipSubmission`) ou reportar erros
  (`CorrectionRequest`). Buscas e desconhecidos são logados (`SearchLog`,
  `UnknownChip`) para alimentar o backlog de enriquecimento.

---

## 2. Regras de ouro (leia sempre — quebrar isto quebra o produto)

1. **O banco de produção não está acessível ao agente.** Comandos que **alteram
   dados** (`migrate`, `load_brands --commit`, `import_*`, `merge_*`,
   `normalize_convention`, `purge_*`) devem ser **propostos e revisados**, mas **executados pelo
   usuário**. Claude **edita arquivos** (yaml/código); o usuário **roda** e confirma.
   1b. **O BANCO DE PRODUÇÃO É A FONTE DA VERDADE do catálogo VIVO — ele só cresce,
   nunca se reconstrói do git.** Os `known_parts` entram todo dia (busca do operador,
   `import_*`, enriquecimento FBGA via API, submissão+aprovação) e hoje passam de 6 mil.
   **Git/yamls = GRAMÁTICA + código** (Opção 2, jul/2026: os `known_parts` **saíram dos
   yamls** — vivem no banco, com revisão in-DB; ver regra 2b). Bootstrap de banco VAZIO
   usa `seed_known_parts.json` (dump curado ~600, só dev/CI, gap-fill, **nunca**
   re-sincronizado). O git **NÃO** é o catálogo (o banco tem 6 mil+). Consequências
   **invioláveis**: **(a)** deploy é **ADITIVO** — migrations aditivas + upsert de
   gramática/seed; **nunca** apaga/reconstrói `known_parts` (confirmei: nem
   `deploy_catalog` nem `purge_enriched` tocam confirmed/manual). **(b)** Migrar pra
   ambiente novo = **levar o banco existente adiante** (dump→restore, ou apontar o
   código novo ao banco atual) — **JAMAIS** "sobe banco vazio + `deploy_catalog`" (foi
   o que perdeu 5.900 `known_parts` no 1º deploy da escalabilidade, jul/2026: o prod
   novo só recebeu o seed dos yamls). **(c)** Antes de **qualquer** operação destrutiva
   (`purge_*`, `dedupe_*`, swap de banco): **backup fresco (Render Export) + revisão do
   dono**, obrigatório. **(d)** A rede é o **backup diário** (Render Export + PITR 3 dias);
   recuperação = `restore_known_parts <dump>.json` (gap-fill, provado em ~15 min). **(e)**
   Trava automática: rode **`guard_catalog`** depois de todo deploy (e/ou agendado) — ele
   guarda o high-water mark de `known_parts` e **falha com alarme** se a contagem
   despencar (>10%), pegando a perda silenciosa sem depender de ninguém perceber.
2. **Visibilidade ≠ autoridade.** Um `KnownPart` é *reconhecido* na camada 1
   (`known_exact=True`) quando tem **specs reais** (capacity/emcp_ram/emcp_nand/
   density) **ou** é `confirmed`/`manual` — gate `_USABLE`, equivalente fiel ao
   antigo `status="enriched"`. Mas *vencer a gramática* (autoridade) é só de
   `confirmed`/`manual`; `distributor`/`estimated` são reconhecidos e complementam
   decode incompleto, porém a **gramática completa prevalece** sobre eles. O campo
   `status` (raw/enriched/failed) foi **removido** (jun/2026). ⚠️ Não estreite o
   gate para "confidence ∈ confirmed/manual" — esconde os registros de
   distribuidor/estimado com specs e quebra o reconhecimento em massa. **(Opção 2:
   `_USABLE &= review_status='approved'` — só aprovado é visível; ver 2b.)**
   2b. **`known_parts` são NATIVOS DO BANCO com revisão in-DB (Opção 2, jul/2026).** A
   autoridade não mora mais no yaml — mora no banco. **Só `review_status='approved'` é
   visível/autoritativo no engine.** **TRAVA de escrita:** um AGENTE só grava known_part
   via **`submit_known_parts <arquivo> --commit`** (entra `submitted`, oculto) → o dono
   **aprova no admin** (fila `review_status`; **four-eyes**: quem submete ≠ quem aprova).
   É **PROIBIDO** escrever o banco direto (shell/ORM/admin ad-hoc) — o `submit` é o único
   caminho que passa pelo **portão**. A **gramática** continua via yaml/PR (`load_brands`).
   Pipelines de máquina (`import_*`/`enrich_*`/`bless_base`) gravam `approved` direto
   (fontes confiáveis). O **portão vive no MODELO** (`KnownPart.clean()`/`save()` +
   `CheckConstraint`s de confidence/review_status/four-eyes) → cobre **TODO** write, não
   só o yaml. Ver `chips/knowledge/convention.py` (normalização, fonte única).
3. **Cache do engine recarrega SOZINHO via `catalog_version` — não precisa reiniciar.** O engine
   usa `lru_cache` chaveado por `catalog_version`; `load_brands --commit` (e as migrações de dados)
   sobem a versão e todo worker recarrega famílias/mapas na próxima query (passo 1B). Isto
   SUBSTITUIU o antigo "reinicie o servidor após `populate_* --overwrite`".
4. **`DecodeMap` — não inverta `val_primary`/`val_secondary`.** Cada mapa tem seu
   padrão, **siga as linhas já existentes dele**: em mapas de **capacidade**,
   `val_primary` é a capacidade legível (ex.: `16GB`; em eMCP `val_primary`=NAND,
   `val_secondary`=RAM); em mapas de **densidade DRAM** (`DRAM_PC`/`DRAM_MOBILE`),
   `val_primary` é a densidade em **Gb** e `val_secondary` os **MB por die**.
   **Nunca** escreva "por die" em `val_secondary` — o engine anexa (senão vira
   "por die por die").
5. **Famílias KM com dígito na 3ª posição** (KM1/2/4/5/8…): `decode_gen_pos` tem
   que ser `None`. Caso contrário o engine produz texto Frankenstein
   ("tipo 'X' — consultar datasheet").
6. **Só `confidence` `confirmed`/`manual` vence a gramática.** Dados de
   `distributor` são frequentemente **errados** (capacidade/tipo de RAM) — só
   complementam quando a gramática está incompleta. Veja `_result_from_known`
   em `chips/engine.py`. (Os níveis de IA `ai_*` foram removidos com o Gemini.)
7. **Nunca delete famílias do `populate`.** Para desativar, use `active=False`
   no admin (ou no seed). Deletar quebra histórico e FKs.
8. **`purge_enriched` é destrutivo** (apaga KnownParts legados `ai_*`/`estimated`
   e a antiga fila raw, invisíveis ao engine pós-remoção do status). É **dry-run
   por padrão**; use `--commit` (grava backup JSON antes). É o passo de limpeza
   pós-migração `0012`.
9. **Nunca commite segredos.** `.env` é gitignored. Chaves vivem só no `.env`
   local e nas env vars do Render.
10. **Gemini foi REMOVIDO** (jun/2026). Não há mais fallback de IA nem
    enriquecimento automático: o núcleo é **banco confirmado + gramática**. As
    specs entram por confirmação manual nos yamls (`known_parts`) via `load_brands`,
    complementadas por `import_*` + admin.
11. **Rentabilidade tem fonte ÚNICA: `assess_profitability`.** Nunca reimplemente
    regra de rentabilidade em outro lugar. O `is_dead_by_generation` (engine) e o
    gateway do estoque (`estoque/views.py`) **derivam** dela — ver §4 e **`RENTABILIDADE.md`**.
12. **Tipo tem fonte ÚNICA: `chips/chip_types.py` (convenção OPÇÃO 1, jun/2026).** A
    geração da **DRAM discreta** vive no **`chip_type`** (`DDR3`, `LPDDR4X`, `GDDR5`,
    `SDRAM`…), espelhada no `subtype`; **gerenciada** (eMMC/UFS/eMCP/uMCP/NAND) mantém o
    `chip_type` (subtype = geração LPDDR / célula NAND / vazio). ❌ **NUNCA**
    `chip_type="RAM"` nem `"DDR"` genérico. Engine, gateway, profitability e o **portão do
    `load_brands`** (schema Pydantic) leem de `chip_types.py`; valide com `validate_convention`
    e migre legado com `normalize_convention` (reversível). Ver §6 (convenção completa) e `chips/chip_types.py`.

---

## 3. Stack tecnológica (o QUÊ)

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.11.9 (`runtime.txt`) |
| Framework | **Django 5.2.15 (LTS)** — pinado em `requirements*.txt`; roda em Python 3.11 |
| Banco | **PostgreSQL** (local e produção). Testes usam SQLite em memória |
| Front-end | **HTMX** + templates Django + **CSS puro** — **sem** React/SPA/build JS |
| Estáticos | **WhiteNoise** (`CompressedManifestStaticFilesStorage`) |
| Servidor prod | **gunicorn** (`Procfile`) |
| Deploy | **Render** (workspace **Hobby pago**: web + Postgres pagos, ~US$17/mês [jun/2026], 2 custom domains inclusos) — auto-deploy no push para `main` |
| Export | **openpyxl** (estoque → `.xlsx`) |
| Coleta (local) | `curl_cffi`, `playwright`, `pdfplumber`, Nexar/Octopart |

Dependências: **`requirements.txt`** (ambiente local completo, com scrapers) e
**`requirements-render.txt`** (produção — sem `curl_cffi`/`playwright`, com
`gunicorn`). Mantenha os dois em sincronia ao adicionar libs de runtime.

---

## 4. Arquitetura

### Apps Django

```
core/      → configuração do projeto (settings, urls, wsgi/asgi)
chips/     → CORAÇÃO: engine de classificação, modelos de dados, API de busca
estoque/   → inventário por lote (Lot/InventoryEntry); requer login + PAPEL
tenancy/   → multi-empresa (T1, jul/2026): Company/Branch/Membership, papéis
             admin/gerente/operador, escopo fail-closed — PLANO_MULTITENANT.md
pages/     → CMS simples de documentação (modelo Page, servido em /<slug>/)
```

### O engine de classificação — `chips/engine.py` (arquivo mais importante)

Ponto de entrada único: **`classify(pn)`**. Normaliza o PN e tenta, **em ordem**:

1. **Banco exato (registro utilizável)** — `KnownPart` com **specs reais** ou
   `confidence` ∈ (`confirmed`, `manual`) — gate `_USABLE` em `chips/engine.py`,
   substituto fiel do antigo `status="enriched"` (campo removido em jun/2026). Se
   achar, `_result_from_known` funde com a gramática. ⚠️ **Visibilidade ≠ autoridade:**
   - `confirmed`/`manual` → **banco vence** (verificado por humano);
   - `distributor`/`estimated` com specs → **reconhecidos** (`known_exact=True`),
     mas a **gramática completa vence** o valor (só complementam decode incompleto).
2. **Lookup FBGA** — se o PN casa o padrão FBGA (`^[A-Z][A-Z0-9]{4}$`, ex.: `D9VFC`),
   busca por `KnownPart.fbga_code` (também restrito a confirmed/manual). É o código
   que o operador lê no chip Micron. Desconhecido → enfileira em `UnknownChip`.
3. **Gramática da família** — `_result_from_family`: decode posicional via
   `ChipFamily` + `DecodeMap`. PNs não confirmados saem com `pn_not_in_db=True`.
   **Não há mais fila de revisão raw** (o `KnownPart status="raw"` foi removido):
   PNs buscados ficam em `SearchLog`; o que o operador tenta lançar e não é
   confirmado vai para `PendingEntry` (fila de conferência do estoque).
4. **Fuzzy matching** — sugestões por distância visual/Levenshtein para typo.

Além disso: **`assess_profitability(result)`** aplica as regras comerciais
(eMCP/uMCP, eMMC, UFS, LPDDR, DDR) e devolve `RENTÁVEL` / `NÃO RENTÁVEL` /
`INDETERMINADO`. Os limiares vivem em **`ProfitabilityConfig`** (singleton no
banco, editável no admin); `assess_profitability` é a **fonte única da verdade**
da rentabilidade.

**`is_dead_by_generation(result)`** (mesmo arquivo) é **derivado** — não tem lista
própria: `assess_profitability(_strip_capacity(result)) == "NÃO RENTÁVEL"`, ou seja,
"ainda é não rentável depois de remover os números de capacidade?". Detecta
rejeição que **independe da capacidade** (geração/era/tipo: LPDDR2-, DDR2-, MCP
legado, NOR/K5…) e fica sempre em sincronia com a rentabilidade. O **gateway de
triagem do estoque** (`estoque/views.py::_compute_gateway`) consome os dois:
rentabilidade decide APROVADO/REPROVADO, e `is_dead_by_generation` manda chip de
geração morta ao descarte **mesmo sem confirmação no banco** (rótulo distinto +
`RejectedEntry` de auditoria). Contrato completo: **`RENTABILIDADE.md`**.

### Modelos — `chips/models.py`

`Brand` → `ChipFamily` → `KnownPart`; `DecodeMap` (tabelas de decode reusáveis);
`Source`, `SearchLog`, `UnknownChip`, `CorrectionRequest`, `ChipSubmission`.

- **Ladder de confiança** (alta→baixa): `confirmed` > `manual` > `distributor` >
  `estimated`. Só `confirmed`/`manual` são **autoritativos** (vencem a gramática);
  os níveis de IA (`ai_*`) foram removidos junto com o Gemini.
- **Sem campo `status`:** o antigo `raw/enriched/failed` foi **removido** (jun/2026).
  Visibilidade no engine (camada 1) = ter **specs reais** OU ser `confirmed`/`manual`
  (gate `_USABLE`); **autoridade** sobre a gramática = só `confirmed`/`manual`.
- **`ChipFamily`** carrega a "anatomia" do PN: `decode_cap_pos/len/map`,
  `decode_gen_pos/map`, `decode_density_type` (`pc` usa `pn[3:5]`/`DRAM_PC`;
  `mobile` usa `pn[3]`/`DRAM_MOBILE` — **mutuamente exclusivos** com `cap_map`),
  `suffix_rules`, `pn_length`, `priority`, `active`, `is_emcp`.
- **`ChipFamily.doc_page`** liga a família a uma página de documentação (`pages.Page`).

**Três camadas — schema COMPARTILHADO, lógica GENÉRICA, dado POR-MARCA (não confundir).**
Uma dúvida recorrente: "cada marca tem um campo/mapa próprio de eMCP — isso não é má
prática?" Não. A separação é de propósito:
- **Campo do modelo (schema) = compartilhado.** Existe **um** `emcp_ram`, **um**
  `emcp_nand`, **um** `capacity` no `KnownPart`, usados por TODAS as marcas. Não há
  `emcp_ram_samsung`. (Um sistema de preço/rentabilidade lê esses campos normalizados
  e vale pra qualquer marca — igual `assess_profitability`.)
- **Lógica do engine = genérica.** Zero `if` por marca no decode: um caminho único lê
  `decode_cap_map`/`decode_gen_map` de qualquer família (o único trecho Samsung-específico
  é o fallback legado `EMCP_RAM_TYPES`, isolado e escopado).
- **Mapa de decode (`DecodeMap`) = por-marca, e OBRIGATÓRIO ser assim.** A nomenclatura
  de densidade de cada fabricante colide: o código `64` = **8GB** na SK Hynix mas **64GB**
  na Kingston; `32` = 4GB (Hynix) vs 32GB (Kingston). Fundir num mapa global daria erro
  catastrófico. Por isso `DecodeMap` é keyed `(map_name, char_key, brand)` — cada marca tem
  suas tabelas (prefixo `SAM_`/`HYX_`/… é só legibilidade; a FK `brand` é que separa). A
  exceção são `DRAM_PC`/`DRAM_MOBILE` (`brand=None`, globais) porque a JEDEC padronizou os
  códigos de DRAM — o único caso onde compartilhar é correto.
- **eMCP: RAM decodificada POR-FAMÍLIA (não por geração), NAND compartilhado** (padrão SK Hynix;
  Samsung alinhada jul/2026 — bug X6). O NAND é family/generation-independent (mesma chave = mesmo
  NAND em qualquer família: X6=32GB em KMD/KMG/KM4), então `SAM_EMCP_NAND` é compartilhado. A RAM
  NÃO: **famílias da MESMA geração divergem no mesmo código** (KMD e KM4 são ambos LPDDR4X mas X6 =
  3GB vs 2GB — a RAM depende da família, o `pn[2]`, não só da densidade). Logo, **um mapa de RAM por
  família = zero ambiguidade**. Dois formatos, conforme a estrutura da família:
  - **Famílias de LETRA** (KMD, KMG…): SPLIT — `decode_cap`→`SAM_EMCP_NAND` (NAND, `val_secondary`
    vazio) + `decode_gen`→`SAM_EMCP_RAM_<FAM>` (RAM "LPDDR<g> <cap>" embutida). Ex: `SAM_EMCP_RAM_KMD`, `SAM_EMCP_RAM_KMG`.
  - **Famílias de DÍGITO** (KM4, KM5…): a regra de ouro #5 proíbe `decode_gen` no dígito `pn[2]`,
    então COMBINADO — `decode_cap`→`SAM_EMCP_CAP_<FAM>` `[chave, NAND, RAM]`; o tipo vem do `subtype`.
    Ex: `SAM_EMCP_CAP_KM4`.
  Grammar EXATA nos dois: só chaves com fonte Tier-1 (código sem confirmação → RAM "não mapeada",
  NAND ainda decodifica quando compartilhado). Ver `chips/knowledge/samsung.yaml`.

### Camada web

- **`chips/views.py`** → `/chips/search/` (JSON), `/chips/decode/` (parcial HTMX),
  `/chips/stats/`, `/chips/report/`, `/chips/submit/`.
- **`estoque/views.py`** → CRUD de lotes em `/estoque/...`, preview/classify,
  export `.xlsx`. Tudo `@login_required`.
- **`pages/views.py`** + `core/urls.py` → home `/` e páginas `/<slug>/`
  (a rota slug é a **última** — captura tudo).
- **Auth:** login em `/login/`, sem cadastro público; `LOGIN_REDIRECT_URL=/estoque/`.

### Mapa de arquivos-chave

```
chips/engine.py          → classify(), gramática, profitability
chips/models.py          → todo o modelo de dados + glossário nos docstrings
chips/chip_types.py      → FONTE ÚNICA do vocabulário de tipos (chip_type/subtype): canonical_chip_type(), profit_family(), label_kind() — consumida por engine, gateway e validate/normalize_convention
chips/conventions.py     → canonical_gen(): fonte única do LABEL de geração (limpa o subtype; consumida pelo gateway)
chips/labels.py          → i18n: fonte única dos RÓTULOS traduzidos do engine (profitability_label, source_label) — canônico ≠ rótulo, ver I18N.md
locale/                  → catálogos .po/.mo (es, en, zh_Hans) — 4 idiomas ativos; cadeia de detecção: UserLanguage (tenancy) > cookie > Accept-Language > pt-br
chips/admin.py           → workflows de triagem (ChipFamily, KnownPart, correções)
chips/management/commands/→ pipeline de dados (populate/import/fix/collect) — §5
core/settings.py         → config; DATABASE_URL, NEXAR_*, etc.
core/settings_test.py    → SQLite em memória para testes
estoque/                 → inventário por lote
scripts/                 → coleta/enriquecimento OFFLINE (local-only) — §5
```

---

## 5. Comandos essenciais

> Rodar a partir da raiz do projeto, com o venv ativo e Postgres no ar.
> Comandos que **escrevem no banco** devem ser executados pelo **usuário**.

### Setup local

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt        # ambiente completo (com scrapers)
playwright install chromium            # só se for usar coleta
cp .env.example .env                   # se existir; senão crie o .env (ver §6)
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Testes (sempre com settings de teste — SQLite)

```bash
python manage.py test chips --settings=core.settings_test
```

Há também testes de regressão do engine na raiz (`test_samsung_*.py`,
`test_psg_*.py`) e em `scripts/` (`test_fase0/1/2.py`, `test_ui.py`) — cada um
sobe o Django e checa a saída de `classify(pn)`.

### Pipeline de dados — montar/atualizar a gramática e o banco

**Seguros para produção** (determinísticos, só DB; idempotentes; aceitam
`--dry-run` / `--overwrite`):

```bash
python manage.py load_brands --brand samsung   # carrega a GRAMÁTICA da marca (famílias+mapas) do chips/knowledge/<marca>.yaml (10 marcas). Valida c/ Pydantic (DATA CONTRACT: normaliza chip_type/subtype/interface, rejeita ativo-genérico), sobe catalog_version. Samsung 1ª: mapas GLOBAIS DRAM_PC/DRAM_MOBILE (brand=None). Dry-run padrão; --commit grava. ⚠ Opção 2 (jul/2026): o YAML tem SÓ GRAMÁTICA — os known_parts SAÍRAM (vivem no banco, regra 2b). load_brands é ADITIVO (upsert), nunca apaga known_parts existentes. NÃO resta populate_*/add_chip_families/fix_known_parts.
python manage.py submit_known_parts <arquivo>.yaml   # AUTORIDADE (Opção 2): submete known_parts pelo portão → review_status='submitted' (oculto) → dono aprova no admin. É o canal do chat de marca (substitui a autoria via yaml). --commit grava; --user <username> (four-eyes).
python manage.py import_micron_catalog *_full-catalog.csv   # CSVs Micron da raiz (pipeline de máquina → grava approved)
python manage.py import_samsung_psg --all                   # CSVs em data/psg/
python manage.py link_doc_pages / sync_index_page
python manage.py validate_convention       # read-only: aponta registros fora da convenção (chip_types.py)
python manage.py normalize_convention --commit   # migra chip_type legado ("RAM")→geração canônica (reversível via JSON)
python manage.py check_translations        # read-only: PORTÃO dos catálogos i18n (locale/*.po) — placeholders, HTML, glossário protegido, fuzzy/vazio, .mo fresco. Roda após TODA atualização de tradução (inclusive por IA) e na suíte. Ver I18N.md §7.
python manage.py guard_catalog             # TRIPWIRE: roda DEPOIS de todo deploy — falha com alarme se o nº de known_parts despencar (>10% do high-water). Read-only exceto o bump do high-water. `--reset` só após queda legítima e revisada. Ver regra de ouro §2.1b.
python manage.py restore_known_parts <dump>.json   # RECUPERAÇÃO: gap-fill de known_parts a partir de um dump/backup (cria só os que faltam, mapeia marca, religa família por prefixo; --commit). É o procedimento pós-incidente de perda.
python manage.py bootstrap_tenancy --company eMiner --admin <u> --manager <u> --operator <u>…   # backfill T1 (multi-empresa): cria a Company, dá papéis nominais, seeda o contador de lote, restringe o Django admin à plataforma (tira is_staff de não-super) e derruba sessões. Dry-run padrão; --commit grava (backup antes). Ver PLANO_MULTITENANT.md §16.
```

**Manutenção de estoque** (dry-run por padrão, reversíveis via JSON; rodar com
`DATABASE_URL` apontando ao Render):

```bash
python manage.py clean_lote --lot 39 --since 2026-06-16   # remove PNs novos NÃO confirmados (typos/contaminação); --keep, --commit, --revert
python manage.py bless_base --lot 39 --since 2026-06-16    # promove a base lançada antes do corte a KnownPart confidence=manual; --commit, --revert
python manage.py audit_targets --file correcoes.csv        # read-only: status (CONFIRMADO/GRAMATICA/NAO-VISIVEL/AUSENTE) de cada PN destino
python manage.py fix_pns --lot 39 --file correcoes.csv     # corrige PNs (merge/rename/refresh) via CSV errado,certo; reavalia estado a cada passo; --commit, --revert
```

> O bloqueio **"só confirmados"** em `estoque/views.py::add_chip` barra PN não
> confirmado: vai para `PendingEntry` (fila em `/admin/estoque/pendingentry/`,
> ações Aprovar/Reprovar) em vez do estoque. `bless_base` é a ponte para não
> travar reposição dos comuns. Cada KnownPart salvo dispara o bump de `catalog_version`
> (signal em `chips/apps.py`) → o engine recarrega sozinho, **sem reiniciar**.

**Somente local** (precisam de `playwright`/`curl_cffi`/`pdfplumber` ou chaves de
API — **não** rodam no Render: a imagem de produção (`requirements-render.txt`)
não inclui esses pacotes):

```bash
python scripts/collect_pns.py --brand Samsung      # coleta PNs crus (default: Samsung!)
python scripts/nexar_validate.py --validate <PN>   # Octopart/Nexar
python manage.py enrich_micron_fbga / lookup_fbga <FBGA> / fill_capacity_from_micron_api
```

Ordem típica (DB vazio → populado), encadeada pelo **`deploy_catalog`**: `migrate` →
`load_brands` (as 10 marcas — grava gramática + known_parts dos yamls) → `link_doc_pages`/
`sync_index_page` → `import_*` (PSG etc., complementam) → (coleta/enriquecimento local, se houver).
O `catalog_version` sobe no fim e o cache recarrega sozinho (sem reiniciar). **Nada de `populate_*`,
`add_chip_families` nem `fix_known_parts` — aposentados; o conhecimento é YAML.**

### Deploy (Render)

**Repositório:** `github.com/HandsonMatheus/whatthechip` (remote `origin`); **push em `main` →
deploy automático**. A raiz do repo **É** o projeto Django (sem subpasta `chipdocs/`; os comandos
não usam `cd`). Config vive no **dashboard do Render** (não há `render.yaml`):

- **Build Command:** `pip install -r requirements-render.txt && python manage.py migrate && python manage.py collectstatic --noinput`
- **Start:** `gunicorn core.wsgi --bind 0.0.0.0:$PORT` (`Procfile`).
- **Env vars lidas por `core/settings.py`:** `DATABASE_URL` (Render injeta ao conectar o Postgres) ·
  **`DJANGO_SECRET_KEY`** (obrigatória — o fallback é inseguro, só dev) · **`DEBUG=False`** (⚠ o
  default do código é `True`) · `RENDER_EXTERNAL_HOSTNAME` (automática, já em `ALLOWED_HOSTS`).
  `NEXAR_*` **não** é necessária no Render (só scripts locais).
- **Estáticos:** WhiteNoise (`CompressedManifestStaticFilesStorage`); `collectstatic` roda no build → `staticfiles/`. Sem nginx.
- **Migrations rodam no build.** A `chips/0016` (pghistory) cria tabelas de evento + gatilhos Postgres
  nas 4 tabelas de catálogo — **aditiva e segura, aplica sozinha** no deploy; histórico em `/admin/` → Pghistory → Events.
- **Armadilhas:** `DEBUG` default `True` (garanta `False`); **Django 6.0 exige Python 3.12+** — não
  suba o Django sem subir o `runtime.txt` (hoje 3.11.9) senão o build quebra; pin do Django idêntico
  em `requirements.txt` e `requirements-render.txt`; se estourar conexões Postgres, ative **PgBouncer**
  (§7); cold start no free; edição **RAW** no banco (sem subir `catalog_version`) só reflete após
  restart — mas `load_brands --commit` sobe a versão e reflete **na hora** (regra de ouro #3).
- **Sem shell interativo no Render:** comandos pontuais (`createsuperuser`, `deploy_catalog`, `import_*`)
  rodam **localmente apontando `DATABASE_URL` ao Render** — sempre com revisão do dono.

### Atualizar o catálogo em produção (o comando que se roda ao adicionar chips)

**Sempre que chips novos entram** (você ou o chat da marca editam `chips/knowledge/<marca>.yaml`), pra
levar do local até a produção — **por marca**, um `load_brands` pra cada marca tocada:

**1. Local — valida e testa:**

```bash
python manage.py load_brands --brand <marca>            # dry-run = o PORTÃO valida (nada grava)
python manage.py load_brands --brand <marca> --commit   # grava no banco LOCAL + sobe catalog_version
python manage.py runserver                              # confere os PNs na busca
```

**2. Produção — publica (2 passos):**

```bash
# a) versiona o yaml no repo (push em main → Render redeploy o CÓDIGO):
git add chips/knowledge/<marca>.yaml && git commit -m "catalog: <marca> +PNs" && git push origin main
# b) grava no banco de PROD, rodando LOCALMENTE com o DATABASE_URL do Render:
export DATABASE_URL="postgresql://…@…render.com:5432/…"   # pega no dashboard do Render — é SEGREDO
python manage.py load_brands --brand <marca> --commit
```

- **Reflete NA HORA, sem restart:** o `--commit` sobe o `catalog_version`; os workers de prod recarregam o catálogo na próxima busca (regra de ouro #3). Não precisa redeploy/restart pra o PN aparecer.
- **NÃO existe shell interativo do Render nesse fluxo** — o comando roda **no seu PC** apontando `DATABASE_URL` ao Postgres do Render. Esse `DATABASE_URL` tem a senha → é **segredo**: quem roda é o dono; o chat da marca **ensina o passo**, não usa a URL.
- **Só o passo (a) [push] não faz o PN aparecer em prod** — o redeploy do código roda `migrate`+`collectstatic`, mas **não** roda `load_brands`. É o passo (b) que popula o banco de prod. (Os dois: (a) versiona, (b) publica no banco.)
- **Pré-requisito (só na 1ª vez):** o sistema novo (branch `escalabilidade`) precisa **já estar no ar em prod** — é o primeiro deploy, com runbook próprio. Enquanto ele não acontece, o `load_brands` só roda no **local**; a prod ainda está no sistema antigo.
- **Micron:** a cobertura de massa dela vem também de `import_micron_catalog *_full-catalog.csv` (local-only, CSVs não versionados) — rode à parte, localmente, ao atualizar a Micron.

### Contrato de autoria (o que um chat de marca segue) — Opção 2

> **📖 GUIA COMPLETO OBRIGATÓRIO: [`AUTORIA.md`](AUTORIA.md).** É o passo a passo inteiro
> (as duas trilhas, o **teste-golden** por família, o **handshake** de rentabilidade, todas as
> travas e onde vivem no código, o checklist e a publicação). **Um chat de marca lê o `AUTORIA.md`
> inteiro ANTES de adicionar PNs.** Este §5 é o resumo executivo.

Um chat cuida de UMA marca e tem **DUAS trilhas**, que escrevem em lugares diferentes:

- **Trilha A — GRAMÁTICA** (famílias + mapas): edita `chips/knowledge/<marca>.yaml` → `load_brands`
  (dry-run = portão) → **commit no git / PR** → o dono roda `--commit`. Reconstruível, versionada.
- **Trilha B — KNOWN_PARTS** (autoridade): pesquisa Tier-1 → arquivo de submissão → o chat **valida**
  (`submit_known_parts <arquivo>` dry-run = portão) e **entrega o arquivo**; o **DONO roda o `--commit`**
  (`--user <id-do-chat>` ≠ dono, p/ four-eyes) → grava `submitted` (oculto) → **aprova no admin**. O chat
  NÃO roda o commit: sandbox isolado não alcança o banco do dono + regra de ouro #1. Known_part vive no banco.

> **⚠ TRAVA DE ESCRITA (inviolável).** Um agente **só** escreve catálogo por esses dois canais
> (yaml→`load_brands` p/ gramática; `submit_known_parts`→aprovação p/ known_parts). É **PROIBIDO**
> escrever o banco direto (shell/ORM/admin ad-hoc/import) — só esses canais passam pelo **portão**.
> As pipelines de máquina (`import_*`/`enrich_*`/`bless_base`) são operação do **dono**, não do chat.

**Papel e disciplina (o *porquê* do portão).** Você **pesquisa e confirma** PNs de UMA marca (a sua)
em fontes Tier-1 e escreve — você **não inventa**. Regras invioláveis:

- **Nunca adivinhe, estime ou infira** PN ou spec. Não confirmado em **Tier-1** (datasheet do fabricante = ouro; Octopart = secundário; distribuidor **NÃO** é Tier-1 — confunde Gb/GB)? Então **não decide**: não preenche `capacity`/`emcp_*`/`density` "no olho", não normaliza PN por semelhança, não completa chave de decode sem PN âncora.
- **Só a sua marca.** Não colete nem edite PNs/famílias/mapas de outra marca. **Nunca** toque em mapa GLOBAL de outra marca (`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung).
- **`known_parts` exige fonte Tier-1 citável na `notes`.** Sem fonte → não submete como `confirmed`/`manual` (o `submit` avisa, o revisor exige).
- **Não achou em Tier-1? PARE e sinalize.** Não adiciona "por garantia". PN **ambíguo** (conflito tipo×spec, tipo-lixo, módulo) **nunca** se resolve sozinho — pergunte ao dono.

> O portão (Pydantic + `clean()` do modelo) barra o erro de **convenção/estrutura**; estas regras
> barram o erro de **fato**. A revisão humana do dono (aprovação in-DB) é o filtro final de veracidade.

**Anatomia do yaml (SÓ GRAMÁTICA agora)** — 3 seções (`brand` e `families` obrigatórias; `maps` conforme a marca):

- `brand`: `name` (exato), `code` (curto único), `notes`.
- `maps`: tabelas `[chave, val_primary, val_secondary]` reusáveis (regra de primary/secondary por tipo — regra de ouro #4).
- `families`: a **GRAMÁTICA** posicional — `prefix`, `chip_type`/`subtype`/`interface`, `priority`, `pn_length`, `is_emcp`, `active`, `decode_cap_*`/`decode_gen_*`/`decode_density_type`, `suffix_rules`.
- **`known_parts` NÃO vai mais no yaml** (Opção 2) — vão pelo `submit_known_parts` (arquivo de submissão de mesma forma: `part_number` + specs + `confidence` + `notes` com a fonte Tier-1).

**Convenção que o portão força** (idêntica a §6): `chip_type` canônico (geração pra DRAM discreta;
❌ nunca `RAM`/`DDR` genérico em família **ativa** → rejeita); `subtype` = só geração/célula (sem
Mobile/Multi-Channel/+eMMC/densidade/tensão/largura); `interface` = largura (`x8`/`x16`) ou vazio;
`emcp_ram` = `'LPDDR{n} {cap}GB'` (tipo **antes**).

**Checklist de handoff (rode LOCAL; NÃO toque em prod — quem publica é o dono):**
- [ ] Só mexi na MINHA marca (yaml e/ou submissão); não toquei em mapa global de outra.
- [ ] Nada inventado/estimado; todo known_part com **fonte Tier-1 na `notes`**; ambíguo → perguntei.
- [ ] Gramática: `load_brands --brand X` (dry-run/portão) passou · nenhuma família com `decode_density_type` **e** `decode_cap_map` juntos · KM com dígito na 3ª pos → `decode_gen_pos: null`.
- [ ] **Família nova → GOLDEN (OBRIGATÓRIO, testado):** entreguei PNs âncora + saída esperada (tipo/subtipo/capacidade/**rentabilidade**) no `_<MARCA>_GOLDEN` do `chips/tests.py`. É a prova de que a família nova decodifica certo (o `characterize` não valida PN novo). ⚠ `GoldenObrigatorioTests` **FALHA** se família de prefixo novo não tiver âncora — não é opcional.
- [ ] **Tipo novo → HANDSHAKE:** o `RentabilidadeHandshakeTests` passa (declarei a regra de rentabilidade do tipo em `chip_types.py`/`assess_profitability`; nenhum tipo comercial em INDETERMINADO).
- [ ] Known_parts: `submit_known_parts <arq>` (dry-run = portão) passou; cada um com **fonte Tier-1 na `notes`**; entrego o **arquivo validado** ao dono (ele roda o `--commit` + aprova — sandbox isolado + regra #1).
- [ ] **A suíte inteira verde:** `python manage.py test chips estoque --settings=core.settings_test` (roda golden + handshake + portão) · `characterize_baseline --diff` mostrou **só** o pretendido.
- [ ] Entreguei as saídas ao dono. **Banco local atualizado** (migrate + gramática em dia) antes de testar.

**Publicar (o DONO faz, apontando `DATABASE_URL` ao prod — é segredo):** gramática = `git push` (versiona) **+**
`load_brands --brand X --commit` (grava no banco de prod, aditivo, sobe `catalog_version`); known_parts =
`submit_known_parts --commit` + **aprovar no admin**. Depois: `guard_catalog`. Reflete na hora, sem restart.

**Marca nova (11ª+):** basta criar `chips/knowledge/<marca>.yaml` (só gramática) — o `deploy_catalog`
**descobre sozinho** (glob). Opcional: um `<marca>.md` (camada humana). Portão, contrato e engine já valem pra ela.

---

## 6. Convenções e regras do projeto

- **Idioma:** código, docstrings, comentários, `verbose_name` e mensagens em
  **português**; nomes de comandos/campos/termos de domínio em inglês como já
  estão. Mantenha o padrão existente.
- **Variáveis de ambiente** (lidas em `core/settings.py` via `python-dotenv`):
  `DJANGO_SECRET_KEY`, `DEBUG`, `DATABASE_URL` (ou `DB_NAME/USER/PASSWORD/HOST/PORT`),
  `RENDER_EXTERNAL_HOSTNAME`,
  `NEXAR_CLIENT_ID`/`NEXAR_CLIENT_SECRET`.
- **Migrations:** toda mudança de modelo gera `makemigrations` + `migrate`.
  Nunca edite migrations já aplicadas em produção; crie uma nova.
- **Mudou a gramática (`load_brands --commit` ou admin)?** O `catalog_version` sobe
  (loader bumpa explícito; admin via signal `post_save`) e o engine recarrega sozinho —
  **sem reiniciar** (regra de ouro #3).
- **Estilo de código:** siga os padrões já presentes nos arquivos vizinhos
  (PEP 8, docstrings explicativos com o *porquê*). Não recrie um "linter humano"
  aqui — espelhe o código existente.
- **Hierarquia de fontes (imutável)** ao gravar dados: fabricante/datasheet >
  Octopart/Nexar > distribuidor B2B rastreável > Preduo > IA > especulação.
  Importadores **nunca** rebaixam um registro `confirmed`/`manual`.
- **Não confie em dado de distribuidor ou IA** sem verificação por datasheet/Octopart
  (confundem Gb/GB, invertem primary/secondary, alucinam capacidade).
- **Tenancy (T1–T4, jul/2026 — contrato: PRECIFICACAO §10; execução/bíblia: PLANO_MULTITENANT.md).**
  Catálogo = GLOBAL; estoque = POR-EMPRESA **(T3: Lot/Entry/Pending/Rejected têm
  `company` NOT NULL, `objects` = `CompanyScopedManager` fail-closed — mas o
  `Meta.default_manager_name` é o CRU `all_companies`: a validação de UniqueConstraint
  do Django 5 e o admin usam `_default_manager`, que não pode filtrar (bug de prod
  2026-07-09) — escopo nas views é sempre EXPLÍCITO via `Model.objects`; numeração
  `unique (company, number)`; T4: RLS+FORCE no Postgres — policies leem os GUCs
  `app.company_id`/`app.platform` que o TenancyMiddleware emite transaction-local;
  `manage.py shell` em tabela de estoque devolve 0 linhas sem `company_scope(...)` —
  é o fail-closed do banco, não bug)**. **Toda tabela nova exige decisão explícita de tenancy** —
  o teste `TenancyDeclarationTests` (estoque/tests.py) FALHA se um modelo novo não estiver
  na lista GLOBAL nem escopado. View de estoque usa `@role_required('operator'|'manager')`
  (`tenancy/access.py`) — nunca só `@login_required`; esconder botão no template NUNCA é a
  única barreira. Papel vem do `Membership` (operador < gerente < admin); plataforma =
  `is_superuser` (Django admin via `all_companies` — `PlatformScopedAdmin`), que navega o
  app com Membership real (SEM bypass nos gates). Fora de request o escopo é explícito:
  `with company_scope(company):` ou, em comando, `--company <slug>` +
  `scope_command_to_company()` (auto-resolve com UMA empresa ativa; 2+ exige o slug).
  O lote é ativo da EMPRESA (não do usuário): `Lot.operator` = "quem abriu".
- **Part-name da API Micron FBGA não é fonte para tipo de RAM** (BUG-8, 2026-06-19).
  A API retorna strings como `"MLC EMMC/LPDDR2 72G VFBGA"` que podem pertencer a
  famílias relacionadas com RAM diferente. Para MT29TZZZ, a API dizia "LPDDR2" mas
  a família é LPDDR3 (MT29PZZZ é que é LPDDR2). Regra: o **prefixo do PN** define
  o tipo de RAM (`_infer_lpddr_gen` em `fill_capacity_from_micron_api.py`); para
  confirmar, use **datasheet oficial** ou **DigiKey** — nunca o campo `part-name` da API.

### Convenção de campos → label da caixa física (estoque)

> **⚠ CONVENÇÃO OPÇÃO 1 (endurecida 2026-06-29) — FONTE ÚNICA DE TIPOS:
> `chips/chip_types.py`.** Para **DRAM discreta** (DDR/LPDDR/GDDR/SDRAM/RDRAM) a
> **GERAÇÃO vai no `chip_type`** (`DDR3`, `LPDDR4X`, `GDDR5`, `SDRAM`…), **espelhada no
> `subtype`** — ❌ **NUNCA** `chip_type="RAM"` nem `"DDR"` genérico. Memória **gerenciada**
> (eMMC/UFS/eMCP/uMCP/NAND) mantém o `chip_type`. Razão: o `chip_type` é o **único** campo
> de tipo que o `InventoryEntry` persiste — por isso ele carrega a geração. Validar com
> `python manage.py validate_convention`; migrar legado com `normalize_convention`.

O gateway `estoque/views.py::_compute_destination` escolhe o branch via
`chip_types.py::label_kind(canonical_chip_type(chip_type, subtype))` e monta o label com
os campos abaixo. **Alimente os campos certos; não mexa no gateway.** Modelo: `JW464` (`SLC NAND 512MB`).

| Tipo | `chip_type` | `subtype` | Capacidade | Resultado |
|---|---|---|---|---|
| NAND raw | `"NAND Flash"` | célula: `"SLC NAND"` / `"MLC NAND"` / `"TLC NAND"` | `capacity` em bytes (`"512MB"`, `"4GB"`) | `"SLC NAND 512MB"` |
| eMMC | `"eMMC"` | — | `capacity` em GB (`"16GB"`) | `"EMMC16GB"` |
| eMCP | `"eMCP"` | geração RAM (`"LPDDR3"`) | `emcp_nand` = `"16GB"`; `emcp_ram` = `"LPDDR3 1GB"` (tipo + GB) | `"EMCP16+1"` |
| uMCP | `"uMCP"` | geração RAM | `emcp_nand`, `emcp_ram` | `"UMCP…+…"` |
| UFS | `"UFS"` | — | `capacity` em GB | `"UFS128GB"` |
| DDR/GDDR/SDRAM/RDRAM | **a geração** `"DDR3"`/`"DDR4"`/`"GDDR5"`/`"SDRAM"`… | espelha o `chip_type` | `density_gbit` = die em Gb | `"DDR3+8G"` |
| LPDDR avulso | **a geração** `"LPDDR4"`/`"LPDDR4X"`/`"LPDDR5"`… | espelha o `chip_type` | `capacity` = pacote em GB | `"LPDDR4+4GB"` |

**Regras absolutas de campo:**
- `subtype` = **SOMENTE** célula (NAND) ou geração (RAM) — nunca densidade, bus width, voltagem, "Mobile", "Multi-Channel", "paralela industrial"
- `interface` = bus width (`"x8"`, `"x16"`) para DDR/GDDR; vazio para LPDDR eMCP
- `emcp_ram` = `"LPDDR{n} {cap}GB"` — tipo **antes** da capacidade (ex.: `"LPDDR3 1GB"`, nunca `"1GB LPDDR3"`)
- `density_gbit` é o campo modelo do `KnownPart` para densidade DDR (em Gb); `dram_density` é campo calculado pelo engine — não confundir
- Tudo que sobrar (temperatura, organização, variante, ECC) vai no `tip`/`notes`

Fonte única em código: **`chips/chip_types.py`** (a convenção completa está resumida acima). Específico da Micron: **`MICRON.md`**.

> **O estoque é um SNAPSHOT — gravado do classify do SERVIDOR (jun/2026).** A entrada
> `InventoryEntry` vem de `estoque/views.py::_snapshot(server_result)`, **nunca do POST do
> cliente** (era bug: capacidade DDR virava `None`). Derivados: `capacity` por
> `_size_for_entry` (DDR/GDDR/SDRAM/RDRAM = **densidade em Gbit `2G`/`4G`/`8G`**, igual à
> caixa; LPDDR/eMMC/UFS = pacote em **GB**; eMCP/uMCP usam `emcp_*`; ignora a string
> `'None'`; **case-sensitive `Gb`≠`GB`**); `interface` por `_clean_interface` (tira a
> geração espelhada — só bus width/versão). O `export_xls` converte o timestamp p/ Brasília
> (`timezone.localtime`). **Como é snapshot, defasa quando o engine melhora** → re-snapshot
> o lote (backfill: re-rodar `_snapshot` sobre as entradas). Solução definitiva = cálculo on-read.

> **Label protegido por `canonical_gen` (2026-06-19) — FONTE ÚNICA da convenção.**
> O label da caixa é montado em `estoque/views.py::_compute_destination`, que passa o
> `subtype` por `chips/conventions.py::canonical_gen()`. Ela reduz qualquer subtype ao
> token canônico de geração/célula por **whitelist** (`"LPDDR4 Mobile"`→`"LPDDR4"`,
> `"DDR3 SDRAM"`→`"DDR3"`, `"SLC NAND paralela industrial"`→`"SLC NAND"`), cobrindo
> **todas as marcas** e os **dois caminhos** (banco confirmado e gramática),
> retroativamente, sem reescrever o banco — mesma filosofia de fonte única do
> `assess_profitability` (Regra de ouro #11). **Continue escrevendo `subtype` limpo no
> write-time** (populate/import/fix): `canonical_gen` é fail-open (token não reconhecido
> passa intacto) e o subtype cru ainda aparece no card de busca.

### Convenção i18n — TODA string nova nasce no lugar certo (inviolável)

> A plataforma é multilíngue (pt-br/es/en/zh-hans — I18N.md). String "esquecida"
> em PT não é detalhe: é bug de produto para 3 dos 4 públicos. A convenção tem
> **portões automáticos** — quebrá-la deixa a suíte vermelha, não é opcional.

| Onde a string nasce | Como nasce | Portão que pega |
|---|---|---|
| Template (HTML/JS inline) | `{% trans %}` / `{% blocktrans trimmed %}` | `check_translations` (entrada vazia) + smoke 4 idiomas |
| View (mensagem/fragmento p/ usuário) | `gettext` (eager) | idem |
| **Choices de modelo exibido a usuário** (`get_FOO_display`) | `gettext_lazy` nos RÓTULOS (valores = chave, nunca traduz) | `I18nChoicesDeclarationTests` — choices sem `_lazy` **e** sem declaração explícita = suíte vermelha |
| JS estático (`static/js/*.js`) | `gettext('…')` + catálogo `djangojs` (rota `i18n/js/`) | `check_translations` |
| Conteúdo editorial (CMS) | arquivo `_content/<slug>.<código>.html` (fallback pt-br automático); metadados via chave `i18n` do `import_content` | teste de home multilíngue + fallback |
| Valor CANÔNICO do engine / string PERSISTIDA (`rejection_reason`, label de caixa, snapshot, export) | **NUNCA traduz** — rótulo só na exibição via `chips/labels.py` | `test_valor_canonico_nunca_muda` + suíte |
| Django admin | **fixo em pt-br** (superfície de plataforma — decisão 2026-07-08); `verbose_name` fica PT | `AdminPlataformaPtBrTests` |

Regra de bolso: **lógica compara CHAVE; usuário vê RÓTULO; banco guarda CANÔNICO.**
**Criando tela/página/string nova? O contrato de autoria é o `MULTILANGUAGE.md` §7**
(“toda string nasce marcada E traduzida na MESMA entrega” + tabela faça/nunca + fluxo
+ 6 proibições). Processo profundo, rotina de tradução por IA e glossário: **`I18N.md`** (§5–§7).

---

## 7. Armadilhas comuns (o que costuma quebrar)

- **Cache velho:** uma escrita em massa na gramática que **não** sobe o `catalog_version`
  → o engine serve famílias/mapas antigos. `load_brands --commit` bumpa explícito e o admin
  bumpa via signal, então na prática só quebra se alguém gravar em bulk por fora. (Regra de ouro #3.)
- **Registro não autoritativo:** PN com dado certo mas `confidence` fora de
  (`confirmed`, `manual`) → o engine não o usa como autoridade (cai na gramática).
  Promova a `confirmed`/`manual`. (Regra de ouro #2.)
- **`known_part` do yaml que não "pega":** preencher capacidade sem `confidence: confirmed`/`manual`
  deixa o registro perdendo para a gramática (só complementa decode incompleto). Ponha
  `confidence: confirmed` com fonte Tier-1 na `notes`. (Antes o sintoma era `status="raw"`; o campo
  `status` foi removido.)
- **Unidade Micron (Gb × GB):** no nome de peça MTFC, "G" é **Gbit**, não GB
  (64G = 8GB); densidade de eMCP/uMCP é total do pacote. Por isso
  `import_micron_catalog` **deixa `capacity=""`** para eMCP/uMCP (o engine decodifica).
  Burlar isso gera o bug clássico "544Gb → 68GB".
- **`decode_density_type` + `decode_cap_map` juntos** na mesma família → conflito.
  São mutuamente exclusivos (K4F/K4U/K3U devem ter `decode_density_type=""`).
- **Limite de conexões do Postgres** depende do tier da instância paga (não é
  mais o free de ~10). Se aparecer "too many connections", ative o **connection
  pooling (PgBouncer)** nativo do Render antes de pensar em subir o tier.
- **Versão do Django travada em 5.2.x (LTS) + Python 3.11.** O Django 6.0 exige
  **Python 3.12+**; **não suba o Django para 6.0 sem subir o `runtime.txt`** para
  3.12 — senão o build no Render quebra. (Se o ambiente local tiver 6.0 instalado,
  rode `pip install -r requirements.txt` para alinhar em 5.2.15.)
- **Scrapers são frágeis e local-only:** preduo/glochip estão atrás de Cloudflare
  (exigem Playwright); `--brand` default é "Samsung" em `collect_pns`
  — fácil raspar a marca errada por omissão.
- **`confidence="estimated"`** (ex.: Wayback) fica oculto na UI de triagem até
  confirmação manual.
- **`enrich_micron_fbga.py` NÃO salva `emcp_ram`/`emcp_nand`.** Ele só cria o
  KnownPart com FBGA + PN completo + `subtype` copiado do base. Os campos de
  capacidade ficam vazios até o `fill_capacity_from_micron_api` rodar. Com DB
  vazio para `emcp_ram`, a gramática vence no engine — por isso erros no decode
  map (ex.: BUG-8) aparecem mesmo em chips com KnownPart `confidence=confirmed`.
  Depois de `fill_capacity_from_micron_api`, o DB tem valores explícitos e vence.
- **FBGA duplicado (PN raw vs normalizado):** `enrich_micron_fbga.py` salva o PN no
  formato raw da API (ex.: `"MT29C4G48MAZAPAKD-5 IT"` com hífen/espaço); `fix_known_parts`
  cria o PN normalizado (`"MT29C4G48MAZAPAKD5IT"`). Dois registros, mesmo `fbga_code`.
  O engine (`chips/engine.py`, handler `MultipleObjectsReturned`) prefere o registro
  com `chip_type` preenchido — órfãos com `chip_type=""` são ignorados automaticamente.
  Limpeza via shell é opcional (não urgente): `KnownPart.objects.filter(part_number__contains="-", chip_type="").delete()`.
- **Label "NAND" sem info:** antes de 2026-06-19, o branch NAND do gateway usava
  `_extract_gb` (só lê GB) e `chip_type` ("NAND Flash") → resultava em `"NAND"` para
  chips < 1GB. Corrigido em `estoque/views.py`: agora usa `subtype` + `_format_cap`
  (lê MB e GB). O `subtype` deve ser `"SLC NAND"` / `"MLC NAND"` / `"TLC NAND"`.
- **`subtype` verboso no label da caixa — mitigado por `canonical_gen` (2026-06-19):**
  o gateway (`_compute_destination`) normaliza o `subtype` via
  `chips/conventions.py::canonical_gen()` ao montar o label, então qualificadores
  (`"paralela industrial"`, `"Multi-Channel"`, `"Mobile"`, `"PC DRAM"`, `"8GB"`, `"x16"`)
  **não truncam mais a etiqueta**. Ainda assim, escreva `subtype` = 1–3 palavras (só o
  tipo) no write-time: a normalização é fail-open e o subtype cru aparece no card de busca.
- **`is_dead_by_generation` falso para LPDDR2 com decode DRAM_MOBILE (2026-06-19):**
  `_strip_capacity` usa `re.I` e remove todos os padrões `\d+(GB|MB)` de `dram_density`
  — inclusive `"8Gb"` (b minúsculo). Ex.: `"8Gb = 1GB por die [~]"` → `" =  por die [~]"`.
  O bloco LPDDR standalone checava `cap_gb is None → INDETERMINADO` **antes** de
  `lpddr_gen < lpddr_min_gen`, então `is_dead_by_generation` retornava `False` para
  LPDDR2 cujo único campo de capacidade era `dram_density`. Efeito: chip LPDDR2
  não confirmado caía na **FILA** em vez do descarte automático. O bloco eMCP tinha
  fix equivalente (2026-05-27) mas o LPDDR standalone não. **Corrigido em
  `chips/engine.py` (2026-06-19):** verificação de geração movida para antes de
  `_extract_gib`. Chips históricos afetados: K3PE, K4P, K4E8E. Sintoma que revelou:
  K3PE0E000E (LPDDR2 2GB) ia para a FILA apesar de `profitable="NÃO RENTÁVEL"`.
- **GDDR entra no bloco DDR via substring mas lookbehind bloqueia decode (2026-06-20):**
  `"DDR" in combined` é `True` para "GDDR2" (substring). `_ddr_generation` usa
  `(?<![A-Z])DDR(\d+)?` — lookbehind falha quando 'G' precede 'DDR' → `ddr_gen=None` →
  INDETERMINADO. **Corrigido em `chips/engine.py` (2026-06-20):** bloco GDDR próprio
  adicionado **antes** do bloco DDR. Extrai geração via `GDDR(\d+)`; geração ausente ou
  `< cfg.gddr_min_gen` (default 3) → NÃO RENTÁVEL. Campo `gddr_min_gen` adicionado ao
  `ProfitabilityConfig` em `chips/models.py` (requer `makemigrations` + `migrate`).
  Chip revelador: K4N51163Q7 (GDDR2) retornava INDETERMINADO.
- **ePoP retorna INDETERMINADO quando gramática não decodifica capacidade (2026-06-20):**
  KAT (ePoP, Samsung ~2012-2015): `is_emcp=True` → bloco eMCP. `emcp_ram` recebe
  placeholder "tipo 'T' — consultar datasheet ⚠ cap. não mapeada" (string não-vazia,
  sem GB) → `_extract_gib` = None → `ram_gb is None` → INDETERMINADO. Decisão de
  negócio (2026-06-20): ePoP é **sempre NÃO RENTÁVEL** (memória empilhada em SoC,
  sem mercado B2B de reciclagem). **Corrigido:** `"epop"` adicionado ao bloco de tipos
  sempre NÃO RENTÁVEL em `assess_profitability` (antes do bloco eMCP) → intercepta
  ePoP antes de chegar ao guard de capacidade.
- **Padrão recorrente — INDETERMINADO em vez de NÃO RENTÁVEL para chips legados:**
  Chips reprovados **por tipo ou geração** (não por capacidade) retornam INDETERMINADO
  quando `assess_profitability` chega a um bloco que exige dados de capacidade e não
  os encontra. Instâncias corrigidas: LPDDR2 com DRAM_MOBILE (2026-06-19), GDDR2
  (2026-06-20), ePoP (2026-06-20), **eMCP com geração de RAM desconhecida
  (2026-07-09, JW500/MT29C "Mobile DDR" 512MB)** — o bail `lpddr_gen is None`
  vinha ANTES dos limiares de RAM/NAND, que não dependem de geração; agora a
  capacidade reprova primeiro e geração-desconhecida só segura o veredito
  quando as capacidades passam nos mínimos. **Regra de prevenção:** ao adicionar um novo
  chip_type ao sistema, pergunte — "este tipo é NÃO RENTÁVEL independente de
  capacidade?". Se sim → bloco de tipos no topo de `assess_profitability`. Se é
  NÃO RENTÁVEL por geração → verificar geração ANTES de `_extract_gib` no bloco —
  e limiares de CAPACIDADE nunca podem ficar atrás de um bail por dado ausente
  de que eles não precisam.
- **`_CAP_RE` não suportava capacidades decimais → RENTÁVEL falso (2026-06-27):**
  `_CAP_RE = re.compile(r"(\d+)\s*([TGMK])B")` — `\d+` sem `(?:\.\d+)?`. Para
  `"1.5GB"`: re.search encontra `"5GB"` na posição 2 (o "." não é dígito, a engine
  avança e casa `"5"` + `"GB"`) → retorna **5.0 GB** em vez de 1.5 GB. No bloco LPDDR,
  5.0 >= threshold 2.0 → **RENTÁVEL** (errado). Chip revelador: K4E2E304EA (LPDDR3
  1.5GB Samsung). **Corrigido:** `_CAP_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([TGMK])B")`.
  `_GBIT_RE` e `_CAP_NUM_RE` já tinham `(?:\.\d+)?` — só `_CAP_RE` estava vulnerável.
- **Capacidade Micron LPDDR (MT5x) — o `D{N}` do PN NÃO multiplica densidade (2026-06-27):**
  A fórmula oficial é `depth × width ÷ 8 = GB` — `depth × width` já é o dispositivo INTEIRO; o
  sufixo `D2`/`D4`/`D8` é dies/canais no encapsulamento. O pipeline antigo (`fill_mt53b_density.py`,
  REMOVIDO) fazia `× dies` e inflou ×N: `MT53E768M32D4` virou 12GB (24Gb×4) em vez de 3GB. Hoje o
  engine decodifica via `ChipFamily.decode_density_type='micron'` (depth×width, sem dies). **Nomenclatura
  oficial Micron: "52"=LPDDR3, "53"=LPDDR4 (MT53E=LPDDR4X) — `MT52L` é LPDDR3, não LPDDR4.** Regra
  geral que isto ensinou: num FBGA `confidence="confirmed"`, o **ouro é só a IDENTIDADE** (PN↔FBGA da
  API); `capacity`/`subtype`/`density` são calculados localmente e podem estar errados — **atestar
  sempre em tier-1** (datasheet/DigiKey), nunca assumir. Ferramentas: `fix_micron_lpddr_specs` (normaliza
  specs MT5x, guard de eMCP), `fix_micron_capacity --family lpddr` (capacity). Detalhes: **`MICRON.md`**.
- **Densidade DDR fora do lugar (`capacity='2G'` + `density_gbit` vazio) → chip
  invisível ao PREÇO (2026-07-11, lote 40):** a convenção (§6) manda densidade de
  DDR/GDDR/SDRAM/RDRAM em `density_gbit` (banco) / `dram_density` (engine), mas
  (a) as famílias DDR de **SK Hynix/Nanya** decodificam bytes-por-die no
  `capacity` ('256MB') sem `decode_density_type`, e (b) o `bless_base` promovia
  snapshot com `capacity='2G'` (Gbit da caixa) sem density — nos dois casos
  `density_gbit_num` (F0) ficava None e o pricing dava NO_KEY. **Corrigido em
  camadas:** regra 4 do `apply_kp_convention` (auto-preenche `density_gbit` no
  save — TODO caminho de escrita; fill-only, `'GB'` nunca entra: Gb≠GB),
  `_known_dram_density` no engine (serve o `density_gbit` também nos caminhos
  known-SEM-família), `validate_convention` reporta ("densidade fora do lugar") +
  `normalize_convention` backfilla o legado (reversível), `load_brands` AVISA
  família DDR-kind sem decode de densidade, e o pricing mantém fallback de
  leitura (`_gbit_from_capacity`). **Reforma dos yamls DESNECESSÁRIA (dono
  delegou e foi resolvido no engine, 2026-07-11):** as posições de densidade
  variam por marca (o decode `pc` fixo em `pn[3:5]` só serve à Samsung), então
  em vez de operar ~28 famílias, `_result_from_family` DERIVA o `dram_density`
  de família DDR-kind com cap_map per-die (`'256MB'` → `2Gb = 256MB por die
  [✓]`, MB×8÷1024) — todas as marcas de uma vez; 14 goldens atualizados com a
  densidade nova (aritmética conferida). `GDDR5X` entrou no vocabulário
  (`chip_types.py`) — antes o `normalize_convention` o dobrava pra `GDDR`
  genérico e MUDAVA a triagem. O aviso do `load_brands` agora só dispara para
  família DDR-kind **sem NENHUMA fonte** (nem density_type nem cap_map) —
  censo 2026-07-11: Samsung K4J/K4N/K4Z e SK Hynix H5RS (GDDR legadas),
  GigaDevice GDQ, Micron MT40A/MT41K, e as famílias MAGRAS de Nanya
  (NT5AD/NT5CC/NT5PA) e PieceMakers (PMA/PMD/PME/PMS/PMF) — estas últimas
  decodificam só o TIPO pelo prefixo e dependem de KnownParts para specs
  (que a regra 4 + `_known_dram_density` já servem); decidir na reforma de
  dado se ganham mapas próprios. **Extensão per-die GB (lote 042,
  2026-07-31):** o derive aceitava só 'NNNMB' e Gbit pelado — die ≥ 1GB
  ('1GB'/'2GB', ex.: HYX_DDR4_CAP 8G→1GB, H5CG DDR5 2GB) ficava SEM chave
  de preço ('densidade indisponível') e o chip entrava no estoque sem
  categoria (H-00 na máscara). `RX_DIE_GB` (convention.py) + GB×8=Gb no
  engine e no `_gbit_from_capacity`: dentro de kind-DDR capacity é per-die
  por convenção, então é seguro; fora, 'GB' segue pacote (regra 4 de
  ESCRITA continua recusando 'GB' — a conversão é só de LEITURA).

---

## 8. Glossário de domínio

- **eMCP** — eMMC (NAND) + LPDDR (RAM) no mesmo encapsulamento (`is_emcp=True`).
- **uMCP** — UFS (NAND) + LPDDR (RAM) no mesmo pacote.
- **eMMC / UFS** — padrões de armazenamento NAND gerenciado (UFS é mais novo/rápido).
- **LPDDR(2–5X)** — RAM móvel. **DDR(1–5) / SDRAM / RDRAM** — RAM de PC.
  **GDDR / gDDR3** — memória de GPU (não confundir com DDR).
- **FBGA code** — ID físico de 5 caracteres gravado a laser (ex.: `D9VFC`); é o que
  o operador lê, não o PN completo.
- **gramática** — decode posicional do PN pelas regras da `ChipFamily` + `DecodeMap`.
- **gabarito** — o conjunto curado de famílias/mapas definido nos `chips/knowledge/<marca>.yaml`
  e carregado por `load_brands`.
- **confidence** — confiança do `KnownPart`: `confirmed` > `manual` > `distributor`
  > `estimated`. Só `confirmed`/`manual` são autoritativos (vencem a gramática). O
  antigo campo `status` (raw/enriched/failed) foi removido.
- **destino / rentabilidade** — saída comercial da triagem (caixa física + RENTÁVEL?).

---

## 9. Documentação profunda (leia sob demanda)

Estes docs já existem na raiz. **Não duplique o conteúdo deles aqui** — abra o
relevante quando a tarefa pedir:

- **`README.md`** — visão geral e setup. O **contrato de autoria** resumido está no **§5** acima.
- **`AUTORIA.md`** — ⭐ **o processo OBRIGATÓRIO de um chat de marca para adicionar PNs**, de ponta a ponta: as duas trilhas (gramática/known_parts), o **teste-golden** por família, o **handshake** de rentabilidade, a tabela completa "classe de erro → trava", o checklist de handoff, a publicação, e o que NÃO é automatizável (fato → revisão humana). **Um chat de marca lê este arquivo inteiro antes de adicionar PNs.**
- **`RENTABILIDADE.md`** — bíblia técnica completa do sistema de rentabilidade: `assess_profitability`, `is_dead_by_generation`, `ProfitabilityConfig`, gateway do estoque, todos os bugs corrigidos, limitações, regras invioláveis, checklist para novos chip_types. **Leia antes de tocar em qualquer código de rentabilidade.**
- **`MICRON.md`** — bíblia técnica e de negócio da Micron: famílias, decode maps, convenção de campos, pipeline, fontes de dados, bugs corrigidos, lacunas.
- **`PIECEMAKERS.md`** — bíblia técnica PieceMakers: anatomia do PN PMF, decode map PMF_DDR3_CAP, famílias, rentabilidade, fontes, armadilhas.
- **`TOSHIBA-KIOXIA.md`** — bíblia técnica Toshiba / Kioxia: família THGBM (eMMC), decode maps THGBM_CAP/THGBM_GEN, eMCP TYC, famílias bloqueadas (KLUE/THGAF), armadilhas de sub-prefixo, gaps e roadmap. **CONSOLIDAÇÃO (2026-07-01):** Toshiba + Kioxia + KIOXIA(dup) viraram UMA marca **`Toshiba-Kioxia`** (code TXK) — mesma empresa (rename out/2019), em `chips/knowledge/toshiba-kioxia.yaml` (11 famílias). **Para adicionar/corrigir chip Toshiba-Kioxia, edite `chips/knowledge/toshiba-kioxia.yaml`** (contrato de autoria em §5).
- **`FUZZY.md`** — bíblia técnica do sistema de sugestão inteligente de PNs: `_visual_edit_distance`, matriz de confusão visual, `_prefix_candidates`, `_combined_suggestions`, gate de confiança, frontend diff, tuning. **Leia antes de tocar nas funções `_fuzzy_*` / `_prefix_*` do engine.**
- **`I18N.md`** — ⭐ bíblia técnica da **internacionalização (i18n)** — **sistema COMPLETO em 4 idiomas (pt-br/es/en/zh-hans, jul/2026)**: a cadeia de resolução (preferência do usuário `tenancy.UserLanguage` > cookie > Accept-Language/região > pt-br), as 3 superfícies (UI/`gettext`+`.po`, saída do engine com chave-canônica-vs-rótulo via `chips/labels.py` — **nunca compare contra o rótulo na lógica, use a chave** —, CMS **files-first**: `_content/<slug>.<código>.html` + `django-modeltranslation` p/ metadados), como adicionar um idioma (≈ 2 `.po`), a **rotina de tradução segura para modelo de IA** (contrato §7.1 + portão `check_translations` + glossário DO-NOT-TRANSLATE), extração/compilação sem gettext (`scripts/i18n_extract.py`/`i18n_compile.py`), armadilhas (string persistida = canônica; snapshot; `"por die"` no `DecodeMap`; JS estático via `JavaScriptCatalog`) e deploy do `.mo`. **Leia antes de mexer em tradução.** É o arquivo que o chat especializado em i18n mantém.
- **`MULTILANGUAGE.md`** — documento de **FEATURE** do multilíngue + ⭐ **CONTRATO DE AUTORIA (§7)**: além da descrição de produto (4 idiomas, cadeia de decisão, seletores, mapa do que é/não é traduzido), o **§7 é leitura OBRIGATÓRIA para QUALQUER chat que crie tela/página/mensagem/string** — a regra "toda string nasce marcada E traduzida na MESMA entrega", a tabela "vou criar X → faça Y (nunca Z)", o fluxo do autor (extract → traduzir os SEUS msgids → compile → `check_translations` → suíte → mesmo commit) e as 6 proibições. Não duplica o técnico — aponta pro `I18N.md`.

> ⚠️ **Não há mais `docs/archive/` nem notas de sessão** (removidas na limpeza v1.0.0-beta,
> jul/2026). Handoff/histórico vive no git e no chat, não em arquivo solto. **O código é a
> fonte da verdade**; confirme em `chips/engine.py` / `core/settings.py`.

---

## 10. Higiene de documentação (regras para agentes em sessões futuras)

- **`CLAUDE.md` é o índice canônico de onboarding.** Ao aprender algo durável
  (uma regra que evita um bug, um comando novo, uma decisão de arquitetura),
  **atualize a seção certa aqui** — não crie um documento novo solto na raiz.
- **Não crie arquivos de nota de sessão** (tipo `NEXT_CHAT` / `BRIEFING_*` / handoffs datados).
  De `.md` de projeto existem: **README + CLAUDE + os 10 de marca + AUTORIA + RENTABILIDADE +
  MICRON/PIECEMAKERS/TOSHIBA-KIOXIA + FUZZY + I18N + MULTILANGUAGE** (bíblias técnicas/feature
  permanentes; política v1.0.0-beta, jul/2026). Handoff de fim de sessão vai no git/PR e no
  chat — nunca em arquivo novo na raiz.
- **Decisões de arquitetura duradouras** vão para a seção certa do próprio **`CLAUDE.md`**
  (o hub) ou pro `.md` da marca — nunca num doc solto.
- **Em qualquer conflito entre documentos, o código vence**
  (`chips/engine.py`, `core/settings.py`).

<!-- Nota de manutenção: ao adicionar uma regra crítica nova, coloque-a na §2
(Regras de ouro) e, se for específica de um tópico, prefira apontar para o doc
profundo em vez de despejar detalhe aqui. Manter este arquivo enxuto e universal. -->
