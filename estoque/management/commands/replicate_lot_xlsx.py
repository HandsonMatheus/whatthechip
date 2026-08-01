"""
replicate_lot_xlsx — DEV/teste: replica um LOTE a partir do export .xlsx.

Nasceu na repactuação (2026-07-31): o dono quer ver como o lote ABERTO de
produção fica sob a convenção NOVA de preços (unificado, faixa nos combos,
per-die GB…) SEM tocar a prod — replica no localhost e testa a valoração
viva, a OV draft (ponto MÉDIO da faixa) e as caixas.

Lê só **PN + Qty** do export (as demais colunas são snapshot da prod —
ignoradas de propósito); cada PN passa pelo ``classify()`` LOCAL e a entrada
nasce com o snapshot + chave de preço DAQUI — é exatamente o ponto: ver o
mesmo material sob o engine/grid novos.

⚠ BYPASSA o portão da bancada DE PROPÓSITO (não confirmado / não rentável /
sem rentabilidade entram mesmo assim): isto é uma RÉPLICA do que JÁ ESTÁ em
produção, não um lançamento novo. O resumo conta quantos NÃO passariam no
portão de hoje — é dado de teste, não aprovação. Uso local; desfazer =
apagar o lote no admin (nada além do lote é tocado).

    python manage.py replicate_lot_xlsx lote_042.xlsx --company eminer
    python manage.py replicate_lot_xlsx lote_042.xlsx --company eminer --commit
"""

import os
from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db import transaction

from core.safe_command import SafeWriteCommand


class Command(SafeWriteCommand):
    help = ('Replica um lote a partir do EXPORT .xlsx (PN+qtd), reclassificando '
            'tudo no engine LOCAL — teste da convenção nova de preços. '
            'Dry-run por padrão; --commit cria o lote.')

    def add_arguments(self, parser):
        parser.add_argument('xlsx', help='Export do lote (.xlsx).')
        parser.add_argument('--company', default=None,
                            help='Slug da empresa (obrigatório se houver 2+ ativas).')
        parser.add_argument('--operator', default='',
                            help='Username do operador do lote (default: 1º superuser).')
        parser.add_argument('--commit', action='store_true',
                            help='Cria o lote de verdade (sem isto: dry-run).')

    def handle(self, *args, **opts):
        from tenancy.scope import scope_command_to_company
        company = scope_command_to_company(opts.get('company'),
                                           stdout=self.stdout)

        try:
            import openpyxl
        except ImportError:
            raise CommandError('openpyxl não instalado.')
        if not os.path.exists(opts['xlsx']):
            raise CommandError(f"arquivo não existe: {opts['xlsx']}")

        User = get_user_model()
        if opts['operator']:
            operator = User.objects.filter(username=opts['operator']).first()
            if operator is None:
                raise CommandError(f"usuário {opts['operator']!r} não existe.")
        else:
            operator = User.objects.filter(is_superuser=True).first()
            if operator is None:
                raise CommandError('nenhum superuser — informe --operator.')

        ws = openpyxl.load_workbook(opts['xlsx'], data_only=True).worksheets[0]
        linhas = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            pn = str(row[0] or '').strip()
            if not pn or pn.upper() == 'TOTAL':
                continue
            try:
                qty = max(1, int(row[2] or 1))
            except (TypeError, ValueError):
                qty = 1
            linhas.append((pn, qty))
        if not linhas:
            raise CommandError('nenhuma linha PN no export.')

        # ── projeção: classify LOCAL linha a linha ───────────────────────────
        from chips.engine import assess_profitability, classify
        from estoque.views import (_is_confirmed, _price_key_fields,
                                   _snapshot)

        preparadas, sem_chave, barrados = [], Counter(), Counter()
        for pn, qty in linhas:
            r = classify(pn)
            snap = _snapshot(r)
            snap.pop('confidence', None)
            key = _price_key_fields(r)
            if key.get('price_key_reason'):
                sem_chave[key['price_key_reason']] += 1
            prof = assess_profitability(r)
            if not _is_confirmed(r):
                barrados['não confirmado (iria pra fila hoje)'] += 1
            elif prof == 'NÃO RENTÁVEL':
                barrados['não rentável (iria pro descarte hoje)'] += 1
            elif prof != 'RENTÁVEL':
                barrados['sem rentabilidade (botão desabilitado hoje)'] += 1
            preparadas.append((pn, qty, snap, key))

        total_un = sum(q for _p, q in linhas)
        self.stdout.write(f"=== replicate_lot_xlsx "
                          f"({'COMMIT' if opts['commit'] else 'DRY-RUN'}) ===")
        self.stdout.write(f'  {len(preparadas)} PNs · {total_un} un. · '
                          f'com chave de preço: '
                          f'{len(preparadas) - sum(sem_chave.values())} · '
                          f'sem chave: {sum(sem_chave.values())}')
        for motivo, n in sem_chave.most_common(8):
            self.stdout.write(f'    sem chave · {n:>3}× {motivo}')
        for rotulo, n in barrados.most_common():
            self.stdout.write(f'    portão   · {n:>3}× {rotulo}')
        if not opts['commit']:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN — nada criado. Re-rode com --commit.'))
            return

        from chips.models import CatalogVersion
        from estoque.models import InventoryEntry, Lot
        versao = CatalogVersion.current()
        with transaction.atomic():
            lot = Lot.open_for_company(
                company, operator,
                f'réplica de {os.path.basename(opts["xlsx"])} (teste da '
                f'convenção nova — replicate_lot_xlsx)')
            for pn, qty, snap, key in preparadas:
                InventoryEntry.objects.create(
                    lot=lot, part_number=pn, quantity=qty,
                    snapshot_catalog_version=versao, **snap, **key)
        self.stdout.write(self.style.SUCCESS(
            f'✅ Lote #{lot.number:03d} criado com {len(preparadas)} entradas '
            f'({total_un} un.). Abra /estoque/ e confira a valoração '
            f'(faixa = ponto médio na OV). Desfazer: apagar o lote no admin.'))
