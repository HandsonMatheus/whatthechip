# -*- coding: utf-8 -*-
"""
auditar_planilha_comprador.py — READ-ONLY: no QUE ele mexeu antes de devolver?

O comprador exporta a compra, trabalha na planilha e devolve o arquivo mexido
(`vendas/planilha.py` documenta a ida; `vendas/planilha_auditoria.py`, a volta).
Numa compra de 105 categorias e 434 PNs, "ele mexeu em vários preços" não se
confere no olho — e conferir no olho é onde some o desconto que ninguém viu.

Este comando põe a planilha ao lado da ORDEM DE VENDA e diz, linha a linha, o
que difere: preço, quantidade enviada, recusa e as somas. Depois separa o que
a diferença CUSTA em duas contas que não podem se misturar:

  · a RECUSA — direito dele, e o sistema tem campo para ela (`SettlementLine.
    qty_rejected`). "Mandei 10, chegou 1 danificado, pago 9" é o combinado;
  · a REPRECIFICAÇÃO — ele reescrever o ¥ unitário que a OV CONGELOU. Também
    tem campo (`SettlementLine.new_unit_rmb`), e é uma NEGOCIAÇÃO, não um
    lançamento: é a conta que precisa aparecer separada para ser respondida.

Somadas, as duas dão o total dele e a diferença "fecha" — e é justamente por
fechar que passar batido é fácil.

  NÃO ESCREVE NADA. Nem no banco, nem na planilha de entrada. Rode com o
  DATABASE_URL do banco que quer conferir (regra de ouro §2.1: quem aponta
  para produção é o dono):

    python manage.py auditar_planilha_comprador arquivo.xlsx
    python manage.py auditar_planilha_comprador arquivo.xlsx --so EMIN-SO-2026-0004
    python manage.py auditar_planilha_comprador arquivo.xlsx --out diferencas.xlsx
    python manage.py auditar_planilha_comprador arquivo.xlsx --sem-banco

⚠ `--sem-banco` compara contra a ABA CHIPS do próprio arquivo em vez da OV.
  Serve para dar uma resposta antes de ter o banco na mão, e só: a aba Chips é
  TESTEMUNHA (ele quase nunca desce até os 434 PNs, então o ¥ de lá costuma ser
  o que saiu do sistema), nunca JUIZ. Quem decide preço é a linha congelada.

⚠ ESCOPO, e este é o buraco da casa (CLAUDE.md §7): comando roda fora de
  request ⇒ zero GUC ⇒ o RLS devolve ZERO LINHAS EM SILÊNCIO. Aqui o zero
  seria a resposta mais perigosa possível — "nenhuma diferença encontrada",
  que é exatamente o que autoriza pagar sem discutir. Por isso o comando abre
  `platform_scope()` + `company_scope()` e ABORTA GRITANDO se a OV vier sem
  linha nenhuma, em vez de imprimir um relatório limpo sobre o nada.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from vendas import planilha_auditoria as pa
from vendas.planilha_auditoria import FRASE

ZERO = Decimal('0.00')

#: As colunas de `SalesOrderLine` que este comando lê — TODAS da `vendas/0001`.
#: Explícitas pelo mesmo motivo do `diag_ordem_venda`: um `SELECT *` do ORM
#: pede toda coluna do MODELO e o Postgres recusa a que o banco ainda não
#: migrou. O cenário é exatamente este (comando local apontando para prod).
COLUNAS_LINHA = ('pk', 'brand', 'kind', 'gen', 'tier_value', 'tier_unit',
                 'quantity', 'unit_rmb')


def _chaves(marca, caixa, tipo, capacidade):
    """As DUAS chaves pelas quais uma linha da planilha acha a do banco.

    A primária é (marca, CAIXA WTC) — o código de caixa é função da chave de
    preço menos a marca (`CategoryCode.label_for_key`), então o par identifica
    a linha sem ambiguidade e é o vocabulário que ele e a bancada compartilham.

    A secundária existe porque a caixa pode faltar dos dois lados: '—' quando
    o PN não tem chave de preço, e vazia num export antigo. Cair para
    (marca, tipo, capacidade) recupera a linha; não casar NADA reporta como
    'sumiu', que é o alarme certo — e não um silêncio."""
    m = pa.normaliza(marca)
    cx = pa.normaliza(caixa)
    principal = (m, cx) if cx and cx != '—' else None
    return principal, (m, pa.normaliza(tipo), pa.normaliza(capacidade))


def linhas_da_ordem(codigo, slug):
    """A verdade: as linhas CONGELADAS da OV, já com rótulo e caixa.

    Devolve ``(cabecalho, [linha, ...])``. Roda dentro do escopo — ver o ⚠ do
    módulo. Levanta `CommandError` quando não acha a ordem OU quando ela vem
    sem linha: o zero silencioso é o inimigo deste comando."""
    from pricing.models import CategoryCode
    from tenancy.models import Company
    from tenancy.scope import company_scope, platform_scope
    from vendas.models import SalesOrder, SalesOrderLine

    # A OV se acha FORA do escopo de propósito: é ela que DIZ de qual empresa
    # é o escopo. `all_companies` aqui é escape de plataforma explícito
    # (auditável por grep), e a busca é por UM código — não por "todas".
    qs = SalesOrder.all_companies.all()
    if slug:
        try:
            qs = qs.filter(company=Company.objects.get(slug=slug))
        except Company.DoesNotExist:
            raise CommandError('Empresa com slug %r não existe.' % slug)
    if codigo:
        qs = qs.filter(code_str=codigo)
    achadas = list(qs.values('pk', 'company_id', 'number', 'status',
                             'code_str', 'lot_id', 'total_rmb'))
    if codigo and not achadas:
        raise CommandError(
            'Nenhuma Ordem de Venda com código %r neste banco. Confira o '
            'DATABASE_URL — apontar para o banco errado é a forma silenciosa '
            'de este comando não achar diferença nenhuma.' % codigo)
    if len(achadas) != 1:
        raise CommandError(
            'A planilha não diz de qual ordem é (ou há %d candidatas). '
            'Informe --so <código>.' % len(achadas))
    ov = achadas[0]

    with platform_scope():
        with company_scope(ov['company_id']):
            cruas = list(SalesOrderLine.all_companies
                         .filter(order_id=ov['pk']).values(*COLUNAS_LINHA))
            # Recusa/repreciação JÁ registradas no sistema — para separar
            # "ele escreveu na planilha" de "ele já lançou aqui dentro".
            registrado = _acertos_registrados(ov['pk'])
            linhas = []
            for c in cruas:
                obj = SalesOrderLine(**c)
                # create=False, SEMPRE: cunhar código de caixa a partir de uma
                # auditoria é criar vocabulário lendo — e código de caixa é
                # eterno (CLAUDE.md §7, F12).
                caixa = CategoryCode.label_for_key(
                    c['kind'], c['gen'], c['tier_value'], c['tier_unit'],
                    create=False) or '—'
                ja = registrado.get(c['pk'], {})
                linhas.append({
                    'pk': c['pk'],
                    'marca': c['brand'] or '—',
                    'tipo': obj.type_label,
                    # `capacity_label` e '' na chave PLANA (K9, sem
                    # capacidade de proposito); a planilha escreve '—'.
                    'capacidade': obj.capacity_label or '—',
                    'caixa': caixa,
                    'qty': c['quantity'],
                    'unit': c['unit_rmb'],
                    'rec_sistema': ja.get('qty_rejected'),
                    'unit_sistema': ja.get('new_unit_rmb'),
                })
    if not linhas:
        raise CommandError(
            'A ordem %s existe e voltou com ZERO linhas. Isso não é "ordem '
            'vazia": sob RLS, comando fora de request lê zero em silêncio '
            '(CLAUDE.md §7). Rode como o dono do banco e confira o escopo — '
            'não interprete como "ele não mudou nada".'
            % (ov['code_str'] or ov['number']))
    return ov, linhas


def _acertos_registrados(order_pk):
    """``{order_line_id: {'qty_rejected', 'new_unit_rmb'}}`` do acerto vivo.

    Fica isolado num try/except porque `Settlement`/`SettlementLine` são da
    `vendas/0003`: contra um banco mais velho o SELECT quebra, e a ausência do
    acerto não pode derrubar a auditoria de PREÇO, que é o que se veio ver."""
    try:
        from vendas.models import SettlementLine
        return {r['order_line_id']: r for r in SettlementLine.all_companies
                .filter(settlement__order_id=order_pk)
                .values('order_line_id', 'qty_rejected', 'new_unit_rmb')}
    except Exception:
        return {}


def referencia_da_aba_chips(chips):
    """O preço ORIGINAL reconstruído da aba de detalhe, quando não há banco.

    Agrega os 434 PNs por (marca, caixa) e devolve o ¥ unitário — que é
    constante dentro do par, por construção: a caixa É a chave de preço menos
    a marca. Se dois PNs do mesmo par trouxerem ¥ diferente, ele editou a aba
    Chips também, e aí a testemunha está contaminada: devolvemos o conflito em
    vez de escolher um dos dois em silêncio."""
    por_chave, conflitos = {}, []
    for l in chips['linhas']:
        if l['unit'] is None:
            continue
        ch = (pa.normaliza(l['marca']), pa.normaliza(l['caixa']))
        anterior = por_chave.setdefault(ch, {'unit': l['unit'], 'qty': ZERO,
                                             'marca': l['marca'],
                                             'caixa': l['caixa'], 'pns': 0})
        if anterior['unit'] != l['unit']:
            conflitos.append((l['marca'], l['caixa'], anterior['unit'],
                              l['unit'], l['pn']))
        anterior['qty'] += l['qtd'] or ZERO
        anterior['pns'] += 1
    return por_chave, conflitos


def compara(planilha, banco):
    """O coração: casa linha a linha e devolve os ACHADOS, já classificados.

    Cada achado é um dicionário com o de/para e o impacto em ¥. A classificação
    NÃO é cosmética — ela separa o que é direito dele (recusa) do que é
    proposta de renegociação (preço) e do que não deveria existir (mexer na
    quantidade ENVIADA, que é o que o cliente despachou e a planilha só
    informa). Um relatório que soma os três num número só responde "quanto" e
    esconde "por quê", e é o "por quê" que se responde numa conversa."""
    por_caixa, por_rotulo = {}, {}
    for b in banco:
        principal, secundaria = _chaves(b['marca'], b['caixa'], b['tipo'],
                                        b['capacidade'])
        if principal:
            por_caixa.setdefault(principal, []).append(b)
        por_rotulo.setdefault(secundaria, []).append(b)

    achados, usados = [], set()
    for p in planilha['linhas']:
        principal, secundaria = _chaves(p['marca'], p['caixa'], p['tipo'],
                                        p['capacidade'])
        cand = (por_caixa.get(principal) if principal else None) \
            or por_rotulo.get(secundaria) or []
        # Ambiguidade não se resolve por sorteio: duas linhas do banco para a
        # mesma linha da planilha viram achado próprio, e a conta fica de fora.
        if len(cand) > 1:
            achados.append({'tipo_achado': 'ambigua', 'planilha': p,
                            'banco': None, 'candidatas': len(cand)})
            continue
        b = cand[0] if cand else None
        if b is None:
            achados.append({'tipo_achado': 'so_na_planilha', 'planilha': p,
                            'banco': None})
            continue
        usados.add(b['pk'])
        achados.append(_confere(p, b))

    for b in banco:
        if b['pk'] not in usados:
            achados.append({'tipo_achado': 'so_no_banco', 'planilha': None,
                            'banco': b})
    return achados


def _confere(p, b):
    """Uma linha da planilha contra a linha congelada. Todas as diferenças,
    não só a primeira — ele mexeu em preço E quantidade na mesma linha em pelo
    menos um caso, e parar no primeiro achado esconderia o segundo."""
    unit_db = b['unit']
    unit_pl = p['unit']
    env_db = Decimal(b['qty'])
    env_pl = p['enviados']
    rec = p['recusados'] or ZERO
    apr = p['aprovados']

    # APROVADOS é o que ele efetivamente paga. Preferimos o que ELE escreveu;
    # sem isso, deduzimos de enviados − recusados. Nunca o contrário: deduzir
    # por cima do que ele escreveu seria discutir com o próprio documento.
    if apr is None:
        apr = (env_db if env_pl is None else env_pl) - rec

    diffs = []
    if unit_db is not None and unit_pl is not None and unit_pl != unit_db:
        diffs.append('preco')
    if unit_pl is None and unit_db is not None:
        diffs.append('preco_apagado')
    if env_pl is not None and env_pl != env_db:
        diffs.append('enviados')
    if rec:
        diffs.append('recusa')
    # A CONTA DELE fecha? Duas identidades que a planilha do sistema mantém.
    if env_pl is not None and apr is not None and (env_pl - rec) != apr:
        diffs.append('conta_aprovados')
    if (p['resultado'] is not None and unit_pl is not None
            and apr is not None and p['resultado'] != apr * unit_pl):
        diffs.append('conta_resultado')

    # ── O QUANTO CUSTA, decomposto ──────────────────────────────────────
    # Referência = o que a OV congelou: enviados × ¥ congelado.
    valor_ov = (env_db * unit_db) if unit_db is not None else None
    base = unit_db if unit_db is not None else unit_pl
    perda_recusa = ((env_db - apr) * base
                    if (base is not None and apr is not None) else None)
    perda_preco = (apr * (unit_db - unit_pl)
                   if (unit_db is not None and unit_pl is not None
                       and apr is not None) else None)
    valor_dele = (apr * unit_pl) if (unit_pl is not None
                                     and apr is not None) else None
    return {
        'tipo_achado': 'linha', 'planilha': p, 'banco': b,
        'diffs': diffs, 'aprovados': apr,
        'valor_ov': valor_ov, 'valor_dele': valor_dele,
        'perda_recusa': perda_recusa, 'perda_preco': perda_preco,
    }


# ── APRESENTAÇÃO ────────────────────────────────────────────────────────────
def _y(v, casas=2):
    """¥ legível. `None` vira '—' e NUNCA 0,00: 'sem preço' e 'de graça' são
    fatos diferentes e a diferença some se os dois virarem zero."""
    if v is None:
        return '—'
    q = Decimal(v).quantize(Decimal('0.01') if casas else Decimal('1'))
    inteiro, _, dec = str(abs(q)).partition('.')
    grupos = ''
    while len(inteiro) > 3:
        grupos, inteiro = '.' + inteiro[-3:] + grupos, inteiro[:-3]
    txt = inteiro + grupos + ((',' + dec) if casas else '')
    return ('−' if q < 0 else '') + txt


def _q(v):
    """Quantidade é PEÇA: inteiro, sempre. `Decimal('193')` impresso como
    '193.00' num relatório de chips lê como preço e faz a coluna inteira
    parecer dinheiro."""
    if v is None:
        return '—'
    d = Decimal(v)
    return str(int(d)) if d == d.to_integral_value() else str(d)


def _ao_lado(entrada):
    """`.../arquivo.xlsx` → `.../arquivo - PINTADA.xlsx`.

    Ao lado do original e com nome diferente: sobrescrever a entrada apagaria
    a prova do que ele mandou, e é a prova que sustenta a conversa."""
    import os
    raiz, ext = os.path.splitext(entrada)
    return '%s - PINTADA%s' % (raiz, ext or '.xlsx')


def _rotulo(d):
    return '%s · %s %s · %s' % (d['marca'], d['tipo'], d['capacidade'],
                                d['caixa'])


def _rot(a):
    """O rótulo do achado, preferindo a referência e caindo para a planilha.

    Em `--sem-banco` a referência é a aba Chips agregada por (marca, caixa) —
    ela não tem tipo nem capacidade da CHAVE DE PREÇO (o tipo do PN é o do
    chip: 'LPDDR4X' onde a chave é 'LPDDR4'). Sem a queda, o relatório inteiro
    sairia 'Micron ·   · F-15', que é ilegível justamente no modo em que o
    leitor ainda não tem o banco para consultar."""
    b, p = a.get('banco'), a.get('planilha')
    if b and (b.get('tipo') or b.get('capacidade')):
        return _rotulo(b)
    if p:
        return _rotulo(p)
    return _rotulo(b)


def _tabela(escreve, cabecalho, largura, linhas):
    if not linhas:
        return
    escreve('  ' + '  '.join(t.ljust(w) if i == 0 else t.rjust(w)
                             for i, (t, w) in enumerate(zip(cabecalho, largura))))
    escreve('  ' + '  '.join('─' * w for w in largura))
    for ln in linhas:
        escreve('  ' + '  '.join(str(t).ljust(w) if i == 0
                                 else str(t).rjust(w)
                                 for i, (t, w) in enumerate(zip(ln, largura))))


class Command(BaseCommand):
    help = ('READ-ONLY: compara a planilha devolvida pelo comprador com as '
            'linhas congeladas da Ordem de Venda e diz no que ele mexeu.')

    def add_arguments(self, p):
        p.add_argument('arquivo', help='O .xlsx que o comprador devolveu.')
        p.add_argument('--so', default=None,
                       help='Código da OV (ex.: EMIN-SO-2026-0004). Omitido, '
                            'é lido do título da planilha.')
        p.add_argument('--company', default=None,
                       help='Slug da empresa, se houver ordem homônima.')
        p.add_argument('--out', default=None,
                       help='Onde gravar a planilha DELE pintada. Padrão: '
                            'ao lado do arquivo de entrada, com sufixo '
                            '"- PINTADA".')
        p.add_argument('--detalhe', action='store_true',
                       help='O relatório longo, seção por seção. O padrão é '
                            'o resumo curto — a planilha pintada é onde a '
                            'diferença se lê.')
        p.add_argument('--sem-banco', action='store_true',
                       help='Usa a aba Chips como referência em vez da OV. '
                            'Testemunha, não juiz — ver o ⚠ do módulo.')

    def handle(self, *a, **o):
        escreve = self.stdout.write
        resumo, chips = pa.abas(o['arquivo'])
        if not resumo or not resumo['linhas']:
            raise CommandError(
                'Não achei a tabela de categorias no arquivo. O parser casa '
                'por CABEÇALHO — se a aba veio sem a linha de títulos '
                '(recorte, colagem em arquivo novo), não há como saber qual '
                'coluna é o preço, e chutar a posição é como se lê a coluna '
                'errada com convicção.')

        codigo = o['so'] or self._codigo_do_titulo(o['arquivo'])
        if o['sem_banco']:
            ov, banco, conflitos = self._banco_faz_de_conta(chips)
        else:
            ov, banco = linhas_da_ordem(codigo, o['company'])
            conflitos = []

        achados = compara(resumo, banco)
        if o['detalhe']:
            self._relatorio(escreve, ov, resumo, chips, banco, achados,
                            conflitos, o['sem_banco'])

        from vendas.planilha_auditoria_saida import pinta_planilha
        saida = o['out'] or _ao_lado(o['arquivo'])
        contas = pinta_planilha(o['arquivo'], saida, achados, resumo)
        self._curto(escreve, ov, resumo, achados, contas, saida,
                    o['sem_banco'], o['detalhe'])

    # ── entradas ────────────────────────────────────────────────────────
    def _codigo_do_titulo(self, caminho):
        """O A1 da planilha é 'EMIN-SO-2026-0004 · Wu Quan · LOT-2026-0007'.
        Ler o código dali evita digitá-lo — e digitar o código de OUTRA ordem
        é como se compara a planilha certa com o banco errado."""
        import openpyxl
        wb = openpyxl.load_workbook(caminho, data_only=True)
        for ws in wb.worksheets:
            for r in range(1, 4):
                for c in range(1, 4):
                    v = ws.cell(r, c).value
                    for pedaco in str(v or '').replace('·', ' ').split():
                        if '-SO-' in pedaco:
                            return pedaco.strip()
        return None

    def _banco_faz_de_conta(self, chips):
        """`--sem-banco`: a aba Chips no lugar da OV, e dizendo que é."""
        if not chips or not chips['linhas']:
            raise CommandError('--sem-banco precisa da aba Chips, e este '
                               'arquivo não tem uma legível.')
        ref, conflitos = referencia_da_aba_chips(chips)
        banco = [{'pk': i, 'marca': v['marca'], 'tipo': '', 'capacidade': '',
                  'caixa': v['caixa'], 'qty': v['qty'], 'unit': v['unit'],
                  'rec_sistema': None, 'unit_sistema': None}
                 for i, v in enumerate(ref.values())]
        return {'code_str': '(sem banco — referência: aba Chips)',
                'status': '?', 'total_rmb': None, 'number': 0}, banco, conflitos

    # ── relatório ───────────────────────────────────────────────────────
    def _relatorio(self, escreve, ov, resumo, chips, banco, achados,
                   conflitos, sem_banco):
        b = self.style.MIGRATE_HEADING
        alerta, ok = self.style.WARNING, self.style.SUCCESS

        linhas = [a for a in achados if a['tipo_achado'] == 'linha']
        preco = [a for a in linhas if 'preco' in a['diffs']
                 or 'preco_apagado' in a['diffs']]
        env = [a for a in linhas if 'enviados' in a['diffs']]
        recusa = [a for a in linhas if 'recusa' in a['diffs']]
        conta = [a for a in linhas if 'conta_aprovados' in a['diffs']
                 or 'conta_resultado' in a['diffs']]
        so_pl = [a for a in achados if a['tipo_achado'] == 'so_na_planilha']
        so_bd = [a for a in achados if a['tipo_achado'] == 'so_no_banco']
        ambig = [a for a in achados if a['tipo_achado'] == 'ambigua']
        checks = [l for l in resumo['linhas'] if l['check']]
        ilegiveis = [l for l in resumo['linhas'] if l['check_ilegivel']]

        escreve(b('\n═══ A COMPRA ═══'))
        escreve('  Ordem ............ %s  (%s)' % (ov.get('code_str') or
                                                   ov.get('number'),
                                                   ov.get('status')))
        escreve('  Referência ....... %s' % ('ABA CHIPS do próprio arquivo — '
                                             'testemunha, não juiz'
                                             if sem_banco else
                                             'linhas CONGELADAS da OV'))
        escreve('  Categorias ....... %d na referência · %d na planilha'
                % (len(banco), len(resumo['linhas'])))
        escreve('  Marcas dele ...... %d linhas com check%s'
                % (len(checks),
                   ' · %d célula tocada mas ilegível' % len(ilegiveis)
                   if ilegiveis else ''))
        if chips and chips['linhas']:
            escreve('  Aba Chips ........ %d PNs%s'
                    % (len(chips['linhas']),
                       ' · total ¥ %s' % _y(chips['total']['total'])
                       if chips['total'] else ''))
        for c in conflitos:
            escreve(alerta('  ⚠ aba Chips com ¥ divergente no mesmo par '
                           '%s/%s: %s vs %s (%s) — a testemunha foi editada.'
                           % (c[0], c[1], _y(c[2]), _y(c[3]), c[4])))

        # 1 ── PREÇO
        escreve(b('\n═══ 1. ¥ UNITÁRIO ALTERADO — %d categorias ═══'
                  % len(preco)))
        if not preco:
            escreve(ok('  Nenhuma. Todo ¥ unitário da planilha bate com a '
                       'referência.'))
        else:
            _tabela(escreve,
                    ('CATEGORIA', 'ENV', '¥ OV', '¥ DELE', 'Δ/UN', 'APROV',
                     'IMPACTO ¥', 'CHK'),
                    (42, 6, 9, 9, 9, 6, 12, 4),
                    [(_rot(a), _q(a['banco']['qty']),
                      _y(a['banco']['unit']), _y(a['planilha']['unit']),
                      _y((a['planilha']['unit'] - a['banco']['unit'])
                         if a['planilha']['unit'] is not None else None),
                      _q(a['aprovados']),
                      _y(-a['perda_preco'] if a['perda_preco'] is not None
                         else None),
                      '√' if a['planilha']['check'] else '')
                     for a in sorted(preco,
                                     key=lambda x: -(x['perda_preco'] or ZERO))])

        # 2 ── ENVIADOS (a coluna que ele não deveria tocar)
        escreve(b('\n═══ 2. QUANTIDADE ENVIADA ALTERADA — %d ═══' % len(env)))
        escreve('  A recusa dele tem coluna própria (RECHAZADOS). Mexer em '
                'ENVIADOS reescreve o que o\n  cliente despachou — o número '
                'que a OV congelou e o packing list acompanha.')
        if not env:
            escreve(ok('  Nenhuma.'))
        else:
            _tabela(escreve, ('CATEGORIA', 'OV', 'PLANILHA', 'Δ', 'CHK'),
                    (42, 8, 10, 8, 4),
                    [(_rot(a), _q(a['banco']['qty']),
                      _q(a['planilha']['enviados']),
                      _y(a['planilha']['enviados'] - a['banco']['qty'], 0),
                      '√' if a['planilha']['check'] else '')
                     for a in env])

        # 3 ── RECUSA (direito dele)
        escreve(b('\n═══ 3. RECUSA DECLARADA — %d categorias ═══'
                  % len(recusa)))
        if not recusa:
            escreve('  Nenhuma linha com RECHAZADOS > 0.')
        else:
            _tabela(escreve, ('CATEGORIA', 'ENV', 'RECUSA', 'APROV',
                              'CUSTA ¥', 'NO SISTEMA'),
                    (42, 6, 8, 7, 11, 11),
                    [(_rot(a), _q(a['banco']['qty']),
                      _q(a['planilha']['recusados']), _q(a['aprovados']),
                      _y(-a['perda_recusa']) if a['perda_recusa'] else '—',
                      ('já: %s' % a['banco']['rec_sistema'])
                      if a['banco']['rec_sistema'] else 'só na planilha')
                     for a in recusa])

        # 4 ── ARITMÉTICA
        escreve(b('\n═══ 4. A CONTA DELE NÃO FECHA — %d ═══' % len(conta)))
        if not conta:
            escreve(ok('  Nenhuma. Aprovados = enviados − recusados, e '
                       'resultado = aprovados × ¥ dele, em toda linha.'))
        for a in conta:
            p = a['planilha']
            porques = []
            if 'conta_aprovados' in a['diffs']:
                porques.append('aprovados %s ≠ enviados %s − recusados %s'
                               % (p['aprovados'], p['enviados'],
                                  p['recusados'] or 0))
            if 'conta_resultado' in a['diffs']:
                porques.append('¥ resultado %s ≠ aprovados %s × ¥ %s = %s'
                               % (_y(p['resultado']), a['aprovados'],
                                  _y(p['unit']),
                                  _y(a['aprovados'] * p['unit'])))
            escreve(alerta('  linha %-4d %s' % (p['linha'], _rot(a))))
            for q in porques:
                escreve('            · %s' % q)

        # 5 ── DESCASADAS
        if so_pl or so_bd or ambig:
            escreve(b('\n═══ 5. LINHAS QUE NÃO CASARAM ═══'))
            for a in so_pl:
                escreve(alerta('  só na planilha (linha %d): %s'
                               % (a['planilha']['linha'],
                                  _rotulo(a['planilha']))))
            for a in so_bd:
                escreve(alerta('  sumiu da planilha: %s · %s un × ¥ %s'
                               % (_rot(a), _q(a['banco']['qty']),
                                  _y(a['banco']['unit']))))
            for a in ambig:
                escreve(alerta('  ambígua (%d candidatas no banco): %s'
                               % (a['candidatas'], _rotulo(a['planilha']))))

        # 6 ── O CHECK DELE × O QUE MUDOU DE FATO
        mudou = {id(a['planilha']) for a in linhas if a['diffs']}
        sem_check = sorted(
            [a for a in linhas if a['diffs'] and not a['planilha']['check']],
            key=lambda a: (0 if 'preco' in a['diffs'] else 1,
                           -(a['perda_preco'] or ZERO)))
        check_vazio = [a for a in linhas
                       if a['planilha']['check'] and not a['diffs']]
        escreve(b('\n═══ 6. O CHECK DELE × O QUE MUDOU DE FATO ═══'))
        escreve('  O check é o que ELE diz ter mexido; a coluna acima é o que '
                'a referência PROVA. As\n  duas listas abaixo são onde os dois '
                'discordam — e a primeira é a que custa dinheiro.')
        if sem_check:
            escreve(alerta('  MUDOU SEM CHECK (%d):' % len(sem_check)))
            for a in sem_check:
                escreve('    · %s — %s'
                        % (_rot(a), ', '.join(FRASE.get(d, d)
                                              for d in a['diffs'])))
        else:
            escreve(ok('  Mudou sem check: nenhuma.'))
        if check_vazio:
            escreve('  CHECK SEM MUDANÇA (%d) — marcou, mas o valor bate:'
                    % len(check_vazio))
            for a in check_vazio:
                escreve('    · %s (¥ %s)' % (_rot(a),
                                             _y(a['banco']['unit'])))
        for l in ilegiveis:
            escreve(alerta('  CHECK ILEGÍVEL: linha %d, %s %s %s — a célula '
                           'tem só espaço em branco. Alguém digitou ali; '
                           'não dá para saber o quê.'
                           % (l['linha'], l['marca'], l['tipo'],
                              l['capacidade'])))
        del mudou

        # 7 ── FECHAMENTO
        v_ov = sum((a['valor_ov'] for a in linhas
                    if a['valor_ov'] is not None), ZERO)
        p_rec = sum((a['perda_recusa'] for a in linhas
                     if a['perda_recusa'] is not None), ZERO)
        p_pre = sum((a['perda_preco'] for a in linhas
                     if a['perda_preco'] is not None), ZERO)
        escrito = sum((a['planilha']['resultado'] for a in linhas
                       if a['planilha']['resultado'] is not None), ZERO)
        escreve(b('\n═══ 7. O QUE A DIFERENÇA CUSTA ═══'))
        escreve('  ¥ da OV (enviados × ¥ congelado) ....... %14s' % _y(v_ov))
        escreve('  − recusa (direito dele) ................ %14s' % _y(-p_rec))
        escreve('  − repreciação (proposta dele) .......... %14s' % _y(-p_pre))
        escreve('  ' + '─' * 55)
        escreve('  = ¥ que a planilha propõe .............. %14s'
                % _y(v_ov - p_rec - p_pre))
        escreve('  ¥ que ELE somou na coluna RESULTADO .... %14s' % _y(escrito))
        if escrito != (v_ov - p_rec - p_pre):
            escreve(alerta('  ⚠ as duas contas divergem em ¥ %s — a coluna '
                           'RESULTADO dele não é\n    o produto das outras '
                           'colunas dele em toda linha (ver seção 4).'
                           % _y(abs(escrito - (v_ov - p_rec - p_pre)))))
        if p_pre:
            escreve(alerta('\n  A REPRECIFICAÇÃO é ¥ %s — %s%% do valor '
                           'fechado. É proposta, não lançamento: o campo dela '
                           'no sistema\n  é o `new_unit_rmb` do acerto, e '
                           'nada disso entra sozinho.'
                           % (_y(p_pre),
                              _y(p_pre * 100 / v_ov, 1) if v_ov else '?')))

    # ── o resumo curto (o padrão) ───────────────────────────────────────
    def _curto(self, escreve, ov, resumo, achados, contas, saida, sem_banco,
               ja_detalhou):
        """Seis linhas. O relatório longo existe atrás do `--detalhe`, mas o
        padrão é este: quem confere já conhece a planilha, e o lugar onde a
        diferença se lê é ela, pintada. O terminal só diz quanto e onde doeu.
        """
        linhas = [a for a in achados if a['tipo_achado'] == 'linha']
        preco = [a for a in linhas if 'preco' in a['diffs']]
        env = [a for a in linhas if 'enviados' in a['diffs']]
        # SEM CHECK é a única lista que sobrevive ao corte: é o que ele mexeu
        # e não marcou, ou seja, exatamente o que passaria batido.
        sem_check = sorted([a for a in preco if not a['planilha']['check']],
                           key=lambda a: -(a['perda_preco'] or ZERO))
        v_ov = sum((a['valor_ov'] for a in linhas
                    if a['valor_ov'] is not None), ZERO)
        p_rec = sum((a['perda_recusa'] for a in linhas
                     if a['perda_recusa'] is not None), ZERO)
        p_pre = sum((a['perda_preco'] for a in linhas
                     if a['perda_preco'] is not None), ZERO)

        if not ja_detalhou:
            escreve('')
        escreve(self.style.MIGRATE_HEADING(
            '%s · %d categorias · referência: %s'
            % (ov.get('code_str') or ov.get('number'), len(resumo['linhas']),
               'ABA CHIPS do próprio arquivo' if sem_banco
               else 'linhas congeladas da OV')))
        escreve('  %d preços mexidos — %d baixou, %d subiu'
                % (len(preco), contas['baixou'], contas['subiu']))
        if sem_check:
            escreve(self.style.WARNING(
                '  %d SEM o check que ele mesmo usou para marcar:'
                % len(sem_check)))
            for a in sem_check:
                escreve('    · %-34s ¥%s → ¥%s   −¥ %s'
                        % (_rot(a), _y(a['banco']['unit'], 0),
                           _y(a['planilha']['unit'], 0),
                           _y(a['perda_preco'])))
        for a in env:
            escreve(self.style.WARNING(
                '  quantidade ENVIADA alterada: %s   %s → %s'
                % (_rot(a), _q(a['banco']['qty']),
                   _q(a['planilha']['enviados']))))
        escreve('  ¥ %s fechado  →  ¥ %s proposto   (recusa ¥ %s · preço ¥ %s)'
                % (_y(v_ov, 0), _y(v_ov - p_rec - p_pre, 0), _y(p_rec, 0),
                   _y(p_pre, 0)))
        escreve(self.style.SUCCESS('  Planilha pintada: %s' % saida))
        if not ja_detalhou:
            escreve('  (o relatório linha a linha está atrás de --detalhe)')
