# AUTORIA — o processo obrigatório de um chat de marca para adicionar PNs

> Guia definitivo de como um **chat de marca** (um agente que cuida de UMA marca) adiciona
> chips ao WhatTheChip **sem erro** e **em escala**, e como o **dono** publica. É a versão
> longa e didática do contrato do `CLAUDE.md §5` — leia isto inteiro antes de tocar em qualquer
> yaml ou submissão. Vale para **qualquer marca, atual ou futura**.

---

## 0. A filosofia em 4 frases

1. **O banco de produção é a fonte da verdade** do catálogo vivo (6 mil+ PNs, cresce todo dia).
   Git/yamls = **gramática + código**; a autoridade (`known_parts`) vive no **banco**.
2. **Você PESQUISA e CONFIRMA, não inventa.** Fonte não-Tier-1 (datasheet do fabricante = ouro;
   Octopart = secundário; distribuidor **não** é Tier-1)? Então **não decide**.
3. **Duas trilhas, dois canais de escrita** (nunca o banco direto): GRAMÁTICA via yaml→`load_brands`;
   KNOWN_PARTS via `submit_known_parts`→aprovação do dono.
4. **Só a sua marca.** Nunca toque em outra marca nem nos mapas globais (donos = Samsung).

---

## 1. Leitura obrigatória (o chat lê ANTES de qualquer coisa)

| Arquivo | Por quê |
|---|---|
| `CLAUDE.md` (§2 regras de ouro, §5 contrato, §6 convenção) | a espinha de segurança + a convenção |
| `<MARCA>.md` (ex.: `SAMSUNG.md`) | anatomia do PN da marca, pegadinhas, fontes, bugs conhecidos |
| `chips/knowledge/<marca>.yaml` | a GRAMÁTICA atual da marca (o que você vai editar) |
| `chips/knowledge/schema.py` | o **portão** — o que é aceito/rejeitado (escreva já no formato certo) |
| `chips/chip_types.py` | a **fonte única** dos tipos canônicos (`chip_type`/`subtype`) |

---

## 2. A TRAVA DE ESCRITA (o invariante inviolável)

> Um agente **só** escreve catálogo por **dois canais**, e ambos passam pelo **portão**:
> - **GRAMÁTICA** (famílias + mapas): edita o yaml → `load_brands` (dry-run = portão) → PR.
> - **KNOWN_PARTS** (autoridade): o chat **valida** (`submit_known_parts <arquivo>` dry-run = portão) e
>   **entrega o arquivo**; o **DONO roda o `--commit`** (grava `submitted`, oculto) e **aprova**. Por quê:
>   o chat roda num sandbox **isolado** que **não alcança** o banco do dono (sem túnel de rede), e a
>   **regra de ouro #1** manda o commit ser do dono (existe por causa do incidente dos 5.900).
>
> É **PROIBIDO** escrever o banco direto (shell/ORM/admin ad-hoc/import) e escrever em **prod**. As pipelines de máquina
> (`import_*`/`enrich_*`/`bless_base`) são operação do **dono**, não do chat. Por quê: o portão
> vive no **modelo** (`KnownPart.clean()`/`save()` + `CheckConstraint`s) — todo write passa por ele,
> mas escrever "por fora" é a única forma de burlar, então é proibido por contrato.

---

## 3. Trilha A — GRAMÁTICA (adicionar/corrigir família ou mapa)

A gramática é o decode posicional: dado um PN, quais posições/tabelas dizem o tipo, a geração e a
capacidade. Uma família conserta/quebra **todos** os PNs dela de uma vez — por isso é a trilha mais
poderosa e a mais perigosa.

### 3.1 Anatomia de uma família (no yaml)
`prefix` · `chip_type`/`subtype`/`interface` · `pn_length` · `is_emcp` · `active` · `priority` ·
`decode_cap_pos`/`decode_cap_len`/`decode_cap_map` · `decode_gen_pos`/`decode_gen_map` ·
`decode_density_type` · `suffix_rules` · `tip` · `reasoning`.

### 3.2 O portão rejeita ANTES de gravar (o que ele pega)
Rodar `load_brands --brand <marca>` (dry-run) É o portão. Ele **rejeita com erro acionável** se:
- **Convenção:** `chip_type` genérico (`RAM`/`DDR`) em família ativa; `subtype` sujo (com
  Mobile/Multi-Channel/densidade/tensão); `interface` carregando geração de RAM.
- **Estrutura do decode (F2/E):** `decode_cap_pos` setado **sem** `cap_map` nem `density_type`
  (não há como decodificar); posição `pos+len` **passa do `pn_length`** (lê fora do PN).
- **Regra de ouro #5:** família KM com dígito na 3ª posição sem `decode_gen_pos: null`.
- **Mutuamente exclusivos:** `decode_density_type` **e** `decode_cap_map` juntos.
- **Duplicata:** dois `prefix` iguais na mesma marca; `char_key` repetido num mapa.
- **Mapa global (F2/D):** definir `DRAM_PC`/`DRAM_MOBILE` em yaml **não-Samsung** → recusa (esses
  são universais, brand=None; só a Samsung os define, o resto só referencia).
- **Cross-brand:** um `prefix` que já pertence a **outra marca** (prefixo é único global).

### 3.3 O TESTE-GOLDEN (obrigatório para família nova) — a prova positiva
O portão prova que a família é **bem-formada**; o golden prova que ela **decodifica CERTO**.

Cada família nova entra com **PNs âncora + a saída esperada**, no `_<MARCA>_GOLDEN` do
`chips/tests.py`. Uma linha real:
```
K4W4G1646Q  →  GDDR3 · 512MB · dram_density "4Gb=512MB por die" · RENTÁVEL
```
Por que é insubstituível:
- O `characterize --diff` só diz "nada que já existia mudou" — ele **não valida uma família nova**
  (o PN novo não tem "antes" pra comparar). O golden é a **única** prova de que a família nasce certa.
- **Pega decode errado:** se você mandar ler a capacidade na posição errada, o golden âncora dá "2MB"
  em vez de "8MB" → **falha na sua cara**, antes de entregar.
- **Pega sequestro entre famílias:** se mexer numa família e ela "capturar" PNs de outra (por
  `priority`), a âncora da outra família muda de resposta → o golden dela **falha** e aponta o culpado.
- **Já é price-ready:** a linha guarda a **rentabilidade**, que é a chave da futura faixa de preço.

> ✅ **Enforcement AUTOMÁTICO (jul/2026):** `GoldenObrigatorioTests` **falha** se uma família de
> **prefixo NOVO** (fora do baseline `_FAMILIES_GRANDFATHERED`, as 188 famílias que já existiam)
> entrar **sem** PN-âncora num `_<MARCA>_GOLDEN`. As 188 atuais são grandfathered (provadas em prod);
> **toda família nova** tem que trazer o golden — não é mais só disciplina, a suíte trava.

> 🔴 **E a suíte trava para TODO MUNDO, não só para você (incidente 2026-08-24).** O
> `GoldenObrigatorioTests` é global: ele varre `chips/knowledge/*.yaml` inteiro. Naquele dia ele
> falhou com **13 famílias de TRÊS marcas** — ESMT (11), SanDisk (`SD5DH26`), Toshiba-Kioxia
> (`TYE0`) — todas criadas no mesmo dia, nenhuma com âncora. Efeito colateral: um chat de marca que
> **não mexeu em nada** roda `test chips`, vê vermelho e não tem como saber que a dívida é de outro.
> Os três já tinham os PNs pesquisados nos seus `submissions/*.yaml` — só não os ligaram ao golden.
>
> **Gramática e golden são a MESMA entrega.** Criou família no yaml? A âncora entra no mesmo passo,
> não "na próxima rodada".
>
> ⚠ **Família MAGRA precisa MAIS de âncora, não menos.** É contraintuitivo: sem
> `decode_cap_map`/`decode_density_type` a família não decodifica capacidade, então parece que "não
> há o que provar". Ao contrário — sobra exatamente o que mais quebra: o `chip_type` e o **veredito
> de rentabilidade**. É aí que mora o bug recorrente do projeto, "INDETERMINADO em vez de NÃO
> RENTÁVEL para chip legado" (`CLAUDE.md §7`), que já mordeu LPDDR2, GDDR2, ePoP e eMCP de geração
> desconhecida. A âncora de uma magra tipicamente é uma linha só — tipo + `INDETERMINADO`, ou tipo +
> `NÃO RENTÁVEL` quando a geração já reprova. Barata de escrever, e é a única prova que existe.

### 3.4 O HANDSHAKE de rentabilidade — nenhum chip fica sem decisão comercial
Um teste (`RentabilidadeHandshakeTests`) garante que **nenhum `chip_type` comercial cai em
INDETERMINADO com specs saudáveis**. Consequência prática: se você adicionar um **tipo/geração novo**
ao `chip_types.py` (ex.: `DDR6`, `GDDR7`) e **não** declarar a regra de rentabilidade, o teste
**quebra**. Você é forçado a decidir: é rentável (qual limiar?) ou não? — antes de o chip chegar ao
operador. Foi exatamente o buraco do GDDR (era comercial e devolvia INDETERMINADO). É também o **guard
do preço**: sem "é rentável?" não há faixa de preço.

### 3.5 Regressão
- `characterize_baseline --diff <baseline>` → prova que **só** o pretendido mudou (0 nos PNs existentes).
- Rode o **teste de regressão dedicado da marca** (`test_<marca>_*`) quando existir.

### 3.6 `reasoning` (advisory)
Preencha o `reasoning` da família com a **fonte Tier-1 da regra de decode** (a proveniência que a
gramática não tinha). Hoje é recomendado (90% do legado não tem → não é hard-reject); o `load_brands`
avisa quem está sem.

---

## 4. Trilha B — KNOWN_PARTS (a autoridade que vence a gramática)

Um `known_part` é um PN confirmado com specs que **vencem** a gramática (só `confidence`
confirmed/manual). Na Opção 2, ele vive no **banco**, não no yaml.

**Forma do arquivo de submissão** — duas chaves no topo, e a primeira é uma **pegadinha**:

```yaml
brand: Kingston          # ⚠ TEXTO PURO. Nunca o bloco name/code/notes.
known_parts:
  - part_number: D2516EC4BXGGB
    chip_type: DDR3L
    density_gbit: 4Gb
    confidence: confirmed
    notes: "fonte Tier-1 aqui"
```

⚠ **`brand` na SUBMISSÃO é o NOME da marca, em texto.** O bloco

```yaml
brand:                   # ❌ isto é o yaml de GRAMÁTICA, não o de submissão
  name: Kingston
  code: KST
  notes: ''
```

pertence a `chips/knowledge/<marca>.yaml`. Na submissão ele faz o valor virar um dict, a busca da
marca não casa nada, e **até 2026-08-19 o comando respondia "crie a gramática antes"** — conselho
errado, que manda o dono procurar um problema que não existe. Mordeu duas vezes (Kingston,
2026-08-17 e 2026-08-19); hoje o `submit_known_parts` detecta o bloco e mostra a linha certa, mas
o arquivo continua sendo responsabilidade do chat de marca. A submissão só NOMEIA a marca —
`name`/`code`/`notes` são da gramática, que já existe quando você submete.

**Fluxo:**
1. Pesquisa Tier-1 → escreve um arquivo de submissão (mesma forma: `part_number` + specs +
   `confidence` + **`notes` com a fonte Tier-1**).
2. O chat **valida**: `submit_known_parts <arquivo>` (dry-run = portão) + confere numa base de teste
   própria (a suíte golden). **Entrega o ARQUIVO** validado ao dono — o chat NÃO roda o `--commit`.
3. O **DONO roda o `--commit`** na máquina dele: `submit_known_parts <arquivo> --commit --user <id-do-chat>`
   → grava `submitted` (oculto). Por quê é o dono: o sandbox do chat é **isolado**, não alcança o banco
   do dono (sem rede); e a **regra de ouro #1** manda o commit ser do dono (incidente dos 5.900).
   ⚠ `--user` = um usuário que **representa o chat** (ex.: `samsung-chat`), **≠ do dono** — senão o
   four-eyes barra na aprovação. (No teste local dá pra rodar sem `--user`: fica isento.)
4. O **dono aprova** no admin (`/admin/chips/knownpart/`, filtro review_status → Submetido). A
   aprovação aplica **four-eyes** (quem submete ≠ quem aprova) e carimba quem/quando.
5. Só depois de aprovado o PN fica **visível/autoritativo**.

**Travas embutidas:** o mesmo portão da convenção roda no `clean()` do modelo; `confidence` sem fonte
Tier-1 → o `submit` avisa e o revisor exige; PN já aprovado **não é rebaixado** por uma re-submissão
(não tira do ar); dedup por PN normalizado; `CheckConstraint`s de confidence/review_status/four-eyes.

### 4.1 PN que JÁ está aprovado (o balde COMPLEMENTO) — 2026-08-17

O dry-run agora confronta cada PN com o **banco** (pela chave `part_number_norm`) e classifica:

| Balde | O que é | O que acontece |
|---|---|---|
| `NOVO` | não existe | entra `submitted` (fluxo normal) |
| `RESUBMETE` | existe em draft/submitted/rejected | reescrito como `submitted` |
| `COMPLEMENTO` | **aprovado com campo VAZIO** que o arquivo preenche | só com `--fill-empty` |
| `CONFLITO` | aprovado com valor **diferente** | nunca aplicado — vira `<arquivo>.conflitos.yaml` |
| `IGUAL` | aprovado e já com o dado | nada |

Por que isso existe: até 2026-08-17 a checagem morava **dentro** do bloco do `--commit`, então o
dry-run dizia "13 válidos" para uma submissão que ia gravar 12, e o aviso só nascia depois de
gravar. Dezenas de PNs "confirmados" ficaram *identity-only* e os LOTES herdaram snapshot sem spec.

**Regra para o chat:** se o dry-run mostrar `COMPLEMENTO`, a entrega ao dono TEM que incluir o
`--fill-empty` no comando de `--commit` — senão aqueles PNs são pulados de novo, em silêncio.

`--fill-empty` é **aditivo**: preenche só campo vazio, nunca sobrescreve, nunca mexe no
`review_status` (o registro não sai do ar), exige `notes`/`source_url` no PN, e grava backup
reversível (`--revert`). Sobrescrever valor aprovado continua sendo decisão humana no admin.

⚠ Completar o catálogo **não** conserta os lotes: `InventoryEntry` guarda o snapshot do
lançamento. O fechamento do laço é o `resnapshot_lote --all --commit` (o comando avisa).

Panorama de TODAS as marcas de uma vez (read-only): `python manage.py audit_submissions`.

### 4.2 CONFLITO — quem vence é decidido por CAMPO, não por PN (2026-08-17)

A 1ª varredura em produção achou **147 conflitos** (contra 2 campos vazios): o registro tinha
valor das **pipelines de import** (Micron API, Samsung PSG), virou `approved`, e a submissão
Tier-1 que ia corrigir foi pulada. Aplicar tudo em bloco seria pior — em vários campos o BANCO
é melhor (`interface: 'x16 @ 800MHz (1600MTPS)'` no banco contra `'x16'` no arquivo).

Política (decisão do dono), aplicada por `python manage.py resolve_conflicts`:

| classe | campos | política |
|---|---|---|
| **preço** | `chip_type` `subtype` `capacity` `density_gbit` `density_gb` `emcp_ram` `emcp_nand` | a **submissão** vence — é o que mexe no valor do lote, revise o diff do dry-run |
| **identidade** | `device` `fbga_code` | a **submissão** vence |
| **interface** | `interface` | fica o **mais específico** (o mais longo) |
| **texto** | `notes` | **merge** — o import tem Voltage/Package, a submissão tem o raciocínio Tier-1 |
| | `source_url` | mantém a do banco e registra a da submissão dentro do `notes` (o campo é UMA url) |

Dry-run por padrão, backup + `--revert`, `--exclude` pra tirar PN de fora, `--sem-precos` pra
aplicar só a parte segura. PN que o portão do modelo rejeitar é reportado sem derrubar a varredura.

---

## 5. O mapa completo — classe de erro → trava (tudo que criamos)

| Classe de erro | Trava (automática) | Onde vive |
|---|---|---|
| Forma/convenção (tipo genérico, subtype sujo) | Portão Pydantic + `KnownPart.clean()` | `schema.py`, `models.py`, `convention.py` |
| Estrutura de decode (posição/chave inválida) | Validadores estruturais (F2/E) | `schema.py::FamilySpec._estrutura_decode` |
| Duplicata (PN/prefixo/char_key) | Dedup no portão + `UniqueConstraint` norm | `schema.py`, `models.py` |
| Colisão entre marcas (prefixo) | Guard cross-brand + `UniqueConstraint(prefix)` | `load_brands.py`, `models.py` |
| Sobrescrever mapa global (densidade) | Guard de mapa global (F2/D) | `load_brands.py` |
| Vocabulário de confiança / review inválido | `CheckConstraint`s no banco | `models.py` |
| Auto-aprovação (autoridade) | Four-eyes (clean + CheckConstraint) | `models.py`, `admin.py` |
| Registro não-aprovado vazando pro engine | `_USABLE &= approved` | `engine.py` |
| Perda catastrófica de catálogo | Tripwire `guard_catalog` + backup + `restore_known_parts` | comandos |
| Regressão (quebrar PN que funcionava) | `characterize_baseline --diff` + suíte | comando + `tests.py` |
| **Família nova decodificando errado** | **Teste-golden** (âncora → saída esperada) | `tests.py::_<MARCA>_GOLDEN` |
| **Tipo novo sem decisão comercial (INDETERMINADO)** | **Handshake** de rentabilidade | `tests.py::RentabilidadeHandshakeTests` |
| INDETERMINADO mentindo "Rentável: sim" | Estado âmbar no gateway | `estoque/views.py`, template |
| Fato errado (spec plausível mas incorreta) | ⚠ **NÃO automatizável** — fonte Tier-1 + revisão humana | disciplina + aprovação do dono |

---

## 6. Checklist de handoff (o chat roda LOCAL; NÃO toca em prod)

- [ ] Só mexi na MINHA marca (yaml e/ou submissão); não toquei em mapa global de outra.
- [ ] Nada inventado/estimado; PN ambíguo → **perguntei ao dono**.
- [ ] **Gramática:** `load_brands --brand X` (dry-run/portão) passou.
- [ ] **Família nova:** entreguei **PNs âncora no golden** (tipo/subtipo/capacidade/rentabilidade).
- [ ] **Tipo novo:** o **handshake** passa (declarei a regra de rentabilidade).
- [ ] `characterize_baseline --diff` mostrou **só** o pretendido; rodei o teste dedicado da marca.
- [ ] **Known_parts:** cada um com **fonte Tier-1 na `notes`**; `submit_known_parts <arq>` (dry-run = portão)
      passou. Entrego o **ARQUIVO validado** ao dono (ele roda o `--commit` + aprova — sandbox isolado + regra #1).
- [ ] **A suíte inteira verde:** `python manage.py test chips estoque --settings=core.settings_test`.
- [ ] Banco local atualizado (`migrate` + gramática em dia) antes de testar.
- [ ] Entreguei ao dono: o **arquivo de submissão** (known_parts) e/ou o **diff do yaml + golden** (gramática), + as saídas dos testes. **Não toquei no banco do dono nem em prod.**

---

## 7. Publicação (o DONO faz — `DATABASE_URL` de prod é segredo)

- **Gramática:** `git push` (versiona) **+** `load_brands --brand X --commit` contra o prod (aditivo,
  sobe `catalog_version` → reflete na hora, sem restart).
- **Known_parts:** `submit_known_parts --commit` + **aprovar no admin**.
- **Sempre depois:** `guard_catalog` (confirma que o catálogo não despencou).

---

## 8. O que NÃO está automatizado (honestidade)

O portão pega erro de **forma e estrutura**; o golden pega erro de **decode**; o handshake pega
**dead-end comercial**. Mas **nenhum sistema pega erro de FATO** — uma spec plausível mas errada
(capacidade trocada, geração errada) passa por todas as travas. Só a **fonte Tier-1 obrigatória** + a
**revisão humana do dono** (aprovação in-DB) barram isso. É o mesmo teto de Wikidata/MDM/PIM: dado
curado é humano-no-loop. Por isso a disciplina "não invente, cite a fonte, ambíguo → pergunte" é
inegociável.

---

## 9. Marca nova (11ª, 50ª, …) — a prova da escala

Basta criar `chips/knowledge/<marca>.yaml` (só gramática) — o `deploy_catalog` **descobre sozinho**
(glob). **Todas** as travas acima já valem pra ela sem nenhuma configuração: portão, dedup, guards,
handshake, golden, tripwire. Opcional: um `<marca>.md` (camada humana). É isso que torna o processo
escalável a qualquer marca **atual ou futura** — nenhuma trava é específica de marca.

---

## 10. Onde cada peça vive (referência rápida)
`chips/knowledge/schema.py` (portão) · `chips/knowledge/convention.py` (normalização, fonte única) ·
`chips/models.py` (clean/save + constraints + review in-DB) · `chips/engine.py` (`_USABLE` approved,
`assess_profitability`, `_match_family`) · `chips/chip_types.py` (vocabulário + `profit_family`) ·
`chips/admin.py` (fila de aprovação, four-eyes; `ProfitabilityConfig`) · `chips/tests.py`
(`_<MARCA>_GOLDEN`, `RentabilidadeHandshakeTests`, portão) · `estoque/views.py` (gateway) ·
comandos: `load_brands`, `submit_known_parts`, `guard_catalog`, `restore_known_parts`, `characterize_baseline`.
