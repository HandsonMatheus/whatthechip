# Roteiro de conferência — lista de compras no telefone

Companheiro de `vendas/tests_tela1_celular.py`. O que está lá é o que Python
consegue provar: que a regra existe e mora na faixa certa. O que está aqui é o
que só o olho no aparelho responde — se a regra certa produz o desenho certo.

Origem: seis achados do dono no iPhone, 2026-09-02.

**Antes de tudo:** limpe o cache do navegador do telefone. Duas vezes já
perdemos meia hora achando que uma regra não tinha funcionado, e era o
`components.css` velho em cache. Se algo abaixo falhar, refaça com cache limpo
antes de reportar.

---

## Preparo

1. `python manage.py runserver 0.0.0.0:8000`
2. No telefone, `http://192.168.100.164:8000/` (o IP do Mac na rede de casa —
   confirme com `ipconfig getifaddr en0`, ele muda quando o roteador reinicia).
3. Entre como comprador e abra **Suas compras**.

---

## 1 · Origem (era: não aparecia)

**Onde:** cada cartão, segunda linha.
**Esperado:** selo preto, texto branco, caixa alta — `PCB`, `CELULAR`, `K9`,
`MISTO`. Sem ícone.
**Falha típica:** cartão sem selo nenhum. Quer dizer que a célula da origem
voltou a levar `class="c"`, e a regra `.dtab .c .otag{display:none}` a apagou.

## 2 · Barra de filtros (era: rachada em faixas cinza)

**Onde:** o bloco acima da lista.
**Esperado:** três faixas, cada uma **cheia de ponta a ponta** — busca com o
botão de exportar à direita; "Todos os status"; "Qualquer período". Nenhum
retângulo cinza sobrando ao lado de um controle.
**Falha típica:** volta o cinza. É o fundo `var(--line)` aparecendo no vão de
uma linha incompleta — algum controle perdeu o `flex:1 1 100%`.
**Teste extra:** escolha "Datas específicas…". Os dois campos de data têm de
ocupar a linha inteira também, sem cinza.

## 3 · US$ ao lado do ¥ (era: só RMB)

**Onde:** canto superior direito do cartão.
**Esperado:** `¥ 203.237,00` grande e, logo abaixo, `US$ 28.453,18` menor e
cinza. Rótulo `ESPERADO` acima dos dois.
**Falha típica A:** só o ¥. O acompanhante não acendeu.
**Falha típica B (a que importa):** **gire para paisagem e volte.** O US$ tem
de continuar aparecendo em paisagem — a faixa dele é 1100px, não 600px. Se
sumir em paisagem, alguém moveu a regra para o bloco de telefone e o tablet
ficou sem nenhum dos dois.
**Falha típica C:** abra no computador em tela cheia. Ali o US$ tem de
aparecer **uma vez só**, na coluna Total US$ — se aparecer também embaixo do
¥, o seletor perdeu a disputa de especificidade.

## 4 · Status (era: "A CONFERIR")

**Onde:** pastilha âmbar na segunda linha do cartão.
**Esperado:** `EM TRÂNSITO`.
**Confira também:** o seletor "Todos os status" — a opção tem de dizer
`Em trânsito (N)`, com a mesma contagem de antes.
**Confira também:** abra um cartão. A ficha tem de dizer `Em trânsito`
também — lista e ficha falam da mesma condição.
**Não pode mudar:** o link continua `?status=a_conferir`. Se virou outra
coisa, todo filtro salvo quebrou.

## 5 · Paginação (era: quebrada)

**Onde:** rodapé da lista. Precisa de mais de uma página — ponha `?per=1`.
**Esperado:** **duas faixas empilhadas.** Em cima, "N na fila" e "N esperando
a sua conferência". Embaixo, ocupando a largura toda: "Página 1 de N" com as
duas setas à direita, cada seta com pelo menos 52px de altura (dá para acertar
com o polegar sem mirar).
**Falha típica:** as duas coisas espremidas na mesma faixa, com a seta cortada
pela borda. É o `flex-wrap:nowrap` de volta.
**Teste de toque:** avance e volte uma página com o polegar, sem ampliar.

## 6 · Esperado × Resultado (era: só o esperado)

**Onde:** segunda linha do cartão.
**Esperado:** `RESULTADO` seguido do valor. Numa ordem ainda sem fatura, um
travessão — `RESULTADO —` — e isso é a resposta certa, não um defeito: ela
ainda não foi conferida.
**Numa ordem faturada:** o valor e, embaixo, `falta US$ N` em âmbar ou
`quitado` em verde.
**Falha típica:** dois montantes sem rótulo nenhum. Aí não dá para saber qual
é o esperado e qual é o resultado — foi exatamente por isso que o guia §7.2
mandava esconder um dos dois.

---

---

## 7 · Ficha da compra: um nome só para o estado

Achado do dono, 2026-09-02: a mesma compra tinha **três** nomes na mesma tela
— `EM TRÂNSITO` na lista, `RECEBIMENTO` no selo ao lado do código e
`RECEBIDO` no trilho de etapas. E `RECEBIDO` estava errado: a caixa não tinha
sido recebida, o passo só estava corrente.

**Abra uma compra enviada e ainda não marcada como recebida.**

- **No topo:** só o código do lote. **Nenhum selo** ao lado dele.
  *Falha:* qualquer pastilha reaparecendo ali. Ela era uma segunda fonte para
  o mesmo fato — o trilho anda por data real, ela andava por uma cascata de
  `if` sobre fatura e preço, e as duas divergiam.
- **No trilho:** o terceiro passo diz `EM TRÂNSITO`, em cinza.
  *Falha:* dizer `RECEBIDO` com o passo cinza — o rótulo afirmando o contrário
  do que a cor mostra.
- **Clique em "Marcar como recebido".** O passo tem de virar `RECEBIDO`,
  com o check verde. É a única coisa que faz esse nome aparecer.
- **Compare com a lista:** as duas telas usam a mesma palavra para o mesmo
  estado. Se divergirem de novo, é sinal de que alguém recalculou o estado em
  vez de ler o `steps`.

---

## 8 · Confirmação antes de marcar como recebido

Marcar recebimento é de mão única: a **primeira data vale** e não há tela
nenhuma para corrigi-la depois. Por isso o botão passou a perguntar.

- **Clique em "Marcar como recebido".** Abre um diálogo. **Nada foi gravado
  ainda** — feche no X e recarregue a página: o passo continua `EM TRÂNSITO`.
- **Confira o que o diálogo mostra:** o código do lote, a data do envio e a
  data que **vai** ser gravada (hoje). Essa última é o ponto: o sistema grava
  hoje, não o dia em que a caixa chegou. Se chegou sexta e você marcar
  segunda, o registro diz segunda — e é aqui que dá para perceber antes.
- **Feche com Esc.** Tem de fechar sem gravar.
- **Feche clicando em "Cancelar".** Idem.
- **Agora confirme.** Só então o passo vira `RECEBIDO`, com check verde, e o
  botão some da barra.
- **No telefone:** o diálogo vira folha de altura inteira, e os dois botões do
  rodapé ficam lado a lado com 52px de altura. Confirme que dá para acertar
  "Cancelar" com o polegar sem mirar — é o botão que evita o erro
  irreversível.

⚠ Se o diálogo **não** abrir e o recebimento for marcado direto, não é bug de
tela: quer dizer que o bloco de JS foi parar depois do `return` do IIFE, e a
confirmação deixou de existir sem nenhum sinal. Há um teste só para isso
(`PosicaoDoScriptTests`).

---

## Por fim, o que este roteiro NÃO cobre

- **Telas 2 e 3** (gaveta de preços e catálogo) continuam quebradas no
  telefone. São a próxima da fila, uma de cada vez.
- **O passo `Enviado` tem o mesmo defeito do `Recebido`, um passo antes.**
  Enquanto a compra não foi despachada, o trilho já escreve `ENVIADO` num
  passo cinza. Não foi mexido — não foi pedido.
- **O passo `pulado`.** Resultado fechado sem ninguém ter marcado o
  recebimento: aí o trilho diz `RECEBIDO` de propósito, porque a caixa
  demonstravelmente chegou. É a única exceção à regra "só vira Recebido
  quando o comprador marca", e ela existe para a tela não dizer
  `EM TRÂNSITO` ao lado de um resultado já fechado.
