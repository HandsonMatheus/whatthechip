import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings_test")
django.setup()

from django.test.utils import setup_test_environment, teardown_test_environment
from django.test.runner import DiscoverRunner
from django.core.management import call_command

setup_test_environment()
runner = DiscoverRunner()
old_config = runner.setup_databases()

YAML_PATH = "submissions/nanya_nt5ad_512m16a4_2026-08-27.yaml"
PNS = [
    "NT5AD512M16A4-GZ", "NT5AD512M16A4-GZI", "NT5AD512M16A4-GZNA",
    "NT5AD512M16A4-GZT", "NT5AD512M16A4-HR", "NT5AD512M16A4-HRA",
    "NT5AD512M16A4-HRH", "NT5AD512M16A4-HRI", "NT5AD512M16A4-HRK",
]

try:
    print("=== 1) load_brands --brand nanya --commit --skip-known-parts ===")
    call_command("load_brands", "--brand", "nanya", "--commit", "--skip-known-parts", verbosity=1)

    from chips.engine import clear_engine_cache, classify
    clear_engine_cache()

    print("\n=== 2) classify() ANTES (deve reproduzir o debug: gramatica reconhece, sem capacidade) ===")
    r = classify("NT5AD512M16A4")
    print(f"  NT5AD512M16A4 (PN da bancada): known_exact={r.get('known_exact')} "
          f"chip_type={r.get('chip_type')!r} profitable={r.get('profitable')!r}")
    for pn in PNS[:2]:
        r = classify(pn)
        print(f"  {pn}: known_exact={r.get('known_exact')} profitable={r.get('profitable')!r}")

    print("\n=== 3) submit_known_parts (DRY-RUN) ===")
    call_command("submit_known_parts", YAML_PATH)

    print("\n=== 4) submit_known_parts --commit ===")
    call_command("submit_known_parts", YAML_PATH, "--commit")

    from chips.models import KnownPart
    n = KnownPart.objects.filter(part_number__in=PNS).update(review_status="approved")
    print(f"\n=== 5) {n} aprovados (simulando admin) ===")
    clear_engine_cache()

    print("\n=== 6) classify() DEPOIS de aprovar (todos os 9) ===")
    for pn in PNS:
        r = classify(pn)
        print(f"  {pn}: known_exact={r.get('known_exact')} chip_type={r.get('chip_type')} "
              f"density_gbit={r.get('density_gbit_num')!r} dram_density={r.get('dram_density')!r} "
              f"confidence={r.get('confidence')!r} profitable={r.get('profitable')}")

    print("\n=== 7) PN exato da bancada (sem sufixo) continua sem resolver? ===")
    r = classify("NT5AD512M16A4")
    print(f"  NT5AD512M16A4: known_exact={r.get('known_exact')} profitable={r.get('profitable')!r}")

    print("\n=== 8) confirma -IX (excluido) continua desconhecido ===")
    r = classify("NT5AD512M16A4-IX")
    print(f"  NT5AD512M16A4-IX: known_exact={r.get('known_exact')} profitable={r.get('profitable')!r}")

    print("\n=== OK: script terminou sem excecoes ===")
except Exception:
    import traceback
    print("\n=== ERRO ===")
    traceback.print_exc()
finally:
    runner.teardown_databases(old_config)
    teardown_test_environment()
