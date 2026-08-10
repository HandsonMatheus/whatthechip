> ⚠️ **DUAS TRILHAS (Opção 2).** A **GRAMÁTICA** da ISSI (famílias + decode maps) vai morar em
> **`chips/knowledge/issi.yaml`** (via `load_brands --brand issi`) — **ainda não existe** (marca em
> onboarding, zero precedente). Os **known_parts** (PNs confirmados = autoridade) **não vão no yaml** —
> vivem no **banco**, submetidos por `submit_known_parts` e **aprovados pelo dono** no admin (four-eyes).
> **Processo obrigatório completo — LEIA: `AUTORIA.md`** (índice: `CLAUDE.md §5`).
>
> **Este `.md` é a camada humana** — não reproduz dado (isso vive no yaml e no banco, quando existirem).
> Aqui ficam: **convenções, o processo de pesquisa/submissão, anatomia do PN, armadilhas, rentabilidade
> (princípio), fontes, o *porquê*** e ponteiros — modelo estrutural: `SK_HYNIX.md` (referência pedida
> pelo dono) e `ESMT.md` (precedente mais próximo: marca nova onboardada no mesmo dia, 2026-08-05).
>
> ⚠️ **Estado em 2026-08-05: marca 100% nova.** Zero `chips/knowledge/issi.yaml`, zero known_parts, zero
> família pesquisada. Este documento é só o **framework de processo** — a pesquisa real de PNs ISSI
> começa na próxima sessão/mensagem. §3/§4/§6/§8 ficam como esqueleto/placeholder de propósito.

---

# ISSI.md — Guia Técnico e de Negócio (marca em onboarding)

> Em conflito, o **código é a fonte da verdade** (`chips/engine.py`, `chips/chip_types.py`). Quando
> `chips/knowledge/issi.yaml` existir, ele também manda sobre este texto. Regras gerais do WTC: `CLAUDE.md`.

**ISSI (Integrated Silicon Solution, Inc.)** é fabricante de memória e de ICs analógicos/mixed-signal —
histórico em SRAM, DRAM de nicho/legada e NOR/NAND Flash —, fundada em Fremont, Califórnia (EUA). **Este
parágrafo é orientação geral, não dado verificado**: confirmar na 1ª pesquisa real (a) se `issi.com`
ainda é o domínio oficial vigente e quem emite os datasheets hoje (histórico de mercado: a ISSI foi
adquirida por um consórcio investidor por volta de 2015 — checar se isso mudou a fonte Tier-1 antes de
tratá-la como automática), e (b) quais linhas de produto realmente aparecem na bancada da eMiner. Nada
deste parágrafo é usado pelo engine.

Esta marca é a próxima ("13ª+", contando os 12 `chips/knowledge/*.yaml` que já existem hoje) na tradição
do WTC: `AUTORIA.md §9`/`CLAUDE.md §5` já preveem esse caminho — basta criar o `issi.yaml` que o
`load_brands`/`deploy_catalog` a descobrem sozinhos (glob), sem nenhuma configuração extra. Todas as
travas (portão, dedup, guards, handshake, golden, tripwire) já valem pra ela.

**⚠ Sequência obrigatória (confirmado lendo `submit_known_parts.py` em 2026-08-05 — vale pra qualquer
marca nova, não só ISSI):** o comando faz `Brand.objects.filter(name=brand_name).first()` e **levanta
`CommandError` se a marca não existir** — essa checagem roda **antes** do early-return de dry-run (linha
79 vs. linha 102 do comando). Ou seja: `load_brands --brand issi --commit` (Trilha A) **precisa rodar
antes** de qualquer `submit_known_parts` (Trilha B) funcionar, nem que seja só validar um rascunho em
dry-run. O `AUTORIA.md` descreve as duas trilhas como independentes — na prática, pra marca nova, A
destrava B (mesmo achado já registrado na sessão de onboarding da ESMT, mesmo dia; reconfirmado aqui
lendo o código de novo, não só citado de segunda mão).

**Contexto de hoje no sistema (estado datado, não é convenção — confirmar se ainda vale antes de
assumir):** a ISSI já é citada por nome em `PROMPT_PRECOS.md` (regra 4, "marca sem aba própria" — junto
de Rayson/PieceMakers/GigaDevice/ESMT/Winbond): sem gramática/known_parts, hoje ela cairia na tabela
genérica `Other Brands` (casa por marca+tipo+capacidade) e, se não achar ali, na Nanya como curinga
(só cobre LPDDR4/DDR — eMMC/eMCP/UFS/uMCP fora do `Other Brands` ficaria sem preço). Isso só diz onde a
marca cairia HOJE na UI de preço — não é gramática nem substitui a pesquisa Tier-1.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro

### 0.1 Onde vive o conhecimento

```
chips/knowledge/issi.yaml   ← GRAMÁTICA (famílias + decode maps). AINDA NÃO EXISTE (Opção 2: só gramática).
banco (submit_known_parts→aprovação)   ← known_parts confirmados = autoridade (não no yaml). Zero ainda.
AUTORIA.md / CLAUDE.md §5   ← o processo OBRIGATÓRIO das duas trilhas + convenção + comandos
chips/chip_types.py         ← vocabulário de chip_type — já cobre SRAM/NOR Flash/NAND Flash (ver §5)
```

**Duas trilhas** (detalhe em `AUTORIA.md`): **gramática** (família/mapa) → criar/editar
`chips/knowledge/issi.yaml` → `load_brands --brand issi` (dry-run = portão) → o **dono** roda `--commit`.
**known_parts** (autoridade) → arquivo de submissão → `submit_known_parts` (dry-run) → o **dono** roda
`--commit` + **aprova no admin**. ⚠ **Toda família da ISSI será "nova"** (a marca não tem baseline
grandfathered) → **PN-âncora no golden é OBRIGATÓRIO**, sem exceção (`GoldenObrigatorioTests` falha
sem). **NÃO tocar sem revisão:** `chips/engine.py`, `estoque/views.py` (globais), yamls/known_parts de
outra marca, mapas globais (`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung).

### 0.2 Regras de ouro — nunca violar

1. **Eu (chat) edito arquivos. O dono roda os comandos que escrevem no banco.** Nunca `load_brands
   --commit` / `submit_known_parts --commit` / `migrate` — meu sandbox é isolado e não alcança o banco
   dele; meu papel é entregar o yaml/arquivo de submissão validado (dry-run passou), nunca gravar.
2. **`load_brands --brand issi` (dry-run) é o portão** da gramática — valida a convenção, nada é
   gravado. `submit_known_parts <arquivo>` (dry-run) é o portão dos known_parts. Depois do `--commit`, o
   cache recarrega sozinho (`catalog_version`), sem restart.
3. **OPÇÃO 1 — a GERAÇÃO vai no `chip_type`** para toda DRAM discreta que a ISSI fizer (SDRAM/DDR/DDR2/
   DDR3…): ex. `chip_type="DDR3"`, nunca `"RAM"`/`"DDR"` genérico (família ativa com tipo genérico é
   **rejeitada** pelo portão). Espelhar no `subtype`. Memória gerenciada (eMMC/UFS/eMCP/uMCP), **se a
   ISSI tiver** — a confirmar, não presumir — mantém o `chip_type` como o tipo; `subtype` = geração LPDDR
   ou célula NAND. Fonte única: `chips/chip_types.py`.
4. **`subtype` = SÓ geração/célula**, 1–3 palavras. ❌ densidade, bus width, tensão, "Industrial",
   "Mobile", nome comercial, qualificador de package.
5. **`interface`** = bus width (`x8`/`x16`/`x4`) para DDR/SDRAM discreto, lido da posição real do PN;
   vazio para LPDDR standalone e eMCP/uMCP. Nunca a geração de RAM no `interface`.
6. **Se existir eMCP/uMCP** (a confirmar): `emcp_ram` = tipo ANTES da capacidade (`"LPDDR3 1GB"`, nunca
   `"1GB LPDDR3"`); `emcp_nand` = só GB.
7. **Nunca inverta `val_primary`/`val_secondary`** nos decode maps — quando o mapa já existir, siga o
   padrão das linhas dele. Nunca escreva `"por die"` no secondary (o engine já anexa).
   `decode_density_type` e `decode_cap_map` são **mutuamente exclusivos** na mesma família (o portão
   rejeita os dois juntos).
8. **Não confie em distribuidor/IA sem verificar.** Erram Gb/GB, invertem primary/secondary, alucinam
   capacidade. Cruzar sempre com datasheet oficial / Octopart (categorização própria, não a descrição do
   distribuidor dentro dele).
9. **⚠️ Ouro = IDENTIDADE, não as specs derivadas — atestar SEMPRE em Tier-1.** Um `confidence="confirmed"`
   verifica que o PN/laser-marking é real; `capacity`/`subtype`/geração são **derivados** (decode map,
   distribuidor, ou inferência por prefixo) e podem estar errados mesmo assim — foi o erro `MT52L=LPDDR4`
   da Micron (era LPDDR3) e o `H9DA`≠LPDDR3 da SK Hynix: geração por prefixo/nome sem atestar é o modo de
   falha nº1. **A ISSI não tem nenhum precedente confirmado ainda — toda família é a "primeira vez",
   redobre o cuidado.**
10. **Só a MINHA marca (ISSI).** Não coletar/editar PN, família ou mapa de outra marca; nunca tocar em
    mapa global (`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung); nunca reusar uma chave de posição de outra
    marca "porque parece igual" (foi a causa raiz do bug X6 da Samsung) — nem assumir que a mesma chave
    vale o mesmo dentro da própria família sem checar mais de um PN confirmado.
11. **PN ambíguo, tipo-lixo ou módulo → NUNCA decido sozinho.** Paro e pergunto ao dono. Nenhuma
    heurística ("subtype vence", "por analogia com família parecida") substitui a palavra do dono sobre
    o que a peça realmente é.
12. **Spec essencial (capacidade, interface/versão, tipo) não confirmável em Tier-1 → EXCLUIR o PN da
    submissão inteiramente.** Nunca campo em branco, genérico ou estimado "pra documentar proveniência"
    — regra sem exceção, mesmo para tipo catálogo (NOR Flash = `dead`, SRAM = `indeterminado` — ver §5) onde a capacidade não muda o
    veredito de rentabilidade. Documentar a tentativa/beco-sem-saída no rodapé "NÃO submetidos".
13. **Escopo é só dado (yaml da ISSI + arquivos de submissão).** Não editar `.py`/testes/infra/scripts
    sem pedido explícito do dono, mesmo que pareça um ajuste pequeno ou já "sancionado" por processo
    (ex.: handshake de rentabilidade em `chip_types.py`) — se a mudança reclassifica algo que um
    comentário/teste já sinaliza como decisão pendente do dono, é sinal de PARE e pergunte.
14. **Se eu delegar pesquisa a um sub-agente:** proibir explicitamente edição de arquivo no prompt dele
    — já houve incidente de sub-agente editando yaml de outra marca por engano (revertido).

### 0.3 Hierarquia de fontes (a confirmar/ajustar na prática — ainda sem precedente ISSI)

```
1. Site oficial + datasheet ISSI (domínio a confirmar — provável issi.com) → Tier 1
2. Octopart / Nexar — categorização PRÓPRIA do Octopart, nunca a descrição do distribuidor dentro dele → Tier 2
3. Alldatasheet / LCSC / DigiKey / Mouser com rastreabilidade ISSI → Tier 2
4. Distribuidor B2B rastreável (Preduo, WinSource, Jotrin…) → só apoio; nunca rebaixa um confirmed; nunca decide capacidade sozinho
5. iFixit/GSMArena → chip_type confirmado por inspeção física (se aparecer em device teardown)
6. IA externa → ÚLTIMO RECURSO; verificar SEMPRE contra 1–3
```
Nunca fonte primária: fóruns, distribuidor sem rastreio, catálogos genéricos, eBay, IA sem verificação.
Regra geral do WTC (`CLAUDE.md §6`): fabricante/datasheet > Octopart/Nexar > distribuidor B2B rastreável
> Preduo > IA > especulação — importadores **nunca** rebaixam um registro `confirmed`/`manual`.

---

## 1. Convenção Canônica de Campos ⚠️ LEIA PRIMEIRO

> **OPÇÃO 1. Fonte única: `chips/chip_types.py` (código).** Contexto geral: `CLAUDE.md §6`. Ainda não sei
> quais categorias a ISSI realmente cobre — **não presuma o perfil da marca antes da hora**; a tabela
> abaixo é a convenção universal do WTC, aplique conforme cada família se confirma.

| Tipo | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| DDR1–5 / SDRAM | a geração (`DDR2`, `DDR3`…) ou `"SDRAM"` (legado, sempre NÃO RENTÁVEL) | espelha | bus width (`x8`/`x16`/`x4`) | `density_gbit` (Gb/die) |
| LPDDR standalone (se houver) | a geração (`LPDDR4X`…) | espelha | `""` | `capacity` (pacote, bytes) |
| eMMC / UFS (se houver) | `"eMMC"`/`"UFS"` | `""` | versão (`"eMMC 5.1"` etc.) | `capacity` (GB) |
| eMCP / uMCP (se houver) | `"eMCP"`/`"uMCP"` | geração RAM | `""` | `emcp_nand` (GB) + `emcp_ram` (tipo+GB) |
| NAND Flash (raw, se houver) | `"NAND Flash"` | célula (`"SLC NAND"`/`"MLC NAND"`/`"TLC NAND"`) | — | `capacity` (bytes) |
| SRAM / NOR Flash / catálogo (prováveis pelo perfil histórico da marca) | `"SRAM"`/`"NOR Flash"`/etc. | descritivo (categoria `catalog` — chip_type MANDA, não normaliza) | — | sem caixa comercial (ver §5) |

**Regras absolutas** (idênticas em todo o WTC): `subtype` nunca carrega densidade/bus width/tensão/
qualificador de mercado. `density_gbit` = Gb por die (é o campo do `KnownPart` que você preenche; `dram_density` é o derivado pelo engine — não confundir, `CLAUDE.md §6`). `capacity` = pacote em bytes, nunca Gbit.
`emcp_ram` = `"LPDDR{n} {cap}GB"` (tipo antes). `tip`/`notes` = todo o resto (tensão, velocidade,
organização, avisos, proveniência).

**Label da caixa** (referência, mesmo padrão de todas as marcas): DDR `{subtype}+{density_gbit}G` ·
LPDDR `{chip_type}+{cap GB}G` · eMCP `EMCP{nand}+{ram}` · eMMC `EMMC{cap}GB` · UFS `UFS{cap}GB` · NAND
`{subtype}{capacity}` (ex. `SLC NAND 512MB`) · catálogo (SRAM/NOR Flash) = identifica mas **sem caixa
comercial** (`commercial=False`, ver §5).

---

## 2. Processo de pesquisa e submissão — o COMO

### 2.1 Trilha A — Gramática (família nova ou correção)

1. Confirmar o prefixo/família em fonte Tier-1 (§0.3) — **nunca** criar família por analogia estrutural
   sem fonte que nomeie o prefixo diretamente.
2. Editar/criar `chips/knowledge/issi.yaml`: `brand` (`name` exato — provavelmente `"ISSI"`; `code` curto
   único — provavelmente `"ISSI"` também, já que o nome da marca já é curto), `maps` (tabelas
   `[char_key, val_primary, val_secondary]`, prefixo de mapa por legibilidade, ex. `ISSI_SRAM_CAP` — a FK
   `brand` é quem realmente separa), `families` (a gramática posicional: `prefix`,
   `chip_type`/`subtype`/`interface`, `priority`, `pn_length`, `is_emcp`, `active`,
   `decode_cap_*`/`decode_gen_*`/`decode_density_type`, `suffix_rules`, `reasoning` com a fonte).
3. Rodar `python manage.py load_brands --brand issi` (dry-run = portão) — resolver os erros até passar.
4. **Família nova → GOLDEN obrigatório:** entregar PN-âncora + saída esperada (tipo/subtipo/capacidade/
   **rentabilidade**) em `_ISSI_GOLDEN` (`chips/tests.py`). `GoldenObrigatorioTests` falha sem isso.
5. **Tipo novo em `chip_types.py`** (só se a ISSI trouxer algo que ainda não existe no vocabulário — hoje
   parece improvável, ver §5) → declarar a regra de rentabilidade junto; `RentabilidadeHandshakeTests`
   falha sem.
6. Rodar a suíte (`python manage.py test chips estoque --settings=core.settings_test`) +
   `characterize_baseline --diff` — só o pretendido deve mudar.
7. Entregar ao dono: diff do yaml + golden + saída dos testes. Ele roda `--commit` local, depois publica
   em prod (`git push` + `load_brands --brand issi --commit` apontando o `DATABASE_URL` do Render).

### 2.2 Trilha B — Known_parts (autoridade — a que vence a gramática)

1. Pesquisa Tier-1 exaustiva por PN (não presumir por semelhança com PN "parecido").
2. Escrever o arquivo `submissions/issi_<familia>_<data>.yaml`: `part_number` + specs + `confidence`
   (`confirmed`/`manual`, ver regra de ouro #12 se algo essencial não confirma) + **`notes` com a fonte
   Tier-1 citável** (URL/nome do datasheet — sem fonte não vira `confirmed`/`manual`).
3. **Lembrete de sequência (achado desta sessão, §0 acima):** `submit_known_parts` só valida em dry-run
   se a `Brand` "ISSI" já existir no banco — ou seja, a Trilha A (mesmo que só `--commit` local, sem
   publicar em prod) precisa rodar pelo menos uma vez antes de eu conseguir validar QUALQUER submissão.
4. Validar: `python manage.py submit_known_parts <arquivo>.yaml` (dry-run = portão). Corrigir até passar.
5. **Entregar o arquivo validado ao dono** — eu NÃO rodo o `--commit` (sandbox isolado + regra de ouro
   #1). Comando que entrego: só `submit_known_parts <arquivo>.yaml --commit` — **sem `--user`**, mesmo
   que o `AUTORIA.md` mencione `--user <id-do-chat>` para four-eyes (correção do dono, 2026-07-10).
6. O dono roda o `--commit` (grava `submitted`, oculto) e **aprova no admin**
   (`/admin/chips/knownpart/`).
7. Só depois de aprovado o PN fica visível/autoritativo no engine.

### 2.3 Disciplina de pesquisa (como NÃO tropeçar)

- **Pesquisar o CLUSTER inteiro, nunca 1 PN por rodada** — mesmo se a chave/família já está bem
  confirmada, o objetivo é cobertura de PNs, não só validar a regra. Buscar site-wide (`site:ifixit.com
  <FAMÍLIA>`, `<FAMÍLIA> datasheet part number list`) e abrir/ler a fonte primária direto — nunca confiar
  só no resumo em prosa da busca.
- **Mostrar a aritmética Gb→GB sempre** que eu reportar uma capacidade — nunca só declarar "XGB
  confirmado". De preferência 2+ fontes independentes batendo, cada uma com a conta visível.
- **Listar os known_parts da submissão direto no chat** (PN + spec principal + confidence), além de
  entregar o arquivo — o dono confere em paralelo sem abrir o arquivo primeiro.
- **Toda entrega de known_parts vem com o comando pronto** (dry-run já rodado + `--commit`), mesmo se
  ainda houver pergunta/pendência na mesma mensagem.
- **A lista de "fuzzy suggestions" do debug já são KnownParts `approved`** — pesquisar/resubmeter um PN
  que está lá é redundante. O alvo real é o PN NÃO identificado; pra ampliar o lote, faço forward-lookup
  no prefixo do alvo, não puxo da lista de fuzzy.
- **Nunca reusar uma chave de posição assumindo que vale o mesmo valor em outra família** (ou até dentro
  da mesma família, em PNs/sufixos diferentes) — confirmar cada chave com PN âncora próprio; se dois PNs
  confirmados com a mesma chave divergirem, o PN exceção vira known_part individual, o default do mapa
  segue a maioria.
- **Antes de bulk-submeter (>5-10 PNs de uma família de uma vez), pedir ao dono uma query read-only de
  `part_number_norm`** contra o banco — pega tanto colisão de formatação (mesmo PN, string diferente)
  quanto cobertura já `approved` por outro canal invisível pra mim (ex. import de máquina).
- **`submissions/*.yaml` não vai pro git** — é formulário de uso único; só o `issi.yaml` (gramática) é
  versionado.
- **Se `AskUserQuestion` falhar** (erro de ferramenta): perguntar em texto normal no corpo da resposta é
  um fallback válido — não insistir na tool nem travar a conversa.

### 2.4 Checklist de handoff (resumo — completo em `AUTORIA.md §6`)

- [ ] Só mexi na ISSI; não toquei em mapa global de outra marca.
- [ ] Nada inventado/estimado; ambíguo → perguntei ao dono; essencial não confirmado → excluí o PN.
- [ ] Gramática: `load_brands --brand issi` (dry-run) passou; família nova → golden entregue.
- [ ] Tipo novo (se houver) → handshake de rentabilidade passa.
- [ ] Known_parts: cada um com fonte Tier-1 na `notes`; `submit_known_parts` (dry-run) passou; listei os
      PNs no chat; entreguei o arquivo + o comando (`--commit`, sem `--user`).
- [ ] Suíte inteira verde + `characterize_baseline --diff` só com o pretendido.
- [ ] Não toquei no banco do dono nem em prod; não editei `.py`/testes/infra sem pedir.

---

## 3. Anatomia do PN — como LER um chip ISSI

### 3.1 Candidatos de linha de produto a confirmar (NÃO é gramática — só pista de onde procurar)

> Lista de memória geral de mercado, **sem fonte Tier-1 citada** — equivalente ao papel da "escada de
> prefixo" do `ESMT.md §3.1`. Cada prefixo abaixo precisa da MESMA verificação Tier-1 (datasheet oficial
> nomeando o prefixo) antes de virar família na gramática. Não decodificar nada daqui sem PN âncora real.

```
IS61 / IS62         → SRAM (assíncrona/síncrona) — linha historicamente forte da marca
IS42 / IS43 / IS45 / IS46  → SDRAM/DDR de nicho ou legada
IS25                → NOR Flash (SPI)
IS34 / IS37          → NAND Flash
```

**Relevância pra bancada — a confirmar, não presumir:** SRAM e NOR Flash (perfil mais provável da ISSI)
podem aparecer com menos frequência na reciclagem de memória do que DDR/eMMC/UFS das marcas grandes — mas
`PROMPT_PRECOS.md` já cita a ISSI por nome (ver intro), então o dono já espera vê-la na bancada. Confirmar
volume real antes de decidir se vale família dedicada ou só known_parts avulsos.

### 3.2 Estrutura do PN

**[A PREENCHER]** — nenhuma família ISSI confirmada ainda. Ao pesquisar a primeira, documentar aqui — no
mesmo nível de detalhe do `SK_HYNIX.md §2` / `ESMT.md §3.2` — por família: onde fica o bloco de
capacidade (posição/tamanho) e qual mapa do `issi.yaml` ele usa; qual posição/mapa indica geração ou
célula; organização/bus width, se houver; e qualquer pegadinha posicional (prefixo mais longo vencendo
outro mais curto, sufixo que parece capacidade mas não é, PN literal por extenso vs. código curto de
tabela — a ESMT, por exemplo, usa PN literal; a ISSI pode seguir qualquer um dos dois padrões).

---

## 4. Armadilhas e Decisões Arquiteturais

**[A PREENCHER]** — nenhuma armadilha ISSI-específica confirmada ainda; esta seção cresce conforme a
pesquisa avança (mesmo padrão do `SK_HYNIX.md §3`/`ESMT.md §4`). Enquanto isso, de olho nas armadilhas
**sistêmicas** já provadas em outras marcas (`CLAUDE.md §7`) — têm boa chance de reaparecer aqui:

- Unidade Gb×GB confundida (o erro mais comum do domínio inteiro).
- `decode_density_type` + `decode_cap_map` juntos na mesma família (mutuamente exclusivos).
- Tipo/geração morta retornando INDETERMINADO em vez de NÃO RENTÁVEL (checar geração ANTES de exigir
  capacidade) — relevante se a ISSI trouxer SDRAM pura ou SRAM/NOR Flash (tipos catálogo, ver §5).
- `subtype` verboso vazando pro label da caixa (mitigado por `canonical_gen`, mas escrever limpo mesmo
  assim no write-time).
- Mesma chave de posição com valor diferente dentro da MESMA família (não só entre famílias) — sempre
  checar mais de um PN confirmado por chave antes de assumir que ela generaliza.

---

## 5. Rentabilidade — princípio (os valores NÃO ficam aqui)

**Fonte única: `assess_profitability`** (`chips/engine.py`); os limiares vivem no `ProfitabilityConfig`
(admin, o dono edita). ⚠ **É dado mutável** — muda com o mercado — por isso este doc **não cita valores
nem veredictos por família**.

Regras duráveis (essas não mudam): nunca reimplementar a regra de rentabilidade em outro lugar; `capacity`
sempre em MB/GB, nunca Gbit (senão vira INDETERMINADO = bloqueador).

**Achado específico da ISSI (confirmado em código, `chips/chip_types.py`, 2026-08-05):** as linhas de
produto mais prováveis da marca (§3.1) já têm `chip_type` declarado — **não deve ser necessário abrir
tipo novo nem disparar o Handshake de rentabilidade (§2.1 passo 5) só pra começar**:
- **`SRAM`** já existe: categoria `catalog`, `profit_family="indeterminado"`, `commercial=False` —
  identifica/rotula o chip, mas **sem caixa física** no gateway do estoque (não é bin-triado por
  capacidade).
- **`NOR Flash`** já existe: categoria `catalog`, `profit_family="dead"` (sempre NÃO RENTÁVEL),
  `commercial=False`.
- **`NAND Flash`** (raw) já existe: categoria `nand_raw`, `profit_family="dead"`.
- Se a ISSI também tiver DRAM discreta (SDRAM/DDR/LPDDR de nicho ou legada), os tipos DRAM padrão já
  cobrem — nada novo a declarar.

Isso só muda se a pesquisa **confirmar** um tipo genuinamente não coberto (raro) — aí sim é decisão do
dono + Handshake, nunca decisão do chat.

*Nota de contexto (não é rentabilidade, é onde a marca cai na UI de preço hoje):* a ISSI já é citada em
`PROMPT_PRECOS.md` como marca "sem aba própria" — cai no `Other Brands` (casa por marca+tipo+capacidade)
e, se não achar ali, na Nanya como curinga (só LPDDR4/DDR). Isso pode mudar; confirmar em
`PRECIFICACAO.md` antes de assumir que ainda vale.

---

## 6. Gaps e Roadmap

- [ ] **Confirmar o domínio/situação corporativa oficial da ISSI** antes de tratar `issi.com` como Tier-1
  automático na hierarquia (§0.3) — histórico de aquisição por consórcio investidor (~2015) a reconfirmar.
- [ ] **Confirmar quais linhas de produto (§3.1) realmente aparecem na bancada** — SRAM/NOR Flash/NAND
  Flash/DRAM de nicho são candidatos por perfil histórico da marca, nenhum confirmado ainda.
- [ ] **Definir `brand.code`** no yaml — sugestão natural `"ISSI"` (já curto), a confirmar com o dono ao
  criar o `issi.yaml`.
- [ ] **Primeira família:** seguir a Trilha A completa (§2.1), incluindo o golden obrigatório em
  `_ISSI_GOLDEN` (`chips/tests.py`) — não é opcional, `GoldenObrigatorioTests` falha sem PN-âncora porque
  nenhum prefixo ISSI está no baseline grandfathered.
- [ ] **Rodar `load_brands --brand issi` (dry-run/commit) assim que o 1º rascunho de yaml existir** —
  necessário mesmo só pra destravar validação de known_parts em dry-run (§0, achado de hoje).
- [ ] **Confirmar se `chip_types.py` já cobre 100% do que a pesquisa encontrar** (SRAM/NOR/NAND Flash já
  cobertos, ver §5) — só abrir tipo novo se a pesquisa revelar algo genuinamente não coberto.

---

## 7. Fontes de pesquisa

Ver §0.3 (hierarquia completa, ainda sem precedente testado). Ponto de partida: site oficial + datasheets
ISSI (domínio a confirmar), Octopart, Alldatasheet, LCSC, DigiKey/Mouser. Evitar como fonte de
capacidade/tipo: qualquer distribuidor sem rastreio e resumo de IA sem verificação — mesmo cuidado que
todas as outras marcas do WTC.

---

## 8. Histórico (o *porquê* — durável)

- **2026-08-05 — criação deste `.md`.** Pedido do dono: ler `CLAUDE.md` (inteiro) + `SK_HYNIX.md`
  (referência de formato) e gerar o guia de convenções/processo pra ISSI virar "chat de marca" antes de
  qualquer PN real ser pesquisado. Além dos dois arquivos indicados, usei como molde estrutural mais
  próximo o `ESMT.md` (marca onboardada no mesmo dia, mesmas circunstâncias — zero yaml/known_part) e
  dobrei pra dentro deste doc as obrigações cross-marca já aprendidas com outras marcas (disciplina de
  pesquisa em cluster, aritmética Gb/GB visível, listar known_parts no chat, excluir-não-adivinhar,
  nunca `--user` no comando entregue, não mexer em código sem pedir, restringir escopo de sub-agentes) —
  mesma lista que a sessão ESMT já havia consolidado.
- **2026-08-05 — achado técnico (verificado direto no código, não só citado):** `submit_known_parts.py`
  exige a `Brand` já existir no banco **mesmo em dry-run** (`CommandError` na checagem, antes do
  early-return de dry-run) — Trilha A destrava Trilha B pra qualquer marca nova, ISSI inclusa.
- **2026-08-05 — achado de rentabilidade (verificado em `chips/chip_types.py`):** `SRAM`, `NOR Flash` e
  `NAND Flash` já existem no vocabulário de tipos (categoria `catalog`/`nand_raw`, sem caixa comercial ou
  sempre NÃO RENTÁVEL) — as linhas de produto mais prováveis da ISSI não devem exigir Handshake de tipo
  novo pra começar.
- **2026-08-05 — achado de contexto (verificado em `PROMPT_PRECOS.md`):** a ISSI já é citada por nome
  como marca "sem aba própria" de preço — cai no `Other Brands`/curinga Nanya hoje.
- Nenhuma família, nenhum known_part, nenhum `chips/knowledge/issi.yaml` existe ainda para esta marca.

> O inventário de chaves/mapas vai viver no **`issi.yaml`** (gramática, quando criado); os **known_parts**
> confirmados (com a proveniência Tier-1 nas `notes`) vão viver no **banco**, submetidos via
> `submit_known_parts`. Tudo que é cross-marca (comandos, convenção, rentabilidade, arquitetura) está no
> **`CLAUDE.md`** — o único `.md` mantido nesse papel, e é quem aponta pro `AUTORIA.md`.

---

> **Regra de trabalho:** eu crio/edito o `issi.yaml` e preparo arquivos de submissão de known_parts; o
> dono roda `load_brands --brand issi` (sempre dry-run antes do `--commit`) e o `submit_known_parts`
> (idem) e aprova no admin. **Ponto mais importante:** a ISSI começa do ZERO — toda família nova PRECISA
> de golden test, todo known_part PRECISA de fonte Tier-1 citada na `notes`, e PN ambíguo ou tipo
> genuinamente novo NUNCA se decide sozinho — pergunto ao dono primeiro.
