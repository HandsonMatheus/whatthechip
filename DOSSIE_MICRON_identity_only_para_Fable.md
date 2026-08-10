# Dossiê — o problema dos known_parts Micron sem spec (para o Fable propor a solução)

> **Como usar:** este arquivo é o apanhado COMPLETO de uma sessão longa investigando por que
> milhares de chips Micron confirmados no banco não têm capacidade/tipo corretos, o que já foi
> tentado, o que funciona, e — principalmente — **onde tudo esbarra**. O objetivo NÃO é você
> repetir o que já foi feito, é você propor uma **solução real de ponta a ponta** com olhos
> frescos. Leia inteiro antes de propor. O contexto do projeto está no `CLAUDE.md` do repo.

---

## 1. Contexto de negócio (por que isso importa)

**WhatTheChip (WTC)** classifica Part Numbers de chips de memória recuperados para o mercado de
reciclagem (eMiner, Paraguai). Um operador lê o código gravado a laser no chip e o sistema tem que
devolver **tipo** (eMMC/eMCP/uMCP/UFS/LPDDR/DDR…), **capacidade**, e **rentabilidade** (manda pra
bancada X? é sucata?). Sem tipo+capacidade corretos, o operador não consegue triar nem precificar
o chip pra enviar ao cliente.

Micron é uma das piores marcas nesse aspecto porque a maioria dos registros nasceu de **enrichment
por FBGA** (o `enrich_micron_fbga` criou o KnownPart a partir do código FBGA de 5 chars gravado no
chip, mas **NÃO** preencheu capacidade/RAM — isso ficava pro `fill_capacity_from_micron_api`, que
nem sempre rodou ou funcionou).

---

## 2. O problema, medido (números reais deste dia, banco de PRODUÇÃO)

Micron tem **5809** known_parts approved, TODOS confidence confirmed/manual.

**851 são "identity-only"** (confirmed/manual mas SEM spec própria — capacity/emcp_ram/emcp_nand/
density todos vazios). Ou seja: o carimbo "Confirmado" atesta a **identidade** (PN↔FBGA), **não a
spec**. A spec, quando aparece na tela, vem emprestada da gramática (decode posicional feito por IA
— NÃO é fonte de verdade e já errou várias vezes; o dono desconfia dela com razão).

Triando os 851 por `is_dead_by_generation` (a regra de rentabilidade do próprio engine):
- **115 são MORTOS por geração** (LPDDR1/LPDDR2, DDR2, Mobile SDR/DDR legado) → **sucata**,
  capacidade irrelevante. Pula.
- **736 são "VIVOS"** (capacidade-dependentes — precisam da spec pra decidir):
  - **~567 DRAM discreta** (LPDDR4=235, LPDDR4X=250, LPDDR5=67, LPDDR3=14, DDR4=1) → falta densidade.
  - **~169 gerenciados** (eMCP=103, uMCP=30, eMMC=36) → falta capacidade + split NAND/RAM.

**São DOIS problemas distintos, não um:**
- **Problema A — capacidade faltando** (os 736 acima).
- **Problema B — TIPO errado.** Muitos registros têm `chip_type` trocado (eMCP marcado como uMCP e
  vice-versa; 26 com o tipo inválido "MCP"; discretos LPDDR4X que na verdade são LPDDR5X). O tipo
  errado é **pior** que capacidade faltando — decide a bancada e o preço errados.

---

## 3. O que JÁ foi feito nesta sessão (não repetir)

### Fase 1 — corrigir o TIPO via API da Micron (FUNCIONOU, feito)
Construído o comando **`chips/management/commands/fix_micron_type_from_api.py`** (temporário, NÃO
commitado no git — é remediação, não código permanente). Ele:
- Consulta a **API FBGA oficial da Micron** (`getpartbyfbgacode`, reverse lookup FBGA→PN);
- Usa **SÓ** o que a API devolve DIRETO: `sub_category` (o catálogo em que a Micron cadastra a peça)
  → o tipo, e `part_name` (a string oficial) → a geração da RAM;
- **Mapa `sub_category` → `chip_type`:** `*ufs-based-mcp*`→uMCP · `*emmc-based-mcp*`→eMCP ·
  `*nand-mcp*`+part_name tem "EMMC"→eMCP · senão/vazio → **NÃO TOCA** (sem alucinação);
- Escreve pelo portão (`kp.save()`), dry-run padrão, `--revert`.

**Resultado:** de 1475 gerenciados-com-FBGA, **34 tipos corrigidos**, 115 confirmados, 1326
não-tocados (ambíguos/vazios), 0 falso. Os 34 foram **verificados em Tier-1 independente**
(catálogo Micron + NetSource + o próprio part-name "UMCP"). Exemplos: 30× MT29VZZZ eMCP→uMCP,
2× MT29C4G48 "MCP"→eMCP, 2× MT29TZZZ→uMCP.

> ⚠ **Descoberta crítica:** o `fill_capacity_from_micron_api` (o comando ANTIGO) tem
> **contaminação embutida** — ele captura o `sub_category` mas o joga fora, e preenche
> interface/geração com **chutes hardcoded por família** (`_infer_interface`/`_infer_lpddr_gen`:
> MT30AZZZ→"UFS 3.1"+"LPDDR5" sempre, etc.). Rodá-lo nos MCP **carimba tipo errado**. NÃO usar pros
> gerenciados. Só o ramo "standalone" dele (MTFC/MTFD) é limpo (usa a convenção oficial do PN).

### Fase 2 — capacidade (TRAVOU, é o cerne do problema não-resolvido)
Ver seção 5 (as paredes). Resumo: **não existe atalho de máquina pro split NAND/RAM nem pra
densidade da discreta.**

---

## 3b. ⚠⚠ ACHADO Nº1 — o TIPO vem da FAMÍLIA, não do known_part (reformula TUDO)

Confirmado ao vivo (2026-07-11) com debug de `classify()` vs known_part vs família:
```
JZ013  MT29TZZZ7D7EKKBT: known_part.chip_type=uMCP · familia(MT29TZZZ).chip_type=eMCP · classify=eMCP
JZ100  MT29VZZZBD9FQOPR: known_part.chip_type=uMCP · familia(MT29VZZZ).chip_type=eMCP · classify=eMCP
```
O `_result_from_known` (chips/engine.py) **sobrescreve capacidade/emcp_* do known_part, MAS mantém o
`chip_type` da FAMÍLIA (gramática) — ignora o do known_part.** Consequências:

1. **A Fase 1 (fix_micron_type_from_api) corrigiu `known_part.chip_type` — mas isso é INVISÍVEL no
   classify/estoque.** Os 34 "corrigidos" mudaram um campo que o engine não lê pro tipo. O dado ficou
   mais consistente, mas o tipo na TELA continua o da família. (Foi um erro de premissa: assumi que o
   engine lê o known_part pro tipo — não lê.)
2. As famílias `MT29VZZZ/MT29TZZZ/MT30AZZZ` estão tipadas **eMCP na gramática**, mas na verdade são
   **uMCP** (MT29TZZZ parece uniforme) ou **MISTAS** (MT29VZZZ tem PNs eMCP E uMCP sob o mesmo
   prefixo — provado: JZ091=emmc-based, JZ141=ufs-based). **Um `chip_type` de família ÚNICO não pode
   estar certo pra família mista.**

**Candidato de solução (o nó central pro Fable):** fazer o `_result_from_known` deixar o known_part
`confirmed`/`manual` **sobrescrever o `chip_type`** (como já faz com capacidade). Realiza a filosofia
do projeto (known_part = verdade; gramática segura o mundo) e resolve a família mista **por-PN**.
⚠ **Mas está entrelaçado:** só é seguro se os `known_part.chip_type` estiverem CONFIÁVEIS antes
(senão propaga o tipo errado do enrichment FBGA antigo). Ou seja, **engine-change + correção-de-tipo-
confiável são o MESMO problema.** Testar contra golden/characterize (pode mexer em muitos PNs de
todas as marcas). Este é, provavelmente, o ponto onde o Fable deve começar.

## 4. O que FUNCIONA (Tier-1, validado nesta sessão)

1. **`sub_category` da API FBGA = tipo autoritativo.** Limpo, headless, escalável. Resolveu o
   Problema B onde a API responde. (Vocabulário visto: `obsolete-ufs-based-mcp`,
   `obsolete-emmc-based-mcp`, `obsolete-nand-mcp-catalog`, `nand-based-mcp`, e VAZIO.)
2. **`part_name` da API = tipo de RAM/NAND real + densidade TOTAL.** Ex.: "SLC EMMC/LPDDR2 36G",
   "UMCP 136G". Muito melhor que chutar por família — provou que **MT29PZZZ tem variantes Mobile-DDR
   E LPDDR2 sob o mesmo prefixo** (chute por família erraria metade).
3. **Cross-check aritmético (a joia):** onde existe o split do mapa `MIC_MCP_CAP` E o total da API,
   dá pra CONFERIR: `(NAND_GB + RAM_GB) × 8 == total_Gbit?`. Provado no `MT29TZZZ8D6DKEZB`:
   split (16GB, 1GB) → (16+1)×8 = **136 Gbit** = total "UMCP 136G" ✓. **Duas fontes Tier-1 batendo
   = confiança sem chute.** Este é o padrão de ouro a escalar SE tivéssemos as duas fontes.

---

## 5. O que NÃO funciona / as PAREDES (o coração do impasse)

1. **A API FBGA tem BURACOS grandes.** ~metade das consultas volta `part_name=''` e `sub_category=''`
   — em especial as variantes "ES" (engineering sample) e vários FBGA não catalogados. Os 2 chips do
   estoque em produção (JZ083, JZ013) voltaram vazios, apesar de resolverem o PN completo.
2. **O `part_name`, quando vem, dá só a densidade TOTAL** ("UMCP 80G"), **NÃO o split NAND/RAM**.
   Sem o split não dá pra montar `emcp_nand`/`emcp_ram` (o label da caixa).
3. **O mapa `MIC_MCP_CAP` (split, "verificado contra CSV oficial") tem cobertura RALA.** Numa amostra
   de 10 uMCP modernos, só **1** tinha entrada no mapa. E ele só cobre as famílias `MT29VZZZ/TZZZ/
   MT30AZZZ` (não `MT29C`).
4. **A DRAM discreta (567, o grosso) a API FBGA NEM cobre** — todos os FBGA "Z…" voltam vazio.
5. **Os PNs discretos são o formato ABREVIADO automotivo** (`MT62F1BAD4BS-DC-Y52P`,
   `MT62DC116DX-Y42M`), NÃO o formato padrão que decodifica sozinho (`MT62F1G64D4EK-023 = 8GB`). O
   datasheet PÚBLICO lista só o formato padrão → **o PN abreviado não aparece nele**. (E confirmou:
   esses "LPDDR4X" na verdade são **LPDDR5X** — erro de tipo na discreta também.)
6. **A página de detalhe da Micron (que TEM a densidade numa tabela limpa) é renderizada por JS e
   pede login** → `web_fetch` só pega a casca ("Specifications: No results found / Sign in"). É a
   parede final: a informação existe, mas atrás de JS+login.
7. **Distribuidores inconsistentes/bloqueados:** DigiKey abre mas é pesada e muitas vezes só dá a
   densidade TOTAL ("1Tbit"), sem split; Octopart/ICQQG/micro-semiconductor às vezes têm o PN mas
   raramente o split; vários bloqueiam o fetch.
8. **A busca web é fuzzy e não confiável por-PN:** às vezes acha o catálogo certo, às vezes só
   distribuidor. Já me fez cravar um "erro" (MT30AZZZDD9ZTPWL como eMCP) que a API depois desmentiu
   (era uMCP). **Fonte única fuzzy = risco de contaminar.**

---

## 6. Becos sem saída (NÃO retentar)

- **Gramática/decode posicional pra preencher spec:** é feito por IA por observação, NÃO é Tier-1, e
  já deu erro (bug X6, densidade DDR fora do lugar, etc.). Escrever spec da gramática dentro de um
  registro confirmado = "lavar palpite com carimbo". Riscado explicitamente pelo dono.
- **Confiar no `part_name` pra tipo de RAM** (BUG-8 documentado: API disse "LPDDR2" num chip LPDDR3).
- **Rodar o `fill_capacity_from_micron_api` nos MCP** (contamina o tipo — seção 3).
- **Chutar o split a partir do total** (80G total → "deve ser 64+16"): é chute, proibido.
- **Web scraping por-PN em escala:** JS+login na Micron, inconsistência nos distribuidores.

---

## 7. Ferramentas e artefatos existentes (para reuso)

- `fill_capacity_from_micron_api.py` — API FBGA (headless, curl_cffi). Helpers reusáveis:
  `_query_by_fbga(fbga)` → `{part_name, part_number, sub_category}`; `_decode_mcp_capacity(pn)` →
  (NAND_GB, RAM_GB) via `MIC_MCP_CAP` (ralo); `_parse_part_name_total_gbit`. ⚠ o ramo MCP dele
  contamina (chutes `_infer_*`).
- `fix_micron_type_from_api.py` — corrige TIPO via sub_category (Fase 1, limpo, temporário).
- `audit_known_parts --empty` / `export_identity_only` — listam os identity-only.
- Engine: `classify(pn)`, `is_dead_by_generation(result)` (triagem de sucata), `_result_from_family`.
- `MIC_MCP_CAP` DecodeMap no banco (split NAND/RAM, keyed pn[8:11], só famílias ZZZ, cobertura rala).

---

## 8. Restrições de governança (invioláveis)

- **Regra de ouro #1:** o AGENTE edita arquivos/pesquisa; o DONO roda os comandos que escrevem no
  banco de prod (a sandbox do agente NÃO alcança o banco de prod — URL secreta, isolada).
- **Opção 2:** known_parts vivem no banco. Escrita por AGENTE só via `submit_known_parts`→aprovação
  no admin (four-eyes). **Pipelines de máquina** (import_*/enrich_*/fill_capacity/o novo fix_type)
  gravam `approved` direto — é o caminho permitido pro dono. Tudo reversível (backup/--revert).
- **Sem chute. Sem gramática escrita em confirmado. Fonte Tier-1 citável (datasheet/catálogo Micron/
  Octopart) na `notes`. Mostrar a aritmética Gb→GB. Ambíguo → não decide, sinaliza.**

---

## 9. AS PERGUNTAS QUE O FABLE PRECISA RESPONDER (o pedido real)

1. **Qual é a fonte ESCALÁVEL do split NAND/RAM** (gerenciados) e da **densidade** (discreta), dado
   que: a API só dá total, o decode map é ralo, e o datasheet/part-detail da Micron é JS+login?
   - Vale automatizar a leitura da página JS (headless browser tipo Playwright, que o projeto já tem
     local)? A tabela "Specifications" da part-detail renderizada tem tudo. É a fonte óbvia — o
     bloqueio é técnico (JS+login), não de dado.
   - Existe um endpoint/JSON da Micron por-PN (não só por-FBGA) que a part-detail consome?
   - Vale um cadastro Micron (login) + a API/decoder autenticada, que talvez devolva o que a pública
     não dá?
2. **O split VALE o esforço, ou tipo+total+geração basta pra triar/enviar?** (Decisão de negócio: o
   label da caixa precisa do split, mas a bancada+rentabilidade talvez não. Reduzir o escopo pode
   resolver 90% do valor.)
3. **Qual a ORDEM/escopo?** ~736 vivos, mas triados por estoque são pouquíssimos (2 em produção
   agora). Vale só estoque∩rentável primeiro? A cauda longa (banco todo) compensa o grind?
4. **Como industrializar a correção de TIPO** que já provou funcionar (sub_category), inclusive pros
   discretos LPDDR4X→LPDDR5X, sem tocar nos que a API não cobre?

---

## 9b. LEAD promissor (descoberto no fim, vale o Fable avaliar)

**DigiKey ABRE no `web_fetch` e dá o TOTAL de densidade de forma confiável** — campo "Memory Size"
(ex.: "280Gbit") + "Memory Format" (ex.: "FLASH, RAM" = é MCP) + "Base Product Number". Diferente da
part-detail da Micron (JS+login), a página DigiKey é HTML servido (pesada, ~74k chars → fetch salva
em arquivo, dá pra `grep "Memory Size"`). Ou seja: **há uma fonte semi-escalável pro TOTAL** (1 fetch
+ grep por PN). Provado nos 2 chips do estoque (JZ083/JZ013 = 280Gbit cada).

Além disso: **o código de config do PN (pn[8:11]) codifica o total**, confirmado por 2 fontes
independentes por chave — `8D6`→136Gbit (API), `7D7`→280Gbit (DigiKey). Um decode "config→total"
SEMEADO E VERIFICADO contra DigiKey/API (não observação de IA) seria Tier-1-grounded.

**Caminho candidato pro Fable montar:** (a) DigiKey/config-code → TOTAL confiável; (b) split via
`MIC_MCP_CAP` onde existe, **cross-checado** contra o total (a joia da seção 4); (c) onde o split não
existe, ou o negócio aceita "total + tipo" (rentabilidade não precisa do split exato — só o label da
caixa precisa), ou datasheet. Isso pode fechar a maioria do valor SEM a página JS da Micron. ⚠ O
DigiKey dá o TOTAL, **não o split** — o split de 280Gbit só fechou por decomposição aritmética
(NAND 32GB + RAM 3GB), que é inferência, não dado literal.

## 10. Estado atual (o que está no banco AGORA)

- Fase 1 (tipo) rodada em prod: **34 tipos corrigidos** (uMCP/eMCP), verificados. Reversível.
- Capacidade: **inalterada** — os 736 vivos continuam sem spec própria. Nada foi chutado.
- 2 chips do estoque (lote 40 prod): `JZ083`=`MT29VZZZ7D7DQKWL` e `JZ013`=`MT29TZZZ7D7EKKBT` →
  identificados como **uMCP** (tipo no banco "eMCP" está errado); capacidade exata pendente (atrás
  do JS+login da Micron).
- Ferramenta `fix_micron_type_from_api.py` existe local (não no git — é temporária).

**Resumo de uma linha pro Fable:** *o TIPO a gente resolve barato via API (sub_category); a
CAPACIDADE não tem fonte de máquina — o dado existe só na part-detail JS+login da Micron. A pergunta
é como industrializar a leitura dessa página (ou uma fonte equivalente) sem chute, ou se o negócio
aceita parar em tipo+total sem o split.*
