import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings_test")
django.setup()

from django.test.utils import setup_test_environment, teardown_test_environment
from django.test.runner import DiscoverRunner
from django.core.management import call_command

setup_test_environment()
runner = DiscoverRunner()
old_config = runner.setup_databases()

YAML_PATH = "submissions/nanya_nt5cb_128m16h_2026-08-26.yaml"
PNS = ["NT5CB128M16HP-DI", "NT5CB128M16HP-EK", "NT5CB128M16HP-CG", "NT5CB128M16HP-DII"]
CASE_PN = "NT5CB128M16HP"  # PN exato do debug ao vivo (sem sufixo)

try:
    print("=== 1) load_brands --brand nanya --commit --skip-known-parts ===")
    call_command("load_brands", "--brand", "nanya", "--commit", "--skip-known-parts", verbosity=1)

    from chips.engine import clear_engine_cache, classify
    clear_engine_cache()

    print(f"\n=== 2) classify({CASE_PN}) ANTES -- NT5CB nao tem ChipFamily (100% invisivel) ===")
    r = classify(CASE_PN)
    print(f"  known_exact={r.get('known_exact')} chip_type={r.get('chip_type')!r} "
          f"capacity={r.get('capacity')!r} profitable={r.get('profitable')!r}")

    print("\n=== 3) submit_known_parts (DRY-RUN) ===")
    call_command("submit_known_parts", YAML_PATH)

    print("\n=== 4) submit_known_parts --commit ===")
    call_command("submit_known_parts", YAML_PATH, "--commit")

    from chips.models import KnownPart
    n = KnownPart.objects.filter(part_number__in=PNS).update(review_status="approved")
    print(f"\n=== 5) {n} aprovados (simulando admin) ===")
    clear_engine_cache()

    print("\n=== 6) classify() DEPOIS de aprovar ===")
    for pn in PNS:
        r = classify(pn)
        print(f"  {pn}: known_exact={r.get('known_exact')} chip_type={r.get('chip_type')} "
              f"dram_density={r.get('dram_density')!r} profitable={r.get('profitable')}")

    print(f"\n=== 7) classify({CASE_PN}) DE NOVO -- PN exato da bancada, sem sufixo ===")
    r = classify(CASE_PN)
    print(f"  known_exact={r.get('known_exact')} profitable={r.get('profitable')!r}")

    print("\n=== OK: script terminou sem excecoes ===")
except Exception:
    import traceback
    print("\n=== ERRO ===")
    traceback.print_exc()
finally:
    runner.teardown_databases(old_config)
    teardown_test_environment()
