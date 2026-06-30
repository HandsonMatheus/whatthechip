# Briefing — Arquitetura para escala global do WhatTheChip (WTC)

> **Para que serve este documento.** É o ponto de partida de um chat focado **100% em
> arquitetura e escalabilidade**. Reúne, num lugar só: (1) o contexto de negócio e a
> **visão — onde queremos chegar**; (2) a arquitetura atual e o que ela acerta; (3) o
> **diagnóstico completo dos pontos que travam a escala**, com evidência real coletada
> operando o sistema em produção. O objetivo do próximo chat é **pesquisar as melhores
> soluções do mercado hoje** para escalar isto de forma saudável, **decidir** e **meter a
> mão no código**.
>
> Escrito por um agente (Claude) depois de mexer no sistema inteiro nesta sessão: engine
> de classificação, gramática, rentabilidade, convenção de tipos, e um **deploy real em
> produção** (catálogo + correção de estoque). Os problemas abaixo não são teóricos — cada
> um tem evidência do que aconteceu na prática.
>
> ⚠️ **Como usar no próximo chat:** este `.md` é o *briefing*, não a decisão. Ele expõe os
> problemas e faz as perguntas; o chat focado deve trazer alternativas do mercado, pesar
> trade-offs com o dono (eMiner) e só então implementar. **O código é a fonte da verdade** —
> confirme tudo em `chips/engine.py`, `chips/models.py`, `core/settings.py` antes de agir.

---

## 1. O que é o WTC e ONDE QUEREMOS CHEGAR

### O produto
**WhatTheChip** é uma aplicação Django que **classifica Part Numbers (PNs) de chips de
memória** para o mercado de **reciclagem / refurbishing** de eletrônicos. Operado pela
**eMiner (Paraguai)**.

O usuário é um **operador de bancada**: lê o código gravado a laser num chip recuperado,
digita na busca, e recebe **em tempo real**:
- **Tipo e specs** — eMMC / UFS / eMCP / uMCP / LPDDR / DDR / GDDR / NAND…, capacidade,
  densidade, interface;
- **Destino comercial** — para qual caixa física o chip vai, e se é **RENTÁVEL / NÃO
  RENTÁVEL / INDETERMINADO** (recondicionar vs. sucata/moagem).

Ou seja, é ao mesmo tempo **classificador** e **ferramenta de triagem de rentabilidade**.

### A visão (o norte de todas as decisões)
> **Ser o "Google dos chips": a base de classificação de chips mais ampla e precisa do
> mundo.**

Concretamente, "escalar de forma saudável" significa chegar a:

1. **100–200 marcas** (hoje são ~9–14 com tratamento real). Cada marca nova traz famílias,
   regras de decode e PNs confirmados próprios.
2. **Cobertura da cauda longa** — milhões de PNs possíveis. A gramática generaliza; o banco
   confirma. Os dois precisam crescer ordens de magnitude.
3. **Onboarding de marca sem depender de um desenvolvedor.** Hoje, adicionar uma marca é
   editar arquivos Python. A meta é que um **curador (ou uma IA)** produza o conhecimento da
   marca num formato estruturado e o sistema absorva — sem tocar em código de aplicação.
4. **Crescimento colaborativo e auditável** — buscas, desconhecidos, submissões e correções
   já são logados; isso deve virar um pipeline de enriquecimento que escala.
5. **Multi-tenant (fase futura, outro chat):** cada empresa cliente com seu **tenant** —
   estoque, operadores e limiares de rentabilidade próprios — enquanto o **conhecimento de
   chips permanece global e compartilhado** (o moat: cada PN confirmado por um cliente
   melhora a base para todos).

### As duas fontes de conhecimento (a base de tudo)
1. **Banco de PNs confirmados (`KnownPart`)** — a **fonte da verdade**. PNs com `confidence`
   = `confirmed`/`manual` vencem qualquer decode.
2. **Gramática (`ChipFamily` + `DecodeMap`)** — a **válvula de escape** que decodifica
   posicionalmente qualquer PN ainda não confirmado. É a prioridade de *cobertura* porque
   generaliza: corrigir a regra de uma família conserta **todos** os chips dela de uma vez.

Esse desenho de duas camadas é **correto e deve ser preservado**. O problema não é o
desenho — é **onde e como o conhecimento dessas camadas é armazenado e alimentado**.

---

## 2. Arquitetura atual (o que existe e funciona)

| Camada | Tecnologia |
|---|---|
| Linguagem / framework | Python 3.11 · **Django 5.2 LTS** |
| Banco | **PostgreSQL** (prod e local); SQLite em memória nos testes |
| Front | **HTMX** + templates + CSS puro (sem SPA/build JS) |
| Deploy | **Render** (auto-deploy no push para `main`); gunicorn + WhiteNoise |

**Apps:** `chips/` (coração: engine, modelos, API de busca), `estoque/` (inventário por
lote, com login), `pages/` (CMS simples de documentação).

**O engine — `chips/engine.py`** (arquivo mais importante). Ponto de entrada `classify(pn)`,
que tenta em ordem: (1) banco exato (`KnownPart` utilizável), (2) lookup FBGA, (3) gramática
da família, (4) fuzzy matching. Além disso `assess_profitability(result)` aplica as regras
comerciais — **fonte única** da rentabilidade — e `is_dead_by_generation` deriva dela.

**O padrão que ACERTAMOS (e queremos estender):** a recém-criada **`chips/chip_types.py`** é
a **fonte única do vocabulário de tipos** (`chip_type`/`subtype`), consumida pelo engine,
pelo gateway do estoque e pelos validadores. Junto com `canonical_gen` (label) e
`assess_profitability` (rentabilidade), é o modelo a seguir: **uma fonte declarativa, todos
leem dela**. A tese deste documento é **levar esse mesmo princípio — dado declarativo, não
código espalhado — para o resto do sistema.**

### 2.1 Os três sistemas adjacentes que pesam nas decisões

Quem for decidir a arquitetura precisa entender três peças que conversam com o catálogo —
porque decisões como **frescor do estoque** (4.4) e **multi-tenant** dependem delas.

**(a) A convenção de tipos (`chips/chip_types.py`) — o MODELO PROVADO.** Foi o trabalho
desta sessão. A regra ("opção 1"): para **DRAM discreta** (DDR/LPDDR/GDDR/SDRAM) a **geração
vai no `chip_type`** (`DDR3`, `LPDDR4X`…), espelhada no `subtype`; memória **gerenciada**
(eMMC/UFS/eMCP/uMCP/NAND) mantém o `chip_type`. Existe porque o `chip_type` é o **único**
campo de tipo que o `InventoryEntry` do estoque persiste — então ele tem que carregar a
geração. O ponto para o próximo chat: **isto é a prova de conceito do princípio "fonte única
+ dado declarativo".** Foi validada por uma **rede de regressão** (caracterizar `classify()`
para 100% dos ~6.500 registros, antes/depois, e diferenciar) e por um **deploy real em
produção** — comportamento preservado. O caminho data-driven do resto do sistema é **estender
este modelo**, não inventar outro.

**(b) A rentabilidade — a SEGUNDA fonte única (e a primeira a virar por-tenant).**
`assess_profitability(result)` é a fonte única das regras comerciais (eMCP/LPDDR/DDR/UFS…);
`is_dead_by_generation` deriva dela; os limiares vivem em **`ProfitabilityConfig`** (singleton
no banco, editável no admin). Dois fatos que pesam nas decisões: (1) é **outro** sistema
single-source que já funciona — reforça o padrão a estender; (2) na visão multi-tenant, a
rentabilidade é **a primeira coisa que vira por-tenant** — mercados diferentes valorizam chips
de forma diferente, então `ProfitabilityConfig` singleton → **por-tenant** é uma mudança já no
horizonte. A *classificação* (o que o chip É) é global; a *rentabilidade* (quanto vale) é do
tenant.

**(c) O estoque — a camada CONSUMIDORA (e o que vira por-tenant).** `Lot` → `InventoryEntry`
(guarda o **snapshot** da classificação — ver 4.4). O **gateway de triagem**
(`estoque/views.py`) decide o destino em 3 etapas (a primeira que falha decide):
**identificação** (tem specs?) → **fonte** (confirmado no banco?) → **rentabilidade**
(`assess_profitability`). Saídas: `aprovado` / `fila` (vai pra `PendingEntry`, gestor revisa) /
`reprovado` (vai pra `RejectedEntry`, auditoria) / `desconhecido`; há um bloqueio **"só
confirmados"** que barra PN não confirmado de contaminar o estoque. Para as decisões: o estoque
é a camada que, no futuro, é **por-tenant** (lotes, operadores, fila) — e ela **consome** o
catálogo **global** + a rentabilidade. Essa **fronteira global × tenant** é o que mantém o
"Google dos chips" compartilhado enquanto cada cliente tem o seu estoque.

---

## 3. O diagnóstico central: **conhecimento-como-código**

O sistema funciona, mas **o conhecimento por marca vive em Python**. Cada marca, cada
família, cada regra de decode e cada correção de PN é uma **edição de código + commit +
deploy**. A 9 marcas dá pra segurar; à meta de 100–200, trava. Quase todos os problemas
abaixo são sintomas dessa raiz.

A consequência prática: **só um desenvolvedor (ou uma IA editando Python ao vivo, que é
frágil) consegue adicionar/corrigir conhecimento.** Isso é incompatível com "Google dos
chips" — onde o gargalo tem que ser a *curadoria* (pesquisa tier-1 da verdade do chip), não
a *engenharia* (transcrever isso pra Python e fazer deploy).

---

## 4. Os problemas, em detalhe (com evidência desta sessão)

> Cada item traz: **o que é / o que eu vi**, **por que trava a escala**, e uma **direção
> possível** (ponto de partida para a pesquisa — não uma decisão fechada).

### 4.1 `fix_known_parts` — ~600 correções *hardcoded* em Python
**O que vi:** rodando o deploy em produção, o comando reportou `11 corrigido(s), 0
criado(s), 586 já correto(s), 3 não encontrado(s)`. São ~600 entradas, cada uma um dict
Python com `chip_type`, `capacity`, `subtype`, `notes`, `source_url` e um campo **`Motivo`**
(a justificativa tier-1 da correção). Exemplos reais que passaram: `MT29C4G48MAZAPAMC5IT`
(SLC NAND 512MB, confirmado por FBGA), `MT42L384M32D3LP…` (LPDDR2 1.5GB), `MT41K64M16TW`
(corrigindo `chip_type='Flash'` errado → `DDR3L`), `KLUDG4U1EA` (Samsung classificado como
Kioxia por engano).

**Por que trava:** a abstração ("correção autoritativa que vence tudo") **é necessária** —
mas a *autoridade* já é o `confidence=confirmed` do `KnownPart`; o arquivo é só um jeito de
popular isso. A 200 marcas vira um arquivo de dezenas de milhares de linhas: lento de
carregar, campo minado de conflito de merge, ilegível, e **impossível para um curador
não-dev contribuir**. O `Motivo` (que é ouro — a procedência tier-1) fica enterrado em
comentário de código em vez de ser um dado consultável.

**Direção possível:** as correções viram **DADO** (CSV/JSON/tabela no banco), com `Motivo` e
`source_url` como **colunas de procedência**. Um importador genérico aplica. O
`fix_known_parts.py` se aposenta. Pergunta para o mercado: *qual o melhor formato/ferramenta
para um "catálogo de correções" versionável, auditável e editável por não-devs?*

### 4.2 `populate_*` + `add_chip_families` — gramática-como-código, **e duplicada**
**O que vi:** um arquivo Python por marca (`populate_samsung`, `populate_hynix`,
`populate_micron_mcp`, `populate_kingston`, `populate_sandisk`, `populate_toshiba`,
`populate_rayson`, `populate_piecemakers`, `populate_gigadevice`) definindo famílias +
decode maps como dicts. **E** o `add_chip_families.py` **redefine famílias que os
`populate_*` já definem** — vi `H5AN`, `H5TC`, `MT40A`, `MT41K`, `TH58`, `NT5CC`… aparecerem
nos dois. Como rodam em sequência, **um sobrescreve o outro** — foi exatamente o bug que me
mordeu nesta sessão (editei a família num arquivo e o outro revertia).

**Por que trava:** a *lógica* de decode (no engine) é genérica e boa; mas os *dados* de
decode (prefixos, posições, mapas, sufixos) estão presos em Python, **um arquivo por marca**.
A 200 marcas, são 200 arquivos Python escritos à mão, com a duplicação magras-vs-full
multiplicando o risco de conflito.

**Direção possível:** o conhecimento de cada marca vira **dado estruturado** — um
`samsung.yaml`/`.json` (famílias + mapas + PNs confirmados) — carregado por **um** comando
genérico (`load_brand`). O engine não muda. Mata a duplicação: **uma fonte por família**.
Pergunta para o mercado: *como definir uma "gramática de PN" de forma declarativa e
validável? Existe DSL/schema de catálogo pronto, ou se desenha um schema próprio (ex.: JSON
Schema) com validação no load?*

**Sub-questão estrutural (a decidir no formato): um modelo ou dois?** Hoje a gramática são
**duas** entidades — `ChipFamily` (a anatomia do PN: prefixo, posições, comprimentos, e
*qual* tabela usar) e `DecodeMap` (a tabela de tradução código→valor, ex.: `DRAM_PC`:
`CH→32Gb/4GB`), ligadas por FK. É normalização clássica: define a tabela uma vez, várias
famílias a referenciam. **Quando o reuso é real, é saudável** — `DRAM_PC`/`DRAM_MOBILE` são
compartilhados por várias famílias Samsung, e consertar a tabela conserta todas de uma vez.
**Quando não é, vira só indireção** — boa parte dos mapas é **1:1 com uma única família**
(`PMF_DDR3_CAP`, `THGBM_CAP`, `GD5F_NAND_CAP`…), e aí a separação não compra nada (a
armadilha "`decode_density_type` e `decode_cap_map` são mutuamente exclusivos" é sintoma
desse acoplamento frágil; e entender uma família exige olhar a família **e** perseguir os
FKs até os mapas — dois lugares, onboarding mais pesado). **Ponto central:** isso é
*ortogonal* ao problema de escala — um modelo ou dois, ambos são **código** hoje. Mas o
trade-off **normalizar × desnormalizar** reaparece no formato declarativo: o `samsung.yaml`
pode **embutir** o mapa em cada família (fácil de ler/escrever, mas repete os compartilhados)
ou ter uma **seção de mapas compartilhados** (DRY, com a mesma indireção de hoje). *Lean*
inicial: **inline por padrão + uma seção opcional de mapas compartilhados** para os poucos
genuinamente reutilizados (estilo JEDEC) — pega o melhor dos dois. **Antes de decidir,
medir** o reuso real dos `DecodeMap` atuais (quantos são compartilhados vs. 1:1).

### 4.3 O deploy — 13+ passos manuais, lento e frágil
**O que vi nesta sessão, ao vivo, três fragilidades reais:**
- **(a) Localhost × produção sem trava.** Você rodou metade dos comandos no localhost
  achando que era produção (o `manage.py` sem `DATABASE_URL=` usa o banco local). Só
  descobrimos porque uma remoção retornou lista vazia. **Não há nenhuma trava** que diga
  "você está prestes a gravar no banco X".
- **(b) Migração linha-a-linha.** O `normalize_convention --commit` ficou **minutos** no ar
  porque aplica **1 SELECT + 1 UPDATE por registro × 3.189 registros** contra um Postgres
  remoto (Oregon). Um `bulk_update` faria em segundos. (Rodar no Shell do Render, mesma
  região do banco, também mitiga — latência ~1ms vs ~200ms.)
- **(c) Reverts poluindo o repo.** Cada comando reversível (`fix_pns`, `refresh_lote`,
  `normalize_convention`, `clean_lote`, `bless_base`) cospe um `*_revert.json` na **raiz do
  repositório**. Um deles chegou a renomear/mexer num arquivo **versionado** (precisei
  restaurar via git).

**Por que trava:** o deploy de catálogo é uma cerimônia de 13+ comandos, em ordem,
cada um com `--commit` e o `DATABASE_URL` certo, mais reiniciar o serviço (cache `lru_cache`
do engine — regra de ouro #3). Frágil para fazer com frequência; e a frequência **vai
aumentar** com mais marcas.

**Direção possível:** um único `deploy_catalog` (ou migração Django de dados que roda sozinha
no deploy do Render); `bulk_update` no lugar dos loops; uma **trava de segurança** que
imprime/confirma o banco-alvo antes de gravar; reverts numa pasta dedicada ou tabela de
auditoria. Pergunta para o mercado: *qual a melhor prática para migrações de DADOS (não
schema) idempotentes, reversíveis e seguras em produção, em escala?*

### 4.4 O estoque guarda um *snapshot* da classificação — e ele **defasa**
**O que vi:** o `InventoryEntry` grava `chip_type`/`capacity`/etc. **no momento do
lançamento**. Quando o engine melhora (corrigimos um bug de "dies" da Micron, por ex.), o
estoque **não atualiza sozinho** — tivemos que rodar `fix_pns` no lote 39 para reclassificar
15 entradas (uma Micron estava gravada como **48GB**; o valor correto era **6GB**).

**Por que trava:** a cada melhoria do engine, **todo lote de todo cliente** vira dívida de
reclassificação manual. Com muitos tenants e muitos lotes, isso não fecha.

**Direção possível (a discutir, tem trade-off):** classificar **on-read** (o engine como
fonte única, sem snapshot persistido) — sempre fresco, mas custa CPU por exibição; ou um
**refresh barato/agendado**; ou um **cache invalidável** por mudança de catálogo. Pergunta
para o mercado: *snapshot vs. cálculo-na-leitura para dados derivados que mudam quando a
regra muda — qual padrão, considerando performance e multi-tenant?*

**⚠ Aplicado nesta sessão (2026-06-30) — corrige na fonte, NÃO substitui o on-read.** O
`add_chip` passou a gravar de `estoque/views.py::_snapshot(server_result)` (não mais do POST
do cliente — capacidade DDR virava `None`); `_size_for_entry` captura a densidade DRAM
(formato `2G` p/ DDR/GDDR/SDRAM/RDRAM; GB p/ LPDDR/eMMC/UFS; case-sensitive `Gb`≠`GB`);
`_clean_interface` remove a geração espelhada do `interface`; o `export_xls` converte o
timestamp p/ Brasília. **O on-read deve preservar/superar essa lógica** — `_snapshot` é a
referência do que a leitura precisa produzir. Backfill de lote existente = re-rodar
`_snapshot` sobre as entradas (não há comando ainda; foi feito por snippet no Render Shell).

### 4.5 Normalização de PN no *write-time*
**O que vi:** PNs não são canonizados na escrita, então **duplicam**. No deploy apareceu
`MT29C4G48MAZAPAMC-5 IT` (cru, com hífen e espaço) convivendo com `MT29C4G48MAZAPAMC5IT`
(normalizado) — o engine tem até um *handler* para preferir um sobre o outro. Há também o
caso histórico de `:` / `.` gerando variantes. Sobram 5 duplicatas FBGA cruas inertes.

**Por que trava:** é uma **classe inteira de bug** (duplicatas, lookups que falham,
contagens erradas) que reaparece a cada importação/enriquecimento. A 200 marcas e milhões de
PNs, isso vira ruído crônico.

**Direção possível:** **uma** função canônica de PN aplicada em **toda** escrita e busca
(normalização no write-time + na query). Elimina a classe de bug de uma vez. Tipicamente
barato e alto retorno — bom candidato a "primeiro passo".

### 4.6 Resíduos que confundem quem lê o sistema
**O que vi:** o `add_chip_families` ainda imprime *"o engine usa **Gemini** para decodificar
os detalhes…"* — mas o **Gemini foi removido** (jun/2026). Achei `confidence='ai_high'` num
registro (KLUDG) — resíduo de runs antigas de IA. O antigo campo `status` (raw/enriched) foi
removido, mas o conceito ainda aparece em docs.

**Por que importa:** não trava a escala, mas **induz a decisão errada** de quem (humano ou
IA) for mexer — e a base de onboarding tem que ser confiável. Limpeza barata.

---

## 5. O que NÃO mexer (os acertos a preservar)

- **`chip_types.py`** como fonte única de tipos — recém-provado nesta sessão; é o **modelo**
  a estender, não a substituir.
- **`canonical_gen`** (label) e **`assess_profitability`** (rentabilidade) — mesma filosofia
  de fonte única; mantêm o sistema coerente.
- **A gramática (`ChipFamily` + `DecodeMap`)** como camada de generalização — corrigir uma
  família conserta todos os chips dela. O que muda é *de onde* ela é alimentada, não o que
  ela é.
- **A escada de confiança** (`confirmed` > `manual` > `distributor` > `estimated`) — o modelo
  de autoridade é sólido.
- **O padrão dry-run + revert** — a intenção está certa; falta *unificar e organizar* (4.3),
  não abandonar.
- **A hierarquia de fontes** (fabricante/datasheet > Octopart/Nexar > distribuidor > IA) — a
  disciplina de procedência tier-1 é o que dá valor ao "Google dos chips".

A mensagem para o próximo chat: **isto é uma evolução, não uma reescrita.** O núcleo está
certo; o objetivo é tirar o conhecimento de dentro do código.

---

## 6. Restrições e princípios (invioláveis)

- **Regra de ouro #1:** o agente **edita arquivos**; o **usuário roda** os comandos que
  alteram o banco. Toda proposta tem que respeitar isso (dry-run primeiro, reversível).
- **Idioma:** código, docstrings, comentários e mensagens em **português**; termos de domínio
  em inglês como já estão.
- **Stack travada:** Django **5.2.x LTS** + Python **3.11** (o Render espelha isso). Não subir
  major sem alinhar runtime.
- **Migrações comportamento-preservantes:** qualquer refactor pesado precisa ser provado por
  **rede de regressão** (caracterizar a saída de `classify()` para 100% dos registros antes/
  depois e diferenciar) — foi assim que a convenção de tipos foi validada com segurança.
- **Fonte única > código espalhado.** O princípio-guia de todas as decisões.
- **O código é a fonte da verdade** em qualquer conflito de documentação.
- **Sem segredos no repo.** `.env` gitignored; chaves só em env vars do Render.

---

## 7. A pergunta para o próximo chat (o que levar ao mercado)

O foco é **buscar as melhores soluções do mercado hoje** — não reinventar. Tópicos a
pesquisar e decidir:

1. **Catálogo data-driven / PIM.** Como sistemas de catálogo de peças (ex.: Octopart, Nexar,
   DigiKey, ou PIMs genéricos) modelam famílias, atributos e procedência de forma que
   curadores alimentem **dados**, não código. Vale um PIM pronto, ou um schema próprio?
2. **Definição declarativa da gramática de PN.** Schema (JSON Schema?), DSL, ou tabela —
   para descrever prefixos, posições de decode, mapas e sufixos por marca, com **validação no
   load** e mensagens claras. Como o mercado faz "parsers configuráveis por dado".
3. **Migrações de dados em produção, em escala.** Idempotência, reversibilidade, `bulk`,
   execução automática no deploy (vs. terminal manual), trava de banco-alvo. Frameworks e
   padrões recomendados em Django/Postgres.
4. **Dado derivado: snapshot vs. on-read vs. cache.** Padrão para classificação que muda
   quando a regra muda, equilibrando performance e (futuro) multi-tenant.
5. **Normalização canônica de identificadores** no write-time — padrão simples, mas confirmar
   a melhor prática (onde aplicar, como migrar os existentes sem perder histórico).
6. **(Fase futura) Multi-tenancy em Django** — separar o **global** (catálogo de chips) do
   **por-tenant** (estoque, operadores, limiares de rentabilidade). Bibliotecas/padrões
   (schema-per-tenant, row-level, etc.) e implicações.
7. **Pipeline de enriquecimento colaborativo** — transformar buscas/desconhecidos/submissões
   logados num funil de curadoria que escala (fila, priorização por volume, IA assistindo a
   pesquisa tier-1 mas humano confirmando).

---

## 8. Sequência de ataque sugerida (rascunho, o chat decide)

1. **Fundação, baixo risco:** (4.5) **normalização de PN no write-time** + (4.2-parcial)
   **unificar as definições de família** (matar a duplicação `populate_*` × `add_chip_families`).
   Não muda comportamento, deixa o terreno limpo.
2. **A alavanca grande:** desenhar o **formato de dado por marca** (schema + validação) e um
   **loader genérico**; migrar **uma marca** e o **`fix_known_parts`** como prova de conceito,
   com rede de regressão garantindo comportamento idêntico.
3. **Operacional:** (4.3) **deploy num comando** (+ `bulk_update`, trava de banco, reverts
   organizados) e (4.6) **limpeza dos resíduos**.
4. **Frescor:** (4.4) decidir e implementar o modelo de classificação do estoque.
5. **Depois, outro chat:** multi-tenancy.

---

## 9. Apêndice — mapa de arquivos-chave (para navegar rápido)

```
chips/engine.py           → classify(), gramática, assess_profitability (núcleo)
chips/chip_types.py       → FONTE ÚNICA de tipos (o padrão a estender)
chips/conventions.py      → canonical_gen() (fonte única do label de geração)
chips/models.py           → Brand → ChipFamily → KnownPart; DecodeMap; modelo + glossário
chips/management/commands/ → populate_* (1 por marca), add_chip_families, fix_known_parts,
                             import_*, normalize_convention, validate_convention, …
estoque/                  → Lot / InventoryEntry (snapshot), gateway de triagem, fix_pns,
                             refresh_lote, clean_lote (todos com dry-run + revert)
core/settings.py          → DATABASE_URL, config Render
CLAUDE.md                 → onboarding canônico (regras de ouro, convenções, armadilhas)
docs/                     → bíblias técnicas por tema (MICRON, RENTABILIDADE, FUZZY, …) e
                             a convenção de campos (CONVENCAO_CAMPOS_ESTOQUE.md)
```

**Glossário mínimo:** *gramática* = decode posicional do PN por `ChipFamily`+`DecodeMap`;
*FBGA* = código físico de 5 chars gravado a laser (o que o operador lê); *confidence* =
escada de autoridade do `KnownPart`; *gateway* = decisão de destino/rentabilidade do estoque;
*tenant* (futuro) = uma empresa cliente com estoque/operadores próprios sobre o catálogo global.

---

> **Resumo de uma linha para abrir o próximo chat:** *"O WTC quer ser o Google dos chips
> (100–200 marcas, multi-tenant). O núcleo (engine + gramática + fonte única de tipos) está
> certo, mas o conhecimento por marca está preso em código Python — preciso das melhores
> soluções do mercado para torná-lo data-driven, com deploy/migração saudáveis, sem reescrever
> o que funciona."*
