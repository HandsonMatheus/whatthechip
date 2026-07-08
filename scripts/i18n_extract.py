"""
scripts/i18n_extract.py — extração de msgids SEM gettext (fallback de sandbox)
===============================================================================
O fluxo CANÔNICO de extração é `python manage.py makemessages -l <lng>` (exige
GNU gettext instalado — ver I18N.md §6.2). Este script é o FALLBACK documentado
(I18N.md §6.3) para ambientes sem gettext (ex.: sandbox de um agente): varre os
templates (via ``django.utils.translation.templatize``, o MESMO pré-processador
que o makemessages usa), os ``.py`` dos apps do projeto e o ``static/js`` e
imprime a lista de msgids por domínio (``django`` e ``djangojs``) em JSON.

Uso (na raiz do projeto, venv ativo):
    python scripts/i18n_extract.py > /tmp/msgids.json

Saída: {"django": ["msgid", ...], "djangojs": ["msgid", ...]}

⚠ NÃO substitui o makemessages para msgids com plural (ngettext) ou contexto
(pgettext) complexos — cobre o subconjunto que o projeto usa ({% trans %},
{% blocktrans trimmed %}, gettext/_ em Python, gettext() em JS). Os msgids
gerados são idênticos aos do makemessages (mesmo templatize), então os .po
continuam msgmerge-compatíveis quando o gettext estiver disponível.
"""

import io
import json
import os
import re
import sys
import tokenize
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings_test')

import django  # noqa: E402

django.setup()

from django.utils.translation import templatize  # noqa: E402

# Onde procurar (espelha o que o makemessages veria, menos venv/estáticos):
TEMPLATE_DIRS = [
    BASE / 'templates',
    BASE / 'chips' / 'templates',
    BASE / 'estoque' / 'templates',
    BASE / 'pricing' / 'templates',
]
PY_APPS = ['chips', 'estoque', 'pricing', 'tenancy', 'pages', 'core']
JS_FILES = [BASE / 'static' / 'js' / 'mic.js']   # únicos .js com gettext() hoje

# Nomes de função que marcam tradução (mesmos keywords do xgettext p/ Django):
GETTEXT_NAMES = {'_', 'gettext', 'gettext_lazy', '_lazy', 'ugettext',
                 'gettext_noop', 'ngettext', 'ngettext_lazy', 'pgettext',
                 'pgettext_lazy'}


def _msgids_from_python_source(src: str, origin: str) -> list[str]:
    """Extrai os 1ºs argumentos-string de chamadas gettext num fonte Python.

    Usa o tokenizer real (não regex): imune a comentários/aspas mistas. Para
    ngettext/pgettext pega o argumento singular/msgid (suficiente p/ o projeto).
    """
    out = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except tokenize.TokenError:
        print(f'⚠ tokenize falhou em {origin}', file=sys.stderr)
        return out

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == tokenize.NAME and tok.string in GETTEXT_NAMES:
            # Próximo token significativo tem que ser '('
            j = i + 1
            while j < len(tokens) and tokens[j].type in (tokenize.NL, tokenize.COMMENT):
                j += 1
            if j < len(tokens) and tokens[j].type == tokenize.OP and tokens[j].string == '(':
                # pgettext: o msgid é o SEGUNDO argumento — pula o contexto.
                skip_first = tok.string.startswith('pgettext')
                j += 1
                parts, seen_comma = [], False
                while j < len(tokens):
                    t = tokens[j]
                    if t.type == tokenize.STRING:
                        if not skip_first or seen_comma:
                            parts.append(eval(t.string))  # literal seguro (é STRING)
                    elif t.type == tokenize.OP and t.string == ',':
                        if skip_first and not seen_comma:
                            seen_comma = True
                        elif parts:
                            break          # 1º argumento terminou
                    elif t.type == tokenize.OP and t.string == ')':
                        break
                    elif t.type in (tokenize.NL, tokenize.COMMENT):
                        pass
                    elif parts:
                        break              # expressão no meio → não é literal puro
                    j += 1
                if parts:
                    out.append(''.join(parts))
        i += 1
    return out


# O templatize() emite pseudo-Python (feito p/ o xgettext, indentação solta) —
# o tokenize estrito do CPython rejeita. As formas emitidas são FECHADAS
# (gettext('…') / ngettext('…','…',n) / pgettext('ctx','…')), então regex basta.
# O templatize emite strings com prefixo u (``gettext(u'…')``) — o [uU]? cobre.
_STR = r"(?:[uU]?'((?:[^'\\]|\\.)*)'|[uU]?\"((?:[^\"\\]|\\.)*)\")"
_RX_GETTEXT  = re.compile(r"(?<!p)(?<!n)gettext\(\s*" + _STR)
_RX_NGETTEXT = re.compile(r"ngettext\(\s*" + _STR)
_RX_PGETTEXT = re.compile(r"pgettext\(\s*" + _STR + r"\s*,\s*" + _STR)


def _unescape(m_single, m_double):
    raw = m_single if m_single is not None else m_double
    return raw.encode().decode('unicode_escape') if '\\' in raw else raw


def _msgids_from_templatized(pseudo: str) -> list[str]:
    out = []
    for m in _RX_GETTEXT.finditer(pseudo):
        out.append(_unescape(m.group(1), m.group(2)))
    for m in _RX_NGETTEXT.finditer(pseudo):
        out.append(_unescape(m.group(1), m.group(2)))       # forma singular
    for m in _RX_PGETTEXT.finditer(pseudo):
        out.append(_unescape(m.group(3), m.group(4)))       # msgid (2º arg)
    return out


def extract_django_domain() -> list[str]:
    msgids: set[str] = set()
    # 1) Templates → templatize() (o MESMO pré-processador do makemessages) → regex
    for tdir in TEMPLATE_DIRS:
        if not tdir.exists():
            continue
        for path in sorted(tdir.rglob('*.html')):
            src = path.read_text(encoding='utf-8')
            pseudo = templatize(src, origin=str(path))
            msgids.update(_msgids_from_templatized(pseudo))
    # 2) Python dos apps
    for app in PY_APPS:
        for path in sorted((BASE / app).rglob('*.py')):
            if 'migrations' in path.parts:
                continue
            src = path.read_text(encoding='utf-8')
            msgids.update(_msgids_from_python_source(src, str(path)))
    return sorted(msgids)


_JS_GETTEXT = re.compile(
    r"""gettext\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""")


def extract_djangojs_domain() -> list[str]:
    msgids: set[str] = set()
    for path in JS_FILES:
        if not path.exists():
            continue
        for m in _JS_GETTEXT.finditer(path.read_text(encoding='utf-8')):
            raw = m.group(1) if m.group(1) is not None else m.group(2)
            msgids.add(raw.replace("\\'", "'").replace('\\"', '"'))
    return sorted(msgids)


if __name__ == '__main__':
    print(json.dumps({
        'django':   extract_django_domain(),
        'djangojs': extract_djangojs_domain(),
    }, ensure_ascii=False, indent=1))
