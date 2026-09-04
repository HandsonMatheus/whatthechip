# Teste de interface — PDF do resultado da compra

O script (`vendas/tests_pdf_resultado.py`) trava o que some sem avisar: ordem
das seções, subtotais, cor da diferença, tokens do design system, fonte do
cabeçalho e a tinta da linha de total. O que ele **não** julga é se o papel
se lê. Isso é olho, e é este roteiro.

Rodar em **staging**, com uma OV real de lote fechado e resultado dado.

    python manage.py test vendas.tests_pdf_resultado

## Como abrir

1. Painel do comprador → **Compras** → abrir uma compra com resultado dado.
2. Botão de exportar → **PDF do resultado**.
3. Abrir o arquivo em tela cheia **e imprimir uma folha A4**. Metade dos
   defeitos de cor só aparece no papel.

## 1 · Topo

- [ ] O título grande é **Purchase result (採購結果)** — não o código do lote.
- [ ] À direita, o rótulo **Sales Order (銷售訂單)** e, embaixo, o código da
      OV em Helvetica (não em Courier: é número de documento, não terminal).
- [ ] O rótulo e o código estão **mais perto um do outro** do que o rótulo
      está do logo. Se o bloco parecer torto, é isto que saiu do lugar.
- [ ] A régua azul fica **abaixo de todas as informações**, separando os
      dados dos números.
- [ ] **Ship from** está em caixa de frase, igual a "Lot closed on", "Box
      received on", "Result closed on" e "Exchange rate". Nenhum campo do
      topo grita em caixa alta.
- [ ] Abra também o **packing list** da mesma OV: ali "SHIP FROM" e "SHIP TO"
      **continuam** em caixa alta. São documentos diferentes, e a caixa alta é
      a convenção do que viaja com a caixa.

## 2 · Os três números

- [ ] Os três rótulos são `EXPECTED (預期)`, `FINAL RESULT (最終結果)` e
      `DIFFERENCE (差額)` — "FINAL" sozinho não diz final de quê.
- [ ] `EXPECTED` cinza, `FINAL RESULT` azul, `DIFFERENCE` na cor do sinal:
      **âmbar se veio a menos**, **verde se bateu ou veio a mais**.
- [ ] Em cada um, **US$ na frente e grande**, ¥ apagado embaixo.
- [ ] Milhar com vírgula: `US$ 170,137.63`, nunca `US$ 170137.63`.
- [ ] Nenhuma caixa colorida em volta dos números — só os números.

## 3 · Cabeçalho da tabela (o que mudou em 04/09)

- [ ] A faixa preta está na **IBM Plex Mono**, a mesma `--font-mono` da tela.
      Abrir a tela do comprador ao lado: tem de bater, letra por letra.
- [ ] Os rótulos latinos estão **todos em CAIXA ALTA**; os ideogramas, não
      (não têm caixa).
- [ ] Cada rótulo cabe em **uma linha só** — nada de "CATEGORY" em cima e
      "(類別)" embaixo.
- [ ] **REJECTED** sai em vermelho e **ACCEPTED** em verde, dentro da faixa
      preta — exatamente como na tela.

## 4 · Corpo e linha de total (o que mudou em 04/09)

- [ ] As colunas **Rejected** e **Accepted** têm fundo rosa e verde claros em
      **todas** as linhas.
- [ ] Na **faixa de cada marca** e na **linha de TOTAL**, essas duas colunas
      ficam num tom **visivelmente mais escuro** — é o que faz o olho
      entender que ali é soma, não lançamento.
- [ ] A faixa da marca continua cinza no resto da linha: o cinza **não** pode
      cobrir o rosa e o verde.
- [ ] Recusa **zero** sai apagada; recusa que existe sai em vermelho escuro
      com o sinal `−`.
- [ ] Sem zebra. Linhas separadas por fio.

## 5 · Impresso

- [ ] Na folha impressa, o tom escuro da linha de total **ainda se distingue**
      do tom claro das linhas comuns. Impressora jato-de-tinta clareia tinta
      pálida — se sumir no papel, avisar, porque a receita da mistura é um
      parâmetro só (`_mistura(..., peso)` em `vendas/pdf.py`).
- [ ] O número preto por cima do fundo escurecido continua legível.

## 6 · Rodapé

- [ ] A data está **por extenso nas duas línguas**: `4 September 2026
      (2026年9月4日)`, e não `04/09/2026`. É o que impede que quem lê mm/dd
      entenda 9 de abril.
- [ ] Os ideogramas do rodapé aparecem como **caracteres**, não como
      quadradinhos. Quadradinho ali significa que a fonte CJK não subiu no
      deploy.
- [ ] O chinês não tem zero à esquerda: `2026年9月4日`, nunca `2026年09月04日`.
- [ ] Abra o **packing list**: a data dele **continua** em `dd/mm/aaaa`. O
      formato curto é o que alfândega e transportadora esperam.

## 7 · Multi-página

- [ ] Numa compra com muitas linhas, o cabeçalho preto **se repete** no topo
      de cada página, já monoespaçado e com os dois rótulos coloridos.
- [ ] A linha de TOTAL aparece **uma vez só**, no fim.
- [ ] O rodapé traz o código do lote em todas as páginas — o lote saiu do
      topo, mas não da vida.

## Se algo falhar

Anotar **qual item** e anexar o PDF. O renderizador é `vendas/pdf.py`,
função `render_result_pdf`; a armadilha que já apareceu quatro vezes é a
mesma: `TEXTCOLOR`/`ALIGN` num `TableStyle` **não atravessam um Paragraph**.
Se um texto saiu preto ou encostado à esquerda sem motivo, é isso.
