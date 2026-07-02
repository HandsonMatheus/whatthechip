# WhatTheChip? — v1.0.0-beta

**O "Google dos chips".** Classifica Part Numbers (PNs) de chips de memória para o mercado de
**reciclagem / refurbishing** de eletrônicos — operado pela **eMiner (Paraguai)**. Um operador de
bancada lê o código gravado a laser num chip recuperado, digita na busca, e o sistema devolve na hora
**o que é** (eMCP / eMMC / UFS / LPDDR / DDR…, capacidade, densidade, interface) e **se vale a pena**:
`RENTÁVEL` / `NÃO RENTÁVEL` / `INDETERMINADO` — recondicionar vs. sucata. É ao mesmo tempo um
**classificador** e uma **ferramenta de triagem de rentabilidade**.

---

## Como classifica

`classify(pn)` normaliza o PN e tenta, **em ordem**:

1. **Banco de PNs confirmados** (`KnownPart`) — a fonte da verdade. Um registro com `confidence` ∈ (`confirmed`, `manual`) é autoritativo e **vence a gramática**.
2. **Lookup FBGA** — pelo código de 5 caracteres gravado no chip (ex.: `D9VFC`), que é o que o operador costuma ler quando o PN completo não está legível.
3. **Gramática da família** — decodifica cada posição do PN pelas regras da `ChipFamily` + `DecodeMap`, cobrindo a cauda longa de PNs ainda não confirmados.
4. **Fuzzy matching** — sugestões por similaridade visual para erros de digitação, quando nada casa.

Em paralelo, `assess_profitability` aplica as regras comerciais (por tipo, geração e capacidade)
e devolve o veredito de rentabilidade.

Digite um PN como `KMQ310006A` e o card devolve, em tempo real: fabricante, tipo, capacidade
(NAND + RAM nos eMCPs), nível de confiança, link para a documentação da família e o veredito de
rentabilidade — sem recarregar a página (HTMX).

---

## O conhecimento é YAML

Cada marca vive em **`chips/knowledge/<marca>.yaml`** — 10 marcas: `samsung`, `hynix`, `micron`,
`toshiba-kioxia`, `sandisk`, `kingston`, `nanya`, `piecemakers`, `gigadevice`, `rayson`. Um arquivo
declara a **gramática** (famílias + decode maps) e a **autoridade** (`known_parts` confirmados). O
comando **`load_brands`** carrega e **valida no portão** (schema Pydantic — o *data contract*): se o
yaml segue a convenção, grava; senão, **rejeita com erro acionável** antes de qualquer coisa ir pro ar.

Não há mais `populate_*` / `add_chip_families` / `fix_known_parts` — foram aposentados; o conhecimento
é 100% declarativo. Ao gravar, o `catalog_version` sobe e o engine **recarrega o cache sozinho**, sem
reiniciar o servidor.

> Como escrever/corrigir uma marca (o contrato de autoria) e todas as regras de arquitetura estão no
> **`CLAUDE.md`** — leia-o antes de tocar no catálogo.

---

## Stack

Django 5.2 LTS · Python 3.11 · PostgreSQL · HTMX (server-rendered, sem SPA) · WhiteNoise · gunicorn ·
deploy no **Render**.

---

## Setup local

Pré-requisitos: **Python 3.11** e **PostgreSQL** rodando.

```bash
git clone https://github.com/HandsonMatheus/whatthechip.git
cd whatthechip
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Crie o `.env` na raiz (já está no `.gitignore` — **nunca commite**):

```bash
DJANGO_SECRET_KEY=uma-chave-longa-e-aleatoria
DEBUG=True
DB_NAME=whatthechip
DB_USER=wtc_user
DB_PASSWORD=sua_senha
DB_HOST=localhost
DB_PORT=5432
```

Monte o banco e o catálogo, depois suba o servidor:

```bash
bash setup.sh                      # migrations + deploy_catalog (carrega as 10 marcas dos yamls)
python manage.py createsuperuser   # acesso ao /admin/
python manage.py runserver         # http://localhost:8000
```

---

## Testes

```bash
python manage.py test chips --settings=core.settings_test   # SQLite em memória (~130 testes)
```

A suíte inclui a **rede de regressão do catálogo**: identifica todos os PNs de cada marca a partir do
yaml e trava a saída do `classify`, para que uma mudança de gramática não quebre outra marca em silêncio.

---

## Deploy (Render)

Push em **`main`** dispara o **deploy automático**; o build roda `migrate` + `collectstatic`. Variáveis
obrigatórias no painel do Render: **`DJANGO_SECRET_KEY`**, **`DEBUG=False`**, **`DATABASE_URL`**
(injetada ao conectar o Postgres). Para **(re)carregar o catálogo em produção**, rode o
`deploy_catalog --commit` **localmente apontando `DATABASE_URL` ao Render** (não há shell interativo no
free/hobby por padrão). Sequência completa, env vars e armadilhas: **`CLAUDE.md` §5**.

---

## Estrutura

```
chips/     engine.py (classify + assess_profitability) · models.py · chip_types.py (convenção de tipos)
           knowledge/<marca>.yaml  ← o conhecimento · management/commands/ (load_brands, deploy_catalog…)
estoque/   inventário por lote + triagem de rentabilidade (requer login)
pages/     site editorial público — conteúdo vivo em _content/*.html, lido em runtime
core/      settings, urls, wsgi
```

---

## Documentação

- **`CLAUDE.md`** — **o hub**: regras de ouro, arquitetura do engine, comandos, convenção de campos e o **contrato de autoria do yaml** (o que um chat de marca segue). Comece por aqui.
- **10 `.md` de marca** (`SAMSUNG.md`, `MICRON.md`, `SK_HYNIX.md`, …) — a camada humana por marca: anatomia do PN, armadilhas, fontes Tier-1, histórico de bugs. Os dados vivos ficam no yaml, não no `.md`.
- **`RENTABILIDADE.md`** e **`FUZZY.md`** — bíblias técnicas dos subsistemas de rentabilidade e de sugestão inteligente de PNs.

---

*WhatTheChip · v1.0.0-beta · jul/2026 · eMiner (Paraguai)*
