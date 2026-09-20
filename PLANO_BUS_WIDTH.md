# PLANO_BUS_WIDTH.md — separar LARGURA (`bus_width`) de PROTOCOLO (`interface`)

**Para:** o executor (Opus 5, outro chat) · **Autor:** Fable, sessões de 2026-09-12 e
2026-09-15 · **Dono:** Raphael/Handson (eMiner) · **Estado:** decisões travadas (§1 e
§10.1), diagnóstico verificado no código (§2 e §10.2), fases prontas para executar
(§4 = Parte 1, §10.4 = Parte 2).

> ### REVISÃO 1 — 2026-09-15 (leia antes de tudo)
> Em 13–14/09 o comprador (Wu Quan, SO EMIN-SO-2026-0007) revelou que a largura **muda
> preço, rentabilidade e caixa**: chips de **78 bolas (= x4/x8)** de DDR3 valem zero em
> 1Gb (recusa), ¥0,50 em 2Gb e ¥1 em 4Gb, contra ¥2/¥3/¥4 dos de 96 bolas (x16); DDR4/DDR5
> não sofrem desconto; foi −¥6.399 (−15,2%) num lote de 10.000 peças. Fonte:
> o **Apêndice D** deste arquivo (cópia integral do `CONHECIMENTO_largura_preco_rentabilidade.md`,
> procedência marcada linha a linha pelo autor original).
>
> Consequências para este plano:
> - **D1 caiu.** Largura entra no preço, na caixa (código E-##, eterno), na rentabilidade
>   e na linha da venda. Isso é a **Parte 2** (§10), que só começa depois da Parte 1 inteira.
> - **A Parte 1 (§4) continua sendo a fundação e a ordem não muda**, mas ganhou **sete
>   emendas** (marcadas `[Rev.1]` no texto): E1 gramática de largura em família PROVADA
>   (engine decodifica em leitura, como densidade); E2 `bus_width_source` no resultado;
>   E3 `bless_base` e a aprovação de `PendingEntry` **nunca** copiam largura para o
>   catálogo; E4 os 3 modelos de lote ganham também `width_class` + `bus_width_source`;
>   E5 o 25º canal de escrita (`estoque/admin.py:15-40`); E6 I4 reescrito; E7 o
>   `characterize_baseline` captura `bus_width_source`.
> - Decisões novas do dono (2026-09-15): D9–D12 em §10.1.
> - Esta Rev.1 substitui o texto de 12/09 **no mesmo arquivo** (ele ainda não tinha sido
>   commitado); não existe "v0" para consultar — o que vale é o que está aqui.

> ### REVISÃO 2 — 2026-09-19 (as duas telas do comprador)
> O dono perguntou como a largura entra na **tabela de preços** e na **tela da compra** do
> comprador. O estudo está no **§10.7**, feito lendo o código; ele acrescenta D13–D15 e
> **substitui a P5 no ponto do 8Gb estreito** (nasce como linha em branco, não "sem linha").
> Achado que vale por si: quatro dicionários do sistema são chaveados pela chave de preço
> SEM a largura e perderiam uma das duas linhas **em silêncio** (§10.7.1) — o eMMC só não
> cai nisso porque partiu a tela em duas seções em vez de alargar a matriz. Nada na Parte 1
> muda por causa desta revisão.

> Este plano substitui o `DOSSIE_bus_width_para_Fable.md` como fonte da tarefa. O
> dossiê acertou o diagnóstico central e errou em três pontos que mudam o desenho
> (§2.0). Onde os dois divergirem, vale este plano — e onde este plano divergir do
> código, vale o código (CLAUDE.md §10). Todo número daqui que veio de amostra está
> marcado como amostra; o banco real se mede na Fase 0, antes de qualquer edição.

---

## 0. Como usar este plano (leia antes de abrir um arquivo)

1. **Leia `CLAUDE.md` inteiro** (1.348 linhas) antes de editar qualquer coisa. Este
   plano aponta seções dele em vez de repeti-las. Em especial: §2 (regras de ouro 1,
   1b, 2b, 3, 12), §5 (comandos, deploy, contrato de autoria), §6 (convenção de
   campos), §7 (as armadilhas de RLS, de migração à frente do deploy, de campo de
   medida e de "vocabulário fora do modelo").
2. **Contrato de operação — não se negocia** (é o mesmo do dossiê §10 e do
   `HANDOFF_largura_barramento.md` §2):
   - **TRAVA DE ESCRITA.** Você nunca escreve no catálogo direto (shell, ORM, admin).
     Gramática = yaml → `load_brands`; known_parts = `submit_known_parts` → aprovação.
     O backfill desta tarefa é a exceção justificada — e mesmo assim **quem roda é o
     dono**, depois de ver o dry-run.
   - **Quem roda comando que grava é o dono.** Você prepara, explica, entrega com
     dry-run. Nunca peça `--commit` sem ter mostrado o dry-run.
   - **Nada vai para produção sem passar pelo local.** `env -u DATABASE_URL` = Postgres
     local; `DATABASE_URL` exportado = Render. Todo script que toca banco imprime o
     banco-alvo na primeira linha (`core/safe_command.py::SafeWriteCommand` faz isso
     para comandos; scripts avulsos copiam o banner do `COLETAR_largura_bits.py:150`).
   - **Zero alto.** Ler 0 linhas nunca é "não tem" — é leitura que não aconteceu.
     Aborte vermelho. (Catálogo é GLOBAL, sem RLS; estoque tem RLS — §2.6.)
   - **Verificar antes de afirmar.** Mostre a conta. O dono prefere "não sei" a
     número bonito e errado; nesta sessão ele pegou dois erros do dossiê por
     aritmética própria.
   - **Português do Brasil** em código, docstrings, mensagens e neste plano.
   - **Migração de banco em produção roda SÓ no build do Render** (push → migrate).
     Nunca `migrate` local apontando para prod com código à frente do deploy
     (CLAUDE.md §7, incidente eRecyclo LOT/001: `AddField NOT NULL` + código antigo =
     INSERT recusado em silêncio). Isto vale para as duas migrations deste plano.
   - **Não crie arquivos de nota na raiz** além do que este plano pede (CLAUDE.md
     §10). O que for regra durável vai para a seção certa do `CLAUDE.md`.
3. **Ordem é lei.** As fases têm portas (§5). Pular uma porta é exatamente como
   este projeto perdeu 5.900 known_parts em julho e meio-migrou o pricing em agosto.
4. **Testes durante e ao fim de cada fase** (`wtc-convencao-testes`): suíte inteira
   `python manage.py test chips estoque --settings=core.settings_test`, o golden por
   família, o `characterize_baseline --diff` com as TRÊS COLUNAS intactas, e um
   conjunto de testes de frontend/terminal entregue ao dono no fim de cada fase.
5. **Sandbox não tem Django** (`wtc-device-bash-sem-django-manage-py`): você entrega os
   comandos prontos; quem roda no terminal dele é o dono. Você edita arquivos e escreve
   testes; a prova roda na máquina dele.

---

## 1. Decisões travadas pelo dono (2026-09-12)

| # | Pergunta | Decisão |
|---|---|---|
| D1 | O que a feature faz com a largura | **[Rev.1 — REVISADA]** Na **Parte 1**: `bus_width` em `KnownPart`/`ChipFamily`, engine copia para o resultado, card da bancada ganha "Largura", torneira RAM pode ler; **preço, caixa e rentabilidade NÃO mudam na Parte 1** (o baseline tem de dar três colunas intactas). Na **Parte 2** (§10) a largura entra no preço, na caixa e na rentabilidade — decisão do dono em 2026-09-15 depois do conhecimento do comprador. |
| D2 | Procedência (§7.1 do dossiê) | **Sem coluna extra.** Procedência = `confidence` do registro + fonte Tier-1 nas `notes`, igual a `capacity`/`density_gbit`. Regra escrita no portão e nos docs: **o banco NUNCA recebe largura derivada do PN** — é a lei do próprio coletor (circularidade). Os "41 por regra" da Samsung vivem na planilha, não no banco. |
| D3 | Submissão com `interface: x16` depois da migração | **Rejeitar no dry-run**, com a correção na mensagem ("largura vai em `bus_width`"). O chat corrige o arquivo. Arquivo antigo (há 113 em `submissions/`) re-rodado com `--fill-empty` falha até ser editado — de propósito. |
| D4 | Micron `"x16 @ 800MHz (1600MTPS)"` | `bus_width='x16'`; o resto vira **`notes` → `Speed: 800MHz (1600MTPS)`** (mesmo formato `k: v \| k: v` das notes da Micron); `interface` fica vazio. Os registros com **só** velocidade (`"@ 1866MHz (...)"`) seguem a mesma regra. |
| D5 | Largura fora de DRAM discreta (NAND, LPDDR) | Delegado ao Fable: **pesquisado e decidido em §3.2** — `bus_width` é largura de I/O de qualquer classe que tenha **um** barramento de dados; gerenciados ficam vazios (portão). |
| D6 | Estoque (lotes) | **Coluna `bus_width` nos 3 modelos de lote, só daqui para a frente.** Migration aditiva, sem backfill, histórico intocado. Linha antiga continua com `x16` em `interface`. |
| D7 | Os 25 yamls de família com `interface: xN` | **O executor edita os 3 yamls no mesmo PR** (renomeação mecânica, sem fato novo); dry-run do `load_brands` mostra o diff; o dono roda `--commit`. |
| D8 | Vocabulário fechado | **`x4 · x8 · x16 · x32 · x64`** (+ vazio). `CheckConstraint` no banco. |

Decisões já do dossiê que continuam valendo: não reescrever histórico de lote (D6
respeita); `interface` continua sendo o campo de **versão de protocolo** (eMMC 5.1,
UFS 3.1 — "a versão do eMMC vale dinheiro", 2026-08-27); a linha "Largura" no card
é obrigatória se o move acontecer (D1 confirma).

**[Rev.1] Decisões de 2026-09-15 (Parte 2 — detalhadas em §10.1):** D9 preço e caixa
usam a **classe** de largura (`narrow` = x4/x8 · `wide` = x16), o catálogo continua
exato; D10 DDR3 estreito ganha **código de caixa novo**, o código atual passa a
significar x16; D11 largura desconhecida na bancada → **foto frente/verso → fila de
revisão no Django admin**, chip fica **INDETERMINADO** até a revisão; D12 DDR3 estreito
segue **RENTÁVEL** ao preço baixo, com limiar novo editável no admin
(`ddr3_narrow_min_gbit`, default 2 Gb — abaixo disso é sucata; cobre a recusa do 1Gb).

---

## 2. Diagnóstico verificado (arquivo:linha, repo em 2026-09-12, HEAD `e9f90fb`)

### 2.0 Três correções ao dossiê — mudam o desenho

**C1. `KnownPart.interface` NÃO chega à tela quando o PN tem família.**
`chips/engine.py:766 _result_from_known` copia do KnownPart só `capacity`/
`dram_density` (944-947), `device` (949-950), `subtype` quando `human_verified` (961-962),
`confidence`/`source_url` (952-953). O `interface` do resultado vem de
`_result_from_family` (483: `"interface": fam.interface`; 523: geração decodificada
para eMMC/UFS). Os quatro pontos do dossiê (1544, 1591, 1644, 1688) são só os caminhos
**known SEM família** e **FBGA**. Isto já estava na memória do projeto
(`wtc-known-part-interface-nao-aparece-classify`: K4B1G0846I com `x8` no banco →
`classify()` devolve `""`). Consequência dupla:
- o "ouro" da Samsung (93 K4B com largura) está **invisível hoje** — o move não é
  regressão de tela para ele, é a primeira vez que ele aparece;
- `bus_width` só aparece na bancada se `_result_from_family` **e** `_result_from_known`
  forem ensinados a copiá-lo (§4 F2). É comportamento **novo**, não preservação — e o
  baseline vai mostrar isso na coluna `bus_width` (não nas três colunas).

**C2. A Micron grava LARGURA + VELOCIDADE no mesmo campo.**
`chips/management/commands/import_micron_catalog.py:156-164 _build_interface` monta
`"x16 @ 800MHz (1600MTPS)"` a partir de `BUS WIDTH` + `SPEED` + `MT/s` do CSV oficial
(docstring: linha 19). No baseline de agosto (`baseline_pre_t6.json`, 7.843 PNs, saída
do `classify()`) existem **949** valores da forma `xN @ NMHz (NMTPS)` (LPDDR5 744,
DDR5 194, DDR3 11) e **~41** só com velocidade (`@ NMHz (NMTPS)` 35, `@ NSR` 6). O
regex do dossiê (`^x(4|8|16|32|64)$`) classificaria tudo isso como PROTOCOLO e a
migração passaria por cima. Pior: **a velocidade só existe ali** — `_build_notes`
(168-178) grava Voltage/Package/Config/Protocol/Temp/Status, não Speed. Descartar seria
"sobra sem destino = dado apagado em silêncio" (CLAUDE.md §7). Daí D4.

**C3. `bless_base` é um 24º canal de escrita.**
`estoque/management/commands/bless_base.py:199` promove entrada de lote a KnownPart
copiando `interface=e.interface` — o `x16` gravado no lote em agosto voltaria para o
campo errado a cada avalização. Não está na lista de 23 do dossiê (que só olhou
`chips/management/commands/`). Idem, do lado do estoque: `fix_pns.py:74/85/258/278`,
`clean_lote.py:192/228`, `resnapshot_lote.py:39/49`, `reconcile_lote_039.py:72`,
`estoque/admin.py:37/109/142` carregam listas explícitas com `interface`. **[Rev.1] E
há um 25º:** a aprovação de `PendingEntry` no admin (`estoque/admin.py:15-40`) faz
`KnownPart.objects.update_or_create(... interface=pend.interface ..., confidence="manual")`
— promove o snapshot do lote a catálogo, igual ao `bless_base`.

E duas boas notícias, também verificadas:
- **Preço e rentabilidade não leem `interface`.** `assess_profitability`
  (`chips/engine.py:1085`) não referencia o campo; em `pricing/` a única ocorrência é
  um comentário de `pdf.py:357`. O golden `_ident()` (`chips/tests.py:1576`) também
  não inclui `interface`. As TRÊS COLUNAS (destino/rentabilidade/chave de preço) ficam
  intactas **por construção** — e o `characterize_baseline --diff` prova.
- O único consumidor "escondido" é o fallback `gen = … or result.get('interface')` em
  `estoque/views.py:572-574` (`_compute_destination`). Medido no baseline de agosto:
  **0 labels começam com `x`** — o fallback não é atingido por largura hoje.

### 2.1 O que `interface` é hoje (o modelo assumido, não descuido)

| onde | o que diz |
|---|---|
| `chips/models.py:75` (`ChipFamily`) e `:215` (`KnownPart`) | `TextField(blank=True, default="")`, sem constraint, sem `help_text`. Nasceu na `0001_initial`. |
| `chips/admin.py:45-50` | descrição do campo na família: *"versão do padrão de armazenamento — ex: 'eMMC 5.1', 'UFS 3.1'"* → **protocolo**. |
| `CLAUDE.md:482` e `:589` | *"`interface` = largura (`x8`/`x16`) ou vazio"* / *"bus width para DDR/GDDR; vazio para LPDDR eMCP"* → **largura**. |
| `estoque/views.py:127-136 _clean_interface` | *"`interface` no estoque = bus width (x16) ou versão (eMMC 5.1)"* → **os dois**. |
| `chips/conventions.py:47-53 is_ram_generation` + `chips/knowledge/convention.py:160-161` + `schema.py:164-166` | a única trava é **negativa**: `interface` não pode ser geração de RAM. |
| `chips/engine.py:615` `(fam.interface or "eMMC").split("+")[0]` e `:872-886` | o engine **depende** de `fam.interface` ser protocolo para montar `emcp_nand` ("eMMC 5.1 64GB") e decidir UFS×eMMC. |
| `normalize_convention.py:56-66, 151-159` | a 2ª exceção "campo fora do lugar" **move protocolo do `subtype` para o `interface`** e desiste do registro se houver conflito. |
| `resolve_conflicts.py:69` `_MAIS_ESPECIFICO = {"interface"}` | política "o mais longo vence" — feita para `'x16 @ 800MHz (1600MTPS)'` ganhar de `'x16'`. |

Ou seja: dois modelos de catálogo e três de estoque aplicam **o mesmo campo com duas
semânticas**, de forma consistente. A tarefa é separar as semânticas, não "limpar".

### 2.2 O conteúdo real — amostra e baseline (o banco se mede na Fase 0)

Seed curado (`seed_known_parts.json`, 596 PNs, **amostra**): 154 `xN` (todos em
`chip_type` DDR*/GDDR*, mais 1 NAND `KF98G16Q4X`), 174 protocolo, 268 vazio — bate com
o dossiê.

Baseline de agosto (`baseline_pre_t6.json`, 7.843 PNs, saída do `classify()`, **não**
o campo do banco): **1.581 PNs mostram largura na tela hoje** — 632 `xN` puro + 949
`xN @ …`. Por fonte: 1.514 known-sem-família (Micron via FBGA/PN cheio), 57
known-com-família (a **família** carrega o `xN`: ESMT/Foresee/Samsung GDDR), 10
gramática. Por valor: x64 375 · x32 404 · x16 382 · x8 340 · x4 80 (soma 1.581; o x64 é
LPDDR5 Micron — daí D8). Por tipo: LPDDR5 744 · DDR2 339 · DDR5 194 · DDR3 166 ·
SDRAM 63 · GDDR3 30 · GDDR5 24 · GDDR6 12 · DDR3L 8 · GDDR5X 1.

Famílias com `interface: xN` no yaml (verificado com grep): **25 — ESMT 21, Samsung 3
(K4G x32, K4W x16, K4Z x32), Foresee 1 (F60C x16)**. Fora do padrão e **fora deste
move**: `K9C` `"NAND (x8/x16)"` e `K9HDG` `"NAND (x8)"` (samsung.yaml:1171/1243 —
descrição, não token; decisão do dono depois), `ACR`/`KF` da Kingston (`"DDR3 / DDR4"`,
famílias bogus inativas).

Submissões: **113 arquivos** em `submissions/*.yaml` contêm `interface: xN`
(contagem de linhas yaml+submissions: x16 819 · x8 575 · x4 240 · x32 105 · x64 17).
São histórico versionado; com D3, um re-`submit` deles falha até serem editados.

### 2.3 Onde `interface` nasce — TODOS os canais de escrita (24)

Legenda: **T** = ensinar `bus_width` (lista explícita de campos); **R** = rotear largura
para `bus_width` no write-time (usa `split_bus_width`, §3.4); **—** = nada a fazer.

| canal | arquivo:linha | hoje | ação |
|---|---|---|---|
| portão Pydantic (yaml/submissão) | `chips/knowledge/schema.py:70` (FamilySpec), `:184` (KnownPartSpec), `:164-166` | `interface` livre; só barra geração de RAM | **T + rejeitar** `interface` com largura (D3) |
| portão do modelo | `chips/models.py:284 clean()` → `chips/knowledge/convention.py:132 apply_kp_convention` | idem | **T + rejeitar** (só quando o valor MUDOU — grandfather, §4 F2) |
| `load_brands` | `load_brands.py:51 _FAMILY_FIELDS`, `:59 _KNOWNPART_FIELDS` | upsert do yaml | **T** (família); T no known (legado, nenhum yaml tem) |
| `submit_known_parts` | `submit_known_parts.py:80 _FIELDS` | 13 campos | **T** |
| `audit_submissions` | `audit_submissions.py:45 _CAMPOS`, `:59 _CLASSE` | `interface: "texto"` | **T** (`bus_width: "identidade"`) |
| `resolve_conflicts` | `resolve_conflicts.py:66-70` | `interface` = mais específico | **T** (`bus_width` ∈ `_ARQUIVO_VENCE`) |
| `dedupe_known_parts` | `dedupe_known_parts.py:39 _FIELDS` | revert/merge | **T** |
| `purge_enriched` | `purge_enriched.py:130` | backup JSON | **T** |
| `restore_purge` | `restore_purge.py:35 FIELDS` | restaura do backup | **T** |
| `restore_known_parts` | `restore_known_parts.py:22 _FIELDS`, `:79` | gap-fill + `apply_kp_convention` | **T** |
| `import_micron_catalog` | `import_micron_catalog.py:156-164, 168-178, 266, 482, 505, 624` | `interface = "x32 @ 1866MHz"` | **T + R**: `bus_width ← BUS WIDTH`; `Speed:` nas notes; `interface` só protocolo |
| `import_samsung_psg` | `import_samsung_psg.py:126, 194, 247, 300` | coluna `interface` do CSV | **T + R** (`split_bus_width` na leitura) |
| `normalize_convention` | `normalize_convention.py` (inteiro) | 2 exceções "campo fora do lugar" | **vira a 3ª exceção** (§4 F3) |
| `characterize_baseline` | `characterize_baseline.py:70` | captura `interface` | **T** (nova coluna `bus_width`) |
| `audit_campo_forma` | `audit_campo_forma.py:453` | relatório | **T** |
| `bless_base` (estoque→catálogo) | `estoque/management/commands/bless_base.py:199` | `interface=e.interface` | **R** (lote legado com `x16` no `interface` → `bus_width`) |
| `fix_pns` | `fix_pns.py:74, 85, 258, 278` | snapshot de lote | **T** (lado lote, D6) |
| `clean_lote` | `clean_lote.py:192, 228` | revert de lote | **T** |
| `resnapshot_lote` | `resnapshot_lote.py:39 _FIELDS, :49 _SNAP_KEYS` | reescreve snapshot | **T** (⚠ ver §2.6) |
| `reconcile_lote_039` | `reconcile_lote_039.py:72` | recontagem | **T** |
| `estoque/admin.py` | `:37, :109` (Pending→Inventory), `:76, :142` (list_display/fields) | cópia de campos | **T** |
| **[Rev.1]** aprovação de `PendingEntry` → `KnownPart` | `estoque/admin.py:15-40` (`update_or_create`, `confidence="manual"`) | copia `interface` do lote para o catálogo | **T + NUNCA copiar largura** (E3): `bus_width` do catálogo só vem de datasheet/Tier-1/backfill; o que a bancada observou fica no lote e na revisão (§10) |
| `estoque/views.py::_snapshot` | `estoque/views.py:139-160` (`:156`) | grava `_clean_interface(result)` | **T + R**: `bus_width` no snapshot; `_clean_interface` passa a tirar largura também |
| `import_chipid` | `import_chipid.py:169, 190, 239, 275` | SQL cru do projeto legado `classifier_*` | **—** (fonte legada não tem o campo; documentar) |
| `fill_capacity_from_micron_api` | `:649, :882` | infere **protocolo** NAND pela família | **—** (é protocolo, fica) |

Não precisam de `bus_width` (listas de **spec**, não de campo): `correct_known_parts`,
`export_identity_only`, `audit_sem_specs`, `audit_known_parts`, `fix_micron_*`,
`analyze_micron_mcp_keys`, `diag_pn`, `audit_estoque_drift`, `guard_catalog`,
`deploy_catalog`. E **`_HAS_SPECS`/`_USABLE` (`engine.py:132-162`) NÃO ganham
`bus_width`**: known_part só com largura continua identity-only — largura não é spec de
capacidade.

### 2.4 Onde `interface` é lido

| leitor | arquivo:linha | efeito do move |
|---|---|---|
| engine, família | `engine.py:483` (seed), `:523` (gen eMMC/UFS), `:615` (versão NAND do eMCP), `:648` (limpa no eMCP), `:872-886`, `:896-914` | **intocado** — tudo protocolo. `_result_from_family` ganha `"bus_width": fam.bus_width`. |
| engine, known | `:766 _result_from_known` (não copia `interface`), `:1544/:1591` (known sem família), `:1644/:1688` (FBGA), `:1481` (K9) | ganham `bus_width` (§4 F2, regra de merge). |
| gateway/label | `estoque/views.py:572-574` fallback de geração | 0 casos hoje; baseline prova depois. |
| estoque snapshot | `estoque/views.py:156`, `:1158` (setdefault) | grava `bus_width`; `interface` sem largura. |
| templates | `estoque/templates/estoque/partials/confirm_card.html:107, 111, 172`; `chips/templates/chips/partials/decode_card.html:85-88, 106-109`; `estoque.html:1729` (debug) | linha **"Largura"** nova nos dois cards (ramo não-eMCP). O `hidden` da :172 **não** ganha par: o snapshot é do servidor, o POST do cliente é ignorado (CLAUDE.md §6). |
| export xlsx | `estoque/views.py:1598, :1635` | coluna `Interface` fica. Coluna `Bus width` **fora do escopo** (planilha vai ao cliente; decisão à parte). |
| admin | `chips/admin.py:45-50, :126`; `estoque/admin.py:76, :142` | `bus_width` entra nos fieldsets/list_display. |
| recontagem | `estoque/reconcile_core.py:49, :60` (`iface` no blob D3/D4) | `x16` nunca contribuiu; intocado. |
| baseline | `characterize_baseline.py:70` | diff esperado na coluna `interface`; nova coluna `bus_width` ignorada no diff até regravar o baseline (`:236-246`). |
| lote (modelo) | `estoque/models.py:544, :632, :710`; `display_interface :604` | D6: campo novo ao lado; propriedade nova `display_bus_width` opcional. |

### 2.5 Ferramentas do levantamento de largura (raiz do repo)

`COLETAR_largura_bits.py:114-120 largura_do_banco` lê `kp.interface` (já trata
`'x16 @ …'` pegando o 1º token); `HANDOFF_largura_barramento.md` §4 Etapa 2 diz *"o
campo `interface` do KnownPart já é a largura"*; `PROMPT_chat_Samsung_largura_2026-09-12.md`
pede *"campo `interface` do known_part"* **e** manda gravar por `load_brands` (erro:
known_part não vai no yaml desde a Opção 2 — vai por `submit_known_parts`; upgrade de
valor aprovado vai por `resolve_conflicts`, memória `wtc-interface-vocabulario-fechado-emmc-ufs`).
`check_k4b_x4x8.py` deduz largura do PN para um CSV — ferramenta de planilha, nunca de
banco. Todos passam a falar `bus_width` na Fase 6.

### 2.6 Efeitos colaterais que já existem e este trabalho herda

- **pghistory.** `KnownPart`, `ChipFamily` e `DecodeMap` são `@pghistory.track()`
  (`models.py:58, 140, 168`). Campo novo ⇒ o `makemigrations` também adiciona a coluna
  em `chips_knownpartevent`/`chips_chipfamilyevent` e recria os gatilhos
  (`RemoveTrigger`/`AddTrigger`), exatamente como a `0020` fez para `review_status`.
  Migration fica maior; é normal. **Não edite a migration gerada à mão.**
- **`catalog_version` sobe a cada `save()` de KnownPart** (`chips/apps.py:18-32`).
  Um backfill de ~1.600 registros via `save()` bumpa ~1.600 vezes (barato) e marca
  **todas** as entradas de lote como defasadas (`snapshot_catalog_version < atual`).
  O on-read (`estoque/views.py:394-411`) recalcula **em memória, sem gravar**, até 150
  por render. **Quem persiste é só o `resnapshot_lote`** — e ele compara `interface` em
  `_SNAP_KEYS` (`:49`): se o dono rodá-lo num lote antigo depois do move, o `x16` da
  linha vira `''` e `bus_width` ganha o valor. **Isto não faz parte desta tarefa**
  (D6: histórico intocado) — está escrito no runbook como "não rode `resnapshot_lote`
  esperando preservar `interface`".
- **RLS.** Catálogo (`chips_*`) é GLOBAL — o backfill não precisa de `platform_scope()`.
  As tabelas de lote têm RLS + FORCE; a migration do estoque (D6) é **só DDL, sem
  RunPython** — DDL enxerga todas as linhas, não cai no zero silencioso. Se em algum
  momento você precisar LER lote em comando: `with platform_scope():` (CLAUDE.md §7).
- **Migration aditiva `NOT NULL default ''`** só é segura se o código que a conhece já
  estiver no ar quando ela rodar — isto é, **no build do Render**, nunca antes.
- **Suíte em SQLite** (`core/settings_test.py`): `CheckConstraint` com `__in` funciona
  nos dois bancos; regex não é portável — por isso o desenho da constraint em §3.3.
- **Submissão Samsung em voo.** O prompt de largura já foi entregue ao chat da Samsung
  pedindo `interface`. Se ele entregar antes da Fase 2 estar no ar, o arquivo entra com
  `interface: x8`; o backfill (F3) é **idempotente e re-rodável** — roda de novo depois
  e move. Se entregar depois, o portão rejeita e ele corrige (D3). Os dois caminhos
  fecham; nenhum perde dado.

---

## 3. O contrato do campo — o modelo de domínio final

### 3.1 Definições

| campo | significa | vocabulário | exemplos |
|---|---|---|---|
| **`bus_width`** (novo, `KnownPart` + `ChipFamily` + 3 modelos de lote) | **largura do barramento de DADOS do dispositivo**, como o fabricante publica na organização (`depth × width`: `512Mx16`, `1 Gig x 8`, JEDEC "Configuration") | **fechado**: `''`, `x4`, `x8`, `x16`, `x32`, `x64` (D8) | `x8` para K4B1G0846I; `x64` para MT62F768M64 |
| **`interface`** (existente) | **versão do protocolo** de armazenamento gerenciado (eMMC/UFS) ou descrição de interface física de NAND/NOR (`Async/ONFI`, `SPI`, `NOR (async)`) | livre, **mas nunca um token de largura** (invariante I2) | `eMMC 5.1`, `UFS 3.1`, `eMMC 4.x` |

Os dois são **ortogonais**: um chip pode ter os dois (NAND paralela: `Async/ONFI` + `x8`),
um só, ou nenhum. O que **não** é `bus_width`: banda (MB/s), encapsulamento
(FBGA-96), velocidade (`800MHz`), largura de **módulo** (x64 de um DIMM — o catálogo é de
componente; o x64 que existe aqui é de **pacote** LPDDR5, que é componente).

### 3.2 Em que classes `bus_width` existe (D5 — pesquisado, decisão do Fable)

O dono delegou. Critério: **o campo só faz sentido onde o fabricante publica UMA
largura de barramento de dados como atributo de identidade do dispositivo** — a
largura tem que ser fato do chip, não modo de operação nem propriedade de um sub-die.

| classe (`chip_types.py::category`) | `bus_width`? | por quê (fonte primária) |
|---|---|---|
| `dram_pc` (DDR1–5), `dram_gpu` (GDDR), `dram_legacy` (SDRAM/RDRAM), `dram_unknown` | **sim** | organização no PN e no datasheet (JESD79: "Configuration 512 Mb x4"; Samsung "Bit Org."; Micron "1 Gig x 8"). É o caso que motivou o trabalho. |
| `dram_mobile` (LPDDR1–5X avulso) | **sim** | Micron publica `BUS WIDTH` x16/x32/x64 no catálogo oficial (o `import_micron_catalog` já lê essa coluna) e a codifica no PN (`MT62F768M64D4WT` = 768 Meg × **64**). É largura do pacote = do dispositivo vendido. |
| `nand_raw` (NAND Flash paralela, K9) | **sim** | os datasheets da Micron chamam-se literalmente *"1Gb x8, x16: NAND Flash Memory"* / *"4Gb, 8Gb, 16Gb: x8, x16 NAND Flash Memory"* — largura de I/O é atributo do dispositivo (é o caso `KF98G16Q4X`). |
| `NOR Flash` paralela | **sim** (raro) | mesma lógica (x8/x16); SPI NOR **não** (x1/x2/x4 são linhas de comando, não organização — fica em `interface: SPI`). |
| `managed_nand` (eMMC, UFS, SSD) | **não — vazio obrigatório** | em eMMC a largura de dados é **modo configurado pelo host**: JESD84 `EXT_CSD[183] BUS_WIDTH`, "supports 1-bit (default), 4-bit, 8-bit" — todo eMMC suporta as três; não identifica dispositivo. UFS usa *lanes*, não largura. |
| `managed_mcp` (eMCP, uMCP) | **não — vazio obrigatório** | o pacote tem **dois** barramentos (RAM LPDDR x32 + NAND 8-bit de host); um campo só seria ambíguo. A RAM já vive em `emcp_ram`/`subtype`. |
| `catalog` (MCP, ePoP, SoC, PMIC, SRAM, …) | **não** | sem barramento único identificável no nosso modelo. |

Regra prática (deny by default, igual ao `is_ram_generation`): **`bus_width` não-vazio
só é aceito quando `spec_for(chip_type).category ∈ {dram_pc, dram_mobile, dram_gpu,
dram_legacy, dram_unknown, nand_raw}` ou `chip_type == "NOR Flash"`.** `chip_type`
vazio (identity-only) → aceita (fail-open, como `family_type_conflict`: o tipo vem da
família). Conferido contra o baseline de agosto: os 1.581 valores de largura de hoje
estão TODOS em DDR/GDDR/SDRAM/LPDDR5 (+1 NAND no seed) — a regra não bloqueia nenhum
dado existente.

> Fontes usadas na decisão (verificadas em 2026-09-12): datasheet eMMC 5.1 (Farnell
> 4159922: "Supports three data bus widths: 1 bit (default), 4 bits, 8 bits";
> `BUS_WIDTH` = EXT_CSD[183]); Micron *"1Gb x8, x16: NAND Flash Memory"*
> (MT29F1G08/16); Micron LPDDR5 `MT62F768M64D4WT-031` (DigiKey), organização
> 768M×64 no próprio PN; catálogo oficial Micron com coluna `BUS WIDTH`
> (`import_micron_catalog.py:19`).

### 3.3 Invariantes (cada um tem dono no código E trava de teste)

| # | invariante | onde mora | trava |
|---|---|---|---|
| I1 | `bus_width ∈ {'', x4, x8, x16, x32, x64}` em `KnownPart`, `ChipFamily` e nos 3 modelos de lote | `chips/conventions.py::BUS_WIDTH_VOCAB` (fonte única, tupla) + `CheckConstraint` `<tabela>_bus_width_vocab` em cada modelo + `is_bus_width()` (fullmatch) | teste que lê a constraint do `Meta` e compara com `BUS_WIDTH_VOCAB` (espelho, como `test_o_portao_conta_o_MESMO_que_o_engine_le`) |
| I2 | `interface` **nunca** é token de largura | portão Pydantic (`schema.py`) rejeita; `KnownPart.clean()` rejeita quando o valor **mudou**; `CheckConstraint` `knownpart_interface_nao_e_largura` = `~Q(interface__in=[x4…x64 + X4…X64])` (Fase 5, depois do backfill); `ChipFamily` idem | `InterfaceNaoELarguraTests` |
| I3 | `bus_width` só em classe permitida (§3.2) | `chips/knowledge/convention.py::bus_width_problem(chip_type, bus_width)` chamada por `clean()` e pelo `KnownPartSpec`/`FamilySpec` | `BusWidthClassePermitidaTests` |
| I4 | **[Rev.1]** **`KnownPart.bus_width` (a testemunha) nunca recebe largura derivada do PN nem observada na bancada** — só datasheet/Tier-1 (submissão), catálogo oficial (`import_micron_catalog`) e o backfill do legado. O **engine** PODE deduzir largura do PN em leitura, mas só por `decode_width_*` de família **provada pelo coletor** (≥5 acordos, 0 divergências, ≥2 larguras), e o resultado diz de onde veio (`bus_width_source`). Nenhum caminho leva largura de gramática/lote/revisão de volta ao catálogo: `bless_base` e a aprovação de `PendingEntry` **não copiam** o campo (E3) | `BlessBaseBusWidthTests` (nunca escreve `bus_width`), `PendingAprovacaoNaoCopiaLarguraTests`, checklist do CSV (HANDOFF §4 Etapa 8) |
| I5 | mover nunca apaga: toda sobra de `interface` tem destino (`Speed:` → `notes`) ou o registro **não migra** e é reportado | `split_bus_width` (§3.4) devolve a sobra; `normalize_convention` só grava quando a sobra é vazia ou é velocidade | `SplitBusWidthTests` + `NormalizeLarguraNoLugarCertoTests` (o caso "sobra desconhecida" tem que ficar de fora e aparecer no relatório) |
| I6 | as TRÊS COLUNAS não mudam | `characterize_baseline --diff` antes/depois de cada fase que toca dado ou engine | veredito "AS TRÊS COLUNAS INTACTAS"; único diff esperado: colunas `interface` e `bus_width` |

### 3.4 O parser — fonte única `split_bus_width(interface) -> (bus_width, speed, resto)`

Vive em `chips/knowledge/convention.py` (ao lado de `RX_DENSITY_BARE`/`RX_DIE_MB`) e é
usado por: `normalize_convention` (backfill), `bless_base` (lote legado → catálogo),
`import_samsung_psg`, `estoque/views.py::_clean_interface`, `MEDIR_bus_width.py`.

```
RX_BUS_WIDTH_LEAD = re.compile(r"^\s*(x(?:4|8|16|32|64))\b\s*(.*)$", re.I)
RX_SPEED          = re.compile(r"^@\s*(\S.*)$")          # '@ 800MHz (1600MTPS)' → '800MHz (1600MTPS)'
```

| entrada (`interface`) | `bus_width` | `speed` | `resto` | destino |
|---|---|---|---|---|
| `x16` / `X16` / ` x16 ` | `x16` | `` | `` | migra |
| `x16 @ 800MHz (1600MTPS)` | `x16` | `800MHz (1600MTPS)` | `` | migra; `notes += " \| Speed: 800MHz (1600MTPS)"` |
| `x32 @ 1866MHz` | `x32` | `1866MHz` | `` | migra + notes |
| `@ 1866MHz (3733MTPS)` (só velocidade) | `` | `1866MHz (3733MTPS)` | `` | `interface` → `''`; notes (D4) |
| `x16 (2 dies)` (sobra desconhecida) | `x16` | `` | `(2 dies)` | **não migra**; relatório "SOBRA SEM DESTINO" — decisão humana |
| `eMMC 5.1`, `UFS 3.1`, `Async/ONFI`, `Parallel NAND (8-bit)`, `NAND (x8/x16)` | `` | `` | (entrada intacta) | **não é largura** — fica |
| `x8x16`, `x 16`, `16x` | `` | `` | (intacta) | não casa; fica; aparece no censo como OUTRO |
| `` | `` | `` | `` | nada |

Regras: (a) o token é normalizado para minúsculo `x`; (b) `notes` recebe `Speed:` uma
vez só — idempotente: se `notes` já contém `Speed: <mesmo valor>`, não repete; (c)
`notes` vazio vira `"Speed: …"`, não `" | Speed: …"`; (d) nunca toca em `interface` de
protocolo, mesmo que contenha um número.

---

## 4. Fases de execução

Cada fase traz: objetivo · mudanças (arquivo:linha) · travas (testes que nascem com a
mudança, e a mutação que tem de morder) · comandos (dry-run → commit; quem roda) ·
critério de pronto · reversão. **Uma fase só começa quando a porta da anterior
fechou (§5).**

### Fase 0 — MEDIR o banco real + congelar o baseline (read-only, sem editar nada)

**Objetivo.** Trocar os números de amostra por números do banco (local = dump fresco
de prod, e prod) e congelar as três colunas antes de qualquer mudança.

**Mudanças.** Só um script novo na raiz: `MEDIR_bus_width.py` (Apêndice A). READ-ONLY,
em transação revertida, banner de banco-alvo, aborta em zero. Ele imprime:

1. `KnownPart.interface` em **6 baldes** × **classe** (`category` do `chip_types.py`):
   VAZIO · LARGURA_PURA (`^x(4|8|16|32|64)$`, case-insensitive) · LARGURA+VELOCIDADE
   (`^xN\s*@…`) · VELOCIDADE_SÓ (`^@…`) · PROTOCOLO (o resto que casa `eMMC|UFS|ONFI|
   Async|NAND|NOR|SPI|PPN`) · OUTRO (tudo que sobrou — **cada valor distinto listado**).
2. Os mesmos baldes para `ChipFamily.interface` (esperado: 25 LARGURA_PURA; os 2 `K9C`/`K9HDG` caem em PROTOCOLO pela palavra NAND e aparecem na lista "largura DENTRO de texto" — não migram, ficam para o dono).
3. **Divergência known × família**: registros cuja família tem `xN` e o próprio registro
   tem outro `xN` (hoje a família vence na tela; depois do move o registro
   `confirmed`/`manual` vence — §4 F2 — e a tela muda para esses; precisa de lista).
4. `bus_width` que a classe **não permite** (§3.2): largura em eMMC/UFS/eMCP/uMCP/catalog
   — esperado 0; se houver, é decisão do dono antes de migrar.
5. **Por marca**: quantos migram, quantos ficam, quantos são OUTRO.
6. Lote (D6, só para saber o tamanho): `InventoryEntry`/`Pending`/`Rejected` com
   `interface` de largura, sob `platform_scope()` — informativo, nada será tocado.
7. Totais varridos (`KnownPart.objects.count()`, famílias, lotes) — e **aborta se zero**.

**Comandos (dono, local primeiro, prod depois):**

```bash
# local — banco restaurado do dump mais recente do Render (receita: memória wtc-restaurar-dump-prod-local)
env -u DATABASE_URL python MEDIR_bus_width.py
env -u DATABASE_URL python manage.py characterize_baseline --out baseline_bus_width_ANTES_local.json
# prod — read-only (transação revertida / comando read-only); confira o banner
python MEDIR_bus_width.py
python manage.py characterize_baseline --out baseline_bus_width_ANTES_PROD.json
```

**Critério de pronto.** Você tem, por escrito no chat (e o dono viu): a tabela dos 6
baldes × classe para KnownPart e para ChipFamily, a lista completa de OUTRO, a lista de
divergências known×família, o nº de registros que a Fase 3 vai mover, e os dois
baselines gravados. **Sem isso, não há Fase 1.** Se aparecer forma que este plano não
previu (um OUTRO que não seja os 2 da Samsung), ela entra na tabela do §3.4 com destino
decidido pelo dono antes de o backfill existir — nunca "trato no código quando
aparecer".

**Reversão.** Nada foi escrito.

> ### RESULTADO DA FASE 0 — medido em 2026-09-19 (banco local, dump de prod) `[Rev.2]`
>
> **9.066 KnownPart · 277 ChipFamily.** Largura morando no campo errado: **3.539
> registros** — 1.759 largura pura + 1.657 largura+velocidade (todos Micron) + 123 só
> velocidade. Conferido por dois cortes independentes que batem: por classe
> (1462+135+84+77+1 = 1.759) e por marca (21+4+6+24+1129+154+92+70+175+84 = 1.759).
>
> **As três caixas de risco vieram ZERADAS:** sobra sem destino 0 · largura em classe não
> permitida 0 · divergência known × família 0. Os dois piores cenários que a F3 temia não
> existem neste banco. `ChipFamily`: exatamente as **25** previstas (ESMT 21, Samsung 3,
> Foresee 1), mais 4 OUTRO (Kingston ACR/KF/KVR "DDR3 / DDR4" — famílias bogus — e Samsung
> K4Y `DRSL`, que é interface Rambus legítima e fica). Lote, informativo (D6, intocado):
> InventoryEntry 225 · PendingEntry 13 · RejectedEntry 757.
>
> **Achado lateral, fora desta tarefa:** dos 265 OUTRO, **245 são GERAÇÃO DE RAM escrita no
> `interface`** (53 `DDR3`, 48 `LPDDR3`, 39 `LPDDR4X`, 39 `DDR3L`…). A regra 3 do
> `apply_kp_convention` já proíbe isso, então é legado anterior à regra ou entrada por
> `.update()`. Não migra para largura e não atrapalha o backfill.
>
> ### PILOTO SAMSUNG — medido em 2026-09-19, e ele reordena o trabalho `[Rev.2]`
>
> O dono pediu uma marca de teste antes de decidir a ordem geral. Samsung, decodificando
> `pn[5:7]` sobre o baseline (sem banco), por família de PC DRAM:
>
> | família | tipo | PNs | → x4 | → x8 | → x16 | → x32 | estreitos |
> |---|---|---:|---:|---:|---:|---:|---:|
> | K4B | DDR3 | 167 | 34 | 59 | 74 | 0 | **93** |
> | K4A | DDR4 | 61 | 6 | 28 | 27 | 0 | 34 |
> | K4R | DDR5 | 21 | 6 | 8 | 7 | 0 | 14 |
> | K4T | DDR2 | 14 | 0 | 5 | 9 | 0 | 5 |
> | K4H | DDR1 | 5 | 1 | 1 | 3 | 0 | 2 |
> | K4D/K4G/K4J/K4N/K4W/K4Z | GDDR | 84 | 0 | 0 | 36 | 48 | **0** |
>
> Três conferências independentes fecham com o coletor de 12/09: K4B = **93** (o ouro),
> famílias travadas = **55** (o "+55 linhas" do HANDOFF) e GDDR = **84 PNs, 0 estreitos**.
>
> **Reordenação — com a correção do dono (2026-09-19).** Dos +55 do HANDOFF, 7 são
> DDR1/DDR2 e saem (já são sucata por geração, não são comerciais). Os outros **48 são
> DDR4/DDR5 e FICAM**: hoje não têm desconto de largura, mas o dono decidiu coletá-los
> assim mesmo — *"o preço não é diferente hoje, mas um dia será, e eu tenho que estar
> preparado"*. ⚠ Uma primeira versão desta nota chamou esses 48 de "retorno comercial
> zero": mediu o preço de HOJE e confundiu isso com valor. Largura é fato permanente do
> chip; a tabela do comprador muda.
>
> **O argumento técnico reforça a decisão:** o gatilho da fila de foto (P3) é
> `WIDTH_SPLIT_GENS`. No dia em que DDR4 entrar nessa tupla, **todo DDR4 sem largura
> conhecida vira INDETERMINADO e cai na fila** — a bancada para. Catálogo já preenchido =
> o engine resolve e a fila nunca enche. Coletar agora custa ~20 consultas de datasheet;
> coletar depois custa operação parada (é o risco 1 do §10.6, antecipado).
>
> **Prioridade de marca = volume de DRAM COMERCIAL (DDR3+DDR4+DDR5) sem largura**, não
> volume de PNs e não só DDR3.
>
> DRAM comercial no catálogo — **1.609 PNs** (DDR3/3L 1.012 · DDR4 381 · DDR5 216) — e
> quantos NÃO mostram largura na bancada hoje: **1.096**. Por marca, ordenado por trabalho
> real: **Micron 567** (de 950) · **Samsung 249** (de 249) · **SK Hynix 111** (de 111) ·
> **Nanya 82** (de 137) · **PieceMakers 70** (de 70) · GigaDevice 6 · outras 11. Com
> largura completa na tela: Winbond 33, ESMT 12, Kingston 9, Foresee 4.
>
> ⚠ **A coluna "mostra" é a C1 em números, não falta de dado.** A Samsung mostra largura em
> **0** dos seus 167 DDR3 — e o censo lê **175 larguras puras** no campo dela, das quais o
> coletor provou 52 por datasheet só em K4B. O dado existe e não chega à bancada porque o
> caminho da família vence o do registro (§2.0 C1). **O maior ganho disponível não é
> pesquisa: é tornar visível o que já está no banco.** A pesquisa marca a marca é o que
> sobra depois disso — e começa por quem tem DDR3 e não tem largura.
>
> **Correção de um alarme meu:** eu havia dito que o `46` errado do `SAMSUNG.md` (linha 109)
> carimbaria x4 em tudo. Medido: **zero PNs** do catálogo têm `pn[5:7] == '46'`. O erro na
> documentação é real e a Etapa 1 do HANDOFF manda corrigir, mas ninguém está pisando nele.
>
> **K4W — decisão do dono, 2026-09-19: ignorar.** 30 PNs classificados GDDR3, todos NÃO
> RENTÁVEL, todos sem chave de preço. O HANDOFF registrava que a Samsung publica o datasheet
> como DDR3; a verificação de 19/09 deu fontes contraditórias (um agregador diz "DDR3 DRAM
> 64MX16 PBGA96", o Octopart lista o mesmo PN ora DDR3 ora GDDR3) e a organização é
> consistente em todas (128M×16, 96 bolas). **Não trabalhamos com GDDR** — fica como está.

### Fase 1 — Schema: colunas novas + constraints de vocabulário (migrations ADITIVAS)

**Objetivo.** Criar o lugar certo. Nada muda de comportamento nesta fase.

**Mudanças.**

- `chips/conventions.py` — ao lado de `_RAM_GEN_RE`/`is_ram_generation` (:38-53):
  ```python
  BUS_WIDTH_VOCAB = ("x4", "x8", "x16", "x32", "x64")   # fonte única (D8)
  _BUS_WIDTH_RE = re.compile(r"x(4|8|16|32|64)", re.I)
  def is_bus_width(text: str) -> bool:      # fullmatch, lista fechada — "x8 @ 800MHz" NÃO é
      t = (text or "").strip()
      return bool(t) and bool(_BUS_WIDTH_RE.fullmatch(t))
  ```
  Módulo puro (só `re`) — pode ser importado no topo de `models.py` sem ciclo.
- `chips/models.py`:
  - `ChipFamily.bus_width = models.TextField(blank=True, default="", help_text="Largura do barramento de dados da família (x4/x8/x16/x32/x64) quando é fixa na família — ou vazio. NUNCA a versão de protocolo (isso é `interface`).")` logo abaixo de `interface` (:75); **[Rev.1] E1** e, ao lado dos `decode_cap_*`/`decode_gen_*` (:76-91): `decode_width_pos` (Integer null), `decode_width_len` (default 1), `decode_width_map` (TextField, nome do `DecodeMap` de largura) — `help_text` dizendo que SÓ família provada pelo coletor declara (HANDOFF §4 Etapa 9). Vão para a mesma migration `0024` (o pghistory espelha no `chipfamilyevent`).
  - `KnownPart.bus_width = models.TextField(blank=True, default="", help_text="Largura do barramento de dados do dispositivo: x4/x8/x16/x32/x64 ou vazio. Vem de datasheet/Tier-1 — NUNCA deduzida do part number (circularidade do coletor).")` abaixo de `interface` (:215);
  - `Meta.constraints`: `CheckConstraint(condition=Q(bus_width__in=("",) + BUS_WIDTH_VOCAB), name="knownpart_bus_width_vocab")` e `chipfamily_bus_width_vocab` (mesmo padrão de `knownpart_confidence_vocab`, :263-265 — só que **importando** a tupla em vez de repetir a lista).
- `estoque/models.py` (D6, **[Rev.1] E4 — três colunas, não uma**): em `InventoryEntry` (:544), `PendingEntry` (:632), `RejectedEntry` (:710):
  - `bus_width = CharField(max_length=8, blank=True, default='', verbose_name='Largura')` + `CheckConstraint <tabela>_bus_width_vocab`;
  - `width_class = CharField(max_length=8, blank=True, default='', verbose_name='Classe de largura')` + constraint vocab `('', 'narrow', 'wide')` — é o que o preço/caixa da Parte 2 leem; na Parte 1 é gravado pelo snapshot a partir de `bus_width` (`width_class_of`, §10.3) e fica vazio quando a largura é desconhecida;
  - `bus_width_source = CharField(max_length=12, blank=True, default='')` + constraint vocab `('', 'banco', 'familia', 'gramatica', 'revisao')`.
  **Sem RunPython, sem backfill.** `verbose_name` em PT (admin é pt-br fixo — CLAUDE.md §6). Criar as três agora evita uma 2ª migration do estoque na Parte 2.
- `python manage.py makemigrations chips estoque` → `chips/0024_…` (vai trazer também `knownpartevent`/`chipfamilyevent` + `RemoveTrigger`/`AddTrigger` do pghistory — normal, não edite) e `estoque/0026_…`. `makemigrations --check --dry-run` limpo depois.

**Travas.**
- `BusWidthVocabEspelhoTests`: a lista da constraint (lida de `KnownPart._meta.constraints`, `ChipFamily`, e dos 3 modelos de lote) **é** `("",) + BUS_WIDTH_VOCAB`; `is_bus_width("x8")` e `is_bus_width(" X8 ")` True (tolerante a caixa/espaço — a regra 5 do `apply_kp_convention` normaliza para `x8` antes de gravar; o banco só aceita a forma canônica); `is_bus_width("x8 @ 800MHz")`, `"x2"`, `"x128"`, `"DDR4"`, `"x8x16"` False.
- Constraint morde: `KnownPart(bus_width="x2").save()` → `IntegrityError`/`ValidationError` (o `clean()` da Fase 2 pega antes; nesta fase, teste direto com `objects.update()` — que pula `save()` — para provar que é o **banco** que barra).
- `TenancyDeclarationTests` continua verde (não há modelo novo).
- Mutação: remover `x64` da tupla → o espelho falha.

**Comandos (dono).** Local: `python manage.py migrate` (banco local) + suíte. **Prod: só
pelo push** (build do Render roda `migrate`). Depois do deploy: `guard_catalog`.

**Critério de pronto.** Migrations aplicadas local; suíte verde; `characterize_baseline
--diff baseline_bus_width_ANTES_local.json` → **IDÊNTICO** (nada mudou de comportamento);
deploy no ar (prod migrada pelo build) e `guard_catalog` verde.

**Reversão.** `migrate chips 0023` / `migrate estoque 0025` (colunas vazias — sem perda).
Em prod, reverter = push do commit anterior + `migrate` reverso no build; nunca à mão.

> ⚠ **Por que a Fase 1 e a Fase 2 podem (e devem) ir no MESMO deploy:** a coluna nova
> só existe no banco depois do `migrate` do build; o código da Fase 2 já a conhece.
> O que não pode é o inverso (banco à frente do código). Se preferir dois deploys por
> tamanho de PR, a Fase 1 sozinha é inerte e segura.

### Fase 2 — Portões, engine, telas, i18n e os 24 canais

**Objetivo.** Ensinar tudo que escreve e tudo que lê. Ainda sem mover dado. Ao fim,
`bus_width` vazio em todo lugar → **comportamento idêntico ao de hoje** (baseline
IDÊNTICO), mas o sistema já aceita largura só no lugar certo.

**2a. Portão — fonte única `chips/knowledge/convention.py`**

- `_CLEAN_FIELDS` (:23) ganha `"bus_width"` (limpa `'None'`).
- `apply_kp_convention` (:132): **regra 5** — `bus_width` normalizado (`strip().lower()`);
  se não for `is_bus_width` **nem vazio**, deixa como está para o `clean()` rejeitar
  (o normalizador não levanta exceção — docstring do módulo). Regra 3 (:160-161) fica
  como está (geração de RAM em `interface` → `''`).
- Novas funções:
  - `bus_width_problem(chip_type, bus_width) -> str | None` — I1 + I3: vocabulário e
    classe permitida (§3.2). Mensagem acionável: *"`bus_width='x8'` não se aplica a eMMC
    (largura de dados é modo do host, EXT_CSD BUS_WIDTH) — deixe vazio"* / *"`bus_width='x2'`
    fora do vocabulário {x4, x8, x16, x32, x64}"*.
  - `interface_problem(interface) -> str | None` — I2: se `RX_BUS_WIDTH_LEAD` casa
    (`x16`, `x16 @ …`, `X16`), devolve *"largura de barramento vai em `bus_width`, não em
    `interface` (`interface` = versão de protocolo: eMMC 5.1, UFS 3.1). Mova `x16` para
    `bus_width`"* — é a mensagem que o chat de marca vai ler no dry-run (D3).
  - `split_bus_width(interface) -> (bus_width, speed, resto)` — §3.4, com `RX_BUS_WIDTH_LEAD`
    e `RX_SPEED`.
- `KnownPart.clean()` (`models.py:284`): chama `bus_width_problem` (sempre — campo novo,
  não há legado a perdoar) e `interface_problem` **só quando `interface` mudou** em
  relação ao banco (mesmo truque de grandfather das `measure_problems`, `models.py:304-312`) — sem
  isso o re-save de qualquer registro legado com `x16` quebraria `resnapshot`/`bless_base`/
  o próprio backfill antes de ele rodar. Depois da Fase 5 a constraint do banco fecha
  o resto.
- `ChipFamily` **não tem `clean()`** hoje (só o portão Pydantic e, na Fase 5, a constraint
  cobrem o admin). Adicione um `clean()` mínimo em `ChipFamily` chamando `interface_problem`
  (só quando `interface` mudou) e `bus_width_problem(chip_type, bus_width)` — o admin chama
  `full_clean()`; o `load_brands` já valida antes.
- `chips/knowledge/schema.py`: `FamilySpec.bus_width: str = ""` (:70) e
  `KnownPartSpec.bus_width: str = ""` (:184); nos `model_validator` de cada um, **antes**
  do `apply_kp_convention`: `if interface_problem(self.interface): raise ValueError(...)`
  (rejeita — D3), depois `bus_width_problem` idem. `extra="forbid"` já barra chave
  desconhecida — `bus_width` passa a ser conhecida.
- `load_brands.py`: `_FAMILY_FIELDS` (:51) e `_KNOWNPART_FIELDS` (:59) ganham `"bus_width"`.
  Aviso (não erro) quando família DDR-kind **sem** `bus_width` e sem `interface`? **Não** —
  família pode ser multi-largura de propósito (K4B tem x4/x8/x16). Só o registro sabe.

**2b. Engine — `chips/engine.py`**

- `_result_from_family` (:477-505): `"bus_width": fam.bus_width`, `"bus_width_source":
  "familia" if fam.bus_width else ""` no dict base.
- **[Rev.1] E1 — largura pela GRAMÁTICA (família provada).** Depois do decode de
  densidade em `_result_from_family`, um bloco genérico (zero `if` por marca — CLAUDE.md §4):
  ```python
  # Largura de barramento decodificada do PN — SÓ em família cujo yaml declara
  # decode_width_* (e só o coletor PROVADO autoriza declarar: ≥5 acordos, 0
  # divergências, ≥2 larguras — HANDOFF §4). É a "válvula de escape" da largura:
  # o banco (datasheet) vence; a gramática cobre a cauda. NUNCA volta ao catálogo.
  if fam.decode_width_pos is not None and fam.decode_width_map:
      wmap = _load_decode_map(fam.decode_width_map)
      pos, wlen = fam.decode_width_pos, (fam.decode_width_len or 1)
      if len(pn) >= pos + wlen:
          entry = wmap.get(pn[pos:pos + wlen])
          if entry and is_bus_width(entry[0]):
              r["bus_width"], r["bus_width_source"] = entry[0].lower(), "gramatica"
  ```
  `ChipFamily` ganha `decode_width_pos` (Integer null), `decode_width_len` (default 1),
  `decode_width_map` (nome de `DecodeMap`, por marca — ex.: `SAM_DDR_WIDTH` com
  `[04,x4] [08,x8] [16,x16] [32,x32] [06,x4] [07,x8]`; SK Hynix `HYX_DDR_WIDTH`
  `[4,x4] [8,x8] [6,x16]` em `pn[6]`). `FamilySpec` (schema.py) + `_FAMILY_FIELDS`
  (load_brands.py:51) + o portão: `decode_width_pos` setado sem `map` → rejeita (mesmo
  padrão F2/E do `decode_cap_pos`). Nanya soletra a largura depois de um prefixo de
  profundidade variável (`NT5CB256M8`, `NT5CC128M16`): o executor verifica se
  `suffix_rules` já cobre um regex de captura; se não, adiciona `decode_width_regex`
  (`M(4|8|16|32)`) — o menor mecanismo genérico que resolva, com teste. **Nenhuma
  família recebe `decode_width_*` neste PR**: as regras entram pela Trilha A dos chats de
  marca, uma família por vez, com o relatório do coletor citado no `reasoning` do yaml e
  **âncoras x4/x8/x16 no golden** da marca (`EngineBusWidthTests` ganha um caso por
  família provada). O que este PR entrega é o MECANISMO + a ordem de precedência.
- `_result_from_known` (:766): depois do bloco de `subtype` (:961-962):
  ```python
  # Largura de barramento: dado do registro é mais específico que o da família
  # e que a gramática. Verificado por humano vence sempre; distributor/estimated
  # só COMPLEMENTA (mesma doutrina de capacity, regra de ouro #2/#6).
  if known.bus_width and (human_verified or not r.get("bus_width")):
      r["bus_width"], r["bus_width_source"] = known.bus_width, "banco"
  ```
  Ordem de precedência final (E2): **banco (`confirmed`/`manual`) > gramática (família
  provada) > família (`ChipFamily.bus_width` fixo) > banco `distributor`/`estimated`
  (complementa) > vazio.** `bus_width_source ∈ {'', 'banco', 'gramatica', 'familia'}` no
  engine; `'revisao'` só entra no gateway do estoque (Parte 2, §10.4 P3).
- Dicts literais: `:1481` (K9) `"bus_width": "", "bus_width_source": ""`; `:1544`, `:1591`
  (known sem família), `:1644`, `:1688` (FBGA) `"bus_width": known.bus_width,
  "bus_width_source": "banco" if known.bus_width else ""`.
- **Nada muda em `interface`** no engine: `:483, :523, :615, :648, :872-886, :896-914`
  ficam. Não escreva shim "se `interface` parece largura, mostra em `bus_width`" —
  esconderia a migração e o baseline deixaria de contar a verdade.
- `assess_profitability`, `is_dead_by_generation`, `pricing.derive_price_key`: **intocados na
  Parte 1** (D1 revisada: a largura entra neles na Parte 2, §10.4 P2 — e `derive_price_key`
  fica puro até lá também; o eixo é da linha).

**2c. Estoque — `estoque/views.py`**

- `_clean_interface` (:127-136): além da geração, **remove largura** — `bw, sp, resto
  = split_bus_width(ifc)`; se `bw` ou `sp` → devolve `resto` (que é `''`). Docstring
  passa a dizer *"`interface` no estoque = versão (eMMC 5.1) — nunca geração nem largura
  (isso é `bus_width`)"*. Efeito: a partir do deploy, **lote novo nunca mais grava `x16`
  em `interface`**, mesmo na janela em que a família ESMT ainda diz `interface: x16`.
- `_snapshot` (:139-160): `"bus_width": (result.get("bus_width") or "").strip()`. O dict
  entra por `**_snapshot(server_result)` nos `create()` de `RejectedEntry`/`PendingEntry`/
  `InventoryEntry` (`:1284-1286, :1327, :1347-1349, :1411-1419`) e em `replicate_lot_xlsx.py:100`
  e `resnapshot_lote.py:108` — por isso o campo **tem de existir nos 3 modelos (F1) no mesmo
  deploy**, senão o lançamento quebra com `TypeError` (chave inesperada).
- `:1158` (setdefault do resultado reduzido): `'bus_width'` na tupla — senão o preview
  de PN em fila dá 500 (bug de 2026-08-05 repetido).
- `_compute_destination` (:572-574): **não mexa** no fallback de `interface` (0 casos;
  baseline vigia). Não use `bus_width` no label **na Parte 1** (código de caixa é ETERNO —
  CLAUDE.md §7); a Parte 2 (D10) cunha código NOVO só para o estreito, sem renomear os
  existentes.
- `estoque/models.py`: `display_bus_width` opcional (espelho de `display_interface` :604).
- Comandos do lado lote (D6): `resnapshot_lote.py:39/49`, `fix_pns.py:74/85/258/278`,
  `clean_lote.py:192/228`, `reconcile_lote_039.py:72`, `estoque/admin.py:37/109/142/76`
  ganham `bus_width` nas listas.
- **[Rev.1] E3 — `bless_base.py:199` e a aprovação de `PendingEntry` (`estoque/admin.py:15-40`)
  NUNCA escrevem `bus_width` no KnownPart.** O lote pode carregar largura vinda da
  gramática (E1) ou da revisão por foto (Parte 2); copiar isso para o catálogo lavaria
  largura deduzida/observada para dentro da testemunha independente e mataria o
  cruzamento do coletor (I4). Os dois só tiram a largura de `interface` legado
  (`bw, sp, resto = split_bus_width(e.interface)` → `interface = resto if (bw or sp)
  else e.interface`) e **descartam `bw`** — o valor não é perdido: o backfill da Fase 3 já
  o moveu no catálogo quando ele existia lá; se não existia, a bancada não é fonte de
  catálogo. Trava: `BlessBaseBusWidthTests` (entrada com `bus_width='x16'`,
  `bus_width_source='gramatica'` promovida → KnownPart com `bus_width=''`) e
  `PendingAprovacaoNaoCopiaLarguraTests`.
- `_snapshot` também grava `"bus_width_source": result.get("bus_width_source") or ""` e
  `"width_class": width_class_of(result.get("bus_width"))` (§10.3 — `x4/x8 → 'narrow'`,
  `x16 → 'wide'`, resto → `''`). Na Parte 1 `width_class` é só materialização; ninguém lê.

**2d. Telas + i18n**

- `estoque/templates/estoque/partials/confirm_card.html`: no ramo **não-eMCP** (:110-113),
  depois de "Interface": `<div class="spec"><div class="spec__l">{% trans "Largura" %}</div><div class="spec__v">{{ result.bus_width|default:"—" }}</div></div>`.
  No ramo eMCP **não** (gerenciado = vazio por regra). O `hidden` da :172 não ganha par.
- `chips/templates/chips/partials/decode_card.html`: bloco `{% if result.bus_width %}` com
  label `{% trans "Largura" %}` nos dois `dc2-specs` (:85-90 e :106-111).
- `estoque.html:1729` (debug copiável): `lines.push('Largura:     ' + (d.bus_width || '—'));`.
- **i18n (MULTILANGUAGE.md §7 — mesma entrega):** `msgid "Largura"` nos 3 `.po`
  (`locale/es|en|zh_Hans/LC_MESSAGES/django.po`): es `Ancho de bus` · en `Bus width` ·
  zh_Hans `位宽`. Fluxo: `scripts/i18n_extract.py` → traduzir os SEUS msgids →
  `scripts/i18n_compile.py` → `python manage.py check_translations` verde. Confira o
  glossário DO-NOT-TRANSLATE do `I18N.md` antes (o token `x16` nunca traduz — é valor
  canônico; só o rótulo traduz).
- Card mascarado (`confirm_card_masked.html`) **não** mostra largura (não mostra
  `interface` hoje; a máscara é sobre o que o chip É — CLAUDE.md §7, 2026-09-09).
- Admin: `chips/admin.py:45` fieldset da família ganha `"bus_width"` e a `description`
  (:47-50) passa a explicar os dois campos; `:126` fieldset do KnownPart idem.

**2e. Os comandos do catálogo (listas explícitas — §2.3)**

`submit_known_parts.py:80`, `audit_submissions.py:45` (+ `_CLASSE["bus_width"] =
"identidade"`, :59), `resolve_conflicts.py:66-70` (`bus_width` em `_ARQUIVO_VENCE` — é fato
sobre QUAL peça é; `interface` continua `_MAIS_ESPECIFICO`), `dedupe_known_parts.py:39`,
`purge_enriched.py:130`, `restore_purge.py:35`, `restore_known_parts.py:22`,
`characterize_baseline.py:70` (`"bus_width": r.get("bus_width") or ""` **e [Rev.1] E7
`"bus_width_source": r.get("bus_width_source") or ""`** — na Parte 2 a coluna de
procedência é o que separa "mudou porque o datasheet diz" de "mudou porque a gramática
deduziu"), `audit_campo_forma.py:453`.

`import_micron_catalog.py` (**T + R**): `info["bus_width"] = bus_width.strip().lower()`
(:266), `info["interface"] = ""` para DRAM (protocolo só quando o CSV traz `PROTOCOL`,
que é o caso uMCP — aí `interface` = protocolo, `bus_width` = vazio por I3);
`_build_notes` (:168-178) ganha `("Speed", f"{speed} ({mts})" if mts and mts != speed else speed)`;
`_maybe_update("bus_width", …)` (:505) e as listas `:482`, `:624`. `_build_interface`
(:156-164) morre — grep para garantir que ninguém mais a chama.

`import_samsung_psg.py` (**T + R**): na leitura (:194) `bw, sp, resto = split_bus_width(interface)`;
grava `bus_width=bw`, `interface=resto`, `Speed:` em notes se `sp`.

**2f. Travas da Fase 2** (nomes sugeridos; cada uma com a mutação que tem de morder)

| classe de teste | garante | mutação que morde |
|---|---|---|
| `SplitBusWidthTests` | a tabela do §3.4 linha a linha (inclui `X16`, sobra desconhecida, protocolo intacto) | trocar `fullmatch`→`search` no `is_bus_width`; aceitar sobra desconhecida |
| `InterfaceNaoELarguraTests` | `KnownPartSpec(interface="x16")` → `ValueError` com a palavra `bus_width` na mensagem; `KnownPart.clean()` rejeita quando `interface` **mudou** para largura; **não** rejeita re-save de legado com `x16` inalterado (grandfather) | remover a comparação com o banco (quebra o grandfather); remover a checagem (aceita) |
| `BusWidthClassePermitidaTests` | `bus_width="x8"` em eMMC/eMCP/uMCP/UFS → rejeita; em DDR3/LPDDR5/NAND Flash/NOR Flash/chip_type vazio → aceita | inverter a allow-list |
| `EngineBusWidthTests` | (a) família com `bus_width='x16'` + known `confirmed` `x8` → resultado `x8`/`banco`; (b) known `distributor` `x8` + família `x16` → `x16`/`familia`; (c) known `distributor` `x8` + família vazia → `x8`/`banco`; (d) known sem família → `bus_width` do registro; (e) FBGA idem; (f) K9 → `''`; (g) eMCP: `interface` do resultado continua `''` e `bus_width` `''`; **[Rev.1]** (h) família com `decode_width_pos/map` (fixture `_WIDTHTEST`, valores que não existem no mundo real) → `x8`/`gramatica` no PN certo e `''` no PN cujo código não está no mapa; (i) known `confirmed` `x16` vence a gramática `x8`; (j) `decode_width_pos` sem `map` é rejeitado pelo `load_brands` | trocar a condição do merge por "sempre known"; esquecer um dict literal; inverter a precedência banco×gramática |
| `SnapshotBusWidthTests` (estoque) | `_snapshot` grava `bus_width`; `_clean_interface("x16")=="", ("x16 @ 800MHz")=="", ("eMMC 5.1")=="eMMC 5.1"`; lançamento novo de DDR3 com família `x16` grava `interface=''`, `bus_width='x16'` | tirar o `split` do `_clean_interface` |
| `CardLarguraTests` | pela VIEW de verdade (`confirm_card` renderizado): DDR3 com largura mostra "Largura x16"; eMCP não mostra a linha; em `zh-hans` mostra `位宽` (I18N — teste em 2 idiomas, como `tests_origem_do_lote`) | remover a linha do template |
| `ComandosCarregamBusWidthTests` | scanner: cada lista `_FIELDS`/`_CAMPOS`/`FIELDS` dos comandos do §2.3 contém `bus_width` (lê as constantes importadas, não regex em texto); `import_micron_catalog._build_notes` produz `Speed:`; `_build_interface` não existe mais | tirar de uma lista |
| `BlessBaseBusWidthTests` | entrada de lote com `interface='x16'` promovida → KnownPart `bus_width='x16'`, `interface=''`; com `interface='eMMC 5.1'` → intacta | tirar o `split` |
| `characterize` | `bus_width` aparece no JSON | — |

**Comandos (dono).** Suíte inteira + `check_translations` + `python manage.py
characterize_baseline --diff baseline_bus_width_ANTES_local.json` → **IDÊNTICO** (aviso
"colunas AUSENTES no baseline: bus_width" é esperado, :241-245). `load_brands --brand
esmt` (dry-run) ainda **passa** nesta fase? **Não** — o yaml da ESMT ainda tem
`interface: x16` e o portão agora rejeita (I2). É de propósito e é a razão de a Fase 4
vir logo depois; até lá **ninguém roda `load_brands` da ESMT/Foresee/Samsung** (registre
no chat do dono e no PR).

> ⚠ Alternativa se o dono preferir não travar o `load_brands` das 3 marcas por um dia:
> fazer a Fase 4 (edição dos yamls) **no mesmo PR** da Fase 2. É o recomendado: são 25
> linhas mecânicas, e o dry-run do `load_brands` de cada marca é a prova.

**Critério de pronto.** Suíte verde (com as 8 classes novas), `check_translations` verde,
`makemigrations --check` limpo, baseline **IDÊNTICO** (ou, se a Fase 4 foi no mesmo PR e o
`load_brands` local já rodou: o único diff é `interface` `'xN' → ''` nos PNs das 25 famílias,
três colunas intactas), PR revisado pelo dono, **deploy no
ar** (build migra a 0024/0026), `guard_catalog` verde, e um teste de frontend entregue:
buscar `K4B1G0846I` na bancada → "Largura —" (ainda; o dado só move na Fase 3) e
`MT53E…` idem; nada mais mudou.

**Reversão.** Revert do commit (código) — as colunas ficam, vazias, inertes.

### Fase 3 — Backfill de `KnownPart`: a 3ª exceção "campo fora do lugar" do `normalize_convention`

**Objetivo.** Mover, no banco, a largura de `interface` para `bus_width` (e a velocidade
Micron para `notes`), **só em `KnownPart`**, com dry-run, revert e idempotência. Não é
comando novo: CLAUDE.md §7 é explícito — *"a MIGRAÇÃO mora no `normalize_convention`,
não num comando novo"* (é a 3ª exceção, gêmea da densidade de 2026-07-11 e da geração de
2026-08-28).

**Mudanças — `chips/management/commands/normalize_convention.py`.**

- Docstring do módulo (:1-30): parágrafo *"Excecao 3 (2026-09-12): LARGURA NO LUGAR
  CERTO"* com as regras abaixo.
- `_plan(obj)` (:96-163): novo bloco, **só para `KnownPart`** (`hasattr(obj, "bus_width")`
  e `isinstance` — `ChipFamily` NÃO entra: família vem do yaml, Fase 4; se o comando
  tocasse a família, o próximo `load_brands` desfaria — dossiê §5.1):
  ```python
  # (só a parte da largura; o resto do _plan — chip_type/densidade/geração — segue igual
  #  e NÃO é descartado quando a largura não migra: `motivo` vai para o relatório, não para o ch)
  bw, sp, resto = split_bus_width(obj.interface)
  motivo = ""
  if bw and resto:
      motivo = "SOBRA SEM DESTINO"                 # 'x16 (2 dies)': não migra, decisão humana
  elif bw or sp:
      atual = (obj.bus_width or "").strip().lower()
      if bw and bus_width_problem(obj.chip_type, bw):
          motivo = "CLASSE NÃO PERMITE"            # eMMC com x8? reporta, não migra
      elif bw and atual and atual != bw:
          motivo = "CONTRADIÇÃO"                   # já tem OUTRA largura: não arbitra
      else:
          if bw and not atual:
              ch["bus_width"] = [obj.bus_width, bw]          # FILL-ONLY
          ch["interface"] = [obj.interface, ""]              # só esvazia quando TUDO teve destino (I5)
          if sp:
              novo = _notes_com_speed(obj.notes, sp)         # idempotente (§3.4 regras b/c)
              if novo != obj.notes:
                  ch["notes"] = [obj.notes, novo]
  # `motivo` não-vazio → o handle() conta em NÃO MIGRADOS[motivo] e lista o PN
  ```
  Regras: FILL-ONLY em `bus_width`; `interface` **só** esvazia quando tudo que havia
  nela foi para algum lugar (I5); `notes` só cresce; nada em `ChipFamily`; não toca em
  `confidence`/`review_status` (o registro `submitted` também migra — é dado, não
  autoridade); `save(update_fields=[...])` como hoje (passa pelo `clean()` — que aceita,
  porque `interface` muda **para vazio** e `bus_width` está no vocabulário e na classe).
- Relatório do dry-run (:229-247): seções novas **"bus_width — largura no lugar certo
  (N KnownPart)"** com os movimentos `'x16' → bus_width`, `'x16 @ …' → bus_width + Speed`,
  `'@ …' → Speed`; **"NÃO MIGRADOS"** com 3 sub-baldes e a lista completa (não amostra):
  SOBRA SEM DESTINO · CONTRADIÇÃO (já tinha outra largura) · CLASSE NÃO PERMITE; e **por
  marca**. O número de "KnownParts a migrar" tem de bater com a Fase 0.
- `class Command(BaseCommand)` (:165) → **`SafeWriteCommand`** (`core/safe_command.py`): banner
  de banco-alvo + confirmação digitada no `--commit`. Hoje o comando não imprime o
  banco-alvo — e o dossiê §10.3 registra que já se rodou em prod achando que era local.
- Opção `--out <caminho>` para o JSON de reversão (default mantém
  `normalize_convention_revert.json` — `chips/tests.py:3759-3763` depende do nome). O
  runbook **sempre** passa `--out normalize_convention_revert_<BANCO>_<AAAAMMDD>.json`
  (padrão do `backfill_doc_codes_revert_PROD_20260902.json`); `.gitignore` já cobre
  `*_revert.json`.
- `_revert` (:173-186): já genérico por campo — cobre `bus_width`/`interface`/`notes` sem
  mudança. Teste de ida-e-volta obrigatório.
- ⚠ O comando é UM só: o dry-run vai listar também movimentos das exceções 1 e 2
  (chip_type canônico, densidade, geração de eMCP) para registros que entraram desde a
  última rodada. São legítimos e reversíveis pelo mesmo JSON — mas o dono precisa ver
  esses números separados dos da largura antes do `--commit`, não descobrir depois.

**Travas — `NormalizeLarguraNoLugarCertoTests`** (modelo: `NormalizeGeracaoNoLugarCertoTests`,
`chips/tests.py:3572`):

| caso | esperado | mutação que morde |
|---|---|---|
| `interface='x16'`, `bus_width=''` | `bus_width='x16'`, `interface=''` | — |
| `interface='x16 @ 800MHz (1600MTPS)'`, `notes='Voltage: 1.5V'` | `bus_width='x16'`, `interface=''`, `notes='Voltage: 1.5V \| Speed: 800MHz (1600MTPS)'` | descartar a velocidade (I5) |
| `interface='@ 1866MHz'`, `notes=''` | `interface=''`, `notes='Speed: 1866MHz'` | — |
| rodar 2× | 2ª rodada: **"KnownParts a migrar: 0"** (idempotente; olha o PLANO, não só o valor — lição de 2026-08-28) | — |
| `interface='x16'`, `bus_width='x8'` | **não migra**, aparece em CONTRADIÇÃO | migrar por cima |
| `interface='x16 (2 dies)'` | não migra, SOBRA SEM DESTINO | migrar e perder `(2 dies)` |
| `chip_type='eMMC'`, `interface='x8'` | não migra, CLASSE NÃO PERMITE | — |
| `interface='eMMC 5.1'` | intacto | regex frouxo |
| `ChipFamily` com `interface='x16'` | **intocada** pelo comando | incluir família |
| `--commit` + `--revert` | ida-e-volta devolve os 3 campos | — |
| `submitted` (não aprovado) com `x16` | migra também | — |

**Comandos (dono) — local primeiro, contra o dump de prod restaurado:**

```bash
env -u DATABASE_URL python manage.py normalize_convention            # dry-run: confira o banner e os números contra a Fase 0
env -u DATABASE_URL python manage.py normalize_convention --commit --out normalize_convention_revert_LOCAL_$(date +%Y%m%d).json
env -u DATABASE_URL python manage.py normalize_convention            # dry-run de novo: "KnownParts a migrar: 0"
env -u DATABASE_URL python manage.py characterize_baseline --diff baseline_bus_width_ANTES_local.json --summary
env -u DATABASE_URL python manage.py test chips estoque --settings=core.settings_test
env -u DATABASE_URL python MEDIR_bus_width.py                         # LARGURA_PURA/LARGURA+VEL/VELOCIDADE_SÓ em KnownPart = 0 (ou só os NÃO MIGRADOS listados)
```

Só depois, **prod** (código da Fase 2 já no ar; Render Export fresco feito — regra 1b(c)):

```bash
export DATABASE_URL="postgresql://…render.com…"   # segredo do dono
python manage.py normalize_convention                                  # dry-run — números têm que bater com o MEDIR de prod
python manage.py normalize_convention --commit --out normalize_convention_revert_PROD_$(date +%Y%m%d).json
python manage.py normalize_convention                                  # "a migrar: 0"
python manage.py characterize_baseline --diff baseline_bus_width_ANTES_PROD.json --summary
python MEDIR_bus_width.py
python manage.py guard_catalog
```

**O que o `--diff` TEM de mostrar (e nada além):** "AS TRÊS COLUNAS INTACTAS";
`interface` mudando `'x16' → ''` / `'x16 @ …' → ''` exatamente nos PNs do relatório do
backfill que estavam nos caminhos **known sem família/FBGA** (para os known **com**
família a tela nunca mostrou o valor do registro — C1); e nada em `dest_label`,
`profitable`, `is_dead`, `price_key`. Se o `--summary` mostrar `dest_label` mudando em
qualquer PN, **pare**: é o fallback de `_compute_destination:572-574` sendo atingido —
reverta (`--revert`) e traga o caso para o dono.

**Critério de pronto.** Local: as 6 linhas acima verdes, e a lista de NÃO MIGRADOS
(esperada: 0 ou pequena — os `K9C`-like são família, não entram) revisada pelo dono.
Prod: idem + `guard_catalog` + teste de frontend: `K4B1G0846I` mostra **Largura x8**
(pela primeira vez), `MT53E…` (LPDDR4X Micron sem largura) segue "—", um LPDDR5 Micron
mostra `x64`, um eMCP não mostra a linha.

**Reversão.** `normalize_convention --revert <json>` no **mesmo** banco (o JSON tem os pks).
Mesmo padrão dos reverts anteriores. Confirme relendo (sob RLS não há problema aqui —
catálogo é global — mas releia mesmo assim: "não deu erro" não é prova).

> ### CÓDIGO DA FASE 3 PRONTO — escrito em 2026-09-20, ainda NÃO rodado em banco `[Rev.2]`
>
> `normalize_convention` virou a 3ª exceção, `SafeWriteCommand`, com `--out`,
> relatório de NÃO MIGRADOS completo (3 baldes, lista inteira) e por marca.
> **17 travas novas** em `NormalizeLarguraNoLugarCertoTests`; suíte em **634 testes**
> com as 2 vermelhas de sempre (i18n `vendas/fotos.py` + tenancy `DefeitoTipo`/
> `ProvaFoto`, ambas de `12c414e`). Nada foi gravado em banco nenhum.
>
> **Dois desvios do que este plano mandava — os dois porque o plano estava errado:**
>
> 1. **`isinstance(obj, KnownPart)`, não `hasattr(obj, "bus_width")`.** O plano
>    sugeria o `hasattr` como guarda contra a família entrar. Só que a F1 deu
>    `bus_width` **também** à `ChipFamily` — o `hasattr` passaria a ser sempre
>    verdadeiro e a família entraria no backfill, que é exatamente o que o dossiê
>    §5.1 proíbe (o próximo `load_brands` desfaria).
> 2. **`_revert` agora usa `.update()`, não `save()`.** O teste de ida-e-volta
>    pegou: restaurar `interface='x16'` é uma MUDANÇA, e o portão de largura (I2)
>    a recusa — com razão. O revert estourava no meio. Pior, `interface='DDR3'`
>    restaurada seria **apagada** pela regra 3 do `apply_kp_convention` rodando por
>    cima da reversão. Reverter é restaurar um estado que estava no banco, não
>    escrever dado novo; o `.update()` é o mesmo caminho por onde o legado entrou,
>    e em Postgres os gatilhos do pghistory continuam capturando.
>
> **Duas coisas que o plano não previu:**
>
> - `notes` que já declara `Speed:` com OUTRO valor. A nova entra ao lado (I5 —
>   mover nunca apaga) e o dry-run lista esses casos numa seção própria. Não
>   bloqueia a migração.
> - **O relatório tinha linha invisível.** A 1ª exceção (densidade, 2026-07-11)
>   nunca teve contador: aqueles registros entravam no total e não apareciam em
>   balde nenhum. Só se viu porque o dry-run de 20/09 deu `KnownParts a migrar:
>   3682` enquanto os baldes visíveis somavam 3.702 — a conta não fechava dos dois
>   lados. Agora o relatório traz a densidade e uma **conferência dos baldes** com
>   as duas contas e a diferença, porque um mesmo registro pode estar em dois.
>   Um `--commit` não pode ter linha que o dono não viu.
>
> **Como o dry-run se parece** (dados sintéticos, 9 registros):
>
> ```
>   KnownParts a migrar:      5
>
>   bus_width — LARGURA NO LUGAR CERTO (5 KnownPart):
>     [    1x] x16                    ->  bus_width
>     [    1x] x16 @ <velocidade>     ->  bus_width + notes 'Speed:'
>     [    1x] @ <velocidade>         ->  notes 'Speed:'
>     por marca:
>       [    3x] Micron
>       [    2x] Samsung
>
>   ⚠ NAO MIGRADOS (3 KnownPart) — decisao humana; a largura destes fica onde esta:
>     -- SOBRA SEM DESTINO (1) --
>        SOBRA001    interface='x16 (2 dies)'  [DDR3]
>     -- CONTRADICAO (1) --
>        CONTRA001   interface='x16'  bus_width='x8'  [DDR3]
>     -- CLASSE NAO PERMITE (1) --
>        CLASSE001   interface='x8'  [eMMC]
> ```
>
> ### DRY-RUN NO BANCO LOCAL (dump de prod) — 2026-09-20, nada gravado `[Rev.2]`
>
> **3.539 KnownPart** com largura no lugar errado, e os três cortes batem com a
> Fase 0 casa a casa: largura pura 836+519+243+144+17 = **1.759**; largura+velocidade
> 595+452+276+242+92 = **1.657**; só velocidade **123**. Por marca também fecha em
> 3.539 — Micron 2.909 · Samsung 175 · Nanya 154 · PieceMakers 92 · Winbond 84 ·
> SK Hynix 70 · Kingston 24 · ESMT 21 · GigaDevice 6 · Foresee 4.
>
> **NÃO MIGRADOS: 0** — os três baldes de risco seguem vazios, como em 19/09.
>
> **A conferência fecha a aritmética, e ela não é uma soma.** O comando planeja
> 3.682 KnownPart distintos, mas os baldes somam 3.702 — **20 registros estão em
> dois baldes**, e os 20 têm nome:
>
> | | |
> |---|---:|
> | chip_type canônico (KnownPart) | 0 |
> | densidade (exceção 1) | 0 |
> | geração/`subtype` (exceção 2) | 161 |
> | protocolo resgatado do subtype | 2 |
> | largura (exceção 3) | **3.539** |
> | soma dos baldes | 3.702 |
> | REGISTROS distintos | **3.682** (20 em dois baldes) |
>
> Os **2** do protocolo resgatado são, por construção, um subconjunto dos 161 — a
> exceção 2 só escreve na `interface` quando também escreve no `subtype`. Os
> outros **18** são eMCP/uMCP que ganham geração no `subtype` **e** têm velocidade
> (`@ 1866MHz`) na `interface`: migram pelos dois caminhos sem um atropelar o
> outro, e não ganham largura (eMCP não tem — I3). `3.539 + 161 − 18 = 3.682`.
> As 3 famílias `'RAM' → 'DDR'` são `ChipFamily`, contadas à parte.
>
> Se o dry-run trouxer NÃO MIGRADOS > 0, é caso novo entrado depois de 19/09 e
> precisa de decisão antes do `--commit`.

> ### FASE 3 APLICADA NO BANCO LOCAL — 2026-09-20 `[Rev.2]`
>
> `✅ aplicado (3685 mudancas)` = 3.682 KnownPart + 3 ChipFamily (`'RAM' → 'DDR'`).
> Reversível em `normalize_convention_revert_LOCAL_20260920.json`.
>
> | verificação | resultado |
> |---|---|
> | 2ª rodada (idempotência) | `KnownParts a migrar: 0` ✅ |
> | `MEDIR` — largura em `interface` de KnownPart | **0** em todos os baldes ✅ |
> | `MEDIR` — LARGURA+SOBRA · classe não permitida · divergência known×família | 0 · 0 · 0 ✅ |
> | `--diff` — `dest_label` · `profitable` · `is_dead` · `price_key` | **intactos**: as 2.145 mudanças são só `interface` (2.086) e `subtype` (59) ✅ |
> | `ChipFamily.interface` LARGURA_PURA | segue 25 — é a Fase 4, ainda não rodada em banco |
>
> **Por que o `--diff` mostra 2.086 e não 3.539?** É o C1 confirmado no banco: para
> os known **com** família a tela nunca leu o `interface` do registro, então
> esvaziá-lo não muda pixel nenhum. Só os 2.086 do caminho *known sem
> família/FBGA* aparecem. Os 1.453 restantes migraram no dado sem mexer na tela.
>
> **Duas observações que a rodada trouxe** (nenhuma é motivo de parada — as três
> colunas ficaram intactas):
>
> 1. **`'@ NSR' → ''` em 6 registros.** O `split_bus_width` tratou `NSR` como
>    velocidade e escreveu `Speed: NSR` nas notes. Não perdeu dado (I5), mas `NSR`
>    não é velocidade — provavelmente *No Speed Rating* do importador da Micron.
>    Fica para o dono decidir se vira nota melhor.
> 2. **`'LPDDR4X' → 'LPDDR4'` em 1 PN na TELA** — e a transição **não existe** no
>    relatório do comando. `DIAGNOSTICAR_lpddr4x.py` (read-only) achou o culpado
>    entre os 161: **KM4X6001KM**, família KM4 (`subtype: LPDDR4X`), `emcp_ram`
>    dizendo `'LPDDR4 2GB'`.
>
>    **A causa é anterior a esta tarefa, e a lição vale mais que o registro.** Em
>    2026-07-04 a família KM4 foi corrigida no yaml de LPDDR4 para LPDDR4X — e o
>    comentário dessa correção cita *este mesmo part number* como prova (Preduo:
>    Sub-Type "eMMC+LPDDR4x"; página oficial Samsung do KM4X6001KM-B321: 16Gb
>    LPDDR4X a 0,6 V). A correção arrumou a GRAMÁTICA e deixou o REGISTRO para
>    trás. Enquanto o `subtype` do registro estava vazio, a tela lia a família e o
>    erro ficou invisível por dois meses e meio. A exceção 2 promoveu o `LPDDR4`
>    de dentro do `emcp_ram` para o `subtype`, registro venceu gramática, e o erro
>    apareceu. **Corrigir a família não corrige o que já está escrito no
>    known_part** — e campo vazio esconde a dívida em vez de sinalizá-la.
>
>    Correção pelo canal normal: `submissions/samsung_km4x6001km_lpddr4x_2026-09-20.yaml`
>    (`subtype → LPDDR4X`, `emcp_ram → 'LPDDR4X 2GB'`; a capacidade não muda). São
>    CONFLITO, então quem aplica é o `resolve_conflicts --fields subtype,emcp_ram`
>    — `confidence` fica como está, é correção de dado e não de autoridade.
>    **Em produção, aplicar ANTES do backfill rodar lá**, e a regressão nunca
>    acontece.
>
> ⚠ O baseline `baseline_bus_width_ANTES_local.json` é anterior à Fase 1 e **não
> cobre `bus_width`/`bus_width_source`** — o `--diff` avisa e ignora as duas
> colunas. Regravar na Fase 7.

### Fase 4 — As 25 famílias: yaml → `load_brands` (D7)

**Objetivo.** A largura fixa de família muda de chave no yaml (fonte da verdade da
gramática) e entra no banco pelo canal normal.

**Mudanças (3 arquivos, 25 linhas, mais nada):**
- `chips/knowledge/esmt.yaml`: 21 famílias `interface: xN` → `bus_width: xN`.
- `chips/knowledge/samsung.yaml`: `K4G` (:739 `x32`), `K4W` (:991 `x16`), `K4Z` (:1027 `x32`).
- `chips/knowledge/foresee.yaml`: `F60C` (:249 `'x16'`).
- **Não toque** em `K9C` (:1171 `NAND (x8/x16)`) nem `K9HDG` (:1243 `NAND (x8)`): não são
  tokens; ficam para o dono decidir (multi-largura não cabe no vocabulário fechado —
  cabe no registro, que é onde a largura de fato mora).
- Golden: `_ESMT_GOLDEN`/`_SAMSUNG_GOLDEN`/`_FORESEE_GOLDEN` em `chips/tests.py` **não**
  mudam (`_ident()` não olha largura). Adicione **um** caso por marca em
  `EngineBusWidthTests` provando que a família yaml → resultado `bus_width` (ex.: um PN
  M15T da ESMT → `x16`).
- `chips/tests.py:2555` (`FamilySpec(prefix="K4B", chip_type="DDR3", interface="x16")` →
  esperava `"x16"` ficar): **vira o oposto** — `interface="x16"` levanta `ValueError`; e
  `FamilySpec(..., bus_width="x16").bus_width == "x16"`. É mudança de especificação de
  propósito (I2), não regressão — comente a linha com a data.
- `chips/tests_submissions.py:228-243`: `test_interface_fica_o_mais_especifico` usava
  `"x16 @ 800MHz (1600MTPS)"` como exemplo de `interface` — agora o portão rejeita esse
  par. Troque o exemplo para protocolo (`"eMMC 4.41"` × `"e.MMC 4.41 (JESD84-A441)"`, que
  já é o 2º teste) e crie `test_bus_width_arquivo_vence` (`x16` no banco × `x8` no
  arquivo → `x8`, classe identidade).
- `estoque/tests.py:201-223` (`_clean_interface` com `'x16 @ 800MHz'` esperando manter):
  passa a esperar `''` + `bus_width`. Mudança de spec de propósito, datada.

**Comandos (dono):**

```bash
env -u DATABASE_URL python manage.py load_brands --brand esmt          # dry-run = portão; diff mostra 21 famílias com bus_width
env -u DATABASE_URL python manage.py load_brands --brand samsung
env -u DATABASE_URL python manage.py load_brands --brand foresee
env -u DATABASE_URL python manage.py load_brands --brand esmt --commit && …samsung… && …foresee…
env -u DATABASE_URL python manage.py characterize_baseline --diff baseline_bus_width_ANTES_local.json --summary
# prod (depois do push do yaml):
python manage.py load_brands --brand esmt --commit ; python manage.py load_brands --brand samsung --commit ; python manage.py load_brands --brand foresee --commit
python manage.py guard_catalog
```

**Diff esperado no baseline:** `interface` `'x16' → ''` nos PNs dessas 25 famílias que
saem pela gramática ou por known-com-família (os 57 + 10 de agosto); `bus_width` novo
(coluna ignorada até regravar). Três colunas intactas.

**Critério de pronto.** Dry-run das 3 marcas passa no portão; commit local; baseline
como acima; push; commit em prod; `MEDIR_bus_width.py` mostra `ChipFamily` com
LARGURA_PURA = 0 (restam só `K9C`/`K9HDG` na lista "largura DENTRO de texto"); teste de frontend: um PN M15T
(ESMT) mostra "Largura x16", `K4W…` mostra `x16`.

**Reversão.** `git revert` do yaml + `load_brands --commit` de novo (o yaml manda).

### Fase 5 — Fechar a porta no banco: `interface` nunca mais é largura (migration 2)

**Objetivo.** Tornar o erro de classe **impossível**, não improvável (dossiê §7.2) —
inclusive para `.update()`/`bulk_create`/SQL cru/admin, que não passam pelo `clean()`.

**Pré-voo obrigatório (read-only, prod):** `MEDIR_bus_width.py` com **zero** registros
em LARGURA_PURA/LARGURA+VELOCIDADE/VELOCIDADE_SÓ em `KnownPart` **e** em `ChipFamily`
(os 2 `NAND (x8…)` não casam a constraint, ver abaixo). Constraint adicionada com
violador existente **explode o build do Render** (foi a `price_origin_emmc_only` em
2026-08-01) — aqui isso seria um deploy travado com o site no ar, não corrupção, mas
ainda assim: não empurre sem o pré-voo.

**Mudanças.** `chips/models.py` `Meta.constraints` de `KnownPart` e `ChipFamily`:
```python
# I2: largura NUNCA mora em `interface` — só os tokens exatos (portável Postgres/SQLite);
# o resto (`x16 @ …`, `X16 `) é barrado pelo clean()/portão Pydantic. Espelho de BUS_WIDTH_VOCAB.
models.CheckConstraint(
    condition=~models.Q(interface__in=BUS_WIDTH_VOCAB + tuple(t.upper() for t in BUS_WIDTH_VOCAB)),
    name="knownpart_interface_nao_e_largura"),
```
`makemigrations chips` → `chips/0025_…` (só `AddConstraint`; nada de pghistory aqui —
constraints em `Meta` não são espelhadas no event table, ver comentário em
`models.py:128-132`). Não use `__iregex`: não é portável para a suíte em SQLite e
regex em `CHECK` é o tipo de coisa que passa no local e cai em prod.

**Travas.** `InterfaceNaoELarguraTests` ganha o caso de banco: `KnownPart.objects.filter(pk=…).update(interface="x16")` → `IntegrityError` (prova que é o **banco**, não o `clean()`); `update(interface="eMMC 5.1")` passa. Espelho: os tokens da constraint == `BUS_WIDTH_VOCAB` (2 caixas).

**Comandos (dono).** Local: `migrate` + suíte + `MEDIR`. Prod: **push** (build migra).
Depois `guard_catalog`.

**Critério de pronto.** Build do Render verde na 0025; `guard_catalog` verde; o teste de
banco passa.

**Reversão.** `migrate chips 0024` (remove a constraint; dado intacto).

### Fase 6 — Ferramentas de largura, documentação e memória

**Objetivo.** Ninguém mais lê nem escreve "largura em `interface`" — nem humano, nem
chat de marca, nem coletor.

- `COLETAR_largura_bits.py`: `largura_do_banco` (:114-120) lê `kp.bus_width` (e **só**
  ele — não caia no `interface` "por compatibilidade": seria reabrir a porta); `.only()`
  (:160-162) troca `interface` por `bus_width`; docstring/§ "A REGRA" e a folha de
  diagnóstico (:375-381) passam a citar `bus_width`. Rode a Samsung de novo e **confira
  que os 93 do ouro continuam 93** (é o teste de regressão do coletor — 52 diretas + 41
  por regra, K4B 100 acordos / 0 divergências / 3 larguras). Se der diferente, a
  migração perdeu algo: pare.
- `HANDOFF_largura_barramento.md`: §3 (circularidade) e §4 Etapa 2 ("o campo `interface`
  já é a largura" → `bus_width`), Etapa 7 item 6 (formato do campo), §8. **E corrija o
  canal**: known_part não vai no yaml (Opção 2); largura nova de PN já aprovado entra por
  `submit_known_parts --fill-empty` (campo vazio → preenche) ou, se já houver valor
  diferente, por `resolve_conflicts` (classe identidade: arquivo vence). **[Rev.1] Ganha
  a Etapa 9 — "família PROVADA vira `decode_width_*` no yaml"**: o relatório do coletor
  (acordos/divergências/larguras) vai no `reasoning` da família, o chat de marca abre a
  Trilha A, e o golden recebe âncoras x4/x8/x16. É assim que a prova do coletor chega ao
  operador: pela gramática em leitura, nunca escrevendo o PN decodificado no catálogo.
  A tabela de gramática por marca do Apêndice D §6
  (Samsung `pn[5:7]`, SK Hynix `pn[6]`, Nanya `M<largura>`, ESMT, PieceMakers, Kingston;
  **Micron não decodifica** — é FBGA, só catálogo) é o ponto de partida, **não a prova**:
  cada família passa pela barra antes de entrar no yaml.
- `PROMPT_chat_Samsung_largura_2026-09-12.md`: `interface` → `bus_width` em todo lugar;
  "grave com `load_brands`" → "entregue a submissão; o dono roda `submit_known_parts
  --fill-empty --commit`". Se o chat da Samsung já tiver entregado com `interface: x8`,
  o portão explica; ele troca a chave.
- `check_k4b_x4x8.py`: só comentário no topo — "planilha, nunca banco (I4)".
- `CLAUDE.md`: §5 (linha 482) e §6 (linha 589) passam a dizer: *"`interface` = versão de
  protocolo (eMMC 5.1 / UFS 3.1) ou vazio — nunca largura; `bus_width` = largura do
  barramento de dados (x4/x8/x16/x32/x64) de datasheet — nunca deduzida do PN; vazio em
  eMMC/UFS/eMCP/uMCP"*; a tabela de §6 ganha a linha; §7 ganha UM bullet curto
  ("LARGURA E PROTOCOLO NO MESMO CAMPO — separados em 2026-09-12") apontando para este
  plano e para as 3 correções do §2.0 (C1 em especial: known.interface nunca chegou à
  tela com família); §9 lista `PLANO_BUS_WIDTH.md`. A linha 1201 (torneira RAM "depende
  da largura, que vive no `interface`") → `bus_width`.
- `AUTORIA.md`: §3.1 (anatomia: `bus_width`), §3.2 (o portão rejeita largura em
  `interface`, com a mensagem), tabela de política de `resolve_conflicts` (linha
  `bus_width` = identidade, arquivo vence), e um parágrafo **"largura de barramento
  nunca vem do PN"** (I4).
- `SAMSUNG.md` linha ~109 (`46` = x4 — errado, HANDOFF §4 Etapa 1) e a classificação de
  K4W: pendências do dossiê; corrija se o chat da Samsung ainda não corrigiu.
- `chips/admin.py:47-50`: a `description` do fieldset explica os dois campos.
- Memória do projeto (`project_memory_write`): `wtc-bus-width-campo-separado.md` com as
  decisões D1–D8, as 3 correções, e a regra I4; linha no `MEMORY.md`. A memória
  `wtc-interface-vocabulario-fechado-emmc-ufs` ganha um parágrafo "a linha `x4…x64` saiu
  da tabela de `interface` em 2026-09-12 — é `bus_width`".

**Critério de pronto.** `grep -rn "interface" COLETAR_largura_bits.py HANDOFF_largura_barramento.md PROMPT_chat_Samsung_largura_2026-09-12.md` só devolve menções ao campo de **protocolo** ou à história ("antes vivia em `interface`"); coletor da Samsung = 93; `check_translations` e suíte verdes; CLAUDE.md atualizado (o dono lê o diff).

> ### FASE 4 APLICADA NO LOCAL — 2026-09-20 `[Rev.2]`
>
> `load_brands --commit` nas três marcas. **`ChipFamily.interface` LARGURA_PURA = 0**:
> 155 VAZIO · 118 PROTOCOLO · 4 OUTRO (as 3 Kingston bogus + `K4Y DRSL`, Rambus
> legítimo). Sobraram só os dois `K9C`/`K9HDG`, largura dentro de texto de
> protocolo, que ficam por decisão do dono.
>
> **`--diff`: 2.229 linhas, e nenhuma é dinheiro.** `interface` 2.170 · `subtype`
> 58 · `emcp_ram` 1. `dest_label`, `profitable`, `is_dead` e `price_key`
> intactos pela terceira medição seguida.
>
> Comparando com o `--diff` de antes da F4 (2.145), os três deltas têm nome:
>
> - **`interface` +84** — a largura das 25 famílias saindo da tela: `'x16'` +50,
>   `'x32'` +30, `'x8'` +4. É o conserto, não efeito colateral: nesses PNs o que
>   aparecia como *"Interface x16"* passa a aparecer como *"Largura x16"*.
> - **`subtype` −1 e `emcp_ram` +1** — é o **KM4X6001KM**. A regressão
>   `'LPDDR4X' → 'LPDDR4'` **sumiu** da lista de subtype (era a única linha em que
>   a tela perdia informação), e no lugar dela está a correção do `emcp_ram`.
>   O buraco que o `--diff` encontrou foi fechado e o próprio `--diff` prova.
>
> **Efeito de borda não previsto, e bom:** o censo mostra OUTRO caindo de 265 para
> 185 — **80 registros Samsung** (a marca inteira do delta: Samsung OUTRO 179→99)
> perderam a GERAÇÃO DE RAM que estava no `interface` (`'DDR3'` −36, `'DDR3L'`
> −31, `'DDR4'` −13). Não foi o backfill nem o `load_brands`: foi a submissão dos
> 168 passando pelo `save()` → `full_clean()` → regra 3 do `apply_kp_convention`,
> que proíbe geração no `interface` desde antes desta tarefa e limpou o legado ao
> reencostar nele. Zero impacto de tela (C1: nesses PNs a família manda), e é o
> achado lateral da Fase 0 sendo pago sozinho.

> ### FASE 6 FEITA — 2026-09-20 `[Rev.2]`
>
> **Ferramentas**
> - `COLETAR_largura_bits.py` lê `kp.bus_width` (e **só** ele — o comentário no
>   código explica por que "tenta bus_width, senão interface" seria reabrir a
>   porta que a F5 fecha). Tabela de organização completa: 12 códigos em vez de
>   6; empilhados e `2CS` vão para REVISAR com motivo próprio.
> - **Exclusão da circularidade**: o coletor lê `submissions/*largura_decodificador*.yaml`
>   e tira aqueles PNs da contagem de prova. Sem isto a família **K4A** apareceria
>   com 61 acordos / 0 divergências e seria promovida a PROVADA por dados que a
>   própria regra escreveu. Com: 0 acordos, sem prova. Visível na saída.
> - **Teste de regressão passou: OURO = 93** (x4 34 · x8 59), igual a antes do
>   backfill. K4B PROVADA com **100** acordos — o mesmo 100 medido no CSV
>   (73 DDR3 + 27 DDR3L) e no cruzamento do decodificador. Três vias, um número.
>   K4N segue QUEBRADA pelas duas divergências de sempre.
> - `IDENTIFICAR_largura.py`: mesma tabela de 12 códigos, com o `02` (x2) marcado
>   como fora do `BUS_WIDTH_VOCAB`.
>
> **Tela — o buraco que a regra da gramática expôs**
> - `decode_card.html` (2 blocos) e `confirm_card.html` agora imprimem a
>   PROCEDÊNCIA: `banco` sai limpo, `gramatica` sai com *"lido do PN"*, `familia`
>   com *"da família"*, em cinza itálico (`.bw-src`) e com tooltip dizendo que
>   não vale como preço. Fonte vazia não ganha etiqueta (fail-open: etiquetar por
>   ignorância também seria mentir).
> - 4 strings novas traduzidas e compiladas em es/en/zh-hans.
> - `ProcedenciaDaLarguraNaTelaTests`: 5 travas, incluindo a que prova que o
>   RÓTULO traduz e o TOKEN `x8` não.
> - ⚠ Um portão da casa mordeu no caminho: `{# #}` é comentário de UMA linha e o
>   `TemplateMultilineCommentTests` reprovou. Use `{% comment %}`.
>
> **Documentação**
> - `CLAUDE.md` §5 e §6: `interface` = protocolo, `bus_width` = largura, com a
>   regra de fonte (datasheet **ou** decodificador oficial da marca; nunca a
>   gramática do nosso yaml).
> - `HANDOFF_largura_barramento.md`: §3 ganhou a exceção do decodificador **e** a
>   armadilha que ela abre; Etapa 2 trocou o campo e avisa que ler `interface`
>   hoje devolve vazio para todos — falha silenciosa, não erro; Etapa 7 corrige o
>   CANAL (`submit_known_parts --fill-empty`, não yaml); §7 traz a fila medida.
> - `AUTORIA.md`: `bus_width` na lista de campos de família, na tabela de classes
>   do `resolve_conflicts` (com o aviso de nunca usar "o mais longo vence"), e o
>   exemplo de `interface` trocado — o antigo já não existe mais no banco.
> - `PROMPT_chat_Samsung_largura_2026-09-12.md` e `check_k4b_x4x8.py`: atualizados.
>
> **Não feito de propósito:** a "Etapa 9 — família PROVADA vira `decode_width_*`"
> que a Rev.1 previa. A decisão do dono sobre a gramática (§5.1) tirou isso do
> caminho crítico: declarar `decode_width_*` serve para dar palpite em PN novo na
> bancada, não para fazer largura existir. Fica para depois da Parte 2, se valer.
>
> **Suíte: 639 testes**, só as 2 vermelhas herdadas do `12c414e`.

### Fase 7 — Verificação final e entrega

1. **Baseline regravado** depois de tudo (`characterize_baseline --out
   baseline_bus_width_DEPOIS_PROD.json`) — passa a cobrir a coluna `bus_width` daqui em
   diante.
2. `--diff` ANTES→DEPOIS com `--summary`: **AS TRÊS COLUNAS INTACTAS**; transições de
   `interface` só `'xN…' → ''`; nenhum PN adicionado/removido.
3. `guard_catalog` verde; `MEDIR_bus_width.py` em prod: KnownPart e ChipFamily com
   LARGURA em `interface` = 0; `bus_width` preenchido = nº do relatório do backfill +
   famílias.
4. Suíte inteira verde: `python manage.py test chips estoque vendas pricing --settings=core.settings_test`; `check_translations`; `makemigrations --check`.
5. **Testes de frontend entregues ao dono** (lista concreta, ele roda na bancada):
   `K4B1G0846I` → Largura x8 · `K4B1G1646D` → x16 · um M15T (ESMT) → x16 · um LPDDR5
   Micron → x64 · `KLMAG2GESD-B03Q` (eMMC) → Interface eMMC 5.1, sem linha Largura ·
   um eMCP → sem linha · trocar idioma para 中文 → `位宽` · lançar um DDR3 num lote novo
   e conferir no admin `bus_width='x16'`, `interface=''` · abrir um lote **antigo** e
   conferir que a linha de agosto continua `interface='x16'` no admin (D6).
6. Mutações registradas no PR: para cada classe de teste nova, a mutação que mordeu
   (é a convenção da casa — "garantia que você não tentou desligar não é garantia").

---

## 5. Ordem, portas e ambientes

| fase | pré-condição (a porta) | ambiente | prova que fecha a porta |
|---|---|---|---|
| F0 medir | dump fresco de prod restaurado localmente | local + prod (read-only) | tabelas do censo + 2 baselines gravados; OUTRO listado e decidido |
| F1 schema | F0 fechada; `git status` limpo do que não é seu | local → push (build migra) | `migrate` local; suíte; baseline IDÊNTICO; deploy ok; `guard_catalog` |
| F2 portões/engine/telas/comandos | F1 (mesmo PR é o recomendado) | local → push | suíte (+8 classes); `check_translations`; baseline IDÊNTICO; deploy ok |
| F3 backfill KnownPart | **código F2 no ar em prod**; Render Export fresco | local (dump) → prod | dry-run bate com F0; `--commit`; 2º dry-run = 0; `--diff` três colunas intactas; `MEDIR` = 0 largura em `interface` (KnownPart) |
| F4 yaml 25 famílias | F2 no ar (o portão rejeita a chave velha) — recomendado no MESMO PR da F2 | local → push → `load_brands --commit` prod | dry-run das 3 marcas; `MEDIR` = 0 em `ChipFamily` (menos `K9C`/`K9HDG`, largura dentro de texto) |
| F5 constraint `interface` | F3 **e** F4 fechadas em prod; pré-voo `MEDIR` prod = 0 | local → push (build migra) | build verde na 0025; teste de banco; `guard_catalog` |
| F6 ferramentas + docs | F5 | local → push | coletor Samsung = 93; docs; memória |
| F7 verificação | tudo acima | prod | baseline DEPOIS; testes de frontend do dono |

**Sequência de deploys recomendada (3 pushes):** (1) F1+F2+F4 num PR — schema + código +
yaml; depois o dono roda, em prod, `load_brands --commit` das 3 marcas e o backfill (F3);
(2) F5 — a constraint, só depois do pré-voo; (3) F6 — docs/ferramentas (pode ir junto com
F5 se estiver pronto). Entre (1) e (2) o sistema já está correto; a constraint é o
cadeado.

**O que NUNCA acontece nesta tarefa:** `migrate` local contra prod; `resnapshot_lote`
em lote antigo (D6); escrita em `ChipFamily` por comando (só yaml → `load_brands`);
qualquer largura escrita no CATÁLOGO a partir do PN, do lote ou da revisão (I4/E3); shim
no engine lendo largura de `interface`; toque em `price_key`/pricing/caixa/rentabilidade
**na Parte 1** (D1 revisada — é a Parte 2, §10); apagar a velocidade da Micron (D4).

---

## 6. Runbook do dono — os comandos, na ordem (sem `git push`: é sempre por conta dele)

```bash
# ── F0 (read-only) ──────────────────────────────────────────────────────────
env -u DATABASE_URL python MEDIR_bus_width.py
env -u DATABASE_URL python manage.py characterize_baseline --out baseline_bus_width_ANTES_local.json
python MEDIR_bus_width.py                                       # prod — confira o banner
python manage.py characterize_baseline --out baseline_bus_width_ANTES_PROD.json

# ── F1+F2+F4 (depois do PR revisado; LOCAL) ─────────────────────────────────
env -u DATABASE_URL python manage.py migrate
env -u DATABASE_URL python manage.py test chips estoque vendas pricing --settings=core.settings_test
env -u DATABASE_URL python manage.py check_translations
env -u DATABASE_URL python manage.py makemigrations --check --dry-run
env -u DATABASE_URL python manage.py load_brands --brand esmt        # dry-run ×3 (esmt/samsung/foresee)
env -u DATABASE_URL python manage.py load_brands --brand esmt --commit   # ×3
env -u DATABASE_URL python manage.py characterize_baseline --diff baseline_bus_width_ANTES_local.json --summary
#   → esperado: TRÊS COLUNAS INTACTAS; só `interface` 'xN'→'' nas 25 famílias; aviso "coluna bus_width ausente no baseline"

# ── F3 LOCAL (contra o dump de prod) ─────────────────────────────────────────
env -u DATABASE_URL python manage.py normalize_convention
env -u DATABASE_URL python manage.py normalize_convention --commit --out normalize_convention_revert_LOCAL_$(date +%Y%m%d).json
env -u DATABASE_URL python manage.py normalize_convention           # "KnownParts a migrar: 0"
env -u DATABASE_URL python manage.py characterize_baseline --diff baseline_bus_width_ANTES_local.json --summary
env -u DATABASE_URL python MEDIR_bus_width.py
env -u DATABASE_URL python COLETAR_largura_bits.py                  # só depois de o COLETAR ler bus_width (F6): ouro Samsung continua 93

# ── push (1) → build do Render migra 0024/0026 → depois: ────────────────────
python manage.py guard_catalog
python manage.py load_brands --brand esmt --commit ; python manage.py load_brands --brand samsung --commit ; python manage.py load_brands --brand foresee --commit
python manage.py normalize_convention                               # dry-run PROD — bate com o MEDIR de prod?
python manage.py normalize_convention --commit --out normalize_convention_revert_PROD_$(date +%Y%m%d).json
python manage.py normalize_convention                               # 0
python manage.py characterize_baseline --diff baseline_bus_width_ANTES_PROD.json --summary
python MEDIR_bus_width.py                                           # pré-voo da F5: zero largura em interface
python manage.py guard_catalog

# ── push (2): constraint (F5) → build migra 0025 → ──────────────────────────
python manage.py guard_catalog
python manage.py characterize_baseline --out baseline_bus_width_DEPOIS_PROD.json
```

Reversões, se precisar: `normalize_convention --revert normalize_convention_revert_<BANCO>_<data>.json`
(no mesmo banco); yaml = `git revert` + `load_brands --commit`; migrations = commit anterior
+ build (nunca `migrate` à mão em prod).

---

## 5.0 ONDE A LARGURA VALE DINHEIRO — decisão do dono, 2026-09-20 `[Rev.2]`

> *"olha LPDDR não me importo quase nada na vdd, o mais importante é o DDR e
> DDRL, esses sim, LPDDR é o que vem de celular e pra mim a largura dele n
> importa."*

Três baldes, e só um é trabalho:

| balde | largura interessa? | por quê |
|---|---|---|
| **DDR / DDR2 / DDR3 / DDR3L / DDR4 / DDR5 / SDRAM** | **SIM** | é o mercado do comprador; x4/x8 (78 bolas) × x16 (96 bolas) é o corte de preço |
| LPDDR / LPDDR2…5X | não | vem de celular; o dono não diferencia |
| GDDR | não | fora do negócio desde 2026-07-23 (sempre NÃO RENTÁVEL) |

**Isto redimensiona a fila de pesquisa.** A primeira leitura do buraco deu
"3.079 DRAM sem largura" e parecia enorme — mas **~2.9 mil são LPDDR**, quase
todos Micron (LPDDR4X 1.361 · LPDDR4 722 · LPDDR3 169 · LPDDR5 75). Filtrando
pelo balde comercial sobram poucas centenas, e concentradas: Samsung DDR4,
SK Hynix DDR3/DDR4, Rayson, PieceMakers. **Essa é a fila de verdade.**

O `VERIFICAR_largura.py` imprime os três baldes separados e só detalha o
comercial — a linha "← este é o trabalho real".

⚠ Isto NÃO muda a Parte 1: o backfill já moveu a largura de tudo que tinha,
LPDDR incluída (o dado já existia, não custou nada e não se joga fora). Muda
o que se PESQUISA daqui para frente, e muda a Parte 2: o eixo de preço nasce
no DDR, não na LPDDR.

---

## 5.0.1 SAMSUNG: o decodificador do fabricante É Tier-1 (dono, 2026-09-20) `[Rev.2]`

O dono autorizou tratar o **decodificador oficial de part number da Samsung** como
fonte Tier-1 da marca — diferente da gramática do nosso yaml, que é transcrição
nossa. Samsung, *"Component DRAM Ordering Information"*: o PN tem 11 campos e o
**campo 5 é "Bit Organization"**. Legenda oficial, 12 códigos:

```
02: x2 · 04: x4 · 06: x4 Stack (Flexframe) · 07: x8 Stack (Flexframe) · 08: x8
15: x16 (2CS) · 16: x16 · 26: x4 Stack (JEDEC) · 27: x8 Stack (JEDEC)
30: x32 (2CS, 2CKE) · 31: x32 (2CS) · 32: x32
```

Em `K4B2G0846D`: K(1) 4(2) B(3) 2G(4) **08**(5) → x8. É o `pn[5:7]` de sempre.

⚠ **Nossa transcrição tinha 6 dos 12 códigos** (faltavam 02, 15, 26, 27, 30, 31).
Medido: os 268 Samsung DDR do catálogo usam só `16` (120), `08` (101), `04` (47) —
zero exposição. Completar a tabela em `IDENTIFICAR_largura.py` é item da F6.

**Validação do decodificador, por geração** — o que sustenta cada bloco dos 168:

| geração | PNs a emitir | validação INDEPENDENTE do decodificador |
|---|---:|---|
| DDR4 | 61 | 3 datasheets do domínio Samsung: `K4A4G045WD → "1Gx4"`, `K4A8G085WC → "1Gx8"`, `K4A8G165WC → "512Mx16"` ✅ |
| DDR3 + DDR3L | 67 | os 100 registros cuja largura veio do IMPORTADOR: **100/100 concordam**, 0 divergências ✅ |
| DDR5 (K4RA/RB/RC) | 21 | 2 Octopart concordam (`K4RAH086VB` x8, `K4RAH165VB` x16) — secundária ⚠ |
| DDR2 (K4T1/T5) | 14 | nenhuma — anda só no decodificador ⚠ |
| DDR1 (K4H5) | 5 | nenhuma — anda só no decodificador ⚠ |

Os **128 que valem dinheiro** (DDR3/3L/4) estão validados por duas vias
independentes. Os 19 de DDR2/DDR1 andam só no decodificador — e errar ali custa
zero, porque o dono já os declarou fora do mercado.

**`source_url` fica VAZIO de propósito.** Os 168 atravessam 13 famílias e 5
gerações, e as três âncoras são todas DDR4: pendurar um datasheet de DDR4 4Gb
RDIMM como "fonte" de um DDR5 pareceria verificação sem ser. A fonte real é o
decodificador, e ele mora no cabeçalho do arquivo de submissão — que é
versionado no git, PN por PN.

⚠ **Circularidade (HANDOFF §3).** Depois desta submissão a largura Samsung DDR do
catálogo é majoritariamente derivada do decodificador. O `COLETAR_largura_bits.py`
não pode mais usá-la como prova independente da regra posicional — e não precisa:
a regra está provada por documento do fabricante. F6: famílias Samsung DDR entram
como "regra provada por documento" e o coletor as pula.

---

> ### SAMSUNG APLICADA NO LOCAL — 2026-09-20 `[Rev.2]`
>
> `✓ 168 aprovado(s) COMPLETADO(s)` — só `bus_width`, nenhum status mexido.
> Reversível em `var/reverts/fill_kp_revert_20260920_170512.json`.
>
> | | antes | depois |
> |---|---:|---:|
> | KnownPart com largura | 3.416 | **3.584** |
> | DRAM de PC coberta | 88,1% | **95,3%** |
> | fila comercial — Samsung | 170 | **2** (só os RDRAM) |
> | fila comercial — total | 279 | **111** |
>
> Por largura, bate na unidade com o emitido: x16 1.112→1.184 (+72) · x8
> 761→826 (+65) · x4 335→366 (+31). Nos exemplos do `VERIFICAR_largura.py`,
> FONTE = `banco` em 100% e tela == registro.
>
> **A fila que sobra**, e é o roteiro das próximas marcas: SK Hynix 52 (DDR3 22 ·
> DDR4 11 · DDR3L 9 · DDR2 6 · DDR1 3 · DDR5 1) · Micron 44 (**42 são DDR2**, então
> 2 de verdade) · Rayson 11 · Samsung 2 (RDRAM, esquema de PN diferente) ·
> PieceMakers 1 · Toshiba 1.
>
> **SK Hynix é a próxima**, e o método está provado: procurar o decodificador
> publicado pela marca, ancorar cada código com datasheet do domínio dela, e
> cruzar contra os registros que já vieram do importador. Se a Hynix não publicar
> decodificador, são 52 datasheets e a prioridade volta para o dono.

## 5.1 A GRAMÁTICA NÃO É RÉGUA — decisão do dono, 2026-09-20 `[Rev.2]`

> Palavras dele: *"a gramática só é útil na hora de saber rápido info sobre um PN
> novo na bancada, não deve ser usada como régua para nada, ela não é atualizada
> com frequência, nossa fonte de verdade são fontes Tier-1 daquela marca."*

Isto não é um detalhe de implementação — é a hierarquia de autoridade da largura,
e ela muda três coisas deste plano:

1. **`decode_width_*` sai do caminho crítico.** O plano tratava "declarar
   `decode_width_*` nas 10 famílias corroboradas" como o passo que *faz a largura
   da Samsung chegar na bancada*. Errado: o que faz a largura existir é pesquisa
   Tier-1 entrando em `bus_width`, marca por marca. A gramática continua útil para
   o caso que o dono descreveu — **PN novo, desconhecido, chegando na bancada** —
   e só para isso.
2. **`bus_width_source='gramatica'` NUNCA alimenta preço nem rentabilidade.** Na
   Parte 2, o eixo `width_class` e a régua de rentabilidade leem largura **apenas**
   quando `bus_width_source` é `'banco'`. Largura de gramática entra na tela como
   informação, nunca no cálculo do dinheiro. Sem esta trava, um palpite de leitura
   de PN vira preço — que é exatamente o que o dono proibiu.
3. **A tela precisa dizer de onde veio.** ⚠ Hoje NÃO diz: `decode_card.html` (:91,
   :118) e `confirm_card.html` (:115) imprimem `result.bus_width` puro, sem marca
   de procedência. Uma largura adivinhada pelo PN aparece idêntica a uma confirmada
   em datasheet, e o operador não tem como distinguir. O `bus_width_source` já
   existe no resultado do `classify()` — falta chegar ao pixel. **Item novo da F6.**

**O que NÃO muda:** a ordem de precedência do engine (banco confirmado > gramática
> família > banco não-confirmado) continua certa — ela já põe o registro na frente.
E a trava da circularidade (HANDOFF §3) continua valendo em dobro: largura derivada
da gramática nunca entra no catálogo.

---

## 6.0 `resnapshot_lote` — a porta que leva a largura para os LOTES `[Rev.2]`

> Medido em 2026-09-20 (local, dump de prod), **dry-run, nada gravado**:
> **eminer 2.961 entradas · eRecyclo 324**. Não commitado — e por bons motivos.

O `resolve_conflicts` pediu "FECHE O LAÇO" depois da correção do KM4X6001KM, e o
dry-run revelou algo que muda o mapa: **`_SNAP_KEYS` já inclui `bus_width`,
`width_class` e `bus_width_source`** (a F1 deu os três campos aos 3 modelos de
lote). Ou seja: `resnapshot_lote` é a porta pela qual a largura entra nas
entradas de lote — exatamente o que a **Parte 2** precisa para a tela de compra
mostrar duas linhas (P4) e para a rentabilidade do DDR3 estreito (P2).

**Mas rodá-lo agora seria errado, por três razões:**

1. **Não é a pegada do backfill.** O comando reconcilia o lote contra o catálogo
   INTEIRO, então arrasta toda a deriva acumulada desde o último resnapshot — não
   só a largura. No dry-run apareceram, entre milhares de linhas de largura:
   `RS70B08G3` ganhando `price_tier_value: None→8.0` (entrada que não keava preço
   e passa a kear); `KMQEG0013B` com `is_emcp: False→True` + `price_kind: ''→'emcp'`;
   `KMDP60018M` com `emcp_ram: 'LPDDR4X 4GB'→'LPDDR4X 3GB'`; `NT5C128M16`/
   `NT5C256M16` indo para `price_kind: 'none'`. **Isso é dinheiro e classificação,
   não largura.**
2. **O plano já decidiu que é fora de escopo.** §7 itens 6 e 7: *"não rode
   `resnapshot_lote` por causa disso"* e *"é o dono quem decide quando"*. A Fase 3
   é catálogo; lote é D6 (informativo, intocado).
3. **A prova da F3 depende de o lote NÃO mudar.** O critério de pronto é
   `dest_label`/`profitable`/`price_key` intactos. Mexer no snapshot no mesmo
   movimento embaralharia as duas coisas.

**Onde isto entra:** na Parte 2, como passo próprio, com a lista de linhas
NÃO-largura revisada uma a uma antes do `--commit` — e rodado **por empresa**
(`--company eminer`, `--company erecyclo`), porque o escopo é fail-closed.

---

## 6.1 RUNBOOK DO SHELL DO RENDER — o que roda lá, o que NÃO roda `[Rev.2]`

> Pedido do dono em 2026-09-20: *"um guia pós-desenvolvimento de tudo que temos que
> rodar no shell do Render"*. Esta seção substitui, para produção, os comandos com
> `export DATABASE_URL` do §6 — **menos** os três marcados 🖥️, que continuam na
> máquina dele pelo motivo explicado abaixo.

### A regra que decide onde cada comando roda

O shell do Render roda **dentro** do serviço web: o `DATABASE_URL` já está no
ambiente (nada de exportar segredo — foi assim que a senha de produção vazou num
chat em 2026-09-19) e o banco está na **mesma região**, então some a latência
Paraguai→Oregon que fazia o `characterize_baseline` de prod parecer um comando de
4 horas. Lá ele leva o mesmo ~1m30s do local.

O preço é que **o disco do serviço é efêmero**: tudo que um comando escreve em
arquivo morre no próximo deploy ou restart. Daí a regra:

| classe | exemplos | onde |
|---|---|---|
| **lê e imprime** | `MEDIR_bus_width.py`, `guard_catalog`, qualquer dry-run | ✅ shell do Render |
| **escreve no banco, revert = `git revert`** | `load_brands --commit` | ✅ shell do Render |
| **escreve no banco e o revert é um ARQUIVO** | `normalize_convention --commit`, `resolve_conflicts --commit`, `resnapshot_lote --commit`, `submit_known_parts --fill-empty --commit` | 🖥️ **ver abaixo** |
| **`migrate`** | — | ❌ nunca à mão: quem migra é o **build** do Render |

**Os 🖥️ e o revert que some.** O JSON de reversão desses comandos nasce no disco
efêmero. Duas saídas, nesta ordem de preferência:

1. **Render Export fresco imediatamente antes** (regra 1b(c) do plano, já
   obrigatória para a F3). O dump é o rollback de verdade — o JSON é conveniência.
   Com o Export na mão, rodar no shell do Render é seguro e rápido.
2. Se o serviço tiver **disco persistente** montado, o JSON pode morar lá. Confira
   no shell antes: `df -h` e `ls -la /var/data 2>/dev/null`. Se existir, use
   `--out /var/data/<nome>.json`. Sem disco, não adianta escolher caminho.

Rodar da máquina do dono com `export DATABASE_URL` preserva o JSON, mas o
`normalize_convention --commit` são ~3.682 `save()` em ida-e-volta Paraguai→Oregon
— hora e meia de transação aberta. **Não vale**: use o Export + shell do Render.

### Antes de abrir o shell — a ordem que não se inverte

1. `git push` → **build do Render verde** (é ele que roda `migrate`). Banco à
   frente do código = INSERT recusado em silêncio (§7 item 1).
2. **Render Export fresco** (dashboard → banco → Export). Sem isso, não abra o shell.
3. Só então: dashboard → serviço web → **Shell**.

### A sequência da Parte 1, em produção

```bash
# ── 0. onde estou? (o shell não tem banner de banco-alvo como os comandos) ──
python manage.py showmigrations chips estoque | tail -20   # 0024/0026 aplicadas?
python manage.py guard_catalog                              # catálogo saudável ANTES

# ── 1. fotografia ANTES (mesma sessão do diff — o arquivo não sobrevive a deploy)
python manage.py characterize_baseline --out /tmp/baseline_ANTES_PROD.json
python MEDIR_bus_width.py            # confira: 3.539 com largura em interface

# ── 2. F4 — as 25 famílias (revert = git revert + load_brands de novo) ──────
python manage.py load_brands --brand esmt
python manage.py load_brands --brand esmt --commit
python manage.py load_brands --brand samsung
python manage.py load_brands --brand samsung --commit
python manage.py load_brands --brand foresee
python manage.py load_brands --brand foresee --commit

# ── 3. a correção do KM4X6001KM — ANTES do backfill, senão a regressão acontece
python manage.py submit_known_parts submissions/samsung_km4x6001km_lpddr4x_2026-09-20.yaml
python manage.py resolve_conflicts --file submissions/samsung_km4x6001km_lpddr4x_2026-09-20.yaml --fields subtype,emcp_ram
python manage.py resolve_conflicts --file submissions/samsung_km4x6001km_lpddr4x_2026-09-20.yaml --fields subtype,emcp_ram --commit

# ── 4. F3 — o backfill ──────────────────────────────────────────────────────
python manage.py normalize_convention            # LEIA: largura 3.539 · NÃO MIGRADOS 0 · conferência fecha
python manage.py normalize_convention --commit --out /tmp/nc_revert_PROD_$(date +%Y%m%d).json
python manage.py normalize_convention            # "KnownParts a migrar: 0"

# ── 4b. SAMSUNG: a largura pelo decodificador oficial (§5.0.1) ─────────────
#     DEPOIS do backfill, nunca antes: o backfill tem de bater com o censo da
#     Fase 0 (3.539 / NAO MIGRADOS 0), e preencher `bus_width` antes mudaria
#     esses numeros e criaria linhas de CONTRADICAO que nao existem.
#     O arquivo e gerado a partir do BANCO — gere no shell do Render, contra
#     prod, e nao reaproveite o gerado no local (o conjunto de PNs difere).
python GERAR_submissao_samsung_largura.py --out /tmp/samsung_largura_PROD.yaml
python manage.py submit_known_parts /tmp/samsung_largura_PROD.yaml
#     esperado: COMPLEMENTO ~168 · CONFLITO 0 · so `← bus_width`.
#     ⚠ QUALQUER CONFLITO = pare: registro com OUTRA largura, decisao humana.
python manage.py submit_known_parts /tmp/samsung_largura_PROD.yaml --fill-empty --commit

# ── 5. provas ───────────────────────────────────────────────────────────────
python manage.py characterize_baseline --diff /tmp/baseline_ANTES_PROD.json --summary
#   → TEM de mostrar só `interface` e `subtype`. Se `dest_label`/`profitable`/
#     `is_dead`/`price_key` aparecerem, PARE e reverta pelo JSON em /tmp (ele
#     ainda existe nesta sessão).
python MEDIR_bus_width.py            # KnownPart: 0 largura em interface · ChipFamily: 0 LARGURA_PURA
python VERIFICAR_largura.py --revert /tmp/nc_revert_PROD_$(date +%Y%m%d).json
#     A PROVA DE FIM DE FASE (o dono pediu em 20/09): tem de dizer
#     "ZERO invencao", a fila comercial tem de cair para ~111, e nos exemplos
#     a coluna FONTE tem de ser `banco` — nunca `gramatica`.
python manage.py guard_catalog

# ── 6. só agora o 2º push (F5, a constraint) → build migra a 0025 ───────────
#     (o pré-voo é o MEDIR acima: constraint com violador EXPLODE o build)
python manage.py guard_catalog
python manage.py characterize_baseline --out /tmp/baseline_DEPOIS_PROD.json
```

### Armadilhas do shell do Render

- **`env -u DATABASE_URL` não existe aqui.** Lá isso apontaria para lugar nenhum.
  Os comandos do §6 com esse prefixo são os de LOCAL; no Render é `python manage.py …` puro.
- **Comando por empresa roda UMA empresa por vez.** `resnapshot_lote` e
  `refresh_lote` chamam `scope_command_to_company`, que é **fail-closed**: com 2+
  empresas ativas ele EXPLODE pedindo `--company <slug>` em vez de escolher sozinho
  (verificado no local em 2026-09-20). Não existe `--all-companies` — o `--all` ali
  é "todos os LOTES daquela empresa". Liste os slugs e rode um por um:

  ```bash
  python manage.py shell -c "from tenancy.models import Company; [print(c.pk, c.slug, c.name) for c in Company.objects.filter(active=True).order_by('pk')]"
  python manage.py resnapshot_lote --company eminer   --all           # dry-run
  python manage.py resnapshot_lote --company erecyclo --all           # dry-run
  ```
- **RLS sem GUC devolve 0 linhas em silêncio.** Esse `scope_command_to_company` é
  justamente quem seta o GUC `app.company_id` na conexão do processo. Se um comando
  de lote imprimir "Escopo de empresa: …" e mesmo assim 0 linhas onde o local
  mostrou muitas, **não é "nada a fazer"** — investigue. Catálogo
  (`KnownPart`/`ChipFamily`) é global e não tem esse risco.
- **O shell cai.** Sessão longa desconecta. Os comandos com `--commit` rodam em
  `transaction.atomic()`, então uma queda no meio faz rollback — o banco não fica
  pela metade. Mas o JSON em `/tmp` some junto: reconecte e refaça o dry-run antes
  de repetir o `--commit` (é idempotente: se já aplicou, dá "a migrar: 0").
- **Não confie na memória entre sessões.** `/tmp` zera. Baseline ANTES e `--diff`
  na MESMA sessão, sempre.
- **`resnapshot_lote` vai ser pedido três vezes** (depois do `resolve_conflicts`,
  do backfill e da submissão Samsung). **Ignore as três** — lote é Parte 2 (§6.0).
- **O site fica no ar o tempo todo.** Nenhum comando aqui derruba nada — mas o
  `catalog_version` sobe a cada escrita de catálogo e o cache do engine recarrega
  sozinho (passo 1B). Não reinicie o serviço "para pegar a mudança".

---

## 7. Riscos e armadilhas específicas desta tarefa

1. **Banco à frente do código.** As duas migrations criam colunas/constraint `NOT NULL`.
   `migrate` local apontado a prod com o código ainda não deployado = INSERT recusado
   em silêncio (incidente 2026-08-18). Só pelo build.
2. **Regex frouxo no censo/backfill.** O dossiê usaria `^x(4|8|16|32|64)$` e deixaria
   ~1.000 Micron para trás. O `split_bus_width` cobre `xN @ …` e `@ …`; **e o censo
   lista todo OUTRO**, para a forma que ninguém imaginou aparecer ANTES do commit (foi o
   dry-run contra o banco real que pegou o pior erro da migração de geração, 2026-08-28).
3. **Sobra sem destino.** `x16 (2 dies)` ou qualquer resto que não seja velocidade →
   NÃO migra. Migrar "quase tudo" e apagar o resto é o erro que o CLAUDE.md §7 chama de
   "dado apagado em silêncio".
4. **Família vence o registro hoje; amanhã o registro `confirmed` vence.** Para as
   divergências known×família listadas na F0, a tela vai mudar de valor (ex.: família
   ESMT `x16`, registro confirmado `x8` → passa a mostrar `x8`). É correto (dado do
   registro é mais específico) — mas o dono tem que ver a lista antes.
5. **`bus_width` NÃO vira spec** (`_HAS_SPECS`/`_USABLE`): um known_part só com largura
   continua identity-only e continua invisível ao engine. Não mexa no gate `_USABLE`
   (regra de ouro #2 — estreitar ou alargar esconde/expõe registros em massa).
6. **`catalog_version` sobe a cada `save()`** do backfill: todas as entradas de lote
   ficam "defasadas" na régua do on-read (recalculadas em memória, sem gravar). É o
   comportamento normal de qualquer correção de catálogo; não rode `resnapshot_lote`
   por causa disso.
7. **`resnapshot_lote` reescreve `interface`** dos lotes antigos se rodado (`_SNAP_KEYS`).
   Fora do escopo; se um dia rodar por outro motivo, o `x16` das linhas antigas vai para
   `bus_width` — aceitável, mas é o dono quem decide quando.
8. **Submissão em voo da Samsung.** Ver §2.6 — os dois caminhos fecham; o backfill é
   re-rodável.
9. **`--fill-empty` dos arquivos antigos.** 113 submissões com `interface: xN` passam a
   ser rejeitadas no dry-run (D3). Aviso aos chats de marca (Micron principalmente:
   `d9*_family_*.yaml`): trocar a chave; o valor é o mesmo. Se um chat precisar re-rodar
   um arquivo antigo para outro campo, a edição é `sed 's/^\(\s*\)interface:\(\s*\)\(["'"'"']\?x\(4\|8\|16\|32\|64\)\)/\1bus_width:\2\3/'` — mas só o dono/chat da marca executa, no arquivo da marca dele.
10. **Constraint em SQLite × Postgres.** `__in` é portável; regex não. A suíte roda em
    SQLite (`core/settings_test.py`) — se a constraint só valer em Postgres, o teste de
    banco mente.
11. **pghistory.** A migration 0024 recria gatilhos e adiciona a coluna ao event table.
    Se o `makemigrations` gerar algo estranho (ex.: `RemoveTrigger` sem `AddTrigger`),
    pare e compare com a `0020`.
12. **i18n.** String nova sem tradução nos 3 `.po` deixa `check_translations` vermelho
    para todo chat (MULTILANGUAGE.md §7). Mesma entrega.
13. **Vocabulário fora do modelo.** Não escreva `("x4","x8",…)` em lugar nenhum além de
    `chips/conventions.py::BUS_WIDTH_VOCAB` (lição das 4 quebras da origem do lote,
    CLAUDE.md §7). Constraint, portão, censo, coletor: todos importam a tupla.
14. **Não "limpe" o `interface` inteiro.** Protocolo (`eMMC 5.1`, `UFS 3.1`,
    `Async/ONFI`, `Parallel NAND (8-bit)`, `NAND (x8/x16)`) é dado legítimo, o engine
    depende dele (`:615`, `:872-886`). O move é cirúrgico: só o que `split_bus_width`
    reconhece.
15. **Zero alto no censo.** `MEDIR_bus_width.py` aborta se `KnownPart.objects.count()==0`
    ou se a marca com mais registros tiver 0 — e para lotes (RLS) abre `platform_scope()`.
16. **Sandbox sem Django.** Você não roda nada disso; escreve, testa mentalmente, entrega.
    A suíte roda na máquina do dono — peça a saída colada antes de declarar verde.

---

## 8. Reversão por fase (resumo)

| fase | como volta | perde algo? |
|---|---|---|
| F1 | `migrate chips 0023` / `migrate estoque 0025` (local); em prod, commit anterior + build | não (colunas vazias) |
| F2/F4 código+yaml | `git revert` + `load_brands --commit` das 3 marcas | não |
| F3 backfill | `normalize_convention --revert <json do mesmo banco>` | não (JSON tem `interface`, `bus_width`, `notes` antigos) |
| F5 constraint | `migrate chips 0024` | não |
| F6 docs | `git revert` | não |

---

## 9. Definição de pronto (checklist do executor)

- [ ] F0: censo (KnownPart + ChipFamily + divergências + OUTRO listado) e 2 baselines ANTES, vistos pelo dono.
- [ ] F1: `bus_width` + constraints de vocabulário em 5 modelos; migrations 0024/0026 geradas (não editadas); espelho `BUS_WIDTH_VOCAB` testado.
- [ ] F2: `split_bus_width`/`interface_problem`/`bus_width_problem` em `chips/knowledge/convention.py`; `is_bus_width`/`BUS_WIDTH_VOCAB` em `chips/conventions.py`; portão Pydantic rejeita `interface: xN` com a mensagem; `clean()` idem (só valor mudado); engine copia `bus_width` (6 pontos: `_result_from_family`, `_result_from_known`, 1481, 1544, 1591, 1644, 1688); `_clean_interface` tira largura; `_snapshot` grava `bus_width`; card + decode_card + debug com "Largura"; 3 `.po`; admin; 24 canais ensinados (checklist do §2.3 marcado um a um no PR); 8 classes de teste com mutação registrada; baseline IDÊNTICO.
- [ ] F3: `normalize_convention` = 3ª exceção, `SafeWriteCommand`, `--out`, relatório de NÃO MIGRADOS completo, idempotente, ida-e-volta testada; rodado local (dump) e prod; três colunas intactas; `MEDIR` = 0 em KnownPart.
- [ ] F4: 25 linhas de yaml; `load_brands` dry-run ×3; commit local e prod; testes 2555/228/201 re-especificados com data; `MEDIR` = 0 em ChipFamily (menos 2 OUTRO).
- [ ] F5: pré-voo zero; constraint `interface_nao_e_largura` em KnownPart e ChipFamily; migration 0025; teste de banco.
- [ ] F6: COLETAR/HANDOFF/PROMPT/check_k4b em `bus_width` (+ canal certo: submit/resolve, não yaml); coletor Samsung = 93; CLAUDE.md §5/§6/§7/§9 + linha 1201; AUTORIA.md; memória do projeto.
- [ ] F7: baseline DEPOIS gravado; `--diff` ANTES→DEPOIS com três colunas intactas; `guard_catalog`; suíte + `check_translations` + `makemigrations --check` verdes; lista de testes de frontend entregue e rodada pelo dono.
- [ ] **[Rev.1] Emendas E1–E7 na Parte 1:** `decode_width_*` em `ChipFamily`/`FamilySpec`/`_FAMILY_FIELDS` + bloco genérico no engine + portão (pos sem map rejeita) — sem nenhuma família declarada ainda; `bus_width_source` no resultado com a precedência banco > gramática > família > distributor; `bless_base` e a aprovação de `PendingEntry` **nunca** escrevem `bus_width` (testes); os 3 modelos de lote com `bus_width` + `width_class` + `bus_width_source`; `characterize` captura `bus_width_source`; HANDOFF com a Etapa 9.
- [ ] **Parte 2 (§10):** só depois de tudo acima — checklist próprio em §10.4 P0–P7 e §10.5.

---

# PARTE 2 — a largura no PREÇO, na CAIXA, na RENTABILIDADE e na VENDA `[Rev.1]`

> **Só começa quando a Parte 1 inteira (F0–F7) estiver fechada em produção** — inclusive
> a gramática de largura (E1) de pelo menos as famílias DDR3 que o coletor já provou
> (K4B) e as que ele provar até lá. Sem gramática, quase todo DDR3 cai na fila de foto
> (§10.4 P3) no primeiro dia, e uma fila que nasce cheia é uma fila que ninguém revisa.

## 10.1 Decisões travadas pelo dono (2026-09-15) — e o que o comprador ainda não disse

| # | Decisão | Consequência de desenho |
|---|---|---|
| D9 | **Classe, não largura exata**, no preço e na caixa: `narrow` (x4/x8) × `wide` (x16). O catálogo (`bus_width`) continua exato. | Um eixo `width_class` no preço/caixa/linha da venda; `width_class_of(bus_width)` é a fonte única da tradução. Rótulo humano: **`x4/x8`** e **`x16`** (tokens universais, sem tradução); "78/96 bolas" aparece só como dica na bancada e no admin. |
| D10 | **Código de caixa NOVO só para o estreito**; o código atual continua sendo o x16 — gaveta etiquetada não muda de nome. | Na chave da categoria, o eixo vale **`'narrow'` ou `''`**: `''` = o que sempre foi (x16 ou não separado). Zero migração de dado nas categorias existentes; só nasce E-## novo para `DDR3+<n>G x4/x8`. |
| D11 | **Largura desconhecida na bancada → foto frente/verso → fila de revisão no Django admin.** Enquanto não revisado, o chip é **INDETERMINADO**. | Fluxo novo no estoque: `PendingEntry` ganha fotos (bytes no Postgres, padrão `ProvaFoto`), o revisor conta as bolas no verso e grava a classe; a observação vira registro **global por PN** (`WidthReview`) para a bancada não perguntar duas vezes o mesmo PN. **Nunca vai para o catálogo** (I4). |
| D12 | **DDR3 estreito continua RENTÁVEL ao preço baixo**; limiar novo **editável no admin**: `ProfitabilityConfig.ddr3_narrow_min_gbit` (default **2.0**). Abaixo → NÃO RENTÁVEL (cobre a recusa do 1Gb). | Regra nova no bloco DDR do `assess_profitability`; DDR4/DDR5 estreito **sem regra** (preço cheio). Largura desconhecida onde a classe decide o veredito → INDETERMINADO (D11). |

| D16 | **A largura separa em DDR3, DDR4 e DDR5** — não só onde o preço difere hoje (dono, 2026-09-19: *"mesmo que o preço seja o mesmo"*). | `WIDTH_SPLIT_GENS = ("DDR3","DDR4","DDR5")`. Caixa, linha da venda e grid do comprador ganham o eixo nas três; o PREÇO pode ser igual nas duas larguras — é o que torna a virada futura uma linha no admin em vez de uma migração de categoria. Custo real e IRREVERSÍVEL: código de caixa novo para DDR4 e DDR5 estreitos ⇒ **mais caixas físicas na bancada** (hoje: 181 PNs DDR4 + 146 DDR5 estreitos). Custo de fila: pequeno — 524 dos 597 PNs de DDR4/DDR5 são Samsung e Micron, que ficam identificadas. |
| D17 | **Largura desconhecida para a fila de foto em TODAS as gerações que separam**, não só onde o dinheiro depende. | O gatilho `precisa_largura` não olha preço: se a caixa separa, a bancada precisa saber. |
| D18 | **TODO chip terá foto** (dono, 2026-09-19) — feature à parte, a desenhar com calma. | ⚠ Consequência de ARQUITETURA para a P3: o mecanismo de foto da revisão de largura **não pode nascer descartável**. Construir um `PendingFoto` agora e um modelo de foto geral depois = dois sistemas de foto. A P3 passa a ser a **primeira fatia** da feature geral, não um anexo dela. E a escala muda a decisão de armazenamento: o precedente `ProvaFoto` (bytes no Postgres) serve para punhados de comprovantes; ~4.000 entradas de estoque em prod × 2 fotos × ~300KB ≈ 2,4 GB e crescendo — num Postgres Hobby do Render isso é decisão de custo, não detalhe. **Escolher onde a foto mora é o primeiro passo daquela feature, antes de qualquer tela.** |

**[ABERTO] — do comprador, não do dono. São PORTAS da P5 (semear o grid), não do
código:** (1) preço do **4Gb x4** — ele nunca disse `4g04`; por D9 cai na mesma linha
`narrow 4Gb` que o `4g08`, mas isso é dedução, não confirmação; (2) **8Gb estreito** —
nunca discutido: **sem linha** até ele dizer (fica "sem preço" na valoração, visível);
(3) `"DDR4. Only 4G8. 5rmb"` — não encaixa em nada: **não usar**; (4) marca em 78-ball —
"same price" foi sobre ESTE lote: semear as linhas estreitas na **lista genérica** do
comprador (sem marca) e deixar as listas por marca herdarem (a cadeia de resolução é
marca → herança → genérica → herança, `pricing/engine.py:342-364`) — se um dia uma marca
pagar diferente, entra uma linha na lista da marca; (5) divergência de contagem (407
peças) — não é deste plano.

**Verificar antes de desenhar a regra (não perguntar — LER):** a régua viva de
`ProfitabilityConfig` em prod. O default do código é `ddr3_min_gbit = 2.0`
(`chips/models.py:538-542`, "DDR3 < 2 Gb → NÃO RENTÁVEL"; `ddr_min_gen` :533, `ddr4plus_min_gbit` :543), mas a SO-0007 embarcou 1.107
peças de DDR3 **1Gb x16** como RENTÁVEL a ¥2 — a régua viva deve estar em **1 Gb**. Se
estiver em 2, o "caso que mais dói" do Apêndice D §5 (1Gb 78-ball embarcado) aconteceu
por outro caminho (`bless_base`/lote legado?) e a P0 tem de explicar antes de a P2 mexer.

## 10.2 Diagnóstico — onde a largura precisa entrar (verificado, HEAD `e9f90fb`)

| eixo | hoje | o que muda |
|---|---|---|
| **chave de preço** | `derive_price_key` (`pricing/engine.py:199-256`) = `(kind, gen, tier, unidade)`, **função pura do classify**. A `origin` do eMMC NÃO está na tupla: é eixo da LINHA, resolvido de fora (`_row_origin` :487-494; `price()` :497-520; `BuyerPricingContext._rows` :545-551 e `.price()` :562-580; `price_from_key` :583-611; `quotes_for_admin` :613-635; valoração de lote :731-756 passa `lot.origin`). | A largura entra **como a origem**: um eixo da linha (`width_class`), resolvido de fora da tupla pura. `derive_price_key` **não muda**. Precedente: constraint `price_origin_emmc_only` (`pricing/models.py:500-504`) → `price_width_gen_split`. |
| **grid** | `Price` (`:414`): `origin` (`:443`), `UniqueConstraint(price_list, kind, gen, tier_value, tier_unit, origin)` (`:492-495`), `price_origin_vocab` (`:497-499`), `clean()` espelha (`:577-583`). Chave do dict do contexto = 6-tupla (`:545-551`). | `Price.width_class` + vocab + `ddr3_only` + a unique vira 7 campos + `clean()` espelho; dict do contexto vira 7-tupla; `_row_width(kind, gen, width_class)` ao lado de `_row_origin`. |
| **caixa (F12)** | `CategoryCode` (`pricing/models.py:1093`) chaveado por `(kind, gen, tier_value, tier_unit)`; `label_for_key` (`:1156-1200`) cunha E-## eterno; chamadas: `estoque/views.py:207` (cunhagem, portão `entra_no_estoque` :179-210), `vendas/services.py:301, :748, :1486, :2131, :2249, :2406`, `auditar_planilha_comprador.py:127`. | `CategoryCode.width_class` (`''`/`'narrow'`) na unique e em `label_for_key(..., width_class='')`; os 8 chamadores passam o eixo. Código antigo = `''` = intacto (D10). Rótulo: `DDR3+2G x4/x8`. |
| **materialização no lote (F11.1)** | `InventoryEntry.price_kind/gen/tier_value/tier_unit/key_reason` gravados no lançamento (`estoque/views.py:162-177 _price_key_fields`); `resnapshot_lote` renova. | `InventoryEntry.price_width` (`''`/`'narrow'`) materializado junto — derivado de `width_class` do lote (E4) pela régua `WIDTH_SPLIT_GENS`; `_SNAP_KEYS`/`_FIELDS` do `resnapshot` idem. |
| **linha da venda** | `SalesOrderLine` (`vendas/models.py:344-403`): `UniqueConstraint(order, brand, kind, gen, tier_value, tier_unit)` (`:390-392`); `create_draft_for_lot` agrupa por `(brand, price_kind, price_gen, price_tier_value, price_tier_unit)` (`vendas/services.py:59-67`); `price_from_key` (`:103-108`); chaves reconstruídas em `:403, :1480, :2233-2250`. | `SalesOrderLine.width_class` na unique e no agrupamento; `price_from_key(..., width_class=...)`; rótulo da linha (`label`, `:399-405`) mostra `x4/x8`. Linhas antigas ficam `''` — a SO-0007 (média ponderada) é história e **não** se reescreve. |
| **rentabilidade** | bloco DDR (`chips/engine.py:1315-1332`): geração < `ddr_min_gen` → NÃO RENTÁVEL; densidade < `ddr3_min_gbit`/`ddr4plus_min_gbit` → NÃO RENTÁVEL; senão RENTÁVEL. Não olha largura. `is_dead_by_generation` (`:1354`) = "continua NÃO RENTÁVEL sem os números?". | Regra nova **depois** dos limiares atuais: `gen < 4` e `width_class == 'narrow'` e `gbit < cfg.ddr3_narrow_min_gbit` → NÃO RENTÁVEL; `gen < 4` e classe **desconhecida** e `gbit < cfg.ddr3_narrow_min_gbit` → **INDETERMINADO** (a classe decide; D11). Depende de densidade ⇒ `is_dead_by_generation` **não** vira True (é REPROVADO no funil, não descarte-por-geração — o chip volta para a bancada com o motivo). |
| **gateway / bancada** | `_compute_gateway(result, has_cap, lot)` (`estoque/views.py:620-…`): identificação → fonte → rentabilidade; INDETERMINADO = aprovado no funil mas `can_add=False`. `add_chip` (`:1248`). | O gateway **funde a largura declarada** (WidthReview por PN, `source='revisao'`) no `result` antes do `assess_profitability` — como faz com `lot.origin`. Quando o veredito ou a caixa dependem da classe e ela é desconhecida: card pede **2 fotos** e cria `PendingEntry` (INDETERMINADO, H-00). |
| **fotos** | Precedente certo: `vendas.ProvaFoto` (`vendas/models.py:1309-1345`) — bytes em `BinaryField` (1600px + thumb, EXIF fora), `vendas/fotos.py:84 preparar(raw, filename)`. Precedente **errado**: `ChipSubmission.photo` (`chips/models.py:446`) é `ImageField` em disco — **efêmero no Render** (deploy apaga). | Fotos da revisão seguem `ProvaFoto`: `preparar()` sai de `vendas/fotos.py` para `core/fotos.py` (fonte única); modelo novo `PendingFoto` (bytes, presa à `PendingEntry`) — nunca `ImageField`. |
| **admin** | `PendingEntry` aprovado → `InventoryEntry` (`estoque/admin.py:37/109`) **e** → `KnownPart` (`:15-40`, o 25º canal). | Ação "Definir largura (78 = x4/x8 · 96 = x16)" no admin de `PendingEntry`, que grava `WidthReview` + `width_class`/`bus_width_source='revisao'` e só então libera a aprovação; a promoção a `KnownPart` **não** leva largura (E3). |
| **exports / PDFs / planilha do comprador** | `compra_em_planilha` (export) e `auditar_planilha_comprador` (leitura de volta, casa por CABEÇALHO em 4 idiomas, teste de ida-e-volta com ZERO diferença — CLAUDE.md §5); PDFs `pricing/pdf.py`, `vendas/pdf.py`; packing list. | A largura entra **dentro do rótulo da categoria/caixa** (`DDR3+2G x4/x8`, E-##), **não como coluna nova** — as planilhas mantêm as colunas, o parser continua casando por cabeçalho, e o ida-e-volta tem de seguir zero. |
| **origem × tipo (torneira)** | `estoque/politica_origem.py` — RAM nasce 100% aberta; "fase 2 depende da largura, que vive no `interface`" (CLAUDE.md:1201). | Passa a ler `width_class`; **fora deste plano** (é régua de origem, decisão à parte). |

**Baseline:** diferente da Parte 1, aqui as TRÊS COLUNAS **mudam de propósito** para um
conjunto NOMINAL de PNs. A régua vira: *o diff é exatamente o conjunto previsto na P0 —
nem um PN a mais, nem um a menos*. `characterize_baseline` precisa capturar
`width_class`, `bus_width_source` e, no `price_key`, o eixo de largura
(`kind|gen|tier|unidade|width`).

## 10.3 O contrato do eixo `width_class` (fonte única `pricing/convention.py`)

```python
WIDTH_NARROW, WIDTH_WIDE = "narrow", "wide"
WIDTH_CLASSES = ("", WIDTH_NARROW, WIDTH_WIDE)          # lote: '' = desconhecida
WIDTH_AXIS    = ("", WIDTH_NARROW)                     # preço/caixa/linha: '' = x16 ou não separado (D10)
WIDTH_SPLIT_GENS = ("DDR3", "DDR4", "DDR5")            # [D16] gerações em que a largura SEPARA (pós fold_gen: DDR3L→DDR3)

def width_class_of(bus_width: str) -> str:            # x4/x8 → narrow · x16 → wide · resto → ''
def width_axis(kind: str, gen: str, width_class: str) -> str:
    """'narrow' só quando kind == 'ddr', fold_gen(gen) ∈ WIDTH_SPLIT_GENS e a classe é narrow; senão ''.

    ⚠ [D16, dono 2026-09-19] A tupla NÃO é "onde o preço difere" — é "onde a
    largura separa". DDR4 e DDR5 entram mesmo com o preço igual nas duas
    larguras: *"deve ter lá a diferenciação de largura de todo jeito, mesmo que
    o preço seja o mesmo"*. Separar só onde dói hoje é construir a metade que
    depois se refaz — e caixa refeita é gaveta reetiquetada do outro lado do
    mundo."""
```

Regras: (a) `WIDTH_SPLIT_GENS` é **tupla fechada em código, com teste**, não campo de
admin — mudar o conjunto re-chaveia categorias (código eterno) e tem de ser deploy
deliberado com baseline, como esta Parte 2; (b) `x32`/`x64` em `kind='ddr'` não existem
no mercado deste catálogo (GDDR é sucata por tipo, LPDDR tem `kind` próprio) → `''`;
(c) a classe do **lote** distingue desconhecida (`''`) de `wide`; o **eixo** não precisa
(D10) — por isso são dois vocabulários; (d) `is_bus_width`/`BUS_WIDTH_VOCAB` continuam
em `chips/conventions.py` (Parte 1); `width_*` mora no pricing porque é conceito de
MERCADO, não de catálogo.

**Constraints (banco):** `price_width_vocab` (`width_class ∈ WIDTH_AXIS`),
`price_width_gen_split` (`width_class='narrow'` ⇒ `kind='ddr'` **e** `gen ∈ WIDTH_SPLIT_GENS`;
senão `''`) — o nome não cita DDR3 de propósito: a tupla é que manda (D16) — espelho no `Price.clean()` com mensagem amigável, como `origin`;
`categorycode_width_vocab`; `soline_width_vocab`; `inventoryentry_width_class_vocab`
(`WIDTH_CLASSES`) e `price_width_vocab` no `InventoryEntry.price_width`.

**Ordem de precedência da largura na bancada (fonte única no gateway):**
`result.bus_width` do engine (banco > gramática > família) → `WidthReview` do PN
(`revisao`, classe) → desconhecida. A classe declarada por foto **nunca sobrepõe** uma
largura exata do engine; se divergirem (engine `x16`, foto diz 78 bolas), o gateway
**não arbitra**: manda para a fila com o motivo "divergência largura engine × foto" — é
sinal de erro no catálogo ou na gramática, e alguém precisa olhar.

## 10.4 Fases da Parte 2

### P0 — Medir, ler a régua viva, fechar as portas do comprador

- Parte 1 fechada (F7) em prod; `guard_catalog` verde.
- **Ler** `ProfitabilityConfig` em prod (`ddr_min_gen`, `ddr3_min_gbit`,
  `ddr4plus_min_gbit`) — read-only, transação revertida — e explicar a diferença com o
  default do código (§10.1).
- Censo (extensão do `MEDIR_bus_width.py`, seção nova): para `kind='ddr'` e
  `gen ∈ WIDTH_SPLIT_GENS`, quantos PNs do catálogo (`KnownPart` aprovados) e quantas
  entradas de lotes **abertos** têm largura por `banco` / `gramatica` / `familia` / nada —
  por marca e por densidade. É o tamanho (a) do conjunto que muda de veredito/caixa e (b)
  da fila de foto no dia 1. Se (b) for a maioria do DDR3 em lote aberto, **a P3 (foto)
  entra antes da P2 (regra)** ou a gramática das famílias grandes entra primeiro — decisão
  do dono com o número na mão.
- **Lista nominal prevista** (arquivo `baseline_bus_width_PARTE2_previsto.json`): PN →
  {veredito antes, veredito depois, caixa antes, caixa depois, price_key antes/depois}.
  É contra ela que o `--diff` final é conferido.
- Baseline ANTES da Parte 2 (`characterize_baseline --out baseline_bus_width_P2_ANTES_PROD.json`).
- As 4 portas do comprador (§10.1 [ABERTO]) respondidas ou explicitamente adiadas
  (8Gb estreito = sem linha).

### P1 — Vocabulário, chave, grid e caixa (pricing) — migrations ADITIVAS

`pricing/convention.py` (§10.3); `Price.width_class` + constraints + unique de 7 campos
(`makemigrations` gera `RemoveConstraint`/`AddConstraint`/`AddField` — aditivo, default
`''`; **DDL só, sem RunPython** — as tabelas do pricing têm RLS: um RunPython precisaria
do `_liberar_rls` da `pricing/0019`; aqui não há backfill porque `''` já é o valor certo
de todas as linhas existentes); `_row_width(kind, gen, width_class)` ao lado de
`_row_origin` (:487); `price(result, buyer, origin='', width_class='')`,
`BuyerPricingContext.price(...)`/`price_from_key(..., width_class='')`, dict `_rows`
7-tupla, `quotes_for_admin(..., width_class='')`; `CategoryCode.width_class` + unique +
`label_for_key(kind, gen, tier_value, tier_unit, width_class='', create=…)` + `label`
com sufixo ` x4/x8` quando `narrow` (e a convenção `LETRA-##` inalterada: o número nasce
na primeira aprovação, `pricing/convention.py`). Admin do `Price` e do `CategoryCode`
mostram a coluna. Travas: `PriceWidthAxisTests` (vocab/`ddr3_only`/unique/`clean()`
espelho; mutação: aceitar `narrow` em DDR4 → morde), `CategoryCodeWidthTests` (código
antigo de DDR3 continua o mesmo número com `''`; `narrow` cunha número NOVO da letra;
`create=False` nunca cunha), `WidthSplitGensTests` (a tupla é fechada e `DDR3L` dobra em
`DDR3`).

### P2 — Rentabilidade + chave materializada + gateway (engine e estoque)

- `ProfitabilityConfig.ddr3_narrow_min_gbit = FloatField(default=2.0, verbose_name="DDR3 —
  Densidade mínima do ESTREITO (x4/x8), em Gb por die", help_text=…)` (migration chips,
  aditiva).
- `assess_profitability` bloco DDR (`:1315-1332`): a regra entra **depois** de a densidade
  geral já ter reprovado o que reprova (`gbit < min_gbit → NÃO RENTÁVEL` continua vindo
  antes — chip que já é sucata pela régua geral não pede foto) e **antes** do
  `return "RENTÁVEL"` final:
  ```python
  if ddr_gen < 4 and gbit is not None:                       # gbit já passou na régua geral
      wc = result.get("width_class") or width_class_of(result.get("bus_width") or "")
      if wc == WIDTH_NARROW and gbit < cfg.ddr3_narrow_min_gbit - 0.01:
          return "NÃO RENTÁVEL"          # 78 bolas de 1Gb: o comprador recusa
      if not wc and gbit < cfg.ddr3_narrow_min_gbit - 0.01:
          return "INDETERMINADO"         # a classe decide e ninguém sabe → foto (P3)
  ```
  RENTABILIDADE.md ganha a regra e o checklist ("largura muda veredito? só DDR3 estreito").
  `RentabilidadeHandshakeTests` continua verde (nenhum tipo novo). Travas:
  `RentabilidadeLarguraTests` — DDR3 1Gb narrow → NÃO RENTÁVEL; 1Gb wide → o que a régua
  viva disser; 1Gb sem classe → INDETERMINADO; 2Gb narrow → RENTÁVEL (default 2.0);
  subir o limiar para 4 no config → 2Gb narrow vira NÃO RENTÁVEL sem deploy; DDR4 narrow
  → intacto; `is_dead_by_generation` de DDR3 1Gb narrow = **False** (é capacidade, não
  geração); mutações: tirar a checagem de classe, inverter narrow/wide.
- `_price_key_fields` (`estoque/views.py:162-177`) grava `price_width =
  width_axis(kind, gen, entry.width_class)`; `_masked_category` (`:179-210`) passa o eixo
  ao `label_for_key`; `resnapshot_lote` `_FIELDS`/`_SNAP_KEYS` ganham `price_width`.
- `_compute_gateway` (`:620`): antes da etapa 3 funde `WidthReview` do PN (P3) em
  `result['width_class']`/`result['bus_width_source']='revisao'`; devolve
  `precisa_largura=True` quando **kind ddr, gen ∈ `WIDTH_SPLIT_GENS`, classe `''` e o
  chip passou na régua geral** — em QUALQUER densidade, não só abaixo do limiar do
  estreito: a caixa separa estreito de largo em 2Gb e 4Gb também (D10), e um 2Gb sem
  classe na caixa larga é a SO-0007 de novo. Com `precisa_largura`: veredito exibido
  INDETERMINADO com o motivo "largura necessária", `can_add=False`, e o card abre o
  bloco de fotos (P3). Divergência engine×foto → `fila` com motivo.
- `characterize_baseline` captura `width_class`, `bus_width_source`, `price_width`
  (o `price_key` passa a `kind|gen|tier|unidade|width`; **regravar o baseline** antes de
  medir a P2 — coluna nova é ignorada no diff até isso, `:236-246`).

### P3 — A bancada: foto frente/verso → fila → admin (D11)

- Modelos (estoque, migration aditiva, **declaração de tenancy obrigatória** —
  `TenancyDeclarationTests`, `estoque/tests.py:2005-2080`):
  - `WidthReview` — **GLOBAL** (plataforma, sem `company`, como `PoliticaOrigemTipo`
    :484 e `DefeitoTipo`): `part_number_norm` (unique), `width_class ∈ ('narrow','wide')`,
    `balls` (78/96, informativo), `reviewed_by`, `reviewed_at`, `notes`. Motivo de ser
    global: contagem de bolas é fato físico do PN, vale para qualquer empresa e qualquer
    lote — perguntar de novo o mesmo PN é custo sem informação.
  - `PendingFoto` — escopada pela `PendingEntry` (`CompanyBoundByLot`, RLS como a mãe):
    `pending` FK, `lado ∈ ('frente','verso')`, `data`/`thumb` BinaryField, `mime`, `size`,
    `width`, `height`, `uploaded_at` — cópia do desenho de `ProvaFoto`, via
    `core/fotos.py::preparar` (movido de `vendas/fotos.py`, que passa a importar de lá).
    **Nunca `ImageField`** (Render apaga o disco no deploy — `ChipSubmission.photo` é o
    exemplo do que não fazer).
- Bancada (`confirm_card.html` + `add_chip` `:1248`): quando `gateway.precisa_largura`,
  o card mostra "**Largura necessária** — fotografe frente e verso" com dois
  `<input type="file" accept="image/*" capture="environment">` (frente/verso) e o botão
  "Enviar para revisão" (o de "Lançar" fica desabilitado, como já fica no
  INDETERMINADO). O POST cria `PendingEntry` (INDETERMINADO, H-00) + 2 `PendingFoto`
  (reduzidas no servidor; limite de tamanho no `preparar`). Sem foto não envia. i18n nos
  4 idiomas na mesma entrega (`check_translations`). Card mascarado: mesma linha, sem tipo
  (a máscara é sobre o que o chip É — CLAUDE.md §7, 2026-09-09).
- Admin (`estoque/admin.py`, `PendingEntryAdmin`): as fotos aparecem inline (thumb
  clicável → 1600px); ação **"Definir largura: 78 bolas (x4/x8)"** e **"96 bolas
  (x16)"** → grava `WidthReview` (upsert por `part_number_norm`), `pend.width_class`,
  `pend.bus_width_source='revisao'`, e recalcula o snapshot da pendência (veredito e
  caixa passam a existir). A aprovação (`:37/:109`) só é oferecida quando
  `precisa_largura` está resolvido; a promoção a `KnownPart` (`:15-40`) **não** leva
  largura (E3). Dica visual na ação: "DDR3: 78 bolas = x4/x8, 96 bolas = x16" (verificado em datasheet
  Micron — 2Gb DDR3 e 8Gb DDR4 usam o mesmo par 78/96; DDR5 provável mas não verificado,
  e hoje irrelevante: a ação só é oferecida para `WIDTH_SPLIT_GENS`).
- A partir daí, o mesmo PN em qualquer lote resolve pela `WidthReview` (gateway) —
  `bus_width_source='revisao'` na entrada; o card mostra "Largura: x4/x8 (revisão, 78
  bolas)".
- Travas: `FilaLarguraTests` (DDR3 sem classe, em qualquer densidade que passe na régua
  geral → `precisa_largura`, `can_add=False`; DDR3 já reprovado pela régua geral → NÃO pede
  foto; DDR4 sem classe → não pede; POST sem as 2 fotos → 400; com fotos → Pending +
  2 fotos reduzidas, EXIF ausente; ação do admin → `WidthReview` + veredito recalculado;
  2º lote com o mesmo PN → resolve sem perguntar; engine `x16` × review `narrow` →
  `fila` com motivo); `TenancyDeclarationTests` verde por mérito (WidthReview declarada
  GLOBAL com justificativa; PendingFoto escopada); teste pela VIEW em 2 idiomas.

### P4 — A venda (vendas): linha, agrupamento, rótulos, exports

`SalesOrderLine.width_class` (vocab `WIDTH_AXIS`) + `UniqueConstraint(order, brand, kind,
gen, tier_value, tier_unit, width_class)` (migration aditiva, DDL só — tabela RLS, sem
RunPython); `create_draft_for_lot` agrupa por `(..., price_width)` (`services.py:59-67`)
e cria a linha com `width_class`; `price_from_key(..., width_class=line.width_class)`
(`:103-108`); todas as reconstruções de chave (`:403, :1480, :2233-2250`) e os 8
`label_for_key` passam o eixo; `SalesOrderLine.label` mostra ` x4/x8`; PDFs e planilhas
mostram o rótulo/caixa já com o sufixo — **colunas inalteradas**; o parser da planilha
que volta (`vendas/planilha_auditoria.py`) continua casando por cabeçalho e o
**ida-e-volta dá ZERO diferença** (é a trava que pegou a herança de marca da 2ª faixa —
CLAUDE.md §5). Acerto (`SettlementLine`) segue a linha. Travas: `SoLineWidthTests`
(lote com DDR3 2Gb narrow + wide → 2 linhas, rótulos distintos, sem média ponderada;
export→import zero diff; PDF do gerente e packing list mostram as duas). Histórico: a
SO-0007 e anteriores ficam como estão (`''`), com uma nota em `PRECIFICACAO.md`: *"linhas
anteriores a <data> podem misturar larguras — a separação começou em <data>"*.

### P5 — Semear o grid (o dono, em prod, sob `platform_scope()`)

Linhas **estreitas** na **lista genérica** de Wu Quan (sem marca; as listas por marca
herdam — §10.1 porta 4): `ddr/DDR3/1Gb/narrow` = **NÃO COMPRA** (`Price.status='no_buy'` — o vocabulário já
existe: `pricing/models.py:126-128` `STATUS_NO_BUY`/`STATUS_CHOICES`, campo `Price.status` :450, `engine.py:56` `NO_BUY`; o veredito da P2
já barra antes, a linha é o cinto e o suspensório);
`ddr/DDR3/2Gb/narrow` = **¥0,50**; `ddr/DDR3/4Gb/narrow` = **¥1,00**; `8Gb/narrow` =
**sem linha** até o comprador responder. Pelo canal que já existe (fila de
`PriceChangeRequest` no admin, ou comando de linha com `with platform_scope():` e
**releitura** do que gravou — CLAUDE.md §7, `enable_price_row`). Linhas `wide`/`''` ficam
exatamente como estão. Dry-run com a lista das linhas antes/depois.

### P6 — Docs, memória, ferramentas

`PRECIFICACAO.md` (seção do eixo de largura, gêmea da origem); `RENTABILIDADE.md` (regra +
checklist); `CLAUDE.md` §6 (tabela de campos → label ganha a coluna de largura para DDR3),
§7 (um bullet: "LARGURA MUDA PREÇO E CAIXA — 2026-09-15", apontando para cá e para o
Apêndice D), :1201 (torneira lê `width_class`); `DESIGN_SYSTEM.md`/`FRONTEND_V2`
se o card ganhar componente novo; memória do projeto.

### P7 — Verificação nominal

`characterize_baseline --diff baseline_bus_width_P2_ANTES_PROD.json --summary` → o
conjunto de PNs com `dest_label`/`profitable`/`price_key` alterados **é igual** à lista
nominal da P0 (script de conferência: diff de conjuntos, zero sobra dos dois lados);
`guard_catalog`; suíte inteira (`chips estoque vendas pricing`) + `check_translations` +
`makemigrations --check`; testes de frontend do dono: um K4B x8 1Gb → REPROVADO com
motivo; um K4B x8 2Gb → aprovado, caixa `DDR3+2G x4/x8` (E-## novo), preço ¥0,50; um
K4B x16 2Gb → caixa de sempre, ¥3; um DDR3 sem largura → pede as 2 fotos → INDETERMINADO
→ admin define 78 → volta aprovado no estreito; 2º lote com o mesmo PN → não pergunta;
um DDR4 x8 → tudo como antes; fechar um lote com os dois → OV com 2 linhas; export→import
da planilha do comprador zero diff.

## 10.5 Ordem, portas e o que NUNCA acontece na Parte 2

| fase | porta |
|---|---|
| P0 | Parte 1 fechada em prod; régua viva lida; censo; lista nominal; baseline ANTES; portas do comprador |
| P1+P2+P3+P4 | **um PR** (o eixo atravessa preço → caixa → lote → venda; deploy pela metade deixa linha de venda sem eixo que a caixa já tem); migrations aditivas; deploy pelo build; `guard_catalog` |
| P5 | grid semeado pelo dono; dry-run com antes/depois |
| P6–P7 | baseline nominal; docs; testes de frontend |

Nunca: RunPython em tabela RLS sem `_liberar_rls`; reescrever linhas antigas de venda
ou categorias existentes (D10); copiar largura de lote/revisão/gramática para
`KnownPart` (I4/E3); foto em disco; `WIDTH_SPLIT_GENS` em campo de admin; usar
`"DDR4 only 4G8 5rmb"` ou `4g04` como fato; dar largura a `derive_price_key` (a tupla pura
fica pura — o eixo é da linha, como a origem).

## 10.6 Riscos específicos da Parte 2

1. **Fila de foto nascendo cheia.** Sem a gramática (E1) das famílias DDR3 grandes, todo
   DDR3 sem largura conhecida — em qualquer densidade que passe na régua geral — vira
   INDETERMINADO (`precisa_largura`) no dia 1. A P0 mede; o dono
   decide a ordem (gramática antes, ou foto antes com equipe avisada).
2. **Régua viva ≠ default do código.** `ddr3_min_gbit` 1.0 em prod × 2.0 no código: os
   testes usam o default, a prod usa o admin. Teste de rentabilidade com os DOIS valores.
3. **Código de caixa é eterno.** Cunhar `narrow` só pelo portão `entra_no_estoque`
   (aprovado + RENTÁVEL) — nunca no render (bug de 2026-08-18). O 1Gb estreito é NÃO
   RENTÁVEL e **não pode** cunhar caixa.
4. **RLS nas tabelas de preço/venda/estoque.** Toda escrita da P5 e toda leitura de
   comando abrem `platform_scope()`/`company_scope()`; "não deu erro" não é prova — reler.
5. **Divergência engine × foto.** Não arbitrar; fila com motivo. É como se descobre
   gramática errada (a K4N do coletor) ou catálogo errado.
6. **A classe declarada não é largura exata.** `WidthReview` guarda classe; o catálogo
   exige exato — por isso ela nunca sobe (I4), mesmo sendo fato físico.
7. **Média ponderada histórica.** Linhas antigas com `''` misturam larguras; não migrar,
   documentar a data de corte.
8. **Micron.** Não decodifica (FBGA); depende do catálogo (`bus_width` vindo do CSV
   oficial — Parte 1 F3) — os ~950 LPDDR5/DDR5/DDR3 Micron com largura no `interface`
   hoje viram `bus_width` no backfill; DDR3 Micron sem catálogo → foto.

---

## 10.7 As DUAS TELAS DO COMPRADOR — estudo de 2026-09-19 `[Rev.2]`

> Pedido do dono em 2026-09-19, feito lendo o código em HEAD `e9f90fb`. O §10.2 diz
> **que** a largura entra no preço e na linha da venda; não diz **como** as duas telas
> que o comprador usa todo dia param de pé com um eixo a mais. Isto responde isso.
> Procedência, como no Apêndice D: **[DONO 2026-09-19]** = decidido · **[PROPOSTA]** =
> do executor, ainda não ratificado. Onde isto e o §10.4 divergirem, vale isto (é mais
> novo e foi escrito com as telas abertas); onde divergir do código, vale o código.

### 10.7.1 O achado que muda o desenho: a COLISÃO SILENCIOSA

Quatro dicionários do sistema são chaveados pela chave de preço **sem** a largura. Pôr
duas linhas (`narrow` e `''`) da mesma geração e densidade faz o segundo sobrescrever o
primeiro — **sem exceção, sem log, sem célula vazia**: a informação simplesmente não
chega à tela. É o mesmo veneno do zero silencioso do RLS (§7 do CLAUDE.md), com outra
causa.

| onde | chave hoje | o que some |
|---|---|---|
| `pricing/views.py:427` `celulas` | `(price_list_id, gen, tier_value)` | a célula de UMA das larguras — o comprador cota uma e não vê a outra |
| `pricing/views.py:426` `trav_linha` | `(kind, gen, tier_value, tier_unit)` | o selo "travando N pedidos" cai na linha errada |
| `vendas/services.py:2232` `precos` (aba PN a PN) | `(marca, kind, gen, tier_value, tier_unit)` | metade dos chips mostra o ¥ da OUTRA largura |
| `estoque/views.py:221` `keyed` / `:228` `k` | idem | o resumo por categoria do lote |

⚠ O `celulas` **já estaria quebrado hoje** com o eMMC, que tem o eixo `origin`. Não está
porque o eMMC **não enfiou o eixo na matriz**: partiu a página em duas seções e filtrou
`origin` em cada uma (`pricing/views.py:441-452`, o bloco `dual`). Ou seja, o precedente
da casa para "um eixo a mais na tela do comprador" já existe, está em produção desde
2026-08-01 e é o que as duas telas abaixo seguem.

**Trava obrigatória, nas duas telas:** um teste que crie DOIS `Price` (ou duas
`SalesOrderLine`) de mesma marca/geração/densidade e larguras diferentes e exija que **as
duas** apareçam. Mutação que tem de morder: devolver a chave curta ao dict — hoje ela
passa em todos os testes que existem, porque nenhum cenário tem duas larguras.

### 10.7.2 Tela 1 — a tabela de preços do comprador (`/partner/precos/ddr/`)

**Como é hoje.** `partner_kind(request, 'ddr')` (`pricing/views.py:348`) monta uma
MATRIZ: linha = geração + densidade, coluna = marca (+ "Outras" = lista genérica). A
página inteira é UM formulário e o `partner_kind_save` (`:762`) posta **por `p<pk>`**,
fazendo diff só das células alteradas.

**O que NÃO serve.** Dobrar as colunas (cada marca vira x16 + x4/x8) leva a matriz de ~8
para ~16 colunas numa tabela que já rola na horizontal (`dtab__wrap--x`) e que vira
cartão no celular (`DESIGN_SYSTEM.md`). E acrescentar as linhas estreitas **dentro** da
mesma matriz é a colisão do §10.7.1.

**D13 [PROPOSTA] — a página do DDR vira `dual`, exatamente como o eMMC.**

- **Seção 1 — "DDR de 96 bolas (x16)"**: a matriz por marca que já existe, `width_class=''`,
  intacta. Zero mudança de dado, zero mudança de código de caixa (D10).
- **Seção 2 — "DDR3 de 78 bolas (x4/x8)"**: tabela **UNIFICADA**, sem coluna de marca,
  sobre a lista **genérica** — 4 linhas. Unificada porque o comprador disse `Same price`
  para todas as marcas no 78-ball (Apêndice D §2) e porque a cadeia de resolução é
  marca → herança → genérica (`pricing/engine.py:342-364`): se um dia UMA marca pagar
  diferente, entra uma linha na lista dela e o desenho não muda.
- Selo do topo: mais um caso do `seal--dual` (`partner_kind.html:61`), com o texto
  "DUAS TABELAS — 96 bolas (por marca) × 78 bolas (preço único)".

**O que isso custa em código:** `ctx['dual']=True` para `kind='ddr'`, o `rows` unificado
filtrado por `width_class='narrow'` e o `all_rows` da matriz filtrado por `''` (a mesma
forma do bloco eMMC), as duas chaves do §10.7.1, e dois `<h3>` no template. **O
`partner_kind_save` não muda** — posta por pk, e foi assim que o eMMC ganhou a segunda
tabela de graça. O `rotulo` da mensagem de erro (`:790`) ganha a largura, senão dois
erros saem com o mesmo nome.

**Rótulo, e por que aqui ele foge do D9 [PROPOSTA].** O D9 manda `x4/x8` e `x16` como
rótulo humano e deixa "78/96 bolas" só para a bancada e o admin. **Nesta tela os dois
aparecem juntos** — `78 bolas (x4/x8)` — porque "78-ball" é a palavra do PRÓPRIO
comprador (`please remember that 78-ball chips are the least valuable`, Apêndice D §1):
ele não lê part number, ele conta bolas. Escrever só o token canônico numa tela que é
dele seria traduzir o vocabulário dele para o nosso. Os dois tokens são universais e não
se traduzem nos quatro idiomas; só a palavra "bolas" traduz (`balls` / `bolas` / `球`).

**D14 [DONO 2026-09-19] — a seção estreita nasce com as QUATRO densidades: 1Gb, 2Gb, 4Gb
e 8Gb, com o 8Gb SEM COTAÇÃO.** Isto **substitui** a P5 ("8Gb/narrow = sem linha até o
comprador responder"). Motivo: linha sem cotação já é um estado do sistema
(`STATUS_UNQUOTED`, célula vazia, "lacuna" âmbar na barra de tipos — `_kind_nav`,
`pricing/views.py:201`), e é assim que a tabela **pergunta** ao comprador. Três das
quatro portas em aberto do §10.1 (4Gb x4, 8Gb estreito, marca no 78-ball) se fecham
sozinhas quando ele preencher a tabela — sem uma conversa nova no WeChat. O 1Gb nasce
`status='no_buy'` ("x" na célula), que é o que ele já disse.

### 10.7.3 Tela 2 — a compra (`/partner/compras/<pk>/`)

**Como é hoje.** Quatro abas (`vendas/views_partner.py:386 _detalhe`): **resultado**
(`services.result_rows`, agrupado por MARCA e, dentro dela, **uma linha por
`SalesOrderLine`**, cada uma com o seu campo de recusa `rej_<pk>` e de repactuação
`new_unit_rmb`), **chips** (`lot_chips`, PN a PN), **categorias** (`category_glossary`, o
dicionário das caixas WTC) e **pagamentos**.

**O que vem de graça.** Com a largura na `UniqueConstraint` da linha (P4), onde havia UMA
linha passam a existir DUAS — cada uma com recusa e repactuação próprias. **É exatamente
o que faltou na SO-0007**, onde o acerto precisou lançar média ponderada entre 78 e 96
bolas (Samsung DDR3 2Gb virou ¥1,36, um preço que não existe em nenhuma conversa —
Apêndice D §9). A tabela, o agrupamento por marca, os subtotais e o formulário de recusa
**não mudam de forma**.

**O que precisa de mão.** O **rótulo** (`SalesOrderLine.label`, `vendas/models.py:401`):
duas linhas escritas "Samsung · DDR3 2Gb" com preços diferentes são piores que a média
ponderada de hoje — o comprador não saberia em qual digitar a recusa.

**D15 [PROPOSTA] — a linha da venda usa o vocabulário do LOTE (`''`/`narrow`/`wide`), não
o do eixo (`''`/`narrow`).** O §10.3(c) já separa os dois vocabulários pelo motivo certo;
esta é a aplicação dele à `SalesOrderLine`. **A linha é REGISTRO do que embarcou; o preço
e a caixa são CHAVE.** Registro tem de ser exato, chave tem de ser estável — por isso o
D10 mantém `''` para o x16 na `CategoryCode` (código de caixa é eterno) e por isso a
linha **não** pode herdar essa ambiguidade: em `SalesOrderLine`, `''` significa "x16" numa
venda nova e "misturado" numa venda anterior ao corte, e o rótulo não tem como saber
qual. Com `wide` explícito o rótulo diz `x16` ou `x4/x8` sem adivinhar, as linhas antigas
ficam `''` e saem sem sufixo (é a verdade sobre elas), e a consulta ao grid traduz
`wide → ''` num ponto só (`price_from_key`). Custo: um vocabulário a mais na constraint
da linha. Sem isso, ou o rótulo mente ou ele passa a depender da data da ordem.

Nas outras abas: **chips** — a chave de `precos` (colisão §10.7.1) e a largura como
coluna nova na tabela de PN (é tela de comprador, não tem máscara); **categorias** — o
`label_for_key` ganha o eixo (`services.py:2405`) e a caixa estreita entra no glossário
com a dica de bolas, que é onde o comprador aprende a convenção; **exports** (`compra_aba_csv`,
`compra_planilha`, `compra_resultado_pdf`, packing list) — a largura viaja **dentro do
rótulo da categoria**, sem coluna nova, e o ida-e-volta do `auditar_planilha_comprador`
tem de seguir dando ZERO diferença (CLAUDE.md §5).

### 10.7.4 Onde isto entra nas fases da Parte 2

- **P1** (+): `celulas` e `trav_linha` com a largura na chave; `ctx['dual']` para `ddr`;
  as duas seções no `partner_kind.html` + i18n dos rótulos novos nos 4 idiomas;
  `rotulo` do `partner_kind_save`; teste de colisão que morde.
- **P2** (+): `estoque/views.py:221/228`.
- **P4** (+): D15 (vocabulário da linha); `precos` do `lot_chips`; coluna de largura na
  aba de chips; `label_for_key` do glossário; teste de colisão na tela da compra.
- **P5** (revisada por D14): semear **4** linhas estreitas na genérica — 1Gb `no_buy`,
  2Gb ¥0,50, 4Gb ¥1,00, **8Gb sem cotação**.

---

## Apêndice A — `MEDIR_bus_width.py` (censo read-only; Fase 0 e pré-voo da Fase 5)

Modelo: `MEDIR_pratica_origem.py` (boilerplate `django.setup()`) + banner do
`COLETAR_largura_bits.py:150` + savepoint revertido. **Este plano é o único arquivo da
tarefa**: o executor cria `MEDIR_bus_width.py` na raiz copiando o bloco abaixo (não existe
cópia separada para divergir); o dono roda. **Nada aqui escreve.**

```python
# -*- coding: utf-8 -*-
"""
MEDIR_bus_width.py — READ-ONLY. Quanto de LARGURA (x4/x8/x16/x32/x64) mora hoje no
campo `interface`, em KnownPart e ChipFamily, por classe e por marca — e o que NÃO é
largura nem protocolo (OUTRO, listado valor a valor).

    env -u DATABASE_URL python MEDIR_bus_width.py      # local
    python MEDIR_bus_width.py                           # prod (DATABASE_URL exportado)

Roda em transação revertida. Aborta em zero (leitura que não aconteceu ≠ "não tem").
"""
import collections, os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django; django.setup()                                     # noqa: E402
from django.db import connection, transaction                     # noqa: E402
from chips.models import KnownPart, ChipFamily                    # noqa: E402
from chips.chip_types import spec_for                             # noqa: E402
# Depois da Fase 2 importe de chips.knowledge.convention: split_bus_width, e de
# chips.conventions: BUS_WIDTH_VOCAB. Na Fase 0 (antes do código existir) use as cópias abaixo.
VOCAB = ("x4", "x8", "x16", "x32", "x64")
RX_LEAD  = re.compile(r"^\s*(x(?:4|8|16|32|64))\b\s*(.*)$", re.I)
RX_SPEED = re.compile(r"^@\s*(\S.*)$")
RX_PROTO = re.compile(r"(eMMC|UFS|ONFI|Async|NAND|NOR|SPI|PPN|mDOC|Rambus|PCIe)", re.I)
RX_ANY   = re.compile(r"\bx(4|8|16|32|64)\b", re.I)          # largura em QUALQUER posição (só para listar)

def balde(v: str) -> str:
    v = (v or "").strip()
    if not v: return "VAZIO"
    m = RX_LEAD.match(v)
    if m:
        resto = m.group(2).strip()
        if not resto: return "LARGURA_PURA"
        if RX_SPEED.match(resto): return "LARGURA+VELOCIDADE"
        return "LARGURA+SOBRA"          # 'x16 (2 dies)' — sobra sem destino
    if RX_SPEED.match(v): return "VELOCIDADE_SÓ"
    if RX_PROTO.search(v): return "PROTOCOLO"
    return "OUTRO"

def classe(chip_type: str) -> str:
    s = spec_for(chip_type or "")
    return s.category if s else ("(vazio)" if not chip_type else "(fora do vocabulário)")

def main():
    d = connection.settings_dict
    print(f"\n⚠  BANCO-ALVO → name={d.get('NAME')}  host={d.get('HOST') or 'localhost'}  port={d.get('PORT') or ''}\n")
    sid = transaction.savepoint()
    try:
        total = KnownPart.objects.count(); nfam = ChipFamily.objects.count()
        print(f"KnownPart: {total}   ChipFamily: {nfam}")
        if total == 0 or nfam == 0:
            print("✗ ZERO linhas — leitura que não aconteceu (banco errado? vazio?). Abortando."); return 1

        # 1. KnownPart: balde × classe, por marca, e OUTRO valor a valor
        bc = collections.Counter(); por_marca = collections.Counter(); outros = collections.Counter()
        classe_nao_permite = []; diverg = []; sobras = []
        qs = KnownPart.objects.select_related("brand", "family").only(
            "part_number", "interface", "chip_type", "brand__name", "family__interface", "family__prefix")
        for kp in qs.iterator(chunk_size=2000):
            b = balde(kp.interface); c = classe(kp.chip_type)
            bc[(b, c)] += 1
            if b != "VAZIO": por_marca[(kp.brand.name, b)] += 1
            if b == "OUTRO": outros[kp.interface.strip()] += 1
            if b == "LARGURA+SOBRA": sobras.append((kp.part_number, kp.interface))
            if b.startswith("LARGURA") and c in ("managed_nand", "managed_mcp", "catalog"):
                classe_nao_permite.append((kp.part_number, kp.chip_type, kp.interface))
            if b.startswith("LARGURA") and kp.family and RX_LEAD.match(kp.family.interface or ""):
                fw = RX_LEAD.match(kp.family.interface).group(1).lower()
                kw = RX_LEAD.match(kp.interface).group(1).lower()
                if fw != kw: diverg.append((kp.part_number, kp.family.prefix, fw, kw))
        print("\n── KnownPart.interface: balde × classe ──")
        for (b, c), n in sorted(bc.items(), key=lambda kv: -kv[1]): print(f"{n:6d}  {b:20s} {c}")
        print("\n── por marca (só não-vazios) ──")
        for (m, b), n in sorted(por_marca.items()): print(f"{n:6d}  {m:16s} {b}")
        print(f"\n── OUTRO ({sum(outros.values())} registros, {len(outros)} valores distintos) — TODOS: ──")
        for v, n in outros.most_common(): print(f"{n:6d}  {v!r}")
        print(f"\n── LARGURA+SOBRA (não migram): {len(sobras)} ──"); [print("   ", *s) for s in sobras]
        print(f"\n── largura em classe NÃO permitida (eMMC/UFS/eMCP/uMCP/catalog): {len(classe_nao_permite)} ──"); [print("   ", *s) for s in classe_nao_permite]
        print(f"\n── DIVERGÊNCIA known × família (tela vai mudar para o valor do registro): {len(diverg)} ──"); [print("   ", *s) for s in diverg]

        # 2. ChipFamily
        fb = collections.Counter(); fout = []; fdentro = []
        for f in ChipFamily.objects.select_related("brand").only("prefix", "interface", "chip_type", "brand__name"):
            b = balde(f.interface); fb[b] += 1
            if b not in ("VAZIO", "PROTOCOLO"): fout.append((f.brand.name, f.prefix, f.chip_type, f.interface))
            elif RX_ANY.search(f.interface or ""): fdentro.append((f.brand.name, f.prefix, f.chip_type, f.interface))
        print("\n── ChipFamily.interface ──")
        for b, n in fb.most_common(): print(f"{n:6d}  {b}")
        print("   famílias fora de VAZIO/PROTOCOLO (as 25 + os OUTRO):"); [print("   ", *x) for x in sorted(fout)]
        print("   largura DENTRO de texto de protocolo (não migram — decisão do dono):"); [print("   ", *x) for x in sorted(fdentro)]

        # 3. Lote (informativo, D6 — nada será tocado). RLS: precisa do escopo de plataforma.
        try:
            from tenancy.scope import platform_scope
            from estoque.models import InventoryEntry, PendingEntry, RejectedEntry
            with platform_scope():
                for M in (InventoryEntry, PendingEntry, RejectedEntry):
                    tot = M.all_companies.count()
                    n = sum(1 for e in M.all_companies.only("interface").iterator() if balde(e.interface).startswith(("LARGURA", "VELOCIDADE")))
                    print(f"   {M.__name__:15s} total={tot:6d}  com largura/velocidade em interface={n}")
                    if tot == 0: print("   ⚠ zero linhas — se o banco tem lotes, o RLS engoliu a leitura")
        except Exception as exc:            # noqa: BLE001
            print(f"   (lote não lido: {type(exc).__name__}: {exc})")
        return 0
    finally:
        transaction.savepoint_rollback(sid)

if __name__ == "__main__":
    sys.exit(main())
```

O executor ajusta o script depois da Fase 2 para importar `split_bus_width` e
`BUS_WIDTH_VOCAB` da fonte única (as cópias locais existem só porque a Fase 0 roda antes
do código existir — e um teste `MedirEspelhoTests` compara as duas até a troca).

## Apêndice B — Fontes usadas para D5 (§3.2)

- eMMC 5.1 datasheet (Farnell 4159922): *"Supports three data bus widths: 1 bit
  (default), 4 bits, 8 bits"*; `BUS_WIDTH` = Extended CSD byte [183] (modo escolhido pelo
  host) — https://www.farnell.com/datasheets/4159922.pdf
- Micron NAND: datasheets intitulados *"1Gb x8, x16: NAND Flash Memory"* (MT29F1G08/16)
  e *"4Gb, 8Gb, 16Gb: x8, x16 NAND Flash Memory"* — largura de I/O como atributo do
  dispositivo — https://datasheet.octopart.com/MT29F1G08ABADAWP-IT:D-Micron-datasheet-11552893.pdf
- Micron LPDDR5 `MT62F768M64D4WT-031 XT:B` (DigiKey): organização 768M × 64 no PN —
  https://www.digikey.com/en/products/detail/micron-technology-inc/MT62F768M64D4WT-031-XT-B/22041238
- Catálogo oficial Micron com coluna `BUS WIDTH` (x16/x32/x64): `import_micron_catalog.py:19`.
- JEDEC/Samsung/Micron "Configuration"/"Bit Org." — dossiê §6 (pesquisa da sessão anterior).

## Apêndice C — Mensagem de abertura sugerida para o chat do executor

> Você vai executar o `PLANO_BUS_WIDTH.md` (raiz do repo), **Revisão 1 (2026-09-15)** —
> leia primeiro o bloco "REVISÃO 1" do cabeçalho: a Parte 1 (§4) é a fundação e tem sete
> emendas `[Rev.1]`; a Parte 2 (§10) só começa depois da Parte 1 inteira. Antes de qualquer
> edição: leia `CLAUDE.md` inteiro, depois o plano inteiro. Comece pela **Fase 0** — o censo
> (`MEDIR_bus_width.py`) e os dois baselines — e traga os números para eu ver antes de
> abrir um arquivo de código. O dossiê anterior (`DOSSIE_bus_width_para_Fable.md`) foi
> substituído pelo plano; onde divergirem, vale o plano; onde o plano divergir do código,
> vale o código — e me avise. As decisões D1–D8 estão travadas; se algo no banco real
> contrariar uma delas, pare e pergunte. Você não roda nada que escreva: prepara, explica,
> entrega com dry-run; eu rodo. Sem `git push` nas listas de comando.

## Apêndice D — O conhecimento do comprador (cópia integral, 2026-09-15)

> Cópia **integral** do `CONHECIMENTO_largura_preco_rentabilidade.md` (texto intacto; só os
> níveis de título foram rebaixados para caber sob este apêndice) escrito
> pelo chat da SO-0007 em 13–14/09/2026, para este plano ser o único arquivo da tarefa. A
> procedência de cada linha (**[WU]** comprador · **[DATASHEET]** · **[DADOS]** · **[DONO]** ·
> **[ABERTO]**) é do autor original. Onde a Parte 2 (§10) e este apêndice divergirem em
> DESENHO, vale o §10 (que cita as decisões do dono de 15/09); onde divergirem em FATO
> sobre o comprador, vale o apêndice — ele é a fonte.

### Largura de barramento — preço e rentabilidade
##### Conhecimento coletado do comprador (Wu Quan) em 13–14/09/2026, na SO EMIN-SO-2026-0007

Para o chat que está construindo a feature de `bus_width`. Tudo aqui tem
procedência marcada:

- **[WU]** — o comprador disse, textualmente, no WeChat
- **[DATASHEET]** — verificado em fonte primária do fabricante
- **[DADOS]** — inferido cruzando a SO real; a conta está no fim
- **[DONO]** — decisão do dono da eMiner
- **[ABERTO]** — ainda sem resposta; não trate como fato

---

#### 1. A descoberta central

**[WU]** *"My friend, please remember that 78-ball chips are the least
valuable — unless they are DDR4 or DDR5."*

**[DATASHEET]** Micron 2Gb DDR3 (x4/x8/x16), seção Options:
- **78-ball FBGA → x4 e x8**
- **96-ball FBGA → x16**

Logo, **"78-ball" é sinônimo exato de "x4 ou x8"**. O comprador não lê part
number — ele **conta as bolas do encapsulamento**. Isso é a coisa mais
aproveitável de tudo: o operador da bancada consegue fazer a mesma separação
sem saber o que o chip é.

**[DADOS]** Prova de que o rótulo dele agrega x4 e x8: no 1Gb ele contou 221
peças; o 78-ball real da SO (x4 + x8) é 222. **Uma peça de diferença em 222.**
Se o rótulo "1g8" dele fosse só x8, o número seria 55.

---

#### 2. Tabela de preço — 78-ball (x4 + x8)

| Densidade | Preço | Origem |
|---|---|---|
| **1Gb** | **RECUSA — valor zero** | **[WU]** `1g04. No` / `1g08. No` / `1g8没有任何价值` |
| **2Gb** | **¥ 0,50** | **[WU]** `2g08. 0.5rmb` |
| **4Gb** | **¥ 1,00** | **[WU]** `4g08. 1rmb` |
| **8Gb** | **[ABERTO]** | não havia 8Gb 78-ball no lote; nunca foi perguntado |

**x4 e x8 têm o MESMO preço dentro de cada densidade.** **[WU]** *"Because the
number 2g08 I mentioned already includes 2g4"* — ele não separa os dois.

**Marca não altera preço de 78-ball.** **[WU]** Perguntado se ¥0,5 e ¥1 valem
para todas as marcas: *"Same price."*

> ⚠ Assimetria importante para a feature: **78-ball é preço único por
> densidade; 96-ball continua tendo faixa por marca** (ver §4). Não generalize
> o "same price" para o x16.

---

#### 3. A exceção DDR4 / DDR5

**[WU]** *"78-ball chips are the least valuable — **unless they are DDR4 or
DDR5**."*

Perguntado se DDR4/DDR5 de 04 e 08 bits mantêm o preço do 16-bit:
**[WU]** *"Yes, my eldest brother.. You're right."*

Então: **DDR4 e DDR5 de 78-ball não sofrem desconto nenhum.** Foi aplicado na
SO-0007 — 24 peças de Samsung `K4A4G045WD` (4Gb DDR4 **x4**, portanto 78-ball)
ficaram intactas a ¥6.

**[ABERTO]** Ele também disse *"DDR4. Only 4G8. 5rmb"*, que não encaixa em nada
da SO — não existe DDR4 4Gb x8 nela. Pode ser tabela futura ou pode se referir
ao DDR4 8Gb. **Não use esse ¥5 como regra sem confirmar.**

---

#### 4. 96-ball (x16) — referência do grid atual

Estes preços **não vieram desta negociação**; são o grid que já vigorava na
SO-0007, e servem de linha de base para medir o impacto da largura.

| Tipo | Densidade | ¥ |
|---|---|---|
| DDR3 | 1Gb | 2 |
| DDR3 | 2Gb | 3 · **2** nas marcas de segunda linha |
| DDR3 | 4Gb | 4 · **3** nas marcas de segunda linha |
| DDR3 | 8Gb | 4 |
| DDR4 | 4Gb | 6 (Samsung) · 7 (Nanya) · 5 (GigaDevice) |
| DDR4 | 8Gb | 13 (Samsung, SK) · 10 (Micron) |
| DDR4 | 16Gb | 15 |

Segunda linha observada no grid: **ESMT, Kingston, PieceMakers**.
Primeira linha: **Samsung, SK Hynix, Micron, Nanya**.

**[WU]** O 1Gb **x16** continua sendo comprado normalmente — a recusa do 1Gb é
só do 78-ball. Confirmado pelo dono depois de perguntar. São 1.107 peças na
SO-0007 (¥2.214) que **não** foram tocadas.

---

#### 5. O que isso significa para RENTABILIDADE

A largura vira um **eixo novo do veredito**, ortogonal à densidade:

| Condição | Veredito |
|---|---|
| DDR3 1Gb **78-ball** | **NÃO RENTÁVEL** — valor zero, o comprador recusa |
| DDR3 2Gb 78-ball | rentável, mas a ¥0,5 (era ¥3 → **−83%**) |
| DDR3 4Gb 78-ball | rentável, mas a ¥1 (era ¥4 → **−75%**) |
| DDR4/DDR5 78-ball | **sem alteração** — preço cheio |
| Qualquer 96-ball | **sem alteração** |
| **GDDR, qualquer largura** | **[DONO]** sucata — não entra em lote nenhum |

⚠ O caso que mais dói: **DDR3 1Gb 78-ball hoje é classificado como RENTÁVEL
pelo sistema e embarcado — e o comprador recusa.** Custa frete e trabalho de
bancada para voltar zero. É o primeiro caso que a feature tem que barrar.

⚠ Segundo caso: **DDR3 2Gb 78-ball a ¥0,5.** É a maior massa — 1.908 peças
só nesta SO. A ¥0,5 provavelmente fica abaixo do limiar de rentabilidade
(conferir com a régua atual), o que o tornaria descarte também.

---

#### 6. Gramática de PN por marca — verificado nesta sessão

A largura é decodificável do PN nestas marcas. Cada uma foi conferida cruzando
contra o campo `interface` do catálogo, que vem de datasheet.

| Marca | Onde está a largura | Exemplo |
|---|---|---|
| **Samsung** | `pn[5:7]`: `04`=x4 · `08`=x8 · `16`=x16 · `32`=x32 | `K4B2G**08**46D` → x8 |
| **SK Hynix** | dígito em `pn[6]`: `4`=x4 · `8`=x8 · **`6`=x16** | `H5TQ2G**8**3CFR` → x8 |
| **Nanya** | soletrado: `<profundidade>M<largura>` | `NT5CB256**M8**` → x8 |
| **ESMT** | `M15x<dens>G<largura><prof>` | `M15T2G**16**128A` → x16 |
| **PieceMakers** | `PMF5118` + `08`/`16` | `PMF5118**16**EBR` → x16 |
| **Kingston** | `D<prof 2ch><largura 2ch>` | `D**25****16**EC4B` → x16 |
| **Micron** | ⛔ **NÃO decodifica** — é código FBGA de 5 caracteres a laser | `D9MNZ` → consultar `interface` no catálogo |

**Armadilhas já pagas:**
- **Samsung tem `06` = x4 EMPILHADO e `07` = x8 EMPILHADO.** Eletricamente são
  4 e 8 bits, fisicamente são outra coisa. Não estão documentados em nenhum
  `.md` interno.
- **A regra posicional da Samsung QUEBRA no K4N** (GDDR): diz x16, o datasheet
  diz x32. Nunca aplique a gramática de uma família sem prova.
- **LPDDR decodifica "por acaso"**: `K4E4E164EB` é LPDDR3 e a posição devolve
  "x16" porque calha de ter `16` ali. LPDDR/eMMC/eMCP/UFS/NAND usam mapa de
  capacidade, não posição. Teste `chip_type` antes de aceitar a decodificação.
- **NAND também tem largura de I/O**: `KF98G16Q4X` é NAND SLC com `x16`
  legítimo. Largura não é exclusividade de DRAM.

---

#### 7. Fatos da SO-0007, para calibrar

Lote de **10.000 peças / ¥42.217**, PCB, todas as marcas.

| | peças | ¥ |
|---|---:|---:|
| 78-ball afetado | **2.525** | — |
| └ 1Gb — recusado | 222 | −444 |
| └ 2Gb — a ¥0,5 | 1.908 | −4.770 |
| └ 4Gb — a ¥1 | 395 | −1.185 |
| **impacto total** | | **−6.399 (−15,2%)** |
| 96-ball intocado | 4.157 | — |

**25% das peças de DRAM discreta do lote eram 78-ball.** Não é caso de borda.

---

#### 8. [ABERTO] — não trate como fato

1. **4Gb x4 isolado** — ele listou `1g04`, `1g08`, `2g04`, `2g08`, `4g08`, mas
   **nunca disse `4g04`**. Assumimos ¥1 (igual ao 4g08), coerente com "78-ball
   por densidade", mas ele não confirmou.
2. **8Gb 78-ball** — nunca discutido.
3. **`"DDR4. Only 4G8. 5rmb"`** — não encaixa em nada da SO (ver §3).
4. **Divergência de contagem**: no 2Gb e 4Gb ele contou **407 peças a menos**
   que o manifesto. Provavelmente não terminou de separar. Não resolvido.
5. **Marca em 78-ball no futuro** — o "same price" foi sobre ESTE lote. Se um
   dia entrar ESMT/Kingston de 78-ball, não está dito se vale o mesmo ¥0,5.

---

#### 9. Limitação estrutural que a feature precisa resolver

A `vendas.SalesOrderLine` tem `UniqueConstraint(order, brand, kind, gen,
tier_value, tier_unit)` — **sem largura**. Por isso, ao fechar o acerto da
SO-0007, foi preciso lançar **média ponderada** entre 78-ball e 96-ball em cada
linha (ex.: Samsung DDR3 2Gb virou ¥1,36, um preço que não existe em nenhuma
conversa). Custou ¥6,48 de arredondamento e uma nota explicando.

**Com `bus_width` na chave da linha, esse acerto seria exato e legível.** É o
argumento de negócio mais forte para a feature: não é organização de catálogo,
é dinheiro e rastreabilidade de acordo comercial.

---

#### 10. Fontes

- WeChat com Wu Quan, 13–14/09/2026 (prints no chat de origem)
- Micron 2Gb DDR3 SDRAM datasheet — mapeamento 78-ball/96-ball
- Samsung Part Number Decoder (fev/2009) + DDR3 Product Guide
- SO EMIN-SO-2026-0007 e o resultado fechado em 14/09/2026 (¥35.811,52)
- Planilha `SO-0007_bus_width_summary.xlsx` — detalhe por largura, EN/中文
