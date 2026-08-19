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
from django.core.exceptions import FieldError
from django.db import DatabaseError, connection
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


#: As ÚNICAS colunas de SalesOrder que este diagnóstico lê. Explícitas de
#: propósito — ver ovs_do_lote.
COLUNAS_OV = ('pk', 'number', 'status')


def ovs_do_lote(lot_pk):
    """As OVs do lote, como DICTS de 3 colunas — nunca instâncias.

    Um `SELECT *` aqui quebra contra banco mais VELHO que este código: o ORM
    pede toda coluna do modelo e o Postgres recusa a que ainda não foi
    migrada. É exatamente o cenário do dono (comando local apontando pra
    prod) e foi assim que a 1ª rodada deste diagnóstico morreu, em
    `vendas_salesorder.carrier`. Estas três colunas existem desde a
    `vendas/0001` — o diagnóstico sobrevive a qualquer deriva futura."""
    return list(SalesOrder.all_companies.filter(lot_id=lot_pk)
                .values(*COLUNAS_OV))


#: Colunas de Lot que existem desde a estoque/0001. `code_str` fica DE FORA
#: de propósito: é da estoque/0020 (2026-08-18) e não existe num banco mais
#: velho — o rótulo aqui é montado do número, que nunca muda.
COLUNAS_LOTE = ('pk', 'number', 'status', 'closed_at', 'company_id')


def lotes_seguros(qs):
    """Lotes como DICTS de colunas antigas + `rotulo`. Mesmo motivo do
    ovs_do_lote: este comando roda contra banco que pode estar ATRÁS do
    código, e um SELECT * mataria o diagnóstico no meio.

    Tenta o `code_str` (rótulo bonito, `LOT/ERE/001/08/26`) e CAI FORA para o
    número puro se a coluna ainda não existe no banco-alvo. O rótulo é
    cosmético; o diagnóstico não pode morrer por causa dele."""
    try:
        linhas = list(qs.values(*COLUNAS_LOTE, 'code_str'))
    except (DatabaseError, FieldError):
        linhas = list(qs.values(*COLUNAS_LOTE))
    saida = []
    for d in linhas:
        d['rotulo'] = d.get('code_str') or f'LOT/{d["number"]:03d}'
        saida.append(d)
    return saida


def _rotulo_empresa(b):
    return '(PLATAFORMA)' if b.company_id is None else b.company.name


def _deriva_de_migracao():
    """(faltando_no_banco, sobrando_no_banco) comparando os arquivos de
    migração DESTE código com a tabela django_migrations do banco-alvo.

    Existe porque o fluxo do dono é rodar comando LOCAL apontando
    `DATABASE_URL` para PROD (não há shell no Render — CLAUDE.md §5). Quando
    o código local está à frente, uma query comum estoura
    `column ... does not exist` no meio do diagnóstico e o erro parece do
    lote, não do ambiente. Pior: a deriva pode ser A CAUSA que se está
    investigando — código que espera coluna que o banco não tem quebra
    dentro do `except Exception` do create_draft_for_lot, em silêncio."""
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(connection)
    no_disco = set(loader.disk_migrations)
    aplicadas = set(loader.applied_migrations)
    return sorted(no_disco - aplicadas), sorted(aplicadas - no_disco)


#: Tabelas cujo INSERT nasce no fechamento do lote. Se uma delas ganhou coluna
#: NOT NULL que o código NO AR não conhece, o INSERT dele morre — e no
#: fechamento isso some dentro do `except` do create_draft_for_lot.
TABELAS_DO_FECHAMENTO = ('estoque_lot', 'vendas_salesorder',
                         'vendas_docsequence', 'vendas_salesorderline',
                         'vendas_invoice')


def colunas_que_matam_insert(tabelas=TABELAS_DO_FECHAMENTO):
    """Colunas NOT NULL SEM default no banco — as que fazem um INSERT de
    código DESATUALIZADO falhar.

    Por que isto é um portão de verdade (incidente eRecyclo, 2026-08-18): o
    `AddField` do Django adiciona a coluna com default e **em seguida remove o
    default do banco** (o Django não guarda default no Postgres). Então, se o
    banco recebeu a migração mas o código NO AR ainda não conhece o campo, o
    INSERT dele omite a coluna, o Postgres tenta NULL e a linha é recusada.
    Migrar prod com código à frente do deploy é o jeito de cair nisso.

    Devolve {tabela: [coluna, …]} só com as suspeitas."""
    achados = {}
    with connection.cursor() as cur:
        cur.execute("""
            SELECT table_name, column_name
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = ANY(%s)
               AND is_nullable = 'NO'
               AND column_default IS NULL
             ORDER BY table_name, ordinal_position
        """, [list(tabelas)])
        for tabela, coluna in cur.fetchall():
            achados.setdefault(tabela, []).append(coluna)
    return achados


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
                         .values_list('lot_id', flat=True))   # só a FK
            fechados = lotes_seguros(
                Lot.all_companies.filter(status=Lot.STATUS_CLOSED)
                .order_by('company_id', 'number'))
            nomes = dict(Company.objects.values_list('pk', 'name'))
        orfaos = [l for l in fechados if l['pk'] not in com_ov]
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
                n = InventoryEntry.all_companies.filter(lot_id=l['pk']).count()
            quando = (f'{l["closed_at"]:%d/%m/%Y}' if l['closed_at'] else '—')
            empresa = nomes.get(l['company_id'], '?')
            self.stdout.write(f'  {empresa[:16]:<16} {l["rotulo"]:<20} '
                              f'{quando:<12} {n:>8}')
        self.stdout.write(
            '\n  Conserto: python manage.py criar_ov_faltante '
            '--company <slug> [--lot <n>] --commit')

    # ── autópsia de um lote ─────────────────────────────────────────────────
    def _autopsia(self, company, alvo):
        with company_scope(company):
            todos = lotes_seguros(Lot.objects.all())
        so_numero = alvo.rstrip('/').split('/')[-3:]   # LOT/001/08/26 → '001'
        pedido = so_numero[0] if len(so_numero) == 3 else alvo
        lotes = [l for l in todos
                 if str(l['number']) == alvo or str(l['number']) == pedido
                 or l['rotulo'] == alvo]
        if not lotes:
            self.stdout.write(self.style.ERROR(
                f'  Lote {alvo!r} não existe em {company.name}.'))
            return
        lot_d = lotes[0]
        lot_pk = lot_d['pk']
        self.stdout.write(f'\n=== AUTÓPSIA: {lot_d["rotulo"]} '
                          f'({company.name}) ===')
        self.stdout.write(f'  status={lot_d["status"]} · '
                          f'fechado_em={lot_d["closed_at"] or "—"}')

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
            todas = ovs_do_lote(lot_pk)
        vivas = [s for s in todas if s['status'] != STATUS_CANCELLED]
        self.stdout.write('\n── PORTÃO 2: OV já existente ──')
        if vivas:
            for s in vivas:
                self.stdout.write(f'  · {s["number"]} status={s["status"]}')
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
            base = InventoryEntry.objects.filter(lot_id=lot_pk)
            com_chave = base.filter(price_tier_value__isnull=False)
            sem_chave = (base.filter(price_tier_value__isnull=True)
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
            f'    vendas: falha ao criar cotação do lote {lot_pk}\n'
            f'    vendas: lote {lot_pk} fechado com N comprador(es) ativo(s)\n')

    def _migracoes(self):
        """SEMPRE primeiro: sem isto, todo o resto pode ser mentira."""
        faltando, sobrando = _deriva_de_migracao()
        db = connection.settings_dict
        self.stdout.write(f'\n=== BANCO-ALVO: {db.get("NAME")} @ '
                          f'{db.get("HOST") or "localhost"} ===')
        if not faltando and not sobrando:
            self.stdout.write(self.style.SUCCESS(
                '  migrações: código e banco em dia ✓'))
            return True
        if faltando:
            self.stdout.write(self.style.ERROR(
                f'  ⚠ {len(faltando)} migração(ões) NO CÓDIGO e NÃO no banco '
                f'— este código está À FRENTE do banco-alvo:'))
            for app, nome in faltando:
                self.stdout.write(f'      {app}/{nome}')
            self.stdout.write(
                '    Consequência: query de modelo com campo novo estoura\n'
                '    "column ... does not exist" — e o erro PARECE do lote.\n'
                '    ⚠ Se este banco é o de PRODUÇÃO, o código no ar é o do\n'
                '    último deploy, NÃO este. Confira com: git ls-remote origin main')
        if sobrando:
            self.stdout.write(self.style.WARNING(
                f'  ⚠ {len(sobrando)} migração(ões) aplicadas no banco que NÃO '
                f'existem neste código — o banco está à frente:'))
            for app, nome in sobrando:
                self.stdout.write(f'      {app}/{nome}')
        self._colunas_perigosas()
        return False

    def _colunas_perigosas(self):
        """A ponte entre 'há deriva' e 'por isso o INSERT morreu'."""
        if connection.vendor != 'postgresql':
            return
        try:
            achados = colunas_que_matam_insert()
        except DatabaseError:
            return
        if not achados:
            return
        self.stdout.write(
            '\n  Colunas NOT NULL SEM default nas tabelas do fechamento — se o\n'
            '  código NO AR não conhecer alguma delas, TODO INSERT dele nessa\n'
            '  tabela falha (o AddField do Django tira o default depois de criar\n'
            '  a coluna). No fechamento do lote isso some dentro do except do\n'
            '  create_draft_for_lot e derruba a transação inteira — inclusive o\n'
            '  DocSequence, que por isso aparece como "ainda não existe".')
        for tabela, colunas in achados.items():
            self.stdout.write(f'      {tabela}: {", ".join(colunas)}')
        self.stdout.write(self.style.ERROR(
            '  ⇒ Se alguma dessas colunas é RECENTE, o conserto é DEPLOY '
            '(subir o código\n     que combina com o banco), não mexer no dado.'))

    def handle(self, *args, **opts):
        em_dia = self._migracoes()
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
            try:
                self._autopsia(company, alvo) if alvo else self._empresa(company)
            except DatabaseError as e:
                self._erro_de_schema(e, em_dia)
                return
        try:
            self._rebanho()
        except DatabaseError as e:
            self._erro_de_schema(e, em_dia)

    def _erro_de_schema(self, erro, em_dia):
        self.stdout.write(self.style.ERROR(f'\n⛔ O BANCO RECUSOU A CONSULTA: {erro}'))
        if not em_dia:
            self.stdout.write(
                '   É a deriva de migração apontada lá em cima — NÃO é o bug do\n'
                '   lote. Rode este comando com o código do DEPLOY que fez o\n'
                '   fechamento (git stash / checkout da tag), ou migre o banco.')
        else:
            self.stdout.write(
                '   As migrações estão em dia, então isto é outra coisa — '
                'guarde o erro acima.')

    def _empresa(self, company):
        """Sem --lot: só o retrato dos compradores que ela enxerga."""
        compradores = compradores_visiveis(company)
        self.stdout.write(f'\n=== COMPRADORES VISÍVEIS A {company.name} '
                          f'({len(compradores)}; o código exige 1) ===')
        for b in compradores:
            self.stdout.write(f'  · {b.name[:22]:<22} slug={b.slug:<14} '
                              f'empresa={_rotulo_empresa(b)}')
