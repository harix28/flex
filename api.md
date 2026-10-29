
### Eligible work-order assignees

`GET /api/v1/organizations/{tenant_id}/work-order-assignees?offset=0`

Requires a session, current tenant membership and `work_orders.assign` (admin or plant_manager). Returns active technician memberships with active users: `id`, `user_id`, `roles`, `active`, `user_active`, `display_name`; no email or membership-edit authority. Pages contain at most 100 items, with `next_offset` or null. Offset is bounded to 0–100000. Cross-tenant access returns 404; insufficient permission returns 403. Assignment writes retain their existing CSRF, current eligibility and version checks.

Backend errors use `{ "error": { "code": "version_conflict" }, "request_id": "..." }`. The portal preserves these codes for actionable messages. Tenant changes remount scoped page content and clear old results.
