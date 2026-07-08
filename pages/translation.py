"""
pages/translation.py — registro do CMS no django-modeltranslation (I18N.md §9)
===============================================================================
Superfície 3 do i18n: o CONTEÚDO das páginas (a home, contato, fabricantes) é
DADO no banco — gettext não alcança. O modeltranslation cria colunas por idioma
(``title_es``, ``content_zh_hans``…) na MESMA tabela; ``page.title`` devolve o
idioma ativo com fallback pro pt-br (coluna-base) — página sem tradução aparece
em PT, nunca em branco.

- ``slug``/``order`` ficam FORA (são identidade/dado, não língua — a URL é a
  mesma em todo idioma, decisão §2.2 do I18N.md).
- Fonte das traduções: arquivos ``_content/<slug>.<código>.html`` versionados
  no git (ex.: ``index.es.html``), carregados por ``sync_index_page`` /
  ``import_content`` — conteúdo-como-código, mesmo trilho do resto do projeto.
"""
from modeltranslation.translator import TranslationOptions, register

from .models import Page


@register(Page)
class PageTR(TranslationOptions):
    fields = ('title', 'nav_title', 'section', 'content')
