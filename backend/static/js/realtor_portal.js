/**
 * Est8Go Realtor Portal - Modular Logic Engine
 * Premium Version with Action Buttons Restored
 */

const RealtorPortal = (() => {
    const CONFIG = {
        TENANT_ID: "1",
        ENDPOINTS: {
            leads: '/conversations/realtor/leads',
            takeover: '/conversations/takeover/',
            upload: '/listings/realtor/upload'
        }
    };

    const init = () => {
        console.log("🚀 Est8Go Portal Active");
        bindEvents();
        loadLeads();
        setInterval(loadLeads, 20000);
    };

    const bindEvents = () => {
        document.getElementById('addPropTrigger')?.addEventListener('click', () => {
            document.getElementById('uploadModal')?.classList.remove('hidden');
        });
        document.getElementById('closeModal')?.addEventListener('click', () => {
            document.getElementById('uploadModal')?.classList.add('hidden');
        });
        document.getElementById('gpsBtn')?.addEventListener('click', captureLocation);
        document.getElementById('uploadForm')?.addEventListener('submit', handleUpload);
    };

    const captureLocation = () => {
        const btn = document.getElementById('gpsBtn');
        if (!navigator.geolocation) return alert("GPS not supported");
        btn.innerHTML = "🛰️ Verifying Site...";
        navigator.geolocation.getCurrentPosition((pos) => {
            document.getElementById('latitude').value = pos.coords.latitude;
            document.getElementById('longitude').value = pos.coords.longitude;
            btn.classList.replace('bg-emerald-500', 'bg-blue-600');
            btn.innerHTML = "✅ Site Verified";
        });
    };

    const loadLeads = async () => {
        try {
            const response = await fetch(CONFIG.ENDPOINTS.leads, {
                headers: { 'X-Tenant-Id': CONFIG.TENANT_ID }
            });
            const leads = await response.json();

            // Update Stats
            document.getElementById('statCount').innerText = leads.length;
            document.getElementById('statHot').innerText = leads.filter(l => l.status === 'HOT LEAD').length;

            renderLeads(leads);
        } catch (err) {
            console.error("Sync Error:", err);
        }
    };

    const renderLeads = (leads) => {
        const list = document.getElementById('leadList');
        if (!list) return;

        let html = "";
        leads.forEach(lead => {
            const name = lead.name || "Guest User";
            const lastActive = lead.last_active || "Active";
            const prefs = lead.prefs || {};
            const loc = (prefs.location && prefs.location !== "undefined") ? prefs.location : "General";
            const budget = (prefs.budget && !isNaN(prefs.budget)) ? '₦' + Number(prefs.budget).toLocaleString() : "Negotiable";

            const isHot = lead.status === 'HOT LEAD';
            const botLabel = lead.is_bot_active ? 'Takeover' : 'Active';
            const botClass = lead.is_bot_active ? 'bg-slate-900' : 'bg-emerald-500';

            html += `
            <div class="bg-white p-5 rounded-[2.2rem] shadow-sm border border-slate-100 overflow-hidden w-full mb-4">
                <div class="flex items-center gap-3 mb-4">
                    <div class="w-11 h-11 shrink-0 premium-gradient rounded-xl flex items-center justify-center text-white font-black">
                        ${name.charAt(0)}
                    </div>
                    <div class="min-w-0 flex-1">
                        <h3 class="text-sm font-black text-slate-800 truncate">${name}</h3>
                        <p class="text-[9px] text-slate-400 font-bold uppercase">${lastActive}</p>
                    </div>
                    ${isHot ? '<span class="bg-orange-100 text-orange-600 text-[8px] font-black px-2 py-1 rounded-md uppercase">Hot</span>' : ''}
                </div>

                <div class="bg-slate-50 rounded-2xl p-3 mb-4 border border-slate-100">
                    <div class="flex w-full text-left" style="display: table; table-layout: fixed; width: 100%;">
                        <div style="display: table-cell;" class="w-1/2 border-r border-slate-200 pr-2 overflow-hidden">
                            <p class="text-[7px] font-black text-slate-400 uppercase mb-0.5">Searching</p>
                            <p class="text-[10px] font-bold text-indigo-900 truncate">${loc}</p>
                        </div>
                        <div style="display: table-cell;" class="w-1/2 pl-2 overflow-hidden">
                            <p class="text-[7px] font-black text-slate-400 uppercase mb-0.5 text-right">Budget</p>
                            <p class="text-[10px] font-black text-emerald-600 text-right truncate">${budget}</p>
                        </div>
                    </div>
                </div>

                <!-- RESTORED ACTION BUTTONS -->
                <div class="flex gap-2">
                    <a href="tel:${lead.phone}" class="flex-1 bg-indigo-50 text-indigo-600 py-3 rounded-xl text-center active:scale-95 transition">
                        <i class="fa-solid fa-phone text-xs"></i>
                    </a>
                    <a href="https://wa.me/${lead.phone}" class="flex-1 bg-emerald-50 text-emerald-600 py-3 rounded-xl text-center active:scale-95 transition">
                        <i class="fa-brands fa-whatsapp text-sm"></i>
                    </a>
                    <button onclick="RealtorPortal.takeover('${lead.phone}')" class="flex-[1.5] ${botClass} text-white text-[9px] font-black py-3 rounded-xl uppercase active:scale-95 transition shadow-md">
                        ${botLabel}
                    </button>
                </div>
            </div>`;
        });
        list.innerHTML = html || '<div class="text-center py-20 text-slate-300 font-bold">No leads found.</div>';
    };

    const takeover = async (phone) => {
        if (!confirm("Ready to handle this client personally? The AI will stop responding.")) return;
        const res = await fetch(CONFIG.ENDPOINTS.takeover + phone, {
            method: 'POST',
            headers: { 'X-Tenant-Id': CONFIG.TENANT_ID }
        });
        if (res.ok) loadLeads();
    };

    const handleUpload = async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        if (!document.getElementById('latitude').value) return alert("Capture GPS first!");

        const res = await fetch(CONFIG.ENDPOINTS.upload, {
            method: 'POST',
            headers: { 'X-Tenant-Id': CONFIG.TENANT_ID },
            body: formData
        });
        if (res.ok) {
            alert("🎉 Published Successfully!");
            location.reload();
        }
    };

    // 🔹 CRITICAL: Expose functions for HTML buttons to see them
    return { init, takeover };
})();

document.addEventListener('DOMContentLoaded', RealtorPortal.init);