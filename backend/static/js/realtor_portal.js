/**
 * EST8GO REALTOR PORTAL (v3.0.0)
 * ================================
 * SECURITY FIX: tenant_id now read from JWT token via /users/me
 * Never trusts URL parameters for tenant identification.
 * All API calls use Bearer token authentication.
 */

const RealtorPortal = (() => {

    // ── STATE ─────────────────────────────────────────
    let TENANT_ID = null;  // Set after /users/me resolves — never from URL
    let USER_EMAIL = null;
    let USER_ROLE = null;

    const ENDPOINTS = {
        me: '/users/me',
        leads: '/conversations/realtor/leads',
        props: '/listings/',
        takeover: '/conversations/takeover/',
        upload: '/listings/realtor/upload',
    };

    // ── AUTH HEADERS ─────────────────────────────────
    // Always use Bearer token + tenant header together
    const authHeaders = () => {
        const token = localStorage.getItem('access_token');
        if (!token) {
            window.location.replace('/public/login');
            return {};
        }
        const headers = {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        };
        // Only add X-Tenant-Id if we have resolved it from the server
        if (TENANT_ID) headers['X-Tenant-Id'] = String(TENANT_ID);
        return headers;
    };

    // ── SECURE FETCH ─────────────────────────────────
    const apiFetch = async (url, options = {}) => {
        const res = await fetch(url, {
            ...options,
            headers: { ...authHeaders(), ...(options.headers || {}) },
        });
        if (res.status === 401) {
            // Token expired or invalid — force re-login
            localStorage.clear();
            window.location.replace('/public/login');
            return null;
        }
        return res;
    };

    // ── INIT ──────────────────────────────────────────
    const init = async () => {
        // Step 1: Resolve who is logged in from the SERVER — never trust localStorage alone
        const resolved = await resolveCurrentUser();
        if (!resolved) return; // redirected to login

        // Step 2: Bind events and load default tab
        bindEvents();
        switchTab('pulse');

        // Step 3: Auto-refresh leads every 20 seconds
        setInterval(loadPulse, 20000);
    };

    // ── RESOLVE USER FROM SERVER ──────────────────────
    const resolveCurrentUser = async () => {
        try {
            const res = await apiFetch(ENDPOINTS.me);
            if (!res || !res.ok) {
                localStorage.clear();
                window.location.replace('/public/login');
                return false;
            }
            const user = await res.json();

            // Set tenant from SERVER response — not from URL or localStorage
            TENANT_ID = user.tenant_id;
            USER_EMAIL = user.email;
            USER_ROLE = user.role;

            // Populate UI with verified identity
            const nameEl = document.getElementById('userName');
            const roleEl = document.getElementById('userRole');
            if (nameEl) nameEl.textContent = user.first_name || user.email.split('@')[0];
            if (roleEl) roleEl.textContent = user.role;

            // Set avatar initials
            const avatarEl = document.getElementById('userAvatar');
            if (avatarEl) {
                avatarEl.textContent = (user.first_name || user.email).slice(0, 2).toUpperCase();
            }

            return true;
        } catch (e) {
            console.error('Failed to resolve user:', e);
            localStorage.clear();
            window.location.replace('/public/login');
            return false;
        }
    };

    // ── BIND EVENTS ───────────────────────────────────
    const bindEvents = () => {
        document.getElementById('addPropTrigger')
            ?.addEventListener('click', () =>
                document.getElementById('uploadModal').classList.remove('hidden'));
        document.getElementById('closeModal')
            ?.addEventListener('click', () =>
                document.getElementById('uploadModal').classList.add('hidden'));
        document.getElementById('gpsBtn')
            ?.addEventListener('click', captureLocation);
        document.getElementById('uploadForm')
            ?.addEventListener('submit', handleUpload);
        document.getElementById('logoutBtn')
            ?.addEventListener('click', logout);
    };

    // ── TAB SWITCHING ─────────────────────────────────
    const switchTab = (tabName) => {
        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
        document.getElementById(`tab-${tabName}`)?.classList.add('active');
        document.querySelectorAll('.glass-dock button').forEach(btn =>
            btn.classList.remove('nav-active', 'text-slate-400'));
        document.getElementById(`nav-${tabName}`)?.classList.add('nav-active');

        if (tabName === 'pulse') loadPulse();
        if (tabName === 'vault') loadVault();
        if (tabName === 'network') loadNetwork();
    };

    // ── LOAD PULSE (LEADS) ────────────────────────────
    const loadPulse = async () => {
        if (!TENANT_ID) return;
        const res = await apiFetch(ENDPOINTS.leads);
        if (!res || !res.ok) return;
        const data = await res.json();
        const countEl = document.getElementById('statCount');
        if (countEl) countEl.innerText = data.length;
        renderLeads(data);
    };

    // ── LOAD VAULT (LISTINGS) ─────────────────────────
    const loadVault = async () => {
        if (!TENANT_ID) return;
        const res = await apiFetch(ENDPOINTS.props);
        if (!res || !res.ok) return;
        const props = await res.json();
        const list = document.getElementById('inventoryList');
        if (!list) return;

        list.innerHTML = props.map(p => {
            const score = p.trust_score || 0;
            const color = score >= 85 ? 'emerald' : score >= 60 ? 'blue' : 'amber';
            return `
            <div class="bg-white p-6 rounded-[2.5rem] shadow-sm border border-slate-100">
                <div class="flex justify-between items-start mb-4">
                    <div class="min-w-0 flex-1">
                        <h3 class="text-sm font-black text-slate-800 truncate">${p.title}</h3>
                        <p class="text-[9px] text-slate-400 font-bold uppercase">
                            ${p.location} | ₦${(p.price || 0).toLocaleString()}
                        </p>
                    </div>
                    <div class="text-right">
                        <div class="text-lg font-black text-${color}-600">${score}</div>
                        <div class="text-[8px] font-black uppercase text-slate-300">Trust Score</div>
                    </div>
                </div>
                <div class="flex gap-2">
                    <button class="flex-1 bg-slate-900 text-white text-[9px] font-black py-3 rounded-xl uppercase">
                        Edit Media
                    </button>
                    <button class="flex-1 bg-rose-50 text-rose-600 text-[9px] font-black py-3 rounded-xl uppercase">
                        Mark Sold
                    </button>
                </div>
            </div>`;
        }).join('');
    };

    // ── LOAD NETWORK ──────────────────────────────────
    const loadNetwork = () => {
        const list = document.getElementById('networkList');
        if (!list) return;
        list.innerHTML = `
            <div class="bg-white/50 p-4 rounded-2xl flex justify-between items-center">
                <p class="text-xs font-bold text-slate-700">Maitama Partner Share</p>
                <span class="text-[10px] font-black text-emerald-600">5% SPLIT</span>
            </div>`;
    };

    // ── RENDER LEADS ──────────────────────────────────
    const renderLeads = (leads) => {
        const list = document.getElementById('leadList');
        if (!list) return;

        if (!leads.length) {
            list.innerHTML = `<div style="text-align:center;padding:40px;color:rgba(255,255,255,0.3)">
                <div style="font-size:32px;margin-bottom:8px">📭</div>
                <p style="font-size:13px">No active leads yet</p>
            </div>`;
            return;
        }

        list.innerHTML = leads.map(lead => {
            const channelIcon = lead.channel === 'instagram'
                ? '<i class="fa-brands fa-instagram text-pink-500"></i>'
                : lead.channel === 'facebook'
                    ? '<i class="fa-brands fa-facebook text-blue-600"></i>'
                    : '<i class="fa-brands fa-whatsapp text-emerald-500"></i>';

            const prefs = lead.prefs || {};
            const loc = (prefs.location && String(prefs.location) !== 'undefined')
                ? prefs.location : 'General';

            return `
            <div class="bg-white p-6 rounded-[2.5rem] shadow-sm border border-slate-100 mb-4">
                <div class="flex items-center gap-4 mb-4">
                    <div class="relative">
                        <div class="w-12 h-12 premium-indigo rounded-2xl flex items-center
                             justify-center text-white font-black shadow-lg">
                            ${(lead.name || '?').charAt(0)}
                        </div>
                        <div class="absolute -bottom-1 -right-1 bg-white w-5 h-5 rounded-full
                             flex items-center justify-center shadow-sm border border-slate-100"
                             style="font-size:10px">
                            ${channelIcon}
                        </div>
                    </div>
                    <div class="min-w-0 flex-1">
                        <h4 class="text-sm font-black text-slate-800 truncate">${lead.name || 'Unknown'}</h4>
                        <p class="text-[9px] text-slate-400 font-bold">
                            ${lead.last_active || ''} | Searching ${loc}
                        </p>
                    </div>
                </div>
                <div class="flex gap-2">
                    <a href="tel:${lead.phone || ''}"
                       class="flex-1 bg-indigo-50 text-indigo-600 py-3 rounded-xl text-center">
                        <i class="fa-solid fa-phone"></i>
                    </a>
                    <button onclick="window.RealtorPortal.takeover('${lead.phone || ''}')"
                            class="flex-[2] bg-slate-900 text-white text-[9px] font-black
                                   py-3 rounded-xl uppercase">
                        Take Over
                    </button>
                </div>
            </div>`;
        }).join('');
    };

    // ── TAKEOVER ─────────────────────────────────────
    const takeover = async (phone) => {
        const res = await apiFetch(ENDPOINTS.takeover + phone, { method: 'POST' });
        if (res && res.ok) alert('Takeover successful');
    };

    // ── GPS CAPTURE ───────────────────────────────────
    const captureLocation = () => {
        if (!navigator.geolocation) {
            alert('Geolocation not supported on this device.');
            return;
        }
        navigator.geolocation.getCurrentPosition(
            pos => {
                const latEl = document.getElementById('lat');
                const lngEl = document.getElementById('lng');
                if (latEl) latEl.value = pos.coords.latitude;
                if (lngEl) lngEl.value = pos.coords.longitude;
            },
            () => alert('Could not capture location. Please enable GPS.')
        );
    };

    // ── UPLOAD ────────────────────────────────────────
    const handleUpload = async (e) => {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);

        const token = localStorage.getItem('access_token');
        const res = await fetch(ENDPOINTS.upload, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'X-Tenant-Id': String(TENANT_ID),
            },
            body: formData,
        });

        if (res && res.ok) {
            alert('Property uploaded successfully.');
            document.getElementById('uploadModal').classList.add('hidden');
            loadVault();
        } else {
            alert('Upload failed. Please try again.');
        }
    };

    // ── LOGOUT ───────────────────────────────────────
    const logout = () => {
        localStorage.clear();
        window.location.replace('/public/login');
    };

    return { init, switchTab, takeover, logout };
})();

document.addEventListener('DOMContentLoaded', RealtorPortal.init);
window.RealtorPortal = RealtorPortal;