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

- **Detecção de chip *remarked* (remarcado/falsificado):** se gramática e banco
  divergem na capacidade (> 0.1 GB), o sistema levanta a flag `remarked_flag` —
  crítico no mercado de reciclagem, cheio de chips relabelados.
- **Crescimento colaborativo:** quando um PN não é encontrado, o usuário pode
  enviá-lo (com foto) via "Adicionar chip" (`ChipSubmission`) ou reportar erros
  (`CorrectionRequest`). Buscas e desconhecidos são logados (`SearchLog`,
  `UnknownChip`) para alimentar o backlog de enriquecimento.

---

## 2. Regras de ouro (leia sempre — quebrar isto quebra o produto)

1. **O banco de produção não está acessível ao agente.** Comandos que **alteram
   dados** (`migrate`, `populate_*`, `import_*`, `fix_*`, `purge_*`,
   `enrich_*`) devem ser **propostos e revisados**, mas **executados pelo
   usuário**. Claude **edita arquivos**; o usuário **roda** e confirma.
2. **O engine só trata como autoritativo `KnownPart` com `confidence` ∈
   (`confirmed`, `manual`).** Registros `distributor`/`estimated` não vencem a
   gramática — caem na decodificação posicional (camada 2). O antigo campo
   `status` (raw/enriched/failed) foi **removido** (jun/2026), assim como o gate
   `status="enriched"`.
3. **Depois de `populate_* --overwrite`, REINICIE o servidor.** O engine usa
   `lru_cache` para famílias e mapas (`chips/engine.py`). O comando chama
   `clear_engine_cache()` apenas no próprio processo — o servidor web continua
   servindo o cache antigo até reiniciar.
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
    specs entram por confirmação manual (populate_*/import_*/fix_* + admin).
11. **Rentabilidade tem fonte ÚNICA: `assess_profitability`.** Nunca reimplemente
    regra de rentabilidade em outro lugar. O `is_dead_by_generation` (engine) e o
    gateway do estoque (`estoque/views.py`) **derivam** dela — ver §4 e
    `docs/CONTRATO_RENTABILIDADE_GATEWAY.md`.

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
estoque/   → inventário por lote (Lot/InventoryEntry); requer login
pages/     → CMS simples de documentação (modelo Page, servido em /<slug>/)
```

### O engine de classificação — `chips/engine.py` (arquivo mais importante)

Ponto de entrada único: **`classify(pn)`**. Normaliza o PN e tenta, **em ordem**:

1. **Banco exato (confirmados)** — `KnownPart` com `confidence` ∈ (`confirmed`,
   `manual`). Substitui o antigo gate `status="enriched"` (campo removido em
   jun/2026). Se achar, `_result_from_known` funde com a gramática. ⚠️ **Precedência
   real** (não é "banco > tudo"):
   - `confirmed`/`manual` → **banco vence** (verificado por humano);
   - na camada 1 nada além de confirmed/manual aparece — `distributor`/`estimated`
     caem direto na gramática (camada 2) e a gramática completa vence.
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
`RejectedEntry` de auditoria). Contrato completo:
**`docs/CONTRATO_RENTABILIDADE_GATEWAY.md`**.

### Modelos — `chips/models.py`

`Brand` → `ChipFamily` → `KnownPart`; `DecodeMap` (tabelas de decode reusáveis);
`Source`, `SearchLog`, `UnknownChip`, `CorrectionRequest`, `ChipSubmission`.

- **Ladder de confiança** (alta→baixa): `confirmed` > `manual` > `distributor` >
  `estimated`. Só `confirmed`/`manual` são **autoritativos** (vencem a gramática);
  os níveis de IA (`ai_*`) foram removidos junto com o Gemini.
- **Sem campo `status`:** o antigo `raw/enriched/failed` foi **removido** (jun/2026).
  Um KnownPart "existe e é confiável" quando `confidence` ∈ (`confirmed`, `manual`).
- **`ChipFamily`** carrega a "anatomia" do PN: `decode_cap_pos/len/map`,
  `decode_gen_pos/map`, `decode_density_type` (`pc` usa `pn[3:5]`/`DRAM_PC`;
  `mobile` usa `pn[3]`/`DRAM_MOBILE` — **mutuamente exclusivos** com `cap_map`),
  `suffix_rules`, `pn_length`, `priority`, `active`, `is_emcp`.
- **`ChipFamily.doc_page`** liga a família a uma página de documentação (`pages.Page`).

### Camada web

- **`chips/views.py`** → `/chips/search/` (JSON), `/chips/decode/` (parcial HTMX),
  `/chips/stats/`, `/chips/report/`, `/chips/submit/`.
- **`estoque/views.py`** → CRUD de lotes em `/estoque/...`, preview/classify,
  export `.xlsx`. Tudo `@login_required`.
- **`pages/views.py`** + `core/urls.py` → home `/` e páginas `/<slug>/`
  (a rota slug é a **última** — captura tudo).
- **Auth:** login em `/login/`, sem cadastro público; `LOGIN_REDIRECT_URL=/estoque/`.

### Site estático separado — `build.py` (atenção: NÃO é o app Django)

`python3 build.py` gera um site estático em `docs/` a partir de `_content/` +
`_template/` (publicável no GitHub Pages). É a versão **standalone/legada** da
documentação; a versão "viva" servida pelo Django é o app **`pages`**. Não
confunda os dois nem edite um esperando que o outro mude.

### Mapa de arquivos-chave

```
chips/engine.py          → classify(), gramática, profitability
chips/models.py          → todo o modelo de dados + glossário nos docstrings
chips/conventions.py     → canonical_gen(): FONTE ÚNICA da convenção de label (consumida pelo gateway)
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
python manage.py populate_samsung          # gabarito mestre (famílias + DecodeMaps)
python manage.py populate_hynix
python manage.py populate_micron_mcp
python manage.py populate_kingston / populate_sandisk / populate_toshiba / populate_rayson
python manage.py populate_piecemakers      # PieceMakers: Brand + PMF_DDR3_CAP + famílias PMF/PMA/PME/PMD/PMS
python manage.py add_chip_families         # famílias "magras" p/ outras marcas
python manage.py import_micron_catalog *_full-catalog.csv   # CSVs Micron da raiz
python manage.py import_samsung_psg --all                   # CSVs em data/psg/
python manage.py fix_known_parts           # correções curadas (força confirmed)
python manage.py link_doc_pages / sync_index_page
```

**Manutenção de estoque** (dry-run por padrão, reversíveis via JSON; rodar com
`DATABASE_URL` apontando ao Render — ver `docs/archive/2026-06-16-limpeza-e-bloqueio-estoque.md`):

```bash
python manage.py clean_lote --lot 39 --since 2026-06-16   # remove PNs novos NÃO confirmados (typos/contaminação); --keep, --commit, --revert
python manage.py bless_base --lot 39 --since 2026-06-16    # promove a base lançada antes do corte a KnownPart manual/enriched; --commit, --revert
python manage.py audit_targets --file correcoes.csv        # read-only: status (CONFIRMADO/GRAMATICA/NAO-VISIVEL/AUSENTE) de cada PN destino
python manage.py fix_pns --lot 39 --file correcoes.csv     # corrige PNs (merge/rename/refresh) via CSV errado,certo; reavalia estado a cada passo; --commit, --revert
```

> O bloqueio **"só confirmados"** em `estoque/views.py::add_chip` barra PN não
> confirmado: vai para `PendingEntry` (fila em `/admin/estoque/pendingentry/`,
> ações Aprovar/Reprovar) em vez do estoque. `bless_base` é a ponte para não
> travar reposição dos comuns. Reinicie o servidor após `bless_base --commit`.

**Somente local** (precisam de `playwright`/`curl_cffi`/`pdfplumber` ou chaves de
API — **não** rodam no Render: a imagem de produção (`requirements-render.txt`)
não inclui esses pacotes):

```bash
python scripts/collect_pns.py --brand Samsung      # coleta PNs crus (default: Samsung!)
python scripts/nexar_validate.py --validate <PN>   # Octopart/Nexar
python manage.py enrich_micron_fbga / lookup_fbga <FBGA> / fill_capacity_from_micron_api
```

Ordem típica (DB vazio → populado): `migrate` → `populate_*` (+`--overwrite`) →
`link_doc_pages`/`sync_index_page` → `import_*` → `fix_known_parts` → coleta →
enriquecimento → **reiniciar servidor**.

### Deploy (Render)

**Repositório:** `github.com/HandsonMatheus/whatthechip` (remote `origin`). Push
para `main` dispara o **deploy automático no Render**. `Procfile`: `web: gunicorn
core.wsgi --bind 0.0.0.0:$PORT`. Render injeta `DATABASE_URL` e
`RENDER_EXTERNAL_HOSTNAME`. `collectstatic` + WhiteNoise servem os estáticos.
Detalhes e armadilhas: **`DEPLOY_RENDER.md`**.

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
- **Mudou a gramática (populate/admin)?** Reinicie o servidor (regra de ouro #3).
- **Estilo de código:** siga os padrões já presentes nos arquivos vizinhos
  (PEP 8, docstrings explicativos com o *porquê*). Não recrie um "linter humano"
  aqui — espelhe o código existente.
- **Hierarquia de fontes (imutável)** ao gravar dados: fabricante/datasheet >
  Octopart/Nexar > distribuidor B2B rastreável > Preduo > IA > especulação.
  Importadores **nunca** rebaixam um registro `confirmed`/`manual`.
- **Não confie em dado de distribuidor ou IA** sem verificação por datasheet/Octopart
  (confundem Gb/GB, invertem primary/secondary, alucinam capacidade).
- **Part-name da API Micron FBGA não é fonte para tipo de RAM** (BUG-8, 2026-06-19).
  A API retorna strings como `"MLC EMMC/LPDDR2 72G VFBGA"` que podem pertencer a
  famílias relacionadas com RAM diferente. Para MT29TZZZ, a API dizia "LPDDR2" mas
  a família é LPDDR3 (MT29PZZZ é que é LPDDR2). Regra: o **prefixo do PN** define
  o tipo de RAM (`_infer_lpddr_gen` em `fill_capacity_from_micron_api.py`); para
  confirmar, use **datasheet oficial** ou **DigiKey** — nunca o campo `part-name` da API.

### Convenção de campos → label da caixa física (estoque)

O gateway `estoque/views.py::_compute_destination` escolhe o branch pelo `chip_type`
e monta o label com os campos abaixo. **Alimente os campos certos; não mexa no gateway.**
Modelo canônico: `JW464` (`SLC NAND 512MB`).

| Tipo | `chip_type` | `subtype` | Capacidade | Resultado |
|---|---|---|---|---|
| NAND raw | `"NAND Flash"` | célula: `"SLC NAND"` / `"MLC NAND"` / `"TLC NAND"` | `capacity` em bytes (`"512MB"`, `"4GB"`) | `"SLC NAND 512MB"` |
| eMMC | `"eMMC"` | — | `capacity` em GB (`"16GB"`) | `"EMMC16GB"` |
| eMCP | `"eMCP"` | geração RAM (`"LPDDR3"`) | `emcp_nand` = `"16GB"`; `emcp_ram` = `"LPDDR3 1GB"` (tipo + GB) | `"EMCP16+1"` |
| uMCP | `"uMCP"` | geração RAM | `emcp_nand`, `emcp_ram` | `"UMCP…+…"` |
| UFS | `"UFS"` | — | `capacity` em GB | `"UFS128GB"` |
| DDR/GDDR | `"RAM"` | geração (`"DDR3"`) | `density_gbit` = die em Gb | `"DDR3+8G"` |
| LPDDR avulso | `"LPDDR{n}"` | geração (`"LPDDR4"`) | `capacity` = pacote em GB | `"LPDDR4+4GB"` |

**Regras absolutas de campo:**
- `subtype` = **SOMENTE** célula (NAND) ou geração (RAM) — nunca densidade, bus width, voltagem, "Mobile", "Multi-Channel", "paralela industrial"
- `interface` = bus width (`"x8"`, `"x16"`) para DDR/GDDR; vazio para LPDDR eMCP
- `emcp_ram` = `"LPDDR{n} {cap}GB"` — tipo **antes** da capacidade (ex.: `"LPDDR3 1GB"`, nunca `"1GB LPDDR3"`)
- `density_gbit` é o campo modelo do `KnownPart` para densidade DDR (em Gb); `dram_density` é campo calculado pelo engine — não confundir
- Tudo que sobrar (temperatura, organização, variante, ECC) vai no `tip`/`notes`

Referência completa: **`docs/CONVENCAO_MICRON_ESTOQUE.md`**

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

---

## 7. Armadilhas comuns (o que costuma quebrar)

- **Cache velho:** esqueceu de reiniciar após `populate --overwrite` → engine
  serve gramática antiga. (Regra de ouro #3.)
- **Registro não autoritativo:** PN com dado certo mas `confidence` fora de
  (`confirmed`, `manual`) → o engine não o usa como autoridade (cai na gramática).
  Promova a `confirmed`/`manual`. (Regra de ouro #2.)
- **`fix_known_parts` que não "pega":** atualizar capacidade sem setar
  `confidence="confirmed"`/`"manual"` deixa o registro perdendo para a gramática.
  (Antes o sintoma era `status="raw"`; o campo `status` foi removido.)
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
  (2026-06-20), ePoP (2026-06-20). **Regra de prevenção:** ao adicionar um novo
  chip_type ao sistema, pergunte — "este tipo é NÃO RENTÁVEL independente de
  capacidade?". Se sim → bloco de tipos no topo de `assess_profitability`. Se é
  NÃO RENTÁVEL por geração → verificar geração ANTES de `_extract_gib` no bloco.

---

## 8. Glossário de domínio

- **eMCP** — eMMC (NAND) + LPDDR (RAM) no mesmo encapsulamento (`is_emcp=True`).
- **uMCP** — UFS (NAND) + LPDDR (RAM) no mesmo pacote.
- **eMMC / UFS** — padrões de armazenamento NAND gerenciado (UFS é mais novo/rápido).
- **LPDDR(2–5X)** — RAM móvel. **DDR(1–5) / SDRAM / RDRAM** — RAM de PC.
  **GDDR / gDDR3** — memória de GPU (não confundir com DDR).
- **FBGA code** — ID físico de 5 caracteres gravado a laser (ex.: `D9VFC`); é o que
  o operador lê, não o PN completo.
- **remarked** — chip relabelado/falsificado; detectado por divergência gramática×banco.
- **gramática** — decode posicional do PN pelas regras da `ChipFamily` + `DecodeMap`.
- **gabarito** — o conjunto curado de famílias/mapas criado pelos `populate_*`.
- **confidence** — confiança do `KnownPart`: `confirmed` > `manual` > `distributor`
  > `estimated`. Só `confirmed`/`manual` são autoritativos (vencem a gramática). O
  antigo campo `status` (raw/enriched/failed) foi removido.
- **destino / rentabilidade** — saída comercial da triagem (caixa física + RENTÁVEL?).

---

## 9. Documentação profunda (leia sob demanda)

Estes docs já existem na raiz. **Não duplique o conteúdo deles aqui** — abra o
relevante quando a tarefa pedir:

- **`README.md`** — visão geral e setup original.
- **`HANDOFF.md`** — decisões de arquitetura, histórico e correções (BUG-1…BUG-6).
- **`DEPLOY_RENDER.md`** — deploy, env vars, armadilhas de produção.
- **`RENTABILIDADE.md`** — bíblia técnica completa do sistema de rentabilidade: `assess_profitability`, `is_dead_by_generation`, `ProfitabilityConfig`, gateway do estoque, todos os bugs corrigidos, limitações, regras invioláveis, checklist para novos chip_types. **Leia antes de tocar em qualquer código de rentabilidade.**
- **`MICRON.md`** — bíblia técnica e de negócio da Micron: famílias, decode maps, convenção de campos, pipeline, fontes de dados, bugs corrigidos, lacunas.
- **`PIECEMAKERS.md`** — bíblia técnica PieceMakers: anatomia do PN PMF, decode map PMF_DDR3_CAP, famílias, rentabilidade, fontes, armadilhas.
- **`FUZZY.md`** — bíblia técnica do sistema de sugestão inteligente de PNs: `_visual_edit_distance`, matriz de confusão visual, `_prefix_candidates`, `_combined_suggestions`, gate de confiança, frontend diff, tuning. **Leia antes de tocar nas funções `_fuzzy_*` / `_prefix_*` do engine.**
- **`PLANO_MICRON_FBGA.md`** — pipeline FBGA da Micron (estágios iniciais — parcialmente histórico; ver MICRON.md para estado atual).
- **`AUDITORIA_SAMSUNG_2026.md`** / **`BRIEFING_DDR_SAMSUNG.md`** — gabarito Samsung,
  chaves de cap/gen, casos confirmados e descartados.
- **`INVESTIGACAO_ENGINE_STATUS_ENRICHED.md`** — **HISTÓRICO**: documenta o antigo
  gatekeeper `status="enriched"`, removido em jun/2026 (o gate agora é `confidence`
  ∈ confirmed/manual — ver §4). Mantido só como registro.
- **`design_system.md`** (+ `design_system_preview.html`) — tema visual (IBM Carbon
  White), tokens CSS, componentes.
- **`SETUP_CHIPS.md`** — passo a passo de povoamento inicial.
- **`docs/CONVENCAO_MICRON_ESTOQUE.md`** — convenção canônica de campos por tipo de chip
  (NAND / eMMC / eMCP / UFS / DDR / LPDDR) e como cada campo alimenta o label da caixa física.
  Modelo de referência: `JW464`. Leia ao adicionar qualquer novo PN Micron.

> ⚠️ **Notas de sessão antigas foram movidas para `docs/archive/`**
> (`NEXT_CHAT.md`, `BRIEFING_PROXIMO_CHAT.md`, `PROMPT_SESSAO_REFINAMENTO.md`).
> São **históricas** e podem estar desatualizadas (ex.: status do Gemini). **O
> código é a fonte da verdade**; confirme em `chips/engine.py` / `core/settings.py`.

---

## 10. Higiene de documentação (regras para agentes em sessões futuras)

- **`CLAUDE.md` é o índice canônico de onboarding.** Ao aprender algo durável
  (uma regra que evita um bug, um comando novo, uma decisão de arquitetura),
  **atualize a seção certa aqui** — não crie um documento novo solto na raiz.
- **Não crie `NEXT_CHAT.md` / `BRIEFING_*` na raiz.** Para handoff de fim de
  sessão, salve em **`docs/archive/`** com data no nome
  (ex.: `docs/archive/2026-06-14-handoff.md`) e um cabeçalho marcando-o como
  histórico.
- **`docs/archive/` é histórico, não fonte da verdade.** Não aja com base nele
  sem confirmar no código.
- **Decisões de arquitetura duradouras** vão para **`HANDOFF.md`** (já existe),
  não numa nota de sessão nova.
- **Em qualquer conflito entre documentos, o código vence**
  (`chips/engine.py`, `core/settings.py`).

<!-- Nota de manutenção: ao adicionar uma regra crítica nova, coloque-a na §2
(Regras de ouro) e, se for específica de um tópico, prefira apontar para o doc
profundo em vez de despejar detalhe aqui. Manter este arquivo enxuto e universal. -->
