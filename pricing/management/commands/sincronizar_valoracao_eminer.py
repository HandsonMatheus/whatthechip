"""
sincronizar_valoracao_eminer
============================
Faz a VALORAÇÃO da tela de estoque concordar com a VENDA da tela do comprador.

Achado do dono em 2026-09-01, olhando a lista de lotes: a coluna Valoração
mostrava "—" nos lotes 1, 2, 3 e 4, e mostrava US$ 8.443,15 e US$ 7.373,17 nos
lotes 5 e 6 — os valores ANTIGOS, os mesmos que a reconciliação acabou de
corrigir para 6.937,00 e 6.251,00. Duas telas do mesmo sistema dizendo números
diferentes sobre o mesmo lote.

A causa é que são duas coisas diferentes gravadas em momentos diferentes:

  · a VENDA vive em `SalesOrder`/`Invoice` e foi corrigida pela reconciliação;
  · a VALORAÇÃO vive num snapshot `LotPricing`, congelado no FECHAMENTO do
    lote. Os lotes 1, 2 e 4 nasceram agora e nunca tiveram snapshot; o lote 3
    fechou antes de o snapshot existir; e os dos lotes 5 e 6 guardam o número
    velho, porque foram congelados quando ele ainda era o número.

Este comando APPENDA um snapshot novo por lote — não edita o antigo. É a regra
do próprio modelo ("reabrir e fechar de novo cria OUTRO registro; o histórico
fica"), e a tela lê o mais recente. Assim o passado continua auditável.

⚠ 2026-09-01, mais tarde: entraram também o LOT/008 e o LOT/009, a pedido do
  dono (*"se eles já são fechados e pagados, vc pode corrigir pro número da
  ordem final"*). Neles a divergência tinha OUTRA causa, e vale registrar
  porque é bonita: o snapshot guarda uma FAIXA (baixo/médio/alto) e a tela de
  estoque lê o MÉDIO, enquanto a ordem de venda fecha no ALTO. Não era erro
  de ninguém — eram duas colunas do mesmo número, e batem exatamente:
  LOT/008 mid 29.144,00 x alto 30.155,77 = a venda; LOT/009 mid 6.263,15 x
  alto 6.280,89 = a venda. Alinhar e escolher a coluna que o dinheiro usou.
⚠ O LOT/007 entrou depois, e a história dele é a lição: eu ia APAGAR a ordem
  dele (a SO/004), porque em 31/08 ela era um rascunho — o lote tinha fechado,
  o packing list saído e a caixa viajado sem ninguém confirmar a venda. Entre
  aquele diagnóstico e a execução, o dono confirmou a ordem pela tela
  (01/09 03:27) e registrou o despacho de 18/08. O comando de apagar recusou
  sozinho ("ordem confirmada é documento: cancela, não apaga") e foi assim que
  se soube. Confirmada, ela tem total congelado e número final — logo entra
  aqui como as outras.
⚠ Lote cuja venda não passou por aqui não é tocado.

Uso:
    python manage.py sincronizar_valoracao_eminer            # dry-run
    python manage.py sincronizar_valoracao_eminer --commit
    python manage.py sincronizar_valoracao_eminer --revert
"""

import json
import os
from decimal import Decimal as D

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from core.safe_command import SafeWriteCommand
from tenancy.models import Company
from tenancy.scope import company_scope

EMPRESA_SLUG = 'eminer'
#: Os seis da reconciliação, pelo CÓDIGO DA ORDEM — que não muda com a
#: renumeração de lote, ao contrário do número.
ORDENS = ('SO/009/04/26', 'SO/010/06/26', 'SO/011/07/26',
          'SO/005/08/26', 'SO/001/07/26', 'SO/002/07/26',
          # Operação corrente: fechados, vendidos e com total congelado. Ainda
          # NÃO pagos — mas o que se alinha aqui é a ORDEM, que é imutável
          # depois de confirmada ("ajustes entram como acerto"), não o
          # resultado da conferência, que ainda vai existir.
          'SO/008/08/26', 'SO/007/08/26', 'SO/004/08/26')
REVERT = os.path.join(str(settings.BASE_DIR), 'var', 'reverts',
                      'sincronizar_valoracao_eminer_revert.json')
MANTER_ANTIGOS = 10


class Command(SafeWriteCommand):
    help = ('Congela uma valoração nova por lote, igual ao valor da venda '
            'reconciliada — para a tela de estoque parar de divergir.')

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--revert', action='store_true')

    def handle(self, *args, **o):
        if o['revert']:
            return self._revert()

        from pricing.models import LotPricing
        from vendas.models import SalesOrder
        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        w, st = self.stdout.write, self.style

        with company_scope(empresa.id):
            plano = []
            for codigo in ORDENS:
                so = next((x for x in SalesOrder.objects.filter(status='confirmed')
                           if x.code == codigo), None)
                if so is None:
                    raise CommandError(
                        f'Ordem {codigo} não encontrada ou não confirmada. '
                        f'Rode a reconciliação antes desta sincronização.')
                atual = (LotPricing.objects.filter(lot=so.lot)
                         .order_by('-created_at').first())
                plano.append(dict(so=so, lot=so.lot, atual=atual))

            w('')
            w(st.MIGRATE_HEADING('━━ valoração do estoque × venda do comprador ━━'))
            w(f'   {"lote":<16}{"valoração hoje":>16}{"venda":>12}   ação')
            mexer = []
            for p in plano:
                antes = p['atual'].total_mid if p['atual'] else None
                alvo = p['so'].total_usd
                if antes == alvo:
                    acao = 'já bate — não toco'
                else:
                    acao = 'congelar valoração nova'
                    mexer.append(p)
                w(f'   {p["lot"].code:<16}{(str(antes) if antes is not None else "—"):>16}'
                  f'{str(alvo):>12}   {acao}')
            w('')
            if not mexer:
                w(st.SUCCESS('   Nada a fazer: as duas telas já concordam.'))
                return
            w(f'   {len(mexer)} lote(s) recebem snapshot novo. O antigo NÃO é '
              f'apagado —\n   o modelo guarda histórico, e a tela lê o mais recente.')

            if not o['commit']:
                w(st.WARNING('\nDRY-RUN — nada foi gravado. Use --commit para aplicar.'))
                return

            registro = {'quando': timezone.now().isoformat(), 'criados': []}
            with transaction.atomic():
                for p in mexer:
                    registro['criados'].append(self._congelar(p, empresa))
            self._gravar_revert(registro)
            w(st.SUCCESS(f'\nGravado. Reversão em {REVERT}'))

    def _congelar(self, p, empresa):
        from pricing.models import LotPricing
        so, lot = p['so'], p['lot']
        entradas = list(lot.entries.all())
        com_chave = [e for e in entradas if e.price_tier_value is not None]
        valor = so.total_usd
        lp = LotPricing(
            lot=lot, buyer=so.buyer, company=empresa,
            # Total NEGOCIADO não tem faixa: baixo = médio = alto. Fingir uma
            # faixa aqui inventaria incerteza que não existe.
            total_low=valor, total_mid=valor, total_high=valor,
            priced_units=sum(e.quantity for e in com_chave),
            total_units=sum(e.quantity for e in entradas),
            priced_lines=so.lines.count(),
            total_lines=len(entradas),
            lines=[{'fonte': 'reconciliacao_eminer_2026_09_01',
                    'ordem': so.code,
                    'total_usd': str(valor),
                    'total_rmb': str(so.total_rmb),
                    'fx': str(so.fx_usd_rate),
                    'nota': ('Valoração igualada à venda reconciliada. O '
                             'snapshot anterior, se havia, foi mantido — a '
                             'tela lê o mais recente.')}])
        lp.save()
        self.stdout.write(self.style.SUCCESS(
            f'   {lot.code}: valoração US$ {valor} congelada'))
        return {'pk': lp.pk, 'lote': lot.code, 'valor': str(valor)}

    def _revert(self):
        from pricing.models import LotPricing
        if not os.path.exists(REVERT):
            raise CommandError(f'Não há {REVERT} — nada a desfazer.')
        reg = json.load(open(REVERT))
        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        with company_scope(empresa.id), transaction.atomic():
            for d in reg['criados']:
                LotPricing.all_companies.filter(pk=d['pk']).delete()
                self.stdout.write(f'   {d["lote"]}: snapshot removido')
        os.rename(REVERT, REVERT + '.' +
                  timezone.now().strftime('%Y%m%d_%H%M%S') + '.usado')
        self._podar()
        self.stdout.write(self.style.SUCCESS('Revertido.'))

    def _gravar_revert(self, registro):
        os.makedirs(os.path.dirname(REVERT), exist_ok=True)
        if os.path.exists(REVERT):
            os.rename(REVERT, REVERT + '.' +
                      timezone.now().strftime('%Y%m%d_%H%M%S') + '.bak')
        with open(REVERT, 'w') as f:
            json.dump(registro, f, indent=1, ensure_ascii=False)
        self._podar()

    def _podar(self):
        pasta, base = os.path.dirname(REVERT), os.path.basename(REVERT)
        antigos = sorted(f for f in os.listdir(pasta) if f.startswith(base + '.'))
        for f in antigos[:-MANTER_ANTIGOS]:
            os.remove(os.path.join(pasta, f))
