"""
Context processor do CÂMBIO (PLANO_FX, dono 2026-08-01: "deixar mais claro
no frontend o câmbio em tempo real").

Injeta ``wtc_fx`` (taxa vigente + carimbo) em toda página autenticada — o
header do painel interno (base_estoque) estampa "1 ¥ ≈ US$ X · mid-market
DD/MM". A taxa é dado PÚBLICO de mercado (não é preço): aparece para todos
os papéis; os VALORES seguem atrás dos gates de sempre. Custo: 1 query
leve (FxRate mais recente) por página logada.
"""


def fx(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}
    from pricing.engine import fx_display
    # Sem NENHUMA taxa (FxRate vazia): ainda assim rende o widget, como
    # AVISO operacional ("rode fetch_fx_rate") — sumir calado esconderia
    # o problema exatamente de quem pode resolver.
    return {'wtc_fx': fx_display() or {'rate_disp': None}}
