"""
canonize_price_grid — canoniza o grid inteiro na convenção v3.1.

Fold (fonte única ``fold_gen``): DDR3L/U→DDR3 · LPDDR4X→LPDDR4 (avulso) ·
**eMCP/uMCP → gen VAZIO** ("unified by cap" da planilha v9 — dono 2026-07-24:
o combo keia SÓ pelo NAND; a geração da RAM segue nas specs, fora da chave).

Cada GRUPO (lista × kind × gen-base × tier) com grafias legadas vira UMA
linha canônica: mantém a linha já grafada na base (ou renomeia a primeira) e
o ¥/status VENCEDOR é o mais informativo:

    cotado > não-compro > não-fabricado > não-cotado

Empate de DOIS+ COTADOS com ¥ diferentes → prevalece a linha-base (ou a de
menor pk) e o grupo sai no relatório de DIVERGÊNCIA (ajuste fino é decisão
do dono, no admin).

Dry-run por padrão; --commit grava (backup JSON antes — padrão da casa);
--revert <arquivo> desfaz (restaura mantidas e recria as apagadas).

    python manage.py canonize_price_grid --company eminer
    python manage.py canonize_price_grid --company eminer --commit
    python manage.py canonize_price_grid --company eminer --revert canonize_price_grid_backup.json
"""

import json

from django.core.management.base import BaseCommand
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
    help = ('Convenção v3.1: canoniza o grid (fold de gerações — inclusive '
            'combos → gen vazio) fundindo grupos numa linha. Dry-run padrão.')

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
        with transaction.atomic():
            recriar = []
            for grupo in log['grupos']:
                m = grupo['mantida']
                Price.all_companies.filter(pk=m['pk']).update(
                    gen=m['gen'], status=m['status'],
                    price_min=_D(m['price_min']) if m['price_min'] else None,
                    price_max=_D(m['price_max']) if m['price_max'] else None,
                    quote_date=(_d.fromisoformat(m['quote_date'])
                                if m['quote_date'] else None),
                    source=m['source'])
                for v in grupo['apagadas']:
                    # bulk_create pula o save() — recriar via save dobraria o
                    # gen de novo e colidiria com a linha canônica.
                    recriar.append(Price(
                        pk=v['pk'], price_list_id=v['price_list_id'],
                        company_id=v['company_id'], kind=v['kind'],
                        gen=v['gen'], tier_value=_D(v['tier_value']),
                        tier_unit=v['tier_unit'], status=v['status'],
                        price_min=_D(v['price_min']) if v['price_min'] else None,
                        price_max=_D(v['price_max']) if v['price_max'] else None,
                        quote_date=(_d.fromisoformat(v['quote_date'])
                                    if v['quote_date'] else None),
                        source=v['source']))
            Price.all_companies.bulk_create(recriar)
        self.stdout.write(self.style.SUCCESS(
            f"↩ revertido: {len(log['grupos'])} grupo(s) restaurados."))

    # ── pipeline ─────────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        scope_command_to_company(opts['company'], self.stdout)
        if opts['revert']:
            return self._revert(opts['revert'])

        grupos = {}
        for p in Price.objects.select_related('price_list__brand').order_by('pk'):
            k = (p.price_list_id, p.kind, fold_gen(p.kind, p.gen),
                 p.tier_value, p.tier_unit)
            grupos.setdefault(k, []).append(p)

        plano, divergencias = [], []
        for (pl_id, kind, base_gen, tv, tu), rows in grupos.items():
            if len(rows) == 1 and rows[0].gen == base_gen:
                continue                       # já canônica
            # mantida = a já grafada na base; senão a 1ª (menor pk, renomeia)
            mantida = next((r for r in rows if r.gen == base_gen), rows[0])
            resto = [r for r in rows if r.pk != mantida.pk]
            vencedora = max(rows, key=lambda r: (_SCORE[r.status],
                                                 r.pk == mantida.pk))
            cotadas = {r.price_min for r in rows
                       if r.status == STATUS_QUOTED}
            if len(cotadas) > 1:
                lista = mantida.price_list
                precos = ' / '.join(
                    f'{r.gen or "—"} ¥{r.price_min}' for r in rows
                    if r.status == STATUS_QUOTED)
                divergencias.append(
                    f'{kind} {base_gen or "—"} {tv}{tu} [{lista}]: {precos} '
                    f'→ fica ¥{vencedora.price_min}')
            plano.append((mantida, resto, vencedora))

        self.stdout.write(f'=== canonize_price_grid '
                          f"({'COMMIT' if opts['commit'] else 'DRY-RUN'}) ===")
        n_apagar = sum(len(r) for _, r, _ in plano)
        self.stdout.write(f'  grupos a canonizar: {len(plano)} · '
                          f'linhas a fundir/apagar: {n_apagar}')
        if divergencias:
            self.stdout.write(self.style.WARNING(
                f'⚠ {len(divergencias)} DIVERGÊNCIA(s) de ¥ (2+ cotados no '
                'grupo; ajuste no admin se discordar):'))
            for d in sorted(divergencias):
                self.stdout.write(f'    {d}')
        if not plano:
            self.stdout.write(self.style.SUCCESS('Grid já canônico.'))
            return
        if not opts['commit']:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN — nada gravado. Re-rode com --commit.'))
            return

        backup = {'grupos': [{'mantida': _dump(m),
                              'apagadas': [_dump(r) for r in resto]}
                             for m, resto, _ in plano]}
        with open(_BACKUP, 'w') as fh:
            json.dump(backup, fh, ensure_ascii=False, indent=1)

        with transaction.atomic():
            for mantida, resto, vencedora in plano:
                campos = {f: getattr(vencedora, f) for f in _FIELDS}
                for r in resto:
                    r.delete()      # some ANTES do save (libera a chave-base)
                for f, val in campos.items():
                    setattr(mantida, f, val)
                mantida.save()      # o save dobra o gen p/ a base
        self.stdout.write(self.style.SUCCESS(
            f'✅ grid canonizado: {len(plano)} grupo(s), {n_apagar} linha(s) '
            f'fundida(s). Backup: {_BACKUP} (--revert desfaz).'))
