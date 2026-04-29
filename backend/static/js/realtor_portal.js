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
        bindEvents();
        loadLeads();
    };

    const bindEvents = () => {
        document.getElementById('addPropTrigger')?.addEventListener('click', () => document.getElementById('uploadModal').classList.remove('hidden'));
        document.getElementById('closeModal')?.addEventListener('click', () => document.getElementById('uploadModal').classList.add('hidden'));
        document.getElementById('gpsBtn')?.addEventListener('click', captureGPS);

        // --- FORM SUBMISSION FIX ---
        const form = document.getElementById('uploadForm');
        form?.addEventListener('submit', handleUpload);
    };

    const captureGPS = () => {
        const btn = document.getElementById('gpsBtn');
        if (!navigator.geolocation) return alert("GPS not supported");
        btn.innerHTML = "🛰️ Locating Site...";
        navigator.geolocation.getCurrentPosition((pos) => {
            document.getElementById('latitude').value = pos.coords.latitude;
            document.getElementById('longitude').value = pos.coords.longitude;
            btn.className = "w-full bg-blue-600 text-white py-4 rounded-2xl font-black";
            btn.innerHTML = "✅ Site Verified";
        }, (err) => {
            alert("Error: Location access is mandatory for Truth-Verification.");
            btn.innerHTML = "❌ GPS Failed";
        });
    };

    const handleUpload = async (e) => {
        e.preventDefault();
        const submitBtn = document.getElementById('submitBtn');

        // 1. Validation
        if (!document.getElementById('latitude').value) {
            return alert("Wait! You must capture the GPS location while standing on the property.");
        }

        submitBtn.innerHTML = "Publishing to Vault...";
        submitBtn.disabled = true;

        try {
            const formData = new FormData(e.target);
            const token = localStorage.getItem('access_token'); // Get the JWT token from login

            const res = await fetch(CONFIG.ENDPOINTS.upload, {
                method: 'POST',
                headers: {
                    'X-Tenant-Id': CONFIG.TENANT_ID,
                    'Authorization': `Bearer ${token}` // ADDED: Security handshake
                },
                body: formData
            });

            const result = await res.json();

            if (res.ok) {
                alert(`🎉 Success! Property listed with ${result.gps_accuracy}% GPS Accuracy.`);
                location.reload();
            } else {
                alert(`Upload Failed: ${result.detail || 'Unknown Error'}`);
            }
        } catch (err) {
            console.error("Upload Error:", err);
            alert("Connection error. Please try again.");
        } finally {
            submitBtn.innerHTML = "PUBLISH TO TRUTH-VAULT";
            submitBtn.disabled = false;
        }
    };

    const loadLeads = async () => {
        const res = await fetch(CONFIG.ENDPOINTS.leads, { headers: { 'X-Tenant-Id': CONFIG.TENANT_ID } });
        const data = await res.json();
        document.getElementById('statCount').innerText = data.length;
        document.getElementById('statHot').innerText = data.filter(l => l.status === 'HOT LEAD').length;
        renderLeads(data);
    };

    const renderLeads = (leads) => {
        const list = document.getElementById('leadList');
        let html = "";
        leads.forEach(lead => {
            const prefs = lead.prefs || {};
            const loc = (prefs.location && prefs.location !== "undefined") ? prefs.location : "General";
            const budget = (prefs.budget && !isNaN(prefs.budget)) ? '₦' + Number(prefs.budget).toLocaleString() : "Negotiable";
            const botLabel = lead.is_bot_active ? 'Silence AI' : 'Active';
            const botClass = lead.is_bot_active ? 'bg-slate-900' : 'bg-emerald-500';

            html += `
            <div class="bg-white p-6 rounded-[2.2rem] shadow-sm border border-slate-100 mb-4 overflow-hidden">
                <div class="flex items-center gap-4 mb-4">
                    <div class="w-12 h-12 premium-gradient rounded-2xl flex items-center justify-center text-white font-black">${lead.name.charAt(0)}</div>
                    <div class="min-w-0 flex-1">
                        <h3 class="text-sm font-black text-slate-800 truncate">${lead.name}</h3>
                        <p class="text-[9px] text-slate-400 font-bold uppercase">${lead.last_active}</p>
                    </div>
                </div>
                <div class="bg-slate-50 rounded-2xl p-4 mb-4 border border-slate-100">
                    <table style="width: 100%; table-layout: fixed;">
                        <tr>
                            <td style="width: 50%; border-right: 1px solid #e2e8f0; padding-right: 8px;">
                                <p class="text-[8px] font-black text-slate-400 uppercase">Searching</p>
                                <p class="text-[10px] font-bold text-indigo-900 truncate">${loc}</p>
                            </td>
                            <td style="width: 50%; padding-left: 8px;">
                                <p class="text-[8px] font-black text-slate-400 uppercase text-right">Budget</p>
                                <p class="text-[10px] font-black text-emerald-600 text-right truncate">${budget}</p>
                            </td>
                        </tr>
                    </table>
                </div>
                <div class="flex gap-2">
                    <a href="tel:${lead.phone}" class="flex-1 bg-indigo-50 text-indigo-600 py-4 rounded-2xl text-center"><i class="fa-solid fa-phone"></i></a>
                    <a href="https://wa.me/${lead.phone}" class="flex-1 bg-emerald-50 text-emerald-600 py-4 rounded-2xl text-center"><i class="fa-brands fa-whatsapp text-xl"></i></a>
                    <button onclick="window.takeoverChat('${lead.phone}')" class="flex-[1.8] ${botClass} text-white text-[10px] font-black py-4 rounded-2xl uppercase">${botLabel}</button>
                </div>
            </div>`;
        });
        list.innerHTML = html;
    };

    window.takeoverChat = async (phone) => {
        if (!confirm("Silence AI?")) return;
        await fetch(CONFIG.ENDPOINTS.takeover + phone, { method: 'POST', headers: { 'X-Tenant-Id': CONFIG.TENANT_ID } });
        loadLeads();
    };

    const handleUpload = async (e) => {
        e.preventDefault();
        if (!document.getElementById('latitude').value) return alert("Verify GPS first!");
        const formData = new FormData(e.target);
        const res = await fetch(CONFIG.ENDPOINTS.upload, { method: 'POST', headers: { 'X-Tenant-Id': CONFIG.TENANT_ID }, body: formData });
        if (res.ok) { alert("🎉 Property Published!"); location.reload(); }
    };

    return { init };
})();
document.addEventListener('DOMContentLoaded', RealtorPortal.init);