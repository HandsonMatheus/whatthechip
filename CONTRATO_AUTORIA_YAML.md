# CONTRATO DE AUTORIA — YAML de marca (WhatTheChip)

> **Para quem:** o chat de IA responsável por UMA marca. Você pesquisa PNs em fontes
> Tier-1 e escreve o conhecimento da marca em `chips/knowledge/<marca>.yaml`.
> **Cole este arquivo inteiro no seu prompt.** Ele é o *data contract*: siga-o e o
> portão (validação Pydantic) aceita seu YAML; desvie e ele **rejeita com erro
> acionável** antes de qualquer coisa ir pro ar.
>
> **REGRA ZERO:** todo o conhecimento é YAML declarativo. **NÃO existe mais** `populate_*`,
> `add_chip_families` nem `fix_known_parts` — foram aposentados (jul/2026). Você **edita o
> yaml**, roda `load_brands` e valida. Se um `.md` de marca falar de editar Python, é
> histórico — ignore, o yaml é a fonte da verdade.

---

## 1. O fluxo (memorize)

```bash
# 1. edite chips/knowledge/<marca>.yaml
# 2. valide SEM gravar (o portão roda aqui):
python manage.py load_brands --brand <marca>            # dry-run
# 3. se validou, grave:
python manage.py load_brands --brand <marca> --commit
# 4. rede de regressão (garante que NADA mais mudou no catálogo inteiro):
python manage.py characterize_baseline --diff baseline_atual.json --summary
```

- **`load_brands` dry-run é o portão.** Se ele reclamar, o erro diz o campo e o motivo.
  Conserte no yaml e rode de novo. Nada é gravado até `--commit`.
- **`characterize --summary` é a prova.** Depois de commitar, ele mostra CADA PN cujo
  resultado mudou, por campo. Você só deve ver o que pretendia mudar.
- **Nunca** rode comandos que escrevem no banco de produção sem o dono revisar.

---

## 2. Anatomia do arquivo `<marca>.yaml`

Quatro seções. `brand` e `families` são obrigatórias; `maps` e `known_parts` conforme a marca.

```yaml
brand:
  name: Samsung            # nome exibido (exato, com maiúsculas)
  code: SAM                # código curto único
  notes: 'Coreia do Sul · Fundada 1969'

maps:                      # tabelas de decodificação reusáveis (flow-style)
  SAM_FLASH_CAP:
  - ['2', 2GB, '']         # [chave, val_primary, val_secondary]
  - [A, 16GB, '']

families:                  # a GRAMÁTICA — decodifica PNs posicionalmente
- prefix: K4A
  chip_type: DDR4
  # ... (ver §4)

known_parts:               # a AUTORIDADE — PNs confirmados que VENCEM a gramática
- part_number: K4A8G165WC-BCRC
  chip_type: DDR4
  confidence: confirmed
  # ... (ver §6)
```

**Duas fontes de conhecimento, com prioridade:**
1. **`known_parts` = a verdade.** Um PN com `confidence: confirmed` ou `manual` **sempre
   vence** o decode da gramática. É onde entra o PN que você confirmou em Tier-1.
2. **`families` = a válvula de escape.** Decodifica posicionalmente qualquer PN da cauda
   longa que ainda não está confirmado. Corrigir a regra de uma família conserta **todos**
   os chips dela de uma vez.

> Mentalidade: **confirme PNs em `known_parts`** (o objetivo); a **gramática segura o mundo**
> enquanto o banco não cobre tudo.

---

## 3. A CONVENÇÃO (o portão) — as regras que ele força

O portão normaliza e **rejeita** usando as mesmas funções do engine. Escreva já conforme.

### `chip_type` — o tipo canônico (OPÇÃO 1)
- **DRAM discreta:** a GERAÇÃO vai no `chip_type`: `DDR3`, `DDR4`, `DDR5`, `LPDDR4X`,
  `LPDDR5`, `GDDR5`, `SDRAM`, `RDRAM`. ❌ **NUNCA** `RAM` nem `DDR` genérico.
- **Gerenciada:** `eMMC`, `UFS`, `eMCP`, `uMCP`, `NAND Flash`.
- **Catálogo:** `NOR Flash`, `OneNAND`, `MCP`, `ePoP`, `SoC`, `PMIC`, `SRAM`, `Sensor`, `BGA SSD`.
- ⚠ **Família ATIVA com `chip_type` genérico → o portão REJEITA.** Ponha a geração. (Se for
  módulo/tipo-lixo que não classifica, marque `active: false`.)

### `subtype` — SÓ a geração ou a célula
- DRAM: espelha a geração (`DDR3`, `LPDDR4X`). eMCP/uMCP: a geração LPDDR (`LPDDR4X`).
  NAND: a célula (`SLC NAND`, `MLC NAND`, `TLC NAND`). eMMC/UFS: vazio.
- ❌ **NUNCA** qualificadores: `Mobile`, `Multi-Channel`, `PC DRAM`, `+ eMMC 5.1`, `standalone`,
  densidade (`8Gb`), tensão (`1.35V`), largura (`x16`). O portão os remove:
  `'LPDDR3 Mobile'→'LPDDR3'`, `'LPDDR4X + eMMC 5.1'→'LPDDR4X'`, `'DDR3/DDR3L'→'DDR3'`.
- **Exceção `catalog`** (NOR/MCP/ePoP…): o subtype é DESCRITIVO e é preservado (ex.: `NOR Flash + SDRAM`).

### `interface` — largura de barramento ou vazio
- `x8`, `x16` (DDR/GDDR) ou vazio. ❌ **NUNCA** a geração (`DDR4`, `LPDDR5`) — o portão zera.

### `confidence` (known_parts) — o vocabulário
`confirmed` > `manual` > `distributor` > `estimated`. **Só `confirmed`/`manual` vencem a
gramática.** `distributor`/`estimated` só complementam onde o decode é incompleto.

---

## 4. Famílias — a gramática posicional

Uma família decodifica o PN por POSIÇÃO. Campos (só preencha os que a marca usa):

| Campo | O que é |
|---|---|
| `prefix` | o começo do PN que casa a família (ex.: `K4A`) |
| `chip_type` / `subtype` / `interface` | §3 |
| `priority` | menor = testado primeiro entre prefixos que colidem (default 100) |
| `pn_length` | tamanho esperado do PN (opcional) |
| `is_emcp` | `true` p/ eMCP/uMCP |
| `active` | `false` desativa sem deletar (módulos, tipos-lixo) |
| `decode_cap_pos` / `decode_cap_len` / `decode_cap_map` | capacidade: lê `pn[pos:pos+len]` e busca no mapa |
| `decode_gen_pos` / `decode_gen_map` | geração/tipo de RAM por posição |
| `decode_density_type` | `pc` (usa `pn[3:5]`+`DRAM_PC`) ou `mobile` (`pn[3]`+`DRAM_MOBILE`) — densidade DRAM |
| `suffix_rules` | regras por sufixo (tensão, velocidade) |
| `tip` / `reasoning` | doc pro operador / trilha de decode |

**Armadilhas que o portão pega (ou que quebram o engine):**
- ❌ `decode_density_type` **E** `decode_cap_map` na MESMA família → **REJEITADO** (mutuamente
  exclusivos). Densidade DRAM usa `decode_density_type`; capacidade tabelada usa `decode_cap_map`.
- ❌ Família `KM` com dígito na 3ª posição (KM1/2/4/5/8…) com `decode_gen_pos` preenchido →
  **REJEITADO** (regra de ouro #5). Deixe `decode_gen_pos: null`.
- ⚠ Para DDR/LPDDR de densidade (K4A/K4B estilo), NÃO ponha `decode_cap_map` — deixe a
  capacidade nula; `decode_density_type: pc` já preenche o `dram_density`. Pôr `cap_map`
  coloca Gigabit no campo GB (bug clássico).

---

## 5. Mapas (`DecodeMap`) — `[chave, val_primary, val_secondary]`

Cada mapa é uma tabela reusável. **Siga o padrão do mapa** (não inverta primary/secondary):
- **Capacidade** (`SAM_FLASH_CAP`): `val_primary` = capacidade legível (`16GB`), secondary vazio.
- **Capacidade eMCP** (`SAM_EMCP_CAP`): `val_primary` = NAND (eMMC), `val_secondary` = RAM (LPDDR).
- **Densidade DRAM** (`DRAM_PC`/`DRAM_MOBILE`): `val_primary` = densidade em **Gb**,
  `val_secondary` = **MB por die** (❌ nunca escreva "por die" no secondary — o engine anexa).
- **`DRAM_PC` e `DRAM_MOBILE` são GLOBAIS** (compartilhados entre marcas). Se sua marca usa
  `decode_density_type`, referencie-os; **defina-os só se a marca for a dona** (hoje é a Samsung).

⚠ Unidade Micron/NAND: no PN, "G" costuma ser **Gbit**, não GB (64G = 8GB). Confira sempre.

---

## 6. `known_parts` — a AUTORIDADE (o seu trabalho principal)

Cada PN que você confirma em Tier-1 vira uma entrada. Ela **vence a gramática** (se confirmed/manual).

```yaml
known_parts:
- part_number: K4A8G165WC-BCRC   # o PN normalizado ([A-Z0-9]; hífen/espaço OK, o engine normaliza)
  chip_type: DDR4                 # segue a convenção (§3)
  capacity: '512MB'               # p/ eMMC/UFS/LPDDR = pacote em GB; p/ DDR = densidade (2G/4G) ou vazio
  emcp_ram: 'LPDDR4X 4GB'         # eMCP/uMCP: TIPO antes da capacidade
  emcp_nand: 'eMMC 5.1 64GB'
  density_gbit: '8Gb'             # densidade do die (texto)
  interface: ''                   # largura ou vazio (§3)
  fbga_code: D9VFC                # o código de 5 chars gravado a laser (Micron), se houver
  device: 'Galaxy J3'             # aparelho onde aparece (opcional)
  notes: 'Octopart + datasheet Samsung ✓ (2026-07). DDR4 512Mx16.'   # PROVENIÊNCIA — cite a fonte Tier-1
  confidence: confirmed
```

**Regras absolutas de campo (label da caixa física depende disso):**
- `emcp_ram` = `'LPDDR{n} {cap}GB'` — tipo **antes** da capacidade (`'LPDDR3 1GB'`, nunca `'1GB LPDDR3'`).
- `emcp_nand` = `'eMMC {versão} {cap}GB'` (ex.: `'eMMC 5.1 16GB'`).
- O `chip_type` do known_part segue a FAMÍLIA no merge; o que o known_part **provê** é specs
  (capacity, emcp_*, density). Foque em acertar as SPECS + a `confidence` + a `notes` (fonte).
- ❌ Nada de `'None'` string, qualificador no subtype, geração no interface — o portão limpa,
  mas escreva já limpo.

**Hierarquia de fontes (imutável):** datasheet do fabricante > Octopart/Nexar > distribuidor
B2B rastreável > especulação. **Só marque `confirmed`/`manual` com fonte Tier-1** (datasheet ou
Octopart). Distribuidor sem datasheet = `distributor` (não vence a gramática). Nunca confie em
IA ou distribuidor pra tipo de RAM/capacidade sem datasheet — eles confundem Gb/GB e alucinam.

---

## 7. Checklist antes de commitar

1. `chip_type` canônico (sem `RAM`/`DDR` genérico em família ativa)? 
2. `subtype` = só geração/célula (sem Mobile/Multi-Channel/+eMMC/standalone)?
3. `interface` = largura ou vazio (sem geração)?
4. Nenhuma família com `density_type` **e** `cap_map` juntos?
5. KM com dígito na 3ª pos → `decode_gen_pos: null`?
6. `known_parts` confirmados têm `notes` com a **fonte Tier-1**?
7. `python manage.py load_brands --brand <marca>` (dry-run) passou?
8. `characterize --summary` mostrou **só** o que você pretendia mudar?

Passou nos 8 → `--commit`. É isso. Bem-vindo ao catálogo declarativo.
