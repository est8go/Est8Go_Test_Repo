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
            verify: '/listings/admin/verify/',
            delete: '/listings/admin/delete/'
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
        try {
            const res = await fetch(CONFIG.ENDPOINTS.listings, { headers: CONFIG.HEADERS });
            const data = await res.json();
            const body = document.getElementById('listingsTableBody');

            // 🔹 THE SYNTAX-CLEAN TABLE MAPPING
            const colorMap = {
                'emerald': 'bg-emerald-100 text-emerald-700 border-emerald-200',
                'blue': 'bg-blue-100 text-blue-700 border-blue-200',
                'amber': 'bg-amber-100 text-amber-700 border-amber-200',
                'rose': 'bg-rose-100 text-rose-700 border-rose-200'
            };

            body.innerHTML = data.map(item => {
                const activeClass = colorMap[item.status_color] || colorMap['rose'];

                return `
                <tr class="border-b border-slate-100 hover:bg-slate-50 transition">
                    <td class="p-4">
                        <p class="font-bold text-slate-800 text-sm">${item.title}</p>
                        <p class="text-[9px] text-slate-400 font-black uppercase">${item.location}</p>
                    </td>
                    <td class="p-4 text-xs font-semibold text-slate-500">${item.realtor}</td>
                    <td class="p-4 text-center">
                        <span class="px-3 py-1 rounded-full text-[9px] font-black uppercase border ${activeClass}">
                            ${item.trust_score}%
                        </span>
                    </td>
                    <td class="p-4 text-right">
                        <div class="flex flex-col items-end gap-1">
                            ${item.status === 'verified'
                        ? '<span class="text-[10px] font-black text-emerald-600 bg-emerald-50 px-2 py-1 rounded-md">AUTHORIZED ✅</span>'
                        : `<button onclick="AdminPortal.verifyListing('${item.id}')" class="bg-blue-600 text-white text-[9px] font-black px-3 py-1.5 rounded-lg shadow-md uppercase">Verify</button>`
                    }
                            <button onclick="AdminPortal.deleteListing('${item.id}')" class="text-[8px] font-bold text-rose-400 hover:text-rose-600 uppercase transition mt-1">
                                 Remove
                            </button>
                        </div>
                    </td>
                </tr>`;
            }).join('');
        } catch (err) {
            console.error("Failed to load listings:", err);
        }
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
    const deleteListing = async (id) => {
        if (!confirm("🚨 PERMANENT: Is this property sold or fake? This cannot be undone.")) return;
        try {
            const res = await fetch('/listings/admin/delete/' + id, {
                method: 'DELETE',
                headers: { 'X-Tenant-Id': '1' }
            });
            if (res.ok) {
                alert("🗑️ Listing Removed.");
                refreshData();
            }
        } catch (err) { console.error("Delete failed:", err); }
    };

    window.AdminPortal = { switchTab, refreshData, verifyListing, deleteListing };
    return { init };
})();

document.addEventListener('DOMContentLoaded', AdminPortal.init);