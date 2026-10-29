import React, { useState } from 'react';
import { WorkOrderNoteRecord } from '../../services/types';
import { workOrdersApi } from '../../services/api';
import { MessageSquare, Send, AlertCircle, Loader2 } from 'lucide-react';

interface WorkOrderNotesProps {
  tenantId: string;
  workOrderId: string;
  currentVersion: number;
  notes: WorkOrderNoteRecord[];
  canAddNote: boolean;
  onNoteAdded: (note: WorkOrderNoteRecord, newWorkOrderVersion: number) => void;
  onVersionConflict: () => void;
}

export const WorkOrderNotes: React.FC<WorkOrderNotesProps> = ({
  tenantId,
  workOrderId,
  currentVersion,
  notes,
  canAddNote,
  onNoteAdded,
  onVersionConflict,
}) => {
  const [noteText, setNoteText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteText.trim()) return;

    setError(null);
    setIsSubmitting(true);

    try {
      const res = await workOrdersApi.addNote(tenantId, workOrderId, {
        version: currentVersion,
        note_text: noteText.trim(),
      });
      setNoteText('');
      onNoteAdded(res.note, res.work_order_version);
    } catch (err: any) {
      if (err.code === 'version_conflict') {
        setError('A concurrent update occurred. Refreshing current work order state...');
        onVersionConflict();
      } else {
        setError(err.message || 'Failed to append note');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <MessageSquare size={18} style={{ color: 'var(--primary)' }} />
        <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Technician Execution Notes</h3>
        <span className="badge badge-unknown" style={{ marginLeft: 'auto' }}>
          {notes.length} note{notes.length === 1 ? '' : 's'}
        </span>
      </div>

      {error && (
        <div className="alert alert-danger" style={{ margin: 0 }}>
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Notes Timeline */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem',
          maxHeight: '320px',
          overflowY: 'auto',
          paddingRight: '0.25rem',
        }}
      >
        {notes.length === 0 ? (
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontStyle: 'italic', padding: '0.5rem 0' }}>
            No execution notes recorded yet.
          </p>
        ) : (
          notes.map((note) => (
            <div
              key={note.id}
              style={{
                backgroundColor: 'var(--bg-subtle)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.75rem',
                fontSize: '0.875rem',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                  marginBottom: '0.375rem',
                  fontSize: '0.75rem',
                }}
              >
                <strong style={{ color: 'var(--text-primary)' }}>
                  {note.author?.display_name || 'Technician'}
                </strong>
                <span className="mono" style={{ color: 'var(--text-muted)' }}>
                  {new Date(note.created_at).toLocaleString()}
                </span>
              </div>
              <p style={{ color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
                {note.note_text}
              </p>
            </div>
          ))
        )}
      </div>

      {/* Add Note Form */}
      {canAddNote && (
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.5rem' }}>
          <textarea
            className="form-control"
            rows={2}
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            placeholder="Add plain-text technical observation or inspection findings (max 2,000 characters)..."
            required
            maxLength={2000}
            disabled={isSubmitting}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Target version: <strong className="mono">v{currentVersion}</strong>
            </span>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting || !noteText.trim()}
              style={{ fontSize: '0.8125rem', padding: '0.35rem 0.85rem' }}
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Send size={14} />
                  <span>Append Note</span>
                </>
              )}
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
