# Testes — repactuação de preço pelo comprador

> "vamos deixar ele mudar o preco mesmo e fodase… Ele é comprador, ele quem
> diz o preco, se eu achar ruim busco outro e cabou." — dono, 09/09/2026

O comprador muda o ¥ unitário de qualquer linha na conferência. O preço novo
manda no **RESULTADO**, na **fatura**, na **tela do cliente**, no **PDF** e na
**planilha**. O **ESPERADO não se move** — é o combinado, e é a comparação que
explica a queda ao cliente em vez de dar um susto nele.

```
CONGELADO → ESPERADO.  Não se move nunca.
APLICADO  → RESULTADO. É o congelado, ou o repactuado.
```

## No terminal

```bash
# a feature funcionando, ponta a ponta (38)
python manage.py test vendas.tests_repactuacao

# a varredura de situações (44)
python manage.py test vendas.tests_repactuacao_situacoes

# as duas, com o nome de cada caso
python manage.py test vendas.tests_repactuacao vendas.tests_repactuacao_situacoes -v 2

# só um grupo
python manage.py test vendas.tests_repactuacao_situacoes.OsCentavosTests
python manage.py test vendas.tests_repactuacao_situacoes.QuandoNaoPodeTests

# tudo o que pode ter sido afetado
python manage.py test vendas
```

⚠ **Antes de rodar local:** `python manage.py migrate` — a
`0025_settlementdraft_prices` guarda o preço no rascunho, e sem ela o autosave
estoura.

### O que cada grupo cobre

| classe | o que está sendo protegido |
|---|---|
| `OCongeladoNaoSeMoveTests` | a regra central: ESPERADO parado, RESULTADO andando |
| `ODolarDaLinhaRepactuadaTests` | o US$ deriva da taxa travada, **por linha, em centavos** |
| `AFaixaDaMarcaTests` | a faixa soma exatamente as linhas dela, nas duas contas |
| `ORascunhoGuardaOPrecoTests` | o preço sobrevive a sair da página; apagar apaga |
| `OPostDoCompradorTests` | o formulário da conferência |
| `ASetaTests` | ↑ verde, ↓ vermelha, nada quando não tocou — e o **preço antigo riscado**, com a cor amarrada à da seta |
| `NavegadorTests` | a ficha **rodando** num DOM: seta, riscado, autosave, herói × fatura |
| `NumeroDePontaTests` | vírgula, casas, zero, negativo, teto do campo |
| `RecusaMaisRepactuacaoTests` | as duas coisas na mesma linha |
| `VariasLinhasEMarcasTests` | uma sobe, outra desce, e nada vaza entre marcas |
| `ODinheiroDaEmpresaTests` | a **comissão cai junto** com o preço |
| `OPapelEAPlanilhaTests` | o PDF (parcial **e** final) e o XLSX levam o preço novo, a seta e o riscado |
| `QuandoNaoPodeTests` | sem recebimento, outra ordem, outro comprador |
| `DepoisDeFecharTests` | o rascunho morre, a seta fica, não fecha duas vezes |
| `OsCentavosTests` | arredondamento — onde tela e fatura se separam sem ninguém ver |

### Os que precisam de `jsdom` (pulam sozinhos sem ele)

`NavegadorTests` roda o JavaScript da própria ficha num DOM. Sem node com
jsdom a classe **pula** — o portão continua sendo o resto.

```bash
npm install jsdom     # na raiz do projeto
# ou:  NODE_PATH=/caminho/node_modules python manage.py test vendas.tests_repactuacao
```

## Na tela (manual)

Numa OV **confirmada e recebida**, comprador logado, aba **Conferência**.

| # | passo | o que TEM de acontecer |
|---|---|---|
| 1 | Olhar a coluna **UNITÁRIO ¥** | Número normal + um **lápis apagado**. Nenhuma caixa aberta |
| 2 | Clicar no lápis | O número some, o campo abre **focado**, com o congelado no placeholder |
| 3 | Digitar um preço **menor** e sair (Tab) | Campo fecha, aparece **↓ vermelha**, RESULTADO cai, ESPERADO **não muda** |
| 4 | Olhar a **faixa da marca** e o **rodapé** | Os dois acompanham a linha, na mesma hora |
| 5 | Olhar o **cartão do topo** | O US$ do RESULTADO cai junto; o ESPERADO fica parado |
| 6 | Digitar um preço **maior** noutra linha | **↑ verde** |
| 7 | Abrir o lápis e apertar **Esc** | Volta ao valor anterior e fecha, sem alterar nada |
| 8 | Abrir, **apagar** o campo e sair | Volta ao congelado, a seta **some** |
| 9 | Esperar o selo dizer **"Salvo HH:MM"** e dar **F5** | Os preços digitados **continuam lá** |
| 10 | Clicar em **Limpar recusas** | Recusas e preços voltam ao zero |
| 11 | Baixar o **XLSX** | UNITÁRIO = o preço novo · ESPERADO = o congelado · RESULTADO bate com a tela |
| 12 | Baixar o **RESULTADO PARCIAL** | O PDF mostra o preço novo |
| 13 | **Fechar resultado** e recarregar | Some o lápis, **fica a seta**, e o número é o repactuado |
| 14 | Abrir a mesma OV como **cliente** | Ele vê o preço novo no RESULTADO e o combinado no ESPERADO |

### O preço ANTIGO e a tabela parada (09/09)

| # | passo | o que TEM de acontecer |
|---|---|---|
| 19 | Depois de baixar um preço, olhar **embaixo** do número | O congelado aparece **riscado e vermelho**, numa linha menor |
| 20 | Subir um preço noutra linha | O riscado dessa linha é **verde** — a cor segue a seta, sempre |
| 21 | Apagar o campo e sair | Riscado e seta somem **juntos** |
| 22 | Digitar o **mesmo** valor do congelado | Nada acende: sem seta, sem riscado |
| 23 | Dar **F5** com preço repactuado salvo | O riscado já está lá **antes** de qualquer tecla |
| 24 | **Passar o mouse** por cima de qualquer linha | **Nada muda de cor** — nem as colunas brancas, nem as tingidas |
| 25 | Baixar o **RESULTADO PARCIAL** | Na linha repactuada: `US$ x.xx ↓`, o ¥ novo, e o ¥ antigo **riscado** |
| 26 | **Fechar resultado** e baixar o **RESULTADO FINAL** | O mesmo desenho do parcial — o papel definitivo não perde a seta |
| 27 | Numa OV **sem** repactuação, baixar os dois PDFs | Célula do unitário **exatamente como sempre foi**: US$ em cima, ¥ embaixo |

⚠ **Passo 25/26, se a seta não sair:** é a fonte, não o código. A Helvetica do
reportlab não tem `↑↓`; quem os tem é a `vendas/assets/IBMPlexMono-SemiBold.ttf`.
Se ela não subiu no deploy, o PDF cai para `Courier-Bold` e **a seta some — mas
o riscado fica**, que é o que preserva o fato. Conferir o arquivo no servidor
antes de procurar bug no desenho.

### Erros que a tela tem de barrar (passos 15–18)

| # | digitar no campo de preço | esperado |
|---|---|---|
| 15 | `0` ou negativo | Não fecha o resultado; mensagem de preço fora de faixa |
| 16 | `abc` | Não fecha; mensagem de preço inválido |
| 17 | `1000000` | Não fecha (o campo é `max_digits=8`, teto ¥999.999,99) |
| 18 | O **mesmo** valor do congelado | Fecha normalmente, **sem** seta e **sem** repactuação gravada |

### No celular (≤600px)

O unitário não aparece no cartão do telefone (`.c-unit` é `display:none`) —
então **não há repactuação pelo celular**, por desenho. Conferir só que o
cartão continua igual e que a recusa segue funcionando.

## Três coisas que estes testes existem para lembrar

**O ESPERADO parado é a feature, não um detalhe.** Se um dia ele passar a
acompanhar o RESULTADO, todos os testes de `OCongeladoNaoSeMoveTests` caem — e
é para caírem. Sem a diferença na tela, a queda de preço vira um número que
mudou sozinho, que é exatamente o susto que originou tudo isto.

**O dólar arredonda POR LINHA, em centavos, antes de multiplicar.**
2,55 × 0,1481 = 0,377655 → **0,38** → × 10.000 = **3.800,00**. Multiplicar
primeiro daria 3.776,55 — R$ 23 de diferença numa linha só, e a tela
discordaria da fatura sem ninguém ver.

**A comissão cai junto.** 10% sobre o que de fato saiu, não sobre o combinado.
É o número que mostra quanto a repactuação custou de receita — e é o dado que
transforma *"se eu achar ruim busco outro"* numa decisão com conta feita.
