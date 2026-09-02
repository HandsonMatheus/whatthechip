"""
descrever_lotes_renomeados_eminer
=================================
Escreve o CÓDIGO ANTIGO na descrição de cada lote que a renumeração renomeou.

Pedido do dono em 2026-09-01: *"preciso que os lotes que tiveram o nome mudado,
tenham os nomes antigos na DESCRICAO deles proprios"*.

Por que isso importa e não é enfeite: a renumeração de 31/08 pôs a numeração
em ordem cronológica (39→3, 40→5, 41→6, 42→7, 43→8, 44→9, 45→10, 48→11,
49→12, 50→13), mas o mundo lá fora não foi renumerado junto. O packing list
que viajou com a caixa diz `LOT/042/07/26`; a planilha de controle diz 41; o
WhatsApp com o Wu Quan diz 39. Quem procurar por esses números na tela não
acha mais nada, e a única trilha que restava era o JSON de reversão do
comando — que não é lugar onde alguém procura.

A descrição é o campo certo porque é o único texto LIVRE do lote, é o que a
lista mostra ao lado do código, e é o que a busca do comprador varre.

    "EMINER MOBILE"  →  "EMINER MOBILE · antes LOT/039/05/26"
    ""               →  "Antes: LOT/040/07/26"

O código antigo é RECONSTRUÍDO, não digitado: o número vem do `MAPA` do
próprio `renumerar_lotes_eminer` (fonte única — se o mapa mudar, isto
acompanha) e o mês vem do `created_at` do lote, que a renumeração não toca.
A montagem é LOCAL (`codigo_antigo`) desde 2026-09-02: o `doc_code()` do
sistema emite a grafia NOVA, e aqui o que se reproduz é o papel antigo. Escrever o
formato à mão aqui seria criar uma segunda convenção de código.

⚠ Idempotente: lote que já traz "antes LOT/0NN" na descrição é pulado.
⚠ Só os lotes do MAPA. Lote que nunca foi renomeado não ganha nada.

Uso:
    python manage.py descrever_lotes_renomeados_eminer            # dry-run
    python manage.py descrever_lotes_renomeados_eminer --commit
    python manage.py descrever_lotes_renomeados_eminer --revert
"""

import json
import os
import re

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from core.safe_command import SafeWriteCommand
from estoque.management.commands.renumerar_lotes_eminer import MAPA

def codigo_antigo(numero, quando, company_code='') -> str:
    """A grafia ANTIGA do lote: ``LOT/039/05/26``.

    ⚠ Montada AQUI, e não pelo `doc_code()` do sistema, desde 2026-09-02.
    Antes ela vinha de lá — o que estava certo enquanto o sistema escrevia
    nesse formato. O `doc_code` passou a emitir `LOT-2026-0039`, e este comando
    precisa exatamente do contrário: o que está IMPRESSO no papel que viajou
    com a caixa. Grafia histórica é dado congelado, não função viva.

    O código da empresa entra quando ela tinha um (`LOT/EMI/040/07/26`) — a
    grafia antiga o incluía. A eMiner estava sem código na época, e por isso o
    dela sai curto.
    """
    meio = f'{company_code}/' if company_code else ''
    return f'LOT/{meio}{numero:03d}/{quando:%m}/{quando:%y}'

from tenancy.models import Company
from tenancy.scope import company_scope

EMPRESA_SLUG = 'eminer'
#: número de HOJE → número de ANTES. Invertido do MAPA da renumeração, que é
#: o dono do vocabulário; nunca redigitado aqui.
ANTIGO = {novo: antigo for antigo, novo in MAPA.items()}
REVERT = os.path.join(str(settings.BASE_DIR), 'var', 'reverts',
                      'descrever_lotes_renomeados_eminer_revert.json')
MANTER_ANTIGOS = 10
#: Reconhece a marca já escrita, para o comando poder rodar duas vezes.
#: ⚠ O `:?` não é enfeite: o comando escreve DUAS formas — "Antes: LOT/…"
#: quando a descrição está vazia e "· antes LOT/…" quando não está. A 1ª
#: versão do regex exigia espaço logo depois de "antes" e por isso não
#: reconhecia a forma com dois-pontos: rodar de novo empilhava o código na
#: descrição dos lotes sem texto. Pego pelo teste de idempotência.
JA_TEM = re.compile(r'antes:?\s+LOT/', re.IGNORECASE)


class Command(SafeWriteCommand):
    help = ('Escreve o código antigo (LOT/039/05/26…) na descrição dos lotes '
            'renumerados, para quem procurar pelo número velho ainda achar.')

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--revert', action='store_true')

    # ── plano ────────────────────────────────────────────────────────────
    def handle(self, *args, **o):
        if o['revert']:
            return self._revert()

        from estoque.models import Lot
        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        w, st = self.stdout.write, self.style

        with company_scope(empresa.id):
            plano = []
            for novo, antigo in sorted(ANTIGO.items()):
                lot = Lot.objects.filter(number=novo).first()
                if lot is None:
                    plano.append(dict(lot=None, novo=novo, antigo=antigo,
                                      acao='não existe — pulo', muda=False))
                    continue
                codigo = codigo_antigo(antigo, lot.created_at, empresa.code)
                if JA_TEM.search(lot.description or ''):
                    acao, muda, texto = 'já tem — não toco', False, None
                else:
                    texto = self._descricao(lot.description, codigo)
                    acao, muda = f'escrever "{codigo}"', True
                plano.append(dict(lot=lot, novo=novo, antigo=antigo,
                                  codigo=codigo, texto=texto,
                                  acao=acao, muda=muda))

            w('')
            w(st.MIGRATE_HEADING('━━ código antigo na descrição do lote ━━'))
            w(f'   {"hoje":<16}{"antes":<16}   ação')
            mexer = [p for p in plano if p['muda']]
            for p in plano:
                atual = p['lot'].code if p['lot'] else f'#{p["novo"]}'
                w(f'   {atual:<16}{codigo_antigo(p["antigo"], p["lot"].created_at, empresa.code) if p["lot"] else "—":<16}'
                  f'   {p["acao"]}')
            w('')

            existentes = [p for p in plano if p['lot'] is not None]
            if not mexer:
                # ⚠ "nada a fazer" tem DUAS causas opostas, e dizer a errada é
                # pior que não dizer nada: rodado antes da renumeração, nenhum
                # lote existe — e a 1ª versão anunciava "todos já trazem o
                # código antigo", veredito verde sobre coisa nenhuma. Pego no
                # dry-run contra produção em 01/09.
                if not existentes:
                    w(st.WARNING(
                        '   Nenhum dos lotes renumerados existe neste banco '
                        '— a renumeração ainda\n   não rodou aqui. Este '
                        'comando vem DEPOIS dela.'))
                else:
                    w(st.SUCCESS(
                        f'   Nada a fazer: os {len(existentes)} lote(s) '
                        f'encontrados já trazem o código antigo.'))
                return

            w(f'   {len(mexer)} lote(s). A descrição é acrescida, nunca '
              f'substituída —\n   o texto que o operador escreveu continua na '
              f'frente.')

            if not o['commit']:
                w(st.WARNING('\nDRY-RUN — nada foi gravado. Use --commit para aplicar.'))
                return

            registro = {'quando': timezone.now().isoformat(), 'lotes': []}
            with transaction.atomic():
                for p in mexer:
                    self._escrever(p, registro)
            self._gravar_revert(registro)
            w(st.SUCCESS(f'\nGravado. Reversão em {REVERT}'))

    @staticmethod
    def _descricao(atual, codigo):
        """Acrescenta sem apagar. O texto do operador é dele."""
        atual = (atual or '').strip()
        return f'{atual} · antes {codigo}' if atual else f'Antes: {codigo}'

    # ── escrita ──────────────────────────────────────────────────────────
    def _escrever(self, p, registro):
        from estoque.models import Lot
        lot = p['lot']
        registro['lotes'].append({'pk': lot.pk, 'code': lot.code,
                                  'antes': lot.description or ''})
        # `update` e não `save()`: descrição não passa por nenhum portão, e o
        # save() do Lot dispararia evento de histórico por um texto.
        Lot.all_companies.filter(pk=lot.pk).update(description=p['texto'])
        self.stdout.write(self.style.SUCCESS(
            f'   {lot.code}: "{p["texto"]}"'))

    # ── reversão ─────────────────────────────────────────────────────────
    def _revert(self):
        from estoque.models import Lot
        if not os.path.exists(REVERT):
            raise CommandError(f'Não há {REVERT} — nada a desfazer.')
        reg = json.load(open(REVERT))
        empresa = Company.objects.get(slug=EMPRESA_SLUG)
        w = self.stdout.write
        with company_scope(empresa.id), transaction.atomic():
            for d in reg['lotes']:
                Lot.all_companies.filter(pk=d['pk']).update(
                    description=d['antes'])
                w(f'   {d["code"]}: descrição devolvida')
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
