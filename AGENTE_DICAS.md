# AGENTE_DICAS.md — Dicas práticas acumuladas de sessões Claude no WTC

> Complementa o CLAUDE.md (arquitetura) com experiência de sessão.
> CLAUDE.md = o QUÊ e o PORQUÊ. Este arquivo = como não se fuder.
> Atualizado: 2026-06-19.

---

## 1. Antes de qualquer coisa

**Leia CLAUDE.md inteiro.** É curto e evita que você quebre coisas.
Depois leia o arquivo específico da tarefa (ex.: SAMSUNG_PC_DRAM.md para DDR,
AUDITORIA_SAMSUNG_2026.md para eMCP/LPDDR, etc.).

**Nunca aja com base em docs em `docs/archive/`** — são históricos e podem estar
errados. O código é a fonte da verdade (`chips/engine.py`, `core/settings.py`).

---

## 2. Regras de ouro que a prática confirmou

### SUFIXO NÃO IMPORTA (Samsung PC DRAM)
O operador na bancada pode ver o chip com ou sem sufixo legível.
**Sempre adicionar PN base + cada variante sufixada confirmada.**
- ❌ Só `K4B4G1646D-BYK0` → operador digita `K4B4G1646D` → cai na gramática
- ✅ `K4B4G1646D` + `K4B4G1646D-BYK0` + `K4B4G1646D-BYNB` + …

### confidence="confirmed"/"manual" — a única coisa que torna o registro autoritativo
*(O campo `status` foi removido em jun/2026; não existe mais.)*
- `confidence="estimated"` ou `"distributor"` → gramática vence mesmo com dados corretos
- `confidence="confirmed"` ou `"manual"` → banco vence
Sempre setar `confidence="confirmed"` (ou `"manual"`) em `create_defaults` E em `fields`.

### Gramática vence quando confidence < confirmed/manual
A precedência real (não intuitiva) do engine:
- `confirmed` / `manual` → banco vence
- Qualquer outra confidence (`distributor`, `estimated`) + gramática completa → **gramática vence**
Isso significa: um registro com `confidence="distributor"` e dados perfeitos ainda
perde para a gramática. Só `confirmed`/`manual` garante que o banco vence.

### Restart após populate, nunca após fix_known_parts
- `populate_samsung --overwrite` → reiniciar o servidor (lru_cache)
- `fix_known_parts` → **não precisa** reiniciar (grava KnownParts, não toca cache)

---

## 3. Pesquisa de PNs — como confirmar com Tier 1

### Samsung Semiconductor Global (EOL desde jul/2025, mas ainda válido)
As páginas de produto individuais foram para redirect desde 31/07/2025.
**O que ainda funciona:** o Google continua indexando os títulos antigos.

```
Busca: site:semiconductor.samsung.com "K4A8G085WB-BCPB"
Título indexado: "K4A8G085WB-BCPB(8 Gb) | DRAM | Samsung Semiconductor Global"
                                ↑ este "(X Gb)" entre parênteses = Tier 1 ✓
```

Se o título vier com `(X Gb)` ou `(X Mb)`, é confirmação válida mesmo sem acessar
a página. Se só aparecer o PN sem parênteses de capacidade, não conta.

### Hierarquia de fontes (Tier 1 → não aceito)

| Tier | Fonte | Confiança |
|------|-------|-----------|
| 1 ✓ | Samsung Semiconductor Global (título indexado com "(X Gb)") | `confirmed` |
| 1 ✓ | Datasheet Samsung em download.semiconductor.samsung.com | `manual` |
| 1 ✓ | Octopart com atribuição Samsung | `confirmed` |
| 2 | iFixit teardown (identifica chip visualmente) | `manual` |
| 2 | PSG Samsung (PDF de catálogo oficial) | `confirmed` |
| 2 | Preduo / Puris (B2B rastreável) | `confirmed` |
| ❌ | Flash64Box (vídeo YouTube) | não aceito |
| ❌ | Fóruns de reparo asiáticos | não aceito |
| ❌ | WinSource sozinho | não aceito |
| ❌ | Catálogos B2B de Shenzhen | não aceito |
| ❌ | IA generalista (qualquer LLM) | não aceito |

### Estratégia de busca eficiente
1. Tente primeiro: `site:semiconductor.samsung.com "PN"` no Google
2. Se não achar: `"PN" samsung semiconductor global filetype:pdf`
3. Fallback: `"PN" site:octopart.com samsung`
4. Para famílias completas: busca por prefixo `site:semiconductor.samsung.com K4A8G085`
   para ver todos os sufixos disponíveis de uma vez

### WebFetch vs WebSearch
- `WebFetch` de `semiconductor.samsung.com` retorna HTTP 429 frequentemente
  para páginas de categoria (ddr4/, ddr5/) — use `WebSearch` neste caso
- Páginas individuais de PN às vezes funcionam com WebFetch
- Nunca use curl/wget/requests para contornar restrições de WebFetch

---

## 4. fix_known_parts — como usar corretamente

### Campos obrigatórios para DDR

```python
{
    "pn": "K4XXXXX",           # PN base sem sufixo (ou com sufixo se for variante)
    "create": True,            # cria se não existir
    "create_defaults": {       # campos usados só na criação
        "brand_name": "Samsung",
        "chip_type":  "DDR4",
        "subtype":    "DDR4 PC DRAM 8Gb x8",
        "confidence": "confirmed",
    },
    "fields": {                # campos atualizados sempre (criação E update)
        "chip_type":  "DDR4",
        "subtype":    "DDR4 PC DRAM 8Gb x8",
        "capacity":   "1GB",   # MB ou GB — nunca Gbit!
        "interface":  "DDR4",
        "confidence": "confirmed",
    },
    "reason": "Samsung Semiconductor Global: K4A8G085WB-BCPB(8 Gb) ✓. ...",
},
```

### capacity — unidades corretas
- O engine usa `_extract_gib()` que parseia "512MB", "1GB", "2GB", etc.
- **Nunca escrever em Gbit** (ex.: "8Gb") — `_extract_gib()` não parseia Gbit
- Conversão: `capacidade_GB = densidade_Gbit ÷ 8`
  - 1 Gb = 0.125 GB = 128 MB
  - 2 Gb = 256 MB
  - 4 Gb = 512 MB
  - 8 Gb = 1 GB
  - 16 Gb = 2 GB
  - 32 Gb = 4 GB

### chip_type — seja específico, não use "DDR" genérico
A gramática K4B retorna `chip_type="DDR"` — isso é correto para a gramática.
Mas no fix_known_parts, seja específico:
- Sufixo BY/MY/MM → `"DDR3L"`
- Sufixo BC → `"DDR3"`
- PN base K4B com variantes DDR3L e DDR3 → use `"DDR3L"` (mais comum/moderno)

### confidence="confirmed" vs "manual"
- `confirmed` — há URL/título Tier 1 acessível (Samsung Global indexado, Octopart)
- `manual` — só datasheet PDF (não tem página ao vivo verificável)
- Nunca use `confirmed` para dados verificados só por IA ou memória

### Não inventar famílias
Se um prefixo não tem família em `populate_samsung.py`, NÃO crie uma.
Use fix_known_parts com os PNs conhecidos. Documente o gap (ex.: K4RCH).

---

## 5. assess_profitability — entender o cálculo

### Fluxo para DDR standalone
```
chip_type + subtype → combined (uppercase)
"DDR" in combined? → sim → _ddr_generation(combined)
gen < ddr_min_gen(3)? → sim → NÃO RENTÁVEL (DDR1/DDR2)
não → checa densidade:
    gen >= 4? → min_gbit = ddr4plus_min_gbit
    gen == 3? → min_gbit = ddr3_min_gbit
    tenta dram_density field → extrai Gbit
    fallback: capacity field → _extract_gib() → ÷ 0.125 → Gbit
    densidade < min_gbit - 0.01? → NÃO RENTÁVEL
    senão → RENTÁVEL
```

### Thresholds atuais vs corretos (ProfitabilityConfig)

| Campo | Default código | Correto (eMiner) | Efeito |
|-------|---------------|-----------------|--------|
| `ddr_min_gen` | 3 | 3 | DDR1/DDR2 = NÃO RENTÁVEL ✓ |
| `ddr3_min_gbit` | 2.0 Gb | 2.0 Gb | DDR3 < 256MB = NÃO RENTÁVEL ✓ |
| `ddr4plus_min_gbit` | 8.0 Gb | **1.0 Gb** | ⚠ Ajustar no admin! |

O `ddr4plus_min_gbit=8.0` (default) classifica DDR4 4Gb (512MB) como NÃO RENTÁVEL.
O correto para eMiner é `1.0` (1 Gigabit = 128MB). Ajustar no admin Django:
`/admin/chips/profitabilityconfig/`.

### dram_density vs capacity — quando o engine usa cada um
- `dram_density` = string livre ("8Gb = 1GB por die [~]") — a gramática preenche
- `capacity` = campo estruturado ("1GB") — fix_known_parts preenche
- Engine tenta `dram_density` primeiro; fallback para `capacity`
- Para KnownParts via fix_known_parts: preencher `capacity` é suficiente

---

## 6. Debugar uma classificação errada

### Usar o painel de debug (estoque)
No painel de debug de uma busca, os campos-chave para diagnóstico:

```json
{
  "known_exact": false,       // ← false = não achou no banco
  "pn_not_in_db": true,       // ← true = PN não existe como KnownPart
  "classification_source": "gramática",  // ← confirma que veio da gramática
  "confidence": "estimated",  // ← gramática sempre dá estimated
  "in_review_queue": true,    // ← foi enfileirado para revisão
  "profitable": "NÃO RENTÁVEL"
}
```

### Checklist de diagnóstico
1. `pn_not_in_db: true` → PN não está no banco → rodar fix_known_parts
2. `pn_not_in_db: false` mas `known_exact: false` → PN no banco mas `confidence` baixa (`distributor`/`estimated`) → promover para `confirmed`/`manual`
3. `known_exact: true` mas resultado errado → verificar fields do KnownPart no admin
4. Resultado correto mas rentabilidade errada → checar ProfitabilityConfig no admin

### Verificar o que está no banco
```bash
python manage.py shell -c "
from chips.models import KnownPart
obj = KnownPart.objects.filter(pn__startswith='K4B1G').values('pn','status','confidence','chip_type','capacity')
for r in obj: print(r)
"
```

---

## 7. Famílias Samsung — mapa rápido do que existe na gramática

### Famílias com gramática em populate_samsung.py
| Prefixo | Tipo | Observações |
|---------|------|-------------|
| K4H | DDR1 | density via DRAM_PC |
| K4T | DDR2 | density via DRAM_PC |
| K4B | DDR3/DDR3L | density via DRAM_PC |
| K4A | DDR4 | density via DRAM_PC |
| K4RA | DDR5 16Gb | priority=80 |
| K4RB | DDR5 32Gb | priority=80 |
| K4R | RDRAM | priority=100 (pega K4RC se não tiver fix!) |
| K3QF / K3PE | LPDDR2/3 | mobile |
| K3RG | LPDDR4 4CH | mobile |
| K3UH | LPDDR4X | mobile |
| K3LK | LPDDR5 | mobile |
| K4E | LPDDR3 | mobile (pn[4:6]=densidade) |
| K4EBE / K4EHE | LPDDR4 | mobile |
| K4FHE / K4UJE | LPDDR4X | mobile |
| KM* | eMCP / uMCP | várias subfamílias |
| KLU* | UFS | densidade via KUS_CAP |
| KLM* | eMMC | Samsung/Kingston |

### Famílias SEM gramática (atenção especial)
| Prefixo | Tipo real | Risco |
|---------|-----------|-------|
| K4RC | DDR5 32Gb C-die | Cai em K4R → classificado como RDRAM |
| K4RD e posteriores | DDR5 futuro | Mesmo risco |

---

## 8. Dicas de workflow por tarefa

### Adicionar PNs confirmados (o workflow padrão)
1. Pesquisar no Google: `site:semiconductor.samsung.com "PN"` → confirmar "(X Gb)"
2. Anotar: chip_type, density (Gbit), bus width, die revision, sufixo
3. Calcular capacity em MB/GB: density_Gbit ÷ 8
4. Escrever entry no fix_known_parts — base PN + cada sufixo confirmado
5. Verificar sintaxe: `python3 -c "import ast; ast.parse(open('fix_known_parts.py').read()); print('OK')"`
6. Rodar local: `python manage.py fix_known_parts` e confirmar "X criado(s)"
7. Testar a busca no sistema local
8. Commitar + push + rodar fix_known_parts em produção com DATABASE_URL

### Corrigir uma classificação errada em produção
1. Reproduzir localmente com o mesmo PN
2. Ler o JSON de debug completo
3. Identificar fonte: gramática → fix_known_parts; banco com dados ruins → corrigir entry
4. Nunca editar migration já aplicada em produção — criar nova se necessário
5. Corrigir, commitar, rodar fix_known_parts com DATABASE_URL do Render

### Atualizar a gramática (populate_samsung)
1. Ler populate_samsung.py para entender o padrão atual
2. Editar o arquivo
3. Verificar sintaxe
4. Rodar: `python manage.py populate_samsung --overwrite`
5. **Reiniciar o servidor** (lru_cache — obrigatório)
6. Testar com `classify()` via shell ou interface

---

## 9. Templates Django — armadilha do `escapejs` em `data-*` (bug real)

### O problema
Django's `|escapejs` converte **`-`** (hífen) em `-` para segurança em
contextos JavaScript inline (`onclick="...'{{ s|escapejs }}'..."` → correto).

**Mas em atributos `data-*`** o comportamento é errado:
```html
<!-- ❌ ERRADO — data-suggestion recebe K4B4G1646D-BCK0 (literal 6 chars) -->
<span data-suggestion="{{ sug|escapejs }}">
<!-- JavaScript lê el.dataset.suggestion → recebe "-" como texto puro -->
<!-- el.innerHTML = ... + dif + ... → exibe "-" em vez de "-"           -->

<!-- ✅ CORRETO — Django auto-escaping converte < > & " ' mas NÃO o hífen -->
<span data-suggestion="{{ sug }}">
<!-- JavaScript lê el.dataset.suggestion → recebe "-" real                    -->
```

### Regra
| Contexto | Usar |
|----------|------|
| `onclick="...var x='{{ s\|escapejs }}'..."` | `\|escapejs` ✓ |
| `<span data-foo="{{ s }}">` | sem filtro (auto-escaping) ✓ |
| `hx-vals='{"key": "{{ s\|escapejs }}"}'` | `\|escapejs` ✓ (é JSON inline) |
| Texto visível `{{ s }}` dentro de tag | sem filtro ✓ |

### Detectar regressão
Buscar `-` (literal) na página renderizada. Se aparecer na tela = bug.
Corrigido em 2026-06-19: `confirm_card.html` + `decode_card.html` (4 pontos).

---

## 10. Convenção de campos para o estoque — caixa física limpa

> Válido para KnownPart de qualquer DRAM (DDR, GDDR, LPDDR). Alimentar certo
> desde o início evita rótulos poluídos na bancada.

### Como o rótulo da caixa é montado

| `chip_type` contém | Rótulo | Lê de |
|---|---|---|
| `RAM` / `DDR` / `LPDDR` / `SDRAM` | **`{subtype}+{tamanho}G`** | `subtype` + densidade/capacidade |
| `eMMC` | `EMMC{cap}GB` | `capacity` |
| `UFS` | `UFS{cap}GB` | `capacity` |
| `eMCP` / `uMCP` | `EMCP{nand}+{ram}` | `emcp_nand`, `emcp_ram` |

**Para `{tamanho}` em DRAM:**
- DDR / GDDR (componente, 1 die) → lê `dram_density` (ex: "4Gb" → "4G"); fallback: deriva de `capacity` (256MB → 2G, 512MB → 4G, 1GB → 8G, 2GB → 16G)
- LPDDR (pacote multi-die) → lê `capacity` do pacote (ex: "4GB" → "4G")

### Tabela de preenchimento

| Campo | O que vai | O que **NÃO** vai |
|---|---|---|
| `chip_type` | categoria: `RAM` (toda DRAM), `eMMC`, `UFS`, `eMCP`, `uMCP`, `NAND` | specs, densidade |
| `subtype` | **só a geração/variante**: `DDR3`, `DDR3L`, `LPDDR4X`, `GDDR5`, `GDDR6`… | densidade (`4Gb`), barramento (`x16`), voltagem |
| `interface` | barramento elétrico: `x16`, `x32`, velocidade | o protocolo (não repetir `DDR3`, `GDDR5`) |
| `capacity` | capacidade total do **pacote** em bytes: `512MB`, `1GB`, `4GB` | gigabits |

### Exemplos corretos

```python
# GDDR3 (K4W) — componente 4Gb x16
chip_type = "RAM";  subtype = "GDDR3";  interface = "x16";  capacity = "512MB"
# → caixa: GDDR3+4G ✅

# GDDR5 (K4G) — componente 8Gb x32
chip_type = "RAM";  subtype = "GDDR5";  interface = "x32";  capacity = "1GB"
# → caixa: GDDR5+8G ✅

# GDDR6 (K4Z) — componente 16Gb x32
chip_type = "RAM";  subtype = "GDDR6";  interface = "x32";  capacity = "2GB"
# → caixa: GDDR6+16G ✅

# DDR3 (K4B) — componente 8Gb x8
chip_type = "RAM";  subtype = "DDR3";   interface = "x8";   capacity = "1GB"
# → caixa: DDR3+8G ✅

# LPDDR4 — pacote 4GB multi-die
chip_type = "RAM";  subtype = "LPDDR4"; interface = "x32";  capacity = "4GB"
# → caixa: LPDDR4+4G ✅
```

### Bug real: subtype com dados extras → caixa poluída

```
❌  subtype = "gDDR3 4Gb x16"  →  caixa: "gDDR3 4Gb x16+4G"
✅  subtype = "GDDR3"           →  caixa: "GDDR3+4G"
```

### Regras críticas

1. **`subtype` = só a geração.** Nunca coloque densidade (`4Gb`) ou barramento (`x16`) no subtype.
2. **Unidades: die em Gb, pacote em GB.** DDR/GDDR → densidade do die. LPDDR → capacidade do pacote. Nunca troque — gera `32G` no lugar de `4G`.
3. **`interface` = barramento elétrico** (`x16`, `x32`), não o protocolo.
4. **`chip_type="RAM"` é para KnownPart.** O populate_samsung (ChipFamily) pode manter tipos específicos (`GDDR3`, `GDDR5`) — eles são usados pelo engine de classificação, não pela caixa.
5. Corrigido em 2026-06-19: 27 KnownParts GDDR (K4W/K4G/K4Z) + ChipFamilies em populate_samsung.py.

---

## 11. Checklist antes de commitar

- [ ] Sintaxe OK: `python3 -c "import ast; ast.parse(open('arquivo.py').read())"`
- [ ] fix_known_parts rodou sem erros locais
- [ ] Busca de teste retorna `known_exact: true` e `confidence: confirmed`
- [ ] Caixa física mostra `{subtype}+{tamanho}G` limpo (sem densidade/bus no subtype)
- [ ] Nenhum segredo commitado (API keys, DATABASE_URL)
- [ ] Se mudou gramática: populate_samsung rodou + servidor reiniciado
- [ ] Mensagem de commit descritiva (família, nº de PNs, fonte)
