#!/usr/bin/env python3
"""Dickies Dashboard HTML updater - Phase 1 (data-truthful skuData + historicalData).

This script:
  * Loads JSON artifacts from /home/ubuntu/dickies_output/weekly_artifacts
  * Rebuilds `const skuData = [...]` so the SKU table uses real data
  * Appends/overwrites `window.historicalData` at the end of index.html

It does **not** touch the ETL or any Excel files.
"""
from pathlib import Path
import json
import re
from datetime import datetime

# --- CONFIG -----------------------------------------------------------------

DATA_DIR = Path("/home/ubuntu/dickies_output/weekly_artifacts")
HTML_PATH = Path("/var/www/dickies/index.html")
BACKUP_DIR = Path("/home/ubuntu/deployment_package_final")

# --- HELPERS ----------------------------------------------------------------

def load_json(path: Path, description: str):
    if not path.exists():
        raise FileNotFoundError(f"{description} not found at {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def build_enriched_sku_list(raw_skus):
    """Map sku_master.json records to the fields the dashboard expects.

    We also compute:
      - Total YTD sales dollars
      - Total inventory dollars (approximate)
      - % of sales
      - % of inventory
    """
    # First pass: compute totals and per-sku inventory dollars
    total_sales_ytd = 0.0
    total_inv_dollars = 0.0
    tmp = []

    for s in raw_skus:
        sales_ytd = float(s.get("sales_dollars_ytd_ty") or 0.0)
        units_ytd = float(s.get("sales_units_ytd_ty") or 0.0)
        inv_units = float(s.get("inventory_ytd_ty") or 0.0)

        # Average price from YTD metrics (avoid div-by-zero)
        avg_price = sales_ytd / units_ytd if units_ytd else 0.0
        inv_dollars = inv_units * avg_price

        total_sales_ytd += sales_ytd
        total_inv_dollars += inv_dollars

        tmp.append({
            "raw": s,
            "sales_ytd": sales_ytd,
            "units_ytd": units_ytd,
            "inv_units": inv_units,
            "inv_dollars": inv_dollars,
            "avg_price": avg_price,
        })

    if total_sales_ytd <= 0:
        total_sales_ytd = 1.0
    if total_inv_dollars <= 0:
        total_inv_dollars = 1.0

    enriched = []
    for item in tmp:
        s = item["raw"]
        sales_ytd = item["sales_ytd"]
        units_ytd = item["units_ytd"]
        inv_units = item["inv_units"]
        inv_dollars = item["inv_dollars"]
        avg_price = item["avg_price"]

        pct_sales = round(100.0 * sales_ytd / total_sales_ytd, 3)
        pct_inv = round(100.0 * inv_dollars / total_inv_dollars, 3)

        sku_code = s.get("sku") or ""
        fineline = s.get("fineline")
        fineline_desc = s.get("category") or s.get("fineline_name") or ""
        short_desc = s.get("description") or ""
        tier = s.get("tier") or ""
        wos = float(s.get("wos") or 0.0)

        # Retail price: use explicit field if present, otherwise fallback to avg YTD price
        retail_price = float(s.get("retail_price") or avg_price or 0.0)

        # Store count isn't in sku_master yet – set to 0 for now.
        store_count = int(s.get("store_count") or 0)

        # Status logic – simple heuristic for now
        if tier == "A":
            status = "Drive Growth"
        elif tier == "B":
            status = "Protect"
        else:
            status = "Monitor"

        enriched.append({
            "Item_Key": sku_code,                 # best available style identifier
            "Short_Description": short_desc,
            "Fineline": fineline,
            "Fineline_Description": fineline_desc,
            "Retail_Price": round(retail_price, 2),
            "YTD_Sales_Units": int(units_ytd),
            "YTD_Sales_Retail": round(sales_ytd, 2),
            "Total_Inv_Units": int(inv_units),
            "Total_Inv_Retail": round(inv_dollars, 2),
            "Pct_of_Sales": pct_sales,
            "Pct_of_Inventory": pct_inv,
            "WOS_Per_SKU": round(wos, 1),
            "Store_Count": store_count,
            "ABC": tier,
            "Status": status,
        })

    return enriched

def inject_sku_data(html_text: str, sku_list):
    """Replace the existing const skuData = [...] block with new data."""
    sku_js = json.dumps(sku_list, indent=2)
    pattern = re.compile(r"const\\s+skuData\\s*=\\s*\\[(?:.|\\n)*?\\];", re.MULTILINE)
    replacement = "const skuData = " + sku_js + ";"

    new_text, count = pattern.subn(replacement, html_text)
    if count == 0:
        raise RuntimeError("Could not find existing `const skuData = [...]` block to replace.")
    return new_text

def append_historical_data_block(html_text: str, meta, raw_skus, finelines, seasonal_risk, actions):
    """Append a window.historicalData block just before </body>."""
    hist = {
        "meta": meta,
        "skus": raw_skus,
        "finelines": finelines,
        "seasonal_risk": seasonal_risk,
        "actions": actions,
    }
    hist_js = json.dumps(hist, indent=2)

    script_block = "\n<script>\nwindow.historicalData = " + hist_js + ";\n</script>\n</body>"

    if "</body>" not in html_text:
        raise RuntimeError("Could not find </body> tag in HTML.")
    return html_text.replace("</body>", script_block)

# --- MAIN -------------------------------------------------------------------

def main():
    print("=" * 100)
    print("DICKIES DASHBOARD HTML UPDATER – PHASE 1")
    print("=" * 100)

    # 1) Load JSON artifacts
    meta = load_json(DATA_DIR / "meta.json", "meta.json")
    sku_master = load_json(DATA_DIR / "sku_master.json", "sku_master.json")
    fineline_master = load_json(DATA_DIR / "fineline_master.json", "fineline_master.json")
    seasonal_risk = load_json(DATA_DIR / "seasonal_risk.json", "seasonal_risk.json")
    action_items = load_json(DATA_DIR / "action_items.json", "action_items.json")

    raw_skus = sku_master.get("skus") or []
    finelines = fineline_master.get("finelines") or []

    week = meta.get("week") or "??"
    print(f"✅ Loaded Week {week} JSON artifacts")
    print(f"   SKUs: {len(raw_skus)}")
    print(f"   Finelines: {len(finelines)}")

    # 2) Build enriched skuData for the dashboard
    print("\n🔄 Building enriched skuData (YTD $, % of sales, % of stock, WOS)...")
    enriched_skus = build_enriched_sku_list(raw_skus)
    print(f"   ✓ Enriched {len(enriched_skus)} SKUs")

    # 3) Backup current HTML
    if not HTML_PATH.exists():
        raise FileNotFoundError(f"Dashboard HTML not found at {HTML_PATH}")

    html_text = HTML_PATH.read_text(encoding="utf-8")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = BACKUP_DIR / f"index_week{week:02d}_{timestamp}.phase1_backup.html"
    backup_name.write_text(html_text, encoding="utf-8")
    print(f"💾 Backup saved → {backup_name}")

    # 4) Replace skuData block
    print("\n🔄 Injecting new skuData block into index.html...")
    html_text = inject_sku_data(html_text, enriched_skus)
    print("   ✓ skuData block replaced")

    # 5) Append window.historicalData for downstream use (Seasonal + Action Plan)
    print("\n🔄 Appending window.historicalData block...")
    html_text = append_historical_data_block(
        html_text,
        meta=meta,
        raw_skus=raw_skus,
        finelines=finelines,
        seasonal_risk=seasonal_risk,
        actions=action_items,
    )
    print("   ✓ window.historicalData appended")

    # 6) Write the updated HTML back to disk
    HTML_PATH.write_text(html_text, encoding="utf-8")
    print("\n✅ HTML update complete.")
    print("=" * 100)
    print(f"Dashboard: {HTML_PATH}")
    print(f"Backup:    {backup_name}")
    print("=" * 100)
    print("Hard refresh your browser (Ctrl + F5) to see updated SKU metrics.")
    print("=" * 100)

if __name__ == "__main__":
    main()
