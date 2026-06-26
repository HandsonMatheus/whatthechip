# WhatTheChip?

Guia técnico de identificação e classificação de chips IC para o mercado de refurbishing e reciclagem eletrônica — combinando documentação editorial com um engine de decodificação de Part Numbers.

Digite `KMQ310006A` e o sistema responde: *Samsung eMCP — LPDDR3 1GB + eMMC 4GB — Galaxy J3/J5 (2016)*.

---

## O que o projeto faz

**Documentação** — guias por fabricante (Samsung, SK Hynix, Micron, Elpida, Toshiba/KIOXIA, SanDisk/WD, Nanya, Kingston, Rayson, ISSI, GigaDevice) com tabelas de decodificação de Part Numbers (anatomy tables), metodologia de detecção de chips remarked e hierarquia de viabilidade comercial.

**Engine de classificação** — ao digitar um PN na busca, o sistema roda em sequência:

1. **Prefixo** (client-side, instantâneo) — identifica fabricante e tipo pelo prefixo gravado no chip
2. **Banco de PNs confirmados** — um `KnownPart` com `confidence` ∈ (`confirmed`, `manual`) é autoritativo e vence a gramática
3. **Gramática** (server-side) — decodifica cada posição do PN usando as regras da família (ex: posição 3 = capacidade) para a cauda longa de PNs ainda não confirmados
4. **Fuzzy matching** (último recurso) — sugestões por similaridade para erros de digitação quando nada casa

Se a gramática e o banco divergirem na capacidade, o sistema sinaliza automaticamente possível **chip remarked**.

---

## Stack

- **Django 4.2** + **PostgreSQL**
- **HTMX 2.0** — decode card server-rendered, sem SPA
- **CKEditor 4** — edição de conteúdo das páginas de documentação via admin
- **curl_cffi + Playwright** — scraping de catálogos de fabricantes para coleta de PNs

---

## Pré-requisitos

- Python 3.11+
- PostgreSQL rodando localmente

---

## Instalação

### 1. Clonar e instalar dependências

```bash
git clone https://github.com/seu-usuario/whatthechip.git
cd whatthechip/chipdocs
pip install -r requirements.txt
```

### 2. Configurar o banco de dados

Crie o banco no PostgreSQL:

```sql
CREATE DATABASE whatthechip;
CREATE USER wtc_user WITH PASSWORD 'sua_senha';
GRANT ALL PRIVILEGES ON DATABASE whatthechip TO wtc_user;
```

### 3. Criar o arquivo `.env`

```bash
# chipdocs/.env
DJANGO_SECRET_KEY=uma-chave-secreta-longa-e-aleatoria

# Configuração do banco (ajuste conforme seu setup)
DB_NAME=whatthechip
DB_USER=wtc_user
DB_PASSWORD=sua_senha
DB_HOST=localhost
DB_PORT=5432
```

> O `.env` já está no `.gitignore` — nunca commite esse arquivo.

### 4. Ativar o sistema de classificação

```bash
bash setup.sh
```

Esse script faz tudo em ordem:
- Aplica as migrations (cria as tabelas do engine no banco)
- Importa os dados do chipid: famílias Samsung com regras de decode + ~383 PNs enriquecidos + ~3.900 PNs raw
- Adiciona famílias para SK Hynix, Micron, KIOXIA, Nanya e Kingston
- Vincula cada família à sua página de documentação

> **Nota:** o `setup.sh` espera encontrar os dados originais do chipid em `../chipid_data/`. Se você não tem esse diretório, o passo de importação será pulado e o banco iniciará vazio — funcional, mas sem os PNs pré-carregados.

### 5. Rodar o servidor

```bash
python manage.py runserver
```

Acesse `http://localhost:8000`.

---

## Estrutura do projeto

```
chipdocs/
├── chips/                      ← Engine de classificação de chips
│   ├── engine.py               ← Lógica central (4 camadas)
│   ├── models.py               ← Brand, ChipFamily, DecodeMap, KnownPart, SearchLog...
│   ├── admin.py                ← Admin com badges de status e filtros
│   ├── views.py                ← /chips/search/ (JSON) · /chips/decode/ (HTMX) · /chips/stats/
│   ├── templates/chips/partials/
│   │   └── decode_card.html    ← Partial server-rendered injetado pelo HTMX
│   └── management/commands/
│       ├── import_chipid.py    ← Importa dados do chipid (SQLite + JSONs)
│       ├── add_chip_families.py← Famílias SK Hynix, Micron, KIOXIA, Nanya, Kingston
│       └── link_doc_pages.py   ← Vincula ChipFamilies às páginas de documentação
├── pages/                      ← App de documentação com CKEditor
├── core/                       ← settings.py, urls.py
├── templates/                  ← base.html (topbar, sidenav, dark mode, HTMX)
├── scripts/
│   └── collect_pns.py          ← Scraping de PNs de distribuidores e fabricantes
├── _content/                   ← HTML fonte das páginas (index.html = homepage)
├── _template/                  ← CSS e JS base do site estático
├── setup.sh                    ← Script de ativação completo
└── requirements.txt
```

---

## Administração

Acesse `/admin/` com um superusuário:

```bash
python manage.py createsuperuser
```

Principais seções:
- **Chips → ChipFamilies** — famílias de chips com regras de decode posicional. Adicione `decode_cap_pos` e `decode_cap_map` para ampliar a cobertura da gramática.
- **Chips → KnownParts** — banco de PNs confirmados. Um registro é autoritativo (vence a gramática) quando `confidence` ∈ (`confirmed`, `manual`). Use os filtros por `confidence` para ver o que ainda precisa de confirmação.
- **Chips → SearchLogs** — log de cada busca com a fonte usada (grammar, db_exact, not_found). Útil para medir cobertura.
- **Pages** — conteúdo editorial das páginas de documentação via CKEditor.

---

## Workflow de desenvolvimento

### Editar conteúdo da homepage

```bash
# Edite _content/index.html
# Salve — o Django lê o arquivo direto. Nenhum comando necessário.
git add -A && git commit -m "frontend: ..." && git push
```

### Editar CSS ou JS

```bash
# Edite static/css/style.css ou static/js/script.js
# Salve e recarregue o navegador.
git add -A && git commit -m "style: ..." && git push
```

### Confirmar specs de PNs

As specs entram no banco por **confirmação manual** (datasheet / DigiKey / Octopart),
não por IA. O fluxo é editar os comandos de pipeline e rodá-los:

```bash
# Gabaritos curados por marca (famílias + DecodeMaps + KnownParts confirmados)
python manage.py populate_samsung
python manage.py populate_micron_mcp

# Importadores de catálogo
python manage.py import_micron_catalog *_full-catalog.csv

# Correções curadas (força confidence=confirmed)
python manage.py fix_known_parts
```

Pontualmente, dá para confirmar/editar um `KnownPart` direto no admin
(`confidence` = `confirmed`/`manual` para vencer a gramática).

### Coletar novos PNs

```bash
cd scripts/
python collect_pns.py --brand "SK Hynix"
python collect_pns.py --brand Micron --sources preduo,glochip
python collect_pns.py --list-brands
```

---

## Como a busca funciona

**Camada 1 — prefixo (instantânea):** ao digitar qualquer coisa, o JS filtra client-side a tabela de prefixos embutida na página. Resultado imediato sem requisição ao servidor.

**Camada 2 — decode card (6+ caracteres):** após 350ms sem digitar, o HTMX dispara `GET /chips/decode/?pn=XXX`. O servidor roda o engine, renderiza `decode_card.html` e injeta o resultado no `#dc-result` da página — sem JavaScript de manipulação de DOM.

O decode card exibe: fabricante, tipo, subtype, capacidade/densidade, RAM+NAND (para eMCPs), dispositivo compatível, nível de confiança, link para a documentação da família e alerta de remarked quando detectado.

---

## Dependências do sistema

```
Django>=4.2
django-ckeditor>=6.7
Pillow>=10.0
psycopg2-binary>=2.9
python-dotenv>=1.0
curl_cffi>=0.7
playwright>=1.40
tqdm>=4.0
```

---

*WhatTheChip — Revisão 5.0 · maio de 2026*
