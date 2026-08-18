"""
backfill_doc_codes
==================
Põe o CÓDIGO DA EMPRESA nos documentos que já existem — ``LOT/041/08/26`` vira
``LOT/EMI/041/08/26`` (dono, 2026-08-18).

Duas coisas, nesta ordem:

  1. **Empresa sem código ganha um** — as 3 primeiras letras do nome
     (``suggest_company_code``), a mesma regra que agora vale para empresa
     nova. Colisão resolve sozinha: 3 letras → 4 letras → 3 letras + B, C, D…
  2. **Documento antigo é reescrito** — ``code_str`` de Lot, SalesOrder e
     Invoice. Só quem ainda NÃO tem código de empresa no identificador; quem já
     saiu no formato novo não é tocado (número de documento não muda duas vezes).

⚠ A DECISÃO MUDOU. O formato novo tinha sido aplicado só a documento NOVO,
porque papel já impresso não pode divergir da tela. O dono reverteu em
2026-08-18: quer o passado renomeado também. O preço é esse — PDF de lote
antigo que já esteja impresso vai mostrar ``LOT/041/08/26`` enquanto a tela
mostra ``LOT/EMI/041/08/26``. O número (041) e a data não mudam, então o
documento continua rastreável; o que muda é só o prefixo.

Mês/ano vêm do ``created_at`` (``issued_at`` na fatura) — a data REAL de
emissão, não a de hoje. Um lote de julho continua ``…/07/26``.

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
from tenancy.doc_code import doc_code
from tenancy.models import Company, suggest_company_code
from tenancy.scope import company_scope

REVERT_FILE = 'backfill_doc_codes_revert.json'

#: (rótulo, import path, prefixo do documento, campo de data)
ALVOS = (
    ('Lote',   'estoque.models:Lot',          'LOT', 'created_at'),
    ('OV',     'vendas.models:SalesOrder',    'SO',  'created_at'),
    ('Fatura', 'vendas.models:Invoice',       'INV', 'issued_at'),
)


def _revert_path():
    return os.path.join(str(settings.BASE_DIR), REVERT_FILE)


def _modelo(caminho):
    modulo, nome = caminho.split(':')
    from importlib import import_module
    return getattr(import_module(modulo), nome)


def tem_codigo_de_empresa(code_str: str) -> bool:
    """``LOT/EMI/041/08/26`` → True; ``LOT/041/08/26`` e ``''`` → False.

    Olha o segundo pedaço: código de empresa é só LETRAS, número de documento
    é só dígito. Não dá empate."""
    partes = (code_str or '').split('/')
    return len(partes) >= 2 and partes[1].isalpha()


class Command(SafeWriteCommand):
    help = ('Põe o código da empresa nos documentos já existentes '
            '(LOT/041/08/26 → LOT/EMI/041/08/26). Dry-run por padrão.')

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
            if not codigo:
                codigo = suggest_company_code(empresa.name, taken=ocupados)
                if not codigo:
                    sem_codigo.append(empresa)
                    continue
                ocupados.add(codigo)
                plano_empresas.append((empresa, codigo))

            # ⚠ RLS: SELECT e UPDATE só enxergam linha DENTRO do escopo.
            with company_scope(empresa):
                for rotulo, caminho, prefixo, campo_data in ALVOS:
                    Modelo = _modelo(caminho)
                    for obj in Modelo.objects.all().order_by('number'):
                        if tem_codigo_de_empresa(obj.code_str):
                            continue
                        novo = doc_code(prefixo, codigo, obj.number,
                                        getattr(obj, campo_data))
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
            'empresas': [{'pk': e.pk, 'slug': e.slug, 'antes': e.code}
                         for e, _ in plano_empresas],
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
            for empresa, codigo in plano_empresas:
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
            self.stdout.write('\nCÓDIGO DA EMPRESA (novo):')
            for empresa, codigo in plano_empresas:
                self.stdout.write(f'  {empresa.name:<28} → {codigo}')
        if sem_codigo:
            self.stdout.write(self.style.WARNING(
                '\nSEM código possível (nome com menos de 2 letras) — '
                'documentos ficam no formato antigo:'))
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
