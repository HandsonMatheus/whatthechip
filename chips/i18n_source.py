# -*- coding: utf-8 -*-
"""
chips/i18n_source.py — extração de msgids do CÓDIGO-FONTE (i18n — I18N.md §6.3)
================================================================================
Biblioteca usada pelo portão ``check_translations`` (verificação de COMPLETUDE:
toda string marcada no código tem que existir nos catálogos de TODOS os idiomas)
e pelo ``scripts/i18n_extract.py`` (CLI). É o "makemessages sem gettext" do
projeto: usa o MESMO pré-processador de templates do Django (``templatize``),
então os msgids saem idênticos — os .po continuam msgmerge-compatíveis.

Descoberta DINÂMICA de fontes (à prova de app novo — nada de lista hardcoded):
  - templates: ``<BASE>/templates`` + ``<app>/templates`` de todo app LOCAL
    (app cujo path vive dentro do projeto; site-packages fica de fora);
  - python:    todos os ``.py`` dos apps locais + ``core/`` (settings tem
    ``_('Português')`` etc.), excluindo ``migrations/``;
  - js:        ``static/js/*.js`` com chamadas ``gettext('…')`` (domínio
    ``djangojs``).

Cada msgid sai com as LOCALIZAÇÕES ``(arquivo, linha)`` — viram os comentários
``#:`` dos .po (rastreabilidade: Poedit/Weblate mostram onde a string vive).
"""

import io
import re
import tokenize
from pathlib import Path

from django.apps import apps as django_apps
from django.conf import settings

# ── formas emitidas pelo templatize (prefixo u obrigatório de cobrir) ─────────
_STR = r"(?:[uU]?'((?:[^'\\]|\\.)*)'|[uU]?\"((?:[^\"\\]|\\.)*)\")"
_RX_GETTEXT  = re.compile(r"(?<!p)(?<!n)gettext\(\s*" + _STR)
_RX_NGETTEXT = re.compile(r"ngettext\(\s*" + _STR)
_RX_PGETTEXT = re.compile(r"pgettext\(\s*" + _STR + r"\s*,\s*" + _STR)
_RX_JS       = re.compile(
    r"""gettext\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")\s*\)""")

GETTEXT_NAMES = {'_', 'gettext', 'gettext_lazy', '_lazy', 'ugettext',
                 'gettext_noop', 'ngettext', 'ngettext_lazy', 'pgettext',
                 'pgettext_lazy'}


def _base() -> Path:
    return Path(settings.BASE_DIR)


# ⚠ BUG REAL (2026-07-10): o venv do dono vive DENTRO do projeto
# (``chipdocs/venv/``) — sem esta exclusão, ``base in p.parents`` classificava
# django/modeltranslation/pghistory como "apps locais" e o portão varria os
# templates e ``_()`` do PRÓPRIO Django (121 templates + milhares de msgids
# falsos exigidos no catálogo). No sandbox do agente não reproduzia (pacotes
# em ``~/.local``, fora do BASE_DIR) — bug dependente de ambiente. A lista
# espelha o ``makemessages -i venv -i staticfiles`` do fluxo canônico e é
# aplicada TAMBÉM nos walkers (defesa em profundidade contra lixo aninhado).
_EXCLUDED_PARTS = frozenset({
    'venv', '.venv', 'site-packages', 'dist-packages',
    'node_modules', 'staticfiles',
})


def _excluded(path: Path) -> bool:
    return bool(_EXCLUDED_PARTS.intersection(path.parts))


def _local_app_paths():
    """Paths dos apps do PROJETO: dentro de BASE_DIR **e fora** de
    venv/site-packages (o venv mora dentro do projeto — ver nota acima)."""
    base = _base().resolve()
    seen = []
    for cfg in django_apps.get_app_configs():
        p = Path(cfg.path).resolve()
        if base in p.parents and not _excluded(p.relative_to(base)):
            seen.append(p)
    return seen


def template_files():
    dirs = [_base() / 'templates'] + [p / 'templates' for p in _local_app_paths()]
    for d in dirs:
        if d.exists():
            for path in sorted(d.rglob('*.html')):
                if not _excluded(path):
                    yield path


def python_files():
    roots = _local_app_paths() + [_base() / 'core']
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob('*.py')):
            if 'migrations' in path.parts or _excluded(path):
                continue
            yield path


def js_files():
    d = _base() / 'static' / 'js'
    if d.exists():
        yield from sorted(d.glob('*.js'))


def _unescape(m_single, m_double):
    raw = m_single if m_single is not None else m_double
    return raw.encode().decode('unicode_escape') if '\\' in raw else raw


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(_base()))
    except ValueError:
        return str(path)


def _add(out: dict, msgid: str, path: Path, line: int):
    out.setdefault(msgid, []).append((_rel(path), line))


def _scan_templatized(pseudo: str, path: Path, out: dict):
    for rx, grp in ((_RX_GETTEXT, (1, 2)), (_RX_NGETTEXT, (1, 2)),
                    (_RX_PGETTEXT, (3, 4))):
        for m in rx.finditer(pseudo):
            line = pseudo.count('\n', 0, m.start()) + 1
            _add(out, _unescape(m.group(grp[0]), m.group(grp[1])), path, line)


def _scan_python(src: str, path: Path, out: dict):
    """Tokenizer real (imune a comentário/docstring). 1º argumento-string das
    chamadas gettext; pgettext pega o 2º (msgid)."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError):
        return
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == tokenize.NAME and tok.string in GETTEXT_NAMES:
            j = i + 1
            while j < len(tokens) and tokens[j].type in (tokenize.NL, tokenize.COMMENT):
                j += 1
            if j < len(tokens) and tokens[j].type == tokenize.OP and tokens[j].string == '(':
                skip_first = tok.string.startswith('pgettext')
                j += 1
                parts, seen_comma, line = [], False, tok.start[0]
                while j < len(tokens):
                    t = tokens[j]
                    if t.type == tokenize.STRING:
                        if not skip_first or seen_comma:
                            parts.append(eval(t.string))   # literal (é STRING)
                    elif t.type == tokenize.OP and t.string == ',':
                        if skip_first and not seen_comma:
                            seen_comma = True
                        elif parts:
                            break
                    elif t.type == tokenize.OP and t.string == ')':
                        break
                    elif t.type in (tokenize.NL, tokenize.COMMENT):
                        pass
                    elif parts:
                        break
                    j += 1
                if parts:
                    _add(out, ''.join(parts), path, line)
        i += 1


def extract_django(with_locations: bool = False):
    """msgids do domínio ``django`` (templates + python). dict ou lista."""
    from django.utils.translation import templatize
    out: dict = {}
    for path in template_files():
        src = path.read_text(encoding='utf-8')
        _scan_templatized(templatize(src, origin=str(path)), path, out)
    for path in python_files():
        _scan_python(path.read_text(encoding='utf-8'), path, out)
    return out if with_locations else sorted(out)


def extract_djangojs(with_locations: bool = False):
    """msgids do domínio ``djangojs`` (static/js — chamadas gettext())."""
    out: dict = {}
    for path in js_files():
        src = path.read_text(encoding='utf-8')
        for m in _RX_JS.finditer(src):
            raw = m.group(1) if m.group(1) is not None else m.group(2)
            line = src.count('\n', 0, m.start()) + 1
            _add(out, raw.replace("\\'", "'").replace('\\"', '"'), path, line)
    return out if with_locations else sorted(out)


# ── Detector de PT NÃO-MARCADO em templates (heurística do portão) ────────────
# Português "vaza" por acento: texto visível com diacrítico fora de {% trans %}
# é quase certamente string esquecida. Linha DELIBERADAMENTE em pt-br (ex.:
# dump de debug) leva o marcador ``i18n-ok`` num comentário — fica documentada
# no próprio código, não escondida no portão.
_RX_ACCENT = re.compile(r'[ãõçáéíóúâêôàüÃÕÇÁÉÍÓÚÂÊÔÀÜ]')
# ⚠ ORDEM IMPORTA: o BLOCO blocktrans inteiro sai ANTES do regex de tag simples
# (senão a tag de abertura é consumida sozinha e o conteúdo do bloco "vaza"
# para o detector — bug real de 2026-07-08).
_RX_STRIP = [
    re.compile(r'\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}', re.S),
    re.compile(r'\{#.*?#\}', re.S),
    re.compile(r'<!--.*?-->', re.S),
    re.compile(r'\{%\s*blocktrans(?:late)?\b.*?\{%\s*endblocktrans(?:late)?\s*%\}', re.S),
    re.compile(r'\{%\s*trans(?:late)?\s.*?%\}'),                       # {% trans "…" %}
    re.compile(r'\{\{.*?\}\}', re.S),
    re.compile(r'\{%.*?%\}', re.S),
    re.compile(r'/\*.*?\*/', re.S),                                    # comentário CSS/JS
    re.compile(r'(?<![:\'"\w])//[^\n]*'),                              # // JS (não ://)
]


def unmarked_pt_in_templates():
    """[(arquivo, linha, trecho)] com cara de PT cru fora de {% trans %}."""
    hits = []
    for path in template_files():
        src = path.read_text(encoding='utf-8')
        ok_lines = {i + 1 for i, ln in enumerate(src.splitlines())
                    if 'i18n-ok' in ln}
        stripped = src
        for rx in _RX_STRIP:
            # preserva as quebras de linha p/ manter o nº da linha estável
            stripped = rx.sub(lambda m: re.sub(r'[^\n]', ' ', m.group(0)), stripped)
        for i, line in enumerate(stripped.splitlines(), 1):
            if i in ok_lines:
                continue
            if _RX_ACCENT.search(line):
                hits.append((_rel(path), i, line.strip()[:80]))
    return hits
