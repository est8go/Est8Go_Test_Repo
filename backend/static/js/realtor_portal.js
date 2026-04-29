/**
 * EST8GO MASTER EXECUTIVE CONTROLLER (v1.3.0)
 * Final Clean Architecture: Zero-Overflow & Undefined-Sanitized.
 */

const RealtorPortal = (() => {
    // 🔹 1. CONFIGURATION
    const CONFIG = {
        TENANT_ID: "1",
        ENDPOINTS: {
            leads: '/conversations/realtor/leads',
            takeover: '/conversations/takeover/',
            upload: '/listings/realtor/upload'
        }
    };

    // 🔹 2. INITIALIZATION
    const init = () => {
        console.log("🚀 Est8Go Portal Active");
        bindEvents();
        loadLeads();
        setInterval(loadLeads, 20000);
    };

    const bindEvents = () => {
        document.getElementById('addPropTrigger')?.addEventListener('click', () => {
            document.getElementById('uploadModal').classList.remove('hidden');
        });
        document.getElementById('closeModal')?.addEventListener('click', () => {
            document.getElementById('uploadModal').classList.add('hidden');
        });
        document.getElementById('gpsBtn')?.addEventListener('click', captureLocation);
        document.getElementById('uploadForm')?.addEventListener('submit', handleUpload);
    };

    // 🔹 3. CORE LOGIC & SANITIZATION
    const sanitize = (val, fallback) => {
        const sVal = String(val).trim().toLowerCase();
        if (!val || sVal === "undefined" || sVal === "null" || sVal === "nan") return fallback;
        return val;
    };

    const captureLocation = () => {
        const btn = document.getElementById('gpsBtn');
        if (!navigator.geolocation) return alert("GPS not supported");
        btn.innerHTML = "🛰️ Verifying...";
        navigator.geolocation.getCurrentPosition((pos) => {
            document.getElementById('latitude').value = pos.coords.latitude;
            document.getElementById('longitude').value = pos.coords.longitude;
            btn.className = "w-full bg-blue-600 text-white py-4 rounded-2xl font-black";
            btn.innerHTML = "✅ Site Verified";
        });
    };

    const loadLeads = async () => {
        try {
            const res = await fetch(CONFIG.ENDPOINTS.leads, { headers: { 'X-Tenant-Id': CONFIG.TENANT_ID } });
            const data = await res.json();
            document.getElementById('statCount').innerText = data.length;
            document.getElementById('statHot').innerText = data.filter(l => l.status === 'HOT LEAD').length;
            renderLeads(data);
        } catch (err) { console.error("Sync Error:", err); }
    };

    const renderLeads = (leads) => {
        const list = document.getElementById('leadList');
        if (!list) return;
        let html = "";

        leads.forEach(lead => {
            const prefs = lead.prefs || {};

            // Apply Sanitizer (Kills 'undefined' bug)
            const loc = sanitize(prefs.location, "Exploring");
            const rawBudget = sanitize(prefs.budget, "Negotiable");
            const displayBudget = (rawBudget !== "Negotiable") ? '₦' + Number(rawBudget).toLocaleString() : "Negotiable";

            const name = sanitize(lead.name, "Prospect");
            const lastActive = sanitize(lead.last_active, "Active");
            const botLabel = lead.is_bot_active ? 'Silence AI' : 'Active';
            const botClass = lead.is_bot_active ? 'bg-slate-900' : 'bg-emerald-500';

            html += `
            <div class="bg-white p-6 rounded-[2.2rem] shadow-sm border border-slate-100 mb-4 overflow-hidden">
                <div class="flex items-center gap-4 mb-4">
                    <div class="w-12 h-12 premium-gradient rounded-2xl flex items-center justify-center text-white font-black">${name.charAt(0)}</div>
                    <div class="min-w-0 flex-1">
                        <h3 class="text-sm font-black text-slate-800 truncate">${name}</h3>
                        <p class="text-[9px] text-slate-400 font-bold uppercase">${lastActive}</p>
                    </div>
                </div>

                <!-- 🔹 FIXED TABLE (Kills Overflow Bug) -->
                <div class="bg-slate-50 rounded-2xl p-4 mb-5 border border-slate-100" style="overflow: hidden;">
                    <table style="width: 100%; table-layout: fixed; border-collapse: collapse;">
                        <tr>
                            <td style="width: 55%; border-right: 1px solid #e2e8f0; padding-right: 10px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;">
                                <p style="font-size: 8px; font-weight: 900; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">Searching</p>
                                <span style="font-size: 11px; font-weight: 700; color: #1e1b4b;">${loc}</span>
                            </td>
                            <td style="width: 45%; padding-left: 10px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; text-align: right;">
                                <p style="font-size: 8px; font-weight: 900; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">Budget</p>
                                <span style="font-size: 11px; font-weight: 900; color: #059669;">${displayBudget}</span>
                            </td>
                        </tr>
                    </table>
                </div>

                <div class="flex gap-2">
                    <a href="tel:${lead.phone}" class="flex-1 bg-indigo-50 text-indigo-600 py-4 rounded-2xl text-center"><i class="fa-solid fa-phone"></i></a>
                    <a href="https://wa.me/${lead.phone}" class="flex-1 bg-emerald-50 text-emerald-600 py-4 rounded-2xl text-center"><i class="fa-brands fa-whatsapp text-xl"></i></a>
                    <button onclick="RealtorPortal.takeover('${lead.phone}')" class="flex-[1.8] ${botClass} text-white text-[10px] font-black py-4 rounded-2xl uppercase shadow-md">${botLabel}</button>
                </div>
            </div>`;
        });
        list.innerHTML = html || '<div class="text-center py-20 text-slate-300 font-bold italic">Waiting for leads...</div>';
    };

    const takeover = async (phone) => {
        if (!confirm("Ready to handle this personally? AI will stop responding.")) return;
        await fetch(CONFIG.ENDPOINTS.takeover + phone, { method: 'POST', headers: { 'X-Tenant-Id': CONFIG.TENANT_ID } });
        loadLeads();
    };

    const handleUpload = async (e) => {
        e.preventDefault();
        if (!document.getElementById('latitude').value) return alert("Verify GPS first!");
        const formData = new FormData(e.target);
        const res = await fetch(CONFIG.ENDPOINTS.upload, { method: 'POST', headers: { 'X-Tenant-Id': CONFIG.TENANT_ID }, body: formData });
        if (res.ok) { alert("🎉 Published Successfully!"); location.reload(); }
    };

    // 🔹 4. EXPOSE MODULE
    return { init, takeover };
})();

// Initialize and Link to Window
document.addEventListener('DOMContentLoaded', RealtorPortal.init);
window.RealtorPortal = RealtorPortal;