# Guia de implementação — Painel do Comprador (v2)

Referência funcional dos protótipos vivos em `ui_kits/whatthechip/parceiro-*`.
Escrito para um agente que vai implementar, e que **não consegue inferir estas regras lendo só o HTML**: quase toda decisão importante do painel está em uma condição de três caracteres, num comentário, ou no que a tela deliberadamente *não* mostra.

> **Atualizado em 19/08/2026 pela Etapa 0 do briefing v2.** Mudou o essencial: o comprador paga o **WhatTheChip** (não o vendedor), a perna 1 é em **US$**, ¥ e US$ passam a ter o **mesmo corpo** no ciclo de venda, existe a **ordem de venda (OV)** ao lado do lote, `C-###` chama-se **caixa WTC**, e `settled` chama-se **faturado**. As seções §3.2, §4 e §8.8–8.9 já refletem isso. O que ainda **não** mudou está listado em `PLANO-V2-ETAPAS.md` (Etapas 1 a 9).

Leia junto com: `ui_kits/whatthechip/parceiro-compras.js` (dados + regras de dinheiro do lote), `parceiro-data.js` (grade de preços), `parceiro-lote.js` (ficha), `parceiro-grid.js` (grade), `fx.js` (câmbio), `access.js` (papéis).

---

## 0. Como usar este guia

- **§1–§4** são invariantes: valem em todas as telas. Se algo aqui for quebrado, o painel fica errado de um jeito que nenhum teste de tela pega.
- **§5–§8** são as quatro seções do painel, uma por vez, com a regra de negócio antes do desenho.
- **§9** lista o que é andaime de protótipo e **não deve virar produto**. Ler antes de implementar qualquer coisa.
- **§10** é o contrato mínimo de backend que o painel exige.
- **§11** é o checklist de aceite.

Convenção: `¥` = RMB (CNY). "Lote" = a caixa física despachada pelo vendedor. "Linha do lote" = uma combinação categoria WTC × capacidade. "Célula" = um campo de preço na grade.

---

## 1. Quem é o comprador

O comprador é o **parceiro asiático** (no protótipo: *Shenzhen Yuan*, Shenzhen). Ele é a contraparte do vendedor sul-americano (*eMiner*, *RecycleSur*, *Andes Metals*). Não é funcionário da plataforma nem da empresa vendedora — é um tenant separado, com login separado (`login.html`) e um shell visualmente distinto (`.pshell`, com a etiqueta "Parceiro").

O comprador faz **três coisas, e só três**:

1. **Publica preços** — mantém a própria tabela de compra, em ¥, por tipo de chip. É a fonte do preço que o vendedor vê ao triar material.
2. **Confere e paga lotes** — recebe a caixa, lança o que recusou, fecha o resultado e paga.
3. **Gera catálogo** — exporta a própria grade em PDF para mandar ao vendedor.

O que ele **não** faz, e para o que não deve existir rota no painel dele:
- não cria lote, não tria material, não define categoria WTC (`C-###`) — isso é do vendedor/plataforma;
- não altera o conteúdo do lote depois de despachado (nem antes: ele nunca vê o lote antes do despacho);
- não vê estoque, triagem, ou qualquer tela da empresa vendedora;
- não vê os outros compradores nem os preços deles;
- não muda o câmbio — só o consome.

---

## 2. Mapa de telas

| Tela | Arquivo | Rota sugerida | Papel |
|---|---|---|---|
| Compras (home) | `parceiro-compras.html` | `/parceiro/` | Fila de lotes despachados. **Tela de entrada.** |
| Ficha do lote | `parceiro-lote.html?l=<n>` | `/parceiro/lote/<code>/` | Conferência, resultado e pagamento. Peça central. |
| Preços · Resumo | `parceiro.html` | `/parceiro/precos/` | Cobertura da grade por tipo. |
| Preços · grade | `parceiro-precos.html?tipo=<key>` | `/parceiro/precos/<key>/` | Edição da tabela de um tipo. Genérica. |
| Preços · eMCP | `parceiro-emcp.html` | idem, `key=emcp` | Mesma grade, rota fixa (`window.WTC_TYPE`). |
| Preços · eMMC | `parceiro-emmc.html` | idem, `key=emmc` | idem. |
| Preços · SSD | `parceiro-ssd.html` | idem, `key=ssd` | idem. |
| Catálogo | `parceiro-catalogo.html` | `/parceiro/catalogo/` | Gerador de PDF da grade. |

**Nav do shell tem 3 itens** — Compras, Preços, Catálogo. A ficha do lote e as grades são filhas, não itens de nav: a ficha acende "Compras", as grades acendem "Preços".

**As três telas dedicadas (emcp/emmc/ssd) não têm código próprio.** São o mesmo `parceiro-grid.js` com `window.WTC_TYPE` cravado antes do script. Existem porque são as tabelas mais acessadas e merecem URL estável. Em v2, prefira **uma rota parametrizada** (`/parceiro/precos/<key>/`) e trate as três como aliases — não duplique template.

**Chave de tipo inválida ⇒ redirect para o Resumo**, nunca fallback silencioso para um tipo qualquer. A regex é `[a-z0-9]+` e não `[a-z]+`: chave de chip tem dígito (`k9`), e com `[a-z]+` o `k9` virava `k`, não batia com nada e a página caía num tipo padrão sem erro no console. Mantenha o comportamento: chave desconhecida → 302/replace para o Resumo, preservando a query de sessão.

---

## 3. Vocabulário e invariantes

### 3.1 Termos que nunca traduzem
`eMMC`, `eMCP`, `uMCP`, `LPDDR`, `UFS`, `DDR`, `SSD`, `K9`, `PHONE`, `PCB`, `TLC`, `QLC`, `NVMe`, `SATA`, `M.2`, part numbers e nomes de fabricante são **canônicos em qualquer idioma**. O painel é multi-idioma (pt-BR, en, es, zh) e nenhum destes tokens entra no arquivo de tradução.

### 3.2 Caixa WTC (`C-###`)
É o identificador interno que define **o preço** — e é o termo do produto: *caixa*, porque é literalmente a caixa em que o material triado é depositado. Uma linha de lote é `caixa × capacidade`, e todo part number dentro dessa linha vale o mesmo preço unitário. O que varia dentro da linha é PN, fabricante e specs — nunca o preço. Isso é a razão de a aba **Chips** existir separada da aba **Resultado**: a mesma linha aparece como 1 registro de dinheiro e N registros de identificação.

Não confundir com a **categoria**: a convenção WTC de categoria é um código próprio (letra = tipo, número = categoria) e vive no dicionário que a aba **Categorias** vai publicar (Etapa 3). Em `painel.html` e `estoque.html` os dois já convivem: `dest: "C-014"` é a caixa, `cat: "Categoria 04"` é a categoria.

### 3.2.1 Ordem de venda (`SO/####/MM/AA`)
Fechar o lote gera a **OV**, com o preço da tabela do comprador e o câmbio travado naquele instante. O **LOT** é o objeto da caixa; a **OV** é o objeto do dinheiro. As duas listas mostram os dois códigos, e a data exibida ao lado da OV é a da emissão — isto é, o fechamento do lote. A OV é também a referência que o comprador põe no memo da transferência.

### 3.3 Origem do lote
Dois valores: `phone` (Celular) e `pcb` (Placa). Aparece como selo (`FX.origin()`), é dado do lote, e é o eixo por onde a tabela eMMC se divide em duas (ver §5.3).

### 3.4 Código do lote
`LOT/049/07/26` = `LOT / número zero-padded 3 / mês do fechamento / ano`. Gerado a partir de `n` + `closed`. Em v2 o código é **atribuído pelo servidor no fechamento** e é imutável; o painel só o exibe. Nomes de arquivo derivados trocam `/` por `-` (`LOT-049-07-26-lines.csv`).

### 3.5 Estado é derivado, nunca decorativo
Em toda a ficha, o estado de um bloco vem **do que ele produziu**, não de um índice de etapa. `Resultado` está fechado porque existe `done`; `Pagamento` está concluído porque `restCny <= 0 && paidCny > 0`. Se em v2 você guardar um campo `stage` e desenhar a partir dele, os dois vão divergir no primeiro caso de borda.

---

## 4. Dinheiro (a parte que o código não explica)

### 4.1 Duas moedas, dois papéis — e duas hierarquias tipográficas
O comprador **cota e fecha o resultado em ¥ (RMB)** (a tabela de preço dele é em ¥) e **paga em US$**. Nenhuma das duas é tradução da outra no ciclo de venda: uma é o preço, a outra é a transferência.

Daí duas hierarquias no sistema, e usar a errada distorce o argumento da tela:

| Componente | Forma | Onde |
|---|---|---|
| `.mval` | ¥ grande, US$ abaixo, menor e cinza | telas onde o dinheiro é **consequência**: estoque, triagem, painel |
| `.mvd` | ¥ e US$ no **mesmo corpo, mesmo peso, mesma cor**, separados por `=` | o **ciclo de venda**: ficha da compra e da venda, saldo, pagamentos |

Formatação canônica (`fx.js`): **¥ inteiro** (`¥ 12.480`), **US$ com 2 casas** (`US$ 1.844,54`), **taxa com 4 casas** (`0.1478`). Locale `pt-BR` no protótipo; em produção a formatação é server-side e segue o idioma do usuário — mas o número de casas não muda.

### 4.1.1 O `≈` mudou de significado
Antes marcava "US$ é tradução do ¥". Agora marca **estimativa**: rascunho tem valor vivo, re-resolvido contra a tabela do comprador, e leva til. Valor com **câmbio travado sai exato, sem til** — a conversão é aritmética, não palpite. O til vem **uma vez na frente do par**, nunca um por moeda: dois tis afirmam duas incertezas onde existe uma.

### 4.2 A taxa tem quatro estados, e três deles são ruins
`fx.js` modela: `market` (taxa do dia), `fallback` (taxa defasada — a última conhecida, com aviso), `bootstrap` (taxa de contrato, quando não há mercado) e `none` (sem taxa). Sob `none`, **nenhuma tela inventa número**: mostra "sem taxa do dia" e o campo US$ vira `≈ sem taxa do dia`. Em v2 isso significa: o endpoint devolve `rate: null` e o template **não** cai em 0 nem na última taxa sem dizer.

### 4.3 Taxa travada por lote (`lock`, `lockD`)
Cada lote carrega a taxa do dia em que foi **fechado** (`lock: 0.1478`, `lockD: "28/07"`). O US$ de um lote **não é aproximação de hoje** — usa `b.lock`. `lockRate(b) = b.lock || taxa_atual || 0`. Consequência para v2: `lock` é gravado no fechamento e é imutável; toda leitura de US$ da ficha e da lista usa o lock, não a taxa corrente. A taxa corrente aparece só no cabeçalho do shell, como informação de contexto.

### 4.4 O devido é o resultado, nunca o declarado — e quem recebe é o WhatTheChip
Três atores, duas pernas de dinheiro, e elas não se misturam:

```
comprador ──paga o TOTAL CHEIO──▶ WhatTheChip ──paga o LÍQUIDO──▶ cliente
                                     (retém a taxa de serviço)
```

O painel do comprador é **só a perna 1**. Ele não paga o vendedor: paga o WhatTheChip, e a carteira de destino é do WhatTheChip. A perna 2 vive na superfície do cliente e não aparece aqui — nem o valor, nem a data, nem a existência dela. A **taxa de serviço também não aparece aqui**: ela não encolhe o que o comprador deve, e mostrá-la vazaria a margem da plataforma.

A regra de dinheiro mais importante do painel:

```
cny(b)     = Σ (qtd_declarada × preço_unit)   → "Valor do lote"          (¥)
okCny(b)   = Σ (qtd_aprovada  × preço_unit)   → "Resultado"              (¥)
acerto     = okCny − cny                      → sempre ≤ 0               (¥)
dueCny(b)  = okCny(b)                         → o que ele deve           (¥)
dueUsd(b)  = okCny(b) × lock                  → o que ele deve, a pagar  (US$)
paidUsd(b) = Σ pays[].usd                     → o que já pagou           (US$)
restUsd(b) = max(0, dueUsd − paidUsd)         → saldo                    (US$)
```

O **devido nasce em ¥** e vira US$ pela taxa **travada**; o **pago nasce em US$**; o **saldo se resolve em US$** — é em US$ que ele deve, e centavo de dólar é o que a carteira move. O ¥ do saldo é leitura conciliável, derivada, nunca a base da comparação. O valor declarado só sobrevive como referência e como base do "acerto" lançado contra o vendedor.

### 4.5 Arredondamento no centavo
`restUsd = max(0, round((dueUsd − paidUsd) × 100) / 100)`. Sem isso, um resíduo de `3,6e-12` faz um lote quitado dizer "pago em parte". Em v2 use decimal/`Decimal` com 2 casas e compare com tolerância — a tolerância usada nas validações do protótipo é `0.004`.

### 4.6 Nunca dizer PAGO com saldo em aberto
`stTag()` sobrepõe o estado quando há resto:

| Situação | Etiqueta |
|---|---|
| `st = transit` | A CAMINHO (`tag--info`) |
| `st = received` | A CONFERIR (`tag--maybe`) |
| `st = settled`, `paid = 0` | FATURADO (`tag--due`) |
| `st = settled`, `0 < paid < due` | **PAGO EM PARTE** (`tag--due`) |
| `st = paid`, `rest > 0` | **FATURADO / PAGO EM PARTE** — nunca PAGO |
| `rest = 0` | PAGO (`tag--yes`) |

A pastilha diz o **estado**, nunca o **quanto**. Percentual é dado de ficha (barra de progresso na aba Pagamentos), não de etiqueta.

---

## 5. Seção Preços — a grade

### 5.1 Modelo de dados
`parceiro-data.js` define 8 tipos: `emcp`, `umcp`, `lpddr`, `emmc`, `ufs`, `ddr`, `k9`, `ssd`. **A ordem é a do fluxo de triagem** — memória de celular, memória de PCB, NAND avulsa, SSD — não alfabética. Preserve a ordem: é ela que faz a barra lateral espelhar o trabalho real do vendedor.

Cada tipo tem uma **forma** (`form`), e a forma decide o layout da tabela:

| `form` | Estrutura | Tipos | Colunas de preço |
|---|---|---|---|
| `uni` | Uma coluna de preço, vale para todas as marcas | emcp, umcp, lpddr, ufs, k9 | 1 (ou 2 se `range`) |
| `dual` | **Duas tabelas**: celular (unificada) × PCB (matriz por marca) | emmc | 1 + N marcas |
| `brand` | Matriz: uma coluna por marca | ddr | N marcas |
| `linear` | ¥/GB + piso por peça; capacidades **calculadas** | ssd | 2 editáveis + N calculadas |

Modificadores ortogonais:
- `range: true` — a linha tem **faixa** (mínimo e máximo). Só `emcp` e `umcp`. O valor é o par `[min, max]`; os campos são `p<id>` e `pmax<id>`.
- `groups: true` / linhas `["§","LPDDR4"]` — cabeçalho de seção dentro da tabela (geração/família). Não é linha de preço, não conta em `lines`.
- `by: "pn"` — o que **ordena** a linha não é densidade nem marca, é o part number. Só `k9`.

**K9 tem exatamente uma linha e um campo.** Nada ordena uma grade nele: o preço é único, independe de part number, densidade e marca (é NAND Samsung avulsa). Não invente uma grade por densidade para "ficar consistente" — a consistência aqui é a tabela ter o tamanho da realidade.

**SSD não tem grade por densidade.** O preço é linear em ¥/GB com piso por peça. As colunas de capacidade (`caps: [128,256,512,1024]`) são **derivadas**:

```
preço(capacidade) = max( round(¥/GB × GB), piso_por_peça )
```

Quando o piso vence, a célula calculada é marcada em âmbar (`.calc--floor`). Isso é feedback, não erro. Capacidade ≥ 1024 é rotulada em TB.

### 5.2 A convenção de célula — quatro estados, não dois
Esta é a regra que um agente lendo HTML mais erra. Cada célula de preço tem **quatro** valores possíveis, semanticamente distintos:

| Valor no dado | Na tela | Significa | Selo de status |
|---|---|---|---|
| número (`44`, `0.42`) | o número, campo aceso (`.has`) | **cotado** — compro a este preço | `tag--yes` "cotado" |
| `"x"` | `x`, campo em vermelho (`.nox`) | **não compro** este item, decisão ativa | `tag--no` "não compro" |
| `""` (vazio) | campo vazio com placeholder | **sem cotação** — ainda não decidi | `tag--mute` "não cotado" |
| `null` | `—` estático, **não editável** | **não fabricado** — não existe no mundo | `tag--mute` "não fabricado" |

`null` ≠ `""`: um é ausência de produto, o outro é ausência de decisão. `null` não gera input, não entra na contagem de linhas, e nunca pode ser preenchido pelo comprador. Em v2 isso é um enum de 3 estados + valor nullable, ou dois campos (`quote_state`, `price`) — mas **não** um campo numérico com `0` fazendo papel de "x".

Numa matriz por marca, o estado da linha é a **soma** das marcas: tudo `x` ⇒ não compro; tudo `""` ⇒ não cotado; qualquer número ⇒ cotado.

**O status mora em coluna própria** (`<th>Status</th>`), não pendurado no fim do nome da linha. E **todo `<td>` carrega `data-label`** — no telefone a tabela colapsa em cartão e sem o rótulo dois campos de preço lado a lado não dizem qual é mínimo e qual é máximo.

### 5.3 eMMC é o caso de duas tabelas
`form: "dual"`. A mesma família de chip tem dois mercados com estruturas de preço diferentes:
- **de CELULAR**: preço unificado, uma coluna — vale para qualquer marca;
- **de PCB**: matriz por marca (`Samsung, SK hynix, Micron, Kioxia, YMTC, Outras`).

São duas grades na mesma página, cada uma com o próprio rótulo de primeira coluna ("Linha · de CELULAR", "Linha · de PCB, por marca"). O rótulo da 1ª coluna é onde a tabela se identifica — só as páginas com duas grades precisam dizer; nas de uma só, "Linha" basta, porque o título da página já respondeu.

### 5.4 Edição: a página inteira é um formulário, o servidor faz o diff
Comportamento exato do protótipo, e o desenho pretendido para v2:

1. Cada célula editável é um `<input>` nomeado (`p<id>`, `pmax<id>`, `pmin<id>`). O `id` vem de `1200 + índice_do_tipo × 100 + contador` — derivado do **índice na lista canônica**, não de um mapa literal (com mapa, todo tipo novo exige lembrar de dois lugares, e quando um tipo entrou sem entrada a base virou `undefined`, todo `pk++` deu `NaN` e 14 campos colapsaram em dois nomes, silenciosamente).
2. O valor inicial de cada campo é guardado em `init[name]`. A cada `input`, compara-se com `init` e marca-se `dirty`.
3. O rodapé mostra a contagem viva (`"3 células alteradas"` / `"nenhuma alteração"`) e o botão **Enviar** só habilita com ≥ 1 alteração.
4. Enviar manda **as linhas alteradas**, não a tabela toda. O servidor faz o diff e cria um **pedido de revisão** por linha.
5. Depois do envio, os campos limpam o `dirty` e o novo valor passa a ser o `init` — a tela não recarrega.

**Máscara de entrada por forma:**
- normal: `/^(|x|X|\d{0,6})$/` — até 6 dígitos, ou `x`, ou vazio;
- linear (SSD): `/^(|x|X|\d{0,4}([.,]\d{0,2})?)$/` — 2 casas decimais, vírgula aceita e normalizada para ponto.

Caracteres fora da máscara são **removidos**, não rejeitados com erro. `X` maiúsculo normaliza para `x` no blur.

### 5.5 Moderação: preço novo não vale na hora
`REVIEW` marca linhas com pedido pendente (`{"lpddr:LPDDR4 4GB":[34,40]}`). Regra de negócio: **o preço antigo continua valendo** até a plataforma aprovar. A linha em revisão mostra `tag--maybe` com o valor vigente (`em revisão · ¥ 34–40`) em vez do selo de estado normal.

Isso implica, em v2: uma tabela de preço tem **versão vigente** e **pedidos pendentes**. O vendedor sempre lê a vigente. O comprador vê a vigente + a marca de que existe um pedido. Nunca há um terceiro estado onde o comprador acha que já mudou e o vendedor vê outro número.

### 5.6 Contagem de cobertura (`lines` / `miss`)
Para cada tipo: `lines` = células editáveis (exclui `null` e cabeçalhos de seção); `miss` = células `""`. `"x"` **conta como cotado** — é decisão tomada. Estes dois números alimentam:
- a **badge âmbar** na barra lateral de tipos (`miss`, omitida quando zero);
- a coluna "Cotadas" do Resumo e do Catálogo (`lines − miss`, com sub-linha `"N sem cotação"` em âmbar ou `"completa"` em verde);
- os filtros de cobertura do Catálogo.

### 5.7 Barra lateral de tipos
Vive em `parceiro-side.js` e é carregada por **todas** as telas de preço, inclusive o Resumo. Sem ela não se chega a nenhuma tabela — é navegação obrigatória, e estar em toda tela é o que a faz confiável: a única coisa que muda de página para página é qual item está aceso. O primeiro item é sempre **Resumo** (aceso quando não há tipo na rota). Cada item mostra nome + descrição curta + badge de lacunas.

### 5.8 Resumo (`parceiro.html`)
Uma tabela `.dtab`, uma linha por tipo: nome, estrutura da tabela em prosa (`"celular × PCB — duas tabelas"`), linhas, cotadas, chevron. **A linha inteira é clicável** e leva à grade do tipo. O rodapé da lateral carrega a única nota que a tela precisa: SSD não tem grade.

---

## 6. Seção Catálogo

Gerador do PDF que o comprador manda ao vendedor. Layout de duas colunas: seleção de tipos à esquerda, painel de opções à direita.

**Seleção** — tabela `.dtab` com checkbox por tipo. **Todo tipo entra no catálogo até o comprador dizer o contrário**: o estado é um mapa de *exclusões* (`out`), não de inclusões. Consequências: um tipo novo aparece no catálogo automaticamente; o checkbox mestre reflete `all` / `indeterminate`; o botão alterna entre "Marcar todos" e "Desmarcar todos". Filtros: busca por nome/descrição, e cobertura (todos / só completos / só com lacuna).

**Opções do PDF** (caixa preta, `--ink-100`): idioma (中文 simplificado como primeira opção — o comprador é chinês), moeda (`¥ RMB` ou `¥ RMB + US$ ≈`), validade (data), e o que fazer com linhas sem cotação (**ocultar** ou publicar como `—`). Mais uma observação de capa em texto livre, que sai na primeira página abaixo do nome do comprador.

**Carimbo de taxa** — a taxa vai no rodapé de **cada página** do PDF (`mid-market 01/08 · 1 ¥ ≈ US$ 0.1478`). O bloco de carimbo na tela reflete o estado de câmbio ao vivo. Sob `none`, diz "sem taxa do dia" — e nesse caso a opção "¥ RMB + US$ ≈" não pode gerar coluna de dólar.

**Botão Gerar PDF desabilita com zero tipos selecionados** (opacidade + `pointer-events: none`). O rodapé da tabela conta o que vai sair: `"7 de 8 tipos no catálogo · 214 linhas cotadas · 6 sem cotação"`.

---

## 7. Seção Compras — a lista

### 7.1 Regra de entrada
**Só entra na lista o lote que o vendedor fechou E despachou**, com transportadora e código de rastreio preenchidos. Não existe lote "em aberto" no painel do comprador. O primeiro estado possível é `transit`. Se em v2 a lista mostrar lotes não despachados, o painel passa a prometer visibilidade que o negócio não tem.

**Transportadora e rastreio são campos separados** (`carrier`, `track`) — DHL, FedEx, SF Express e EMS aparecem nos dados, e os formatos de código são incompatíveis entre si. Não concatene.

### 7.2 Colunas e degraus de responsividade
`Lote` (código + selo de origem) · `Cliente` · `Chips` (`hide-md`) · `Total ¥` (destaque, `.key`) · `Total US$` (`hide-lg`) · `Resultado` (`hide-sm`) · `Status` · chevron.

A coluna **Resultado** é dupla: o valor do resultado + sub-linha `"a pagar ¥ N"` (âmbar) ou `"quitado"` (verde). Antes do fechamento mostra `—` (`.none`), não zero.

### 7.3 Filtros, ordenação, paginação
- **Busca** casa contra código, cliente, país, cidade, transportadora e rastreio — um único campo, um único `haystack` minúsculo.
- **Status** é um `<select>` com a contagem embutida em cada opção (`"A conferir (2)"`). As contagens vêm do conjunto completo, não do filtrado.
- **Período** filtra pela **data de despacho** (`ship`) — mesma convenção de Estoque e Vendas. Opções: qualquer / últimos 30 dias / últimos 7 dias / datas específicas (revela o range de datas).
- **Ordenação** por clique no `<th class="s">`: `n`, `seller`, `units`, `val`, `usd`, `due`. Default `n` descendente (lote mais novo primeiro). Lotes sem resultado ordenam por `-1` na coluna Resultado, o que os afunda — proposital.
- **Paginação** 10/25/50, com `"1–10 de 24 lotes"` e setas. Trocar filtro, busca ou por-página volta para a página 1.
- **Vazio**: `"Nenhum lote encontrado / Ajuste a busca ou os filtros acima."` — nunca uma tabela vazia sem explicação.
- **Exportar CSV** exporta **o recorte filtrado**, não a base: 13 colunas, separador `;`, BOM UTF-8, nome `compras-<comprador>.csv`. As colunas de resultado saem vazias para lotes não fechados.

### 7.4 A badge do nav
`[data-buys-badge]` no item "Compras" conta **o que exige ação do comprador**:

```
badge = (lotes st=received)  +  (lotes st∈{settled,paid} com restCny > 0)
```

Ou seja: caixas a conferir + dívidas em aberto. Não conta `transit` (não há nada a fazer) nem lotes quitados. Zero ⇒ string vazia, não `0`. Toda tela do painel recalcula a badge no load — em v2, um único endpoint/context processor.

---

## 8. Ficha do lote — a peça central

`parceiro-lote.html` + `parceiro-lote.js` (≈670 linhas). **Uma única UI para todas as etapas da compra.** A folha do registro (identidade, indicadores, campos) e as abas nunca mudam de forma: o que muda é **o que está aceso**. Campos do resultado acendem quando a caixa chega; os do pagamento acendem quando o resultado fecha. A ação da vez fica sempre no mesmo lugar, no canto direito da barra de ação.

Isto é uma convenção do sistema, compartilhada com a ficha da venda (`venda.html`) do outro lado do balcão. Não fragmente em telas por etapa.

### 8.1 Máquina de estados

```
transit ──[comprador: marcar recebido]──► received ──[comprador: fechar resultado]──► settled ──[pagamento]──► paid
   │                                          │                                          │
   └─ vendedor já despachou                   └─ conteúdo do lote CONGELADO              └─ parcial mantém settled
```

| Estado | Quem transiciona | Efeito colateral | Reversível? |
|---|---|---|---|
| `transit` | vendedor (fora deste painel) | lote entra na lista do comprador | — |
| `received` | **comprador** | grava `got` (data); **abre a aba Resultado**; **o vendedor não pode mais alterar o conteúdo do lote** | não |
| `settled` (**faturado**) | **comprador** | grava `done` + `res[]`; lança o **acerto** contra o vendedor; libera pagamento; **números imutáveis** | não (só plataforma reabre, auditado) |
| `paid` | pagamento que zera o saldo | quita o lote | não |

Duas transições são **irreversíveis e avisadas na hora**, no modal, antes do commit. O texto do aviso é parte do contrato, não decoração:
- ao receber: *"A partir daqui o vendedor não pode mais alterar o conteúdo do lote."*
- ao fechar: *"Depois de fechar, os números não podem mais ser alterados."*

Um pagamento parcial **não muda o estado** — o lote continua `settled`, e só a etiqueta vira PARCIAL. `paid` só quando `v >= rest − 0.004`.

### 8.2 Trilho de etapas — cinco células, não seis
`Fechado · Enviado · Recebido · Resultado · Pagamento`.

**A etapa acesa é a última ALCANÇADA, não a próxima a fazer.** Mapeamento: `transit → 1`, `received → 2`, `settled → 4`, `paid → 5`. Células antes da atual levam ✓; a atual mostra a data/valor embaixo; as seguintes ficam apagadas.

O comprador **não tem "a despachar"** — é ação do vendedor —, por isso o trilho dele tem cinco células e o do vendedor tem seis. Não unifique.

O valor de cada célula: `Fechado`→`closed`, `Enviado`→`ship`, `Recebido`→`got` ou `"prev. <eta>"`, `Resultado`→`done` ou `"pendente"`, `Pagamento`→ data do último pagamento / `"parcial"` / `"pendente"` / `"quitado"`.

**Não há etiqueta de estado na linha de identidade** — o trilho ao lado diz a mesma coisa com mais precisão (qual etapa, desde quando), e duas afirmações a 40px uma da outra é eco.

### 8.3 Os três heróis
`Valor do lote` · `Resultado` · `Saldo a pagar`. São os três números que respondem "quanto essa caixa me custa".

- **Valor do lote** é sempre real: `cny(b)`, com `"N un. · M tipos"` embaixo.
- **Resultado** só existe depois do recebimento. Antes: `—` + `"depois do recebimento"`. Nunca zero, nunca o declarado fingindo ser resultado.
- **Saldo a pagar** só existe depois do resultado. Antes: `—` + `"depois do resultado"`. Quando zerado, o rótulo vira **"Quitado"** e a legenda `"nada em aberto"`.

Regra geral: **célula que ainda não tem dado mostra o traço e diz o que falta**, em vez de fingir um número.

### 8.4 As quatro caixas de etapa
Abaixo dos heróis, quatro grupos: `Lote` · `Despacho` · `Resultado` · `Pagamento`. O trilho é o resumo (onde estou); estas caixas são o detalhe (o que cada etapa produziu). Estado de cada caixa: `done` (✓ no cabeçalho) / `now` / `next` (apagada), derivado do dado:

| Caixa | `done` quando | Campos |
|---|---|---|
| Lote | sempre | origem, volume, composição, preço médio |
| Despacho | existe `got` | transportadora, enviado, recebido, câmbio travado + **botão copiar rastreio** |
| Resultado | existe `done` | fechado em, aprovados, recusados, acerto |
| Pagamento | `rest ≤ 0 && paid > 0` | resultado, pago, saldo, nº de registros + **botão copiar carteira** |

Caixas apagadas trazem uma frase explicando **quando acendem** ("Acende quando a caixa for marcada como recebida…", "A carteira da eMiner aparece aqui quando o resultado fechar."). Campos sem dado usam a classe `off`, mantendo o traço.

**Identificador longo em célula estreita corta no MEIO, nunca no fim** (`TQ9fH4mVx…z8gXqN`): a cauda é justamente o que se confere contra a carteira. Vale para endereço de carteira e código de rastreio. O título (`title`) carrega o valor inteiro.

### 8.5 Abas
| Aba | Contador | Disponível |
|---|---|---|
| **Resultado** | nº de linhas do lote | sempre (default) |
| **Chips** | nº de part numbers | sempre |
| **Pagamentos** | nº de pagamentos | **só quando `settled` ou `paid`** |
| **Observações** | nº de notas | sempre |

Aba indisponível fica **desabilitada e visível**, com contador `—` e `title="disponível quando o resultado fechar"`. Não desaparece: o comprador precisa saber que ela existe.

Na barra de abas: filtro de texto (nas abas Resultado e Chips, com placeholder próprio de cada uma), **Imprimir resultado** e **Exportar**.

### 8.6 Aba Resultado — o lançamento
A tela mais importante do painel. Planilha: uma linha por `categoria × capacidade`, agrupada por tipo de chip, com subtotal em cada faixa de tipo e total de cada coluna no rodapé fixo.

**A regra que define o desenho: o comprador digita SEMPRE o que RECUSOU** — a exceção, quase sempre zero — **e o aprovado se calcula sozinho. Lote perfeito = nenhuma tecla digitada.**

Mecânica exata:
- `res[]` é um array paralelo a `lines[]` com a **quantidade aprovada**. Default: a quantidade declarada (tudo aprovado).
- O input mostra `qtd − res[i]` (o recusado), e **vazio significa zero recusas**.
- `input`: só dígitos, máx. 7 caracteres. `rej > qtd` marca o campo (`.bad`) e satura em `res[i] = 0` — o valor não é rejeitado, é clampado.
- `focus` seleciona o conteúdo e acende a linha; `blur` normaliza (`0` volta a vazio) e limpa o `.bad`.
- `Enter` e `↓` descem para a próxima capacidade; `↑` sobe. É entrada de planilha, não de formulário.
- **"Limpar recusas"** zera tudo e aprova o lote inteiro.
- Toda digitação recalcula **ao vivo, só o que mudou**: a célula de recusado, de aprovado e de valor da linha; os subtotais do grupo; os três totais do rodapé; e os heróis do cabeçalho. Não repinta a tabela.

Colunas: `Capacidade · Cat. WTC · Enviados · ¥ unit. · ¥ esperado · US$ ≈ (hide-lg)` e, depois do recebimento, `Recusados (editável) · Aprovados · ¥ resultado`. A célula de resultado mostra o valor e, quando há recusa, o desconto em vermelho (`−¥ 240`).

Antes do recebimento (`transit`), as três colunas de resultado **não existem** — a tabela é a mesma, mais curta.

Dica de uso permanente acima da tabela (só em modo edição): *"Digite só o que recusou — o campo em branco vale zero e o aprovado se calcula sozinho. Enter desce para a próxima capacidade."*

### 8.7 Aba Chips
O detalhado de identificação: cada part number do lote com fabricante, specs com que foi identificado, categoria WTC que definiu o preço, quantidade e valor. Agrupado por tipo de chip, com marcador de cor por grupo e contagem de PNs. Somente leitura.

Serve para conferência física: o comprador tem a peça na mão, lê o PN, e acha a linha.

### 8.8 Aba Pagamentos
Três blocos: **carteira de destino**, **saldo desta compra**, **tabela de parcelas**.

- **Carteira única do WhatTheChip** (`WALLET`): dono, rede (`USDT · TRC-20`), endereço, e a instrução de **colocar o código da ordem (SO) no memo**. Todo pagamento de toda compra vai para este endereço — o comprador **nunca** paga o vendedor direto. O aviso é explícito: *"Confira os seis primeiros e os seis últimos caracteres antes de enviar — transferência em blockchain não volta."* Botão de copiar endereço em todos os lugares onde ele aparece (caixa de etapa, aba, modal).
- **Saldo**: resultado do lote / já pago / restante, cada um no par `¥ = US$`, com barra de progresso e `"N% pago"`. O progresso é calculado **em US$** — é a moeda do pagamento.
- **Tabela**: data, tipo de registro (`INTEGRAL` / `PARCIAL` / `QUITAÇÃO` — "quitação" é o pagamento final que não foi o primeiro), valor no par `¥ = US$`, **referência** da transferência (hash, truncado no meio, copiável), **quem registrou**, e comprovante clicável. Rodapé com total pago e `"restam US$ N"` ou `"saldo zerado"`.
- Vazio: *"Nenhum pagamento registrado. Envie o valor em US$ para a carteira acima e lance aqui — parcial ou integral, sempre com o comprovante anexado."*

### 8.9 Modal de pagamento
Campos: valor (**US$** — a moeda em que ele paga) e comprovante. **Ambos obrigatórios** — o botão de confirmar só habilita com `v > 0 && v <= restUsd + 0.004 && arquivo`.

- Resumo no topo: **ordem (SO)** — é a referência do memo —, resultado do lote no par `¥ = US$`, já pago, **restante** (destacado).
- Endereço da carteira do WhatTheChip, copiável, dentro do modal.
- Entrada de valor aceita decimal, normaliza vírgula, máx. 12 caracteres, um único ponto.
- **Atalhos 25% / 50% / Restante** — o terceiro traz o valor exato do saldo.
- Conversão viva `= ¥ N` usando a **taxa travada do lote**, sem `≈`: com a taxa travada a conversão é exata.
- Acima do saldo: campo em vermelho + `"acima do saldo · máx US$ N"`. Não trunca, não aceita.
- O rótulo do botão muda com o valor: **"Registrar quitação"** quando fecha o saldo, **"Registrar pagamento parcial"** quando não.
- Anexo: PDF/PNG/JPG até 10 MB, com zona de drop, nome do arquivo, botão de remover. *"sem comprovante o pagamento não entra"* — a regra, não um aviso.

Ao confirmar: grava `{d, usd, kind, ref, file, by}`, define `st = paid` se quitou, e o toast diz o resultado em dinheiro (`"Quitado · US$ 3.105,43 pagos para a carteira do WhatTheChip"` / `"Pagamento parcial de US$ 1.201,60 registrado · restam US$ 1.483,53"`).

### 8.10 Aba Observações
O que não cabe em número: avaria na caixa, peso divergente, combinado com o vendedor. Campo de texto + botão, `⌘/Ctrl+Enter` registra, botão desabilitado com campo vazio. Cada nota grava **autor e data**. Notas são removíveis pelo autor.

**Tudo o que está aqui é impresso no PDF do resultado** — é por isso que vale como registro, e é o que a dica sob o campo diz. Se em v2 a nota deixar de sair no PDF, ela perde a função.

### 8.11 Impressão — a folha do resultado
`window.print()` com uma folha própria, montada em JS (e também no evento `beforeprint`, para o print do navegador). É **o documento que o comprador manda de volta ao vendedor**. Conteúdo, em ordem:

1. Cabeçalho: "Resultado do lote", código, vendedor/cidade/país, etiqueta de estado, data de emissão.
2. Duas colunas de dados: origem, transportadora, rastreio, fechado, recebido | câmbio travado, enviados, recusados, aprovados, acerto.
3. Faixa de totais: valor declarado / **resultado** (destacado) / saldo a pagar.
4. Tabela `Resultado por categoria e capacidade`, agrupada por tipo, com `tfoot` de totais.
5. Tabela de pagamentos (se houver).
6. Observações (se houver).
7. Rodapé: `"WhatTheChip · LOT/044/07/26 · valores em ¥ (RMB) na taxa travada de 04/07 · documento gerado pelo comprador em 01/08/26"`.

### 8.12 Exportação CSV
Exporta **a aba aberta** — o recorte que o comprador está olhando. Quatro formatos distintos (Resultado, Chips, Pagamentos, Observações), separador `;`, BOM UTF-8, nome `<CODIGO>-<aba>.csv`. As colunas de resultado só aparecem depois do recebimento.

---

## 9. Andaimes de protótipo — NÃO implementar

Estas partes existem para demonstrar a UI e **não são funcionalidade**:

1. **`demobar`** (barra "Demo · estado do lote", no fim da ficha) — leva o mesmo lote por todas as etapas e restaura os dados originais. É ferramenta de demonstração. **Não vai para produção.** Em produção, as transições vêm das ações reais.
2. **Overrides em `localStorage`** (`wtc_buys`) — o protótipo persiste as mutações no cliente com um mapa `n → patch`, e `null` significa "limpar de volta ao base". Em produção isso é o banco.
3. **`pns()` com gerador pseudoaleatório semeado** — os part numbers da aba Chips são **inventados de forma determinística** (mesma semente ⇒ mesma lista a cada visita, para o lote não mudar de conteúdo ao recarregar). Em produção vêm da triagem do vendedor.
4. **`TODAY = "01/08"` fixo** e `TODAY = new Date(2026,7,2)` na lista — datas cravadas do protótipo. Trocar por data do servidor, no fuso do usuário.
5. **`access.js` role switcher** e o widget de câmbio clicável (`fx.js`) — o widget cicla os quatro estados de taxa para demonstração. Em produção, o estado vem do serviço de câmbio.
6. **Máscara no cliente** — o protótipo esconde campos com CSS (`[data-wtc-needs]`). Em produção o endpoint **omite o campo**, não o esconde no template. Isso vale sobretudo para preço e para a taxa no cabeçalho: `can_see_price` é gate de servidor.
7. **Dados de `parceiro-data.js` e `parceiro-compras.js`** são fixtures. A estrutura é boa; os valores são ilustrativos.

---

## 10. Contrato mínimo de backend

O painel precisa disto para funcionar. Nomes são sugestões; a forma não é.

### 10.1 Preços
```
GET  /parceiro/precos/                 → [{key, name, desc, form, range, by, lines, miss}]
GET  /parceiro/precos/<key>/           → tipo completo: forma, marcas, caps, linhas com
                                          {label, sub, state: quoted|refused|unquoted|na,
                                           price | [min,max] | por marca, review?: valor_vigente}
POST /parceiro/precos/<key>/           → { changes: [{field, value}] } ⇒ cria pedidos de revisão
                                          resposta: quantas linhas entraram em revisão
```
Chave inválida ⇒ 302 para o Resumo. O POST é **idempotente por conteúdo**: reenviar o mesmo valor não cria pedido novo.

### 10.2 Catálogo
```
POST /parceiro/catalogo/               → { types: [key], lang, currency, valid_until, gaps: hide|dash, cover_note }
                                       ⇒ PDF (ou job + polling). Carimbo de taxa por página.
```

### 10.3 Compras
```
GET  /parceiro/compras/                → lista paginada, filtros q / status / period / from / to,
                                          ordenação por n|seller|units|val|usd|due
                                          + contagens por status + badge
GET  /parceiro/compras/export.csv      → mesmo recorte, 13 colunas
GET  /parceiro/lote/<code>/            → lote completo: identidade, datas, carrier/track, lock/lockD,
                                          lines[], res[]?, pays[]?, notes[], pns[]
POST /parceiro/lote/<code>/receber     → { } ⇒ st=received, got=hoje. 409 se não estiver em transit.
POST /parceiro/lote/<code>/resultado   → { res: [qtd_aprovada por linha] } ⇒ st=settled, done=hoje,
                                          grava acerto. 409 se não estiver em received.
                                          Validar 0 ≤ res[i] ≤ qtd[i] por linha, server-side.
POST /parceiro/lote/<code>/pagamento   → multipart { cny, file } ⇒ append em pays[]
                                          Validar 0 < cny ≤ rest (tolerância 0.004) E arquivo presente.
                                          kind derivado, não enviado pelo cliente. st=paid se zerou.
POST /parceiro/lote/<code>/observacao  → { text } ⇒ append, autor = usuário logado, data = hoje
DEL  /parceiro/lote/<code>/observacao/<i>
GET  /parceiro/lote/<code>/resultado.pdf
GET  /parceiro/lote/<code>/<aba>.csv
```

**Todas as quatro ações de mutação precisam de idempotência** (chave de requisição): o comprador está em rede instável e vai clicar duas vezes. Um pagamento duplicado é dinheiro perdido.

**Nunca confie no cliente para:** `kind` do pagamento, `lock`, `due`, código do lote, autoria e data de observação, contagem da badge.

### 10.4 Câmbio
```
GET /fx/                               → { rate, date, is_market, is_fallback, has }
```
Estado `none` é legítimo: `rate: null`, e todo US$ da interface vira "sem taxa do dia".

---

## 11. Checklist de aceite

**Preços**
- [ ] Os quatro estados de célula existem no banco e na UI, com `null` não editável.
- [ ] `x` conta como cotado nas contagens; `""` conta como lacuna.
- [ ] eMCP/uMCP têm faixa (min/máx); K9 tem uma linha; SSD calcula capacidades e marca o piso em âmbar.
- [ ] eMMC renderiza duas grades com rótulos distintos de 1ª coluna.
- [ ] Botão Enviar desabilitado sem alteração; contagem viva de células alteradas; diff no servidor.
- [ ] Linha em revisão mostra o **preço vigente**, e o vendedor lê o vigente.
- [ ] Chave de tipo inválida redireciona ao Resumo.
- [ ] Barra de tipos presente em todas as telas de preço, inclusive o Resumo.

**Compras**
- [ ] Só lotes despachados aparecem.
- [ ] Filtro de período usa a data de **despacho**.
- [ ] Contagens nas opções de status vêm do conjunto completo.
- [ ] Coluna Resultado mostra `—` antes do fechamento, não zero.
- [ ] CSV exporta o recorte filtrado.
- [ ] Badge = a conferir + com saldo em aberto.

**Ficha**
- [ ] `received` e `settled` são irreversíveis, avisados no modal antes do commit.
- [ ] Trilho com **cinco** células; a acesa é a última alcançada.
- [ ] Heróis mostram `—` + o que falta, nunca número falso.
- [ ] Aba Pagamentos desabilitada e visível antes do fechamento.
- [ ] O campo digitado é **recusado**; vazio = zero; `Enter` desce; clamp em `qtd`.
- [ ] O devido é o **resultado**, nunca o declarado.
- [ ] US$ da ficha usa a taxa **travada do lote**.
- [ ] O comprador paga o **WhatTheChip**, em **US$**, e a taxa de serviço **não aparece** na superfície dele.
- [ ] Pagamento exige valor > 0, ≤ saldo, **e** comprovante — e grava referência e quem registrou.
- [ ] Pagamento parcial mantém `settled`; etiqueta vira PAGO EM PARTE; nunca PAGO com saldo.
- [ ] Saldo arredondado no centavo, **em US$**.
- [ ] Observações saem no PDF, com autor e data.
- [ ] PDF do resultado tem as sete seções.
- [ ] Exportação CSV segue a aba aberta.

**Transversal**
- [ ] `.mval` onde o dinheiro é consequência; `.mvd` (¥ = US$, mesmo corpo) no ciclo de venda.
- [ ] `≈` significa **estimativa**, uma vez na frente do par; valor com câmbio travado sai sem til.
- [ ] Estado `none` de câmbio não inventa número em nenhuma tela.
- [ ] Gates de preço aplicados no **servidor** (campo omitido, não escondido).
- [ ] Nenhum termo canônico traduzido em nenhum dos 4 idiomas.
- [ ] Demobar, overrides de `localStorage`, `pns()` semeado e datas fixas **não** foram para produção.
