#!/usr/bin/env python3
"""
html_updater_v5.py

Enhanced version of html_updater_v4.py with additional features:
1. Injects action items from action_items.json as JavaScript variable
2. Adds tier count tokens for dynamic tier display
3. Handles seasonal risk data
4. All features from v4 (SKU data, weekly metrics, Tab 2 insights)

New tokens added:
- [[TIER_A_COUNT]], [[TIER_B_COUNT]], [[TIER_C_COUNT]]
- [[TIER_AB_COUNT]], [[TIER_AB_SALES_PCT]]
- [[ACTION_ITEMS_COUNT]], [[SEASONAL_RISK_COUNT]]
"""

import json
import re
from datetime import datetime
from pathlib import Path


# -----------------------------------------------------------------------------
# Paths and constants
# -----------------------------------------------------------------------------

ARTIFACT_DIR = Path("/home/ubuntu/dickies_output/weekly_artifacts")

# Input JSON files
SKU_FILE = ARTIFACT_DIR / "sku_master.json"
WEEKLY_SUMMARY_FILE = ARTIFACT_DIR / "weekly_sales_summary.json"
META_FILE = ARTIFACT_DIR / "meta.json"
ACTION_ITEMS_FILE = ARTIFACT_DIR / "action_items.json"
SEASONAL_RISK_FILE = ARTIFACT_DIR / "seasonal_risk.json"
TAB2_INSIGHTS_FILE = ARTIFACT_DIR / "weekly_tab2_insights.html"

# Target HTML file
HTML_PATH = Path("/var/www/dickies/index.html")

# Backup directory
BACKUP_DIR = Path("/home/ubuntu/deployment_package_final")


# -----------------------------------------------------------------------------
# SKU loading and JS generation
# -----------------------------------------------------------------------------

def load_sku_data():
    """Load the current week number and list of SKUs from sku_master.json."""
    if not SKU_FILE.exists():
        raise FileNotFoundError(f"Cannot find {SKU_FILE}")
    with SKU_FILE.open("r", encoding="utf-8") as f:
        sku_payload = json.load(f)

    # Handle both formats: {"skus": [...]} or just [...]
    if isinstance(sku_payload, dict):
        skus = sku_payload.get("skus", [])
        week = sku_payload.get("week", 0)
    else:
        skus = sku_payload
        week = 0

    if not skus:
        raise ValueError("sku_master.json has no SKUs")

    return week, skus


def compute_totals(skus):
    """Compute totals for percentage calculations."""
    total_sales_ytd = sum(float(s.get("sales_dollars_ytd", 0) or 0) for s in skus)
    total_inv_ytd = sum(float(s.get("inventory_dollars_lw", 0) or 0) for s in skus)

    if total_sales_ytd == 0:
        total_sales_ytd = 1.0
    if total_inv_ytd == 0:
        total_inv_ytd = 1.0

    return total_sales_ytd, total_inv_ytd


def calculate_tier_stats(skus):
    """Calculate tier counts and sales percentages."""
    tier_counts = {'A': 0, 'B': 0, 'C': 0}
    tier_sales = {'A': 0.0, 'B': 0.0, 'C': 0.0}
    
    total_sales = 0.0
    for s in skus:
        tier = s.get('tier', 'C')
        sales = float(s.get('sales_dollars_ytd', 0) or 0)
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        tier_sales[tier] = tier_sales.get(tier, 0.0) + sales
        total_sales += sales
    
    # Calculate percentages
    tier_a_pct = (tier_sales['A'] / total_sales * 100) if total_sales > 0 else 0
    tier_b_pct = (tier_sales['B'] / total_sales * 100) if total_sales > 0 else 0
    tier_ab_pct = tier_a_pct + tier_b_pct
    
    return {
        'tier_a_count': tier_counts['A'],
        'tier_b_count': tier_counts['B'],
        'tier_c_count': tier_counts['C'],
        'tier_ab_count': tier_counts['A'] + tier_counts['B'],
        'tier_a_sales_pct': tier_a_pct,
        'tier_b_sales_pct': tier_b_pct,
        'tier_ab_sales_pct': tier_ab_pct,
    }


def build_sku_js_array(skus):
    """Build JavaScript array for SKU data."""
    total_sales_ytd, total_inv_ytd = compute_totals(skus)

    js_rows = []
    for s in skus:
        sales_ytd = float(s.get("sales_dollars_ytd", 0) or 0)
        inv_ytd = float(s.get("inventory_dollars_lw", 0) or 0)
        pct_sales = round((sales_ytd / total_sales_ytd) * 100, 1)
        pct_inv = round((inv_ytd / total_inv_ytd) * 100, 1)

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
# Action items and seasonal risk
# -----------------------------------------------------------------------------

def load_action_items():
    """Load action items from JSON."""
    if not ACTION_ITEMS_FILE.exists():
        return []
    
    try:
        with ACTION_ITEMS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("actions", [])
    except Exception as e:
        print(f"⚠️  Could not load action items: {e}")
        return []


def load_seasonal_risk():
    """Load seasonal risk items from JSON."""
    if not SEASONAL_RISK_FILE.exists():
        return []
    
    try:
        with SEASONAL_RISK_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # Handle both formats
        if isinstance(data, list):
            return data
        return data.get("items", [])
    except Exception as e:
        print(f"⚠️  Could not load seasonal risk: {e}")
        return []


def build_action_items_js(actions):
    """Build JavaScript variable for action items."""
    if not actions:
        return "const historicalData = { actions: [] };"
    
    # Convert to JSON and embed in JS
    json_str = json.dumps(actions, indent=2)
    return f"const historicalData = {{ actions: {json_str} }};"


# -----------------------------------------------------------------------------
# Weekly summary and metrics
# -----------------------------------------------------------------------------

def _derive_week_label_from_meta() -> str:
    """Derive week label from meta.json."""
    if not META_FILE.exists():
        return "Latest Week"

    try:
        with META_FILE.open("r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception:
        return "Latest Week"

    pos_file = None
    if isinstance(meta, dict):
        src = meta.get("source_files") or {}
        pos_file = src.get("pos_file")

    if not pos_file or not isinstance(pos_file, str):
        return "Latest Week"

    m = re.search(r"WK(\d+)", pos_file, re.IGNORECASE)
    if not m:
        return "Latest Week"
    week_num = int(m.group(1))
    return f"Week {week_num}"


def load_weekly_metrics() -> dict:
    """Load weekly metrics from weekly_sales_summary.json."""
    if not WEEKLY_SUMMARY_FILE.exists():
        raise FileNotFoundError(f"Cannot find {WEEKLY_SUMMARY_FILE}")

    with WEEKLY_SUMMARY_FILE.open("r", encoding="utf-8") as f:
        summary = json.load(f)

    def _to_float(x):
        try:
            return float(x)
        except Exception:
            return 0.0

    sales_dollars = _to_float(summary.get("sales_dollars_lw"))
    sales_units = _to_float(summary.get("sales_units_lw"))
    inv_units = _to_float(summary.get("inventory_units_lw"))
    inv_dollars = _to_float(summary.get("inventory_dollars_lw"))
    wos = _to_float(summary.get("wos"))

    units_delta = _to_float(summary.get("units_delta"))
    dollars_delta = _to_float(summary.get("dollars_delta"))
    units_pct_delta = _to_float(summary.get("units_pct_delta"))
    dollars_pct_delta = _to_float(summary.get("dollars_pct_delta"))

    # Sell-through
    sell_thru_pct = 0.0
    denom = sales_units + inv_units
    if denom > 0:
        sell_thru_pct = (sales_units / denom) * 100.0

    change_class = "positive" if dollars_pct_delta >= 0 else "negative"
    week_label = _derive_week_label_from_meta()

    return {
        "week_label": week_label,
        "sales_dollars": sales_dollars,
        "sales_units": sales_units,
        "inv_units": inv_units,
        "inv_dollars": inv_dollars,
        "wos": wos,
        "sell_thru_pct": sell_thru_pct,
        "units_delta": units_delta,
        "dollars_delta": dollars_delta,
        "units_pct_delta": units_pct_delta,
        "dollars_pct_delta": dollars_pct_delta,
        "change_class": change_class,
    }


def inject_weekly_metrics(html: str, m: dict, tier_stats: dict, action_count: int, seasonal_count: int) -> str:
    """Replace tokens in HTML with formatted metrics."""
    replacements = {
        # Week labels
        "[[LATEST_WEEK_LABEL]]": m["week_label"],
        "[[CURRENT_ANALYSIS_LABEL]]": f"{m['week_label']} – Total Walmart POS",

        # Sales and inventory
        "[[WEEKLY_SALES_DOLLARS]]": f"${m['sales_dollars']:,.0f}",
        "[[WEEKLY_SALES_UNITS]]": f"{m['sales_units']:,.0f}",
        "[[WEEKLY_INVENTORY_UNITS]]": f"{m['inv_units']:,.0f}",
        "[[WEEKLY_INVENTORY_DOLLARS]]": f"${m['inv_dollars']:,.0f}",
        "[[WEEKLY_WOS]]": f"{m['wos']:.1f}",
        "[[WEEKLY_SELLTHRU]]": f"{m['sell_thru_pct']:.1f}",
        "[[WEEKLY_UNITS_DELTA]]": f"{m['units_delta']:,.0f}",
        "[[WEEKLY_DOLLARS_DELTA]]": f"{m['dollars_delta']:,.0f}",
        "[[WEEKLY_UNITS_PCT_DELTA]]": f"{m['units_pct_delta']:.1f}%",
        "[[WEEKLY_DOLLARS_PCT_DELTA]]": f"{m['dollars_pct_delta']:.1f}%",

        # Tier counts
        "[[TIER_A_COUNT]]": str(tier_stats['tier_a_count']),
        "[[TIER_B_COUNT]]": str(tier_stats['tier_b_count']),
        "[[TIER_C_COUNT]]": str(tier_stats['tier_c_count']),
        "[[TIER_AB_COUNT]]": str(tier_stats['tier_ab_count']),
        "[[TIER_AB_SALES_PCT]]": f"{tier_stats['tier_ab_sales_pct']:.1f}%",

        # Action items and seasonal risk
        "[[ACTION_ITEMS_COUNT]]": str(action_count),
        "[[SEASONAL_RISK_COUNT]]": str(seasonal_count),
    }

    for token, val in replacements.items():
        if token in html:
            html = html.replace(token, val)

    # Change class
    html = html.replace("[[WEEKLY_DOLLARS_CHANGE_CLASS]]", m.get("change_class", ""))

    return html


def inject_tab2_insights(html: str) -> str:
    """Insert Tab 2 insights HTML."""
    placeholder = "[[TAB2_INSIGHTS_HTML]]"
    if placeholder not in html:
        return html

    if not TAB2_INSIGHTS_FILE.exists():
        return html

    try:
        snippet = TAB2_INSIGHTS_FILE.read_text(encoding="utf-8")
    except Exception:
        return html

    return html.replace(placeholder, snippet)


# -----------------------------------------------------------------------------
# HTML replacement
# -----------------------------------------------------------------------------

def replace_sku_block(html: str, new_block: str) -> str:
    """Replace const skuData = [...] block."""
    pattern = re.compile(r"const\s+skuData\s*=\s*\[[\s\S]*?\];", re.MULTILINE)
    if not pattern.search(html):
        raise ValueError("Could not find existing const skuData = [...] block.")
    return pattern.sub(new_block, html, count=1)


def inject_action_items_block(html: str, action_js: str) -> str:
    """
    Inject or replace historicalData.actions JavaScript variable.
    Looks for existing historicalData declaration and replaces it,
    or inserts before closing </script> tag in the main script block.
    """
    # Try to find and replace existing historicalData
    pattern = re.compile(r"const\s+historicalData\s*=\s*\{[\s\S]*?\};", re.MULTILINE)
    if pattern.search(html):
        return pattern.sub(action_js, html, count=1)
    
    # If not found, insert before closing script tag
    # Find the script block that contains skuData
    script_pattern = re.compile(r"(<script[^>]*>)([\s\S]*?const\s+skuData[\s\S]*?)(</script>)", re.MULTILINE)
    match = script_pattern.search(html)
    if match:
        before = match.group(1)
        content = match.group(2)
        after = match.group(3)
        new_content = content + "\n\n// Action items data\n" + action_js + "\n"
        return html.replace(match.group(0), before + new_content + after)
    
    # Fallback: just append to end of HTML (not ideal but safe)
    return html + f"\n<script>\n{action_js}\n</script>\n"


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

def main():
    print("=" * 100)
    print("DICKIES DASHBOARD HTML UPDATER v5")
    print("=" * 100)

    # Load SKUs
    week, skus = load_sku_data()
    print(f"✅ Loaded Week {week}, {len(skus)} SKUs from sku_master.json")

    # Calculate tier stats
    tier_stats = calculate_tier_stats(skus)
    print(f"✅ Tier distribution: A={tier_stats['tier_a_count']}, B={tier_stats['tier_b_count']}, C={tier_stats['tier_c_count']}")
    print(f"   A+B SKUs: {tier_stats['tier_ab_count']} ({tier_stats['tier_ab_sales_pct']:.1f}% of sales)")

    # Build SKU JS array
    new_sku_block = build_sku_js_array(skus)
    print("✅ Built new skuData block")

    # Load action items
    actions = load_action_items()
    print(f"✅ Loaded {len(actions)} action items")

    # Load seasonal risk
    seasonal_risk = load_seasonal_risk()
    print(f"✅ Loaded {len(seasonal_risk)} seasonal risk items")

    # Build action items JS
    action_js = build_action_items_js(actions)

    # Read current HTML
    html_text = HTML_PATH.read_text(encoding="utf-8")

    # Backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"index_week{week:02d}_{timestamp}.v5_backup.html"
    backup_path.write_text(html_text, encoding="utf-8")
    print(f"💾 Backup saved → {backup_path}")

    # 1) Replace SKU block
    updated_html = replace_sku_block(html_text, new_sku_block)

    # 2) Inject action items
    updated_html = inject_action_items_block(updated_html, action_js)
    print("✅ Injected action items JavaScript")

    # 3) Inject weekly metrics and tier tokens
    try:
        weekly = load_weekly_metrics()
        updated_html = inject_weekly_metrics(updated_html, weekly, tier_stats, len(actions), len(seasonal_risk))
        print("✅ Injected weekly metrics and tier tokens")
    except Exception as e:
        print(f"⚠️  Could not inject weekly metrics: {e}")

    # 4) Inject Tab 2 insights
    updated_html = inject_tab2_insights(updated_html)
    if "[[TAB2_INSIGHTS_HTML]]" not in updated_html:
        print("✅ Injected Tab 2 insights")
    else:
        print("ℹ️  No Tab 2 insights injected (token left in HTML)")

    # Write final HTML
    HTML_PATH.write_text(updated_html, encoding="utf-8")

    print("✅ Updated", HTML_PATH)
    print("=" * 100)
    print("SUMMARY:")
    print(f"  • Week: {week}")
    print(f"  • SKUs: {len(skus)}")
    print(f"  • Tiers: A={tier_stats['tier_a_count']}, B={tier_stats['tier_b_count']}, C={tier_stats['tier_c_count']}")
    print(f"  • Actions: {len(actions)}")
    print(f"  • Seasonal Risk: {len(seasonal_risk)}")
    print("=" * 100)
    print("Hard refresh your browser (Ctrl + F5) to see updated data.")
    print("=" * 100)


if __name__ == "__main__":
    main()
