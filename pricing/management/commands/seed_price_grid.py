"""
seed_price_grid — GRID UNIFICADO do comprador (decisão do dono, 2026-07-07).

    python manage.py seed_price_grid --buyer wuquan            # DRY-RUN
    python manage.py seed_price_grid --buyer wuquan --commit   # grava

Toda lista do comprador (cada marca + "Outras marcas") passa a ter as MESMAS
linhas — a GRADE-MESTRA = união de todas as chaves (kind, gen, faixa) que já
existem nas listas dele (o catálogo que o dono curou na planilha). Linhas
criadas entram como:

    · lista de MARCA   → "não fabricado"  (a marca não tinha o combo na
      planilha — regra do dono: ausente da planilha = não fabrica; o comprador
      corrige no /partner/ se a marca passar a fabricar)
    · "Outras marcas"  → "não cotado"     (a genérica não fabrica nada — ela
      oferece TUDO para cotação de marcas descobertas)

Idempotente (só cria o que falta; nunca altera linha existente). Dry-run por
padrão (regra de ouro #1: o dono roda o --commit).
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pricing.models import (Buyer, Price, PriceList, STATUS_NOT_MADE,
                            STATUS_UNQUOTED, UNIFIED_KINDS)
from tenancy.scope import scope_command_to_company


class Command(BaseCommand):
    help = ('Semeia o GRID UNIFICADO: toda lista do comprador ganha as mesmas '
            'linhas (marca → "não fabricado"; Outras marcas → "não cotado"). '
            'DRY-RUN por padrão; --commit grava.')

    def add_arguments(self, parser):
        parser.add_argument('--buyer', required=True, help='Slug do comprador.')
        parser.add_argument('--company', default=None,
                            help='Slug da empresa (obrigatório se houver 2+ ativas).')
        parser.add_argument('--commit', action='store_true',
                            help='Grava de verdade (sem isto: dry-run).')

    def handle(self, *args, **opts):
        scope_command_to_company(opts['company'], self.stdout)
        buyer = Buyer.all_companies.filter(slug=opts['buyer']).first()
        if buyer is None:
            raise CommandError(f"Comprador {opts['buyer']!r} não existe.")

        lists = list(PriceList.all_companies.filter(buyer=buyer, active=True)
                     .select_related('brand'))
        if not lists:
            raise CommandError('O comprador não tem nenhuma lista ativa.')

        rows = list(Price.all_companies.filter(price_list__buyer=buyer)
                    .values_list('price_list_id', 'kind', 'gen',
                                 'tier_value', 'tier_unit', 'origin'))
        master = {(k, g, tv, tu, o) for _, k, g, tv, tu, o in rows}
        existing = {}
        for pl_id, k, g, tv, tu, o in rows:
            existing.setdefault(pl_id, set()).add((k, g, tv, tu, o))

        self.stdout.write(f'Grade-mestra: {len(master)} combos '
                          f'(união das {len(lists)} listas do {buyer.name}).')

        plan = []
        for pl in lists:
            faltam = sorted(master - existing.get(pl.pk, set()))
            # Estrutura unificada: kind unificado SÓ na genérica; eMMC dual
            # (2026-08-01): o subset PHONE também é só-genérica — marca só
            # recebe o subset PCB (o portão do modelo rejeitaria o resto).
            if pl.brand_id is not None:
                faltam = [c for c in faltam
                          if c[0] not in UNIFIED_KINDS
                          and not (c[0] == 'emmc' and c[4] == 'phone')]
            status = STATUS_UNQUOTED if pl.brand_id is None else STATUS_NOT_MADE
            plan.append((pl, faltam, status))
            rotulo = pl.brand.name if pl.brand_id else 'Outras marcas'
            self.stdout.write(
                f'  {rotulo}: +{len(faltam)} linha(s) '
                f'({"não cotado" if pl.brand_id is None else "não fabricado"})')

        if not opts['commit']:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN — nada gravado. Revise e re-rode com --commit.'))
            return

        criadas = 0
        with transaction.atomic():
            for pl, faltam, status in plan:
                for (k, g, tv, tu, o) in faltam:
                    Price.all_companies.create(
                        price_list=pl, kind=k, gen=g, tier_value=tv,
                        tier_unit=tu, origin=o, status=status,
                        source='seed_price_grid (grid unificado)')
                    criadas += 1
        self.stdout.write(self.style.SUCCESS(
            f'✅ COMMIT: {criadas} linha(s) criada(s). O grid agora é o MESMO '
            'em todas as listas.'))
