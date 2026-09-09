> ⚠️ **DUAS TRILHAS (Opção 2, jul/2026).** A **GRAMÁTICA** da Winbond (famílias + decode maps) mora em
> **`chips/knowledge/winbond.yaml`** (via `load_brands --brand winbond`) — **já existe, mas só como
> arquivo MÍNIMO brand-only** (`name: Winbond`, `code: WBD`, zero famílias — detalhe em §0.1/§6). Os
> **known_parts** (PNs confirmados = autoridade) **não vão no yaml** — vivem no **banco**, submetidos por
> `submit_known_parts` e **aprovados pelo dono** no admin (four-eyes). **Processo obrigatório completo —
> LEIA: `AUTORIA.md`** (índice: `CLAUDE.md §5`).
>
> **Este `.md` é a camada humana** — não reproduz dado (isso vive no yaml, brand-only hoje, e no banco,
> ainda com zero known_parts Winbond).
> Aqui ficam: **convenções, o processo de pesquisa/submissão, anatomia do PN, armadilhas, rentabilidade
> (princípio), fontes, o *porquê*** e ponteiros — mesmo papel do `SK_HYNIX.md` (referência de formato
> pedida pelo dono) e do `ESMT.md` (precedente de marca nova na mesma situação de largada).
>
> ⚠️ **Estado em 2026-09-01 (pós-auditoria): `winbond.yaml` MÍNIMO criado (só o bloco `brand`, zero
> família); zero known_part, zero PN pesquisado.** O yaml existe só para a `Brand` passar a existir
> no banco — sem ela o `submit_known_parts` nem valida em dry-run. Nenhuma família foi criada, e
> isso é decisão, não pendência: ver §6.
> Este arquivo **substitui** uma 1ª versão de 2026-08-05 (mesmo pedido do dono, mesmo processo) — não foi
> copiado dela às cegas: cada convenção abaixo foi reconferida hoje contra o `CLAUDE.md`/`AUTORIA.md`
> **atuais** (que cresceram bastante desde agosto: portão de campo de medida endurecido em 26/08, novos
> achados de tenancy/RLS não relevantes aqui, etc.) e contra o código (`chips/chip_types.py`,
> `chips/models.py`, `chips/knowledge/convention.py`). Reconfirmado hoje, não só herdado: grep em
> `prod.json`/`local.json`/`seed_known_parts.json` → **zero** ocorrências de "winbond"; `ls
> chips/knowledge/` → **sem** `winbond.yaml` NESTE MOMENTO da checagem (mais cedo no mesmo dia, antes do
> arquivo mínimo ser criado pra destravar o `submit_known_parts` — ver parágrafo acima; as 12 marcas com
> gramática até então eram esmt, foresee, gigadevice, hynix, kingston, micron, nanya, piecemakers, rayson,
> samsung, sandisk, toshiba-kioxia — Winbond seria a 13ª, no mesmo estágio que ISSI, que já tem `.md` mas
> também zero yaml); `submissions/`
> sem nenhum arquivo Winbond. **Nada mudou no lado Winbond desde agosto — o que mudou foi o sistema ao
> redor dela**, e é isso que este refresh corrige.

---

# WINBOND.md — Guia Técnico e de Negócio (marca em onboarding)

> Em conflito, o **código + o yaml são a fonte da verdade** (`chips/engine.py`,
> `chips/knowledge/winbond.yaml` — hoje brand-only, zero famílias). Regras gerais do WTC: `CLAUDE.md`.

**Winbond Electronics Corporation** (Taiwan, Hsinchu Science Park, fundada em 1987) é fabricante de
memória e semicondutores — perfil mais **industrial/especialidade** que os "3 grandes" de DRAM
(Samsung/SK Hynix/Micron), mais próximo de ESMT/PieceMakers/GigaDevice. Linhas conhecidas (**fontes no
§7 — isto é orientação de EMPRESA, NÃO dado de PN, e NÃO é usado pelo engine**):

- **NOR Flash serial** (código/boot) — a linha comercial mais conhecida da marca globalmente; um dos
  maiores fornecedores do mundo nesse nicho.
- **NAND Flash raw**, inclusive **MCP empilhado NOR+NAND** (linha "SpiStack").
- **Flash segura** (linha "TrustME") — provável nicho automotivo/segurança, baixa prioridade pra bancada
  de reciclagem de consumo.
- **DRAM móvel especial** — PSRAM e "HyperRAM" (interface de pinos reduzida).
- **DRAM móvel padrão** — LPDDR até LPDDR4X.
- **DRAM de especialidade/industrial** — SDR SDRAM até DDR4 SDRAM.

Em 2008 a Winbond fez spin-off da divisão de lógica/consumo (virou **Nuvoton**) e ficou só com memória.
**Este parágrafo é orientação (fontes: Wikipedia + página de linha de produto de um distribuidor — ver
§7), não dado verificado em Tier-1** — confirmar/expandir com o site oficial (`winbond.com`) e datasheets
na 1ª rodada de pesquisa real; não decide nada sozinho e não é usado pelo engine.

**Contexto de hoje no sistema (estado datado, não é convenção — confirmar se ainda vale antes de assumir):**
a Winbond aparece no `PROMPT_PRECOS.md` como marca **"sem aba própria"** de preço (grupo com Rayson/
PieceMakers/GigaDevice/ESMT/ISSI — usa a tabela genérica `Other Brands`, ou o curinga Nanya se bater
tipo+capacidade, mas Nanya só cobre LPDDR4 e DDR). Isso só diz onde ela cai HOJE na UI de preço — não é
gramática nem substitui pesquisa.

**Achado reconfirmado hoje em `chips/chip_types.py`** (grep direto no arquivo, 2026-09-01 — não só
lembrado da sessão de agosto): os tipos abaixo já existem no vocabulário fechado e valem SEM precisar
decidir nada de novo, caso a pesquisa real confirme que a Winbond traz essas famílias:

| `chip_type` | `category` | `profit_family` | `commercial` |
|---|---|---|---|
| `"NOR Flash"` | `catalog` | `dead` (sempre NÃO RENTÁVEL) | `False` — **sem caixa física** |
| `"NAND Flash"` (raw) | `nand_raw` | `dead` (sempre NÃO RENTÁVEL) | `True` (default) — **TEM caixa**, label `"SLC/MLC/TLC NAND <capacidade>"` |
| `"MCP"` | `catalog` | `dead` (sempre NÃO RENTÁVEL) | `False` — sem caixa; candidato pro "SpiStack" NOR+NAND, **a confirmar** |
| `"SDRAM"` | `dram_legacy` | `dead` (sempre NÃO RENTÁVEL) | `True` (default) — TEM caixa |
| `"SRAM"` | `catalog` | `indeterminado` | `False` — sem caixa |
| `"DDR1"`…`"DDR5"` | `dram_pc` | **`ddr`** (segue limiar de mercado, `ProfitabilityConfig`) | `True` (default) |
| `"LPDDR1"`…`"LPDDR5X"` | `dram_mobile` | **`lpddr`** (segue limiar de mercado) | `True` (default) |

⚠ `commercial` (tem caixa física/é roteado no estoque) e `profit_family` (rentabilidade) são **campos
independentes** do `ChipTypeSpec` — não presuma um a partir do outro (foi o erro corrigido na 1ª versão
deste `.md`, 2026-08-05: `NOR Flash` e `NAND Flash` são os DOIS `dead`, mas só o `NOR Flash` é também
`commercial=False`).

⚠️ **CORREÇÃO 2026-09-01 (auditoria do dono):** `commercial=False` **não é lido por nada em produção.**
`is_commercial`/`COMMERCIAL_TYPES` aparecem só em `chips/chip_types.py` e em `chips/tests_convention.py`
— **zero** consumidores em `estoque/views.py` ou em `pricing/`. Então "sem caixa física" é a INTENÇÃO
declarada do tipo, não um comportamento implementado. O que o gateway faz de verdade (medido rodando
`_compute_destination`, 2026-09-01):

```
NOR Flash  cap='16MB'  → caixa='NOR Flash'       categoria='unknown'  kind='none'   NÃO RENTÁVEL
MCP        cap=''      → caixa='MCP'             categoria='unknown'  kind='none'   NÃO RENTÁVEL
SRAM       cap='8MB'   → caixa='SRAM'            categoria='unknown'  kind='none'   INDETERMINADO
NAND Flash cap='128MB' → caixa='SLC NAND 128MB'  categoria='nand'     kind='nand'   NÃO RENTÁVEL
SDRAM      cap='32MB'  → caixa='SDRAM+0.25G'     categoria='ddr'      kind='sdram'  NÃO RENTÁVEL
```

Ou seja: eles **são** roteados — para uma caixa `unknown` com o nome do tipo. Como o código de caixa F12
é **eterno** (nunca reordena nem se reusa), vale perguntar ao dono se `NOR Flash` é uma gaveta aceitável
**antes** de a marca entrar, não depois. Não é decisão deste chat.

**`"PSRAM"`/`"HyperRAM"` continuam AUSENTES do vocabulário** (reconfirmado hoje — nenhuma entrada em
`CHIP_TYPES`): se a pesquisa real confirmar que aparecem na bancada, criar um `chip_type` novo exige
**handshake de rentabilidade** (`RentabilidadeHandshakeTests`) antes de virar família ativa — decisão
do dono, não deste chat. Ver §5.

Como as linhas mais associadas à marca (NOR Flash/NAND Flash) já resolvem como sucata só pelo TIPO,
sem precisar decodificar capacidade, é bem possível que boa parte do volume real de Winbond na bancada
caia em NÃO RENTÁVEL rápido — mas **isso já é regra vigente do sistema, não uma decisão deste chat**, e
não presumir que "então não vale a pena mapear": o chip ainda entra na triagem/estoque (NAND Flash/SDRAM
TÊM caixa), só não é RENTÁVEL.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro

### 0.1 Onde vive o conhecimento

```
chips/knowledge/winbond.yaml   ← GRAMÁTICA (famílias + decode maps). SÓ isso (Opção 2). EXISTE desde
                                  2026-09-01, mas com ZERO famílias: só o bloco `brand`
                                  (name: Winbond / code: WBD), para destravar a Trilha B.
banco (submit_known_parts→aprovação)   ← known_parts confirmados = autoridade (não no yaml). ZERO
                                  known_parts Winbond hoje (reconfirmado 2026-09-01 por grep nos dumps).
AUTORIA.md / CLAUDE.md §5     ← o processo OBRIGATÓRIO das duas trilhas + convenção + comandos
```

**Duas trilhas** (detalhe em `AUTORIA.md`): **gramática** (família/mapa) → criar/editar o yaml →
`load_brands --brand winbond` (dry-run = portão) → o **dono** roda `--commit`. **known_parts**
(autoridade) → `submit_known_parts` (dry-run) → o **dono** roda `--commit` + **aprova no admin**. ⚠ **Toda
família da Winbond será "nova"** (a marca não tem baseline grandfathered) → **PN-âncora no golden é
OBRIGATÓRIO**, sem exceção (`GoldenObrigatorioTests` falha sem — e falha pra **todo mundo** na suíte, não
só pra este chat). **NÃO tocar sem revisão:** `chips/engine.py`, `estoque/views.py` (globais),
yamls/known_parts de outra marca, mapas globais (`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung).

### 0.2 Regras de ouro — nunca violar

1. **Eu (chat) edito arquivos. O dono roda os comandos que escrevem no banco.** Nunca `load_brands
   --commit` / `submit_known_parts --commit` / `migrate` — meu sandbox é isolado e não alcança o banco
   dele; meu papel é entregar o yaml/arquivo de submissão validado (dry-run passou), nunca gravar.
2. **`load_brands --brand winbond` (dry-run) é o portão** da gramática — valida a convenção, nada é
   gravado. `submit_known_parts <arquivo>` (dry-run) é o portão dos known_parts. Depois do `--commit`, o
   cache recarrega sozinho (`catalog_version`), sem restart.
3. **OPÇÃO 1 — a GERAÇÃO vai no `chip_type`** para toda DRAM discreta que a Winbond fizer (SDR SDRAM,
   DDR–DDR4 — a linha "especialidade"): ex. `chip_type="DDR3"`, nunca `"RAM"`/`"DDR"` genérico (família
   ativa com tipo genérico é **rejeitada** pelo portão). Espelhar no `subtype`. DRAM móvel (LPDDR até
   LPDDR4X) segue a mesma regra dos tipos `LPDDR*` já existentes. **NOR Flash / NAND Flash raw / MCP** já
   têm token próprio (categoria `catalog`/`nand_raw`) — aqui o `chip_type` MANDA e `subtype` é
   **descritivo** (não normaliza geração). **PSRAM/HyperRAM não têm token ainda** — não presumir, não
   inventar um `chip_type` novo sem decisão do dono (handshake, ver §5). Fonte única: `chips/chip_types.py`.
4. **`subtype` = SÓ geração/célula** (1–3 palavras) nas categorias DRAM/gerenciada. ❌ densidade, bus
   width, tensão, "Industrial", "Mobile", qualificador de package. Exceção: categoria **catálogo** (NOR
   Flash, SRAM, MCP, NAND Flash) onde `subtype` é **descritivo livre** (o `chip_type` já manda a
   classificação) — ex. um MCP Winbond real poderia ter `subtype="NOR 8MB + NAND 512MB (SpiStack)"`; não
   confundir as duas regras.
5. **`interface`** = bus width (`x8`/`x16`/`x4`) para DDR/SDRAM discreto lido da posição real do PN;
   vazio para LPDDR/PSRAM/HyperRAM standalone e eMCP/uMCP (se existir). Nunca a geração de RAM no
   `interface`.
6. **⚠️ Campo de medida guarda UMA medida — o portão BLOQUEIA isso desde 2026-08-26** (endurecido depois
   da 1ª versão deste `.md`; `chips/knowledge/convention.py::measure_field_problem`, chamado pelo
   `KnownPart.clean()` **e** pelo `KnownPartSpec` — pego no dry-run, antes de gravar). Os campos e as
   regras exatas (verificado direto no código, `chips/models.py`/`convention.py`, 2026-09-01):
   - **`density_gbit`** (`TextField`, ex. `"4Gb"`) — densidade do **die em Gb**. É o único campo de
     medida em **bit** por definição; NÃO está sujeito ao bloqueio de "mais de uma medida" porque não é
     um dos `MEASURE_FIELDS`.
   - **`density_gb`** (`TextField`, ex. `"512MB"` — o nome do campo confunde, mas o valor é em **byte**)
     — companheiro legível do `density_gbit` pro mesmo die; **um dos 4 `MEASURE_FIELDS`** (junto de
     `capacity`, `emcp_ram`, `emcp_nand`).
   - **Bloqueio 1 — mais de uma medida em `capacity`/`emcp_ram`/`emcp_nand`/`density_gb`**: o engine lê
     com `re.search` (pega a PRIMEIRA), então duas medidas na mesma string fazem a ORDEM DAS PALAVRAS
     escolher a prateleira. Prosa com **UMA** medida só passa (feia, mas inofensiva); campo com número
     "pelado" sem unidade (`"2G"`, `"6"`) também passa (é a forma legítima que o `bless_base` grava pra
     DDR-kind).
   - **Bloqueio 2 — unidade de BIT (`Gb`/`Mb`) em `emcp_ram`/`emcp_nand`**: esses dois são SEMPRE byte de
     pacote; o leitor é case-insensitive, então `"8Gb"` entraria como **8 GB** (erro de 8×). Se a medida
     for em bit, o campo certo é `density_gbit`, nunca `emcp_ram`/`emcp_nand`.
   - **⚠️⚠️ O QUE O PORTÃO *NÃO* PEGA — e é justo onde a Winbond mais escorrega: unidade de BIT em
     `capacity`.** `BYTE_ONLY_FIELDS` são só `emcp_ram`/`emcp_nand`. Medido no código em 2026-09-01:
     ```
     capacity = '1Gb'    →  PASSA no portão (nenhum erro)
     _extract_gib('1Gb') =  1.0 GB           ← o certo seria 0.125 GB
     caixa               = 'SLC NAND 1GB'    ← o certo seria 'SLC NAND 128MB'
     ```
     **A nomenclatura da Winbond é toda em BIT** — `W25Q128` = 128 Mbit = **16 MB**; `W25N01G` = 1 Gbit =
     **128 MB** — então este chat vai ler "128" e "01G" no PN o tempo todo. E `NAND Flash` é
     `commercial=True`, cai em `categoria='nand'` e **TEM gaveta física**: um erro de 8× aqui não é
     cosmético, é chip na prateleira errada — e o código de caixa F12 é **eterno**.
     **A conversão é responsabilidade DESTE CHAT, não do portão.** Tabela para não errar:

     | no PN | bits | `capacity` correto | ❌ o que NÃO escrever |
     |---|---|---|---|
     | `…Q80`  | 8 Mbit   | `"1MB"`   | `"8Mb"` (o engine leria 8 GB) |
     | `…Q16`  | 16 Mbit  | `"2MB"`   | `"16Mb"` |
     | `…Q64`  | 64 Mbit  | `"8MB"`   | `"64Mb"` |
     | `…Q128` | 128 Mbit | `"16MB"`  | `"128Mb"` |
     | `…Q256` | 256 Mbit | `"32MB"`  | `"256Mb"` |
     | `…N01G` | 1 Gbit   | `"128MB"` | `"1Gb"` (leria 1 GB — **8×**) |
     | `…N02G` | 2 Gbit   | `"256MB"` | `"2Gb"` |
     | `…N04G` | 4 Gbit   | `"512MB"` | `"4Gb"` |

     A conta é `bits ÷ 8`. **Nunca** submeter capacidade Winbond sem essa divisão escrita na `notes` — a
     disciplina "mostrar a aritmética" do §2.3 aqui é obrigatória, não recomendada.
   - **Densidade sub-1Gb precisa ser FRACIONÁRIA em `density_gbit`** (achado cross-marca, ESMT DDR2,
     2026-08-20): o parser do engine só bate no sufixo literal `"Gb"` (`_GBIT_RE`) — `"512Mb"` **não**
     contém `"Gb"` como substring e vira densidade invisível (`None`) mesmo com o campo "preenchido",
     silenciosamente. Regra: 128Mb→`"0.125Gb"`, 256Mb→`"0.25Gb"`, 512Mb→`"0.5Gb"` — nunca `"512Mb"`. Vale
     popular `density_gb` junto (`"64MB"`) pra deixar o `dram_density` derivado legível. Relevante aqui
     porque a linha "especialidade" da Winbond (SDR SDRAM legada) é candidata natural a densidade
     sub-1Gb.
7. **Se existir eMCP/uMCP** (a confirmar — o perfil da marca sugere mais NOR/NAND/DRAM standalone do que
   memória gerenciada composta, mas não presumir sem pesquisar): `emcp_ram` = tipo ANTES da capacidade
   (`"LPDDR3 1GB"`, nunca `"1GB LPDDR3"`); `emcp_nand` = só GB (byte — ver regra 6).
8. **Nunca inverta `val_primary`/`val_secondary`** nos decode maps — quando o mapa já existir, siga o
   padrão das linhas dele. Nunca escreva `"por die"` no secondary (o engine já anexa).
   `decode_density_type` e `decode_cap_map` são **mutuamente exclusivos** na mesma família (o portão
   rejeita os dois juntos).
9. **Não confie em distribuidor/IA sem verificar.** Erram Gb/GB, invertem primary/secondary, alucinam
   capacidade. Cruzar sempre com datasheet oficial / Octopart (categorização própria, não a descrição do
   distribuidor dentro dele).
10. **⚠️ Ouro = IDENTIDADE, não as specs derivadas — atestar SEMPRE em Tier-1.** Um `confidence="confirmed"`
    verifica que o PN/laser-marking é real; `capacity`/`subtype`/geração são **derivados** e podem estar
    errados mesmo assim — foi o erro `MT52L=LPDDR4` da Micron (era LPDDR3). **`manual` NÃO é um meio-termo
    "mais conservador" entre `confirmed` e `distributor` — é IGUALMENTE autoritativo sobre a gramática**
    (o engine vence com `confidence ∈ {confirmed, manual}`, ponto). A barra pra usar `manual` sem
    datasheet lido é estreita: **três fontes de engenharia convergentes e independentes**, nomeadas na
    `notes` (ex.: fórum de fabricante + banco de programador de chip + teardown técnico) — citar só o
    número de um datasheet que não abriu conta como **uma fonte não lida**, teto `distributor`. **A
    Winbond não tem nenhum precedente confirmado ainda — toda família é a "primeira vez", redobre o
    cuidado.**
11. **Só a MINHA marca (Winbond).** Não coletar/editar PN, família ou mapa de outra marca; nunca tocar em
    mapa global (`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung); nunca reusar uma chave de posição de outra
    marca "porque parece igual" (causa raiz do bug X6 da Samsung) — **nem entre famílias da própria
    Winbond, nem entre PNs-irmãos da mesma família**: confirmar cada chave com PN âncora próprio antes de
    confiar no default do mapa.
12. **PN ambíguo, tipo-lixo ou módulo → NUNCA decido sozinho.** Paro e pergunto ao dono (via
    `AskUserQuestion`; se a ferramenta falhar, pergunto em texto simples no chat mesmo). Nenhuma
    heurística ("subtype vence", "por analogia com família parecida") substitui a palavra do dono. **E o
    inverso também vale:** ausência de fonte Tier-1/Tier-2 pra uma combinação PN-específica **não prova
    que o PN não existe** — se o dono confirmar fisicamente (foto do chip ou "é físico, existe"), o
    caminho certo é submeter `confidence: manual` (organização inferida pela gramática posicional já
    provada da família, nota explícita sobre a ausência de fonte pública) — **não** "corrigir" pro PN
    documentado mais próximo por conta própria.
13. **Spec essencial (capacidade, interface/versão, tipo) não confirmável em Tier-1 → EXCLUIR o PN da
    submissão inteiramente.** Nunca campo em branco, genérico ou estimado "pra documentar proveniência" —
    **sem exceção, nem pra tipo catálogo/`dead`** (NOR Flash, NAND Flash, MCP, SDRAM): mesmo quando a
    capacidade não muda o veredito de rentabilidade (já é sempre NÃO RENTÁVEL por tipo), ela continua
    OBRIGATÓRIA pra o known_part entrar no banco — "capacidade dispensável porque já é dead" já foi
    corrigido nesse exato raciocínio em outra marca ("NÃO podemos subir PNs sem capacidade no banco de
    dados, NUNCA"). Documentar a tentativa/beco-sem-saída no rodapé "NÃO submetidos". Se um PN acabar
    sendo "MCP legado" com specs vazias por convenção (ex.: um SpiStack sem NAND/RAM decodificável), o
    `confidence` mínimo é `manual` — **nunca `distributor`** nesse caso específico (senão o registro fica
    invisível pro engine mesmo aprovado; achado real na SK Hynix H8AC).
    ⚠️ **CORREÇÃO 2026-09-01: esta regra é DISCIPLINA, não trava — o portão NÃO a aplica.** O
    `KnownPartSpec` declara `capacity: str = ""` e o dry-run aprova um PN sem capacidade sem
    reclamar (conferido em `chips/knowledge/schema.py`). Não há rede aqui: se eu submeter
    incompleto, entra incompleto — a única barreira sou eu.
14. **Escopo é só dado (yaml da Winbond + arquivos de submissão).** Não editar `.py`/testes/infra/scripts
    sem pedido explícito do dono, mesmo que pareça um ajuste pequeno.
15. **Se eu delegar pesquisa a um sub-agente:** proibir explicitamente edição de arquivo no prompt dele —
    já houve incidente de sub-agente editando yaml de marca por engano (revertido).
16. **`known_part` casa por STRING EXATA do `part_number`, sem tirar sufixo** (achado cross-marca,
    2026-08-26: `K4B4G0846BHCH9` não resolve com só `K4B4G0846B` cadastrado — a comparação é exata, sem
    normalização de sufixo). Praticamente todo PN real de bancada vem com sufixo de tensão/pacote/revisão
    — **todo sufixo que eu já tenho fonte pra ele (mesmo que só citado como corroboração do PN base) vira
    sua PRÓPRIA linha de known_part**, com os mesmos specs e uma nota curta apontando pra fonte completa
    do PN base, em vez de só mencionar o sufixo dentro da nota de outro registro.

### 0.3 Hierarquia de fontes (a confirmar/ajustar na prática — ainda sem precedente Winbond)

```
1. Site oficial + datasheet Winbond (winbond.com) → Tier 1
2. Octopart / Nexar — categorização PRÓPRIA do Octopart, nunca a descrição do distribuidor dentro dele → Tier 2
3. Alldatasheet / LCSC / DigiKey com rastreabilidade Winbond → Tier 2
4. Distribuidor B2B rastreável (Preduo, WinSource, Jotrin, ineltek, Macnica…) → só apoio; nunca rebaixa
   um confirmed; nunca decide capacidade sozinho
5. iFixit/GSMArena → chip_type confirmado por inspeção física (se aparecer em device teardown)
6. IA externa → ÚLTIMO RECURSO; verificar SEMPRE contra 1–3
```
Nunca fonte primária: fóruns, distribuidor sem rastreio, catálogos genéricos, eBay, IA sem verificação,
Wikipedia (só serviu de orientação de empresa neste `.md`, nunca de PN/spec).

Regra geral do WTC (`CLAUDE.md §6`): fabricante/datasheet > Octopart/Nexar > distribuidor B2B rastreável >
Preduo > IA > especulação — importadores **nunca** rebaixam um registro `confirmed`/`manual`.

---

## 1. Convenção Canônica de Campos ⚠️ LEIA PRIMEIRO

> **OPÇÃO 1. Fonte única: `chips/chip_types.py` (código).** Contexto geral: `CLAUDE.md §6`. A tabela
> abaixo é a convenção universal do WTC — aplique conforme cada família da Winbond se confirma; **não
> presuma qual categoria domina antes da pesquisa real**, mesmo com a orientação do parágrafo "Contexto"
> lá em cima.

| Tipo | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| DDR1–5 / SDRAM (linha "especialidade") | a geração (`DDR2`, `DDR3`…) ou `"SDRAM"` (legado, sempre NÃO RENTÁVEL) | espelha | bus width (`x8`/`x16`/`x4`) | `density_gbit` (Gb/die) — companheiro legível `density_gb` (MB/die) |
| LPDDR standalone (linha móvel padrão) | a geração (`LPDDR4X`…) | espelha | `""` | `capacity` (pacote, bytes) |
| PSRAM / HyperRAM (linha móvel especial) | **token não existe ainda** — não presumir, ver §5 | — | — | — |
| NOR Flash (código/boot — W25X/W35T/W74M, a confirmar) | `"NOR Flash"` (já existe, `dead`/`commercial=False`) | **descritivo livre** (chip_type manda) | — | conforme o tipo |
| NAND Flash raw (W25N/W35N/W29N, a confirmar) | `"NAND Flash"` (já existe, `dead`/`commercial=True`) | célula se souber (`"SLC NAND"` etc.) senão descritivo | — | `capacity` |
| MCP NOR+NAND empilhado ("SpiStack" W25M, a confirmar) | `"MCP"` (já existe, `dead`/`commercial=False`) | descritivo (ex.: composição) | — | conforme confirmável (regra de ouro #13) |
| eMMC / UFS / eMCP / uMCP (se a Winbond tiver — não confirmado no perfil pesquisado) | conforme o tipo | geração RAM ou vazio | conforme o tipo | `capacity` ou `emcp_*` |

**Regras absolutas** (idênticas em todo o WTC, `CLAUDE.md §6`): `subtype` nas categorias DRAM/gerenciada
nunca carrega densidade/bus width/tensão/qualificador de mercado. `density_gbit` = Gb por die, **único**
campo de medida em bit por definição (fora do bloqueio de "uma medida só" — ver regra de ouro #6);
`density_gb` = o companheiro em byte (MB) do mesmo die, **está** sujeito ao bloqueio. `capacity` = pacote
em bytes, nunca Gbit (exceto a forma "pelada" tipo `"2G"` em família DDR-kind, que é convenção da caixa,
não medida ambígua) — **mas isso é DISCIPLINA, não o portão** (regra de ouro #6, bullet do "que o portão
NÃO pega"): `capacity` não está em `BYTE_ONLY_FIELDS`, o parser (`_CAP_RE`) é case-insensitive e lê
`"Gb"` igual a `"GB"`. `emcp_ram` = `"LPDDR{n} {cap}GB"` (tipo antes) — **nunca** unidade de bit aqui, o
portão bloqueia desde 26/08 (esse campo sim está em `BYTE_ONLY_FIELDS`). `tip`/`notes` = todo o resto
(tensão, velocidade, organização, avisos, proveniência).

**Label da caixa** (mecanismo real, `estoque/views.py::_compute_destination` — **não é `commercial`
quem decide isso**, correção que falta acima): quem decide o FORMATO é `label_kind(chip_type)` batendo —
ou não — num if-chain fixo: `umcp`/`emcp`/`ssd`/`k9`/`ufs`/`emmc`/`gddr`/`lpddr`+`ddr`+`sdram`
(combinados)/`nand`. DDR/SDRAM → `{geração}+{densidade}G` (Gb/die; `capacity` é ignorado de propósito
nesse branch). LPDDR → `{geração}+{capacidade}GB`. eMCP/uMCP → `EMCP{nand}+{ram}`/`UMCP{nand}+{ram}`.
eMMC/UFS → `EMMC{cap}`/`UFS{cap}`. **NAND Flash** (`label_kind="nand"`) → branch real:
`"{gen} {capacidade}"` (ex. `"SLC NAND 128MB"` — bate com a tabela medida na abertura do arquivo). **NOR
Flash/MCP/SRAM (`label_kind="none"`) não batem em nenhum branch acima — caem no fallback
`return chip_type or '?', 'unknown'`: o label é a STRING CRUA do `chip_type`, capacidade E subtype
IGNORADOS** (de novo, exatamente o que a tabela medida no topo do arquivo mostra: `caixa='NOR Flash'`,
`caixa='MCP'`, `caixa='SRAM'`, `categoria='unknown'`). **Eles SÃO roteados** — a triagem e o veredito de
rentabilidade rodam normalmente independente do label ter fórmula própria ou cair no fallback; só o
texto impresso na caixa é que fica genérico. Não presumir `{subtype}{capacity}` pra essas famílias
mesmo que a pesquisa confirme capacidade real — o gatilho é `label_kind`, nunca `commercial`.

---

## 2. Processo de pesquisa e submissão — o COMO

### 2.1 Trilha A — Gramática (família nova ou correção)

1. Confirmar o prefixo/família em fonte Tier-1 (§0.3) — **nunca** criar família por analogia estrutural
   sem fonte que nomeie o prefixo diretamente.
2. **Editar** `chips/knowledge/winbond.yaml` (já existe, brand-only — `name: Winbond`, `code: WBD`
   resolvidos em 2026-09-01, ver §6; não mexer nesse bloco `brand`) — acrescentar a família nova em
   `families` (a gramática posicional: `prefix`, `chip_type`/`subtype`/`interface`, `priority`,
   `pn_length`, `is_emcp`, `active`, `decode_cap_*`/`decode_gen_*`/`decode_density_type`, `suffix_rules`,
   `reasoning` com a fonte) e, se a família usar mapa compartilhado, em `maps` (`[char_key, val_primary,
   val_secondary]`, prefixo de mapa por legibilidade, ex. `WB_DDR_CAP` — a FK `brand` é quem realmente
   separa).
3. Rodar `python manage.py load_brands --brand winbond` (dry-run = portão) — resolver os erros até
   passar.
4. **Família nova → GOLDEN obrigatório:** entregar PN-âncora + saída esperada (tipo/subtipo/capacidade/
   **rentabilidade**) em `_WINBOND_GOLDEN` (`chips/tests.py`). **Mecanismo exato (`chips/tests.py`
   ~linha 810):** `GoldenObrigatorioTests` faz AUTODISCOVERY — varre o módulo procurando qualquer dict a
   nível de topo cujo NOME termine em `_GOLDEN` (`if name.endswith("_GOLDEN") and isinstance(val,
   dict)`); não existe lista/registro manual em lugar nenhum, basta criar `_WINBOND_GOLDEN = {...}`
   seguindo o padrão de `_PMK_GOLDEN`/`_GIGA_GOLDEN`/`_RAY_GOLDEN` (marcas recentes na mesma situação de
   largada) que o teste já enxerga sozinho. `GoldenObrigatorioTests` falha sem isso — e **família magra**
   (sem `decode_cap_map`/`decode_density_type`, bem provável pro NOR/NAND/MCP da Winbond) precisa de
   âncora **mais**, não menos: é onde mora o bug recorrente "INDETERMINADO em vez de NÃO RENTÁVEL" (ver
   §4).
5. **Tipo novo em `chip_types.py`** (só se a Winbond trouxer algo que ainda não existe no vocabulário —
   candidato conhecido: PSRAM/HyperRAM, ver §5) → declarar a regra de rentabilidade junto;
   `RentabilidadeHandshakeTests` falha sem.
6. Rodar a suíte (`python manage.py test chips estoque --settings=core.settings_test`) +
   `characterize_baseline --diff` — só o pretendido deve mudar.
7. Entregar ao dono: diff do yaml + golden + saída dos testes. Ele roda `--commit` local, depois publica
   em prod (`git push` + `load_brands --brand winbond --commit` apontando o `DATABASE_URL` do Render).

### 2.2 Trilha B — Known_parts (autoridade — a que vence a gramática)

1. Pesquisa Tier-1 exaustiva por PN (não presumir por semelhança com PN "parecido").
2. Escrever o arquivo `submissions/winbond_<familia>_<data>.yaml`. **Cuidado com a pegadinha do topo:**
   ```yaml
   brand: Winbond            # ⚠ TEXTO PURO. Nunca o bloco name/code/notes (isso é do yaml de gramática).
   known_parts:
     - part_number: W25Q64JVSSIQ
       chip_type: "NOR Flash"
       subtype: "NOR serial SPI"      # categoria catálogo → subtype é DESCRITIVO
       capacity: "8MB"                # ⚠ 64 Mbit ÷ 8 = 8 MB. NUNCA "64Mb": o portão
                                     #   deixa passar e o engine leria 64 GB (regra #6).
       confidence: confirmed
       notes: "fonte Tier-1 aqui + a conta: 64 Mbit ÷ 8 = 8 MB"
   ```
   ⚠️ O exemplo acima **tem** `capacity` de propósito: a 1ª versão deste `.md` mostrava um known_part sem
   ela, contradizendo a própria regra de ouro #13 — e exemplo é o que se copia. (Corrigido 2026-09-01.)
   Escrever `brand:` como bloco (`name:`/`code:`/`notes:`) na SUBMISSÃO já confundiu esse comando em
   outra marca — o valor vira dict e a busca da marca não casa nada.
3. Validar: `python manage.py submit_known_parts <arquivo>.yaml` (dry-run = portão). Corrigir até passar.
   **O dry-run compara cada PN com o banco por `part_number_norm` e classifica em 5 baldes:** `NOVO`
   (entra normal), `RESUBMETE` (existia em draft/submitted/rejected), `COMPLEMENTO` (PN **já aprovado**
   com campo vazio que a submissão preenche — só aplica com `--fill-empty` no `--commit`), `CONFLITO`
   (aprovado com valor DIFERENTE — nunca aplicado automaticamente, vira `<arquivo>.conflitos.yaml` pro
   dono decidir campo a campo), `IGUAL` (nada a fazer). **Se o dry-run mostrar `COMPLEMENTO`, o comando
   que eu entrego TEM que incluir `--fill-empty`** — senão aqueles PNs são pulados de novo, em silêncio.
4. **Entregar o arquivo validado ao dono** — eu NÃO rodo o `--commit` (sandbox isolado + regra de ouro
   #1). Comando que entrego: `submit_known_parts <arquivo>.yaml --commit` (+ `--fill-empty` se houve
   COMPLEMENTO) — **sem `--user`**, mesmo que o `AUTORIA.md` mencione `--user <id-do-chat>` para
   four-eyes (correção explícita do dono, 2026-07-10: "não coloque esse --user seu usuario nos comandos,
   não é necessário" — vale pra qualquer marca).
5. O dono roda o `--commit` (grava `submitted`, oculto) e **aprova no admin**
   (`/admin/chips/knownpart/`).
6. Só depois de aprovado o PN fica visível/autoritativo no engine.

**⚠ Pré-requisito descoberto no onboarding ESMT (vale pra qualquer marca nova, inclusive Winbond):**
`submit_known_parts.py` levanta erro se a `Brand` não existir no banco — **isso acontece mesmo em
dry-run** (a checagem vem antes do early-return). Ou seja, `load_brands --brand winbond --commit`
(Trilha A) precisa rodar **antes** de qualquer `submit_known_parts` (Trilha B) funcionar, nem que seja só
pra validar em dry-run — mesmo que a Trilha A, nesse ponto, seja só uma família mínima criada pra
existir a `Brand`.

### 2.3 Disciplina de pesquisa (como NÃO tropeçar — lições já pagas em outras marcas)

- **Pesquisar o CLUSTER inteiro, nunca 1 PN por rodada** — mesmo se a chave/família já está bem
  confirmada, o objetivo é cobertura de PNs, não só validar a regra. Regra permanente, reforçada
  repetidamente em outras marcas. **E "a gramática já decodifica certo" NUNCA é motivo pra pesquisar ou
  submeter menos** — o objetivo deste chat é o BANCO de known_parts confirmados; a gramática é só a
  válvula de escape enquanto o banco não chega lá, um problema separado.
- **Mostrar a aritmética Gb→GB sempre** que eu reportar uma capacidade — nunca só declarar "XGB
  confirmado". De preferência 2+ fontes independentes batendo, cada uma com a conta visível.
- **Listar os known_parts da submissão direto no chat** (PN + spec principal + confidence), além de
  entregar o arquivo — o dono confere em paralelo sem abrir o arquivo primeiro.
- **Toda entrega de known_parts vem com o comando pronto** (dry-run já rodado + `--commit`, com
  `--fill-empty` se aplicável), mesmo se ainda houver pergunta/pendência na mesma mensagem.
- **Antes de bulk-submeter (>5-10 PNs de uma família de uma vez), pedir ao dono uma query read-only de
  `part_number_norm`** contra o banco — pega colisão de formatação (mesmo PN, string diferente) E
  cobertura já `approved` por outro canal invisível (ex. um `import_*` de máquina).
- **A lista de "fuzzy suggestions" do debug já são KnownParts `approved`** — pesquisar/resubmeter um PN
  que está lá é redundante. O alvo real é o PN NÃO identificado; pra ampliar o lote, faço forward-lookup
  no prefixo do alvo, não puxo da lista de fuzzy.
- **Todo sufixo de tensão/pacote/revisão que eu já tenho fonte pra ele vira sua PRÓPRIA linha de
  known_part** (regra de ouro #16) — o match é por string EXATA, sem normalização; citar o sufixo só como
  corroboração dentro da nota do PN base deixa esse PN específico sem resolver quando o operador digitar
  ele completo na bancada.
- **Nunca reusar uma chave de posição assumindo que vale o mesmo valor em outra família** (ou até dentro
  da mesma família, em PNs-irmãos diferentes) — confirmar cada chave com PN âncora próprio.
- **`submissions/*.yaml` não vai pro git** — é formulário de uso único; só o `winbond.yaml` (gramática) é
  versionado.

### 2.4 Checklist de handoff (resumo — completo em `AUTORIA.md §6`)

- [ ] Só mexi na Winbond; não toquei em mapa global de outra marca.
- [ ] Nada inventado/estimado; ambíguo → perguntei ao dono; essencial não confirmado → excluí o PN
      (mesmo pra tipo catálogo/dead).
- [ ] Nenhum campo de medida com 2+ medidas ou com unidade de bit em `emcp_ram`/`emcp_nand` — dry-run
      confirmaria isso de qualquer forma, mas vale conferir antes.
- [ ] Todo `density_gbit` sub-1Gb está em FRAÇÃO de Gb (0.125 / 0.25 / 0.5), nunca "NNNMb".
      Rodei o grep abaixo e ele voltou vazio. Não confiei no dry-run: para este campo não há portão.
- [ ] Gramática: `load_brands --brand winbond` (dry-run) passou; família nova → golden entregue.
- [ ] Tipo novo (se houver — ex. PSRAM/HyperRAM) → handshake de rentabilidade passa.
- [ ] Known_parts: cada um com fonte Tier-1 na `notes` (ou 3 fontes de engenharia se `manual` sem
      datasheet); `submit_known_parts` (dry-run) passou; verifiquei balde COMPLEMENTO/CONFLITO; listei os
      PNs no chat; entreguei o arquivo + o comando (`--commit`, `--fill-empty` se aplicável, sem `--user`).
- [ ] Suíte inteira verde + `characterize_baseline --diff` só com o pretendido.
- [ ] Não toquei no banco do dono nem em prod.

---

## 3. Anatomia do PN — como LER um chip Winbond

### 3.1 Mapa de famílias por categoria (orientação — fonte de distribuidor, NÃO oficial, confirmar em Tier-1)

```
W25X / W35T / W74M   → NOR Flash serial (código/boot)                       — [A CONFIRMAR em Tier-1]
W25N / W35N / W29N   → NAND Flash raw                                      — [A CONFIRMAR em Tier-1]
W77Q / W77F          → Flash segura "TrustME" (nicho automotivo/segurança) — [A CONFIRMAR em Tier-1]
W25M                 → MCP empilhado NOR+NAND ("SpiStack")                 — [A CONFIRMAR em Tier-1]
PSRAM / HyperRAM      → DRAM móvel especial (prefixo de PN não confirmado) — [A CONFIRMAR em Tier-1]
LPDDR2 (móvel)        → PREFIXO CONFIRMADO 2026-09-01: W97[8/9/A/B]H = Low Power DDR2 SDRAM
                         ("LPDDR2-S4B" no datasheet oficial), 256Mb/512Mb/1Gb/2Gb — ver
                         [[wtc-winbond-lpddr2-w97xh-mobile-dram]] na memória do projeto.
LPDDR1/3/4/4X/5        → DRAM móvel padrão, demais gerações — prefixo AINDA não confirmado — [A CONFIRMAR em Tier-1]
SDR–DDR4 SDRAM        → CONFIRMADO em Tier-1 (parcial): DDR3 "Specialty DRAM" = W631/632/634
                         (ver [[wtc-winbond-ddr3-w63x-specialty-dram]]); DDR2 "Specialty DRAM" =
                         W9712G/W9725G/W9751G/W971GG/W972GG, "6"=x16/"8"=x8, pacotes
                         KB/NB/SB/SS/KS/JB (ver [[wtc-winbond-ddr2-w97x-specialty-dram]]). SDR
                         SDRAM legado e DDR4 puro ainda [A CONFIRMAR em Tier-1].
```
Fonte: página de linha de produto de um distribuidor (ineltek.com, ver §7) + Wikipedia — **nenhuma
família foi criada na gramática a partir disso**; é só um mapa de "onde procurar" quando um PN real
chegar. Cada prefixo acima precisa da MESMA verificação Tier-1 (datasheet oficial nomeando o prefixo
diretamente) antes de virar família na gramática — LPDDR2/W97xH já tem essa confirmação (datasheet
oficial + distribuidores, known_parts submetidos) mas SEM família/gramática criada ainda, mesma
situação do DDR3 W63x e do DDR2 W97x: known_part existe, `ChipFamily` é decisão do dono. Os demais
prefixos deste mapa continuam não confirmados.

### 3.2 Família confirmada

**[A PREENCHER]** — nenhuma família Winbond tem PN-âncora confirmado em Tier-1 ainda. Esta seção nasce na
1ª rodada de pesquisa real (mesmo padrão do `ESMT.md §3.2`, que documentou a família M15T assim que o
dono passou o 1º PN real).

---

## 4. Armadilhas e Decisões Arquiteturais

**Uma armadilha Winbond-específica JÁ está confirmada** (achado de código + nomenclatura pública da
marca, não depende de PN pesquisado — 1º bullet abaixo); as demais nascem conforme a pesquisa real
avança. Enquanto isso, de olho nas armadilhas **sistêmicas** já provadas em outras marcas (`CLAUDE.md
§7`) — têm boa chance de reaparecer aqui:

- **⚠️ `capacity` aceita unidade de BIT sem avisar — risco Nº1 real da marca** (detalhe completo e
  tabela de conversão na regra de ouro #6, "O QUE O PORTÃO NÃO PEGA"). A nomenclatura pública Winbond
  inteira é em bit (`W25Q128`=128 Mbit, `W25N01G`=1 Gbit), mas nada no portão distingue `"Gb"` de `"GB"`
  especificamente em `capacity` (só `emcp_ram`/`emcp_nand` estão em `BYTE_ONLY_FIELDS`). Toda submissão
  desta marca exige a conta ÷8 explícita na `notes` ANTES de escrever `capacity`, sem exceção.
- **Campo de medida com prosa perigosa** (regra de ouro #6) — o portão bloqueia desde 26/08, mas vale
  escrever limpo desde a 1ª submissão em vez de descobrir isso no dry-run. Especialmente relevante pro
  `subtype` descritivo de NOR/NAND/MCP (categoria catálogo): descrever composição é permitido (ex.
  `"NOR 8MB + NAND 512MB"`), mas isso é `subtype`, não `capacity`/`emcp_*` — não confundir os dois campos.
- **Densidade sub-1Gb sem fração** (regra de ouro #6) — a linha "especialidade" (SDR SDRAM legada) é
  candidata natural a densidades pequenas (64Mb/128Mb/256Mb); escrever `density_gbit` como fração de Gb
  desde o primeiro known_part sub-1Gb, não como "NNNMb".
- `decode_density_type` + `decode_cap_map` juntos na mesma família (mutuamente exclusivos).
- **O `save()` REESCREVE parte do que foi submetido — e isso não é alguém editando o seu dado.** A regra
  4 do `apply_kp_convention` (conserto do lote 40, 2026-07-11) auto-preenche `density_gbit` a partir de
  um `capacity` "pelado" em família DDR-kind. Medido em 2026-09-01:
  ```
  DDR3  capacity='2G'     → density_gbit='' ... vira density_gbit='2Gb'   ⚠ mudou
  DDR3  capacity='256MB'  → density_gbit='' ... continua ''               (só a forma pelada dispara)
  ```
  É fill-only e `"GB"` nunca entra (Gb ≠ GB), mas o registro gravado difere do arquivo submetido —
  saber disso evita abrir um falso alarme de "alguém mexeu no meu known_part". **Precisão que falta
  acima:** "DDR-kind" aqui é `label_kind` ∈ `DENSITY_KINDS = ("ddr", "gddr", "sdram", "rdram")`
  (`chips/knowledge/convention.py`) — **NÃO inclui `lpddr`**. Pra Winbond isso importa: a linha
  "especialidade" SDR–DDR4 SDRAM (`label_kind="sdram"`) está dentro da regra 4 e pode ganhar
  `density_gbit` sozinho; a linha móvel LPDDR (`label_kind="lpddr"`) fica de fora — usa `capacity` de
  verdade (pacote), nunca essa auto-conversão de densidade de die.
- Tipo/geração morta retornando INDETERMINADO em vez de NÃO RENTÁVEL (checar geração/tipo ANTES de exigir
  capacidade) — **especialmente relevante aqui**: NOR Flash/NAND Flash raw/MCP já são `dead` por tipo,
  então qualquer família Winbond desses tipos precisa confirmar que herda esse veredito sem cair em
  INDETERMINADO por falta de capacidade (mesmo padrão já corrigido pra SDRAM/GDDR2/ePoP no passado).
- `subtype` verboso vazando pro label da caixa (mitigado por `canonical_gen`, mas escrever limpo mesmo
  assim no write-time) — **exceto** nas famílias de categoria catálogo (NOR Flash/SRAM/MCP/NAND Flash),
  onde `subtype` descritivo é a regra, não a exceção (§1).
- Mesma chave de posição com valor diferente **dentro da mesma família** (não só entre marcas
  diferentes) — vale checar se há mais de um PN real pra mesma chave antes de confiar no default do mapa.
- `known_part` cujo `chip_type` diverge do `is_emcp` da família não sobrepõe — a capacidade some em
  silêncio (o engine tira o tipo da FAMÍLIA, não do known_part). Só relevante se a Winbond acabar tendo
  eMCP/uMCP misturado com famílias NAND/eMMC puras — improvável pelo perfil, mas checar se aparecer.

---

## 5. Rentabilidade — princípio (os valores NÃO ficam aqui)

**Fonte única: `assess_profitability`** (`chips/engine.py`); os limiares vivem no `ProfitabilityConfig`
(admin, o dono edita). ⚠ **É dado mutável** — muda com o mercado — por isso este doc **não cita valores
nem veredictos por família**.

Regras duráveis (essas não mudam): nunca reimplementar a regra de rentabilidade em outro lugar; `capacity`
sempre em MB/GB, nunca Gbit fora da forma "pelada" de DDR-kind (senão vira INDETERMINADO = bloqueador).

**Específico do perfil Winbond (reconfirmado em `chips/chip_types.py`, 2026-09-01):**
- `"NOR Flash"`, `"NAND Flash"` (raw) e `"MCP"` já são **sempre NÃO RENTÁVEL por tipo**
  (`profit_family="dead"`) — junto de SDRAM/RDRAM/EDO DRAM/OneNAND/ePoP. Esse é o veredito comercial
  (`assess_profitability`) e já vem pronto no código — se a Winbond trouxer essas famílias (perfil
  provável, ver "Contexto" na abertura do arquivo), não precisa (re)decidir. ⚠ **`commercial` NÃO é
  sobre isso** (ver correção na abertura do arquivo e em §1): `NOR Flash`/`MCP` têm `commercial=False`,
  `NAND Flash`/`SDRAM` têm `commercial=True` (default), mas essa flag só afeta um teste de handshake
  (`RentabilidadeHandshakeTests`), nunca o veredito real nem a entrada em estoque. O que de fato muda
  entre eles é o `label_kind` (§1): `NOR Flash`/`MCP` caem no fallback sem label formatado
  (`label_kind="none"` → string crua do `chip_type`, categoria `'unknown'`); `NAND Flash`/`SDRAM` têm
  branch de label real (`"nand"`/`"sdram"`) — mas os QUATRO continuam igualmente `dead` na
  rentabilidade, com ou sem label bonito na caixa.
- `"SRAM"` também já existe (categoria catálogo, `commercial=False`, `profit_family="indeterminado"`) —
  mas **não presumir que PSRAM/HyperRAM devem usar esse token** sem confirmar com o dono; tecnicamente
  são famílias diferentes de SRAM tradicional. ⚠️ **E o custo de errar isso é permanente:** `SRAM` é
  `profit_family="indeterminado"`, então um PSRAM mapeado como SRAM fica **sem veredito para sempre** —
  é exatamente o padrão recorrente do `CLAUDE.md §7` ("INDETERMINADO em vez de NÃO RENTÁVEL"), que já
  custou quatro correções no engine. Melhor parar e perguntar do que "usar o token mais parecido".
- `"PSRAM"`/`"HyperRAM"` **não existem como `chip_type` ainda** (reconfirmado hoje — zero ocorrência em
  `CHIP_TYPES`). Se a pesquisa real confirmar que esses chips aparecem na bancada da eMiner, criar o tipo
  novo em `chip_types.py` exige **declarar a regra de rentabilidade junto**
  (`RentabilidadeHandshakeTests` falha sem) — decisão comercial do dono (é rentável? qual limiar?), não
  algo que este chat decide sozinho. Sinalizar e perguntar antes de propor.
- DDR/LPDDR discretos que a Winbond confirmar (linha "especialidade"/"móvel padrão") seguem as regras já
  existentes de `DDR1`–`DDR5`/`LPDDR1`–`LPDDR5X` (`profit_family="ddr"`/`"lpddr"`, segue limiar de
  mercado no `ProfitabilityConfig`) — nenhum tipo novo necessário só por isso.

*Nota de contexto (não é rentabilidade, é onde a marca cai na UI de preço hoje):* Winbond está no grupo
"sem aba própria" do `PROMPT_PRECOS.md` — usa a tabela genérica de preço (`Other Brands`) ou o curinga
Nanya, não uma aba dedicada. Isso pode mudar; confirmar em `PRECIFICACAO.md` antes de assumir que ainda
vale.

---

## 6. Gaps e Roadmap

- [ ] **Confirmar a hierarquia de fontes real** — `winbond.com` (site oficial, localizar onde hospeda os
  datasheets) ainda não testado nesta sessão; as famílias/prefixos do §3.1 vêm só de distribuidor +
  Wikipedia, precisam de confirmação Tier-1 letra a letra.
- [ ] **Nenhum PN real pesquisado ainda** — a 1ª rodada começa quando o dono passar um PN da bancada ou
  pedir pesquisa de uma família específica (mesmo fluxo do `ESMT.md`: dono deu 1 PN, chat confirmou/
  corrigiu antes de mapear a família).
- [ ] **Decidir prioridade de categoria** — dado o perfil (NOR/NAND/MCP prováveis `dead` por tipo; DRAM
  especialidade/móvel seguem tipos já existentes; PSRAM/HyperRAM exigem tipo novo + handshake) — vale
  perguntar ao dono qual categoria aparece de fato na bancada antes de pesquisar às cegas.
- [ ] **PSRAM/HyperRAM: tipo novo em `chip_types.py`?** — só decidir/propor se a pesquisa confirmar que
  esses chips aparecem fisicamente; não adiantar a decisão.
- [x] **`brand.name`/`brand.code`** — RESOLVIDO 2026-09-01: `chips/knowledge/winbond.yaml` criado com
  `name: Winbond` / `code: WBD` (conferido: não colide com ESMT/FRS/GGD/HYX/KST/MIC/NANYA/PMK/RAY/SAM/
  SDK/TXK) e **ZERO famílias**, de propósito — `load_brands --brand winbond` (dry-run) passa. O arquivo
  existe só para destravar a Trilha B: o `submit_known_parts` exige a `Brand` no banco **já no dry-run**
  (checagem na linha 184; o early-return do dry-run só vem na 285). Sem ele, este chat não conseguiria
  nem VALIDAR um arquivo de submissão. **O dono precisa rodar `load_brands --brand winbond --commit`
  uma vez** para a Brand existir.
- [ ] **Primeira família** — nasce SÓ com PN-âncora Tier-1 e o golden na MESMA entrega. Nenhum prefixo
  do §3.1 foi confirmado; criar família a partir da página de distribuidor violaria a regra 1 da
  Trilha A. E família ativa sem âncora deixa a suíte vermelha **para todos os chats**, não só para este.
- [ ] **Golden test + handshake** — nenhum ainda, porque nenhuma família existe.

---

## 7. Fontes de pesquisa

Ver §0.3 (hierarquia completa, ainda sem precedente testado). Ponto de partida: site oficial e datasheets
Winbond (`winbond.com`), Octopart, Alldatasheet, LCSC, DigiKey. Evitar como fonte de capacidade: qualquer
distribuidor sem rastreio e resumo de IA sem verificação — mesmo cuidado que todas as outras marcas do
WTC.

**Fontes usadas só pra escrever a ORIENTAÇÃO de empresa deste `.md`** (não são Tier-1, não confirmam PN
nenhum — citadas por transparência):
- [Winbond — Wikipedia](https://en.wikipedia.org/wiki/Winbond) — histórico da empresa, sede, spin-off da
  Nuvoton.
- [Winbond – Flash & DRAM Memory (ineltek.com)](https://www.ineltek.com/en/winbond-flash-dram-memory/) —
  página de linha de produto de um distribuidor, usada só pra listar nomes de família (W25X/W25N/W77Q/
  W25M/PSRAM/HyperRAM/SDR–DDR4) como ponto de partida — **não confirma nenhum PN individual**.

---

## 8. Histórico (o *porquê* — durável)

- **2026-08-05 — Onboarding original.** Criado a partir de `CLAUDE.md` (lido inteiro) + `SK_HYNIX.md`
  (referência de formato, pedido explícito do dono) + `AUTORIA.md` + `ESMT.md` (precedente de marca nova
  mais recente) + memória de projeto acumulada. Estado confirmado: zero `winbond.yaml`, zero known_part,
  zero PN pesquisado. Achado em `chips/chip_types.py`: NOR Flash/NAND Flash raw já `dead` por tipo;
  PSRAM/HyperRAM sem token. O dono revisou e corrigiu 2 erros factuais direto no arquivo: (1) eu tinha
  escrito que NOR Flash **e** NAND Flash eram os dois `commercial=False` — errado, são flags
  independentes, só o NOR Flash é `commercial=False` (NAND Flash usa o default `True` da dataclass); (2)
  a tabela de convenção usava `dram_density` (campo DERIVADO pelo engine) onde deveria ser `density_gbit`
  (campo de ESCRITA do `KnownPart`) — erro copiado do próprio `SK_HYNIX.md`, que carrega esse mesmo erro
  na fonte (e já tinha contaminado o `ISSI.md`/`ESMT.md` no mesmo dia).
- **2026-09-01 — Refeito a pedido do dono (este arquivo).** Mesmo pedido, mesmo processo (`CLAUDE.md` +
  `SK_HYNIX.md` como referência) — desta vez reconferido linha a linha contra o código atual, não copiado
  da versão de agosto às cegas. Reconfirmado que **nada mudou do lado Winbond** (zero yaml/known_part/PN,
  via grep fresco nos dumps e em `chips/knowledge/`), mas o **sistema ao redor cresceu**: dobrado pro
  `.md` o portão de campo de medida endurecido em 2026-08-26 (`measure_field_problem`,
  `chips/knowledge/convention.py`) — bloqueia mais de uma medida em `capacity`/`emcp_ram`/`emcp_nand`/
  `density_gb`, e unidade de bit especificamente em `emcp_ram`/`emcp_nand`; documentado pela primeira vez
  aqui que `density_gb` é um campo REAL e distinto de `density_gbit` (byte vs. bit, confirmado em
  `chips/models.py`), não apenas o já conhecido `dram_density` (que continua sendo só o derivado de
  leitura). Também dobradas pro `.md`, com fonte conferida na memória do projeto: densidade sub-1Gb exige
  fração de `Gb` (nunca `"NNNMb"`); `manual` é IGUALMENTE autoritativo que `confirmed` (não é meio-termo
  conservador — barra = 3 fontes de engenharia convergentes); confirmação física do dono sobrepõe
  ausência de fonte Tier-1 (submeter `manual`, nunca "corrigir" por conta própria); `known_part` casa por
  string EXATA do PN, então cada sufixo com fonte vira known_part próprio; os baldes
  NOVO/RESUBMETE/COMPLEMENTO/CONFLITO/IGUAL do `submit_known_parts` (com `--fill-empty` quando há
  COMPLEMENTO); e o reforço de que "capacidade não confirmada" nunca é dispensável, nem pra tipo já
  `dead` por tipo. §3/§4/§6 seguem esqueleto/placeholder — nada de decode/pegadinha Winbond foi inventado
  sem fonte Tier-1; crescem PN a PN nas próximas sessões.

- **2026-09-01 — Auditoria do dono (revisão cruzada por outro chat).** Cada afirmação técnica deste `.md`
  foi conferida contra o código, não contra a memória. **Confirmadas corretas:** os 7 `chip_type` com
  seus `profit_family`/`commercial`; `MEASURE_FIELDS`/`BYTE_ONLY_FIELDS` exatos; `density_gb` (byte) ×
  `density_gbit` (bit) e qual dos dois cai no bloqueio; o `_GBIT_RE` que ignora `"512Mb"`; a
  autodescoberta do `_WINBOND_GOLDEN` (`GoldenObrigatorioTests` varre qualquer dict `*_GOLDEN` do módulo
  — não há lista para registrar); e que o `submit_known_parts` exige a `Brand` já no dry-run.
  **Cinco brechas corrigidas:** (1) o portão **não** barra unidade de BIT em `capacity` — e a Winbond é
  nomeada inteira em bit, então era a falha mais provável da marca e o `.md` levava a crer que o portão
  cobria (regra de ouro #6, com tabela de conversão); (2) `commercial=False` não é lido por nenhum
  consumidor em produção — o `.md` descrevia um comportamento que o código não implementa (corrigido com
  a saída real do gateway); (3) o exemplo de YAML do §2.2 mostrava um known_part **sem** `capacity`,
  contradizendo a própria regra de ouro #13 — e exemplo é o que se copia; (4) a regra #13 é disciplina,
  **não** trava: o `KnownPartSpec` aceita `capacity` vazio e o dry-run não reclama; (5) a regra 4 do
  `apply_kp_convention` reescreve `density_gbit` no save, então o gravado difere do submetido (§4).
  Criado também o `winbond.yaml` mínimo (§6). Nenhuma família — ver a justificativa lá.

- **2026-09-01 — Reconciliação (2ª verificação independente, mesmo dia).** O dono pediu a MIM, em
  paralelo, pra conferir a mesma auditoria linha a linha contra o código antes de aceitar qualquer
  correção — e enquanto eu fazia isso, este arquivo já tinha sido corrigido direto no disco (entrada
  acima). Reverifiquei as 6 correções de novo, do zero, direto no código-fonte (`chips/engine.py`,
  `estoque/views.py`, `chips/knowledge/schema.py`, `chips/knowledge/convention.py`, `chips/tests.py`,
  grep completo de `is_commercial`/`COMMERCIAL_TYPES` no repo) — todas se confirmaram exatas, e a versão
  já no disco estava sólida nelas (a tabela de saída medida do gateway, o risco do código de caixa F12
  eterno em §0 e o alerta de INDETERMINADO permanente pra PSRAM/SRAM em §5 são achados bons que eu não
  tinha). Mas achei mais **duas** contradições internas que a correção focada nas 6 brechas não
  alcançou — nenhuma das duas era um dos 6 pontos da auditoria, mas as duas eram sobre o MESMO tema do
  ponto 2 (o `commercial` não decidir o label) e sobreviveram intocadas em outros dois lugares do
  arquivo, direto CONTRADIZENDO a tabela nova de saída medida logo no topo: (1) **§1 "Label da caixa"**
  ainda descrevia a fórmula `{subtype}{capacity}` "quando `commercial=True`" pra NAND/NOR, e dizia que os
  tipos `commercial=False` "não são roteados no estoque como os outros" — o oposto exato do que a própria
  tabela medida no topo do arquivo mostra (`NOR Flash`/`MCP`/`SRAM` SÃO roteados, só caem no fallback de
  label por `label_kind="none"`, não por `commercial`); reescrevi a seção inteira alinhada à tabela
  medida. (2) **§5** repetia a mesma framing errada (`NOR Flash`/`MCP` "sem caixa" por `commercial=False`)
  — corrigido do mesmo jeito. Também: (3) **§4 dizia "nenhuma armadilha Winbond-específica confirmada
  ainda"**, o que já não era verdade com o achado do `capacity`-em-bit no topo do arquivo — adicionei um
  bullet próprio cross-referenciando a regra de ouro #6. Além dessas 3, mais 4 ajustes menores de
  consistência interna (nenhum dos 6 pontos da auditoria, achados por mim ao reler o arquivo inteiro):
  (4) banner de abertura e a nota "em conflito" abaixo do título ainda diziam `winbond.yaml` "ainda não
  existe"/"quando existir", contradizendo o próprio §0.1/§6; (5) o mesmo banner citava um grep antigo
  ("`ls chips/knowledge/` → sem `winbond.yaml`") sem deixar claro que essa checagem foi ANTES do arquivo
  ser criado no mesmo dia — adicionei o marcador temporal; (6) o passo 2 da Trilha A (§2.1) ainda tratava
  `brand.name`/`brand.code` como "a confirmar"/"ainda não escolhido", quando o §6 já registra os dois
  como resolvidos; (7) a armadilha do `save()`/regra 4 em §4 dizia "família DDR-kind" sem precisar o
  `label_kind` exato — acrescentei `DENSITY_KINDS = ("ddr","gddr","sdram","rdram")` e que `lpddr` fica
  FORA dessa auto-conversão (relevante pra Winbond, que tem linha SDRAM E linha LPDDR); detalhei também o
  mecanismo de autodiscovery do golden (`_GOLDEN` por sufixo de nome) no passo 4 da Trilha A, que antes
  só era mencionado en passant aqui em cima.

> O inventário de chaves/mapas vai viver no **`winbond.yaml`** (arquivo já existe, brand-only — as
> famílias entram quando a pesquisa confirmar a 1ª); os
> **known_parts** confirmados (com a proveniência Tier-1 nas `notes`) vivem no **banco** (Opção 2),
> submetidos via `submit_known_parts`. Tudo que é cross-marca (comandos, convenção, rentabilidade,
> arquitetura) está no **`CLAUDE.md`** — o único `.md` mantido nesse papel, e é quem aponta pro
> `AUTORIA.md`.

---

> **Regra de trabalho:** eu crio/edito o `winbond.yaml`. O dono roda `load_brands --brand winbond`
> (sempre dry-run antes do `--commit`) e o `submit_known_parts` (idem). **Ponto mais importante:** esta
> marca não tem NENHUM precedente confirmado ainda — atestar a IDENTIDADE em Tier-1 antes de qualquer
> decode, nunca extrapolar chave por padrão numérico nem por analogia com outra marca ou família (regra
> de ouro #10).
