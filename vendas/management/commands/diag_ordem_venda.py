# -*- coding: utf-8 -*-
"""
diag_ordem_venda.py — READ-ONLY: por que o lote fechou SEM Ordem de Venda?
================================================================================
Segunda vez que acontece em prod (eRecyclo, LOT/001/08/26 — a primeira foi o K9
em 8305e0a). O `create_draft_for_lot` NUNCA levanta, por design (o fechamento
FÍSICO do lote não pode travar por causa da venda — padrão F8), então o motivo
some. Este comando refaz o caminho dele, condição por condição, e diz qual
portão fechou.

Vale para o lote específico E para o rebanho: sem `--lot`, varre TODAS as
empresas e lista todo lote fechado que está sem OV — o "quantos mais estão
assim?" que o incidente sempre levanta depois.

NÃO ESCREVE NADA. Rode com o DATABASE_URL do banco que quer inspecionar:

    python manage.py diag_ordem_venda
    python manage.py diag_ordem_venda --company erecyclo --lot 1
    python manage.py diag_ordem_venda --company erecyclo --lot LOT/001/08/26

⚠ Consertar o que ele achar é o `criar_ov_faltante`.
"""
from django.core.management.base import BaseCommand
from django.db.models import Sum

from estoque.models import InventoryEntry, Lot
from pricing.models import Buyer
from tenancy.models import Company
from tenancy.scope import company_scope, platform_scope
from vendas.models import STATUS_CANCELLED, DocSequence, SalesOrder

SEQ_SO = 'so'


def compradores_visiveis(company):
    """Os compradores que o `create_draft_for_lot` enxergaria fechando um lote
    DESTA empresa — `Buyer.objects` é PlatformSharedManager: empresa + os de
    plataforma (company IS NULL). O código exige EXATAMENTE 1 ativo."""
    with company_scope(company):
        return list(Buyer.objects.filter(active=True).order_by('pk'))


def _rotulo_empresa(b):
    return '(PLATAFORMA)' if b.company_id is None else b.company.name


class Command(BaseCommand):
    help = ('READ-ONLY: reconstitui, portão por portão, por que um lote fechado '
            'não gerou Ordem de Venda — e varre os lotes fechados sem OV.')

    def add_arguments(self, parser):
        parser.add_argument('--company', default='',
                            help='slug da empresa (obrigatório com --lot)')
        parser.add_argument('--lot', default='',
                            help='número do lote (41) ou o código (LOT/001/08/26)')

    # ── varredura ───────────────────────────────────────────────────────────
    def _rebanho(self):
        self.stdout.write('\n=== LOTES FECHADOS SEM ORDEM DE VENDA ===')
        with platform_scope():
            com_ov = set(SalesOrder.all_companies
                         .exclude(status=STATUS_CANCELLED)
                         .values_list('lot_id', flat=True))
            fechados = list(Lot.all_companies.filter(status=Lot.STATUS_CLOSED)
                            .select_related('company').order_by('company__name',
                                                                'number'))
        orfaos = [l for l in fechados if l.pk not in com_ov]
        self.stdout.write(f'  {len(fechados)} lote(s) fechado(s) · '
                          f'{len(fechados) - len(orfaos)} com OV · '
                          f'{len(orfaos)} SEM OV')
        if not orfaos:
            self.stdout.write(self.style.SUCCESS('  Nenhum órfão. ✓'))
            return
        self.stdout.write('\n  EMPRESA          LOTE                 FECHADO EM   '
                          'ENTRADAS')
        for l in orfaos:
            with platform_scope():
                n = InventoryEntry.all_companies.filter(lot=l).count()
            quando = f'{l.closed_at:%d/%m/%Y}' if l.closed_at else '—'
            self.stdout.write(f'  {l.company.name[:16]:<16} {l.code:<20} '
                              f'{quando:<12} {n:>8}')
        self.stdout.write(
            '\n  Conserto: python manage.py criar_ov_faltante '
            '--company <slug> [--lot <n>] --commit')

    # ── autópsia de um lote ─────────────────────────────────────────────────
    def _autopsia(self, company, alvo):
        with company_scope(company):
            lotes = [l for l in Lot.objects.all()
                     if str(l.number) == alvo or l.code == alvo]
        if not lotes:
            self.stdout.write(self.style.ERROR(
                f'  Lote {alvo!r} não existe em {company.name}.'))
            return
        lot = lotes[0]
        self.stdout.write(f'\n=== AUTÓPSIA: {lot.code} ({company.name}) ===')
        self.stdout.write(f'  status={lot.get_status_display()} · '
                          f'fechado_em={lot.closed_at or "—"}')

        # PORTÃO 1 — comprador ativo ÚNICO
        compradores = compradores_visiveis(company)
        self.stdout.write('\n── PORTÃO 1: comprador ativo único ──')
        self.stdout.write(f'  o código exige EXATAMENTE 1 · encontrou '
                          f'{len(compradores)}')
        for b in compradores:
            self.stdout.write(f'    · {b.name[:22]:<22} slug={b.slug:<14} '
                              f'empresa={_rotulo_empresa(b)}')
        if len(compradores) != 1:
            self.stdout.write(self.style.ERROR(
                f'  ⛔ É AQUI: {len(compradores)} ≠ 1 → create_draft_for_lot '
                f'devolve None sem criar nada.'))
            if not compradores:
                self.stdout.write(
                    '     Nenhum comprador ativo visível: ou o comprador desta '
                    'empresa está\n     inativo, ou o de PLATAFORMA (company '
                    'vazio) não existe/foi desativado.')
            else:
                self.stdout.write(
                    '     Mais de um: o sistema não tem como escolher. '
                    'Desative o que não compra\n     este lote, ou deixe só o '
                    'de plataforma.')
        else:
            self.stdout.write(self.style.SUCCESS('  ✓ passa'))

        # PORTÃO 2 — OV já existente (re-fechamento legítimo)
        with platform_scope():
            todas = list(SalesOrder.all_companies.filter(lot=lot))
        vivas = [s for s in todas if s.status != STATUS_CANCELLED]
        self.stdout.write('\n── PORTÃO 2: OV já existente ──')
        if vivas:
            for s in vivas:
                self.stdout.write(f'  · {s.number} status={s.status}')
            self.stdout.write(self.style.SUCCESS(
                '  ✓ a OV EXISTE — este lote não é o caso (o None do '
                're-fechamento é legítimo).'))
        else:
            cancel = len(todas)
            self.stdout.write(f'  nenhuma OV viva '
                              f'({cancel} cancelada(s) no histórico) → o '
                              f'código seguiria em frente')

        # PORTÃO 3 — matéria-prima das linhas
        with company_scope(company):
            com_chave = lot.entries.filter(price_tier_value__isnull=False)
            sem_chave = (lot.entries.filter(price_tier_value__isnull=True)
                         .aggregate(t=Sum('quantity'))['t'] or 0)
            n_com = com_chave.count()
            pecas = com_chave.aggregate(t=Sum('quantity'))['t'] or 0
        self.stdout.write('\n── PORTÃO 3: linhas do lote ──')
        self.stdout.write(f'  com chave de preço: {n_com} lançamento(s) / '
                          f'{pecas} peça(s) · sem chave: {sem_chave} peça(s)')
        self.stdout.write('  (lote sem NENHUMA chave ainda cria OV — com zero '
                          'linhas; não é portão)')

        # PORTÃO 4 — numerador do documento
        with platform_scope():
            seq = DocSequence.all_companies.filter(company=company,
                                                   kind=SEQ_SO).first()
        self.stdout.write('\n── PORTÃO 4: numerador da OV ──')
        self.stdout.write(f'  DocSequence(so) de {company.name}: '
                          f'{"last_number=" + str(seq.last_number) if seq else "ainda não existe (nasce no 1º uso)"}')

        self.stdout.write(
            '\n── SE NENHUM PORTÃO ACIMA EXPLICA ──\n'
            '  Sobrou exceção: o `except Exception` do create_draft_for_lot '
            'engoliu.\n  Procure no log do Render por:\n'
            f'    vendas: falha ao criar cotação do lote {lot.pk}\n'
            f'    vendas: lote {lot.pk} fechado com N comprador(es) ativo(s)\n')

    def handle(self, *args, **opts):
        alvo = (opts['lot'] or '').strip()
        slug = (opts['company'] or '').strip()
        if alvo and not slug:
            self.stdout.write(self.style.ERROR(
                '--lot exige --company <slug>.'))
            return
        if slug:
            try:
                company = Company.objects.get(slug=slug)
            except Company.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'Empresa {slug!r} não existe.'))
                return
            self._autopsia(company, alvo) if alvo else self._empresa(company)
        self._rebanho()

    def _empresa(self, company):
        """Sem --lot: só o retrato dos compradores que ela enxerga."""
        compradores = compradores_visiveis(company)
        self.stdout.write(f'\n=== COMPRADORES VISÍVEIS A {company.name} '
                          f'({len(compradores)}; o código exige 1) ===')
        for b in compradores:
            self.stdout.write(f'  · {b.name[:22]:<22} slug={b.slug:<14} '
                              f'empresa={_rotulo_empresa(b)}')
