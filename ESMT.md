> ⚠️ **DUAS TRILHAS (Opção 2, jul/2026).** A **GRAMÁTICA** da ESMT (famílias + decode maps) vai morar em
> **`chips/knowledge/esmt.yaml`** (via `load_brands --brand esmt`) — **ainda não existe** (marca em
> onboarding). Os **known_parts** (PNs confirmados = autoridade) **não vão no yaml** — vivem no **banco**,
> submetidos por `submit_known_parts` e **aprovados pelo dono** no admin (four-eyes). **Processo obrigatório
> completo — LEIA: `AUTORIA.md`** (índice: `CLAUDE.md §5`).
>
> **Este `.md` é a camada humana** — não reproduz dado (isso vive no yaml e no banco, quando existirem).
> Aqui ficam: **convenções, o processo de pesquisa/submissão, anatomia do PN, armadilhas, rentabilidade
> (princípio), fontes, o *porquê*** e ponteiros — igual ao `SK_HYNIX.md`, que serviu de modelo para este
> arquivo.
>
> ⚠️ **Estado em 2026-08-20: 3 famílias mapeadas (M15T/DDR3L, M14D+M14F/DDR2, M15F/DDR3 — 16 prefixos),
> ainda NÃO carregadas no sistema.** `chips/knowledge/esmt.yaml` (rascunho, 16 famílias) e 4 arquivos de
> submissão (`submissions/esmt_m15t_2026-08-05.yaml`, `esmt_m15t_x8_2026-08-05.yaml`,
> `esmt_m14d_2026-08-20.yaml`, `esmt_m15f_2026-08-20.yaml` — 16 known_parts no total) já existem e
> passaram no portão Pydantic (validado standalone, fora do Django) — falta rodar `load_brands --brand
> esmt` (dry-run) no ambiente local real antes de qualquer `--commit`. §3/§6/§8 atualizados com o que foi
> confirmado; o resto da escada de prefixo (M12L, M13S/M13D, M16U, M53D–M56Z) continua esqueleto.

---

# ESMT.md — Guia Técnico e de Negócio (marca em onboarding)

> Em conflito, o **código + o yaml são a fonte da verdade** (`chips/engine.py`, `chips/knowledge/esmt.yaml`
> quando existir). Regras gerais do WTC: `CLAUDE.md`.

**ESMT** (Elite Semiconductor Memory Technology Inc., Taiwan) é fabricante de memória com perfil mais
industrial/nicho que Samsung/SK Hynix/Micron — histórico em SDRAM/DDR de densidade baixa, SRAM e Flash.
**Este parágrafo é orientação, não dado verificado** — confirmar/expandir com fonte oficial (site do
fabricante, datasheets) na 1ª rodada de pesquisa real; não é usado pelo engine.

Esta marca já tem um **rascunho** de `chips/knowledge/esmt.yaml` (4 famílias M15T) e de submissão de
known_parts (`submissions/esmt_m15t_2026-08-05.yaml`, 4 PNs) — mas **nenhum dos dois foi carregado no
sistema ainda** (nenhum known_part aprovado no banco). É a próxima ("11ª+") na tradição do WTC:
`AUTORIA.md §9`/`CLAUDE.md §5` já preveem esse caminho — basta criar o yaml que o `load_brands`/
`deploy_catalog` a descobrem sozinhos (glob), sem nenhuma configuração extra. Todas as travas (portão,
dedup, guards, handshake, golden, tripwire) já valem pra ela.

**⚠ Sequência obrigatória, descoberta ao ler `submit_known_parts.py` (2026-08-05):** o comando faz
`Brand.objects.filter(name=brand_name).first()` e **levanta erro se a marca não existir** — isso acontece
**mesmo em dry-run** (o early-return de dry-run só vem DEPOIS dessa checagem). Ou seja: pra uma marca nova,
`load_brands --brand esmt --commit` (Trilha A) precisa rodar **antes** de `submit_known_parts` (Trilha B)
funcionar, nem que seja só pra validar em dry-run. O `AUTORIA.md` descreve as duas trilhas como
independentes — na prática, pra marca nova, A destrava B. (Vale pra qualquer marca nova, não só ESMT —
pode valer a pena registrar isso no `AUTORIA.md` também, mas isso não é decisão minha sozinha.)

**Contexto de hoje no sistema (estado datado, não é convenção — confirmar se ainda vale antes de assumir):**
ESMT já aparece como marca **"sem aba própria"** de preço (usa a tabela genérica, junto de
Rayson/PieceMakers/GigaDevice/Winbond — `PROMPT_PRECOS.md`) e num teste de pricing (`pricing/tests.py`,
`chip_type='DDR3'`). Isso só diz onde ela cai HOJE na UI de preço — não é gramática nem substitui pesquisa.

---

## 0. ⚠️ LEIA PRIMEIRO — Regras de ouro

### 0.1 Onde vive o conhecimento

```
chips/knowledge/esmt.yaml   ← GRAMÁTICA (famílias + decode maps). SÓ isso (Opção 2). RASCUNHO (4 famílias
                               M15T — DDR3(L) SDRAM 1G/2G/4G/8G x16 — ainda não passou por load_brands).
banco (submit_known_parts→aprovação)   ← known_parts confirmados = autoridade (não no yaml). Rascunho de
                               submissão pronto (submissions/esmt_m15t_2026-08-05.yaml, 4 PNs), não enviado.
AUTORIA.md / CLAUDE.md §5     ← o processo OBRIGATÓRIO das duas trilhas + convenção + comandos
```

**Duas trilhas** (detalhe em `AUTORIA.md`): **gramática** (família/mapa) → criar/editar o yaml → `load_brands
--brand esmt` (dry-run = portão) → o **dono** roda `--commit`. **known_parts** (autoridade) →
`submit_known_parts` (dry-run) → o **dono** roda `--commit` + **aprova no admin**. ⚠ **Toda família da ESMT
será "nova"** (a marca não tem baseline grandfathered) → **PN-âncora no golden é OBRIGATÓRIO**, sem exceção
(`GoldenObrigatorioTests` falha sem). **NÃO tocar sem revisão:** `chips/engine.py`, `estoque/views.py`
(globais), yamls/known_parts de outra marca, mapas globais (`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung).

### 0.2 Regras de ouro — nunca violar

1. **Eu (chat) edito arquivos. O dono roda os comandos que escrevem no banco.** Nunca `load_brands
   --commit` / `submit_known_parts --commit` / `migrate` — meu sandbox é isolado e não alcança o banco
   dele; meu papel é entregar o yaml/arquivo de submissão validado (dry-run passou), nunca gravar.
2. **`load_brands --brand esmt` (dry-run) é o portão** da gramática — valida a convenção, nada é gravado.
   `submit_known_parts <arquivo>` (dry-run) é o portão dos known_parts. Depois do `--commit`, o cache
   recarrega sozinho (`catalog_version`), sem restart.
3. **OPÇÃO 1 — a GERAÇÃO vai no `chip_type`** para toda DRAM discreta que a ESMT fizer (SDRAM/DDR/DDR2/
   DDR3…): ex. `chip_type="DDR3"`, nunca `"RAM"`/`"DDR"` genérico (família ativa com tipo genérico é
   **rejeitada** pelo portão). Espelhar no `subtype`. Memória gerenciada (eMMC/UFS/eMCP/uMCP/NAND), **se a
   ESMT tiver** — a confirmar, não presumir — mantém o `chip_type` como o tipo; `subtype` = geração LPDDR
   ou célula NAND. Fonte única: `chips/chip_types.py`.
4. **`subtype` = SÓ geração/célula**, 1–3 palavras. ❌ densidade, bus width, tensão, "Industrial",
   "Mobile", "SDRAM" solto, qualificador de package.
5. **`interface`** = bus width (`x8`/`x16`/`x4`) para DDR/SDRAM discreto lido da posição real do PN; vazio
   para LPDDR standalone e eMCP/uMCP. Nunca a geração de RAM no `interface`.
6. **Se existir eMCP/uMCP** (a confirmar): `emcp_ram` = tipo ANTES da capacidade (`"LPDDR3 1GB"`, nunca
   `"1GB LPDDR3"`); `emcp_nand` = só GB.
7. **Nunca inverta `val_primary`/`val_secondary`** nos decode maps — quando o mapa já existir, siga o
   padrão das linhas dele. Nunca escreva `"por die"` no secondary (o engine já anexa). `decode_density_type`
   e `decode_cap_map` são **mutuamente exclusivos** na mesma família (o portão rejeita os dois juntos).
8. **Não confie em distribuidor/IA sem verificar.** Erram Gb/GB, invertem primary/secondary, alucinam
   capacidade. Cruzar sempre com datasheet oficial / Octopart (categorização própria, não a descrição do
   distribuidor dentro dele).
9. **⚠️ Ouro = IDENTIDADE, não as specs derivadas — atestar SEMPRE em Tier-1.** Um `confidence="confirmed"`
   verifica que o PN/laser-marking é real; `capacity`/`subtype`/geração são **derivados** (decode map,
   distribuidor, ou inferência por prefixo) e podem estar errados mesmo assim — foi o erro `MT52L=LPDDR4`
   da Micron (era LPDDR3): geração por prefixo/família sem atestar é o modo de falha nº1. **A ESMT não tem
   nenhum precedente confirmado ainda — toda família é a "primeira vez", redobre o cuidado.**
10. **Só a MINHA marca (ESMT).** Não coletar/editar PN, família ou mapa de outra marca; nunca tocar em
    mapa global (`DRAM_PC`/`DRAM_MOBILE`, dono = Samsung); nunca reusar uma chave de posição de outra marca
    "porque parece igual" (foi a causa raiz do bug X6 da Samsung).
11. **PN ambíguo, tipo-lixo ou módulo → NUNCA decido sozinho.** Paro e pergunto ao dono. Nenhuma heurística
    ("subtype vence", "por analogia com família parecida") substitui a palavra do dono sobre o que a peça
    realmente é.
12. **Spec essencial (capacidade, interface/versão, tipo) não confirmável em Tier-1 → EXCLUIR o PN da
    submissão inteiramente.** Nunca campo em branco, genérico ou estimado "pra documentar proveniência" —
    regra sem exceção, mesmo para tipo catálogo (NOR Flash = `dead`, SRAM = `indeterminado` — ver `chip_types.py`) onde a capacidade não muda o
    veredito de rentabilidade. Documentar a tentativa/beco-sem-saída no rodapé "NÃO submetidos".
13. **Escopo é só dado (yaml da ESMT + arquivos de submissão).** Não editar `.py`/testes/infra/scripts sem
    pedido explícito do dono, mesmo que pareça um ajuste pequeno.
14. **Se eu delegar pesquisa a um sub-agente:** proibir explicitamente edição de arquivo no prompt dele —
    já houve incidente de sub-agente editando yaml de marca por engano (revertido).

### 0.3 Hierarquia de fontes (a confirmar/ajustar na prática — ainda sem precedente ESMT)

```
1. Site oficial + datasheet ESMT (domínio a confirmar — provável esmt.com.tw) → Tier 1
2. Octopart / Nexar — categorização PRÓPRIA do Octopart, nunca a descrição do distribuidor dentro dele → Tier 2
3. Alldatasheet / LCSC / DigiKey com rastreabilidade ESMT → Tier 2
4. Distribuidor B2B rastreável (Preduo, WinSource, Jotrin…) → só apoio; nunca rebaixa um confirmed; nunca decide capacidade sozinho
5. iFixit/GSMArena → chip_type confirmado por inspeção física (se aparecer em device teardown)
6. IA externa → ÚLTIMO RECURSO; verificar SEMPRE contra 1–3
```
Nunca fonte primária: fóruns, distribuidor sem rastreio, catálogos genéricos, eBay, IA sem verificação.
Regra geral do WTC (`CLAUDE.md §6`): fabricante/datasheet > Octopart/Nexar > distribuidor B2B rastreável >
Preduo > IA > especulação — importadores **nunca** rebaixam um registro `confirmed`/`manual`.

---

## 1. Convenção Canônica de Campos ⚠️ LEIA PRIMEIRO

> **OPÇÃO 1. Fonte única: `chips/chip_types.py` (código).** Contexto geral: `CLAUDE.md §6`. Ainda não sei
> quais categorias a ESMT realmente cobre — **não presuma o perfil da marca antes da hora**; a tabela
> abaixo é a convenção universal do WTC, aplique conforme cada família se confirma.

| Tipo | `chip_type` | `subtype` | `interface` | Campo de tamanho |
|---|---|---|---|---|
| DDR1–5 / SDRAM | a geração (`DDR2`, `DDR3`…) ou `"SDRAM"` (legado, sempre NÃO RENTÁVEL) | espelha | bus width (`x8`/`x16`/`x4`) | `density_gbit` (Gb/die) |
| LPDDR standalone (se houver) | a geração (`LPDDR4X`…) | espelha | `""` | `capacity` (pacote, bytes) |
| eMMC / UFS (se houver) | `"eMMC"`/`"UFS"` | `""` | versão (`"eMMC 5.1"` etc.) | `capacity` (GB) |
| eMCP / uMCP (se houver) | `"eMCP"`/`"uMCP"` | geração RAM | `""` | `emcp_nand` (GB) + `emcp_ram` (tipo+GB) |
| SRAM / NOR Flash / catálogo (prováveis pelo perfil industrial) | `"SRAM"`/`"NOR Flash"`/etc. | descritivo (categoria `catalog` — chip_type MANDA, não normaliza) | — | conforme o tipo |

**Regras absolutas** (idênticas em todo o WTC): `subtype` nunca carrega densidade/bus width/tensão/
qualificador de mercado. `density_gbit` = Gb por die (é o campo do `KnownPart` que você preenche; `dram_density` é o derivado pelo engine — não confundir, `CLAUDE.md §6`). ⚠ **Sub-1Gb TEM que ser fracionário
em `Gb`** (ex. `"0.5Gb"` pra 512Mb — nunca `"512Mb"`, o parser numérico do engine só reconhece o sufixo
literal `Gb`; ver §4, achado 2026-08-20). `capacity` = pacote em bytes, nunca Gbit.
`emcp_ram` = `"LPDDR{n} {cap}GB"` (tipo antes). `tip`/`notes` = todo o resto (tensão, velocidade,
organização, avisos, proveniência).

**Label da caixa** (referência, mesmo padrão de todas as marcas): DDR `{subtype}+{density_gbit}G` ·
LPDDR `{chip_type}+{cap GB}G` · eMCP `EMCP{nand}+{ram}` · eMMC `EMMC{cap}GB` · UFS `UFS{cap}GB` · NAND
`{subtype}{capacity}` (ex. `SLC NAND 512MB`).

---

## 2. Processo de pesquisa e submissão — o COMO

### 2.1 Trilha A — Gramática (família nova ou correção)

1. Confirmar o prefixo/família em fonte Tier-1 (§0.3) — **nunca** criar família por analogia estrutural
   sem fonte que nomeie o prefixo diretamente.
2. Editar/criar `chips/knowledge/esmt.yaml`: `brand` (`name` exato, `code` curto único — provavelmente
   `"ESMT"`, já que o nome da marca é o próprio código), `maps` (`[char_key, val_primary, val_secondary]`,
   prefixo de mapa por legibilidade, ex. `ESMT_DDR_CAP` — a FK `brand` é quem realmente separa), `families`
   (a gramática posicional: `prefix`, `chip_type`/`subtype`/`interface`, `priority`, `pn_length`, `is_emcp`,
   `active`, `decode_cap_*`/`decode_gen_*`/`decode_density_type`, `suffix_rules`, `reasoning` com a fonte).
3. Rodar `python manage.py load_brands --brand esmt` (dry-run = portão) — resolver os erros até passar.
4. **Família nova → GOLDEN obrigatório:** entregar PN-âncora + saída esperada (tipo/subtipo/capacidade/
   **rentabilidade**) em `_ESMT_GOLDEN` (`chips/tests.py`). `GoldenObrigatorioTests` falha sem isso.
5. **Tipo novo em `chip_types.py`** (só se a ESMT trouxer algo que ainda não existe no vocabulário) →
   declarar a regra de rentabilidade junto; `RentabilidadeHandshakeTests` falha sem.
6. Rodar a suíte (`python manage.py test chips estoque --settings=core.settings_test`) +
   `characterize_baseline --diff` — só o pretendido deve mudar.
7. Entregar ao dono: diff do yaml + golden + saída dos testes. Ele roda `--commit` local, depois publica em
   prod (`git push` + `load_brands --brand esmt --commit` apontando o `DATABASE_URL` do Render).

### 2.2 Trilha B — Known_parts (autoridade — a que vence a gramática)

1. Pesquisa Tier-1 exaustiva por PN (não presumir por semelhança com PN "parecido").
2. Escrever o arquivo `submissions/esmt_<familia>_<data>.yaml`: `part_number` + specs + `confidence`
   (`confirmed`/`manual`, ver regra de ouro #12 se algo essencial não confirma) + **`notes` com a fonte
   Tier-1 citável** (URL/nome do datasheet — sem fonte não vira `confirmed`/`manual`).
3. Validar: `python manage.py submit_known_parts <arquivo>.yaml` (dry-run = portão). Corrigir até passar.
4. **Entregar o arquivo validado ao dono** — eu NÃO rodo o `--commit` (sandbox isolado + regra de ouro #1).
   Comando que entrego: só `submit_known_parts <arquivo>.yaml --commit` — **sem `--user`**, mesmo que o
   `AUTORIA.md` mencione `--user <id-do-chat>` para four-eyes (correção do dono, 2026-07-10).
5. O dono roda o `--commit` (grava `submitted`, oculto) e **aprova no admin** (`/admin/chips/knownpart/`).
6. Só depois de aprovado o PN fica visível/autoritativo no engine.

### 2.3 Disciplina de pesquisa (como NÃO tropeçar)

- **Pesquisar o CLUSTER inteiro, nunca 1 PN por rodada** — mesmo se a chave/família já está bem
  confirmada, o objetivo é cobertura de PNs, não só validar a regra.
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
  da mesma família, em posições/famílias-irmãs diferentes) — confirmar cada chave com PN âncora próprio.
- **`submissions/*.yaml` não vai pro git** — é formulário de uso único; só o `esmt.yaml` (gramática) é
  versionado.

### 2.4 Checklist de handoff (resumo — completo em `AUTORIA.md §6`)

- [ ] Só mexi na ESMT; não toquei em mapa global de outra marca.
- [ ] Nada inventado/estimado; ambíguo → perguntei ao dono; essencial não confirmado → excluí o PN.
- [ ] Gramática: `load_brands --brand esmt` (dry-run) passou; família nova → golden entregue.
- [ ] Tipo novo (se houver) → handshake de rentabilidade passa.
- [ ] Known_parts: cada um com fonte Tier-1 na `notes`; `submit_known_parts` (dry-run) passou; listei os
      PNs no chat; entreguei o arquivo + o comando (`--commit`, sem `--user`).
- [ ] Suíte inteira verde + `characterize_baseline --diff` só com o pretendido.
- [ ] Não toquei no banco do dono nem em prod.

---

## 3. Anatomia do PN — como LER um chip ESMT

### 3.1 Escada de prefixo por geração (fonte: doc de terceiros no GitHub — NÃO oficial, só pista a confirmar)

```
M12L / M52S / M52D  → SDR SDRAM
M13S / M13D          → DDR / LPDDR
M14D / M14F          → DDR2 SDRAM             ← CONFIRMADO 2026-08-20, ver §3.3
M15T / M15F          → DDR3L / DDR3 SDRAM     ← CONFIRMADO — M15T em 2026-08-05 (§3.2), M15F em 2026-08-20 (§3.4). NÃO é só par de voltagem igual M14D/M14F: DDR3 e DDR3L são chip_types DISTINTOS em chip_types.py, e o M15F mapeia pro tipo diferente (DDR3, não DDR3L) — ver §3.4
M16U                 → DDR4 SDRAM
M53D                 → LPDDR
M54D                 → LPDDR2
M55D                 → LPDDR3
M56Z                 → LPDDR4X
```
Cada prefixo dessa lista precisa da MESMA verificação Tier-1 antes de virar família na gramática — isso é
só um mapa de onde procurar "outros tipos" no futuro, não uma confirmação. A doc de terceiros acertou o
M14D/M14F de primeira (DDR2 SDRAM) — bom sinal de que o resto da escada também deve estar certo, mas
**ainda** não é confirmação, cada prefixo precisa da própria pesquisa Tier-1/2.

### 3.2 M15T — DDR3(L) SDRAM (confirmado 2026-08-05)

O PN é **literal, não um código de 1-2 caracteres por tabela** (diferente da SK Hynix/Samsung): a própria
string já escreve densidade + organização por extenso. Estrutura observada, cruzando 4 PNs confirmados
diretamente via Alldatasheet (título do datasheet cita a organização) + datasheet oficial esmt.com.tw:

```
M15T <densidade em Gb> <largura x> <total de palavras em M, todos os bancos> A
```

| PN confirmado | Densidade | Organização | Conta (bits) | Capacidade |
|---|---|---|---|---|
| M15T**1G**16**64**A | 1Gb | x16, 8 bancos (8M/banco) | 8.388.608 × 16 × 8 = 1.073.741.824 | 1Gb = 128MB |
| M15T**2G**16**128**A | 2Gb | x16, 8 bancos (16M/banco) | 16.777.216 × 16 × 8 = 2.147.483.648 | 2Gb = 256MB |
| M15T**4G**16**256**A | 4Gb | x16, 8 bancos (32M/banco) | 33.554.432 × 16 × 8 = 4.294.967.296 | 4Gb = 512MB |
| M15T**8G**16**512**A | 8Gb | x16, 8 bancos (64M/banco) | 67.108.864 × 16 × 8 = 8.589.934.592 | 8Gb = 1024MB |
| M15T**2G**8**256**A | 2Gb | x8, 8 bancos (32M/banco) | 33.554.432 × 8 × 8 = 2.147.483.648 | 2Gb = 256MB |
| M15T**4G**8**512**A | 4Gb | x8, 8 bancos (64M/banco) | 67.108.864 × 8 × 8 = 4.294.967.296 | 4Gb = 512MB |

O número final (64/128/256/512) bate exatamente com "total de palavras em M por todos os 8 bancos" nos
6 PNs confirmados (4× x16 + 2× x8) — inicialmente era dedução por cruzamento aritmético entre os 4 x16;
a 2ª rodada (2026-08-05) confirmou que o mesmo padrão vale pro par **x8** (`M15T2G8256A`, `M15T4G8512A`)
com **citação direta de organização** (não só o padrão de nomenclatura, que era tudo que eu tinha na 1ª
rodada — por isso tinham ficado de fora, ver §8). Fontes: `M15T4G8512A` tem 3 fontes convergentes
(Alldatasheet + tabela da Satron Electronics `satronel.com` + título indexado do DigChip); `M15T2G8256A`
tem só 1 fonte de conteúdo direta (Alldatasheet) — confiança um degrau abaixo, sinalizado explicitamente
na `notes` do known_part. Os dois foram submetidos com `confidence: confirmed`
(`submissions/esmt_m15t_x8_2026-08-05.yaml`), mas **o dono deve revisar o `M15T2G8256A` com atenção
extra antes de aprovar no admin**, dado o sourcing mais fino. PDF oficial (`esmt.com.tw`) segue
bloqueado pra leitura direta nos dois — mesmo padrão de bloqueio já visto nos outros 4 (ver §6/§7).

⚠ **Sufixo de pedido** (`-DEBG2C`, `-DIBG` etc., depois do "A" final) codifica velocidade+pacote+
temperatura+RoHS segundo uma doc de terceiros (GitHub, não oficial) — **não confirmado letra a letra**.
`normalize_pn("M15T1G1664A-DEBG2C")` → `"M15T1G1664ADEBG2C"` (confirmado rodando a função de verdade) —
ou seja, o prefixo literal sobrevive à normalização, então o match por `prefix` deve funcionar mesmo com
sufixo, mas não testei o `_match_family` do engine de verdade (precisa do Django completo).

⚠ **Tensão dupla:** a ESMT descreve a família inteira como **"DDR3(L)"** — um PN só que opera em 1.5V
(DDR3) OU 1.35V (DDR3L), diferente da SK Hynix (que separa H5TQ/H5TC em prefixos distintos por tensão).
**Decisão do dono (2026-08-05): registrar como `DDR3L`** no nosso `chip_type`/`subtype`.

### 3.3 M14D / M14F — DDR2 SDRAM (confirmado 2026-08-20)

Mesmo padrão literal do M15T (`M14D <densidade> <largura x> <total de palavras em M, todos os bancos> A`),
mas densidade em **Mb** (sem letra "G") quando sub-1Gb, e **com "G"** a partir de 1Gb — mesma lógica do
M15T, só que aqui aparecem os dois regimes porque a família cobre densidades bem menores (128Mb–1Gb):

| PN confirmado | Densidade | Organização | Conta (bits) | Capacidade | Fontes |
|---|---|---|---|---|---|
| M14D**128**16**8**A | 128Mb | x16, 4 bancos (2M/banco) | 2.097.152 × 16 × 4 = 134.217.728 | 128Mb = 16MB | 2 (Suntsu-PDF + Satron) |
| M14D**256**16**16**A | 256Mb | x16, 4 bancos* (16M/banco) | 16.777.216 × 16 = 268.435.456 | 256Mb = 32MB | 2 (Alldatasheet + Satron) |
| M14D**512**16**32**A | 512Mb | x16, 4 bancos (8M/banco) | 8.388.608 × 16 × 4 = 536.870.912 | 512Mb = 64MB | 4 (Alldatasheet+LCSC+Sekorm+Satron) — **PN ao vivo do debug 2026-08-20** |
| M14F**512**16**32**A | 512Mb | x16, 4 bancos* — **1.55V** (M14D=1.8V) | idem acima | 512Mb = 64MB | 1 só (Satron) ⚠ revisar |
| M14D**1G**16**64**A | 1Gb | x16, 8 bancos (8M/banco) | 8.388.608 × 16 × 8 = 1.073.741.824 | 1Gb = 128MB | 4 (Alldatasheet+oficial+Satron+Novitronic) |
| M14D**1G**8**128**A | 1Gb | x8, 8 bancos* | 128M × 8 = 1.073.741.824 | 1Gb = 128MB | 1 só (Satron) ⚠ revisar |

*bancos não confirmados diretamente nesse PN específico — inferido por padrão JEDEC DDR2 (4 bancos até
512Mb, 8 bancos a partir de 1Gb), confirmado diretamente nos irmãos 128Mb/512Mb (4 bancos) e 1Gb x16 (8
bancos) desta mesma família. Não afeta a densidade calculada (independe de quantos bancos a compõem).

⚠ **M14F = par de voltagem do M14D, prefixo SEPARADO** (diferente do M15T, que usa 1 prefixo só pras duas
tensões do DDR3(L)) — ESMT decidiu separar D(1.8V)/F(1.55V) no DDR2. Não existe `"DDR2L"` no vocabulário
de `chip_types.py` (só `"DDR2"`) — **M14F também mapeia pra `chip_type=DDR2`**, confirmado pelo portão
Pydantic (não é decisão arbitrária, é a única forma que resolve a um tipo canônico válido).

⚠ **Densidade sub-1Gb — achado metodológico importante (2026-08-20):** `density_gbit` **tem** que ser
escrito como fração de `Gb` (`"0.5Gb"`, `"0.25Gb"`, `"0.125Gb"`), **nunca** como `"512Mb"`/`"256Mb"`/
`"128Mb"`. Motivo, confirmado lendo `chips/engine.py` direto: o parser `_extract_gbit()` usa
`_GBIT_RE = re.compile(r'(\d+(?:\.\d+)?)\s*Gb\b')` — só reconhece o sufixo literal `"Gb"`; `"512Mb"` NÃO
bate (é `"Mb"`, não `"Gb"`), então `density_gbit_num` ficaria `None` mesmo com o campo "preenchido" — a
mesma classe de bug do caso H5AN (`density_gbit` populado mas invisível pro engine). Provado rodando o
regex real (copiado de `engine.py`) contra os dois formatos no ambiente de validação standalone — ver
§8. Todas as famílias ESMT anteriores (M15T) eram ≥1Gb, então essa armadilha nunca tinha aparecido antes
nesta marca. Também populei `density_gb` (ex. `"64MB"`) pra manter a leitura humana clara — o engine
monta `dram_density = "0.5Gb = 64MB por die [✓]"` (`chips/engine.py::_known_dram_density`).

### 3.4 M15F — DDR3 SDRAM (confirmado 2026-08-20)

Mesmo padrão literal do M15T (`M15F <densidade> <largura x> <total de palavras em M, todos os bancos> A`),
gatilho: PN **ao vivo do debug de estoque** (`M15F1G1664A`, 100% desconhecido, `fuzzy_suggestions` apontava
`M15T1G1664A` e `M14D1G1664A` — nenhum dos dois é o PN real):

| PN confirmado | Densidade | Organização | Conta (bits) | Capacidade | Fontes |
|---|---|---|---|---|---|
| M15F**1G**16**64**A | 1Gb | x16, 8 bancos (8M/banco) | 8.388.608 × 16 × 8 = 1.073.741.824 | 1Gb = 128MB | 3 (oficial esmt.com.tw + Satron + Alldatasheet) — **PN ao vivo do debug 2026-08-20** |
| M15F**2G**16**128**A | 2Gb | x16, 8 bancos (16M/banco) | 16.777.216 × 16 × 8 = 2.147.483.648 | 2Gb = 256MB | listagem Alldatasheet + 4 distribuidores (existência) ⚠ revisar |
| M15F**4G**16**256**A | 4Gb | x16, 8 bancos (32M/banco) | 33.554.432 × 16 × 8 = 4.294.967.296 | 4Gb = 512MB | 4 (Alldatasheet+Sekorm+Satron+listagem) — tensão com 1 divergência, ver abaixo |
| M15F**512**16**32**A | 512Mb | x16, 8 bancos (4M/banco) | 4.194.304 × 16 × 8 = 536.870.912 | 512Mb = 64MB | 3 (Satron+Alldatasheet+datasheetspdf) |

⚠ **`M15F` NÃO é "o mesmo tipo, outra tensão" como o M14D/M14F — é um `chip_type` DIFERENTE.**
`chips/chip_types.py` tem `"DDR3"` e `"DDR3L"` como entradas **distintas** (confirmado lendo o arquivo
direto, não suposição) — diferente do DDR2, onde `"DDR2L"` não existe e M14D/M14F foram forçados pro
mesmo `chip_type=DDR2`. Todo datasheet/título indexado chama a família M15F de **"DDR3 SDRAM"** (sem
"(L)"), contra **"DDR3(L) SDRAM"** do M15T — e a única confirmação direta de tensão que achei
(`M15F1G1664A`, página oficial `esmt.com.tw`) é **1.5V-only**, contra o 1.35V/1.5V dual do M15T. Por
isso: **`chip_type=DDR3` (não `DDR3L`) pro M15F inteiro.** Isso **não muda rentabilidade** — `DDR3` e
`DDR3L` têm o mesmo `ChipTypeSpec` (`dram_pc`/`ddr`/`ddr`, `carries_generation=True`, `commercial=True`),
confirmado rodando os dois lado a lado no ambiente de validação — só deixa o tipo/label exibido mais
preciso.

⚠ **Uma divergência de tensão não resolvida:** a tabela da Satron cita `M15F4G16256A` especificamente
como `"1.35V/1.5V"` (dual, como se fosse DDR3L), enquanto Alldatasheet e Sekorm (2 fontes independentes,
citando o próprio título do datasheet) chamam esse mesmo PN de `"DDR3 SDRAM"` sem "(L)" — mesmo padrão dos
outros 3 M15F, todos 1.5V-only onde a tensão foi confirmada. Mantive `chip_type=DDR3` pelo sinal mais
consistente (nome do datasheet, repetido), mas sinalizei a divergência na `notes` do known_part — pode ser
erro de tabela do distribuidor, ou um sub-sufixo específico dual-rated dentro do mesmo PN base (não
decodifico sufixo de pedido nesta marca, §3.2). Se a tensão exata importar pro caso de uso, vale o dono
conferir o datasheet oficial diretamente.

⚠ **`M15F4G8512A`** (par x8 esperado do `M15F4G16256A`, mesmo padrão do M15T2G8256A/M15T4G8512A) apareceu
**1 única vez**, numa listagem agregada do Alldatasheet (busca por prefixo "M15") — sem página dedicada
própria (busquei direto por ID e não achou) nem qualquer menção em Satron/Sekorm/LCSC/IC-Components apesar
de busca dirigida. Não incluí no yaml nem na submissão (regra de ouro #12 — essencial não confirmável em
Tier-1/2 exclui o PN inteiro, nunca estimar). Pode ser um PN real e obscuro, ou pode ser a ferramenta de
busca confundindo com a linha vizinha do `M15T4G8512A` — não dá pra saber sem uma fonte dedicada.

`M15F2G16128A` também ficou 1 degrau abaixo dos outros 3: a organização só veio da mesma listagem agregada
(não uma página dedicada), embora a EXISTÊNCIA do PN esteja bem corroborada por 4 distribuidores
independentes (`datasheet4u.com` ×2 sufixos, `electronicsdatasheets.com`, `datasheet-pdf.com`,
`edinventory.com`). Confiança tratada como o `M15T2G8256A` da 1ª família (submetido, mas sinalizado pro
dono revisar com atenção extra).

---

## 4. Armadilhas e Decisões Arquiteturais

- **Densidade sub-1Gb precisa de `density_gbit` fracionário em `Gb`** (`"0.5Gb"`, não `"512Mb"`) — senão
  `density_gbit_num` fica `None` em silêncio (`_extract_gbit`/`_GBIT_RE` só reconhece o sufixo `"Gb"`
  literal). Achado ao vivo no M14D/M14F (§3.3, 2026-08-20) — primeira família ESMT sub-1Gb.
- **`WebFetch` pode citar a organização certa e ainda errar a "densidade total" que ele mesmo calcula**
  (visto 2x na rodada dos x8 do M15T, 2026-08-05) — sempre refazer a conta na mão a partir da organização
  citada (NxM x largura x bancos), nunca colar o total que a ferramenta ofereceu de bônus. Ver §7.
- **M14D/M14F: prefixo separado por voltagem no DDR2** (D=1.8V, F=1.55V), diferente do M15T que usa 1
  prefixo só pras duas tensões do DDR3(L). Sem `"DDR2L"` no vocabulário — os dois mapeiam pra `DDR2`.
- **M15T/M15F NÃO segue o mesmo padrão do M14D/M14F** — parece par de voltagem por analogia de prefixo,
  mas `DDR3`/`DDR3L` são `chip_type`s DISTINTOS em `chip_types.py` (diferente de `DDR2`/`"DDR2L"`, onde
  só um existe). Sempre CONFIRMAR o vocabulário antes de assumir "mesmo padrão de uma família parecida" —
  quase presumi DDR3L pro M15F por analogia com M14F antes de checar (§3.4, 2026-08-20).
- **Listagem agregada do Alldatasheet (busca por prefixo) pode citar PN que não existe em nenhuma fonte
  dedicada** (`M15F4G8512A`, §3.4/§6, 2026-08-20) — tratar citação só-em-listagem como pista, não
  confirmação; sempre tentar achar a página dedicada ou 2ª fonte antes de incluir.
- Unidade Gb×GB confundida (o erro mais comum do domínio inteiro).
- `decode_density_type` + `decode_cap_map` juntos na mesma família (mutuamente exclusivos).
- Tipo/geração morta retornando INDETERMINADO em vez de NÃO RENTÁVEL (checar geração ANTES de exigir
  capacidade) — **confirmado que isso já vale pra DDR2** (§5): `assess_profitability` aplica "DDR2 ou
  inferior → NÃO RENTÁVEL" por GERAÇÃO (não por tipo-morto categórico como SDRAM puro).
- `subtype` verboso vazando pro label da caixa (mitigado por `canonical_gen`, mas escrever limpo mesmo
  assim no write-time).

---

## 5. Rentabilidade — princípio (os valores NÃO ficam aqui)

**Fonte única: `assess_profitability`** (`chips/engine.py`); os limiares vivem no `ProfitabilityConfig`
(admin, o dono edita). ⚠ **É dado mutável** — muda com o mercado — por isso este doc **não cita valores
nem veredictos por família**.

Regras duráveis (essas não mudam): nunca reimplementar a regra de rentabilidade em outro lugar; `capacity`
sempre em MB/GB, nunca Gbit (senão vira INDETERMINADO = bloqueador); SDRAM puro (`chip_types.py`, categoria
`dram_legacy`) já é **sempre NÃO RENTÁVEL por tipo**, independente de capacidade — se a ESMT trouxer SDRAM,
esse veredito já existe no código, não precisa (re)decidir. Tipo comercial novo que a ESMT trouxer e que
ainda não exista em `chip_types.py` → precisa do handshake de rentabilidade antes de virar família ativa
(§2.1 passo 5).

**DDR2 (M14D/M14F) — confirmado 2026-08-20, distinção importante:** `DDR2` é categoria `dram_pc` (comercial,
NÃO `dram_legacy`/morta-por-tipo) — a regra que zera a família não é "tipo morto", é **geração dentro de um
tipo vivo**: `assess_profitability` (`chips/engine.py`) aplica "DDR standalone: DDR2 ou inferior → NÃO
RENTÁVEL" por LIMIAR DE GERAÇÃO, igual já documentado pro NT5TU da Nanya. Efeito prático é o mesmo (sempre
NÃO RENTÁVEL, qualquer capacidade), mas o MECANISMO é diferente de "SDRAM puro" — não confundir os dois ao
explicar o veredito.

**DDR3 (M15F) vs DDR3L (M15T) — confirmado 2026-08-20:** os dois têm o **mesmo `ChipTypeSpec`** em
`chip_types.py` (`dram_pc`/`ddr`/`ddr`, `carries_generation=True`, `commercial=True` — confirmado
comparando os dois registros lado a lado no ambiente de validação). Ou seja, **rentabilidade não muda**
entre `DDR3` e `DDR3L` — ambos ficam acima do limiar "DDR2 ou inferior" e o veredito real depende do
`ProfitabilityConfig` atual (mutável), igual já vale pro M15T — **não é previsível sem rodar `classify()`
localmente**, diferente do DDR2 (M14D/M14F), que É um veredito fixo.

*Nota de contexto (não é rentabilidade, é onde a marca cai na UI de preço hoje):* ESMT está no grupo "sem
aba própria" do `PROMPT_PRECOS.md` — usa a tabela genérica de preço, não uma aba dedicada. Isso pode mudar;
confirmar em `PRECIFICACAO.md` antes de assumir que ainda vale.

---

## 6. Gaps e Roadmap

- [x] **Confirmar a hierarquia de fontes real** — esmt.com.tw (oficial, hospeda datasheet em
  `/upload/pdf/ESMT/datasheets/`) + Alldatasheet (mirror confiável, título cita organização) confirmados
  na prática 2026-08-05. `WebFetch` direto no domínio oficial redireciona pra home (bloqueio a bot?) — só
  consegui specs via Alldatasheet/buscas; se o dono tiver o PDF baixado, ler direto resolveria o resto.
- [x] **Primeira família com PN-âncora** — M15T1G1664A + siblings (2G/4G/8G x16), 2026-08-05. **Falta o
  golden de verdade** — rascunho de entrada pronto (ver abaixo), mas ainda não colado em `chips/tests.py`
  (não editei o arquivo — fora do meu escopo sem pedir, regra de ouro #13).
- [ ] **Rodar `load_brands --brand esmt` (dry-run) no ambiente local real** — só validei o rascunho contra
  o `schema.py` (Pydantic) standalone, fora do Django; falta o check de colisão de prefixo entre marcas
  (vive no `load_brands.py`/banco, não no Pydantic isolado).
- [x] **Confirmar organização das variantes x8** (`M15T2G8256A`, `M15T4G8512A`) — 2ª rodada, 2026-08-05:
  ambos confirmados com citação direta de organização (Alldatasheet); `M15T4G8512A` com 3 fontes
  convergentes, `M15T2G8256A` com 1 só (confiança assimétrica, ver §3.2/§8). Submetidos em
  `submissions/esmt_m15t_x8_2026-08-05.yaml`.
- [ ] **Decodificar o sufixo de pedido** (`-DEBG2C` etc.) letra a letra contra o datasheet oficial —
  hoje só tenho a palavra de uma doc de terceiros (não oficial) de que é velocidade+pacote+temp+RoHS.
- [ ] **Golden test + handshake de rentabilidade** — `_ESMT_GOLDEN` em `chips/tests.py` (rascunho abaixo,
  falta o dono ou uma sessão futura colar no arquivo real); `DDR3L` já existe em `chip_types.py`
  (`profit_family="ddr"`), então não deve precisar de handshake novo — a confirmar rodando a suíte.
- [x] **DDR2 M14D/M14F pesquisado** — 2026-08-20, ver §3.3. Gatilho: PN ao vivo do debug de estoque
  (`M14D5121632A`) veio 100% desconhecido. 6 PNs submetidos (128Mb/256Mb/512Mb×2tensão/1Gb×2interface);
  2 deles (`M14F5121632A`, `M14D1G8128A`) só com 1 fonte — revisar com atenção extra antes de aprovar.
- [x] **DDR3 M15F pesquisado** — 2026-08-20, ver §3.4. Gatilho: PN ao vivo do debug de estoque
  (`M15F1G1664A`) veio 100% desconhecido. 4 PNs submetidos (512Mb/1Gb/2Gb/4Gb x16); `chip_type=DDR3`
  (não `DDR3L` — tipo distinto do M15T, não par de voltagem simples); 2 deles (`M15F2G16128A` — só
  listagem agregada — e a nota de tensão divergente do `M15F4G16256A`) sinalizados pro dono revisar.
  `M15F4G8512A` (par x8 esperado) NÃO incluído — só 1 menção sem fonte dedicada, ver §3.4.
- [ ] **Descobrir o resto do catálogo ESMT** (SDR SDRAM M12L/M52S/M52D, DDR/LPDDR M13S/M13D, LPDDR
  M53D–M56Z, DDR4 M16U — ver §3.1) — cada um exige a mesma pesquisa Tier-1/2 do zero, nenhum foi
  verificado ainda. M15T/M15F (DDR3/DDR3L) e M14D/M14F (DDR2) já confirmados.

### Rascunho de golden (para `chips/tests.py::_ESMT_GOLDEN` — NÃO colado no arquivo real, eu não edito `.py`)

```python
# PN            → chip_type, subtype, density_gbit, rentabilidade
"M15T1G1664A"   → "DDR3L", "DDR3L", "1Gb",  <A CONFIRMAR — depende do ProfitabilityConfig atual>
"M15T2G16128A"  → "DDR3L", "DDR3L", "2Gb",  <A CONFIRMAR>
"M15T4G16256A"  → "DDR3L", "DDR3L", "4Gb",  <A CONFIRMAR>
"M15T8G16512A"  → "DDR3L", "DDR3L", "8Gb",  <A CONFIRMAR>
"M15T2G8256A"   → "DDR3L", "DDR3L", "2Gb",  <A CONFIRMAR>
"M15T4G8512A"   → "DDR3L", "DDR3L", "4Gb",  <A CONFIRMAR>
"M14D128168A"   → "DDR2",  "DDR2",  "0.125Gb", NÃO RENTÁVEL (geração DDR2, chips/engine.py — não depende do ProfitabilityConfig)
"M14D2561616A"  → "DDR2",  "DDR2",  "0.25Gb",  NÃO RENTÁVEL (idem)
"M14D5121632A"  → "DDR2",  "DDR2",  "0.5Gb",   NÃO RENTÁVEL (idem) — PN ao vivo do debug 2026-08-20
"M14F5121632A"  → "DDR2",  "DDR2",  "0.5Gb",   NÃO RENTÁVEL (idem)
"M14D1G1664A"   → "DDR2",  "DDR2",  "1Gb",     NÃO RENTÁVEL (idem)
"M14D1G8128A"   → "DDR2",  "DDR2",  "1Gb",     NÃO RENTÁVEL (idem)
"M15F1G1664A"   → "DDR3",  "DDR3",  "1Gb",  <A CONFIRMAR — depende do ProfitabilityConfig atual> — PN ao vivo do debug 2026-08-20
"M15F2G16128A"  → "DDR3",  "DDR3",  "2Gb",  <A CONFIRMAR>
"M15F4G16256A"  → "DDR3",  "DDR3",  "4Gb",  <A CONFIRMAR>
"M15F5121632A"  → "DDR3",  "DDR3",  "0.5Gb", <A CONFIRMAR>
```
Não preenchi o veredito de rentabilidade do M15T (DDR3L) nem do M15F (DDR3) — é dado mutável
(`ProfitabilityConfig`, admin) e eu não tenho visibilidade dele daqui; rodar `classify()` localmente
preenche essa coluna pros dois (mesmo `ChipTypeSpec`, confirmado §5, então devem dar o mesmo veredito entre
si, mas nenhum dos dois é fixo). Já o M14D/M14F (DDR2) **é previsível sem `ProfitabilityConfig`**: "DDR2
ou inferior → NÃO RENTÁVEL" é limiar de GERAÇÃO fixo em `assess_profitability`, não um valor configurável
no admin — por isso já preenchi o veredito.

---

## 7. Fontes de pesquisa

Ver §0.3 (hierarquia completa, ainda sem precedente testado). Confirmadas na prática (2026-08-05):
- **esmt.com.tw** (oficial) — hospeda datasheet em `/upload/pdf/ESMT/datasheets/<PN>(<rev>).pdf`; a URL
  sempre existe/resolve pros PN reais, mas o CONTEÚDO do PDF não abre via `WebFetch` (timeout/bloqueio a
  bot, recorrente em todo PN tentado até agora) — só a existência da URL serve de corroboração.
- **Alldatasheet** (`alldatasheet.com`) — mirror confiável; título já cita organização pros PNs mais
  indexados, e o CONTEÚDO da página (via `WebFetch`, tanto `/datasheet-pdf/pdf/` quanto
  `/datasheet-pdf/view/`) também cita organização quando o título não é suficiente.
- **Satron Electronics** (`satronel.com`) — distribuidor com tabela de specs por família (density,
  organização, package, voltagem, velocidade); tem alguns PNs mas não o catálogo inteiro (não tinha
  `M15T2G8256A`, por exemplo). Bom cross-check quando presente.
- **DigChip** (`digchip.com`) — aggregator; título do resultado de busca às vezes já cita densidade/tipo
  mesmo quando a página em si não abre (mesmo bloqueio do esmt.com.tw).

Confirmadas na prática (2026-08-20, rodada M14D/M14F):
- **LCSC** (`lcsc.com`) — distribuidor B2B rastreável; hospeda o PDF do datasheet oficial diretamente
  (`datasheet.lcsc.com/...`), então o CONTEÚDO abre normalmente via `WebFetch` (sem o bloqueio do
  esmt.com.tw). Bom quando o domínio oficial não abre.
- **Sekorm** (`en.sekorm.com`) — aggregator chinês; já viu uso na rodada M15T também. Título/descrição da
  página costuma citar organização completa com boa precisão (bateu exato com Alldatasheet no caso
  M14D5121632A).
- **Mirrors S3 de distribuidor** (ex. `suntsu-products-s3-bucket.s3.amazonaws.com`) — alguns
  distribuidores hospedam o PDF puro num bucket público; quando abre, é o datasheet oficial completo
  (conteúdo, não só título) e não sofre o bloqueio do domínio oficial.
- **Novitronic**, **IC-Components** — distribuidores menores com página por PN; úteis pra confirmar
  EXISTÊNCIA/ordering code, raramente têm organização detalhada.

Confirmadas na prática (2026-08-20, rodada M15F):
- **Página oficial de produtos** `esmt.com.tw/en/Products/DRAM/...` (não o PDF do datasheet, a página de
  LISTAGEM da categoria) — diferente do PDF individual (que bloqueia), essa página HTML abre normal via
  `WebFetch` e traz uma TABELA completa do catálogo atual (part number, densidade, organização, voltagem)
  — ótima fonte Tier-1 quando existe pra categoria. Não é exaustiva pra peças legadas/descontinuadas (não
  listou `M15F5121632A`/`M15F2G16128A`/`M15F4G16256A`, só o `M15F1G1664A` ainda vendido) — cruzar com
  Alldatasheet/Satron pra completar a família.
- **`satronel.com/.../ddr3-sdram.html`** — mesma família de tabela (distribuidor) já usada com sucesso na
  rodada DDR2; aqui cobriu 4 dos 5 candidatos M15F de uma vez, incluindo voltagem e package.
- **Listagem Alldatasheet por PREFIXO** (`alldatasheet.net/view.jsp?Searchword=M15...`) — retorna todos os
  PNs indexados que começam com aquele prefixo numa tabela só, cada linha já com a organização citada;
  MUITO mais eficiente que buscar PN por PN quando a família inteira é desconhecida — mas ⚠ **tratar como
  pista, não confirmação**: um PN apareceu só nessa listagem (`M15F4G8512A`) e não teve página dedicada
  nem qualquer outra fonte — não foi incluído (§3.4/§6).

Outros a tentar: Octopart, DigiKey. Evitar como fonte de capacidade: qualquer distribuidor sem rastreio
(ex. listagens de marketplace tipo Alibaba — servem só pra confirmar que o PN circula no mercado, nunca
pra spec) e resumo de IA sem verificação — mesmo cuidado que todas as outras marcas do WTC. ⚠ Qualquer
resumo de conteúdo extraído por `WebFetch` pode errar a ARITMÉTICA sozinho mesmo citando a organização
certa (visto ao vivo 2x na rodada M15T x8, e de novo na rodada M14D — o próprio `WebFetch` já chamou
"128Mb" de "8 megabits" e confundiu densidade-por-banco com densidade total) — sempre refazer a conta na
mão a partir da organização citada, nunca colar o total que a ferramenta calculou.

---

## 8. Histórico (o *porquê* — durável)

- **2026-08-05 — PN "MT5T1G1664A" não existe; era M15T1G1664A.** O dono passou esse PN como o 1º alvo da
  marca. Busca exata pela string não achou nada — só resultados sem relação. O que existe, muito
  documentado (ESMT, datasheet oficial), é `M15T1G1664A` (1 caractere de diferença, "T5"→"15"). Confirmado
  com o dono antes de prosseguir (regra: PN ambíguo nunca se decide sozinho). Provável leitura errada do
  laser-marking do chip — vale o operador conferir de novo se aparecer outro PN "MT5T*" no futuro.
- **2026-08-05 — `submit_known_parts.py` exige a `Brand` já existir, mesmo em dry-run.** Descoberto ao ler
  o comando: ele levanta `CommandError` na checagem da `Brand` ANTES do early-return de dry-run. Ou seja,
  `load_brands --brand esmt --commit` (Trilha A) tem que rodar antes de QUALQUER tentativa de
  `submit_known_parts` (Trilha B), nem que seja só validar em dry-run — diferente do que a leitura solta
  do `AUTORIA.md` sugere (as trilhas parecem independentes na descrição, mas não são na prática pra marca
  nova). Ver nota no topo deste arquivo.
- **2026-08-05 — família M15T é literal, não tabela de decode.** Diferente de SK Hynix/Samsung (código de
  1-2 caracteres + `DecodeMap`), a ESMT escreve densidade+organização por extenso no próprio PN. Modelei
  como famílias "magras" (uma por combinação densidade×organização confirmada), sem `decode_cap_pos` —
  capacidade vem de known_parts, não de decode posicional. Mesmo padrão da Nanya (NT5AD/NT5CC/NT5PA).
- **2026-08-05 — correção de doc: `density_gbit` (não `dram_density`) + SRAM≠`dead`.** O dono editou o
  `ESMT.md` direto no disco e corrigiu 2 pontos: (1) o campo de densidade DDR que EU preencho numa
  submissão é `density_gbit` — `dram_density` é derivado pelo engine, nunca uma instrução de
  preenchimento (`CLAUDE.md §6`); essa troca já tinha acontecido antes no `ISSI.md`, mesmo dia, por
  copiar a tabela do `SK_HYNIX.md` (que ainda carrega o campo errado) sem cruzar contra o `CLAUDE.md`
  primeiro — 2ª ocorrência do mesmo erro. (2) a regra de ouro #12 dizia "catálogo/dead (NOR Flash,
  SRAM…)", mas só NOR Flash é `profit_family="dead"` — SRAM é `"indeterminado"` (`chip_types.py`).
  Internalizado antes de seguir pra próxima rodada de pesquisa.
- **2026-08-05 — 2ª rodada: variantes x8 confirmadas (`M15T2G8256A`, `M15T4G8512A`).** Na 1ª rodada só
  tinha dedução por padrão de nomenclatura pros x8 (sem citação direta → ficaram de fora, regra "excluir,
  não adivinhar"). Nesta rodada usei `WebFetch` no CONTEÚDO do datasheet (não só o título) e consegui
  citação direta de organização pros dois. `M15T4G8512A` ganhou 2 fontes independentes extras — tabela da
  Satron Electronics (`satronel.com`, Density 4Gb/Organization "512Mbx8") e o título indexado do DigChip
  ("4Gb DDR3(L) SDRAM") — batendo com a aritmética. `M15T2G8256A` não apareceu em nenhuma fonte de
  terceiro (nem na mesma tabela da Satron, que lista o irmão) — confiança menor, só Alldatasheet, mas
  ainda acima da barra usada pros outros 4 PNs desta família (mesma combinação Alldatasheet + PDF-oficial-
  existente-mas-bloqueado). Sinalizado explicitamente pro dono revisar esse PN com atenção extra antes de
  aprovar. `submissions/esmt_m15t_x8_2026-08-05.yaml` é um arquivo NOVO (não editei o já entregue/possivel-
  mente já consumido da 1ª rodada — `submissions/` é formulário de uso único, não re-sincroniza).
- **2026-08-20 — 3ª rodada: família DDR2 M14D/M14F, disparada por PN ao vivo do debug de estoque.** O dono
  colou a saída do debug de `M14D5121632A` (100% desconhecido, `in_review_queue: true`) e pediu pra
  pesquisar "ele e todos os irmãos e primos", **Tier-1 OU Tier-2** (barra mais solta que as rodadas
  anteriores — só Tier-1). Antes de pesquisar, resinquei TUDO do disco (duas semanas tinham se passado
  desde a última rodada — `chip_types.py`/`engine.py`/`schema.py` já tinham mtimes mais recentes que a
  última entrega) em vez de confiar no cache local, aplicando a lição de [[wtc-reler-antes-sobrescrever-doc-compartilhado]]
  antes mesmo de reescrever qualquer coisa. Achados: (1) família confirmada — mesmo padrão literal do
  M15T, densidade+organização no próprio PN, mas em Mb (sub-1Gb) — ver §3.3; (2) tabela da Satron
  (`satronel.com`) deu o catálogo quase inteiro de uma vez (6 combos), cross-validada contra Alldatasheet/
  LCSC/Sekorm/Suntsu-PDF nos PNs mais documentados; (3) **achado metodológico com potencial impacto
  cross-marca:** `density_gbit` sub-1Gb precisa ser fracionário em `"Gb"` (`"0.5Gb"`, não `"512Mb"`) pro
  parser `_extract_gbit`/`_GBIT_RE` do engine reconhecer — provado rodando o regex real contra os dois
  formatos no ambiente standalone; nenhuma família ESMT anterior tinha densidade sub-1Gb, então essa
  armadilha nunca tinha aparecido nesta marca (mas pode já afetar OUTRAS marcas com known_parts DDR
  sub-1Gb — registrado na memória do projeto pra checar); (4) M14F = par de voltagem do M14D (1.55V vs
  1.8V), prefixo separado (diferente do M15T/DDR3(L)) — mapeia pra `chip_type=DDR2` igual ao M14D, já que
  `"DDR2L"` não existe no vocabulário (confirmado pelo portão, não decisão arbitrária); (5) DDR2 inteiro é
  sempre NÃO RENTÁVEL por GERAÇÃO (`assess_profitability`), não por tipo-morto categórico como SDRAM puro
  — mesmo efeito final do NT5TU da Nanya, mecanismo diferente, não confundir (§5). 2 dos 6 PNs
  (`M14F5121632A`, `M14D1G8128A`) só tiveram 1 fonte apesar de busca dedicada — sinalizados pro dono
  revisar com atenção extra, mesmo padrão do `M15T2G8256A` na rodada anterior.
- **2026-08-20 — 4ª rodada, mesmo dia: família DDR3 M15F, disparada por PN ao vivo do debug de estoque.**
  Poucas horas depois da rodada M14D, o dono colou a saída do debug de `M15F1G1664A` (100% desconhecido,
  `fuzzy_suggestions` apontando `M15T1G1664A` e `M14D1G1664A` — nenhum dos dois é o PN real). Resinquei
  `ESMT.md`/`esmt.yaml`/`chip_types.py`/`engine.py` do disco antes de editar (mesmo dia da rodada
  anterior, sem gap — mas a disciplina vale de qualquer forma); nenhum mtime tinha mudado desde a última
  entrega, sem drift. Achados: (1) família confirmada — mesmo padrão literal, mas aqui a "letra da
  família" (T vs F) NÃO segue o padrão do M14D/M14F: pensei em mapear `M15F` pra `DDR3L` por analogia
  direta com "F = par de voltagem", mas ao CONFIRMAR o vocabulário (`chips/chip_types.py`) descobri que
  `DDR3` e `DDR3L` são chip_types DISTINTOS (diferente do `DDR2`/inexistente-`DDR2L`) — decisão certa foi
  `chip_type=DDR3`, baseada em toda citação de datasheet chamar a família de "DDR3 SDRAM" (sem "(L)") e
  na única tensão confirmada (`M15F1G1664A`, página oficial) ser 1.5V-only, não dual; (2) a página oficial
  de LISTAGEM de produtos (`esmt.com.tw/en/Products/DRAM/...`, não o PDF individual) abriu normalmente via
  `WebFetch` e deu uma tabela Tier-1 completa do catálogo ATUAL — só não é exaustiva pra peças legadas; a
  tabela da Satron (mesmo padrão já usado no DDR2) preencheu o resto; (3) **achado de processo:** uma
  listagem agregada do Alldatasheet por prefixo citou `M15F4G8512A` (par x8 esperado) mas o PN não tem
  página dedicada nem qualquer outra fonte — tratei como pista não confirmada e EXCLUÍ da submissão (regra
  de ouro #12), em vez de confiar cegamente na listagem; (4) uma única divergência de tensão não resolvida
  (`M15F4G16256A`: Satron diz "1.35V/1.5V", Alldatasheet+Sekorm chamam de "DDR3" sem "(L)") — documentada
  e sinalizada em vez de escolhida em silêncio. 4 PNs submetidos (512Mb–4Gb, todos x16); 2 sinalizados pro
  dono revisar com atenção extra (`M15F2G16128A` por sourcing fino, `M15F4G16256A` pela divergência de
  tensão).

> O inventário de chaves/mapas vai viver no **`esmt.yaml`** (gramática, quando existir); os **known_parts**
> confirmados (com a proveniência Tier-1 nas `notes`) vivem no **banco** (Opção 2), submetidos via
> `submit_known_parts`. Tudo que é cross-marca (comandos, convenção, rentabilidade, arquitetura) está no
> **`CLAUDE.md`** — o único `.md` mantido nesse papel, e é quem aponta pro `AUTORIA.md`.

---

> **Regra de trabalho:** eu crio/edito o `esmt.yaml`. O dono roda `load_brands --brand esmt` (sempre
> dry-run antes do `--commit`) e o `submit_known_parts` (idem). **Estado em 2026-08-20:** 3 famílias
> confirmadas (M15T/DDR3L, M14D+M14F/DDR2, M15F/DDR3 — 16 prefixos, 16 known_parts submetidos em 4
> rodadas) — mas o resto da escada de prefixo (§3.1: M12L, M13S/M13D, M16U, M53D–M56Z) segue **sem nenhum
> precedente confirmado**. Continua valendo pra QUALQUER prefixo novo: atestar a IDENTIDADE em Tier-1/2
> antes de qualquer decode, nunca extrapolar chave por padrão numérico nem por analogia com outra marca ou
> com outro prefixo ESMT já confirmado — a analogia M14D/M14F→M15T/M15F quase levou a mapear `M15F` pro
> `chip_type` errado (`DDR3L` em vez de `DDR3`) nesta própria rodada, só não aconteceu porque o vocabulário
> foi checado antes de decidir (regra de ouro #9).
