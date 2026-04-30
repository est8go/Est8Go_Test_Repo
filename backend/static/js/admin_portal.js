/**
 * Est8Go Super Admin - Modular Logic Engine
 */
const AdminPortal = (() => {
    const CONFIG = {
        HEADERS: {
            'X-Tenant-Id': '1' // 'Authorization': `Bearer ${localStorage.getItem('access_token')}` 
        },

        ENDPOINTS: {
            stats: '/listings/admin/system-stats',
            listings: '/listings/admin/trust-monitor',
            tenants: '/listings/admin/tenants-list',
            verify: '/listings/admin/verify/' // 🔹 SOCKET: Add this
        }
    };

    const init = () => {
        // 🔒 COMMENTED FOR TESTING
        /*
        const token = localStorage.getItem('access_token');
        if (!token) { window.location.href = '/public/login'; return; }
        */
        refreshData();
    };

    const switchTab = (tabName) => {
        // 1. Hide all tabs
        document.querySelectorAll('.tab-content').forEach(t => t.classList.add('hidden'));
        // 2. Show target tab
        document.getElementById(`tab-${tabName}`).classList.remove('hidden');
        // 3. Update Title
        document.getElementById('currentTabTitle').innerText = tabName.replace('-', ' ');
        // 4. Update Nav styling
        document.querySelectorAll('aside nav button').forEach(b => b.classList.remove('sidebar-active'));
        document.getElementById(`btn-${tabName}`).classList.add('sidebar-active');

        refreshData();
    };

    const refreshData = async () => {
        await loadStats();
        await loadListings();
        await loadTenants();
    };

    const loadStats = async () => {
        const res = await fetch(CONFIG.ENDPOINTS.stats, { headers: CONFIG.HEADERS });
        const data = await res.json();
        if (data.total_listings !== undefined) {
            document.getElementById('stat-listings').innerText = data.total_listings;
            document.getElementById('stat-tenants').innerText = data.total_tenants;
            document.getElementById('stat-users').innerText = data.total_users;
            document.getElementById('stat-pending').innerText = data.pending_verifications;
        }
    };

    const loadListings = async () => {
        const res = await fetch(CONFIG.ENDPOINTS.listings, { headers: CONFIG.HEADERS });
        const data = await res.json();
        const body = document.getElementById('listingsTableBody');

        body.innerHTML = data.map(item => `
            <tr class="border-b border-slate-100 hover:bg-blue-50 transition">
                <td class="p-4">
                    <p class="font-bold text-slate-800 text-sm">${item.title}</p>
                    <p class="text-[9px] text-slate-400 font-bold uppercase">${item.location}</p>
                </td>
                <td class="p-4 text-xs font-semibold text-slate-600">${item.realtor}</td>
                <td class="p-4 text-center">
                    <span class="px-3 py-1 rounded-full text-[9px] font-black bg-${item.status_color}-100 text-${item.status_color}-700">
                        ${item.trust_score}%
                    </span>
               <td class="p-4 text-right">
                    ${item.status_color === 'green'
                ? '<span class="text-[10px] font-black text-emerald-600">LIVE ✅</span>'
                : `<button onclick="AdminPortal.verifyListing('${item.id}')" class="text-[10px] font-black text-white bg-blue-600 px-3 py-1 rounded-lg uppercase shadow-md hover:bg-blue-700 transition">Verify Listing</button>`
            }
                </td>
            </tr>
        `).join('');
    };

    const loadTenants = async () => {
        const res = await fetch(CONFIG.ENDPOINTS.tenants, { headers: CONFIG.HEADERS });
        const data = await res.json();
        const grid = document.getElementById('tenantGrid');
        grid.innerHTML = data.map(t => `
            <div class="bg-white p-6 rounded-[2rem] shadow-sm border border-slate-200">
                <div class="w-12 h-12 bg-slate-100 rounded-2xl flex items-center justify-center mb-4 text-slate-800 font-black">
                    ${t.name.charAt(0)}
                </div>
                <h4 class="font-black text-slate-800">${t.name}</h4>
                <p class="text-[10px] text-slate-400 font-bold uppercase mb-4">Plan: ${t.plan}</p>
                <div class="flex gap-2">
                    <button class="flex-1 bg-slate-900 text-white text-[9px] font-black py-2 rounded-xl uppercase">Edit</button>
                    <button class="flex-1 bg-red-50 text-red-600 text-[9px] font-black py-2 rounded-xl uppercase">Suspend</button>
                </div>
            </div>
        `).join('');
    };

    const verifyListing = async (id) => {
        if (!confirm("Are you sure? This will make the listing visible to all WhatsApp users.")) return;

        try {
            const res = await fetch(CONFIG.ENDPOINTS.verify + id, {
                method: 'PATCH',
                headers: { 'X-Tenant-Id': '1' }
            });
            if (res.ok) {
                alert("✅ Listing Verified Successfully!");
                refreshData(); // Reload the table
            }
        } catch (err) { console.error("Verification failed:", err); }
    };

    window.AdminPortal = { switchTab, refreshData, verifyListing };
    return { init };
})();

document.addEventListener('DOMContentLoaded', AdminPortal.init);