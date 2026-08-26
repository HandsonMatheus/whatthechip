---
name: whatthechip-design
description: Use this skill to generate well-branded interfaces and assets for WhatTheChip (什么芯片), the memory-chip Part-Number identification and profitability-triage tool, either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the README.md file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.

If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

## Quick reference
- **Global CSS:** link `styles.css` (imports every token file). Tokens are unprefixed CSS custom properties: `--blue-60` (#0f62fe, primary), `--ink-*` neutrals, verdict semantics `--green-50`/`--amber-40`/`--red-60`, `--surface`/`--line`/`--text`/`--muted`, control heights `--ctl-sm/md/lg/xl` + `--shell-h`/`--row-h`, type `--fs-*`, `--sans`/`--mono`/`--cjk`, `--dur-1/2`, `--ease`. Dark bench shell: `--shell*`. **There are no radius or shadow tokens — the system is square and flat.**
- **Fonts:** Manrope (UI), IBM Plex Mono (codes/Part Numbers/figures), Noto Sans SC (什么芯片 / CJK).
- **Components:** `window.WhatTheChipDesignSystem_ed1fad` → `Button`, `Input`, `VerdictPill`, `RentabilityBar`. Load `_ds_bundle.js` after React.
- **Brand:** logo lockups in `assets/` (light + dark, badge + wordmark + 什么芯片). Blue "W" chip-pin badge. Never redraw the mark — copy the SVG.
- **Screens to imitate:** see `ui_kits/whatthechip/` — the seller side (index finder, login, painel, estoque, triagem, venda, vendas-lista, notificações, avisos) and the buyer side (parceiro preços, compras, ficha do lote, catálogo).
- **Voice:** pt-BR, terse and technical, "você", verdict words as pills, Part Numbers in mono, no decorative emoji.
- **Look:** **IBM Carbon.** Square corners (0px, everywhere), flat fills, no shadows, 1px hairline borders, dense data tables, blue primary, dark shell for the logged-in app. The signature graphic is the green/red/amber **rentability bar**.
