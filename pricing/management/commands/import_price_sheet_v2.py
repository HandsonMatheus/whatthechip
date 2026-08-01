"""
import_price_sheet_v2 — repactuação 2026-07-27: a planilha NOVA (aba única).

Formato (WuQuan_price_sheet v9+ preenchida): uma aba `Prices`, colunas
Type|Subtype|Capacity|Unified|Kingston|Micron|Nanya|SK Hynix|Samsung|SanDisk|
Toshiba-Kioxia|Other. Regras POR KIND (a "simplificação" do comprador):

  • eMCP/uMCP  → coluna UNIFIED em **FAIXA** ("90-100"; único caso de faixa
                 no sistema — portão do modelo já reflete). O valor unificado
                 é gravado em TODAS as listas cuja linha não é `not_made`
                 (+ a genérica) — o preço deixa de variar por marca.
  • LPDDR      → UNIFIED **fixo** (sujeira "3," / "8;" é limpa), mesma
                 gravação em todas as listas não-`not_made` + genérica.
  • eMMC/UFS    → UNIFIED **fixo** (correção do comprador 2026-08-01: "eMMC
                 e UFS estavam errados, são unificados" — a coluna Unified
                 sempre esteve preenchida; as colunas por marca IGNORADAS).
  • DDR         → POR MARCA (colunas E..K) + coluna **Other = GENÉRICA**.
                 O UNIFIED da seção é só referência — IGNORADO.

Semântica de célula: número = cotado · "a-b" = faixa (só combos) ·
"x" = **no_buy** (limpa o ¥) · "—" ou vazio = NÃO MEXE (mantém o estado
atual — inclusive not_made). Linha/valor igual ao atual = pulada (idempotente).
Cotações gravadas recebem `quote_date` = hoje.

Dry-run por padrão com o **diff célula a célula** (NOVO/SUBIU/CAIU/IGUAL/
no_buy); --commit grava com backup JSON antes; --revert desfaz.

    python manage.py import_price_sheet_v2 planilha.xlsx --buyer wu-quan --company eminer
    python manage.py import_price_sheet_v2 planilha.xlsx --buyer wu-quan --company eminer --commit
    python manage.py import_price_sheet_v2 --revert import_price_sheet_v2_backup.json --buyer wu-quan --company eminer
"""

import json
import re

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pricing.models import (Buyer, KIND_EMCP, KIND_UMCP, Price, PriceList,
                            STATUS_NO_BUY, STATUS_QUOTED, UNIFIED_KINDS,
                            fold_gen)
from tenancy.scope import scope_command_to_company

_BACKUP = 'import_price_sheet_v2_backup.json'
_TYPE_TO_KIND = {'emcp': 'emcp', 'umcp': 'umcp', 'ufs': 'ufs', 'emmc': 'emmc',
                 'lpddr': 'lpddr', 'ddr': 'ddr'}
# coluna → marca (índices 0-based da linha); 11 = Other → genérica (None).
_BRAND_COLS = {4: 'Kingston', 5: 'Micron', 6: 'Nanya', 7: 'SK Hynix',
               8: 'Samsung', 9: 'SanDisk', 10: 'Toshiba-Kioxia', 11: None}
_RANGE_RE = re.compile(r'^(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)$')
_NUM_RE = re.compile(r'^(\d+(?:\.\d+)?)$')
_CAP_RE = re.compile(r'^(\d+(?:\.\d+)?)(TB|GB|Gb)$')


def _clean(v):
    return str(v).strip().rstrip(',;').strip() if v is not None else ''


def _dump(p):
    return {'pk': p.pk, 'status': p.status,
            'price_min': str(p.price_min) if p.price_min is not None else None,
            'price_max': str(p.price_max) if p.price_max is not None else None,
            'quote_date': str(p.quote_date) if p.quote_date else None}


class Command(BaseCommand):
    help = ('Importa a planilha REPACTUADA (aba única, 2026-07-27). '
            'Dry-run com diff; --commit grava; --revert desfaz.')

    def add_arguments(self, parser):
        parser.add_argument('xlsx', nargs='?', default='')
        parser.add_argument('--buyer', required=True)
        parser.add_argument('--company', default=None)
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--revert', default='', metavar='ARQ.json')

    # ── revert ───────────────────────────────────────────────────────────────
    def _revert(self, path):
        with open(path) as fh:
            log = json.load(fh)
        with transaction.atomic():
            for d in log:
                Price.all_companies.filter(pk=d['pk']).update(
                    status=d['status'],
                    price_min=Decimal(d['price_min']) if d['price_min'] else None,
                    price_max=Decimal(d['price_max']) if d['price_max'] else None,
                    quote_date=(date.fromisoformat(d['quote_date'])
                                if d['quote_date'] else None))
        self.stdout.write(self.style.SUCCESS(
            f'↩ revertido: {len(log)} linha(s) restauradas.'))

    # ── parsing ──────────────────────────────────────────────────────────────
    def _tier(self, kind, raw):
        m = _CAP_RE.match(_clean(raw))
        if not m:
            return None
        v, unit = Decimal(m.group(1)), m.group(2)
        if unit == 'TB':
            v, unit = v * 1024, 'GB'
        esperado = 'Gb' if kind == 'ddr' else 'GB'
        return v if unit == esperado else None

    def _gen(self, kind, subtype):
        s = _clean(subtype)
        if kind in ('lpddr', 'ddr') and s:
            return fold_gen(kind, s.split('/')[0])
        return ''

    def _valor(self, kind, cell):
        """→ ('quoted', min, max) | ('no_buy', None, None) | None (não mexe)."""
        s = _clean(cell)
        if not s or s in ('—', '-'):
            return None
        if s.lower() == 'x':
            return (STATUS_NO_BUY, None, None)
        m = _NUM_RE.match(s)
        if m:
            v = Decimal(m.group(1))
            return (STATUS_QUOTED, v, v)
        m = _RANGE_RE.match(s)
        if m:
            if kind not in (KIND_EMCP, KIND_UMCP):
                raise CommandError(
                    f'FAIXA {s!r} em kind {kind!r} — faixa é SÓ eMCP/uMCP '
                    f'(repactuação 2026-07-27). Corrija a planilha.')
            return (STATUS_QUOTED, Decimal(m.group(1)), Decimal(m.group(2)))
        raise CommandError(f'célula ilegível: {s!r} (kind {kind!r})')

    # ── pipeline ─────────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        scope_command_to_company(opts['company'], self.stdout)
        if opts['revert']:
            return self._revert(opts['revert'])
        if not opts['xlsx']:
            raise CommandError('Informe a planilha (ou --revert).')
        try:
            import openpyxl
        except ImportError:
            raise CommandError('openpyxl não instalado.')

        buyer = Buyer.objects.filter(slug=opts['buyer']).first()
        if buyer is None:
            raise CommandError(f"Comprador {opts['buyer']!r} não existe.")
        listas = {}
        for pl in PriceList.all_companies.filter(buyer=buyer, active=True
                                                 ).select_related('brand'):
            listas[pl.brand.name if pl.brand else None] = pl

        ws = openpyxl.load_workbook(opts['xlsx'], data_only=True)['Prices']
        # (lista, kind, gen, tier) → (status, min, max)
        plano_celulas = {}
        secao = ''
        for row in ws.iter_rows(min_row=5, values_only=True):
            row = list(row) + [None] * (12 - len(row))
            tipo = _clean(row[0]).lower()
            cap = _clean(row[2])
            if tipo and not cap:                      # linha de cabeçalho de seção
                secao = _TYPE_TO_KIND.get(tipo, '')
                continue
            kind = _TYPE_TO_KIND.get(tipo, '') or secao
            if not kind or not cap:
                continue
            tier = self._tier(kind, cap)
            if tier is None:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ capacidade ilegível, pulada: {kind} {cap!r}'))
                continue
            gen = self._gen(kind, row[1])
            if kind in UNIFIED_KINDS:
                v = self._valor(kind, row[3])
                if v is None or None not in listas:
                    continue
                # ESTRUTURAL (2026-07-27): unificado vive SÓ na GENÉRICA — a
                # resolução de qualquer marca cai nela; linhas de marca desses
                # kinds foram extintas (unify_price_rows + portão do modelo).
                plano_celulas[(listas[None].pk, kind, gen, tier)] = v
            else:
                for idx, marca in _BRAND_COLS.items():
                    v = self._valor(kind, row[idx])
                    if v is None or marca not in listas:
                        continue
                    plano_celulas[(listas[marca].pk, kind, gen, tier)] = v

        # cruza com o banco
        rows_db = {(p.price_list_id, p.kind, p.gen, p.tier_value): p
                   for p in Price.objects.filter(price_list__buyer=buyer)}
        nome_por_pk = {pl.pk: (nome or 'GENERICA')
                       for nome, pl in listas.items()}
        mudancas, iguais, ausentes, protegidas = [], 0, [], 0
        for (pl_pk, kind, gen, tier), (st, mn, mx) in sorted(
                plano_celulas.items(),
                key=lambda kv: (kv[0][1], kv[0][2], kv[0][3], nome_por_pk[kv[0][0]])):
            p = rows_db.get((pl_pk, kind, gen, tier))
            if p is None:
                ausentes.append(f'{kind} {gen or "—"} {tier} [{nome_por_pk[pl_pk]}]')
                continue
            if p.status == 'not_made' and kind in UNIFIED_KINDS:
                protegidas += 1                      # unificado não ressuscita not_made
                continue
            if (p.status, p.price_min, p.price_max) == (st, mn, mx):
                iguais += 1
                continue
            antes = (f'¥{p.price_min}–{p.price_max}' if p.price_min != p.price_max
                     else f'¥{p.price_min}') if p.status == STATUS_QUOTED else p.status
            depois = (f'¥{mn}–{mx}' if mn != mx else f'¥{mn}') \
                if st == STATUS_QUOTED else st
            if st == STATUS_QUOTED and p.status == STATUS_QUOTED:
                mid_a, mid_d = (p.price_min + p.price_max) / 2, (mn + mx) / 2
                tag = 'SUBIU' if mid_d > mid_a else 'CAIU'
            elif st == STATUS_QUOTED:
                tag = 'NOVO'
            else:
                tag = 'no_buy'
            mudancas.append((p, st, mn, mx,
                             f'[{tag:>5}] {kind} {gen or "—"} {tier}'
                             f'{p.tier_unit} [{nome_por_pk[pl_pk]}]: '
                             f'{antes} → {depois}'))

        self.stdout.write(f"=== import_price_sheet_v2 "
                          f"({'COMMIT' if opts['commit'] else 'DRY-RUN'}) ===")
        self.stdout.write(f'  células na planilha: {len(plano_celulas)} · '
                          f'mudanças: {len(mudancas)} · iguais: {iguais} · '
                          f'not_made preservadas: {protegidas}')
        if ausentes:
            self.stdout.write(self.style.WARNING(
                f'  ⚠ {len(ausentes)} chave(s) SEM linha no grid (crie via '
                f'add_price_row): ' + '; '.join(sorted(set(ausentes))[:10])))
        for *_resto, txt in mudancas:
            self.stdout.write('  ' + txt)
        if not mudancas:
            self.stdout.write(self.style.SUCCESS('Nada a mudar.'))
            return
        if not opts['commit']:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN — nada gravado. Re-rode com --commit.'))
            return

        with open(_BACKUP, 'w') as fh:
            json.dump([_dump(p) for p, *_r in mudancas], fh, indent=1)
        hoje = date.today()
        with transaction.atomic():
            for p, st, mn, mx, _txt in mudancas:
                p.status, p.price_min, p.price_max = st, mn, mx
                p.quote_date = hoje if st == STATUS_QUOTED else None
                p.save()
        self.stdout.write(self.style.SUCCESS(
            f'✅ {len(mudancas)} linha(s) atualizadas. Backup: {_BACKUP} '
            f'(--revert desfaz).'))
