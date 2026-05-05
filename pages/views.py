import re
import json
from django.shortcuts import render, get_object_or_404
from .models import Page


def _nav_pages():
    # 'index' (Início) e 'contato' são excluídos da sidebar
    return Page.objects.exclude(slug__in=['index', 'contato']).order_by('order')


def _fix_html_links(content):
    """Converte links no formato estático (slug.html) para URLs Django (/slug/).
    Aplicado em todo conteúdo antes de renderizar — não altera o banco."""
    return re.sub(r'href="([A-Za-z0-9_-]+)\.html"', r'href="/\1/"', content)


def _prefix_data_from_db():
    """Extrai prefixos da página 'prefixos' no banco — mesmo algoritmo do build.py."""
    try:
        prefixos = Page.objects.get(slug='prefixos')
        rows = re.findall(
            r'<tr>\s*<td><code>(.*?)</code></td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>',
            prefixos.content, re.DOTALL
        )
        data = [
            {
                'prefix': re.sub(r'<[^>]+>', '', p).strip(),
                'fab':    re.sub(r'<[^>]+>', '', f).strip(),
                'tipo':   re.sub(r'<[^>]+>', '', t).strip(),
            }
            for p, f, t in rows
        ]
        return data
    except Page.DoesNotExist:
        return []


def home(request):
    page = get_object_or_404(Page, slug='index')
    pages = _nav_pages()
    next_page = None  # homepage não navega para próxima

    # Substitui placeholders do build.py pelo conteúdo real do banco
    prefix_data = _prefix_data_from_db()
    prefix_count = len(prefix_data)
    content = page.content
    content = content.replace('{{PREFIX_COUNT}}', str(prefix_count))
    content = content.replace('{{PREFIX_DATA}}', json.dumps(prefix_data, ensure_ascii=False))
    content = _fix_html_links(content)

    # Cria uma cópia da página com conteúdo resolvido (sem alterar o banco)
    page.content = content

    return render(request, 'pages/page.html', {
        'page': page,
        'pages': pages,
        'current_slug': 'index',
        'prev_page': None,
        'next_page': next_page,
    })


def page_detail(request, slug):
    page = get_object_or_404(Page, slug=slug)
    pages = _nav_pages()
    # Páginas fora da nav (ex: contato) não recebem botões prev/next
    in_nav = pages.filter(slug=slug).exists()
    prev_page = pages.filter(order__lt=page.order).last() if in_nav else None
    next_page = pages.filter(order__gt=page.order).first() if in_nav else None
    page.content = _fix_html_links(page.content or '')
    return render(request, 'pages/page.html', {
        'page': page,
        'pages': pages,
        'current_slug': slug,
        'prev_page': prev_page,
        'next_page': next_page,
    })
