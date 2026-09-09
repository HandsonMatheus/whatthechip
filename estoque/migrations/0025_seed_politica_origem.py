"""Semeia a política origem × tipo com a tabela do dono (2026-09-02).

TODAS as combinações nascem EXPLÍCITAS — nenhuma fica implícita. Duas razões:
o admin vira uma torneira legível (você vê o que está aberto E o que está
fechado), e o `bloqueio_de_origem` pode ser fail-closed sem falso positivo
(linha ausente = decisão que ninguém tomou, não permissão).

⚠ `ram` nasce com TUDO ABERTO de propósito: a fase 2 depende da largura de
barramento ("8BIT DDR"), que vive no `interface` e é outro eixo — não um item a
mais nesta tabela. Semear fechado mudaria comportamento hoje sem regra pronta.

⚠ LPDDR ENTRA EM PCB (2026-09-08), e a lição vale mais que a célula: a lista
original ('PCB recebe DDR/eMMC/K9') era o que o dono SABE que vai ali — não o
que ele VERIFICOU que nunca vai. Uma foto do comprador (Wu Quan, LPDDR numa
placa de PCB, "these chips are pretty expensive right now") derrubou a célula
antes de ela chegar em produção. O bloqueio mora DEPOIS da fila e DEPOIS da
rentabilidade, então a única coisa que uma célula fechada por engano consegue
barrar é o material que o sistema já conhece E já avaliou como RENTÁVEL — o
material bom. Bloqueio errado joga dinheiro fora e ensina o operador a
desconfiar da ferramenta; liberação errada só precifica conservador. Os dois
erros não custam o mesmo, e a semente segue essa assimetria.

⚠ PREÇO É OUTRA CONVERSA: hoje só o eMMC carrega origem na chave de preço
(constraint `price_origin_emmc_only`, pricing/0019). LPDDR de celular e LPDDR de
PCB caem na MESMA linha de preço. Se o comprador pagar diferente pelos dois,
abrir a torneira é necessário mas não é suficiente — falta dar origem à chave do
LPDDR, e isso é trabalho de precificação, não desta tabela.

⚠ ORIGENS LEGADAS (`mixed`, `k9`, de estoque/0022) nascem com TUDO ABERTO, e
isto não é descuido: elas existem só para ROTULAR lote importado do controle
antigo (Lot.ORIGIN_LEGACY — fora do formulário de abrir lote). Semear fechado
transformaria a reconciliação do passado numa parede de recusas, contra o
"o que foi já foi" do dono. Se um dia um lote legado for reaberto e alguém
lançar chip nele, a torneira está no admin.

Tabela GLOBAL sem `company` (igual ProfitabilityConfig) → sem RLS, então este
RunPython não precisa do `SET LOCAL app.platform` que os de pricing/vendas usam.
"""
from django.db import migrations

#: kinds PERMITIDOS por origem. Origem que não aparece aqui não é semeada —
#: e o `PoliticaOrigemDeclaracaoTests` fica vermelho até alguém decidir.
PERMITIDO = {
    'phone': {'emcp', 'umcp', 'emmc', 'ufs', 'lpddr'},
    'pcb':   {'ddr', 'emmc', 'k9', 'ssd', 'lpddr'},
    'ram':   None,      # None = TUDO aberto (ver notas)
    'mixed': None,
    'k9':    None,
}
NOTA = {
    'phone': 'Tabela do dono, 2026-09-02.',
    'pcb':   'Tabela do dono, 2026-09-02. SSD entra em PCB (decisão 2026-09-02). '
             'LPDDR entra em PCB (2026-09-08): o comprador mandou foto de um LPDDR '
             'numa placa de PCB — a lista original era o que o dono SABE que vai '
             'ali, não o que ele verificou que nunca vai.',
    'ram':   'FASE 2 — tudo aberto de propósito. A regra de RAM depende da '
             'largura de barramento (8BIT), que vive no `interface`, não no kind.',
    'mixed': 'ORIGEM LEGADA (controle antigo). Tudo aberto: fechar aqui viraria '
             'parede na reconciliação do passado. Ver Lot.ORIGIN_LEGACY.',
    'k9':    'ORIGEM LEGADA (controle antigo). Tudo aberto: fechar aqui viraria '
             'parede na reconciliação do passado. Ver Lot.ORIGIN_LEGACY.',
}


def _kinds():
    # Import tardio e defensivo: a lista de KINDS é do pricing, mas uma migração
    # não pode quebrar se a app mudar de forma no futuro — por isso o fallback
    # literal, que é o vocabulário congelado NESTA data.
    try:
        from pricing.models import KINDS
        return sorted(KINDS)
    except Exception:                                   # noqa: BLE001
        return ['ddr', 'emcp', 'emmc', 'k9', 'lpddr', 'ssd', 'ufs', 'umcp']


def semear(apps, schema_editor):
    Politica = apps.get_model('estoque', 'PoliticaOrigemTipo')
    kinds = _kinds()
    for origem, permitidos in PERMITIDO.items():
        for kind in kinds:
            Politica.objects.update_or_create(
                origin=origem, kind=kind,
                defaults={'permitido': permitidos is None or kind in permitidos,
                          'notes': NOTA[origem]})


def limpar(apps, schema_editor):
    apps.get_model('estoque', 'PoliticaOrigemTipo').objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [('estoque', '0024_politicaorigemtipo')]
    operations = [migrations.RunPython(semear, limpar)]
