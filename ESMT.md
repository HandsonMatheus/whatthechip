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
> ⚠️ **Estado em 2026-08-05: 1ª família mapeada (M15T — DDR3(L) SDRAM), ainda NÃO carregada no sistema.**
> `chips/knowledge/esmt.yaml` (rascunho, 4 famílias) e `submissions/esmt_m15t_2026-08-05.yaml` (4
> known_parts) já existem e passaram no portão Pydantic (validado standalone, fora do Django) — falta
> rodar `load_brands --brand esmt` (dry-run) no ambiente local real antes de qualquer `--commit`. §3/§6/§8
> atualizados com o que foi confirmado; o resto da marca (outros prefixos/tipos) continua esqueleto.

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
    regra sem exceção, mesmo para tipo catálogo/dead (NOR Flash, SRAM…) onde a capacidade não muda o
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
| DDR1–5 / SDRAM | a geração (`DDR2`, `DDR3`…) ou `"SDRAM"` (legado, sempre NÃO RENTÁVEL) | espelha | bus width (`x8`/`x16`/`x4`) | `dram_density` (Gb/die) |
| LPDDR standalone (se houver) | a geração (`LPDDR4X`…) | espelha | `""` | `capacity` (pacote, bytes) |
| eMMC / UFS (se houver) | `"eMMC"`/`"UFS"` | `""` | versão (`"eMMC 5.1"` etc.) | `capacity` (GB) |
| eMCP / uMCP (se houver) | `"eMCP"`/`"uMCP"` | geração RAM | `""` | `emcp_nand` (GB) + `emcp_ram` (tipo+GB) |
| SRAM / NOR Flash / catálogo (prováveis pelo perfil industrial) | `"SRAM"`/`"NOR Flash"`/etc. | descritivo (categoria `catalog` — chip_type MANDA, não normaliza) | — | conforme o tipo |

**Regras absolutas** (idênticas em todo o WTC): `subtype` nunca carrega densidade/bus width/tensão/
qualificador de mercado. `dram_density` = Gb por die. `capacity` = pacote em bytes, nunca Gbit.
`emcp_ram` = `"LPDDR{n} {cap}GB"` (tipo antes). `tip`/`notes` = todo o resto (tensão, velocidade,
organização, avisos, proveniência).

**Label da caixa** (referência, mesmo padrão de todas as marcas): DDR `{subtype}+{dram_density Gb}G` ·
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
M14D / M14F          → DDR2 SDRAM
M15T / M15F          → DDR3 / DDR3L SDRAM  ← a família confirmada abaixo
M16U                 → DDR4 SDRAM
M53D                 → LPDDR
M54D                 → LPDDR2
M55D                 → LPDDR3
M56Z                 → LPDDR4X
```
Cada prefixo dessa lista precisa da MESMA verificação Tier-1 antes de virar família na gramática — isso é
só um mapa de onde procurar "outros tipos" no futuro, não uma confirmação.

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

O número final (64/128/256/512) bate exatamente com "total de palavras em M por todos os 8 bancos" em
todos os 4 PNs — **isso é dedução minha por cruzamento aritmético entre os 4 PNs, não uma tabela oficial
que eu tenha lido** (não consegui abrir o PDF oficial pra confirmar letra a letra; ver §6). Também existem
variantes **x8** na mesma família (`M15T2G8256A`, `M15T4G8512A` — datasheet oficial confirma que existem,
mas não abri o conteúdo pra confirmar a organização com meus próprios olhos → não submetidas ainda,
ver `submissions/esmt_m15t_2026-08-05.yaml` rodapé "NÃO submetidos").

⚠ **Sufixo de pedido** (`-DEBG2C`, `-DIBG` etc., depois do "A" final) codifica velocidade+pacote+
temperatura+RoHS segundo uma doc de terceiros (GitHub, não oficial) — **não confirmado letra a letra**.
`normalize_pn("M15T1G1664A-DEBG2C")` → `"M15T1G1664ADEBG2C"` (confirmado rodando a função de verdade) —
ou seja, o prefixo literal sobrevive à normalização, então o match por `prefix` deve funcionar mesmo com
sufixo, mas não testei o `_match_family` do engine de verdade (precisa do Django completo).

⚠ **Tensão dupla:** a ESMT descreve a família inteira como **"DDR3(L)"** — um PN só que opera em 1.5V
(DDR3) OU 1.35V (DDR3L), diferente da SK Hynix (que separa H5TQ/H5TC em prefixos distintos por tensão).
**Decisão do dono (2026-08-05): registrar como `DDR3L`** no nosso `chip_type`/`subtype`.

---

## 4. Armadilhas e Decisões Arquiteturais

**[A PREENCHER]** — nenhuma armadilha ESMT-específica confirmada ainda; esta seção cresce conforme a
pesquisa avança (mesmo padrão do `SK_HYNIX.md §3`). Enquanto isso, de olho nas armadilhas **sistêmicas**
já provadas em outras marcas (`CLAUDE.md §7`) — têm boa chance de reaparecer aqui:

- Unidade Gb×GB confundida (o erro mais comum do domínio inteiro).
- `decode_density_type` + `decode_cap_map` juntos na mesma família (mutuamente exclusivos).
- Tipo/geração morta retornando INDETERMINADO em vez de NÃO RENTÁVEL (checar geração ANTES de exigir
  capacidade, se a ESMT tiver famílias legadas descontinuadas — SDRAM puro já é sempre NÃO RENTÁVEL por
  tipo, `chip_types.py`).
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
- [ ] **Confirmar organização das variantes x8** (`M15T2G8256A`, `M15T4G8512A`) com fonte direta antes de
  incluir na submissão — hoje ficam de fora (ver §3.2).
- [ ] **Decodificar o sufixo de pedido** (`-DEBG2C` etc.) letra a letra contra o datasheet oficial —
  hoje só tenho a palavra de uma doc de terceiros (não oficial) de que é velocidade+pacote+temp+RoHS.
- [ ] **Golden test + handshake de rentabilidade** — `_ESMT_GOLDEN` em `chips/tests.py` (rascunho abaixo,
  falta o dono ou uma sessão futura colar no arquivo real); `DDR3L` já existe em `chip_types.py`
  (`profit_family="ddr"`), então não deve precisar de handshake novo — a confirmar rodando a suíte.
- [ ] **Descobrir o resto do catálogo ESMT** (SDR SDRAM M12L, DDR2 M14D, LPDDR M53D–M56Z, DDR4 M16U —
  ver §3.1) — cada um exige a mesma pesquisa Tier-1 do zero, nenhum foi verificado ainda.

### Rascunho de golden (para `chips/tests.py::_ESMT_GOLDEN` — NÃO colado no arquivo real, eu não edito `.py`)

```python
# PN            → chip_type, subtype, density_gbit, rentabilidade
"M15T1G1664A"   → "DDR3L", "DDR3L", "1Gb",  <A CONFIRMAR — depende do ProfitabilityConfig atual>
"M15T2G16128A"  → "DDR3L", "DDR3L", "2Gb",  <A CONFIRMAR>
"M15T4G16256A"  → "DDR3L", "DDR3L", "4Gb",  <A CONFIRMAR>
"M15T8G16512A"  → "DDR3L", "DDR3L", "8Gb",  <A CONFIRMAR>
```
Não preenchi o veredito de rentabilidade — é dado mutável (`ProfitabilityConfig`, admin) e eu não tenho
visibilidade dele daqui; rodar `classify()` localmente preenche essa coluna.

---

## 7. Fontes de pesquisa

Ver §0.3 (hierarquia completa, ainda sem precedente testado). Ponto de partida: site oficial + datasheets
ESMT (domínio a confirmar), Octopart, Alldatasheet, LCSC, DigiKey. Evitar como fonte de capacidade:
qualquer distribuidor sem rastreio e resumo de IA sem verificação — mesmo cuidado que todas as outras
marcas do WTC.

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

> O inventário de chaves/mapas vai viver no **`esmt.yaml`** (gramática, quando existir); os **known_parts**
> confirmados (com a proveniência Tier-1 nas `notes`) vivem no **banco** (Opção 2), submetidos via
> `submit_known_parts`. Tudo que é cross-marca (comandos, convenção, rentabilidade, arquitetura) está no
> **`CLAUDE.md`** — o único `.md` mantido nesse papel, e é quem aponta pro `AUTORIA.md`.

---

> **Regra de trabalho:** eu crio/edito o `esmt.yaml`. O dono roda `load_brands --brand esmt` (sempre
> dry-run antes do `--commit`) e o `submit_known_parts` (idem). **Ponto mais importante:** esta marca não
> tem NENHUM precedente confirmado ainda — atestar a IDENTIDADE em Tier-1 antes de qualquer decode, nunca
> extrapolar chave por padrão numérico nem por analogia com outra marca (regra de ouro #9).
