"""
migrate_prices_to_rmb — F10.1: converte os valores gravados de USD → ¥ (RMB
canônico, plano §12.18). DIVIDE pelo `--rate-used` (a taxa em que os USD foram
GERADOS — 0.15 no import da planilha e no WeChat), recuperando os ¥ originais
do comprador (13.50 → ¥90). A taxa VIGENTE (0.14) fica no `Buyer.fx_usd_rate`
e só entra na DERIVAÇÃO de leitura — nunca aqui.

    python manage.py migrate_prices_to_rmb --buyer wu-quan --rate-used 0.15   # DRY-RUN
    ... --commit                                                              # grava
    ... --revert migrate_prices_to_rmb_revert.json                            # desfaz

⚠ RODAR SÓ JUNTO com o deploy da F10 completa (engine/telas em ¥) — antes
disso o banco falaria ¥ e a tela US$. ¥ NÃO-redondo no relatório = valor que o
parceiro digitou em USD pós-launch (revisar caso a caso antes do commit).
Toca: Price.price_min/max e PriceChangeRequest.new_price/old_price.
NÃO toca: LotPricing (snapshots históricos ficam em USD, documentado).
"""

import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pricing.models import Buyer, Price, PriceChangeRequest
from tenancy.scope import scope_command_to_company

_CENT = Decimal('0.01')


class Command(BaseCommand):
    help = ('F10.1: USD gravado → ¥ (divide pela taxa em que os USD nasceram). '
            'DRY-RUN por padrão; --commit grava; --revert desfaz.')

    def add_arguments(self, parser):
        parser.add_argument('--buyer', required=True, help='Slug do comprador.')
        parser.add_argument('--company', default=None)
        parser.add_argument('--rate-used', default='',
                            help='Taxa em que os USD atuais foram gerados (ex.: 0.15).')
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--revert', default='',
                            help='JSON de reversão a desfazer.')
        parser.add_argument('--mark-migrated', action='store_true',
                            help='Só liga a TRAVA (prices_in_rmb=True) sem tocar '
                                 'valores — p/ ambiente que já está em ¥.')

    def handle(self, *args, **opts):
        scope_command_to_company(opts['company'], self.stdout)
        buyer = Buyer.all_companies.filter(slug=opts['buyer']).first()
        if buyer is None:
            raise CommandError(f"Comprador {opts['buyer']!r} não existe.")
        if opts['mark_migrated']:
            buyer.prices_in_rmb = True
            buyer.save(update_fields=['prices_in_rmb'])
            self.stdout.write(self.style.SUCCESS(
                f'🔒 Trava ligada: {buyer.slug} marcado como JÁ em ¥ '
                '(nenhum valor foi alterado).'))
            return
        if opts['revert']:
            out = self._revert(opts['revert'])
            # Desfez a última rodada → destrava para o operador decidir; se os
            # valores CONTINUAM em ¥ (caso dupla-rodada), re-ligue a trava:
            buyer.prices_in_rmb = False
            buyer.save(update_fields=['prices_in_rmb'])
            self.stdout.write(self.style.WARNING(
                '⚠ Trava desligada pelo revert. Confira os valores: se '
                'continuam em ¥ (você desfez uma rodada EXTRA), re-ligue com '
                '--mark-migrated.'))
            return out
        try:
            rate = Decimal(opts['rate_used'])
            if rate <= 0:
                raise InvalidOperation
        except InvalidOperation:
            raise CommandError('--rate-used obrigatório e > 0 (ex.: 0.15).')
        # ── TRAVA anti-dupla-execução (incidente local 2026-07-16: rodou 2× e
        # os ¥ ficaram 6,7× maiores; o aviso de "¥ não-redondo" NÃO pega a 2ª
        # rodada porque ¥600 é redondo). Vale para dry-run e commit. ──
        if buyer.prices_in_rmb:
            raise CommandError(
                f'TRAVA: os preços de {buyer.slug!r} JÁ estão em ¥ '
                f'(prices_in_rmb=True) — re-rodar multiplicaria tudo por '
                f'{(1 / rate):.2f}×. Se este banco realmente ainda está em '
                'USD, desmarque "Preços já em ¥" no admin do comprador.')

        log, nao_redondos = [], []
        planos = [
            ('price', Price.all_companies.filter(
                price_list__buyer=buyer, price_min__isnull=False),
             ('price_min', 'price_max')),
            ('pcr', PriceChangeRequest.all_companies.filter(
                price__price_list__buyer=buyer), ('new_price', 'old_price')),
        ]
        for model_tag, qs, campos in planos:
            for obj in qs.iterator():
                ch = {}
                for f in campos:
                    usd = getattr(obj, f)
                    if usd is None:
                        continue
                    rmb = (usd / rate).quantize(_CENT, ROUND_HALF_UP)
                    ch[f] = [str(usd), str(rmb)]
                    if rmb != rmb.quantize(Decimal('1')):
                        nao_redondos.append((model_tag, obj.pk, f, usd, rmb))
                if ch:
                    log.append({'model': model_tag, 'pk': obj.pk, 'changes': ch})

        self.stdout.write(f'=== migrate_prices_to_rmb ÷{rate} '
                          f"({'COMMIT' if opts['commit'] else 'DRY-RUN'}) ===")
        self.stdout.write(f'  registros a converter: {len(log)}')
        for e in log[:10]:
            self.stdout.write(f'    {e["model"]}#{e["pk"]}: {e["changes"]}')
        if nao_redondos:
            self.stdout.write(self.style.WARNING(
                f'  ⚠ {len(nao_redondos)} valor(es) com ¥ NÃO-redondo '
                f'(digitados em USD pós-launch? revisar):'))
            for m, pk, f, usd, rmb in nao_redondos[:10]:
                self.stdout.write(f'    {m}#{pk}.{f}: US$ {usd} → ¥ {rmb}')
        if not opts['commit']:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN — nada gravado. Revise (¥ redondos = prova) e '
                're-rode com --commit.'))
            return

        with transaction.atomic():
            self._apply(log, novo=True)
            buyer.prices_in_rmb = True          # 🔒 trava a re-execução
            buyer.save(update_fields=['prices_in_rmb'])
        path = 'migrate_prices_to_rmb_revert.json'
        json.dump(log, open(path, 'w'), ensure_ascii=False, indent=0)
        self.stdout.write(self.style.SUCCESS(
            f'✅ {len(log)} registro(s) convertidos p/ ¥ e trava ligada. '
            f'Reversível: {path}'))

    def _apply(self, log, novo: bool):
        modelos = {'price': Price, 'pcr': PriceChangeRequest}
        for e in log:
            Model = modelos[e['model']]
            obj = Model.all_companies.filter(pk=e['pk']).first()
            if obj is None:
                continue
            for f, (old, new) in e['changes'].items():
                setattr(obj, f, Decimal(new if novo else old))
            obj.save()

    def _revert(self, path):
        log = json.load(open(path))
        with transaction.atomic():
            self._apply(log, novo=False)
        self.stdout.write(f'↩ revertido de {path} ({len(log)} registros).')
