# -*- coding: utf-8 -*-
"""
audit_category_codes.py — READ-ONLY: a convenção de caixas × a régua da triagem.
================================================================================
Responde: *"quais códigos de caixa existem no banco que a bancada, HOJE, não
criaria?"* — e, para cada um, **se tem estoque atrás**.

Por que existe (bug do dono, 2026-08-18): até o portão de 2026-08-18, o simples
RENDER do card de conferência cunhava categoria. Bipar um DDR2 criava um E-15
mesmo com o chip indo direto pro R-00 refino — o card nunca mostrava o código,
mas o número da convenção já tinha sido gasto. Em prod isso rendeu categorias de
sucata (DDR1/DDR2/LPDDR1/LPDDR2) e de capacidade abaixo do limiar (eMCP/eMMC
pequenos) misturadas às categorias reais.

O veredito NÃO reimplementa regra nenhuma: monta um `result` sintético a partir
da CHAVE e chama o `assess_profitability` de verdade (chips/engine.py), que lê a
ProfitabilityConfig VIVA. Mexeu no limiar no admin → esta auditoria muda junto.

⚠ Limite honesto da chave: em eMCP/uMCP a chave carrega SÓ o NAND (v3.1,
"unified by cap"). A geração e o tamanho da RAM não estão nela, então o veredito
aqui isola o critério de NAND — a RAM é sintetizada como aprovada de propósito.
Um eMCP com NAND boa e LPDDR2 é reprovado NO CHIP (bancada), não na caixa.

NÃO ESCREVE NADA. Rode com o DATABASE_URL do banco que quer inspecionar
(inclusive produção, pelo Render Shell):

    python manage.py audit_category_codes
    python manage.py audit_category_codes --indevidos
    python manage.py audit_category_codes --fora-da-convencao
    python manage.py audit_category_codes --csv > caixas.csv

Colunas:
    VEREDITO HOJE  o que a régua da bancada diria desta categoria agora
    CONVENÇÃO      consta na TABELA FUNDADORA de pricing/convention.py?
    LANÇAMENTOS    linhas de estoque (todas as empresas) que caem nesta caixa
    PEÇAS          soma das quantidades desses lançamentos

⚠ APAGAR código indevido é ARMADILHA: o próximo número sai de MAX(code)+1, então
apagar E-15..E-19 faz o próximo DDR inédito renascer como E-15 — número que um
cliente pode já ter etiquetado. O número é ETERNO (pricing/convention.py).
Aposentar (marcar) sim; apagar não.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from chips.engine import assess_profitability
from estoque.models import InventoryEntry
from pricing.convention import FOUNDING_TABLE, KIND_LETTER
from pricing.models import CategoryCode, fold_gen

#: chip_type canônico por kind da chave (chips/chip_types.py é quem manda).
_TIPO_CANONICO = {'emmc': 'eMMC', 'ufs': 'UFS', 'ssd': 'SSD',
                  'emcp': 'eMCP', 'umcp': 'uMCP', 'k9': 'K9'}

#: RAM sintética dos combos — ver "limite honesto da chave" no topo.
_RAM_APROVADA = 'LPDDR5 8GB'


def result_sintetico(kind: str, gen: str, tier_value, tier_unit: str) -> dict:
    """Um `result` do classify() reconstruído a partir da CHAVE de categoria.

    Só existe para poder perguntar ao `assess_profitability` DE VERDADE — assim
    o veredito desta auditoria nunca diverge do que a bancada faz, nem quando o
    dono mexe nos limiares do admin."""
    tier = f'{tier_value:g}' if tier_value is not None else ''
    if kind == 'ddr':
        return {'chip_type': gen, 'subtype': gen, 'dram_density': f'{tier}Gb'}
    if kind == 'lpddr':
        return {'chip_type': gen, 'subtype': gen, 'capacity': f'{tier}GB'}
    if kind in ('emcp', 'umcp'):
        return {'chip_type': _TIPO_CANONICO[kind], 'subtype': '', 'is_emcp': True,
                'emcp_ram': _RAM_APROVADA, 'emcp_nand': f'{tier}GB'}
    if kind == 'k9':
        return {'chip_type': 'K9', 'subtype': ''}
    return {'chip_type': _TIPO_CANONICO.get(kind, kind), 'subtype': '',
            'capacity': f'{tier}GB'}


def _chaves_da_convencao():
    """Chaves da TABELA FUNDADORA, normalizadas p/ comparar com o banco."""
    from decimal import Decimal
    return {(k, g, Decimal(t), u) for k, g, t, u, _c in FOUNDING_TABLE}


def _estoque_por_chave():
    """{chave: (lançamentos, peças, empresas)} numa consulta só (sem N+1).

    Manager de PLATAFORMA de propósito: auditoria de convenção é global — a
    caixa é a mesma tabela mundial, não é dado de uma empresa."""
    bruto = (InventoryEntry.all_companies
             .exclude(price_tier_value=None)
             .values('price_kind', 'price_gen', 'price_tier_value',
                     'price_tier_unit', 'company_id')
             .annotate(n=Count('id'), pecas=Sum('quantity')))
    acc = defaultdict(lambda: [0, 0, set()])
    for r in bruto:
        chave = (r['price_kind'], fold_gen(r['price_kind'], r['price_gen']),
                 r['price_tier_value'], r['price_tier_unit'])
        alvo = acc[chave]
        alvo[0] += r['n']
        alvo[1] += r['pecas'] or 0
        alvo[2].add(r['company_id'])
    return acc


class Command(BaseCommand):
    help = ('READ-ONLY: lista os códigos de caixa (F12) com o veredito da régua '
            'de triagem viva e quanto estoque cada um tem atrás.')

    def add_arguments(self, parser):
        parser.add_argument('--indevidos', action='store_true',
                            help='só os que HOJE a bancada não cunharia')
        parser.add_argument('--fora-da-convencao', action='store_true',
                            dest='fora_convencao',
                            help='só os que não estão na TABELA FUNDADORA')
        parser.add_argument('--csv', action='store_true',
                            help='saída em CSV (cola em planilha)')

    def handle(self, *args, **opts):
        convencao = _chaves_da_convencao()
        estoque = _estoque_por_chave()

        linhas = []
        for c in CategoryCode.objects.all().order_by('kind', 'code'):
            if c.kind not in KIND_LETTER:
                continue                      # kind extinto (GDDR) — sem letra
            chave = (c.kind, c.gen, c.tier_value, c.tier_unit)
            veredito = assess_profitability(
                result_sintetico(c.kind, c.gen, c.tier_value, c.tier_unit))
            n, pecas, empresas = estoque.get(chave, (0, 0, set()))
            linhas.append({
                'label': c.label, 'kind': c.kind, 'gen': c.gen,
                'tier': c.tier_value, 'unit': c.tier_unit,
                'veredito': veredito,
                'indevido': veredito == 'NÃO RENTÁVEL',
                'na_convencao': chave in convencao,
                'lancamentos': n, 'pecas': pecas, 'empresas': len(empresas),
                'criado': c.created_at,
            })

        visiveis = linhas
        if opts['indevidos']:
            visiveis = [l for l in visiveis if l['indevido']]
        if opts['fora_convencao']:
            visiveis = [l for l in visiveis if not l['na_convencao']]

        if opts['csv']:
            self.stdout.write('codigo,tipo,geracao,faixa,unidade,veredito,'
                              'na_convencao,lancamentos,pecas,empresas,criado_em')
            for l in visiveis:
                self.stdout.write(
                    f'{l["label"]},{l["kind"]},{l["gen"]},{l["tier"]:g},{l["unit"]},'
                    f'{l["veredito"]},{"sim" if l["na_convencao"] else "nao"},'
                    f'{l["lancamentos"]},{l["pecas"]},{l["empresas"]},'
                    f'{l["criado"]:%Y-%m-%d}')
            return

        self.stdout.write(f'\n=== CÓDIGOS DE CAIXA (F12) — {len(linhas)} no banco ===\n')
        self.stdout.write('CÓDIGO  TIPO   GERAÇÃO  FAIXA        VEREDITO HOJE   '
                          'CONVENÇÃO  LANÇ.  PEÇAS  EMPRESAS')
        for l in visiveis:
            marca = '⛔' if l['indevido'] else '  '
            faixa = f'{l["tier"]:g} {l["unit"]}'.strip()
            self.stdout.write(
                f'{marca}{l["label"]:<6} {l["kind"]:<6} {l["gen"] or "—":<8} '
                f'{faixa:<12} {l["veredito"]:<15} '
                f'{"sim" if l["na_convencao"] else "AUSENTE":<10} '
                f'{l["lancamentos"]:>5}  {l["pecas"]:>5}  {l["empresas"]:>8}')

        indevidos = [l for l in linhas if l['indevido']]
        com_estoque = [l for l in indevidos if l['lancamentos']]
        fora = [l for l in linhas if not l['na_convencao']]
        fora_ok = [l for l in fora if not l['indevido']]

        self.stdout.write('\n── RESUMO ──')
        self.stdout.write(f'  {len(linhas)} códigos no banco · '
                          f'{len(FOUNDING_TABLE)} na TABELA FUNDADORA '
                          f'(pricing/convention.py)')
        self.stdout.write(f'  ⛔ {len(indevidos)} que HOJE a bancada NÃO cunharia '
                          f'(a régua de triagem os reprova)')
        self.stdout.write(f'       {len(com_estoque)} COM lançamento em estoque '
                          f'← decisão humana, não mexer sozinho')
        self.stdout.write(f'       {len(indevidos) - len(com_estoque)} sem nenhum '
                          f'lançamento ← candidatos a aposentadoria')
        if fora_ok:
            rotulos = ', '.join(l['label'] for l in fora_ok)
            self.stdout.write(f'  ➕ {len(fora_ok)} legítimo(s) FORA da convenção — '
                              f'anexar em convention.py: {rotulos}')
        self.stdout.write(
            '\n⚠ APAGAR código indevido é armadilha: o próximo número sai de '
            'MAX(code)+1,\n  então o número apagado RENASCE numa categoria nova — '
            'e pode já estar\n  etiquetado numa caixa física. Aposentar sim; apagar não.\n')
