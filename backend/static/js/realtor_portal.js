/**
 * EST8GO MASTER EXECUTIVE CONTROLLER (v1.2.0)
 * Includes: GPS Proof, Cloud Upload, Lead Sync, and HITL Bridge.
 */

const RealtorPortal = (() => {
    // 1. CONFIGURATION & STATE
    const CONFIG = {
        TENANT_ID: "1",
        ENDPOINTS: {
            leads: '/conversations/realtor/leads',
            takeover: '/conversations/takeover/',
            upload: '/listings/realtor/upload'
        }
    };

    // 2. INITIALIZATION
    const init = () => {
        console.log("🚀 Est8Go Executive Portal: Systems Nominal");
        bindEvents();
        loadLeads();
        // Fast sync for high-scaling performance
        setInterval(loadLeads, 15000);
    };

    const bindEvents = () => {
        // Modal Triggers
        document.getElementById('addPropTrigger')?.addEventListener('click', () => {
            /*  // PREMIUM LOGIN GUARD
              const token = localStorage.getItem('access_token');
              if (!token) {
                  alert("🔒 Access Denied: You must be logged in to your Est8Go account to list a property.");
                  // Optional: window.location.href = "/login"; 
                  return;
              } */
            document.getElementById('uploadModal').classList.remove('hidden');
        });

        document.getElementById('closeModal')?.addEventListener('click', () => {
            document.getElementById('uploadModal').classList.add('hidden');
        });

        // GPS & Form Hooks
        document.getElementById('gpsBtn')?.addEventListener('click', captureLocation);
        document.getElementById('uploadForm')?.addEventListener('submit', handleUpload);
    };

    // 3. CORE BUSINESS LOGIC
    const captureLocation = () => {
        const btn = document.getElementById('gpsBtn');
        if (!navigator.geolocation) return alert("Security Error: Device does not support GPS.");

        btn.innerHTML = "🛰️ SYNCING WITH SATELLITES...";
        navigator.geolocation.getCurrentPosition((pos) => {
            document.getElementById('latitude').value = pos.coords.latitude;
            document.getElementById('longitude').value = pos.coords.longitude;

            // Visual feedback for Truth-Verification
            btn.className = "w-full bg-blue-600 text-white py-4 rounded-2xl font-black shadow-lg animate-bounce";
            btn.innerHTML = "✅ PHYSICAL SITE VERIFIED";
        }, (err) => {
            alert("Mandatory: Location access is required to list properties on Est8Go.");
            btn.innerHTML = "❌ VERIFICATION FAILED";
        });
    };

    const handleUpload = async (e) => {
        e.preventDefault();
        const submitBtn = document.querySelector('#uploadForm button[type="submit"]');

        // Validation: Physical Proof check
        if (!document.getElementById('latitude').value) {
            return alert("Verification Required: You must be on-site to list this property.");
        }

        submitBtn.innerHTML = "PUBLISHING TO VAULT...";
        submitBtn.disabled = true;

        const formData = new FormData(e.target);
        const token = localStorage.getItem('access_token'); // Premium Auth

        try {
            const res = await fetch(CONFIG.ENDPOINTS.upload, {
                method: 'POST',
                headers: {
                    'X-Tenant-Id': CONFIG.TENANT_ID,
                    //  'Authorization': `Bearer ${token}` // 🔐 COMMENTED
                },
                body: formData
            });

            if (res.ok) {
                alert("🎉 SUCCESS: Property is now LIVE and Truth-Verified.");
                location.reload();
            } else {
                if (res.status === 401 || res.status === 403) {
                    alert("🚨 Session Expired: Please log in again to publish.");
                } else {
                    const err = await res.json();
                    alert(`Upload Failed: ${err.detail || 'Ensure all fields are filled'}`);
                }
            }
        } catch (err) {
            alert("Network Error: Cloud connection interrupted.");
        } finally {
            submitBtn.innerHTML = "PUBLISH TO TRUTH-VAULT";
            submitBtn.disabled = false;
        }
    };

    const loadLeads = async () => {
        try {
            const response = await fetch(CONFIG.ENDPOINTS.leads, {
                headers: { 'X-Tenant-Id': CONFIG.TENANT_ID }
            });
            const data = await response.json();

            // Dashboard Stats
            document.getElementById('statCount').innerText = data.length;
            document.getElementById('statHot').innerText = data.filter(l => l.status === 'HOT LEAD').length;

            renderLeads(data);
        } catch (err) { console.error("Lead Sync Error:", err); }
    };

    const renderLeads = (leads) => {
        const list = document.getElementById('leadList');
        if (!list) return;

        let html = "";
        leads.forEach(lead => {
            // 🔹 TRIPLE-GUARD DATA CLEANING
            const rawPrefs = lead.prefs || {};

            // 1. Location Guard: Checks if missing, null, or the literal string "undefined"
            let loc = "General";
            if (rawPrefs.location && String(rawPrefs.location) !== "undefined" && rawPrefs.location !== null) {
                loc = rawPrefs.location;
            }

            // 2. Budget Guard: Checks if it's a valid number
            let budget = "Negotiable";
            if (rawPrefs.budget && !isNaN(rawPrefs.budget) && String(rawPrefs.budget) !== "undefined") {
                budget = '₦' + Number(rawPrefs.budget).toLocaleString();
            }

            const name = lead.name || "Guest";
            const lastActive = lead.last_active || "Active";
            // ... (rest of your variables)

            html += `
            <div class="bg-white p-6 rounded-[2.5rem] shadow-sm border border-slate-100 overflow-hidden w-full mb-5 relative">
                ${isHot ? '<div class="absolute top-0 right-0 bg-orange-500 text-white text-[8px] font-black px-4 py-1 rounded-bl-2xl uppercase tracking-widest">Hot Lead</div>' : ''}
                
                <div class="flex items-center gap-4 mb-5">
                    <div class="w-14 h-14 premium-gradient rounded-2xl flex items-center justify-center text-white text-xl font-black shadow-lg">
                        ${name.charAt(0)}
                    </div>
                    <div class="min-w-0 flex-1">
                        <h3 class="text-base font-black text-slate-800 truncate">${name}</h3>
                        <p class="text-[10px] text-slate-400 font-extrabold uppercase tracking-wide">Last Active ${lastActive}</p>
                    </div>
                </div>

                <!-- 🔹 SOCKET: FIXED TABLE CONTAINER -->
            <div class="bg-slate-50 rounded-2xl p-4 mb-5 border border-slate-100" style="overflow: hidden;">
                <table style="width: 100%; table-layout: fixed; border-collapse: collapse;">
                    <tr>
                        <td style="width: 55%; border-right: 1px solid #e2e8f0; padding-right: 10px; overflow: hidden;">
                            <p style="font-size: 8px; font-weight: 900; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px;">Searching</p>
                            <p style="font-size: 11px; font-weight: 700; color: #1e1b4b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                ${loc}
                            </p>
                        </td>
                        <td style="width: 45%; padding-left: 10px; overflow: hidden;">
                            <p style="font-size: 8px; font-weight: 900; color: #94a3b8; text-transform: uppercase; margin-bottom: 2px; text-align: right;">Budget</p>
                            <p style="font-size: 11px; font-weight: 900; color: #059669; text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                ${budget}
                            </p>
                        </td>
                    </tr>
                </table>
            </div>

                <div class="grid grid-cols-3 gap-3">
                    <a href="tel:${lead.phone}" class="bg-indigo-50 text-indigo-600 py-4 rounded-2xl text-center active:scale-95 transition">
                        <i class="fa-solid fa-phone"></i>
                    </a>
                    <a href="https://wa.me/${lead.phone}" class="bg-emerald-50 text-emerald-600 py-4 rounded-2xl text-center active:scale-95 transition">
                        <i class="fa-brands fa-whatsapp text-xl"></i>
                    </a>
                    <button onclick="RealtorPortal.takeover('${lead.phone}')" class="${botClass} text-white text-[9px] font-black py-4 rounded-2xl uppercase shadow-md active:scale-95 transition">
                        ${botLabel}
                    </button>
                </div>
            </div>`;
        });
        list.innerHTML = html || '<div class="text-center py-20 text-slate-300 font-bold italic">No leads detected today.</div>';
    };

    const takeover = async (phone) => {
        if (!confirm("Ready to handle this client personally? The AI will stop responding.")) return;
        try {
            await fetch(CONFIG.ENDPOINTS.takeover + phone, {
                method: 'POST',
                headers: { 'X-Tenant-Id': CONFIG.TENANT_ID }
            });
            loadLeads();
        } catch (err) { console.error("Takeover Failed:", err); }
    };

    // 4. THE BRIDGE
    return { init, takeover };
})();

// FINAL GLOBAL LINK
document.addEventListener('DOMContentLoaded', RealtorPortal.init);
window.RealtorPortal = RealtorPortal;