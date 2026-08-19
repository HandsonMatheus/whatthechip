# DESIGN_SYSTEM.md — o pacote v2 dentro deste projeto

> O dono entregou o **WhatTheChip Design System** (pacote de aplicação da v2)
> em 2026-08-19 e a ordem foi: *"quero começar a adaptar os usuários ao novo
> design system — comece pela tela de compras do comprador"*. Este arquivo diz
> ONDE ele mora, COMO se usa aqui e o que já foi vestido.

## 1. Onde mora

    static/wtc/wtc.css              entrada única: importa tokens/ + components.css
    static/wtc/tokens/              fonts · colors · typography · spacing · controls · motion
    static/wtc/components.css       .btn .tag .dtab .shell .rhead .mbox .tbar .pgn .mval …
    static/wtc/patterns/parceiro.css   painel do PARCEIRO (.pshell, .papp, .pside, .brow…)
    static/wtc/patterns/ficha.css      página interna de um registro (ainda não usada)

O pacote entrou **como veio**, sem edição — inclusive os comentários, que são
metade do valor dele. Duas coisas ficaram de fora de propósito:

· **as artes da marca** (`assets/`): já existiam em `static/img/`, byte a byte
  iguais. Duas cópias da mesma marca é duas fontes de verdade — quando ela
  mudar, uma fica para trás. Ver `static/wtc/assets/LEIA-ME.txt`.
· **o `smoke-test.html`**: página de teste do pacote, não do produto.

## 2. Como se linka

```html
<link rel="stylesheet" href="{% static 'wtc/wtc.css' %}">
<link rel="stylesheet" href="{% static 'wtc/patterns/parceiro.css' %}">
```

**A ordem não é estética.** Tokens declaram as variáveis, componentes consomem,
padrão consome os dois. Invertida, toda regra cai em `var()` vazio e a página
sai sem cor — sem UM erro no log. Há teste segurando isso
(`DesignSystemNaTelaDoCompradorTests.test_a_pagina_carrega_o_PACOTE_e_na_ordem`).

O padrão vai em `<link>` próprio em vez de descomentar o `@import` de dentro do
`wtc.css`: assim a próxima versão do pacote entra por cópia, sem merge.

As duas famílias (**Manrope** + **IBM Plex Mono**) vêm do Google Fonts e não
estão no pacote. Sem elas tudo cai em system-ui e a densidade muda.

## 3. O que já está vestido

| Superfície | Estado |
|---|---|
| `/partner/` — compras do comprador | ✅ `.pshell` + `.dtab` + `.tag`/`.act` + `.tfoot` |
| Barra e trilho de tipos do parceiro (todas as telas dele) | ✅ `.pshell` · `.papp`/`.pside`/`.pmain` |
| `/partner/precos/`, `/partner/tipo/…`, `how`, notificações | ⏳ conteúdo ainda `.ptn-*` (legado no `<style>` da base) |
| `/partner/compras/<pk>/` — a compra aberta | ⏳ próxima da fila (usar `patterns/ficha.css` + `.rhead`) |
| Telas internas da empresa (estoque, vendas) | ⏳ canary `Company.ui_v2` — ver FRONTEND_V2.md |

## 4. Duas regras deste projeto que o pacote não sabe

**A regra do FRONTEND_V2 ("nunca edite o template atual; faça cópia em `v2/`")
NÃO vale na superfície do comprador.** Aquele canary é por EMPRESA
(`Company.ui_v2`) e o comprador é de PLATAFORMA — não tem empresa, então o flag
nunca o alcançaria. Decisão do dono (2026-08-19): **trocar direto** no
comprador; é um usuário só e o rollback é reverter o commit. Nas telas da
empresa a regra continua valendo.

**O `shell.js` do sistema não vem no pacote.** É ele que mede o cabeçalho,
injeta o hambúrguer, marca `[data-shell="tablet|phone"]` e monta o widget de
perfil `.me`. Enquanto ele não vier, `partner_base.html` traz ~20 linhas que
fazem só isso — e o perfil (idioma · identidade · sair) viaja dentro de
`.pshell__me`, que recebe na mão o mesmo comportamento de gaveta que a folha dá
ao `.me`. Quando o `shell.js` chegar, essas linhas saem.

## 5. Convenções do pacote que o produto usa (e por quê)

· **`.dtab` é a tabela de TODAS as listas** — Estoque, Vendas e Compras. No
  celular a linha vira cartão de duas alturas: identificador + o número que
  decide (`.key`) em cima, o resto embaixo. Rolagem horizontal foi descartada
  pelo sistema de propósito: ela esconde justamente a última coluna, que aqui é
  sempre dinheiro.
· **`.c` código · `.n` número · `.v` valor** (com sub-linha `.due`/`.got`),
  **`.mval`** para o par ¥/US$, **`.tag`** para estado, **`.act`** para ação
  pendente, **`.hb`/`.hg`/`.hr`** para grupo de colunas tingido.
· **Mono em todo part number, código, figura e valor.** Sem exceção.
· **Raio 0, sem sombra, borda de 1px** (o botão é 2px — exceção do Carbon).
· **Selo em CAIXA ALTA**, peso 800.

---

# Anexo — README do pacote, como veio

# WhatTheChip Design System — pacote de aplicação

Este pacote é **só o sistema**: tokens, camada de componente, assets e os quatro componentes React.
Nenhuma tela, nenhum dado de exemplo, nenhum script de protótipo.

## Aplicar

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/wtc/wtc.css">
```

`wtc.css` é a única folha a linkar — ela importa o resto na ordem certa. As duas famílias vêm do
Google Fonts e **não** estão no pacote; sem elas o sistema cai em system-ui e a densidade muda.

Em bundler (Vite/Next/webpack): `import '/wtc/wtc.css'` uma vez, no topo da aplicação.

## O que tem dentro

    wtc.css          entrada única — importa tudo na ordem obrigatória
    tokens/          6 arquivos: fonts · colors · typography · spacing · controls · motion
    components.css   .btn .tag .dtab .shell .rhead .mbox .tbar .pgn .toast .note .mval .otag …
    patterns/        OPCIONAIS, comentados em wtc.css:
                       ficha.css     página interna de um registro (lote, venda, compra)
                       parceiro.css  grade de preços e tabelas do parceiro
    assets/          marca (claro/escuro), favicon

**A ordem não é estética.** Tokens declaram as variáveis, componentes consomem. Invertido, toda
regra cai em `var()` vazio e a página sai sem cor.

## Os quatro componentes React não estão aqui — e não é esquecimento

`Button`, `Input`, `RentabilityBar` e `VerdictPill` moram no design system (`components/core` e
`components/product`) e saem por ele: em projeto ligado ao sistema eles chegam prontos em
`window.<Namespace>`. Uma **cópia** deles dentro deste pacote declarava os mesmos quatro nomes uma
segunda vez e colidia com os originais — dois `Button`, um sobrevivendo. Artefato de saída não é
fonte de componente, então a cópia saiu.

Isto não tira nada do MVP: **a camada de CSS é independente de React.** `.btn`, `.tag`, `.dtab`,
`.rhead`, `.mbox` e o resto são classes que funcionam em HTML puro, Vue, Svelte ou string de
template. Se quiser os wrappers React, copie os quatro arquivos de `components/` do design system —
são pequenos e não têm dependência além do próprio React.

## Uma decisão sua, em uma linha

`components.css` termina com `--bg:var(--ink-10)`. Os tokens dizem `--ink-05` (#f7f8fb); as 16 telas
foram desenhadas e revisadas sobre `--ink-10` (#f2f4f8), um passo mais escuro. Mantive o valor das
telas para o MVP sair igual ao protótipo. **Apague a linha** para usar o fundo do design system.

## O que este pacote conserta em relação ao projeto de origem

No projeto original a folha das telas declarava um `:root` **próprio** — uma cópia dos tokens — porque
as telas eram HTML avulso que não linkava `styles.css`. Duas fontes de verdade, e cópias divergem:
foi assim que 120ms ficou documentado de um lado enquanto 240ms rodava do outro. Aqui a cópia não
existe: `components.css` não tem token nenhum, só consome. Um valor, um lugar.

## Sobre o Carbon

Geometria alinhada ao IBM Carbon e verificada contra a fonte (`carbon-design-system/carbon`), não de
memória: raio 0, sem elevação, foco 2px inset, blue-60 #0f62fe, escala de tipo pela fórmula
(12·14·16·18·20·24·28·32·36·42·48·54·60·68·76·84·92·102·112), espaçamento 2·4·8·12·16·24·32·40·48·64·80·96·160,
três curvas de easing com escolha semântica, seis durações, e as seis alturas de controle sobre
degraus (`--ctl-sm` 40 · `--ctl-md` 48 · `--ctl-lg` 64 · `--ctl-xl` 80 · header 48 · linha 48).

`--fs-NN` e `--spacing-NN` são o **número do degrau** do Carbon, então mapeiam 1:1 para
`type-scale(n)` e `$spacing-NN` — se um dia trocar isto por `@carbon/react`, a tradução é direta.

Duas divergências deliberadas: **Manrope** no lugar de IBM Plex Sans (escolha do time), e por
consequência **peso 600** no rótulo de botão em vez dos 400 do Carbon — 400 em Plex Sans é
opticamente mais pesado que 400 em Manrope, e casar o número deixaria o rótulo fino sobre o azul.

## Regras que o sistema não negocia

- **Raio 0** em tudo. Nada de canto arredondado.
- **Sem sombra.** Separação por fio de 1px (`--line`) e chapa rebaixada (`--ink-05`).
- **Borda de 1px** em tudo, **exceto o botão, que é 2px** — a exceção é do próprio Carbon.
- **Mono** (`--mono`) em todo part number, código, figura e valor. Sem exceção.
- **Selo em CAIXA ALTA**, peso 800, tracking .05em (`.tag`, `.otag`).
- **Foco** 2px `--focus` com `outline-offset:-2px` — nunca cresce a caixa.
- Altura maior **não** significa rótulo maior.
