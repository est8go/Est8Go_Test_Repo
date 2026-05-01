/**
 * EST8GO EXECUTIVE COMMAND ENGINE (v2.0.0)
 * Logic: Pulse Management, Truth Scorecards, and Cross-Realtor Referrals.
 */

const RealtorPortal = (() => {
    const CONFIG = {
        TENANT_ID: new URLSearchParams(window.location.search).get('tenant_id') || "1",
        ENDPOINTS: {
            leads: '/conversations/realtor/leads',
            props: '/listings/',
            takeover: '/conversations/takeover/',
            upload: '/listings/realtor/upload'
        }
    };

    const init = () => {
        bindEvents();
        switchTab('pulse'); // Default tab
        // Sync stats globally
        setInterval(loadPulse, 20000);
    };

    const bindEvents = () => {
        document.getElementById('addPropTrigger')?.addEventListener('click', () => document.getElementById('uploadModal').classList.remove('hidden'));
        document.getElementById('closeModal')?.addEventListener('click', () => document.getElementById('uploadModal').classList.add('hidden'));
        document.getElementById('gpsBtn')?.addEventListener('click', captureLocation);
        document.getElementById('uploadForm')?.addEventListener('submit', handleUpload);
    };

    const switchTab = (tabName) => {
        // 1. Toggle Sections
        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
        document.getElementById(`tab-${tabName}`).classList.add('active');

        // 2. Toggle Nav Icons
        document.querySelectorAll('.glass-dock button').forEach(btn => btn.classList.remove('nav-active', 'text-slate-400'));
        document.getElementById(`nav-${tabName}`).classList.add('nav-active');

        // 3. Load Specific Data
        if (tabName === 'pulse') loadPulse();
        if (tabName === 'vault') loadVault();
        if (tabName === 'network') loadNetwork();
    };

    const loadPulse = async () => {
        const res = await fetch(CONFIG.ENDPOINTS.leads, { headers: { 'X-Tenant-Id': CONFIG.TENANT_ID } });
        const data = await res.json();
        document.getElementById('statCount').innerText = data.length;
        renderLeads(data);
    };

    const loadVault = async () => {
        const res = await fetch(CONFIG.ENDPOINTS.props, { headers: { 'X-Tenant-Id': CONFIG.TENANT_ID } });
        const props = await res.json();
        const list = document.getElementById('inventoryList');

        list.innerHTML = props.map(p => {
            const score = p.trust_score || 65;
            const color = score >= 85 ? 'emerald' : score >= 60 ? 'blue' : 'amber';

            return `
            <div class="bg-white p-6 rounded-[2.5rem] shadow-sm border border-slate-100">
                <div class="flex justify-between items-start mb-4">
                    <div class="min-w-0 flex-1">
                        <h3 class="text-sm font-black text-slate-800 force-truncate">${p.title}</h3>
                        <p class="text-[9px] text-slate-400 font-bold uppercase">${p.location} | ₦${p.price.toLocaleString()}</p>
                    </div>
                    <div class="text-right">
                        <div class="text-lg font-black text-${color}-600">${score}%</div>
                        <div class="text-[8px] font-black uppercase text-slate-300">Truth Score</div>
                    </div>
                </div>
                <div class="flex gap-2">
                    <button class="flex-1 bg-slate-900 text-white text-[9px] font-black py-3 rounded-xl uppercase">Edit Media</button>
                    <button class="flex-1 bg-rose-50 text-rose-600 text-[9px] font-black py-3 rounded-xl uppercase">Mark Sold</button>
                </div>
            </div>`;
        }).join('');
    };

    const loadNetwork = () => {
        document.getElementById('networkList').innerHTML = `
            <div class="bg-white/50 p-4 rounded-2xl flex justify-between items-center">
                <p class="text-xs font-bold text-slate-700">Maitama Partner Share</p>
                <span class="text-[10px] font-black text-emerald-600">5% SPLIT</span>
            </div>
        `;
    };

    const renderLeads = (leads) => {
        const list = document.getElementById('leadList');
        let html = "";
        leads.forEach(lead => {
            // 🔹 1. SOCKET: Channel Icon Logic
            const channelIcon = lead.channel === 'instagram'
                ? '<i class="fa-brands fa-instagram text-pink-500"></i>'
                : lead.channel === 'facebook'
                    ? '<i class="fa-brands fa-facebook text-blue-600"></i>'
                    : '<i class="fa-brands fa-whatsapp text-emerald-500"></i>';

            const prefs = lead.prefs || {};
            const loc = (prefs.location && String(prefs.location) !== "undefined") ? prefs.location : "General";

            html += `
            <div class="bg-white p-6 rounded-[2.5rem] shadow-sm border border-slate-100 mb-4">
                <div class="flex items-center gap-4 mb-4">
                    
                    <!-- 🔹 2. SOCKET: Relative Avatar with Channel Badge -->
                    <div class="relative">
                        <div class="w-12 h-12 premium-indigo rounded-2xl flex items-center justify-center text-white font-black shadow-lg">
                            ${lead.name.charAt(0)}
                        </div>
                        <div class="absolute -bottom-1 -right-1 bg-white w-5 h-5 rounded-full flex items-center justify-center shadow-sm border border-slate-100" style="font-size: 10px;">
                            ${channelIcon}
                        </div>
                    </div>

                    <div class="min-w-0 flex-1">
                        <h4 class="text-sm font-black text-slate-800 truncate">${lead.name}</h4>
                        <p class="text-[9px] text-slate-400 font-bold">${lead.last_active} | Searching ${loc}</p>
                    </div>
                </div>
                <div class="flex gap-2">
                    <a href="tel:${lead.phone}" class="flex-1 bg-indigo-50 text-indigo-600 py-3 rounded-xl text-center active:scale-95 transition">
                        <i class="fa-solid fa-phone"></i>
                    </a>
                    <button onclick="window.RealtorPortal.takeover('${lead.phone}')" class="flex-[2] bg-slate-900 text-white text-[9px] font-black py-3 rounded-xl uppercase active:scale-95 transition">
                        Takeover
                    </button>
                </div>
            </div>`;
        });
        list.innerHTML = html;
    };

    // --- RE-USE PREVIOUS GPS AND UPLOAD LOGIC HERE ---
    const captureLocation = () => { /* ... existing capture logic ... */ };
    const handleUpload = async (e) => { /* ... existing authenticated upload logic ... */ };
    const takeover = async (phone) => { /* ... existing takeover logic ... */ };

    return { init, switchTab, takeover };
})();

document.addEventListener('DOMContentLoaded', RealtorPortal.init);
window.RealtorPortal = RealtorPortal;