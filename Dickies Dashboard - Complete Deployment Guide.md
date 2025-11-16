# Dickies Dashboard - Complete Deployment Guide

## 📦 Package Contents

This deployment package contains all files needed to implement the tier logic fix and dynamic Action Plan tab:

1. **etl_comprehensive_v5.py** - ETL with Pareto-based tier classification
2. **html_updater_v5.py** - Enhanced HTML updater with action items injection
3. **action_plan_tab.html** - New Action Plan tab HTML
4. **austin_insights.py** - Insights generator (already in your repo)
5. **TIER_TOKENS_GUIDE.md** - Guide for updating dashboard narratives
6. **DEPLOYMENT_GUIDE.md** - This file

---

## 🎯 What This Package Fixes

### ✅ Tier Logic (CRITICAL)
- **Before**: Hardcoded tiers (12 A / 21 B / 296 C)
- **After**: Dynamic Pareto-based tiers (~33 A / ~52 B / ~234 C)
- **Impact**: Correct tier assignments based on actual sales %

### ✅ Action Plan Tab
- **Before**: Static text about "296 C-items"
- **After**: 56 dynamic action cards from action_items.json
- **Features**: Priority badges, category filters, responsive layout

### ✅ Dashboard Narratives
- **Before**: Hardcoded "282 A+B SKUs", "296 C-items"
- **After**: Dynamic tokens updated weekly
- **Benefit**: No manual updates needed

---

## 📋 Deployment Steps

### STEP 1: Upload Files to GitHub (5 min)

**Option A: Via GitHub Web Interface (EASIEST)**

1. Go to https://github.com/Jillian-ignited/Dickies_Dashboard

2. Upload `etl_comprehensive_v5.py`:
   - Click on existing `etl_comprehensive_v5.py`
   - Click Edit (pencil icon)
   - Delete all content
   - Copy content from your downloaded `etl_comprehensive_v5.py`
   - Paste into editor
   - Commit message: "Fix tier logic: Implement Pareto-based classification"
   - Click "Commit changes"

3. Upload `html_updater_v5.py`:
   - Click "Add file" → "Upload files"
   - Drag `html_updater_v5.py` from your Downloads folder
   - Commit message: "Add html_updater_v5 with action items injection"
   - Click "Commit changes"

**Option B: Via Git Command Line**

```bash
# On your local machine where you downloaded the files
cd path/to/Dickies_Dashboard

# Copy files
cp ~/Downloads/etl_comprehensive_v5.py ./
cp ~/Downloads/html_updater_v5.py ./

# Commit and push
git add etl_comprehensive_v5.py html_updater_v5.py
git commit -m "Implement tier logic fix and action items injection"
git push origin main
```

---

### STEP 2: Update index.html (15 min)

#### 2A: Replace Action Plan Tab

1. Open `index.html` in your editor
2. Find the Action Plan tab section (search for `<div id="actions" class="tab-content">`)
3. Delete everything from `<div id="actions"...` to its closing `</div>`
4. Copy the entire content of `action_plan_tab.html`
5. Paste it in place of the deleted section
6. Save the file

#### 2B: Add Tier Tokens

Follow the instructions in `TIER_TOKENS_GUIDE.md` to replace hardcoded tier counts with tokens:

**Quick replacements** (use Find & Replace):
- Find: `296 C-items` → Replace: `[[TIER_C_COUNT]] C-items`
- Find: `282 A+B SKUs` → Replace: `[[TIER_AB_COUNT]] A+B SKUs`
- Find: `12 A-tier` → Replace: `[[TIER_A_COUNT]] A-tier`
- Find: `21 B-tier` → Replace: `[[TIER_B_COUNT]] B-tier`

**Verify**: Search for `[[TIER_` to see all tokens you added

#### 2C: Upload Updated index.html to GitHub

Same process as Step 1 - either via web interface or git command line.

---

### STEP 3: Deploy to EC2 (10 min)

#### 3A: SSH into EC2

```powershell
# In PowerShell on Windows
ssh -i "C:\Users\Jillian\OneDrive - ignitedindustries.com\Signal & Scale\Dickies\Dickies-Dashboard.pem" ubuntu@dashboard.signalandscaleinsights.com
```

#### 3B: Pull Latest Code from GitHub

```bash
# On EC2
cd /home/ubuntu/Dickies_Dashboard

# Pull latest changes
git pull origin main

# You should see:
# - etl_comprehensive_v5.py updated
# - html_updater_v5.py added
# - index.html updated
```

#### 3C: Copy Files to Deployment Directory

```bash
# Copy ETL script
cp etl_comprehensive_v5.py /home/ubuntu/deployment_package_final/

# Copy HTML updater
cp html_updater_v5.py /home/ubuntu/deployment_package_final/

# Copy updated dashboard HTML
cp index.html /var/www/dickies/index.html

# Set permissions
sudo chown www-data:www-data /var/www/dickies/index.html
sudo chmod 644 /var/www/dickies/index.html
```

---

### STEP 4: Run ETL with New Tier Logic (5 min)

```bash
# On EC2
cd /home/ubuntu/deployment_package_final

# Run the ETL
python3 etl_comprehensive_v5.py

# Watch for output:
# 📊 Calculating tier assignments (Pareto-based)...
#    ✓ A-tier: 33 SKUs (70.0% of sales)
#    ✓ B-tier: 52 SKUs (25.0% of sales)
#    ✓ C-tier: 234 SKUs (5.0% of sales)
```

**Expected Results**:
- A-tier: ~30-40 SKUs (was 12)
- B-tier: ~40-60 SKUs (was 21)
- C-tier: ~230-250 SKUs (was 296)

**If you see different numbers**, that's OK - it means the tier logic is now based on ACTUAL sales data, not hardcoded counts!

---

### STEP 5: Run HTML Updater v5 (3 min)

```bash
# On EC2
cd /home/ubuntu/deployment_package_final

# Run the updater
python3 html_updater_v5.py

# Watch for output:
# ✅ Loaded Week 40, 317 SKUs from sku_master.json
# ✅ Tier distribution: A=33, B=52, C=234
# ✅ Loaded 56 action items
# ✅ Injected action items JavaScript
# ✅ Injected weekly metrics and tier tokens
```

---

### STEP 6: Verify Dashboard (5 min)

1. **Open browser**: https://dashboard.signalandscaleinsights.com/

2. **Hard refresh**: Ctrl + F5 (Windows) or Cmd + Shift + R (Mac)

3. **Check Executive Summary**:
   - Should show dynamic tier counts (not 12/21/296)
   - Example: "33 A-tier, 52 B-tier, 234 C-tier SKUs"

4. **Check Action Plan Tab**:
   - Should show "85 A+B SKUs Drive 95.0% of Sales" (dynamic)
   - Should display 56 action cards
   - Filter buttons should work (All / Seasonal / Inventory)
   - Cards should have priority badges (HIGH/MEDIUM/LOW)

5. **Check SKU Performance Tab**:
   - Should show dynamic A+B count and sales %

6. **Check for errors**:
   - Open browser console (F12)
   - Look for JavaScript errors
   - If you see "No action items data found", run html_updater_v5.py again

---

## 🧪 Validation Checklist

After deployment, verify:

### ETL Output
- [ ] Tier distribution changed from 12/21/296 to ~33/52/234
- [ ] `sku_master.json` has tier field populated
- [ ] `action_items.json` exists with 56 items
- [ ] `seasonal_risk.json` exists with risk items

### Dashboard Display
- [ ] Executive Summary shows dynamic tier counts
- [ ] Action Plan tab displays 56 action cards
- [ ] Filter buttons work (All / Seasonal / Inventory)
- [ ] Priority badges show (HIGH/MEDIUM/LOW)
- [ ] No `[[TIER_` tokens visible in HTML
- [ ] No JavaScript errors in console

### Data Accuracy
- [ ] A-tier SKUs represent ~70% of cumulative sales
- [ ] B-tier SKUs represent ~25% of cumulative sales
- [ ] C-tier SKUs represent ~5% of cumulative sales
- [ ] Action items match those in action_items.json

---

## 🚨 Troubleshooting

### Problem: Tier counts still show 12/21/296

**Cause**: ETL hasn't run with new tier logic

**Solution**:
```bash
cd /home/ubuntu/deployment_package_final
python3 etl_comprehensive_v5.py
python3 html_updater_v5.py
```

---

### Problem: Action Plan tab shows "Loading action items..."

**Cause**: `historicalData.actions` JavaScript variable not injected

**Solution**:
```bash
# Check if action_items.json exists
ls -lh /home/ubuntu/dickies_output/weekly_artifacts/action_items.json

# If missing, run action generator first
python3 etl_action_generator.py

# Then run updater
python3 html_updater_v5.py
```

---

### Problem: Tokens like [[TIER_A_COUNT]] visible in dashboard

**Cause**: html_updater_v5.py hasn't run, or tokens not in HTML

**Solution**:
```bash
# Run updater
python3 html_updater_v5.py

# If still visible, check that tokens were added to index.html
grep "TIER_A_COUNT" /var/www/dickies/index.html
```

---

### Problem: Dashboard shows old data

**Cause**: Browser cache

**Solution**:
- Hard refresh: Ctrl + F5 (Windows) or Cmd + Shift + R (Mac)
- Or clear browser cache completely

---

### Problem: Permission denied when copying to /var/www/dickies/

**Cause**: File ownership/permissions

**Solution**:
```bash
sudo cp index.html /var/www/dickies/index.html
sudo chown www-data:www-data /var/www/dickies/index.html
sudo chmod 644 /var/www/dickies/index.html
```

---

## 📊 Expected Tier Distribution

After the fix, your tier distribution should follow the Pareto principle:

| Tier | SKU Count | % of Total SKUs | % of Total Sales |
|------|-----------|-----------------|------------------|
| A | ~33 (10%) | ~10% | ~70% |
| B | ~52 (16%) | ~16% | ~25% |
| C | ~234 (74%) | ~74% | ~5% |

**This is NORMAL and CORRECT!** The old 12/21/296 distribution was based on hardcoded cutoffs, not actual sales performance.

---

## 🔄 Weekly Update Process (Going Forward)

Every week when you get new data:

```bash
# 1. Upload new data files to EC2
scp WK202541*.xlsb ubuntu@dashboard.signalandscaleinsights.com:/home/ubuntu/upload/

# 2. SSH into EC2
ssh ubuntu@dashboard.signalandscaleinsights.com

# 3. Run ETL
cd /home/ubuntu/deployment_package_final
python3 etl_comprehensive_v5.py

# 4. Run HTML updater
python3 html_updater_v5.py

# 5. Verify dashboard
# Open browser, hard refresh (Ctrl+F5)
```

That's it! No manual updates needed.

---

## 📝 Files Modified

### On GitHub:
- `etl_comprehensive_v5.py` - Tier logic fix
- `html_updater_v5.py` - Action items injection
- `index.html` - Action Plan tab + tier tokens

### On EC2:
- `/home/ubuntu/deployment_package_final/etl_comprehensive_v5.py`
- `/home/ubuntu/deployment_package_final/html_updater_v5.py`
- `/var/www/dickies/index.html`

### Generated Weekly:
- `/home/ubuntu/dickies_output/weekly_artifacts/sku_master.json`
- `/home/ubuntu/dickies_output/weekly_artifacts/action_items.json`
- `/home/ubuntu/dickies_output/weekly_artifacts/seasonal_risk.json`
- `/home/ubuntu/dickies_output/weekly_artifacts/weekly_sales_summary.json`

---

## 🎓 Key Concepts

### Pareto Principle (80/20 Rule)
- **A-tier**: Top 10% of SKUs drive 70% of sales
- **B-tier**: Next 16% of SKUs drive 25% of sales
- **C-tier**: Bottom 74% of SKUs drive 5% of sales

### Why Tier Counts Changed
- **Old method**: Hardcoded cutoffs (184, 98, 35 SKUs)
- **New method**: Cumulative sales % thresholds (70%, 95%, 100%)
- **Result**: True velocity-based classification

### Action Items Structure
```json
{
  "category": "seasonal_markdown_risk" | "inventory_management",
  "priority": "high" | "medium" | "low",
  "action": {
    "target_id": "SKU or Fineline",
    "recommendation": "What to do",
    "rationale": "Why"
  },
  "expected_impact": {
    "metric": "Impact description",
    "timeframe_weeks": 4
  }
}
```

---

## ✅ Success Criteria

You'll know the deployment succeeded when:

1. ✅ Dashboard shows ~33 A-tier, ~52 B-tier, ~234 C-tier (not 12/21/296)
2. ✅ Action Plan tab displays 56 dynamic action cards
3. ✅ Filter buttons work and update card count
4. ✅ No `[[TIER_` tokens visible in dashboard
5. ✅ No JavaScript errors in browser console
6. ✅ Tier distribution matches Pareto principle (70/25/5)

---

## 📞 Support

If you encounter issues:

1. Check the Troubleshooting section above
2. Review `TIER_TOKENS_GUIDE.md` for token placement
3. Verify file paths match your EC2 setup
4. Check browser console for JavaScript errors
5. Verify JSON files exist in `/home/ubuntu/dickies_output/weekly_artifacts/`

---

## 📅 Deployment Timeline

- **Estimated Time**: 45-60 minutes
- **Recommended Time**: During off-hours (minimal user impact)
- **Rollback Plan**: Restore from backup in `/home/ubuntu/deployment_package_final/`

---

**Last Updated**: Nov 16, 2025
**Version**: 1.0
**Status**: Production Ready ✅
