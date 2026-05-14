# WhatTheChip Design System
**v2.0 · maio 2026 · baseado no IBM Carbon Design System**

> Este documento descreve o sistema de design atual do **WhatTheChip** — aplicação Django de classificação de chips IC para o mercado de reciclagem eletrônica. O sistema é uma implementação fiel do **Carbon White theme** com três extensões proprietárias: troca de família tipográfica para Helvetica Neue, adição de gradientes (adequação ao mercado asiático) e aumento do tamanho-base para 14 px (acessibilidade operacional).

Fonte de verdade: [`static/css/style.css`](static/css/style.css)

---

## 1. Princípios

| # | Princípio | O que significa na prática |
|---|---|---|
| 1 | **Carbon é a fundação** | Botões são quadrados (`border-radius: 2px`), bordas são hairlines de 1 px, profundidade vem de mudança de superfície — não de sombra. |
| 2 | **Gradiente como extensão cultural** | O Carbon vanilla é completamente plano. O WTC adiciona gradientes para aquecimento visual do mercado chinês. Cada gradiente tem função definida; não há gradiente decorativo. |
| 3 | **PN sempre legível** | Part numbers são o dado mais crítico da aplicação. Todo texto de resultado de chip usa contraste ≥ 7:1 (WCAG AAA). `font-mono` em todos os códigos. |
| 4 | **IBM Blue é escasso** | `#0f62fe` marca links, CTAs primários, foco de input e o único acento de cor. Não é usado como fundo de card nem como cor de eyebrow. |
| 5 | **Operador sênior** | Base em 14 px (mínimo absoluto 12 px). Alvos de clique mínimos de 40 px. Dark mode completo com paleta separada. |

---

## 2. Tipografia

### Famílias

| Papel | Família | Fallback |
|---|---|---|
| **Sans-serif principal** | `Helvetica Neue` | `Helvetica, Arial, sans-serif` |
| **Monospace** (PNs, código) | `IBM Plex Mono` | `Fira Code, Courier New, monospace` |

O IBM Carbon vanilla usa **IBM Plex Sans** como família principal. A substituição por **Helvetica Neue** é intencional: a fonte já está instalada no sistema operacional dos usuários-alvo (Windows / macOS / iOS) sem necessidade de carregamento externo. IBM Plex Mono é carregada do Google Fonts para código e part numbers.

```css
--font:      "Helvetica Neue", Helvetica, Arial, sans-serif;
--font-mono: "IBM Plex Mono", "Fira Code", "Courier New", monospace;
```

### Escala tipográfica

Segue Carbon com pesos e tamanhos fiéis — **exceto** pela base em 14 px (Carbon documenta 16 px, porém a aplicação é densa por necessidade operacional).

| Uso | Tamanho | Peso | Line-height | Letter-spacing |
|---|---|---|---|---|
| Display hero (h1) | 28 px | 600 | 1.2 | -0.02 em |
| Section heading (h2) | 20 px | 600 | 1.3 | -0.01 em |
| Sub-heading (h3) | 16 px | 600 | 1.4 | 0 |
| Small heading (h4) | 14 px | 600 | 1.5 | 0 |
| Body padrão (p) | 14 px | 400 | 1.75 | +0.16 px |
| Body compacto (tabela, meta) | 13 px | 400 | 1.5 | +0.16 px |
| Caption / label uppercase | 11–12 px | 600–700 | 1.33 | +0.04–0.1 em |
| Chip type (resultado principal) | 24 px | 700 | 1.15 | -0.01 em |
| Part number (monospace) | 13–21 px | 600–700 | — | +0.03–0.1 em |
| Button | 14 px | 600 | 1.29 | +0.16 px |

> **Carbon precision:** `letter-spacing: 0.16px` no corpo é um detalhe do Carbon que não deve ser removido — faz parte da voz tipográfica.

> **Display leve:** Se houver expansão para marketing em futuro, usar peso 300 para títulos de 42 px+, seguindo a assinatura do Carbon (`display-xl` a 76 px peso 300).

---

## 3. Cores

### 3.1 Tokens de superfície e texto

```css
/* ── Superfícies (Carbon White theme) ──────────────────── */
--bg:        #ffffff;   /* canvas — fundo de página */
--surface:   #ffffff;   /* camada 01 — cards, inputs */
--surface-2: #f4f4f4;   /* camada 02 — stripes, header de tabela */
--surface-3: #e0e0e0;   /* camada 03 — hover em surface-2 */

/* ── Texto ─────────────────────────────────────────────── */
--text-primary:     #161616;   /* charcoal — headings, body principal */
--text-secondary:   #525252;   /* gray 70 — body secundário, nav links */
--text-helper:      #6f6f6f;   /* gray 60 — legendas, metadados */
--text-placeholder: #a8a8a8;   /* gray 40 — placeholders */
--text-on-color:    #ffffff;   /* branco sobre azul/cor */
```

### 3.2 Interação e links

```css
--interactive:        #0f62fe;   /* Carbon Blue 60 — o único acento */
--interactive-hover:  #0353e9;   /* Blue 70 */
--interactive-active: #002d9c;   /* Blue 80 */
--link:               #0f62fe;
--link-hover:         #0043ce;
--link-visited:       #8a3ffc;   /* Purple 60 */
--focus:              #0f62fe;
```

### 3.3 Bordas

```css
--border-subtle:  #e0e0e0;   /* hairline padrão — cards, inputs */
--border-default: #8d8d8d;   /* border mais forte — focus ring interior */
--border-strong:  #161616;   /* charcoal — focus underline Carbon */
```

### 3.4 Semântica

```css
--success:     #198038;   --success-bg:  #defbe6;   --success-bd:  #a7f0ba;
--warning:     #b28600;   --warning-bg:  #fff8e1;   --warning-bd:  #f1c21b;
--error:       #da1e28;   --error-bg:    #fff1f1;   --error-bd:    #ffd7d9;
--info:        #0043ce;   --info-bg:     #edf5ff;   --info-bd:     #d0e2ff;
```

### 3.5 Tags cromáticas

Seguem o padrão de cor das tags Carbon:

```css
--tag-blue-bg:  #d0e2ff;  --tag-blue-fg:  #0043ce;   /* eMMC, DDR */
--tag-green-bg: #defbe6;  --tag-green-fg: #0e6027;   /* UFS */
--tag-teal-bg:  #d9fbfb;  --tag-teal-fg:  #005d5d;   /* UFS 3.x */
--tag-cyan-bg:  #e5f6ff;  --tag-cyan-fg:  #0072c3;   /* interfaces */
--tag-gray-bg:  #e0e0e0;  --tag-gray-fg:  #393939;   /* neutro / inativo */
--tag-cool-bg:  #dde1ff;  --tag-cool-fg:  #393aaa;   /* eMCP */
```

### 3.6 Código

```css
--code-bg:     #f4f4f4;
--code-fg:     #0f62fe;
--code-border: #e0e0e0;
```

### 3.7 Contraste e WCAG

| Par | Ratio mínimo | Nível | Onde |
|---|---|---|---|
| `text-primary` / `bg` (claro) | 16:1 | AAA | Corpo principal |
| `text-secondary` / `bg` | 7:1 | AAA | Corpo secundário |
| `text-helper` / `bg` | 4.6:1 | AA | Metadados |
| `text-on-color` / `interactive` | 4.7:1 | AA | Botão primário |
| `interactive` / `bg` | 4.7:1 | AA | Links |
| **Tipo de chip / bg** | **≥ 7:1** | **AAA obrigatório** | `dc2-chiptype` |

---

## 4. Gradientes

Esta é a **extensão principal** do WTC sobre o Carbon vanilla. Carbon é completamente plano; o WTC adiciona gradientes para aquecimento visual no mercado asiático. A regra central: **cada gradiente tem função definida**.

### Gradientes existentes (implementados)

```css
/* ── Hero — fundo da página inicial ──────────────────────
   Sentido: top-down, azul claro → branco puro
   Função: cria profundidade no hero sem competir com o PN input */
background: linear-gradient(180deg, #dbeafe 0%, #edf5ff 30%, #f4f4f4 80%);
/* Usado em: .hero */
```

### Gradientes propostos (implementar nos próximos sprints)

```css
/* ── Header com gradiente (opção para mercado CN) ────────
   Sentido: left-to-right, azul escuro → azul médio
   Função: dá peso à barra de navegação sem usar cor chapada */
--grad-header: linear-gradient(90deg, #0043ce 0%, #0f62fe 60%, #4589ff 100%);

/* ── Card de resultado — destaque sutil de fundo ─────────
   Sentido: 135deg, azul muito claro → branco
   Função: diferencia o decode card do fundo de página */
--grad-card-result: linear-gradient(135deg, #edf5ff 0%, #ffffff 100%);

/* ── Card remarked — alarme visual ───────────────────────
   Sentido: 135deg, vermelho muito claro → branco
   Função: reforça visualmente a condição de alerta */
--grad-card-danger: linear-gradient(135deg, #fff1f1 0%, #ffffff 100%);

/* ── Rodapé invertido ────────────────────────────────────
   Sentido: top-down, cinza escuro → charcoal
   Função: dá peso ao footer sem corte abrupto */
--grad-footer: linear-gradient(180deg, #262626 0%, #161616 100%);
```

### Regras de uso

1. **Máximo 3 pontos de cor** por gradiente em UI. Mais do que isso é decoração.
2. **Nunca em texto de resultado** (`dc2-chiptype`, `dc2-spec-val`). Gradiente em texto falha em WCAG AAA.
3. **Sentido `to bottom`** para elementos verticais (header, footer), **135deg** para cards e superfícies diagonais.
4. **O Carbon proíbe gradientes em superfícies de marketing** — o WTC os usa como extensão controlada, não como padrão geral.
5. **Dark mode:** gradientes de identidade (header, footer) podem ser mantidos. Gradientes de card devem usar as versões escuras correspondentes.

---

## 5. Espaçamento

Base em **8 px**, derivada do grid de 4 px do Carbon com tokens dobrados para uso comum.

```css
--s1:  2px;   --s2:  4px;   --s3:  8px;   --s4:  12px;
--s5:  16px;  --s6:  24px;  --s7:  32px;  --s8:  40px;
--s9:  48px;  --s10: 64px;  --s11: 80px;  --s12: 96px;
```

| Uso comum | Token |
|---|---|
| Gap interno de badge / inline | `--s2` (4 px) |
| Padding de botão vertical | `--s3` (8 px) |
| Padding horizontal de botão | `--s5` (16 px) |
| Padding interno de card compacto | `--s4` / `--s5` (12–16 px) |
| Padding interno de card standard | `--s6` (24 px) |
| Espaçamento entre seções | `--s8` / `--s9` (40–48 px) |
| Seção de hero / section break | `--s12` (96 px) |

---

## 6. Sombras

Carbon resiste sombras em superfícies de marketing. O WTC as usa de forma controlada no resultado de busca e no painel de estoque.

```css
--shadow-xs: 0 1px 2px rgba(0,0,0,.07);
--shadow-sm: 0 1px 4px rgba(0,0,0,.10);
--shadow-md: 0 2px 8px rgba(0,0,0,.13);
--shadow-lg: 0 4px 16px rgba(0,0,0,.16);
--shadow-xl: 0 8px 32px rgba(0,0,0,.20);
```

**Escala de elevação:**

| Nível | Tratamento | Onde |
|---|---|---|
| 0 — flat | Sem sombra, sem borda | Corpo de texto, footer, `article` |
| 1 — hairline | `border: 1px solid --border-subtle` | Cards, inputs, listas |
| 2 — surface lift | Fundo `--surface-2` sobre `--bg` | Hover de cards, th de tabela |
| 3 — focus ring | `box-shadow: 0 0 0 3px rgba(15,98,254,.2)` | `pin-boxes:focus-within`, inputs focados |
| 4 — dropdown | `--shadow-lg` | Menus suspensos |

---

## 7. Raios de borda

```css
--r-sm: 2px;   /* quase zero — inputs, botões, badges — espírito Carbon */
--r:    4px;   /* padrão — pin-boxes, pin-box, tags */
--r-md: 6px;   /* cards de resultado, decode card */
--r-lg: 8px;   /* modais, painéis maiores */
```

Carbon puro usa `0px`. O WTC usa `2px` como mínimo para suavizar ligeiramente sem abandonar o caráter técnico da marca.

---

## 8. Layout e Grid

```css
--max-w:     1200px;   /* largura máxima do layout geral */
--content-w: 880px;    /* largura máxima do artigo editorial */
--header-height: 48px; /* altura fixa do header sticky */
```

### Estrutura de página

```
┌─ .wtc-header (sticky, 48px, branco + hairline) ──────────────┐
│  .wtc-header-inner (max 1200px, flex, gap 16px)               │
│    .wtc-nav · .wtc-header-actions                             │
└───────────────────────────────────────────────────────────────┘
┌─ .wtc-main (min-height: calc(100vh - 48px - 49px)) ──────────┐
│  └── .hero (home) | .article (páginas editoriais)             │
│      └── conteúdo Django renderizado                          │
└───────────────────────────────────────────────────────────────┘
┌─ .wtc-footer (charcoal, invertido) ──────────────────────────┐
└───────────────────────────────────────────────────────────────┘
```

### `.article` — conteúdo editorial

```css
.article {
  max-width: var(--content-w);   /* 880px */
  margin: 0 auto;
  padding: var(--s7) var(--s5) var(--s11);
}
```

> A sidenav foi **removida no redesign v2**. O CSS preserva `.sidenav { display: none !important }` para compatibilidade retroativa com conteúdo HTML herdado.

---

## 9. Componentes

### 9.1 Header (`wtc-header`)

O header é **branco puro** (`#ffffff`) com hairline inferior sutil. Não usa gradiente por padrão (opção de gradiente documentada na seção de Gradientes).

```css
.wtc-header {
  position: sticky; top: 0; z-index: 200;
  background: var(--header-bg);  /* #ffffff */
  height: 48px;
  /* sem box-shadow — separação por hairline apenas quando necessário */
}
```

**Comportamento dos links de nav:**
- Estado padrão: `color: --text-secondary` (cinza)
- Estado ativo: `color: --interactive` + `font-weight: 600`
- Hover: `text-decoration: underline`, sem mudança de fundo

**Dropdown (`.wtc-dropdown`):**
- Fundo branco puro com `border-top: 2px solid --interactive` — tratamento Carbon de tab ativa
- `box-shadow: 0 4px 16px rgba(0,0,0,.12)` — único shadow do header
- Badge `● Ativo` usa `--success-bg` / `--success`

---

### 9.2 Hero e PIN Search

O hero da página inicial segue o padrão Google Search: **logo SVG centralizado + campo de digitação de part number**.

```css
.hero {
  background: linear-gradient(180deg, #dbeafe 0%, #edf5ff 30%, #f4f4f4 80%);
  padding: var(--s12) var(--s5) var(--s11);
  min-height: 58vh;
  display: flex; align-items: center; justify-content: center;
}
```

**PIN boxes (`.pin-boxes`):**
Cada caractere do PN é um box individual. O container age como um único campo com foco unificado.

```css
.pin-boxes {
  border: 2px solid var(--border-default);
  border-radius: var(--r);
  box-shadow: var(--shadow-md);
  /* focus-within: */
  border-color: var(--interactive);
  box-shadow: 0 0 0 3px rgba(15,98,254,.2), var(--shadow-md);
}

.pin-box {
  width: 44px; height: 56px;
  font-family: var(--font-mono);
  font-size: 21px; font-weight: 600;
  border-right: 1px solid var(--border-subtle);
}

/* Variações de estado */
.pin-box.pin-filled  { background: var(--surface-2); }  /* digitado */
.pin-box.pin-cursor  { animation: pin-cursor-blink 1s step-end infinite; }
.pin-box.pin-prefix  { background: var(--info-bg); color: var(--interactive); }
```

O cursor pisca via `box-shadow: inset 0 -3px 0 var(--interactive)` — inspirado no sublinhado de foco do Carbon.

---

### 9.3 Painel de Resultado (`wtc-rp-*`)

Componente abaixo do PIN search, aparece assim que o motor retorna dados.

```
┌── .wtc-rp-status (status bar: idle / typing / ok / warn) ─┐
├── .wtc-rp-body ─────────────────────────────────────────── │
│   ├── .wtc-rp-chiptype (24px bold — tipo do chip)         │
│   └── .wtc-rp-brand (tag monospace azul)                  │
├── .wtc-rp-specs (grid 2 col) ────────────────────────────  │
│   └── .wtc-rp-spec: .wtc-rp-spec-label + .wtc-rp-spec-val │
└── .wtc-rp-footer (fonte, link doc, reportar erro) ─────────┘
```

**Status bar semântica:**

| Classe | Fundo | Texto | Contexto |
|---|---|---|---|
| `--idle` | `surface-2` | `text-placeholder` | Campo vazio |
| `--typing` | `info-bg` | `interactive` | Digitando, aguardando |
| `--ok` | `success-bg` | `success` | Chip identificado |
| `--warn` | `warning-bg` | `warning` | PN incompleto ou remarked |

---

### 9.4 Decode Card (`dc2-card`)

Componente Django (partial `chips/templates/chips/partials/decode_card.html`) — renderizado via HTMX.

```css
.dc2-card {
  background: var(--surface);
  border-left: 4px solid var(--success);   /* acento lateral — "identificado" */
  border-radius: 0 var(--r-md) var(--r-md) 0;
  overflow: hidden;
}
.dc2-card--remarked { border-left-color: var(--warning); }  /* alerta amarelo */
```

**Estrutura do card:**

```
.dc2-status    (barra superior: ✓ ok / ⚠ remarked / ⌛ incompleto)
.dc2-head      (chiptype esquerda · brand-tag direita)
.dc2-alert     (só se remarked — fundo error-bg, borda-left error)
.dc2-specs     (grid 2 col, gap de 1px sobre --border-subtle)
  .dc2-spec-col: .dc2-spec-label (mono, uppercase, azul) + .dc2-spec-val
.dc2-suffix    (nota de sufixo opcional)
.dc2-footer    (confiança · fonte · link doc · reportar · debug)
```

**Brand tag:**
```css
.dc2-brand-tag {
  font-family: var(--font-mono); font-size: 10px; font-weight: 700;
  color: var(--interactive); background: var(--info-bg);
  border: 1px solid var(--info-bd); border-radius: var(--r-sm);
  padding: 3px 9px; letter-spacing: .06em; text-transform: uppercase;
}
```

---

### 9.5 Tabela de Prefixos (`.pr-*`)

Listagem de prefixos que aparece abaixo do decode card. Grid de 3 colunas: prefixo, fabricante, tipo.

```css
.pr-row {
  display: grid;
  grid-template-columns: 90px 100px 1fr;
  gap: 12px;
  padding: 9px 16px;
  border-bottom: 1px solid var(--border-subtle);
  transition: background 0.1s;
}
.pr-row:hover { background: var(--info-bg); }

.pr-prefix {
  font-family: var(--font-mono); font-weight: 700;
  color: var(--interactive);
  background: var(--info-bg); border: 1px solid var(--info-bd);
  border-radius: var(--r-sm);
  padding: 2px 8px;
}
```

O cabeçalho (`.pr-header`) usa `surface-2` + texto uppercase 10 px — tratamento Carbon de header de tabela.

---

### 9.6 Botões

```css
/* Padrão Carbon: quase-square, padding 10px 20px, peso 600 */
.btn, .wtc-btn, .est-btn {
  border-radius: var(--r-sm);  /* 2px — espírito Carbon */
  font-weight: 600;
  font-family: var(--font);
}

/* Primário */
background: var(--interactive); color: var(--text-on-color);
/* hover: */ background: var(--interactive-hover);

/* Secundário */
background: var(--surface-2); color: var(--text-primary);
border: 1px solid var(--border-default);

/* Ghost */
background: transparent; color: var(--interactive);
/* hover: */ background: var(--info-bg);

/* Danger */
background: transparent; color: var(--error); border: 1px solid transparent;
/* hover: */ background: var(--error-bg);
```

**Altura mínima:** 40 px para botões de corpo, 32 px para botões sm, 48 px para botões lg.

---

### 9.7 Inputs e Formulários

Segue o padrão Carbon: fundo `surface-2` (`#f4f4f4`), borda sutil, sublinhado de foco `2px interactive`.

```css
.est-input {
  height: 40px;
  padding: 0 var(--s4);
  background: var(--surface);
  border: 1px solid var(--border-default);
  border-radius: var(--r-sm);   /* 2px */
}
.est-input:focus {
  border-color: var(--interactive);
  box-shadow: inset 0 0 0 1px var(--interactive);  /* double-border Carbon */
}
```

**Variação monospace** (para PNs): `font-family: var(--font-mono); font-size: 15px; letter-spacing: .03em`.

---

### 9.8 Tabela do Estoque (`.est-table`)

```css
.est-table th {
  background: var(--surface-2);
  border-bottom: 2px solid var(--interactive);  /* acento Carbon */
  font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: .04em;
  color: var(--text-secondary);
}
.est-table td { border-bottom: 1px solid var(--border-subtle); }
.est-table tbody tr:hover td { background: var(--surface-2); }
```

**PN na tabela (`.est-pn`):** `font-family: var(--font-mono); color: var(--interactive); font-size: 13px`.

**Tag de tipo (`.est-type-tag`):** `background: var(--tag-blue-bg); color: var(--tag-blue-fg)`.

**Badge de quantidade (`.est-qty-badge`):** monospace, fundo `surface-2`, borda subtle.

---

### 9.9 Cards de Conteúdo (`.est-card`)

```css
.est-card {
  background: var(--surface);
  border: 1px solid var(--border-subtle);
  padding: var(--s6);   /* 24px — Carbon feature-card padding */
  /* sem border-radius — padrão Carbon flat */
}
```

**Variantes de confirm card (estoque):**
- `.est-confirm--ok`: `border-left: 3px solid var(--success)`
- `.est-confirm--unknown`: `border-left: 3px solid var(--warning)`
- `.est-confirm--done`: `border-left: 3px solid var(--interactive)`

---

### 9.10 Tags e Badges

```css
/* Tag de tipo de chip */
.est-type-tag {
  display: inline-block;
  padding: 1px 8px;
  background: var(--tag-blue-bg); color: var(--tag-blue-fg);
  border-radius: var(--r-sm);
  font-size: 11px; font-weight: 700; letter-spacing: .03em;
}

/* Badge de quantidade */
.est-qty-badge {
  min-width: 36px; text-align: center;
  padding: 2px 8px;
  background: var(--surface-2);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
  font-family: var(--font-mono); font-weight: 700;
}
```

---

### 9.11 Footer (`wtc-footer`)

```css
.wtc-footer {
  background: #161616;   /* Carbon --inverse-canvas: charcoal */
  color: rgba(255,255,255,0.6);
  border-top: 1px solid rgba(255,255,255,0.1);
  font-size: 12px;
  text-align: center;
  padding: var(--s5) var(--s5);
}
```

O footer inverte para charcoal — única superfície escura da página. Segue o padrão Carbon.

---

### 9.12 Código e Part Numbers

```css
code, .chip, .tag {
  font-family: var(--font-mono);
  font-size: 0.875em;
  background: var(--code-bg);      /* #f4f4f4 */
  border: 1px solid var(--code-border);
  border-radius: var(--r-sm);
  padding: 1px 6px;
  color: var(--code-fg);           /* #0f62fe */
  font-weight: 600;
}
```

---

## 10. Dark Mode

Princípio: paleta separada que não inverte cores — adapta tons. O charcoal do footer (`#161616`) **não muda** no dark mode, pois já é o tom mais escuro.

```css
[data-theme="dark"] {
  /* Superfícies */
  --bg:        #161616;
  --surface:   #262626;
  --surface-2: #393939;
  --surface-3: #525252;

  /* Texto */
  --text-primary:   #f4f4f4;
  --text-secondary: #c6c6c6;
  --text-helper:    #a8a8a8;

  /* Bordas */
  --border-subtle:  #393939;
  --border-default: #6f6f6f;

  /* Links / interação ficam mais claros para contraste */
  --interactive:       #78a9ff;   /* Blue 40 */
  --interactive-hover: #a6c8ff;   /* Blue 30 */
  --link:              #78a9ff;
  --link-visited:      #be95ff;
}
```

**Regra para gradientes no dark mode:**
- Gradiente de hero: substituir azul claro `#dbeafe` por azul muito escuro `#001141`
- Cards de resultado: usar fundo escuro `#1c2333` em vez de `#edf5ff`
- Header (se gradiente implementado): manter idêntico ao modo claro — os azuis de identidade sobrevivem

---

## 11. Acessibilidade

| Requisito | Implementação |
|---|---|
| Tamanho mínimo | 12 px. Corpo em 14 px. Resultado de chip em 15–24 px |
| Contraste resultado | WCAG AAA (≥ 7:1) para `dc2-chiptype` e `dc2-spec-val` |
| Contraste geral | WCAG AA (≥ 4.5:1) para todos os textos funcionais |
| Foco de teclado | `box-shadow: 0 0 0 3px rgba(15,98,254,.2)` nos campos; `outline: 2px solid --interactive` nos botões |
| Alvos de toque | 40 px mínimo (botões), 44 px mínimo (pin-box individual) |
| Landmarks | `<header>`, `<nav aria-label>`, `<main id="content">`, `<footer>` obrigatórios |
| Skip link | `<a href="#content">` no topo do `base.html` — ainda não implementado; incluir no próximo sprint |
| ARIA labels | Botões de ícone (tema, câmera) devem ter `aria-label` |
| OCR / câmera | `est-ocr-progress` deve ter `role="progressbar"` e `aria-valuenow` |

---

## 12. Animações e Motion

```css
/* Cursor piscante no PIN input */
@keyframes pin-cursor-blink {
  0%, 49%  { box-shadow: inset 0 -3px 0 var(--interactive); }
  50%, 100% { box-shadow: inset 0 -3px 0 transparent; }
}

/* Flash de linha recém-adicionada (estoque) */
@keyframes est-row-flash {
  0%   { background: var(--info-bg); }
  100% { background: transparent; }
}

/* Fade-in de resultados */
@keyframes wtc-fadein {
  from { opacity: 0; transform: translateY(3px); }
  to   { opacity: 1; transform: none; }
}
```

**Princípio:** transições curtas (`0.1–0.15s`) para estados de hover/focus; `0.25s` para mudanças de conteúdo. Sem animações longas em contexto operacional.

---

## 13. Impressão

```css
@media print {
  .wtc-header, .wtc-footer { display: none; }
  body { background: #fff; color: #000; }
  table th { background: #0f62fe !important; color: #fff !important;
             -webkit-print-color-adjust: exact; }
}
```

---

## 14. Responsivo

| Breakpoint | Layout |
|---|---|
| > 1200px | max-width 1200px centralizado |
| 1056–1200px | Layout normal, padding lateral reduz |
| 672–1055px | Grid de cards 4-up → 2-up |
| < 672px | Single column; `.wtc-nav` oculta para hamburger (a implementar) |

---

## 15. Desvios do Carbon vanilla

| Aspecto | Carbon vanilla | WTC |
|---|---|---|
| Família tipográfica | IBM Plex Sans | **Helvetica Neue** |
| Família mono | IBM Plex Mono | IBM Plex Mono *(mantida)* |
| Border-radius | 0 px | **2–4 px** (levemente suavizado) |
| Gradientes | Apenas hero illustration wash | **Gradiente de hero implementado; propostas para header e cards** |
| Tamanho base | 16 px (Carbon recomenda) | **14 px** (necessidade de densidade operacional) |
| Header | Branco + hairline | Branco + hairline *(idêntico)* · gradiente disponível como opção |
| Footer | Charcoal invertido | Charcoal invertido *(idêntico)* |
| PIN search | n/a (domínio) | **Componente exclusivo WTC** — boxes por caractere |
| Decode card | n/a | **Componente exclusivo WTC** — `dc2-card` com acento lateral |
| Painel de estoque | n/a | **Componente exclusivo WTC** — `est-*` com OCR integrado |
| Status bar semântica | n/a | **Componente exclusivo WTC** — `wtc-rp-status` |

---

## 16. Aliases de compatibilidade retroativa

O CSS mantém aliases para variáveis usadas em conteúdo HTML herdado das páginas de marca (Samsung, Hynix, etc.) geradas pelo `build.py`. Esses aliases mapeiam para os tokens v2:

```css
--ink       → #161616   (= --text-primary)
--hi-1      → #0f62fe   (= --interactive)
--hi-5      → #edf5ff   (= --info-bg)
--rule      → #e0e0e0   (= --border-subtle)
--canvas    → #f4f4f4   (= --surface-2)
--note-bg   → #edf5ff
--warn-bg   → #fff1f1
--font-serif → "Helvetica Neue" (removido Georgia, mapeado p/ Helvetica)
```

Não usar esses aliases em código novo. Usar os tokens v2 (`--text-primary`, `--interactive`, etc.).

---

*WhatTheChip Design System v2.0 · eMiner · Paraguai · maio 2026*
*Baseado no IBM Carbon Design System (https://carbondesignsystem.com)*
