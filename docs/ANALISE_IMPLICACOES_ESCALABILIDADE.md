# Análise de implicações + validação de mercado da proposta de escalabilidade

> **O que é este documento.** É o *teste de estresse* da `docs/PROPOSTA_ESCALABILIDADE.md`,
> pedido pelo dono: as implicações em 7 dimensões, o processo prático do dia a dia (que é
> "extremamente mutável"), e a pergunta-chave — **simplifica ou complica?** — confrontada com a
> filosofia "menos é mais / Python". Inclui pesquisa do que **as gigantes usam hoje** (2025–26)
> para problemas deste tipo, com as fontes.
>
> **A honestidade primeiro:** você pediu para eu *realmente atestar*. A pesquisa **mudou parte
> da minha recomendação** — para melhor e para **mais simples**. A *direção* da proposta está
> certa e é das mais provadas da indústria; mas o **primeiro passo** que eu tinha escrito
> (YAML + Pydantic + loader) é mais máquina do que um time do seu tamanho precisa **agora**. O
> passo inicial mais "menos é mais" é outro, e está abaixo.

> ## ⛔ ATUALIZAÇÃO — a conclusão de FORMATO deste documento foi SUPERSEDIDA (2026-06-30)
> Este documento conclui "**dado em Python primeiro, YAML depois**" (o "degrau 1" abaixo). Essa
> conclusão **foi revista** na `PROPOSTA_ESCALABILIDADE.md` (§4.1/4.2): a decisão FINAL é **YAML
> direto, sem degrau de Python**. Motivo decisivo: a migração é feita por uma **IA** (para quem
> YAML+Pydantic custa o mesmo que dataclasses — a vantagem do Python era ergonomia *humana*), e
> "Python agora, YAML depois" seria uma **migração dupla**. As duas opções eram genuinamente
> próximas — por isso a oscilação — e a discussão da "escada" abaixo continua útil para entender
> *por quê* eram próximas. **Tudo o mais deste documento permanece válido:** as 7 dimensões, a
> validação de mercado, a regra "dado é dado, lógica é no engine", e o veredito "simplifica".
> **Onde ler 'degrau 1 = Python' abaixo, leia 'vamos direto ao YAML, com os mesmos trilhos de
> segurança'.**

---

## 1. O veredito em uma frase (honesto)

> **A direção — "dado declarativo + um engine genérico + um portão de validação" — é uma das
> arquiteturas mais validadas que existem (Salesforce há 25 anos, Kubernetes inteiro, o livro de
> SRE do Google, e todo o cânone de ciência da computação). Ela SIMPLIFICA e envelhece bem, com
> UMA condição inviolável: o dado nunca pode virar lógica. Para um time pequeno, porém, o passo
> certo AGORA não é construir o pipeline de YAML — é a versão mais enxuta dele: o conhecimento
> vira DADO em Python (e CSV para as correções), com um único carregador genérico. Isso já mata
> o bug de duplicação, já tira o arquivo de 607 KB, mantém suas ferramentas (testes, IDE) e
> custa quase nada. O YAML completo vem depois, só quando a dor for real (curador/IA editando
> sem programador).**

Isso é *mais* "menos é mais" do que a primeira proposta — e o mercado concorda (Seção 3).

---

## 2. O que as gigantes usam hoje (2025–2026) — a pesquisa

A pergunta "isso é exótico ou é o padrão da indústria?" tem resposta inequívoca: **é o padrão.**
O formato é sempre o mesmo — *dado declarativo + engine genérico + validação na entrada* — e
aparece em todo sistema que precisa mudar conhecimento sem reescrever o motor:

| Quem | O que faz | Escala / idade |
|---|---|---|
| **Salesforce** | Um *engine* lê **metadados** (o cliente declara objetos/campos/regras como DADO; nada de código gerado). "O sistema materializa componentes virtuais em runtime a partir de metadados." | **~25 anos no mesmo modelo**, centenas de milhares de empresas |
| **Google (livro de SRE)** | Posição oficial: *"ter código E dado, mas separados, é o ideal. A infraestrutura opera sobre dado estático (Protobuf, YAML, JSON)."* E exige: **validação semântica no momento do commit** | Borg/Kubernetes |
| **Kubernetes** | "Configuration as Data": todo recurso é YAML/JSON validado por **schema** + *admission policies*; um *control loop* genérico reconcilia | Escala planetária |
| **Open Policy Agent (Rego)** | "Desacopla a decisão de política do código": regras como dado, versionadas | **Graduado na CNCF**; Netflix, Pinterest (8,5M QPS), Goldman Sachs |
| **Sigma / Semgrep / Falco** | Catálogos de **regras como YAML** em git, validadas por schema, revisadas por PR — *idêntico ao "conhecimento como arquivo revisável"* | 15.000+ / 20.000+ regras; Falco graduado CNCF, ~1M nós |
| **dbt** | Conhecimento de domínio como **arquivos declarativos versionados em git**, com testes de schema e **contratos** que falham o build se o tipo não bate | ~30.000 empresas/semana |
| **Pydantic** | O "portão" em Python: valida dado na fronteira ("parse, don't validate") | 10B+ downloads; OpenAI, AWS, NASA |

E o **cânone** de engenharia diz a mesma coisa há 40 anos:

- **"Out of the Tar Pit"** (2006): a maior fonte de complexidade acidental é *estado + fluxo de
  controle*; a cura é **preferir dado declarativo** (estado como relações = tabelas; lógica como
  funções puras). É **exatamente** o seu desenho (`KnownPart`/`DecodeMap` como dado; `classify`
  como engine).
- **Eric Raymond** (*Art of Unix Programming*): *"Dobre conhecimento em dados, para a lógica do
  programa poder ser burra e robusta… na escolha entre complexidade nos dados e no código,
  escolha os dados."* E: *"Separe política de mecanismo — eles mudam em ritmos diferentes, a
  política muito mais rápido."* O seu sistema é o exemplo perfeito: **specs de chip (política)
  mudam toda hora; o engine (mecanismo) é estável.** Raymond diz que separá-los dá *"complexidade
  global muito menor e custo de ciclo de vida menor"* — o seu argumento de "manutenível por
  décadas", dito pelo cânone.
- **Zen do Python (PEP 20):** "Simples é melhor que complexo"; "deve haver uma maneira óbvia de
  fazer". Trocar `if/elif` gigante por **dado/dicionário** é um refactor Pythônico clássico.

**Conclusão da pesquisa:** a direção não é só defensável — é a coisa mais provada que existe
para este tipo de problema, e é *mais* Pythônica que o estado atual (cravar 200 marcas em 200
arquivos `.py` é a opção *menos* Pythônica).

### 2.1 Mas — o contra-argumento honesto (o que as gigantes diriam a um time pequeno)

A mesma pesquisa trouxe o aviso, e ele é sério:

- **O "relógio da complexidade de configuração"** (Mike Hadlow): a config migra de *hardcoded →
  arquivo → engine de regras → DSL* e **volta ao hardcoded, só que numa linguagem pior**. O
  recado que mira direto na sua esperança de "o dono edita": *"a ideia de que usuários de negócio
  editariam as regras pela interface se mostrou falsa — mapear regra para o engine exige uma
  perícia que só parte do time tem."*
- **Inner-platform effect** (Daily WTF): customizar tanto que você constrói "uma réplica ruim da
  plataforma que já tinha".
- **YAGNI** (Fowler) e **"A Abstração Errada"** (Sandi Metz): *"duplicação é mais barata que a
  abstração errada"*. Não construa o ponto de extensão para uma escala **imaginada**.
- **O meio-termo barato:** mover o conhecimento para **dado em Python** (dataclasses/dicts num
  módulo dedicado — estendendo o seu `chip_types.py`) entrega ~90% do benefício (dado separado da
  lógica, um lugar para editar, diff no git) por ~10% do custo: **sem formato novo, sem loader
  novo, mantendo mypy, debugger, IDE e os seus testes de regressão de graça.**

**É por isso que eu revisei a recomendação.** O destino (externalizar para dado declarativo) está
certo; mas a **forma e o momento** do primeiro passo importam para um time do seu tamanho. A
disciplina: subir a escada **um degrau de cada vez**, e **parar** antes de qualquer DSL.

### 2.2 A escada (e onde parar)

```
Degrau 0  Hardcoded espalhado em 10 arquivos .py     ← VOCÊ ESTÁ AQUI (607 KB, duplicação)
Degrau 1  DADO em Python (dataclasses/dicts) +        ← VÁ PARA CÁ AGORA  (menos é mais)
          UM loader genérico  +  CSV p/ as correções     mata duplicação, tira o 607 KB,
                                                          mantém testes/IDE, custo ~mínimo
Degrau 2  Arquivos YAML/CSV + validação Pydantic       ← QUANDO a dor for real
          (curador/IA edita sem tocar em código)          (dono edita semanalmente, ou
                                                           contribuidor não-dev de verdade)
Degrau 3  Uma DSL / linguagem de regras própria        ← NUNCA (é o relógio de Hadlow)
```

**O degrau 1 já resolve os bugs concretos de hoje** (duplicação `add_chip_families`, arquivo
gigante, ilegibilidade) — que são dor **real, presente**, não imaginada. O degrau 2 resolve uma
dor **futura** (autoria por não-dev/IA) — então espera ela aparecer. E o trabalho do degrau 1
**não é jogado fora**: as dataclasses do degrau 1 *são* o rascunho do schema Pydantic do degrau 2;
converter Python→YAML depois é mecânico.

---

## 3. Implicações nas 7 dimensões (com a recomendação refinada)

> Recomendação refinada = **degrau 1** agora (dado em Python + loader genérico + CSV p/ correções)
> + as peças independentes (`normalize_pn`, `catalog_version`, segurança de deploy, on-read). O
> degrau 2 (YAML) fica adiado.

### 3.1 Segurança da informação — **melhora**
- **Dado em Python / CSV** tem a mesma proteção de hoje (está no repo, controlado por git). Não
  cria superfície de ataque nova. E **CSV é dado, não executa** — risco menor que um `.py` de
  marca, que *pode* rodar código arbitrário. No degrau 2, `yaml.safe_load` + Pydantic é uma
  *fronteira de segurança* — 200 marcas como **dado** é menos arriscado que 200 marcas como
  **código executável**.
- `normalize_pn` + restrição de unicidade **elimina uma classe de bug de integridade** (duplicatas
  que falseiam contagem/lookup) → dado mais confiável.
- `catalog_version` (e, se adotado, `django-pghistory`) dá **trilha de auditoria** de quem mudou o
  quê — ganho de segurança/conformidade.
- Segredos: **inalterado** (`.env` gitignored — já está certo).
- *Veredito:* igual-ou-mais-seguro em cada degrau; os degraus externalizados são **mais** seguros.

### 3.2 Facilidade de edição e versionamento — **melhora muito (já no degrau 1)**
- A maior vitória chega **já no degrau 1**: **um único lugar de definição por família** (mata o
  bug de duplicação), `git diff` por marca, fim do monólito de 607 KB.
- O degrau 2 acrescenta: edição por não-dev, sem risco de quebrar sintaxe, validada por schema.
- Versionamento: histórico do git por arquivo + `catalog_version` em runtime.
- **Caveat honesto:** editar uma *gramática posicional* é difícil para um não-técnico em
  **qualquer** formato (o aviso de Hadlow). Então o ganho de "o dono edita" vale mais para a
  **CSV de correções** (onde você realmente poderia contribuir) e para um futuro curador/IA — não
  finja que YAML de decode vira algo que um leigo edita com conforto.

### 3.3 Riscos de implementação no sistema atual — **baixo e controlado**
- **Degrau 1 é um refactor mecânico** (tirar os dicts de dentro das chamadas ORM imperativas e
  pô-los como dado + um loader), **provado pela rede de regressão** (caracterizar `classify()` em
  100% dos registros, antes/depois). **O engine não muda** — o código mais testado e de maior
  valor fica intacto. Risco *menor* que o do degrau 2 (sem framework novo).
- O ponto de maior risco é a **migração de dedup de PN** (mexe em dado) — mitigada por dry-run +
  reversível + preservação de procedência. Tudo o mais é aditivo.
- Estratégia: **uma marca por vez**, regressão garantindo saída idêntica.
- *Veredito:* risco médio-baixo, bem cercado, porque é **evolução, não reescrita**.

### 3.4 Curva de aprendizado para um programador iniciante — **diminui**
- **Degrau 1:** um iniciante lê `FAMILIES = [ {...}, {...} ]` + um loader de ~80 linhas. Muito mais
  fácil que 10 scripts imperativos de 148 KB com a pegadinha da duplicação. Mantém IDE, mypy,
  debugger.
- **CSV:** trivial.
- **Degrau 2 (Pydantic):** "são só *type hints* do Python" — padrão, pesquisável no Google,
  entediante (no bom sentido). Um conceito novo, bem delimitado.
- *Veredito:* abaixa a barra para a tarefa comum (editar conhecimento) em **todos** os degraus; a
  tarefa rara (mexer no loader/engine) usa conceitos **padrão**, não conhecimento tribal.

### 3.5 Infraestrutura do Render — **igual, usada melhor (sem custo novo)**
- **Nenhuma infra nova** nos degraus próximos. `catalog_version` é **um inteiro no Postgres** (sem
  Redis). Continua no plano **Hobby** de hoje.
- Uso melhor: `preDeployCommand` só para `migrate`; **Render Shell** para os loads (mesma região
  do banco → rápido).
- *Honesto:* `django-pghistory` (se adotado) são gatilhos no Postgres (sem infra), mas adicionam
  volume de escrita no banco → **adie** até a auditoria ser necessidade real.

### 3.6 Funcionamento do estoque — **mais correto, sem perder o histórico**
- *Independente* da questão Python×YAML. O gateway (`_compute_destination`) **não muda**; o
  estoque ganha **snapshot imutável de entrada + cálculo on-read** (reusando `_snapshot`), com
  `resnapshot_lote` em lote, *gated* por `catalog_version`. Acaba o "48 GB defasado" e preserva o
  registro de entrada para auditoria. (Detalhe no §4.4 da proposta.)

### 3.7 Identificação de chips em tempo real — **igual ou melhor**
- O `classify()` **não muda** em nenhum degrau — mesma velocidade, mesma lógica, lê as mesmas
  tabelas. `catalog_version` + cache por versão = mesma velocidade na RAM **+ resultado sempre
  fresco + sem reinício manual**. O caminho de tempo real lê do cache → latência inalterada.
- *Veredito:* desempenho igual ou melhor; resultados mais frescos (some o risco de servir
  gramática velha após um `populate`).

---

## 4. O processo prático no dia a dia (a parte "extremamente mutável")

O coração da sua pergunta: como fica **adicionar/corrigir** conhecimento — que muda o tempo todo?
Comparado lado a lado (hoje × refinado). Note que em todos os casos o ciclo vira **editar uma
entrada de dado → rodar um comando**, com diff estruturado e validação.

### 4.1 Adicionar um PN confirmado novo
- **Hoje:** achar o arquivo certo entre ~10; editar um `dict` no `fix_known_parts.py` (607 KB) ou
  num `populate`; `commit`; `deploy`; **reiniciar**; rodar `fix_pns` para o estoque pegar. **Só um
  dev.**
- **Refinado (CSV):** acrescentar **1 linha** em `samsung_corrections.csv`
  (`part_number, chip_type, capacity, …, source_url, source_tier, reason`) → `load_corrections
  --dry-run` (valida + mostra o diff) → `--commit` → `catalog_version` sobe → o estoque recalcula
  **só os afetados** on-read. Um **curador** (ou IA propõe / humano aprova) faz. **Sem código, sem
  reinício.**

### 4.2 Adicionar uma família nova
- **Hoje:** editar `populate_marca.py`, **risco de colidir** com `add_chip_families`; `commit`;
  `deploy`; **reiniciar**.
- **Refinado (dado em Python):** acrescentar **1 bloco** em `FAMILIES` de `knowledge/samsung.py`
  (com o `cap_map` **inline**) → o loader genérico **valida** (pega `density_type`×`cap_map`
  juntos, a regra das famílias KM, a ordem `val_primary`/`secondary`) → `commit` → `load` →
  `catalog_version` sobe. **Um único lugar de definição → colisão impossível.** (Degrau 2: igual,
  só que em YAML, sem `.py`.)

### 4.3 Adicionar um decode novo a uma família
- **Refinado:** acrescentar linhas no `cap_map`/`gen_map` **inline** da família — ou em
  `shared_maps` se for um dos ~22 reusados. A validação confere a convenção da tabela. Um decode
  que conserta uma família **conserta todos os chips dela** (o valor da gramática, preservado).

### 4.4 Corrigir um PN / decode / regra (o caso mais frequente)
- **Hoje:** caçar o arquivo; editar o `dict`; **torcer** para não quebrar a sintaxe nem colidir com
  outro arquivo; `commit`; `deploy`; **reiniciar**; rodar `fix_pns`.
- **Refinado:** editar **1 linha** (CSV/Python-dado) → `git diff` mostra **exatamente** o
  antes/depois → o loader **valida** → `load` → `catalog_version` sobe → o estoque recalcula os
  afetados → (`pghistory` registra, se adotado). O loop inteiro: **editar uma linha, rodar um
  comando.**
- **Mudança de regra de *rentabilidade*:** já é editável no admin (`ProfitabilityConfig`,
  efeito imediato, sem deploy) — **isso já é o ideal; mantenha.**
- **Mudança de regra de *decode*:** edita o **dado** da família. **Mudança de *lógica* de decode**
  (um tipo de decode inédito): aí sim mexe no `engine.py` — e isso é **raro** e **certo** (lógica é
  código).

**É aqui que a arquitetura paga.** Justamente porque o conhecimento é "extremamente mutável", o
que importa é o **custo de uma mudança**. Hoje: cerimônia frágil de muitos passos. Refinado:
**uma linha + um comando**, com diff e validação. Essa é a diferença que escala de 9 para 200
marcas sem o gargalo virar a engenharia.

---

## 5. Simplifica ou complica? O veredito à luz de "menos é mais"

A pergunta certa é separar **dois tipos de complexidade** (Fred Brooks):

- **Complexidade essencial** — inerente ao problema. *200 marcas, regras que mudam toda hora, Gb×GB,
  remarcação* existem de qualquer jeito. Nenhuma arquitetura faz isso sumir.
- **Complexidade acidental** — auto-infligida. *Arquivo de 607 KB, a duplicação que reverte
  edições, o ritual "reinicie após populate", a cerimônia de 13 passos, o estoque defasado, o
  "salta silencioso" das duplicatas* — **isso a proposta remove.**

O que ela **acrescenta** nos degraus enxutos é mínimo: **um** loader genérico (~80 linhas, lugar
único), `normalize_pn` (~5 linhas) e `catalog_version` (~10 linhas). Some isso e subtraia o que ela
tira: o saldo é **fortemente negativo em complexidade** — ou seja, **mais simples**.

**É mais Pythônico, não menos.** "Simples melhor que complexo", "uma maneira óbvia de fazer",
"dobre conhecimento em dados para a lógica ficar burra e robusta". Hoje o conhecimento está
*espalhado em código imperativo*; a proposta o torna *dado declarativo lido por um engine*. Esse é
o refactor que o próprio Python recomenda.

**A única armadilha — para tatuar na parede:**

> **No dia em que um arquivo de dado de marca (Python/CSV/YAML) precisar de um `if`, um loop ou uma
> expressão para ser entendido — PARE. Essa lógica pertence ao `engine.py`, não ao dado.**

Segure essa linha e a arquitetura é *exatamente* o que a indústria usa e *exatamente* o que "menos
é mais" prescreve. Você já pratica essa disciplina (fonte única de rentabilidade e de tipos;
`validate_convention`). É só estendê-la.

---

## 6. O que construir AGORA × ADIAR (a resposta "menos é mais")

Esta é a parte mais importante para a sua filosofia. Nem tudo da proposta deve ser feito já —
construir na especulação **é** o over-engineering que você (com razão) teme.

**AGORA — essencial, barato, alto valor (resolve dor real e presente):**
1. **`normalize_pn()` + coluna `part_number_norm` + restrição de unicidade** — mata a classe de bug
   de duplicata. ~5 linhas + uma migração.
2. **Dado em Python para famílias + UM loader genérico** — mata a duplicação `add_chip_families`
   (bug concreto), tira o monólito, mantém testes/IDE. **É o degrau 1.**
3. **CSV para as ~600 correções** — tira o `fix_known_parts.py` de 607 KB; você já tem ferramentas
   de CSV.
4. **`catalog_version` + cache por versão** — acaba a regra "reinicie após populate".
5. **Segurança de deploy:** `env.db()` sem default + banner de banco-alvo + `bulk_update` + rodar
   no Render Shell.

**EM SEGUIDA — alto valor, depois que o de cima estiver provado:**
6. **Estoque on-read** reusando `_snapshot` + `resnapshot_lote` *gated* por `catalog_version`.

**ADIAR — não construir na especulação:**
- **Degrau 2 (YAML + Pydantic):** o dado-em-Python já é o precursor; converta **quando** a autoria
  por não-dev/IA for real e você estiver editando com frequência.
- **`django-pghistory`:** adote quando a auditoria for necessidade concreta (é a única que captura
  escrita em massa — bom saber, mas não urgente).
- **Multi-tenant:** só a **costura barata** (FK `tenant` anulável no estoque +
  `ProfitabilityConfig` via função de lookup). Nada mais.
- **Pontuação de completude, enriquecimento por IA:** depois.

> Esse faseamento **é** o "menos é mais": cada item de "AGORA" remove uma dor que existe hoje, com
> custo mínimo; cada item de "ADIAR" espera a dor aparecer. Você nunca constrói plataforma para um
> mercado de um cliente só.

---

## 7. Conclusão — atestando a solução

- **A direção é ideal e provada?** Sim, inequivocamente — é como Salesforce, Kubernetes, OPA,
  Sigma/Semgrep/Falco e dbt são construídos, endossada pelo SRE do Google e por todo o cânone, e é
  explicitamente Pythônica.
- **Simplifica?** Sim — remove complexidade *acidental* com máquina nova *mínima*, desde que o dado
  permaneça dado (sem lógica).
- **Envelhece bem por décadas?** Sim — "política muda mais rápido que mecanismo → separe-os → menor
  custo de ciclo de vida" (Raymond) é a autoridade direta; os 25 anos da Salesforce são a prova.
- **É over-engineering para o seu time?** **Não em princípio — seria em forma e momento.** Por isso
  o caminho refinado: **dado-em-Python + CSV agora; YAML+Pydantic depois, só quando a dor for
  real.** Isso mantém você no lado provado de **todas** as fontes desta pesquisa, e é o mais fiel à
  filosofia "menos é mais".

A mudança que este teste de estresse produziu, em uma linha: **a primeira proposta liderava com o
YAML; a versão atestada lidera com dado-em-Python + CSV, e trata o YAML como destino comprovado a
alcançar quando — e só quando — você sentir a dor.** Mais simples, mais barato, menos risco, mesma
direção.

---

## 8. Fontes (pesquisa de mercado, 2025–2026)

**Arquitetura metadata-driven / config-as-data**
- Salesforce — Platform Multitenant Architecture (engine + metadados, materialização em runtime):
  https://architect.salesforce.com/docs/architect/fundamentals/guide/platform-multitenant-architecture.html
- Google — *Site Reliability Workbook*, cap. 14 (config = "code e data, mas separados"; validação
  semântica no commit): https://sre.google/workbook/configuration-design/
- Kubernetes / Google Cloud — "Configuration as Data": https://cloud.google.com/blog/products/containers-kubernetes/understanding-configuration-as-data-in-kubernetes
- Kubernetes — Validating Admission Policy (schema + CEL, GA v1.30): https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/

**Regras/política como dado + validação**
- CNCF — Open Policy Agent (graduado): https://www.cncf.io/projects/open-policy-agent-opa/ · adopters: https://github.com/open-policy-agent/opa/blob/main/ADOPTERS.md
- Sigma (catálogo de regras YAML): https://sigmahq.io/docs/guide/about.html · Semgrep: https://github.com/semgrep/semgrep-rules
- dbt — model contracts (falha o build se o tipo não bate): https://docs.getdbt.com/docs/mesh/govern/model-contracts
- Pydantic — "Why use Pydantic" (parse-don't-validate, adopters): https://docs.pydantic.dev/latest/why/

**O cânone de complexidade / simplicidade**
- Moseley & Marks — "Out of the Tar Pit" (dado declarativo reduz complexidade acidental): https://curtclifton.net/papers/MoseleyMarks06a.pdf
- Fred Brooks — "No Silver Bullet" (essencial × acidental): https://www.cs.unc.edu/techreports/86-020.pdf
- Eric S. Raymond — *Art of Unix Programming* (Regra da Representação; Política × Mecanismo): http://www.catb.org/esr/writings/taoup/html/ch01s06.html
- Tim Peters — PEP 20, Zen of Python: https://peps.python.org/pep-0020/

**O contra-argumento honesto (over-engineering)**
- Mike Hadlow — "The Configuration Complexity Clock": https://mikehadlow.blogspot.com/2012/05/configuration-complexity-clock.html
- Alex Papadimoulis — "The Inner-Platform Effect": https://thedailywtf.com/articles/The_Inner-Platform_Effect · "Soft Coding": https://thedailywtf.com/articles/Soft_Coding
- Martin Fowler — "Yagni": https://martinfowler.com/bliki/Yagni.html
- Sandi Metz — "The Wrong Abstraction": https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction
- karlicoss — "Your configs suck? Try a real programming language" (dataclasses como config): https://beepb00p.xyz/configs-suck.html

---

> **Resumo de uma linha:** *a pesquisa confirma a direção como das mais provadas da indústria e a
> mais Pythônica — e refina o primeiro passo para o mais enxuto possível (dado-em-Python + CSV,
> YAML só quando a dor chegar). Simplifica, é seguro, cabe no Render de hoje, não toca no engine de
> tempo real, e a única regra de ouro é: dado é dado, lógica é no engine.*
