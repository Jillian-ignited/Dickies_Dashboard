#!/usr/bin/env python3
"""
html_updater_v3.py

Safe SKU-data-only HTML updater for the Dickies dashboard.
"""

import json
from pathlib import Path
import re
from datetime import datetime

ARTIFACT_DIR = Path("/home/ubuntu/dickies_output/weekly_artifacts")
SKU_FILE = ARTIFACT_DIR / "sku_master.json"
HTML_PATH = Path("/var/www/dickies/index.html")
BACKUP_DIR = Path("/home/ubuntu/deployment_package_final")


# -----------------------------------------------------------------------------
# Load SKU data
# -----------------------------------------------------------------------------
def load_sku_data():
    if not SKU_FILE.exists():
        raise FileNotFoundError(f"Cannot find {SKU_FILE}")
    with SKU_FILE.open("r", encoding="utf-8") as f:
        sku_payload = json.load(f)

    skus = sku_payload.get("skus", [])
    if not skus:
        raise ValueError("sku_master.json has no 'skus' array")

    return sku_payload["week"], skus


# -----------------------------------------------------------------------------
# Totals for % calcs
# -----------------------------------------------------------------------------
def compute_totals(skus):
    total_sales_ytd = sum(float(s.get("sales_dollars_ytd_ty", 0) or 0) for s in skus)
    total_inv_ytd   = sum(float(s.get("inventory_ytd_ty", 0) or 0) for s in skus)

    if total_sales_ytd == 0:
        total_sales_ytd = 1.0
    if total_inv_ytd == 0:
        total_inv_ytd = 1.0

    return total_sales_ytd, total_inv_ytd


# -----------------------------------------------------------------------------
# Build front-end compatible skuData JS array
# -----------------------------------------------------------------------------
def build_sku_js_array(skus):
    total_sales_ytd, total_inv_ytd = compute_totals(skus)

    js_rows = []
    for s in skus:
        sales_ytd = float(s.get("sales_dollars_ytd_ty", 0) or 0)
        inv_ytd   = float(s.get("inventory_ytd_ty", 0) or 0)
        pct_sales = round((sales_ytd / total_sales_ytd) * 100, 1)
        pct_inv   = round((inv_ytd   / total_inv_ytd)   * 100, 1)

        # Escape quotes for JS
        desc = (s.get("description", "") or "")
        desc = desc.replace('"', '\\"').replace("'", "\\'")

        row = {
            "Item_Key": s.get("sku", ""),
            "Item_Description": desc,
            "Fineline": str(s.get("fineline", "") or ""),
            "Size": "",
            "ABC": s.get("tier", "") or "",
            "Sales_13W_Retail": round(sales_ytd, 2),
            "Total_Inv_Retail": round(inv_ytd, 2),
            "Pct_of_Sales": pct_sales,
            "Pct_of_Inventory": pct_inv,
            "WOS_Per_SKU": float(s.get("wos", 0) or 0),
            "Store_Count": 0,
            "Style_Action": s.get("status", "Monitor") or "Monitor",
        }
        js_rows.append(row)

    # Convert rows to JS
    lines = []
    lines.append("const skuData = [")
    for r in js_rows:
        obj = (
            "  {"
            f" Item_Key: '{r['Item_Key']}',"
            f" Item_Description: '{r['Item_Description']}',"
            f" Fineline: '{r['Fineline']}',"
            f" Size: '{r['Size']}',"
            f" ABC: '{r['ABC']}',"
            f" Sales_13W_Retail: {r['Sales_13W_Retail']},"
            f" Total_Inv_Retail: {r['Total_Inv_Retail']},"
            f" Pct_of_Sales: {r['Pct_of_Sales']},"
            f" Pct_of_Inventory: {r['Pct_of_Inventory']},"
            f" WOS_Per_SKU: {r['WOS_Per_SKU']},"
            f" Store_Count: {r['Store_Count']},"
            f" Style_Action: '{r['Style_Action']}'"
            " },"
        )
        lines.append(obj)
    lines.append("];")

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Replace JS block
# -----------------------------------------------------------------------------
def replace_sku_block(html, new_block):
    pattern = re.compile(r"const\s+skuData\s*=\s*\[[\s\S]*?\];", re.MULTILINE)

    if not pattern.search(html):
        raise ValueError("Could not find existing const skuData = [...] block.")

    return pattern.sub(new_block, html, count=1)


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    print("=" * 100)
    print("DICKIES DASHBOARD HTML SKU UPDATER v3")
    print("=" * 100)

    week, skus = load_sku_data()
    print(f"✅ Loaded Week {week}, {len(skus)} SKUs from sku_master.json")

    new_sku_block = build_sku_js_array(skus)
    print("✅ Built new skuData block")

    html_text = HTML_PATH.read_text(encoding="utf-8")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"index_week{week:02d}_{timestamp}.sku_backup.html"
    backup_path.write_text(html_text, encoding="utf-8")
    print(f"💾 Backup saved → {backup_path}")

    updated_html = replace_sku_block(html_text, new_sku_block)
    HTML_PATH.write_text(updated_html, encoding="utf-8")

    print("✅ Updated /var/www/dickies/index.html with fresh skuData")
    print("=" * 100)
    print("Hard refresh your browser (Ctrl + F5) to see updated SKU data.")
    print("=" * 100)


if __name__ == "__main__":
    main()

