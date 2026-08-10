# PLANO — Micron identity-only, Fase 2 (capacidade + tipo, sem alucinação)

> ⚠️ **Doc de TRABALHO temporário** (mesma exceção do `PLANO_QUALIDADE_DADOS.md`, a pedido do dono).
> Escrito por **Fable** (2026-07-15) após investigação independente do código, do banco de conhecimento
> e das fontes externas. **Executor previsto: Opus Max, em outro chat.** Quando o plano terminar,
> dobrar o durável no `CLAUDE.md`/`MICRON.md` e apagar este arquivo.
>
> **Leitura obrigatória do executor, nesta ordem:** `CLAUDE.md` (§2 regras de ouro, §5, §6) →
> `AUTORIA.md` (inteiro) → `DOSSIE_MICRON_identity_only_para_Fable.md` (inteiro) → `MICRON.md` →
> este plano. O dossiê é o contexto; este plano é a ordem de execução.

---

## 0. Sumário executivo

**O rombo:** 851 known_parts Micron `confirmed`/`manual` aprovados **sem spec própria** (medição no
banco de prod, 2026-07-11, do dossiê). O carimbo "Confirmado" atesta só a **identidade** (PN↔FBGA);
a spec exibida vem emprestada da gramática (não é fonte de verdade). Triagem: **115 mortos por
geração** (sucata — capacidade irrelevante) e **736 vivos**: ~**567 DRAM discreta** (falta densidade)
+ ~**169 gerenciados** (eMCP 103 · uMCP 30 · eMMC 36 — falta capacidade e split NAND/RAM). Além da
capacidade, há **tipo errado** (eMCP↔uMCP; "MCP" carimbado em chips que não são PoP e vice-versa;
LPDDR4X que é LPDDR5X) — e tipo errado é pior: decide bancada e preço errados.

**A tese da solução, em 5 movimentos:**

1. **Consertar o engine primeiro** (Achado nº1 do dossiê, confirmado no código): hoje o
   `chip_type` do known_part confirmado é **ignorado** quando há família — qualquer correção de tipo
   fica invisível. Tornar o `chip_type` simétrico ao `subtype` (que já sobrescreve,
   `chips/engine.py:907`), **gated por auditoria prévia**.
2. **Tipo em massa por fontes estruturadas oficiais** (API FBGA `sub_category` — já provado na
   Fase 1; catálogo oficial CSV para os discretos) — nunca por part-name, nunca por chute de família.
3. **Capacidade dos gerenciados em camadas**: TOTAL via API/DigiKey API → **split só com
   cross-check aritmético** `(NAND+RAM)×8 == total` ou datasheet → resíduo vai a relatório, não a
   palpite.
4. **Densidade da discreta via catálogo oficial machine-readable** (CSV "Export Full Catalog" /
   endpoint XHR da tabela) — a única fonte que cobre o formato abreviado automotivo; possível
   subproduto: gramática MT62* nova **verificada por âncoras** (aí sim, escala para sempre).
5. **Resíduo manual priorizado por valor** (estoque ∩ rentável primeiro), com as travas de
   procedência já institucionalizadas (dry-run, backup/revert, carimbo de fonte, amostragem do dono).

**O que este plano NÃO faz:** backfill de gramática em registro confirmado (riscado pelo dono),
chute de split a partir do total, confiança em part-name para tipo de RAM, scraping fuzzy por-PN.

---

## 1. Diagnóstico consolidado (verificado no código em 2026-07-15)

### 1.1 Como o rombo nasceu (cadeia causal)

1. `enrich_micron_fbga.py` cria KnownPart `confidence="confirmed"` com **só** PN completo + FBGA +
   chip_type/subtype copiados do registro-base (`KnownPart.objects.create(...)`, linhas ~403-412).
   Design *identity-first* deliberado: 1 registro por FBGA. Spec ficava para depois.
2. `fill_capacity_from_micron_api.py` deveria fechar a spec, mas: a API volta vazia para ~metade
   dos FBGAs (provado de novo hoje: cluster `MT29TZZZ7D7` inteiro, 8 variantes, tudo vazio —
   inclusive JZ013 do estoque); o mapa `MIC_MCP_CAP` tem **18 chaves** e cobertura rala; e o ramo
   MCP dele **contamina** (`_infer_interface`/`_infer_lpddr_gen` = chutes hardcoded por família,
   linhas ~786-816) — o dossiê já o proibiu para gerenciados.
3. A gramática Micron não fecha o buraco: `MT29P` não decodifica capacidade, `MTFC` não tem decode
   no engine, `MT29C` nem família tem (`chips/knowledge/micron.yaml`), e o formato abreviado
   automotivo (`MT62F1BAD4BS-DC…`) não tem o bloco `[depth][width]` que o
   `decode_density_type='micron'` exige.
4. Os registros já estão `review_status='approved'` → `submit_known_parts` **os pula**
   (`submit_known_parts.py:112`). Não existe hoje canal de preenchimento em lote além do admin,
   um a um — inviável para 736.

### 1.2 O nó do engine (Achado nº1 do dossiê — confirmado, com nuance)

Em `chips/engine.py::_result_from_known` (712+): quando o PN casa família, o resultado nasce de
`_result_from_family` e o `chip_type` do known_part **nunca** é lido. As exceções que JÁ existem:

- `subtype` de confirmed/manual **sobrescreve** (linha 907) — o precedente de simetria;
- `source_url` contendo `ufs-based-mcp`/`emmc-based-mcp` **sobrescreve o chip_type** (linhas
  863-884, fix BUG-3) — um override por-PN que já roda em produção, mas só quando o
  `source_url` carrega a pista;
- **sem família**, o fallback usa `known.chip_type` normalmente (linhas 1398-1425).

Consequência: a Fase 1 (34 tipos corrigidos no banco) só aparece na tela nos registros cujo
`source_url` tem a substring certa. A correção certa é generalizar o override — §4, Fase B.

### 1.3 O que a investigação de hoje acrescentou ao dossiê

- **API FBGA aceita busca por prefixo de PN** (`.../en_US/-/MT29TZZZ7D7/-` → 8 variantes) — dá
  para varrer cluster por cluster sem conhecer FBGAs; útil para registros sem `fbga_code`.
- **`part-catalog` e `part-detail` da Micron são casca JS** também no fetch headless (confirmado);
  a tabela "Specifications" e o catálogo carregam por XHR pós-render. O endpoint desse XHR **não
  foi capturado ainda** (bloqueio de permissão no Chrome durante a sessão) — é a sonda nº1 da
  Fase 0. O padrão AEM do site (`_jcr_content.products.json/...` no decoder FBGA) sugere que o
  catálogo tem servlet análogo.
- **DigiKey via fetch de keyword devolve casca** (JS) — o lead 9b do dossiê só funciona com URL
  exata de produto; NÃO é industrializável por scraping. **Mas o DigiKey tem API oficial v4**
  (developer.digikey.com, registro gratuito, `ProductDetails` com atributos paramétricos — "Memory
  Size", "Memory Format" —, limites típicos ~120 req/min e ~1000 req/dia) → cobre os 736 em ~1 dia
  de execução, de forma estruturada e sancionada. É o substituto correto do scraping.
- **Nexar/Octopart já está integrado no projeto** (`scripts/nexar_validate.py`, GraphQL com
  `specs { attribute displayValue }`; chaves via `.env`). Limite: plano gratuito = 10 parts TOTAL;
  Starter ~US$99/mês = 2.000 parts/mês. Alternativa paga se DigiKey não bastar — e é a fonte que o
  próprio dono usa como rede de segurança.
- **Confirmação do padrão config-code→total**: JZ091 (`7C7`) = "ALL IN ONE MCP **280G**" na API;
  o dossiê havia confirmado `7D7` = **280Gbit** via DigiKey. Dois códigos vizinhos, mesmo total —
  consistente com pn[8]=RAM e pn[10]=NAND codificando densidades e o char do meio variando por
  outra dimensão. **Hipótese a validar por chave, nunca a assumir** (lição KMR '31': mesma chave
  pode divergir DENTRO da família).

### 1.4 ⚡ ADENDO (2026-07-15, mesma sessão) — a PAREDE Nº6 CAIU: endpoint do catálogo capturado

Com a permissão de JS no Chrome do dono, capturei o XHR que alimenta a tabela do part-catalog e
**provei que ele responde headless, sem login, JSON estruturado**:

```
https://www.micron.com/content/micron/us/en/products/<caminho-da-página>/part-catalog/
  _jcr_content.products.json/getpartcatalog/<duas-últimas-pastas-do-caminho>/-/en_US.json

Ex. (testado): .../products/multichip-packages/ufs-based-mcp/part-catalog/
  _jcr_content.products.json/getpartcatalog/multichip-packages/ufs-based-mcp/-/en_US.json
```

**O que devolve, por parte** (campos confirmados no uMCP, obsolete-emmc e lpddr5x): `part-number`
COMPLETO (com sufixo), `part-key`, `part-name`, e `attr[]` com **Component Density** (o TOTAL,
ex.: "560Gb"), **Technology** (ex.: "uMCP TLC LPDDR4" — **tipo + célula NAND + geração RAM numa
coluna oficial**), **Protocol** (UFS2.2/3.1 = interface), I/O Voltage, Part Status, package —
às vezes **Component Config** ("130Gb x32"). É a MESMA fonte do "Export Full Catalog", sem clique
manual e re-executável (fonte incremental permanente).

**Mapa dos catálogos** (índice em `micron.com/products/obsolete` + páginas correntes do docstring
do `import_micron_catalog`): correntes: emmc-based-mcp, ufs-based-mcp, nand-based-mcp, emmc, ufs,
lpddr-components/{lpddr3,lpddr4,lpddr4x,lpddr5,lpddr5x}, dram-components/{ddr4,ddr5}. Obsoletos:
obsolete-ddr4/ddr3/ddr2-sdram, obsolete-sdram, obsolete-rldram-memory, obsolete-lpddr,
obsolete-lpddr4, obsolete-lpddr5, obsolete-lpddr5x, obsolete-{mlc,tlc,slc,3d}-nand, obsolete-emmc,
obsolete-universal-flash-storage, obsolete-{parallel,serial}-nor, obsolete-xccela-flash,
**obsolete-nand-mcp-catalog**, **obsolete-umcp-catalog**, obsolete-gddr6.
⚠ Pegadinha real do índice: os links rotulados "LPDDR3"/"LPDDR2" apontam para os slugs
`obsolete-lpddr5`/`obsolete-lpddr4` — **validar cada catálogo pelo CONTEÚDO, nunca pelo rótulo**.

**Limites já medidos (honestidade):** (a) o catálogo LPDDR5X lista só PNs em **formato padrão**
(`MT62F1536M32D4DS…`) — o **abreviado automotivo continua fora** → para os 567 discretos o
DigiKey API/datasheet segue sendo o caminho por-PN; (b) obsolete-emmc = MTFC+N2M (os eMCP MT29
não estão lá — enumerar obsolete-umcp-catalog/nand-mcp na Fase 0); (c) o cluster do estoque
(`MT29TZZZ7D7…`) **não aparece** em catálogo nenhum (consistente com a API vazia — a parede nº1
persiste para não-indexados); (d) paginação do servlet não investigada (a UI tem "Show all" —
testar se o JSON traz tudo ou pagina).

**Ganhos imediatos:** confirma oficialmente **MT62F = LPDDR5X** (base para a família/gramática
MT62* com âncoras do próprio catálogo — conserto PERMANENTE do tipo dos discretos novos);
Technology+Protocol+Density oficiais para todo PN indexado; e o cross-check do split ganha uma
fonte de TOTAL independente da API FBGA.

### 1.5 Restrições herdadas (invioláveis — repetidas porque o executor vai esbarrar nelas)

- Regra de ouro #1: o agente **edita arquivos e pesquisa**; o **dono roda** tudo que escreve no
  banco. Dry-run padrão, `--commit` só o dono, backup JSON + `--revert` sempre.
- Backfill de gramática em registro confirmado = **riscado** (PLANO_QUALIDADE_DADOS §1.2).
- Distribuidor nunca é fonte de capacidade; part-name nunca é fonte de tipo de RAM (BUG-8);
  total de MCP **nunca** vira `capacity` (bug "68GB"); `Gb`≠`GB` case-sensitive; mostrar a conta
  `Gbit÷8=GB` na entrega; ambíguo → não decide, lista no resíduo.
- Escrita sempre pelo portão (`kp.save()` → `full_clean`), que também bumpa `catalog_version`.
  O pghistory (migração 0016) audita cada write — usar isso a favor (trilha de auditoria).

---

## 2. Respostas às 4 perguntas do dossiê (§9)

**P1 — fonte escalável do split (gerenciados) e da densidade (discreta):**
Não existe UMA fonte; existe um **funil de fontes com regras de decisão determinísticas** (§3).
Para gerenciados: API FBGA (tipo+total) → DigiKey API (total, tipo) → split apenas onde
`MIC_MCP_CAP` existir **e** o cross-check aritmético fechar, ou datasheet. Para discreta: o
catálogo oficial da Micron em forma machine-readable (CSV exportado ou o endpoint XHR da tabela —
sonda da Fase 0) → DigiKey API → datasheet. A página part-detail JS+login fica como camada
**opcional** (Playwright local + conta Micron), condicionada à autorização do dono — não é
bloqueante para nenhuma fase.

**P2 — o split vale o esforço?** Vale **onde muda decisão**. A rentabilidade eMCP/uMCP usa limiares
por campo (`emcp_min_ram_gb`, `emcp_min_nand_gb`) — sem split o gateway continua INDETERMINADO.
Porém "tipo certo + geração + TOTAL na tela" já corta o custo humano da fila (o operador decide na
hora com o total à vista). Recomendação: **estado intermediário honesto** — gravar tipo+geração
(fontes oficiais) e o TOTAL **em `notes`** (nunca em `capacity`), e perseguir o split apenas:
(a) nos ~133 eMCP/uMCP vivos com chave `MIC_MCP_CAP` OU total disponível (cross-check); (b) no
que está/entrar no estoque; (c) via datasheet quando rentável. O resto fica documentado como
resíduo com total conhecido. **Decisão do dono: aceitar esse estado intermediário?** (§6-D1)

**P3 — ordem/escopo:** valor primeiro: (1º) estoque ∩ vivos (hoje: JZ083, JZ013), (2º) vivos
rentáveis-prováveis por tipo/geração, (3º) cauda viva, (4º) mortos = só tipo (capacidade
irrelevante — princípio da memória `wtc-identity-only-remediacao`). O grind da cauda só se paga
com os caminhos de máquina (CSV/API); o manual é reservado ao que aparece na esteira.

**P4 — industrializar o tipo:** generalizar o override no engine (Fase B), promover
`fix_micron_type_from_api` a comando versionado com teste (decisão do dono, §6-D4), e cobrir os
discretos com o catálogo oficial (coluna TECHNOLOGY do CSV distingue LPDDR4X de LPDDR5X por PN).
Guard imutável: fonte vazia/ambígua → **não toca** (o padrão da Fase 1: 1326 não-tocados, 0 falso).

---

## 3. Arquitetura da solução — o funil de fontes

Cada registro identity-only passa pelo funil do seu segmento. Cada camada só grava o que ela
**prova**; o que não provar desce. Nada é gravado por inferência de camada anterior.

```
SEGMENTO A — GERENCIADOS vivos (~169: eMCP 103 · uMCP 30 · eMMC 36)
  A0. MTFC* (eMMC): capacidade determinística do PN (MTFC{N}G = N GB — convenção oficial
      de nomenclatura; ramo standalone do fill_capacity é limpo e já testado)      → capacity
  A1. Catálogo JSON `getpartcatalog` (§1.4): Technology ("uMCP TLC LPDDR4")        → chip_type/subtype
                                            Protocol (UFS2.2/eMMC…)                → interface
                                            Component Density (TOTAL)              → notes
  A2. API FBGA (part-name + sub_category):  tipo (sub_category)                    → chip_type
                                            geração RAM (SÓ prefixo do PN, regra BUG-8) → subtype
                                            TOTAL Gbit (part-name)                 → notes
  A2b. DigiKey API v4 (ProductDetails):     Memory Size (total) p/ quem A1/A2 vazio → notes
                                            Memory Format ("FLASH, RAM")           → cross-check tipo
  A3. SPLIT — só com prova dupla:
      • chave MIC_MCP_CAP existe E (NAND+RAM)×8 == TOTAL(A1/A2/A2b) → emcp_nand + emcp_ram
        (carimbo: mapa + total independente + a conta)
      • OU datasheet Tier-1 lido (split literal)                  → emcp_nand + emcp_ram
      • total sem split confiável → FICA no relatório de resíduo (com o total em notes)
  A4. Resíduo manual (datasheet por PN-base), priorizado estoque∩rentável.

SEGMENTO B — DISCRETA viva (~567: LPDDR4X 250 · LPDDR4 235 · LPDDR5 67 · LPDDR3 14 · DDR4 1)
  B1. Catálogo oficial machine-readable — endpoint `getpartcatalog` (§1.4; o CSV manual vira
      fallback): PART NUMBER → TECHNOLOGY (corrige LPDDR4X→LPDDR5X)  → chip_type/subtype
                             → COMPONENT DENSITY ("32Gb")             → capacity (LPDDR, ÷8) /
                                                                        density_gbit (DDR)
      (import_micron_catalog --only-update já implementa o mapeamento; auditar antes de reusar)
      ⚠ Medido: cobre só PN em formato PADRÃO — o abreviado automotivo cai direto no B2.
  B2. DigiKey API v4 por PN (Memory Size = densidade do dispositivo p/ discreto).
  B3. Se B1 cobrir bem o formato abreviado: construir decode/gramática MT62*/MT53*-DC com
      PNs âncora verificados (trilha A do AUTORIA.md, golden obrigatório) — ganho permanente.
  B4. Resíduo manual (datasheet automotivo se acessível), priorizado.

SEGMENTO C — MORTOS por geração (115)
  C1. Só TIPO/geração corretos (fontes de A1/B1) p/ triagem robusta; capacidade NÃO se pesquisa.
  C2. Recategorização pendente MT29C: eMCP→MCP (chip_type "MCP" já existe em chip_types.py,
      profit_family="dead") — sobra da investigação JW500.
```

**Regra transversal de procedência (todo write):** `notes` recebe carimbo
`[fonte oficial][URL/endpoint][data][valor bruto][conta Gb→GB quando houver]`. Fonte estruturada
oficial (sub_category, CSV, Memory Size) basta para **tipo/total**; **split exige duas provas**
(mapa+total OU datasheet literal). Conflito entre fontes → não grava, vai ao CSV de conflitos.

---

## 4. Fases de execução

> Cada fase: entregável, comandos (dono executa), critério de aceite, rollback. O executor NÃO
> roda `--commit`; entrega dry-run + instruções, como manda a regra #1. Depois de cada commit do
> dono: suíte (`test chips estoque --settings=core.settings_test`), `characterize_baseline --diff`
> (diff SÓ nos PNs do lote — qualquer PN fora da lista = abortar e reverter) e, em prod,
> `guard_catalog`.

### Fase 0 — Sondas e medição (read-only, 1 sessão)

1. **Re-medir o rombo** no banco-alvo com o script do PLANO_QUALIDADE_DADOS §3.1 +
   `export_identity_only --brand Micron` — números frescos por segmento (o plano usa os de 07-11).
2. ~~Capturar o endpoint XHR do part-catalog~~ **FEITO (§1.4).** Resta: **enumerar TODOS os
   catálogos** (correntes + obsoletos, lista no §1.4) pelo endpoint `getpartcatalog`, salvar os
   JSONs como snapshot local datado, e **testar paginação** (a UI tem "Show all"; conferir se o
   JSON vem completo — comparar contagem com a UI em 1 catálogo grande).
3. **Indexar os snapshots contra os identity-only** (script read-only): para cada PN dos 736,
   casa em algum catálogo (exato/normalizado)? Sai a matriz de cobertura por segmento — é ela que
   dimensiona o que sobra pro DigiKey/datasheet. ⚠ Já medido: o abreviado automotivo
   (`MT62F1BAD4BS-DC…`) NÃO está no catálogo LPDDR5X — não esperar cobertura ali.
4. **DigiKey API:** dono cria conta developer (gratuita) e registra app; testar `ProductDetails`
   com 5 PNs conhecidos (JZ083 `MT29VZZZ7D7DQKWL`, JZ013, 1 MT62F, 1 MT53E-DC, 1 MTFC) e salvar
   as respostas como fixtures.
5. **Auditoria tipo-vs-família** (read-only, insumo da Fase B): contar, por família, os
   confirmed/manual com `known.chip_type ≠ fam.chip_type` — dimensiona o risco do override.
6. *(Opcional, decisão D2)* Conta Micron + Playwright local na part-detail: provar se logado a
   tabela Specifications aparece e tem split.

**Aceite:** números frescos + fixtures reais de cada fonte + resposta às sondas 2/3/4.

### Fase A — Estancar a régua (curta)

1. **Congelar o uso do ramo MCP do `fill_capacity_from_micron_api`** (comentário/guard no código
   ou nota operacional): proibido para gerenciados (contaminação `_infer_*`) — o dossiê já manda;
   formalizar para não ser re-rodado por engano.
2. Registrar no `MICRON.md` que identity-only não se resolve por submit (pula approved) — canal é
   pipeline do dono.

### Fase B — Engine: `chip_type` confirmado passa a valer (o nó central)

**Pré-condição:** auditoria da Fase 0.5 revisada com o dono; se houver famílias onde o
`known.chip_type` legado é lixo em massa, corrigi-las ANTES (Fase C) ou gate por carimbo.

1. Em `_result_from_known`, junto do override de subtype (engine.py:907), adicionar:
   `if human_verified and known.chip_type: r["chip_type"] = known.chip_type` (+ coerência de
   `is_emcp`/rota de label via `chip_types.py::label_kind`). Manter o override por `source_url`
   (BUG-3) como fallback — remove-se depois, não junto.
2. **Testes obrigatórios:** goldens novos cobrindo (a) known uMCP em família eMCP → exibe uMCP;
   (b) known sem chip_type → família continua valendo; (c) regressão das exceções KMR310001M-like.
   `characterize_baseline --diff` deve mostrar mudança **apenas** nos PNs com chip_type divergente
   (a lista da auditoria) — qualquer outro = investigar antes de commitar.
3. Efeito imediato: os 34 da Fase 1 ficam visíveis; famílias mistas (MT29VZZZ) passam a resolver
   por-PN.

**Rollback:** revert do commit de código (gramática/banco intocados).

### Fase C — TIPO em massa (gerenciados + discretos)

1. **Gerenciados:** re-rodar `fix_micron_type_from_api` (agora visível pós-Fase B) no conjunto
   inteiro com FBGA; para PNs sem FBGA, usar a busca por **prefixo de PN** da mesma API (achado
   novo, §1.3). Mesmo contrato: vazio/ambíguo → não toca.
2. **MT29C:** recategorizar eMCP→"MCP" (lista da Fase 0; datasheet da família 152-ball PoP como
   fonte — pendência do caso JW500). ⚠ Evidência por-PN vence a regra de família: onde a API deu
   `sub_category`/part-name eMMC, o registro é eMCP mesmo sendo MT29C (foi o caso de 2 na Fase 1).
3. **Discretos:** novo modo/comando lendo o **CSV oficial** (coluna TECHNOLOGY): PN casa →
   corrige chip_type/subtype (ex.: LPDDR4X→LPDDR5X); PN não consta → não toca. Fixtures + testes
   de parser antes de rodar.
4. Entregar ao dono: dry-run com contagem por transição de tipo (`eMCP→uMCP: N`, …) + amostra de
   20 para conferência Octopart antes do `--commit`.

**Aceite:** 0 registros com tipo vindo de fonte vazia; relatório de não-tocados com motivo.

### Fase D — Capacidade dos GERENCIADOS (o funil A)

Construir **`fill_micron_specs`** (management command novo, versionado, owner-run) com:

- `--segment managed|discrete` · `--source api|digikey|csv=<path>|map-crosscheck` · `--limit` ·
  `--fbga/--pn` (teste unitário) · dry-run padrão · `--commit` · backup JSON + `--revert` ·
  escrita `save()` (portão) · carimbo de procedência em `notes`.
- **Regras de decisão (hard-coded, sem IA):**
  - `capacity` de MTFC pelo PN (`MTFC{N}[GT]`) — reusar `_capacity_from_mtfc_pn` testado;
  - TOTAL: da API (part-name via `_parse_part_name_total_gbit`) ou DigiKey (Memory Size);
    grava **só em notes**;
  - SPLIT: somente `map-crosscheck` — chave `MIC_MCP_CAP` presente **e** `(NAND+RAM)×8 == total`
    → grava `emcp_nand`/`emcp_ram` com a conta no carimbo; total divergente → CSV de conflito
    (inclui suspeita de chave errada no mapa — alimenta correção de gramática, não write);
  - interface eMMC/UFS: só de `sub_category`/`source_url` (nunca `_infer_*`);
  - **nunca** grava `capacity` em eMCP/uMCP; **nunca** rebaixa confidence; fill-only (campo
    preenchido não é sobrescrito — divergência vai pro relatório).
- Saída sempre em 3 listas: `filled` / `skipped(+motivo)` / `conflict(+valores)` — em CSV.

Rodar em lotes (ex.: 50), dono confere amostra por lote. Estoque primeiro (JZ083/JZ013).

**Aceite:** todo eMCP/uMCP vivo com: tipo oficial + (split provado OU total em notes + presença
no relatório de resíduo). eMMC MTFC 100% com capacity.

### Fase E — Densidade da DISCRETA (o funil B)

1. Com os CSVs da Fase 0 (ou o endpoint XHR): rodar o modo `csv` do `fill_micron_specs` (ou
   `import_micron_catalog --only-update` **após auditoria** do seu mapeamento — ele é anterior às
   convenções novas; validar contra `chip_types.py` antes de confiar): `COMPONENT DENSITY` →
   `capacity` (LPDDR, mostrar ÷8) / `density_gbit` (DDR). PN não consta → não toca.
2. DigiKey API para os que o CSV não cobrir.
3. **Se** a cobertura do CSV revelar o padrão do formato abreviado: propor família/decode MT62*
   (trilha A completa: yaml + portão + golden com PNs âncora do CSV + handshake). É o único
   caminho aqui que escala para além destes 567.
4. Resíduo → relatório priorizado.

**Aceite:** % de discretos vivos com densidade de fonte oficial (meta: CSV+API ≥ 80%; medir na
Fase 0 antes de prometer); goldens para qualquer gramática nova.

### Fase F — Resíduo manual + institucionalização

1. Pesquisa PN-a-PN **só** do resíduo estoque∩rentável (método das INVESTIGACAO_*.md: datasheet
   via PN-base, DigiKey paramétrico, cluster inteiro por rodada, aritmética exposta).
2. Dobrar no `CLAUDE.md`/`MICRON.md`: o funil de fontes, a proibição do ramo MCP do fill antigo,
   o estado "identidade confirmada / spec pendente" e o comando novo.
3. Apagar este plano e o dossiê (ou arquivar via git) — política §10.
4. *(Decisão D6)* Regra no portão para NOVOS confirmed-sem-spec (status `identity` ou rebaixa) —
   estanca recorrência; hoje só a Micron cria esses registros por pipeline.

---

## 5. Travas anti-alucinação (checklist inviolável do executor)

1. Nenhum write sem **fonte estruturada oficial ou datasheet lido**; carimbo em `notes` com
   URL/endpoint + data + valor bruto + conta. Fonte vazia/ambígua → **não toca** (padrão Fase 1).
2. **Split = duas provas** (mapa+total batendo, ou datasheet literal). Total nunca vira capacity
   de MCP. Extrapolação de progressão (caso `8G96M`) é proibida — vai pro resíduo.
3. part-name **nunca** decide tipo/geração de RAM (BUG-8); geração vem do prefixo do PN ou de
   coluna oficial (TECHNOLOGY).
4. Parsers novos só entram com **fixtures reais** (respostas salvas na Fase 0) e testes de
   unidade; regex de capacidade respeita `Gb`≠`GB` e decimais (lições `_CAP_RE`).
5. Todo comando de escrita: dry-run padrão, `--commit` explícito, backup JSON + `--revert`,
   escrita pelo portão, relatório filled/skipped/conflict. Lotes com amostragem humana (20/lote,
   Octopart do dono) antes de escalar o lote seguinte.
6. Pós-commit sempre: suíte verde + `characterize_baseline --diff` restrito à lista do lote +
   (prod) `guard_catalog`. Diff inesperado = revert imediato.
7. O executor **não roda `--commit`** nem toca prod (regra de ouro #1); entrega comandos prontos.
8. Conflito entre fonte e mapa/gramática = candidato a **bug de gramática**: reportar para
   correção via yaml (trilha A), nunca "resolver" gravando por cima.
9. Mortos por geração: não pesquisar capacidade (custo sem valor); só tipo.
10. Toda entrega de lote vem com a lista PN+campo+valor+fonte **colada no chat** (memória
    `wtc-listar-known-parts-no-chat`).

---

## 6. Decisões que só o DONO toma (bloqueantes marcadas)

| # | Decisão | Bloqueia | Recomendação do Fable |
|---|---|---|---|
| D1 | Aceitar estado intermediário "tipo+geração+total em notes, sem split"? | Fase D | Sim — honesto e reduz fila; split segue nos casos provados |
| D2 | Conta Micron (login) + Playwright na part-detail (ToS/risco)? | nada (opcional) | Adiar; só se CSV+DigiKey deixarem buraco relevante |
| D3 | Criar conta DigiKey API (gratuita)? Upgrade Nexar (pago) se preciso? | Fases 0/D/E | DigiKey sim, já; Nexar só se DigiKey falhar |
| D4 | Promover `fix_micron_type_from_api` a comando versionado (com testes)? | Fase C | Sim — será re-rodado (API é viva) |
| D5 | Ligar o override de chip_type no engine (afeta todas as marcas)? | Fase B | Sim, com a auditoria prévia + goldens; é a filosofia do projeto |
| D6 | Regra no portão p/ novos confirmed-sem-spec (status `identity`?) | Fase F | Sim, ao final — estanca recorrência |
| D7 | Escopo do manual: só estoque∩rentável (recomendado) ou cauda toda? | Fase F | Só estoque∩rentável; cauda espera as fontes de máquina |

---

## 7. Métricas de aceite (medir na Fase 0 e ao fim de cada fase)

- Identity-only vivos Micron (era 736 em 07-11): meta ↓ contínua, com **zero** write sem carimbo.
- % de vivos com `chip_type` de fonte oficial (sub_category/CSV): meta ≥ 95% dos que a fonte cobre.
- Gerenciados: % com split provado; % com total-em-notes; resíduo listado = 100% justificado.
- Discretos: % com densidade de fonte oficial.
- Estoque: 0 chips identity-only pendentes (JZ083/JZ013 resolvidos na primeira rodada da Fase D).
- Regressão: characterize diff fora-da-lista = 0 em todos os commits; suíte verde; guard_catalog ok.

## 8. Apêndice — referências rápidas

- **Endpoints (formato confirmado 2026-07-15):** FBGA fwd/rev:
  `micron.com/content/micron/us/en/sales-support/design-tools/fbga-parts-decoder/_jcr_content.products.json/getpartbyfbgacode/-/-/-/en_US/-/{PN|-}/{FBGA|-}`
  → `details[]: part-number, part-name, sub-category, fbga-code, pageurl` (campos podem vir "").
  Busca por prefixo de PN funciona. **Catálogo (a descoberta desta sessão):**
  `micron.com/content/micron/us/en/products/<path>/part-catalog/_jcr_content.products.json/getpartcatalog/<2-últimas-pastas>/-/en_US.json`
  → `details[]: part-number completo, part-key, part-name, attr[{Component Density, Technology,
  Protocol, I/O Voltage, Part Status Code, Component Config…}]` — headless, sem login; lista de
  catálogos no §1.4. DigiKey: developer.digikey.com → Product Information v4 → ProductDetails
  (OAuth2; sandbox disponível).
- **Código:** engine `_USABLE`:153 · `_result_from_known`:712 (`human_verified`:741, BUG-3
  source_url override:863-884, subtype override:907) · fallback sem-família usa known.chip_type:
  1398-1425 · FBGA path:1491+ · `submit` pula approved: `submit_known_parts.py:112` ·
  contaminação `_infer_*`: `fill_capacity_from_micron_api.py:786-816` · MTFC limpo: idem 579-593 e
  `_capacity_from_mtfc_pn` · criação identity-first: `enrich_micron_fbga.py:403-412` ·
  mapa 18 chaves + famílias sem decode: `chips/knowledge/micron.yaml`.
- **Ferramentas prontas:** `export_identity_only` · `audit_known_parts --empty` ·
  `fix_micron_type_from_api` (local, fora do git) · `characterize_baseline` · `guard_catalog` ·
  pghistory (auditoria de writes) · `scripts/nexar_validate.py` (GraphQL specs).
- **Cross-check âncora:** `8D6`: (16+1)×8 = 136Gbit = "UMCP 136G" ✓ (dossiê §4) · `7C7`/`7D7`:
  280Gbit (API/DigiKey) — validar split por chave antes de usar.
