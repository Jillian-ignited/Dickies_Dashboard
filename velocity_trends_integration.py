"""
Velocity Trends File Integration
Adds size-level analysis and WOS validation
"""

import pandas as pd
from typing import Dict, List


def read_velocity_trends(velocity_file: str) -> pd.DataFrame:
    """
    Read Velocity Trends file - Detail Data sheet
    
    Returns:
        DataFrame with Prime Item level data
    """
    print("\n📊 Reading Velocity Trends File...")
    
    df = pd.read_excel(velocity_file, sheet_name='Detail Data', header=1)
    
    print(f"   ✓ {len(df)} Prime Items (size/color level)")
    
    return df


def map_velocity_to_styles(velocity_df: pd.DataFrame) -> Dict[str, List[Dict]]:
    """
    Map Prime Items to Style/Color codes
    
    Args:
        velocity_df: Velocity Trends DataFrame
    
    Returns:
        Dictionary mapping Style/Color to list of Prime Items
        {
            'EU1939RBD': [
                {'prime_item': 574680967, 'size': '32X32', 'status': 'A', 'wos': 12.5, ...},
                {'prime_item': 574680949, 'size': '34X32', 'status': 'A', 'wos': 8.3, ...},
            ],
            ...
        }
    """
    print("\n🔗 Mapping Velocity Data to Style/Color codes...")
    
    style_map = {}
    
    for idx, row in velocity_df.iterrows():
        # Vndr Category 2 contains the Style/Color code
        style_color = str(row.get('Vndr Category 2', '')).strip()
        
        if not style_color or pd.isna(style_color):
            continue
        
        # Extract key metrics
        prime_item = row.get('Prime Item Nbr', '')
        size = str(row.get('Prime Size Description', '')).strip()
        item_status = str(row.get('Item Status', '')).strip()
        
        # Sales and inventory
        lw_pos_qty = row.get('LW POS Qty', 0) or 0
        lw_inv_retail = row.get('Total LW Str Inv Retail', 0) or 0
        lw_avg_retail = row.get('LW Avg Retail', 0) or 1  # Avoid division by zero
        
        # Calculate inventory in units (retail $ / avg retail)
        lw_inv_units = lw_inv_retail / lw_avg_retail if lw_avg_retail > 0 else 0
        
        # Calculate WOS
        wos = (lw_inv_units / lw_pos_qty) if lw_pos_qty > 0 else 0
        
        # Store count
        curr_valid_stores = row.get('Curr Valid Stores', 0) or 0
        
        # Build Prime Item record
        prime_item_record = {
            'prime_item': prime_item,
            'size': size,
            'item_status': item_status,
            'lw_pos_qty': float(lw_pos_qty),
            'lw_inv_units': float(lw_inv_units),
            'lw_inv_retail': float(lw_inv_retail),
            'wos': round(float(wos), 1),
            'curr_valid_stores': int(curr_valid_stores),
            'unit_retail': float(row.get('Unit Retail', 0) or 0),
            'unit_cost': float(row.get('Unit Cost', 0) or 0),
        }
        
        # Add to style map
        if style_color not in style_map:
            style_map[style_color] = []
        
        style_map[style_color].append(prime_item_record)
    
    print(f"   ✓ Mapped {len(style_map)} Style/Color codes")
    print(f"   ✓ Total Prime Items: {sum(len(v) for v in style_map.values())}")
    
    return style_map


def enrich_sku_master_with_size_analysis(sku_master: List[Dict], style_map: Dict[str, List[Dict]]) -> List[Dict]:
    """
    Enrich SKU master with size-level analysis from Velocity Trends
    
    Args:
        sku_master: List of SKU records
        style_map: Style/Color to Prime Items mapping
    
    Returns:
        Enriched SKU master with size analysis
    """
    print("\n💎 Enriching SKU Master with Size Analysis...")
    
    enriched_count = 0
    
    for sku in sku_master:
        sku_code = sku.get('sku', '')
        
        # Initialize store_count to 0 (will be updated if velocity data exists)
        sku['store_count'] = 0
        
        if sku_code in style_map:
            prime_items = style_map[sku_code]
            
            # Calculate size-level metrics
            total_prime_items = len(prime_items)
            active_items = [p for p in prime_items if p['item_status'] == 'A']
            # Use max instead of sum to get actual store count (sizes are in same stores)
            total_stores = max(p['curr_valid_stores'] for p in prime_items) if prime_items else 0
            
            # WOS distribution
            wos_values = [p['wos'] for p in prime_items if p['wos'] > 0]
            avg_wos = sum(wos_values) / len(wos_values) if wos_values else 0
            max_wos = max(wos_values) if wos_values else 0
            min_wos = min(wos_values) if wos_values else 0
            
            # Sales distribution
            total_sales = sum(p['lw_pos_qty'] for p in prime_items)
            
            # Identify productive vs. dead sizes
            productive_sizes = [p for p in prime_items if p['lw_pos_qty'] > 0 and p['wos'] < 20]
            dead_sizes = [p for p in prime_items if p['wos'] > 30 or (p['lw_pos_qty'] == 0 and p['lw_inv_units'] > 0)]
            
            # Add size analysis to SKU record
            sku['size_analysis'] = {
                'total_prime_items': total_prime_items,
                'active_items': len(active_items),
                'total_stores': total_stores,
                'avg_wos': round(avg_wos, 1),
                'max_wos': round(max_wos, 1),
                'min_wos': round(min_wos, 1),
                'productive_sizes': len(productive_sizes),
                'dead_sizes': len(dead_sizes),
                'size_efficiency_pct': round((len(productive_sizes) / total_prime_items * 100), 1) if total_prime_items > 0 else 0,
            }
            
            # Flatten store_count to top level for dashboard display
            sku['store_count'] = total_stores
            
            # Store Prime Item details
            sku['prime_items'] = prime_items
            
            enriched_count += 1
    
    print(f"   ✓ Enriched {enriched_count} SKUs with size analysis")
    
    return sku_master


def generate_size_recommendations(sku_master: List[Dict]) -> List[Dict]:
    """
    Generate size optimization recommendations
    
    Args:
        sku_master: Enriched SKU master with size analysis
    
    Returns:
        List of size optimization recommendations
    """
    print("\n📋 Generating Size Optimization Recommendations...")
    
    recommendations = []
    
    for sku in sku_master:
        if 'size_analysis' not in sku:
            continue
        
        size_analysis = sku['size_analysis']
        dead_sizes = size_analysis.get('dead_sizes', 0)
        size_efficiency = size_analysis.get('size_efficiency_pct', 0)
        
        # Recommendation logic
        if dead_sizes > 0 and size_efficiency < 70:
            recommendation = {
                'sku': sku['sku'],
                'fineline': sku['fineline'],
                'tier': sku['tier'],
                'total_sizes': size_analysis['total_prime_items'],
                'dead_sizes': dead_sizes,
                'size_efficiency_pct': size_efficiency,
                'recommendation': f"Optimize size curve - {dead_sizes} dead sizes out of {size_analysis['total_prime_items']}",
                'priority': 'high' if dead_sizes > 3 else 'medium',
                'expected_impact': 'Reduce inventory bloat, improve WOS'
            }
            recommendations.append(recommendation)
    
    print(f"   ✓ Generated {len(recommendations)} size optimization recommendations")
    
    return recommendations
