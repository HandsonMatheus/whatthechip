import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings_test")
django.setup()

from django.test.utils import setup_test_environment, teardown_test_environment
from django.test.runner import DiscoverRunner
from django.core.management import call_command

setup_test_environment()
runner = DiscoverRunner()
old_config = runner.setup_databases()

YAML_PATH = "submissions/nanya_nt5cc_2026-07-15.yaml"
PNS = ["NT5CC64M16FN-DHA", "NT5CC64M16FP-DHA",
       "NT5CC512M8CN-DI", "NT5CC512M8CN-DIA", "NT5CC512M4GN-CG"]
CASE_PN = "NT5CC512M4GN"  # PN exato do debug ao vivo (sem sufixo -CG)

try:
    print("=== 1) load_brands --brand nanya --commit --skip-known-parts ===")
    call_command("load_brands", "--brand", "nanya", "--commit", "--skip-known-parts", verbosity=1)

    from chips.engine import clear_engine_cache, classify
    clear_engine_cache()

    print(f"\n=== 2) classify({CASE_PN}) -- PN do debug ao vivo, grammar-only (sem known_part) ===")
    r = classify(CASE_PN)
    print(f"  known_exact={r.get('known_exact')} chip_type={r.get('chip_type')!r} "
          f"subtype={r.get('subtype')!r} family={r.get('family')!r} "
          f"capacity={r.get('capacity')!r} profitable={r.get('profitable')!r} "
          f"pn_not_in_db={r.get('pn_not_in_db')}")
    print("  (compare chip_type acima com o debug ao vivo do usuario, que mostrou 'DDR3' -- "
          "esta sandbox usa o yaml ATUAL, que define NT5CC como DDR3L)")

    print("\n=== 3) submit_known_parts (DRY-RUN) ===")
    call_command("submit_known_parts", YAML_PATH)

    print("\n=== 4) submit_known_parts --commit ===")
    call_command("submit_known_parts", YAML_PATH, "--commit")

    from chips.models import KnownPart
    print("\n=== 5) status apos submit (oculto, review_status=submitted) ===")
    for pn in PNS:
        kp = KnownPart.objects.filter(part_number=pn).first()
        print(f"  {pn}: existe={bool(kp)} review_status={kp.review_status if kp else None} "
              f"density_gbit={kp.density_gbit if kp else None} chip_type={kp.chip_type if kp else None}")

    n = KnownPart.objects.filter(part_number__in=PNS).update(review_status="approved")
    print(f"\n=== 6) {n} aprovados (simulando admin) ===")
    clear_engine_cache()

    print("\n=== 7) classify() DEPOIS de aprovar (os 4 novos known_parts) ===")
    for pn in PNS:
        r = classify(pn)
        print(f"  {pn}:")
        print(f"      known_exact  = {r.get('known_exact')}")
        print(f"      chip_type    = {r.get('chip_type')}")
        print(f"      dram_density = {r.get('dram_density')!r}")
        print(f"      profitable   = {r.get('profitable')}")

    print(f"\n=== 8) classify({CASE_PN}) DE NOVO -- confirma que continua sem known_part dedicado ===")
    r = classify(CASE_PN)
    print(f"  known_exact={r.get('known_exact')} capacity={r.get('capacity')!r} "
          f"profitable={r.get('profitable')!r}")

    print("\n=== OK: script terminou sem excecoes ===")
except Exception:
    import traceback
    print("\n=== ERRO ===")
    traceback.print_exc()
finally:
    runner.teardown_databases(old_config)
    teardown_test_environment()
