Action button; blue "primary" is the one call-to-action per zone. Secondary = "ghost"; destructive = "danger"; confirm = "success".

\`\`\`jsx
<Button variant="primary" onClick={submit}>Continuar triagem</Button>
<Button variant="ghost" size="sm">Cancelar</Button>
<Button variant="danger" size="sm">Fechar lote</Button>
\`\`\`

Variants: primary · ghost · danger · success. Sizes: sm (36) · md (48) · lg (56) — as alturas de `--ctl-*`. Cantos 0px (Carbon). Pass \`iconLeft\` for a leading SVG.
