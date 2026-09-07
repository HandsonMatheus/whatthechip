# Teste de interface — o rascunho da conferência (autosave)

O script (`vendas/tests_rascunho_conferencia.py`, 27 testes) trava o que vive
no **servidor**: grava, volta, não vaza para o cliente, some ao fechar e nunca
recusa por conteúdo.

O autosave em si é **JavaScript**. Foi verificado num navegador de verdade
(Chromium + Playwright, 19 asserções) rodando o script **real** da página
renderizada pelo Django contra um servidor que registra cada corpo recebido —
o teste confere o que o SERVIDOR viu, não o que o script diz que mandou.
**Este roteiro é o que substitui isso na sua mão.**

    python manage.py test vendas.tests_rascunho_conferencia
    python manage.py test                 # a suíte inteira, no Postgres

Rodar em **staging**, no painel do comprador, numa compra **recebida e sem
fatura** (Conferência), com pelo menos duas marcas.

## 1 · O pedido, na forma mais curta

- [ ] Digitar recusas em três linhas, **sair da página** (voltar para a lista
      de compras) e **abrir a compra de novo**: os três números estão lá.
- [ ] Fechar a aba do navegador inteira e reabrir a compra: idem.
- [ ] Abrir o diálogo "Fechar resultado", escrever uma observação, sair por
      **Revisar lançamentos**, recarregar a página e reabrir o diálogo: o
      texto continua lá.

## 2 · O selo

- [ ] Na barra azul de dica, à direita, aparece **`Salvando…`** e logo depois
      **`Salvo HH:MM`**.
- [ ] A hora está no **seu relógio** e no formato do **idioma da página**
      (24h em português/espanhol/中文). Trocando o idioma no seletor, o
      formato acompanha.
- [ ] Antes de digitar qualquer coisa numa compra nova, a barra é a de sempre
      — sem selo, sem espaço sobrando.

## 3 · Quando ele salva

- [ ] Digitando rápido, o selo **não** pisca a cada tecla — ele espera você
      parar (~1s).
- [ ] Saindo do campo (Tab ou clique fora), salva na hora.
- [ ] **Limpar recusas** apaga na tela **e salva o vazio**: recarregando, os
      campos continuam vazios. (Se voltarem preenchidos, é regressão.)
- [ ] Trocar de aba do navegador (ou trocar de app no celular) logo depois de
      digitar, **antes** do salvamento automático: voltando à compra o número
      está lá. É o `sendBeacon` — o caso em que mais se perdia trabalho.

## 4 · Quando dá errado

- [ ] Desligar a rede (DevTools → Network → Offline), digitar: o selo fica
      **vermelho** dizendo que não salvou. Religando e digitando de novo,
      volta a `Salvo`.
- [ ] Digitar mais que a quantidade enviada: o **navegador** barra no campo,
      com a dica. Nada é salvo por cima.

## 5 · O rascunho NÃO é um resultado — o item mais importante

- [ ] Com recusas digitadas e **sem fechar**, abrir a mesma compra na tela do
      **CLIENTE** (dono do lote): ele vê **0 recusados**. Nada do que você
      digitou aparece para ele.
- [ ] O trilho de etapas continua em **Conferência** e não há fatura.
- [ ] O botão **Fechar resultado** continua abrindo o diálogo de confirmação
      com os números certos, e só grava depois do "Fechar resultado" de lá.
- [ ] Depois de fechar: recarregar a compra e conferir que os números
      mostrados são os do **acerto**. Fechar com um número diferente do que
      estava no rascunho é o teste bom — tem de valer o do acerto.
- [ ] Fechado o resultado, digitar não é mais possível e **nada** fica
      tentando salvar (sem selo, sem erro vermelho).

## 6 · As três telas do comprador concordam

- [ ] Com o rascunho preenchido, o botão **Exportar** (planilha) traz os
      mesmos recusados que a tela.
- [ ] O **Resultado parcial** (PDF) traz os números que estão na tela AGORA —
      ele lê o formulário, não o rascunho. Digite um número, **não espere o
      salvamento**, e clique: o PDF sai com o que você acabou de digitar.

## 7 · Duas abas

- [ ] Abrir a mesma compra em duas abas, digitar em cada uma: **a última a
      salvar vence**. É o comportamento esperado; não há aviso de conflito.
      Se isso incomodar na prática, dá para trancar por versão — hoje não
      está trancado.
