# Tier Tokens Replacement Guide

## Overview

This guide shows you exactly where to replace hardcoded tier counts with dynamic tokens in your `index.html` file. The tokens will be automatically populated by `html_updater_v5.py` each week.

---

## Available Tokens

| Token | Description | Example Value |
|-------|-------------|---------------|
| `[[TIER_A_COUNT]]` | Number of A-tier SKUs | 33 |
| `[[TIER_B_COUNT]]` | Number of B-tier SKUs | 52 |
| `[[TIER_C_COUNT]]` | Number of C-tier SKUs | 234 |
| `[[TIER_AB_COUNT]]` | Total A+B SKUs | 85 |
| `[[TIER_AB_SALES_PCT]]` | % of sales from A+B SKUs | 95.0% |
| `[[ACTION_ITEMS_COUNT]]` | Total action items | 56 |
| `[[SEASONAL_RISK_COUNT]]` | Seasonal risk items | 10 |

---

## Replacement Locations

### 1. Executive Summary Tab

**Find this text** (around line 5700-5800):
```html
<p>The current assortment of <strong>329 SKUs</strong> is split into <strong>12 A-items</strong>, <strong>21 B-items</strong>, and <strong>296 C-items</strong>...</p>
```

**Replace with**:
```html
<p>The current assortment of <strong>[[TIER_A_COUNT]] A-items</strong>, <strong>[[TIER_B_COUNT]] B-items</strong>, and <strong>[[TIER_C_COUNT]] C-items</strong>...</p>
```

---

### 2. SKU Performance Tab

**Find this text** (around line 6200-6300):
```html
<p><strong>282 A+B SKUs</strong> drive the majority of sales...</p>
```

**Replace with**:
```html
<p><strong>[[TIER_AB_COUNT]] A+B SKUs</strong> drive [[TIER_AB_SALES_PCT]] of sales...</p>
```

---

**Find this text**:
```html
<p>The remaining <strong>35 C-tier SKUs</strong> contribute minimal volume...</p>
```

**Replace with**:
```html
<p>The remaining <strong>[[TIER_C_COUNT]] C-tier SKUs</strong> contribute minimal volume...</p>
```

---

### 3. Growth Roadmap Tab (Action Plan)

**Find this text** (around line 6900-7000):
```html
<p>Identify C-items for phase-out: Review 296 C-items, prioritize worst performers</p>
```

**Replace with**:
```html
<p>Identify C-items for phase-out: Review [[TIER_C_COUNT]] C-items, prioritize worst performers</p>
```

---

**Find this text**:
```html
<p>Complete C-item phase-out: Exit all 296 slow SKUs</p>
```

**Replace with**:
```html
<p>Complete C-item phase-out: Exit all [[TIER_C_COUNT]] slow SKUs</p>
```

---

**Find this text**:
```html
<p>Focus on 33 A+B SKUs</p>
```

**Replace with**:
```html
<p>Focus on [[TIER_AB_COUNT]] A+B SKUs</p>
```

---

### 4. Seasonal Insights Tab

**Find this text** (around line 7100-7200):
```html
<p>Of the 329 total SKUs, 12 are A-tier heroes...</p>
```

**Replace with**:
```html
<p>Of the total SKUs, [[TIER_A_COUNT]] are A-tier heroes...</p>
```

---

## Search & Replace Strategy

Use your text editor's Find & Replace function:

### Find: `329 SKUs`
**Replace with**: `[[TIER_A_COUNT]] A-tier + [[TIER_B_COUNT]] B-tier + [[TIER_C_COUNT]] C-tier SKUs`

### Find: `282 A+B SKUs`
**Replace with**: `[[TIER_AB_COUNT]] A+B SKUs`

### Find: `296 C-items` or `296 C-tier`
**Replace with**: `[[TIER_C_COUNT]] C-items`

### Find: `35 C-tier`
**Replace with**: `[[TIER_C_COUNT]] C-tier`

### Find: `12 A-tier` or `12 A-items`
**Replace with**: `[[TIER_A_COUNT]] A-tier`

### Find: `21 B-tier` or `21 B-items`
**Replace with**: `[[TIER_B_COUNT]] B-tier`

### Find: `33 SKUs` (in context of A+B)
**Replace with**: `[[TIER_AB_COUNT]] SKUs`

---

## Testing After Replacement

After running `html_updater_v5.py`, verify these values in your browser:

1. **Check Executive Summary**: Should show dynamic tier counts (not 12/21/296)
2. **Check SKU Performance**: Should show A+B count and sales %
3. **Check Action Plan**: Should show correct C-tier count in recommendations
4. **Check for leftover tokens**: Search HTML source for `[[TIER_` - if found, those tokens weren't replaced

---

## Common Mistakes to Avoid

❌ **Don't replace inside JavaScript code blocks** - Only replace in HTML text content
❌ **Don't replace in comments** - Only replace visible text
❌ **Don't replace partial matches** - Make sure you're replacing the full phrase

✅ **Do replace in paragraphs, headings, and table cells**
✅ **Do preserve surrounding HTML tags**
✅ **Do test after each major section of replacements**

---

## Verification Checklist

After making all replacements:

- [ ] Search for `296` in HTML - should only appear in historical data/charts
- [ ] Search for `282` in HTML - should only appear in historical data/charts
- [ ] Search for `329` in HTML - should only appear in historical data/charts
- [ ] Search for `[[TIER_` - should find all tokens you added
- [ ] Run `html_updater_v5.py` - should replace all tokens
- [ ] Hard refresh browser (Ctrl+F5) - should see dynamic counts

---

## Need Help?

If a token isn't being replaced:
1. Check that `html_updater_v5.py` ran without errors
2. Check that `sku_master.json` has tier field populated
3. Check that token spelling matches exactly (case-sensitive)
4. Check that token is in HTML content, not inside `<script>` or `<style>` blocks

---

**Last Updated**: Nov 16, 2025
**Version**: 1.0
