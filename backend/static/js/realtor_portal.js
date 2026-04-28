/**
 * Est8Go Realtor Portal - Modular Logic Engine
 * High-performance, secure, and encapsulated.
 */

const RealtorPortal = (() => {
    // 🔹 CONFIGURATION
    const CONFIG = {
        TENANT_ID: "1",
        ENDPOINTS: {
            leads: '/conversations/realtor/leads',
            takeover: '/conversations/takeover/',
            upload: '/listings/realtor/upload' // <--- Ensure this starts with /listings
        }
    };

    // 🔹 INITIALIZATION
    const init = () => {
        console.log("🚀 Est8Go Modular Controller Active");
        bindEvents();
        loadLeads();
        // Auto-refresh leads every 30 seconds
        setInterval(loadLeads, 30000);
    };

    // 🔹 EVENT BINDING (Modular Delegation)
    const bindEvents = () => {
        const addPropTrigger = document.getElementById('addPropTrigger');
        const gpsBtn = document.getElementById('gpsBtn');
        const uploadForm = document.getElementById('uploadForm');

        // Toggle Modal
        addPropTrigger?.addEventListener('click', () => {
            document.getElementById('uploadModal')?.classList.remove('hidden');
        });

        document.getElementById('closeModal')?.addEventListener('click', () => {
            document.getElementById('uploadModal')?.classList.add('hidden');
        });

        // GPS Logic
        gpsBtn?.addEventListener('click', captureLocation);

        // Upload Logic
        uploadForm?.addEventListener('submit', handleUpload);
    };

    // 🔹 TRUTH MOAT: GPS VERIFICATION
    const captureLocation = () => {
        const btn = document.getElementById('gpsBtn');
        if (!navigator.geolocation) return alert("GPS is not supported by your device.");

        btn.innerHTML = '<i class="fa-solid fa-satellite-dish animate-pulse"></i> Verifying Site...';

        // ... inside captureLocation function ...
        navigator.geolocation.getCurrentPosition((pos) => {
            // UPDATED: Use full names to match the Audit
            document.getElementById('latitude').value = pos.coords.latitude;
            document.getElementById('longitude').value = pos.coords.longitude;

            btn.classList.replace('bg-emerald-500', 'bg-blue-600');
            btn.innerHTML = "✅ Site Verified";
        }, (err) => {
            alert("Physical proof is required. Please enable location services.");
            btn.innerHTML = '❌ Verification Failed';
        });
    };

    // 🔹 LEAD DATA SYNC
    const loadLeads = async () => {
        try {
            const response = await fetch(CONFIG.ENDPOINTS.leads, {
                headers: { 'X-Tenant-Id': CONFIG.TENANT_ID }
            });
            const leads = await response.json();
            renderLeads(leads);
        } catch (err) {
            console.error("Dashboard Sync Failed:", err);
        }
    };

    const renderLeads = (leads) => {
        const list = document.getElementById('leadList');
        if (!list) return;

        let html = "";
        leads.forEach(lead => {
            const loc = (lead.prefs.location && lead.prefs.location !== "undefined") ? lead.prefs.location : "General";
            const budget = (lead.prefs.budget && !isNaN(lead.prefs.budget)) ? '₦' + Number(lead.prefs.budget).toLocaleString() : "Negotiable";

            html += `
                <div class="bg-white p-5 rounded-[2rem] shadow-sm border border-slate-100 overflow-hidden mb-4">
                    <div class="flex items-center gap-3 mb-4">
                        <div class="w-10 h-10 premium-gradient rounded-xl flex items-center justify-center text-white font-black">
                            ${lead.name.charAt(0)}
                        </div>
                        <div class="min-w-0 flex-1">
                            <h3 class="text-sm font-black text-slate-800 truncate">${lead.name}</h3>
                            <p class="text-[9px] text-slate-400 font-bold uppercase tracking-tight">${lead.last_active}</p>
                        </div>
                    </div>
                    <div class="bg-slate-50 rounded-2xl p-3 mb-4 flex border border-slate-100">
                        <div class="w-1/2 border-r border-slate-200 pr-2">
                            <p class="text-[7px] font-black text-slate-400 uppercase mb-0.5">Searching</p>
                            <p class="text-[10px] font-bold text-indigo-900 truncate">${loc}</p>
                        </div>
                        <div class="w-1/2 pl-2">
                            <p class="text-[7px] font-black text-slate-400 uppercase mb-0.5 text-right">Budget</p>
                            <p class="text-[10px] font-black text-emerald-600 text-right truncate">${budget}</p>
                        </div>
                    </div>
                </div>`;
        });
        list.innerHTML = html || '<div class="text-center py-20 text-slate-300">No active prospects</div>';
    };

    // 🔹 SECURE UPLOAD
    const handleUpload = async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);

        if (!document.getElementById('lat').value) {
            return alert("Verification Required: You must capture GPS while on-site.");
        }

        try {
            const res = await fetch(CONFIG.ENDPOINTS.upload, {
                method: 'POST',
                headers: { 'X-Tenant-Id': CONFIG.TENANT_ID },
                body: formData
            });

            if (res.ok) {
                alert("🎉 Property Published with Truth-Verification!");
                location.reload();
            } else {
                alert("Upload failed. Ensure all fields are filled.");
            }
        } catch (err) {
            console.error("Form Error:", err);
        }
    };

    // 🔹 EXPOSE INIT
    return { init };
})();

// Initialize the platform engine
document.addEventListener('DOMContentLoaded', RealtorPortal.init);