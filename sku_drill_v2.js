/**
 * Size Drill-Down Logic for Hierarchical SKU Table
 * Supports 3-level hierarchy: Fineline → SKU (Style/Color) → Size (Prime Item)
 */

// WOS thresholds
const WOS_HEALTHY = 18;
const WOS_MONITOR = 23;

// State management
const expandedRows = new Set();

/**
 * Load and process SKU data from sku_master.json
 */
async function loadHierarchicalData() {
    try {
        const response = await fetch('../weekly_artifacts/sku_master.json');
        const data = await response.json();
        
        if (!data || !data.skus) {
            throw new Error('Invalid data format');
        }

        // Build hierarchical structure
        const hierarchy = buildHierarchy(data.skus);
        
        // Render the table
        renderHierarchicalTable(hierarchy);
        
    } catch (error) {
        console.error('Failed to load data:', error);
        const tbody = document.getElementById('hierarchyTableBody') || document.getElementById('tableBody');
        tbody.innerHTML = 
            '<tr><td colspan="7" class="error">Failed to load data. Please check console for details.</td></tr>';
    }
}

/**
 * Build 3-level hierarchy from flat SKU list
 */
function buildHierarchy(skus) {
    const finelines = {};
    
    // Group SKUs by fineline
    skus.forEach(sku => {
        const fl = sku.fineline || 'Unknown';
        
        if (!finelines[fl]) {
            finelines[fl] = {
                name: fl,
                skus: []
            };
        }
        
        finelines[fl].skus.push(sku);
    });
    
    // Calculate fineline aggregates
    Object.values(finelines).forEach(fl => {
        fl.totalSales = fl.skus.reduce((sum, sku) => sum + (sku.sales_dollars_ytd_ty || 0), 0);
        fl.totalInventory = fl.skus.reduce((sum, sku) => sum + (sku.inventory_dollars_lw || 0), 0);
        fl.avgWOS = fl.totalInventory > 0 && fl.totalSales > 0 ? (fl.totalInventory / (fl.totalSales / 52)) : 0;
        fl.storeCount = Math.max(...fl.skus.map(sku => (sku.prime_items || []).reduce((max, pi) => Math.max(max, pi.curr_valid_stores || 0), 0)));
    });
    
    return Object.values(finelines).sort((a, b) => b.totalSales - a.totalSales);
}

/**
 * Render the hierarchical table
 */
function renderHierarchicalTable(finelines) {
    const tbody = document.getElementById('hierarchyTableBody') || document.getElementById('tableBody');
    tbody.innerHTML = '';
    
    finelines.forEach((fineline, flIndex) => {
        // Render fineline row
        tbody.appendChild(createFinelineRow(fineline, flIndex));
        
        // Render SKU rows (initially hidden)
        fineline.skus.forEach((sku, skuIndex) => {
            tbody.appendChild(createSKURow(sku, flIndex, skuIndex));
            
            // Render size rows (initially hidden)
            const primeItems = sku.prime_items || [];
            primeItems.forEach((size, sizeIndex) => {
                tbody.appendChild(createSizeRow(size, flIndex, skuIndex, sizeIndex));
            });
        });
    });
}

/**
 * Create fineline row (Level 0)
 */
function createFinelineRow(fineline, flIndex) {
    const row = document.createElement('tr');
    row.className = 'fineline-row';
    row.dataset.level = '0';
    row.dataset.flIndex = flIndex;
    
    const hasChildren = fineline.skus.length > 0;
    const expandBtn = hasChildren ? '<span class="expand-btn" onclick="toggleFineline(' + flIndex + ')">▶</span>' : '';
    
    // For finelines, use different action text
    let action;
    if (fineline.avgWOS <= WOS_HEALTHY) {
        action = '<span class="icon-keep action-keep">KEEP</span>';
    } else if (fineline.avgWOS <= WOS_MONITOR) {
        action = '<span class="icon-monitor action-monitor">MONITOR</span>';
    } else {
        action = '<span class="icon-drop action-drop">REVIEW</span>';
    }
    
    row.innerHTML = `
        <td style="width: 50px; padding: 12px 15px;">${expandBtn}</td>
        <td style="width: 30%; padding: 12px 15px;" class="level-0">
            ${fineline.name}
            <span style="color: #666; font-weight: 400; margin-left: 8px;">(${fineline.skus.length} SKUs)</span>
        </td>
        <td style="width: 80px; padding: 12px 15px; text-align: center;"></td>
        <td style="width: 14%; padding: 12px 15px; text-align: right;">${formatCurrency(fineline.totalSales)}</td>
        <td style="width: 14%; padding: 12px 15px; text-align: right;">${formatCurrency(fineline.totalInventory)}</td>
        <td style="width: 80px; padding: 12px 15px; text-align: right;" class="${getWOSClass(fineline.avgWOS)}">${fineline.avgWOS.toFixed(1)}</td>
        <td style="width: 100px; padding: 12px 15px; text-align: right;">${fineline.storeCount.toLocaleString()}</td>
        <td style="width: 120px; padding: 12px 15px;">${action}</td>
    `;
    
    return row;
}

/**
 * Create SKU row (Level 1)
 */
function createSKURow(sku, flIndex, skuIndex) {
    const row = document.createElement('tr');
    row.className = 'sku-row hidden';
    row.dataset.level = '1';
    row.dataset.flIndex = flIndex;
    row.dataset.skuIndex = skuIndex;
    row.dataset.parentFl = flIndex;
    
    const primeItems = sku.prime_items || [];
    const hasChildren = primeItems.length > 0;
    const expandBtn = hasChildren ? '<span class="expand-btn" onclick="toggleSKU(' + flIndex + ',' + skuIndex + ')">▶</span>' : '';
    
    const sales = sku.sales_dollars_ytd_ty || 0;
    const inventory = sku.inventory_dollars_lw || 0;
    const wos = sku.wos || 0;
    const stores = (sku.prime_items || []).reduce((max, pi) => Math.max(max, pi.curr_valid_stores || 0), 0);
    
    row.innerHTML = `
        <td style="width: 50px; padding: 12px 15px;">${expandBtn}</td>
        <td style="width: 30%; padding: 12px 15px;" class="level-1">
            ${sku.sku}
            ${hasChildren ? '<span style="color: #666; font-weight: 400; margin-left: 8px;">(' + primeItems.length + ' sizes)</span>' : ''}
        </td>
        <td style="width: 80px; padding: 12px 15px; text-align: center;"><span class="tier-badge tier-${sku.tier}">${sku.tier}</span></td>
        <td style="width: 14%; padding: 12px 15px; text-align: right;">${formatCurrency(sales)}</td>
        <td style="width: 14%; padding: 12px 15px; text-align: right;">${formatCurrency(inventory)}</td>
        <td style="width: 80px; padding: 12px 15px; text-align: right;" class="${getWOSClass(wos)}">${wos.toFixed(1)}</td>
        <td style="width: 100px; padding: 12px 15px; text-align: right;">${stores.toLocaleString()}</td>
        <td style="width: 120px; padding: 12px 15px;">${getAction(wos)}</td>
    `;
    
    return row;
}

/**
 * Create size row (Level 2)
 */
function createSizeRow(size, flIndex, skuIndex, sizeIndex) {
    const row = document.createElement('tr');
    row.className = 'size-row hidden';
    row.dataset.level = '2';
    row.dataset.flIndex = flIndex;
    row.dataset.skuIndex = skuIndex;
    row.dataset.sizeIndex = sizeIndex;
    row.dataset.parentSku = `${flIndex}-${skuIndex}`;
    
    const sales = (size.lw_pos_qty || 0) * (size.unit_retail || 0) * 52; // Weekly to annual
    const inventory = size.lw_inv_retail || 0;
    const wos = size.wos || 0;
    const stores = size.curr_valid_stores || 0;
    
    row.innerHTML = `
        <td style="width: 50px; padding: 12px 15px;"></td>
        <td style="width: 30%; padding: 12px 15px;" class="level-2">${size.size}</td>
        <td style="width: 80px; padding: 12px 15px; text-align: center;"></td>
        <td style="width: 14%; padding: 12px 15px; text-align: right;">${formatCurrency(sales)}</td>
        <td style="width: 14%; padding: 12px 15px; text-align: right;">${formatCurrency(inventory)}</td>
        <td style="width: 80px; padding: 12px 15px; text-align: right;" class="${getWOSClass(wos)}">${wos.toFixed(1)}</td>
        <td style="width: 100px; padding: 12px 15px; text-align: right;">${stores.toLocaleString()}</td>
        <td style="width: 120px; padding: 12px 15px;" class="${getActionClass(wos)}">${getAction(wos)}</td>
    `;
    
    return row;
}

/**
 * Toggle fineline expansion
 */
function toggleFineline(flIndex) {
    const isExpanded = expandedRows.has(`fl-${flIndex}`);
    const skuRows = document.querySelectorAll(`tr[data-parent-fl="${flIndex}"]`);
    const expandBtn = document.querySelector(`tr[data-fl-index="${flIndex}"] .expand-btn`);
    
    if (isExpanded) {
        // Collapse
        expandedRows.delete(`fl-${flIndex}`);
        skuRows.forEach(row => row.classList.add('hidden'));
        expandBtn.textContent = '▶';
        expandBtn.classList.remove('expanded');
        
        // Also collapse all child SKUs
        skuRows.forEach(row => {
            const skuIndex = row.dataset.skuIndex;
            if (skuIndex !== undefined) {
                expandedRows.delete(`sku-${flIndex}-${skuIndex}`);
                const sizeRows = document.querySelectorAll(`tr[data-parent-sku="${flIndex}-${skuIndex}"]`);
                sizeRows.forEach(sizeRow => sizeRow.classList.add('hidden'));
            }
        });
    } else {
        // Expand
        expandedRows.add(`fl-${flIndex}`);
        skuRows.forEach(row => row.classList.remove('hidden'));
        expandBtn.textContent = '▼';
        expandBtn.classList.add('expanded');
    }
}

/**
 * Toggle SKU expansion
 */
function toggleSKU(flIndex, skuIndex) {
    const key = `sku-${flIndex}-${skuIndex}`;
    const isExpanded = expandedRows.has(key);
    const sizeRows = document.querySelectorAll(`tr[data-parent-sku="${flIndex}-${skuIndex}"]`);
    const expandBtn = document.querySelector(`tr[data-fl-index="${flIndex}"][data-sku-index="${skuIndex}"] .expand-btn`);
    
    if (isExpanded) {
        // Collapse
        expandedRows.delete(key);
        sizeRows.forEach(row => row.classList.add('hidden'));
        expandBtn.textContent = '▶';
        expandBtn.classList.remove('expanded');
    } else {
        // Expand
        expandedRows.add(key);
        sizeRows.forEach(row => row.classList.remove('hidden'));
        expandBtn.textContent = '▼';
        expandBtn.classList.add('expanded');
    }
}

/**
 * Get WOS CSS class
 */
function getWOSClass(wos) {
    if (wos <= WOS_HEALTHY) return 'wos-healthy';
    if (wos <= WOS_MONITOR) return 'wos-monitor';
    return 'wos-dead';
}

/**
 * Get action recommendation
 */
function getAction(wos) {
    if (wos <= WOS_HEALTHY) return '<span class="icon-keep action-keep">KEEP</span>';
    if (wos <= WOS_MONITOR) return '<span class="icon-monitor action-monitor">MONITOR</span>';
    return '<span class="icon-drop action-drop">DROP</span>';
}

/**
 * Get action CSS class
 */
function getActionClass(wos) {
    if (wos <= WOS_HEALTHY) return 'action-keep';
    if (wos <= WOS_MONITOR) return 'action-monitor';
    return 'action-drop';
}

/**
 * Format currency
 */
function formatCurrency(value) {
    if (value === 0) return '$0';
    return '$' + Math.round(value).toLocaleString();
}
