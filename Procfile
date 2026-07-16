# --timeout 120 + --workers 2 (incidente 2026-07-16): a valoração on-read de
# lote grande estourava o timeout default de 30s e o worker único morria em
# loop (site "caiu"). O fix de raiz é o batch do price_lot (pricing/engine.py);
# o timeout maior é o cinto de segurança e o 2º worker evita fila atrás de
# página lenta. Se o Start Command estiver preenchido no dashboard do Render,
# ELE vence este arquivo — manter os dois iguais.
web: gunicorn core.wsgi --bind 0.0.0.0:$PORT --timeout 120 --workers 2
