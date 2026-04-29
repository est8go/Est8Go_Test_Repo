document.getElementById('loginForm').onsubmit = async (e) => {
    e.preventDefault();
    const btn = document.getElementById('loginBtn');
    btn.innerHTML = "VERIFYING...";
    btn.disabled = true;

    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    try {
        // We use standard URLSearchParams for OAuth2 compatibility
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);

        const res = await fetch('/auth/login', {
            method: 'POST',
            body: formData
        });

        const data = await res.json();

        if (res.ok) {
            // 1. SAVE THE KEYS TO THE KINGDOM
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user_role', data.role);
            localStorage.setItem('tenant_id', data.tenant_id);

            // 2. INTELLIGENT REDIRECT
            if (data.role === 'superuser' || data.tenant_id === 1) {
                window.location.href = '/public/super-admin-portal';
            } else {
                window.location.href = '/public/realtor-portal';
            }
        } else {
            alert("❌ Invalid Credentials. Access Denied.");
            btn.innerHTML = "AUTHENTICATE";
            btn.disabled = false;
        }
    } catch (err) {
        alert("System offline. Please check connection.");
        btn.innerHTML = "AUTHENTICATE";
        btn.disabled = false;
    }
};