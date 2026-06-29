# BRIEFING — Convenção geral de tipos de chip (insumo para o chat de design)

**WhatTheChip — documento de fundação para escalar a 100+ marcas**
Criado: 2026-06-29 | Status: **INSUMO** (fatos auditados no código — não é a convenção final)

> **Para que serve:** este documento alimenta um chat dedicado a *desenhar* a
> convenção canônica de tipos de chip antes de seguir populando marcas. Ele
> entrega os **fatos já verificados no código** para que o chat de design **decida**
> a convenção, sem gastar esforço re-investigando. Tudo aqui foi extraído de
> `chips/engine.py`, `estoque/views.py`, `chips/conventions.py` e dos 9
> `populate_*.py` em 2026-06-29.
>
> **Regra de ouro do projeto (vale aqui também):** em conflito, **o código é a
> fonte da verdade**. Se uma afirmação deste briefing divergir do código, releia o
> código e atualize este doc.

---

## 0. Como usar este briefing

1. Leia as §§1–6 para entender **o estado atual** (o que existe, o que é sólido, o
   que diverge).
2. **Leia a §6-A antes de propor qualquer mudança** — é o contrato de campos dos
   dois consumidores (motor do site + funil do estoque) e a tabela-mestre de raio
   de impacto. É o que mantém a mudança segura.
3. Use as §§7–8 como pauta de **decisão**: a §7 lista os requisitos inegociáveis
   que a convenção tem que respeitar; a §8 lista as decisões em aberto, com
   trade-offs, **sem pré-decidir** — é o trabalho do chat de design.
4. A §9 trata da cauda longa de tipos (Samsung tem muitos) — o que é "comercial"
   (roteado no estoque) vs "catálogo".
5. A §10 são as restrições de processo (como mudanças entram em produção).

---

## 1. A pergunta de negócio

A eMiner comercializa hoje: **uMCP, eMCP, eMMC, UFS, LPDDR e DDR**, e vai expandir.
Meta: catalogar **100+ marcas**. A pergunta que dispara este trabalho:

> *Existe uma convenção organizacional única de tipos de chip? Para LPDDR, todas as
> marcas usam os mesmos campos? E para DDR? Há um padrão para todos os tipos?*

A resposta curta (detalhada nas §§2–5): **o esquema de campos é uniforme e imposto
pelo código; o vocabulário de `chip_type` que cada marca grava tem dois dialetos e
é inconsistente — sobretudo na DRAM discreta (DDR/GDDR/SDRAM).** É isso que precisa
ser padronizado antes de escalar.

**Requisito de negócio que decide o design (do operador):** o destino no estoque
**tem que mostrar a geração** — "RAM" sozinho é inútil na bancada. É obrigatório
saber sempre a versão (DDR3 vs DDR4 vs LPDDR4X…).

---

## 2. Achado central — a convenção vive em dois níveis

| Nível | O quê | Estado |
|---|---|---|
| **1. Esquema de campos por tipo** | Quais campos do `KnownPart`/resultado decidem o chip e o label | ✅ **Uniforme e imposto** — fonte única no gateway, igual para todas as marcas |
| **2. Vocabulário de `chip_type`** | Qual string a marca grava em `chip_type` (e onde a geração mora) | ⚠️ **Dois dialetos, inconsistente** — principalmente em DDR/GDDR/SDRAM |

O Nível 1 está sólido. O problema a resolver é o Nível 2.

---

## 3. Nível 1 — Esquema de campos por tipo (imposto pelo gateway)

O gateway `estoque/views.py::_compute_destination` é **brand-agnostic**: decide o
formato do label só pelo `chip_type` e, para cada tipo, lê **sempre os mesmos
campos** — não importa a marca. É a verdadeira convenção, e é fonte única.

| Tipo (`chip_type` contém) | Branch | Campos lidos (idêntico p/ TODAS as marcas) | Label exemplo |
|---|---|---|---|
| `umcp` | uMCP | `emcp_nand` + `emcp_ram` | `UMCP128+8` |
| `emcp` (ou `is_emcp=True`) | eMCP | `emcp_nand` + `emcp_ram` | `EMCP16+1.5` |
| `ufs` | UFS | `capacity` (GB/TB do pacote) | `UFS128GB` |
| `emmc` | eMMC | `capacity` (GB do pacote) | `EMMC16GB` |
| `gddr` (ou subtype GDDR + ct RAM) | **GDDR** | `dram_density` (Gb/die) + `subtype` (geração) | `GDDR3+4G` |
| `lpddr` / `ddr` / `ram` / `dram` / `sdram` | DDR/LPDDR | ver abaixo | `DDR4+4G` / `LPDDR4+8GB` |
| `nand` | NAND | `subtype` (célula) + `capacity` (MB/GB) | `SLC NAND 512MB` |

Para a DRAM discreta o `{tamanho}` depende da família — **a "alma do projeto":**

- **LPDDR** (móvel, pacote multi-die) → capacidade do **pacote** em **GB**, de `capacity`. Ex.: `4GB → 4GB`.
- **DDR / GDDR** (componente, 1 die) → densidade do **die** em **Gb**, de `dram_density` (fallback: deriva de `capacity`). Ex.: `4Gb → 4G`.

> **Regra inviolável de unidade: die em `Gb` (gigabit), pacote em `GB` (gigabyte).
> 1GB = 8Gb.** Tratar capacidade de pacote LPDDR como densidade de die gera "32G"
> no lugar de "4G". (Foi a classe do bug de dies da Micron.)

**Importante:** o *mecanismo de decode* (como a gramática chega nesses campos)
**varia por marca** e isso é OK — é a anatomia de entrada de cada uma:

| Mecanismo | Marcas |
|---|---|
| `decode_density_type='pc'/'mobile'` + DecodeMaps | Samsung |
| `decode_density_type='micron'` (depth×width÷8) | Micron |
| Apenas DecodeMaps posicionais | SK Hynix, Rayson, PieceMakers, GigaDevice |

A **saída** (os campos da tabela acima) é a mesma; só o caminho difere. **A
convenção do Nível 1 não precisa mudar** — ela é o alvo que todo decode deve atingir.

---

## 4. Nível 2 — Matriz de dialetos por marca (a divergência)

Existem **dois jeitos** de gravar `chip_type` para DRAM e eles não concordam:

- **Dialeto A — `chip_type` dedicado por geração:** a geração mora no `chip_type`
  (`chip_type="DDR4"`, `"GDDR3"`, `"LPDDR4X"`).
- **Dialeto B — `chip_type="RAM"` + geração no `subtype`:** o tipo é genérico,
  a geração mora no `subtype`.

| Categoria | Samsung | SK Hynix | Rayson | PieceMakers | GigaDevice | Micron | Toshiba | Kingston | SanDisk |
|---|---|---|---|---|---|---|---|---|---|
| **uMCP** | `uMCP` | `uMCP` | — | — | — | `uMCP` | — | — | — |
| **eMCP** | `eMCP` | `eMCP` | — | — | — | `eMCP` | `eMCP` | `eMCP` | `eMCP` |
| **eMMC** | `eMMC` | `eMMC` | `eMMC` | — | — | — | `eMMC` | — | `eMMC` |
| **UFS** | `UFS` | `UFS` | — | — | — | — | `UFS` | — | `UFS` |
| **LPDDR** | `LPDDRn` (A)¹ | `LPDDRn` (A) | `LPDDRn` (A) | — | — | — | — | — | — |
| **DDR** | **misto**² | `RAM` (B) | — | `RAM` (B) | `RAM` (B) | — | — | — | — |
| **GDDR** | `GDDRn` (A) | `RAM` (B) | — | — | — | — | — | — | — |
| **SDRAM** | `SDRAM` (A) | — | — | `RAM` (B) | — | — | — | — | — |
| **NAND** | `NAND Flash` | — | — | — | `NAND Flash` | — | — | — | — |

¹ Samsung LPDDR é dialeto A **exceto** o `K3` genérico (`chip_type="RAM"`, subtype `"LPDDR2 / LPDDR3 (legado)"`).
² Samsung DDR é **internamente inconsistente** — ver §5.1.

**Leitura:** memória **gerenciada** (eMCP, uMCP, eMMC, UFS, NAND) está
**padronizada** entre as marcas — é a maioria do volume e não é o problema. A
divergência está na **DRAM discreta**: LPDDR converge no dialeto A; DDR/GDDR/SDRAM
estão divididos entre A (Samsung) e B (Hynix/PieceMakers/GigaDevice).

---

## 5. Inconsistências catalogadas (com exemplos exatos do código)

### 5.1 Samsung não é um dialeto único — convivem três padrões para DDR
```
K4H  chip_type="DDR"    subtype="DDR1"            ← gen no subtype
K4T  chip_type="DDR"    subtype="DDR2"            ← gen no subtype
K4B  chip_type="DDR"    subtype="DDR3/DDR3L"      ← gen no subtype (e ambígua!)
K4A  chip_type="DDR4"   subtype="DDR4"            ← gen no chip_type (dedicado)
K4RA chip_type="DDR5"   subtype="DDR5"            ← gen no chip_type (dedicado)
K4S  chip_type="SDRAM"  subtype="PC-66/100/133"   ← subtype nem é geração
K4R  chip_type="RDRAM"  subtype="Rambus DRAM (RDRAM)"
```
Ou seja: DDR1/2/3 sob `chip_type="DDR"`, mas DDR4/5 sob `chip_type` dedicado.
**Não existe "o dialeto Samsung" pronto para copiar** — ele teria que ser definido
e a própria Samsung alinhada a ele.

### 5.2 `subtype` de eMCP/uMCP tem formatos incompatíveis entre marcas
O `chip_type="eMCP"` é uniforme, mas o `subtype` (que carrega a geração de RAM para
o label e para a rentabilidade) é um caos:
```
SK Hynix  H9TQ  subtype="LPDDR3"                                   ← limpo ✅
Samsung   KMF   subtype="LPDDR3 + eMMC"                            ← verboso
Samsung   KM8   subtype="UFS + LPDDR4X/5X (alta densidade)"        ← verboso
Samsung   KM    subtype="embedded Multi-Chip Package (LPDDR + eMMC)"
Kingston  *     subtype="eMCP Kingston"                            ← nem é geração ❌
```
`canonical_gen` (fonte única de exibição) salva o **label** na maioria dos casos
verbosos, mas `subtype="eMCP Kingston"` não tem geração nenhuma para extrair.

### 5.3 `subtype` de eMMC/UFS poluído em algumas marcas
A convenção diz `subtype=""` para eMMC/UFS (o gateway ignora). SK Hynix segue
(`subtype=""`); Samsung grava `"UFS 2.1 Samsung"`, `"eMMC Samsung"`. Não quebra o
label (gateway usa `capacity`), mas suja o card e foge da convenção.

### 5.4 `subtype` de NAND mistura célula + marca
```
Samsung  K9F  subtype="Samsung SLC NAND"   ← deveria ser só "SLC NAND"
```
`canonical_gen` normaliza para `"SLC NAND"` no label, mas o write-time está sujo.

### 5.5 DDR ≠ GDDR — são tipos distintos (não os agrupe)
Compartilham o **esquema de campos** (`dram_density` + `subtype`), mas:
- **Gateway:** branch de GDDR (linha ~236) roda **antes** do de DDR (linha ~242),
  porque `'ddr' in 'gddr3'` é `True` por substring (causaria falso-positivo).
- **Rentabilidade:** blocos separados — `gddr_min_gen` (≈linha 1157) vs
  `ddr_min_gen` (≈linha 1168). Revelado pelo bug do GDDR2 (jun/2026).

Qualquer convenção tem que tratá-los como **irmãos com esquema de campos comum,
porém tipos separados**.

---

## 6. Comportamento do gateway hoje (a "tolerância" que segura os dois dialetos)

Hoje **os dois dialetos funcionam** porque o gateway é deliberadamente tolerante:

- **LPDDR/DDR (linha ~242):** casa `'lpddr' in ct or 'ddr' in ct or ct in
  ('ram','dram','sdram')` — pega tanto `chip_type="DDR4"` quanto `chip_type="RAM"`.
- **Escolha LPDDR×DDR (linha ~261):** `if 'lpddr' in ct or gen.upper().startswith('LPDDR')`
  — funciona pelo `chip_type` **ou** pela geração derivada do `subtype`.
- **Geração do label:** `gen = canonical_gen(subtype) or interface`. **Atenção:** o
  gateway tira a geração do **`subtype`**, **não** do `chip_type`. Então
  `chip_type="DDR4"` com `subtype` vazio cairia em `interface`, **não** em "DDR4".
- **Fallback "RAM" (linha ~274):** o label cru `"RAM"` só aparece quando `subtype`
  **e** densidade estão vazios. Na prática o destino mostra a geração — mas o risco
  do dialeto B é exatamente esse: a geração mora só no `subtype` (demovível).

`canonical_gen` (`chips/conventions.py`) é a fonte única de exibição: reduz qualquer
`subtype`/geração ao token canônico por whitelist (`"DDR3 SDRAM"→"DDR3"`,
`"LPDDR4 Mobile"→"LPDDR4"`), cobrindo as duas vias (banco e gramática),
retroativamente, fail-open.

**Conclusão:** a tolerância é **implícita** e depende de substring + `subtype`
preenchido. A 100 marcas isso vira deriva: cada chat novo escolhe um dialeto "que
funciona" e a base vira mosaico, inauditável e sem correção em bulk confiável.

---

## 6-A. Contrato de campos dos consumidores — raio de impacto (o que NÃO pode quebrar)

> **Por que esta seção existe:** mudar a convenção de `chip_type`/`subtype` mexe nos
> campos que **dois consumidores** leem. Para fazer isso com segurança, é preciso
> saber **exatamente** o que cada um busca e o que quebra. Há **uma única função de
> classificação** — `chips/engine.py::classify(pn)` — que devolve um `dict` de
> resultado. Os dois consumidores leem desse mesmo dict.

### 6-A.1 O dict de resultado de `classify()` (a interface comum)

`classify()` produz ~40 chaves. As que importam para a convenção:
```
chip_type · subtype · capacity · dram_density · emcp_nand · emcp_ram · is_emcp ·
interface · confidence · known_exact · classification_source · brand · profitable ·
remarked_flag · fuzzy_suggestions · pn · pn_full · tip · source_url · grammar_complete
```
O engine **preenche** essas chaves de duas fontes (mesma ordem do `classify`):
- **`_result_from_known`** (banco) lê do `KnownPart`: `chip_type, subtype, capacity,
  density_gbit/density_gb, emcp_ram, emcp_nand, interface, device, notes, confidence,
  source_url, fbga_code`.
- **`_result_from_family`** (gramática) lê do `ChipFamily`+`DecodeMap`: `chip_type,
  subtype, interface, decode_*, is_emcp, tip` (a capacidade/densidade é **calculada**).

### 6-A.2 Consumidor 1 — Motor de identificação do site (`chips/views.py`)

| Rota | O que faz | Campos |
|---|---|---|
| `/chips/search/` | **`JsonResponse(result)`** — serializa o dict **INTEIRO** | **todas** as ~40 chaves vão para o frontend |
| `/chips/decode/` | Card HTMX (`decode_card.html`) | `result.*` + `confidence_label/key`, `show_source`, `family_undocumented`, `profitable/key` |

> ⚠️ **O site expõe o dict inteiro.** Renomear/alterar a semântica de **qualquer
> chave** do resultado muda o contrato da API JSON e do card de decode. Adicionar
> chave nova é seguro; **renomear/remover não é.**

### 6-A.3 Consumidor 2 — Funil de triagem do estoque (`estoque/views.py`)

Lê do `server_result` (re-classificado no servidor) e decide em 3 etapas + monta o
label. Campos lidos, por finalidade:

| Etapa / função | Campos lidos do resultado |
|---|---|
| **1. Identificação** (`_has_capacity`) — "tem specs reais?" | `capacity`, `emcp_nand`, `emcp_ram`, `dram_density` |
| **2. Fonte** (`_is_confirmed`) — "confirmado no banco?" | `confidence`, `known_exact` |
| **3. Rentabilidade** (`assess_profitability`) | `chip_type`, `subtype`, `capacity`, `dram_density`, `emcp_nand`, `emcp_ram` |
| **Label da caixa** (`_compute_destination`, §3/§6) | `chip_type`, `subtype`, `emcp_nand`, `emcp_ram`, `capacity`, `dram_density`, `interface` |
| Sinal de typo | `fuzzy_suggestions` |

**O que o estoque PERSISTE** (`InventoryEntry`): `chip_type, brand, capacity,
emcp_ram, emcp_nand, is_emcp, interface, classification_source`.
**`PendingEntry`/`RejectedEntry`** acrescentam: `confidence`, `nearest_confirmed` /
`rejection_reason`.

> ⚠️ **Achado de segurança:** o `InventoryEntry` **NÃO** guarda `subtype` nem
> `dram_density`. Eles são lidos **transitoriamente** para decidir destino e
> rentabilidade no momento da triagem, mas **não** entram na linha salva. Logo:
> - mudar `subtype`/`dram_density` afeta **a decisão de triagem e o card do site**,
>   **não** as linhas já no estoque;
> - mudar `chip_type`/`capacity`/`emcp_*` afeta **decisão + persistência + site**.

### 6-A.4 Tabela-mestre de raio de impacto (consultar ANTES de mudar qualquer campo)

| Campo | Site (JSON/card) | Estoque: decisão/label | Estoque: persiste | Mudança afeta… |
|---|:---:|:---:|:---:|---|
| `chip_type` | ✅ | ✅ (escolhe o branch) | ✅ | **tudo** — roteamento, label, rentab, persistência, API |
| `subtype` | ✅ | ✅ (label + rentab) | ❌ | label/rentab/card; **não** muda linhas salvas |
| `capacity` | ✅ | ✅ (LPDDR/eMMC/UFS/NAND) | ✅ | label gerenciada/LPDDR + rentab + persist + API |
| `dram_density` | ✅ | ✅ (DDR/GDDR label+rentab) | ❌ | label/rentab DDR-GDDR + card; **não** persiste |
| `emcp_nand`/`emcp_ram` | ✅ | ✅ (label + rentab) | ✅ | label eMCP/uMCP + rentab + persist + API |
| `interface` | ✅ | fallback de geração | ✅ | fallback do label + persist + API |
| `is_emcp` | ✅ | branch eMCP | ✅ | roteamento eMCP + persist |
| `confidence` / `known_exact` | ✅ | etapas fonte/identif. | (pend/rej) | gate "confirmado" da triagem |

**Regra de mudança segura derivada disto:** alterações de convenção devem ser
**aditivas e idempotentes** (preferir normalização no consumo via `canonical_gen` +
write-time limpo), com **migração reversível** e **teste de regressão** cobrindo: (a)
o label de cada tipo no `_compute_destination`, (b) o veredito de
`assess_profitability`, (c) a serialização de `/chips/search/`. Rodar a suíte
(`python manage.py test chips estoque --settings=core.settings_test`) antes e depois.

---

## 7. Requisitos inegociáveis que a convenção DEVE respeitar

A convenção final tem que satisfazer **todos** estes (são restrições, não escolhas):

1. **A geração é sempre visível no destino.** "RAM"/"LPDDR" sem geração é inútil
   na bancada. A geração precisa ser **impossível de perder** (campo obrigatório e,
   de preferência, primário).
2. **Unidade: die em Gb, pacote em GB.** LPDDR usa capacidade-de-pacote (GB); DDR
   usa densidade-de-die (Gb). Nunca trocar.
3. **DDR ≠ GDDR ≠ SDRAM ≠ RDRAM** — tipos distintos (branch e rentabilidade
   separados), mesmo compartilhando esquema de campos.
4. **Memória gerenciada já está padronizada** (eMCP/uMCP/eMMC/UFS/NAND) — não
   regredir; só limpar `subtype` (gerações de eMCP/uMCP) e zerar `subtype` de
   eMMC/UFS.
5. **Fonte única.** A convenção é definida uma vez e consumida em todo lugar
   (gateway, engine, write-time) — estilo `canonical_gen`/`assess_profitability`.
   Nada de regra duplicada por marca.
6. **Retrocompatível e sem reescrever o ouro.** Não rebaixar `confirmed`/`manual`;
   migração em bulk reversível; o campo `status` não existe mais.
7. **Ouro = identidade, atestar tier-1.** Specs derivadas podem estar erradas mesmo
   em registro confirmado; a gramática não é deus.

---

## 8. Decisões em aberto para o chat de design (NÃO decididas aqui)

Estas são as escolhas reais. O briefing apresenta os trade-offs, **sem decidir**.

### 8.1 Qual dialeto canônico para DRAM discreta? (a decisão central)

| Opção | Dialeto A — `chip_type` dedicado por geração | Dialeto B — `chip_type="RAM"` + `subtype` |
|---|---|---|
| Geração | **Primária** (no `chip_type`) — difícil de perder ✅ req. #1 | Secundária (no `subtype`) — pode esvaziar → "RAM" |
| Branches do gateway | Mais valores, mas substring (`'ddr' in ct`) já generaliza DDR1..5 | 1 branch só |
| Base atual | Samsung (parcial e inconsistente, §5.1) | Hynix, PieceMakers, GigaDevice (limpo) |
| Requisito #1 | Favorecido | Exige `subtype` sempre preenchido + talvez fallback no gateway |

> Argumento do usuário a favor da Samsung como base: maior volume, mais tipos
> fabricados, primeira marca categorizada. **Contraponto factual (§5.1):** a Samsung
> não é um dialeto único hoje — adotá-la = *definir* a regra limpa e *alinhar* a
> Samsung a ela (DDR1/2/3 hoje são `chip_type="DDR"`).
>
> Caminho híbrido possível: **geração no `chip_type` dedicado (filosofia A)** + o
> `subtype` espelha a geração (redundância segura) + melhoria de 1 linha no gateway
> para derivar a geração também do `chip_type` (`gen = canonical_gen(subtype) or
> canonical_gen(chip_type) or interface`). Atende o req. #1 sem depender de subtype.

### 8.2 Vocabulário fechado de `chip_type`
Definir a **lista canônica** de valores aceitos (ex.: `DDR1..DDR5`, `GDDR2..GDDR6`,
`SDRAM`, `RDRAM`, `LPDDR1..LPDDR5X`, `eMMC`, `UFS`, `eMCP`, `uMCP`, `NAND Flash`, …)
e o que fazer com tipos fora da lista (rejeitar no write-time? rotular catálogo?).

### 8.3 Formato canônico de `subtype` por tipo
Ex.: eMCP/uMCP → só a geração de RAM (`"LPDDR4X"`); eMMC/UFS → `""`; NAND → célula
(`"SLC NAND"`); DDR/GDDR → geração. Resolver os casos sujos da §5.2–5.4.

### 8.4 Imposição: tolerar no gateway vs validar no write-time
Hoje é tolerância implícita (§6). Decidir se haverá uma função de
normalização/validação de `chip_type`+`subtype` rodando nos `populate_*`/`fix_*`
(fonte única), que rejeite ou normalize o que foge do vocabulário — aí o gateway
para de adivinhar.

### 8.5 Onde a convenção é documentada (acabar com a contradição entre docs)
Hoje os docs divergem: `docs/CONVENCAO_CAMPOS_ESTOQUE.md` mostra LPDDR como
`chip_type="RAM"`; `SK_HYNIX.md §2` / `CLAUDE.md §6` mostram `chip_type="LPDDR3"`.
Decidir a tabela canônica única e referenciá-la em todos os `.md` de marca.

---

## 9. Tipos "comerciais" (roteados) vs "catálogo" (cauda longa)

O gateway só roteia: `umcp, emcp, ufs, emmc, gddr, lpddr, ddr/ram/sdram, nand`.
A Samsung carrega uma **cauda longa de tipos que o estoque NÃO roteia** (caem em
`unknown`):
```
MCP (NOR+SDRAM/PSRAM), OneNAND, NOR Flash, SRAM, ePoP, BGA SSD,
SoC (Exynos), Sensor (ISOCELL), PMIC, Mask ROM
```
A convenção precisa definir **o que é comercial** (entra na triagem de
rentabilidade/destino) **vs catálogo** (existe no banco para classificação, mas não
tem caixa física). Ex.: `ePoP` já é tratado como sempre NÃO RENTÁVEL; `PMIC`/`SoC`
provavelmente são catálogo. A 100 marcas, novos tipos vão surgir (DDR6, LPDDR6,
UFS 4.x, GDDR7…) — o vocabulário tem que ser extensível por design.

---

## 10. Restrições de processo (regras de ouro relevantes)

- **Claude edita arquivos; o usuário roda os comandos** (`populate_*`, `fix_*`,
  `migrate`). Sempre `--dry-run` antes; idempotente; reversível.
- **Após `populate_* --overwrite`, REINICIAR o servidor** (cache `lru_cache` do
  engine).
- **Nunca commitar segredos.** Não rebaixar `confirmed`/`manual`.
- **`status` (raw/enriched/failed) foi removido** (jun/2026) — não reintroduzir.
  Visibilidade no engine = specs reais OU `confidence` confirmed/manual.

---

## 11. O que o chat de design NÃO deve fazer

- **Não re-investigar** o que já está aqui — partir destes fatos (e confirmar no
  código só pontos de dúvida).
- **Não alterar o Nível 1** (esquema de campos) sem motivo forte — ele é o alvo
  estável; o trabalho é no Nível 2 (vocabulário de `chip_type`).
- **Não quebrar a memória gerenciada** já padronizada.
- **Não decidir por tolerância silenciosa** — a meta é convenção explícita e imposta.
- **Não reescrever o banco confirmado** sem migração reversível e revisão do usuário.
- **Não mexer em campo nenhum sem consultar a tabela de raio de impacto (§6-A.4)** —
  e nunca renomear/remover chave do dict de resultado (o site serializa o dict
  inteiro); mudanças aditivas e normalização no consumo são o caminho seguro.

---

### Anexo — arquivos-fonte (para o chat de design conferir)
```
estoque/views.py        → _compute_destination (gateway, §3/§6), _compute_gateway
chips/conventions.py    → canonical_gen (fonte única de exibição)
chips/engine.py         → assess_profitability (blocos DDR/GDDR/LPDDR/eMCP §5.5),
                          _result_from_family, _result_from_known
chips/management/commands/populate_*.py  → o que cada marca grava (§4/§5)
docs/CONVENCAO_CAMPOS_ESTOQUE.md         → convenção atual (a unificar, §8.5)
CLAUDE.md §6 + <MARCA>.md §2              → tabelas de convenção por marca
```
