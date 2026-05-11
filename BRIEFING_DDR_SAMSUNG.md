# Briefing — Refinamento de Chips DDR Samsung (WhatTheChip)

## Contexto do Projeto

**WhatTheChip** é um sistema Django de classificação de chips IC para o mercado de reciclagem eletrônica (eMiner/Paraguay). O operador escaneia o Part Number de um chip, o motor classifica e retorna tipo, capacidade, interface, destino comercial (reacondicional vs. resíduo) e tip com instruções de bancada.

O projeto vive em `/Users/raphaelsilvabastos/Documents/WhatTheChip/chipdocs/`.

**Claude NUNCA roda o servidor.** Apenas edita arquivos. Após cada sessão o usuário roda:
```
python manage.py populate_samsung --overwrite
python manage.py fix_known_parts
# + restart do servidor Django para limpar o lru_cache de _get_all_families()
```

---

## Workflow da Sessão

1. Usuário escaneia chip físico → copia o bloco de debug JSON completo aqui.
2. Usuário consulta uma IA externa (Gemini, GPT etc.) e cola a análise dela.
3. **Claude analisa com cautela**, verifica a matemática e as fontes.
4. **Regra de ouro:** nunca aceitar dado de AI externa sem verificar Octopart ou datasheet. AI erra frequentemente (troca Gb/GB, inverte primary/secondary, alucina cap_keys).
5. Claude edita os arquivos necessários e documenta a razão da mudança.

---

## Arquivos Principais

| Arquivo | Função |
|---|---|
| `chips/management/commands/populate_samsung.py` | Gabarito mestre: famílias, DecodeMaps, cap_maps |
| `chips/management/commands/fix_known_parts.py` | Correções pontuais de registros sujos/alucinados no banco |
| `chips/engine.py` | Motor de classificação (não mexer sem entender o lru_cache) |
| `chips/models.py` | Modelos Django (ChipFamily, DecodeMap, KnownPart…) |

---

## Arquitetura do Motor (engine.py)

- **Camada 1:** `KnownPart` exato no banco → resultado completo
- **Camada 2:** Gramática da família (`ChipFamily`) → decodificação posicional do PN
- **Camada 3:** Gemini (fallback IA com Google Search grounding)
- **Camada 4:** Fuzzy matching para sugestões de typo

**`_get_all_families()` tem `@lru_cache(maxsize=1)`** — após `populate_samsung`, é necessário **reiniciar o servidor Django** para que as novas famílias sejam carregadas. O comando populate já chama `clear_engine_cache()` mas isso só limpa o processo do comando, não o processo do servidor.

**Campos-chave do resultado:**
- `capacity` — GB total (operador legível) — preenchido por `decode_cap_pos/map`
- `dram_density` — "Xb = YGB por die [~]" — preenchido por `decode_density_type`
- `emcp_nand` / `emcp_ram` — para eMCP/uMCP
- `emcp_source: "parcial (gramática)"` = cap_key não encontrado no mapa
- `raw_in_db: true` = chip enfileirado para enriquecimento (status="raw")

---

## Convenção dos DecodeMaps

Todos os mapas seguem: `(chave, val_primary, val_secondary)`

- **`val_primary`** = valor legível pelo operador (GB, ex: `"4GB"`)
- **`val_secondary`** = referência técnica (Gb, ex: `"32Gb"`)
- Engine: `r["capacity"] = entry[0]` → sempre GB na tela

**NUNCA** colocar "por die" no val_secondary — o engine já acrescenta " por die" automaticamente na string de `dram_density`. Se vier no mapa, duplica: "por die por die".

---

## Famílias DDR Samsung — O Que Já Existe

### Standalone DRAM (não-eMCP)

| Família | Tipo | Decode | Prioridade | Observação |
|---|---|---|---|---|
| `K3Q` | LPDDR3 | `decode_density_type="mobile"`, pn[3] | 40 | K3QF... usa sub-família K3QF |
| `K3QF` | LPDDR3 | `decode_cap_pos=4, len=1, map=K3QF_CAP` | 40 | prefixo 4 chars vence K3Q |
| `K3R` | LPDDR3 | `decode_density_type="mobile"`, pn[3] | 40 | |
| `K4E` | LPDDR3 | `decode_cap_pos=3, len=2, map=K4E_CAP` | 100 | |
| `K4F` | LPDDR4 | `decode_cap_pos=3, len=2, map=LPDDR4_CAP` | 100 | `decode_density_type=""` obrigatório |
| `K4U` | LPDDR4X | `decode_cap_pos=3, len=2, map=LPDDR4_CAP` | 100 | `decode_density_type=""` obrigatório |
| `K3U` | LPDDR4X | `decode_cap_pos=3, len=2, map=LPDDR4_CAP` | 40 | multi-channel |
| `K3KL` | LPDDR5 | `decode_cap_pos=4, len=2, map=LPDDR5_CAP` | 40 | ⚠ alguns SKUs são LPDDR5X |
| `K3LK` | LPDDR5X | `decode_cap_pos=4, len=2, map=LPDDR5_CAP` | 40 | VDDQ=0.5V — risco de queima |
| `K3L` | LPDDR5X | `decode_cap_pos=4, len=2, map=LPDDR5_CAP` | 60 | fallback — K3LK/K3KL têm prioridade |
| `K7` | SRAM | — | 100 | legado, resíduo |

### Mapas de Capacidade

**DRAM_MOBILE** (pn[3], 1 char — K3Q, K3R):
```
P=64MB · 1=128MB · 2=256MB · 4=512MB · 6=768MB · 8=1GB · F=2GB · B=1.5GB · G=2GB · H=4GB
```

**DRAM_PC** (pn[3:5], 2 chars — K4P, K4X):
```
64=8MB · 28=16MB · 56=32MB · 51=64MB · 1G=128MB · 2G=256MB · 4G=512MB · 8G=1GB · AG/AH=2GB
```

**LPDDR4_CAP** (pn[3:5] — K4F, K4U, K3U):
```
2E=1.5GB · 4E=512MB · 8E=1GB · 6E=2GB · 7E=3GB · BE/HE/H6=4GB · CE/H7=8GB · HD=16GB
```

**LPDDR5_CAP** (pn[4:6] — K3KL, K3LK, K3L):
```
9L=2GB · BK=4GB · 8L=4GB · 7K=8GB · CK=8GB · 4K=12GB · 5L=16GB
```

**K3QF_CAP** (pn[4], 1 char — K3QF sub-família):
```
1=1GB (8Gb, resíduo) · 2=2GB (16Gb, reacondicional seletivo)
```
⚠ F3/F4 ainda não confirmados por Octopart — não mapear sem evidência.

---

## Famílias DDR Ainda NÃO Mapeadas / A Explorar

Estes são os alvos para as próximas sessões DDR:

### DDR3/DDR4 PC (desktop/notebook)
- **K4B** — DDR3 SDRAM. ✅ REFINADO em 2026-05-08. Ver tabela de destinos abaixo.
- **K4A** — DDR4 SDRAM. ✅ REFINADO em 2026-05-08. Ver tabela de destinos abaixo.
- **K4Z** — DDR4X / LPDDR4X variante (Surface, Chromebooks).
- **K4C** — ❌ DESCARTADO (2026-05-09): nenhum PN Samsung real confirmado. Possível fantasma ou confusão com SK Hynix. Não mapear.
- **K4W** — ✅ CORRIGIDO (2026-05-09): NÃO é DDR3L. É **gDDR3 (Graphics DDR3)** — VRAM em GPUs de entrada (ATI HD4550, VRAM notebook). Mapeado na seção GDDR com decode_density_type="pc".

### LPDDR5 / LPDDR5X gaps
- `K3KL` com sufixo `*EM` podem ser LPDDR5X — confirmar por datasheet antes de classificar junto com LPDDR5 padrão.
- K3QF3 / K3QF4 — ainda sem Octopart. Aguardar chip físico.

### eMCP / uMCP gaps
- Cap_keys não mapeados no SAM_EMCP_CAP: `Z6`, `T9`, `512GB+12GB` (S22 Ultra).

---

## Regras de Prioridade (ChipFamily)

```
.order_by("priority", "-prefix_len")
```
- **Número menor = testado primeiro**
- Mesmo número → prefixo mais longo vence
- Exemplo: K3LK (priority=40, 4 chars) vence K3L (priority=60, 3 chars)

---

## Armadilhas Conhecidas

| Armadilha | Descrição |
|---|---|
| **Gb vs GB** | AI frequentemente confunde. Sempre verificar: se diz "32Gb LPDDR4X" → 32÷8 = 4GB. |
| **"por die" duplicado** | Não colocar "por die" no val_secondary dos mapas. O engine já acrescenta. |
| **lru_cache** | Após populate_samsung, reiniciar o servidor. Só assim as famílias novas aparecem. |
| **AI inventando cap_keys** | Ex.: AI sugeriu "KBKB" de 4 chars para K3LK. Era BK de 2 chars. Verificar no Octopart. |
| **AI trocando primary/secondary** | Ex.: LPDDR5_CAP inicial tinha Gb em val_primary. UI mostrava "64Gb" em vez de "8GB". |
| **Distribuidor vs. datasheet** | Dados de distribuidores (Censtry, Wolfchip, Jotrin) frequentemente errados. fix_known_parts.py tem histórico de correções. |
| **Device "Galaxy MX6432"** | Código interno Samsung (64=eMMC, 32=Gb RAM). Não é nome de celular — limpar campo device. |
| **decode_density_type em K4F/K4U/K3U** | DEVE ser `""`. Se "mobile", produz densidade por die errada além do cap_map. |

---

## Estrutura de um Chip no Debug JSON

```json
{
  "pn": "KXXXXXXX",
  "chip_type": "LPDDR4",
  "family_prefix": "K4F",
  "brand": "Samsung",
  "capacity": "4GB",           ← val_primary do decode_cap_map
  "dram_density": "32Gb = 4GB por die [~]",  ← apenas se decode_density_type != ""
  "emcp_nand": null,           ← preenchido só para eMCP/uMCP
  "emcp_ram": null,
  "emcp_source": null,         ← "gramática" | "parcial (gramática)" | null
  "classification_source": "gramática",
  "raw_in_db": false,          ← true = enfileirado para enriquecimento
  "confidence": "estimated"
}
```

---

## Checklist Antes de Adicionar ao SAM_EMCP_CAP / Qualquer Mapa

1. ✅ Octopart ou datasheet confirma NAND e RAM?
2. ✅ A matemática fecha? (Gb ÷ 8 = GB)
3. ✅ A chave (cap_key) não conflita com entrada existente?
4. ✅ Se conflita: o dado novo é mais confiável (fabricante > Octopart > AI externa > especulação)?
5. ✅ Se corrigindo entrada existente: adicionar entrada em fix_known_parts.py com reason?
6. ✅ Atualizar comentários e tips que referenciam o valor antigo?

---

## Chips Recentemente Adicionados/Corrigidos (referência histórica)

| PN | Cap-key | Valor | Fonte | Ação |
|---|---|---|---|---|
| KMQX10013MB | X1 | 32GB+2GB | Octopart | corrigido (era 64GB+4GB) |
| KM5P9001DMB424 | P9 | 64GB+4GB | Octopart | novo |
| KM5V8001DM-B622 | V8 | 128GB+4GB | Fabricante | corrigido (era 8GB) |
| KM5C7001DM-B622 | C7 | 64GB+4GB | Fabricante | novo |
| KM2L9001CM-B518 | L9 | 128GB+6GB | Fabricante | novo |
| KM8F9001JM-B813 | F9 | 256GB+8GB | Fabricante | novo |
| KM8F8001MM-B813 | F8 | 256GB+12GB | Fabricante | novo |
| KMFN60012MB214 | N6 | 8GB+1GB | Octopart | novo |
| K3KL9L90DMMGCU | 9L | 2GB LPDDR5X | Octopart | novo + fix_known_parts |
| K3LKBKB0BMMGCP | BK | 4GB LPDDR5X | Octopart | novo |
| K3KL8L80EMMGCU | 8L | 4GB LPDDR5X | Octopart | novo |
| K3QF1F10DMAGCE000 | — | 1GB (K3QF sub-fam) | Octopart | nova sub-família K3QF |
| KMDP6001DA | P6 | 64GB+4GB | Datasheet | corrigido device (override em fix_known_parts) |
| KMQD60013M | D6 | 32GB+3GB | — | corrigido (era 2GB) |
| KMGP6001BM | P6 | 64GB+3GB LPDDR3 | Datasheet | KMG corrigido: eMCP LPDDR3 (era uMCP); P6 corrigido 4GB→3GB |
| KMGD6001BM | D6 | 32GB+3GB LPDDR3 | Datasheet | reversal fix_known_parts: dado do Jotrin estava certo (eMCP+LPDDR3) |
| K4W1G1646D-EC12 | 1G | gDDR3 1Gb=128MB | Esquemático/Octopart | K4W novo: gDDR3 GPU (era DDR3L ultrabook — erro auditoria) |
| K4C | — | — | — | Descartado: família fantasma, zero PNs Samsung reais confirmados |
| KLM (família) | pn[6] | F=eMMC 4.5 / E=eMMC 5.0 / J=eMMC 5.1 | Catálogo Samsung | SAM_EMMC_GEN criado; decode_gen_pos=6 adicionado ao KLM |
| KMQ8X000SA / KMR8X0001M | 8X | **16GB** NAND (era 8GB) | SBiT B2B ✓ | 8X corrigido; KMR8X fix_known_parts emcp_ram=2GB |
| — | 5X | bloqueado | sem evidência | removido do SAM_EMCP_CAP |
| — | NX | bloqueado | IA externa (distribuidor) | removido do SAM_EMCP_CAP |
| K4B1G1646GBCK0 | — | 1Gb DDR3 128MB x16 1.5V 96-FBGA | Octopart | K4B: interface→DDR3, suffix_rules limpas, reasoning corrigido, tip com destino por densidade |
| K4A8G165WC-BCRC | — | 8Gb DDR4 1GB x16 1.2V DDR4-2400 96-FBGA | Octopart | K4A: interface→DDR4, reasoning adicionado, tip com guia comercial por densidade |

---

## Destinos Comerciais (para tips)

| Categoria | Destino |
|---|---|
| uMCP UFS (KM5/KM8/KM2) 64GB+ | Bancada reacondicional uMCP — Prioridade Diamante |
| uMCP UFS (KMD/KML/KMG) | Bancada reacondicional uMCP Premium |
| eMCP 32GB+3GB / 64GB+4GB+ | Bancada reacondicional eMCP |
| LPDDR5/5X (K3KL/K3LK) | Bancada reacondicional MOBILE — tolerância zero para resíduo |
| LPDDR4/4X 2GB+ | Bancada reacondicional mobile |
| LPDDR3 2GB (K3Q, K3R, K4E) | Reacondicional seletivo — checar demanda B2B |
| LPDDR3 1GB ou menos | Resíduo (moagem/refino) — sem liquidez B2B |
| DDR3 K4B — 1Gb (128MB) | Resíduo (moagem/refino) — sem liquidez B2B em 2026 |
| DDR3 K4B — ≥2Gb (256MB+) | Checar demanda antes de reacondicionar — a definir |
| DDR4 K4A — qualquer densidade | Bancada reacondicional — alta liquidez B2B (upgrades corporativos/notebooks) |
| SRAM (K7) | Resíduo (moagem/refino) |
| DDR3/DDR4 PC | A definir na sessão DDR |
