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
2. **O engine só enxerga `KnownPart` com `status="enriched"`.** Um registro em
   `status="raw"` é **invisível** para a classificação, mesmo com dados certos.
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
   `distributor` e de IA (`ai_*`) são frequentemente **errados** (capacidade/tipo
   de RAM) — só complementam quando a gramática está incompleta. Veja
   `_result_from_known` em `chips/engine.py`.
7. **Nunca delete famílias do `populate`.** Para desativar, use `active=False`
   no admin (ou no seed). Deletar quebra histórico e FKs.
8. **`purge_enriched` é destrutivo** (apaga KnownParts de IA/scraping). Rode
   **sempre** com `--dry-run` antes.
9. **Nunca commite segredos.** `.env` é gitignored. Chaves vivem só no `.env`
   local e nas env vars do Render.
10. **Gemini é legado / em remoção** (ver §4). Não construa nada novo em cima
    dele; o núcleo é **banco + gramática**.

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
| IA (legado) | Google Gemini via `google-generativeai` — desligado por padrão |
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

1. **Banco exato** — `KnownPart` com `status="enriched"`. Se achar, `_result_from_known`
   funde com a gramática. ⚠️ **Atenção à precedência real** (não é "banco > tudo"):
   - `confidence` `confirmed`/`manual` → **banco vence** (verificado por humano);
   - demais (`distributor`/`ai_*`/`estimated`) + gramática completa → **gramática vence**.
2. **Lookup FBGA** — se o PN casa o padrão FBGA (`^[A-Z][A-Z0-9]{4}$`, ex.: `D9VFC`),
   busca por `KnownPart.fbga_code`. É o código que o operador lê no chip Micron.
   Desconhecido → enfileira em `UnknownChip` para resolução noturna.
3. **Gramática da família** — `_result_from_family`: decode posicional via
   `ChipFamily` + `DecodeMap`. PNs não confirmados entram na **fila de revisão**
   (`KnownPart status="raw"`).
4. **Gemini (LEGADO)** — só roda se `GEMINI_ENABLED=true` (default **false**).
   **Tratar como descontinuado.** Todo o caminho Gemini é no-op por padrão
   (`_get_api_key()` retorna `""`).
5. **Fuzzy matching** — sugestões por distância de Levenshtein para erro de digitação.

Além disso: **`assess_profitability(result)`** aplica as regras comerciais
(eMCP/uMCP, eMMC, UFS, LPDDR, DDR) e devolve `RENTÁVEL` / `NÃO RENTÁVEL` /
`INDETERMINADO`. Os limiares estão documentados no docstring da função.

### Modelos — `chips/models.py`

`Brand` → `ChipFamily` → `KnownPart`; `DecodeMap` (tabelas de decode reusáveis);
`Source`, `SearchLog`, `UnknownChip`, `CorrectionRequest`, `ChipSubmission`.

- **Ladder de confiança** (alta→baixa): `confirmed` > `manual` > `distributor` >
  `ai_high` > `ai_medium` > `ai_low` > `estimated`.
- **Status de `KnownPart`:** `raw` (coletado, sem specs) → `enriched` (utilizável)
  / `failed`.
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
chips/engine.py          → classify(), gramática, profitability, Gemini (legado)
chips/models.py          → todo o modelo de dados + glossário nos docstrings
chips/admin.py           → workflows de triagem (ChipFamily, KnownPart, correções)
chips/management/commands/→ pipeline de dados (populate/import/fix/collect) — §5
core/settings.py         → config; flags GEMINI_ENABLED, DATABASE_URL, etc.
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

### Testes (sempre com settings de teste — SQLite, Gemini off)

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
python scripts/enrich_gemini.py --brand Samsung --limit 50 [--retry-failed]
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
  `RENDER_EXTERNAL_HOSTNAME`, `GEMINI_API_KEY`, `GEMINI_ENABLED`,
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

---

## 7. Armadilhas comuns (o que costuma quebrar)

- **Cache velho:** esqueceu de reiniciar após `populate --overwrite` → engine
  serve gramática antiga. (Regra de ouro #3.)
- **Registro invisível:** PN com dado certo mas `status="raw"` → engine ignora.
  Promova para `enriched`. (Regra de ouro #2.)
- **`fix_known_parts` que não "pega":** atualizar capacidade sem setar
  `status="enriched"` + `confidence="confirmed"` deixa o registro perdendo para a
  gramática. Histórico em **`INVESTIGACAO_ENGINE_STATUS_ENRICHED.md`**.
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
  (exigem Playwright); `--brand` default é "Samsung" em `collect_pns`/`enrich_gemini`
  — fácil raspar a marca errada por omissão.
- **`confidence="estimated"`** (ex.: Wayback) fica oculto na UI de triagem até
  confirmação manual.

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
- **raw / enriched / failed** — estados de `KnownPart` (só `enriched` é usado pelo engine).
- **destino / rentabilidade** — saída comercial da triagem (caixa física + RENTÁVEL?).

---

## 9. Documentação profunda (leia sob demanda)

Estes docs já existem na raiz. **Não duplique o conteúdo deles aqui** — abra o
relevante quando a tarefa pedir:

- **`README.md`** — visão geral e setup original.
- **`HANDOFF.md`** — decisões de arquitetura, histórico e correções (BUG-1…BUG-6).
- **`DEPLOY_RENDER.md`** — deploy, env vars, armadilhas de produção.
- **`PLANO_MICRON_FBGA.md`** — pipeline FBGA da Micron (estágios, decode de densidade).
- **`AUDITORIA_SAMSUNG_2026.md`** / **`BRIEFING_DDR_SAMSUNG.md`** — gabarito Samsung,
  chaves de cap/gen, casos confirmados e descartados.
- **`INVESTIGACAO_ENGINE_STATUS_ENRICHED.md`** — o bug do gatekeeper `status/confidence`.
- **`design_system.md`** (+ `design_system_preview.html`) — tema visual (IBM Carbon
  White), tokens CSS, componentes.
- **`SETUP_CHIPS.md`** — passo a passo de povoamento inicial.

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
