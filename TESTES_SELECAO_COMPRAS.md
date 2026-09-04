# Teste de interface — seleção de linhas na lista de compras

O script (`vendas/tests_a_pagar.py`) trava o que vive no **servidor**: a coluna
existe, a linha carrega o dado que o rodapé soma, o `ids` recorta de verdade e
não é porta para a ordem de outro comprador.

O recálculo do rodapé é **JavaScript** e o repo não tem toolchain JS, então
ninguém consegue rodar um teste de node aqui. A lógica foi verificada num
harness de DOM (jsdom, 25 asserções: soma, plural singular/plural, `<small>`
sobrevivendo à troca do número, href do export, estado indeterminado da caixa
mestre, shift-clique nos dois sentidos, clique na célula, e o retorno ao total
do servidor ao desmarcar). **Este roteiro é o que substitui isso na sua mão** —
se algum item falhar, é regressão de JS.

Rodar em **staging**, no painel do comprador, com pelo menos 3 compras e ao
menos uma com fatura em aberto.

    python manage.py test vendas

## 1 · A coluna e a tipografia

- [ ] Existe uma caixa de seleção no **começo de cada linha** e uma no
      cabeçalho, com **18px** (não a caixa minúscula do navegador) e marcada
      no **azul do sistema**.
- [ ] O valor da coluna **A pagar** tem o **mesmo tamanho e a mesma fonte** do
      valor da coluna Resultado (mono, 14px) — só a cor muda, âmbar.
      Foi o defeito de 04/09: ele saía 11px em sans, com corpo de sub-linha.
- [ ] Linha sem dívida mostra `—` **cinza**, não âmbar.
- [ ] Os dois cabeçalhos dizem **ESPERADO ¥** e **ESPERADO US$** — não "Total".

## 2 · O rodapé ao vivo

- [ ] Sem nada marcado, o rodapé diz `Total · N compras` e os dois números são
      os do **recorte inteiro** (todas as páginas).
- [ ] Marcando **uma** linha: o rótulo vira `Selecionada · 1 compra`
      (**singular**) e os dois totais passam a ser os daquela linha.
- [ ] Marcando **duas**: `Selecionadas · 2 compras` e a soma das duas.
- [ ] Os rótulos pequenos "Resultado" e "A pagar" **continuam** acima dos
      números depois de marcar — se sumirem, o JS está reescrevendo a célula
      inteira.
- [ ] **Desmarcando tudo**, o rodapé volta exatamente aos números do servidor.
- [ ] A caixa do cabeçalho marca/desmarca a página inteira, e fica no estado
      **traço** (indeterminado) quando só algumas estão marcadas.

## 2b · Seleção: aparência e atalhos

- [ ] Linha marcada fica com **a linha inteira azul** — não só a célula da
      caixa. É o `.sel` que o design system já definia.
- [ ] **SHIFT-clique**: marcar a linha 1, segurar shift e clicar na linha 5
      marca as cinco. Funciona **nos dois sentidos** (de baixo para cima
      também) e, partindo de uma marcada, **desmarca** o intervalo.
- [ ] Segurar shift e clicar **não pinta o texto** da tabela de azul (seleção
      de texto do navegador).
- [ ] Clicar em **qualquer ponto da célula da caixa** — inclusive no respiro
      ao lado — marca a linha e **não abre a compra**.

## 2c · O fio vertical de hover SAIU

- [ ] Passando o mouse sobre uma linha, ela fica azul e **não aparece nenhum
      traço vertical** na borda esquerda.
- [ ] O mesmo em **todas as outras tabelas** do sistema (estoque, vendas,
      grade de preços, catálogo): o fio saiu do componente, não desta tela.
- [ ] Na tabela com rolagem horizontal (a que gruda a 1ª coluna), a **linha
      divisória vertical** entre a coluna grudada e o resto **continua lá** —
      essa é outra coisa, e é o que separa o que rola do que fica.

## 3 · O export segue a seleção

- [ ] Sem seleção, o botão de exportar baixa **o recorte filtrado inteiro**.
- [ ] Com 2 linhas marcadas, o CSV vem com **cabeçalho + 2 linhas**, e são
      exatamente as marcadas.
- [ ] Marcar e desmarcar tudo devolve o export ao recorte inteiro.
- [ ] Trocar de página **limpa** a seleção (é esperado: a caixa do cabeçalho
      marca a PÁGINA, e as outras páginas não estão no HTML).

## 4 · Sem JavaScript

Desligue o JS no navegador e recarregue:

- [ ] A coluna de seleção aparece e não faz nada — sem erro no console.
- [ ] O rodapé mostra os totais do servidor, corretos.
- [ ] O botão de exportar baixa o recorte inteiro.

Degradar para o comportamento anterior é o certo: a seleção é conveniência,
não requisito.

## 5 · Clique na linha

- [ ] Clicar na **caixa** marca a linha e **não** navega para a compra.
- [ ] Clicar em **qualquer outro ponto** da linha continua abrindo a compra.

## Se algum item falhar

Anote qual. O JS vive no fim de
`vendas/templates/vendas/partner_compras.html`, no bloco "SELEÇÃO DE LINHAS";
o filtro do `ids` vive no `_recorte` de `vendas/views_partner.py`.
