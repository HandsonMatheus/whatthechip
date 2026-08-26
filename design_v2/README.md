# WhatTheChip — Design System

WhatTheChip (**什么芯片**, "o Google dos chips") is a bench tool for the electronics
recycling / refurbish market, operated by **eMiner (Paraguay)**. An operator reads the
laser-etched **Part Number** off a recovered memory chip, types it, and instantly learns
**what it is** (eMCP · eMMC · UFS · LPDDR · DDR · NAND — capacity, density, interface) and
**whether it is worth reconditioning** — the verdict system `RENTÁVEL` / `NÃO RENTÁVEL` /
`INDETERMINADO`. Identified chips are triaged into **lots** (lotes) that get exported for sale.

Supported manufacturers: Samsung, SK Hynix, Micron, SanDisk, Toshiba/Kioxia, GigaDevice,
PieceMakers, Foresee, Kingston, Nanya, Rayson, ISSI, Elpida.

The real product is **Django 5.2 + HTMX** (server-rendered), Postgres, deployed on **Render**.

## Sources (ground truth)
This design system was built by reading real code. If you have access, explore these to build
more faithful designs:
- **Product repo** — https://github.com/HandsonMatheus/whatthechip  (templates, `static/css/design.css`,
  `_content/index.html`, `estoque/` inventory app — the source of every layout and value here)
- **IBM Carbon** — https://github.com/carbon-design-system/carbon  (the product's original tokens derive
  from Carbon's gray/blue scales; our neutral "ink" ramp and blue #0f62fe come from there)
- **IBM Carbon** — the design language of this system. Grays, blue #0f62fe, square corners, flat
  fills, hairline borders, dense data tables.

## Design direction — IBM Carbon
This system **is** Carbon, applied to a bench tool. Square corners (0px, with no exceptions),
**flat** fills with no elevation, **1px hairline** borders doing the separating work, **dense**
data tables, and **Signal Blue #0f62fe** as the single primary action color. The logged-in bench
app keeps a **dark top shell** to frame "workbench mode" apart from the public site.

An earlier pass had reskinned this toward Render.com — rounded 8/12/16px corners, soft shadow
scale, airy spacing. That direction was dropped and every trace of it removed: there are no
radius tokens and no shadow tokens in this system. If a design needs a rounded corner or a drop
shadow, it is off-system.

---

## CONTENT FUNDAMENTALS
- **Language:** Portuguese (pt-BR) is primary; the product is multilingual (en / es / zh-hans) and the
  Chinese wordmark **什么芯片** always sits beside "WhatTheChip".
- **Voice:** terse, technical, operator-facing, confident. Second person **"você"**. Instructions read
  like bench steps: *"Leia o chip → digite o PN → lance no lote."*
- **Casing:** sentence case for UI; **verdict words in CAPS** context (Rentável/Não rentável as pills);
  micro-labels are UPPERCASE mono with letter-spacing (e.g. `RENTABILIDADE`, `UNIDADES`, `TIPOS`).
- **Numbers & codes:** always **IBM Plex Mono**. Part Numbers uppercased. Thousands in pt-BR (`1.840`).
  Lot numbers zero-padded (`#042`).
- **Status-first microcopy:** "Chip identificado", "PN incompleto — continue digitando", "Aguardando PN…",
  "1× → caixa EMCP 16+1", "Enviado à fila de conferência".
- **Emoji:** not used in chrome. The *product* uses a few **functional status glyphs** inline
  (✓ ⚠ ⌛). Keep decorative emoji out.
- **Examples:** "Continuar triagem", "Fechar lote", "Reabrir", "Reportar erro", "Enviar para análise",
  "Nenhum lote aberto agora".

## VISUAL FOUNDATIONS
- **Color:** neutral **ink** scale (cool grays, Carbon-derived) for text/surfaces/borders; **Signal Blue**
  (`#0f62fe`, hover `#0353e9`) for brand + every primary/interactive element; three **verdict semantics** —
  green `#24a148` (Rentável), amber `#f1c21b` (Indeterminado), red `#da1e28` (Não rentável). Max one
  content background (`--bg` #f7f8fb) + white surfaces. The internal navbar uses a near-black **dark shell**.
- **Type:** UI = **Manrope** (`--sans`); codes/figures = **IBM Plex Mono** (`--mono`); CJK = **Noto Sans SC**
  (`--cjk`). The scale is **Carbon's**, computed not chosen — `Y1 = 12px, Yn = Yn-1 + (INT[(n-2)/4] + 1) × 2`
  → 12 · 14 · 16 · 18 · 20 · 24 · 28 · 32 · 36 · 42 · 48 · 54 · 60 · 68 · 76 · 84 · 92 · 102 · 112.
  `--fs-NN` **is** the step number, so it maps 1:1 onto Carbon's `type-scale(n)`; the semantic roles
  (`--fs-body`, `--fs-h1`, `--fs-label`…) are pinned to steps. Carbon has no step below 12px, so
  there is no 11px or 10px label — weight and tracking separate them, not size.
- **Spacing:** Carbon's scale — 8px grid with a **2px mini-unit**: 2 · 4 · 8 · 12 · 16 · 24 · 32 · 40 ·
  48 · 64 · 80 · 96 · 160. `--spacing-NN` maps 1:1 onto Carbon's `$spacing-NN`; `--s-1`…`--s-10` are
  short authoring aliases over the same values. There is **no 20px step** — Carbon doesn't have one.
  The work area is a 1680px ruler with 32px gutters.
- **Control heights:** Carbon's ladder — `sm 32 · field 40 · lg 48 (its default button) · xl 64 · 2xl 80`,
  header 48, table row lg 48 — exposed as `--cds-*`. The product's four names now each **land on a step**:
  `--ctl-sm` = field 40 · `--ctl-md` = lg 48 · `--ctl-lg` = xl 64 · `--ctl-xl` = 2xl 80, with
  `--shell-h 48` and `--row-h 48`. They are defined as `var(--cds-*)`, not as repeated numbers, so a
  control cannot drift off the ladder. (Previously 36 · 48 · 56 · 76 with header 52 and row 56 — four of
  the six sat *between* two steps, the same defect as a type scale eyeballed by hand.) A taller control
  does NOT mean a bigger label.
- **Motion:** Carbon's three productive curves — `--ease` standard `(.2,0,.38,.9)` for state changes in
  place, `--ease-in` entrance `(0,0,.38,.9)`, `--ease-out` exit `(.2,0,1,.9)` — and Carbon's six duration
  steps (70 · 110 · 150 · 240 · 400 · 700ms). The choice of curve is semantic, not decorative.
- **Radius:** none. Everything is square — 0px, including tags, bars, cards, inputs and buttons. The
  only exceptions in the whole system are status dots and avatars (`border-radius:50%`).
- **Elevation:** none. There is no shadow scale. Separation is done with 1px `--line` borders and
  with the rebated fills (`--ink-05`, `--ink-10`) — never by lifting a surface.
- **Cards/panels:** white surface, 1px `--line` border, square. Hover tints the surface; nothing
  lifts, nothing casts. **No colored left-border accents.**
- **Borders:** 1px `--line` hairline everywhere — except the **button**, which is 2px
  (`$button-border-width`), Carbon's own exception.
- **Hover/press:** hover = subtle surface tint or darker blue; focus = `outline:2px solid var(--blue-60)`
  with `outline-offset:-2px` (inset, so it never grows the box). Press = slight brightness drop.
  Fields carry a 1px bottom rule that turns blue on focus — that rule, not a halo, is the focus signal.
- **Backgrounds:** flat. A faint chip-grid texture appears only on the login screen (masked, low opacity).
  No gradients (one subtle brand gradient exists only on the project tile).
- **Signature element:** the **rentability bar** — a single segmented green/red/amber bar showing a lot's
  triage split. It is the business KPI (sellable vs scrap) and recurs on lot cards, headers, and heroes.
- **Imagery:** product photography of chips/boards is cool-toned and literal; used sparingly.

## ICONOGRAPHY
- **Inline stroke SVGs**, `viewBox="0 0 24 24"` (or `0 0 32 32` for nav marks), `stroke-width` ~2,
  `stroke="currentColor"`, rounded joins. **No icon font, no PNG icons, no emoji-as-icon.**
- The set is hand-drawn to match **Lucide** (same 1.5–2px stroke, rounded style). **If you need a fuller
  icon set, use [Lucide](https://lucide.dev) via CDN** — it is the nearest match. *(Substitution flagged:
  the product ships its own inline SVGs, not a named icon library.)*
- Glyphs in use: search/mag, microphone, sun/moon, globe (language), user/avatar, eye (reveal), arrow,
  chevron, close (×), plus, box/cube (lot), grid (painel), trash (discard), upload/export, alert-triangle,
  check-badge (queue), send (paper-plane).

---

## COMPONENTS
Reusable React primitives (`window.WhatTheChipDesignSystem_ed1fad`). These are extracted from the
product's real UI vocabulary (the product is server-rendered and has no formal component library, so
these are faithful pattern extractions, not a 1:1 port).

- **Button** (`components/core`) — primary (blue) / ghost / danger / success; heights from the control
  scale (sm 36 · md 48 · lg 56); square; `iconLeft`.
- **Input** (`components/core`) — Carbon text field: rebated slab, one 1px bottom rule that turns blue
  on focus, inset 2px outline, square; `mono` variant for Part Numbers.
- **VerdictPill** (`components/product`) — the profitability tag: rentavel / nao / indeterminado. 11px/800,
  6px square marker, 0 radius.
- **RentabilityBar** (`components/product`) — the signature split bar, square segments, optional legend.

*Intentional additions:* none beyond the extracted vocabulary. Candidates for later (present as patterns
in the UI kit, not yet packaged as components): Badge (lot status), ShellNav (dark navbar), LotCard,
DecodeCard/SpecGrid, StatCell, QtyStepper, Toast.

## UI KIT — `ui_kits/whatthechip/`
High-fidelity, interactive recreations of the real product surfaces:
- **index.html** — public chip finder (Google-style: logo over the search bar; decode result with
  spec-first card + discreet verdict pill; fuzzy + partial-PN suggestions; light/dark).
- **login.html** — bench sign-in (masked chip-grid backdrop).
- **painel.html** — post-login launcher: greeting, mission steps, "continue the open lot" hero, day pulse, shortcuts.
- **estoque.html** — inventory workspace: "Em triagem agora" (active open lots with rentability bar) +
  dense **lot ledger** table (search, status filters, period/sort filters, on-demand create).
- **triagem.html** — bench mode / lot detail: sticky scan console + gateway (rentável→box, indeterminado→rever,
  não rentável→descarte, não identificado→fila) + live lot tally.
- **venda.html / vendas-lista.html** — the seller's side of a sale: record header (code + stage rail +
  the action of the moment), stage groups, and the queue of lots sold to the platform.
- **parceiro\*.html** — the buyer's side: price grids per chip type (`parceiro-side.js` is the shared
  type rail), purchases list, lot record with the result spreadsheet, generated catalogue.
- **notificacoes.html / avisos.html** — the notification centre and the in-app notice patterns.

## FOUNDATIONS — `foundations/`
Specimen cards for the Design System tab: colors (Signal Blue, neutral ink, verdict semantics, surface),
type (families, scale, mono/PNs), spacing, control heights, motion, and brand (logo lockup, rentability
bar). Groups: Brand · Colors · Components · Controls · Motion · Spacing · Type. There is no radius card
and no elevation card — those documented a scale this system does not have.

**When authoring a card:** link the Google Fonts stylesheet as well as `styles.css` (without it the card
renders in a fallback face instead of Manrope), write it in **pt-BR** like the product, and take label
sizes/weights from the type tokens (`--fs-label`, `--fw-black`, `--ls-label`) rather than hardcoding them.

## TWO SOURCES OF TRUTH — read before exporting
`tokens/*.css` (linked via `styles.css`) is the design system. `ui_kits/whatthechip/wtc-carbon.css`
declares its **own** `:root` block, because the kit screens are standalone HTML that do not link
`styles.css`. The kit is therefore a *mirror* of the tokens, not a consumer of them — and mirrors
drift. When changing a token, change both, or the design system will document one thing while the
screens do another. (Found exactly this way: the kit's motion was already Carbon-correct —
70/150/240ms on `cubic-bezier(.2,0,.38,.9)` — while the design system still carried 120ms on a
lookalike curve.)

## FILE INDEX (root manifest)
- `styles.css` — global entry point (consumers link this); `@import`s all token files.
- `tokens/` — `fonts.css`, `colors.css`, `typography.css`, `spacing.css`, `controls.css`, `motion.css`.
  (No `radius-shadow.css`: the system has no radius and no elevation.)
- `components/core/`, `components/product/` — React primitives (+ `.d.ts`, `.prompt.md`, card HTML).
- `foundations/` — specimen cards.
- `ui_kits/whatthechip/` — the product screens above (seller + buyer side), sharing
  `wtc-carbon.css` (the system's real CSS), `wtc-parceiro.css`, `shell.js`, `viewport.js`.
- `assets/` — logo lockups (light/dark), favicon, product photo. `static/img/` holds the originals from the repo.
- `thumbnail.html` — project tile. `SKILL.md` — Agent-Skill wrapper.
- `design_handoff_whatthechip/` — developer handoff (roles matrix, open questions for the backend).

## CAVEATS
- **Sans = Manrope** (Google Fonts, weights 300–800: 300 on page titles, 800 on uppercase labels).
  It is a substitution for the product's Helvetica Neue — flagged. If a Helvetica Neue webfont file
  is licensed and provided, swap it in `tokens/fonts.css` and `--font-sans`.
- **Icons** are hand-drawn inline SVGs matched to Lucide (flagged substitution — no named icon lib in the source).
- **Component set** is a focused core (Button, Input, VerdictPill, RentabilityBar); more patterns live in the
  UI kit and can be promoted to components on request.
- **Dark theme** is fully wired for the public site (`[data-theme="dark"]`); the bench app shell is dark regardless.
- UI-kit demos use small in-file mock catalogs; the real data comes from the Django `/chips/search/` and
  `/estoque/` endpoints.
