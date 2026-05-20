/**
 * EST8GO AUTH GUARD v2.0
 * ========================
 * Drop this <script> tag at the TOP of any protected page (before body content):
 *   <script src="/static/js/auth_guard.js"></script>
 *
 * For superuser-only pages, add data-require-superuser="true" to the <html> tag:
 *   <html lang="en" data-require-superuser="true">
 */

/**
 * EST8GO AUTH GUARD v3.0
 * ========================
 * Drop this <script> tag at the TOP of any protected page:
 *   <script src="/static/js/auth_guard.js"></script>
 *
 * For superuser-only pages, add data-require-superuser="true" to <html>:
 *   <html lang="en" data-require-superuser="true">
 *
 * Tenant dashboard: /public/business
 * Admin dashboard:  /public/super-admin-portal
 */

(function () {
  const token = localStorage.getItem("access_token");
  const role = localStorage.getItem("user_role");
  const isSuperuser = role === "superuser";
  const requiresSuperuser =
    document.documentElement.dataset.requireSuperuser === "true";

  // No token → kick to login
  if (!token) {
    window.location.replace("/public/login");
    return;
  }

  // Superuser-only page but user isn't superuser → send to business dashboard
  if (requiresSuperuser && !isSuperuser) {
    window.location.replace("/public/business");
    return;
  }

  // Expose helpers to the page
  window.Auth = {
    token,
    role,
    isSuperuser,
    tenantId: parseInt(localStorage.getItem("tenant_id") || "0", 10),
    email: localStorage.getItem("user_email") || "",

    /** Returns headers object with Bearer token for fetch() calls */
    headers() {
      return {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      };
    },

    /** Authenticated fetch wrapper — auto-handles 401 */
    async fetch(url, options = {}) {
      const res = await fetch(url, {
        ...options,
        headers: { ...Auth.headers(), ...(options.headers || {}) },
      });
      if (res.status === 401) {
        Auth.logout();
        return null;
      }
      return res;
    },

    /** Clear session and redirect to login */
    logout() {
      localStorage.clear();
      window.location.replace("/public/login");
    },
  };
})();