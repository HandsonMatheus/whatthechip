# Setup — Integração chipid → WhatTheChip

Passos para ativar a fusão. Execute dentro de `chipdocs/`.

## 1. Instalar dependências novas

```bash
pip install python-dotenv curl_cffi tqdm
pip install playwright && playwright install chromium   # opcional, para scraping
```

## 2. Criar o arquivo .env

```bash
# chipdocs/.env  (não commitar!)
DJANGO_SECRET_KEY=uma-chave-secreta-longa-e-aleatoria
# Banco (DATABASE_URL ou DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT)
```

## 3. Rodar a migration

```bash
python manage.py migrate
```

> Se der erro de dependência com `pages`, verifique que a migration `pages/0001_initial.py`
> existe. Se não existir, rode `python manage.py makemigrations pages` antes.

## 4. Importar os dados do chipid

```bash
python manage.py import_chipid \
    --sqlite /caminho/para/chipid_project/db.sqlite3 \
    --state-dir /caminho/para/chipid_project/scripts/state
```

Isso importa:
- Brands (Samsung, Micron, SK Hynix, KIOXIA…)
- ChipFamilies com regras de decodificação
- DecodeMaps (CAP_MAP, DRAM_PC, DRAM_MOBILE, EMMC_GEN)
- ~383 KnownParts enriquecidos (Samsung eMCPs com device + capacidade)
- ~3.900+ PNs raw de todas as marcas (na fila de enriquecimento)

## 5. Vincular doc_page nas famílias (admin)

Acesse `/admin/chips/chipfamily/` e vincule cada família à sua página de documentação:

| Família (prefix) | doc_page slug |
|------------------|---------------|
| KLM, KLU, KM, K4B, K4A… | fab-samsung |
| H5AN, H9TQ, HKMAG… | fab-hynix |
| MT40A, MTFC, MT29… | fab-micron |
| NT5, NT5CC… | fab-nanya |
| … | … |

## 6. Testar a busca

Inicie o servidor e teste na página inicial:

- `KLM` → prefixo Samsung eMMC (camada 1, instantâneo)
- `KMQ310006A` → Samsung eMCP com LPDDR3 1GB / eMMC 4GB / Galaxy J3/J5 (camada 2, banco)
- `K4B4G16E` → Samsung DDR3 com densidade decodificada pela gramática (camada 2, gramática)
- `H9TQ64A8MDAC` → SK Hynix eMCP; se não estiver no banco, decodificado pela gramática (camada 2)

## 7. Confirmar specs de PNs (quando quiser)

As specs entram no banco por **confirmação manual** (datasheet / DigiKey / Octopart),
não por IA. Edite os comandos de pipeline e rode-os:

```bash
# Gabaritos curados (famílias + DecodeMaps + KnownParts confirmados)
python manage.py populate_samsung
python manage.py import_micron_catalog *_full-catalog.csv
python manage.py fix_known_parts   # correções curadas (força confidence=confirmed)
```

Pontualmente, dá para confirmar/editar um `KnownPart` direto no admin
(`confidence` = `confirmed`/`manual` para vencer a gramática).

## 8. Coletar novos PNs (quando quiser expandir)

```bash
cd scripts/
python collect_pns.py --brand "SK Hynix"
python collect_pns.py --brand Micron --sources preduo,glochip
python collect_pns.py --list-brands    # lista todas as marcas suportadas
```
