
import sys
import os

# Move up two levels from apps/systech to get to bench root
bench_path = os.path.abspath(os.path.join(os.getcwd(), '..', '..'))
sites_path = os.path.join(bench_path, 'sites')

print(f"Bench Path: {bench_path}")
print(f"Sites Path: {sites_path}")

# Add frappe to path
sys.path.append(os.path.join(bench_path, 'apps', 'frappe'))

try:
    from frappe.utils import get_sites
    sites = get_sites(sites_path)
    print("SITES FOUND:", sites)
except Exception as e:
    import traceback
    traceback.print_exc()
