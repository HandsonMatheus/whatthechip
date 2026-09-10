# -*- coding: utf-8 -*-
"""A lista INICIAL de defeitos — tirada do que o comprador já manda no WeChat.

Não é a lista final e não pretende ser: o dono disse *"a lista de defeitos é
criada por mim e se ele quiser mais defeitos eu adiciono"*. Isto é só o ponto
de partida, para a tela não nascer vazia. Daqui em diante quem manda é o admin.

⚠ `update_or_create` pelo código, e NUNCA sobrescreve o que já existe além do
  que a semente conhece: se o dono renomear "Canto lascado" ou trocar a
  severidade, rodar a migração de novo não desfaz a edição dele. Semente que
  reverte trabalho humano é semente que ninguém deixa rodar duas vezes.

Os nomes em chinês são os que ELE usa (缺角, 划痕, 起泡, 温度过高) — vieram das
mensagens dele, não de dicionário. É o que faz a etiqueta ser reconhecível na
tela dele em vez de uma tradução plausível que ele nunca viu.
"""
from django.db import migrations

#  código               PT                  ES                    ZH          EN                   sev         ordem
DEFEITOS = [
    ('balls_faltando',  'Balls faltando',   'Balls faltantes',    '缺球',      'Missing balls',     'recusa',   10),
    ('empolamento',     'Empolamento',      'Ampollas',           '起泡',      'Blistering',        'recusa',   20),
    ('superaquecido',   'Superaquecido',    'Sobrecalentado',     '温度过高',   'Overheated',        'recusa',   30),
    ('trincado',        'Trincado',         'Agrietado',          '裂纹',      'Cracked',           'recusa',   40),
    ('oxidado',         'Oxidado',          'Oxidado',            '氧化',      'Oxidized',          'recusa',   50),
    ('canto_lascado',   'Canto lascado',    'Esquina astillada',  '缺角',      'Chipped corner',    'desconto', 60),
    ('risco',           'Risco',            'Rayadura',           '划痕',      'Scratch',           'desconto', 70),
    ('balls_deformados','Balls deformados', 'Balls deformados',   '球变形',    'Deformed balls',    'desconto', 80),
    ('residuo',         'Resíduo de solda', 'Residuo de soldadura', '锡渣',    'Solder residue',    'desconto', 90),
    ('marcacao_fraca',  'Marcação apagada', 'Marcado borroso',    '字迹模糊',   'Faded marking',     'desconto', 100),
]


def semear(apps, schema_editor):
    DefeitoTipo = apps.get_model('vendas', 'DefeitoTipo')
    for codigo, pt, es, zh, en, sev, ordem in DEFEITOS:
        DefeitoTipo.objects.update_or_create(
            codigo=codigo,
            defaults={'nome_pt': pt, 'nome_es': es, 'nome_zh': zh,
                      'nome_en': en, 'severidade': sev, 'ordem': ordem,
                      'ativo': True})


def limpar(apps, schema_editor):
    DefeitoTipo = apps.get_model('vendas', 'DefeitoTipo')
    DefeitoTipo.objects.filter(
        codigo__in=[d[0] for d in DEFEITOS]).delete()


class Migration(migrations.Migration):

    dependencies = [('vendas', '0027_prova_rls')]

    operations = [migrations.RunPython(semear, limpar)]
