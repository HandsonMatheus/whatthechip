"""
test_runner.py — runner de teste que ISOLA a cache do engine entre os testes.

**Problema (instabilidade por ordem):** `chips.engine` cacheia famílias e mapas de
decode com `@lru_cache` chaveado por `catalog_version` (ver `_families_for_version` /
`_decode_map_for_version`). Em PRODUÇÃO a versão é MONOTÔNICA — só sobe — então a
chave nunca se repete e a cache é sempre correta (é a regra de ouro #3).

Nos TESTES, cada caso recria o banco e o `catalog_version` volta a números baixos.
Assim o MESMO número de versão passa a valer para catálogos DIFERENTES (marcas
diferentes carregadas em testes diferentes) → um teste serve a cache "velha" de
outro. Sintoma: a suíte passa ou falha dependendo da ORDEM em que os testes rodam
(ex.: `--reverse` quebra testes distintos). Cada teste tenta se proteger chamando
`clear_engine_cache()` na mão, mas quem esquece fica frágil.

**Solução (test-only):** limpar as caches do engine ANTES de cada teste, de forma
central. Vive apenas no `TEST_RUNNER` de `core.settings_test` — **não toca em código
de produção nem na lógica de nenhum teste**.
"""
from unittest.runner import TextTestResult

from django.test.runner import DiscoverRunner


class _EngineCacheClearMixin:
    """Mixin de TestResult: limpa a cache do engine no início de CADA teste."""

    def startTest(self, test):
        try:
            from chips.engine import clear_engine_cache
            clear_engine_cache()
        except Exception:
            # Em algum teste o engine pode não estar importável — não é fatal.
            pass
        super().startTest(test)


class EngineCacheIsolationRunner(DiscoverRunner):
    """DiscoverRunner que injeta o mixin acima no result class do unittest.

    Compõe com o result padrão do Django (preservando `--debug-sql` / `--pdb`),
    então o único efeito adicional é o `clear_engine_cache()` por teste.
    """

    def get_resultclass(self):
        base = super().get_resultclass() or TextTestResult
        return type(
            "EngineCacheIsolating" + base.__name__,
            (_EngineCacheClearMixin, base),
            {},
        )
