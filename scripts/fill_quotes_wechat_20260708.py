# One-off (2026-07-08): cotações do Wu Quan via WeChat → banco. O DONO roda:
#
#   python manage.py shell -c "$(cat scripts/fill_quotes_wechat_20260708.py)"
#
# Fonte (chat WeChat 08/07/2026, câmbio 0.15):
#   LPDDR3 1G=¥5 · 2G=¥8 · 3G=¥10 · 4G=¥12   (contexto: Micron + genérica)
#   Samsung LPDDR4 1GB=¥7 · Rayson eMMC 8G=¥10 (Rayson → Outras marcas)
#
# Regras: idempotente; linha inexistente é CRIADA cotada; não-cotado/não-
# fabricado vira cotado; JÁ COTADA com valor DIFERENTE é MANTIDA e reportada
# (nunca sobrescreve cotação divergente sem o dono decidir — protege as
# LPDDR3 próprias de Samsung/SK, que valem mais). Entrada direta do dono =
# autoridade (a moderação é do fluxo do PARCEIRO). pghistory registra tudo.
from datetime import date
from decimal import Decimal

from pricing.models import Price, PriceList, STATUS_QUOTED
from tenancy.models import Company
from tenancy.scope import company_scope

RATE = Decimal('0.15')
QD = date(2026, 7, 8)
SRC = 'cotação WeChat Wu Quan 08/07/2026 (câmbio 0.15)'

# (marca da lista | None = Outras marcas, kind, gen, faixa, unidade, RMB)
ALVOS = [
    ('Micron',  'lpddr', 'LPDDR3', '1', 'GB', 5),
    ('Micron',  'lpddr', 'LPDDR3', '2', 'GB', 8),
    ('Micron',  'lpddr', 'LPDDR3', '3', 'GB', 10),
    ('Micron',  'lpddr', 'LPDDR3', '4', 'GB', 12),
    ('Samsung', 'lpddr', 'LPDDR4', '1', 'GB', 7),
    (None,      'lpddr', 'LPDDR3', '1', 'GB', 5),
    (None,      'lpddr', 'LPDDR3', '2', 'GB', 8),
    (None,      'lpddr', 'LPDDR3', '3', 'GB', 10),
    (None,      'lpddr', 'LPDDR3', '4', 'GB', 12),
    (None,      'lpddr', 'LPDDR4', '1', 'GB', 7),
    (None,      'emmc',  '',       '8', 'GB', 10),   # Rayson → Outras marcas
]

with company_scope(Company.objects.get(slug='eminer')):
    for marca, kind, gen, tier, unit, rmb in ALVOS:
        usd = (Decimal(rmb) * RATE).quantize(Decimal('0.01'))
        qs = (PriceList.objects.filter(brand__name=marca) if marca
              else PriceList.objects.filter(brand__isnull=True))
        pl = qs.first()
        rotulo = f"{marca or 'Outras marcas'} · {kind}/{gen or '—'} {tier}{unit}"
        if pl is None:
            print(f'✗ {rotulo}: LISTA INEXISTENTE — pulei')
            continue
        row = Price.objects.filter(price_list=pl, kind=kind, gen=gen,
                                   tier_value=Decimal(tier),
                                   tier_unit=unit).first()
        if row is None:
            Price(price_list=pl, kind=kind, gen=gen, tier_value=Decimal(tier),
                  tier_unit=unit, status=STATUS_QUOTED, price_min=usd,
                  price_max=usd, quote_date=QD, source=SRC).save()
            print(f'+ {rotulo}: linha CRIADA e cotada em US$ {usd}')
        elif row.status == STATUS_QUOTED and row.price_min == usd:
            print(f'= {rotulo}: JÁ TEM US$ {row.price_min} — nada a fazer')
        elif row.status == STATUS_QUOTED:
            print(f'⚠ {rotulo}: JÁ COTADA em US$ {row.price_min} (≠ US$ {usd} '
                  'do chat) — MANTIDA; se quiser trocar, decida no admin')
        else:
            era = row.get_status_display()
            row.status = STATUS_QUOTED
            row.price_min = row.price_max = usd
            row.quote_date = QD
            row.source = SRC
            row.save()
            print(f'✓ {rotulo}: preenchida US$ {usd} (era "{era}")')
    print('— fim. Card/bancada refletem na hora (tabela viva).')
