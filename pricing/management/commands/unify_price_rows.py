"""
unify_price_rows — repactuação 2026-07-27 (ESTRUTURAL): colapsa o preço dos
kinds UNIFICADOS (eMCP/uMCP/LPDDR) na lista GENÉRICA e APAGA as linhas de
marca — inclusive `not_made`, que bloquearia o fallback da resolução.

Depois disto: linha desses kinds existe SÓ na genérica; a resolução de
QUALQUER marca cai nela (marca → herança → genérica); o portão do modelo
impede recriar linha de combo/LPDDR em lista de marca; o /partner/ mostra a
seção "Unificado" uma vez só.

Fonte do valor da genérica: a própria genérica (se cotada); senão o valor
MAIS ALTO entre as linhas de marca cotadas (critério do dono, 2026-07-23:
"considera o preço mais alto"), reportado. Dry-run por padrão; --commit com
backup JSON; --revert restaura as linhas apagadas e a genérica.

    python manage.py unify_price_rows --buyer wuquan --company eminer
    python manage.py unify_price_rows --buyer wuquan --company eminer --commit
"""

import json

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from pricing.models import (Buyer, Price, PriceList, STATUS_QUOTED,
                            UNIFIED_KINDS)
from tenancy.scope import platform_scope, scope_command_to_company

_BACKUP = 'unify_price_rows_backup.json'


def _dump(p):
    return {'pk': p.pk, 'price_list_id': p.price_list_id,
            'company_id': p.company_id, 'kind': p.kind, 'gen': p.gen,
            'tier_value': str(p.tier_value), 'tier_unit': p.tier_unit,
            'status': p.status,
            'price_min': str(p.price_min) if p.price_min is not None else None,
            'price_max': str(p.price_max) if p.price_max is not None else None,
            'quote_date': str(p.quote_date) if p.quote_date else None}


class Command(BaseCommand):
    help = ('Repactuação 2026-07-27: preço de eMCP/uMCP/LPDDR vira SÓ da '
            'lista genérica (apaga linhas de marca). Dry-run por padrão.')

    def add_arguments(self, parser):
        parser.add_argument('--buyer', required=True)
        parser.add_argument('--company', default=None)
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--revert', default='', metavar='ARQ.json')

    def _revert(self, path):
        from datetime import date as _d
        with open(path) as fh:
            log = json.load(fh)
        recriar = []
        # RLS: .update()/bulk_create em linha de plataforma.
        with platform_scope():
            for d in log['genericas']:
                Price.all_companies.filter(pk=d['pk']).update(
                    status=d['status'],
                    price_min=Decimal(d['price_min']) if d['price_min'] else None,
                    price_max=Decimal(d['price_max']) if d['price_max'] else None,
                    quote_date=(_d.fromisoformat(d['quote_date'])
                                if d['quote_date'] else None))
            for d in log['apagadas']:
                # bulk_create pula o save(): o portão novo rejeitaria a
                # recriação de linha de marca (é revert, estado histórico).
                recriar.append(Price(
                    pk=d['pk'], price_list_id=d['price_list_id'],
                    company_id=d['company_id'], kind=d['kind'], gen=d['gen'],
                    tier_value=Decimal(d['tier_value']),
                    tier_unit=d['tier_unit'], status=d['status'],
                    price_min=Decimal(d['price_min']) if d['price_min'] else None,
                    price_max=Decimal(d['price_max']) if d['price_max'] else None,
                    quote_date=(_d.fromisoformat(d['quote_date'])
                                if d['quote_date'] else None)))
            Price.all_companies.bulk_create(recriar)
        self.stdout.write(self.style.SUCCESS(
            f"↩ revertido: {len(log['apagadas'])} linha(s) de marca "
            f"recriadas, {len(log['genericas'])} genéricas restauradas."))

    def handle(self, *args, **opts):
        scope_command_to_company(opts['company'], self.stdout)
        if opts['revert']:
            return self._revert(opts['revert'])
        buyer = Buyer.objects.filter(slug=opts['buyer']).first()
        if buyer is None:
            raise CommandError(f"Comprador {opts['buyer']!r} não existe.")
        generica = PriceList.all_companies.filter(
            buyer=buyer, brand__isnull=True, active=True).first()
        if generica is None:
            raise CommandError('Comprador sem lista genérica.')

        de_marca = list(Price.all_companies
                        .filter(price_list__buyer=buyer,
                                kind__in=UNIFIED_KINDS,
                                price_list__brand__isnull=False)
                        .select_related('price_list__brand'))
        gen_rows = {(p.kind, p.gen, p.tier_value, p.tier_unit): p
                    for p in Price.all_companies.filter(
                        price_list=generica, kind__in=UNIFIED_KINDS)}

        # valor da genérica quando ela não está cotada: o MAIS ALTO das marcas
        ajustes_genericas, faltantes = [], []
        por_chave = {}
        for p in de_marca:
            por_chave.setdefault((p.kind, p.gen, p.tier_value, p.tier_unit),
                                 []).append(p)
        for chave, rows in sorted(por_chave.items()):
            g = gen_rows.get(chave)
            cotadas = [r for r in rows if r.status == STATUS_QUOTED]
            if g is None:
                faltantes.append(f'{chave[0]} {chave[1] or "—"} {chave[2]}'
                                 f'{chave[3]} — SEM linha genérica (crie via '
                                 f'add_price_row)')
                continue
            if g.status != STATUS_QUOTED and cotadas:
                melhor = max(cotadas, key=lambda r: (r.price_max, r.price_min))
                ajustes_genericas.append((g, melhor))

        self.stdout.write(f"=== unify_price_rows "
                          f"({'COMMIT' if opts['commit'] else 'DRY-RUN'}) ===")
        self.stdout.write(f'  linhas de MARCA a apagar (unificados): '
                          f'{len(de_marca)} · genéricas a completar: '
                          f'{len(ajustes_genericas)}')
        for g, melhor in ajustes_genericas:
            self.stdout.write(
                f'  genérica ← {melhor.price_list.brand.name}: {g.kind} '
                f'{g.gen or "—"} {g.tier_value}{g.tier_unit} = '
                f'¥{melhor.price_min}–{melhor.price_max} (o mais alto)')
        for txt in faltantes:
            self.stdout.write(self.style.WARNING('  ⚠ ' + txt))
        if not de_marca and not ajustes_genericas:
            self.stdout.write(self.style.SUCCESS('Estrutura já unificada.'))
            return
        if not opts['commit']:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN — nada gravado. Re-rode com --commit.'))
            return

        backup = {'apagadas': [_dump(p) for p in de_marca],
                  'genericas': [_dump(g) for g, _m in ajustes_genericas]}
        with open(_BACKUP, 'w') as fh:
            json.dump(backup, fh, indent=1)
        # RLS (Camada B): linha de PLATAFORMA (company IS NULL desde
        # pricing/0021) — só o app.company_id NÃO abre a escrita.
        # ⚠ .delete() sob RLS não estoura: apaga ZERO em silêncio.
        with platform_scope():
            for g, melhor in ajustes_genericas:
                g.status = STATUS_QUOTED
                g.price_min, g.price_max = melhor.price_min, melhor.price_max
                g.quote_date = melhor.quote_date
                g.save()
            for p in de_marca:
                p.delete()
        self.stdout.write(self.style.SUCCESS(
            f'✅ estrutura unificada: {len(de_marca)} linha(s) de marca '
            f'apagadas. Backup: {_BACKUP} (--revert desfaz).'))
