# Instrução para o próximo chat — WhatTheChip Motor de Classificação

## Contexto do projeto
Django app de classificação de chips IC para o mercado de reciclagem eletrônica.
Pasta do projeto: `/Users/raphaelsilvabastos/Documents/WhatTheChip/chipdocs/`

O usuário testa chips digitando PNs no campo de busca, copia o debug (botão 📋 Debug)
e manda para um classificador IA externo. O classificador detecta erros e o usuário
traz aqui para corrigir o código. **Você só edita arquivos — nunca roda o servidor.**

---

## Fluxo de trabalho padrão

1. Usuário cola um **bloco de debug** (PN + JSON completo) + análise do classificador externo
2. Você lê o debug, **forma sua própria opinião** antes de aceitar a análise externa
3. Se concordar: faz a correção mínima no arquivo correto
4. Se discordar: explica o motivo e não muda nada (ver seção "Armadilhas")
5. Verifica sintaxe com `ast.parse` via bash
6. Resposta curta: diz o que mudou e por quê

---

## Arquivos que você vai editar

### `chips/management/commands/populate_samsung.py`
**O gabarito principal.** Toda edição aqui vale para TODOS os chips da família, não só o PN testado.

Contém:
- `SAM_EMCP_CAP` — mapa de capacidade eMCP/uMCP (2 chars, pn[3:5]) → (NAND_GB, RAM_GB)
- `SAM_FLASH_CAP` — mapa Flash standalone (1 char, pn[3]) → capacidade
- `SAM_EMCP_GEN` — mapa geração RAM (1 char, pn[2]) → tipo LPDDR
- `_families()` — lista de ChipFamily: prefixo, chip_type, decode rules

Após qualquer edição, rodar no servidor:
```bash
python manage.py populate_samsung --overwrite
# reiniciar Django (limpa lru_cache)
```

### `chips/management/commands/fix_known_parts.py`
Correções de registros sujos no banco (dados errados de distribuidores ou Gemini).
Rodar: `python manage.py fix_known_parts`

### `chips/management/commands/add_chip_families.py`
Famílias de outras marcas (SK Hynix, Micron, KIOXIA, Nanya, Kingston + Samsung NAND K9x).
**Atenção:** KLUDG foi removido daqui (era Kioxia por engano — é Samsung UFS 2.1).

### `_content/index.html` / `static/css/style.css`
Frontend. Após editar, rodar: `python manage.py sync_index_page`

---

## Estado atual do SAM_EMCP_CAP (36 chaves mapeadas)

Chaves de entrada/resíduo (NAND ≤ 8GB → vai para resíduo):
- `11` → 4GB + 512MB
- `72` → 8GB + 1GB
- `5X` → 8GB + 1GB
- `8X` → 8GB + 1GB  ← adicionado nesta sessão (KMR8X0001M)
- `NW` → 8GB + 1GB  ← adicionado nesta sessão (KMRNW0001M)

Chaves mid-range:
- `82` → 16GB + 1GB
- `31` → 16GB + 2GB
- `E1` → 16GB + 2GB  ← adicionado nesta sessão (KMQE10013M)
- `BT` → 16GB + 2GB
- `V7` → 16GB + 2GB
- `21` → 32GB + 2GB
- `41` → 32GB + 4GB
- `D6` → 32GB + 3GB
- `E6` → 32GB + 3GB  (alias D6)
- `G6` → 32GB + 3GB  ← adicionado nesta sessão (KMDG6001BM)
- `V6` → 32GB + 3GB  (alias D6)
- `GD` → 32GB + 3GB
- `W7` → 32GB + 3GB  (alias GD)
- `W8` → 32GB + 4GB

Chaves premium:
- `X1` → 64GB + 4GB
- `H9` → 64GB + 4GB  (alias X1)
- `U6` → 64GB + 3GB
- `X6` → 64GB + 3GB  (alias U6)
- `T6` → 64GB + 4GB
- `H6` → 64GB + 4GB
- `P6` → 64GB + 4GB  (KMDP6001DA — P não é cap Flash, é densidade RAM)
- `M4` → 128GB + 4GB
- `Y6` → 128GB + 4GB
- `K6` → 128GB + 8GB
- `J2` → 128GB + 6GB  ← NÃO ALTERAR (confirmado KMQJ2, ver armadilha abaixo)
- `V8` → 128GB + 8GB  ← adicionado nesta sessão (KM8V8001JM)
- `L6` → 256GB + 8GB
- `P5` → 256GB + 8GB

Chaves NVMe BGA (mapa KUS_CAP separado):
- `02` → 128GB, `03` → 256GB, `04` → 512GB, `05` → 1TB

**Chaves ainda não mapeadas** (vão para Gemini): Z6, e várias de alta densidade (512GB+12GB, etc.)

---

## Famílias Samsung definidas (população atual)

### Flash standalone
- `KLM` — eMMC Samsung (decode: SAM_FLASH_CAP pn[3])
- `KLU` — UFS Samsung genérico (decode: SAM_FLASH_CAP pn[3])
- `KLUDG` — UFS 2.1 Samsung ← adicionado (era Kioxia por engano em add_chip_families.py)
- `KLUCG` — UFS 2.0 Samsung ← adicionado
- `KLUFG` — UFS 3.1 Samsung ← adicionado

### eMCP clássico (KM + LETRA na 3ª pos)
- `KMJ/KMK` — LPDDR2 + eMMC (legado)
- `KMF/KMN/KMQ` — LPDDR3 + eMMC 5.1
- `KMR` — LPDDR4/4X + eMMC 5.1
- `KMS` — LPDDR4X + eMMC 5.1
- `KMD` — LPDDR4X + eMMC 5.1 (NÃO uMCP)
- `KMV` — LPDDR2 + eMMC (legado, separado de KMV2/KMV3)

### eMCP com dígito numérico na 3ª pos (decode_gen_pos=None OBRIGATÓRIO)
- `KM4` — LPDDR4 + eMMC 5.1 ← adicionado nesta sessão
  - decode_gen_pos=None (o '4' não é letra de geração RAM)

### uMCP (UFS + LPDDR)
- `KMG` — UFS 3.1 + LPDDR4X
- `KML` — UFS 3.1 + LPDDR5
- `KMV2/KMV3` — UFS 4.0 + LPDDR5X (flagship)

### uMCP linha numérica (decode_gen_pos=None OBRIGATÓRIO)
- `KM8` — UFS + LPDDR4X/5X ← decode_gen_pos=None + decode_cap_map adicionados
- `KM5` — UFS + LPDDR4X/5X ← idem
- `KM2` — UFS 3.1 + LPDDR5 (ultra-premium) ← adicionado nesta sessão
- `KM1` — UFS 4.0 + LPDDR5X (ultra-premium) ← adicionado nesta sessão

### Fallbacks genéricos
- `KM` — eMCP Samsung genérico (priority=90, captura qualquer KM não mapeado)
- `K3` — LPDDR2/3 legado (priority=90)

---

## Regra crítica: decode_gen_pos para famílias numéricas

**Qualquer família KM + DÍGITO na 3ª posição DEVE ter `decode_gen_pos=None`.**

O SAM_EMCP_GEN contém apenas letras (J, K, F, N, Q, R, S, D, E, G, L, V).
Se decode_gen_pos aponta para uma posição com dígito, o engine gera:
`"tipo 'X' — consultar datasheet"` colado no valor do DB → Frankenstein de texto.

Famílias afetadas: KM1, KM2, KM4, KM5, KM8, KMV (legado — decode_gen_pos=None por motivo diferente).

---

## Loop de upsert no populate_samsung (comportamento atual)

```python
# Busca por prefix SEM brand (corrige entradas com brand errado)
fam = ChipFamily.objects.filter(prefix=prefix).first()
# Quando brand muda, zera doc_page (herda da nova marca)
brand_changed = (not created) and (fam.brand_id != samsung.pk)
if brand_changed:
    fam.doc_page = None
fam.brand = samsung
```

Isso garante que famílias cadastradas erradas (ex: KLUDG como Kioxia) são migradas
para Samsung sem criar duplicatas, e o doc_url deixa de apontar para /fab-toshiba/.

---

## Armadilhas conhecidas — NÃO cair nelas

### 1. J2 ≠ 8GB + 1GB
O classificador externo uma vez sugeriu mudar `J2` para 8GB + 1GB alegando ser
"Galaxy Grand Prime". **Errado.** J2 = 128GB + 6GB, confirmado por KMQJ20013M.
O chip barato do Grand Prime era KMRNW (cap_key NW = 8GB + 1GB).

### 2. KMFJ20005AB213 — PN com sufixo de lote
PN de 14 chars (normal é 10). Os últimos chars (AB213, B213) são código de lote
do operador, não parte do PN. O decode em pn[3:5] = "J2" está correto → 128GB + 6GB.
Não mudar J2 por causa desse PN.

### 3. KLUDG não é Kioxia
A entrada KLUDG foi removida de add_chip_families.py (onde estava como Kioxia).
Agora está em populate_samsung.py como Samsung UFS 2.1.
Se rodar add_chip_families --overwrite, não vai recriar a entrada Kioxia.

### 4. KMD é eMCP, não uMCP
KMD (LPDDR4X + eMMC 5.1) foi historicamente confundido com uMCP.
O armazenamento é eMMC — NÃO UFS. Famílias uMCP Samsung começam em KMG.

### 5. Classificador externo nem sempre tem razão
O classificador acerta ~90% das vezes, mas comete erros históricos (confunde eras,
mistura famílias). Sempre verificar contra os padrões internos antes de editar.

---

## Correções pendentes de banco (rodar no servidor)

```bash
# Aplica todas as novas chaves e famílias desta sessão
python manage.py populate_samsung --overwrite

# Limpa KnownParts sujos
python manage.py fix_known_parts

# Atualiza frontend (debug button, dc-incomplete banner)
python manage.py sync_index_page

# Reiniciar Django (limpa lru_cache de famílias e decode maps)
```

### fix_known_parts — correções pendentes no banco:
- `KMDP6001DA` — RAM corrigida para LPDDR4X 4GB (era 6GB de distribuidor)
- `KMQD60013M` — RAM corrigida para LPDDR3 3GB (era 2GB de distribuidor)
- `KMRNW0001M` — NAND/RAM corrigidos (era alucinação Gemini 64GB+4GB)
- `KMGD6001BM` — NAND/interface corrigidos (era eMMC, é UFS 3.1)
- `KLUDG4U1EA` — capacity=128GB, interface=UFS 2.1, device limpo

---

## Como ler um bloco de debug

Campos mais importantes para diagnóstico:

| Campo | O que indica |
|-------|-------------|
| `classification_source` | `gramática` = só o código local; `gramática+db` = complementou com banco; `db` = só banco |
| `known_exact` | `true` = tinha KnownPart exato no banco |
| `family_prefix` | qual família foi matched (prefixo mais longo vence) |
| `emcp_source` | onde vieram os valores de NAND/RAM |
| `source_url` | `gemini:PN` = Gemini já tinha consultado e guardado no banco |
| `Gemini: não executado` | gramática ou banco resolveu sem chamar API |

### Diagnóstico rápido por sintoma:

**"tipo 'X' — consultar datasheet"** no emcp_ram
→ pn[2] é dígito (KM1/2/4/5/8), falta `decode_gen_pos=None` na família

**capacidade em branco + classification_source=gramática**
→ cap_key (pn[3:5]) não está no SAM_EMCP_CAP → adicionar chave

**classification_source=gramática+db / source_url=gemini:PN**
→ cap_key ausente no mapa local, DB/Gemini preencheu → adicionar chave para tornar gramática pura

**brand errado (ex: Kioxia em vez de Samsung)**
→ família com prefix mais longo cadastrada com brand errado → adicionar prefix correto em populate_samsung + rodar --overwrite

**doc_url apontando para marca errada**
→ family.doc_page herdado da marca anterior → resolvido pelo loop de upsert (doc_page=None ao migrar brand)

**família caindo no fallback KM genérico**
→ prefixo específico não está em _families() → adicionar entrada com priority < 90

---

## Verificação de sintaxe (sempre rodar após editar)

```bash
cd /sessions/confident-nifty-rubin/mnt/chipdocs
python -c "import ast; ast.parse(open('chips/management/commands/populate_samsung.py').read()); print('✓ ok')"
```
