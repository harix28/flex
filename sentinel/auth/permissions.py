"""Only implemented permissions. No organization role grants platform access."""
from typing import Literal
Role = Literal['admin', 'plant_manager', 'technician', 'viewer']
PERMISSIONS = {
    'admin': frozenset({'organization.read', 'members.manage', 'registry.read', 'registry.manage', 'installations.manage', 'replay.read', 'replay.ingest', 'predictions.read', 'predictions.create', 'work_orders.read', 'work_orders.create', 'work_orders.approve', 'work_orders.assign', 'work_orders.update', 'work_orders.cancel', 'work_orders.notes'}),
    'plant_manager': frozenset({'organization.read', 'registry.read', 'registry.manage', 'installations.manage', 'replay.read', 'replay.ingest', 'predictions.read', 'predictions.create', 'work_orders.read', 'work_orders.create', 'work_orders.approve', 'work_orders.assign', 'work_orders.update', 'work_orders.cancel', 'work_orders.notes'}),
    'technician': frozenset({'organization.read', 'registry.read', 'installations.manage', 'replay.read', 'predictions.read', 'predictions.create', 'work_orders.read', 'work_orders.create', 'work_orders.execute', 'work_orders.notes'}),
    'viewer': frozenset({'organization.read', 'registry.read', 'replay.read', 'predictions.read', 'work_orders.read'}),
}


def permits(roles, permission):
    return any(permission in PERMISSIONS.get(role, ()) for role in roles)
