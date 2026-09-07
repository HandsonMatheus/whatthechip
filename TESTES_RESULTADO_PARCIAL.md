# Teste de interface — Resultado parcial

O script (`vendas/tests_resultado_parcial.py`, 31 testes) trava o que vive no
**servidor**: a rota só existe na Conferência, o PDF diz PARCIAL, o número é o
mesmo que a fatura vai congelar, e **nada é gravado**.

O desvio do botão é **JavaScript** e o repo não tem toolchain JS. A lógica foi
verificada num harness de DOM (jsdom, 17 asserções) rodando o script **real** da
página renderizada pelo Django — não uma transcrição à mão. **Este roteiro é o
que substitui isso na sua mão**: se algum item falhar, é regressão de JS.

    python manage.py test vendas
    python manage.py test vendas.tests_resultado_parcial

Rodar em **staging**, no painel do comprador, numa compra **recebida e ainda
sem fatura** (etapa Conferência), com pelo menos duas marcas na planilha.

## 1 · Onde o botão aparece

- [ ] Na etapa **Conferência**, a barra de ação mostra **dois** botões:
      `Resultado parcial` (contorno, com o ícone da impressora) e
      `Fechar resultado` (azul cheio), nessa ordem.
- [ ] Em **Em trânsito** (ainda não marcada como recebida), o botão
      `Resultado parcial` **não existe** — só `Marcar como recebido`.
- [ ] Depois de **fechar o resultado**, o `Resultado parcial` **some** e no
      lugar dele fica o `Imprimir resultado`. Os dois nunca aparecem juntos.
- [ ] Em uma compra de **rascunho** (falta preço/congelar), não aparece.

## 2 · O que o botão faz

- [ ] Digitar recusas em **duas marcas diferentes**, escrever algo na caixa de
      observação do diálogo de fechamento (abrir o diálogo, digitar, fechar
      com **Revisar lançamentos**) e clicar em `Resultado parcial`.
- [ ] O PDF abre em **outra aba** — a tela da conferência continua atrás,
      **com os números que você digitou ainda nos campos**.
- [ ] ⚠ O clique **não abre** o diálogo "Fechar resultado". Se abrir, PARE: o
      "Fechar resultado" desse diálogo grava o acerto de verdade.
- [ ] Digitar uma recusa **maior que a quantidade enviada** e clicar: o
      navegador barra no próprio campo, com a dica. Não gera papel.

## 3 · O papel

- [ ] O nome do arquivo é **`PARTIAL-RESULT-<código da SO>.pdf`** — o mesmo
      código que aparece no topo da tela, com `PARTIAL-` na frente.
- [ ] O **título grande** diz `Partial result (部分結果)`. Não diz
      "Purchase result".
- [ ] O número azul do topo diz **`PARTIAL RESULT (部分結果)`** — não
      "FINAL RESULT".
- [ ] O campo **`Result closed on (結果確認日期)`** mostra um **travessão**.
      É correto: não houve fechamento. É o segundo sinal, depois do título, de
      que o papel ainda não é o final.
- [ ] O resto é **igual** ao PDF do resultado fechado: mesmas colunas, mesmas
      faixas por marca, mesma origem do lote, mesmo rodapé.
- [ ] A **observação que você digitou** aparece na seção de notas do PDF, com a
      data de hoje.
- [ ] Os números batem com o que a tela mostra ao vivo (Resultado e Esperado).

## 4 · Não grava nada — o item mais importante

- [ ] Gerar o parcial **três vezes seguidas**, mudando as recusas entre elas.
- [ ] Recarregar a ficha da compra (F5): a etapa continua **Conferência**, sem
      fatura, e o trilho não avançou.
- [ ] Abrir a aba **Observações**: a observação que entrou no PDF **não está
      lá**. Ela só é salva quando você fecha o resultado.
- [ ] O botão `Fechar resultado` ainda funciona depois disso, e a fatura sai
      com o valor do último parcial que você gerou com essas mesmas recusas.

## 5 · O acesso

- [ ] Estando logado como **outro comprador**, colar a URL
      `/partner/compras/<pk>/resultado-parcial.pdf` de uma compra que não é
      sua dá **404**.
- [ ] Abrir essa URL **direto na barra do navegador** (que é um GET) dá erro de
      método, não um PDF. É de propósito: as recusas vêm do formulário, e um
      GET só poderia gerar um papel dizendo que você aceitou tudo.

## 6 · Regressão do que já existia

- [ ] `Fechar resultado` **continua abrindo o diálogo de confirmação**, com os
      totais certos, e só grava depois do "Fechar resultado" de lá.
- [ ] `Imprimir resultado` (depois de fechado) continua dizendo
      `Purchase result (採購結果)` e `FINAL RESULT (最終結果)`, e o arquivo
      continua se chamando `RESULT-<código da SO>.pdf`.
- [ ] Recusa maior que a quantidade no `Fechar resultado` continua voltando
      para a tela com a mensagem em vermelho, sem emitir fatura.
