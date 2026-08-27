> ⚠️ **DUAS TRILHAS (Opção 2, jul/2026).** A **GRAMÁTICA** da Kingston (a família eMCP embarcado +
> os módulos DIMM desativados) vive em **`chips/knowledge/kingston.yaml`** (via `load_brands`). Os
> **known_parts** (PNs confirmados = autoridade) **NÃO ficam mais no yaml** — vivem no **banco**,
> submetidos por `submit_known_parts` e **aprovados pelo dono** no admin (four-eyes). **Processo
> obrigatório completo — LEIA: `AUTORIA.md`** (índice: `CLAUDE.md §5`).
>
> **Este `.md` é a camada humana** — NÃO reproduz os dados (decode key→valor, PNs confirmados):
> esses vivem no **yaml** (gramática) e no **banco** (known_parts). Aqui ficam: **convenções,
> anatomia do PN, armadilhas, rentabilidade, fontes, o *porquê*** e ponteiros.

---

# KINGSTON.md — Bíblia Técnica e de Negócio

> Em conflito, o **código + o yaml são a fonte da verdade** (`chips/engine.py`,
> `chips/knowledge/kingston.yaml`). Regras gerais do WTC: `CLAUDE.md`.

**Kingston Technology** (EUA, fundada 1987) é majoritariamente uma **montadora de módulos**
(DIMM/SO-DIMM) — um módulo (`KVR`/ValueRAM, `KF`/Fury, `ACR`/Action) é uma placa com dies de OUTRO
fabricante por baixo, e o PN do módulo não é o que um operador lê num **chip** individual. ⚠
**Correção 2026-08-17 (era regra de ouro errada até aqui): a Kingston TAMBÉM vende DRAM discreta
embarcada com PN próprio** — linha "Embedded Discrete DRAM" (kingston.com/us/embedded/dram),
DDR3/DDR3L, DDR4, LPDDR4 e LPDDR4x, documentada em flyers oficiais no domínio `media.kingston.com`.
⚠ **Correção 2026-08-19 (mesma classe de erro): a Kingston TAMBÉM vende eMMC standalone (embarcado,
sem RAM composta)** — linha "eMMC Embedded Flash" (kingston.com/en/embedded/emmc-embedded-flash),
PN formato `EMMC[capacidade]-[rev]`, flyers oficiais (comercial + i-Temp) também em
`media.kingston.com`. Então a marca contribui **três** tipos de chip de verdade ao catálogo: o
**eMCP** (eMMC + LPDDR compostos, embarcados/smartphones de entrada — cobertura por GRAMÁTICA no
yaml), a **DRAM discreta embarcada** (DDR3L/DDR4/LPDDR4/LPDDR4x avulsos) e o **eMMC standalone**
(sem RAM junto, `chip_type="eMMC"`, `subtype` vazio) — as duas últimas cobertas só por
**known_parts** (ver §1/§5, listas enumeradas da própria Kingston, não regra posicional).
`brand.code = KST`. O yaml de gramática hoje tem **5 famílias eMCP reais + 1 fallback genérico** +
**3 prefixos de módulo desativados** (`active: false`) — a lista viva está no yaml; nem a DRAM
discreta nem o eMMC standalone têm (nem precisam de) família própria, ver §5.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro

### 0.1 Onde vive o conhecimento

```
chips/knowledge/kingston.yaml         ← GRAMÁTICA (a família eMCP + os módulos desativados). SÓ isso (Opção 2).
banco (submit_known_parts→aprovação)  ← known_parts confirmados = autoridade (não no yaml)
AUTORIA.md / CLAUDE.md §5             ← o processo OBRIGATÓRIO das duas trilhas + convenção + comandos
```

**Duas trilhas** (detalhe em `AUTORIA.md`): **gramática** (família/mapa) → edita o yaml →
`load_brands --brand kingston` (dry-run = portão) → o **dono** roda `--commit`. **known_parts**
(autoridade) → escreve um arquivo de submissão → `submit_known_parts` (dry-run = portão) → o
**dono** roda `--commit` + **aprova no admin**. ⚠ **Família de prefixo NOVO → PN-âncora no golden é
OBRIGATÓRIO** (`GoldenObrigatorioTests` falha sem — as 6 famílias atuais, 5 eMCP + o fallback
`EMCP`, já são grandfathered/provadas; a DRAM discreta embarcada — §5 — não cria família nova, por
isso não precisa de golden). **NÃO tocar sem revisão:** `chips/engine.py`, `estoque/views.py`
(globais), yamls/known_parts de outras marcas, mapas globais (`DRAM_PC`/`DRAM_MOBILE`, dono =
Samsung — Kingston nunca referencia esses mapas, mesmo tendo DRAM discreta própria via known_parts).

### 0.2 Regras de ouro — nunca violar

1. **Claude edita arquivos. O usuário roda os comandos.** Nunca `load_brands --commit`/`migrate` sem confirmação.
2. **`load_brands --brand kingston` (dry-run) é o portão** — valida a convenção, nada gravado. Depois `--commit` (recarrega o cache sozinho, sem restart).
3. **Só eMCP tem GRAMÁTICA (família/decode posicional) aqui — não é mais "o único chip de
   verdade".** `chip_type="eMCP"`, `is_emcp=True`, categoria `managed_mcp`, é a ÚNICA coberta por
   `ChipFamily` no yaml. DRAM discreta e eMMC standalone (regras 9 e 14) também são chips REAIS da
   marca, só que cobertos por **known_parts** direto, nunca por família nova. Fonte única da
   convenção: `chips/chip_types.py`.
4. **Os dois lados do MESMO PN usam unidades DIFERENTES — a pegadinha nº1 da marca.** `pn[0:2]`
   (NAND) já é **GB direto** (`"16"` = 16GB, sem conta). `pn[6:8]` (RAM) é **Gbit ÷ 8 = GB**
   (`"08"` = 8Gbit ÷ 8 = **1GB**, não 8GB). Aplicar ÷8 no lado NAND (ou deixar de aplicar no lado
   RAM) é o erro clássico — mostre a conta sempre que confirmar um known_part novo.
5. **Sufixo `NL2` × `NL3`/`EL3` decide a GERAÇÃO real da RAM, e a gramática (decode map) SEMPRE
   assume LPDDR3.** `NL2` = LPDDR2 (162-ball, só confirmado em 4GB/8GB); `NL3`/`EL3` = LPDDR3
   (221-ball, todas as capacidades). Um PN com sufixo `NL2` que não vira `known_part` confirmado
   com `subtype`/`emcp_ram` = LPDDR2 **explícito** aparece errado (LPDDR3) pro operador — a
   gramática não lê sufixo, só a posição numérica. Sempre confira o sufixo antes de submeter.
6. **`interface` = a versão eMMC do pacote** (`"eMMC 5.0"`/`"eMMC 5.1"` — confira o yaml/datasheet
   por família, não assuma um valor fixo pra marca toda). Nunca a geração da RAM.
7. **Módulos (`KVR`/`KF`/`ACR`) ficam `active: false` — NUNCA reative nem complete capacidade
   neles.** São código de MÓDULO (placa), não de chip — o die de baixo é de outro fabricante.
   `active=false` os **remove da lista de match do engine** (`_get_all_families()` filtra
   `active=True` — `chips/engine.py`): um PN desses prefixos hoje não casa com família nenhuma e
   cai no fluxo de desconhecido/fuzzy, igual a um prefixo nunca cadastrado. Reativar não é
   "completar dado que falta" — é fazer o engine decodificar specs de um chip que não existe
   fisicamente na bancada (o chip real é de outro fabricante).
8. **Prefixo K em chip BGA = Samsung até prova em contrário — a armadilha nº1 de IDENTIDADE da
   marca.** Kingston **não fabrica silício**: todo chip BGA avulso com prefixo `K` (`K4…`, `K9…`,
   `KM…`, `KL…`, `KF9…`) é **Samsung**, e `brand=Kingston` num chip desses é quase sempre
   **misread de OCR/laser** — os 7 "Kingston" das pendências de jun/2026 eram TODOS Samsung
   (`KFG1G16U2C`/`KFG1GN6W2D`/`KFG1GNGW2D` OneNAND · `KFM4G16Q4B` MuxOneNAND · `KFC1G16U2C` =
   misread de `KFG…` · `KFMNX0012M` = `KMFNX0012M` eMCP · `KFFN60012M` = `KMFN60012M` uMCP).
   Confirme pelo PN inteiro; `KF9…` NAND = Samsung, não Kingston Fury. PN Kingston real é
   numérico (`16EMCP…`) ou de módulo (`KVR…`/`KF…/…` com capacidade após a barra). (Esses NAND
   crus `K9*`/`KF9*` são dead-by-type; na bancada física, NAND cru **TSOP** vai pra caixa **K9** —
   tipo próprio da operação desde 2026-08-14, nada a ver com Kingston.)
   ⚠ **O TESTE CERTO é a marcação do PACOTE, nunca a origem/contexto do die (corrigido 2026-08-19,
   caso `FH32B08UCT1` — eu errei pro lado oposto antes de corrigir, ver §7).** Um PN sem NENHUMA
   semelhança com o padrão Kingston (nem `K` de prefixo, nem `EMCP`/`EMMC`/`D####`) AINDA ASSIM É
   Kingston de verdade se o PACOTE FÍSICO está marcado "Kingston" — Kingston empacota/marca NAND
   cru de terceiros sob a própria marca o tempo todo (mesmo padrão dos módulos DIMM/eMCP, só que
   pra NAND avulso agora), isso é prática normal da indústria (private-label packaging), não um
   erro. `FH32B08UCT1` é exatamente isso: célula/die de fabricação Toshiba (flashinfo.top, die
   marking `983A98A376D1`), mas pacote marcado Kingston — confirmado FISICAMENTE pelo dono na
   bancada. `brand=Kingston` está CORRETO aqui. **O que NÃO conta como Kingston** é o caso oposto —
   um chip com marcação de OUTRA marca (ou sem marcação nenhuma) que só foi encontrado dentro de um
   produto acabado Kingston (die pelado de rework) — aí sim o contexto de origem vazou pro campo
   marca sem base na marcação real. **Regra prática: pesquisa web sozinha (fórum + cross-reference)
   NUNCA basta pra decidir isso — pergunte ao dono se o pacote físico está marcado ou não antes de
   excluir um PN por "não é Kingston de verdade".**
9. **DRAM discreta Kingston é REAL (corrigido 2026-08-17) — mas é lista fechada, não regra
   posicional.** A linha "Embedded Discrete DRAM" (DDR3/DDR3L, DDR4, LPDDR4, LPDDR4x) é confirmada
   em `kingston.com/us/embedded/dram` + 3 flyers oficiais em `media.kingston.com`. Como a Kingston
   publica a lista EXATA de PN que vende (não uma regra tipo `pn[x:y]→capacidade`), trate como
   **known_parts direto** (Trilha B) — não crie `ChipFamily`/decode map pra ela (evita inventar
   grammar sobre um padrão que não está documentado posição-a-posição). `chip_type` já existe pra
   todos (`DDR3L`/`DDR4`/`LPDDR4`/`LPDDR4X`) — sem tipo novo, sem handshake pendente. Um chip físico
   com marcação Kingston que não bate nem com eMCP nem com nenhum PN dessa lista (ou lista-irmã que
   você ainda não achou) é candidato a legado/não-catalogado — pesquise o cluster antes de excluir
   (ver caso `D1216MCABXGGBS` no histórico §7: identidade confirmada fisicamente, família "MCAB" só
   nesse chip, não em nenhum flyer atual — tratado como legado, não como erro; **segundo caso
   confirmado 2026-08-19**, PN `D2516EC4BXGGB`, família `EC4B` — mesmo padrão: geração obsoleta,
   substituída pela `ECMD` atual no mesmo prefixo de densidade — ver §7).
10. **Não confie em distribuidor sozinho para capacidade** (mesmo um B2B rastreável já usado como
    apoio no catálogo atual) — cruze com `kingston.com`/Octopart antes de subir
    `confidence: confirmed`. PN ambíguo (sufixo estranho, capacidade fora da tabela) → **pergunte
    ao dono**, nunca decida sozinho. E **exclua, não adivinhe**: spec ESSENCIAL que não fechar em
    fonte Tier-1 → o PN **sai da submissão** (nunca campo em branco/estimado — regra cross-marca).
11. **Pesquise o CLUSTER inteiro, nunca 1 PN por rodada** (regra PERMANENTE do dono, cobrada 5×
    agora — caso `EMMC04G-WT32` no §7, 2026-08-19, foi a última vez): cada rodada cobre a
    família/chave completa — capacidades e sufixos irmãos — mesmo que a chave já esteja bem
    confirmada. O objetivo é **cobertura de PNs**, não provar a regra de novo. ⚠ **Regra
    operacional explícita (reforçada após o miss de 2026-08-19): TODO PN visto em QUALQUER fonte
    buscada durante a rodada entra na submissão — não só o(s) PN(s) que casam com o padrão/sufixo
    específico do alvo original.** Buscar uma fonte só pra CONTEXTO/COMPARAÇÃO (ex.: o flyer vigente,
    pra confirmar que o alvo é legado) e depois descartar os PNs vigentes encontrados nessa MESMA
    fonte é o erro exato a evitar — se um fetch devolveu uma tabela inteira com specs, a tabela
    inteira é candidata a known_parts, não só a linha que motivou a busca.
12. **Toda entrega de submissão LISTA os known_parts no chat** — PN + spec + confidence colados na
    mensagem, não só o arquivo (pedido do dono, 2026-07-09).
13. **O comando entregue é sempre o par dry-run + `--commit`, sem `--user`** —
    `submit_known_parts <arquivo>` e `submit_known_parts <arquivo> --commit`, mesmo quando a mesma
    mensagem tem pergunta/pendência (dono, 2026-07-09/10; o `--user` citado no `AUTORIA.md` não
    vai no comando entregue).
14. **eMMC standalone Kingston é REAL (confirmado 2026-08-19) — mesmo tratamento da regra 9: lista
    fechada, known_parts direto, nunca família nova.** Linha "eMMC Embedded Flash"
    (`kingston.com/en/embedded/emmc-embedded-flash`), PN formato `EMMC[capacidade]-[rev]` (ex.:
    `EMMC04G-M627`), flyers oficiais comercial + i-Temp + automotivo em `media.kingston.com`.
    `chip_type="eMMC"`
    já existe no vocabulário (`chip_types.py`, categoria `managed_nand`) — sem tipo novo, sem
    handshake. **`subtype` fica VAZIO** (diferente da DRAM discreta, onde `subtype` espelha o
    `chip_type` — aqui é igual ao eMCP/UFS: geração não vai no subtype porque não há geração de RAM
    pra carregar). Capacidade é **GB literal** (sem conta Gb÷8, diferente da DRAM/LPDDR) — mesmo
    padrão do lado NAND do PN eMCP (regra 4). 1º caso: `EMMC04GM627` físico não bateu no flyer
    vigente (que lista `EMMC04G-MT32`/`-CT32`) — **3º caso confirmado do padrão "família legada fora
    dos flyers vigentes"** (depois de `MCAB` e `EC4B`, ver §7) — corroborado como `EMMC04G-M627` via
    tier inferior denso. Terreno novo (nenhum known_part de eMMC standalone submetido antes por este
    chat): mapeamento de campo (`capacity` vs `emcp_nand`) é inferência minha por analogia, não
    precedente copiado — conferir o dry-run antes do `--commit`. **Achado 2026-08-19 (2ª rodada,
    PN `EMMC16GTB28`): múltiplas gerações de sufixo/pacote podem coexistir pra MESMA capacidade**
    (não é só 1 legado isolado — ver §7). Ao pesquisar um PN novo desta linha, busque explicitamente
    por variações do sufixo numérico (`TB28`↔`TB29`↔`TA29`↔`TX29`↔`TY29` etc.), não só a capacidade.
15. **Um md5 batendo no momento do commit NÃO prova que o arquivo continua igual quando o dono roda
    o comando depois** — se outro processo tem escrita no mesmo disco (aqui tem: "infra" corrige
    arquivos por fora, já aconteceu 2×), o arquivo pode mudar entre eu commitar e o dono rodar. Não
    inferir "formato X funciona" a partir de um run bem-sucedido sem confirmar que o arquivo
    executado era mesmo o que eu escrevi (caso `brand:` bloco×string, 2026-08-17/19 — ver §7).

### 0.3 Hierarquia de fontes (imutável)

```
1. kingston.com — seção Embedded/Industrial (Tier 1) → datasheet/specsheet oficial por PN
2. Octopart com fonte rastreável
3. Distribuidor B2B rastreável (ex.: Puris.net) — só apoio pra capacidade; nunca decide sozinho, nunca rebaixa um confirmed
4. Chip físico lido na esteira/bancada — forte pra IDENTIDADE (o PN existe, o sufixo é esse); não substitui datasheet pra spec
5. IA externa — ÚLTIMO RECURSO; verificar SEMPRE
```
Nunca fonte primária: fóruns, catálogos genéricos sem rastreio, eBay, IA sem verificação.

---

## 1. Convenção Canônica de Campos ⚠️ LEIA PRIMEIRO

> **OPÇÃO 1. Fonte única da convenção: `chips/chip_types.py` (código).** Contexto geral: CLAUDE.md.
> Kingston usa **três** categorias agora: gerenciada/composta (eMCP, via gramática), DRAM discreta
> (DDR3L/DDR4/LPDDR4/LPDDR4x, via known_parts enumerado — §0.2 regra 9) e eMMC standalone (via
> known_parts enumerado — §0.2 regra 14).

| Tipo | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| eMCP (única família de gramática ativa) | `"eMCP"` | geração da RAM (`"LPDDR3"` ou `"LPDDR2"` — nunca as duas juntas) | versão eMMC (`"eMMC 5.0"`/`"eMMC 5.1"`) | `emcp_nand` (GB) + `emcp_ram` (tipo+capacidade) |
| DDR3L / DDR4 (known_parts, sem família) | a geração (`"DDR3L"`/`"DDR4"`) | espelha o `chip_type` | bus width (`"x8"`/`"x16"`) | `density_gbit` = die em Gb (nunca GB) |
| LPDDR4 / LPDDR4x (known_parts, sem família) | a geração (`"LPDDR4"`/`"LPDDR4X"`) | espelha o `chip_type` | `""` | `capacity` = pacote em GB (código Gbit÷8, mostre a conta) |
| eMMC standalone (known_parts, sem família) | `"eMMC"` | **vazio** (igual eMCP/UFS — sem geração de RAM pra carregar) | versão eMMC (`"eMMC 5.0"`/`"eMMC 5.1"`) | `capacity` = GB **literal** (sem conta, diferente da DRAM) |
| Módulo DIMM (`KVR`/`KF`/`ACR`, `active: false`) | genérico (`"RAM"`/`"DDR"`) — só existe porque a família está desativada; nunca ativar assim | — | — | — |

**Regras absolutas:** `subtype` = só a geração da RAM (nunca "162-ball"/"221-ball"/"Mobile" — isso
é `tip`). `emcp_nand` = GB direto (o código do PN já é GB, sem conta). `emcp_ram` = `"LPDDR{n}
{cap}GB"`, tipo **antes** da capacidade, `{cap}` calculado a partir de **Gbit ÷ 8** (nunca o
número cru do PN) — **abaixo de 1GB use MB** (ex.: a família de 4GB usa `"LPDDR3 512MB"`, não
`"0.5GB"`; o parser do engine lê os dois). `tip` = o resto (ball-count, geração de package
NL2/NL3/EL3, origem, destino).

**Label da caixa:** `EMCP{nand}+{ram}` (ex.: `EMCP16+1` pra 16GB eMMC + 1GB LPDDR3) — mesmo padrão
cross-marca do `CLAUDE.md §6`.

---

## 2. Anatomia do PN — como LER um chip Kingston

> A estrutura vem do decode das 5 famílias eMCP (`chips/knowledge/kingston.yaml`) — aqui fica a
> ESTRUTURA (durável) e as pegadinhas; os valores de cada chave vivem nos mapas do yaml
> (`KST_EMCP_NAND_CAP`/`KST_EMCP_RAM_CAP`).

**Formato: `[NN]EMCP[NN]-[sufixo]`** (ex.: `16EMCP08-NL3DTB28`):

- **`pn[0:2]`** — capacidade **NAND** (eMMC), código = **GB direto** (`"16"` → 16GB). Mapa
  `KST_EMCP_NAND_CAP`. Cada capacidade é uma família própria — `04EMCP`/`08EMCP`/`16EMCP`/
  `32EMCP`/`64EMCP` — o código de NAND faz parte do **prefixo**, não é uma posição dentro de uma
  família única.
- **literal `"EMCP"`** (`pn[2:6]`) — assinatura fixa da linha.
- **`pn[6:8]`** — capacidade **RAM** (LPDDR), código = **Gbit ÷ 8 = GB** (`"08"` → 8Gbit ÷ 8 =
  **1GB**). Mapa `KST_EMCP_RAM_CAP`, já devolve a string `"LPDDR3 <cap>"` pronta (tipo embutido).
- **sufixo** (após o `-`, ex.: `NL3DTB28`) — **NÃO decodificado pela gramática** (vira `tip`, não é
  posição lida). Os 2 primeiros caracteres dizem a geração/package real: `NL2` = LPDDR2 (162-ball)
  × `NL3`/`EL3` = LPDDR3 (221-ball). **A gramática sempre devolve LPDDR3** (default da família) —
  só um `known_part` confirmado com o sufixo `NL2` corrige o caso pra LPDDR2 (regra de ouro §0.2#5).

**Ordem de match (`chips/engine.py::_match_family`):** primeira família ativa, ordenada por
`priority` (crescente) e depois por tamanho de prefixo (decrescente), cujo `pn.startswith(prefix)`
bate. As 5 famílias eMCP têm `priority=50` — entre elas o prefixo de 6 chars (`"16EMCP"` etc.)
sempre vence o fallback genérico `"EMCP"` (4 chars) por ser mais longo, então o genérico só casa
com um PN que comece literalmente em `"EMCP"` sem os 2 dígitos de NAND na frente — **raro, não
editar sem um PN real que precise dele.**

---

## 3. Armadilhas e Decisões Arquiteturais

- **Gb×GB assimétrico no MESMO PN (regra de ouro §0.2#4)** — o lado NAND (`pn[0:2]`) é GB puro; o
  lado RAM (`pn[6:8]`) é Gbit÷8. Fácil aplicar a conta errada nos dois lados por hábito (a maioria
  das outras marcas usa Gbit dos dois lados). Refaça a conta na mão ao confirmar um PN novo.
- **Sufixo inventado — erro de IA já documentado no catálogo:** um known_part anterior citava
  `"32EMCP16-NL3DTB29"`; **esse PN não existe.** O real, confirmado via distribuidor B2B, é
  `"32EMCP16-EL3GTB29"` — a família de 32GB só tem variante `EL3`, nunca `NL3`. Lição durável:
  **nunca extrapole o sufixo por padrão visual** (`NL3`→`EL3` não é um typo aleatório, é uma
  revisão de package real) — exija o PN exato de uma fonte, não "parecido com".
- **`KF` é ambíguo entre marcas.** `KF9…` de NAND costuma ser **Samsung**, não Kingston Fury — o
  prefixo curto sozinho não decide a marca.
- **Módulo ≠ chip.** `KVR`/`KF`/`ACR` identificam a placa DIMM/SO-DIMM, não o die dentro dela — o
  die de baixo é de outro fabricante. `active: false` **remove a família do match** (não é
  "reconhece mas sem specs" — ver §0.2#7); é decisão definitiva, não um placeholder à espera de dado.
- **`decode_gen_len: 2` sempre** — diferente de famílias de outras marcas que codificam RAM em 1
  caractere, aqui são sempre 2 (`pn[6:8]`), inclusive pra capacidades pequenas (`"04"`, não `"4"`).

---

## 4. Rentabilidade — princípio (os valores NÃO ficam aqui)

**Fonte única: `assess_profitability`** (`chips/engine.py`); os limiares vivem no
**`ProfitabilityConfig`** (admin, você edita). ⚠ **É dado mutável** — por isso este doc não cita
limiar nem veredicto por capacidade (dataria no dia seguinte).

Regras duráveis: eMCP é avaliado pelo par `emcp_nand`/`emcp_ram` (nunca só um dos dois); a
capacidade sempre chega em MB/GB nas duas pontas — nunca deixe um código Gbit cru vazar pro campo
(vira **INDETERMINADO** = bloqueador de produção). Como o engine lê: `emcp_nand` → GB direto;
`emcp_ram` → extrai a capacidade da string `"LPDDR{n} {cap}"`.

---

## 5. Gaps e Roadmap (o durável — o resto está no yaml)

- **eMMC standalone Kingston — PESQUISADO e CONFIRMADO 2026-08-19 (§0.2 regra 14), CATÁLOGO VIGENTE
  COMPLETO submetido (20 known_parts).** Não virou família nova (known_parts direto, mesma lógica
  da regra 9 — não é prefixo posicional). PN-âncora legado: `EMMC04G-M627` (+ irmã i-Temp
  `EMMC04G-W627`) — geração obsoleta fora dos flyers vigentes. Depois do miss documentado em §7
  (`EMMC04G-WT32` extraído e não submetido na 1ª entrega), o arquivo foi expandido pros **18 PN dos
  3 flyers vigentes inteiros** (comercial: `MT32`/`CT32`/`MV28`/`MW28`/`TS0A`/`TB9F`/`TY29`×3;
  industrial: `WT32`/`WV28`/`WW28`/`IY29`×3; automotivo: `AR0A`×2) — Tier-1 direto, sem precisar de
  corroboração externa. Ainda por pesquisar: (a) outras capacidades da geração legada `627`
  (8G/16G/32G/64G/128G/256G) — busquei e não achei, mas o gatilho até agora sempre foi um PN físico
  específico, não uma varredura completa; (b) `EMMC04G-S627` — achado em fonte (verical) mas
  bloqueado por robots.txt antes de confirmar specs, excluído por ora; (c) `E04GS14DXI` (linha da
  tabela i-Temp, PN sem o prefixo "EMMC" que todo outro PN do catálogo usa) — sem corroboração
  independente, excluído como provável artefato de extração de PDF, não confirmado nem descartado
  em definitivo.
- **eMMC standalone — 2ª rodada 2026-08-19 (PN `EMMC16GTB28`) achou uma SEGUNDA geração de
  sufixo/pacote, +5 known_parts (total 25).** `EMMC16G-TB28` (pacote FBGA-153 fino, 0.8mm) e
  `EMMC16G-TB29`/`EMMC32G-TB29` (pacote FBGA-153 maior/mais espesso, 1.4mm, datasheet conjunto
  próprio) são gerações DIFERENTES entre si e diferentes de `MW28`/`TY29` (flyer vigente) — mesma
  capacidade, 3+ códigos de sufixo distintos coexistindo. Mesmo padrão pro lado 4G/8G:
  `EMMC04G-MK27` + `EMMC08G-ML36` (flyer alternativo `eMMC_Product_flyer.pdf`, também em
  `media.kingston.com`, distinto do `emmc_flyer_us.pdf` já usado). **GAP aberto — existência
  confirmada, specs NÃO confirmados** (2 tentativas de fonte cada, nenhuma rendeu tabela completa):
  `EMMC04G-M657` (3ª opção de 4G no mesmo flyer alternativo), `EMMC64G-W525` (achado incidental, nem
  capacidade confirmada). Retomar quando um PN físico novo disparar a busca de novo, ou se uma fonte
  melhor aparecer. ~~`EMMC32G-TA29`/`EMMC64G-TA29`/`EMMC128-TA29` e `EMMC32G-TX29`/`EMMC64G-TX29`/
  `EMMC128-TX29`~~ **RESOLVIDO 2026-08-20** — 6 known_parts confirmados (datasheet oficial Kingston
  + Arrow/Avnet/DigiKey/Mouser), ver §7. Lição: as 2 tentativas de ontem não esgotaram tier-2, só
  pararam cedo. **4ª expansão 2026-08-26 — geração "S100" achada (PN físico `EMMC16GS100`), +4
  known_parts (04G/08G/16G/32G, total 35).** Geração BEM mais antiga que as outras (Obsolete desde
  ~2016/2017) — não está em nenhum dos 2 flyers já usados neste arquivo. eMMC 5.0 confirmado direto
  só na irmã de 32GB, resto por inferência de família. 64G/128G tentados e não achados — ver §7.
- **NAND Flash cru Kingston (chip_type "NAND Flash", categoria `nand_raw`) — ABERTO 2026-08-19,
  2 known_parts (`FH32B08UCT1`/`FH64B08UCT1`, ver §7).** Kingston empacota/marca NAND cru de
  terceiros (célula Toshiba confirmada nos 2 achados) sob a própria marca — `profit_family="dead"`
  no chip_types.py, preço fixo/sucata, rigor de fonte relaxado com autorização do dono. Padrão de PN
  `FH[capacidade]B08UCT1` — só 32GB/64GB confirmados até agora, tentei 08G/16G/128G sem achar fonte.
  Gatilho sempre foi PN físico direto do estoque, não varredura.
- **eMMC gerenciado Kingston, prefixo `KE4` (chip_type "eMMC" standalone, sem RAM combo) — 12
  known_parts em 3 rodadas (2026-08-20 ×2 + 2026-08-26, ver §7).** Era achado lateral não perseguido
  desde 2026-08-19; agora tem **3 formatos de PN confirmados, cobrindo PELO MENOS 2 gerações eMMC
  diferentes**: forma curta `KE4CN[dígito][letra][dígito]A` (9 chars, eMMC 4.5, 6 PN via RS
  Components: KE4CN2H5A=4GB/153pin, KE4CN3H5A=8GB/153pin, KE4CN3K6A=8GB/169pin, KE4CN4A5A=16GB/153pin,
  KE4CN4K6A=16GB/169pin, KE4BT4B6A=16GB/169pin-FBGA — prefixo "KE4BT" em vez de "KE4CN"); forma longa
  `KE4CN2L2…` (14+ chars, mais campos — empilhamento de dies/revisão; o PN físico que disparou a 1ª
  rodada, `KE4CN2L2SA5H2A`, foi resolvido em tier 2 — 8GB, 2 dies de 4GB, célula Toshiba, 162-Ball
  FBGA, com discrepância documentada contra o storage anunciado do aparelho onde é usado); e o formato
  NOVO achado na 3ª rodada, `KE44B-[dígito][letra]AN/[cap]GB` (hífen+barra, capacidade LITERAL no
  sufixo, **eMMC 4.41** — geração diferente da 4.5 da família CN/BT — 3 PN: 2/4/8GB, 153/169-pin
  FBGA). A 3ª rodada também RESOLVEU `KE4CN5B6A` (antes excluído por ambiguidade "32Gbit"×"32GByte")
  — Octopart confirmou independentemente 32GB/eMMC 4.5 — e achou a irmã `KE4BT5D6A` (32GB). Lição:
  quando o campo curto de capacidade de um distribuidor usa unidade "bit" isolada sem bater com o
  campo de organização/sufixo do próprio PN, é sinal de inconsistência de template, não spec real —
  vale cruzar com uma 2ª fonte antes de excluir ou aceitar.
- **128GB eMCP** — nunca confirmado em nenhuma fonte; 64GB é o teto atual da linha. Se aparecer,
  precisa de PN-âncora + fonte Tier-1/B2B antes de virar família nova.
- **`NL2` (LPDDR2) só confirmado em 4GB/8GB.** Se aparecer numa capacidade maior (16GB+), é
  candidato a exceção real ou a sufixo mal-lido — confirmar fonte antes de aceitar.
- **eMCP `08EMCP04`/`08EMCP08` tem 2 gerações de sufixo pesquisadas a fundo — "AV100" (9 known_parts,
  2 rodadas: 20/08 + 26/08 — ver §7) e "CV100" (3 known_parts, 2026-08-20 — ver §7) —, além de
  DT227/DM327/AS100/DM627 já cobertos por gramática.** AV100 tem forma BASE (sem revisão) E formas
  com revisão "-C##" coexistindo como known_parts distintos — a 2ª rodada confirmou que a forma base
  `08EMCP04-NL2AV100` é PN real (não só truncamento do `08EMCP04NL2AV1` registrado na 1ª rodada; os
  dois aparecem fisicamente na bancada). Busca incidental achou AINDA MAIS sufixos não perseguidos:
  `BT227` (existe em 04 e 08), `BS100`, `CU100`, `DT527`, `EL2BV100` (esse último com token `EL2` —
  nem NL2 nem EL3, geração não documentada ainda). Padrão igual ao TB28/TB29/TA29/TX29 do eMMC
  standalone — família eMCP provavelmente tem MUITAS gerações paralelas de sufixo, catalogar todas é
  rodada própria (grande), não cabe numa correção pontual disparada por 1 PN de fila de revisão.
- **Módulos (`KVR`/`KF`/`ACR`) seguem desativados por design** — não é backlog pendente, é decisão.
- **DRAM discreta embarcada (§0.2 regra 9) — submissão inicial de 2026-08-17 cobriu os 4 flyers
  oficiais atuais (~30 PN: DDR3L/DDR4/LPDDR4/LPDDR4x); 2ª rodada 2026-08-19 somou a família legada
  `EC4B` (2 PN, DDR3L 4Gb x16, obsoleta); 3ª rodada 2026-08-26 somou a família legada `EETB` (2 PN,
  DDR3L 4Gb x8, obsoleta, mesmo código de densidade "5128" do `ECMD` atual — ver §7).** Ainda por
  pesquisar: (a) família "MCAB" do caso `D1216MCABXGGBS` — só esse PN confirmado, pode ter irmãs
  (outras capacidades/pacotes) que nenhum flyer atual lista, prováveis legado pré-"ECMD"; (b) ~~linha
  eMMC standalone embarcada~~ RESOLVIDO 2026-08-19 — ver entradas acima, 31 known_parts; (c) o padrão
  de família legada obsoleta (visto 3× agora em DDR3L: `MCAB`, `EC4B` e `EETB`) pode se repetir em
  DDR4/LPDDR4/LPDDR4x também — só aparece quando um PN físico novo dispara a busca, não dá pra
  antecipar sem gatilho real.

---

## 6. Fontes de pesquisa

Ver hierarquia completa em §0.3. Tier 1: `kingston.com` (Embedded/Industrial). Tier 2: Octopart
rastreável. Apoio (nunca decisivo sozinho): distribuidor B2B rastreável (ex.: Puris.net) e
confirmação física do chip na esteira/bancada. **Evitar:** distribuidor sem rastreio, fóruns, IA
sem verificação cruzada. Sempre conferir: `Xbit ÷ 8 = YB` no lado RAM do PN.

**DRAM discreta embarcada:** landing `kingston.com/us/embedded/dram` lista os flyers oficiais por
família (URLs em `media.kingston.com/pdfs/...` — mudam de nome entre revisões, procure pelo link
"Product Flyer" da família certa em vez de fixar a URL). DigiKey/Mouser/Future Electronics/Octopart
como cross-check (não como fonte decisiva) — vários PN da linha aparecem lá com o datasheet Kingston
espelhado.

---

## 7. Histórico (o *porquê* — durável)

- **Confirmação física na esteira ancorou a família de 16GB** — reforça que, quando possível, ler
  o chip real na bancada é a melhor evidência de identidade disponível pra essa marca (catálogo
  oficial magro, poucas famílias).
- **Sufixo `NL3DTB29` inventado num ciclo anterior de enriquecimento** (família de 32GB) — ver §3.
  É o motivo da regra "nunca extrapole sufixo por padrão" estar em negrito nas regras de ouro.
- **2026-08-17 — "Kingston não fabrica DRAM avulsa" era regra ERRADA, corrigida no primeiro caso
  real.** Disparado pelo PN físico `D1216MCABXGGBS` (dono leu 4 linhas no chip: `N11044-01` /
  `1648 S2C 6` (date code ~semana 48/2016) / `D1216MCABXGGBS` / `54MJE222000J`). A busca no PN
  exato não bateu em NENHUMA fonte Tier-1 (kingston.com, Octopart, DigiKey todos "not found"; só
  corretor chinês de 2ª linha, um com spec incompatível "PC1600") — mas a busca mais ampla achou a
  linha real "Embedded Discrete DRAM" da Kingston, com o MESMO código de organização `1216` (2Gb
  x16) usado pela família atual `D1216ECMD…`. Conclusão aplicada: identidade do PN físico é
  confirmada (leitura direta), a classificação (DDR3L/2Gb/x16) é inferida por analogia à família
  confirmada — não por datasheet próprio, porque `D1216MCABXGGBS` não está em nenhum flyer vigente
  (provável SKU legado, pré-padronização no código "ECMD"). Lição: um PN não bater em Tier-1 não
  prova que a marca/categoria esteja errada — pode ser só um SKU antigo fora do catálogo atual;
  vale ampliar a busca pra família/linha de produto antes de descartar.
- **2026-08-19 — segundo caso de DRAM discreta legada: família `EC4B`, irmã obsoleta da `ECMD`
  atual.** Disparado pelo PN físico `D2516EC4BXGGB` (debug de estoque real, `known: false`). Tier-1
  vigente (os 3 flyers oficiais em `media.kingston.com`) só lista a família `ECMD` no prefixo de
  densidade `2516` (4Gb x16) — `EC4B` não aparece em nenhum flyer atual. Ampliando pra tier
  inferior: **7+ fontes independentes** (Octopart, alldatasheet, datasheet4u, harddiskdirect,
  datasheets.com, electronicsdatasheets.com, newtownspares, verical, censtry) concordam nos specs —
  DDR3L, 4Gb, 256Mx16, FBGA-96, 1.35V — e todas convergem numa velocidade DIFERENTE da `ECMD`:
  **1600 Mbps/CL11** (`ECMD` no mesmo prefixo é 1866/2133 Mbps). O Octopart marca **status Obsolete,
  last tracked 2020-12-30** — bate com a leitura de "geração anterior, descontinuada". Cadastrado
  como known_parts (`D2516EC4BXGGB` C-Temp + `D2516EC4BXGGBI` I-Temp) com `confidence: confirmed`
  apoiado em corroboração tier-inferior densa, não em datasheet Kingston hospedado (Tier-1 direto
  não confirma essa família específica). Busquei irmãs de outra capacidade/organização
  (`D1216EC4B…`/`D2568EC4B…`/`D5128EC4B…`/`B5116EC4B…`, espelhando o espectro completo da `ECMD`) e
  não achei nenhuma — cluster desta família parece ser só essas 2 PN. **Padrão confirmado agora 2×**
  (`MCAB` em 2026-08-17, `EC4B` em 2026-08-19): a Kingston trocou o código de família ao longo do
  tempo mantendo o prefixo de densidade (`1216`/`2516`/etc.) estável — quando Tier-1 não bate mas o
  prefixo de densidade sim, é um forte indício de família legada, não de marca errada.
- **2026-08-19 — `brand:` no arquivo de submissão é STRING, nunca bloco — mordeu 2× antes de
  virar regra permanente (§0.2 regra 15).** Hipótese minha (errada): `submit_known_parts` reusaria
  o schema `BrandFile` da gramática (`brand: {name, code, notes}`). Real: são schemas SEPARADOS —
  `BrandFile`/`BrandSpec` (em `chips/knowledge/schema.py`) é só do `load_brands`; a submissão faz
  `Brand.objects.filter(name=<valor de brand>)` direto, então `brand:` tem que ser o nome em texto
  puro (`brand: Kingston`). Com bloco, a busca nunca casa → `CommandError: marca '{dict}' não
  existe` (mensagem enganosa, sugere "crie a gramática" quando o problema é só formato). Mordeu 2×
  (batch DRAM 17/08, batch EC4B 19/08) porque, entre as duas, eu vi um dry-run "funcionar" no
  terminal do dono e concluí (errado) que bloco funcionava — não percebi que o arquivo tinha sido
  corrigido por fora (por quem mantém o código) entre eu commitar e o dono rodar. Corrigido de vez
  em `AUTORIA.md §4` (commit `dcad9ae`) com exemplo ❌/✅ lado a lado, e o próprio comando agora
  detecta o bloco e aponta a correção certa. Lição: md5 batendo no commit não prova nada sobre o
  que roda depois, se outro processo escreve no mesmo disco.
- **2026-08-19 — terceiro caso do padrão "família legada": eMMC standalone, PN `EMMC04G-M627`.**
  Disparado por PN físico direto do estoque (`known: false`). Mesma forma dos casos `MCAB`/`EC4B`:
  o flyer vigente lista `EMMC04G-MT32`/`-CT32` (não `-M627`) no mesmo código de capacidade `04G`.
  Tier inferior (alldatasheet, ic-components, LCSC, Utmel) confirma `EMMC04G-M627`: eMMC 5.1,
  FBGA-153, MLC, -25~+85°C. Achei também a irmã i-Temp `EMMC04G-W627` (datasheet Kingston mirror no
  DigiKey: eMMC 5.0, FBGA-153, MLC, -40~+85°C, VCC 3.3V/VCCQ 1.8-3.3V) — confirma que a geração
  `627` cobre mais de um grau térmico, mesmo padrão da `ECMD`/i-Temp. Fecha o gap de eMMC standalone
  que estava aberto desde a criação deste doc (§5). Ver regra 14.
- **2026-08-19 — eMMC standalone tem MUITAS gerações de sufixo coexistindo, não só 1 legado
  isolado (achado na 2ª rodada, PN físico `EMMC16GTB28`).** Diferente do padrão visto em MCAB/EC4B/
  "627" (1 geração legada isolada por família), aqui achei pelo menos 4 famílias de sufixo
  PARALELAS pras mesmas capacidades (16-128GB): `TB28`, `TB29`, `TA29`, `TX29`, além da `TY29`/
  `MW28`/`TB9F` já confirmadas no flyer vigente — cada uma com datasheet/pacote físico PRÓPRIO
  (ex.: `TB28` é FBGA-153 fino de 0.8mm; `TB29` é FBGA-153 grande de 1.4mm — fisicamente peças
  diferentes, não o mesmo chip com nome trocado). Também achei que a Kingston mantém pelo menos
  DOIS flyers oficiais diferentes no mesmo domínio `media.kingston.com`
  (`emmc_flyer_us.pdf` vigente vs `eMMC_Product_flyer.pdf`, achado por busca — este último lista
  `M627`/`MK27`/`M657`/`ML36`/`TB29`/`TX29`, um vocabulário de PN diferente do primeiro). Lição:
  pra essa linha específica, "achei um PN que não bate no flyer vigente" não implica 1 geração
  legada isolada — pode ser QUALQUER UMA de várias gerações paralelas, e vale a pena buscar
  variações do sufixo numérico (`28`↔`29`, `A`↔`B`↔`X`↔`Y` na posição da letra) tanto quanto buscar
  a capacidade. Especificações de 4 PN encontrados nesta rodada (`M657`, `TA29`×3, `TX29`×3,
  `W525`) ficaram com existência confirmada mas specs NÃO confirmados após 2 tentativas de fonte
  cada — excluídos por ora (ver §5), não forcei confidence sem dado.
- **2026-08-19 — miss concreto da regra 11: `EMMC04G-WT32` extraído e não submetido na 1ª entrega.**
  Na mesma rodada de pesquisa do caso `EMMC04G-M627`/`W627` acima, busquei os 3 flyers oficiais
  vigentes (comercial, i-Temp, automotivo) só pra CONTEXTO/COMPARAÇÃO — confirmar que M627/W627 eram
  legados fora do catálogo atual. Extraí a tabela inteira dos 3 flyers (18 PN, specs completos:
  capacidade, pacote, tipo de NAND, faixa de temperatura) mas só submeti os 2 PN legados que
  motivaram a busca — os 18 PN vigentes (Tier-1 direto, mais fáceis de confirmar que os legados)
  ficaram de fora do arquivo. O dono colou um NOVO debug (`EMMC04GWT32`, `known: false`) e teve que
  redescobrir um PN que eu já tinha na mão, com specs prontos. Causa: tratei "PN que motivou a busca"
  como o único alvo válido da rodada, em vez de tratar "todo PN que a rodada revelou" como o escopo.
  Corrigido: arquivo expandido de 2 pra 20 known_parts (os 2 legados + os 18 vigentes dos 3 flyers).
  Regra 11 (§0.2) ganhou a frase operacional explícita. Lição pra qualquer chat de marca, não só
  Kingston: contexto buscado numa rodada não é descartável só por não ser o alvo original — se tem
  PN+specs extraíveis numa fonte já aberta, vai pro arquivo, mesmo que a motivação original da busca
  fosse outra.
- **2026-08-19 — `FH32B08UCT1`: eu errei ao excluir, dono corrigiu com leitura física do chip
  (ver §0.2 regra 8 revisada).** PN veio no debug de estoque marcado pra fila Kingston
  (`known:false`), sem bater em NENHUM padrão conhecido da marca (sem prefixo `K`, sem
  `EMCP`/`EMMC`/`D####`). Só com pesquisa web (2 fóruns chineses de produção de pendrive + o
  cross-reference flashinfo.top apontando fabricante da célula = Toshiba/东芝), concluí ERRADO que
  não era chip Kingston de verdade e não submeti nada. O dono corrigiu na hora, com a fonte mais
  forte disponível — leu o chip FISICAMENTE na bancada: "é kingston porque esta escrito kingston,
  mas é grande e antigasso". O teste certo é o que está IMPRESSO NO PACOTE, não de onde o die veio
  nem quem fabricou a célula por baixo — Kingston empacota NAND de terceiros sob a própria marca
  (mesmo padrão dos módulos DIMM/eMCP). Corrigido: submetido `FH32B08UCT1` (32GB, TLC, TSOP48,
  processo 15nm/planar) + irmã achada na mesma rodada `FH64B08UCT1` (64GB, TLC, BGA132, BiCS3/3D
  NAND — geração mais NOVA que a de 32GB apesar do PN parecido). `chip_type="NAND Flash"`
  (categoria `nand_raw`, `profit_family="dead"` — preço fixo, não diferencia por spec fina);
  `confidence:confirmed` aqui usa fonte de menor tier com autorização explícita do dono, dado o
  contexto de baixo valor econômico ("é sucata"). Lição durável: pesquisa web sozinha nunca deveria
  ter bastado pra excluir um PN só por "não bate no padrão da marca" — perguntar ao dono se o
  pacote físico está marcado é mais barato e mais confiável que concluir sozinho a partir de fórum
  + cross-reference. Achado lateral, não perseguido a fundo: existe uma linha Kingston "eMMC
  gerenciado" com prefixo `KE4…` (153/169-pin BGA, achada via RS Components) que este chat nunca
  pesquisou — candidata a rodada futura, não gap urgente (achado incidental de uma busca de
  siblings pra outra coisa).
- **2026-08-20 — sufixo de lote pode vir GRAVADO NO PACOTE pra NAND Flash cru; suposição antiga
  ("sufixo é só metadado de catálogo") não é universal.** Dono colou debug do MESMO chip
  `FH32B08UCT1` de ontem, mas desta vez a leitura física trouxe `FH32B08UCT10C` — o sufixo de
  lote/revisão "-0C" (o mesmo já visto na URL do flashinfo.top) estava de fato impresso no pacote
  desta unidade. Até aqui a regra usada neste chat era "sufixo de revisão/distribuidor não é o que
  vem gravado no chip" (ex. `-M06U` suprimido no caso `EMMC04G-W627`) — vale às vezes, mas NÃO
  sempre; NAND cru reempacotado por lote parece ser um caso onde o sufixo É físico. Ação: cadastrado
  `FH32B08UCT1-0C` como known_part próprio (mesmas specs da base `FH32B08UCT1`) em vez de confiar
  que `part_number_norm` apara sufixo curto sem hífen sozinho — mais barato registrar as duas formas
  que apostar na normalização. Dono sugeriu "cadastrar a gramática" (Trilha A) pra esse caso — não
  segui: `chip_type="NAND Flash"` aqui é lista fechada de 2 SKU (regra 9/14 já estabelece esse
  padrão pra TODO caso "legado" desta marca — known_parts, nunca `ChipFamily` nova) e
  `profit_family="dead"` (sucata, sem ganho em decodificar capacidade por posição). Lição geral:
  quando `known:false` reaparece pro MESMO PN já submetido, primeiro checar se o batch anterior já
  rodou dry-run+`--commit`+aprovação no admin (motivo mais comum e mais barato de checar) antes de
  assumir um bug de normalização ou pedir gramática nova.
- **2026-08-20 — `08EMCP04NL2AV1`: 1º caso real de correção de gramática eMCP via known_part
  (o mecanismo já estava documentado, regra §0.2#5, mas nunca tinha sido usado nesta rodada).**
  Debug de estoque trouxe PN com `classification_source:"gramática"`, `grammar_complete:true` — a
  família `08EMCP` JÁ decodifica NAND/RAM certo por posição, mas o token de sufixo `NL2` (LPDDR2)
  caiu no default da gramática (`LPDDR3`, sempre, por design — ver §2). Não é PN sem grammar, é
  gramática incompleta numa sub-decisão que a própria família já documentava como não-automatizável.
  Busquei a string exata e não achei em distribuidor nenhum — mas achei que "AV1" bate com os 3
  primeiros chars de "AV100", geração de sufixo real (Octopart): `08EMCP04-NL2AV100-{C06,C30,C50}`
  (LPDDR2) + irmãs `EL3AV100-{C06,C30U,C50}` (LPDDR3) + irmã de capacidade `08EMCP08-EL3AV100-C50`
  (RAM=1GB). Registrei a string truncada do debug MAIS as 6 formas completas achadas — não assumi
  qual revisão (`C06`/`C30`/`C50`) é a unidade física real, registrei as 3 (specs idênticas entre
  elas, só o código de revisão muda, e revisão não tem campo próprio no schema). `08EMCP08-NL2AV100`
  (par LPDDR2 do RAM=1GB) buscado e NÃO achado — excluído, não adivinhado. Achado lateral não
  perseguido: família `08EMCP` tem ainda MAIS gerações de sufixo (`CV100`/`BT227`/`DT527`/
  `EL2BV100` — esse último com token `EL2` inédito, geração não documentada) — catalogar todas é
  rodada própria, sinalizado em §5, não teve compromisso de perseguir agora. Lição: quando
  `classification_source:"gramática"` + `grammar_complete:true` mas o `tip` da própria família já
  avisa de uma ambiguidade conhecida (aqui: "verificar sufixo NL2/NL3 visualmente"), o caminho é
  known_part pontual pra essa PN exata — nunca editar o decode map da gramática pra "adivinhar"
  o token a partir de regex, porque o próprio texto da família já documenta que isso não é
  confiável por posição sozinha.
- **2026-08-20 — linha `KE4` (eMMC gerenciado) pesquisada a fundo pela 1ª vez; achado principal foi
  um GAP, não uma resposta.** PN físico do debug `KE4CN2L2SA5H2A` chegou com TUDO vazio (nem
  fallback genérico bateu — `chip_type`/`brand`/família todos ""). Busca confirmou que a linha KE4
  é real (RS Components, título "Kingston" + campos estruturados de capacidade/pacote) e achou 6
  known_parts na forma CURTA do PN (`KE4CN[dígito][letra][dígito]A`, 9 chars — 4/8/16GB × 153/169-pin
  BGA). Mas o PN do debug é de uma forma LONGA (`KE4CN2L2…`, 14+ chars) estruturalmente diferente —
  tentei 6+ fontes (Xecor e Brokerforum bloquearam 403; findchips não achou o PN exato; HKin sem
  specs abertas) e nenhuma confirmou capacidade pra essa forma. Não registrei o PN do debug — sem
  fonte confirmada, não tem o que preencher (regra "excluir, não adivinhar" aplicada ao caso mais
  literal possível: nem um known_part parcial dava pra montar). Lição: quando a pesquisa web esgota
  sem confirmar um PN específico mas confirma a MARCA/linha geral (achei 6 irmãs reais, só não a
  que disparou a busca), o known_parts do que FOI confirmado ainda vale a entrega — não é tudo ou
  nada — mas o PN original fica como gap explícito no §5, candidato a leitura física do pacote pelo
  dono (mesma lógica do caso `FH32B08UCT1`: quando a web empaca, bancada resolve). Achado à parte:
  `KE4CN5B6A` tinha "32Gbit" em vez de "GByte" na RS — capacidade genuinamente ambígua (32GB por
  padrão de família, ou 4GB se Gbit for literal), excluído em vez de escolher uma leitura.
- **2026-08-20 (mesmo dia, 2ª rodada) — `KE4CN2L2SA5H2A` resolvido depois que o dono pediu "pode
  confirmar em tier 2".** Primeira rodada tinha desistido cedo demais — Xecor/Brokerforum bloquearam
  (403) e parei de tentar outras fontes tier-2 sem esgotar a lista. Voltei e achei em Win Source
  (via Octopart, confirmado 2x que o PN aparece sozinho na página, sem mistura com outro registro):
  "4GB + 4GB" / "162 Ball Fbga Tsb 19NM". Capacidade = 8GB (2 dies de 4GB empilhados) — e o dígito
  "2" logo após "KE4CN" bate com o MESMO significado da forma curta (onde "2"=4GB, ex. KE4CN2H5A) —
  ou seja, as duas formas de PN desta família COMPARTILHAM a lógica do dígito de capacidade, só a
  forma longa tem campos extra pra empilhamento/revisão que a forma curta (die único) não precisa.
  "Tsb" na descrição do pacote = Toshiba — mesmo padrão de célula-de-terceiro-sob-marca-própria já
  visto em `FH32B08UCT1`/`FH64B08UCT1`. Cross-check serviceemmc.com achou o aparelho de destino
  (Huawei Y221-U22) — mas o GSMArena lista esse aparelho com "4GB" de armazenamento anunciado, não
  8GB; documentei a discrepância em vez de escondê-la (pode ser arredondamento de marketing/reserva
  de sistema, ou variante regional com chip diferente — não decidido). Lição: "não achei em 2-3
  fontes" não é o mesmo que "esgotei tier 2" — antes de declarar gap aberto por falta de fonte, vale
  tentar mais alguns distribuidores (Octopart/Win Source resolveram o que Xecor/Brokerforum/findchips
  não tinham resolvido), especialmente quando o dono pede explicitamente pra insistir num tier.
- **2026-08-20 (mesmo dia, 3ª rodada) — `EMMC64G-TA29` reaplicou a MESMA lição do KE4, logo em
  seguida.** PN físico do dono (`EMMC64GTA29`) era exatamente um dos PN que eu tinha excluído no dia
  anterior (2026-08-19) por "specs não confirmados" — mas só tinha tentado 2 fontes antes de
  desistir. Com o PN físico batendo de novo e a lição fresca do caso KE4 ("não achei em 2-3 fontes
  ≠ esgotei tier 2"), insisti mais e achei rápido: datasheet oficial Kingston (Future Electronics,
  documento único cobrindo os 5 PN da família TB29/TA29 — `EMMC16G-TB29`, `EMMC32G-TB29`,
  `EMMC32G-TA29`, `EMMC64G-TA29`, `EMMC128-TA29`) + Arrow/Avnet/TrustedParts/Octopart confirmando os
  mesmos PN. Aproveitei a mesma rodada pra checar a geração vizinha `TX29` (também excluída ontem) —
  achei em DigiKey/Mouser/Avnet nas 3 capacidades (32/64/128GB). Resultado: 6 known_parts novos no
  arquivo eMMC standalone, 2 gaps do §5 fechados de uma vez. Lição reforçada (2ª vez no mesmo dia):
  quando um PN excluído por "specs não confirmados" volta no debug físico, vale re-tentar a pesquisa
  ANTES de repetir a exclusão — o gap de ontem pode ter sido só pesquisa curta, não ausência real de
  fonte.
- **2026-08-26 — terceiro caso do padrão "família legada": DRAM discreta, PN `D5128EETBPGGBU`.**
  Disparado por PN físico direto do estoque (`known: false`, tudo vazio — nem fallback genérico
  bateu, mesma forma dos casos KE4/FH32B08UCT1). Mesmo padrão de `MCAB`/`EC4B`: o flyer DDR3/3L
  oficial vigente (`MKF_585_DDR3_3L_US.pdf`, também espelhado em `MKF_944_dram_flyer_us.pdf`) lista a
  família `ECMD` no mesmo código de densidade/organização `5128` (`D5128ECMDPGJD`, 4Gb, 512Mx8, DDR3L
  1.35V, 1866Mbps, FBGA-78 — já no known_parts desde a submissão inicial de 17/08) — `EETB` não
  aparece em nenhum flyer atual. Octopart/electronicsdatasheets/harddiskdirect confirmam
  `D5128EETBPGGBU` com specs quase idênticas ao ECMD (4Gb, 512Mx8, DDR3/3L, 1.35V, FBGA-78) mas
  velocidade MENOR (1600Mbps contra 1866/2133 do ECMD — mesmo padrão já visto no EC4B) e **lifecycle
  "Obsolete" explícito, last-time-buy 30/09/2020** — confirma leitura de geração anterior
  descontinuada. Achei também `D5128EETBPGGBU-U` (mesmas specs, catálogo Octopart separado) — sufixo
  "-U" recorrente também na família `ECMD` (`D5128ECMDPGJD-U`), não é exclusividade do legado.
  Busquei irmãs de outra densidade (`D1216EETB…`/`D2516EETB…`/`D2568EETB…`, espelhando os códigos já
  confirmados do `ECMD`) e variante industrial (`-I`) — não achei nenhuma; cluster desta família
  parece ser só essas 2 PN, mesmo padrão do `EC4B`. **Padrão confirmado agora 3×** (`MCAB` 17/08,
  `EC4B` 19/08, `EETB` 26/08): quando Tier-1 vigente não bate mas o código de densidade/organização
  sim, é forte indício de família legada — não de marca errada.
- **2026-08-20 (mesmo dia, 4ª rodada) — `08EMCP08EL3CV100`: mesma família AV100/CV100, mas desta vez
  o subtype da gramática JÁ estava certo por coincidência.** PN físico veio com
  `classification_source:"gramática"`, `grammar_complete:true`, subtype mostrado "LPDDR3" — só que
  aqui o token real do sufixo (`EL3`) TAMBÉM é LPDDR3, então o default da gramática (sempre LPDDR3,
  regra §0.2#5) acertou por coincidência, diferente do caso `08EMCP04NL2AV1` de mais cedo no mesmo
  dia (onde o token era `NL2`/LPDDR2 e a gramática errava). O gap real aqui era só
  `known_exact:false` + `confidence:"estimated"` — faltava known_part confirmado. Geração de sufixo
  "CV100" já estava sinalizada como "não perseguida" desde a entrega AV100 (achado incidental, mesmo
  dia). Pesquisei a fundo: achei `08EMCP08-EL3CV100` (forma base, sem revisão) confirmado em
  Jotrin/Octopart/Apogeeweb E numa fonte mais forte que catálogo de distribuidor — bax.com.ua vende a
  peça usada com leitura REAL do CSD register do chip (ferramenta Z3X Easy Jtag + E-Mate Pro eMMC
  Tool): "1GB ОЗП + 8 GB Флеш пам'яті", "Extended CSD rev 1.7 (MMC 5.0)" — dump de silício, não só
  texto de catálogo. Também achei a revisão `-C50` e a irmã LPDDR2 `08EMCP08-NL2CV100` ("eMCP 8GB
  eMMC5.0 + 8Gb LPDDR2" via ERSA Electronics). Tentei achar o par de RAM=512MB (`08EMCP04-*CV100`) e
  outras revisões (`C06`/`C30`, por analogia à AV100) — não achei em nenhuma fonte, excluídos. Achado
  lateral: a mesma busca revelou MAIS 2 gerações de sufixo nunca sinalizadas antes (`BS100`, `CU100`,
  vistas juntas com `CV100`/`BT227`/`AV100`/`DT227` numa listagem Alibaba, mesmo pacote BGA221) —
  somadas à lista "não perseguido" do §5, fora do escopo desta rodada (mesmo critério já usado pra
  CV100/BT227/DT527/EL2BV100 na entrega AV100).
- **2026-08-26 — eMMC standalone ganha uma geração de sufixo BEM mais antiga: "S100" (PN físico
  `EMMC16GS100`).** Debug de estoque veio 100% vazio (`known:false`, nem fallback bateu). Conferi de
  novo os 2 flyers já usados neste arquivo (`emmc_flyer_us.pdf` vigente e `eMMC_Product_flyer.pdf`
  alternativo) especificamente atrás de "S100" — não está em nenhum dos dois, é geração nova pra
  este chat. Diferente de TB28/TB29/TA29/TX29 (todas relativamente recentes), "S100" tem lifecycle
  "Obsolete" explícito com last-time-buy em **2016-06-01** (Octopart) — descontinuada há quase 10
  anos, a geração mais antiga confirmada nesta linha até agora. Cluster achado (Octopart, Avnet,
  Elnec, Jotrin, TrustedParts, Datasheets360): `EMMC04G-S100`, `EMMC08G-S100`, `EMMC16G-S100`,
  `EMMC32G-S100` — todas pacote 153-ball BGA. Versão eMMC "5.0" confirmada direto só na irmã de 32GB
  (Octopart: "32GB eMMC v5.0" explícito) — apliquei às outras 3 por inferência de família, mesmo
  padrão de transparência já usado nas TX29 de 64/128GB. Tentei achar `EMMC64G-S100`/`EMMC128-S100`
  (completar a progressão) — não achei em nenhuma fonte; a geração parece genuinamente parar em
  32GB, consistente com ser uma geração mais antiga/pequena (capacidades maiores viraram comuns
  depois). Muitas variantes de sufixo de revisão apareceram nas buscas (`-A06U`/`-E06U`/`-R10` no
  16G; `-A08U`/`-B08U`/`-E08U`/`-G08U` no 04G) — não persegui nenhuma, registrei só a forma BASE (a
  mesma que disparou a rodada), mesmo padrão de escopo das entradas anteriores deste arquivo. +4
  known_parts, arquivo vai de 31 pra 35.
- **2026-08-26 (mesmo dia, depois) — linha `KE4` ganha um 3º formato de PN E resolve uma ambiguidade
  antiga de 2026-08-20 (`KE4CN5B6A`).** PN físico do debug `KE44B26BN8GB` veio 100% vazio. Achei a
  forma com separadores, `KE44B-26BN/8GB`, confirmada Kingston via RS Components (Tier-1) + Octopart
  + Elnec + Kynix + veswin.com — **eMMC 4.41 explícito** (JEDEC JESD84-A4411), 169-Pin FBGA, 8GByte.
  ⚠ 2 distribuidores menores (Jotrin, EmbedIc) atribuíam esse mesmo PN à STMicroelectronics —
  divergência isolada contra 5 fontes mais fortes concordando em Kingston; segui a maioria. Achei o
  cluster completo do novo formato `KE44B-[dígito][letra]AN/[cap]GB`: 2GB/153pin, 4GB/169pin,
  8GB/169pin — todas eMMC 4.41 (2 confirmadas direto, 1 por inferência entre as duas). Achado
  relevante de método: o `KE44B-25AN/2GB` tinha o mesmo tipo de inconsistência já visto no
  `KE4CN5B6A` de 20/08 (campo curto "Capacity" da RS dizendo "2Gbit" enquanto o campo "Organisation"
  da MESMA página e o próprio sufixo do PN batem com 2GByte) — dessa vez com Octopart confirmando
  independente "2GB" puro, o que me deu confiança pra tratar como inconsistência de template da RS,
  não spec real. Isso me fez VOLTAR no `KE4CN5B6A` (excluído em 20/08 por essa mesma ambiguidade,
  sem 2ª fonte na hora) — Octopart agora confirma "32G-byte (32GB)" + "32GB eMMC V4.5" explícito,
  resolvendo definitivamente: 32GB, não 4GB. Também achei a irmã `KE4BT5D6A` (32GB) varrendo a mesma
  família KE4BT. +5 known_parts no arquivo já existente (`kingston_emmc_ke4_2026-08-20.yaml`, 7→12),
  1 dos 5 é a resolução do `KE4CN5B6A` que antes era exclusão. Lição durável: quando um distribuidor
  usa unidade "bit" isolada num campo resumido sem bater com um campo estruturado mais granular
  (Organisation) OU o próprio sufixo do PN, vale desconfiar do campo resumido antes de aceitar ou
  excluir — e revisitar exclusões antigas quando uma 2ª fonte aparecer depois.
- **2026-08-26 (mesmo dia, depois) — eMCP "AV100" ganha a forma BASE como known_part próprio; dono
  confirma que forma curta E longa aparecem as DUAS fisicamente.** PN físico do debug
  `08EMCP04NL2AV100` chegou com `known_exact:false`, subtype errado (LPDDR3 em vez de LPDDR2, mesmo
  bug de sempre) — mas desta vez a leitura veio COMPLETA (sem truncar), diferente do
  `08EMCP04NL2AV1` registrado na 1ª rodada (20/08). Dono comentou "tem o que termina no 1 e o que
  termina no 100" — confirmando que os dois textos aparecem de verdade na bancada, não é só uma
  leitura truncada da outra. Pesquisei e achei `08EMCP04-NL2AV100` (forma BASE, sem sufixo de
  revisão) como PN real e distinto em 2 fontes independentes: DigiPart (catálogo estruturado: "eMCP
  8GB eMMC TLC + 4Gb LPDDR2", pacote BGA162) e um teardown de campo real (X/Twitter, desmontagem de
  modem 4G USB) — "eMCP: 08EMCP04-NL2AV100 (8GB eMMC + 512MB LPDDR2)", confirmação de uso real, não
  só catálogo. Tentei achar a irmã LPDDR3 da forma base (`08EMCP04-EL3AV100`) — existe como página
  própria em 2 distribuidores, mas as 2 tentativas de fetch falharam (bloqueio/só metadata) e não
  consegui confirmar specs no texto — não incluí (existência de SKU não é confirmação de spec). A
  forma base `08EMCP08-EL3AV100` que aparecia em busca acabou sendo a MESMA página já usada como
  fonte do `-C50` existente (mesmo ID de produto Worldway) — não duplicada. `08EMCP08-NL2AV100`
  (par RAM=1GB) segue sem fonte, mesma exclusão da 1ª rodada. +1 known_part no arquivo já existente
  (`kingston_emcp_av100_2026-08-20.yaml`, 8→9).

> O inventário de chaves/mapas vive no **`kingston.yaml`** (gramática); os **known_parts**
> confirmados (com a proveniência Tier-1/B2B nas `notes`) vivem no **banco** (Opção 2), submetidos
> via `submit_known_parts`. Tudo que é cross-marca (comandos, convenção, rentabilidade,
> arquitetura) está no **CLAUDE.md** — o único `.md` mantido, e é quem aponta pro contrato de
> autoria do yaml.

---

> **Regra de trabalho:** Claude edita a `kingston.yaml` (e escreve arquivos de submissão de
> known_parts). O usuário roda `load_brands`/`submit_known_parts` (sempre dry-run antes do
> `--commit`) e aprova no admin. **Ponto mais importante:** o mesmo PN mistura duas unidades
> diferentes (NAND=GB direto, RAM=Gbit÷8) — mostrar a conta sempre, e nunca aceitar sufixo
> "parecido" sem fonte exata.
