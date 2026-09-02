# Convenção de identificadores de documento — LOT e SO

> **⚠ STATUS: ESPECIFICAÇÃO. NADA DISTO ESTÁ IMPLEMENTADO.**
> Este arquivo descreve o que foi DECIDIDO em 2026-09-01, não o que o código faz
> hoje. Não o indexe no `CLAUDE.md` nem em outro doc antes de a implementação
> estar no ar — o `CLAUDE.md` é onboarding do que EXISTE, e apontar para uma
> convenção não construída faz o próximo agente programar contra ficção.
>
> Quando estiver implementado: mova o conteúdo essencial para o `CLAUDE.md §6`
> (convenções) e registre as armadilhas no `§7`. Este arquivo então some — ele é
> a ponte entre a decisão e o código, não uma bíblia permanente.
>
> **Plano de execução (decisões do dono de 2026-09-02 já aplicadas):**
> `PLANO_CONVENCAO_IDENTIFICADORES.md`.

---

## 1. A forma

```
LOT-2026-0041                    lote
EMIN-SO-2026-0004                ordem de venda
```

Gramática: `[CÓDIGO-EMPRESA-]TIPO-AAAA-NNNN`

| Token | Regra |
|---|---|
| `CÓDIGO-EMPRESA` | 4 letras maiúsculas, de `Company.code`. **Só na SO.** O lote não tem. Empresa sem código → formato legado (ver §3). |
| `TIPO` | `LOT` ou `SO`. Vocabulário fechado. |
| `AAAA` | Ano com **quatro** dígitos. |
| `NNNN` | Número com zero-padding em 4 dígitos, **reiniciando a cada ano**. |

---

## 2. As regras que não são óbvias

Estas são as que se perdem se ninguém escrever. Cada uma foi decidida por um
motivo, e o motivo está no §6.

**2.1 — O ano é o da ABERTURA do lote.**
Não o do fechamento, não o do despacho. É de onde o `Lot.code` já tira hoje
(`created_at`). Um lote aberto em dezembro de 2026 e fechado em fevereiro de
2027 é `LOT-2026-00NN`.

**2.2 — A SO HERDA o ano do lote dela.**
Não o ano da própria criação, nem o do despacho. A venda é o acerto daquele
lote; um lote de 2026 vendido em janeiro não virou campanha de 2027.

**2.3 — O número reinicia a cada ano.**
A chave de unicidade deixa de ser `(empresa, número)` e passa a ser
`(empresa, tipo, ano, número)`. O `DocSequence` ganha uma linha por ano.

**2.4 — ⚠ O contador de um ano pode andar DEPOIS que o ano acabou.**
Consequência direta de 2.2 + 2.3, e é a regra menos intuitiva de todas: como a
SO puxa o número do contador **do ano do lote**, um lote aberto em dezembro de
2026 e vendido em fevereiro de 2027 consome o próximo número de **2026**, em
fevereiro de 2027. Alguém vai olhar isso em março e achar que é bug. **Não é.**

**2.5 — O lote NÃO leva prefixo de empresa.**
Porque o código do lote é número interno. Isto só é seguro junto com a mudança
de tela do §5 — sem ela, reabre uma colisão conhecida (§6.4).

**2.6 — O prefixo sai de um CAMPO, nunca do nome.**
`Company.code` é armazenado, único entre os preenchidos e editável. Derivar do
nome a cada render faria renomear a empresa renomear todos os documentos dela.

---

## 3. Empresa sem código

`Company.code` vazio é o marcador de legado. Com ele vazio, o documento cai no
**formato antigo** — nunca num código quebrado do tipo `-SO-2026-0004`. Ninguém
é forçado a ter código.

---

## 4. O que NÃO muda

- **A sequência e os números existentes.** Reescreve-se a GRAFIA, não a
  numeração. E, como tudo que existe hoje é de 2026, aplicar o reinício anual
  agora **não renumera absolutamente nada** — a regra só passa a ter efeito em
  1º de janeiro de 2027. É a hora mais barata que vai existir.
- **Número emitido nunca se reusa.** Mesma regra dos códigos de caixa (F12).

---

## 5. O que viaja JUNTO — é uma entrega só

Tirar o prefixo de empresa do lote **só é seguro** porque o lote sai da tela do
comprador. Hoje ele é a **primeira coluna** do painel dele, e sem prefixo o lote
1 de dois clientes vira a mesma string.

Portanto, na mesma entrega:

- [ ] O lote **sai** da tabela do painel do comprador; a **ordem** vira a
      primeira coluna.
- [ ] O lote continua **buscável** por ele, mesmo fora da tabela — quem tem um
      packing list antigo na mão precisa achar.
- [ ] A busca aceita **as duas grafias**, a nova e a legada. **Obrigatório, não
      opcional** (§6.5).

---

## 6. As decisões, e o que foi recusado

**6.1 — Por que ano de quatro dígitos, e por que ele saiu do meio.**
O formato antigo era `LOT/041/08/26`. Ler `08/26` exige saber que é mês/ano
*nessa* ordem — e essa ambiguidade **já mordeu este projeto**: a planilha mestra
da eMiner trazia `2026-04-07` com mm/dd trocado, e a data do LOT/004 teve de ser
confirmada na mão com o dono. O comprador é chinês; `2026` não tem como ser lido
ao contrário.

**6.2 — Por que o ano ANTES do número.**
Porque a alternativa não ordena. Como texto, `LOT-0001-2027` vem **antes** de
`LOT-0041-2026` — a comparação bate no `0` contra o `4` antes de chegar no ano.
Numa pasta de packing lists ordenada por nome, ou numa planilha ordenada pelo
código, os anos se misturam. É a mesma razão pela qual o Odoo escreve
`INV/2026/00001` e não `INV/00001/2026`.

**6.3 — Por que o prefixo vem do `Company.code` e não das "4 primeiras letras".**
Duas razões. Renomear a empresa não pode renomear os documentos dela. E "as 4
primeiras letras" **colide**: *Recicladora Sul* e *Recicladora Norte* dão `RECI`
as duas. É um código de 4 letras **semeado** pelo nome, com a colisão resolvida
por quem cadastra — não uma fatia do nome.
⚠ Escolher o código de cada empresa é decisão que se toma **uma vez**: mudar
prefixo depois que a numeração está em uso repercute em tudo (é o aviso que o
próprio NetSuite dá na documentação de numeração por subsidiária).

**6.4 — Por que tirar o prefixo do lote exige tirá-lo da tela.**
O código de empresa entrou nos documentos em agosto/2026 exatamente para matar
uma colisão real, registrada no `tenancy/doc_code.py`: *"o comprador, que lê
ordens de várias empresas, via dois `LOT/001/08/26` na lista dele"*. O segundo
cliente (eRecyclo) deixou de ser hipótese. Tirar o prefixo mantendo a coluna
reabre o bug.

**6.5 — Por que a busca DEVE aceitar as duas grafias.**
O `code_str` é congelado de propósito, e o motivo está escrito no próprio
`doc_code.py`: *papel já impresso não pode divergir da tela*. Reescrever os
antigos rompe isso — o packing list que viajou para Macau diz `SO/004/08/26`. A
busca aceitando as duas grafias é o que impede que toda referência antiga
(WhatsApp, packing list, print recortado) fique órfã. Sem ela, esta mudança
destrói rastreabilidade.

**6.6 — O que o código deixa de dizer.**
O identificador da SO não diz mais **quando a venda aconteceu** — diz o ano da
campanha do lote. A data da venda vive em `shipped_at` (despacho) e no
`settled_at` do acerto. Está na tela e no PDF; só saiu do nome.

**6.7 — Formatos recusados, e por quê.**
- `LOT/EMIN/041/08/26` — o que sairia "de graça" ao preencher o código da
  eMiner. Mais longo que o antigo, menos legível que o novo, e mantém a data
  ambígua. É o pior dos três.
- `EMIN-LOT-2026-0041` — lote com prefixo, para ficar simétrico à SO. Recusado:
  fica parecido demais com a SO, que é justamente a confusão que originou toda
  esta conversa.
- `LOT-0041-2026` (ano no fim) — recusado por 6.2.
- Sequência perpétua com o ano só como enfeite — recusado: quem vê um ano colado
  num número de 4 dígitos espera que reinicie, e reiniciar mantém o número
  legível para sempre.

---

## 7. Onde mora no código

| Peça | O que fazer |
|---|---|
| `tenancy/doc_code.py` | Fonte única. O formato vira um **mapa por tipo de documento** (`{'LOT': …, 'SO': …}`), **não um `if`** — mesma forma do `Lot.ORIGIN_ICONS`. Tipo novo = uma linha, nenhum ramo muda. |
| `tenancy/models.py` | `Company.code` já é `max_length=4`. Mudar só a **semente** de 3 para 4 letras (`suggest_company_code`), e apenas para empresa NOVA. |
| `vendas/models.py` — `DocSequence` | Ganha o ano na chave: `unique (company, kind, year)`; `next_number(company, kind, year)` mantendo o `select_for_update`. |
| `vendas/models.py` — `SalesOrder` | O ano do código vem do **lote**, não do próprio `created_at`. |
| `tenancy/management/commands/backfill_doc_codes.py` | Já existe e já reescreve `code_str`. Estender para o formato novo; **idempotente**. |
| `vendas/services.py` — `purchase_haystack` | Indexar a grafia nova **e** a legada. |
| Painel do comprador | Lote sai da tabela; ordem vira primeira coluna (§5). |

⚠ **Prazo real:** a mudança da chave de unicidade tem de estar no ar **antes de
1º de janeiro de 2027**. Depois disso, o primeiro documento do ano novo colide
com o número 1 do ano velho.

---

## 8. Travas obrigatórias

Sem estas, a convenção não está entregue. Cada garantia precisa passar por
**mutação individual** — neste projeto já houve trava que existia e não
protegia nada.

**Suíte (SQLite — contrato):**
- [ ] O formato dos dois documentos, com e sem código de empresa.
- [ ] Empresa **sem** código cai no formato legado.
- [ ] Colisão de prefixo entre duas empresas é recusada no cadastro.
- [ ] A SO herda o ano do lote — **incluindo** o caso que motivou a regra: lote
      aberto em dezembro, ordem criada em janeiro.
- [ ] O número reinicia na virada do ano.
- [ ] ⚠ O contador de 2026 continua andando em 2027 quando o lote é de 2026
      (§2.4) — é o comportamento correto e precisa de teste, senão alguém
      "conserta" isso.
- [ ] A busca acha pela grafia nova **e** pela legada.
- [ ] O lote continua buscável mesmo fora da tabela do comprador.

**Réplica (Postgres com papel restrito — RLS real):**
- [ ] O backfill dos `code_str` roda sobre os documentos reais e é
      **idempotente**: rodar duas vezes não empilha nem altera.
- [ ] A nova constraint de unicidade aplica sem violação nos dados existentes.

**Mutação (cada uma tem de MORDER):**
- [ ] Derivar o prefixo do nome em vez do `Company.code`.
- [ ] Deixar a SO usar o próprio ano em vez do ano do lote.
- [ ] Tirar a grafia legada da busca.
- [ ] Não reiniciar o número na virada do ano.
- [ ] Dar prefixo de empresa ao lote.

---

## 9. Relação com o plano de aposentar a INV

**Nenhuma — de propósito.** Esta convenção é mudança de grafia, sem risco de
dinheiro; aquele plano é migração contábil. Riscos independentes viajam em
deploys independentes: quando algo quebrar, você precisa saber qual das duas
mudanças causou.

**Esta vem ANTES.** Assim a caracterização que abre o plano da INV já nasce com
o formato final, e a rede daquele plano continua medindo só o que ela deve medir.
