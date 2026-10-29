import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../services/api';
import { Member, Role } from '../services/types';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { Modal } from '../components/common/Modal';
import { UserPlus, RefreshCw, AlertCircle } from 'lucide-react';

export const MembersPage: React.FC = () => {
  const { activeTenant, user } = useAuth();
  const [members, setMembers] = useState<Member[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; requestId?: string } | null>(null);

  // Add Member Modal
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [targetUserId, setTargetUserId] = useState('');
  const [selectedRoles, setSelectedRoles] = useState<Role[]>(['viewer']);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchMembers = useCallback(async () => {
    if (!activeTenant) return;
    setIsLoading(true);
    setError(null);

    try {
      const res = await authApi.getMembers(activeTenant.id);
      setMembers(res.items);
    } catch (err: any) {
      setError({ message: err.message || 'Failed to list members', requestId: err.requestId });
    } finally {
      setIsLoading(false);
    }
  }, [activeTenant]);

  useEffect(() => {
    fetchMembers();
  }, [fetchMembers]);

  const handleRoleToggle = (role: Role) => {
    setSelectedRoles((prev) =>
      prev.includes(role) ? (prev.length > 1 ? prev.filter((r) => r !== role) : prev) : [...prev, role]
    );
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTenant || !targetUserId.trim()) return;
    setFormError(null);
    setIsSubmitting(true);

    try {
      await authApi.addMember(activeTenant.id, targetUserId.trim(), selectedRoles);
      setIsAddModalOpen(false);
      setTargetUserId('');
      setSelectedRoles(['viewer']);
      fetchMembers();
    } catch (err: any) {
      setFormError(err.message || 'Failed to add member to organization');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdateRoles = async (memberId: string, currentRoles: Role[], roleToToggle: Role) => {
    if (!activeTenant) return;
    const newRoles = currentRoles.includes(roleToToggle)
      ? currentRoles.filter((r) => r !== roleToToggle)
      : [...currentRoles, roleToToggle];

    if (newRoles.length === 0) {
      alert('A member must hold at least one role.');
      return;
    }

    try {
      await authApi.updateMember(activeTenant.id, memberId, newRoles, true);
      fetchMembers();
    } catch (err: any) {
      alert(err.message || 'Failed to update member roles');
    }
  };

  const handleDisableMember = async (memberId: string, memberEmail: string) => {
    if (!activeTenant || !window.confirm(`Revoke organization membership for ${memberEmail}?`)) return;
    try {
      await authApi.removeMember(activeTenant.id, memberId);
      fetchMembers();
    } catch (err: any) {
      alert(err.message || 'Failed to revoke membership');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Organization Members &amp; Roles</h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Tenant isolation, localized role-based access control, and last-admin invariant enforcement.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={fetchMembers}
            disabled={isLoading}
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setFormError(null);
              setIsAddModalOpen(true);
            }}
          >
            <UserPlus size={16} />
            <span>Add Member</span>
          </button>
        </div>
      </div>

      {error && <ErrorState message={error.message} requestId={error.requestId} onRetry={fetchMembers} />}

      {/* Table / Loading */}
      {isLoading ? (
        <LoadingState message="Loading organization memberships..." />
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>User Display Name</th>
                <th>Email Address</th>
                <th>User ID</th>
                <th>Assigned Roles (Tenant Scoped)</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{m.display_name}</div>
                    {m.user_id === user?.id && (
                      <span className="badge badge-unknown" style={{ fontSize: '0.65rem', marginTop: '0.125rem' }}>
                        Current User
                      </span>
                    )}
                  </td>
                  <td className="mono" style={{ fontSize: '0.8125rem' }}>{m.email}</td>
                  <td className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }} title={m.user_id}>
                    {m.user_id.substring(0, 8)}...
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                      {(['admin', 'plant_manager', 'technician', 'viewer'] as const).map((r) => {
                        const hasRole = m.roles.includes(r);
                        return (
                          <button
                            key={r}
                            type="button"
                            onClick={() => handleUpdateRoles(m.id, m.roles, r)}
                            style={{
                              fontSize: '0.7rem',
                              padding: '0.15rem 0.4rem',
                              borderRadius: 'var(--radius-sm)',
                              border: `1px solid ${hasRole ? 'var(--primary)' : 'var(--border-subtle)'}`,
                              backgroundColor: hasRole ? 'rgba(14, 165, 233, 0.15)' : 'transparent',
                              color: hasRole ? 'var(--primary)' : 'var(--text-muted)',
                              cursor: 'pointer',
                            }}
                            title={`Toggle ${r} role`}
                          >
                            {r}
                          </button>
                        );
                      })}
                    </div>
                  </td>
                  <td>
                    <span className={`badge ${m.active ? 'badge-low' : 'badge-unknown'}`}>
                      {m.active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td>
                    {m.active && (
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => handleDisableMember(m.id, m.email)}
                        style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', color: 'var(--urgent-text)' }}
                      >
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Member Modal */}
      {isAddModalOpen && (
        <Modal
          isOpen={isAddModalOpen}
          onClose={() => setIsAddModalOpen(false)}
          title="Add User to Organization"
          footer={
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setIsAddModalOpen(false)}
                disabled={isSubmitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                form="add-member-form"
                className="btn btn-primary"
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Adding Member...' : 'Confirm Membership'}
              </button>
            </>
          }
        >
          <form id="add-member-form" onSubmit={handleAddMember} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {formError && (
              <div className="alert alert-danger" style={{ margin: 0 }}>
                <AlertCircle size={16} />
                <span>{formError}</span>
              </div>
            )}

            <div className="form-group">
              <label className="form-label" htmlFor="member-user-id">
                User UUID *
              </label>
              <input
                id="member-user-id"
                type="text"
                className="form-control mono"
                value={targetUserId}
                onChange={(e) => setTargetUserId(e.target.value)}
                placeholder="e.g., 29473e09-6a1c-4b53-b564-216d371fe597"
                required
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Enter the UUID of an existing active user created via the operator CLI.
              </span>
            </div>

            <div className="form-group">
              <label className="form-label">
                Assign Roles (Tenant-Scoped)
              </label>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {(['admin', 'plant_manager', 'technician', 'viewer'] as const).map((r) => {
                  const isChecked = selectedRoles.includes(r);
                  return (
                    <label
                      key={r}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        fontSize: '0.8125rem',
                        cursor: 'pointer',
                        padding: '0.35rem 0.65rem',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: isChecked ? 'rgba(14, 165, 233, 0.15)' : 'var(--bg-subtle)',
                        border: `1px solid ${isChecked ? 'var(--primary)' : 'var(--border-subtle)'}`,
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => handleRoleToggle(r)}
                      />
                      <span style={{ textTransform: 'capitalize' }}>{r.replace('_', ' ')}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
