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
