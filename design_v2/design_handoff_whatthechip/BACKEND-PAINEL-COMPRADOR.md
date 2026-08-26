# Painel do comprador — especificação de backend

Escrito para o agente que vai implementar o **backend** do painel do comprador (o parceiro asiático).
Fonte: os protótipos vivos em `ui_kits/whatthechip/parceiro-*` + `fx.js`, depois de aplicadas as etapas 0–8 do briefing v2.

Companhia deste arquivo:
- `GUIA-PAINEL-COMPRADOR.md` — o **porquê** de cada regra (decisões de produto e de desenho).
- `PLANO-V2-ETAPAS.md` — o histórico das mudanças do briefing v2 e as dívidas abertas.

Este arquivo é o **o quê**: entidades, invariantes, endpoints, validações. Onde uma regra parecer arbitrária, o guia explica; não invente uma terceira versão.

Convenções: `¥` = CNY (RMB). `US$` = USD. **Caixa WTC** = `C-###`, o recipiente físico que define o preço. **Categoria** = `L-##`, letra do tipo + número da caixa. **Linha do lote** = marca × tipo × capacidade × caixa.

---

## 1. Atores e tenancy

Três atores, e o painel do comprador é a superfície de **um** deles.

| Ator | Quem é | Superfície |
|---|---|---|
| Cliente / vendedor | recicladora sul-americana (eMiner, RecycleSur, Andes Metals) | `venda*.html`, `estoque`, `triagem`, `painel` |
| **WhatTheChip** | a plataforma | intermedia as duas pernas de dinheiro |
| **Comprador** | parceiro asiático (Shenzhen Yuan) | **este painel** |

O comprador é um **tenant separado**: login próprio, shell próprio (`.pshell`, etiqueta "Parceiro"), e nenhuma rota compartilhada com a empresa vendedora.

### 1.1 Sigilo — assimétrico, e a assimetria é decisão de produto
- **O comprador VÊ o nome do cliente** (coluna `Cliente` na lista, `seller` na ficha).
- **O cliente NÃO vê o comprador.** Nunca. Nem nome, nem cidade, nem que existe mais de um.
- Consequência para o backend: toda serialização voltada ao cliente passa por um filtro que remove identidade do comprador. A folha do resultado (§8) é o caso crítico — é gerada pelo comprador e **lida pelo cliente**.

### 1.2 O que o comprador faz — e só isso
1. **Publica preços** (a tabela dele, em ¥) — é a fonte do preço que o vendedor vê ao triar.
2. **Confere e paga lotes** — recebe a caixa, lança o recusado, fecha o resultado, paga.
3. **Gera catálogo** — exporta a própria grade em PDF.

O que **não** existe rota para ele fazer: criar lote, triar material, definir caixa WTC, alterar conteúdo de lote, ver estoque/triagem do vendedor, ver outros compradores ou preços deles, alterar câmbio, ver a taxa de serviço da plataforma, ver a perna 2 do dinheiro.

### 1.3 Gate de preço — não existe nesta superfície, e é de propósito
Os papéis mascaráveis (`access.js`, `data-wtc-needs="price"`) são da **empresa vendedora**. O comprador é outro tenant e o preço que ele vê é a **tabela dele** — esconder isso não é sigilo, é defeito. Se um dia houver papéis dentro da empresa compradora, vale a regra do sistema: **quem não pode ver preço não vê a coluna** (campo omitido no endpoint, nunca `•••` nem `display:none`).

---

## 2. Dinheiro — as invariantes que o resto depende

### 2.1 Duas pernas, e elas não se misturam

```
comprador ──paga o TOTAL CHEIO (US$)──▶ WhatTheChip ──paga o LÍQUIDO (US$)──▶ cliente
                                            (retém taxa de serviço)
```

Este painel é **só a perna 1**. A perna 2 e a taxa de serviço **não aparecem em nenhum endpoint do comprador** — nem valor, nem data, nem existência. A taxa não encolhe o que ele deve; mostrá-la vazaria a margem da plataforma.

### 2.2 Duas moedas, dois papéis
- O comprador **cota e fecha o resultado em ¥** — a tabela de preço dele é em ¥.
- O comprador **paga em US$** — é a moeda da transferência (USDT · TRC-20).
- Nenhuma é tradução da outra: uma é o preço, a outra é a transferência.

Formatação canônica, **server-side** em produção: **¥ inteiro** (`¥ 12.480`), **US$ com 2 casas** (`US$ 1.844,54`), **taxa com 4 casas** (`0.1478`). O número de casas não muda com o idioma; o separador sim.

### 2.3 A taxa travada por lote (`lock`, `lockD`)
Cada lote carrega a taxa do dia em que foi **fechado**. `lock` é gravado no fechamento e é **imutável**.

- Todo US$ da ficha e da lista usa `lock`, **nunca a taxa de hoje**.
- `rateOf(lote) = lote.lock || taxa_corrente || 0`.
- A taxa corrente aparece só no cabeçalho do shell, como contexto.

### 2.4 O devido é o resultado, nunca o declarado

```
units      = Σ linha.qty                              → peças enviadas
cny        = Σ linha.qty × linha.unit                 → RESULTADO ESPERADO   (¥)
okUnits    = Σ res[i]                                 → peças aprovadas
okCny      = Σ res[i] × linha[i].unit                 → RESULTADO FINAL      (¥)
diferença  = okCny − cny                              → sempre ≤ 0           (¥)
dueCny     = okCny                                    → o que ele deve       (¥)
dueUsd     = round2(okCny × lock)                     → o que ele deve       (US$)
paidUsd    = round2(Σ pays[].usd)                     → o que já pagou       (US$)
restUsd    = max(0, round2(dueUsd − paidUsd))         → saldo                (US$)
paidCny    = round(paidUsd / lock)                    → leitura derivada     (¥)
restCny    = round(restUsd / lock)                    → leitura derivada     (¥)
paidPct    = paidUsd / dueUsd × 100
```

- O **devido nasce em ¥** e vira US$ pela taxa travada.
- O **pago nasce em US$**.
- O **saldo se resolve em US$** — é em US$ que ele deve, e centavo de dólar é o que a carteira move. O ¥ do saldo é leitura conciliável, **derivada, nunca base de comparação**.
- O valor declarado sobrevive como **referência** (o par Esperado × Final) e como base da **diferença** lançada contra o vendedor.

### 2.5 Arredondamento e tolerância
Use `Decimal` com 2 casas em US$ e inteiro em ¥. Tolerância de comparação: **`0.004`**. Sem isso um resíduo de `3,6e-12` faz um lote quitado dizer "PARCIAL".

### 2.6 Nunca dizer PAGO com saldo em aberto
A etiqueta é **derivada**, não armazenada:

| Situação | Etiqueta |
|---|---|
| `st = transit` | A CAMINHO |
| `st = received` | A CONFERIR |
| `st = settled` e `paidUsd = 0` | FATURADO |
| `st = settled` e `0 < paidUsd < dueUsd` | **PARCIAL** |
| `st = paid` e `restUsd > 0` | **FATURADO / PARCIAL** — nunca PAGO |
| `restUsd = 0` | PAGO |

A pastilha diz o **estado**, nunca o **quanto**. Percentual é dado de ficha, não de etiqueta. E a etiqueta tem **uma ou duas palavras** — não "RECEBIDO EM PARTE".

### 2.7 Os quatro estados do câmbio
O serviço de câmbio devolve um destes, e três são ruins:

| Estado | Significado | Na interface |
|---|---|---|
| `market` | taxa do dia | `mid-market 01/08 · 1 ¥ ≈ US$ 0.1478` |
| `fallback` | última taxa conhecida, defasada | mesma leitura, com aviso |
| `bootstrap` | taxa de contrato, sem mercado | `contrato <data>` |
| `none` | sem taxa | **"sem taxa do dia"** |

Sob `none`: `rate: null`, e **nenhuma tela inventa número**. O campo US$ vira `≈ sem taxa do dia`. Não caia em 0 nem na última taxa sem dizer.

### 2.8 O `≈` significa ESTIMATIVA, não "moeda secundária"
- Valor ainda re-resolvível (sem câmbio travado) → leva `≈`, **uma vez na frente do par**, nunca um por moeda.
- Valor com câmbio travado → sai **exato, sem til**: a conversão é aritmética, não palpite.

---

## 3. Modelo de dados

### 3.1 `Buyer` (tenant)
`id`, `name` (Shenzhen Yuan), `city`, `country`, `locale` (default `zh-hans`), `fee_contract` (não visível a ele).

### 3.2 `PriceTable` — a grade do comprador
Uma por **tipo de chip** por comprador. Oito tipos, e **a ordem é a do fluxo de triagem**, não alfabética:

`emcp · umcp · lpddr · emmc · ufs · ddr · k9 · ssd`

Campos: `key`, `name`, `desc`, `form`, `range`, `groups`, `by`, `brands[]`, `caps[]`.

**A forma decide o layout, e são quatro:**

| `form` | Estrutura | Tipos | Colunas de preço |
|---|---|---|---|
| `uni` | uma coluna, vale para todas as marcas | emcp, umcp, lpddr, ufs, k9 | 1 (2 se `range`) |
| `dual` | **duas tabelas**: celular (unificada) × PCB (matriz por marca) | emmc | 1 + N marcas |
| `brand` | matriz, uma coluna por marca | ddr | N marcas |
| `linear` | ¥/GB + piso por peça; capacidades **calculadas** | ssd | 2 editáveis + N calculadas |

Modificadores ortogonais:
- `range: true` — a linha tem **faixa** `[mín, máx]`. Só `emcp` e `umcp`.
- `groups: true` — cabeçalhos de seção dentro da tabela (`["§","LPDDR4"]`). **Não é linha de preço**, não conta em `lines`.
- `by: "pn"` — o que ordena a linha é o part number. Só `k9`.

**Dois casos que parecem inconsistência e não são:**
- **K9 tem exatamente uma linha e um campo.** O preço é único: independe de part number, densidade e marca (NAND Samsung avulsa). Não crie grade por densidade "para ficar consistente" — a consistência é a tabela ter o tamanho da realidade.
- **SSD não tem grade por densidade.** Preço linear, e as colunas de capacidade (`caps: [128,256,512,1024]`) são **derivadas**:
  ```
  preço(capacidade) = max( round(¥_por_GB × GB), piso_por_peça )
  ```
  Quando o piso vence, a célula calculada é marcada em âmbar. É feedback, não erro. Capacidade ≥ 1024 é rotulada em TB.

### 3.3 `PriceLine` / `PriceCell` — **quatro estados, não dois**

A regra que mais se erra. Cada célula tem quatro valores possíveis, semanticamente distintos:

| Valor | Na tela | Significa | Selo |
|---|---|---|---|
| número | o número, campo aceso | **cotado** — compro a este preço | `cotado` |
| `"x"` | `x`, campo em vermelho | **não compro** — decisão ativa | `não compro` |
| `""` | campo vazio | **sem cotação** — ainda não decidi | `não cotado` |
| `null` | `—` estático, **não editável** | **não fabricado** — não existe no mundo | `não fabricado` |

`null` ≠ `""`: um é ausência de **produto**, o outro é ausência de **decisão**. `null` não gera input, não entra na contagem de linhas, e **nunca** pode ser preenchido pelo comprador.

**No banco:** um enum de 3 estados (`quoted` / `refused` / `unquoted`) + `price` nullable + um flag `manufactured`. **Não** um campo numérico com `0` fazendo papel de `"x"`.

Em matriz por marca, o estado da **linha** é a soma das marcas: tudo `x` ⇒ não compro; tudo `""` ⇒ não cotado; qualquer número ⇒ cotado.

### 3.4 `PriceReview` — moderação
```
{"lpddr:LPDDR4 4GB": [34,40], "emcp:eMCP 64GB": [62,74], "ufs:UFS 3.1 256GB": [118]}
```
Regra de negócio: **o preço antigo continua valendo** até a plataforma aprovar. A linha em revisão mostra o **valor vigente** com selo `em revisão · ¥ 34–40`.

No banco: uma tabela de preço tem **versão vigente** e **pedidos pendentes**. O vendedor sempre lê a vigente. Nunca existe um terceiro estado onde o comprador acha que mudou e o vendedor vê outro número.

### 3.5 `BlockedQuote` — pedido travado por falta de cotação
```
ddr:   {box:"C-026", row:"DDR5 16GB",   orders:2, units:110, since:"01/08"}
lpddr: {box:"C-031", row:"LPDDR4X 6GB", orders:1, units:140, since:"31/07"}
emmc:  {box:"C-005", row:"eMMC 256GB",  orders:1, units:90,  since:"30/07"}
```
É o estado `falta preço` do cliente **visto do lado de quem pode resolver**. Não é uma lacuna comum, e a distinção é a única que importa aqui:

| | Conta | Natureza |
|---|---|---|
| **lacuna** (`miss`) | célula `""` em caixa que ninguém está vendendo | pode esperar |
| **travado** (`BlockedQuote`) | lote **já fechado** que a plataforma não consegue precificar | **fila de trabalho** |

Derivado, não armazenado: é a agregação dos lotes em `falta preço` por (tipo, linha). Precisa de `orders`, `units` e `since` (a data do lote travado mais antigo).

### 3.6 `Lot` / `SalesOrder`
Dois códigos, dois objetos:
- **LOT** = o objeto da **caixa**. `LOT/049/07/26` = `LOT / n zero-padded 3 / mês do fechamento / ano`.
- **SO** = o objeto do **dinheiro**. `SO/0142/07/26` = `SO / número zero-padded 4 / mês do fechamento / ano`. Emitida **no fechamento**, com o preço da tabela e o câmbio travado naquele instante. É a referência do **memo** da transferência.

Ambos **atribuídos pelo servidor** e **imutáveis**. A data exibida ao lado da SO é a de emissão — isto é, `closed`. Nomes de arquivo derivados trocam `/` por `-`.

Campos do lote na superfície do comprador:
```
n, so, origin (phone|pcb), seller, city, country,
closed, ship, eta, got, done,
carrier, track,
st (transit|received|settled|paid),
lock, lockD,
lines[], res[], pays[], notes[]
```

### 3.7 `LotLine` — **campos nomeados, nunca posicionais**
```
{mk: "Samsung", t: "eMMC", cap: "32GB", box: "C-014", qty: 240, unit: 15}
```
Granularidade: **marca × tipo × capacidade × caixa**.

- É a **marca** que abre o grupo na conferência, porque é por marca que o material chega separado na bancada.
- O **preço vem da caixa** — duas marcas na mesma capacidade podem ter o mesmo ¥ e ainda assim ser conferidas em blocos separados, porque quem oxidou foi um fabricante.
- A ordem dos grupos é a de **aparição no lote**, não alfabética: é a ordem em que o vendedor separou.

Este campo era uma tupla posicional e a migração para nomes foi feita justamente porque **índice trocado não dá erro: dá número errado, calado.** Não volte para tupla.

### 3.8 `res[]` — o resultado
Array **paralelo a `lines[]`** com a **quantidade aprovada** por linha. Default no recebimento: `res[i] = lines[i].qty` (tudo aprovado).

⚠️ **O acoplamento posicional é uma dívida conhecida.** Se `lines` mudar de estrutura, `res` gravado antes aponta para a linha errada — em silêncio. Em produção, **grave o resultado com chave de linha** (`line_id`), não por índice. O protótipo se defende descartando `res` de comprimento incompatível; o banco não deve precisar disso.

### 3.9 `Payment` (perna 1)
```
{d: "16/07", usd: 1201.60, kind: "partial"|"full",
 ref: "<hash da transferência>", file: "usdt-so-0131-16jul.pdf", by: "Shenzhen Yuan"}
```
- `usd` é o valor nativo. **Não guarde ¥** — derive.
- `kind` é **derivado no servidor** (`full` se zerou o saldo), nunca enviado pelo cliente.
- `ref` é a referência da transferência (hash). Truncada no meio na exibição (`9d41c7e0…517402`), copiável, com o valor inteiro no `title`.
- `file` é o **comprovante obrigatório** — nesta perna ele é prova de transferência.
- `by` é o usuário logado, resolvido no servidor.

Rótulo exibido: `INTEGRAL` (primeiro e único), `PARCIAL`, `QUITAÇÃO` (o `full` que não foi o primeiro).

### 3.10 `Note`
```
{d: "12/07/26", who: "Shenzhen Yuan", t: "<texto>"}
```
Autor e data **resolvidos no servidor**. Removível pelo autor. **Sai no PDF do resultado** — é isso que a faz valer como registro. Se deixar de sair, perde a função.

### 3.11 `WtcBox` / `Category` — o dicionário
Duas coisas que o sistema não pode confundir:

- **Caixa** (`C-###`) — o recipiente físico da bancada. É o que a linha do lote carrega e **é o que define o preço**.
- **Categoria** (`L-##`) — a classificação: **letra = tipo de chip, número = categoria**.

**O número é o mesmo nos dois.** Caixa `C-014` ⇒ categoria `E-14`. Decisão de projeto, não coincidência: quem está com a caixa na mão lê o código direto do rótulo, e os dois nunca divergem. Numeração própria exigiria tabela de tradução na cabeça de quem separa material.

⚠️ **As letras do protótipo são inventadas** (`E M U L F D K S`) e moram num lugar só (`LETTER` em `wtc-categorias.js`). Substitua pelas reais.

Caixa que aparece num lote e não está no dicionário **não pode sumir da tela**: devolva um registro sintético marcado (`unknown: true`). Caixa desconhecida é notícia para a plataforma, não uma linha a menos.

### 3.12 `Wallet` — destino do pagamento
```
{owner: "WhatTheChip Ltd.", net: "USDT · TRC-20",
 addr: "TQ9fH4mVx2Kd7YbLpJs3RnAeW6cUz8gXqN",
 memo: "coloque o código da ordem (SO) no campo de memo/referência"}
```
**Carteira do WhatTheChip, não do vendedor.** Todo pagamento de toda compra vai para este endereço.

### 3.13 `Carrier` — rastreio
Transportadoras com página conhecida (o código vira link): **DHL, FedEx, UPS, SF Express, EMS, Correios**. Fora da lista, o código fica em texto puro copiável — melhor sem link do que com link quebrado.

`carrier` e `track` são **campos separados**. Os formatos de código são incompatíveis entre si; não concatene.

---

## 4. Máquina de estados do lote

```
transit ──[comprador: marcar recebido]──▶ received ──[comprador: fechar resultado]──▶ settled ──[pagamento]──▶ paid
```

| Estado | Quem transiciona | Efeito colateral | Reversível |
|---|---|---|---|
| `transit` | vendedor (fora deste painel) | lote entra na lista do comprador | — |
| `received` | **comprador** | grava `got`; abre a aba Resultado; **o vendedor não pode mais alterar o conteúdo do lote** | **não** |
| `settled` (FATURADO) | **comprador** | grava `done` + `res[]`; lança a **diferença** contra o vendedor; gera a folha do resultado; libera pagamento; **números imutáveis** | **não** (só a plataforma reabre, auditado) |
| `paid` | pagamento que zera o saldo | quita o lote | não |

### 4.1 Regra de entrada na lista
**Só entra lote que o vendedor fechou E despachou**, com transportadora e data de envio. Não existe lote "em aberto" no painel do comprador; o primeiro estado possível é `transit`. Se a lista mostrar lotes não despachados, o painel passa a prometer visibilidade que o negócio não tem.

### 4.2 Duas transições irreversíveis, avisadas antes do commit
O texto do aviso é **parte do contrato**, não decoração:
- ao receber: *"A partir daqui o vendedor não pode mais alterar o conteúdo do lote."*
- ao fechar: *"Depois de fechar, os números não podem mais ser alterados."*

Retorne **409** se a transição vier fora de ordem (`receber` num lote que não está em `transit`; `resultado` num que não está em `received`).

### 4.3 Pagamento parcial não muda o estado
O lote continua `settled`; só a etiqueta vira PARCIAL. `paid` só quando `v >= restUsd − 0.004`.

### 4.4 O trilho tem **cinco** células
`Fechado · Enviado · Recebido · Resultado · Pagamento`

A etapa acesa é a **última alcançada**, não a próxima a fazer: `transit→1`, `received→2`, `settled→4`, `paid→5`.

O comprador **não tem "a despachar"** — é ação do vendedor —, por isso o trilho dele tem cinco e o do vendedor tem seis. Não unifique.

### 4.5 Estado é derivado, nunca decorativo
Em toda a ficha, o estado de um bloco vem **do que ele produziu**: `Resultado` está fechado porque existe `done`; `Pagamento` está concluído porque `restUsd <= 0 && paidUsd > 0`. Se você guardar um campo `stage` e desenhar a partir dele, os dois divergem no primeiro caso de borda.

### 4.6 Ação pendente × estado
A pastilha de **chamada** aparece só para quem tem de agir. Ato do outro lado do balcão é **estado**, e estado é neutro (com `title` dizendo de quem é a bola).

Na lista do comprador:

| Estado | Pastilha |
|---|---|
| `received` | **chamada** `CONFERIR` (azul — ato sobre a caixa) |
| `settled`/`paid` com `restUsd > 0` | **chamada** `PAGAR` (âmbar — ato sobre dinheiro) |
| `transit` | estado, `title: "a caminho — nada a fazer ainda"` |
| quitado | estado, `title: "encerrado"` |

A cor diz a **natureza do ato**, nunca quem o pratica: **azul = caixa, âmbar = dinheiro**.

---

## 5. Endpoints

Nomes são sugestões; a **forma** não é.

### 5.1 Preços

```
GET  /parceiro/precos/
     → [{key, name, desc, form, range, by, lines, miss, block}]
     + block_total: {types, orders, units}

GET  /parceiro/precos/<key>/
     → tipo completo: form, brands[], caps[], groups,
       rows: [{label, sub, state, price|[min,max]|por_marca, review?, blocks?}]
     Chave inválida ⇒ 302 para o Resumo, preservando a query de sessão.

POST /parceiro/precos/<key>/
     ← {changes: [{field, value}]}          (só as células alteradas)
     ⇒ cria um pedido de revisão por linha
     → {reviews_created: N}
```

**Regras:**
- A página inteira é um formulário e **o servidor faz o diff**. O cliente manda só o alterado.
- **Idempotente por conteúdo**: reenviar o mesmo valor não cria pedido novo.
- Nomes de campo: `p<id>`, `pmax<id>`, `pmin<id>`, com `id = 1200 + índice_do_tipo_na_lista_canônica × 100 + contador`. Derive do índice, **não de um mapa literal** — mapa exige lembrar cada tipo novo em dois lugares, e um tipo sem entrada fez a base virar `undefined`, todo `pk++` dar `NaN` e 14 campos colapsarem em dois nomes, sem erro no console.
- Máscaras de entrada (validar server-side também):
  - normal: `^(|x|X|\d{0,6})$`
  - linear (SSD): `^(|x|X|\d{0,4}([.,]\d{0,2})?)$` — vírgula normaliza para ponto
- Caracteres fora da máscara são **removidos**, não rejeitados com erro. `X` normaliza para `x`.
- `null` (não fabricado) **não aceita valor**. Rejeite.

**Chave de tipo:** a regex é `[a-z0-9]+`, **não** `[a-z]+` — chave de chip tem dígito (`k9`). Com `[a-z]+` o `k9` virava `k`, não batia com nada e a página caía num tipo padrão sem erro. Chave desconhecida ⇒ redirect ao Resumo, nunca fallback silencioso.

**Contagem de cobertura** (`lines` / `miss`): `lines` = células editáveis (exclui `null` e cabeçalhos de seção); `miss` = células `""`. **`"x"` conta como cotado** — é decisão tomada.

### 5.2 Catálogo

```
POST /parceiro/catalogo/
     ← {types: [key], lang, currency, valid_until, gaps: "hide"|"dash", cover_note}
     ⇒ PDF (ou job + polling)
```

- **Seleção por exclusão, não por inclusão.** O estado é um mapa de *excluídos* — um tipo novo entra no catálogo automaticamente.
- Filtros de tela: busca por nome/descrição; cobertura (`all` / `full` / `gap`).
- `lang`: **中文 simplificado é a primeira opção** — o comprador é chinês.
- `currency`: `¥ RMB` ou `¥ RMB + US$ ≈`.
- `gaps`: ocultar linhas sem cotação, ou publicar como `—`.
- **Carimbo de taxa no rodapé de cada página**: `mid-market 01/08 · 1 ¥ ≈ US$ 0.1478`.
- Sob câmbio `none`, a opção `¥ RMB + US$ ≈` **não pode gerar coluna de dólar**.
- Zero tipos selecionados ⇒ geração desabilitada.

### 5.3 Compras — a lista

```
GET  /parceiro/compras/
     ?q= &status= &period=any|d30|d7|custom &from= &to=
     &sort=n|seller|so|units|val|usd|due &dir=asc|desc
     &page= &per=10|25|50
     → {rows[], total, counts_by_status{}, badge}

GET  /parceiro/compras/export.csv    → o MESMO recorte filtrado, 14 colunas
```

**Colunas da lista:** `Lote (código + selo de origem)` · `Cliente` · `Ordem (código + data)` · `Chips` · `Total ¥` · `Total US$` · `Resultado` · `Status` · chevron.

- **Busca** casa contra: código do lote, código da ordem, cliente, país, cidade, transportadora, rastreio — um único `haystack` minúsculo.
- **Status** traz a **contagem embutida** em cada opção (`"A conferir (2)"`), e as contagens vêm do **conjunto completo**, não do filtrado.
- **Período** filtra pela data de **despacho** (`ship`) — mesma convenção de Estoque e Vendas.
- **Ordenação** default `n` descendente (lote mais novo primeiro). Lotes sem resultado ordenam por `-1` na coluna Resultado, o que os afunda — proposital.
- **Coluna Resultado é dupla**: valor + sub-linha `falta US$ N` (âmbar) ou `quitado` (verde). Antes do fechamento mostra `—`, **não zero**.
- **Vazio**: `"Nenhum lote encontrado / Ajuste a busca ou os filtros acima."` — nunca tabela vazia sem explicação.
- Trocar filtro, busca ou por-página volta para a página 1.

**CSV**, 14 colunas, separador `;`, BOM UTF-8, nome `compras-<comprador>.csv`:
```
Lote · Ordem · Categoria · Cliente · País · Transportadora · Rastreio · Chips ·
CNY total · Taxa travada · USD total · CNY resultado · USD a pagar · Status
```
As colunas de resultado saem **vazias** para lotes não fechados.

**Badge do nav** (`[data-buys-badge]` no item "Compras"):
```
badge = (lotes st=received) + (lotes st∈{settled,paid} com restUsd > 0)
```
Caixas a conferir + dívidas em aberto. **Não conta** `transit` (nada a fazer) nem quitados. Zero ⇒ **string vazia**, não `0`. Um único endpoint/context processor — toda tela do painel recalcula no load.

> ⚠️ Observação de desenho, para quando houver volume real: se a maioria das linhas virar chamada, a cor de chamada deixa de chamar. Nesse caso, a chamada deve ser só a **mais antiga em atraso** por tipo de ato, não toda linha elegível.

### 5.4 Ficha do lote

```
GET  /parceiro/lote/<code>/
     → identidade, datas, carrier/track, lock/lockD,
       lines[], res[]?, pays[]?, notes[], pns[], boxes_used{}

POST /parceiro/lote/<code>/receber
     ← {}
     ⇒ st=received, got=hoje, res inicializado com as quantidades declaradas
     409 se não estiver em transit

POST /parceiro/lote/<code>/resultado
     ← {res: [qtd_aprovada por linha], note?: "<texto opcional>"}
     ⇒ st=settled, done=hoje, grava a diferença, gera a folha do resultado
     409 se não estiver em received
     Validar 0 ≤ res[i] ≤ lines[i].qty por linha, SERVER-SIDE

POST /parceiro/lote/<code>/pagamento
     ← multipart {usd, file}
     ⇒ append em pays[]; kind derivado; st=paid se zerou
     Validar 0 < usd ≤ restUsd (tolerância 0.004) E arquivo presente

POST /parceiro/lote/<code>/observacao      ← {text}
DEL  /parceiro/lote/<code>/observacao/<i>  (só o autor)

GET  /parceiro/lote/<code>/resultado.pdf
GET  /parceiro/lote/<code>/<aba>.csv       (lines|chips|cats|pays|notes)
```

**As quatro mutações precisam de chave de idempotência.** O comprador está em rede instável e vai clicar duas vezes. Um pagamento duplicado é dinheiro perdido.

**Nunca confie no cliente para:** `kind` do pagamento, `lock`, `dueUsd`, código do lote, código da ordem, autoria e data de observação, contagem da badge, `by` do pagamento.

---

## 6. A ficha — comportamento que o backend tem de suportar

Uma única UI para todas as etapas. A folha do registro e as abas **nunca mudam de forma**: o que muda é o que está aceso.

### 6.1 Os três heróis — **Esperado × Final × Diferença**
| Herói | Valor | Legenda |
|---|---|---|
| **Resultado esperado** | `cny` (imutável) | `1.970 un. · fechado em 27/07` |
| **Resultado final** | `okCny` (vivo, congela na fatura) | `−¥ 405 contra o esperado` / `sem diferença` |
| **Saldo a pagar** | `restUsd` | `45% pago · US$ 1.462 já pagos` |

- Esperado é **o preço fechado com o cliente**, o número que ele tinha na mão quando a caixa saiu. Um número só, mudando, apagaria a referência — e é contra a referência que se discute uma recusa.
- A **diferença** vive na legenda, não numa quarta célula: ela é a conta entre os dois números acima.
- Célula sem dado mostra `—` **e diz o que falta** (`"depois do recebimento"`, `"depois do resultado"`), nunca zero fingindo ser número.
- Quando o saldo zera, o rótulo vira **"Quitado"**.

### 6.2 As quatro caixas de etapa
`Lote · Despacho · Resultado · Pagamento`. Estado de cada uma: `done` / `now` / `next`, **derivado do dado**:

| Caixa | `done` quando | Campos |
|---|---|---|
| Lote | sempre | ordem, origem, volume, conteúdo (`N tipos · M linhas`) |
| Despacho | existe `got` | transportadora, enviado, recebido, câmbio travado + **rastreio clicável ou copiável** |
| Resultado | existe `done` | fechado em, aprovados, recusados, diferença |
| Pagamento | `restUsd ≤ 0 && paidUsd > 0` | bruto, serviço, líquido, recebido + **copiar carteira** |

Caixas apagadas trazem a frase que explica **quando acendem**.

**Identificador longo em célula estreita corta no MEIO, nunca no fim** (`TQ9fH4mVx…z8gXqN`): a cauda é justamente o que se confere contra a carteira. Vale para endereço de carteira, código de rastreio e hash de transferência. O valor inteiro vai no `title`.

### 6.3 As cinco abas
| Aba | Contador | Disponível |
|---|---|---|
| **Resultado** | linhas do lote | sempre (default) |
| **Chips** | part numbers | sempre |
| **Categorias** | caixas usadas neste lote | sempre |
| **Pagamentos** | pagamentos | **só quando `settled` ou `paid`** |
| **Observações** | notas | sempre |

Aba indisponível fica **desabilitada e visível**, com contador `—` e `title="disponível quando o resultado fechar"`. Não desaparece: o comprador precisa saber que existe.

### 6.4 Aba Resultado — o lançamento

**A regra que define o desenho: o comprador digita SEMPRE o que RECUSOU** — a exceção, quase sempre zero — **e o aprovado se calcula sozinho. Lote perfeito = nenhuma tecla digitada.**

- `res[]` guarda a **quantidade aprovada**; o input mostra `qty − res[i]` (o recusado).
- **Vazio significa zero recusas.**
- `rej > qty` marca o campo e **satura** em `res[i] = 0` — clampa, não rejeita.
- `Enter` e `↓` descem para a próxima linha; `↑` sobe. É entrada de planilha, não de formulário.
- **"Limpar recusas"** zera tudo e aprova o lote inteiro.
- Recálculo **ao vivo, só o que mudou**: célula de recusado, de aprovado, de valor da linha, subtotais do grupo, três totais do rodapé, e os heróis. Não repinta a tabela.

**Agrupamento por MARCA**, com subtotal por faixa e total de cada coluna no rodapé fixo.

**Colunas:** `Tipo · Capacidade · Caixa WTC · Enviados · ¥ unit. · ¥ esperado` e, depois do recebimento, `Recusados (editável) · Aprovados · ¥ resultado`. Antes do recebimento as três últimas **não existem** — a tabela é a mesma, mais curta.

Não há coluna `US$ ≈` nesta planilha: duas escalas de dinheiro na mesma linha é o que a tabela do sistema existe para evitar.

**No telefone (≤600px)** a planilha vira cartão, na ordem do trabalho de bancada: tipo/capacidade/caixa → `enviados N` → **o campo** (48px de altura, rótulo próprio) → `aprovados` + `¥ resultado`. Preço unitário e esperado saem — são referência, e referência não se lê com o dedo ocupado. Uma **barra viva** grudada no rodapé mostra o resultado final e a diferença, porque no telefone os heróis já rolaram para fora da tela.

### 6.5 Aba Chips
Cada part number com fabricante, specs de identificação, caixa WTC, quantidade e valor. Agrupado por tipo. **Somente leitura.** Serve para conferência física: o comprador tem a peça na mão, lê o PN, acha a linha.

Todo PN de uma linha é **do fabricante daquela linha** — a linha tem marca, e sortear PN de outra marca contradiz a própria linha.

### 6.6 Aba Categorias
Dicionário da convenção: `Categoria · Caixa WTC · Tipo · O que entra · Nesta compra`.

- As caixas desta compra vêm marcadas **com a quantidade**, não com um visto: dizer "veio" é menos do que dizer quanto veio, e é a quantidade que se confere contra a bancada.
- Caixa fora do dicionário entra no fim, marcada.
- **Leitura apenas** — a convenção é da plataforma, não do comprador.

### 6.7 Aba Pagamentos
Três blocos: **carteira de destino**, **saldo desta compra**, **tabela de parcelas**.

- Carteira do WhatTheChip, com o aviso explícito: *"Você paga o WhatTheChip, nunca o vendedor direto. Confira os seis primeiros e os seis últimos caracteres antes de enviar: transferência em blockchain não volta."*
- Saldo: resultado / já pago / restante, cada um no par `¥ = US$`, com barra de progresso calculada **em US$**.
- Tabela: `Data · Registro · Valor pago (¥ = US$) · Referência · Registrado por · Comprovante`.
- Vazio: *"Nenhum pagamento registrado. Envie o valor em US$ para a carteira acima e lance aqui — parcial ou integral, sempre com o comprovante anexado."*

### 6.8 Modal de pagamento
Campos: **valor em US$** e **comprovante**. Ambos obrigatórios — confirmar só habilita com `v > 0 && v <= restUsd + 0.004 && arquivo`.

- Resumo: **ordem (SO)** — é a referência do memo —, resultado (`¥ = US$`), já pago, **restante** destacado.
- Endereço da carteira, copiável, dentro do modal.
- Entrada aceita decimal, normaliza vírgula, máx. 12 caracteres, um único ponto.
- **Atalhos 25% / 50% / Restante** — o terceiro traz o valor exato do saldo.
- Conversão viva `= ¥ N` pela **taxa travada**, **sem `≈`**: com taxa travada a conversão é exata.
- Acima do saldo: campo em vermelho + `"acima do saldo · máx US$ N"`. Não trunca, não aceita.
- Rótulo do botão muda: **"Registrar quitação"** quando fecha o saldo, **"Registrar pagamento parcial"** quando não.
- Anexo: PDF/PNG/JPG até 10 MB. *"sem comprovante o pagamento não entra"* — a regra, não um aviso.

### 6.9 Aba Observações
Campo de texto + botão; `⌘/Ctrl+Enter` registra; botão desabilitado com campo vazio. Cada nota grava **autor e data**, e é removível pelo autor. **Tudo aqui é impresso no PDF do resultado.**

A observação opcional do **diálogo de fechamento** entra nesta mesma lista — não num campo próprio, que criaria dois lugares onde procurar o que o comprador escreveu.

### 6.10 Exportação CSV
Exporta **a aba aberta**. Separador `;`, BOM UTF-8, nome `<CODIGO>-<aba>.csv`.

| Aba | Colunas |
|---|---|
| Resultado | `Marca · Tipo · Capacidade · Caixa WTC · Enviados · CNY unit. · CNY esperado` (+ `Recusados · Aprovados · CNY resultado` depois do recebimento) |
| Chips | `Part number · Fabricante · Caixa WTC · Identificação · Chips · CNY unit. · CNY total` |
| Pagamentos | `Data · Registro · USD pago · CNY equivalente · Referência · Registrado por · Comprovante` |
| Observações | `Data · Autor · Observação` |

---

## 7. Documentos gerados

### 7.1 Folha do resultado — **o comprador gera, o CLIENTE recebe**
Este é o documento mais sensível do painel, porque atravessa o balcão. **Três coisas que a tela mostra e ele não pode ter:**

1. **Pagamentos** — são a perna comprador → WhatTheChip, e o cliente não vê nem que ela existe. Ficam na aba e no CSV, que são internos.
2. **Nome do comprador** — a autoria das observações vira **"Conferência"**. O cliente sabe que alguém conferiu; não pode saber quem comprou.
3. **Linguagem de fatura** — o selo da tela diz FATURADO/PARCIAL (estado de cobrança). No documento o estado é **do documento**: `EM CONFERÊNCIA` ou `CONFERIDO`. O rodapé também não nomeia quem gerou.

Conteúdo, em ordem:
1. Cabeçalho: "Resultado do lote", código, vendedor/cidade/país, estado do documento, data de emissão.
2. Duas colunas: ordem, origem, transportadora, rastreio, fechado, recebido | câmbio travado, enviados, recusados, aprovados, diferença.
3. Faixa de três números: **Resultado esperado · Resultado final (azul claro) · Diferença (amarelo claro)**. Aqui a diferença tem **célula própria** — no papel não há legenda para pendurá-la, e é ela que o cliente vai querer discutir.
4. Tabela `Resultado por marca, tipo e capacidade`, agrupada, com `tfoot` de totais.
5. Observações da conferência.
6. Rodapé: `WhatTheChip · LOT/044/07/26 · SO/0131/07/26 · valores em ¥ (RMB) na taxa travada de 04/07 · documento de conferência emitido em 01/08/26`.

**A folha nasce no fechamento** do resultado, automaticamente.

**Cores de papel são literais, não tokens.** Papel não tem modo escuro — com token de tema a célula sai azul-marinho quando a tela está no escuro.

### 7.2 Catálogo de preços
Ver §5.2. Gerado sob demanda, com carimbo de taxa por página.

---

## 8. Invariantes de leitura — viram constraints no banco

O protótipo costura estas quatro na leitura porque override antigo fica preso no navegador do usuário. **No backend, são constraints e migrações** — o dado não deve poder existir errado.

1. **Formato do lançamento.** Pagamento em ¥ convertido pela taxa travada para US$; parcela `full` absorve a sobra de centavos (migrar preserva o que o lançamento **significava** — sem isso um lote quitado passa a dizer "PARCIAL").
2. **Cadeia de datas.** `closed → ship → got → done → pagamentos`, cada elo limitado a hoje e **nunca antes do anterior**. O primeiro elo é o **fechamento**: a caixa não pode sair antes de o lote existir.
3. **Alinhamento do resultado.** `res` tem de corresponder a `lines`. No protótipo, comprimento incompatível descarta o override; no banco, **use `line_id`** e o problema não existe.
4. **Coerência de estado.** Estado antes da confirmação não pode ter transportadora nem data de envio. Estado com resultado tem de ter `done`. Etc.

O princípio: **o sistema se conserta sozinho em vez de deixar o defeito preso na frente de quem está olhando.**

---

## 9. Vocabulário — o que nunca traduz

`eMMC · eMCP · uMCP · LPDDR · UFS · DDR · SSD · K9 · PHONE · PCB · TLC · QLC · NVMe · SATA · M.2`, part numbers e nomes de fabricante são **canônicos em qualquer idioma**. O painel é multi-idioma (`pt-br · es · en · zh-hans`) e nenhum destes tokens entra no arquivo de tradução.

**Mono** (fonte monoespaçada) para: código de lote, código de ordem, part number, endereço de carteira, hash, quantidade e valor. Prosa em sans.

---

## 10. Andaimes do protótipo — **NÃO implementar**

Existem para demonstrar a UI e não são funcionalidade:

1. **`demobar`** — a barra "Demo · estado do lote" no fim da ficha. Leva o mesmo lote por todas as etapas. **Não vai para produção**; em produção as transições vêm das ações reais.
2. **Overrides em `localStorage`** (`wtc_buys`) — o protótipo persiste mutações no cliente com um mapa `n → patch`, e `null` significa "limpar de volta ao base". Em produção isso é o banco.
3. **`pns()` com gerador pseudoaleatório semeado** — os part numbers são **inventados deterministicamente** (mesma semente ⇒ mesma lista, para o lote não mudar de conteúdo ao recarregar). Em produção vêm da triagem do vendedor.
4. **`fakeRef()`** — hash de transferência sintético. Em produção vem da blockchain.
5. **`TODAY = "01/08"`** e `new Date(2026,7,2)` — datas cravadas. Trocar por data do servidor, no fuso do usuário.
6. **Widget de câmbio clicável** — cicla os quatro estados de taxa para demonstração. Em produção o estado vem do serviço de câmbio.
7. **Máscara no cliente** (`[data-wtc-needs]`) — em produção o endpoint **omite o campo**, não o esconde no template.
8. **Fixtures** de `parceiro-compras.js`, `parceiro-data.js` e `wtc-categorias.js` — a estrutura é boa, os valores são ilustrativos. As **letras da categoria** são inventadas.

---

## 11. Checklist de aceite

**Preços**
- [ ] Os quatro estados de célula existem no banco e na API, com `null` não editável.
- [ ] `"x"` conta como cotado nas contagens; `""` conta como lacuna.
- [ ] eMCP/uMCP têm faixa; K9 tem **uma** linha; SSD calcula capacidades e marca o piso.
- [ ] eMMC devolve **duas** grades, com rótulos distintos de 1ª coluna.
- [ ] Diff no servidor; POST idempotente por conteúdo; contagem de células alteradas.
- [ ] Linha em revisão devolve o **preço vigente**, e o vendedor lê o vigente.
- [ ] Chave de tipo inválida redireciona ao Resumo (regex `[a-z0-9]+`).
- [ ] `BlockedQuote` distingue lacuna de pedido travado, com `orders`, `units` e `since`.

**Compras**
- [ ] Só lotes despachados aparecem.
- [ ] Período filtra pela data de **despacho**.
- [ ] Contagens de status vêm do conjunto completo, não do filtrado.
- [ ] Coluna Resultado devolve `null` antes do fechamento, não zero.
- [ ] CSV exporta o recorte filtrado, 14 colunas, `;` + BOM.
- [ ] Badge = a conferir + com saldo em aberto; zero ⇒ vazio.

**Ficha**
- [ ] `received` e `settled` são irreversíveis e retornam 409 fora de ordem.
- [ ] Trilho com **cinco** etapas; a acesa é a última alcançada.
- [ ] Heróis devolvem Esperado, Final e Diferença — e `null` + motivo quando não há dado.
- [ ] Aba Pagamentos indisponível (mas listada) antes do fechamento.
- [ ] O campo digitado é **recusado**; vazio = zero; clamp em `qty`; validação server-side por linha.
- [ ] O devido é o **resultado**, nunca o declarado.
- [ ] Todo US$ do lote usa a taxa **travada**.
- [ ] Pagamento exige `usd > 0`, `≤ restUsd`, **e** comprovante; `kind`, `ref` e `by` resolvidos no servidor.
- [ ] Pagamento parcial mantém `settled`; etiqueta vira PARCIAL; nunca PAGO com saldo.
- [ ] Saldo arredondado no centavo, em US$, tolerância `0.004`.
- [ ] Observação do diálogo de fechamento entra na lista de observações.
- [ ] Observações saem no PDF, com data — e autoria como **"Conferência"**.
- [ ] As quatro mutações aceitam chave de idempotência.

**Documentos**
- [ ] Folha do resultado **sem pagamentos, sem nome do comprador, sem linguagem de fatura**.
- [ ] Estado do documento é `EM CONFERÊNCIA` / `CONFERIDO`.
- [ ] Folha gerada automaticamente no fechamento.
- [ ] Catálogo com carimbo de taxa por página; `none` não gera coluna de dólar.

**Transversal**
- [ ] ¥ inteiro / US$ 2 casas / taxa 4 casas, server-side.
- [ ] `≈` significa estimativa; valor com câmbio travado sai sem til.
- [ ] Câmbio `none` não inventa número em nenhum endpoint.
- [ ] Nenhum termo canônico traduzido em nenhum dos 4 idiomas.
- [ ] Perna 2 e taxa de serviço **ausentes** de toda resposta do comprador.
- [ ] Demobar, `localStorage`, `pns()` semeado, `fakeRef()` e datas fixas **não** foram para produção.

---

## 12. Decisões que valem revisão com o app na mão

Três respostas que dei por conta própria durante o design, e que são **rename, não redesenho**:

1. **As letras da categoria** (`E M U L F D K S`) são inventadas. Moram em `LETTER`, num lugar só.
2. **O agrupamento da conferência por marca** mudou a granularidade da linha do lote. Se o app agrupa diferente, é `byBrand()` → outra função — mas a linha precisa continuar tendo marca.
3. **Oito estados onde o briefing nomeia seis.** Dois pares que o protótipo separa estão colapsados no briefing: `a conferir` cobre *a caminho* + *chegou*, e não há estado para *resultado pronto, a aceitar*. Se o app tem exatamente seis, diga quais pares fundem.

E duas perguntas que nunca foram respondidas:
- **Quem aprova** o pedido de revisão de preço — a plataforma sempre, ou automático com teto?
- O comprador pode **contestar** um lote inteiro, em vez de só recusar linhas?
