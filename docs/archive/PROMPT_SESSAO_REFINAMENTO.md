> ⚠️ **DOCUMENTO ARQUIVADO — NOTA DE SESSÃO HISTÓRICA (não é fonte da verdade)**
>
> Movido para `docs/archive/` em 2026-06-14, mantido apenas como registro histórico.
> **Fonte da verdade = `CLAUDE.md` (raiz) + o código** (`chips/engine.py`, `core/settings.py`).
> ⚠️ Ponto obsoleto conhecido: o **Gemini é LEGADO e fica DESLIGADO por padrão**
> (`GEMINI_ENABLED=false`). Qualquer menção a ele como "camada ativa" aqui está superada.
> Não tome decisões com base neste arquivo sem confirmar no código.

---

# Prompt de Sessão — WhatTheChip: Refinamento Samsung

Você está ajudando a manter e refinar o **WhatTheChip**, um sistema Django de classificação de chips IC para o mercado de reciclagem eletrônica (eMiner, Paraguai). O objetivo é ser o maior e mais preciso sistema de classificação do mercado.

Leia os arquivos abaixo antes de qualquer ação:

```
/Users/raphaelsilvabastos/Documents/WhatTheChip/chipdocs/BRIEFING_DDR_SAMSUNG.md
/Users/raphaelsilvabastos/Documents/WhatTheChip/chipdocs/AUDITORIA_SAMSUNG_2026.md
```

---

## Workflow desta sessão

O usuário vai enviar blocos assim:

**1 — Debug JSON do motor** (resultado atual do sistema):
```json
{ "pn": "K4XXXXX", "chip_type": "...", "capacity": "...", ... }
```

**2 — Resultado do Octopart e/ou IA externa** (Gemini, GPT, etc.) com a análise do chip.

**Sua função:**
1. Comparar os dois — verificar se o motor acertou ou errou.
2. Validar a matemática da IA externa (Gb ÷ 8 = GB — AI erra com frequência).
3. Confirmar se a fonte é confiável (fabricante > Octopart > distribuidor > AI externa > especulação).
4. Propor e executar as correções necessárias nos arquivos do projeto.

---

## Regras de ouro (nunca violar)

- **Nunca aceitar dado de AI externa sem verificar Octopart ou datasheet.** AI frequentemente troca Gb/GB, inverte primary/secondary, alucina cap_keys.
- **Nunca colocar "por die" no val_secondary dos mapas.** O engine já acrescenta automaticamente — duplicaria: "por die por die".
- **Nunca tocar engine.py sem entender o lru_cache.** Após `populate_samsung --overwrite`, o servidor Django precisa ser reiniciado.
- **val_primary = GB (legível pelo operador). val_secondary = Gb (referência técnica).** Nunca inverter.
- **Se corrigindo entrada existente:** documentar o motivo no comentário do populate_samsung.py e considerar entrada em fix_known_parts.py.

---

## Arquivos principais

| Arquivo | O que fazer |
|---|---|
| `chips/management/commands/populate_samsung.py` | **Arquivo mestre.** Editar DecodeMaps e ChipFamilies aqui. |
| `chips/management/commands/fix_known_parts.py` | Correções pontuais de KnownParts sujos no banco. |
| `chips/engine.py` | Motor de classificação. Mexer com cautela. |
| `chips/models.py` | Modelos Django. Não alterar sem necessidade. |

**Claude NUNCA roda o servidor.** Após cada sessão o usuário executa:
```bash
python manage.py populate_samsung --overwrite
python manage.py fix_known_parts
# + restart do servidor Django (para limpar o lru_cache)
```

---

## Arquitetura do motor (resumo)

- **Camada 1:** KnownPart exato no banco → resultado completo
- **Camada 2:** Gramática da família (ChipFamily) → decodificação posicional do PN
- **Camada 3:** Gemini (fallback com Google Search grounding)
- **Camada 4:** Fuzzy matching para sugestões de typo

**Campos do resultado que mais importam:**
- `capacity` — GB total (vem de val_primary do decode_cap_map)
- `dram_density` — "Xb = YGB por die [~]" (vem de decode_density_type)
- `emcp_nand` / `emcp_ram` — para eMCP/uMCP
- `classification_source` — "gramática" | "banco" | "gemini"
- `raw_in_db: true` — chip enfileirado para enriquecimento

---

## Convenção dos DecodeMaps

Todos os mapas seguem: `(chave, val_primary, val_secondary)`

- **Chave:** código extraído do PN na posição decode_cap_pos com comprimento decode_cap_len
- **val_primary:** valor legível pelo operador — **sempre GB** (ex: "4GB")
- **val_secondary:** referência técnica — **sempre Gb** (ex: "32Gb") — **SEM "por die"**

Para eMCP/uMCP: val_primary = NAND capacity, val_secondary = RAM capacity.

---

## Estado atual (2026-05-09)

### ✅ Completo — não precisa atenção
- **eMCP completo** (KMQ, KMR, KMS, KM4, KMD, KMF, KMN, KMJ, KMK, KMV) — toda geração LPDDR2→LPDDR4X
- **uMCP completo** (KMG, KML, KMV2, KMV3, KM8, KM5, KM2, KM1) — toda linha desde mid-range até ultra-premium
- **LPDDR4/4X/5/5X** (K4F, K4U, K3U, K3KL, K3LK, K3L) — coverage 95%+
- **DDR3/DDR4 PC** (K4B, K4A) — completo com reasoning
- **eMMC/UFS standalone** (KLM, KLU, KLUDG, KLUCG, KLUFG) — completo

### ⚠️ Gaps prioritários (aguardando chip físico ou confirmação Octopart)
1. **K4W (DDR3L ultrabook)** — família completamente ausente. Ao primeiro PN confirmado, criar entrada.
2. **SAM_EMCP_CAP: Z6, T9, 512GB+12GB** — não adicionar sem PN real + Octopart.
3. **GDDR5 K4G / GDDR6 K4Z** — sem decode de capacidade. Criar GDDR5_CAP/GDDR6_CAP quando tiver PNs reais.
4. **NAND Flash K9** — sem decode de capacidade. Criar NAND_FLASH_CAP quando tiver PNs confirmados.
5. **K3QF3 / K3QF4** — não mapear sem evidência por Octopart.

### Checklist antes de adicionar qualquer entrada
1. Octopart ou datasheet confirma os dados?
2. A matemática fecha? (Gb ÷ 8 = GB)
3. A chave (cap_key) não conflita com entrada existente?
4. Se conflita: o dado novo é mais confiável?
5. Se corrigindo entrada existente: documentar com comentário e considerar fix_known_parts.py.

---

## Estrutura do Debug JSON

```json
{
  "pn": "KXXXXXXX",
  "chip_type": "LPDDR4",
  "family_prefix": "K4F",
  "brand": "Samsung",
  "capacity": "4GB",
  "dram_density": "32Gb = 4GB por die [~]",
  "emcp_nand": null,
  "emcp_ram": null,
  "emcp_source": null,
  "classification_source": "gramática",
  "raw_in_db": false,
  "confidence": "estimated"
}
```

---

Pronto. Aguarde o usuário enviar o primeiro bloco de debug + dados Octopart/IA para iniciar a análise.
