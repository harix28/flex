# Organization roles and permissions

Implementation authority: `sentinel/auth/permissions.py`. Roles are additive only
within an explicit active organization membership; none grants platform access.

| Implemented permission | viewer | technician | plant_manager | admin |
|---|---|---|---|---|
| organization.read | Yes | Yes | Yes | Yes |
| members.manage | No | No | No | Yes |
| registry.read | Yes | Yes | Yes | Yes |
| registry.manage | No | No | Yes | Yes |
| installations.manage | No | Yes | Yes | Yes |
| replay.read | Yes | Yes | Yes | Yes |
| replay.ingest | No | No | Yes | Yes |

`organization.read` returns only the authorized organization's ID/name/slug and the
acting membership's roles. Member listing, addition, role updates and disabling all
require `members.manage`. All mutations additionally require valid session-bound CSRF.
Every request resolves the current session user and current database membership.
Global `/auth/me`, logout, CSRF refresh and self password change are session operations,
not organization permissions. A local operator's CLI privileges are separate.

Allowed role strings: `admin`, `plant_manager`, `technician`, `viewer`. Strict schemas
reject unknown or duplicate role names and extra fields. Phase 2 manager values migrate
to plant_manager; ml_engineer memberships require explicit operator resolution before
upgrade. There is no implicit translation of old role names in API requests.

Last-admin protection is transactional and serialized per organization. The remaining
admin must have active membership, active user and usable local password identity.
Neither self-demotion nor simultaneous demotions can remove the final usable admin.
Removing a membership disables it, preserving installation verifier references.

## Planned, not implemented

| Future activity | Intended roles; still requires resource/action-specific design |
|---|---|
| Read registry/maintenance resources | viewer, technician, plant_manager, admin |
| Maintenance updates and inspection recording | technician; assignment checks required |
| Operational management / maintenance approval | plant_manager; approval separation required |
| Organization membership administration | admin; implemented now |

Registry HTTP workflows are implemented in Phase 4; maintenance and approval are implemented in Phase 7. Physical telemetry remains pending.
Their future permission names are not granted by the current mapping. Phase 7 explicitly grants organization admins maintenance approval. Platform-wide administrator access is not
implemented. Experimental API keys grant no permissions in this matrix.


Phase 4 registry.manage covers machine/sensor creation, explicit metadata updates and
archive/retire. installations.manage covers creating and closing mappings. All reads
need registry.read; all writes require current membership and existing CSRF protection.
See [registry](MACHINE_SENSOR_REGISTRY.md). Registry permissions grant no maintenance
approval, platform administration, telemetry ingestion or experimental API-key access.

Phase 5 adds session-authorized replay.read and replay.ingest as shown above.
See [replay contract](REPLAY_INGESTION.md); the experimental API key cannot bypass it.

## Phase 7 maintenance permissions

| Action | viewer | technician | plant_manager | admin |
|---|---|---|---|---|
| Read work orders/history | Yes | Yes | Yes | Yes |
| Create drafts | No | Yes | Yes | Yes |
| Approve, assign, edit, cancel | No | No | Yes | Yes |
| Add versioned notes | No | Assigned only | Yes | Yes |
| Execute start/block/resume/complete | No | Assigned and currently eligible | Manager override | Admin override |

Every execution action requires an active eligible assigned technician, including
when executed by a manager/admin. A viewer who used to be the assignee cannot execute.
Active membership and user/session status are checked on every request. See
[maintenance workflow](MAINTENANCE_WORKFLOW.md) for the evidence-refresh approval policy.
