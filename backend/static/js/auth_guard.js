/**
 * EST8GO AUTH GUARD v2.0
 * ========================
 * Drop this <script> tag at the TOP of any protected page (before body content):
 *   <script src="/static/js/auth_guard.js"></script>
 *
 * For superuser-only pages, add data-require-superuser="true" to the <html> tag:
 *   <html lang="en" data-require-superuser="true">
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

  // Superuser-only page but user isn't superuser → kick to realtor portal
  if (requiresSuperuser && !isSuperuser) {
    window.location.replace("/public/realtor-portal");
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
      localStorage.removeItem("access_token");
      localStorage.removeItem("user_role");
      localStorage.removeItem("tenant_id");
      localStorage.removeItem("user_email");
      window.location.replace("/public/login");
    },
  };
})();
