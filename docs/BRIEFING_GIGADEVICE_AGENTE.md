# BRIEFING — Agente especialista em GigaDevice (WhatTheChip)

> **Para uso em nova sessão de chat.**
> Leia este documento antes de qualquer ação. Ele resume tudo que o sistema WTC
> já sabe sobre GigaDevice e o que precisa ser feito.

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
- Nunca delete famílias — use `active=False` para desativar.
- Após `populate --overwrite`: **reiniciar o servidor** (lru_cache).

---

## 2. Estado atual da GigaDevice no WTC

### O que já existe no codebase

| Arquivo | O que tem |
|---|---|
| `chips/scripts/scrape_preduo.py` | Prefixo `("GD", "GigaDevice")` para detecção de marca |
| `chips/management/commands/collect_pns.py` | `"GigaDevice": ["GD25Q", "GD25B", "GD5F1", "GD5F2"]` |
| `scripts/test_fase2.py` | `("GD25Q64CSIG", "GigaDevice")` confirma detecção de marca |

### O que NÃO existe ainda

- **Nenhum `ChipFamily`** para GigaDevice em `add_chip_families.py` nem em nenhum `populate_*.py`.
- **Nenhum `KnownPart`** confirmado.
- **Nenhum `DecodeMap`** nem regra de decodificação.

A marca é reconhecida, mas qualquer PN GD cai direto no fuzzy matching (sugestões por similaridade) — sem classificação real, porque não há família nem KnownPart.

---

## 3. Portfólio GigaDevice relevante para reciclagem

GigaDevice é fabricante chinês de semicondutores (fundado 2005). No mercado de
reciclagem eletrônica, os produtos relevantes são:

### 3.1 NOR Flash SPI — série GD25 e GD55

A linha mais comum. Chips NOR Flash SPI usados como BIOS de placa-mãe,
firmware de roteadores, micro-controladores de periféricos. São chips de baixo
custo e **geralmente NÃO RENTÁVEIS** no mercado de reciclagem (confirme com o
operador antes de criar regras de rentabilidade).

**Gama de densidades:** 512Kb a 2Gb (em Mbit — unidade de medida do setor).

**Séries principais (GD25):**

| Série | Tensão | Subtipo | Notas |
|---|---|---|---|
| GD25Q | 3V | SPI NOR padrão (Quad SPI) | Mais comum; ex.: GD25Q128 |
| GD25B | 3V | SPI NOR enhanced (4I/O default) | Mais novo |
| GD25D | 3V | SPI NOR Dual | Legado |
| GD25F | 3V | SPI NOR com ECC | Alta confiabilidade |
| GD25R | 3V | SPI NOR com RPMC | Segurança |
| GD25T | 3V | SPI NOR DTR | Alta velocidade |
| GD25LQ | 1.8V | SPI NOR padrão | Prefixo "L" = low voltage |
| GD25LB | 1.8V | SPI NOR enhanced | |
| GD25LE | 1.8V | SPI NOR compacto (WLCSP) | |
| GD25LF | 1.8V | SPI NOR com ECC | |

**Série GD55** (2026, 2Gb+, mais nova — raramente em reciclagem ainda):
`GD55T`, `GD55F`, `GD55B`, `GD55LT`, `GD55LB`, `GD55LF`.

### 3.2 NAND Flash SPI — série GD5F

Chips NAND gerenciados via interface SPI. Mais relevantes para reciclagem que
NOR porque têm maior capacidade e valor.

| PN base | Densidade | Capacidade |
|---|---|---|
| GD5F1GQ4 | 1Gbit | 128MB |
| GD5F2GQ4 | 2Gbit | 256MB |
| GD5F4GQ4 | 4Gbit | 512MB |
| GD5F1GQ5 / GD5F1GM9 | 1Gbit | 128MB (gerações mais novas) |

Interface: SPI / QSPI (não ONFI/Toggle — é NOR-like interface em NAND).
`chip_type = "NAND Flash"`, `subtype = "SPI NAND"`.

### 3.3 NAND Flash Paralelo — série GD5F (ONFI)

GigaDevice também fabrica NAND paralelo (ONFI), mas é menos comum no mercado de
reciclagem de equipamentos de consumo. Não priorize sem demanda concreta.

---

## 4. Anatomia do Part Number — GD25 (NOR Flash)

### Estrutura geral

```
GD  25  [L]  [tipo]  [capacidade]  [revisão]  [-sufixo-pacote]

GD    = GigaDevice
25    = Flash Memory (família principal)
L     = presente se 1.8V (Low Voltage); ausente se 3V
tipo  = letra(s) indicando subtipo de interface/feature
cap   = código numérico da capacidade em Mbit
rev   = letra de revisão da geração (C, D, E, F, G, H, J…)
sufixo= código de embalagem e temperatura (ex.: SIG, TIG, etc.)
```

### Letra de tipo (posição após "25" ou "25L")

| Letra | Significado |
|---|---|
| Q | Quad SPI padrão (mais comum) |
| B | Enhanced Quad SPI (4I/O default) |
| D | Dual SPI (legado) |
| F | Com ECC integrado |
| R | Com RPMC (Replay Protected Monotonic Counter) |
| T | DTR (Double Transfer Rate) |
| E | Versão compacta / WLCSP |
| H | Outro subtipo |

### Códigos de capacidade (campo crítico — confuso!)

> ⚠️ **ARMADILHA PRINCIPAL**: Para capacidades menores, o código NÃO é o valor em Mbit diretamente.

| Código no PN | Densidade real | Capacidade em MB |
|---|---|---|
| `05` | 512Kb | 0,0625 MB |
| `10` | 1Mbit | 0,125 MB |
| `20` | 2Mbit | 0,25 MB |
| `40` | 4Mbit | 0,5 MB |
| `80` | 8Mbit | 1 MB |
| `16` | 16Mbit | 2 MB |
| `32` | 32Mbit | 4 MB |
| `64` | 64Mbit | 8 MB |
| `128` | 128Mbit | 16 MB |
| `256` | 256Mbit | 32 MB |
| `512M` | 512Mbit | 64 MB |

> **"40" = 4Mbit (não 40Mbit)!** — os códigos `40` e `80` são os mais confusos.
> A partir de `16`, o número corresponde ao Mbit diretamente.

**Exemplo completo:**
```
GD25Q128ESIG
GD   = GigaDevice
25   = NOR Flash família principal
Q    = Quad SPI
128  = 128Mbit = 16MB
E    = revisão E
SIG  = package (SOP8 208mil, temperatura industrial)
```

### Para o WTC: campos corretos

```python
chip_type = "NOR Flash"
subtype   = "SPI NOR"        # interface, não geração
interface = "SPI"
capacity  = "16MB"           # sempre em MB (humano-legível)
# NOR Flash não tem decode por geração — não use decode_gen_pos
```

> **Não confunda Mbit com MB.** Internamente o WTC usa MB; o dado do fabricante
> é em Mbit. Sempre converta: Mbit ÷ 8 = MB.

---

## 5. Anatomia do Part Number — GD5F (NAND Flash SPI)

```
GD5F  [densidade]  [série]  [variant]  [package]

GD5F   = GigaDevice NAND Flash
density: 1=1Gbit, 2=2Gbit, 4=4Gbit, 8=8Gbit
série: GQ4, GQ5, GM9, etc.
```

Exemplos:
- `GD5F1GQ4UBYIG` — 1Gbit (128MB) SPI NAND, série GQ4
- `GD5F2GQ4UBYIG` — 2Gbit (256MB)
- `GD5F4GQ4UBYIG` — 4Gbit (512MB)

```python
chip_type = "NAND Flash"
subtype   = "SPI NAND"
interface = "SPI"
capacity  = "128MB"   # GD5F1GQ4
```

---

## 6. Rentabilidade esperada

Baseado no perfil de mercado de reciclagem:

| Produto | Expectativa | Razão |
|---|---|---|
| NOR Flash ≤64Mbit (≤8MB) | NÃO RENTÁVEL | Chips de firmware de baixíssimo valor |
| NOR Flash 128Mbit (16MB) | Provavelmente NÃO RENTÁVEL | Ainda commodity barato |
| NOR Flash 256Mbit+ | A verificar | Pode ter nicho específico |
| NAND Flash 1Gbit+ | A verificar com operador | Maior valor potencial |

> **Não configure regras de rentabilidade sem confirmar com o operador/eMiner.**
> A `assess_profitability` em `chips/engine.py` é a fonte única de rentabilidade.

---

## 7. O que o agente deve entregar

### Prioridade 1 — `populate_gigadevice.py` (comando Django)

Criar `chips/management/commands/populate_gigadevice.py` seguindo o padrão de
`populate_samsung.py` / `populate_hynix.py`. Incluir:

1. **Famílias NOR Flash GD25** para os prefixos mais comuns no mercado de reciclagem:
   - `GD25Q` (3V Quad) — a mais encontrada
   - `GD25B` (3V enhanced) — crescente
   - `GD25LQ` (1.8V Quad)
   - `GD25LB` (1.8V enhanced)

2. **Família NAND Flash GD5F**:
   - `GD5F` com decode de densidade pelo dígito após "GD5F"

3. Cada família deve ter:
   - `chip_type`, `subtype`, `interface`, `priority`
   - `decode_cap_pos`, `decode_cap_len`, `decode_cap_map` corretos (ou vazios se o decode posicional for inviável pela variabilidade da capacidade)
   - `tip` explicando a armadilha dos códigos de capacidade (40=4Mbit, 80=8Mbit)

### Prioridade 2 — `GIGADEVICE.md`

Documento de referência técnica (seguindo o padrão de `SAMSUNG.md`, `MICRON.md`).

### Prioridade 3 — `fix_known_parts.py` (entradas)

PNs mais comuns encontrados no mercado de reciclagem que aparecem como
`pn_not_in_db=true`. Adicionar como `confidence="confirmed"` apenas com fonte
Tier 1 verificada (datasheet GigaDevice ou DigiKey).

---

## 8. Fontes Tier 1 para GigaDevice

- **Datasheets oficiais**: https://www.gigadevice.com/product/flash/spi-nor-flash/serial-nor-flash
- **DigiKey**: https://www.digikey.com — busca por "GigaDevice" ou PN específico
- **Cross-reference**: https://www.gigadevice.com/technical-resource/flash-cross-reference

> ⚠️ **Fontes proibidas**: IA sem verificação, dados de distribuidores B2C sem
> rastreamento, Preduo/Glochip (Cloudflare — apenas para coleta offline com Playwright).

---

## 9. Armadilhas e cuidados

- **"40" e "80" no PN NÃO são 40Mbit/80Mbit** — são 4Mbit e 8Mbit. Verifique o datasheet.
- **Não confunda GD25 (NOR Flash) com GD5F (NAND Flash)**: tipos de chip completamente diferentes.
- **NOR Flash não tem "geração" de RAM** — não use campos `emcp_ram`, `emcp_nand`. Não é eMCP.
- **Capacidade sempre em MB no WTC** (não Mbit, não GB para chips pequenos como estes): `capacity="16MB"` (para GD25Q128).
- **`decode_cap_map` para GD25Q**: a variabilidade do código de capacidade (40, 80, 16, 32…) pode tornar o decode posicional frágil. Se o mapa ficar muito complexo, deixe `decode_cap_pos=None` e cubra via `KnownPart` confirmado os SKUs mais comuns.
- **GD55 é a nova geração** (2Gb+) — raramente em reciclagem ainda (2026). Não priorize.
- **Não há fallback de IA.** A classificação se apoia só em gramática + banco de PNs confirmados; sem família nem `KnownPart`, o PN GD não é classificado.

---

## 10. Checklist de entrega

Antes de encerrar a sessão:

- [ ] `populate_gigadevice.py` criado e testado com `--dry-run`
- [ ] Famílias GD25Q, GD25B, GD25LQ, GD25LB, GD5F cobertas
- [ ] `chip_type` e `subtype` corretos para cada família
- [ ] Códigos de capacidade verificados contra datasheet (não inventados)
- [ ] `GIGADEVICE.md` criado com anatomia do PN documentada
- [ ] `fix_known_parts.py` com PNs confirmados (se houver com fonte Tier 1)
- [ ] `CLAUDE.md` atualizado se houver nova regra de domínio relevante
- [ ] Commits preparados (usuário executa o push)

---

*Gerado em 2026-06-20. Fontes: codebase WTC + gigadevice.com (Tier 1).*
