# -*- coding: utf-8 -*-
"""
retire_category_codes.py — APOSENTA código de caixa (F12) sem liberar o número.
================================================================================
O par de ESCRITA do ``audit_category_codes``. Tira de circulação as categorias
que a régua de triagem reprova — as que nasceram do bug de 2026-08-18, em que
bipar um chip na bancada já cunhava categoria (ver 741bcfe).

**Por que aposentar e não apagar.** O próximo número sai de ``MAX(code)+1``.
Apagar E-15..E-19 faz o próximo DDR inédito **renascer como E-15** — e esse
número pode já estar escrito numa etiqueta, numa gaveta, do outro lado do
mundo. A regra da convenção é eterna: *número nunca reordena nem se reusa*
(pricing/convention.py). Aposentar marca `retired_at` e pronto: a linha fica,
o número fica queimado, e a categoria some das telas.

**Volta atrás sozinho.** Se um dia a régua mudar (o dono baixa `ddr_min_gen`
no admin) e um chip dessa categoria for aprovado de novo, o
``CategoryCode.label_for_key`` REATIVA a linha e devolve o MESMO código.
Aposentadoria é estado, não lápide.

**Trava de segurança:** recusa aposentar código que tem LANÇAMENTO em estoque
— caixa com chip dentro é decisão humana, não de comando. `--force` existe,
mas exige o dono saber o que está fazendo.

    python manage.py retire_category_codes                    # dry-run
    python manage.py retire_category_codes --commit
    python manage.py retire_category_codes --reativar E-15 --commit
    python manage.py retire_category_codes --motivo "sucata (bug 2026-08-18)" --commit

⚠ Rode o `audit_category_codes` ANTES: é ele que mostra a lista com o veredito
e quantos chips existem atrás de cada caixa.
"""
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from chips.engine import assess_profitability
from core.safe_command import SafeWriteCommand
from pricing.models import CategoryCode

from .audit_category_codes import _estoque_por_chave, result_sintetico

_MOTIVO_PADRAO = 'não rentável pela régua de triagem'


class Command(SafeWriteCommand):
    help = ('Aposenta os códigos de caixa que a triagem reprova — sem apagar '
            'a linha e sem liberar o número para reuso.')

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true',
                            help='grava (sem isto é dry-run)')
        parser.add_argument('--motivo', default=_MOTIVO_PADRAO,
                            help='texto gravado em retired_reason')
        parser.add_argument('--reativar', metavar='LABEL', default='',
                            help='desfaz a aposentadoria de UM código (ex.: E-15)')
        parser.add_argument('--force', action='store_true',
                            help='aposenta mesmo com lançamento em estoque')

    # ── reativar ────────────────────────────────────────────────────────────
    def _reativar(self, alvo, commit):
        achado = next((c for c in CategoryCode.objects.all()
                       if c.label == alvo), None)
        if achado is None:
            raise CommandError(f'Código {alvo!r} não existe.')
        if not achado.is_retired:
            self.stdout.write(f'{alvo} já está em uso — nada a fazer.')
            return
        self.stdout.write(f'{alvo} → reativar ({achado.kind} '
                          f'{achado.gen or "—"} {achado.tier_value:g}'
                          f'{achado.tier_unit})')
        if not commit:
            self.stdout.write(self.style.WARNING('DRY-RUN — nada gravado.'))
            return
        achado.retired_at = None
        achado.retired_reason = ''
        achado.save(update_fields=['retired_at', 'retired_reason'])
        self.stdout.write(self.style.SUCCESS(f'✅ {alvo} de volta ao serviço.'))

    def handle(self, *args, **opts):
        commit = opts['commit']
        if opts['reativar']:
            return self._reativar(opts['reativar'].strip().upper(), commit)

        estoque, total_lancamentos = _estoque_por_chave()
        if not total_lancamentos:
            # Mesmo tripwire da auditoria: "sem estoque" é o que autoriza
            # aposentar, e o RLS devolve exatamente isso quando a leitura é
            # barrada. Aqui o erro seria ESCRITA — então trava, não avisa.
            raise CommandError(
                'ZERO lançamentos no banco INTEIRO — não dá para saber quais '
                'caixas estão cheias.\nOu o banco está vazio, ou a leitura foi '
                'barrada (RLS sem GUC). Rode o audit_category_codes e confira '
                'o total varrido antes de gravar.')

        alvos, protegidos = [], []
        for c in CategoryCode.objects.filter(retired_at=None).order_by('kind', 'code'):
            veredito = assess_profitability(
                result_sintetico(c.kind, c.gen, c.tier_value, c.tier_unit))
            if veredito != 'NÃO RENTÁVEL':
                continue
            n, pecas, _emp = estoque.get(
                (c.kind, c.gen, c.tier_value, c.tier_unit), (0, 0, set()))
            (alvos if not n or opts['force'] else protegidos).append(
                (c, n, pecas))

        self.stdout.write(f'\n=== APOSENTAR CÓDIGO DE CAIXA '
                          f"({'COMMIT' if commit else 'DRY-RUN'}) ===")
        self.stdout.write(f'  {total_lancamentos} lançamento(s) varrido(s) · '
                          f'motivo: {opts["motivo"]!r}')
        if protegidos:
            self.stdout.write(self.style.WARNING(
                f'\n⛔ {len(protegidos)} reprovado(s) COM chip na caixa — '
                f'NÃO serão tocados (decisão humana; --force ignora):'))
            for c, n, pecas in protegidos:
                self.stdout.write(f'    {c.label}  {c.kind} {c.gen or "—"} '
                                  f'{c.tier_value:g}{c.tier_unit}  '
                                  f'{n} lanç. / {pecas} peças')
        if not alvos:
            self.stdout.write(self.style.SUCCESS(
                '\nNenhum código a aposentar. Nada a fazer.'))
            return
        self.stdout.write(f'\n✂ {len(alvos)} código(s) a aposentar '
                          f'(número CONTINUA ocupado para sempre):')
        for c, _n, _p in alvos:
            self.stdout.write(f'    {c.label}  {c.kind} {c.gen or "—"} '
                              f'{c.tier_value:g}{c.tier_unit}')

        if not commit:
            self.stdout.write(self.style.WARNING(
                '\nDRY-RUN — nada gravado. Re-rode com --commit.'))
            return

        agora = timezone.now()
        with transaction.atomic():
            for c, _n, _p in alvos:
                c.retired_at = agora
                c.retired_reason = opts['motivo'][:200]
                c.save(update_fields=['retired_at', 'retired_reason'])
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ {len(alvos)} código(s) aposentado(s). Nenhuma linha apagada, '
            f'nenhum número liberado.\n   Desfazer um: '
            f'retire_category_codes --reativar <CÓDIGO> --commit'))
