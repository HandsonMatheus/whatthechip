# Briefing para o design v2 — o ciclo de VENDA (cliente ↔ comprador)

> **Para quem é:** a sessão de design que mantém o WhatTheChip Design System.
> **O que é:** o inventário das funcionalidades que existem no produto hoje e
> que o protótipo da v2 ainda não cobre. Não é pedido de implementação — é o
> mapa do que precisa de desenho.
>
> **Data:** 19/08/2026 · **Escopo:** app `vendas` + superfície do comprador
> (`/partner/`) · **Estado:** tudo abaixo está EM PRODUÇÃO ou em commit
> pendente de push, com testes.

---

## 0. O modelo de negócio, em cinco linhas

Sem isto nada do resto faz sentido:

1. O **cliente** (empresa recicladora) tria chips e **fecha um lote**.
2. Fechar o lote gera uma **ordem de venda (OV)** para o **comprador**, com o
   preço da tabela dele e o câmbio ¥→US$ travado naquele instante.
3. O cliente **despacha** a caixa. A OV só existe para o comprador depois disso.
4. O comprador **recebe**, **confere** (recusa o que não presta) e **fecha o
   resultado** — que vira a fatura. Ele paga o **WhatTheChip**.
5. O **WhatTheChip** paga o **cliente**, retendo uma **taxa de serviço de 10%**.

> ⚠ **O comprador e o cliente nunca se veem.** Na superfície do cliente a
> contraparte se chama **“WhatTheChip”** e mais nada — nome, pagamentos,
> comprovantes e ritmo de pagamento do comprador são segredo de mercado.

---

## 1. As duas telas que precisam ser gêmeas

**Regra do dono, repetida três vezes:** a tela da **compra** (comprador) e a
tela da **ordem de venda** (cliente) são **o mesmo desenho, na mesma ordem,
com funções diferentes**. Mesmo esqueleto, mesmos lugares — muda quem age em
cada etapa.

| | Comprador (`/partner/compras/<id>/`) | Cliente (`/vendas/<id>/`) |
|---|---|---|
| Etapa 1 | vê o lote fechado | **fecha o lote** |
| Etapa 2 | vê o rastreio | **despacha** (transportadora, rastreio, data) |
| Etapa 3 | **marca o recebimento** | vê a data |
| Etapa 4 | **confere e fecha o resultado** | vê o resultado por categoria |
| Etapa 5 | **paga o WhatTheChip** | **recebe do WhatTheChip** (líquido) |

A tela do comprador já foi vestida com `patterns/ficha.css` (barra de ação ·
folha com identidade e KPIs · grupos de campos por etapa · abas + planilha).
**A do cliente ainda não** — é o próximo encaixe, e é onde o design precisa
dizer como as funções dele ocupam o mesmo gabarito.

---

## 2. Funcionalidades por etapa

### 2.1 Despacho (F4) — ato do CLIENTE

- Campos: **transportadora**, **rastreio**, **data de envio**. Uma caixa por
  lote (não há modelo de volume).
- **Editável** (rastreio digitado errado tem que ser corrigível; o número às
  vezes só sai horas depois). A data é obrigatória; o rastreio pode entrar
  depois.
- **Frete não entra**: despacho é logística, não dinheiro.
- O **despacho é que confirma a venda**. Antes dele a OV é rascunho, invisível
  para o comprador.
- O comprador **só lê**: etapa “Enviado” + rastreio clicável quando a
  transportadora é conhecida (DHL/FedEx/UPS); desconhecida fica em texto puro
  — melhor sem link do que com link quebrado.

**Precisa de desenho:** o bloco de despacho no gabarito da ficha do cliente, e
o estado “despacho pendente” na lista de vendas.

### 2.2 Recebimento — ato do COMPRADOR

- Um botão, que grava a data. **A conferência não abre antes dele** — não se
  confere caixa que não chegou.
- Quando ele marca, o crachá do cliente vira **“recebida pelo comprador”**.

### 2.3 Conferência e resultado — ato do COMPRADOR

O coração do produto.

- Planilha agrupada por **marca → capacidade**, com: tipo, capacidade, **caixa
  WTC**, enviados, ¥ unitário, ¥ esperado e **campo de recusa** por linha.
- Ele digita **só o que recusou**; branco vale zero.
- **Recalcula ao vivo enquanto digita**: total de recusados, aceitos, ¥ a pagar
  e o **resultado no topo da tela**. Conforto — o servidor recalcula tudo no
  envio.
- **Confirmação antes de gravar**: diálogo com lote, enviados, recusados,
  aprovados, resultado, a diferença contra o esperado e a observação opcional.
  Depois de fechado, os números não mudam mais.
- Fechar o resultado **gera o PDF automaticamente** (é o documento que ele
  manda ao cliente).
- **Três abas de leitura ao lado da planilha:**
  - **Chips** — todo PN do lote com spec, caixa WTC, quantidade e preço (a
    conferência detalhe a detalhe);
  - **Categorias** — o dicionário da convenção WTC (letra = tipo, número =
    categoria), com as que vieram nesta compra marcadas;
  - **Pagamentos** — o histórico com comprovantes (só do lado do comprador).

**O par que manda na tela:** **RESULTADO ESPERADO** (imutável — o preço fechado
com o cliente, o número que ele tinha na mão quando a caixa saiu) × **RESULTADO
FINAL** (move-se enquanto ele digita, congela na fatura), **com a diferença
explícita**. Um número só, mudando, apagaria a referência.

**¥ e US$ têm o MESMO tamanho.** Ele fecha em ¥ e paga em US$; nenhum dos dois
é nota de rodapé do outro.

### 2.4 Pagamento — DUAS pernas, e elas não se misturam

```
comprador ──paga o TOTAL CHEIO──▶ WhatTheChip ──paga o LÍQUIDO──▶ cliente
                                      (retém 10%)
```

**Perna 1 — comprador → WhatTheChip** (tela do comprador)
- Valor em **US$** (a moeda em que ele paga), parcial permitido.
- **Comprovante obrigatório** (PDF ou imagem), guardado no banco.
- Histórico com data, valor, referência, quem registrou e o comprovante.

**Perna 2 — WhatTheChip → cliente** (tela do cliente)
- **Bruto − taxa de serviço = líquido**, e **líquido − recebido = falta**.
- Histórico dos **repasses** (data, valor, referência) — **sem comprovante**.
- Registrar repasse é ato da **plataforma**, não do cliente.

> ⚠ **O cliente não vê NADA da perna 1** — nem valor, nem data, nem
> referência, nem comprovante. “Pago” numa tela não é “recebido” na outra: o
> cliente só vê dinheiro que **saiu da conta do WhatTheChip**.

### 2.5 Taxa de serviço da plataforma (novidade de 19/08)

- **10% por padrão, por empresa** (contrato é por cliente; dá para negociar
  outro percentual).
- **Congelada na fatura** na emissão, como o câmbio — mudar o cadastro não
  reescreve venda já acertada.
- **Não encolhe o que o comprador deve**: o total dele continua cheio.
- **Aparece só na ordem de venda.** Não aparece na tela do lote, e **não
  aparece para o gerente** (ver §4).

**Precisa de desenho:** a faixa de dinheiro do cliente tem hoje **cinco**
números em sequência (bruto · taxa · líquido · recebido · falta). É muito para
uma linha só — o design v2 precisa decidir a hierarquia (o que é KPI, o que é
detalhe) sem esconder a dedução.

---

## 3. As duas listas

**Lista de vendas do cliente (`/vendas`)**
`Ordem (código + data) · Lote · Chips · Estimado (¥ + US$) · Resultado ·
A receber · **Status por último**`

**Lista de compras do comprador (`/partner/`)**
`Lote · Cliente · Ordem (código + data) · Chips · Total ¥ · Total US$ ·
Resultado (com o “falta” embaixo) · Situação · abrir`

Convenção das duas: **“≈” marca estimativa**. Rascunho tem valor vivo
(re-resolvido contra a tabela do comprador); confirmado mostra o congelado sem
til, porque a taxa de câmbio congelou junto e a conversão é exata.

**Estados que a lista precisa distinguir** (são seis, e cada um pede uma ação
diferente):

| estado | quem age | o que falta |
|---|---|---|
| falta preço | comprador | cotar a categoria na tabela dele |
| a congelar | sistema | nada — congela sozinho |
| despacho pendente | cliente | postar a caixa |
| a conferir | comprador | receber e conferir |
| faturado / pago em parte | comprador | pagar |
| pago | — | fechado |

---

## 4. Regras invioláveis que o desenho precisa respeitar

1. **Dinheiro não vira bolinha — a coluna some.** Quem não pode ver preço
   (gerente, operador) não recebe `•••` no lugar do valor: a coluna inteira
   deixa de existir, na tela e no PDF. Bolinha é um espaço vazio dizendo “aqui
   tem dinheiro que você não pode ver”.
2. **Quantidade não é dinheiro.** O gerente vê chips, categorias, recusas e
   estado — some só o valor.
3. **Segredo de mercado.** Na superfície do cliente a contraparte é
   “WhatTheChip”. Nunca o nome do comprador, nem o do usuário que registrou um
   pagamento. Única exceção sancionada: o bloco **SHIP TO** do documento de
   embarque (que mostra o destinatário, não o comprador).
4. **Nada abaixo da tabela.** Lote grande tem centenas de linhas; botão no fim
   dela é botão que ninguém alcança. Ação da vez no topo; o resto vira diálogo.
5. **Nada muda de lugar entre uma etapa e outra.** Os campos e as abas só
   *acendem* quando a etapa que os produz acontece — o gabarito fica visível,
   os valores não.
6. **Mono em todo código, part number, figura e valor.**
7. **Quatro idiomas** (pt-br · es · en · zh-hans). Toda string nasce traduzida.
   O chinês é do comprador — ele lê a tela dele em 中文.

---

## 5. Documentos gerados (PDF)

Três, com públicos diferentes — e o desenho deles é papel, não tela:

1. **Conferência do lote** (gerente) — o que viaja com a caixa: quantidade por
   caixa WTC e por tipo, quem fechou, quando, o câmbio travado, blocos SHIP
   FROM / SHIP TO e a **declaração aduaneira** (`PCB CHIPS FOR DISPOSAL` +
   valor declarado). **Nenhuma coluna de dinheiro existe nele.**
2. **O mesmo documento, versão com preço** (admin) — idêntico, com ¥ unitário e
   totais.
3. **Resultado** (o comprador gera, o cliente recebe) — o que foi enviado,
   recusado e aprovado por categoria, mais a caixa **Esperado × Final ×
   Diferença** (Final em azul claro, Diferença em amarelo claro). **Sem nome de
   comprador e sem menção a fatura.**

---

## 6. O que já está vestido com o design system, e o que falta

| Superfície | Estado |
|---|---|
| `/partner/` — lista de compras | ✅ `.pshell` + `.dtab` + `.tag` + `.tfoot` |
| `/partner/compras/<id>/` — a compra aberta | ✅ ficha (`.fbar` · `.sheet` · `.fgrid` · `.nb` · `.sst` · `.mbox`) |
| Barra e trilho de tipos do parceiro | ✅ `.pshell` · `.papp`/`.pside`/`.pmain` |
| `/partner/precos/` e telas de preço | ⏳ conteúdo ainda legado |
| `/vendas` — lista de vendas do cliente | ⏳ tabela própria, precisa virar `.dtab` |
| `/vendas/<id>/` — a OV do cliente | ⏳ **a próxima**: recebe o mesmo gabarito da ficha, com as funções do cliente |
| Estoque, painel, bancada | ⏳ canary por empresa |

---

## 7. O que eu pediria ao design, em ordem de valor

1. **A ficha do cliente** — o gabarito já existe; o que falta é a decisão de
   quais campos e ações do cliente ocupam cada uma das quatro peças, sem sair
   do desenho da tela do comprador.
2. **A faixa de dinheiro com cinco números** (§2.5) — hierarquia sem esconder a
   dedução.
3. **Os seis estados da lista** (§3) — hoje cada um é uma pastilha; falta dizer
   quais são *ação pendente* (pedem cor de chamada) e quais são *estado*.
4. **A tela de preços do parceiro** — é a única superfície do comprador ainda
   no desenho antigo, e ela é a que ele usa para cotar (a origem de tudo).
5. **O celular.** A lista já colapsa em cartão pelo próprio sistema; a **ficha**
   ainda não foi olhada em 390px com a planilha de recusas — é onde ele
   confere, e digitar número em tabela no telefone é o caso mais difícil da
   tela.
