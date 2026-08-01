"""
fetch_fx_rate — busca a taxa CNY→USD mid-market do DIA (PLANO_FX, 2026-08-01).

    python manage.py fetch_fx_rate            # busca e grava a taxa de hoje
    python manage.py fetch_fx_rate --dry-run  # mostra sem gravar

Fonte: open.er-api.com (agregador mid-market gratuito, sem chave — a "taxa
que o Google/XE mostram"; já foi usada no projeto). UM número por dia
(referência DIÁRIA — verificável pelos dois lados, decisão do PLANO_FX §1.5),
4 casas (§1.7). Idempotente: re-rodar no mesmo dia ATUALIZA a linha do dia.

Fallback: fonte fora do ar → repete a última taxa conhecida com
``is_fallback=True`` (o front avisa; o fechamento de lote NUNCA bloqueia por
câmbio — PLANO_FX Fase C). Tabela vazia + fonte fora = erro (sem o bootstrap
não há o que repetir — rode de novo quando a rede voltar).

Agendamento: 1×/dia (Render Cron Job ou scheduler), antes do expediente.
"""

import json
import urllib.error
import urllib.request
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand, CommandError

_URL = 'https://open.er-api.com/v6/latest/CNY'
_FONTE = 'open.er-api.com (mid-market diária)'


class Command(BaseCommand):
    help = ('Busca a taxa CNY→USD mid-market do dia e grava em FxRate '
            '(1 linha/dia, idempotente). --dry-run mostra sem gravar.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Mostra a taxa sem gravar.')

    def _busca(self):
        with urllib.request.urlopen(_URL, timeout=20) as resp:
            dados = json.load(resp)
        usd = dados['rates']['USD']
        return Decimal(str(usd)).quantize(Decimal('0.0001'), ROUND_HALF_UP)

    def handle(self, *args, **opts):
        from pricing.models import FxRate
        hoje = date.today()
        try:
            rate = self._busca()
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError,
                json.JSONDecodeError) as exc:
            ultima = FxRate.current()
            if ultima is None:
                raise CommandError(
                    f'fonte fora do ar ({exc}) e tabela FxRate VAZIA — '
                    'nada a repetir. Rode de novo quando a rede voltar.')
            if opts['dry_run']:
                self.stdout.write(self.style.WARNING(
                    f'DRY-RUN: fonte fora do ar ({exc}) — repetiria '
                    f'{ultima.rate} de {ultima.date} como fallback.'))
                return
            fx, criada = FxRate.objects.update_or_create(
                date=hoje, defaults={'rate': ultima.rate, 'source': _FONTE,
                                     'is_fallback': True})
            self.stdout.write(self.style.WARNING(
                f'⚠ fonte fora do ar ({exc}) — FALLBACK: repetida a taxa '
                f'{ultima.rate} de {ultima.date} para {hoje}.'))
            return

        if opts['dry_run']:
            self.stdout.write(f'DRY-RUN: 1 ¥ = US$ {rate} ({_FONTE}) — '
                              'nada gravado.')
            return
        fx, criada = FxRate.objects.update_or_create(
            date=hoje, defaults={'rate': rate, 'source': _FONTE,
                                 'is_fallback': False})
        self.stdout.write(self.style.SUCCESS(
            f"✅ {hoje}: 1 ¥ = US$ {rate} ({'nova' if criada else 'atualizada'}"
            f' · {_FONTE}). O "≈ US$" dos lotes abertos já reflete.'))
