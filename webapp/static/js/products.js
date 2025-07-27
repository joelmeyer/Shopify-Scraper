let products = [];
let filtered = [];
let sortKey = 'id';
let sortAsc = true;
const perPage = 50;
const backendChunkSize = 5000;
let currentPage = 1;
let totalPages = 1;
let totalRecords = 0;
let allDataLoaded = false;

async function fetchProducts(page = 1, append = false) {
    document.getElementById('loading').style.display = '';
    document.getElementById('errorMsg').style.display = 'none';
    try {
        const chunkPage = Math.floor((products.length) / backendChunkSize) + 1;
        const res = await fetch(`/api/products?page=${chunkPage}&per_page=${backendChunkSize}`);
        if (!res.ok) throw new Error('Failed to fetch products');
        const data = await res.json();
        if (append) {
            products = products.concat(data.products);
        } else {
            products = data.products;
        }
        filtered = [...products];
        totalRecords = data.total;
        totalPages = Math.ceil(totalRecords / perPage) || 1;
        if (products.length < totalRecords) {
            // Continue loading next chunk in background
            fetchProducts(page, true).then(() => {
                populateFilters();
                filterTable();
            });
        } else {
            allDataLoaded = true;
        }
        populateFilters();
        filterTable();
    } catch (err) {
        document.getElementById('errorMsg').textContent = err.message;
        document.getElementById('errorMsg').style.display = '';
    } finally {
        document.getElementById('loading').style.display = 'none';
    }
}

function computeStats(list) {
    const total = list.length;
    const available = list.filter(p => p.available).length;
    const vendors = [...new Set(list.map(p => p.vendor).filter(Boolean))];
    const alcoholTypes = {};
    list.forEach(p => {
        if (p.alcohol_type) alcoholTypes[p.alcohol_type] = (alcoholTypes[p.alcohol_type]||0)+1;
    });
    const prices = list.map(p => parseFloat(p.price)).filter(x => !isNaN(x));
    const minPrice = prices.length ? Math.min(...prices) : null;
    const maxPrice = prices.length ? Math.max(...prices) : null;
    const avgPrice = prices.length ? (prices.reduce((a,b)=>a+b,0)/prices.length) : null;
    const vendorCounts = {};
    list.forEach(p => { if (p.vendor) vendorCounts[p.vendor]=(vendorCounts[p.vendor]||0)+1; });
    const mostPopularVendors = Object.entries(vendorCounts).sort((a,b)=>b[1]-a[1]).slice(0,3);
    const lastUpdated = list.length ? list.map(p => p.updated_at).filter(Boolean).sort().reverse()[0] : null;
    return {
        total, available, vendors, alcoholTypes, minPrice, maxPrice, avgPrice, mostPopularVendors, lastUpdated
    };
}

function renderStatsPanel() {
    const stats = computeStats(filtered);
    const allStats = computeStats(products);
    let html = '';
    html += `<div><b>Total Products:</b> ${allStats.total}</div>`;
    html += `<div><b>Available:</b> ${allStats.available}</div>`;
    html += `<div><b>Unique Vendors:</b> ${allStats.vendors.length}</div>`;
    html += `<div><b>Last Updated:</b> ${allStats.lastUpdated ? formatDate(allStats.lastUpdated) : '-'}</div>`;
    html += `<div><b>Alcohol Types:</b> ` + Object.entries(allStats.alcoholTypes).map(([k,v])=>`${k} (${v})`).join(', ') + `</div>`;
    html += `<div><b>Price:</b> Min ${allStats.minPrice!==null?allStats.minPrice.toFixed(2):'-'}, Max ${allStats.maxPrice!==null?allStats.maxPrice.toFixed(2):'-'}, Avg ${allStats.avgPrice!==null?allStats.avgPrice.toFixed(2):'-'}</div>`;
    html += `<div><b>Top Vendors:</b> ` + (allStats.mostPopularVendors.length ? allStats.mostPopularVendors.map(([v,c])=>`${v} (${c})`).join(', ') : '-') + `</div>`;
    html += `<div><b>Showing:</b> ${filtered.length} of ${products.length} products</div>`;
    document.getElementById('statsPanel').innerHTML = html;
}

function renderTable() {
    const body = document.getElementById('productsBody');
    body.innerHTML = '';
    const start = (currentPage - 1) * perPage;
    const end = Math.min(start + perPage, filtered.length);
    for (let i = start; i < end; i++) {
        const p = filtered[i];
        const availClass = p.available ? 'availability-yes' : 'availability-no';
        const availText = p.available ? 'Yes' : 'No';
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${p.image_url ? `<img src="${p.image_url}" class="product-img">` : ''}</td>
            <td><a href="${p.url}" target="_blank">${p.title}</a></td>
            <td>${p.price || ''}</td>
            <td class="${availClass}">${availText}</td>
            <td>${p.vendor || ''}</td>
            <td>${p.alcohol_type || ''}</td>
            <td><span class="date-cell">${p.published_at || ''}</span></td>
            <td><span class="date-cell">${p.updated_at || ''}</span></td>
            <td><input type="checkbox" class="ignore-notifications-toggle" data-id="${p.id}" ${p.ignore_notifications ? 'checked' : ''}></td>
            <td>
                <button class="expand-btn" data-idx="${i}" style="background:none;border:none;font-size:18px;cursor:pointer;">▶</button>
                <button class="edit-btn" data-id="${p.id}" style="margin-left:8px;padding:4px 10px;font-size:14px;background:#2563eb;color:#fff;border:none;border-radius:4px;">Edit</button>
            </td>
        `;
        body.appendChild(row);
        // Details row (hidden by default)
        const details = document.createElement('tr');
        details.className = 'details-row';
        details.style.display = 'none';
        details.innerHTML = `<td colspan="10">
            <div style="padding:12px 18px;background:#f6f6fa;border-radius:7px;">
                <b>Input URL:</b> ${p.input_url || ''}<br>
                <b>Created At:</b> <span class="date-cell">${p.created_at || ''}</span><br>
                <b>Last Seen:</b> <span class="date-cell">${p.last_seen || ''}</span><br>
                <b>Became Available At:</b> <span class="date-cell">${p.became_available_at || ''}</span><br>
                <b>Became Unavailable At:</b> <span class="date-cell">${p.became_unavailable_at || ''}</span><br>
                <b>Date Added:</b> <span class="date-cell">${p.date_added || ''}</span><br>
                <b>Ignore Notifications:</b> <input type="checkbox" class="ignore-notifications-toggle" data-id="${p.id}" ${p.ignore_notifications ? 'checked' : ''}> <span style="font-size:13px;color:#888;">(Suppress webhook alerts for this product)</span>
            </div>
        </td>`;
        body.appendChild(details);
    }
    // Add expand/collapse logic
    document.querySelectorAll('.expand-btn').forEach(btn => {
        btn.onclick = function() {
            const idx = parseInt(btn.getAttribute('data-idx'));
            const detailsRow = body.children[(idx - start) * 2 + 1];
            if (detailsRow.style.display === 'none') {
                detailsRow.style.display = '';
                btn.textContent = '▼';
            } else {
                detailsRow.style.display = 'none';
                btn.textContent = '▶';
            }
        };
    });
    // Add ignore_notifications toggle logic
    document.querySelectorAll('.ignore-notifications-toggle').forEach(toggle => {
        toggle.onchange = async function() {
            const id = toggle.getAttribute('data-id');
            const checked = toggle.checked ? 1 : 0;
            try {
                const res = await fetch(`/api/products/${id}/ignore`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ignore_notifications: checked })
                });
                if (!res.ok) throw new Error('Failed to update ignore_notifications');
                // Update local data
                products.forEach(p => { if (p.id == id) p.ignore_notifications = checked; });
                filtered.forEach(p => { if (p.id == id) p.ignore_notifications = checked; });
            } catch (err) {
                alert('Error updating ignore_notifications: ' + err.message);
            }
        };
    });
    // Add edit modal logic
    document.querySelectorAll('.edit-btn').forEach(btn => {
        btn.onclick = function() {
            const id = btn.getAttribute('data-id');
            const product = products.find(p => p.id == id);
            if (!product) return;
            document.getElementById('editProductId').value = product.id;
            document.getElementById('editProductTitle').value = product.title || '';
            document.getElementById('editProductPrice').value = product.price || '';
            document.getElementById('editProductAvailable').value = product.available ? '1' : '0';
            document.getElementById('editProductVendor').value = product.vendor || '';
            populateEditAlcoholTypeDropdown(product.alcohol_type || 'Unwanted');
            document.getElementById('editProductIgnoreNotifications').checked = !!product.ignore_notifications;
            document.getElementById('editProductModal').style.display = 'block';
        };
    });
    document.getElementById('closeEditModal').onclick = function() {
        document.getElementById('editProductModal').style.display = 'none';
    };
    document.getElementById('cancelEditModal').onclick = function() {
        document.getElementById('editProductModal').style.display = 'none';
    };
    document.getElementById('editProductForm').onsubmit = async function(e) {
        e.preventDefault();
        const id = document.getElementById('editProductId').value;
        const title = document.getElementById('editProductTitle').value;
        const price = document.getElementById('editProductPrice').value;
        const available = document.getElementById('editProductAvailable').value;
        const vendor = document.getElementById('editProductVendor').value;
        const alcohol_type = document.getElementById('editProductAlcoholType').value;
        const ignore_notifications = document.getElementById('editProductIgnoreNotifications').checked ? 1 : 0;
        try {
            const res = await fetch(`/products/${id}/edit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `title=${encodeURIComponent(title)}&price=${encodeURIComponent(price)}&available=${encodeURIComponent(available)}&vendor=${encodeURIComponent(vendor)}&alcohol_type=${encodeURIComponent(alcohol_type)}&ignore_notifications=${encodeURIComponent(ignore_notifications)}`
            });
            if (!res.ok) throw new Error('Failed to update product');
            document.getElementById('editProductModal').style.display = 'none';
            // Update product in local arrays
            [products, filtered].forEach(arr => {
                const idx = arr.findIndex(p => p.id == id);
                if (idx !== -1) {
                    arr[idx] = {
                        ...arr[idx],
                        title,
                        price,
                        available: available === '1',
                        vendor,
                        alcohol_type,
                        ignore_notifications
                    };
                }
            });
            renderTable();
            renderStats();
        } catch (err) {
            alert('Error updating product: ' + err.message);
        }
    };
    // Render dates in browser timezone
    document.querySelectorAll('.date-cell').forEach(cell => {
        if (cell.textContent && !isNaN(Date.parse(cell.textContent))) {
            const d = new Date(cell.textContent);
            cell.textContent = d.toLocaleString();
        }
    });
    renderStatsPanel();
}

function renderPagination() {
    const pagDiv = document.getElementById('pagination');
    pagDiv.innerHTML = '';
    function pageBtn(p, label) {
        const el = document.createElement(p === currentPage ? 'span' : 'a');
        el.textContent = label || p;
        if (p !== currentPage) el.href = '#';
        if (p === currentPage) el.className = 'active';
        el.onclick = e => { e.preventDefault(); currentPage = p; fetchProducts(p); };
        return el;
    }
    if (currentPage > 1) {
        pagDiv.appendChild(pageBtn(1, '« First'));
        pagDiv.appendChild(pageBtn(currentPage-1, '‹ Prev'));
    }
    for (let p=1; p<=totalPages; ++p) {
        if (p === 1 || p === totalPages || Math.abs(p-currentPage)<=1) {
            pagDiv.appendChild(pageBtn(p));
        } else if ((p === 2 && currentPage > 4) || (p === totalPages-1 && currentPage < totalPages-3)) {
            const span = document.createElement('span');
            span.textContent = '...';
            pagDiv.appendChild(span);
        }
    }
    if (currentPage < totalPages) {
        pagDiv.appendChild(pageBtn(currentPage+1, 'Next ›'));
        pagDiv.appendChild(pageBtn(totalPages, 'Last »'));
    }
}

function sortTable(key) {
    if (sortKey === key) sortAsc = !sortAsc; else { sortKey = key; sortAsc = true; }
    filtered.sort((a, b) => {
        let va = a[key] || '';
        let vb = b[key] || '';
        if (key === 'price') { va = parseFloat(va)||0; vb = parseFloat(vb)||0; }
        if (va < vb) return sortAsc ? -1 : 1;
        if (va > vb) return sortAsc ? 1 : -1;
        return 0;
    });
    renderTable();
}

function filterTable() {
    const q = document.getElementById('searchInput').value.toLowerCase();
    const vendor = document.getElementById('vendorFilter').value;
    const type = document.getElementById('typeFilter').value;
    const avail = document.getElementById('availableFilter').value;
    const inputUrl = document.getElementById('inputUrlFilter').value;
    const ignore = document.getElementById('ignoreFilter').value;
    filtered = products.filter(p => {
        let match = true;
        if (q) match = (p.title && p.title.toLowerCase().includes(q)) || (p.vendor && p.vendor.toLowerCase().includes(q)) || (p.alcohol_type && p.alcohol_type.toLowerCase().includes(q));
        if (vendor && p.vendor !== vendor) match = false;
        if (type && p.alcohol_type !== type) match = false;
        if (avail && String(Number(!!p.available)) !== avail) match = false;
        if (inputUrl && p.input_url !== inputUrl) match = false;
        if (ignore !== '' && String(Number(!!p.ignore_notifications)) !== ignore) match = false;
        return match;
    });
    sortTable(sortKey);
    renderStats();
}

function resetFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('vendorFilter').value = '';
    document.getElementById('typeFilter').value = '';
    document.getElementById('availableFilter').value = '';
    document.getElementById('inputUrlFilter').value = '';
    document.getElementById('ignoreFilter').value = '';
    filterTable();
}

function populateFilters() {
    const vendors = [...new Set(products.map(p => p.vendor).filter(Boolean))].sort();
    const types = [...new Set(products.map(p => p.alcohol_type).filter(Boolean))].sort();
    const inputUrls = [...new Set(products.map(p => p.input_url).filter(Boolean))].sort();
    const vendorSel = document.getElementById('vendorFilter');
    const typeSel = document.getElementById('typeFilter');
    const inputUrlSel = document.getElementById('inputUrlFilter');
    vendorSel.innerHTML = '<option value="">All Vendors</option>';
    typeSel.innerHTML = '<option value="">All Types</option>';
    inputUrlSel.innerHTML = '<option value="">All Input URLs</option>';
    vendors.forEach(v => { const o = document.createElement('option'); o.value = v; o.textContent = v; vendorSel.appendChild(o); });
    types.forEach(t => { const o = document.createElement('option'); o.value = t; o.textContent = t; typeSel.appendChild(o); });
    inputUrls.forEach(u => { const o = document.createElement('option'); o.value = u; o.textContent = u; inputUrlSel.appendChild(o); });
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    if (isNaN(d)) return dateStr;
    return d.toLocaleString();
}

// --- State Persistence Helpers ---
const STATE_KEY = 'shopifyScraperProductsStateV2';
const PRODUCTS_KEY = 'shopifyScraperProductsDataV2';
const PRODUCTS_CACHE_TTL = 60 * 60 * 1000; // 1 hour

function saveState() {
    const state = {
        search: document.getElementById('searchInput').value,
        vendor: document.getElementById('vendorFilter').value,
        type: document.getElementById('typeFilter').value,
        avail: document.getElementById('availableFilter').value,
        inputUrl: document.getElementById('inputUrlFilter').value,
        sortKey,
        sortAsc,
        currentPage
    };
    localStorage.setItem(STATE_KEY, JSON.stringify(state));
}

function loadState() {
    const state = JSON.parse(localStorage.getItem(STATE_KEY) || '{}');
    if (state.search !== undefined) document.getElementById('searchInput').value = state.search;
    if (state.vendor !== undefined) document.getElementById('vendorFilter').value = state.vendor;
    if (state.type !== undefined) document.getElementById('typeFilter').value = state.type;
    if (state.avail !== undefined) document.getElementById('availableFilter').value = state.avail;
    if (state.inputUrl !== undefined) document.getElementById('inputUrlFilter').value = state.inputUrl;
    if (state.sortKey) sortKey = state.sortKey;
    if (state.sortAsc !== undefined) sortAsc = state.sortAsc;
    if (state.currentPage) currentPage = state.currentPage;
}

function saveProductsToCache() {
    const cache = {
        products,
        totalRecords,
        timestamp: Date.now(),
        version: 2
    };
    localStorage.setItem(PRODUCTS_KEY, JSON.stringify(cache));
}

function loadProductsFromCache() {
    const cache = JSON.parse(localStorage.getItem(PRODUCTS_KEY) || 'null');
    if (!cache || !cache.products || !cache.timestamp) return false;
    if (Date.now() - cache.timestamp > PRODUCTS_CACHE_TTL) return false;
    products = cache.products;
    totalRecords = cache.totalRecords || products.length;
    allDataLoaded = true;
    filtered = [...products];
    totalPages = Math.ceil(totalRecords / perPage) || 1;
    return true;
}

// --- Patch event handlers to save state ---
['searchInput','vendorFilter','typeFilter','availableFilter','inputUrlFilter','ignoreFilter'].forEach(id => {
    document.getElementById(id).addEventListener('change', saveState);
    document.getElementById(id).addEventListener('input', saveState);
});

// Patch sortTable and pagination to save state
const origSortTable = sortTable;
sortTable = function(key) {
    origSortTable(key);
    saveState();
};

const origRenderPagination = renderPagination;
renderPagination = function() {
    origRenderPagination();
    // Patch page buttons to save state
    document.querySelectorAll('#pagination a').forEach(a => {
        a.addEventListener('click', () => {
            saveState();
        });
    });
};

// --- Patch fetchProducts to save products to cache ---
const origFetchProducts = fetchProducts;
fetchProducts = async function(page = 1, append = false) {
    await origFetchProducts(page, append);
    if (allDataLoaded) saveProductsToCache();
};

// --- On page load, restore state and products ---
document.addEventListener('DOMContentLoaded', function() {
    let usedCache = false;
    if (loadProductsFromCache()) {
        usedCache = true;
        populateFilters();
        loadState();
        filterTable();
        renderPagination();
        renderStats();
        renderTable();
    } else {
        origFetchProducts(currentPage);
        loadState();
        renderStats();
    }
});
document.getElementById('searchInput').addEventListener('input', filterTable);
document.getElementById('vendorFilter').addEventListener('change', filterTable);
document.getElementById('typeFilter').addEventListener('change', filterTable);
document.getElementById('availableFilter').addEventListener('change', filterTable);
document.getElementById('inputUrlFilter').addEventListener('change', filterTable);
document.getElementById('ignoreFilter').addEventListener('change', filterTable);
window.onload = function() {
    fetchProducts(currentPage);
    renderStats();
};
document.getElementById('refreshBtn').onclick = async function() {
    products = [];
    filtered = [];
    allDataLoaded = false;
    await fetchProducts(1, false);
    renderTable();
    populateFilters();
    renderPagination();
    renderStats();
};
function exportCSV() {
    let csv = '';
    const headers = ['Title','Price','Available','Vendor','Alcohol Type','Published At','Updated At','Input URL'];
    csv += headers.join(',') + '\n';
    filtered.forEach(p => {
        csv += [
            '"'+(p.title||'')+'"',
            p.price||'',
            p.available ? 'Yes' : 'No',
            '"'+(p.vendor||'')+'"',
            '"'+(p.alcohol_type||'')+'"',
            p.published_at||'',
            p.updated_at||'',
            '"'+(p.input_url||'')+'"'
        ].join(',') + '\n';
    });
    const blob = new Blob([csv], {type:'text/csv'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'products.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
document.getElementById('exportBtn').onclick = exportCSV;
function renderStats() {
    // Compute stats from filtered and all products
    const total = products.length;
    const filteredCount = filtered.length;
    const available = filtered.filter(p => p.available).length;
    const totalAvailable = products.filter(p => p.available).length;
    const vendors = [...new Set(filtered.map(p => p.vendor).filter(Boolean))];
    const allVendors = [...new Set(products.map(p => p.vendor).filter(Boolean))];
    const alcoholTypes = {};
    filtered.forEach(p => {
        if (p.alcohol_type) alcoholTypes[p.alcohol_type] = (alcoholTypes[p.alcohol_type]||0)+1;
    });
    const prices = filtered.map(p => parseFloat(p.price)).filter(x => !isNaN(x));
    const minPrice = prices.length ? Math.min(...prices) : '';
    const maxPrice = prices.length ? Math.max(...prices) : '';
    const avgPrice = prices.length ? (prices.reduce((a,b)=>a+b,0)/prices.length).toFixed(2) : '';
    // Top vendors
    const vendorCounts = {};
    filtered.forEach(p => { if (p.vendor) vendorCounts[p.vendor] = (vendorCounts[p.vendor]||0)+1; });
    const topVendors = Object.entries(vendorCounts).sort((a,b)=>b[1]-a[1]).slice(0,3);
    // Last updated (most recent updated_at or last_seen)
    let lastUpdated = '';
    if (filtered.length) {
        const dates = filtered.map(p => p.updated_at || p.last_seen).filter(Boolean);
        if (dates.length) {
            lastUpdated = new Date(Math.max(...dates.map(d=>+new Date(d))));
            lastUpdated = lastUpdated.toLocaleString();
        }
    }
    // Active filters summary
    const filterSummary = [];
    if (document.getElementById('searchInput').value) filterSummary.push('Search: "'+document.getElementById('searchInput').value+'"');
    if (document.getElementById('vendorFilter').value) filterSummary.push('Vendor: '+document.getElementById('vendorFilter').value);
    if (document.getElementById('typeFilter').value) filterSummary.push('Type: '+document.getElementById('typeFilter').value);
    if (document.getElementById('availableFilter').value) filterSummary.push('Available: '+(document.getElementById('availableFilter').value==='1'?'Yes':'No'));
    if (document.getElementById('inputUrlFilter').value) filterSummary.push('Input URL: '+document.getElementById('inputUrlFilter').value);
    // Render
    let html = '';
    html += `<div><b>Total Products:</b> ${filteredCount} <span style="color:#888;font-size:13px;">/ ${total}</span></div>`;
    html += `<div><b>Available:</b> ${available} <span style="color:#888;font-size:13px;">/ ${totalAvailable}</span></div>`;
    html += `<div><b>Unique Vendors:</b> ${vendors.length} <span style="color:#888;font-size:13px;">/ ${allVendors.length}</span></div>`;
    html += `<div><b>Last Updated:</b> ${lastUpdated||'-'}</div>`;
    html += `<div><b>Alcohol Types:</b> ${Object.keys(alcoholTypes).length ? Object.entries(alcoholTypes).map(([k,v])=>`${k} (${v})`).join(', ') : '-'}</div>`;
    html += `<div><b>Price:</b> ${prices.length ? `min $${minPrice} / avg $${avgPrice} / max $${maxPrice}` : '-'}`;
    html += `<div><b>Top Vendors:</b> ${topVendors.length ? topVendors.map(([v,c])=>`${v} (${c})`).join(', ') : '-'}</div>`;
    if (filterSummary.length) html += `<div style="color:#2563eb;"><b>Active Filters:</b> ${filterSummary.join('; ')}</div>`;
    document.getElementById('statsPanel').innerHTML = html;
}

function getAvailableAlcoholTypes() {
    const types = [...new Set(products.map(p => p.alcohol_type).filter(Boolean))].sort();
    if (!types.includes('Unwanted')) types.unshift('Unwanted');
    return types;
}

function populateEditAlcoholTypeDropdown(selectedType) {
    const select = document.getElementById('editProductAlcoholType');
    select.innerHTML = '';
    getAvailableAlcoholTypes().forEach(type => {
        const opt = document.createElement('option');
        opt.value = type;
        opt.textContent = type;
        if (type === selectedType) opt.selected = true;
        select.appendChild(opt);
    });
}
