> ⚠️ **DUAS TRILHAS (Opção 2, jul/2026).** A **GRAMÁTICA** da Winbond (famílias + decode maps) vai morar em
> **`chips/knowledge/winbond.yaml`** (via `load_brands --brand winbond`) — **ainda não existe** (marca em
> onboarding, zero pesquisa Tier-1 feita). Os **known_parts** (PNs confirmados = autoridade) **não vão no
> yaml** — vivem no **banco**, submetidos por `submit_known_parts` e **aprovados pelo dono** no admin
> (four-eyes). **Processo obrigatório completo — LEIA: `AUTORIA.md`** (índice: `CLAUDE.md §5`).
>
> **Este `.md` é a camada humana** — não reproduz dado (isso vive no yaml e no banco, quando existirem).
> Aqui ficam: **convenções, o processo de pesquisa/submissão, anatomia do PN, armadilhas, rentabilidade
> (princípio), fontes, o *porquê*** e ponteiros — igual ao `SK_HYNIX.md` (referência de formato pedida
> pelo dono) e ao `ESMT.md` (precedente mais recente de marca nova, mesma situação de largada).
>
> ⚠️ **Estado em 2026-08-05: onboarding puro — zero yaml, zero known_part, zero PN pesquisado ainda.**
> Nenhuma família/decodificação foi criada. Confirmado por grep em `prod.json`/`local.json`/
> `seed_known_parts.json` (dumps do catálogo): **nenhuma ocorrência de "winbond"** — a marca não tem
> nenhum known_part no banco/dump hoje. `chips/knowledge/` também não tem `winbond.yaml` (12 marcas hoje:
> esmt, foresee, gigadevice, hynix, kingston, micron, nanya, piecemakers, rayson, samsung, sandisk,
> toshiba-kioxia — Winbond seria a 13ª). Este `.md` nasce ANTES da pesquisa, pra pesquisa começar
> disciplinada.

---

# WINBOND.md — Guia Técnico e de Negócio (marca em onboarding)

> Em conflito, o **código + o yaml são a fonte da verdade** (`chips/engine.py`,
> `chips/knowledge/winbond.yaml` quando existir). Regras gerais do WTC: `CLAUDE.md`.

**Winbond Electronics Corporation** (Taiwan, Hsinchu Science Park, fundada em 1987) é fabricante de
memória e semicondutores — histórico mais **industrial/especialidade** que os "3 grandes" de DRAM
(Samsung/SK Hynix/Micron), perfil mais próximo de ESMT/PieceMakers/GigaDevice. Linhas conhecidas (**ver
fontes no §7 — isto é orientação de empresa, NÃO dado de PN, e NÃO é usado pelo engine**):

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
a Winbond já aparece no `PROMPT_PRECOS.md` como marca **"sem aba própria"** de preço (grupo com Rayson/
PieceMakers/GigaDevice/ESMT/ISSI — usa a tabela genérica `Other Brands`, ou o curinga Nanya se bater
tipo+capacidade, mas Nanya só cobre LPDDR4 e DDR). Isso só diz onde ela cai HOJE na UI de preço — não é
gramática nem substitui pesquisa.

**Achado direto no código, relevante pro perfil da marca (`chips/chip_types.py`, lido 2026-08-05):** os
tipos `"NOR Flash"` e `"NAND Flash"` (raw) **já existem no vocabulário e já são sempre NÃO RENTÁVEL por
tipo** (`profit_family="dead"`) — junto de RDRAM/EDO DRAM/MCP/OneNAND/ePoP, também `dead`. ⚠ Cuidado com o
`commercial`: `NOR Flash` é `catalog`/`commercial=False` (sem caixa física), mas `NAND Flash` é
`nand_raw`/`commercial=True` (TEM caixa — `"SLC NAND 512MB"` — só que continua sucata por tipo); SDRAM idem
(`dead` porém `commercial=True`). Como essas são as linhas mais associadas à marca, é bem possível que boa parte do volume real de
Winbond na bancada já resolva como sucata só pelo TIPO, sem precisar decodificar capacidade — mas **isso
já é regra vigente do sistema, não uma decisão deste chat**; não presumir que "então não vale a pena
mapear" sem perguntar ao dono (o chip ainda entra na triagem/estoque, só não é RENTÁVEL). Já `"SRAM"`
também existe (categoria catálogo, `commercial=False`, `profit_family="indeterminado"`), mas **não está
confirmado que PSRAM/HyperRAM devem usar esse token** — tecnicamente são famílias diferentes da SRAM
tradicional. `"PSRAM"`/`"HyperRAM"` como tokens próprios **não existem ainda** em `chip_types.py`: se a
pesquisa real confirmar que esses chips aparecem na bancada, criar um `chip_type` novo exige o
**handshake de rentabilidade** (`RentabilidadeHandshakeTests`, `AUTORIA.md §3.4`) antes de virar família
ativa — decisão do dono, não deste chat.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro

### 0.1 Onde vive o conhecimento

```
chips/knowledge/winbond.yaml   ← GRAMÁTICA (famílias + decode maps). SÓ isso (Opção 2). AINDA NÃO EXISTE
                                  — zero família criada, zero pesquisa Tier-1 feita.
banco (submit_known_parts→aprovação)   ← known_parts confirmados = autoridade (não no yaml). ZERO
                                  known_parts Winbond hoje (confirmado por grep nos dumps do catálogo).
AUTORIA.md / CLAUDE.md §5     ← o processo OBRIGATÓRIO das duas trilhas + convenção + comandos
```

**Duas trilhas** (detalhe em `AUTORIA.md`): **gramática** (família/mapa) → criar/editar o yaml →
`load_brands --brand winbond` (dry-run = portão) → o **dono** roda `--commit`. **known_parts**
(autoridade) → `submit_known_parts` (dry-run) → o **dono** roda `--commit` + **aprova no admin**. ⚠ **Toda
família da Winbond será "nova"** (a marca não tem baseline grandfathered) → **PN-âncora no golden é
OBRIGATÓRIO**, sem exceção (`GoldenObrigatorioTests` falha sem). **NÃO tocar sem revisão:**
`chips/engine.py`, `estoque/views.py` (globais), yamls/known_parts de outra marca, mapas globais
(`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung).

### 0.2 Regras de ouro — nunca violar

1. **Eu (chat) edito arquivos. O dono roda os comandos que escrevem no banco.** Nunca `load_brands
   --commit` / `submit_known_parts --commit` / `migrate` — meu sandbox é isolado e não alcança o banco
   dele; meu papel é entregar o yaml/arquivo de submissão validado (dry-run passou), nunca gravar.
2. **`load_brands --brand winbond` (dry-run) é o portão** da gramática — valida a convenção, nada é
   gravado. `submit_known_parts <arquivo>` (dry-run) é o portão dos known_parts. Depois do `--commit`, o
   cache recarrega sozinho (`catalog_version`), sem restart.
3. **OPÇÃO 1 — a GERAÇÃO vai no `chip_type`** para toda DRAM discreta que a Winbond fizer (SDR SDRAM,
   DDR–DDR4 — a linha "especialidade" já mapeada por fonte de orientação): ex. `chip_type="DDR3"`, nunca
   `"RAM"`/`"DDR"` genérico (família ativa com tipo genérico é **rejeitada** pelo portão). Espelhar no
   `subtype`. DRAM móvel (LPDDR até LPDDR4X) segue a mesma regra dos tipos `LPDDR*` já existentes.
   **NOR Flash / NAND Flash raw** já têm token próprio (`chip_type="NOR Flash"`/`"NAND Flash"`, categoria
   `catalog`/`nand_raw`) — aqui o `chip_type` MANDA e `subtype` é **descritivo** (não normaliza geração).
   **PSRAM/HyperRAM não têm token ainda** — não presumir, não inventar um chip_type novo sem decisão do
   dono (regra de ouro #11 + handshake, ver §5). Fonte única: `chips/chip_types.py`.
4. **`subtype` = SÓ geração/célula** (1–3 palavras) nas categorias DRAM/gerenciada. ❌ densidade, bus
   width, tensão, "Industrial", "Mobile", qualificador de package. Exceção: categoria **catálogo** (NOR
   Flash, SRAM, MCP) onde `subtype` é **descritivo livre** (o `chip_type` já manda a classificação) — não
   confundir as duas regras.
5. **`interface`** = bus width (`x8`/`x16`/`x4`) para DDR/SDRAM discreto lido da posição real do PN;
   vazio para LPDDR/PSRAM/HyperRAM standalone e eMCP/uMCP (se existir). Nunca a geração de RAM no
   `interface`.
6. **Se existir eMCP/uMCP** (a confirmar — o perfil da marca sugere mais NOR/NAND/DRAM standalone do que
   memória gerenciada composta, mas não presumir sem pesquisar): `emcp_ram` = tipo ANTES da capacidade
   (`"LPDDR3 1GB"`, nunca `"1GB LPDDR3"`); `emcp_nand` = só GB.
7. **Nunca inverta `val_primary`/`val_secondary`** nos decode maps — quando o mapa já existir, siga o
   padrão das linhas dele. Nunca escreva `"por die"` no secondary (o engine já anexa).
   `decode_density_type` e `decode_cap_map` são **mutuamente exclusivos** na mesma família (o portão
   rejeita os dois juntos).
8. **Não confie em distribuidor/IA sem verificar.** Erram Gb/GB, invertem primary/secondary, alucinam
   capacidade. Cruzar sempre com datasheet oficial / Octopart (categorização própria, não a descrição do
   distribuidor dentro dele).
9. **⚠️ Ouro = IDENTIDADE, não as specs derivadas — atestar SEMPRE em Tier-1.** Um `confidence="confirmed"`
   verifica que o PN/laser-marking é real; `capacity`/`subtype`/geração são **derivados** e podem estar
   errados mesmo assim — foi o erro `MT52L=LPDDR4` da Micron (era LPDDR3). **A Winbond não tem nenhum
   precedente confirmado ainda — toda família é a "primeira vez", redobre o cuidado.**
10. **Só a MINHA marca (Winbond).** Não coletar/editar PN, família ou mapa de outra marca; nunca tocar em
    mapa global (`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung); nunca reusar uma chave de posição de outra
    marca "porque parece igual" (foi a causa raiz do bug X6 da Samsung) — **nem entre famílias da própria
    Winbond**: achado recorrente em outras marcas é a mesma chave de 2 chars significando densidades
    diferentes DENTRO da mesma família, numa posição que a gramática ainda não decodifica — sempre checar
    se há mais de um PN real confirmado pra mesma chave antes de confiar no default do mapa.
11. **PN ambíguo, tipo-lixo ou módulo → NUNCA decido sozinho.** Paro e pergunto ao dono (via
    `AskUserQuestion`; se a ferramenta falhar, pergunto em texto simples no chat mesmo — fallback já
    usado neste projeto). Nenhuma heurística ("subtype vence", "por analogia com família parecida")
    substitui a palavra do dono sobre o que a peça realmente é.
12. **Spec essencial (capacidade, interface/versão, tipo) não confirmável em Tier-1 → EXCLUIR o PN da
    submissão inteiramente.** Nunca campo em branco, genérico ou estimado "pra documentar proveniência" —
    regra sem exceção, mesmo para tipo catálogo (NOR Flash = `dead`, SRAM = `indeterminado` — ver §5) onde a capacidade não muda o
    veredito de rentabilidade. Documentar a tentativa/beco-sem-saída no rodapé "NÃO submetidos". Se um
    PN acabar sendo "MCP legado" com specs vazias por convenção (ex.: um SpiStack sem NAND/RAM
    decodificável), o `confidence` mínimo é `manual` — **nunca `distributor`** nesse caso específico
    (senão o registro fica invisível pro engine mesmo aprovado; achado real na SK Hynix H8AC).
13. **Escopo é só dado (yaml da Winbond + arquivos de submissão).** Não editar `.py`/testes/infra/scripts
    sem pedido explícito do dono, mesmo que pareça um ajuste pequeno.
14. **Se eu delegar pesquisa a um sub-agente:** proibir explicitamente edição de arquivo no prompt dele —
    já houve incidente de sub-agente editando yaml de marca por engano (revertido).

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
| DDR1–5 / SDRAM (linha "especialidade") | a geração (`DDR2`, `DDR3`…) ou `"SDRAM"` (legado, sempre NÃO RENTÁVEL) | espelha | bus width (`x8`/`x16`/`x4`) | `density_gbit` (Gb/die) |
| LPDDR standalone (linha móvel padrão) | a geração (`LPDDR4X`…) | espelha | `""` | `capacity` (pacote, bytes) |
| PSRAM / HyperRAM (linha móvel especial) | **token não existe ainda** — não presumir, ver §5 | — | — | — |
| NOR Flash (código/boot — W25X/W35T/W74M, a confirmar) | `"NOR Flash"` (já existe, `dead` por tipo) | **descritivo livre** (chip_type manda) | — | conforme o tipo |
| NAND Flash raw (W25N/W35N/W29N, a confirmar) | `"NAND Flash"` (já existe, `dead` por tipo) | célula se souber (`"SLC NAND"` etc.) senão descritivo | — | `capacity` |
| MCP NOR+NAND empilhado ("SpiStack" W25M, a confirmar) | `"MCP"` (já existe, `dead` por tipo) | descritivo (ex.: composição) | — | conforme confirmável (regra de ouro #12) |
| eMMC / UFS / eMCP / uMCP (se a Winbond tiver — não confirmado no perfil pesquisado) | conforme o tipo | geração RAM ou vazio | conforme o tipo | `capacity` ou `emcp_*` |

**Regras absolutas** (idênticas em todo o WTC): `subtype` nas categorias DRAM/gerenciada nunca carrega
densidade/bus width/tensão/qualificador de mercado. `density_gbit` = Gb por die (é o campo do `KnownPart` que você preenche; `dram_density` é o derivado pelo engine — não confundir, `CLAUDE.md §6`). `capacity` = pacote em
bytes, nunca Gbit. `emcp_ram` = `"LPDDR{n} {cap}GB"` (tipo antes). `tip`/`notes` = todo o resto (tensão,
velocidade, organização, avisos, proveniência).

**Label da caixa** (referência, mesmo padrão de todas as marcas): DDR `{subtype}+{density_gbit}G` ·
LPDDR `{chip_type}+{cap GB}G` · eMCP `EMCP{nand}+{ram}` · eMMC `EMMC{cap}GB` · UFS `UFS{cap}GB` · NAND/NOR
`{subtype}{capacity}` quando `commercial=True`; tipos `dead`/`indeterminado` de categoria catálogo não têm
caixa comercial própria (`commercial=False` — não são roteados no estoque como os outros).

---

## 2. Processo de pesquisa e submissão — o COMO

### 2.1 Trilha A — Gramática (família nova ou correção)

1. Confirmar o prefixo/família em fonte Tier-1 (§0.3) — **nunca** criar família por analogia estrutural
   sem fonte que nomeie o prefixo diretamente.
2. Editar/criar `chips/knowledge/winbond.yaml`: `brand` (`name` exato — provavelmente `"Winbond"`, a
   confirmar; `code` curto único — provavelmente `"WINBOND"` ou `"WB"`, a decidir), `maps`
   (`[char_key, val_primary, val_secondary]`, prefixo de mapa por legibilidade, ex. `WB_DDR_CAP` — a FK
   `brand` é quem realmente separa), `families` (a gramática posicional: `prefix`,
   `chip_type`/`subtype`/`interface`, `priority`, `pn_length`, `is_emcp`, `active`,
   `decode_cap_*`/`decode_gen_*`/`decode_density_type`, `suffix_rules`, `reasoning` com a fonte).
3. Rodar `python manage.py load_brands --brand winbond` (dry-run = portão) — resolver os erros até
   passar.
4. **Família nova → GOLDEN obrigatório:** entregar PN-âncora + saída esperada (tipo/subtipo/capacidade/
   **rentabilidade**) em `_WINBOND_GOLDEN` (`chips/tests.py`). `GoldenObrigatorioTests` falha sem isso.
5. **Tipo novo em `chip_types.py`** (só se a Winbond trouxer algo que ainda não existe no vocabulário —
   candidato conhecido: PSRAM/HyperRAM, ver §5) → declarar a regra de rentabilidade junto;
   `RentabilidadeHandshakeTests` falha sem.
6. Rodar a suíte (`python manage.py test chips estoque --settings=core.settings_test`) +
   `characterize_baseline --diff` — só o pretendido deve mudar.
7. Entregar ao dono: diff do yaml + golden + saída dos testes. Ele roda `--commit` local, depois publica
   em prod (`git push` + `load_brands --brand winbond --commit` apontando o `DATABASE_URL` do Render).

### 2.2 Trilha B — Known_parts (autoridade — a que vence a gramática)

1. Pesquisa Tier-1 exaustiva por PN (não presumir por semelhança com PN "parecido").
2. Escrever o arquivo `submissions/winbond_<familia>_<data>.yaml`: `part_number` + specs + `confidence`
   (`confirmed`/`manual`, ver regra de ouro #12 se algo essencial não confirma) + **`notes` com a fonte
   Tier-1 citável** (URL/nome do datasheet — sem fonte não vira `confirmed`/`manual`).
3. Validar: `python manage.py submit_known_parts <arquivo>.yaml` (dry-run = portão). Corrigir até passar.
4. **Entregar o arquivo validado ao dono** — eu NÃO rodo o `--commit` (sandbox isolado + regra de ouro
   #1). Comando que entrego: só `submit_known_parts <arquivo>.yaml --commit` — **sem `--user`**, mesmo
   que o `AUTORIA.md` mencione `--user <id-do-chat>` para four-eyes (correção do dono, 2026-07-10).
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
  confirmada, o objetivo é cobertura de PNs, não só validar a regra. Regra permanente, reforçada 4x em
  outras marcas.
- **Mostrar a aritmética Gb→GB sempre** que eu reportar uma capacidade — nunca só declarar "XGB
  confirmado". De preferência 2+ fontes independentes batendo, cada uma com a conta visível.
- **Listar os known_parts da submissão direto no chat** (PN + spec principal + confidence), além de
  entregar o arquivo — o dono confere em paralelo sem abrir o arquivo primeiro.
- **Toda entrega de known_parts vem com o comando pronto** (dry-run já rodado + `--commit`), mesmo se
  ainda houver pergunta/pendência na mesma mensagem.
- **Antes de bulk-submeter (>5-10 PNs de uma família de uma vez), pedir ao dono uma query read-only de
  `part_number_norm`** contra o banco — pega colisão de formatação (mesmo PN, string diferente) E
  cobertura já `approved` por outro canal invisível (ex. um `import_*` de máquina), duas categorias de
  redundância que o `fuzzy_sugest.` do debug NÃO cobre.
- **A lista de "fuzzy suggestions" do debug já são KnownParts `approved`** — pesquisar/resubmeter um PN
  que está lá é redundante. O alvo real é o PN NÃO identificado; pra ampliar o lote, faço forward-lookup
  no prefixo do alvo, não puxo da lista de fuzzy.
- **Nunca reusar uma chave de posição assumindo que vale o mesmo valor em outra família** (ou até dentro
  da mesma família, em PNs-irmãos diferentes) — confirmar cada chave com PN âncora próprio.
- **`submissions/*.yaml` não vai pro git** — é formulário de uso único; só o `winbond.yaml` (gramática) é
  versionado.

### 2.4 Checklist de handoff (resumo — completo em `AUTORIA.md §6`)

- [ ] Só mexi na Winbond; não toquei em mapa global de outra marca.
- [ ] Nada inventado/estimado; ambíguo → perguntei ao dono; essencial não confirmado → excluí o PN.
- [ ] Gramática: `load_brands --brand winbond` (dry-run) passou; família nova → golden entregue.
- [ ] Tipo novo (se houver — ex. PSRAM/HyperRAM) → handshake de rentabilidade passa.
- [ ] Known_parts: cada um com fonte Tier-1 na `notes`; `submit_known_parts` (dry-run) passou; listei os
      PNs no chat; entreguei o arquivo + o comando (`--commit`, sem `--user`).
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
LPDDR–LPDDR4X         → DRAM móvel padrão (prefixo de PN não confirmado)   — [A CONFIRMAR em Tier-1]
SDR–DDR4 SDRAM        → DRAM especialidade/industrial (prefixo não confirmado) — [A CONFIRMAR]
```
Fonte: página de linha de produto de um distribuidor (ineltek.com, ver §7) + Wikipedia — **nenhuma
família foi criada na gramática a partir disso**; é só um mapa de "onde procurar" quando um PN real
chegar, o mesmo papel que a "escada de prefixo" (fonte GitHub não-oficial) cumpriu no `ESMT.md §3.1`
antes da 1ª pesquisa real daquela marca. Cada prefixo acima precisa da MESMA verificação Tier-1
(datasheet oficial nomeando o prefixo diretamente) antes de virar família na gramática — **nenhum foi
confirmado ainda**.

### 3.2 Família confirmada

**[A PREENCHER]** — nenhuma família Winbond tem PN-âncora confirmado em Tier-1 ainda. Esta seção nasce na
1ª rodada de pesquisa real (mesmo padrão do `ESMT.md §3.2`, que documentou a família M15T assim que o
dono passou o 1º PN real).

---

## 4. Armadilhas e Decisões Arquiteturais

**[A PREENCHER]** — nenhuma armadilha Winbond-específica confirmada ainda; esta seção cresce conforme a
pesquisa avança (mesmo padrão do `SK_HYNIX.md §3`/`ESMT.md §4`). Enquanto isso, de olho nas armadilhas
**sistêmicas** já provadas em outras marcas (`CLAUDE.md §7`) — têm boa chance de reaparecer aqui:

- Unidade Gb×GB confundida (o erro mais comum do domínio inteiro).
- `decode_density_type` + `decode_cap_map` juntos na mesma família (mutuamente exclusivos).
- Tipo/geração morta retornando INDETERMINADO em vez de NÃO RENTÁVEL (checar geração/tipo ANTES de exigir
  capacidade) — **especialmente relevante aqui**: NOR Flash/NAND Flash raw já são `dead` por tipo
  (`chip_types.py`), então qualquer família Winbond desses tipos precisa confirmar que herda esse
  veredito sem cair em INDETERMINADO por falta de capacidade (o mesmo padrão já foi corrigido pra
  SDRAM/GDDR2/ePoP no passado — ver `CLAUDE.md §7`).
- `subtype` verboso vazando pro label da caixa (mitigado por `canonical_gen`, mas escrever limpo mesmo
  assim no write-time) — **exceto** nas famílias de categoria catálogo (NOR Flash/SRAM/MCP), onde
  `subtype` descritivo é a regra, não a exceção (§1).
- Mesma chave de posição com valor diferente **dentro da mesma família** (não só entre marcas
  diferentes) — padrão achado repetidamente em famílias Samsung de chave curta + sufixo longo não
  decodificado; vale checar se há mais de um PN real pra mesma chave antes de confiar no default do
  mapa.

---

## 5. Rentabilidade — princípio (os valores NÃO ficam aqui)

**Fonte única: `assess_profitability`** (`chips/engine.py`); os limiares vivem no `ProfitabilityConfig`
(admin, o dono edita). ⚠ **É dado mutável** — muda com o mercado — por isso este doc **não cita valores
nem veredictos por família**.

Regras duráveis (essas não mudam): nunca reimplementar a regra de rentabilidade em outro lugar; `capacity`
sempre em MB/GB, nunca Gbit (senão vira INDETERMINADO = bloqueador).

**Específico do perfil Winbond (verificado em `chip_types.py`, 2026-08-05):**
- `"NOR Flash"` e `"NAND Flash"` (raw) já são **sempre NÃO RENTÁVEL por tipo** (`profit_family="dead"`) —
  junto de SDRAM/RDRAM/EDO DRAM/MCP/OneNAND/ePoP. ⚠ Mas diferem no `commercial`: `NOR Flash` é
  `catalog`/`commercial=False` (sem caixa), `NAND Flash` é `nand_raw`/`commercial=True` (tem caixa
  `"SLC NAND …"`, mas sucata por tipo); SDRAM idem (`dead`/`commercial=True`). Se a Winbond trouxer essas famílias
  (perfil provável, ver "Contexto" na abertura do arquivo), o veredito já existe no código, não precisa
  (re)decidir.
- `"SRAM"` também já existe (categoria catálogo, `commercial=False`, `profit_family="indeterminado"`) —
  mas **não presumir que PSRAM/HyperRAM devem usar esse token** sem confirmar com o dono; tecnicamente
  são famílias diferentes de SRAM tradicional.
- `"PSRAM"`/`"HyperRAM"` **não existem como `chip_type` ainda**. Se a pesquisa real confirmar que esses
  chips aparecem na bancada da eMiner, criar o tipo novo em `chip_types.py` exige **declarar a regra de
  rentabilidade junto** (`RentabilidadeHandshakeTests` falha sem) — decisão comercial do dono (é
  rentável? qual limiar?), não algo que este chat decide sozinho. Sinalizar e perguntar antes de propor.
- DDR/LPDDR discretos que a Winbond confirmar (linha "especialidade"/"móvel padrão") seguem as regras já
  existentes de `DDR1`–`DDR5`/`LPDDR1`–`LPDDR5X` — nenhum tipo novo necessário só por isso.

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
- [ ] **Decidir prioridade de categoria** — dado o perfil (NOR/NAND raw prováveis `dead` por tipo; DRAM
  especialidade/móvel seguem tipos já existentes; PSRAM/HyperRAM exigem tipo novo + handshake) — vale
  perguntar ao dono qual categoria aparece de fato na bancada antes de pesquisar às cegas.
- [ ] **PSRAM/HyperRAM: tipo novo em `chip_types.py`?** — só decidir/propor se a pesquisa confirmar que
  esses chips aparecem fisicamente; não adiantar a decisão.
- [ ] **`brand.name`/`brand.code`** — confirmar a forma exata esperada (`"Winbond"` vs. nome legal
  completo; `code` curto) antes de criar o yaml.
- [ ] **Golden test + handshake** — nenhum ainda, porque nenhuma família existe.

---

## 7. Fontes de pesquisa

Ver §0.3 (hierarquia completa, ainda sem precedente testado). Ponto de partida: site oficial + datasheets
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

- **2026-08-05 — Onboarding.** Criado a partir de `CLAUDE.md` (lido inteiro) + `SK_HYNIX.md` (referência
  de formato, pedido explícito do dono) + `AUTORIA.md` (processo obrigatório, `CLAUDE.md §5` manda ler
  antes de qualquer PN) + `ESMT.md` (precedente mais recente de marca nova, mesma situação de largada) +
  as convenções acumuladas na memória do projeto (disciplina de pesquisa, regras de ouro, checklist).
  Estado confirmado antes de escrever: **zero** `winbond.yaml`, **zero** known_part no banco/dumps (grep
  em `prod.json`/`local.json`/`seed_known_parts.json`), **zero** PN pesquisado. Winbond já aparece no
  `PROMPT_PRECOS.md` como marca "sem aba própria" — só contexto de UI, não gramática. Achado extra
  (`chips/chip_types.py`): `NOR Flash`/`NAND Flash` raw já são `dead` por tipo; `PSRAM`/`HyperRAM` ainda
  não têm token — candidatos a tipo novo + handshake quando a pesquisa confirmar. §3/§4/§6 ficaram como
  esqueleto/placeholder — nada de decode/pegadinha Winbond foi inventado sem fonte Tier-1; crescem PN a
  PN nas próximas sessões.

> O inventário de chaves/mapas vai viver no **`winbond.yaml`** (gramática, quando existir); os
> **known_parts** confirmados (com a proveniência Tier-1 nas `notes`) vivem no **banco** (Opção 2),
> submetidos via `submit_known_parts`. Tudo que é cross-marca (comandos, convenção, rentabilidade,
> arquitetura) está no **`CLAUDE.md`** — o único `.md` mantido nesse papel, e é quem aponta pro
> `AUTORIA.md`.

---

> **Regra de trabalho:** eu crio/edito o `winbond.yaml`. O dono roda `load_brands --brand winbond`
> (sempre dry-run antes do `--commit`) e o `submit_known_parts` (idem). **Ponto mais importante:** esta
> marca não tem NENHUM precedente confirmado ainda — atestar a IDENTIDADE em Tier-1 antes de qualquer
> decode, nunca extrapolar chave por padrão numérico nem por analogia com outra marca ou família (regra
> de ouro #9).
