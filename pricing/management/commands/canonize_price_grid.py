"""
canonize_price_grid — funde as GÊMEAS de geração do grid numa passada só.

Convenção v3 (dono, 2026-07-23): variantes L/U/X dobram na geração-base
(fold_gen) — inclusive nos combos. O grid legado tem linhas gêmeas por lista
(ex.: LPDDR4 4GB e LPDDR4X 4GB na MESMA lista). Este comando resolve tudo:

  • gêmea (base + variante na mesma lista): mantém a linha-BASE e apaga a
    variante. O ¥/status VENCEDOR é o mais informativo:
        cotado > não-compro > não-fabricado > não-cotado
    (a variante cotada vence a base vazia — o ¥ real não se perde).
    Empate de DOIS COTADOS com ¥ diferentes → prevalece a BASE e o par sai
    no relatório de DIVERGÊNCIA (ajuste fino é decisão do dono, no admin).
  • variante SEM gêmea: só renomeia para a base (o save dobra sozinho).

Dry-run por padrão; --commit grava (com backup JSON antes — padrão da casa
pós-incidente ¥); --revert <arquivo> desfaz (restaura bases e recria as
variantes apagadas).

    python manage.py canonize_price_grid --company eminer
    python manage.py canonize_price_grid --company eminer --commit
    python manage.py canonize_price_grid --company eminer --revert canonize_price_grid_backup.json
"""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pricing.models import (Price, STATUS_NO_BUY, STATUS_NOT_MADE,
                            STATUS_QUOTED, STATUS_UNQUOTED, fold_gen)
from tenancy.scope import scope_command_to_company

_SCORE = {STATUS_QUOTED: 3, STATUS_NO_BUY: 2, STATUS_NOT_MADE: 1,
          STATUS_UNQUOTED: 0}
_FIELDS = ('status', 'price_min', 'price_max', 'quote_date', 'source')
_BACKUP = 'canonize_price_grid_backup.json'


def _dump(p):
    return {'pk': p.pk, 'price_list_id': p.price_list_id,
            'company_id': p.company_id, 'kind': p.kind,
            'gen': p.gen, 'tier_value': str(p.tier_value),
            'tier_unit': p.tier_unit, 'status': p.status,
            'price_min': str(p.price_min) if p.price_min is not None else None,
            'price_max': str(p.price_max) if p.price_max is not None else None,
            'quote_date': str(p.quote_date) if p.quote_date else None,
            'source': p.source}


class Command(BaseCommand):
    help = ('Convenção v3: canoniza o grid inteiro (renomeia variantes e '
            'funde gêmeas L/U/X→base). Dry-run por padrão; --commit grava.')

    def add_arguments(self, parser):
        parser.add_argument('--company', default=None)
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--revert', default=None, metavar='ARQ.json')

    # ── revert ───────────────────────────────────────────────────────────────
    def _revert(self, path):
        from datetime import date as _d
        from decimal import Decimal as _D
        with open(path) as fh:
            log = json.load(fh)

        def _restore(p, d):
            p.gen = d['gen']
            p.status = d['status']
            p.price_min = _D(d['price_min']) if d['price_min'] else None
            p.price_max = _D(d['price_max']) if d['price_max'] else None
            p.quote_date = _d.fromisoformat(d['quote_date']) if d['quote_date'] else None
            p.source = d['source']
            # bulk update SEM save(): o save dobraria o gen de novo.
            Price.all_companies.filter(pk=p.pk).update(
                gen=p.gen, status=p.status, price_min=p.price_min,
                price_max=p.price_max, quote_date=p.quote_date, source=p.source)

        with transaction.atomic():
            for item in log['renomeadas']:
                p = Price.objects.get(pk=item['pk'])
                _restore(p, item)
            recriar = []
            for item in log['fundidas']:
                base = Price.objects.get(pk=item['base']['pk'])
                _restore(base, item['base'])
                v = item['variante']
                # bulk_create pula o save() — recriar a VARIANTE via save
                # dobraria o gen de novo e colidiria com a base.
                recriar.append(Price(
                    pk=v['pk'], price_list_id=v['price_list_id'],
                    company_id=v['company_id'],
                    kind=v['kind'], gen=v['gen'],
                    tier_value=_D(v['tier_value']), tier_unit=v['tier_unit'],
                    status=v['status'],
                    price_min=_D(v['price_min']) if v['price_min'] else None,
                    price_max=_D(v['price_max']) if v['price_max'] else None,
                    quote_date=_d.fromisoformat(v['quote_date']) if v['quote_date'] else None,
                    source=v['source']))
            Price.all_companies.bulk_create(recriar)
        self.stdout.write(self.style.SUCCESS(
            f"↩ revertido: {len(log['renomeadas'])} renomeada(s) + "
            f"{len(log['fundidas'])} fusão(ões) desfeitas."))

    # ── pipeline ─────────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        scope_command_to_company(opts['company'], self.stdout)
        if opts['revert']:
            return self._revert(opts['revert'])

        variantes = [p for p in Price.objects.select_related('price_list')
                     if fold_gen(p.kind, p.gen) != p.gen]
        renomear, fundir, divergencias = [], [], []
        for v in variantes:
            base = Price.objects.filter(
                price_list_id=v.price_list_id, kind=v.kind,
                gen=fold_gen(v.kind, v.gen), tier_value=v.tier_value,
                tier_unit=v.tier_unit).first()
            if base is None:
                renomear.append(v)
                continue
            vence_variante = _SCORE[v.status] > _SCORE[base.status]
            if (v.status == base.status == STATUS_QUOTED
                    and v.price_min != base.price_min):
                divergencias.append(
                    f'{v.kind} {fold_gen(v.kind, v.gen)} {v.tier_value}'
                    f'{v.tier_unit} [{v.price_list}]: base ¥{base.price_min} '
                    f'MANTIDA · variante {v.gen} ¥{v.price_min} descartada')
            fundir.append((base, v, vence_variante))

        self.stdout.write(f'=== canonize_price_grid '
                          f"({'COMMIT' if opts['commit'] else 'DRY-RUN'}) ===")
        self.stdout.write(f'  variantes no grid: {len(variantes)} · '
                          f'renomear: {len(renomear)} · '
                          f'fundir (gêmeas): {len(fundir)}')
        if divergencias:
            self.stdout.write(self.style.WARNING(
                f'⚠ {len(divergencias)} DIVERGÊNCIA(s) de ¥ (dois cotados; '
                'prevalece a BASE — ajuste no admin se discordar):'))
            for d in sorted(divergencias):
                self.stdout.write(f'    {d}')
        if not variantes:
            self.stdout.write(self.style.SUCCESS('Grid já canônico.'))
            return
        if not opts['commit']:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN — nada gravado. Re-rode com --commit.'))
            return

        backup = {'renomeadas': [_dump(v) for v in renomear],
                  'fundidas': [{'base': _dump(b), 'variante': _dump(v)}
                               for b, v, _ in fundir]}
        with open(_BACKUP, 'w') as fh:
            json.dump(backup, fh, ensure_ascii=False, indent=1)

        with transaction.atomic():
            for base, v, vence_variante in fundir:
                if vence_variante:
                    for f in _FIELDS:
                        setattr(base, f, getattr(v, f))
                v.delete()          # some ANTES do save (libera a chave-base)
                base.save()         # valida + (no-op de fold: já é base)
            for v in renomear:
                v.save()            # o próprio save dobra o gen
        self.stdout.write(self.style.SUCCESS(
            f'✅ grid canonizado: {len(renomear)} renomeada(s), '
            f'{len(fundir)} gêmea(s) fundida(s). Backup: {_BACKUP} '
            f'(--revert desfaz).'))
