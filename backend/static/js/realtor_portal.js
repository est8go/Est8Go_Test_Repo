/**
 * Est8Go Realtor Portal - Master Logic Engine
 */

const RealtorPortal = (() => {
    const CONFIG = {
        TENANT_ID: "1",
        ENDPOINTS: {
            leads: '/conversations/realtor/leads',
            takeover: '/conversations/takeover/'
        }
    };

    const init = () => {
        console.log("🚀 Est8Go Portal Active");
        bindEvents();
        loadLeads();
        setInterval(loadLeads, 15000);
    };

    const bindEvents = () => {
        document.getElementById('addPropTrigger')?.addEventListener('click', () => alert("Property Upload coming in Stage B Part 2!"));
    };

    const loadLeads = async () => {
        try {
            const response = await fetch(CONFIG.ENDPOINTS.leads, {
                headers: { 'X-Tenant-Id': CONFIG.TENANT_ID }
            });
            const data = await response.json();

            document.getElementById('statCount').innerText = data.length;
            document.getElementById('statHot').innerText = data.filter(l => l.status === 'HOT LEAD').length;

            renderUI(data);
        } catch (err) { console.error("Sync Error:", err); }
    };

    const renderUI = (leads) => {
        const list = document.getElementById('leadList');
        let html = "";

        leads.forEach(lead => {
            const name = lead.name || "Guest";
            const lastActive = lead.last_active || "Active";
            const prefs = lead.prefs || {};
            const loc = (prefs.location && prefs.location !== "undefined") ? prefs.location : "Exploring";
            const budget = (prefs.budget && !isNaN(prefs.budget)) ? '₦' + Number(prefs.budget).toLocaleString() : "Negotiable";

            const isHot = lead.status === 'HOT LEAD';
            const botLabel = lead.is_bot_active ? 'Silence AI' : 'Controlled';
            const botClass = lead.is_bot_active ? 'bg-slate-900' : 'bg-emerald-500';

            html += `
            <div class="bg-white p-6 rounded-[2.2rem] shadow-sm border border-slate-100 overflow-hidden w-full mb-4 relative">
                ${isHot ? '<div class="absolute top-0 right-0 bg-orange-500 text-white text-[8px] font-black px-4 py-1 rounded-bl-2xl uppercase tracking-widest">Hot</div>' : ''}
                
                <div class="flex items-center gap-4 mb-5">
                    <div class="w-12 h-12 shrink-0 premium-gradient rounded-2xl flex items-center justify-center text-white font-black shadow-lg">
                        ${name.charAt(0)}
                    </div>
                    <div class="min-w-0 flex-1">
                        <h3 class="text-sm font-black text-slate-800 force-truncate">${name}</h3>
                        <p class="text-[10px] text-slate-400 font-bold uppercase">${lastActive}</p>
                    </div>
                </div>

                <div class="bg-slate-50 rounded-2xl p-4 mb-5 border border-slate-100">
                    <table style="width: 100%; table-layout: fixed;">
                        <tr>
                            <td style="width: 50%; border-right: 1px solid #e2e8f0; padding-right: 8px; overflow: hidden;">
                                <p class="text-[8px] font-black text-slate-400 uppercase mb-0.5">Searching</p>
                                <p class="text-[11px] font-bold text-indigo-900 force-truncate">${loc}</p>
                            </td>
                            <td style="width: 50%; padding-left: 8px; overflow: hidden;">
                                <p class="text-[8px] font-black text-slate-400 uppercase mb-0.5 text-right">Budget</p>
                                <p class="text-[11px] font-black text-emerald-600 text-right force-truncate">${budget}</p>
                            </td>
                        </tr>
                    </table>
                </div>

                <div class="flex gap-2">
                    <a href="tel:${lead.phone}" class="flex-1 bg-indigo-50 text-indigo-600 py-4 rounded-2xl text-center active:scale-95 transition">
                        <i class="fa-solid fa-phone"></i>
                    </a>
                    <a href="https://wa.me/${lead.phone}" class="flex-1 bg-emerald-50 text-emerald-600 py-4 rounded-2xl text-center active:scale-95 transition">
                        <i class="fa-brands fa-whatsapp text-xl"></i>
                    </a>
                    <button onclick="window.takeoverChat('${lead.phone}')" class="flex-[1.8] ${botClass} text-white text-[10px] font-black py-4 rounded-2xl uppercase shadow-md active:scale-95 transition">
                        ${botLabel}
                    </button>
                </div>
            </div>`;
        });
        list.innerHTML = html || '<div class="text-center py-20 text-slate-300 font-bold">Waiting for leads...</div>';
    };

    // 🔹 THE BRIDGE: Exposed to the window so HTML can see it
    window.takeoverChat = async (phone) => {
        if (!confirm("Ready to handle this personally? AI will stop responding.")) return;
        const res = await fetch(CONFIG.ENDPOINTS.takeover + phone, {
            method: 'POST',
            headers: { 'X-Tenant-Id': CONFIG.TENANT_ID }
        });
        if (res.ok) loadLeads();
    };

    return { init };
})();

document.addEventListener('DOMContentLoaded', RealtorPortal.init);