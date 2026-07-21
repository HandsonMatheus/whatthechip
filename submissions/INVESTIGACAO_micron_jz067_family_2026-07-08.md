# Investigação — FBGA JZ067 e família Micron (2026-07-08)

> Motivada pelo debug da bancada: FBGA `JZ067` não identificado (SearchLog
> 08/07/2026 15:22, `in_review_queue=true`, fuzzy sugeriu JZ007/017/027/037/047).
> Segui a regra "nunca descobrir um só": resolvi os 6 códigos via API FBGA
> oficial da Micron + forward-lookup pra mapear a família inteira. Dois dos
> três achados abaixo **não são fix de uma linha** — guardado aqui pra quem
> for resolver, com a decisão pendente do dono. Ver
> `micron_jz067_family_2026-07-08.yaml` pro que JÁ está pronto pra submeter.

## 1. MTFC não é só eMMC — a gramática assume errado

**O que está no yaml hoje:** `chips/knowledge/micron.yaml`, família `MTFC`:
`chip_type: eMMC` fixo pro prefixo inteiro, `decode_cap_pos: null` (capacidade
nunca vem da gramática pra essa família, só de known_part ou do pipeline local
`fill_capacity_from_micron_api`).

**Evidência coletada:** forward-lookup por `MTFC256G` na API oficial da Micron
devolveu 90+ variantes, divididas em DOIS `sub-category` distintos:

| PN (amostra) | sub-category | part-name |
|---|---|---|
| MTFC256GBCAQTC-IT / -WT / -AAT | `emmc` / `obsolete-emmc` | "EMMC 2T LFBGA" |
| MTFC256GBCAVTC-AIT / -AAT | `universal-flash-storage` | "UFS 2T LFBGA" |
| MTFC256GASAONS-IT/AIT/AAT | `universal-flash-storage` | "...256Gb Universal Flash Storage" |
| MTFC256GAZAOTD-AAT/AIT/IT | `universal-flash-storage` | "UFS 2T TFBGA" |
| **MTFC256GAOAMAM-WT** (irmão direto do JZ067, FBGA JZ059) | — (vazio na API) | confirmado **UFS** via datasheet oficial Micron hospedado no DigiKey (`153ball_ufs_v21...pdf`, Rev. I 12/18) — Tabela 1 lista literalmente este PN como 256GB UFS 153-ball VFBGA |

Confirma o que o `MICRON.md` já registra pro `MT29VZZZ` (eMMC×UFS trocados,
BUG-3) — só que aqui é o **MTFC inteiro**, não um caso isolado.

**Por que não é fix de uma linha:** não achei nenhuma regra posicional no
bloco depois de `MTFC{cap}G` que separe eMMC de UFS de forma confiável (ao
contrário do MT29VZZZ, onde `pn[11]` F/G já resolve isso via
`fix_micron_mcp_classification`). O diferenciador parece exigir o
`sub-category`/`part-name` da API **por PN individual** — e justamente o
`JZ067` (o alvo original) não tem esses campos preenchidos na resposta da
API (veio vazio). Ou seja, nem a própria Micron expõe o sinal pra este PN
específico.

**O que ainda é ambíguo, sem decisão:**

| FBGA | PN | Sinal que achei | Confiança |
|---|---|---|---|
| **JZ067** (alvo original) | MTFC256GBAOANAM-WT | API sem metadata · irmão mais próximo com datasheet oficial (JZ059) é UFS · revendedores genéricos (Heisener/Jotrin/ssfkg, todos Tier-3) chamam de "eMMC" — mas usam a mesma etiqueta "MASSFLASH/CONTROLLER" que aparece em peças UFS confirmadas, não é sinal confiável | baixa |
| JZ059 / JZ061 (ES) | MTFC256GAOAMAM-WT (+ES) | **UFS confirmado** — datasheet oficial Micron/DigiKey | alta (pode ir pra submissão assim que quiser) |
| JZ068 (ES) | MTFC256GBAOANAM-WT ES | mesmo caso do JZ067 (variante ES) | baixa |
| JZ037 | MTFC64GAPAKEA-WT | API sem metadata, nenhum datasheet específico achado | baixa |

**Pergunta pro dono:** trato JZ067/68/37 como UFS por proximidade de família
(JZ059 confirmado) mesmo sem datasheet exato, ou seguro só o que tem fonte
Tier-1 direta e deixo esses três de fora até achar mais?

## 2. Chave de capacidade `AD7` não existe no mapa `MIC_MCP_CAP` (família MT29TZZZ)

**O que está no mapa hoje:** 18 chaves em `MIC_MCP_CAP`, todas no formato
`[char0][D][char2]`. Existem `AD8` e `AD9` (char0=`A`), mas nenhuma com
char2=`7`.

**Evidência coletada:** forward-lookup por `MT29TZZZAD7` na API da Micron
devolveu 4 FBGA reais compartilhando essa chave — não é typo isolado:

| FBGA | PN completo |
|---|---|
| JZ003 | MT29TZZZAD7JKKFB-107 W.97R |
| JZ007 | MT29TZZZAD7JKKCY-107 W.97W |
| JZ012 | MT29TZZZAD7EKKFB-107 W.97R |
| JZ014 | MT29TZZZAD7EKKCY-107 W.97W |

Única fonte que achei (WorldWay Electronics, revendedor Tier-3) descreve o
PN como "32Gx8 MLC NAND eMMC + 1Gx32 Mobile LPDDR3 SDRAM" — notação ambígua
(pode ler como NAND=4GB via convenção JEDEC depth×width, ou 32GB se for
capacidade total já em bits com ×8 só indicando largura de I/O; as duas
leituras existem em datasheets Micron reais). **Não usei pra preencher
capacidade** — violaria a regra de não inventar chave por padrão sem fonte
Tier-1/Tier-2+ clara.

**Por que não é fix de uma linha:** o padrão char0='A'→RAM 4GB bate (mesmo
valor em AD8/AD9), então a RAM é um palpite razoável — mas o NAND (char2='7')
não tem nenhuma âncora no mapa atual pra interpolar, e a MICRON.md é
explícita: não inventar chave MCP por "padrão matemático" sem PN-âncora +
fonte Tier-2+. Tentei achar o datasheet oficial específico da combinação AD7
(dois PDFs Micron encontrados nesta sessão cobrem só 8D5 — single-PN — e a
família UFS 153-ball, nenhum dos dois é a família eMCP/AD7) e não localizei.

**Pergunta pro dono:** quer que eu envie os 4 FBGA com `chip_type`/`subtype`
preenchidos (eMCP/LPDDR3) mas `emcp_nand`/`emcp_ram` em branco — pelo menos
ficam acháveis na bancada em vez de "desconhecido" — ou prefere segurar até
eu achar a capacidade certa?

## 3. Chave `7C7` (família MT29VZZZ) — nem o padrão de posições bate

FBGA **JZ027** → `MT29VZZZ7C7DQKWL-062 W ES.97Y`. `pn[8]`='7' leria RAM=3GB
(consistente com a linha `7D8` do mapa e com o `tip` da família), mas
`pn[9:11]`="C7" não bate com nenhum código NAND existente (todos os outros
começam com 'D', este começa com 'C'). Pode ser um segmento alinhado
diferente nessa variante específica, ou uma chave genuinely nova. Também é
**ES** (engineering sample) — provavelmente nunca vendido comercialmente,
baixa prioridade de reciclagem e provavelmente sem datasheet público. Não
persegui mais fundo nesta sessão; menor prioridade dos três achados.

## 4. Atualização 2026-07-08 (pedido do dono: "nada de capacidade em branco, pesquise tier 1, divida em fases")

### Fase 1 — Octopart/DigiKey por PN (8 códigos)

Capacidade agora **sólida** (3 fontes independentes convergindo: convenção do
PN + campo de densidade do Octopart + descrição de 2+ distribuidores):

| FBGA | PN | Densidade Octopart | Capacidade |
|---|---|---|---|
| JZ067 | MTFC256GBAOANAM-WT | "2Tb 256G x 8" + Avnet "2048G" + DigiKey "2TBIT" | **256GB confirmado** |
| JZ037 | MTFC64GAPAKEA-WT | "512Gb 64G x 8" + Fly-Wing "512GBIT" + DigiKey "512G" | **64GB confirmado** |

Interface (eMMC×UFS) continua SEM sinal — Octopart só chama de "MMC ic
memory" genérico pros dois, nenhum distribuidor especifica UFS nem eMMC.
Testei a hipótese "categoria Octopart 'Memory Cards' = eMMC" — **descartada**:
JZ047 (eMMC confirmado) NÃO tem essa tag, mas JZ067/037 (interface
desconhecida) TÊM. Não é sinal confiável, não usei.

JZ061 (MTFC256GAOAMAM-WT ES): Octopart sem dados (página vazia).
JZ068 (MTFC256GBAOANAM-WT ES): Octopart retornou descrição de OUTRO chip
completamente diferente ("IC Flash 128M Spi 108MHZ 16SO W" — SPI 128Mbit,
nada a ver com um flash de 256GB em BGA) — **dado corrompido/errado no
Octopart, descartei inteiro**, não uso essa página pra nada.

Cluster AD7 (MT29TZZZ) — capacidade TOTAL (NAND+RAM) via part-name
Micron/DigiKey, mas SEM split NAND×RAM ainda:

| FBGA | PN | part-name (DigiKey) | Total |
|---|---|---|---|
| JZ003 | ...AD7JKKFB-107 W.97R | "Mlc EMMC/LPDDR3 272G" | 272Gbit = 34GB |
| JZ007 | ...AD7JKKCY-107 W.97W | "Mlc EMMC/LPDDR3 288G" | 288Gbit = 36GB |
| JZ012 | ...AD7EKKFB-107 W.97R | sem dados no Octopart | — |
| JZ014 | ...AD7EKKCY-107 W.97W | notação ambígua ("32Gx8+1Gx32"), não uso sozinha | — |

**Achado importante:** JZ003 e JZ007 têm a MESMA chave de posição `AD7` mas
totais DIFERENTES (34GB vs 36GB) — confirma que `pn[8:11]` sozinho não
determina a capacidade nessa família; o sufixo depois (`FB` vs `CY`) também
importa. O modelo de 3 caracteres do `MIC_MCP_CAP` é insuficiente aqui.

### Fase 2 — Numbering guide oficial da Micron (Tier-1 direto)

Achei os dois PDFs oficiais de numeração da Micron (`micron.com/numbering`):

- **`numemmc.pdf`** ("Flash + Controller... aka e-MMC **and custom card**
  part numbers") — confirma OFICIALMENTE que o prefixo MTFC é compartilhado
  entre eMMC padrão e "custom card" (onde entram os UFS) — **não existe
  posição no PN que separe os dois**. Isso não é falha da nossa gramática,
  é a Micron documentando que a distinção não é posicional. Reforça a
  necessidade de resolver por API/catálogo por PN, não por regra de decode.
- **`nummcp.pdf`, seção "All-in-One Part Numbering System"** — confirma
  `29T = LPDDR3-S4 + MLC e.MMC` (bate com nossa família) e traz as tabelas de
  densidade eMMC (`V/W/1/2/4/5/6/7/8/9/A/B` = 512MB…512GB) e LPDRAM
  (`T/U/V/W/X/Y/1-9/A/B/C` = 768Mb…64Gb, em Gbit).

  Testei a tabela em JZ003 (`AD7JKKFB`): lendo `A`+`D` como
  densidade+largura LPDRAM (16Gb → **2GB RAM**) e `7`+`J` como
  densidade+controller eMMC (32GB → **32GB NAND**, controller v5.0) dá
  32+2 = **34GB — bate exato com o total do Octopart pra JZ003.**

  **Mas ao aplicar a MESMA leitura em JZ007** (mesmos 4 primeiros
  caracteres `AD7J`, só muda o final `KKCY` vs `KKFB` do JZ003), a conta
  prevê os MESMOS 34GB — só que o Octopart mostra **36GB** pro JZ007. ⚠
  **Contradição** — significa que os caracteres finais (`KK`+`FB`/`CY`)
  também afetam a densidade (provável "chip count"/nº de dies, que o guide
  também documenta como segmento separado) e eu não consegui isolar esse
  segmento com confiança na extração do PDF (tabela de 2 colunas that saiu
  embaralhada no texto). **Não uso a leitura 32GB+2GB como confirmada** —
  é só uma hipótese que bateu uma vez e quebrou na segunda tentativa.

### Onde isso deixa cada pendência

- **JZ067 / JZ037** — capacidade sólida (256GB / 64GB), interface eMMC×UFS
  segue sem resposta mesmo depois de 2 fases de pesquisa Tier-1/Tier-2 real
  (Octopart + numbering guide oficial confirmam que não é posicional).
- **JZ061 / JZ068** — sem dado novo (Octopart vazio ou corrompido).
- **AD7 (JZ003/007/012/014)** — total confirmado só pra 2 dos 4; NAND×RAM
  ainda sem split confiável pra nenhum; JZ012/014 sem nenhum dado novo.

## 5. Resolvido 2026-07-08 — JZ067 é eMMC (Mouser, link do dono)

O dono trouxe `mouser.com/ProductDetail/Micron/MTFC256GBAOANAM-WT-TR` —
campo estruturado "Categoría de producto: eMMC" + "Tipo de producto: eMMC"
(não é texto solto de revendedor, é atributo categórico do Mouser, uma
distribuidora autorizada grande — mais confiável que Heisener/Jotrin/AAA
Chips que descartei na Fase 1). **JZ067 e JZ068 (ES, mesmo corpo de PN)
migraram pra `micron_jz067_family_2026-07-08.yaml` como eMMC 256GB
confirmed.**

**Achado que isso revela:** dentro da MESMA família de código
("O_AM_M"/"BAOANAM", capacidade 256GB), a revisão **"A" é UFS** (JZ059,
confirmado por datasheet oficial — seção 1) e a revisão **"B" é eMMC**
(JZ067/68, confirmado agora por Mouser). Não é coincidência de fonte
diferente — é a Micron trocando a interface entre revisões do mesmo
corpo de PN. **Não generalizar** esse padrão A=UFS/B=eMMC pra outras
famílias/capacidades sem confirmar cada uma (é exatamente o tipo de
"padrão que bate uma vez" que já quebrou no caso do AD7 — seção 4).

Tentei o mesmo método (Mouser) no JZ037 (`MTFC64GAPAKEA-WT`) — **não
está listado no Mouser** (fetch direto e busca por categoria eMMC+64GB
Micron não trouxeram essa peça; é obsoleta, pode ter saído do catálogo
deles). JZ037 continua com interface em aberto.

### Pendências finais (pós-Mouser)

- **Resolvido:** JZ067, JZ068 (eMMC 256GB, prontos no yaml).
- **Ainda em aberto:** JZ037 (interface), JZ061 (sem dado em lugar nenhum),
  cluster AD7 inteiro (split NAND×RAM).

## O que NÃO precisa de correção / já está pronto

`JZ047` (chave `AD8`, já mapeada corretamente) e `JZ017` (UFS 32GB, fonte
100% API oficial Micron) não dependem de nenhum dos gaps acima — já estão em
`micron_jz067_family_2026-07-08.yaml`, prontos pra dry-run.
