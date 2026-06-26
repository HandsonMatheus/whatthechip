# 🚀 Deploy do WhatTheChip no Render

> **Estado atual:** Junho 2026 · **Render** (Free Tier) · **Django 5.2.15 (LTS) + Python 3.11.9**
>
> **Fonte da verdade:** este documento + os arquivos de config na raiz (`Procfile`,
> `runtime.txt`, `requirements-render.txt`) + `core/settings.py`. Em qualquer
> conflito, **o código vence**.

---

## Visão geral

- **Hospedagem:** Render **Web Service** (Free) + banco **PostgreSQL** no Render.
- **Servidor:** `gunicorn`; estáticos servidos pela **WhiteNoise** (sem nginx).
- **Repositório:** `github.com/HandsonMatheus/whatthechip` (remote `origin`).
  **Push em `main` → deploy automático** no Render.
- ⚠️ **A raiz do repositório É o projeto Django** (`manage.py`, `core/`, `Procfile`
  estão na raiz). **Não existe** subpasta `chipdocs/` dentro do repo — por isso os
  comandos **não** usam `cd chipdocs`. (A pasta local pode se chamar `chipdocs`, mas
  ela mesma é a raiz do git.)

---

## 1. Arquivos de configuração (na raiz, versionados)

### `Procfile`
```
web: gunicorn core.wsgi --bind 0.0.0.0:$PORT
```

### `runtime.txt`
```
python-3.11.9
```
⚠️ **Django 5.2.x (LTS) roda em Python 3.11.** O **Django 6.0 exige Python 3.12+** —
se for subir o Django para 6.x, **suba também o `runtime.txt` para 3.12**, senão o
build no Render quebra. (Ver regra de ouro / armadilhas no `CLAUDE.md`.)

### `requirements-render.txt` (produção)
Lista enxuta para produção — **sem** os scrapers locais (`curl_cffi`, `playwright`,
`pdfplumber`). Principais pacotes:

```
Django==5.2.15        # pin LTS — manter igual ao requirements.txt
psycopg2-binary
dj-database-url        # lê DATABASE_URL do Render
gunicorn               # servidor WSGI de produção
whitenoise             # estáticos sem nginx
python-dotenv
Pillow, tqdm, openpyxl
```

> **Por que dois arquivos?** `requirements.txt` é o ambiente local completo (com
> scrapers); `requirements-render.txt` é o de produção. **Mantenha os dois em
> sincronia** ao adicionar libs de runtime — em especial, **o pin do Django deve
> ser idêntico nos dois**.

---

## 2. Configuração do Web Service (painel do Render)

Não há `render.yaml` no repo — a configuração vive no **dashboard do Render**. Se
mudar a estrutura do repositório, ajuste os comandos abaixo no painel.

| Campo | Valor |
|---|---|
| **Name** | `whatthechip` |
| **Language / Environment** | `Python 3` |
| **Branch** | `main` |
| **Build Command** | `pip install -r requirements-render.txt && python manage.py migrate && python manage.py collectstatic --noinput` |
| **Start Command** | `gunicorn core.wsgi --bind 0.0.0.0:$PORT` |
| **Plan** | `Free` |
| **Auto-Deploy** | `Yes` (redeploy automático a cada push em `main`) |

---

## 3. Banco de dados PostgreSQL

1. No dashboard: **New + → PostgreSQL**.
   - **Name:** `whatthechip-db` · **Database:** `whatthechip` · **User:** `wtc_user`
   - **Region:** a mesma do Web Service · **Plan:** `Free`
2. **Conecte o banco ao Web Service** — o Render injeta a env var **`DATABASE_URL`**
   automaticamente.
3. `core/settings.py` lê `DATABASE_URL` via **`dj-database-url`** (`conn_max_age=600`).
   Sem `DATABASE_URL`, ele cai nas variáveis `DB_NAME/USER/PASSWORD/HOST/PORT`
   (padrão de desenvolvimento local).

---

## 4. Variáveis de ambiente (Web Service → Environment)

Estas são as variáveis **realmente lidas** por `core/settings.py`:

| Variável | Obrigatória | Observação |
|---|---|---|
| `DATABASE_URL` | sim (prod) | Render injeta ao conectar o Postgres. |
| `DJANGO_SECRET_KEY` | **sim** | Gere uma chave forte (comando abaixo). Sem ela, o código usa um fallback **inseguro** só para dev. |
| `DEBUG` | **sim** | `False` em produção. ⚠️ O default do código é `True`. |
| `RENDER_EXTERNAL_HOSTNAME` | automática | O Render injeta; `ALLOWED_HOSTS` já a inclui. |

> `NEXAR_CLIENT_ID` / `NEXAR_CLIENT_SECRET` **não** são necessárias no Render — são
> usadas apenas por scripts locais (`scripts/nexar_validate.py`).

Gerar uma `SECRET_KEY`:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 5. Arquivos estáticos

Servidos pela **WhiteNoise** com `CompressedManifestStaticFilesStorage`. O
`collectstatic` roda no **Build Command** e gera `staticfiles/`
(`STATIC_ROOT = BASE_DIR/'staticfiles'`). Não há nginx.

---

## 6. Migrations e comandos de gestão

- O **Build Command** roda `migrate` a cada deploy.
- O Render free **não oferece shell interativo**. Para comandos pontuais
  (`createsuperuser`, `populate_*`, `fix_known_parts`), rode **localmente apontando
  para o banco do Render**:

```bash
export DATABASE_URL="postgresql://wtc_user:SENHA@dpg-xxxx.render.com:5432/whatthechip"
python manage.py createsuperuser
python manage.py migrate
```

> ⚠️ Comandos que **escrevem no banco de produção** devem ser feitos com cuidado e,
> de preferência, revisados antes (ver regras de ouro no `CLAUDE.md`).

---

## 7. Armadilhas de produção

- **Postgres free ≈ 10 conexões** simultâneas (`"too many connections"`).
  `conn_max_age=600` ajuda; se estourar, upgrade do plano ou PgBouncer.
- **Cold start:** o free tier hiberna após inatividade — a 1ª requisição demora.
- **Cache de gramática (`lru_cache`):** um **novo deploy reinicia o gunicorn** e
  limpa o cache do engine. Mas alterações feitas **direto no banco** (via
  `DATABASE_URL` local) **não** reiniciam a prod — só refletem após o próximo
  deploy/restart. (Ver regra de ouro #3 no `CLAUDE.md`.)
- **`DEBUG`:** o default do código é `True` — garanta `DEBUG=False` no Render.
- **`SECRET_KEY`:** garanta `DJANGO_SECRET_KEY` setada (o fallback é só para dev).
- **Django 6.0 / Python 3.12:** ver §1.

### Hardening recomendado (ainda NÃO configurado)

`core/settings.py` **não** define hoje redirect HTTPS nem cookies seguros. Para
produção, considere adicionar (guardado por `not DEBUG` para não atrapalhar o dev):

```python
SECURE_SSL_REDIRECT   = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE    = not DEBUG
# Render termina o TLS no proxy — necessário para o Django reconhecer HTTPS:
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

---

## 8. Troubleshooting

| Sintoma | Causa provável / solução |
|---|---|
| `ModuleNotFoundError: No module named 'X'` | Pacote não está em **`requirements-render.txt`** (Render usa este, não o `requirements.txt`). Adicione e faça push. |
| `DATABASES is improperly configured` | `DATABASE_URL` ausente no Environment, ou Postgres fora do ar. |
| App no ar mas **banco vazio** | Rode `migrate` / `populate_*` via `DATABASE_URL` local (§6). |
| `Too many connections` | Limite do Postgres free (§7). |
| **Build quebrou após bump do Django** | Python incompatível — Django 6.0 exige 3.12+ (§1). |
| `DisallowedHost` / 400 | Falta `RENDER_EXTERNAL_HOSTNAME` (normalmente automática) ou host fora de `ALLOWED_HOSTS`. |

---

## 9. Checklist de deploy

- [ ] `Procfile`, `runtime.txt`, `requirements-render.txt` na raiz e versionados
- [ ] Build/Start Commands no painel **sem** `cd chipdocs`
- [ ] PostgreSQL criado e **conectado** (DATABASE_URL injetada)
- [ ] `DJANGO_SECRET_KEY` definida e `DEBUG=False` no Environment
- [ ] Deploy verde; `migrate` + `collectstatic` rodaram no build
- [ ] `/admin/` acessível; superusuário criado (via `DATABASE_URL` local)

---

## 📚 Referências

- [Render — Deploy Django](https://render.com/docs/deploy-django)
- [Django 5.2 — Settings](https://docs.djangoproject.com/en/5.2/ref/settings/)
- [Gunicorn](https://docs.gunicorn.org/) · [WhiteNoise](https://whitenoise.readthedocs.io/)

---

> Dúvidas em algum passo? O `CLAUDE.md` na raiz tem o panorama geral do projeto;
> este doc cobre só o deploy.
