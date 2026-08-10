import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings_test")
django.setup()

from django.test.utils import setup_test_environment, teardown_test_environment
from django.test.runner import DiscoverRunner
from django.core.management import call_command

setup_test_environment()
runner = DiscoverRunner()
old_config = runner.setup_databases()

YAML_PATH = "submissions/nanya_nt5tu_2026-07-15.yaml"
PNS = ["NT5TU32M16FG-AC", "NT5TU32M16EG-AC", "NT5TU32M16CG-25C",
       "NT5TU64M16HG", "NT5TU64M16GG", "NT5TU128M8HE"]
CASE_PN = "NT5TU32M16FG-AC"

try:
    print("=== 1) load_brands --brand nanya --commit --skip-known-parts (com NT5TU novo) ===")
    call_command("load_brands", "--brand", "nanya", "--commit", "--skip-known-parts", verbosity=1)

    from chips.engine import clear_engine_cache, classify, assess_profitability, is_dead_by_generation
    clear_engine_cache()

    print(f"\n=== 2) classify({CASE_PN}) SO com gramatica (sem known_part) ===")
    r = classify(CASE_PN)
    ident = (r.get("chip_type") or "", r.get("capacity") or "", r.get("emcp_nand") or "",
             r.get("emcp_ram") or "", r.get("dram_density") or "", assess_profitability(r))
    print(f"  ident (p/ golden) = {ident}")
    print(f"  known_exact={r.get('known_exact')} pn_not_in_db={r.get('pn_not_in_db')}")
    print(f"  is_dead_by_generation = {is_dead_by_generation(r)}")
    print("  (compare com o debug ao vivo ORIGINAL: 100% em branco, known=false)")

    print("\n=== 3) submit_known_parts (DRY-RUN) ===")
    call_command("submit_known_parts", YAML_PATH)

    print("\n=== 4) submit_known_parts --commit ===")
    call_command("submit_known_parts", YAML_PATH, "--commit")

    from chips.models import KnownPart
    print("\n=== 5) status apos submit (oculto, review_status=submitted) ===")
    for pn in PNS:
        kp = KnownPart.objects.filter(part_number=pn).first()
        print(f"  {pn}: existe={bool(kp)} review_status={kp.review_status if kp else None} "
              f"density_gbit={kp.density_gbit if kp else None}")

    n = KnownPart.objects.filter(part_number__in=PNS).update(review_status="approved")
    print(f"\n=== 6) {n} aprovados (simulando admin) ===")
    clear_engine_cache()

    print("\n=== 7) classify() DEPOIS de aprovar ===")
    for pn in PNS:
        r = classify(pn)
        print(f"  {pn}:")
        print(f"      known_exact  = {r.get('known_exact')}")
        print(f"      chip_type    = {r.get('chip_type')}")
        print(f"      dram_density = {r.get('dram_density')!r}")
        print(f"      profitable   = {r.get('profitable')}")

    print("\n=== OK: script terminou sem excecoes ===")
except Exception:
    import traceback
    print("\n=== ERRO ===")
    traceback.print_exc()
finally:
    runner.teardown_databases(old_config)
    teardown_test_environment()
