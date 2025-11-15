"""
Dickies Dashboard - v5
Comprehensive ETL pipeline for Walmart Dickies performance dashboard.

- Ingests weekly POS, ladder, and velocity files
- Builds normalized JSON artifacts for the web dashboard
- Calculates:
    - SKU master view
    - Fineline rollups
    - Weekly sales summary
    - Seasonal risk flags
    - Action items (via external generator)
    - Meta metrics

Version: 5.0
"""

import os
import json
import math
import traceback
from datetime import datetime
from typing import Dict, List, Any

import pandas as pd
import numpy as np


class DickiesDashboardETL:
    def __init__(self, pos_file: str, ladder_file: str, velocity_file: str, output_dir: str):
        self.pos_file = pos_file
        self.ladder_file = ladder_file
        self.velocity_file = velocity_file
        self.output_dir = output_dir

        self.pos_lw = None          # Last-week POS (store-level)
        self.pos_ytd = None         # YTD POS (store-level)
        self.ladder = None          # Style ladder (item-level)
        self.velocity = None        # Velocity / seasonal curves

        self.sku_master: List[Dict[str, Any]] = []
        self.fineline_rollup: List[Dict[str, Any]] = []
        self.weekly_summary: Dict[str, Any] = {}
        self.seasonal_risk: List[Dict[str, Any]] = []
        self.action_items: List[Dict[str, Any]] = []
        self.meta: Dict[str, Any] = {}

        self.metrics: Dict[str, Any] = {}
        self.tier_assignments = {
            'A': set(),
            'B': set(),
            'C': set()
        }

    # ---------------------------------------------
    # Utility helpers
    # ---------------------------------------------
    def _ensure_output_dir(self):
        os.makedirs(self.output_dir, exist_ok=True)

    @staticmethod
    def _safe_float(x, default=0.0):
        try:
            if pd.isna(x):
                return default
            return float(x)
        except Exception:
            return default

    @staticmethod
    def _safe_int(x, default=0):
        try:
            if pd.isna(x):
                return default
            return int(x)
        except Exception:
            return default

    # ---------------------------------------------
    # Loaders
    # ---------------------------------------------
    def load_pos_data(self):
        """
        Load POS YTD data and locate the real table header dynamically.

        Strategy:
        - Scan all sheets in the POS workbook
        - For each sheet, look for a row containing "WD Style/Color"
        - Use that row as the header
        - Pick the first table that has both:
            * "WD Style/Color"
            * "Sales Retail $ 2025YTD"
        """
        print("📥 Loading POS data...")

        import numpy as np
        import pandas as pd

        xls = pd.ExcelFile(self.pos_file)
        target_style_col = "WD Style/Color"
        target_sales_col = "Sales Retail $ 2025YTD"

        pos_ytd_df = None
        chosen_sheet = None
        chosen_header_row = None

        # Examine each sheet in the workbook
        for sheet_name in xls.sheet_names:
            tmp = xls.parse(sheet_name, header=None)

            # Look for a row that contains "WD Style/Color"
            header_row_indices = np.where(tmp.eq(target_style_col).any(axis=1))[0]

            if len(header_row_indices) == 0:
                continue  # no header in this sheet — skip

            # For each possible header row, try treating it as the table header
            for header_row in header_row_indices:
                df = xls.parse(sheet_name, header=header_row)
                df.columns = [str(c).strip() for c in df.columns]

                # Check if the expected columns exist in this header
                if target_style_col in df.columns and target_sales_col in df.columns:
                    df = df[df[target_style_col].notna()].copy()  # remove blank rows

                    if len(df) == 0:
                        continue

                    pos_ytd_df = df
                    chosen_sheet = sheet_name
                    chosen_header_row = header_row
                    break

            if pos_ytd_df is not None:
                break

        if pos_ytd_df is None:
            raise ValueError(
                "❌ Could not locate POS YTD table with both "
                f"'{target_style_col}' and '{target_sales_col}' in any sheet.\n"
                f"Sheets scanned: {xls.sheet_names}"
            )

        # Normalize header names one more time
        pos_ytd_df.columns = [str(c).strip() for c in pos_ytd_df.columns]

        # Store clean dataframe
        self.pos_ytd_df = pos_ytd_df.reset_index(drop=True)

        print(f"   POS YTD loaded from sheet '{chosen_sheet}' (header row {chosen_header_row})")
        print(f"   POS rows loaded: {len(self.pos_ytd_df)}")

        def load_ladder_data(self):        """
        Load the Velocity Trends workbook.

        This version does NOT depend on self.pos_lw.
        It simply loads velocity_raw from the file directly.
        """
        print("📥 Loading Velocity data...")

        try:
            # Try best-known sheet name
            try:
                df = pd.read_excel(self.velocity_file, sheet_name="Velocity Detail")
            except Exception:
                # Fallback to first sheet
                df = pd.read_excel(self.velocity_file, sheet_name=0)

            print(f"   Velocity rows loaded: {len(df)}")

            # store raw velocity
            self.velocity_raw = df

        except Exception as e:
            print(f"   ⚠️ Could not load velocity data ({e}). Continuing without it.")
            self.velocity_raw = None

        def load_velocity_data(self):
            """
            TEMP STUB:
            We are parking velocity integration for now so the ETL file
            does not crash. This function intentionally does nothing.
            """
            print("\n⚠️ Skipping velocity data load (temporary stub).")
            self.velocity = None

    # ---------------------------------------------
    # Tier logic (A/B/C)
    # ---------------------------------------------
     def calculate_tiers(self):
        """
        TEMP STUB:
        Use existing tier fields in sku_master.json for now.
        Full recalculation logic will be rebuilt cleanly later.
        """
        print("\n⚠️ Skipping tier recalculation (temporary stub).")
        # If metrics dict exists, leave it as-is. Otherwise, just set zeros.
        if not hasattr(self, "metrics"):
            self.metrics = {}
        self.metrics.setdefault("tier_a_count", 0)
        self.metrics.setdefault("tier_b_count", 0)
        self.metrics.setdefault("tier_c_count", 0)
   # ---------------------------------------------
    # SKU Master builder
    # ---------------------------------------------
    def build_sku_master(self):
        """
        Build SKU Master JSON for the dashboard.

        Key additions in v5:
        - For each SKU, we add:
            * sales_pct_of_total: share of total YTD sales dollars
            * cumulative_sales_pct: cumulative share when sorted by sales descending
            * inventory_pct_of_total: share of total LW inventory dollars
        """
        print("📊 Building SKU Master...")

        if self.pos_lw is None or self.ladder is None:
            raise RuntimeError("POS LW and Ladder data must be loaded before building SKU master.")

        # Aggregate YTD sales dollars at SKU key level to join into the LW frame
        ytd = self.pos_ytd.groupby(['WD Style/Color'], as_index=False)[
            'Sales Retail $ 2025YTD'
        ].sum().rename(columns={'Sales Retail $ 2025YTD': 'sales_dollars_ytd'})

        # Aggregate YTD units similarly
        ytd_units = self.pos_ytd.groupby(['WD Style/Color'], as_index=False)[
            'Sales Units 2025YTD'
        ].sum().rename(columns={'Sales Units 2025YTD': 'sales_units_ytd'})

        # Last-week aggregation at SKU level from store-level POS
        lw_group = self.pos_lw.groupby(['WD Style/Color'], as_index=False).agg({
            'Sales Units LW': 'sum',
            'Sales Units LWLY': 'sum',
            'Sales Retail $ LW': 'sum',
            'Sales Retail $ LWLY': 'sum',
            'Store On Hand Units LW': 'sum',
            'Store On Hand Retail LW': 'sum'
        }).rename(columns={
            'Sales Units LW': 'sales_units_lw',
            'Sales Units LWLY': 'sales_units_lwly',
            'Sales Retail $ LW': 'sales_dollars_lw',
            'Sales Retail $ LWLY': 'sales_dollars_lwly',
            'Store On Hand Units LW': 'inventory_units_lw',
            'Store On Hand Retail LW': 'inventory_dollars_lw'
        })

        # Merge YTD and LW
        sku_df = lw_group.merge(ytd, on='WD Style/Color', how='left')
        sku_df = sku_df.merge(ytd_units, on='WD Style/Color', how='left')

        # Join ladder attributes
        ladder_cols = [
            'WD Style/Color',
            'Fineline',
            'Item Description',
            'Color',
            'Gender',
            'Category',
            'Sub Category',
            'AUR TY',
            'AUR LY'
        ]
        ladder_subset = self.ladder[[c for c in ladder_cols if c in self.ladder.columns]].copy()
        sku_df = sku_df.merge(ladder_subset, on='WD Style/Color', how='left')

        # Attach tier info from tier_assignments (calculated from YTD sales)
        def _lookup_tier(sku):
            if sku in self.tier_assignments['A']:
                return 'A'
            if sku in self.tier_assignments['B']:
                return 'B'
            if sku in self.tier_assignments['C']:
                return 'C'
            return 'C'  # default safety

        sku_df['tier'] = sku_df['WD Style/Color'].apply(_lookup_tier)

        sku_master: List[Dict[str, Any]] = []

        # Pre-calc total sales & inventory dollars to later compute shares
        total_sales_ytd = sku_df['sales_dollars_ytd'].fillna(0).sum()
        total_inventory_lw = sku_df['inventory_dollars_lw'].fillna(0).sum()

        # Avoid division by zero
        total_sales_ytd = float(total_sales_ytd) if total_sales_ytd and not math.isnan(total_sales_ytd) else 0.0
        total_inventory_lw = float(total_inventory_lw) if total_inventory_lw and not math.isnan(total_inventory_lw) else 0.0

        # We'll also compute cumulative sales pct over descending YTD sales
        sku_df = sku_df.sort_values(by='sales_dollars_ytd', ascending=False).reset_index(drop=True)

        cumulative_sales = 0.0

        for _, row in sku_df.iterrows():
            sku = row['WD Style/Color']

            sales_dollars_ytd = self._safe_float(row.get('sales_dollars_ytd', 0.0))
            sales_units_ytd = self._safe_float(row.get('sales_units_ytd', 0.0))

            sales_units_lw = self._safe_float(row.get('sales_units_lw', 0.0))
            sales_units_lwly = self._safe_float(row.get('sales_units_lwly', 0.0))
            sales_dollars_lw = self._safe_float(row.get('sales_dollars_lw', 0.0))
            sales_dollars_lwly = self._safe_float(row.get('sales_dollars_lwly', 0.0))
            inventory_units_lw = self._safe_float(row.get('inventory_units_lw', 0.0))
            inventory_dollars_lw = self._safe_float(row.get('inventory_dollars_lw', 0.0))

            # Sell-through, unit and dollar changes likely already provided at store level
            # but we can read them directly if present (for now we default to 0 if missing).
            sell_through_ty = self._safe_float(row.get('ST TY', 0.0))
            sell_through_ly = self._safe_float(row.get('ST LY', 0.0))
            st_change = self._safe_float(row.get('% Change in ST', 0.0))
            unit_pct_change = self._safe_float(row.get('% Unit Diff', 0.0))
            dollar_pct_change = self._safe_float(row.get('% $ Diff', 0.0))

            # WOS based on LW inventory and LW sales units
            if sales_units_lw > 0:
                wos = inventory_units_lw / max(sales_units_lw, 0.0001)
            else:
                wos = 0.0

            # Per-SKU sales share and cumulative share (Pareto)
            if total_sales_ytd > 0 and sales_dollars_ytd > 0:
                share = sales_dollars_ytd / total_sales_ytd
            else:
                share = 0.0

            cumulative_sales += sales_dollars_ytd
            cumulative_share = cumulative_sales / total_sales_ytd if total_sales_ytd > 0 else 0.0

            # Inventory share
            if total_inventory_lw > 0 and inventory_dollars_lw > 0:
                inv_share = inventory_dollars_lw / total_inventory_lw
            else:
                inv_share = 0.0

            record = {
                # Identity
                'sku': sku,
                'fineline': row.get('Fineline', ''),
                'description': row.get('Item Description', ''),
                'color': row.get('Color', ''),
                'gender': row.get('Gender', ''),
                'category': row.get('Category', ''),
                'sub_category': row.get('Sub Category', ''),

                # Price
                'aur_ty': self._safe_float(row.get('AUR TY', 0.0)),
                'aur_ly': self._safe_float(row.get('AUR LY', 0.0)),

                # YTD metrics
                'sales_units_ytd': sales_units_ytd,
                'sales_dollars_ytd': sales_dollars_ytd,

                # Weekly LW metrics
                'sales_units_lw': sales_units_lw,
                'sales_units_lwly': sales_units_lwly,
                'sales_dollars_lw': sales_dollars_lw,
                'sales_dollars_lwly': sales_dollars_lwly,
                'inventory_units_lw': inventory_units_lw,
                'inventory_dollars_lw': inventory_dollars_lw,

                # Performance
                'sell_through_ty': sell_through_ty,
                'sell_through_ly': sell_through_ly,
                'st_change': st_change,
                'unit_pct_change': unit_pct_change,
                'dollar_pct_change': dollar_pct_change,

                'wos': round(wos, 1),
                'tier': row.get('tier', 'C'),

                # New v5 fields (shares)
                'sales_pct_of_total': round(share, 6),
                'cumulative_sales_pct': round(cumulative_share, 6),
                'inventory_pct_of_total': round(inv_share, 6),
            }

            sku_master.append(record)

        self.sku_master = sku_master

        print(f"   SKU Master built: {len(sku_master):,} SKUs")

    # ---------------------------------------------
    # Fineline Rollup
    # ---------------------------------------------
    def build_fineline_rollup(self):
        """
        Roll up by fineline using the POS LW/YTD data.
        """
        print("📊 Building Fineline Rollup...")

        df = self.pos_lw.copy()
        df.columns = [str(c).strip() for c in df.columns]

        required_cols = [
            'Fineline',
            'Sales Units LW',
            'Sales Units LWLY',
            'Sales Retail $ LW',
            'Sales Retail $ LWLY',
            'Store On Hand Units LW',
            'Store On Hand Retail LW',
            'Sales Units 2025YTD',
            'Sales Retail $ 2025YTD'
        ]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required fineline column: {col}")

        grouped = df.groupby('Fineline', as_index=False).agg({
            'Sales Units LW': 'sum',
            'Sales Units LWLY': 'sum',
            'Sales Retail $ LW': 'sum',
            'Sales Retail $ LWLY': 'sum',
            'Store On Hand Units LW': 'sum',
            'Store On Hand Retail LW': 'sum',
            'Sales Units 2025YTD': 'sum',
            'Sales Retail $ 2025YTD': 'sum'
        })

        fineline_rows: List[Dict[str, Any]] = []

        for _, row in grouped.iterrows():
            sales_units_lw = self._safe_float(row['Sales Units LW'])
            sales_units_lwly = self._safe_float(row['Sales Units LWLY'])
            sales_dollars_lw = self._safe_float(row['Sales Retail $ LW'])
            sales_dollars_lwly = self._safe_float(row['Sales Retail $ LWLY'])
            inventory_units_lw = self._safe_float(row['Store On Hand Units LW'])
            inventory_dollars_lw = self._safe_float(row['Store On Hand Retail LW'])
            sales_units_ytd = self._safe_float(row['Sales Units 2025YTD'])
            sales_dollars_ytd = self._safe_float(row['Sales Retail $ 2025YTD'])

            if sales_units_lw > 0:
                wos = inventory_units_lw / max(sales_units_lw, 0.0001)
            else:
                wos = 0.0

            # Compute sell-through using standard formula if we have receipts (not included here)
            # For now we default ST metrics to None at fineline level in this function.
            record = {
                'fineline': row['Fineline'],
                'sales_units_lw': sales_units_lw,
                'sales_units_lwly': sales_units_lwly,
                'sales_dollars_lw': sales_dollars_lw,
                'sales_dollars_lwly': sales_dollars_lwly,
                'inventory_units_lw': inventory_units_lw,
                'inventory_dollars_lw': inventory_dollars_lw,
                'sales_units_ytd': sales_units_ytd,
                'sales_dollars_ytd': sales_dollars_ytd,
                'wos': round(wos, 1),
            }

            fineline_rows.append(record)

        self.fineline_rollup = fineline_rows

        print(f"   Finelines rolled up: {len(fineline_rows):,}")

    # ---------------------------------------------
    # Weekly Sales Summary
    # ---------------------------------------------
    def build_weekly_sales_summary(self):
        """
        Build top-line weekly sales summary and performance metrics.
        """
        print("📊 Building Weekly Sales Summary...")

        df = self.pos_lw.copy()

        total_sales_units_lw = self._safe_float(df['Sales Units LW'].sum())
        total_sales_units_lwly = self._safe_float(df['Sales Units LWLY'].sum())
        total_sales_dollars_lw = self._safe_float(df['Sales Retail $ LW'].sum())
        total_sales_dollars_lwly = self._safe_float(df['Sales Retail $ LWLY'].sum())
        total_inventory_units_lw = self._safe_float(df['Store On Hand Units LW'].sum())
        total_inventory_dollars_lw = self._safe_float(df['Store On Hand Retail LW'].sum())

        # Simple YoY deltas
        units_delta = total_sales_units_lw - total_sales_units_lwly
        dollars_delta = total_sales_dollars_lw - total_sales_dollars_lwly

        units_pct_delta = (units_delta / total_sales_units_lwly * 100.0) if total_sales_units_lwly > 0 else 0.0
        dollars_pct_delta = (dollars_delta / total_sales_dollars_lwly * 100.0) if total_sales_dollars_lwly > 0 else 0.0

        # WOS at total level
        if total_sales_units_lw > 0:
            wos = total_inventory_units_lw / max(total_sales_units_lw, 0.0001)
        else:
            wos = 0.0

        summary = {
            'sales_units_lw': total_sales_units_lw,
            'sales_units_lwly': total_sales_units_lwly,
            'sales_dollars_lw': total_sales_dollars_lw,
            'sales_dollars_lwly': total_sales_dollars_lwly,
            'inventory_units_lw': total_inventory_units_lw,
            'inventory_dollars_lw': total_inventory_dollars_lw,
            'units_delta': units_delta,
            'dollars_delta': dollars_delta,
            'units_pct_delta': units_pct_delta,
            'dollars_pct_delta': dollars_pct_delta,
            'wos': wos,
        }

        self.weekly_summary = summary
        print("   Weekly summary built.")

    # ---------------------------------------------
    # Seasonal Risk & Action Items (via external generator)
    # ---------------------------------------------
    def load_seasonal_risk_and_actions(self):
        """
        Loads seasonal_risk.json and action_items.json if present.
        (They are generated by etl_action_generator.py)
        """
        print("📥 Loading Seasonal Risk & Action Items JSON...")
        seasonal_risk_path = os.path.join(self.output_dir, "seasonal_risk.json")
        action_items_path = os.path.join(self.output_dir, "action_items.json")

        if os.path.exists(seasonal_risk_path):
            with open(seasonal_risk_path, "r") as f:
                self.seasonal_risk = json.load(f)
            print(f"   Seasonal risk items: {len(self.seasonal_risk)}")
        else:
            print("   ⚠️ seasonal_risk.json not found; skipping.")

        if os.path.exists(action_items_path):
            with open(action_items_path, "r") as f:
                self.action_items = json.load(f)
            print(f"   Action items: {len(self.action_items)}")
        else:
            print("   ⚠️ action_items.json not found; skipping.")

    # ---------------------------------------------
    # Meta builder (summary metrics for dashboard)
    # ---------------------------------------------
    def calculate_summary_metrics(self):
        """
        Build summary metrics stored in meta.json
        """
        print("📊 Calculating summary metrics (meta)...")

        # Tier counts from tier_assignments
        tier_a_count = len(self.tier_assignments['A'])
        tier_b_count = len(self.tier_assignments['B'])
        tier_c_count = len(self.tier_assignments['C'])

        # Compute avg WOS from SKU master if available
        avg_wos = 0.0
        if self.sku_master:
            wos_vals = [self._safe_float(x.get('wos', 0.0)) for x in self.sku_master]
            if wos_vals:
                avg_wos = float(np.mean(wos_vals))

        self.metrics.update({
            'tier_a_count': tier_a_count,
            'tier_b_count': tier_b_count,
            'tier_c_count': tier_c_count,
            'avg_wos': avg_wos,
        })

    def build_meta(self):
        """
        Build meta.json with metadata, metrics, and configuration.
        """
        print("📊 Building Meta JSON...")
        self.calculate_summary_metrics()

        meta = {
            'generated_at': datetime.utcnow().isoformat() + "Z",
            'source_files': {
                'pos_file': os.path.basename(self.pos_file),
                'ladder_file': os.path.basename(self.ladder_file),
                'velocity_file': os.path.basename(self.velocity_file),
            },
            'metrics': self.metrics,
        }

        self.meta = meta

    # ---------------------------------------------
    # Save helpers
    # ---------------------------------------------
    def _save_json(self, name: str, obj: Any):
        path = os.path.join(self.output_dir, name)
        with open(path, "w") as f:
            json.dump(obj, f, indent=2)
        print(f"💾 Saved {name} -> {path}")

    # ---------------------------------------------
    # Run pipeline
    # ---------------------------------------------
    def run(self) -> bool:
        """
        Execute full ETL pipeline and save artifacts.
        """
        try:
            self._ensure_output_dir()

            # 1) Load all inputs
        self.load_pos_data()
        self.load_ladder_data()
        # TEMP: Skip velocity + tier recompute until we rebuild cleanly
        # self.load_velocity_data()
        # self.calculate_tiers()


            # 2) Core logic
            self.build_sku_master()
            self.build_fineline_rollup()
            self.build_weekly_sales_summary()

            # 3) Load seasonal risk + actions if they exist (from separate generator)
            self.load_seasonal_risk_and_actions()

            # 4) Build meta
            self.build_meta()

            # 5) Save artifacts
            self._save_json("sku_master.json", self.sku_master)
            self._save_json("fineline_rollup.json", self.fineline_rollup)
            self._save_json("weekly_sales_summary.json", self.weekly_summary)
            self._save_json("seasonal_risk.json", self.seasonal_risk)
            self._save_json("action_items.json", self.action_items)
            self._save_json("meta.json", self.meta)

            print("\n✅ All artifacts saved successfully.")
            print(f"   Output directory: {self.output_dir}")
            print(f"   Tier counts: A={self.metrics.get('tier_a_count')}, "
                  f"B={self.metrics.get('tier_b_count')}, "
                  f"C={self.metrics.get('tier_c_count')}")
            print(f"   Avg WOS: {self.metrics.get('avg_wos', 0):.1f}")
            print(f"   Seasonal Risk Items: {len(self.seasonal_risk)}")
            print("=" * 100)

            return True

        except Exception as e:
            print(f"\n❌ ETL FAILED: {e}")
            traceback.print_exc()
            return False


if __name__ == '__main__':
    POS_FILE = '/home/ubuntu/dickies_data/weekly_uploads/FYE2026_WM_STORES_WMWK40.xlsx'
    LADDER_FILE = '/home/ubuntu/dickies_data/weekly_uploads/WK202540 WM Ladder - WM 11.11.25.xlsb'
    VELOCITY_FILE = '/home/ubuntu/dickies_data/weekly_uploads/Genuine Dickies Velocity Trends_Modular.xlsx'
    OUTPUT_DIR = '/home/ubuntu/dickies_output/weekly_artifacts'

    etl = DickiesDashboardETL(POS_FILE, LADDER_FILE, VELOCITY_FILE, OUTPUT_DIR)
    success = etl.run()
    exit(0 if success else 1)
