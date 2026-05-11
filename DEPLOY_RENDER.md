# 🚀 GUIA COMPLETO: DEPLOY DO WHATTHECHIP NO RENDER

> **Data:** Maio 2026 | **Projeto:** WhatTheChip | **Plataforma:** Render (Free Tier)

---

## 📋 PRÉ-REQUISITOS

- ✅ Repositório GitHub: `https://github.com/HandsonMatheus/whatthechip.git`
- ✅ Conta Render: [render.com](https://render.com)
- ✅ Chave da API Google Gemini
- ✅ Projeto sem Playwright instalado

---

## PASSO 1: PREPARAR O REPOSITÓRIO

### 1.1 Criar arquivo `Procfile` (raiz do projeto)

```bash
# Na raiz, FORA de chipdocs/
echo "web: cd chipdocs && gunicorn core.wsgi --bind 0.0.0.0:$PORT" > Procfile
```

**Exemplo de estrutura:**
```
whatthechip/
├── Procfile                    ← NOVO
├── runtime.txt                 ← NOVO
├── requirements-render.txt     ← NOVO
└── chipdocs/
    ├── manage.py
    ├── requirements.txt
    ├── core/
    └── ...
```

### 1.2 Criar arquivo `runtime.txt` (raiz do projeto)

```bash
echo "python-3.11.9" > runtime.txt
```

### 1.3 Criar arquivo `requirements-render.txt` (raiz do projeto)

```bash
cat > requirements-render.txt << 'EOF'
# Core
Django>=4.2
psycopg2-binary>=2.9
Pillow>=10.0

# Production
gunicorn>=21.0
whitenoise>=6.5
python-dotenv>=1.0

# Admin & Editor
django-ckeditor>=6.7

# Google AI
google-generativeai>=0.5

# Utilities
tqdm>=4.0
EOF
```

**Por que `requirements-render.txt`?**
- Render usa este arquivo (não o local)
- Remove `curl_cffi` e `playwright` (não precisam)
- Adiciona `gunicorn` e `whitenoise` (necessários para produção)

### 1.4 Atualizar `chipdocs/core/settings.py`

**Adicione no topo do arquivo:**
```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
```

**Encontre a seção `DATABASES` e substitua por:**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'whatthechip'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}
```

**Encontre `ALLOWED_HOSTS` e substitua por:**
```python
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    os.getenv('RENDER_EXTERNAL_HOSTNAME', 'localhost'),
]
```

**Encontre `DEBUG` e substitua por:**
```python
DEBUG = os.getenv('DEBUG', 'False') == 'True'
```

**Adicione no final do arquivo:**
```python
# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Security
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
```

### 1.5 Criar arquivo `.dockerignore` (raiz)

```bash
cat > .dockerignore << 'EOF'
venv/
.git/
.gitignore
*.pyc
__pycache__/
*.db
db.sqlite3
.env
.DS_Store
*.log
node_modules/
EOF
```

### 1.6 Fazer commit e push

```bash
git add Procfile runtime.txt requirements-render.txt chipdocs/core/settings.py .dockerignore
git commit -m "chore: adicionar configuração para Render"
git push origin main
```

---

## PASSO 2: CRIAR SERVIÇO NO RENDER

### 2.1 Acessar Render

1. Acesse [render.com](https://render.com)
2. Clique em **"Sign up"** → conecte com GitHub
3. Autorize Render a acessar seus repositórios

### 2.2 Criar novo Web Service

1. No dashboard Render, clique em **"New +"** 
2. Selecione **"Web Service"**
3. Procure por `whatthechip` e clique em **"Connect"**

### 2.3 Configurar o serviço

Na página de criação, preencha:

| Campo | Valor |
|---|---|
| **Name** | `whatthechip` |
| **Environment** | `Python 3` |
| **Build Command** | `pip install -r requirements-render.txt && cd chipdocs && python manage.py migrate && python manage.py collectstatic --noinput` |
| **Start Command** | `cd chipdocs && gunicorn core.wsgi --bind 0.0.0.0:$PORT` |
| **Plan** | `Free` |
| **Auto-deploy** | `Yes` (faz redeploy automaticamente no push) |

---

## PASSO 3: ADICIONAR BANCO DE DADOS POSTGRESQL

### 3.1 Criar PostgreSQL no Render

1. No dashboard, clique em **"New +"**
2. Selecione **"PostgreSQL"**
3. Preencha:
   - **Name:** `whatthechip-db`
   - **Database:** `whatthechip`
   - **User:** `wtc_user`
   - **Region:** Mesma da Web Service
   - **Plan:** `Free`

4. Clique em **"Create Database"**
5. **Aguarde 2-3 minutos** até o banco estar pronto

### 3.2 Copiar credenciais do banco

Após criação, a página mostrará:
```
External Database URL: postgresql://wtc_user:XXXX@dpg-xxxxx.render.com:5432/whatthechip
```

**Copie esta URL inteira** (vamos usar no próximo passo)

---

## PASSO 4: CONFIGURAR VARIÁVEIS DE AMBIENTE

### 4.1 Na página do Web Service (não do banco!)

1. Clique no seu serviço `whatthechip` (Web Service)
2. Vá em **"Environment"** (lado esquerdo)
3. Clique em **"Add Environment Variable"**

### 4.2 Adicionar variáveis

Adicione as seguintes variáveis:

**1. Database (CÓPIA AUTOMÁTICA)**
```
DATABASE_URL = postgresql://wtc_user:XXXX@dpg-xxxxx.render.com:5432/whatthechip
```
*(Render copia automaticamente quando você conecta o banco)*

**2. Django**
```
DJANGO_SECRET_KEY = gera-uma-chave-aleatoria-de-64-caracteres
DEBUG = False
ALLOWED_HOSTS = seu-app.onrender.com
```

Para gerar uma SECRET_KEY, use:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**3. Google Gemini**
```
GEMINI_API_KEY = sua-chave-do-google-ai-studio
```

**4. Banco de Dados (manual, se não copiar automaticamente)**
```
DB_NAME = whatthechip
DB_USER = wtc_user
DB_PASSWORD = (senha do Render PostgreSQL)
DB_HOST = (host do PostgreSQL Render)
DB_PORT = 5432
```

### 4.3 Verificar variáveis

Certifique-se de que todas estão listadas em **Environment Variables**.

---

## PASSO 5: FAZER O DEPLOY

### 5.1 Primeiro deploy

1. Volte à página do serviço `whatthechip`
2. Clique em **"Manual Deploy"** → **"Deploy latest commit"**
3. **Aguarde 5-10 minutos** (Render faz build, instala dependências, roda migrations)

### 5.2 Acompanhar o build

1. Clique em **"Logs"** para ver o progresso
2. Procure por mensagens como:
   ```
   ✓ Building Docker image...
   ✓ Running migrations...
   ✓ Collecting static files...
   ```

### 5.3 Acessar o app

Após sucesso, você receberá uma URL como:
```
https://whatthechip.onrender.com
```

Clique em **"Open"** para testar!

---

## 🔧 PASSO 6: TROUBLESHOOTING

### Erro: "ModuleNotFoundError: No module named 'xyz'"

**Solução:**
1. Verifique se o módulo está em `requirements-render.txt`
2. Faça push novamente
3. Clique em **"Manual Deploy"**

### Erro: "DATABASES is improperly configured"

**Solução:**
1. Verifique se `DATABASE_URL` está em **Environment Variables**
2. Certifique-se de que o PostgreSQL está rodando (check status em Render)

### App carrega mas banco está vazio

**Solução:** Execute migrations manualmente

1. No terminal do seu computador:
```bash
pip install python-dotenv psycopg2-binary django
export DATABASE_URL="postgresql://..."  # Cole a URL do Render
cd chipdocs
python manage.py migrate --database default
python manage.py createsuperuser
```

2. Ou pelo Render Shell (experimental):
```bash
# Render não oferece shell direto, mas você pode rodar commands assim:
# Após fazer push, edite Procfile temporariamente:
# web: cd chipdocs && python manage.py migrate
# Depois reverta
```

### "Connection refused" ou "Too many connections"

**Motivo:** Limite de 10 conexões simultâneas atingido

**Solução:**
- Upgrade para plano pago (Render Postgres Starter ~$15/mês)
- Ou configure connection pooling com PgBouncer

---

## ✅ CHECKLIST FINAL

- [ ] `Procfile` criado na raiz
- [ ] `runtime.txt` criado na raiz
- [ ] `requirements-render.txt` criado na raiz
- [ ] `chipdocs/core/settings.py` atualizado com variáveis de ambiente
- [ ] `.dockerignore` criado
- [ ] Commit feito e push para GitHub
- [ ] Web Service criado no Render
- [ ] PostgreSQL criado no Render
- [ ] Variáveis de ambiente configuradas
- [ ] Build executado com sucesso
- [ ] App acessível em `https://seu-app.onrender.com`
- [ ] Migrations rodadas
- [ ] Superusuário criado (admin)

---

## 📚 REFERÊNCIAS

- [Render Django Docs](https://render.com/docs/deploy-django)
- [Django Settings](https://docs.djangoproject.com/en/4.2/ref/settings/)
- [Gunicorn Docs](https://docs.gunicorn.org/)

---

**Pronto para fazer deploy! 🚀**

Alguma dúvida em algum passo? Manda uma mensagem que ajudo!
