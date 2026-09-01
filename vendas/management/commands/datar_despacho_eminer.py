"""
datar_despacho_eminer
=====================
Carimba envio e recebimento nas ordens antigas que nunca os tiveram.

Achado do dono em 2026-09-01, na lista de Vendas: LOT/005 e LOT/006 seguiam
em "despacho pendente". Não era bug de tela (esse foi o outro, a precedência
do badge): em produção essas duas ordens simplesmente não têm `shipped_at`
nem `received_at`. Foram confirmadas em 11/07 e 17/07, pagas nos mesmos dias,
e ninguém registrou que a caixa saiu ou chegou — o despacho (F4) só passou a
ser preenchido em agosto, e elas são de julho.

A data vem do PAGAMENTO, por decisão do dono ("pode usar as datas de
pagamento"), e é LIDA DO PRÓPRIO `Payment` — não há data escrita à mão aqui.
Se o pagamento for corrigido um dia, o comando relê a nova; e se por acaso a
data gravada divergir da que eu suponho, é a do banco que vale.

    shipped_at   = data do pagamento           (DateField — "o dia que saiu")
    received_at  = meio-dia desse mesmo dia    (DateTimeField)

Mesmo dia para os dois porque é o que se sabe: no registro antigo tudo
colapsou numa data só. Mentir com um intervalo inventado ("saiu dia 11,
chegou dia 19") seria pior do que o empate.

⚠ Só preenche campo VAZIO — com UMA exceção nomeada, o `CORRECOES` abaixo.
  Despacho já registrado por gente é fato; sobrescrever fato tem de ser
  decisão explícita, com o valor velho guardado na reversão.
⚠ `carrier`, `tracking` e `shipped_by` ficam em branco: não se sabe, e chutar
  transportadora num registro fiscal é pior do que deixar vazio.
⚠ Os três legados (SO/009, SO/010, SO/011) JÁ têm recebimento e por isso já
  aparecem como "recebida"; falta só o envio deles. Ficam de fora por padrão
  — `--incluir-legados` os inclui.

Uso:
    python manage.py datar_despacho_eminer                      # dry-run
    python manage.py datar_despacho_eminer --commit
    python manage.py datar_despacho_eminer --incluir-legados
    python manage.py datar_despacho_eminer --revert
"""

import json
import os
from datetime import date, datetime
from datetime import timezone as _tz

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from core.safe_command import SafeWriteCommand
from tenancy.models import Company
from tenancy.scope import company_scope

EMPRESA_SLUG = 'eminer'
#: As duas de julho, pelo CÓDIGO DA ORDEM (não muda com renumeração de lote).
ORDENS = ('SO/001/07/26', 'SO/002/07/26')
#: Os três importados do controle antigo: têm recebimento, falta o envio.
LEGADOS = ('SO/009/04/26', 'SO/010/06/26', 'SO/011/07/26')
#: CORREÇÃO de despacho JÁ REGISTRADO — sobrescreve, ao contrário do resto.
#: Produção diz que a SO/005 (LOT/003, o lote de US$ 23.224) saiu em 18/08
#: com o rastreio DHL 2486463965 — o MESMO que está no LOT/010. Os dois na
#: mesma caixa, no mesmo dia. O dono corrigiu em 2026-09-01: *"Dia 11 de
#: julho foi quando o lote de 23k foi despachado"*. Ou seja, alguém carimbou
#: no lote 39 o embarque do lote 45.
#: ⚠ O RASTREIO não é tocado aqui: apagar número de transportadora é decisão
#:   separada, e o comando avisa na saída que ele ficou órfão.
CORRECOES = {'SO/005/08/26': date(2026, 7, 11)}
REVERT = os.path.join(str(settings.BASE_DIR), 'var', 'reverts',
                      'datar_despacho_eminer_revert.json')
MANTER_ANTIGOS = 10


def _meio_dia(d):
    return datetime(d.year, d.month, d.day, 12, 0, tzinfo=_tz.utc)


class Command(SafeWriteCommand):
    help = ('Carimba shipped_at/received_at nas ordens antigas sem despacho, '
            'usando a data do pagamento.')

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--revert', action='store_true')
        parser.add_argument('--incluir-legados', action='store_true',
                            dest='legados',
                            help='Também carimba o ENVIO dos três registros '
                                 'legados (o recebimento deles já existe).')

    # ── plano ────────────────────────────────────────────────────────────
    def handle(self, *args, **o):
        if o['revert']:
            return self._revert()

        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        w, st = self.stdout.write, self.style
        # A correção entra SEMPRE: não é carimbo de campo vazio, é conserto
        # de fato errado, e esconder isso atrás de uma flag seria escondê-lo.
        codigos = (tuple(ORDENS) + tuple(CORRECOES)
                   + (tuple(LEGADOS) if o['legados'] else ()))

        with company_scope(empresa.id):
            plano = [self._ler(c) for c in codigos]

            w('')
            w(st.MIGRATE_HEADING('━━ despacho das ordens antigas ━━'))
            w(f'   {"ordem":<16}{"lote":<16}{"pago em":>12}'
              f'{"enviada":>12}{"recebida":>12}   ação')
            mexer = [p for p in plano if p['muda']]
            for p in plano:
                so = p['so']
                w(f'   {so.code:<16}{so.lot.code:<16}'
                  f'{(p["pago_em"].strftime("%d/%m/%Y") if p["pago_em"] else "—"):>12}'
                  f'{(so.shipped_at.strftime("%d/%m/%Y") if so.shipped_at else "—"):>12}'
                  f'{(so.received_at.strftime("%d/%m/%Y") if so.received_at else "—"):>12}'
                  f'   {p["acao"]}')
            w('')

            if not mexer:
                w(st.SUCCESS('   Nada a fazer: todas já têm despacho.'))
                return

            w(f'   {len(mexer)} ordem(ns). Transportadora e rastreio ficam em '
              f'branco nos carimbos —\n   não se sabe, e chutar é pior que '
              f'deixar vazio.')
            for p in mexer:
                if p['corrigir'] and p['so'].tracking:
                    w(st.WARNING(
                        f'   ⚠ {p["so"].code} tem rastreio {p["so"].carrier} '
                        f'{p["so"].tracking} amarrado ao despacho ANTIGO '
                        f'({p["so"].shipped_at:%d/%m/%Y}).\n     Ele NÃO é '
                        f'apagado aqui — decida à parte se pertence a este '
                        f'lote.'))

            if not o['commit']:
                w(st.WARNING('\nDRY-RUN — nada foi gravado. Use --commit para aplicar.'))
                return

            registro = {'quando': timezone.now().isoformat(), 'ordens': []}
            with transaction.atomic():
                for p in mexer:
                    self._carimbar(p, registro)
            self._gravar_revert(registro)
            w(st.SUCCESS(f'\nGravado. Reversão em {REVERT}'))

    def _ler(self, codigo):
        from vendas.models import SalesOrder
        so = next((x for x in SalesOrder.objects.filter(status='confirmed')
                   if x.code == codigo), None)
        if so is None:
            raise CommandError(f'Ordem {codigo} não encontrada ou não confirmada.')

        inv = next((i for i in so.invoices.all() if i.status != 'cancelled'),
                   None)
        pag = (inv.payments.order_by('paid_at', 'id').first()
               if inv is not None else None)
        pago_em = pag.paid_at if pag else None

        # CORREÇÃO tem precedência: sobrescreve despacho já registrado.
        certo = CORRECOES.get(codigo)
        corrigir = certo is not None and so.shipped_at != certo
        falta_envio = so.shipped_at is None and not corrigir
        falta_receb = so.received_at is None

        if corrigir:
            acao = (f'CORRIGE envio '
                    f'{so.shipped_at:%d/%m/%Y} → {certo:%d/%m/%Y}'
                    if so.shipped_at else f'CORRIGE envio → {certo:%d/%m/%Y}')
            muda = True
        elif certo is not None:
            acao, muda = 'já corrigido — não toco', False
        elif pago_em is None:
            acao, muda = 'PULA — sem pagamento, não há data de onde tirar', False
        elif not falta_envio and not falta_receb:
            acao, muda = 'já tem os dois — não toco', False
        else:
            partes = ([f'envio {pago_em:%d/%m}'] if falta_envio else []) + \
                     ([f'recebimento {pago_em:%d/%m}'] if falta_receb else [])
            acao, muda = 'carimbar ' + ' e '.join(partes), True

        return dict(so=so, pago_em=pago_em, certo=certo, corrigir=corrigir,
                    falta_envio=falta_envio, falta_receb=falta_receb,
                    acao=acao, muda=muda)

    # ── escrita ──────────────────────────────────────────────────────────
    def _carimbar(self, p, registro):
        """Grava, guardando o valor ANTERIOR de cada campo tocado.

        O registro de reversão guarda o valor velho, não a lista de campos:
        carimbo em campo vazio volta para None, correção volta para a data
        que estava lá. Uma forma só serve aos dois casos — e sem ela, reverter
        uma CORREÇÃO apagaria o despacho original em vez de devolvê-lo."""
        so = p['so']
        antes = {}

        if p['corrigir']:
            antes['shipped_at'] = so.shipped_at.isoformat() if so.shipped_at else None
            so.shipped_at = p['certo']
            so.save(update_fields=['shipped_at'])
            self.stdout.write(self.style.SUCCESS(
                f'   {so.code}: envio CORRIGIDO para {p["certo"]:%d/%m/%Y}'))
        else:
            dia = p['pago_em']
            campos = []
            if p['falta_envio']:
                antes['shipped_at'] = None
                so.shipped_at = dia             # DateField: o dia que saiu
                campos.append('shipped_at')
            if p['falta_receb']:
                antes['received_at'] = None
                so.received_at = _meio_dia(dia)  # DateTimeField
                campos.append('received_at')
            so.save(update_fields=campos)
            self.stdout.write(self.style.SUCCESS(
                f'   {so.code}: {" + ".join(campos)} = {dia:%d/%m/%Y}'))

        registro['ordens'].append({'pk': so.pk, 'code': so.code, 'antes': antes})

    # ── reversão ─────────────────────────────────────────────────────────
    def _revert(self):
        from vendas.models import SalesOrder
        if not os.path.exists(REVERT):
            raise CommandError(f'Não há {REVERT} — nada a desfazer.')
        reg = json.load(open(REVERT))
        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        w = self.stdout.write
        with company_scope(empresa.id), transaction.atomic():
            for d in reg['ordens']:
                # Devolve cada campo ao valor que tinha ANTES deste comando —
                # None onde estava vazio, a data velha onde houve correção.
                volta = {c: (date.fromisoformat(v) if v else None)
                         for c, v in d['antes'].items() if c == 'shipped_at'}
                volta.update({c: None for c in d['antes'] if c != 'shipped_at'})
                SalesOrder.all_companies.filter(pk=d['pk']).update(**volta)
                w(f'   {d["code"]}: {" + ".join(sorted(volta))} devolvido(s)')
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
