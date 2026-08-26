# O AUTO-ACESSO DO PARCEIRO VOLTA À POLICY DE LEITURA (regressão da 0021).
#
# A `pricing/0010_buyer_self_policy` nasceu de um bug de PRODUÇÃO (2026-07-09):
# o parceiro não tem Membership → o middleware não emite `app.company_id` → a
# policy devolvia ZERO linhas de `pricing_buyer` → `partner_required` não achava
# o buyer → 403. O conserto foi a cláusula de auto-acesso via
# `pricing_buyer_users` + `app.user_id`.
#
# A `0021_comprador_plataforma` (2026-08-03) trocou a `tenant_isolation` por
# quatro policies (read/ins/upd/del) e a cláusula **não foi para a de LEITURA**:
#
#     _READ_WIDE = "(company_id = GUC OR PLAT OR company_id IS NULL)"  ← sumiu
#     _WRITE     = "(company_id = GUC OR PLAT OR PARTNER)"             ← sobrou
#
# POR QUE PRODUÇÃO NÃO CAIU: a mesma migração rodou `_flip_para_plataforma` e
# pôs `company=NULL` em todo Buyer — e `company_id IS NULL` deixa a linha
# legível por qualquer um. O portão do parceiro passou a funcionar por acidente
# do DADO, não pela policy. No dia em que existir um Buyer com `company_id`
# preenchido — e o model continua suportando, `company` é nullable — o parceiro
# dele leva 403. É o bug de 2026-07-09 dormindo.
#
# O `PartnerSelfAccessRLSTests` cravava exatamente isso e está vermelho desde
# então (registrado como "vermelho conhecido" em a6b2008, sem causa).
#
# ESCOPO: só `pricing_buyer`, igual à 0010. As tabelas sensíveis
# (PriceList/Price/PriceChangeRequest/eventos) NÃO ganham cláusula nenhuma — o
# parceiro chega nelas dentro do `company_scope` que o `partner_required` abre
# depois de achar o buyer. Achar o buyer é o único passo que acontece ANTES de
# existir escopo, e é só ele que precisa disto.
#
# Só AMPLIA visibilidade, e só para os usuários do PRÓPRIO buyer: nenhuma linha
# que era legível deixa de ser. Reversível — o reverso recria a `tenant_read`
# no formato da 0021.
#
# ⚠ Residual que continua de pé (a 0021 documenta o equivalente para escrita):
# com `company_id IS NULL` na leitura, dois compradores de PLATAFORMA se
# enxergam. Hoje há um. Apertar exigiria trocar o `IS NULL` por um join até o
# buyer, o que mexe no que a 0021 decidiu de propósito — decisão do dono,
# anotada no PLANO_COMPRADOR_V2.md.

from django.db import migrations

_GUC = "NULLIF(current_setting('app.company_id', true), '')::int"
_PLAT = "current_setting('app.platform', true) = '1'"
_SELF = ("id IN (SELECT buyer_id FROM pricing_buyer_users"
         " WHERE user_id = NULLIF(current_setting('app.user_id', true), '')::int)")

_READ_0021 = f"(company_id = {_GUC} OR {_PLAT} OR company_id IS NULL)"
_READ_NOVA = f"(company_id = {_GUC} OR {_PLAT} OR company_id IS NULL OR {_SELF})"


def _troca(schema_editor, using):
    schema_editor.execute('DROP POLICY IF EXISTS tenant_read ON pricing_buyer')
    schema_editor.execute(
        f'CREATE POLICY tenant_read ON pricing_buyer FOR SELECT USING ({using})')


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return                                     # SQLite (testes): no-op
    _troca(schema_editor, _READ_NOVA)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    _troca(schema_editor, _READ_0021)


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0025_categorycode_retired'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
