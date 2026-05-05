# WhatTheChip?

Guia técnico de identificação e classificação de chips IC para o mercado de refurbishing e reciclagem eletrônica — combinando documentação editorial com um engine de decodificação de Part Numbers.

Digite `KMQ310006A` e o sistema responde: *Samsung eMCP — LPDDR3 1GB + eMMC 4GB — Galaxy J3/J5 (2016)*.

---

## O que o projeto faz

**Documentação** — guias por fabricante (Samsung, SK Hynix, Micron, Elpida, Toshiba/KIOXIA, SanDisk/WD, Nanya, Kingston, Rayson, ISSI, GigaDevice) com tabelas de decodificação de Part Numbers (anatomy tables), metodologia de detecção de chips remarked e hierarquia de viabilidade comercial.

**Engine de classificação** — ao digitar um PN na busca, o sistema roda 4 camadas em sequência:

1. **Prefixo** (client-side, instantâneo) — identifica fabricante e tipo pelo prefixo gravado no chip
2. **Gramática** (server-side) — decodifica cada posição do PN usando as regras da família (ex: posição 3 = capacidade)
3. **Banco de PNs** — confirma ou enriquece com dados que a gramática não consegue extrair (RAM+NAND de eMCPs, dispositivo compatível, confiança)
4. **Gemini** (fallback) — para PNs sem família mapeada ou sem dados no banco

Se a gramática e o banco divergirem na capacidade, o sistema sinaliza automaticamente possível **chip remarked**.

---

## Stack

- **Django 4.2** + **PostgreSQL**
- **HTMX 2.0** — decode card server-rendered, sem SPA
- **CKEditor 4** — edição de conteúdo das páginas de documentação via admin
- **Gemini 2.5 Pro/Flash** — fallback de classificação com Google Search Grounding
- **curl_cffi + Playwright** — scraping de catálogos de fabricantes para coleta de PNs

---

## Pré-requisitos

- Python 3.11+
- PostgreSQL rodando localmente
- Conta Google AI Studio com chave de API Gemini (para o fallback de classificação)

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
GEMINI_API_KEY=sua-chave-do-google-ai-studio

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
│   ├── collect_pns.py          ← Scraping de PNs de distribuidores e fabricantes
│   └── enrich_gemini.py        ← Enriquecimento em batch via Gemini
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
- **Chips → ChipFamilies** — famílias de chips com regras de decode posicional. Adicione `decode_cap_pos` e `decode_cap_map` para reduzir chamadas ao Gemini.
- **Chips → KnownParts** — banco de PNs com status `raw` / `enriched` / `failed`. Use os filtros para ver a fila de enriquecimento.
- **Chips → SearchLogs** — log de cada busca com a fonte usada (grammar, db_exact, gemini, not_found). Útil para medir cobertura.
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

### Enriquecer PNs raw com Gemini

```bash
cd scripts/

# Processa 50 PNs Samsung por rodada
python enrich_gemini.py --brand Samsung --limit 50

# Mais workers para acelerar (cuidado com rate limit da API)
python enrich_gemini.py --brand Samsung --workers 3 --limit 200

# Re-tentar os que falharam
python enrich_gemini.py --brand Samsung --retry-failed
```

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
google-generativeai>=0.5
```

Modelos Gemini ativos: `gemini-2.5-pro` (preferencial) e `gemini-2.5-flash` (fallback).

---

*WhatTheChip — Revisão 5.0 · maio de 2026*
