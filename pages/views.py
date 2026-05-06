import re
import json
from pathlib import Path
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from .models import Page

# _content/ — fonte de verdade para todo o conteúdo editorial.
# index.html e todas as páginas são lidas direto do disco quando o arquivo
# existir em _content/{slug}.html, sem passar pelo banco (CKEditor).
# O banco ainda é usado para metadados: title, order, prev/next.
_CONTENT_DIR = Path(settings.BASE_DIR) / "_content"
_INDEX_CONTENT_PATH = _CONTENT_DIR / "index.html"


def _nav_pages():
    # 'index' (Início) e 'contato' são excluídos da sidebar
    return Page.objects.exclude(slug__in=['index', 'contato']).order_by('order')


def _fix_html_links(content):
    """Converte links no formato estático (slug.html) para URLs Django (/slug/).
    Aplicado em todo conteúdo antes de renderizar — não altera o banco."""
    return re.sub(r'href="([A-Za-z0-9_-]+)\.html"', r'href="/\1/"', content)


def _prefix_data_from_db():
    """
    Gera lista de prefixos diretamente da tabela ChipFamily.

    Substituiu o parser de regex que lia o HTML da página 'prefixos' — que era
    frágil (quebrava silenciosamente se o CKEditor reformatasse o HTML) e mantinha
    duas fontes de verdade separadas. Agora há uma única fonte: ChipFamily.

    A página 'prefixos' continua existindo como documento editorial para o usuário
    ler, mas não é mais usada como fonte de dados para a busca.
    """
    from chips.models import ChipFamily
    families = (
        ChipFamily.objects
        .filter(active=True)
        .select_related('brand')
        .order_by('brand__name', 'prefix')
    )
    return [
        {
            'prefix':    f.prefix,
            'fab':       f.brand.name,
            'tipo':      f"{f.chip_type}{' ' + f.subtype if f.subtype else ''}".strip(),
            'pn_length': f.pn_length,   # None → UI usa debounce fallback
        }
        for f in families
    ]


def home(request):
    pages = _nav_pages()

    # Lê _content/index.html direto do disco — sem passar pelo banco.
    content = _INDEX_CONTENT_PATH.read_text(encoding="utf-8")

    prefix_data  = _prefix_data_from_db()
    prefix_count = len(prefix_data)
    content = content.replace('{{PREFIX_COUNT}}', str(prefix_count))
    content = content.replace('{{PREFIX_DATA}}', json.dumps(prefix_data, ensure_ascii=False))
    content = _fix_html_links(content)

    # Objeto simples para manter compatibilidade com o template pages/page.html
    class _IndexPage:
        title   = 'Início'
        content = ''
    page = _IndexPage()
    page.content = content

    return render(request, 'pages/page.html', {
        'page': page,
        'pages': pages,
        'current_slug': 'index',
        'prev_page': None,
        'next_page': None,
    })


def page_detail(request, slug):
    page = get_object_or_404(Page, slug=slug)
    pages = _nav_pages()
    # Páginas fora da nav (ex: contato) não recebem botões prev/next
    in_nav = pages.filter(slug=slug).exists()
    prev_page = pages.filter(order__lt=page.order).last() if in_nav else None
    next_page = pages.filter(order__gt=page.order).first() if in_nav else None

    # Lê conteúdo direto de _content/{slug}.html quando o arquivo existir.
    # Isso faz de _content/ a fonte de verdade para todo conteúdo editorial,
    # igual ao que já é feito com a homepage. Editar o arquivo → mudança
    # imediata no site, sem precisar sincronizar com o banco.
    # Se o arquivo não existir (página criada só no admin), usa o banco.
    content_file = _CONTENT_DIR / f"{slug}.html"
    if content_file.exists():
        page.content = _fix_html_links(content_file.read_text(encoding="utf-8"))
    else:
        page.content = _fix_html_links(page.content or '')

    return render(request, 'pages/page.html', {
        'page': page,
        'pages': pages,
        'current_slug': slug,
        'prev_page': prev_page,
        'next_page': next_page,
    })
