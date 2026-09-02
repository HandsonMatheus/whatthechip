"""
backfill_doc_codes
==================
Reescreve o CÓDIGO dos documentos que já existem para a convenção de
2026-09-02 — ``LOT/003/05/26`` vira ``LOT-2026-0003``, ``SO/007/08/26`` vira
``EMIN-SO-2026-0007`` (CONVENCAO_IDENTIFICADORES.md).

Duas coisas, nesta ordem — e a ordem IMPORTA:

  1. **Código de 4 letras em cada empresa** (dono, 2026-09-02): eMiner →
     ``EMIN``, eRecyclo → ``EREC``. Empresa que já tenha 4 letras não é
     tocada. Colisão resolve pela regra do ``suggest_company_code``.
  2. **Documento antigo é reescrito** — ``code_str`` de Lot e SalesOrder.

⚠ Se o passo 2 rodasse primeiro, as ordens sairiam com o código VELHO da
empresa e o passo 1 não as alcançaria mais.

⚠ A FATURA (INV) NÃO ENTRA. Decisão do dono de 2026-09-02: ela está sendo
aposentada em entrega separada, e reescrever o identificador de um documento
que está saindo só cria trabalho de reconciliação. Ela fica em
``INV/EMI/003/08/26``.

⚠ ISTO REESCREVE CÓDIGO DE DOCUMENTO, inclusive de lote já despachado e de
ordem já quitada. É a decisão do dono desde 2026-08-18, reafirmada em 09-02:
ele quer tela e papel na mesma grafia. O preço é o PDF já impresso divergir.
O NÚMERO e a DATA não mudam — só a grafia —, então o documento continua
rastreável pelo número.

O ano vem do ``doc_year`` do documento (preenchido pela migração), com o ano
do ``created_at`` como rede. A ordem de venda usa o ano do LOTE dela — que é
exatamente o que o ``doc_year`` dela guarda (§2.2).

RLS (⚠ armadilha §6.2.2): o laço abre ``company_scope(empresa)`` por empresa.
Sem o GUC, com FORCE RLS, tanto o SELECT quanto o UPDATE casam **zero linhas em
silêncio** — e o comando reportaria "nada a fazer" num banco cheio.

Regra de ouro #1: ESCREVE no banco → dry-run por padrão.
Reversível: o ``--commit`` grava ``backfill_doc_codes_revert.json`` na BASE_DIR
com o valor ANTERIOR de cada campo; ``--revert`` restaura exatamente aquilo.

Uso (o banner do SafeWriteCommand mostra o BANCO-ALVO antes de tudo):
    python manage.py backfill_doc_codes                 # dry-run — só mostra
    python manage.py backfill_doc_codes --commit        # aplica
    python manage.py backfill_doc_codes --revert        # desfaz o último commit
    python manage.py backfill_doc_codes --company erecyclo   # uma empresa só
"""

import json
import os

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction

from core.safe_command import SafeWriteCommand
from tenancy.doc_code import _ano_de, doc_code
from tenancy.models import Company, suggest_company_code
from tenancy.scope import company_scope

REVERT_FILE = 'backfill_doc_codes_revert.json'

#: (rótulo, import path, prefixo do documento, campo de data)
#: ⚠ A Fatura SAIU daqui em 2026-09-02 (ela está sendo aposentada — não tocar).
ALVOS = (
    ('Lote',   'estoque.models:Lot',          'LOT', 'created_at'),
    ('OV',     'vendas.models:SalesOrder',    'SO',  'created_at'),
)


def _revert_path():
    return os.path.join(str(settings.BASE_DIR), REVERT_FILE)


def _modelo(caminho):
    modulo, nome = caminho.split(':')
    from importlib import import_module
    return getattr(import_module(modulo), nome)


def ja_no_formato_novo(code_str: str) -> bool:
    """``LOT-2026-0041``/``EMIN-SO-2026-0004`` → True; qualquer grafia com
    ``/`` (e vazio) → False.

    O separador basta e não dá empate: a grafia velha é toda com barra, a nova
    é toda com hífen. Serve à IDEMPOTÊNCIA — rodar duas vezes não reescreve."""
    return bool(code_str) and '/' not in code_str


class Command(SafeWriteCommand):
    help = ('Reescreve lote e ordem de venda na convenção nova '
            '(LOT/003/05/26 → LOT-2026-0003; SO/007/08/26 → '
            'EMIN-SO-2026-0007). A fatura NÃO é tocada. Dry-run por padrão.')

    def add_arguments(self, parser):
        parser.add_argument('--company', default=None,
                            help='Slug de UMA empresa. Omitido = todas.')
        parser.add_argument('--commit', action='store_true',
                            help='Aplica. Sem isso, só simula (dry-run).')
        parser.add_argument('--revert', action='store_true',
                            help='Restaura os valores do último --commit.')

    # ── main ────────────────────────────────────────────────────────────────

    def handle(self, *args, **opts):
        if opts['revert']:
            return self._revert()

        empresas = Company.objects.all().order_by('pk')
        if opts['company']:
            empresas = empresas.filter(slug=opts['company'])
            if not empresas.exists():
                raise CommandError(f'Empresa com slug {opts["company"]!r} não existe.')

        commit = opts['commit']
        # Códigos já em uso — a sugestão de cada empresa nova entra aqui na
        # hora, senão duas empresas "Brasil …" sairiam ambas como BRA.
        ocupados = set(Company.objects.exclude(code='').values_list('code', flat=True))

        plano_empresas, plano_docs, sem_codigo = [], [], []

        for empresa in empresas:
            codigo = empresa.code
            # Código de 4 LETRAS (dono, 2026-09-02). Vazio e código curto ganham
            # a semente; quem já tem 4 fica como está — código de empresa é
            # decisão que se toma uma vez, e mexer nele repercute em tudo.
            if len(codigo) != 4:
                ocupados.discard(codigo)          # o próprio código velho libera
                novo_codigo = suggest_company_code(empresa.name, taken=ocupados)
                if not novo_codigo:
                    sem_codigo.append(empresa)
                    if not codigo:
                        continue                  # segue sem prefixo (legado)
                else:
                    plano_empresas.append((empresa, codigo, novo_codigo))
                    codigo = novo_codigo
                ocupados.add(codigo)

            # ⚠ RLS: SELECT e UPDATE só enxergam linha DENTRO do escopo.
            with company_scope(empresa):
                for rotulo, caminho, prefixo, campo_data in ALVOS:
                    Modelo = _modelo(caminho)
                    for obj in Modelo.objects.all().order_by('number'):
                        if ja_no_formato_novo(obj.code_str):
                            continue
                        quando = getattr(obj, campo_data)
                        # O ano do documento: o campo é a fonte; o created_at é
                        # rede para a janela entre a migração e este comando.
                        ano = getattr(obj, 'doc_year', 0) or _ano_de(quando)
                        novo = doc_code(prefixo, codigo, obj.number, quando,
                                        ano=ano)
                        if novo == obj.code_str:
                            continue
                        plano_docs.append({
                            'empresa': empresa.slug, 'empresa_pk': empresa.pk,
                            'rotulo': rotulo, 'modelo': caminho, 'pk': obj.pk,
                            'antes': obj.code_str, 'depois': novo,
                        })

        self._mostrar(plano_empresas, plano_docs, sem_codigo)

        if not commit:
            self.stdout.write(self.style.WARNING(
                '\nDRY-RUN — nada foi gravado. Repita com --commit para aplicar.'))
            return

        if not plano_empresas and not plano_docs:
            self.stdout.write('Nada a fazer.')
            return

        revert = {
            'empresas': [{'pk': e.pk, 'slug': e.slug, 'antes': antes}
                         for e, antes, _ in plano_empresas],
            'docs': [{'modelo': d['modelo'], 'pk': d['pk'],
                      'empresa_pk': d['empresa_pk'], 'antes': d['antes']}
                     for d in plano_docs],
        }
        with open(_revert_path(), 'w', encoding='utf-8') as fh:
            json.dump(revert, fh, ensure_ascii=False, indent=2)

        self._gravar(plano_empresas, plano_docs)
        self.stdout.write(self.style.SUCCESS(
            f'\n✓ {len(plano_empresas)} empresa(s) e {len(plano_docs)} documento(s) '
            f'atualizados. Revert em {_revert_path()}'))

    # ── escrita ─────────────────────────────────────────────────────────────

    def _gravar(self, plano_empresas, plano_docs):
        with transaction.atomic():
            for empresa, _antes, codigo in plano_empresas:
                # update() e não save(): o save() da Company revalida o slug e
                # dispara o auto-código — aqui o código já foi escolhido.
                Company.objects.filter(pk=empresa.pk).update(code=codigo)

            por_empresa = {}
            for d in plano_docs:
                por_empresa.setdefault(d['empresa_pk'], []).append(d)
            for empresa_pk, docs in por_empresa.items():
                with company_scope(empresa_pk):
                    for d in docs:
                        # update() de novo: o save() do documento roda
                        # full_clean e reescreveria o passado por outros
                        # motivos. Backfill toca UM campo e mais nada.
                        _modelo(d['modelo']).objects.filter(pk=d['pk']).update(
                            code_str=d['depois'])

    def _revert(self):
        caminho = _revert_path()
        if not os.path.exists(caminho):
            raise CommandError(f'Sem arquivo de revert em {caminho}.')
        with open(caminho, encoding='utf-8') as fh:
            dados = json.load(fh)

        with transaction.atomic():
            for e in dados.get('empresas', []):
                Company.objects.filter(pk=e['pk']).update(code=e['antes'])
            por_empresa = {}
            for d in dados.get('docs', []):
                por_empresa.setdefault(d['empresa_pk'], []).append(d)
            for empresa_pk, docs in por_empresa.items():
                with company_scope(empresa_pk):
                    for d in docs:
                        _modelo(d['modelo']).objects.filter(pk=d['pk']).update(
                            code_str=d['antes'])

        self.stdout.write(self.style.SUCCESS(
            f'✓ Revertidos {len(dados.get("empresas", []))} código(s) de empresa '
            f'e {len(dados.get("docs", []))} documento(s).'))

    # ── relatório ───────────────────────────────────────────────────────────

    def _mostrar(self, plano_empresas, plano_docs, sem_codigo):
        if plano_empresas:
            self.stdout.write('\nCÓDIGO DA EMPRESA (4 letras):')
            for empresa, antes, codigo in plano_empresas:
                self.stdout.write(
                    f'  {empresa.name:<28} {antes or "(vazio)":<8} → {codigo}')
        if sem_codigo:
            self.stdout.write(self.style.WARNING(
                '\nSEM código possível (nome com menos de 2 letras) — '
                'a ordem de venda sai sem prefixo (SO-2026-0004):'))
            for empresa in sem_codigo:
                self.stdout.write(f'  {empresa.name} (slug={empresa.slug})')

        if not plano_docs:
            self.stdout.write('\nNenhum documento a renomear.')
            return

        self.stdout.write(f'\nDOCUMENTOS a renomear ({len(plano_docs)}):')
        atual = None
        for d in plano_docs:
            if d['empresa'] != atual:
                atual = d['empresa']
                self.stdout.write(f'  [{atual}]')
            antes = d['antes'] or '(vazio)'
            self.stdout.write(f'    {d["rotulo"]:<7} {antes:<22} → {d["depois"]}')
