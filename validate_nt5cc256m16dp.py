import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings_test")
django.setup()

from django.test.utils import setup_test_environment, teardown_test_environment
from django.test.runner import DiscoverRunner
from django.core.management import call_command

setup_test_environment()
runner = DiscoverRunner()
old_config = runner.setup_databases()

YAML_PATH = "submissions/nanya_nt5cc_256m16dp_2026-08-27.yaml"
PNS = [
    "NT5CC256M16DP-DI", "NT5CC256M16DP-DIA", "NT5CC256M16DP-DIB", "NT5CC256M16DP-DIH",
    "NT5CC256M16DP-DII", "NT5CC256M16DP-DINA", "NT5CC256M16DP-DIT", "NT5CC256M16DP-EK",
    "NT5CC256M16DP-EKA", "NT5CC256M16DP-EKB", "NT5CC256M16DP-EKH", "NT5CC256M16DP-EKI",
    "NT5CC256M16DP-EKNA", "NT5CC256M16DP-EKT", "NT5CC256M16DP-FLA", "NT5CC256M16DP-FLB",
    "NT5CC256M16DP-FLH", "NT5CC256M16DP-FLI", "NT5CC256M16DP-FLNA", "NT5CC256M16DP-FLT",
]

try:
    print("=== 1) load_brands --brand nanya --commit --skip-known-parts ===")
    call_command("load_brands", "--brand", "nanya", "--commit", "--skip-known-parts", verbosity=1)

    from chips.engine import clear_engine_cache, classify
    clear_engine_cache()

    print("\n=== 2) classify() ANTES (deve reproduzir o debug) ===")
    r = classify("NT5CC256M16DP")
    print(f"  NT5CC256M16DP (PN da bancada): known_exact={r.get('known_exact')} "
          f"chip_type={r.get('chip_type')!r} profitable={r.get('profitable')!r}")

    print("\n=== 3) submit_known_parts (DRY-RUN) ===")
    call_command("submit_known_parts", YAML_PATH)

    print("\n=== 4) submit_known_parts --commit ===")
    call_command("submit_known_parts", YAML_PATH, "--commit")

    from chips.models import KnownPart
    n = KnownPart.objects.filter(part_number__in=PNS).update(review_status="approved")
    print(f"\n=== 5) {n} aprovados (simulando admin) ===")
    clear_engine_cache()

    print(f"\n=== 6) classify() DEPOIS de aprovar (todos os {len(PNS)}) ===")
    ok = 0
    for pn in PNS:
        r = classify(pn)
        good = (r.get('known_exact') is True and r.get('chip_type') == 'DDR3L'
                and r.get('density_gbit_num') == 4.0 and r.get('profitable') == 'RENTÁVEL')
        ok += good
        print(f"  {pn}: known_exact={r.get('known_exact')} chip_type={r.get('chip_type')} "
              f"density_gbit={r.get('density_gbit_num')!r} confidence={r.get('confidence')!r} "
              f"profitable={r.get('profitable')} {'OK' if good else 'MISMATCH'}")
    print(f"\n  {ok}/{len(PNS)} bateram o esperado exatamente (DDR3L, 4Gb, RENTAVEL)")

    print("\n=== 7) PN exato da bancada (sem sufixo) continua sem resolver? ===")
    r = classify("NT5CC256M16DP")
    print(f"  NT5CC256M16DP: known_exact={r.get('known_exact')} profitable={r.get('profitable')!r}")

    print("\n=== OK: script terminou sem excecoes ===")
except Exception:
    import traceback
    print("\n=== ERRO ===")
    traceback.print_exc()
finally:
    runner.teardown_databases(old_config)
    teardown_test_environment()
