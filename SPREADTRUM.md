> ⚠️ **DUAS TRILHAS (Opção 2, jul/2026).** A **GRAMÁTICA** da Spreadtrum iria morar em
> **`chips/knowledge/spreadtrum.yaml`** (via `load_brands --brand spreadtrum`) — **não existe, e este
> documento argumenta que talvez nem deva existir no formato normal** (ver §2). Os **known_parts** (PNs
> confirmados = autoridade) **não vão no yaml** — vivem no **banco**, via `submit_known_parts` +
> aprovação do dono (four-eyes). **Processo obrigatório completo — LEIA: `AUTORIA.md`**
> (índice: `CLAUDE.md §5`).
>
> **Este `.md` é a camada humana** — não reproduz dado mutável (isso vive no yaml e no banco, quando
> existirem). Aqui ficam: **convenções, anatomia do PN, armadilhas, how-to de pesquisa, hierarquia de
> fontes, o *porquê*** e ponteiros — mesmo escopo leve do `SK_HYNIX.md`/`ESMT.md`.
>
> ⚠️ **Estado em 2026-08-17: BRAINSTORM. Nada carregado, nada submetido, nada decidido.**
> Não existe `spreadtrum.yaml`, não existe known_part, não existe golden, não existe marca no banco.
> Este documento é o levantamento que precede a decisão comercial do dono — e essa decisão
> (§6) é **bloqueadora**: sem ela não há triagem, não há caixa, não há preço.

---

# SPREADTRUM.md — Guia Técnico e de Negócio (marca em brainstorm)

> Em conflito, o **código é a fonte da verdade** (`chips/engine.py`, `chips/chip_types.py`).
> Regras gerais do WTC: `CLAUDE.md`. Processo de autoria: `AUTORIA.md`.

**Spreadtrum** (展讯通信, *Zhǎnxùn Tōngxìn*, Xangai, fundada em abril/2001) é uma **fabless de SoC de
celular** — projeta, não fabrica. Foi adquirida pela **Tsinghua Unigroup** em **23/dez/2013**, absorveu a
**RDA Microelectronics** em **jul/2014**, e em **13/junho/2018** a marca combinada foi relançada como
**UNISOC** (紫光展锐, *Zǐguāng Zhǎnruì*).

Isso importa para nós por uma razão só, e é a mais importante deste arquivo:

> ## 🔴 A Spreadtrum/UNISOC NUNCA fabricou memória.
>
> Nenhum PN `SC*`, `T*`, `UMS*`, `UIS*`, `SR*`, `RDA*` é DRAM, NAND, eMMC ou eMCP. O portfólio é
> **SoC de aplicação + baseband, transceiver RF e PMIC**. Classificar qualquer peça desta marca como
> memória é **erro de fato**, não erro de decode.
>
> Consequência direta: **esta é a primeira marca do WTC que não tem uma única peça na tese central do
> negócio** (memória vendida por capacidade). Todas as 10+ marcas existentes são fabricantes de memória.
> A Spreadtrum é uma marca de **tipo catálogo**, e hoje `chip_types.py` a trata assim
> (`"SoC": commercial=False, profit_family="indeterminado"`).
>
> ⚠ Confusão a NÃO fazer: a ex-controladora Tsinghua Unigroup também controlava a **YMTC**, que É
> fabricante de NAND. YMTC é empresa-irmã com marca própria — **nunca marcada UNISOC/Spreadtrum**.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro específicas desta marca

### 0.1 Onde vive o conhecimento

```
chips/knowledge/spreadtrum.yaml   ← NÃO EXISTE. Ver §2 antes de criar — a marca não tem
                                     gramática posicional decodificável.
banco (submit_known_parts→aprovação)  ← known_parts confirmados = a ÚNICA rota viável aqui.
AUTORIA.md / CLAUDE.md §5             ← o processo obrigatório das duas trilhas
chips/chip_types.py                   ← "SoC" já existe: catalog / commercial=False / indeterminado
```

### 0.2 Regras de ouro

1. **Eu (chat) edito arquivos. O dono roda os comandos que escrevem no banco.** Nunca `--commit`,
   nunca `migrate`. Sandbox isolado + regra de ouro #1 (incidente dos 5.900).
2. **Esta marca NÃO TEM DATASHEET PÚBLICO. De nenhuma peça.** O `alldatasheet` devolve *"No Data"* para
   a série SC9830 inteira. A hierarquia de fontes normal do WTC (**datasheet do fabricante = ouro**)
   simplesmente **não se aplica** — ver §5 para a hierarquia substituta.
3. **Nenhuma peça desta marca é memória** (§ acima). Se algo marcado Spreadtrum aparecer classificado
   como DRAM/eMMC/eMCP no sistema, é bug.
4. **PN ambíguo → NUNCA decido sozinho.** Pergunto ao dono. Nesta marca a ambiguidade é a regra, não a
   exceção (§4).
5. **Distribuidor aqui é pior que inútil — é ativamente poluído.** Os agregadores (DigiPart,
   ic-components, veswin, Ariat) inventam campos: fabricante "SC", "Motorola Semiconductor Products",
   package "BGAQFN" (impossível), "869 pins" copiado entre PNs diferentes. Ver §4.6.
6. **Não construa gramática posicional sobre esta marca.** §2 é o argumento completo.

---

## 1. O que estes chips SÃO e o que FAZEM

Um SoC Spreadtrum de celular é **o cérebro completo do aparelho num único encapsulamento**: processador
de aplicação (roda o Android) **+ modem de banda base** (fala com a torre) no mesmo silício. É a peça
que a bancada chinesa chama indistintamente de **CPU** ou **基带 (jīdài, "baseband")** — nesta marca os
dois termos apontam para a mesma peça, porque AP e baseband são integrados.

O que **não** está dentro dele: RAM e armazenamento. Todos os SoCs desta lista expõem interface
**LPDDR + eMMC externa** — a memória mora ao lado, num eMCP separado (peça de **outra** marca:
Samsung `KM*`, SK Hynix, Micron…). Nenhuma fonte documenta PoP (memória empilhada) em nenhum PN desta
família; a única evidência física localizada (Samsung SM-J100H, um aparelho SC7727S) mostra o eMCP
`KMN5W000ZM-B207` como peça **discreta e separada** na placa.

**Segmento:** Android de entrada, 2014–2019. Faixa típica dos aparelhos: 512 MB–1 GB de RAM,
4–8 GB de armazenamento. São os chips de celular barato de mercado emergente (Índia, África, América
Latina, Sudeste Asiático) — Samsung série J, Nokia série C, Alcatel 1, Micromax, Wiko, ZTE Blade,
Tecno/Infinix, tablets Huawei MediaPad.

### 1.1 A tríade Spreadtrum numa placa

Quem colhe chip de placa de celular Spreadtrum vai encontrar tipicamente **3 peças da mesma marca**, e
elas são funcionalmente diferentes:

| Prefixo | O que é | Exemplos confirmados |
|---|---|---|
| `SC` + 4 dígitos | **SoC** (AP + baseband) — a peça grande | SC7731C, SC9830I, SC9832E |
| `SR3xxx` | **Transceiver RF** — BGA pequeno, 4,5 × 4,5 mm, 123 esferas, pitch 0,35 mm | SR3595D, SR3595D1, SR3593A |
| `SC27xx` | **PMIC** (gestão de energia + codec de áudio + carga de bateria num chip) | SC2721G, SC2723G, SC2730, SC2731 |
| `RDA*` | Legado RDA — baseband GSM, Bluetooth+FM, front-end RF | RDA6625, RDA5876, RDA8851 |

⚠ **Note que `SC` cobre SoC E PMIC.** `SC9832E` é SoC; `SC2721G` é PMIC. O prefixo de duas letras não
resolve o tipo — só o número resolve. Qualquer regra futura de triagem precisa olhar o bloco numérico.

---

## 2. 🔴 Anatomia do PN — a descoberta que muda o desenho

### 2.1 A Spreadtrum/UNISOC nunca publicou tabela de decodificação de part number

Ao contrário de Samsung, Micron e SK Hynix — cujos PNs são **frases gramaticais** onde cada posição
carrega um campo (densidade, organização, geração, revisão) — a Spreadtrum trata seus PNs como
**identificadores opacos**. Nenhuma fonte primária, nenhum documento de engenharia, nem o kernel do
Linux (cujos bindings foram escritos por engenheiros `@spreadtrum.com`/`@unisoc.com`), nem a
TechInsights publica um esquema posicional.

**Isso não é um buraco de pesquisa. É uma propriedade da marca.**

### 2.2 A única regra posicional defensável (e ela é fraca)

O **primeiro dígito depois de `SC`** correlaciona com a **era do modem**:

| Faixa | Era | Verificação |
|---|---|---|
| `SC65xx` | 2G GSM/GPRS, feature phone | ✅ sustenta (SC6531 e variantes) |
| `SC68xx` | 2G — mas smartphone Android | ⚠ era 2G sim, feature phone não |
| `SC77xx` | **3G** (WCDMA/HSPA+, sem LTE) | ✅ sustenta forte |
| `SC88xx` | 2G **e** 3G — atravessa a fronteira | ❌ **CONTRAEXEMPLO conhecido** |
| `SC98xx` | **4G LTE** | ✅ sustenta forte |

O padrão posicional mais limpo encontrado em toda a linha: **SC8830** (3G) e **SC9830A** (4G) têm
**CPU, GPU e nó idênticos** (4× Cortex-A7, Mali-400 MP2, 28 nm) — só o modem muda, e o PN muda só o
`8`→`9` na primeira posição, preservando `830`. É elegante, mas é **N=1**. Não vira regra.

### 2.3 Os sufixos NÃO são decodificáveis — e três hipóteses óbvias estão REFUTADAS

| Hipótese intuitiva | Veredito | Prova |
|---|---|---|
| `I` = India / International | ❌ **REFUTADO** | `SC9853I` e `SC9861G-IA` → **I = Intel** (núcleos x86 Airmont) |
| `T` = TD-SCDMA (China Mobile) | ❌ **Sem suporte** | Os TD-SCDMA reais são SC8800G/8810/8825/8830 — nenhum usa sufixo T. O único T documentado (W377T) = *dual-system* |
| `G` = Global / GSM | ❌ **Enfraquecido** | `G` aparece em **PMIC** (SC2721G, SC2723G), onde "mercado global" não faz sentido |
| `C` = China | ❓ Sem nenhuma evidência | SC7731C e SC6531C aparecem em aparelhos globais |

O que se **observa** (padrão, não regra documentada): `A` ≈ respin posterior do mesmo die; `E` ≈ respin
mais integrado/custo otimizado lançado depois (o SC9832E é oficialmente *"the world's most integrated
quad-core LTE chip platform"*); sufixos são **empilháveis** (`SC6531EFM`, `SC6531EFH` provam
composição modular). Nada disso é decodificável com segurança.

### 2.4 ⚠️ Consequência para o WTC: `KnownPart`, nunca `DecodeMap`

> **Recomendação técnica (minha; a decisão é do dono):** se esta marca entrar no sistema, ela entra
> como **tabela de PNs confirmados** (Trilha B, `known_parts`), **não** como família com decode
> posicional (Trilha A). Uma família `prefix: SC` com `decode_cap_pos` seria ficção — não há capacidade
> para decodificar (SoC não tem capacidade) e não há posição que signifique algo.
>
> Se um `spreadtrum.yaml` for criado, o papel dele seria mínimo: registrar prefixos (`SC`, `SR`, `RDA`)
> apontando para `chip_type: SoC` / `PMIC` sem nenhum decode — só para o PN ser **reconhecido** e
> roteado, não decodificado. **Isso precisa ser validado contra o `schema.py` antes de virar plano**:
> uma família sem `decode_*` é aceita pelo portão? Não testei. E o `GoldenObrigatorioTests` vai exigir
> PN-âncora — o que um golden de SoC afirmaria, se não há capacidade nem geração?
>
> **Pergunta aberta ao dono, não decidida aqui.**

### 2.5 Anatomia da marcação a laser (observada na foto do dono, 2026-08-17)

Não achei nenhum teardown ou datasheet documentando o *top marking* desta marca. O que segue é
**observação direta da foto do lote**, não fonte:

```
┌─────────────────────────┐
│   [logotipo em caixa]  ®│  ← linha 1: logo Spreadtrum
│   SPREADTRUM®           │  ← linha 2: nome da marca
│   SC7727SE              │  ← linha 3: O PART NUMBER
│   1791031               │  ← linha 4: lote / data / rastreio
│   ...                   │  ← linha 5: código adicional
└─────────────────────────┘
```

A linha 3 é a única que interessa para identificação. As linhas 4–5 são código de lote/fábrica — **não
decodificáveis** sem tabela interna do fabricante, e **não** devem ser digitadas como PN.

⚠ Na foto do dono a marcação está **no limite da legibilidade** (superfície escura, laser de baixo
contraste). Isso não é um acaso — é a condição normal desta marca em peça recuperada, e é a causa raiz
da pegadinha nº 1 (§4.1).

---

## 3. O que há no lote (leitura de 2026-08-17)

Sete PNs distintos foram lidos pelo dono. **Um deles não existe** e um segundo não foi confirmado
existir. Tudo abaixo é **3G ou 4G Cat 4, 28 nm, Cortex-A7/A53 — a faixa mais barata do mercado, era
2014–2018.**

| PN lido | Existe? | O que é | Modem |
|---|---|---|---|
| `SC7715T` | ⚠️ **NÃO CONFIRMADO** — zero cobertura pública (§4.3) | — | — |
| `SC7727S` | ✅ | **DUAL**-core A7 @1,2 GHz, Mali-400, 28 nm, 2014 | 3G HSPA+ |
| `SC7727SE` | ✅ | **QUAD**-core A7 @1,2 GHz, 28 nm, **PMIC integrado**, mar/2016 | 3G HSPA+ |
| `SC7731C` | ✅ | Quad A7 @1,2 GHz, Mali-400, 28 nm, dual-SIM, 2014 | 3G HSPA+ (WCDMA) |
| `SC9830I` | ✅ | Quad A7 @1,5 GHz, Mali-400, 28 nm, VoLTE, nov/2016 | **4G LTE Cat 4** |
| `SC98301` | ❌ **NÃO EXISTE** — é `SC9830I` mal lido (§4.1) | — | — |
| `SC9832E` | ✅ | Quad **A53** @1,4 GHz (64-bit), **Mali-T820**, 28 nm HPC+, jun/2018 | **4G LTE Cat 4** |

> ⚠️ Esta tabela é **estado datado**, não convenção — vai apodrecer. O dado vivo pertence ao banco
> (`known_parts`), quando e se a marca entrar. Está aqui só porque ainda não há banco.

**Os três marcadores que realmente separam as peças** (úteis na bancada e na negociação):

1. **Contagem de núcleos** separa `SC7727S` (2) de `SC7727SE` (4). É a diferença mais brusca do lote —
   sufixo cosmético, silício diferente.
2. **Faixa numérica** separa 3G (`77xx`) de 4G (`98xx`). É o divisor de valor mais provável: LTE tem
   vida útil maior no parque instalado.
3. **GPU** separa gerações: Mali-400 (Utgard, 2014–16) vs Mali-T820 (Midgard, 2018). O `SC9832E` é o
   único do lote com arquitetura ARMv8 de 64 bits — e o único **ainda listado como produto ativo pela
   UNISOC**.

---

## 4. ☠️ Armadilhas — cada uma custou tempo de pesquisa

### 4.1 A pegadinha nº 1: `1` ↔ `I` ↔ `l` — `SC98301` **não existe**

`SC98301` (terminando em **dígito 1**) não é produto da Spreadtrum. O PN real é **`SC9830I`**
(terminando em **letra I maiúscula**), confirmado pelo **press release da própria Spreadtrum**
(21/11/2016, sobre o tablet Huawei MediaPad), onde a empresa escreve `SC9830i`.

A confusão é **endêmica e trilateral** nesta família:
- `SC9830I` → correto (fabricante)
- `SC98301` → grafia de broker; o DigiPart mantém as **duas páginas**, e elas se listam mutuamente como
  "similar part", **com os mesmos fornecedores e quantidades quase idênticas** — é o mesmo estoque
  catalogado sob duas grafias
- `SC9830l` (**L minúsculo**) → é como a **GSMArena** grava o chipset do Huawei MediaPad T2 7.0

O mesmo ruído gera outros PNs-fantasma: `SC9830TW` (só existe em lista de "similares"), `SC9863A1` (a
PhonesData criou uma **página de chipset inteira** com 18 aparelhos que são todos `SC9863A`). Vendedores
de chip recuperado chegam a enumerar as variantes no próprio título do anúncio: *"5C9832E SC9B32E
SC983ZE SC9832E BGA IC Chip"* — **5↔S, B↔8, Z↔2** no mesmo PN.

> ⚠️ **Mas a normalização `1`→`I` NÃO pode ser regra genérica desta marca.** `SC9853I` é PN legítimo
> (8× Intel Airmont, 14 nm) e `SC9820A` também. A regra segura é **whitelist de PNs conhecidos**, nunca
> regex de substituição. Mesma filosofia do `known_parts` vencendo a gramática.

### 4.2 `SC7727S` ≠ `SC7727SE` — dual vs quad

Duas letras a mais dobram o número de núcleos. `SC7727S` é **dual-core**; `SC7727SE` é **quad-core** e
ainda foi o **primeiro chip Spreadtrum com PMIC integrado ao baseband**. Não são o mesmo silício com
sufixo cosmético, e um não substitui o outro em reparo. Se o operador digitar "SC7727S" para uma peça
`SE`, a peça fica errada no catálogo.

### 4.3 `SC7715T` — não consegui confirmar que existe

Busca dirigida ao PN devolve **sempre** o `SC7715` base. Não aparece em base de specs, nem em listagem
de broker, nem em estêncil de reballing — **ao contrário do `SC7715A`, que aparece nos três**. Duas
leituras possíveis, ambas não verificadas:

- é um `SC7715A` mal lido (`A` desgastado lido como `T`), ou
- o `T` é marcação de lote/região que vazou para a linha do PN

> **Ação:** refotografar essa peça com luz rasante antes de qualquer catalogação. Não submeter.
> (Regra de ouro do WTC: spec essencial não confirmável em Tier-1 → **excluir o PN da submissão
> inteiramente**, nunca campo estimado.)

### 4.4 `SC9830A` vs `SC9830I` — SKUs distintos, specs publicadas idênticas

Ambos existem, ambos têm entrada própria na PhoneDB (ids 654 e 687). **Nenhuma fonte publica uma
diferença** de clock, GPU, cache, modem ou processo entre eles. A diferença observável é de
posicionamento: o `A` foi anunciado em abr/2015 para **smartphones** (Samsung J1/J2/J3, Z2, Z4); o `I`
foi promovido em nov/2016 para **tablets LTE de 7"** da Huawei. Provável bin/variante do mesmo die para
outro segmento — **hipótese, não confirmada**.

⚠ As bases de dispositivos **não são confiáveis** para distinguir A de I: a DeviceBeast lista o mesmo
Galaxy J3 (2016) sob os dois. Só o press release e a PhoneDB tratam os dois com rigor.

### 4.5 O modelo comercial do aparelho não determina o chip

Para o **mesmo** Samsung SM-J120H ("Galaxy J1 2016"), a Spreadtrum diz `SC7727SE` no próprio press
release; a GSMArena e a Wikipedia dizem `SC9830`. O irmão SM-J120F é Exynos 3475 — nem Spreadtrum é.
Houve revisões de hardware / SKUs regionais.

> **Regra de bancada: nunca presuma o PN pelo modelo do aparelho. Leia a serigrafia do chip.**

### 4.6 Dados de encapsulamento: os de distribuidor são lixo — os de BOM da FCC são ouro

Não existe datasheet público desta marca, e por meses o único dado de package em circulação era
lixo de catálogo:
- `"869 pins"` — aparece **copiado** em SC7731G, SC9832A, SC98301, SC9863A. Campo autogerado.
- `"454 pins"` — DeviceBeast, para SC7731C e SC7731G (mesmo valor), linhagem de fonte única.
- `"BGAQFN"` — fisicamente impossível.
- Fabricante declarado `"SC"`, `"SPREADT"`, `"S"`, **`"Motorola Semiconductor Products"`**.

**Fonte substituta descoberta em 2026-08-17 — a lista de materiais anexada aos pedidos de
homologação da FCC.** Fabricantes de celular anexam o BOM completo, com package, dimensão e
pitch de cada componente. É documento regulatório, não catálogo — trate como **Tier-1**:

| Designador | PN | Função | Package (literal do BOM) |
|---|---|---|---|
| U2100 | SC9863A / SC9863A1 | SoC | **FCCSP-774ball, 13,0 × 12,6 × 0,83 mm, pitch 0,4** |
| U0200 | SC2721G | PMIC | **FC BGA-166, 6,2 × 5,8 × 0,85 mm, pitch 0,4** |
| U0600 | SR3595D | RF transceiver | **BGA-123ball, 4,5 × 4,5 × 0,85 mm, pitch 0,35** |
| U0601 | RPM6743-31 | PA LTE multibanda | 4,0 × 6,8 × 0,8 mm |
| U0705 | RTM7916-51 | FEM GSM/GPRS/EDGE | 5,3 × 5,5 × 0,842 mm |
| U502 | eMMC 5.1 32GB | memória (3ª marca) | LFBGA-153, 11,5 × 13,0 × 0,9 mm |

Fontes: FCC-ID **YHLBLUG52L** (doc 6330141) e FCC-ID **2ACCJB118** (doc 4699823) — dois
aparelhos diferentes, linhas idênticas. Corrobora o `SR3595D Device Specification V1.2`.

> **Método reutilizável:** para qualquer SoC desta família sem dado de package, procure um
> aparelho que o use e busque o BOM no `fcc.report` pelo FCC-ID. É a única rota Tier-1 de dado
> mecânico que esta marca tem. ⚠ Ainda **não há** BOM localizado para SC7715/7727/7731/9830.

### 4.7 "SPREADTRUM" na marcação ≠ datador confiável

A marca corporativa virou UNISOC em **13/06/2018**, então marcação "SPREADTRUM" aponta para produção
sob a marca antiga. **Mas:** `SC9832E` e `SC9863A` continuam listados como **produtos correntes** no
site da UNISOC — o mesmo PN pode ter sido fabricado depois de 2018 com marcação UNISOC. O par
PN↔marca não é 1:1, e máscaras/estoque antigos persistem após rebrand. **A data de lote no chip é mais
confiável que o logotipo.**

### 4.8 Um mesmo die pode ter três prefixos

`UIS8581A ≈ SC9863A` e `UIS7862 ≈ UMS512`. Padrão observado: `UMS` = SKU smartphone, `UIS` = mesmo
silício em SKU automotivo/IoT, `SC` = designação legada. E o número **gravado no chip** é o PN interno
(`UMS9230`), **não** o nome comercial (`T616`) que aparece na ficha do aparelho. Qualquer mapa de
reconhecimento futuro precisa das duas colunas.

---

## 4.9 🔴 O 套片 (tàopiàn) — o SoC nunca anda sozinho

**Esta é a informação comercial mais importante deste documento.** Descoberta em 2026-08-17,
a partir da observação do comprador de que os SoCs "têm que ir acompanhados de um chip menor".

### O conceito, na definição do próprio meio chinês

Do fórum de engenharia 一牛网 (16rd), respondendo "o que quer dizer 套片?":

> **"手机芯片一般都是按套片出的，厂商一般会出CPU/基带，射频收发，电源管理，无线连接芯片一组相匹配的，
> 单买一颗也没意义。"**
> *"Chips de celular normalmente saem em 套片. O fabricante lança CPU/baseband, transceiver de RF,
> gerenciamento de energia e chip de conectividade como um grupo casado; **comprar uma peça
> sozinha não faz sentido**."*

A própria Spreadtrum usa o termo em inglês nos press releases: *"Spreadtrum's **bundle chipset**"*.
Cada anúncio de plataforma nomeia o conjunto — não o chip.

### A tabela de pareamento (o que confirmamos)

| SoC | PMIC (SC27xx) | RF (SR3xxx) | Conectividade | Confiança |
|---|---|---|---|---|
| **SC9830I** | **SC2723M** | **SR3593S** | SC2331S | 🟢 **PR oficial** (Galaxy J2 2016 / SM-J210F) |
| **SC7727SE** | *nenhum — PMU INTEGRADA* | **SR3532S** | SC2331S | 🟢 **PR oficial** (Galaxy J1 2016 / SM-J120H) |
| SC9863A | SC2721G | SR3595D / D1 | SC2342B | 🟢 **BOM FCC ×2 + device tree** |
| SC9832E | SC2721G | SR3595D | SC2342B | 🟡 estêncil Amaoe/MaAnt SU3 |
| SC7727S | SC2723S / SC2723E | SR3532S (provável) | — | 🟡 listas de loja de reparo |
| SC7731C | ? *(possivelmente integrada)* | **SR3533G** | — | 🟡 esquemático NTPCB |
| SC7731E | SC2720A | ? | — | 🟠 baixa |
| SC7715 / SC7715A / SC7715T | ? | ? | — | 🔴 **não confirmado** |
| SC9830 / SC9830A / SC9832A | ? | ? | — | 🔴 **não confirmado** |

⚠️ **Pegadinha do SC7727SE:** ele **não tem PMIC discreto** — foi o primeiro Spreadtrum com a
PMU integrada ao baseband (declaração oficial). Isso o torna o **teste discriminante** para
descobrir de qual chip o comprador está falando (§4.9 abaixo).

### Por que precisam andar juntos — o técnico

Um SoC Spreadtrum **não funciona com PMIC genérico nem de outra plataforma**. Quatro razões,
todas de fonte primária:

1. **Barramento proprietário.** O PMIC não fica em I²C — pendura no **ADI bus** (Analog-Digital
   Interface), serial dedicado do SoC. No device tree do próprio fabricante:
   `&adi_bus { pmic@0 { compatible = "sprd,sc2721"; spi-max-frequency = <26000000>; …`.
   **Os offsets de registrador mudam por modelo de PMIC.**
2. **O PMIC não é "só fonte".** O binding oficial do kernel lista os subnós reais:
   `sc27xx-regulator`, `sc27xx-fgu` (fuel gauge), `sc27xx-rtc`, `sc27xx-eic` (GPIOs),
   `sc2721-audio-codec`, `sc27xx-typec`, `sc27xx-poweroff`, `sc27xx-7sreset`, `sc27xx-vibrator`.
   **Trocar só a CPU e manter um PMIC estranho quebra:** rails e sequência de boot, o próprio
   botão de ligar, o áudio, o carregador, o RTC, e os GPIOs que dão enable no LCD e na câmera.
3. **O RF transceiver é o RELÓGIO do sistema.** Do `SR3595D Device Specification V1.2`:
   *"Three sets of 26MHz reference clock outputs"* + clock de 32 kHz. O clock de referência do
   baseband **vem do chip de RF**, não de um cristal ligado ao SoC. Sem o SR3xxx correto, o SoC
   não tem clock.
4. **PMIC e RF são acoplados entre si.** O SC2721G traz *"Temperature sensor ADC for 26M
   oscillator tuning"* — é o PMIC que faz a compensação térmica do oscilador da cadeia de RF.

### 🔴 Consequência operacional — a mais urgente deste documento

> **Se a colheita pegou só o chip grande e descartou os pequenos, o valor do lote foi destruído
> na bancada.** O comprador não quer 400 SoCs soltos: ele quer 套片 — conjuntos casados.
>
> **Ação imediata, antes de qualquer negociação:**
> 1. Verificar se os `SC27xx` (PMIC, ~6 × 6 mm) e `SR3xxx` (RF, ~4,5 × 4,5 mm) foram recolhidos.
> 2. Se ainda houver placas na operação, **começar a colher os pequenos junto do grande**, com
>    a origem registrada (qual SoC saiu da mesma placa).
> 3. Contar por PN. Um conjunto casado vale mais que a soma das peças soltas; peças soltas de
>    um lado sem o par do outro podem não valer nada.

### ⚠️ O que ainda NÃO sabemos — e a pergunta que resolve

A evidência prova o **conceito** (套片), mas **não decide** se o comprador quer o PMIC, o RF, ou
o conjunto inteiro. Ambos são "menores" que o SoC: RF ≈ 12% da área, PMIC ≈ 22%.
**Não presumir — perguntar.** As duas perguntas que desambiguam estão no dossiê do comprador
(`DOSSIE_SPREADTRUM_BUYER_EN.md §7.1`), incluindo o teste do SC7727SE.

---

## 5. How-to: como pesquisar e confirmar um PN desta marca

A hierarquia de fontes padrão do WTC (**datasheet do fabricante = ouro; Octopart = secundário;
distribuidor ≠ Tier-1**) **não se aplica** aqui, porque o topo da pirâmide não existe. Hierarquia
substituta, em ordem:

| Nível | Fonte | Por quê |
|---|---|---|
| **Tier-1** | **Press release da própria Spreadtrum/UNISOC** (PR Newswire, GlobeNewswire) | É a empresa falando. Foi o que resolveu `SC9830I`, `SC7727SE` e `SC7731E` |
| **Tier-1** | **unisoc.com** — página de produto | Oficial. Cobre só o que ainda está ativo (SC9832E, SC9863A) |
| **Tier-1** | **Bindings do kernel Linux** (`kernel.org`, patches `@unisoc.com`) | Escritos por engenheiros da própria empresa. Confirmam PNs internos e tipo de chip (foi assim que se confirmou SC27xx = PMIC) |
| **Tier-2** | TechInsights (die shots), imprensa técnica chinesa (C114, icsmart, EET-China, 16rd) | Análise independente; a imprensa chinesa cobre lançamentos que a ocidental ignora |
| **Tier-3** | chaynikam.info, Notebookcheck, PhoneDB, DeviceBeast, unite4buy | Agregadores. **DeviceBeast e PhoneDB não são independentes entre si** — dois deles concordando pode ser uma fonte só |
| **☠️ Não usar** | DigiPart, ic-components, veswin, Ariat, listagens de eBay/Alibaba | Campos inventados (§4.6) |

**Regras práticas:**
1. **Duas fontes de linhagem diferente**, não duas fontes. DeviceBeast+PhoneDB = uma.
2. **Press release ganha de agregador, sempre** — inclusive contra GSMArena/Wikipedia (§4.5).
3. `phonedb.net` bloqueia acesso automatizado (403) — usar via metadados de busca, não via conteúdo.
4. Não existe datasheet. Parar de procurar depois da 2ª tentativa no alldatasheet.

---

## 6. 🔴 Rentabilidade — a decisão que falta (bloqueadora)

**Estado atual do sistema:** `chips/chip_types.py` declara
`"SoC": ChipTypeSpec("catalog", "none", "indeterminado", commercial=False)`.
Ou seja: **sem caixa física, sem roteamento no estoque, sem veredito de rentabilidade.** Decisão do
dono em 2026-08-17: **fica assim por enquanto.**

O que o levantamento de mercado diz — e é honesto dizer que **não é animador**:

- **Memória é o ativo líquido; SoC não é.** A cobertura de imprensa chinesa sobre recuperação de chips
  descreve LPDDR/UFS como 通用性极强 ("compatibilidade extremamente ampla"), precificados
  **individualmente por capacidade**. O mesmo material **não discute CPU/SoC**. A lógica técnica é a
  razão: memória é peça padronizada e fungível; **SoC é específico de placa e de firmware**.
- **A demanda de reuso concentra-se em chips pós-2018.** Um guia B2B chinês afirma que
  *"chips lançados após 2018 têm maior demanda de recuperação"* — o que coloca SC7731C/SC9830I/SC7727S
  **do lado errado da linha**. (⚠ fonte comercial com características de SEO — indicativo, não apurado.)
- **Rendimento real de lote recondicionado é baixo.** Caso documentado: apenas **40% das peças aptas**,
  60% descartadas, tornando o custo final maior que comprar novo.
- **Reballing é obrigatório, não opcional.** *"You cannot solder a pulled chip onto a new board without
  reballing it first to ensure planarity."* Existem estênceis de reballing dedicados a esta família
  (Amaoe SU3 e U-SCU2 cobrem SC9832E, SC9863A, SC7731C, SC7715A, SC7727S) — o que **prova que existe
  demanda de reparo real** para estes PNs. É o sinal positivo mais concreto que encontrei.

> **NÃO existe nenhum dado de preço confiável para SoC Spreadtrum recuperado.** Nenhuma cotação para
> SC7731C, SC9830I ou SC9832E em estado 拆机 (pulled) foi localizada. Qualquer número que apareça numa
> conversa vem do comprador, não de referência pública — **e isso é uma desvantagem de negociação que
> vale nomear**.

**O princípio do WTC vale igual:** rentabilidade é **market-variable**, mora no código
(`assess_profitability`) + admin (`ProfitabilityConfig`), **nunca neste `.md`**. Zero números aqui, por
convenção.

**Se um dia o dono decidir tornar `SoC` comercial**, o `RentabilidadeHandshakeTests` **vai quebrar** até
que a regra de rentabilidade seja declarada — o sistema força a decisão antes de o chip chegar ao
operador. É o comportamento correto: *sem "é rentável?" não há faixa de preço.*

---

## 7. ⚠️ Compliance — a parte que pode inviabilizar o embarque

Levantamento factual, **não é aconselhamento jurídico**. Verificar com despachante antes de qualquer
decisão operacional.

1. **China proíbe importação de resíduo sólido desde 01/01/2021**, em regime total (notificação
   conjunta MEE + Ministério do Comércio + Alfândega). Lixo eletrônico já era proibido antes disso sob
   a "sétima categoria" (废七类). **Placa sucateada / sucata eletrônica não entra legalmente na China.**
2. **Produto eletromecânico usado (旧机电产品) é regime SEPARADO** e a definição inclui explicitamente
   *"peças e componentes"*. Três faixas: proibido (só com consentimento MOFCOM), restrito (licença de
   importação), licença automática. Pode exigir inspeção pré-embarque.
3. **A linha divisória é a classificação, e ela não é escolha do exportador.** Se a carga for
   classificada como **resíduo** → proibida. Se for classificada como **peça eletromecânica usada** →
   regime de licenciamento, possivelmente viável.
4. **Convenção de Basileia mudou em 01/01/2025.** As emendas de e-waste tornam **TODOS** os movimentos
   transfronteiriços de resíduo eletrônico sujeitos ao procedimento de **consentimento prévio
   informado (PIC)** — inclusive o não-perigoso, porque a entrada B1110 (que permitia circulação sem
   controle) **foi excluída**. Texto da própria convenção: *"Used equipment is waste in a country if it
   is defined as or considered to be waste under the provisions of that country's national
   legislation"* — **não existe resposta universal; vale o enquadramento do país importador.**
5. **Não verificado:** status de Paraguai e China como Partes da Basileia, requisitos bilaterais, e o
   código HS aplicável a CI recuperado solto. **Precisa de checagem antes de embarcar.**

---

## 8. O que NÃO fazer

- ❌ Classificar qualquer peça Spreadtrum/UNISOC como memória.
- ❌ Criar família com `decode_cap_pos`/`decode_gen_pos` para esta marca (§2.4).
- ❌ Aplicar regex `1`→`I` genérico nos PNs (quebra `SC9853I`).
- ❌ Usar contagem de pinos/package de distribuidor (§4.6).
- ❌ Presumir o PN pelo modelo do aparelho (§4.5).
- ❌ Submeter `SC7715T` ou `SC98301` — um não foi confirmado, o outro não existe.
- ❌ Digitar linha de lote (`1791031`) como se fosse PN.
- ❌ Tratar "SPREADTRUM" na marcação como datador (§4.7).

---

## 9. Perguntas abertas para o dono

1. **`SoC` vira tipo comercial?** Hoje é `commercial=False` → não tem caixa nem roteamento. Sem essa
   decisão não há triagem operacional possível. *(Respondida em 2026-08-17: fica catálogo por enquanto.)*
2. **Se virar comercial: preço por peça, por PN, ou lote fechado?** SoC não tem capacidade — a régua
   ¥/GB do resto do sistema não se aplica. O paralelo mais próximo no sistema é o **K9** (tipo plano,
   ¥ fixo/unidade, sem marca nem capacidade) — vale considerar o mesmo desenho.
3. **A marca entra como yaml de reconhecimento sem decode, ou só como known_parts?** (§2.4 — precisa
   validar contra `schema.py` e `GoldenObrigatorioTests` antes de virar plano.)
4. **Os 7 PNs são o inventário completo ou uma amostra?** "Centenas de chips" com 7 PNs distintos
   sugere que falta contagem por PN — que é exatamente o que o comprador vai pedir primeiro (§ dossiê).
5. **Há PMICs (`SC27xx`) e transceivers RF (`SR3xxx`) no mesmo lote?** Se a colheita foi por placa, é
   provável que sim, e eles são peças diferentes com mercado diferente.

---

## 10. Fontes (as que resistiram à verificação)

**Tier-1 — a própria empresa:**
- Press release SC7715 (27/01/2014) · SC7727SE / Galaxy J1 SM-J120H (22/03/2016) · **SC9830i / tablet
  Huawei (21/11/2016)** · SC9832E ("most integrated quad-core LTE") · SC7731E / Mobicel (10/07/2018) ·
  SC8800G (40 nm TD-HSPA) — todos via PR Newswire
- Rebrand UNISOC (13/06/2018) · aquisição Spreadtrum pela Tsinghua Unigroup (23/12/2013) · aquisição
  RDA (18/07/2014)
- unisoc.com — páginas de produto SC9832E, SC9863A, linha T/W/V/A/UIS
- kernel.org — `sprd,sc27xx-pmic.txt` (PMIC), `sprd.yaml` (SoC bindings); patches `@unisoc.com`
- SEC 6-K Spreadtrum Communications (famílias SC6600/SC6800/SC8800)

**Tier-2 — análise independente:**
- TechInsights (SR3593A, SR3595, SR3595A) · C114 · icsmart · EET-China · bbs.16rd.com (tabela oficial de
  suporte a memória: SC9832E e SC9863A suportam eMCP; uMCP/UFS não)
- Wikipedia: UNISOC · List of UNISOC processors · Yangtze Memory Technologies · China's waste import ban
- MEE (Ministério de Ecologia e Meio Ambiente da China) — proibição de resíduo sólido 01/01/2021
- Convenção de Basileia — FAQ das emendas de e-waste em vigor 01/01/2025

**Tier-3 — agregadores (⚠ DeviceBeast e PhoneDB compartilham linhagem):**
- chaynikam.info · Notebookcheck · DeviceBeast · PhonesData · PhoneMore · unite4buy · Kimovil · GSMArena

**☠️ Consultadas e descartadas:** DigiPart, ic-components, veswin, Ariat-Tech, listagens eBay/Alibaba
(§4.6). Grokipedia (erra as datas de aquisição verificáveis contra press release primário).

---

## 11. Ponteiros

- **Processo obrigatório de autoria:** `AUTORIA.md` (duas trilhas, portão, golden, handshake, four-eyes)
- **Índice de comandos e regras de ouro:** `CLAUDE.md` §2, §5, §6
- **Vocabulário de tipos:** `chips/chip_types.py` — `"SoC"` já existe (catalog/indeterminado/não-comercial)
- **Portão da gramática:** `chips/knowledge/schema.py`
- **Precedente de tipo plano sem capacidade:** o **K9** (NAND cru em TSOP, ¥ fixo/unidade) — ver
  `PRECIFICACAO.md §12.22`. É o desenho mais próximo do que um SoC precisaria.
- **Dossiê em inglês para o comprador:** `DOSSIE_SPREADTRUM_BUYER_EN.md`
