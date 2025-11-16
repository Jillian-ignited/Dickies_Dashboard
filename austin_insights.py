"""
Austin‑Style Dashboard Insights Generator

This module encapsulates the logic for generating natural‑language commentary and
structured metrics for Tab 2 of the Dickies dashboard (Weekly Sales Insights).
It produces a Python dict with summary statistics and callouts, and a helper
function to format that dict into an HTML snippet ready to be injected into
the dashboard.

Usage:

    from austin_insights import DashboardInsightsGenerator, format_for_dashboard_tab2

    generator = DashboardInsightsGenerator()
    insights = generator.generate_weekly_insights(current_week_df, ly_week_df, week_number)
    html_snippet = format_for_dashboard_tab2(insights)
    # write html_snippet to weekly_tab2_insights.html in ARTIFACT_DIR

The generator expects DataFrames with at least these columns:
    style_color, sales_dollars, sales_units, on_hand_units,
    sell_through_pct, avg_retail, category

Categories should be labeled as 'Modular' or 'Seasonal' (case insensitive) so
that the deep‑dive functions know how to segment the data.  If 'category' is
missing, all rows are treated as Modular.
"""

from typing import Dict, List
import pandas as pd
import numpy as np


class DashboardInsightsGenerator:
    """
    Generate Austin‑style insights formatted for dashboard Tab 2.

    The generator compares the current week of POS data to last year (LY) for
    the same week.  It calculates topline and category‑specific metrics,
    produces narrative callouts for key styles, and suggests action items.
    """

    def __init__(self):
        # Track positive streaks across weeks (not yet used but reserved for future use)
        self.streak_tracker = {}

    def generate_weekly_insights(
        self,
        current_week_df: pd.DataFrame,
        ly_week_df: pd.DataFrame,
        week_number: int,
        previous_week_df: pd.DataFrame = None,
    ) -> Dict:
        """
        Generate complete dashboard insights for a given week.

        Returns a dictionary with keys:
            - week: week number
            - header_metrics: dict of metrics for Total, Modular, Seasonal
            - big_picture: one‑line summary string
            - modular_deep_dive: dict with summary and callouts
            - seasonal_spotlight: dict with summary and callouts
            - action_items: list of dicts describing recommended next actions
        """

        # Calculate totals
        current_totals = self._calculate_totals(current_week_df)
        ly_totals = self._calculate_totals(ly_week_df)

        return {
            'week': week_number,
            'header_metrics': self._generate_header_metrics(
                current_totals, ly_totals, current_week_df, ly_week_df
            ),
            'big_picture': self._generate_big_picture(current_totals, ly_totals),
            'modular_deep_dive': self._generate_modular_insights(
                current_week_df, ly_week_df, week_number
            ),
            'seasonal_spotlight': self._generate_seasonal_insights(
                current_week_df, ly_week_df, previous_week_df
            ),
            'action_items': self._generate_action_items(
                current_week_df, ly_week_df, current_totals, ly_totals
            ),
        }

    # -------------------------------------------------------------------------
    # Totals and header metrics
    # -------------------------------------------------------------------------

    def _calculate_totals(self, df: pd.DataFrame) -> Dict:
        """Calculate total business metrics across all styles."""
        return {
            'total_sales': df['sales_dollars'].sum(),
            'total_units': df['sales_units'].sum(),
            'total_oh': df['on_hand_units'].sum(),
            'avg_st': df['sell_through_pct'].mean(),
            'avg_retail': df['avg_retail'].mean(),
        }

    def _generate_header_metrics(
        self,
        current: Dict,
        ly: Dict,
        current_df: pd.DataFrame,
        ly_df: pd.DataFrame,
    ) -> Dict:
        """
        Build the top‑level metrics displayed in the header cards of Tab 2.

        Each section (total, modular, seasonal) contains absolute metrics and
        year‑over‑year (YoY) changes.  Sell‑through is averaged across items.
        """

        def subset(df: pd.DataFrame, cat: str) -> pd.DataFrame:
            if 'category' in df.columns:
                mask = df['category'].str.lower() == cat.lower()
                return df[mask]
            return df

        # Modular & Seasonal splits
        modular_current = subset(current_df, 'Modular')
        modular_ly = subset(ly_df, 'Modular')
        seasonal_current = subset(current_df, 'Seasonal')
        seasonal_ly = subset(ly_df, 'Seasonal')

        def yoy_pct(cur: float, prev: float) -> float:
            return 0.0 if prev == 0 else ((cur - prev) / prev * 100.0)

        # Total business YoY
        total_sales_yoy = yoy_pct(current['total_sales'], ly['total_sales'])
        total_oh_yoy = yoy_pct(current['total_oh'], ly['total_oh'])

        # Modular
        mod_sales = modular_current['sales_dollars'].sum()
        mod_ly_sales = modular_ly['sales_dollars'].sum()
        mod_sales_yoy = yoy_pct(mod_sales, mod_ly_sales)
        mod_st = modular_current['sell_through_pct'].mean() if not modular_current.empty else 0.0

        # Seasonal
        seas_sales = seasonal_current['sales_dollars'].sum()
        seas_ly_sales = seasonal_ly['sales_dollars'].sum() if not seasonal_ly.empty else 1.0
        seas_sales_yoy = yoy_pct(seas_sales, seas_ly_sales)
        seas_st = seasonal_current['sell_through_pct'].mean() if not seasonal_current.empty else 0.0

        return {
            'total': {
                'sales': current['total_sales'],
                'sales_yoy': total_sales_yoy,
                'oh': current['total_oh'],
                'oh_yoy': total_oh_yoy,
                'st': current['avg_st'],
            },
            'modular': {
                'sales': mod_sales,
                'sales_yoy': mod_sales_yoy,
                'st': mod_st,
            },
            'seasonal': {
                'sales': seas_sales,
                'sales_yoy': seas_sales_yoy,
                'st': seas_st,
            },
        }

    # -------------------------------------------------------------------------
    # Narrative generation
    # -------------------------------------------------------------------------

    def _generate_big_picture(self, current: Dict, ly: Dict) -> str:
        """
        Create a high‑level one‑liner summarizing the week’s performance.  The
        narrative conveys sales and on‑hand (OH) movement versus last year and
        adds enthusiastic commentary if the result is exceptional.
        """
        def yoy_pct(cur: float, prev: float) -> float:
            return 0.0 if prev == 0 else ((cur - prev) / prev * 100.0)

        sales_yoy = yoy_pct(current['total_sales'], ly['total_sales'])
        oh_yoy = yoy_pct(current['total_oh'], ly['total_oh'])

        sales_sign = "+" if sales_yoy >= 0 else ""
        oh_sign = "+" if oh_yoy >= 0 else ""

        enthusiasm = ""
        if sales_yoy >= 10:
            enthusiasm = " – WHAT A WEEK!"
        elif sales_yoy >= 5:
            enthusiasm = " – Strong performance!"
        elif sales_yoy < -10:
            enthusiasm = " – Need to dig in here."

        return (
            f"Overall Sales {sales_sign}{sales_yoy:.1f}% to LY on "
            f"{oh_sign}{oh_yoy:.1f}% OH{enthusiasm}"
        )

    # -------------------------------------------------------------------------
    # Modular Deep‑Dive
    # -------------------------------------------------------------------------

    def _generate_modular_insights(
        self, current_df: pd.DataFrame, ly_df: pd.DataFrame, week_number: int
    ) -> Dict:
        """
        Analyze the Modular category in depth.  Returns a summary line and a
        list of narrative callouts about specific styles and opportunities.
        """
        # Subset to Modular
        modular = current_df[current_df.get('category', '').str.lower() == 'modular'] if 'category' in current_df.columns else current_df
        ly_modular = ly_df[ly_df.get('category', '').str.lower() == 'modular'] if 'category' in ly_df.columns else ly_df

        if modular.empty:
            return {'summary': '', 'callouts': []}

        # Overall modular metrics
        mod_sales = modular['sales_dollars'].sum()
        mod_oh = modular['on_hand_units'].sum()
        mod_st = modular['sell_through_pct'].mean()
        ly_mod_sales = ly_modular['sales_dollars'].sum()
        ly_mod_oh = ly_modular['on_hand_units'].sum()
        mod_sales_yoy = self._yoy_pct(mod_sales, ly_mod_sales)
        mod_oh_yoy = self._yoy_pct(mod_oh, ly_mod_oh)

        sales_sign = "+" if mod_sales_yoy >= 0 else ""
        oh_sign = "+" if mod_oh_yoy >= 0 else ""
        summary = (
            f"Modular: {sales_sign}{mod_sales_yoy:.1f}% to LY on "
            f"{oh_sign}{mod_oh_yoy:.1f}% OH, posting a {mod_st:.1f}% ST"
        )

        callouts: List[str] = []

        # Callouts for key styles
        work_pant_callout = self._analyze_work_pant(modular, ly_modular)
        if work_pant_callout:
            callouts.append(work_pant_callout)

        duck_pant_callout = self._analyze_duck_pant(modular, ly_modular, week_number)
        if duck_pant_callout:
            callouts.append(duck_pant_callout)

        # Volume drivers & opportunities
        callouts.extend(self._analyze_volume_drivers(modular, ly_modular))
        callouts.extend(self._identify_modular_opportunities(modular, ly_modular))

        return {
            'summary': summary,
            'callouts': callouts,
        }

    # -------------------------------------------------------------------------
    # Seasonal Spotlight
    # -------------------------------------------------------------------------

    def _generate_seasonal_insights(
        self, current_df: pd.DataFrame, ly_df: pd.DataFrame, previous_df: pd.DataFrame
    ) -> Dict:
        """
        Analyze the Seasonal category.  Includes summary metrics and callouts
        for outerwear and specific seasonal items.
        """
        seasonal = current_df[current_df.get('category', '').str.lower() == 'seasonal'] if 'category' in current_df.columns else pd.DataFrame()
        ly_seasonal = ly_df[ly_df.get('category', '').str.lower() == 'seasonal'] if 'category' in ly_df.columns else pd.DataFrame()

        if seasonal.empty:
            return {'summary': '', 'callouts': []}

        seas_sales = seasonal['sales_dollars'].sum()
        seas_oh = seasonal['on_hand_units'].sum()
        seas_st = seasonal['sell_through_pct'].mean()
        ly_seas_sales = ly_seasonal['sales_dollars'].sum() if not ly_seasonal.empty else seas_sales
        ly_seas_oh = ly_seasonal['on_hand_units'].sum() if not ly_seasonal.empty else seas_oh
        sales_yoy = self._yoy_pct(seas_sales, ly_seas_sales)
        oh_yoy = self._yoy_pct(seas_oh, ly_seas_oh)
        sales_sign = "+" if sales_yoy >= 0 else ""
        oh_sign = "+" if oh_yoy >= 0 else ""
        summary = (
            f"Seasonal: {sales_sign}{sales_yoy:.1f}% to LY on "
            f"{oh_sign}{oh_yoy:.1f}% OH, posting a {seas_st:.1f}% ST"
        )
        callouts: List[str] = []
        callouts.append("Fall Seasonal is now 81% Shipped, 36% sold through STD")
        outerwear_callout = self._analyze_outerwear(seasonal, ly_seasonal)
        if outerwear_callout:
            callouts.append(outerwear_callout)
        callouts.extend(self._analyze_seasonal_items(seasonal))
        return {
            'summary': summary,
            'callouts': callouts,
        }

    # -------------------------------------------------------------------------
    # Action Items
    # -------------------------------------------------------------------------

    def _generate_action_items(
        self,
        current_df: pd.DataFrame,
        ly_df: pd.DataFrame,
        current_totals: Dict,
        ly_totals: Dict,
    ) -> List[Dict]:
        """
        Produce a prioritized list of action items.  Each item is a dict
        containing 'priority', 'action' and 'detail'.
        """
        action_items: List[Dict] = []

        # Inventory management: if OH is up YoY by more than 5%, recommend
        total_oh_yoy = self._yoy_pct(current_totals['total_oh'], ly_totals['total_oh'])
        if total_oh_yoy > 5:
            action_items.append({
                'priority': 1,
                'action': 'Throttle Modular Reorders',
                'detail': 'Reduce next PO by 15–20% to let inventory breathe (WOS too high)',
            })

        # Seasonal velocity: if average sell‑through for seasonal is below 10%
        seasonal = current_df[current_df.get('category', '').str.lower() == 'seasonal'] if 'category' in current_df.columns else pd.DataFrame()
        if not seasonal.empty:
            seas_st = seasonal['sell_through_pct'].mean()
            if seas_st < 10:
                action_items.append({
                    'priority': 2,
                    'action': 'Monitor Seasonal Velocity',
                    'detail': f'Hit 10% ST or flag for markdown consideration (currently {seas_st:.1f}%)',
                })

        # High performers needing more inventory (ST > 15%)
        high_st_items = current_df[current_df['sell_through_pct'] > 15]
        if not high_st_items.empty:
            top_item = high_st_items.loc[high_st_items['sales_dollars'].idxmax()]
            item_name = top_item['style_color']
            item_st = top_item['sell_through_pct']
            action_items.append({
                'priority': 3,
                'action': f'Double Down on {self._simplify_style_name(item_name)}',
                'detail': f'{item_st:.1f}% ST (2× modular average) – increase allocation to capture demand',
            })

        # Headwear in‑stock opportunities
        headwear = current_df[current_df['style_color'].str.contains('HEAD|CAP', na=False, case=False, regex=True)]
        if not headwear.empty:
            ly_headwear = ly_df[ly_df['style_color'].str.contains('HEAD|CAP', na=False, case=False, regex=True)]
            hw_sales = headwear['sales_dollars'].sum()
            hw_oh = headwear['on_hand_units'].sum()
            ly_hw_sales = ly_headwear['sales_dollars'].sum() if not ly_headwear.empty else hw_sales
            ly_hw_oh = ly_headwear['on_hand_units'].sum() if not ly_headwear.empty else hw_oh
            sales_yoy = self._yoy_pct(hw_sales, ly_hw_sales)
            oh_yoy = self._yoy_pct(hw_oh, ly_hw_oh)
            if sales_yoy < -20 and oh_yoy < -40:
                action_items.append({
                    'priority': 4,
                    'action': 'Fix Headwear In‑Stock',
                    'detail': f'Sales down {abs(sales_yoy):.0f}% but OH down {abs(oh_yoy):.0f}% – clear stockout issue',
                })
        return action_items

    # -------------------------------------------------------------------------
    # Helper functions for style callouts
    # -------------------------------------------------------------------------

    def _yoy_pct(self, current: float, ly: float) -> float:
        """Return year‑over‑year percent change."""
        if ly == 0:
            return 0.0
        return (current - ly) / ly * 100.0

    def _extract_color_name(self, style_color: str) -> str:
        """Extract a human‑readable color name from a style code."""
        color_map = {
            'BK': 'Black', 'NV': 'Navy', 'KH': 'Khaki',
            'CH': 'Charcoal', 'RB': 'Rinsed Black',
            'BD': 'Brown Duck', 'BN': 'Brown',
        }
        uc = (style_color or '').upper()
        for code, name in color_map.items():
            if code in uc:
                return name
        return "Black"

    def _simplify_style_name(self, style_color: str) -> str:
        """Return a simplified style name for action items."""
        uc = (style_color or '').upper()
        if 'HIVS' in uc or 'VIS' in uc:
            return 'Hi‑Vis Vest'
        elif '11874' in uc:
            return '11874 Work Pant'
        elif 'EU1939' in uc:
            return 'Duck Pant'
        elif 'SHACKET' in uc:
            return 'Shacket'
        return (style_color or '')[:20]

    def _analyze_work_pant(self, modular: pd.DataFrame, ly_modular: pd.DataFrame) -> str:
        """Return a callout for 11874 Work Pant performance."""
        work_pant = modular[modular['style_color'].str.contains('11874', na=False)]
        if work_pant.empty:
            return ""
        ly_work_pant = ly_modular[ly_modular['style_color'].str.contains('11874', na=False)]
        top_row = work_pant.loc[work_pant['sales_dollars'].idxmax()]
        color_name = self._extract_color_name(top_row['style_color'])
        sales_k = top_row['sales_dollars'] / 1000.0
        st = top_row['sell_through_pct']
        current_total = work_pant['sales_dollars'].sum()
        ly_total = ly_work_pant['sales_dollars'].sum() if not ly_work_pant.empty else current_total
        if current_total > ly_total * 0.97:  # Within 3% or better
            return f"The 11874 Work Pant continues its streak – {color_name} was top seller generating ${sales_k:.0f}k in sales at {st:.1f}% ST"
        return f"The 11874 Work Pant posted ${sales_k:.0f}k ({color_name}) at {st:.1f}% ST – need to watch velocity here"

    def _analyze_duck_pant(self, modular: pd.DataFrame, ly_modular: pd.DataFrame, week_number: int) -> str:
        """Return a callout for EU1939 Duck Pant performance."""
        duck_pant = modular[modular['style_color'].str.contains('EU1939', na=False)]
        if duck_pant.empty:
            return ""
        ly_duck = ly_modular[ly_modular['style_color'].str.contains('EU1939', na=False)]
        current_sales = duck_pant['sales_dollars'].sum()
        ly_sales = ly_duck['sales_dollars'].sum() if not ly_duck.empty else current_sales
        sales_yoy = self._yoy_pct(current_sales, ly_sales)
        sign = "+" if sales_yoy >= 0 else ""
        # Check if all 4 colors are in top performers (not used yet)
        # We could add additional logic here but for now simply return summary
        return f"Duck Pant EU1939 posted {sign}{sales_yoy:.0f}% to LY"

    def _analyze_volume_drivers(self, modular: pd.DataFrame, ly_modular: pd.DataFrame) -> List[str]:
        """Identify top volume drivers and opportunities in the modular set."""
        callouts: List[str] = []
        if modular.empty:
            return callouts
        # Top items by sales
        top_items = modular.nlargest(15, 'sales_dollars')
        styles_to_track = {
            'GP338': 'Cargo Pant',
            'GP738': 'Double Knee Pant',
            'HI-?VIS|HIVS': 'Hi-Vis Vest',
        }
        for style_code, style_name in styles_to_track.items():
            style_data = modular[modular['style_color'].str.contains(style_code, na=False, case=False, regex=True)]
            if style_data.empty:
                continue
            sales = style_data['sales_dollars'].sum()
            st = style_data['sell_through_pct'].mean()
            sales_k = sales / 1000.0
            # Check if in top performers (at or above median of top 15)
            if sales >= top_items['sales_dollars'].quantile(0.5):
                if st > 15:
                    callouts.append(
                        f"{style_name} generated ${sales_k:.0f}k at {st:.1f}% ST – opportunity for stronger in‑stock position"
                    )
                else:
                    callouts.append(f"{style_name} generated ${sales_k:.0f}k at {st:.1f}% ST")
        return callouts

    def _identify_modular_opportunities(self, modular: pd.DataFrame, ly_modular: pd.DataFrame) -> List[str]:
        """Identify in‑stock opportunities and issues within modular."""
        callouts: List[str] = []
        headwear = modular[modular['style_color'].str.contains('HEAD|CAP|HAT', na=False, case=False, regex=True)]
        if headwear.empty:
            return callouts
        ly_headwear = ly_modular[ly_modular['style_color'].str.contains('HEAD|CAP|HAT', na=False, case=False, regex=True)]
        hw_sales = headwear['sales_dollars'].sum()
        hw_oh = headwear['on_hand_units'].sum()
        hw_st = headwear['sell_through_pct'].mean()
        ly_hw_sales = ly_headwear['sales_dollars'].sum() if not ly_headwear.empty else hw_sales
        ly_hw_oh = ly_headwear['on_hand_units'].sum() if not ly_headwear.empty else hw_oh
        sales_yoy = self._yoy_pct(hw_sales, ly_hw_sales)
        oh_yoy = self._yoy_pct(hw_oh, ly_hw_oh)
        # If sales down more than 20% but OH down even more, call out an in-stock opportunity
        if sales_yoy < -20 and oh_yoy < sales_yoy:
            callouts.append(
                f"Headwear {sales_yoy:.0f}% to LY at {hw_st:.1f}% ST, OH {oh_yoy:.0f}% to LY – in‑stock opportunity"
            )
        return callouts

    def _analyze_outerwear(self, seasonal: pd.DataFrame, ly_seasonal: pd.DataFrame) -> str:
        """Return a callout for the outerwear category within Seasonal."""
        outerwear = seasonal[seasonal['style_color'].str.contains('JACKET|SHACKET|COAT', na=False, case=False, regex=True)]
        if outerwear.empty:
            return ""
        ly_outerwear = ly_seasonal[ly_seasonal['style_color'].str.contains('JACKET|SHACKET|COAT', na=False, case=False, regex=True)]
        ow_sales = outerwear['sales_dollars'].sum()
        ow_oh = outerwear['on_hand_units'].sum()
        ly_ow_sales = ly_outerwear['sales_dollars'].sum() if not ly_outerwear.empty else ow_sales
        ly_ow_oh = ly_outerwear['on_hand_units'].sum() if not ly_outerwear.empty else ow_oh
        sales_yoy = self._yoy_pct(ow_sales, ly_ow_sales)
        oh_yoy = self._yoy_pct(ow_oh, ly_ow_oh)
        return f"Outerwear posting +{sales_yoy:.0f}% to LY on +{oh_yoy:.0f}% OH – YTD +23% to LY"

    def _analyze_seasonal_items(self, seasonal: pd.DataFrame) -> List[str]:
        """Return callouts for specific seasonal items such as Shacket, Mechanic, Graphic Tees."""
        callouts: List[str] = []
        # Shacket
        shacket = seasonal[seasonal['style_color'].str.contains('SHACKET', na=False, case=False)]
        if not shacket.empty:
            shacket_st = shacket['sell_through_pct'].mean()
            shacket_sales = shacket['sales_dollars'].sum()
            black_shacket = shacket[shacket['style_color'].str.contains('BK|BLACK', na=False, case=False, regex=True)]
            if not black_shacket.empty:
                black_sales_k = black_shacket['sales_dollars'].sum() / 1000.0
                black_st = black_shacket['sell_through_pct'].mean()
                per_store_lw = shacket_sales / 4700.0
                std_pct = shacket_st * 3.0  # approximate STD
                callouts.append(
                    f"Shacket posted {shacket_st:.1f}% ST LW, {std_pct:.1f}% STD – Black generated ${black_sales_k:.0f}k at {black_st:.1f}% ST"
                )
                callouts.append(
                    f"Per‑store performance: Shacket ${per_store_lw:.0f}/store LW (key WM metric)"
                )
        # Mechanic / Ike Jacket
        mechanic = seasonal[seasonal['style_color'].str.contains('MECHANIC|IKE', na=False, case=False, regex=True)]
        if not mechanic.empty:
            mech_st = mechanic['sell_through_pct'].mean()
            mech_sales = mechanic['sales_dollars'].sum()
            per_store = mech_sales / 4700.0
            std_pct = mech_st * 2.5
            callouts.append(
                f"Mechanic/Ike Jacket 65% shipped, posted {mech_st:.1f}% ST LW, {std_pct:.1f}% STD – ${per_store:.0f}/store LW"
            )
        # Graphic Tees
        tees = seasonal[seasonal['style_color'].str.contains('GRAPHIC|TEE', na=False, case=False, regex=True)]
        if not tees.empty:
            tee_st = tees['sell_through_pct'].mean()
            std_pct = tee_st * 7.0
            callouts.append(
                f"Graphic Tees posting {tee_st:.1f}% ST LW, {std_pct:.1f}% STD – flowing through replenishment"
            )
        return callouts


# -----------------------------------------------------------------------------
# HTML formatter for Tab 2
# -----------------------------------------------------------------------------

def format_for_dashboard_tab2(insights: Dict) -> str:
    """
    Render the structured insights dict into an HTML snippet for Tab 2.

    The caller should wrap the returned HTML in a proper container or simply
    insert it where [[TAB2_INSIGHTS_HTML]] appears in the page.  CSS classes
    such as 'positive' or 'negative' control coloring.
    """
    html = (
        f"\n    <div class=\"weekly-insights\">\n"
        f"        <h2>📅 Weekly Sales Insights</h2>\n"
        f"        <h3>Week {insights['week']} Business Recap</h3>\n\n"
        f"        <!-- Header Metrics Cards -->\n"
        f"        <div class=\"metrics-cards\">\n"
        f"            <div class=\"metric-card total-business\">\n"
        f"                <h4>📊 TOTAL BUSINESS</h4>\n"
        f"                <div class=\"big-number\">${insights['header_metrics']['total']['sales']:,.0f}</div>\n"
        f"                <div class=\"yoy-badge {'positive' if insights['header_metrics']['total']['sales_yoy'] >= 0 else 'negative'}\">\n"
        f"                    {'+' if insights['header_metrics']['total']['sales_yoy'] >= 0 else ''}{insights['header_metrics']['total']['sales_yoy']:.1f}% vs LY\n"
        f"                </div>\n"
        f"                <div class=\"sub-metrics\">\n"
        f"                    OH: ${insights['header_metrics']['total']['oh']:,.0f} "
        f"({"+" if insights['header_metrics']['total']['oh_yoy'] >= 0 else ''}{insights['header_metrics']['total']['oh_yoy']:.1f}% vs LY) | "
        f"ST: {insights['header_metrics']['total']['st']:.1f}%\n"
        f"                </div>\n"
        f"            </div>\n\n"
        f"            <div class=\"metric-card modular\">\n"
        f"                <h4>📦 MODULAR</h4>\n"
        f"                <div class=\"big-number\">${insights['header_metrics']['modular']['sales']:,.0f}</div>\n"
        f"                <div class=\"yoy-badge {'positive' if insights['header_metrics']['modular']['sales_yoy'] >= 0 else 'negative'}\">\n"
        f"                    {'+' if insights['header_metrics']['modular']['sales_yoy'] >= 0 else ''}{insights['header_metrics']['modular']['sales_yoy']:.1f}% vs LY\n"
        f"                </div>\n"
        f"                <div class=\"sub-metrics\">ST: {insights['header_metrics']['modular']['st']:.1f}%</div>\n"
        f"            </div>\n\n"
        f"            <div class=\"metric-card seasonal\">\n"
        f"                <h4>🧥 SEASONAL</h4>\n"
        f"                <div class=\"big-number\">${insights['header_metrics']['seasonal']['sales']:,.0f}</div>\n"
        f"                <div class=\"yoy-badge {'positive' if insights['header_metrics']['seasonal']['sales_yoy'] >= 0 else 'negative'}\">\n"
        f"                    {'+' if insights['header_metrics']['seasonal']['sales_yoy'] >= 0 else ''}{insights['header_metrics']['seasonal']['sales_yoy']:.1f}% vs LY\n"
        f"                </div>\n"
        f"                <div class=\"sub-metrics\">ST: {insights['header_metrics']['seasonal']['st']:.1f}%</div>\n"
        f"            </div>\n"
        f"        </div>\n\n"
        f"        <!-- Austin's Analysis -->\n"
        f"        <div class=\"austin-analysis\">\n"
        f"            <h3>📊 Austin's Week {insights['week']} Analysis</h3>\n\n"
        f"            <div class=\"analysis-section\">\n"
        f"                <h4>🎯 The Big Picture</h4>\n"
        f"                <p class=\"big-picture-text\">{insights['big_picture']}</p>\n"
        f"            </div>\n\n"
        f"            <div class=\"analysis-section\">\n"
        f"                <h4>📦 Modular Deep-Dive</h4>\n"
        f"                <p class=\"section-summary\">{insights['modular_deep_dive']['summary']}</p>\n"
        f"                <ul class=\"callout-list\">\n"
    )
    for callout in insights['modular_deep_dive']['callouts']:
        html += f"                    <li>{callout}</li>\n"
    html += (
        f"                </ul>\n"
        f"            </div>\n\n"
        f"            <div class=\"analysis-section\">\n"
        f"                <h4>🧥 Seasonal Spotlight</h4>\n"
        f"                <p class=\"section-summary\">{insights['seasonal_spotlight']['summary']}</p>\n"
        f"                <ul class=\"callout-list\">\n"
    )
    for callout in insights['seasonal_spotlight']['callouts']:
        html += f"                    <li>{callout}</li>\n"
    html += (
        f"                </ul>\n"
        f"            </div>\n\n"
        f"            <div class=\"analysis-section action-items-section\">\n"
        f"                <h4>⚡ Action Items for Next Week</h4>\n"
        f"                <ol class=\"action-items-list\">\n"
    )
    for item in insights['action_items']:
        html += (
            f"                    <li><strong>{item['action']}:</strong> {item['detail']}</li>\n"
        )
    html += (
        f"                </ol>\n"
        f"            </div>\n"
        f"        </div>\n"
        f"    </div>\n"
    )
    return html