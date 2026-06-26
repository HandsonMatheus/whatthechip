# BRIEFING — Agente especialista em PieceMakers Technology (WhatTheChip)

> **Para uso em nova sessão de chat.**
> Leia este documento antes de qualquer ação. Ele resume tudo que o sistema WTC
> já sabe sobre PieceMakers e o que precisar ser descoberto e implementado.

---

## 1. Contexto do sistema (leia primeiro)

**WhatTheChip (WTC)** é um classificador Django de chips para o mercado de
reciclagem/refurbishing (eMiner, Paraguai). O operador digita um Part Number
(PN) lido a laser no chip e o sistema retorna: tipo, specs, e se é RENTÁVEL.

**Dois pilares:**
1. **Banco de PNs confirmados (`KnownPart`)** — fonte da verdade; o engine só trata um registro como autoritativo (vence a gramática) quando `confidence` ∈ (`confirmed`, `manual`). *(Não há mais campo `status`; foi removido em jun/2026.)*
2. **Gramática (`ChipFamily` + `DecodeMap`)** — decodificação posicional para a cauda longa de PNs não confirmados.

**Regras absolutas:**
- Dados de IA e distribuidores são **frequentemente errados** — só use datasheets oficiais / DigiKey / Mouser (Tier 1).
- Claude edita arquivos; o **usuário executa** todos os comandos no banco.
- **0 invenção de dados** — se não há fonte verificável, documenta como "desconhecido" e avança.
- Nunca delete famílias — use `active=False` para desativar.
- Após `populate --overwrite`: **reiniciar o servidor** (lru_cache).

---

## 2. O que é PieceMakers Technology

**PieceMakers Technology, Inc.**

| Campo | Info |
|---|---|
| País | Taiwan (sede em Hsinchu) |
| Fundação | 2006 |
| Tipo | Fabless DRAM design company |
| Fundador | Tah-Kang Joseph Ting (>40 anos de experiência, >60 patentes) |
| Certificações | ISO 9001, ISO 14001 |
| Representantes | China, Japão, França, Israel, Turquia |
| Site | https://www.piecemakers.com.tw |

### Portfólio de produtos

| Produto | Descrição |
|---|---|
| **HBLL-RAM** | 2D SIP, 144 Gbps bandwidth — AI/HPC |
| **HiBaLL-RAM** | 3D stacking, >1 Tbps — bleeding edge |
| **PIM-DDR3** | Processing-in-Memory (CNN em DRAM), >1 TOPS |
| **Standard DRAM** | DDR clássico (SDR, DDR1, DDR2, DDR3, etc.) |
| **KGD DRAM** | Known Good Die — fornecimento sem encapsulamento |
| **PSRAM** | Pseudo-Static RAM |

**Para o mercado de reciclagem eletrônica, os produtos relevantes são:**
- **Standard DRAM** (DDR, DDR2, DDR3 — os chips de memória PC padrão)
- **PSRAM** (se aparecer em placas de hardware antigo)

Os produtos de alta largura de banda (HBLL, HiBaLL, PIM) são de nicho
industrial/AI e **não aparecem no mercado de reciclagem de massa**.

---

## 3. Estado atual no WTC

**PieceMakers tem ZERO presença no codebase WTC.**

Não existe:
- Nenhuma `Brand` registrada
- Nenhum `ChipFamily`
- Nenhum `KnownPart`
- Nenhuma menção em qualquer script de coleta, scraping ou engine

Isso significa que qualquer PN PieceMakers digitado hoje retorna "não encontrado"
e vai para `UnknownChip`. A marca sequer é detectada como "GigaDevice" seria.

---

## 4. O que é necessário descobrir

> ⚠️ **A anatomia do PN de PieceMakers é desconhecida no WTC.**
> O agente deve pesquisar a partir de fontes Tier 1 antes de criar qualquer família.

### 4.1 Missão de pesquisa — o que o agente deve descobrir

1. **Prefixo(s) dos PNs** — qual string identifica chips PieceMakers? (ex.: "PM", "PMC", "PTK"?)
2. **Estrutura posicional** — onde fica a densidade? a largura de barramento? a geração DDR?
3. **Tabela de capacidade** — que códigos mapeiam para quais densidades em Gb/MB?
4. **Geração DDR** — DDR1/2/3/4? como é codificado?
5. **Interface** — barramento: x8, x16, x32?
6. **Exemplos reais de PNs** encontrados nos dados do operador

### 4.2 Onde pesquisar (Tier 1 obrigatório)

- **DigiKey**: https://www.digikey.com/en/products/filter/dram/774?s=N4IgjCBcoAxaBjKAzAhgGwM4FMA2IArGAJwDMIAugL4A — filtrar por "PieceMakers"
- **Mouser**: https://www.mouser.com — buscar "PieceMakers" em Integrated Circuits > Memory
- **Site oficial**: https://www.piecemakers.com.tw/en/product/standard-dram
- **Datasheets**: quando encontrar um PN concreto, buscar o datasheet PDF oficial no site da PieceMakers ou DigiKey

> **Nunca use** dados de distribuidores sem rastreamento, IA, ou sites de preço como
> Octopart sem verificar o datasheet. PieceMakers é pequena; dados de IA tendem a
> alucinar ou confundir com outros fabricantes.

---

## 5. Como adicionar PieceMakers ao WTC (após pesquisa)

### Passo 1 — Criar a Brand (se não existir)

No arquivo `chips/management/commands/add_chip_families.py`:

```python
brand, _ = Brand.objects.get_or_create(
    name="PieceMakers",
    defaults={"slug": "piecemakers"},
)
```

### Passo 2 — Criar ChipFamily(s) com o prefixo correto

```python
ChipFamily.objects.update_or_create(
    prefix="[PREFIXO_DESCOBERTO]",
    defaults={
        "brand": brand,
        "chip_type": "RAM",          # para DDR padrão
        "subtype": "DDR3",           # ajuste conforme a família
        "interface": "x16",          # ajuste conforme o PN
        "decode_density_type": "pc", # para DDR de PC
        # ou usar decode_cap_map se for mais adequado
        "priority": 30,
        "tip": "PieceMakers Technology — DRAM padrão; verificar datasheet para decode",
    },
)
```

> **Atenção:** `decode_density_type` e `decode_cap_map` são **mutuamente exclusivos**
> na mesma família. Use um ou outro, nunca os dois.

### Passo 3 — Testar com `--dry-run` e depois sem

```bash
python manage.py add_chip_families --dry-run
python manage.py add_chip_families --overwrite
# Reiniciar servidor após --overwrite
```

### Passo 4 — Adicionar PNs confirmados em `fix_known_parts.py`

Apenas com fonte Tier 1 verificada. Seguir o padrão existente no arquivo:

```python
{
    "part_number": "[PN_CONFIRMADO]",
    "brand": "PieceMakers",
    "chip_type": "RAM",
    "subtype": "DDR3",
    "capacity": "512MB",         # do pacote completo
    "density_gbit": 4,           # densidade do die em Gbit
    "interface": "DDR3",
    "confidence": "confirmed",
    "source_url": "[URL_DIGIKEY_OU_DATASHEET]",
},
```

---

## 6. Campos corretos por tipo de chip

### DDR (RAM de PC — chip_type = "RAM")

| Campo | Valor correto |
|---|---|
| `chip_type` | `"RAM"` |
| `subtype` | `"DDR3"` / `"DDR2"` / `"DDR4"` / `"SDRAM"` (só a geração) |
| `interface` | `"x16"` ou `"x8"` (barramento do die, não geração) |
| `density_gbit` | densidade do die em Gbit (ex.: 4 para chip de 4Gb) |
| `capacity` | vazio para RAM avulsa; preenchido apenas se PN confirmar |

> `subtype` = **SOMENTE** a geração — nunca "DDR3 SDRAM", "DDR3 PC", "Multi-Channel".
> `interface` = barramento (x8, x16) — nunca "DDR3", nunca a geração.

**Label da caixa física gerado pelo gateway:**
```
DDR3 + 4G   →  "DDR3+4G"   (densidade do die em Gbit)
```

### PSRAM (chip_type = "RAM", subtype = "PSRAM")

PSRAM é tecnicamente SRAM com interface de DRAM. Raramente aparece em
reciclagem de massa. Tratar como:

```python
chip_type = "RAM"
subtype   = "PSRAM"
interface = ""        # depende do PN — verificar datasheet
```

---

## 7. Rentabilidade esperada

| Produto | Expectativa | Razão |
|---|---|---|
| DDR1/DDR2 (SDRAM legado) | NÃO RENTÁVEL | Geração morta |
| DDR3 (density ≥ 4Gb) | RENTÁVEL (potencial) | Ainda em uso |
| DDR3 (density < 4Gb) | Depende | Verificar config do ProfitabilityConfig |
| DDR4 | RENTÁVEL (se confirmado) | Alta demanda |
| PSRAM | Depende do mercado | Nicho específico |

> **Não configure regras de rentabilidade novas.** A fonte única de rentabilidade
> é `assess_profitability` em `chips/engine.py`, que usa `ProfitabilityConfig`
> editável no admin. Só modifique `ProfitabilityConfig` com aprovação do operador.

---

## 8. Armadilhas antecipadas

- **PN desconhecido**: PieceMakers é fabricante pequeno; se DigiKey não encontrar,
  provavelmente o PN que chegou ao operador pode ser de outro fabricante ou estar
  parcialmente ilegível. Documente como `UnknownChip` e não invente dados.

- **Confundir DDR PC com DDR móvel**: PieceMakers faz RAM de PC (DDR padrão). Não
  confundir com LPDDR Samsung/Hynix (móvel). O WTC trata de forma diferente:
  DDR PC usa `decode_density_type="pc"`, LPDDR usa `decode_density_type="mobile"`.

- **"KGD" no PN**: Known Good Die — chip sem encapsulamento. Se aparecer, tratar
  com o mesmo chip_type/subtype do PN base, mas adicionar nota no `tip`.

- **HBLL/HiBaLL/PIM chips**: estes NÃO aparecem em reciclagem de consumo. Se
  aparecerem, sinalize ao operador — pode ser erro de digitação.

- **`decode_density_type` vs `decode_cap_map`**: nunca use os dois na mesma
  família. DDR de PC → `decode_density_type="pc"` + `DRAM_PC` DecodeMap.

---

## 9. Checklist de entrega

Antes de encerrar a sessão:

- [ ] Pesquisa Tier 1 concluída: prefixo e estrutura do PN documentados com fonte
- [ ] `add_chip_families.py` atualizado com família(s) PieceMakers (se houver prefixo confirmado)
- [ ] `fix_known_parts.py` com PNs confirmados (fonte Tier 1 citada)
- [ ] `PIECEMAKERS.md` criado se houver volume suficiente de informação
- [ ] Se pesquisa inconclusiva: registrar o que foi tentado e onde buscar depois
- [ ] `CLAUDE.md` atualizado se houver nova regra de domínio relevante
- [ ] Commits preparados (usuário executa o push)

---

## 10. Honestidade esperada do agente

Este briefing é honesto sobre as lacunas. PieceMakers é um fabricante pequeno
com pouca presença pública em bases de dados de reciclagem. **É possível que a
pesquisa Tier 1 não encontre volume suficiente para justificar uma família no WTC
neste momento.** Nesse caso, a resposta correta é documentar essa conclusão —
não criar dados fictícios para "cumprir a tarefa".

Resposta aceitável: "Pesquisei DigiKey, Mouser e o site oficial. Encontrei X PNs
confirmados. Criamos família(s) Y. Não há volume suficiente para decode
posicional — coberto via KnownPart individual."

Resposta **inaceitável**: criar famílias ou PNs com dados não verificados.

---

*Gerado em 2026-06-20. Fontes: piecemakers.com.tw (Tier 1) + codebase WTC.*
