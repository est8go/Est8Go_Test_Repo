-- Est8Go: Remove test users from tenant 1, keep the admin account only
-- Run once via Supabase SQL editor or psql

-- Remove any extra seat entitlements for non-admin users under tenant 1
DELETE FROM seat_entitlements
WHERE tenant_id = 1
  AND user_id IN (
    SELECT id FROM users
    WHERE tenant_id = 1
      AND role != 'admin'
  );

-- Remove the non-admin users under tenant 1
DELETE FROM users
WHERE tenant_id = 1
  AND role != 'admin';

-- Wallet is already correct (1090 credits) — no credit adjustment needed

-- Remove stale test account across all tenants
DELETE FROM users WHERE email = 'elixirplate@gmail.com';
