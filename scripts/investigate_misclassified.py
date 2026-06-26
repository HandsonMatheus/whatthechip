"""
Investiga a origem dos registros MT53B classificados como eMMC/uMCP
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from chips.models import KnownPart

print("=== MT53B com chip_type=eMMC ===")
for kp in KnownPart.objects.filter(chip_type="eMMC", part_number__startswith="MT53B"):
    print(f"  id={kp.id}  PN={kp.part_number}")
    print(f"    chip_type={kp.chip_type}  subtype={kp.subtype or '(vazio)'}")
    print(f"    capacity={kp.capacity or '-'}  density={kp.density_gbit or '-'}")
    print(f"    source={kp.source}  source_url={kp.source_url or '-'}")
    print(f"    confidence={kp.confidence}")
    print(f"    notes={kp.notes[:80] if kp.notes else '-'}")
    print()

print("=== MT53B com chip_type=uMCP ===")
for kp in KnownPart.objects.filter(chip_type="uMCP", part_number__startswith="MT53B"):
    print(f"  id={kp.id}  PN={kp.part_number}")
    print(f"    chip_type={kp.chip_type}  subtype={kp.subtype or '(vazio)'}")
    print(f"    source={kp.source}  source_url={kp.source_url or '-'}")
    print(f"    confidence={kp.confidence}")
    print()
