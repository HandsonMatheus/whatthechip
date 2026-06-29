# Pendências Samsung — identificação para a convenção WhatTheChip

> **Para o chat da Samsung.** Dois itens. Devolva no **formato do §3**.

---

## 1. Convenção (como a resposta deve vir)

- **`chip_type` canônico** — a **GERAÇÃO vai no `chip_type`** para DRAM discreta
  (`DDR3` `DDR4` `DDR5` `LPDDR4X` `GDDR5`…). Gerenciada: `eMMC` `UFS` `eMCP` `uMCP`
  `NAND Flash`.
- **`subtype`** = espelha a geração / célula.
- **Unidades:** densidade do **die** em **Gb**; capacidade do **pacote** em **GB**.

---

## 2. Itens

### Item 1 — `DA97` (`chip_type="Appliance Part"`, confidence `ai_high`)
`DA97` tem só 4 caracteres (curto demais para um PN de chip) e o tipo
`"Appliance Part"` veio de um **palpite antigo de IA** (`ai_high`). Suspeita: **não é
um chip** — entrou por engano.

**Pergunta:** confirmar que `DA97` deve ser **REMOVIDO** do banco de chips? Se for um
chip real, qual o PN completo e o tipo correto?

### Item 2 — `K4RCH046VM` (+ variantes `-2CCM`, `-2CLP`) — **DDR5** confirmado
Já estão no banco como **DDR5, 4 GB, confidence confirmed**. O problema é só de
classificação: o engine os rotula errado como **RDRAM** porque caem na família `K4R`
(RDRAM) — **falta uma família `K4RC`**. Vou **adicionar a família `K4RC = DDR5`** para
consertar pela regra (sem mexer PN a PN). Para montar o **decode** da família
corretamente, preciso da **anatomia do PN**:

| PN | `chip_type` (banco) | capacity (banco) |
|---|---|---|
| `K4RCH046VM` | `DDR5` | `4GB` |
| `K4RCH046VM-2CCM` | `DDR5` | `4GB` |
| `K4RCH046VM-2CLP` | `DDR5` | `4GB` |

**Perguntas:**
1. Em que **posição** do PN `K4RC…` está codificada a densidade/capacidade?
2. `K4RCH046VM` = qual **densidade do die (Gb)** e capacidade do pacote (GB)?
3. Há outras variantes `K4RC…` com capacidades diferentes? Como o código muda?

---

## 3. Formato da resposta

```
PN/família | chip_type | subtype | density(Gb die) | capacity(GB) | posição do código de capacidade | obs
```
