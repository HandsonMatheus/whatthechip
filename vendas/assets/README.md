# Assets do PDF (vendas)

`wtc-logo.png` — 2400×440 RGBA, gerado do `static/img/wtc-logo-light.svg`
(o de tinta escura, para papel branco) com `cairosvg` a `scale=8`:

    import cairosvg
    from PIL import Image
    cairosvg.svg2png(url='static/img/wtc-logo-light.svg',
                     write_to='/tmp/logo.png', scale=8)
    im = Image.open('/tmp/logo.png').convert('RGBA')
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255))   # achata no branco
    Image.alpha_composite(bg, im).convert('RGB').save(
        'vendas/assets/wtc-logo.png', optimize=True)

**Achatado no branco (RGB, sem alfa) de propósito:** PNG com transparência vira
DOIS objetos no PDF (a imagem + a máscara /SMask). Em RGB é um só — arquivo
menor, e "1 imagem = 1 logo" continua verdade para quem lê o PDF.

**Por que PNG e não o SVG:** o reportlab não desenha SVG. Converter no build
exigiria `svglib`/`cairosvg` em produção (`requirements-render.txt`) por causa
de um logo — o raster commitado é determinístico e não pesa no deploy. Mesmo
padrão da fonte CJK em `pricing/fonts/`.

Mudou a marca? Rode o comando acima de novo e comite o PNG.

---

`IBMPlexMono-SemiBold.ttf` — a `--font-mono` do design system
(`tokens/typography.css`), no peso 600 que o `.dtab th` usa. Vem do pacote
`@ibm/plex-mono` (woff → ttf com `fontTools`), licença **SIL OFL 1.1** em
`LICENSE-IBMPlexMono.txt`.

Só o **cabeçalho da tabela do PDF do resultado** a usa, para o topo preto do
papel ser a mesma coisa que o topo preto da tela. O resto do documento segue
em Helvetica: a Manrope não está embutida.

**Ela não é mais estreita que a Courier.** Toda monoespaçada de texto avança
600/1000 por caractere — Plex, Courier, JetBrains Mono, Roboto Mono, as mesmas
600. O que faz a tela parecer mais apertada é o desenho da letra, não a
métrica. A quebra de linha do cabeçalho foi resolvida repartindo as colunas
(`larguras` em `vendas/pdf.py`), não trocando a fonte.

Se o arquivo não subir no deploy, `_mono_font()` cai na Courier-Bold e o PDF
continua saindo — o teste `test_o_topo_preto_usa_a_mono_do_design_system`
avisa que o fallback entrou.
