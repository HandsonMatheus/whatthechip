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
Então a marca contribui **dois** tipos de chip de verdade ao catálogo: o **eMCP** (eMMC + LPDDR,
embarcados/smartphones de entrada — cobertura por GRAMÁTICA no yaml) e a **DRAM discreta
embarcada** (cobertura só por **known_parts** — ver §1/§5, é lista enumerada da própria Kingston,
não regra posicional). `brand.code = KST`. O yaml de gramática hoje tem **5 famílias eMCP reais +
1 fallback genérico** + **3 prefixos de módulo desativados** (`active: false`) — a lista viva está
no yaml; a DRAM discreta não tem (nem precisa de) família própria, ver §5.

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
3. **Dois chips de verdade aqui (desde 2026-08-17): eMCP (gramática) e DRAM discreta embarcada
   (known_parts — regra 9).** eMCP: `chip_type="eMCP"`, `is_emcp=True`, categoria `managed_mcp`.
   DRAM: `chip_type` = geração (`DDR3L`/`DDR4`/`LPDDR4`/`LPDDR4X`). Fonte única da convenção:
   `chips/chip_types.py`. Módulos seguem fora (regra 7).
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
   numérico (`16EMCP…`), da linha Embedded DRAM (`D…`/`B…`/`C…`/`Q…` + código `ECMD`/`AN9`/
   `ANBH`/`MCAB`/`PM…`/`XM…` — regra 9) ou de módulo (`KVR…`/`KF…/…` com capacidade após a
   barra). (Esses NAND
   crus `K9*`/`KF9*` são dead-by-type; na bancada física, NAND cru **TSOP** vai pra caixa **K9** —
   tipo próprio da operação desde 2026-08-14, nada a ver com Kingston.)
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
   nesse chip, não em nenhum flyer atual — tratado como legado, não como erro).
10. **Não confie em distribuidor sozinho para capacidade** (mesmo um B2B rastreável já usado como
    apoio no catálogo atual) — cruze com `kingston.com`/Octopart antes de subir
    `confidence: confirmed`. PN ambíguo (sufixo estranho, capacidade fora da tabela) → **pergunte
    ao dono**, nunca decida sozinho. E **exclua, não adivinhe**: spec ESSENCIAL que não fechar em
    fonte Tier-1 → o PN **sai da submissão** (nunca campo em branco/estimado — regra cross-marca).
11. **Pesquise o CLUSTER inteiro, nunca 1 PN por rodada** (regra PERMANENTE do dono, cobrada 4×):
    cada rodada cobre a família/chave completa — capacidades e sufixos irmãos — mesmo que a chave
    já esteja bem confirmada. O objetivo é **cobertura de PNs**, não provar a regra de novo.
12. **Toda entrega de submissão LISTA os known_parts no chat** — PN + spec + confidence colados na
    mensagem, não só o arquivo (pedido do dono, 2026-07-09).
13. **O comando entregue é sempre o par dry-run + `--commit`, sem `--user`** —
    `submit_known_parts <arquivo>` e `submit_known_parts <arquivo> --commit`, mesmo quando a mesma
    mensagem tem pergunta/pendência (dono, 2026-07-09/10; o `--user` citado no `AUTORIA.md` não
    vai no comando entregue).

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
> Kingston usa **duas** categorias agora: gerenciada/composta (eMCP, via gramática) e DRAM discreta
> (DDR3L/DDR4/LPDDR4/LPDDR4x, via known_parts enumerado — §0.2 regra 9).

| Tipo | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| eMCP (única família de gramática ativa) | `"eMCP"` | geração da RAM (`"LPDDR3"` ou `"LPDDR2"` — nunca as duas juntas) | versão eMMC (`"eMMC 5.0"`/`"eMMC 5.1"`) | `emcp_nand` (GB) + `emcp_ram` (tipo+capacidade) |
| DDR3L / DDR4 (known_parts, sem família) | a geração (`"DDR3L"`/`"DDR4"`) | espelha o `chip_type` | bus width (`"x8"`/`"x16"`) | `density_gbit` = die em Gb (nunca GB) |
| LPDDR4 / LPDDR4x (known_parts, sem família) | a geração (`"LPDDR4"`/`"LPDDR4X"`) | espelha o `chip_type` | `""` | `capacity` = pacote em GB (código Gbit÷8, mostre a conta) |
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

- **eMMC standalone Kingston (linha Embedded, PNs `EMMC…G-…`) — candidato AINDA NÃO PESQUISADO.**
  O kingston.com (Embedded) lista eMMC avulso além do eMCP; se confirmado em Tier-1, decide-se
  entre known_parts enumerados (padrão da regra 9) ou família nova (aí prefixo novo ⇒ PN-âncora
  no golden é obrigatório — não é grandfathered). Até lá, os chips da marca no catálogo são os
  dois da abertura: eMCP + DRAM discreta embarcada.
- **128GB eMCP** — nunca confirmado em nenhuma fonte; 64GB é o teto atual da linha. Se aparecer,
  precisa de PN-âncora + fonte Tier-1/B2B antes de virar família nova.
- **`NL2` (LPDDR2) só confirmado em 4GB/8GB.** Se aparecer numa capacidade maior (16GB+), é
  candidato a exceção real ou a sufixo mal-lido — confirmar fonte antes de aceitar.
- **Módulos (`KVR`/`KF`/`ACR`) seguem desativados por design** — não é backlog pendente, é decisão.
- **DRAM discreta embarcada (§0.2 regra 9) — submissão inicial de 2026-08-17 cobriu os 4 flyers
  oficiais atuais (~30 PN: DDR3L/DDR4/LPDDR4/LPDDR4x).** Ainda por pesquisar: (a) família "MCAB"
  do caso `D1216MCABXGGBS` — só esse PN confirmado, pode ter irmãs (outras capacidades/pacotes) que
  nenhum flyer atual lista, prováveis legado pré-"ECMD"; (b) linha eMMC standalone embarcada
  (PNs `EMMC…G-…`, vista em menções soltas do kingston.com Embedded) — ainda NÃO pesquisada a
  fundo, candidata a outra rodada de known_parts.

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
