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
