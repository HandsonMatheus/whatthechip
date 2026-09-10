# -*- coding: utf-8 -*-
"""O tratamento da FOTO DE PROVA, antes de ela entrar no banco.

Este módulo existe por causa de uma conta: uma foto de celular tem 3–8 MB, e
uma conferência rende dez ou vinte delas. Guardar o original poria 160 MB de
um lote só no Postgres da Render — e o PDF teria de ler tudo isso para desenhar
imagens de 6 cm de largura. Reduzir no upload não é otimização; é o que torna a
feature possível.

Três coisas acontecem aqui, e cada uma resolve um problema real:

1. **`exif_transpose` primeiro.** Celular grava a foto sempre na mesma
   orientação física e diz no EXIF como girar. Quem redimensiona antes de
   aplicar isso entrega foto deitada — o clássico "por que a foto está de
   lado?" que aparece só no PDF, porque o navegador respeita o EXIF e o
   reportlab não.

2. **Reamostragem para caber num quadrado de lado máximo.** Mantém proporção,
   nunca AUMENTA (uma foto já pequena passa intacta) e recomprime em JPEG.

3. **O EXIF não é copiado.** Encolhe o arquivo e, mais importante, tira a
   GEOLOCALIZAÇÃO: a foto atravessa o balcão até o cliente, e a coordenada da
   bancada do comprador não tem por que ir junto.
"""
import io

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

#: O lado maior da imagem que vai ao PDF e à tela ampliada. 1600px sustenta um
#: zoom razoável numa foto de chip e cabe em ~300 KB de JPEG.
LADO_GRANDE = 1600
#: A miniatura da grade. Ela vem em TODA listagem, então é pequena de verdade.
LADO_THUMB = 240

QUALIDADE_GRANDE, QUALIDADE_THUMB = 80, 70

#: Teto do arquivo que ENTRA. Acima disso nem tentamos abrir: uma imagem
#: gigante consome memória do worker antes de qualquer validação nossa.
MAX_BYTES = 12 * 1024 * 1024

#: O que o Pillow lê sem dependência extra. ⚠ HEIC (padrão do iPhone) NÃO está
#: aqui de propósito: exigiria `pillow-heif` no requirements. Preferimos a
#: recusa explícita a uma dependência nova — e o WeChat, que é por onde as
#: fotos vinham, já converte para JPEG ao enviar.
FORMATOS = {'JPEG', 'PNG', 'WEBP'}


def _abrir(raw):
    from PIL import Image, UnidentifiedImageError
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except UnidentifiedImageError:
        raise ValidationError(
            _('Não consegui ler esta imagem. Envie JPG, PNG ou WEBP — '
              'foto de iPhone pode vir em HEIC, que ainda não lemos.'))
    except Exception:
        raise ValidationError(_('Arquivo de imagem corrompido.'))
    if img.format and img.format.upper() not in FORMATOS:
        raise ValidationError(
            _('Formato %(f)s não aceito. Use JPG, PNG ou WEBP.')
            % {'f': img.format})
    return img


def _reduz(img, lado, qualidade):
    from PIL import Image, ImageOps
    # ⚠ ANTES de qualquer redimensionamento — ver o item 1 do docstring.
    img = ImageOps.exif_transpose(img)
    if img.mode not in ('RGB', 'L'):
        # JPEG não tem canal alfa: um PNG transparente vira preto sem isto.
        fundo = Image.new('RGB', img.size, (255, 255, 255))
        img = img.convert('RGBA')
        fundo.paste(img, mask=img.split()[-1])
        img = fundo
    img.thumbnail((lado, lado), Image.LANCZOS)   # nunca aumenta
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=qualidade, optimize=True,
             progressive=True)                    # sem `exif=` → EXIF some
    return buf.getvalue(), img.width, img.height


def preparar(raw, filename=''):
    """``bytes`` de entrada → ``dict`` pronto para virar ``ProvaFoto``.

    Devolve ``data``/``thumb`` já em JPEG, mais as medidas da versão grande.
    Levanta ``ValidationError`` com mensagem que o comprador entende — ele está
    na bancada com o celular, não vai abrir um log.
    """
    if not raw:
        raise ValidationError(_('Arquivo vazio.'))
    if len(raw) > MAX_BYTES:
        raise ValidationError(
            _('Foto muito grande (%(mb).1f MB). O limite é %(lim)d MB.')
            % {'mb': len(raw) / 1024 / 1024, 'lim': MAX_BYTES // 1024 // 1024})

    img = _abrir(raw)
    grande, w, h = _reduz(img, LADO_GRANDE, QUALIDADE_GRANDE)
    thumb, _tw, _th = _reduz(_abrir(raw), LADO_THUMB, QUALIDADE_THUMB)
    return {'data': grande, 'thumb': thumb, 'mime': 'image/jpeg',
            'filename': (filename or '')[:160], 'size': len(grande),
            'width': w, 'height': h}
