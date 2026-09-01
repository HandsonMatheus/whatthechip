"""
renumerar_lotes_eminer
======================
Recontagem dos lotes da eMiner a partir do 1, em ordem de ABERTURA (dono,
2026-09-01).

Por que: a numeração começava no 39 — herança de uma contagem manual anterior
ao sistema —, tinha buraco no 46 e no 47, e os três envios legados entraram
fora dela. Depois desta recontagem a lista lê 1, 2, 3, … sem salto.

A ORDEM RELATIVA NÃO MUDA. Por data de abertura os lotes 39→50 já estavam em
sequência perfeita; o que este comando faz é comprimir a faixa e encaixar os
legados, que já nasceram com 1, 2 e 4. Nenhum lote passa na frente de outro.

⚠ ISTO REESCREVE CÓDIGO DE DOCUMENTO. O `LOT/039/05/26` que o comprador tem
   em papel vira `LOT/003/05/26`. O dono pediu explicitamente, ciente disso —
   é a mesma decisão que ele já tinha tomado em 2026-08-18 no
   `backfill_doc_codes`. O MÊS de cada código é preservado: o lote 3 continua
   `/05/26` porque abriu em maio. Só o número muda.

O que NÃO muda: os códigos de ordem de venda e de fatura. Eles têm sequência
própria, perpétua por empresa, e não citam o lote.

Regra de ouro: ESCREVE -> dry-run por padrão, herda de SafeWriteCommand.

Uso:
    python manage.py renumerar_lotes_eminer               # dry-run
    python manage.py renumerar_lotes_eminer --commit
    python manage.py renumerar_lotes_eminer --revert
    python manage.py renumerar_lotes_eminer --so-fechados # deixa os abertos

⚠ Roda DEPOIS do alinhar_vendas_eminer e do criar_lotes_legados_eminer: os dois
   miram em lote por NÚMERO e passariam a mirar errado.
"""

import json
import os

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from core.safe_command import SafeWriteCommand
from tenancy.models import Company
from tenancy.scope import company_scope

EMPRESA_SLUG = 'eminer'
REVERT = os.path.join(str(settings.BASE_DIR), 'var', 'reverts',
                      'renumerar_lotes_eminer_revert.json')
MANTER_ANTIGOS = 10

#: de → para. Os lotes 1, 2 e 4 (legados) não aparecem: já nasceram no lugar.
MAPA = {39: 3, 40: 5, 41: 6, 42: 7, 43: 8, 44: 9, 45: 10,
        48: 11, 49: 12, 50: 13}

#: Enquanto troca, os números vão para cá. Sem isto, mover 40→5 com o 5 já
#: tomado por um passo anterior estoura a UniqueConstraint no meio da
#: transação. Duas fases resolvem qualquer mapa, inclusive os que trocam pares.
OFFSET = 1000


class Command(SafeWriteCommand):
    help = 'Renumera os lotes da eMiner a partir do 1, em ordem de abertura.'

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--revert', action='store_true')
        parser.add_argument('--so-fechados', action='store_true',
                            help='Não mexe nos lotes abertos (48, 49, 50).')

    def handle(self, *args, **o):
        if o['revert']:
            return self._revert()

        from estoque.models import Lot
        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        with company_scope(empresa.id):
            mapa = dict(MAPA)
            if o['so_fechados']:
                abertos = set(Lot.objects.filter(status='open')
                              .values_list('number', flat=True))
                mapa = {de: para for de, para in mapa.items() if de not in abertos}

            plano = self._planejar(mapa, empresa)
            self._mostrar(plano, empresa)

            if not o['commit']:
                self.stdout.write(self.style.WARNING(
                    '\nDRY-RUN — nada foi gravado. Use --commit para aplicar.'))
                return

            registro = {'quando': timezone.now().isoformat(), 'lotes': []}
            with transaction.atomic():
                # fase 1: todo mundo para a faixa de trânsito
                for p in plano:
                    Lot.all_companies.filter(pk=p['pk']).update(
                        number=p['para'] + OFFSET)
                # fase 2: número final + código novo
                for p in plano:
                    Lot.all_companies.filter(pk=p['pk']).update(
                        number=p['para'], code_str=p['codigo_novo'])
                    registro['lotes'].append(
                        {'pk': p['pk'], 'de': p['de'], 'para': p['para'],
                         'codigo_antes': p['codigo_atual'],
                         'code_str_antes': p['code_str_atual']})
                self._checar_depois(empresa, exigir_contiguo=not o['so_fechados'])
            self._gravar_revert(registro)
            self.stdout.write(self.style.SUCCESS(
                f'\n{len(plano)} lote(s) renumerado(s). Reversão em {REVERT}'))

    # ── planejar ─────────────────────────────────────────────────────────
    def _planejar(self, mapa, empresa):
        from estoque.models import Lot
        from tenancy.doc_code import doc_code
        plano = []
        # Destino ocupado por um lote que TAMBÉM está se movendo é legítimo —
        # é o caso de uma troca em cadeia, e é exatamente para isso que existe
        # a faixa de trânsito. Ocupado por quem NÃO se move é recusa.
        em_transito = set(mapa)
        for de, para in sorted(mapa.items()):
            try:
                lot = Lot.objects.get(number=de)
            except Lot.DoesNotExist:
                raise CommandError(
                    f'Lote {de} não existe. O mapa está velho — talvez a '
                    f'renumeração já tenha rodado.')
            ocupante = Lot.objects.filter(number=para).first()
            if (ocupante is not None and ocupante.pk != lot.pk
                    and ocupante.number not in em_transito):
                raise CommandError(
                    f'O número {para} já é do lote {ocupante.code}, que não '
                    f'está no mapa. Recuso sobrescrever.')
            plano.append(dict(
                pk=lot.pk, de=de, para=para, lot=lot,
                codigo_atual=lot.code, code_str_atual=lot.code_str,
                # mês/ano do código: o da ABERTURA do lote, preservado.
                codigo_novo=doc_code('LOT', empresa.code, para, lot.created_at)))
        destinos = [p['para'] for p in plano]
        if len(set(destinos)) != len(destinos):
            raise CommandError('O mapa manda dois lotes para o mesmo número.')
        return plano

    def _checar_depois(self, empresa, exigir_contiguo=True):
        """Dentro da transação: se a numeração final tiver buraco ou repetido,
        levanta e o atomic desfaz tudo.

        `exigir_contiguo=False` com --so-fechados: deixar os lotes abertos de
        fora produz buraco POR DEFINIÇÃO (eles ficam lá em cima), então só a
        checagem de repetido faz sentido. O aviso na tela diz isso.
        """
        from estoque.models import Lot
        nums = sorted(Lot.objects.values_list('number', flat=True))
        if len(nums) != len(set(nums)):
            raise CommandError('Número repetido depois de renumerar.')
        if not exigir_contiguo:
            return
        if nums and nums != list(range(1, len(nums) + 1)):
            faltando = sorted(set(range(1, max(nums) + 1)) - set(nums))
            raise CommandError(
                f'A numeração final não é 1..{len(nums)} sem buraco — '
                f'faltam {faltando}. Nada foi gravado.')

    # ── mostrar ──────────────────────────────────────────────────────────
    def _mostrar(self, plano, empresa):
        from estoque.models import Lot
        w, st = self.stdout.write, self.style
        w('')
        w(st.MIGRATE_HEADING('━━ renumeração dos lotes da eMiner ━━'))
        w(f'   {"":<4}{"hoje":<18}{"":<4}{"depois":<18}{"aberto em":<12}{"status"}')
        movidos = {p['de'] for p in plano}
        for lot in Lot.objects.order_by('number'):
            p = next((x for x in plano if x['pk'] == lot.pk), None)
            if p:
                w(f'   →   {p["codigo_atual"]:<18}    {p["codigo_novo"]:<18}'
                  f'{lot.created_at:%d/%m/%Y}  {lot.status}')
            else:
                w(f'       {lot.code:<18}    {"(fica como está)":<18}'
                  f'{lot.created_at:%d/%m/%Y}  {lot.status}')
        w('')
        w(f'   {len(plano)} lote(s) mudam de número. A ordem relativa é a mesma —')
        w(f'   só some o buraco do 46/47 e os legados entram na frente.')
        abertos = [p for p in plano
                   if Lot.objects.get(pk=p['pk']).status == 'open']
        if not any(l.number in {p['de'] for p in plano}
                   for l in Lot.objects.filter(status='open')):
            w(st.WARNING(
                '   ⚠ --so-fechados: os lotes abertos ficam com o número '
                'antigo,\n     então a sequência final terá buraco até eles '
                'fecharem e você rodar de novo.'))
        if abertos:
            w(st.WARNING(
                f'   ⚠ {len(abertos)} deles estão ABERTOS agora '
                f'({", ".join(p["codigo_atual"] for p in abertos)}). Quem estiver '
                f'bipando chip vai ver o código mudar embaixo da mão. '
                f'--so-fechados deixa esses de fora.'))
        w(st.WARNING(
            '   ⚠ Isto reescreve o código do documento. O papel que o comprador '
            'já tem\n     vai divergir da tela. O mês de cada um é preservado.'))

    # ── reverter ─────────────────────────────────────────────────────────
    def _revert(self):
        from estoque.models import Lot
        if not os.path.exists(REVERT):
            raise CommandError(f'Não há {REVERT} — nada a desfazer.')
        reg = json.load(open(REVERT))
        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        with company_scope(empresa.id), transaction.atomic():
            for d in reg['lotes']:
                Lot.all_companies.filter(pk=d['pk']).update(
                    number=d['de'] + OFFSET)
            for d in reg['lotes']:
                Lot.all_companies.filter(pk=d['pk']).update(
                    number=d['de'], code_str=d['code_str_antes'])
                self.stdout.write(f'   {d["para"]} → {d["de"]}  '
                                  f'({d["codigo_antes"]})')
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
