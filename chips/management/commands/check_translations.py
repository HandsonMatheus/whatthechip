# -*- coding: utf-8 -*-
"""
check_translations — o PORTÃO dos catálogos de tradução (i18n — I18N.md §7).
==============================================================================
Valida os ``locale/<lng>/LC_MESSAGES/*.po`` contra as regras invioláveis da
rotina de tradução (inclusive a rotina com modelo de IA). É o análogo i18n do
``validate_convention``: **read-only**, falha alto (exit ≠ 0) e roda:

  - depois de TODA atualização de catálogo (humana ou por IA), antes do commit;
  - na suíte de testes (``chips/tests_i18n.py`` chama a mesma engine);
  - opcionalmente no CI/deploy.

O que ele barra (a tabela "classe de erro → trava" do I18N.md §7):
  1. Idioma ativado em ``settings.LANGUAGES`` sem catálogo (.po) no disco.
  2. Entrada sem tradução (msgstr vazio) ou marcada ``#, fuzzy``.
  3. Placeholders quebrados: ``%(nome)s`` faltando/sobrando/renomeado,
     ``%s``/``%d`` em quantidade errada, ``{nome}`` divergente, ``%%`` perdido.
  4. HTML quebrado: tags (<strong>, <em>, <code>, <br>…) ou entidades
     (&nbsp;…) que existem no msgid e sumiram/mudaram no msgstr.
  5. Termo PROTEGIDO traduzido (glossário DO-NOT-TRANSLATE abaixo): termos de
     domínio que têm que sobreviver intactos em QUALQUER idioma.
  6. Espaço nas bordas divergente (msgid termina com espaço e msgstr não —
     quebra concatenação em template/JS).
  7. ``.mo`` ausente ou mais velho que o ``.po`` (tradução que "não aparece").
  8. **COMPLETUDE (a trava anti-"esqueci"): string MARCADA no código que não
     existe no catálogo de algum idioma.** Extrai os msgids do código-fonte
     (``chips/i18n_source.py``, descoberta dinâmica — cobre app novo) e exige
     cada um em TODO ``.po``. É o que impede um chat de marcar e não traduzir:
     a suíte (PortaoDeCatalogoTests) roda este comando → fica vermelha.
  9. **PT NÃO-MARCADO em template** (heurística por diacrítico fora de
     ``{% trans %}``): texto cru esquecido vira erro. Exceção deliberada
     (ex.: dump de debug) leva ``i18n-ok`` num comentário NA LINHA — a
     exceção fica documentada no código, não escondida aqui.

Parser .po próprio (sem dependência): cobre o subconjunto usado no projeto
(msgid/msgstr/flags/multilinha). Uso:

    python manage.py check_translations              # todos os idiomas ativos
    python manage.py check_translations --language es
    python manage.py check_translations --allow-fuzzy   # fuzzy vira aviso
"""
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import to_locale

# ── Glossário DO-NOT-TRANSLATE (fonte única — o I18N.md §7 aponta pra cá) ────
# Termos de domínio que precisam aparecer INTACTOS no msgstr sempre que
# aparecem no msgid. São dados/termos técnicos do mercado, não língua.
PROTECTED_TERMS = [
    'WhatTheChip', 'Part Number', 'PN', 'FBGA',
    'eMCP', 'uMCP', 'eMMC', 'UFS', 'LPDDR', 'DDR', 'GDDR', 'NAND',
    'US$', 'USD', 'Octopart', 'datasheet', 'SK Hynix', 'Samsung', 'Micron',
    'Enter',
]

_RX_NAMED = re.compile(r'%\([^)]+\)[sdif]')            # %(nome)s
_RX_POS   = re.compile(r'(?<!%)%[sdif]')               # %s solto (não %%s)
_RX_BRACE = re.compile(r'\{[a-zA-Z_][a-zA-Z0-9_]*\}')  # {nome}
_RX_TAG   = re.compile(r'</?[a-zA-Z][^>]*>')           # <strong style=…> etc.
_RX_ENT   = re.compile(r'&[a-zA-Z]+;|&#\d+;')          # &nbsp; &#8230;


def _protected_rx(term: str) -> re.Pattern:
    # \b não funciona colado em han (han é word char) → lookaround ASCII manual.
    return re.compile(r'(?<![A-Za-z0-9])' + re.escape(term) + r'(?![A-Za-z0-9])')


def parse_po(path: Path) -> list[dict]:
    """Parser .po mínimo: [{'msgid', 'msgstr', 'fuzzy', 'line'}]. Ignora o
    header (msgid ""). Suporta strings multilinha e escapes do formato .po."""
    entries, cur, state = [], None, None
    def _unq(s):
        s = s[1:-1]
        return (s.replace('\\\\', '\x00').replace('\\"', '"')
                 .replace('\\n', '\n').replace('\\t', '\t')
                 .replace('\x00', '\\'))
    for lineno, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = raw.strip()
        if line.startswith('#'):
            if cur is None or cur.get('_done'):
                cur = {'msgid': '', 'msgstr': '', 'fuzzy': False, 'line': lineno}
            if line.startswith('#,') and 'fuzzy' in line:
                cur['fuzzy'] = True
            continue
        if line.startswith('msgid '):
            if cur is None or cur.get('_done'):
                cur = {'msgid': '', 'msgstr': '', 'fuzzy': False, 'line': lineno}
            cur['line'] = lineno
            cur['msgid'] += _unq(line[6:].strip())
            state = 'msgid'
        elif line.startswith('msgstr'):
            cur['msgstr'] += _unq(line.split(' ', 1)[1].strip())
            state = 'msgstr'
        elif line.startswith('"') and cur is not None and state:
            cur[state] += _unq(line)
        elif not line and cur is not None and state == 'msgstr':
            cur['_done'] = True
            if cur['msgid']:                      # pula o header
                entries.append(cur)
            state = None
    if cur is not None and not cur.get('_done') and cur.get('msgid'):
        entries.append(cur)
    return entries


def check_entry(e: dict) -> list[str]:
    """Regras 2–6 para UMA entrada. Devolve a lista de violações."""
    problems = []
    mid, mst = e['msgid'], e['msgstr']
    if e['fuzzy']:
        problems.append('fuzzy (revisar e remover a flag)')
    if not mst:
        problems.append('sem tradução (msgstr vazio)')
        return problems                            # sem msgstr, nada mais a checar
    # 3. placeholders
    if sorted(_RX_NAMED.findall(mid)) != sorted(_RX_NAMED.findall(mst)):
        problems.append(f'placeholders %(nome)s divergem: '
                        f'{_RX_NAMED.findall(mid)} → {_RX_NAMED.findall(mst)}')
    mid_pos = _RX_POS.findall(re.sub(_RX_NAMED, '', mid))
    mst_pos = _RX_POS.findall(re.sub(_RX_NAMED, '', mst))
    if mid_pos != mst_pos:
        problems.append(f'placeholders posicionais divergem: {mid_pos} → {mst_pos}')
    if sorted(_RX_BRACE.findall(mid)) != sorted(_RX_BRACE.findall(mst)):
        problems.append('placeholders {nome} divergem')
    if mid.count('%%') != mst.count('%%'):
        problems.append('escape %% diverge (literal % some/quebra o format)')
    # 4. HTML
    if _RX_TAG.findall(mid) != _RX_TAG.findall(mst):
        problems.append(f'tags HTML divergem: {_RX_TAG.findall(mid)} '
                        f'→ {_RX_TAG.findall(mst)}')
    if sorted(_RX_ENT.findall(mid)) != sorted(_RX_ENT.findall(mst)):
        problems.append(f'entidades HTML divergem: {_RX_ENT.findall(mid)} '
                        f'→ {_RX_ENT.findall(mst)}')
    # 5. glossário protegido
    for term in PROTECTED_TERMS:
        rx = _protected_rx(term)
        n_id, n_st = len(rx.findall(mid)), len(rx.findall(mst))
        if n_id and n_st < n_id:
            problems.append(f'termo protegido sumiu/traduzido: "{term}"')
    # 6. bordas
    if (mid[:1].isspace() != mst[:1].isspace()) or \
       (mid[-1:].isspace() != mst[-1:].isspace()):
        problems.append('espaço nas bordas diverge (quebra concatenação)')
    if mid.count('\n') != mst.count('\n'):
        problems.append('número de quebras de linha diverge')
    return problems


class Command(BaseCommand):
    help = 'Valida os catálogos .po/.mo (o portão da rotina de tradução — I18N.md §7).'

    def add_arguments(self, parser):
        parser.add_argument('--language', help='Só este idioma (ex.: es)')
        parser.add_argument('--allow-fuzzy', action='store_true',
                            help='Fuzzy vira aviso em vez de erro')

    def handle(self, *args, **opts):
        base = Path(settings.BASE_DIR)
        langs = [code for code, _n in settings.LANGUAGES
                 if code != settings.LANGUAGE_CODE]
        if opts['language']:
            if opts['language'] not in langs:
                raise CommandError(
                    f'"{opts["language"]}" não está em settings.LANGUAGES '
                    f'(ou é o idioma-fonte).')
            langs = [opts['language']]

        # Domínios exigidos = os que existem para QUALQUER idioma ativo.
        domains = set()
        for code in langs:
            d = base / 'locale' / to_locale(code) / 'LC_MESSAGES'
            domains.update(p.stem for p in d.glob('*.po')) if d.exists() else None
        domains = sorted(domains) or ['django']

        # Regra 8 (COMPLETUDE): msgids extraídos do CÓDIGO — todo catálogo
        # precisa contê-los. Import tardio: a lib usa templatize (setup pronto).
        from chips.i18n_source import (extract_django, extract_djangojs,
                                       unmarked_pt_in_templates)
        source_ids = {
            'django':   extract_django(with_locations=True),
            'djangojs': extract_djangojs(with_locations=True),
        }

        total_err = 0

        # Regra 9: PT cru (não marcado) em template — antes dos catálogos,
        # porque string não marcada nem chega a virar msgid.
        for f, line, trecho in unmarked_pt_in_templates():
            self.stderr.write(self.style.ERROR(
                f'✗ NÃO-MARCADA {f}:{line} «{trecho}» — texto PT fora de '
                f'{{% trans %}}. Marque (MULTILANGUAGE.md §7) ou, se for '
                f'deliberado (debug), anote "i18n-ok" na linha.'))
            total_err += 1
        for code in langs:
            locdir = base / 'locale' / to_locale(code) / 'LC_MESSAGES'
            for domain in domains:
                po_path = locdir / f'{domain}.po'
                mo_path = locdir / f'{domain}.mo'
                tag = f'{code}/{domain}'
                if not po_path.exists():
                    self.stderr.write(self.style.ERROR(
                        f'✗ {tag}: catálogo AUSENTE ({po_path}) — idioma ativado '
                        f'sem tradução (regra 1).'))
                    total_err += 1
                    continue
                entries = parse_po(po_path)
                n_err = 0
                # Regra 8: completude — marcado no código ⊆ catálogo.
                po_ids = {e['msgid'] for e in entries}
                for msgid, locs in sorted(source_ids.get(domain, {}).items()):
                    if msgid not in po_ids:
                        onde = ', '.join(f'{f}:{l}' for f, l in locs[:3])
                        self.stderr.write(self.style.ERROR(
                            f'✗ {tag}: FALTA no catálogo «{msgid[:60]}» '
                            f'(marcada em {onde}) — string marcada sem '
                            f'tradução. Rode a rotina (MULTILANGUAGE.md §7.2).'))
                        n_err += 1
                for e in entries:
                    probs = check_entry(e)
                    if opts['allow_fuzzy']:
                        probs = [p for p in probs if not p.startswith('fuzzy')]
                    for p in probs:
                        self.stderr.write(self.style.ERROR(
                            f'✗ {tag}:{e["line"]} «{e["msgid"][:60]}» — {p}'))
                        n_err += 1
                # 7. .mo presente e fresco
                if not mo_path.exists():
                    self.stderr.write(self.style.ERROR(
                        f'✗ {tag}: .mo AUSENTE — compile (compilemessages ou '
                        f'scripts/i18n_compile.py). O runtime lê o .mo (§8.6).'))
                    n_err += 1
                elif mo_path.stat().st_mtime < po_path.stat().st_mtime:
                    self.stderr.write(self.style.ERROR(
                        f'✗ {tag}: .mo mais VELHO que o .po — recompile.'))
                    n_err += 1
                total_err += n_err
                if n_err == 0:
                    self.stdout.write(self.style.SUCCESS(
                        f'✓ {tag}: {len(entries)} entradas OK'))

        if total_err:
            raise CommandError(
                f'{total_err} problema(s) de tradução — o catálogo NÃO está '
                f'publicável. Corrija e rode de novo (I18N.md §7).')
        self.stdout.write(self.style.SUCCESS('Catálogos publicáveis. ✓'))
