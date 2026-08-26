# Plano v2 — aplicação do briefing de vendas, por etapas

Fonte: `uploads/BRIEFING_DESIGN_V2_VENDAS.md` (19/08/2026).
Uma etapa por sessão. Nada começa antes de a etapa anterior estar fechada.

**Status:** Etapas 0 a 8 ✅ aplicadas em 19/08. Próxima: 9.

---

## Decisões fechadas

Das 10 perguntas, 8 foram respondidas e 2 eu decidi — e as duas estão marcadas para você contestar.

| # | Decisão |
|---|---|
| Q1 | **O comprador vê o nome do cliente**; o cliente só vê "WhatTheChip". O sigilo é de um lado só. |
| Q2 | **Eu decidi** (ficou em branco): os seis estados são da **OV**, e as duas listas mostram o mesmo estado — muda só quem é cobrado por ele. O comprador não vê OV em `falta preço`, `a congelar` nem `despacho pendente`, porque antes do despacho a OV é rascunho e invisível para ele. **`falta preço` chega ao comprador pela superfície de Preços** (a badge âmbar de lacuna que já existe na barra de tipos), nunca como linha de compra — é o que reconcilia "quem age: comprador" com "invisível antes do despacho". |
| Q3 | **Eu decidi** a leitura: `C-###` **é** a caixa WTC — já convivía com `cat:"Categoria 04"` em `painel.html`/`estoque.html`. Então não houve rename de dado, só de **rótulo** ("Cat. WTC" → "Caixa WTC"). O código letra+número do briefing é o da **categoria**, e vira conteúdo do dicionário da aba Categorias (Etapa 3), onde eu preciso das letras reais de cada tipo. |
| Q4 | OV = `SO/####/MM/AA` (ex.: `SO/0142/07/26`), emitida no fechamento; a data exibida ao lado é a do fechamento. |
| Q5 | Planilha de conferência agrupa por **marca** → capacidade. Implica linha de lote com marca — ver Etapa 3. |
| Q6 | Aba **Observações fica**, e a observação do diálogo de confirmação entra nela. |
| Q7 | **O design system adota os nomes do app** (`.fbar/.sheet/.fgrid/.sst/.mbox`). Bloqueado: preciso de `patterns/ficha.css` para mapear — `.sst` e `.mbox` não são adivinháveis. |
| Q8 | Saldo com **as duas moedas lado a lado, mesmo tamanho**. Novo componente `.mvd`. |
| Q9 | O cliente vê **percentual e valor** da taxa de serviço. |
| Q10 | Rastreio clicável para **todas as seis** transportadoras (DHL, FedEx, UPS, SF Express, EMS, Correios); desconhecida continua em texto puro copiável. |

---

## O que o briefing muda no que já existe

Cinco pontos onde o briefing **contradiz** o protótipo atual. Não são acréscimos: são correções.

| Hoje no protótipo | Briefing | Onde dói |
|---|---|---|
| Comprador paga a **eMiner** (`WALLET.owner = "eMiner Recovery Ltd."`) | Comprador paga o **WhatTheChip**; o WTC paga o cliente retendo **10%** | `parceiro-compras.js`, aba e modal de pagamento, ficha inteira |
| Pagamento lançado em **¥** | Perna 1 é em **US$** | modal de pagamento, saldo, tabela de parcelas |
| **¥ primário, US$ é `≈` menor** (`.mval__u`) | **¥ e US$ têm o mesmo tamanho** | `fx.js`, token de par de moeda, todas as fichas e listas |
| Heróis: `Valor do lote · Resultado · Saldo` | Par que manda: **Esperado × Final**, com a **Diferença explícita** | `rmx` das duas fichas |
| Só existe o código do **LOT** | Existe a **ordem de venda (OV)**, com código e data próprios, nas duas listas | ambas as listas, ambas as fichas, PDFs |

Mais três acréscimos estruturais: **taxa de serviço de 10%** (congelada na fatura, invisível para o gerente e para a tela do lote), **seis estados de lista** no lugar de quatro, e uma **terceira aba de leitura** (Categorias).

---

## Etapa 0 — Base: vocabulário, dinheiro e o terceiro ator ✅

Aplicada em 19/08. O que entrou:

- **WhatTheChip como contraparte financeira**: `WALLET.owner` deixou de ser a eMiner. O comprador nunca paga o vendedor direto, e a aba de pagamento diz isso em uma linha.
- **Perna 1 em US$**: `pays[]` passou de `{cny}` para `{d, usd, kind, ref, file, by}`. Novas funções `dueUsd` / `paidUsd` / `restUsd`; o ¥ do saldo virou leitura derivada. Modal, atalhos (25/50/restante), validação de teto e toasts todos em US$.
- **Novo componente de dinheiro `.mvd`** — ¥ e US$ no mesmo corpo, mesmo peso, mesma cor, separados por `=` literal. Convive com `.mval` (que continua servindo estoque/triagem/painel, onde o dinheiro é consequência). No herói o par empilha por definição: numa linha só, o `=` é exatamente onde a quebra cai.
- **`≈` mudou de significado**: era "US$ é tradução", virou **estimativa**. Valor com câmbio travado sai exato, sem til.
- **Ordem de venda**: `so` nos sete lotes, `soCode()`/`soDate()`, campo `Ordem` no grupo Lote, coluna no CSV, linha no resumo do modal (é a referência do memo) e no cabeçalho do PDF. A busca da lista casa por ordem também.
- **`settled` → FATURADO** e `PARCIAL` → **PAGO EM PARTE**, na pastilha, no filtro da lista e na barra de demo.
- **"Cat. WTC" → "Caixa WTC"** nas duas abas, no PDF e nos CSVs.
- **Rastreio clicável** por transportadora conhecida; desconhecida mantém o botão de copiar.
- **Referência e autoria do pagamento** na tabela da aba, no PDF e no CSV.
- Guia `GUIA-PAINEL-COMPRADOR.md` atualizado nas seções que passaram a mentir (§3.2, §4.1, §4.4, §4.5, §4.6, §8.1, §8.8, §8.9, §11).

**Achado que encurta as Etapas 1 e 2:** `venda-data.js` **já modela** a taxa de serviço e o pagador — tem `FEE`, `grossCny`, `feeCny`, `netCny` e `PAYEE`, e as notas já vêm de "WhatTheChip · Conferência". O lado do cliente está mais adiantado do que o briefing sugere; o que falta é hierarquia e rótulo, não modelo.

**Dívida deixada de propósito:** a folha impressa do comprador ainda é **uma só** e inclui a tabela de pagamentos — que é a perna 1 e o cliente não pode ver. Está marcada com comentário no código e resolve na Etapa 6, que divide o documento em dois. Até lá, saída interna.

---

## Etapa 1 — A ficha do cliente no gabarito (pedido #1 do briefing) ✅

Aplicada em 19/08. A ficha já estava no gabarito — trilho de seis células, quatro caixas de etapa, abas, gate de preço. O que faltava eram as funções do cliente:

- **Despacho editável.** O mesmo diálogo despacha e corrige: em trânsito reabre com os valores preenchidos e o botão troca de nome. **Data de envio virou obrigatória** (é ela que confirma a venda) e **o rastreio virou opcional** — o número às vezes só sai horas depois da postagem. Sem frete: despacho é logística, não dinheiro. Trava quando a caixa é recebida.
- **Rastreio clicável** para as seis transportadoras; sem código a caixa diz que ele pode entrar depois. A lista de URLs foi para `fx.js`, porque as duas fichas mostram o mesmo código e duas listas divergiriam sem avisar.
- **`EM CONFERÊNCIA` → `A CONFERIR`**, o mesmo vocabulário dos seis estados da lista. A frase inteira do briefing — *"recebida pelo comprador"* — vive no trilho, onde há largura; a pastilha fica com duas palavras, como todas as outras do sistema.
- **Ordem de venda** no grupo Lote, no resumo do diálogo de despacho e no cabeçalho do PDF.

---

## Etapa 2 — A faixa de dinheiro do cliente (pedido #2) ✅

**Cinco números em sequência não são cinco KPIs.** `bruto · taxa · líquido · recebido · falta` cabem em três heróis sem esconder nada, porque dois deles são a **conta** de outro — então viram legenda do número que explicam, não detalhe escondido:

| Herói | Valor | Legenda |
|---|---|---|
| Resultado bruto | bruto | `esperado ¥ 26.500 · diferença −¥ 2.069` ← o par Esperado × Final × Diferença |
| Líquido | líquido | `menos serviço de 10% · −US$ 361,09` ← a dedução, percentual **e** valor |
| Falta receber | saldo | `45% repassado · US$ 1.462 já na conta` |

A caixa do **detalhe** (aba Pagamentos) mantém os cinco em sequência de propósito: é onde a subtração precisa poder ser lida linha a linha.

Mais:

- **Perna 2 em US$** — `pays[]` passou de `{cny, tx, file}` para `{usd, ref}`. Valores dos fixtures recalculados na taxa travada de cada ordem, e as parcelas agora somam o líquido exato (a venda 127 dizia "quitada" faltando ¥ 311,90).
- **Repasse não tem comprovante.** A coluna saiu da aba, do PDF e do CSV. Comprovante é prova da perna 1, e essa perna o cliente não vê — nem valor, nem data, nem existência. Aqui o que autentica é a **referência** em cadeia.
- **Taxa por empresa e congelada na emissão**: cada registro carrega o seu `fee`; `FEE` global é só o padrão de quem não tem contrato próprio. Uma linha sob o painel de saldo diz o que congelou e quando.
- **Percentual e valor** sempre juntos (Q9).
- A **lista de vendas** acompanhou: KPIs de recebido e a receber em US$, e a coluna "A receber" também.

**Ainda não feito nesta etapa:** o rename de classe (`.fbar/.sheet/.fgrid/.sst/.mbox`), que depende do Q11.

---

## Etapa 3a — A ficha do comprador: o par que manda e a terceira aba ✅

Aplicada em 19/08. A Etapa 3 foi **partida em duas**: 3a não mexe no modelo de dados, 3b mexe. Pôr as duas no mesmo passo era juntar mudança de argumento com mudança de granularidade, e a segunda é a que quebra em silêncio.

**O par que manda.** Os heróis deixaram de ser `Valor do lote · Resultado · Saldo` e passaram a **Resultado esperado × Resultado final · Saldo**. Esperado é imutável — é o preço fechado com o cliente, o número que ele tinha na mão quando a caixa saiu. Final se move enquanto o comprador digita.

A **diferença** vive na legenda do Final (`−¥ 405 contra o esperado`), com peso e cor — não numa quarta célula. Ela é a conta entre os dois números acima; uma célula própria a trataria como um terceiro valor independente. É a mesma solução dada à faixa do cliente na Etapa 2, e as duas telas são gêmeas.

**Aba Categorias** — dicionário da convenção: letra = tipo, número = categoria. Novo arquivo `wtc-categorias.js`, e as **letras moram todas em `LETTER`**, num lugar só, para trocar numa edição (são inventadas: `E M U L F D K S`).

Duas decisões que valem revisão:
- **o número da categoria é o número da caixa** — caixa 14 ⇒ categoria `E-14`. Quem está com a caixa na mão lê o código direto do rótulo, e os dois nunca divergem. Uma numeração própria exigiria tabela de tradução na cabeça de quem separa material.
- **"nesta compra" é quantidade, não visto** — dizer "veio" é menos do que dizer quanto veio, e é a quantidade que se confere contra a bancada.
- caixa do lote fora do dicionário entra marcada, no fim: caixa desconhecida é notícia para a plataforma, não uma linha a menos na tabela.

**Observação no diálogo de fechamento.** Vai para a aba Observações e daí para a folha do resultado — não para um campo próprio do fechamento, que criaria dois lugares onde procurar o que o comprador escreveu.

**A folha do resultado nasce no fechamento**, e o toast do fechamento diz isso. **Não** ganhou botão próprio no grupo Resultado: os botões-dado dos grupos mostram um *valor* que também é ação (o rastreio, o endereço da carteira) — imprimir não é valor, e a barra de abas já tem "Imprimir resultado" a 300px de distância. Duas portas para a mesma ação é o eco que o resto do sistema evita.

**A coluna `US$ ≈` saiu da planilha de conferência.** O briefing lista as colunas dela e o dólar não está lá; e duas escalas de dinheiro na mesma linha é o que a `.dtab` existe para evitar. Como efeito colateral, a planilha ganhou a largura que a coluna gastava.

---

## Etapa 3b — Agrupar a conferência por marca ✅

Aplicada em 19/08. **A linha do lote deixou de ser posicional.** Era `[tipo, capacidade, caixa, qtd, preço]` e a marca entraria no meio disso — índice trocado não dá erro, dá número errado, calado. Agora é `{mk, t, cap, box, qty, unit}`, e campo que falta aparece como `undefined` na hora.

**Granularidade:** marca × tipo × capacidade × caixa. É a marca que abre o grupo, porque é por marca que o material chega separado na bancada — e o preço continua vindo da **caixa**, então duas marcas na mesma capacidade podem ter o mesmo ¥ e ainda assim ser conferidas em blocos diferentes, porque quem oxidou foi um fabricante. A ordem dos grupos é a de aparição no lote, não alfabética: é a ordem em que o vendedor separou.

O que mudou junto:

- `byType()` → **`byBrand()`**; `types()` sobrou só para contar tipos distintos nos resumos, sem agrupar nada;
- a planilha ganhou coluna **Tipo** (a briefing lista tipo e capacidade separados) e **`¥ unit.` cede a 1100px** — taxa cede antes de valor;
- as **recusas do diálogo de fechamento** passaram a ser por marca, que é o grupo em que a conferência andou;
- a folha impressa segue a mesma agrupação ("Resultado por marca, tipo e capacidade") e o CSV ganhou a coluna Marca;
- **`pns()` respeita a marca da linha** — antes a mesma linha sorteava PNs de fabricantes diferentes, o que contradizia a própria linha;
- os lotes ganharam linhas: 49 foi de 7 para 9, 44 de 4 para 5. Os **totais foram preservados**, então os `pays` em US$ continuam reconciliando.

**A dívida que a mudança criou, e o conserto.** `res[i]` pertence a `lines[i]`. Um `res` gravado no `localStorage` por versão anterior tem outro comprimento e passa a apontar para a linha errada — o lote 48 chegou a dizer resultado ¥ 25.990 sobre esperado ¥ 22.470, com tudo aprovado. Não há como remapear (não se sabe qual linha antiga virou quais novas), então **override com `res` de comprimento incompatível é descartado inteiro na leitura** e o registro volta ao dado de base — é o que uma migração faz quando o mapeamento não existe.

**Não entrou:** a planilha do **cliente** continua agrupando por tipo. O briefing pede marca para a planilha de **conferência** (§2.3) e "resultado por categoria" para o cliente — um produz o resultado, o outro o lê. Quando as duas pontas apontarem para o mesmo registro, a do cliente herda a granularidade.

---

## Etapa 4 — As duas listas: colunas e os seis estados (pedido #3) ✅

---

## Etapa 4 — As duas listas: colunas e os seis estados (pedido #3) ✅

Aplicada em 19/08. O pedido era preciso: *"hoje cada um é uma pastilha; falta dizer quais são ação pendente (pedem cor de chamada) e quais são estado"*.

**A regra que faltava, e ela é do sistema:** a pastilha de chamada aparece **só na lista de quem tem de agir**. Ato do outro lado do balcão é **estado**, e estado é neutro — com um `title` dizendo de quem é a bola. Sem isso as duas listas gritariam a mesma linha para os dois lados, e "ação pendente" deixaria de querer dizer nada.

E a cor diz a **natureza do ato**, nunca quem o pratica: **azul = ato sobre a caixa** (despachar, conferir), **âmbar = ato sobre dinheiro** (aceitar, pagar) — o mesmo âmbar de todo saldo em aberto.

| Estado | Ator | Na lista do cliente | Na lista do comprador |
|---|---|---|---|
| falta preço | comprador | estado (âmbar) | não aparece — chega pela superfície de Preços |
| a congelar | sistema | estado (azul) | não aparece |
| despacho pendente | cliente | **chamada azul** DESPACHAR | não aparece |
| a caminho | comprador | estado | estado |
| a conferir | comprador | estado | **chamada azul** CONFERIR |
| resultado pronto | cliente | **chamada âmbar** ACEITAR | — |
| faturado / pago em parte | comprador | estado (a receber) | **chamada âmbar** PAGAR |
| pago | — | estado | estado |

**Dois estados novos, de verdade e não só na pastilha.** `falta preço` e `a congelar` existem antes de a ordem ser emitida, e nos dois o **câmbio não está travado** — é isso que eles são. Consequências que precisaram existir para os estados não serem cenário:

- preço unitário pode ser `null` (caixa não cotada); soma como zero mas **nunca calado** — a planilha diz "sem preço / aguarda cotação" e o herói diz "parcial: 1 caixa sem preço";
- `lock` nulo, então o valor é estimativa viva e leva **`≈`**; travado, sai exato. É a convenção do til do briefing, agora com um caso real que a exercita;
- o cliente **não tem botão** nesses dois: o lugar da ação da vez vira aviso de espera dizendo o que se espera (`.wait`);
- trilho na primeira célula, e `s.lock.toFixed()` guardado em três lugares onde derrubava a ficha;
- a barra de demo ganhou os dois, e normaliza o lote (cotado + travado) ao sair deles — saltar de "falta preço" para "recebido" fazia as parcelas do repasse nascerem `NaN`.

**Colunas.** `Ordem (código + data)` entrou nas duas listas: na do cliente como **célula de identidade** (a ordem é o objeto do dinheiro; o lote passou para a segunda coluna), na do comprador depois de Cliente, ordenável. Status segue por último, antes do chevron. A busca casa por ordem nas duas.

**A coluna nova custou largura, e a resposta foi a que a folha já prescrevia.** O comentário do `wtc-carbon.css` diz, desde antes: *"a descrição é a primeira coisa a sair quando falta largura: sem ela a tabela transbordaria e levaria a coluna de Status para fora da tela"* — e era exatamente isso que estava acontecendo entre 881 e 1100px. A regra do sistema é **subtração por papel**, não rolagem lateral (`.dtab__wrap--x` existe para as grades de preço, onde o que sai de vista é outra marca, não a coluna de dinheiro). Então:

- **o selo de origem sai a 1100px** — é qualificador do lote, não o lote; no cartão do telefone o sistema já o troca por `data-meta`, então a subtração é a mesma decisão;
- **Resultado** (cliente) e **Chips** (comprador) passaram de `hide-md` para `hide-lg`: leitura intermediária e quantidade cedem antes do dinheiro que decide;
- **pastilhas voltaram a ter uma ou duas palavras** — "RECEBIDO EM PARTE" fazia a coluna Status medir 181px e empurrava a si mesma para fora da tela. Agora `PARCIAL` e `A ACEITAR` (que também nomeia o ato, no vocabulário dos seis estados);
- `Total ¥ (RMB)` → `Total ¥`: o rótulo travava 151px de coluna, e o `¥` já diz RMB — a tela carrega o selo "Todos os preços em ¥ (RMB)".

Medido a 924px nas duas listas: `tabela == wrap`, Status visível, nenhuma célula transbordando a própria coluna.

---

## Etapa 5 — A coluna que some (regra inviolável #1) ✅ auditada

Auditoria em 19/08. **A regra já estava cumprida** — esta etapa não produziu mudança, produziu evidência. Registro o que foi verificado, porque "nada a fazer" só vale se alguém disser o que olhou.

O que foi conferido, arquivo por arquivo:

| Superfície | Mecanismo | Resultado |
|---|---|---|
| `venda.js` (ficha do cliente) | gate `M()` em cada célula, cabeçalho, rodapé de soma, CSV e folha impressa | coluna **omitida do HTML**, não escondida |
| `vendas-lista.html` | `$m` nas células + `[data-money]` oculto no `<th>` + faixa de KPIs inteira fora | colunas fecham em cima |
| `estoque.html` | `data-wtc-needs="price"` no `<th>` **e** no `<td>` | `access.js` aplica `display:none` nos dois |
| `painel.html` | KPI de dinheiro trocado por KPI de ritmo (`needs="noprice"`) | o lugar não fica vazio: recebe outro dado |
| folha impressa do cliente | mesmo gate da tela — sem preço ela é o **laudo** do lote, não um documento financeiro | papel circula mais que tela |

**Nenhuma bolinha.** As três ocorrências de `•••` no kit são outra coisa: o fantasma `C-•••` da bancada vazia em `triagem.html` (placeholder de forma, antes de existir chip) e o `placeholder` do campo de senha no login. Nenhuma delas tapa dinheiro.

**Quantidade não é dinheiro:** sem preço, os três heróis da ficha do cliente passam a ser o físico do lote (volume, aprovados, recusados) e a planilha mantém chips, caixas, recusas e estado. O registro continua inteiro.

**Exceção por desenho, não por esquecimento:** a superfície do **comprador** não tem gate de preço. Os papéis de `access.js` são da empresa vendedora; o comprador é outro tenant, e o preço que ele vê é a **tabela dele**. Esconder de um comprador o próprio preço não é sigilo, é defeito. Se um dia houver papéis dentro da empresa compradora, o gate nasce lá — e aí vale a mesma regra: a coluna some.

---

## Etapa 6 — Os três PDFs

### Doc 3 — Resultado (o comprador gera, o cliente recebe) ✅

Aplicado em 19/08, e com ele **paga a dívida deixada na Etapa 0**: a folha do comprador era a tela impressa, e incluia a tabela de pagamentos — a perna comprador→WhatTheChip, que o cliente não pode ver.

Três vazamentos fechados, os três encontrados por reler a regra §4.3 contra o que a folha imprimia:

1. **Pagamentos** saíram inteiros. Ficaram na aba e no CSV, que são internos do comprador.
2. **O nome do comprador** saiu da autoria das observações — no papel elas são da "Conferência". O cliente sabe que alguém conferiu; não pode saber quem comprou. Na tela do comprador o nome fica, porque ali ele é o autor **e** o leitor.
3. **Linguagem de fatura** saiu: o selo da tela diz FATURADO/PARCIAL (estado de cobrança) e no documento o estado é do **documento** — `EM CONFERÊNCIA` ou `CONFERIDO`. O rodapé também parou de nomear quem gerou.

E entrou o que faltava: a caixa **Esperado × Final × Diferença**. Aqui a diferença tem célula própria, ao contrário da tela — no papel não há legenda para pendurá-la, e é ela que o cliente vai querer discutir. Final em azul claro, Diferença em amarelo claro, **em cor literal e não em token**: papel não tem modo escuro, e com `var(--blue-10)` a célula saía azul-marinho quando a tela estava no escuro.

### Docs 1 e 2 — Conferência do lote (gerente) e a mesma com preço (admin) ✅

Aplicados em 19/08 como **a folha de embarque**, um segundo documento na ficha do cliente, com botão próprio ao lado de Imprimir. Dois documentos, um contêiner: `prMode` decide qual é montado, e o `beforeprint` remonta o selecionado — imprimir pelo atalho do navegador sai igual ao do botão.

**Um documento com um gate, não dois.** Sem preço é a folha do gerente; com preço é a mesma folha mais ¥ unitário e totais. Dois documentos separados divergiriam no primeiro campo novo que alguém acrescentasse.

O que ela tem:

- **`SHIP FROM` / `SHIP TO`** — e o Ship to é a **única exceção sancionada** ao segredo de mercado: mostra o destinatário logístico (armazém alfandegado da plataforma), nunca o comprador. A caixa precisa de endereço para viajar; o cliente não precisa de um nome para saber a quem vendeu, e continua não sabendo.
- **Declaração aduaneira** em moldura própria: `PCB CHIPS FOR DISPOSAL`, posição tarifária, incoterm, peças e valor declarado.
- **Conteúdo por caixa WTC** (novo `byBox()`) — uma caixa, uma linha, com os tipos que ela contém. É assim que o material viaja e assim que a alfândega conta; a planilha do resultado é outra coisa.
- **Três assinaturas**: quem fechou (impresso, vem do papel logado), conferido na origem e recebido no destino (em branco, para caneta) — é o que faz a folha valer como recibo de embarque.

**Uma exceção deliberada ao gate de dinheiro:** o **valor declarado** sai mesmo para quem não vê preço. Declaração aduaneira sem valor não passa na alfândega — aquele número é obrigação legal, não informação de negócio. É a única cifra que atravessa o gate, e está comentada no código como tal.

Cores literais também aqui, pelo mesmo motivo da caixa de três números: esta folha é lida por um conferente de armazém e por um fiscal.

---

## Etapa 7 — Telas de preço do parceiro (pedido #4) ✅

Aplicada em 19/08. O briefing chama estas telas de "a origem de tudo", e o que faltava não era desenho — era **fechar o laço do `falta preço`**, o estado que a Etapa 4 criou na lista do cliente e que eu tinha decidido entregar ao comprador por aqui, sem ainda ter construido o caminho.

**Duas contagens diferentes exigem duas marcas.** A barra de tipos tinha uma só, âmbar, contando células sem cotação. Somar as duas coisas apagava justamente a diferença que importa:

| Marca | Conta | O que é |
|---|---|---|
| âmbar | lacuna | célula sem cotação numa caixa que ninguém está vendendo — **pode esperar** |
| vermelha | pedido travado | lote **já fechado** que a plataforma não consegue precificar sem esta tabela — **fila de trabalho** |

A vermelha vem antes da âmbar na linha, porque é ela que decide a ordem em que o comprador abre as tabelas hoje.

O caminho completo, três paradas:

1. **Faixa no topo do Resumo** — `4 pedidos travados esperando a sua cotação`, com uma célula por tabela: tipo, linha exata, caixa, pedidos, unidades e desde quando. Cada célula é um link para a grade que resolve. A faixa **desaparece quando zera** — não é um painel, é uma fila.
2. **Coluna "Cotadas" do Resumo** diz `travando 2 pedidos` em vez de `1 sem cotação` quando as duas coisas são verdade: as duas são, mas só uma explica a urgência.
3. **Na grade**: aviso vermelho no topo (para quem chegou pela barra e não pela faixa) e, na **coluna Status da linha exata**, `travando 2 pedidos` no lugar de `não cotado`.

**O que não mudou, de propósito:** as oito tabelas, as quatro formas (`uni`/`dual`/`brand`/`linear`), os quatro estados de célula e a moderação. Essa parte do desenho já respondia ao briefing — o que faltava era ela saber por que uma lacuna específica é urgente.

---

## Etapa 8 — Celular: a ficha em 390px (pedido #5) ✅

Aplicada em 19/08. O briefing chama isto de "o caso mais difícil da tela", e é: **é o único lugar do sistema onde se digita dentro de uma tabela.**

A `.dtab` já virava cartão a 600px. O que faltava era o cartão **saber o papel de cada célula** — sem isso as nove células caíam numa pilha indistinguível, com o campo de recusa perdido no meio. Cada célula ganhou classe de papel (`c-t`, `c-cap`, `c-box`, `c-qty`, `c-rej`, `c-ok`, `c-val`) e o cartão virou uma grade de duas colunas.

**A ordem do cartão é a ordem do trabalho de bancada:**

1. o que ele tem na mão — tipo, capacidade, caixa;
2. quanto veio — `enviados 420 un.`;
3. **o campo** — linha inteira, 48px de altura (acima do mínimo de 44), rótulo próprio em âmbar;
4. a consequência — aprovados e ¥ resultado, um degrau abaixo, dividindo uma linha.

**Preço unitário e ¥ esperado saem.** São referência, e referência não se lê com o dedo ocupado.

**A barra viva.** O briefing pede o resultado "no topo da tela" enquanto ele digita. No telefone o topo já rolou — os heróis estão a mil pixels e o rodapé de soma está no fim de uma lista longa. Então o número que se move **acompanha o dedo**: uma barra grudada embaixo, com o resultado final e a diferença, alimentada pelo mesmo `live()` que já move o resto. Ela **só existe no telefone** — acima de 600px o número já está nos heróis e no rodapé, e um terceiro lugar seria eco. O rodapé de soma, em troca, sai: quem soma no telefone é a barra.

Medido a 390px: linha em `grid`, campo de **48×294px**, barra viva em `flex`, seis campos de recusa.

---

## Etapa 9 — Quatro idiomas

`pt-br · es · en · zh-hans`. Toda string nasce traduzida; o comprador lê em 中文. Auditoria de termos canônicos (nunca traduzem) e da regra de mono em código, part number, figura e valor.

---

## Invariantes de leitura (o que os módulos de dados costuram sozinhos)

Três classes de defeito apareceram nesta sessão, sempre pelo mesmo caminho: override gravado no navegador por uma versão anterior do modelo, que não some com deploy. Todas as três são costuradas **na leitura**, nos dois módulos:

1. **Formato do lançamento** — pagamento em ¥ (`{cny, tx, file}`) convertido pela taxa travada para `{usd, ref}`; parcela `full` absorve a sobra de centavos, porque migrar preserva o que o lançamento *significava*.
2. **Cadeia de datas** — `closed → ship → got → done → pagamentos`, cada elo limitado a hoje e nunca antes do anterior. O primeiro elo é o **fechamento**: a caixa não pode sair antes de o lote existir.
3. **Invariantes de estado** — `res` de comprimento incompatível com `lines` descarta o override inteiro (não há como remapear); estado antes da confirmação (`noprice`/`tofreeze`) não pode ter transportadora nem data de envio.

O princípio: **o protótipo se conserta sozinho em vez de deixar o defeito preso no navegador de quem está olhando.**

E uma quarta, que não é de dado e sim de DOM: **a folha impressa tem de ser filha direta do `body`.** A regra de impressão esconde tudo com `body>*{display:none}` e reabre só `.prt`, mas o `viewport.js` do protótipo embrulha a página em dois `div`s — a folha virou neta do `body`, e `!important` não salva um descendente de ancestral escondido. Os três PDFs saíam **em branco**. Os construtores reancoram a folha no `body` a cada montagem, porque CSS não seleciona ancestral e o embrulho pode voltar quando o enquadramento muda.

---

## Dívidas abertas fora do escopo das etapas

- **11px de rolagem lateral da página**, pré-existente e em todas as 16 telas: o menu de conta do cabeçalho (`.me`) termina 11px além do viewport quando a janela fica estreita (medido: `.me` até 920px num viewport de 909). Não é a tabela — as duas listas fecham dentro do próprio wrap. Conserto é no shell compartilhado; vale uma passada própria.
- **A folha impressa do comprador** ✅ resolvida na Etapa 6 (doc 3): pagamentos, nome do comprador e linguagem de fatura fora.

---

## Perguntas que travam etapas

As 10 da primeira rodada estão fechadas (ver *Decisões*). Abriram três:

| # | Pergunta | Trava |
|---|---|---|
| Q11 | **Mande `patterns/ficha.css`** (ou conecte o repo). Q7 diz que o DS adota os nomes do app, mas `.sst` e `.mbox` não são adivinháveis, e renomear errado em 16 telas é pior que não renomear. | 1, 3 |
| Q14 | Os seis estados do briefing **colapsam** dois pares que o protótipo separa: `a conferir` cobre a caminho + chegou, e não há estado para *resultado pronto, a aceitar*. Implementei **oito**, com os nomes do briefing onde existem. Se o app tem exatamente seis, me diga quais os dois pares viram — é rename, não redesenho. | 4 (feito, revisável) |
| Q12 | ✅ **Respondido:** os repasses são sempre em **US$** — e o preço congelado do lote fechado também é em US$: travar o câmbio é justamente o ato de definir esse dólar. | — |
| Q13 | ✅ **Respondido:** posso inventar as letras; o Claude da aplicação corrige. Vou propor `E`/`M`/`U`/`L`/`F`/`D`/`K`/`S` na Etapa 3 e deixar num só lugar, fácil de trocar. | — |

E uma confirmação: sobraram a Etapa 3 (a mais pesada — agrupar por marca muda a granularidade da linha do lote), a 5 (auditoria da coluna que some, e o cliente já está quase todo lá) e a 6 (os três PDFs). Diz por qual seguir.
