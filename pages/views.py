import re
import json
from pathlib import Path
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext as _
from .models import Page

# _content/ — fonte de verdade para todo o conteúdo editorial.
# index.html e todas as páginas são lidas direto do disco quando o arquivo
# existir em _content/{slug}.html, sem passar pelo banco (CKEditor).
# O banco ainda é usado para metadados: title, order, prev/next.
_CONTENT_DIR = Path(settings.BASE_DIR) / "_content"
_INDEX_CONTENT_PATH = _CONTENT_DIR / "index.html"


def _localized_content_path(slug: str):
    """Resolve o arquivo de conteúdo NO IDIOMA ATIVO (i18n — I18N.md §9).

    Convenção: ``_content/<slug>.<código>.html`` é a tradução (ex.:
    ``index.es.html``, ``index.zh-hans.html``); ``_content/<slug>.html`` é o
    original pt-br e o FALLBACK universal — página sem tradução aparece em PT,
    nunca em branco. As traduções são arquivos versionados no git (conteúdo-
    -como-código), produzidos pela rotina do I18N.md §7.

    Devolve o Path existente ou None (página só-banco).
    """
    lang = translation.get_language() or settings.LANGUAGE_CODE
    if lang != settings.LANGUAGE_CODE:
        localized = _CONTENT_DIR / f"{slug}.{lang}.html"
        if localized.exists():
            return localized
    base = _CONTENT_DIR / f"{slug}.html"
    return base if base.exists() else None


def _nav_pages():
    # Menus de fabricantes e tabela rápida foram removidos do frontend (jun/2026).
    # Retorna queryset vazio — nenhuma página de conteúdo aparece na nav.
    return Page.objects.none()


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
            'pn_length': f.pn_length,   # None → UI requer Enter explícito para classificar
        }
        for f in families
    ]


def home(request):
    pages = _nav_pages()

    # Lê _content/index[.<lang>].html direto do disco — sem passar pelo banco.
    # O idioma ativo escolhe o arquivo; sem tradução → fallback pt-br (§9 do I18N.md).
    content_path = _localized_content_path('index') or _INDEX_CONTENT_PATH
    content = content_path.read_text(encoding="utf-8")

    prefix_data  = _prefix_data_from_db()
    prefix_count = len(prefix_data)
    content = content.replace('{{PREFIX_COUNT}}', str(prefix_count))
    content = content.replace('{{PREFIX_DATA}}', json.dumps(prefix_data, ensure_ascii=False))

    # Stats strip da index — números reais do banco.
    # Formatação pt-BR: separador de milhar com espaço (ex: 12 847).
    from chips.models import Brand, KnownPart, SearchLog

    def _fmt(n):
        return f"{n:,}".replace(",", " ")

    content = content.replace('{{STAT_PARTS}}',    _fmt(KnownPart.objects.count()))
    # marcas SUPORTADAS = as que têm pelo menos uma família (classificam algo). Exclui
    # marcas-fantasma vazias (ex.: 'AMD (Xilinx)', 'Elpida') criadas por scrapers/imports
    # que inflavam o número. É o nº de yamls em chips/knowledge/ (10 em jul/2026).
    content = content.replace('{{STAT_BRANDS}}',
                              _fmt(Brand.objects.filter(families__isnull=False).distinct().count()))
    content = content.replace('{{STAT_FAMILIES}}', _fmt(prefix_count))
    content = content.replace('{{STAT_SEARCHES}}', _fmt(SearchLog.objects.count()))

    content = _fix_html_links(content)

    # Objeto simples para manter compatibilidade com o template pages/page.html
    class _IndexPage:
        title   = _('Início')     # i18n: aparece no <title> da aba
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

    # Lê conteúdo direto de _content/{slug}[.<lang>].html quando existir.
    # _content/ é a fonte de verdade editorial; o idioma ativo escolhe o
    # arquivo traduzido, com fallback pro pt-br (I18N.md §9). Se não houver
    # arquivo (página criada só no admin), usa o banco — onde o
    # modeltranslation resolve content_<lang> com fallback pt-br sozinho.
    content_file = _localized_content_path(slug)
    if content_file is not None:
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
