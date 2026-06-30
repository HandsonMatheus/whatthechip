# Proposta de arquitetura para escalar o WhatTheChip

> **O que é este documento.** É a **resposta ao** `docs/BRIEFING_ESCALABILIDADE.md`: a
> minha posição, problema por problema, sobre a melhor forma técnica de escalar o WTC de
> ~9 para 100–200 marcas — fundamentada em (1) leitura do código real, (2) medição de
> evidências no próprio repositório, (3) pesquisa das melhores práticas de Django/Postgres
> de 2025–2026 e (4) pesquisa do que **as gigantes usam hoje** para este tipo de problema
> (fontes ao final).
>
> **Esta é a versão revisada** após o teste de estresse das suas perguntas (segurança, edição,
> riscos, curva de aprendizado, Render, estoque, tempo real, "simplifica ou complica?"). A
> análise completa dessas 7 dimensões + a validação de mercado está no documento-companheiro
> **`docs/ANALISE_IMPLICACOES_ESCALABILIDADE.md`**; aqui ficou **incorporado o que mudamos** (ver
> o changelog no fim). Mudança principal: **o conhecimento vai direto para YAML/CSV** (dado fora
> do código), não para um degrau intermediário em Python.
>
> **Para quem não é técnico:** cada seção começa com a recomendação em linguagem simples
> (*"Em uma frase"*) e só depois entra no detalhe técnico (nomes de bibliotecas, mecanismos
> Django) para quem for implementar. Você pode ler só as frases-resumo e a Seção 1 e já ter
> a posição inteira.
>
> **Natureza:** é uma **proposta para você decidir**, não uma decisão tomada. Respeita as
> regras de ouro: *o agente edita arquivos, você roda os comandos*; toda mudança pesada é
> provada por **rede de regressão**; **é evolução, não reescrita** — o engine não muda.

---

## 1. A posição em uma frase

> **O núcleo do WTC está certo e não deve ser reescrito. O problema é um só — o
> conhecimento por marca está digitado dentro de programas Python — e a solução é um só
> princípio, que você já provou funcionar com o `chip_types.py`: tirar o dado de dentro do
> código e botá-lo num formato declarativo, validado na entrada e lido por um carregador
> genérico. Duas peças novas e pequenas resolvem quase tudo: (a) um modelo de dados por
> marca (arquivo → validação → carregador → o mesmo banco de hoje) e (b) um "número de
> edição do catálogo" (`catalog_version`) consultado na leitura.**

Tudo o que segue é o detalhamento dessas duas peças e de como elas atacam cada um dos seis
problemas do briefing.

**A pesquisa de mercado confirmou que essa direção não é um chute — é o padrão mais provado que
existe** para este tipo de problema: é como Salesforce (há ~25 anos), o Kubernetes inteiro, o
Open Policy Agent (CNCF) e o dbt são construídos, e é o que o livro de SRE do Google recomenda
("código E dado, mas separados") e o cânone de engenharia prega há 40 anos (Raymond: *"dobre
conhecimento em dados; separe política de mecanismo, porque a política muda mais rápido"*). É
também **mais Pythônico** que o estado atual. Com **uma** regra de ouro que mantém tudo simples
("menos é mais") por décadas:

> 🔑 **Dado é dado; lógica é no engine.** O arquivo de marca descreve *fatos e mapeamentos*
> (prefixo, posição, tabela). No dia em que ele precisar de um `if`, um loop ou uma expressão
> para ser entendido — **PARE**: isso é lógica, vai para o `engine.py`, não para o dado. Segurar
> essa linha é o que separa "dado declarativo" (a coisa certa) de "uma linguagem de programação
> ruim dentro do YAML" (o erro clássico). Você já pratica isso (fonte única de tipos e de
> rentabilidade).

---

## 2. O diagnóstico que eu confirmo (com evidência medida)

O briefing acerta a raiz: **conhecimento-como-código**. Eu não aceitei isso de palavra —
medi no repositório. Os números justificam a urgência e calibram a solução:

| Evidência medida | Valor | O que significa |
|---|---|---|
| `fix_known_parts.py` | **607 KB** de Python | ~600 correções, cada uma um `dict` com a procedência (`reason`/`source_url`) enterrada em comentário de código |
| `populate_samsung.py` / `populate_hynix.py` | **148 KB / 134 KB** | A "gramática" de cada marca é dado digitado dentro de um programa |
| Famílias definidas nos `populate_*` | **~178** | A 200 marcas isto vira milhares de famílias escritas à mão, em ~10 arquivos gigantes |
| Mapas de decode distintos | **58** | — |
| → usados por **1 só** família (indireção pura) | **36 (62%)** | Maioria: o mapa separado não compra nada, só espalha o conhecimento em dois lugares |
| → **compartilhados** (2+ famílias) | **22 (38%)** | Minoria, mas alguns muito reusados: `SAM_EMCP_CAP` por **22** famílias, `SAM_EMCP_GEN`/`SAM_FLASH_CAP`/`NAND_FLASH_CAP` por **8**, `DRAM_PC` por **6** |

E confirmei no código os três bugs/fragilidades que o briefing cita, lendo as linhas exatas:

1. **A duplicação `add_chip_families` × `populate_*` é real** (`add_chip_families.py`, ~linha
   655). Quando a família já existe e se roda com `--overwrite`, o comando faz
   `setattr` de **apenas 8 campos** (`chip_type`, `subtype`, `interface`, `is_emcp`,
   `decode_density_type`, `tip`, `priority`, `active`) com os valores "magros" dele. Ele
   **não** zera as posições de decode (essa parte do briefing eu corrijo — os
   `decode_cap_pos` etc. são preservados), mas **sobrescreve** os 8 campos por cima do que o
   `populate_samsung` definiu. Isso (a) **reverte edições** intencionais e (b) pode criar a
   combinação proibida `decode_density_type` + `decode_cap_map` ao mesmo tempo (a armadilha
   "mutuamente exclusivos" do CLAUDE.md). É exatamente o "editei num arquivo e o outro
   revertia" que travou a sessão anterior.
2. **O cache do engine fica velho por desenho** (`engine.py`, linha 285). `_get_all_families()`
   é `@lru_cache(maxsize=1)` **sem argumento** — a "chave" do cache nunca muda quando as
   linhas do banco mudam. Por isso existe a regra de ouro #3 ("reinicie após `populate`"):
   o `cache_clear()` só limpa o processo do comando, não os processos do servidor web.
3. **PNs duplicam por falta de canonização** (`engine.py`, linhas 1333/1377/1443). O engine
   tem um `except KnownPart.MultipleObjectsReturned: # salta silencioso` — ou seja, o
   sistema já **convive** com PNs que normalizam igual (`...MC-5 IT` vs `...MC5IT`) tapando
   o sintoma em vez de impedir a duplicata na escrita.

Conclusão do diagnóstico: **a gramática já é dado vestido de código.** Um `ChipFamily` é um
punhado de inteiros e strings curtas; um `DecodeMap` tem 4 colunas úteis. Nada ali *precisa*
ser Python. Isso muda a natureza da solução: não é uma reescrita arriscada, é **mudar a casa
do dado** que o engine já consome.

---

## 3. Os dois insights que unificam tudo

Antes de ir problema a problema: a pesquisa convergiu para **duas** ideias que, sozinhas,
resolvem ou destravam quase todos os seis problemas. Entendê-las primeiro evita tratar seis
sintomas como seis projetos separados.

### Insight A — O modelo híbrido: *arquivo → validação → carregador → o mesmo banco*

**Em linguagem simples:** hoje o conhecimento de uma marca está digitado dentro de um
programa; só um programador edita, e um erro de digitação quebra o app. Na proposta, o
conhecimento de cada marca vira um **arquivo de texto estruturado** (como um formulário
preenchido) que um curador — ou uma IA — edita. Antes de salvar, um **"inspetor" automático**
confere o formulário e aponta os erros em linguagem clara. Depois, **um único carregador
genérico** lê o formulário para dentro do banco que o engine já usa. O engine não muda.

Esse é o padrão dominante em 2025–2026 para "regra/configuração como dado" — é como
funcionam o GitOps, os *seeds* do dbt e o `sync_rules` do `django-rules`: **os arquivos
versionados são a fonte da verdade; um comando os sincroniza para o banco.** Você ganha de
graça o que hoje não tem: histórico e auditoria (`git diff` de uma marca), revisão antes de
aplicar, e validação na entrada. E encaixa perfeitamente na sua regra de ouro #1 (o curador
edita o arquivo; você roda o `--commit`).

### Insight B — O carimbo `catalog_version` (o "número de edição do catálogo")

**Em linguagem simples:** imagine que o catálogo inteiro de chips tem um **número de edição**,
como um livro. Toda vez que você muda uma regra de decode ou adiciona uma marca, a edição
sobe em 1. Esse **único número**, consultado na hora de ler, resolve **três** problemas de
uma vez:

- **o cache velho** (Problema 4.4-cache): o engine vê que sua cópia das regras é de uma
  edição antiga e recarrega sozinho — **acaba a regra "reinicie após `populate`"**;
- **o estoque defasado** (Problema 4.4): cada item guarda sob qual edição foi classificado;
  só recalcula os que ficaram para trás, nunca a frota inteira;
- **a auditoria**: toda classificação salva pode registrar "decidida na edição N".

Tecnicamente é uma linha-singleton no Postgres (`CatalogVersion`, um inteiro), incrementada
quando a gramática muda. É o sucessor estrutural das suas três regras manuais de hoje
("reinicie", "rode o fix para reclassificar", "promova a confirmed") — um carimbo único,
consultado na leitura, no mesmo espírito de *fonte única* do seu `assess_profitability`.

> **⚠ Correção (chat de estoque): o carimbo tem de cobrir a RENTABILIDADE também.** O destino do
> estoque depende de **duas** coisas: a gramática (`ChipFamily`/`DecodeMap`) **e** os limiares do
> `ProfitabilityConfig`. Se você muda um limiar no admin (ex.: `ddr4plus_min_gbit` → 1.0), a
> rentabilidade dos itens muda — mas a *gramática* não mudou, então um carimbo que só sobe com a
> gramática **não percebe**, e o estoque mostra "rentável?" defasado **em silêncio** (nem o atalho
> de igualdade pega). **Regra:** o `catalog_version` sobe quando muda `ChipFamily`, `DecodeMap`
> **ou** `ProfitabilityConfig` — ou seja, tudo que altera a saída de `classify()` + `assess_
> profitability`. Continua sendo **um** inteiro; só ampliamos *o que* o faz subir (um
> `post_save` no `ProfitabilityConfig` também — e, quando vier o upgrade de preço, também
> `PriceQuote`/`PriceConfig`; ver §4.7).

Guarde estes dois nomes — **modelo híbrido** e **`catalog_version`**. Eles reaparecem abaixo.

---

## 4. Recomendação, problema por problema

### 4.1 + 4.2 — O conhecimento por marca vira DADO declarativo

*(Trato os dois juntos porque a solução é a mesma peça: o modelo híbrido do Insight A.)*

> **🔄 Decisão FINAL: YAML direto (e por que paro de oscilar aqui).** Transparência total: eu
> balancei nesta questão (YAML → Python → YAML → Python). Isso aconteceu porque as duas opções são
> de fato **próximas** — mas o seu argumento desta vez é o **decisivo**, e desmonta exatamente a
> perna em que o "Python primeiro" se apoiava. **Vamos direto ao YAML/CSV**, sem o degrau de
> Python. Dois motivos, ambos seus:
>
> 1. **Quem faz a migração é uma IA** — e, para uma IA, escrever YAML+Pydantic é tão fácil quanto
>    dataclasses. Os ganhos do degrau Python (mypy/IDE/debugger, "sem formato novo") valem para um
>    **humano** editando; valem pouco quando quem migra é a IA. A premissa de custo do "Python
>    primeiro" era **ergonomia humana** — que aqui é fraca.
> 2. **"Python agora, YAML depois" é uma migração DUPLA:** extrair de `populate_*` → dataclasses
>    (1º passe + regressão) e depois dataclasses → YAML (2º passe + 2ª regressão). Ir direto ao
>    YAML faz a parte difícil (extrair + loader + regressão) **uma vez só** e já chega no destino.
>    "Resolver de uma vez" é o certo.
>
> O que **continua valendo**: o engine não muda; o Python fica onde é mecanismo (**carregador e
> engine**); a regra de ouro **dado é dado, lógica é no engine** (nada de `if`/loop no YAML); e os
> **trilhos de segurança** da migração (§7, passo 4) — **uma marca por vez**, regressão +
> **amostragem manual de PNs inéditos**, e o portão Pydantic. *(Isto supersede o "Python primeiro"
> do `ANALISE`, que vou alinhar. Considero a decisão final — não reabro sem informação nova, ex.:
> "um dev humano júnior vai manter esses arquivos no dia a dia".)*

**Em uma frase:** cada marca vira um `marca.yaml` (gramática) + `marca.csv` (correções), validados
por **Pydantic** e carregados por **um** comando genérico `load_brands` para as **mesmas tabelas**
`ChipFamily`/`DecodeMap`/`KnownPart` de hoje. Os ~10 `populate_*.py` e o `add_chip_families.py` se
aposentam, e **o engine não muda**.

**Por quê assim, e não as alternativas:**

- **Arquivos no repo como fonte da verdade** (e não "tudo no banco editado pelo admin")
  porque só os arquivos versionados te dão `git diff`, revisão antes de aplicar e o histórico
  de procedência — e porque mexer no banco de produção direto contraria sua regra de ouro #1.
  E não "só arquivos lidos em tempo real" porque isso obrigaria a reescrever o engine; o banco
  continua sendo a leitura rápida e indexada que o engine já faz.
- **Validação com Pydantic v2** (e não JSON Schema cru) porque ele dá a **melhor mensagem de
  erro** para um autor não-dev ou uma IA: *"families.2.decode_cap_pos: era esperado um número
  inteiro, veio 'três'"*. E porque as suas **regras de ouro viram código executável**: a
  exclusividade `decode_density_type` × `decode_cap_map` (#4), o "famílias KM com dígito na 3ª
  posição precisam de `decode_gen_pos=None`" (#5), a ordem `val_primary`/`val_secondary` em
  eMCP — tudo isso vira um validador com mensagem humana, em vez de uma armadilha tribal num
  `.md`. **Isto transforma a sua lista de "armadilhas comuns" em guarda-corpos automáticos.**
- **Formato — gramática em YAML, correções em CSV.** YAML aceita comentário (onde mora a
  procedência legível) e estrutura aninhada (família → seus mapas); é o mais amigável para uma IA
  gerar e para revisar em PR — é assim que catálogos de regras como Sigma e Semgrep funcionam. O ponto fraco do YAML (indentação/"problema da Noruega") é **neutralizado pelo
  Pydantic**, que falha alto e claro na entrada. As ~600 correções do `fix_known_parts` são
  uma **tabela plana** — CSV é o formato natural, e você **já tem ferramentas de CSV**
  (`import_*`, `audit_targets --file`, `fix_pns --file`).

**Isto mata a duplicação (4.2) por construção:** uma marca = um arquivo = uma definição
completa. O carregador **recusa** uma segunda definição do mesmo prefixo com um erro claro,
em vez de meio-sobrescrever em silêncio. O bug do `add_chip_families` **não pode mais
existir**.

**A sub-questão "um modelo ou dois" (inline × normalizado) — agora com a medição feita.**
O briefing pediu para *medir antes de decidir*. Medi: **62% dos mapas (36/58) são usados por
uma única família** — para esses, o mapa separado é só indireção, deve ser **embutido
(inline)** na família. Mas **38% (22) são compartilhados, alguns pesadamente** (`SAM_EMCP_CAP`
por 22 famílias). Logo a recomendação não é um chute, é o que o dado manda: **inline por
padrão + uma seção `shared_maps` para os ~22 genuinamente reusados** (estilo JEDEC),
referenciados por nome. O carregador expande os dois para a tabela `DecodeMap` de hoje — **o
banco não muda**; muda só a ergonomia de quem escreve. Exemplo do formato:

```yaml
# chips/knowledge/samsung.yaml
shared_maps:                 # os ~22 mapas reusados (corrige aqui, conserta todas as famílias)
  SAM_EMCP_CAP:
    "P6": { primary: "16GB", secondary: "4GB" }   # NAND, RAM — eMCP
  DRAM_PC:
    "4G": { primary: "4Gb", secondary: "512MB" }  # 'por die' o engine anexa — não escreva aqui

families:
  - prefix: K3QF                # mapa local → INLINE, sem indireção (é dos 62%)
    chip_type: LPDDR3
    decode_cap_pos: 4
    cap_map:
      "1": { primary: "1GB", secondary: "8Gb" }   # K3QF1F10DMAGCE000 ✓ Octopart
  - prefix: K4A                 # mapa reusado → referência ao compartilhado (é dos 38%)
    chip_type: DDR4
    cap_map: { $ref: DRAM_PC }
```

**Proveniência como dado de primeira classe (resolve a "preocupação do ouro enterrado").**
Hoje o `reason` (a justificativa tier-1) mora num comentário de código — invisível a qualquer
consulta. Na proposta, vira **campo**: `source_url`, `confidence`, um novo `source_tier`
(enum espelhando sua hierarquia de fontes: datasheet > Octopart > distribuidor > IA) e
`reason`/`provenance_note`, todos validados e carregados em colunas consultáveis. Aí você
consegue perguntar ao sistema "quais PNs `confirmed` estão sem datasheet?" — e a procedência
vira o que **torna seguro** o autoria por IA (um `source_tier` baixo cai automaticamente para
revisão humana, nunca vence a gramática). O `git log` do `samsung.yaml` passa a ser a sua
trilha de auditoria temporal, de graça.

**Não compre um PIM.** Avaliei: PIMs genéricos (Pimcore, Akeneo) modelam "produto com
atributos", não uma **gramática posicional de decode** (prefixo → posição → tabela). Adotar um
significaria torcer um motor genérico e reapontar seu `classify()` para um schema estranho —
uma reescrita. Mantenha o schema próprio; **roube só três ideias** do mundo dos catálogos de
peças (ex.: Part-DB, open-source): (1) a **abstração de "provedor"** — cada script de coleta/
enriquecimento passa a emitir o **mesmo registro declarativo** para revisão humana, em vez de
escrever direto no banco; (2) modelar **família → atributos tipados → datasheet/fonte
ligada** (você quase já faz); (3) **pontuação de completude** — um `load_brands --report` que
mostra, por marca, % de famílias com mapa, % de PNs confirmados, `source_url` faltando —
transformando curadoria em backlog medível.

---

### 4.3 — O deploy: de cerimônia de 13 passos a um comando seguro

**Em uma frase:** um único comando `deploy_catalog` (com trava de banco-alvo, `--dry-run`
padrão e `--commit`), rodado **de dentro do Render** (mesma região do banco), substituindo a
sequência manual; loops viram `bulk_update`; reverts saem do repositório para o banco.

As três fragilidades reais que você viu têm, cada uma, uma correção direta:

**(a) Localhost × produção sem trava.** A causa-raiz é o `dj_database_url` com *default* para
o banco local — sem `DATABASE_URL`, ele **cai em silêncio** no localhost. Correções, em
camadas: (1) trocar para `env.db()` **sem default**, que **quebra alto** se faltar a variável,
em vez de escrever no lugar errado; (2) um **banner de banco-alvo** impresso antes de qualquer
escrita (`host` + `name`, no estilo do `flush` do próprio Django); (3) em modo interativo,
**exigir que você digite o nome do banco** para confirmar. Esses três juntos teriam impedido o
acidente. O jeito mais limpo: um **comando-base** que *todos* os comandos que escrevem herdam,
fazendo isso automaticamente.

**(b) Migração linha-a-linha.** A matemática explica os "minutos": 1 SELECT + 1 UPDATE por
registro × 3.189 registros contra Oregon (~200 ms cada) ≈ **~20 min só de latência**. A
correção é dupla e ambas valem: (1) **`bulk_update`/`bulk_create(update_conflicts=True)`** —
carrega os registros uma vez, muda na memória, grava em lotes de ~500; isso transforma 20 min
em **segundos**; (2) **rodar no Render Shell**, na mesma região do banco (latência ~1 ms em vez
de ~200 ms pela rede privada). Você não precisa de `COPY` cru a 6.500 registros — o `bulk_*`
já resolve, e mantém suas validações (escada de confiança, `canonical_gen`) no passo de
preparação em memória.

**(c) Reverts poluindo o repo.** O `*_revert.json` na raiz é "reversibilidade feita à mão como
arquivo". A prática atual é **guardar histórico e reverts no banco**. Recomendo adotar
**`django-pghistory`**: ele registra as mudanças por **gatilho no Postgres**, então captura
**até as escritas em massa** (`bulk_update`) que as bibliotecas baseadas em *signals*
(`django-reversion`, `django-simple-history`) **perdem** — e isso importa porque seu pipeline
é todo de comandos que fazem escrita em massa. Toda a trilha fica no Postgres, nada no git, e
você ganha um histórico consultável de quem mudou o quê. (Correção barata e imediata enquanto
isso: se algum arquivo ainda precisar ser escrito, mande-o para uma pasta `var/reverts/` no
`.gitignore`, nunca para a raiz.)

**Sobre rodar no deploy do Render:** ponha **só o `migrate`** no `preDeployCommand` (roda uma
vez, numa instância separada, antes do deploy — perfeito para mudanças de schema). Os comandos
**destrutivos** (`populate --overwrite`, `import_*`, `fix_pns`) **não** vão no pre-deploy; eles
são *one-off Jobs* / Render Shell que você dispara. O fluxo-alvo fica: **você roda
`python manage.py deploy_catalog --commit` no Render Shell, lê o banner confirmando o banco
certo, acompanha um log em vez de treze** — e (graças ao Insight B) o cache se atualiza sozinho,
sem reinício manual.

---

### 4.4 — O estoque defasado: snapshot imutável + cálculo na leitura

**Em uma frase:** pare de usar **uma** coluna para responder **duas** perguntas diferentes —
congele o snapshot de entrada (o que decidimos no lançamento, imutável, para auditoria) e
calcule a classificação **atual** na leitura via `classify()`, recalculando só o que ficou
para trás usando o `catalog_version`.

Este é o ponto com trade-off genuíno, então vou ser claro. Você guarda hoje um **snapshot** da
classificação no `InventoryEntry`. Quando o engine melhora (o fix dos "dies" da Micron mudou
48GB→6GB), o snapshot não acompanha. As opções:

- **Só calcular na leitura** (sem snapshot): sempre fresco, zero dívida — mas **perde a
  memória** do que foi decidido na entrada. Para um negócio de reciclagem que pode precisar
  *defender uma decisão comercial passada*, isso sozinho não serve.
- **Só snapshot + refresh manual** (hoje): rápido de ler, mas defasa e vira dívida de
  reclassificação a cada melhoria.
- **O híbrido (recomendado):** as duas perguntas são legítimas e **diferentes** — *"o que
  decidimos na entrada?"* (fato histórico, imutável) e *"o que o chip é hoje?"* (derivado, tem
  que acompanhar a regra). Guarde **as duas**: congele o snapshot de entrada (com
  `intake_at` + `intake_catalog_version`) e **nunca o mude**; mostre a classificação **atual**
  recalculada na leitura, com atalho: se `intake_catalog_version == catalog_version`, nem
  recalcula. O recálculo acontece **uma vez por item por mudança de regra**, preguiçosamente —
  nunca a frota toda no deploy.
  > **Decisão do dono (2026-06-30):** o **frontend mostra a classificação ATUAL** (opção *b* — o
  > operador vê sempre o valor de hoje, ex.: 6GB). O snapshot de entrada e o **histórico de mudanças
  > ficam INTERNOS** (auditoria, via o snapshot imutável + o `django-pghistory` do passo 3) — **não**
  > há UI de "entrada × hoje" na tela do operador. Simplifica o frontend; o histórico fica consultável
  > por trás.

**Âncora de implementação — reuse o `_snapshot()`, não reinvente (heads-up do chat de estoque,
2026-06-30).** O `estoque/views.py::_snapshot(server_result)` já é, hoje, a **derivação por
tipo, autoritativa no servidor** que a leitura precisa produzir — e foi endurecido nesta data
(passou a gravar do `classify()` do servidor, **não** do `request.POST`, que fazia a capacidade
DDR virar a string `'None'`). O on-read **não cria lógica nova**: chama a **mesma** função —
`_snapshot(classify(pn))` — agora no momento da leitura. Isso aplica a sua *fonte única* ao
estoque: **uma derivação, dois pontos de chamada** (congela na entrada + recalcula na leitura).
Os invariantes que o `_snapshot` já codifica e que a leitura **tem de preservar/superar**:
(1) **autoridade server-side** — nunca o POST; (2) capacidade **por tipo** via `_size_for_entry`
— **densidade em Gbit (formato `2G`) para DDR/GDDR/SDRAM/RDRAM** × **capacidade em GB para
LPDDR/eMMC/UFS** × **`emcp_*` para eMCP/uMCP**; (3) **`Gb` ≠ `GB`** case-sensitive (o bug
clássico 8×); (4) `_clean_interface` (remove a geração espelhada, deixa só bus width/versão);
(5) `None` → `''`. Antes de implementar, **ler**: `estoque/views.py` (`_snapshot`/
`_size_for_entry`/`_clean_interface`), `BRIEFING §4.4` (nota "Aplicado nesta sessão") e
`CLAUDE.md §6` (bloco "O estoque é um SNAPSHOT").

**O backfill vira um comando de verdade (criado junto do on-read).** Hoje o re-snapshot de um
lote existente é feito **à mão no Render Shell**; o `refresh_lote` que existe **só** reescreve o
`classification_source` (a coluna *Source*) — de propósito **não** toca nas specs. Falta o
comando que re-roda o **`_snapshot` completo** (capacity/interface/emcp_*). Recomendo criá-lo
(ex.: `resnapshot_lote`) com três amarras à proposta: (a) **gated pelo `catalog_version`**
(Insight B) — só re-snapshota as entradas cujo `intake_catalog_version` ficou para trás, nunca a
frota inteira; (b) dry-run + `--commit` + `--revert`, com o **revert em `var/reverts/`**, não na
raiz do repo — aliás, o `refresh_lote` atual cospe `refresh_lote_NNN_revert.json` em `BASE_DIR`,
que é **exatamente** o Problema 4.3(c); corrija junto; (c) **`bulk_update`** no lugar do loop de
`.update()` (Problema 4.3b). É o irmão em-lote do on-read: a leitura faz `_snapshot(classify(pn))`
para 1 item; o comando faz o mesmo para o lote.

**O que NÃO fazer aqui:** não materializar o `classify()` em *view* SQL nem em `GeneratedField`
do Postgres. O engine lê um catálogo de **outra** tabela e roda Python arbitrário — colunas
geradas exigem função `IMMUTABLE` da mesma tabela, e uma *materialized view* obrigaria a
reescrever a gramática em SQL, criando uma **segunda fonte da verdade** que contraria suas
regras #11/#12. O backfill `resnapshot_lote` vira um **refresh em lote opcional** (agendado,
gated por `catalog_version`), não a ponte manual entre um bug corrigido e uma tela certa.

**As quatro condições de entrada do §4.4 (revisão do chat de estoque — pré-requisitos, não
detalhes para depois).** O chat que cuida do estoque verificou estes quatro pontos no código e
estão certos:

1. **On-read é FALLBACK; o lote é o caminho principal — senão a tela trava.** A lista do estoque
   renderiza um lote inteiro (centenas/milhares de linhas). Se o on-read recalcular o lote todo,
   síncrono, na primeira abertura após cada bump de versão, **o primeiro a abrir paga N `classify()`
   numa requisição** — uma página de vários segundos. **Inverter:** o **batch** (`resnapshot_lote`,
   disparado no bump ou agendado) é o principal; o **on-read** recalcula só as **linhas visíveis**
   (paginadas), nunca o lote inteiro síncrono.
2. **O carimbo cobre a rentabilidade** — tratado no Insight B (sobe também com `ProfitabilityConfig`).
   Sem isso, o eixo "rentável?" fica defasado em silêncio.
3. **Histórico interno vem do `django-pghistory` (passo 3) — sem "mostrar os dois".** Como o frontend
   mostra só o atual (decisão do dono acima), a UI não precisa reconstruir o destino da entrada. O
   **histórico de mudanças** do chip vem do pghistory na `InventoryEntry` (registra cada alteração dos
   campos salvos, automaticamente). *Opcional:* se quiser o **destino exato da entrada** no histórico
   (não só os campos crus), salve também `subtype`/`dram_density` na entrada — hoje o `_snapshot` não os
   guarda. Não é bloqueador.
4. **Backfill proativo das linhas existentes — não deixe o 1º leitor pagar.** As linhas atuais não
   têm `intake_catalog_version`. Marcá-las como "versão atual" → **nunca** recalculam (erradas, são
   de gramática velha); marcá-las como 0 → **todas** recalculam na 1ª leitura → o pico do furo #1
   cai sobre o estoque inteiro de uma vez. **Plano:** rodar `resnapshot_lote` **proativamente** nos
   lotes existentes (Render Shell, em lote, gated por versão), congelando o destino de cada um.

---

### 4.4-cache — Aposentar o `lru_cache` e a regra "reinicie após populate"

**Em uma frase:** dê uma "chave de edição" ao cache do engine — `lru_cache` keyed no
`catalog_version` — e o catálogo se recarrega sozinho em todos os workers, sem reinício.

A causa do problema é precisa: `_get_all_families()` é cacheado **sem argumento**, então a
chave nunca muda quando o banco muda; e cada worker do gunicorn é um **processo separado**, com
seu próprio cache — por isso o `clear_engine_cache()` de um comando não alcança o servidor. A
correção mantém a velocidade de hoje (objeto pesado na RAM do processo) e conserta a
invalidação:

```python
@lru_cache(maxsize=4)                 # guarda as últimas edições; as velhas saem sozinhas
def _load_catalog(version: int):
    return _build_catalog_from_db()   # SELECT das famílias + mapas

def get_catalog():
    return _load_catalog(CatalogVersion.current())   # 1 SELECT barato escolhe a edição
```

Depois de um `populate` que incrementa a edição, **cada worker, sozinho, sem reinício**: lê o
novo número → erra o cache → reconstrói do banco → cacheia sob a chave nova. Dispara o
incremento por `post_save`/`post_delete` em `ChipFamily`/`DecodeMap` (pega **também edições no
admin**) **e** explicitamente no fim de cada `populate_*`/`import_*`/`fix_*` (cinto e
suspensório, porque escrita em massa não emite *signal*). **Não precisa de Redis** — o único
dado compartilhado é um inteiro, e o Postgres serve isso em sub-milissegundo. Resultado:
**some a regra de ouro #3.**

---

### 4.5 — Normalização canônica de PN na escrita

**Em uma frase:** uma função `normalize_pn()` aplicada em **toda** escrita e **toda** busca,
materializada numa coluna `part_number_norm` com **restrição de unicidade** — assim a
duplicata vira impossível no banco, não "saltada em silêncio" no engine.

É o problema de **maior retorno por menor esforço** — bom primeiro passo. O desenho à prova de
falha tem camadas:

- **Uma função só**, usada idêntica na escrita, na query e na migração: `NFKC` (junta formas
  esquisitas tipo full-width), remove separadores (`-`, espaço), `.upper()`.
- **Onde aplicar:** um **campo de modelo customizado** (`PartNumberField` com `get_prep_value`)
  garante a canonização inclusive no `bulk_create`; mas a **garantia real** é uma **coluna
  normalizada `part_number_norm` + `UniqueConstraint(fields=["part_number_norm"])`**, porque
  só a restrição no banco sobrevive a `bulk_create`, `.update()`, admin e SQL cru. Manter o
  `part_number` cru para exibição **elimina o handler "preferir cru vs normalizado"** do engine.
- **Migração na ordem certa (importa):** primeiro adiciona a coluna (anulável), faz o
  *backfill* em massa, **resolve as colisões preservando a procedência** (sobrevive o de maior
  confiança — `confirmed` > `manual` > `distributor` > `estimated` —, reaponta as FKs do
  estoque/submissões para o sobrevivente, registra o merge numa tabela de auditoria, apaga o
  perdedor), e **só então** adiciona a restrição de unicidade. Nada de história perdida.

---

### 4.6 — Limpeza de resíduos

**Em uma frase:** baixo esforço, alto valor de confiabilidade — remova as menções a Gemini, ao
campo `status` e aos níveis `ai_*`, porque elas **induzem ao erro** quem (humano ou IA) for
fazer o onboarding.

Concretamente: a mensagem "o engine usa Gemini…" no `add_chip_families`; o `confidence='ai_high'`
residual; o conceito de `status` (raw/enriched) ainda citado em docs. Não trava a escala, mas a
base de onboarding tem que ser confiável — e, no novo modelo, o validador Pydantic pode
**rejeitar** `confidence` fora do vocabulário (`confirmed`/`manual`/`distributor`/`estimated`),
impedindo a volta dos resíduos.

---

### 4.7 — Compatibilidade com o próximo upgrade: preço por categoria (`PRECIFICACAO.md`)

**Em uma frase:** sim, o plano prevê isso — e mais: **o refactor é um *facilitador* do upgrade de
preço**, não só compatível. O seu `PRECIFICACAO.md` já está desenhado no mesmo espírito (fonte
única, escada, dado-não-código) e **depende exatamente das convenções canônicas que este refactor
solidifica**. A planilha que você mandou confirma: a chave é `(marca, tipo, subtipo, capacidade)` —
**não** por PN —, e a precificação roda **a jusante** da rentabilidade (a instrução é clara: "chip
sem lucro é sucata, não tem preço").

**Como o upgrade encaixa (mapa direto):**

| Peça do preço (`PRECIFICACAO.md` / planilha) | Onde o plano já a acomoda |
|---|---|
| Chave `PriceClass = (brand, chip_type, subtype, capacity_token)` | É a convenção **OPÇÃO 1 / `chip_types.py` / `canonical_gen`** — a fonte única de tipos que o refactor reforça. A chave de preço é um *join* nos campos que o engine já produz canonicamente. |
| A tabela de preços (marca × tipo × subtipo × capacidade → preço) | Modelos **`PriceClass`/`PriceQuote` no banco, editados no admin** (preço é operacional — ver abaixo). O **CSV + loader** serve só p/ o *bulk-import inicial* da sua planilha e atualizações em massa. |
| `resolve_price()` escada (exato → interpolado → sem-marca → ausente) | **Lógica no engine, dado na tabela** — exatamente "dado é dado, lógica é no engine". A jusante de `assess_profitability`, sem reimplementar rentabilidade (Regra #11). |
| Preço muda → estoque revalua | O **`catalog_version`** (já ampliado p/ `ProfitabilityConfig`) cobre também `PriceQuote`/`PriceConfig`: nova cotação → bump → on-read/`resnapshot` revalua só o afetado. |
| `quote_date` + frescor (cotação é série temporal datada) | É o mesmo trade-off **snapshot × on-read** do §4.4 aplicado ao preço: congela o preço-de-entrada (auditoria) + mostra a cotação atual com a data na leitura. |
| Cotações sujas na planilha ("20-23rmb", "90rmb-110rmb") | O **portão Pydantic/CSV** rejeita preço não-numérico e exige número + data limpos — a validação melhora a higiene do dado de preço de graça. |
| Chips sem preço | Mostram **"sem cotação"** (decisão do dono: **sem interpolação**). O comprador trabalha de **um painel só** com TODOS os tipos (a lista da planilha = `--price-skeleton`): vê o que tem e o que não tem preço de uma vez — **sem fila separada**. |

**Preço é dado OPERACIONAL, não conhecimento curado — vive no DB + admin, não em arquivo.** O seu
caso de preço deixa nítida uma distinção que o refactor já respeita:

- **Conhecimento curado** (gramática, correções de PN) → **arquivos versionados** (YAML/CSV) + loader.
  Muda devagar, precisa de revisão/histórico/procedência; autor = curador/IA.
- **Config operacional volátil** (`ProfitabilityConfig` e **os preços**) → **DB + Django admin**. Muda
  toda hora, efeito imediato, autor = operador/comprador não-técnico; **não** passa por git.

Os preços são o segundo caso — igual ao `ProfitabilityConfig` de hoje (singleton no admin). O
CSV/loader é só a ponte de *bulk-import* da planilha; a **fonte da verdade do preço é o banco**.

**Suas 4 considerações — todas suportadas:**

1. **"Preços flutuam muito, editável no admin."** ✅ `PriceQuote` é modelo Django → admin de graça. E
   como cada mudança é uma **cotação datada** (série temporal, `PRECIFICACAO §2`), "flutua muito" é
   tratado de origem: novo preço = nova cotação com data; histórico preservado; o card mostra data +
   cor de frescor. Salvar a cotação faz o `catalog_version` subir → o estoque revalua sozinho.
2. **"Comprador terá um admin interno para mudar preços."** ✅ Django admin tem **permissões por
   usuário/grupo** — o comprador ganha uma tela focada de "editar preços" (filtrada por marca/tipo),
   sem acesso ao resto. (Pode ser o admin nativo filtrado ou uma página HTMX simples sobre os mesmos
   modelos.)
3. **"Não temos preço para tudo; o comprador ainda está preenchendo."** ✅ **Decisão do dono:** chip sem
   preço mostra **"sem cotação"** (sem interpolação/chute). E o comprador trabalha de **um painel só, com
   TODOS os tipos possíveis** (a lista da planilha = o `--price-skeleton`), vendo de uma vez o que **tem**
   e o que **não tem** preço — **sem fila separada** (não há por que dividir). Uma `PriceClass` sem
   cotação é só uma linha em branco nesse painel; ele preenche in-place no admin.
4. **"Adicionar/remover tipos de chip e capacidades com facilidade."** ✅ É **o que o refactor compra**:
   o tipo vive na fonte única `chip_types.py` (novo tipo = 1 entrada) e a capacidade é só um
   `capacity_token` numa linha `PriceClass`. Adicionar = uma linha no admin (ou no CSV/skeleton);
   **remover = `active=False`** (soft-delete, igual à regra "nunca delete famílias"), preservando o
   histórico de cotações e de estoque. As categorias de preço são **desacopladas** do catálogo — dá
   para criar a categoria de uma capacidade nova antes mesmo de existir um chip dela.

**As 3 coisas a garantir (pequenas) para ficar fácil:**

1. **`catalog_version` sobe também com `PriceQuote`/`PriceConfig`** (um `post_save` a mais —
   extensão de uma linha do que já está no Insight B).
2. **Uma função canônica única `price_key(result)`** que monta o `capacity_token` no formato da
   planilha (eMCP `"16+1"` de NAND+RAM; DDR `"8Gb"` de die) — reusando os helpers de tipo/capacidade
   do `_snapshot`/`chip_types`, **não** o label da caixa (que colapsa o subtipo; o próprio
   `PRECIFICACAO §3` avisa: "o token da caixa ≠ a chave de preço").
3. **Decidir snapshot × on-read do preço** (o mesmo do §4.4): recomendo **congelar o preço-de-entrada
   para auditoria E mostrar a cotação atual on-read** com a data/frescor.

**Sinergia de bônus:** depois do refactor, a **lista de categorias de preço pode ser GERADA do
catálogo YAML** — um `load_brands --price-skeleton` que emite o CSV de preço vazio (todas as
combinações `(marca, tipo, subtipo, capacidade)` que precisam de cotação) para o comprador
preencher, **em sincronia** com o catálogo. A planilha de hoje foi montada à mão a partir dos
`populate_*` (diz a própria aba de instruções); no novo modelo, ela **nasce do mesmo dado**.

> **Conclusão:** faça o refactor **primeiro** (como você planeja) — ele torna a chave de preço
> confiável (convenções canônicas), entrega o loader+CSV que a tabela de preço usa, e estende o
> `catalog_version` para revaluar o estoque quando o preço muda. O upgrade de preço vira *adicionar
> uma tabela + uma função-escada a jusante da rentabilidade* — sem tocar no que já existe, e
> **mais fácil** por causa do refactor, não apesar dele.

---

## 5. Fase futura — pipeline de enriquecimento (multi-tenant descartado)

> **Multi-tenant: DESCARTADO pelo dono (2026-06-30).** A versão anterior previa uma "costura barata"
> para multi-tenant (FK `tenant` anulável, `get_profitability_config(tenant)`, `django-scopes`).
> **Removido a pedido** — o WTC fica single-tenant. Nada no resto do plano depende disso; o catálogo
> já é global por desenho, e a separação `chips/` (global) × `estoque/` (operacional) continua sendo
> uma boa organização independentemente de tenancy.

**Pipeline de enriquecimento.** Boa notícia: **o seu desenho já é a prática recomendada** —
registro canônico (`KnownPart`) + filas de triagem (`PendingEntry`/`ChipSubmission`) + escada
de confiança + logs de demanda (`SearchLog`/`UnknownChip`) é o padrão "propõe → curador
confirma → canônico" do Wikidata/OSM/MusicBrainz. Acréscimos baratos: (1) um `demand_score` no
`UnknownChip` ranqueado por **velocidade de busca recente × impacto** (reusando o
`assess_profitability` para priorizar chips *rentáveis* desconhecidos); (2) exigir uma
**nota/fonte curta** em todo confirmar/rejeitar (alimenta a auditoria); (3) se um dia voltar a
**IA**, só como **propositora para a fila** — nunca autoritativa: proposta por-campo com fonte
citada, **a gramática como verificador determinístico** (se a capacidade proposta diverge do
decode, vai para revisão humana), e o operador-especialista como dono único do "confirmed".
Isso **valida** a sua decisão de ter removido o Gemini, não a contradiz.

---

## 6. O que NÃO mexer (os acertos a preservar)

- **`chip_types.py`, `canonical_gen`, `assess_profitability`** — as três fontes únicas; são o
  modelo a *estender*, e a prova de que o princípio funciona.
- **A gramática (`ChipFamily` + `DecodeMap`)** como camada de generalização — muda *de onde* ela
  é alimentada (arquivo, não código), não *o que* ela é. **O engine `classify()` não muda.**
- **A escada de confiança** e **a hierarquia de fontes** — o modelo de autoridade é sólido;
  só passa a ser *campo consultável* em vez de comentário.
- **O padrão dry-run + revert** e a separação `chips/` × `estoque/` — corretos; a proposta os
  *unifica e organiza*, não os abandona.

---

## 7. Sequência de ataque recomendada

> **Os dois chats revisores convergiram num enquadramento útil: são DUAS frentes de risco muito
> diferente.** O **encanamento barato** conserta dor que você já sentiu na pele (o cache velho que
> mostrou `[DDR]`, o acidente localhost×produção, o `normalize` de 20 min, as duplicatas MT29C) —
> risco quase zero, **faça já**. A **migração do conhecimento** é uma aposta de *escala* — **faça
> por último**, devagar, **direto ao YAML** (1 marca por vez), e só ela exige cuidado especial.

Ordenada por **risco crescente**, cada passo provado pela **rede de regressão** (caracterizar
`classify()` para 100% dos registros antes/depois):

1. **Encanamento barato (risco quase zero, comportamento inalterado) — FAÇA JÁ:** (4.5)
   `normalize_pn()` + `UniqueConstraint`; (4.4-cache) `catalog_version` + `lru_cache(version)`
   (subindo **também** com `ProfitabilityConfig` — Insight B); (4.3) trava de banco (`env.db()` sem
   default + banner) + `bulk_update`; (4.6) limpeza dos resíduos. Conserta dor já sentida.
2. **Frescor do estoque (4.4)** com as **quatro condições de entrada** do chat de estoque
   (lote-primeiro + on-read só do visível; carimbo cobrindo rentabilidade; congelar o destino de
   entrada; backfill proativo). Depende do `catalog_version` do passo 1.
3. **Operacional (4.3):** o **`deploy_catalog` num comando** (Render Shell, `django-pghistory`).
4. **A migração do conhecimento — a aposta de escala, POR ÚLTIMO (encerra o refactor), direto ao YAML:** o conhecimento
   vira **`marca.yaml` (gramática) + `marca.csv` (correções)** validados por **Pydantic** + **um
   carregador genérico `load_brands`**; **uma marca por vez**, regressão garantindo saída idêntica,
   e **aposenta `populate_*` + `add_chip_families`** (mata a duplicação). Vai direto ao destino
   (sem degrau de Python) porque a migração é feita pela IA e um waypoint seria passe duplo. ⚠
   **Cuidado especial (caveat do chat de arquitetura):** a regressão cobre os **registros
   existentes**, mas a gramática existe para **generalizar à cauda longa que NÃO está no banco** —
   e *essa* parte a regressão não testa. Um decode errado no dado quebra a família inteira.
   **Mitigação:** uma marca por vez **+ amostragem manual de PNs inéditos** por família, além do
   replay dos existentes.
5. **Sistema de precificação — LOGO APÓS o refactor (`PRECIFICACAO.md` + §4.7):** modelos
   `PriceClass`/`PriceQuote`/`PriceConfig`; `resolve_price()` a jusante de `assess_profitability`
   (não reimplementa rentabilidade — Regra #11); **preços editáveis no admin** pelo comprador (não em
   arquivo); `catalog_version` cobrindo o preço; bulk-import da planilha via CSV; fila "sem cotação".
   Os passos 1–4 são **pré-requisito**: tornam a chave `(marca, tipo, subtipo, capacidade)` confiável
   — por isso o refactor "considera fortemente" o preço (catalog_version já ampliado, convenção única,
   loader+CSV, `--price-skeleton` gerado do catálogo).
6. **Outra conversa, depois:** os acréscimos do **pipeline de enriquecimento** (§5) — construção
   quando houver volume. *(Multi-tenant foi descartado — ver §5.)*

---

## 8. Resumo das ferramentas recomendadas (e por quê)

| Decisão | Ferramenta / mecanismo | Por que esta |
|---|---|---|
| Validar o arquivo de marca | **Pydantic v2** | Melhores mensagens de erro p/ não-dev/IA; suas regras de ouro viram validadores |
| Formato da gramática | **YAML + Pydantic** (+ `$ref` p/ mapas compartilhados) | Dado fora do código; comentário (procedência) + aninhamento; validação na entrada; IA escreve direto |
| Formato das correções | **CSV** | Dado plano; você já tem ferramentas de CSV; mata o arquivo de 607 KB |
| Carregar p/ o banco | **1 comando `load_brands`** (estilo `sync_rules`) | Fonte única; recusa duplicata; engine intacto |
| Escrita em massa | **`bulk_update` / `bulk_create(update_conflicts=True)`** | 20 min → segundos; idempotente |
| Auditoria / reverts | **`django-pghistory`** | Por gatilho no Postgres: pega escrita em massa; nada no git |
| Cache do catálogo | **`lru_cache(version)` + `CatalogVersion`** | Auto-invalida em todos os workers; sem Redis; sem reinício |
| Unicidade de PN | **coluna `part_number_norm` + `UniqueConstraint`** | Única garantia que sobrevive a bulk/admin/SQL cru |
| Segurança do deploy | **`env.db()` sem default + banner + confirmação** | Impede o acidente localhost × produção |

---

## 9. Princípios preservados (inegociáveis)

- **O agente edita arquivos; você roda os comandos.** Tudo acima respeita isto: o curador/agente
  edita `marca.yaml`; você roda `load_brands --dry-run` (valida e mostra o diff) e depois
  `--commit`.
- **Rede de regressão** prova cada refactor pesado (comportamento idêntico antes/depois).
- **Fonte única > código espalhado** — o princípio-guia; a proposta inteira é estendê-lo.
- **Dado é dado; lógica é no engine.** Nada de `if`/loop/expressão no `marca.yaml`. Conhecimento
  (fatos, mapeamentos) sai para o dado; lógica de decode/rentabilidade fica no `engine.py`. É o
  que impede o "dado declarativo" de degenerar numa linguagem ruim dentro do YAML.
- **É evolução, não reescrita** — o engine `classify()` e o desenho de duas camadas ficam.
- **O código é a fonte da verdade** em qualquer conflito de documentação.

---

## 10. Fontes (pesquisa de mercado, 2025–2026)

**Dado declarativo / validação / catálogo**
- GitOps — Git como fonte única: https://www.xopsschool.com/tutorials/git-as-single-source-of-truth/
- django-rules — padrão `rules.py` + `sync_rules`: https://github.com/dfunckt/django-rules
- dbt seeds — dado de referência versionado: https://docs.getdbt.com/docs/build/seeds
- Pydantic v2 — erros de validação: https://docs.pydantic.dev/latest/errors/errors/
- Validar YAML com Pydantic: https://www.sarahglasmacher.com/how-to-validate-config-yaml-pydantic/
- JSON × YAML × TOML (comentários, autoria humana): https://dev.to/jsontoall_tools/json-vs-yaml-vs-toml-which-configuration-format-should-you-use-in-2026-1hlb
- Normalizado × desnormalizado (regra das tabelas de lookup): https://www.couchbase.com/blog/normalization-vs-denormalization-comparison/
- Part-DB — abstração de provedor de informação: https://docs.part-db.de/usage/information_provider_system.html
- Octopart/Nexar API (família → atributos → documentos): https://octopart.com/api/v4/reference
- Linhagem/proveniência de dados consultável: https://atlan.com/data-lineage-explained/

**Migração de dados / deploy / Postgres**
- Django 5.2 — operações de migração (`RunPython`, `reverse_code`, `elidable`): https://docs.djangoproject.com/en/5.2/ref/migration-operations/
- Django 5.2 — escrevendo migrações (reversível, não-atômica/lotes): https://docs.djangoproject.com/en/5.2/howto/writing-migrations/
- Django 5.2 — QuerySet (`bulk_update`, `bulk_create`): https://docs.djangoproject.com/en/5.2/ref/models/querysets/
- Haki Benita — carga rápida no Postgres (benchmark): https://hakibenita.com/fast-load-data-python-postgresql
- Render — deploys (pre-deploy command, timeouts): https://render.com/docs/deploys
- Render — one-off jobs / SSH & Shell (mesma região): https://render.com/docs/one-off-jobs · https://render.com/docs/ssh
- Adam Johnson — dry-run via rollback: https://adamj.eu/tech/2022/10/13/dry-run-mode-for-data-imports-in-django/
- CommCareHQ — migração na prática (comando × migração): https://commcare-hq.readthedocs.io/migrations_in_practice.html
- django-environ — falhar se faltar `DATABASE_URL`: https://django-environ.readthedocs.io/en/latest/quickstart.html
- Krzysztof Żuraw — gunicorn + lru_cache (cache por-processo): https://krzysztofzuraw.com/blog/2017/gunicorn-and-lru-cache-pitfall/

**Frescor / normalização / cache**
- Django 5.2 — `UniqueConstraint` / campos customizados / cache: https://docs.djangoproject.com/en/5.2/ref/models/constraints/ · https://docs.djangoproject.com/en/5.2/howto/custom-model-fields/ · https://docs.djangoproject.com/en/5.2/topics/cache/
- Postgres — colunas geradas (exigência IMMUTABLE): https://www.postgresql.org/docs/current/ddl-generated-columns.html
- DHH/37signals — expiração de cache por chave (geracional): https://signalvnoise.com/posts/3113-how-key-based-cache-expiration-works
- Paolo Melchiorre (Django core) — colunas geradas no Postgres: https://www.paulox.net/2023/11/24/database-generated-columns-part-2-django-and-postgresql/

**Auditoria / curadoria colaborativa**
- django-pghistory (gatilho no Postgres, pega escrita em massa): https://github.com/AmbitionEng/django-pghistory
- Wikidata — ranking de confiança + referências: https://www.wikidata.org/wiki/Help:Ranking
- MusicBrainz — votação/auto-editor: https://musicbrainz.org/doc/Introduction_to_Voting
- django-fsm-2 (sucessor mantido do django-fsm): https://github.com/django-commons/django-fsm-2
- Anthropic — reduzir alucinações (citar-ou-abster): https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations

---

## 11. O que mudou nesta revisão (changelog)

Para você reler rápido — o que esta sessão de teste de estresse aprendeu e mudou:

1. **Direção confirmada pelo mercado.** A pesquisa do que as gigantes usam hoje (Salesforce,
   Kubernetes, OPA/CNCF, dbt) + o cânone (Out of the Tar Pit, Raymond, Zen do Python) atestou que
   "dado declarativo + engine genérico + validação" é **o padrão mais provado** para este problema
   — e o mais Pythônico. Detalhe e fontes em `docs/ANALISE_IMPLICACOES_ESCALABILIDADE.md`.
2. **Decisão FINAL do formato: YAML direto (fecha a oscilação).** Eu balancei (YAML → Python →
   YAML → Python) porque as duas opções são genuinamente próximas. O fator **decisivo** (seu
   argumento): **(a) a migração é feita por uma IA**, para quem YAML+Pydantic é tão fácil quanto
   dataclasses — a vantagem do degrau Python era ergonomia *humana* (mypy/IDE), fraca aqui;
   **(b) "Python agora, YAML depois" é migração dupla** (dois passes, duas regressões). Ir direto
   ao YAML resolve de uma vez. **FINAL: gramática em YAML+Pydantic, correções em CSV, sem waypoint
   de Python.** Supersede o "Python primeiro" do `ANALISE` (alinhei os dois). Trilhos de segurança
   intactos: 1 marca/vez + amostragem de PNs inéditos + portão Pydantic. (§4.1/4.2, §7, §8.)
3. **Nova regra de ouro:** *dado é dado, lógica é no engine* — nada de `if`/loop no dado; é o que
   mantém a coisa simples por décadas e evita virar "uma linguagem ruim dentro do YAML". (§1, §9.)
4. **Estoque on-read ancorado no `_snapshot`** (heads-up do chat de estoque, 2026-06-30): a leitura
   reusa `_snapshot(classify(pn))` — não reinventa a derivação por tipo; e falta criar o comando
   `resnapshot_lote` (o `refresh_lote` atual só reescreve a coluna *Source*). (§4.4.)
5. **Quatro condições de entrada do §4.4 (revisão do chat de estoque) — viraram pré-requisito:**
   on-read em **lote-primeiro** (só recalcula o visível, nunca o lote inteiro síncrono); congelar o
   **destino da entrada** (o `_snapshot` não guarda `subtype`/`dram_density`); **backfill proativo**
   das linhas antigas. (§4.4.)
6. **O carimbo `catalog_version` passou a cobrir a RENTABILIDADE** (furo do chat de estoque): sobe
   também quando muda `ProfitabilityConfig`, senão o eixo "rentável?" defasa em silêncio. (Insight B.)
7. **Risco concentrado da migração (caveat do chat de arquitetura):** a regressão cobre os registros
   **existentes**, não a cauda longa que a gramática generaliza. Mitigação: uma marca por vez +
   **amostragem manual de PNs inéditos**. E a sequência virou **duas frentes**: encanamento já,
   migração do conhecimento por último. (§7.)
8. **As 7 dimensões** das suas perguntas + o veredito "simplifica ou complica" estão no
   documento-companheiro `ANALISE_IMPLICACOES_ESCALABILIDADE.md`.
9. **Sistema de precificação integrado (§4.7 + passo 5).** A planilha que você mandou (preço por
   **categoria** — marca×tipo×subtipo×capacidade, **não** por PN) encaixa direto: preço é **dado
   operacional** (DB + admin, igual ao `ProfitabilityConfig`), **não** arquivo; o `catalog_version`
   passou a cobrir `PriceQuote`/`PriceConfig`; e add/remove de tipos e capacidades fica fácil (fonte
   única `chip_types.py` + `active=False`). A precificação virou **passo 5** explícito da sequência,
   logo após o refactor, que é seu **facilitador** (chave canônica confiável + loader/CSV).

> Próximo passo combinado: você relê; concordando, montamos o **plano de implementação** começando
> pelo **encanamento barato** da Seção 7 (passo 1 — risco quase zero, conserta dor já sentida). A
> migração do conhecimento (passo 4) fica por último e devagar, **direto ao YAML** (1 marca por vez).

---

## 12. Decisões — fechadas e em aberto

**✅ Fechadas (2026-06-30):**

- **Multi-tenant: DESCARTADO.** WTC fica single-tenant (§5).
- **`django-pghistory`: ADOTAR, escopado ao catálogo.** Em linguagem simples: é uma biblioteca que
  registra automaticamente *quem mudou o quê e quando* nas tabelas escolhidas, guardando o histórico
  **dentro do Postgres** (via gatilhos). Como usa gatilhos, pega **até as escritas em massa** dos seus
  comandos (que as outras ferramentas perdem) e substitui os `*_revert.json` na raiz do repo. **Escala
  bem aqui:** o histórico cresce com as *mudanças* (o catálogo muda pouco), fica só no banco (sem infra
  nova), e o aplicamos **escopado às tabelas do catálogo** (`ChipFamily`/`DecodeMap`/`KnownPart`/
  `ProfitabilityConfig`). Entra junto do `deploy_catalog` (passo 3). *(O preço não precisa dele: o
  `PriceQuote` datado já É o histórico.)*
- **Prova de conceito da migração (passo 4): PieceMakers.** Ótima escolha — o baseline mostra só **3
  registros** PieceMakers, todos limpos. Prova o loader sem risco; a Samsung (a grande, dona dos
  `shared_maps`) vem depois.
- **Pré-requisito da rede de regressão: CONFIRMADO.** O `prod_data.json` (7021 PNs, 14 marcas), o método
  (SQLite descartável + pipeline real `classify()`, read-only) e o baseline (`docs/CARACTERIZACAO_BASELINE.md`
  + `caracterizacao_baseline.xlsx`) **existem**. **Passo 0 do plano:** transformar o harness ad-hoc num
  **comando reutilizável** (ex.: `characterize_baseline`) — é a rede de segurança de todo passo que toca o
  engine.

**✅ Fechadas (2026-06-30, segunda rodada):**

- **Estoque (passo 2) — exibição:** o **frontend mostra só o valor ATUAL** (opção *b*); o histórico de
  mudanças do chip fica **interno** (snapshot de entrada imutável + `django-pghistory`). **Sem** UI de
  "entrada × hoje".
- **Precificação (passo 5) — sem preço → "sem cotação"** (sem interpolação/chute). **Sem fila separada:**
  o comprador tem **um painel com TODOS os tipos** (a lista da planilha = `--price-skeleton`), preço e
  sem-preço juntos, preenchendo in-place no admin.

**🟢 Nada mais em aberto** — pronto para montar o plano de implementação.

---

> **Resumo de uma linha:** *o WTC não precisa de reescrita — precisa que o conhecimento que já
> é dado saia do código para arquivos validados (YAML/CSV), com um "número de edição" consultado
> na leitura. Duas peças pequenas, na ordem da Seção 7, e os seis problemas caem juntos, sem
> tocar no engine. Regra única que mantém tudo simples: dado é dado, lógica é no engine.*
