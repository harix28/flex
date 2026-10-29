import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import { predictionsApi } from '../../services/api';
import { Cpu, AlertCircle, Loader2 } from 'lucide-react';

interface RunPredictionModalProps {
  isOpen: boolean;
  onClose: () => void;
  tenantId: string;
  machineId: string;
  assetCode: string;
  latestCycle?: number | null;
  onSuccess: (prediction: any) => void;
}

export const RunPredictionModal: React.FC<RunPredictionModalProps> = ({
  isOpen,
  onClose,
  tenantId,
  machineId,
  assetCode,
  latestCycle,
  onSuccess,
}) => {
  const [useCustomCutoff, setUseCustomCutoff] = useState(false);
  const [cutoffCycle, setCutoffCycle] = useState<number | ''>(latestCycle || 31);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const cycle = useCustomCutoff && typeof cutoffCycle === 'number' ? cutoffCycle : undefined;
      const res = await predictionsApi.runPrediction(tenantId, machineId, cycle);
      onSuccess(res.prediction);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to evaluate prediction');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Run RUL Prediction: ${assetCode}`}
      footer={
        <>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            form="run-prediction-form"
            className="btn btn-primary"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Evaluating Neural Model...</span>
              </>
            ) : (
              <>
                <Cpu size={16} />
                <span>Run Inference</span>
              </>
            )}
          </button>
        </>
      }
    >
      <form id="run-prediction-form" onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          Execute causal inference using the verified model <strong className="mono">fd001-v1</strong> against stored telemetry. The model extracts a trailing 30-cycle observation window.
        </p>

        {error && (
          <div className="alert alert-danger" style={{ margin: 0 }}>
            <AlertCircle size={18} style={{ flexShrink: 0 }} />
            <div>
              <strong>Evaluation Error:</strong> {error}
            </div>
          </div>
        )}

        <div className="form-group">
          <label className="form-label" style={{ cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={useCustomCutoff}
              onChange={(e) => setUseCustomCutoff(e.target.checked)}
              style={{ marginRight: '0.5rem' }}
            />
            <span>Specify custom cutoff cycle (historical back-test)</span>
          </label>
        </div>

        {useCustomCutoff && (
          <div className="form-group">
            <label className="form-label" htmlFor="cutoff-cycle-input">
              Cutoff Flight Cycle (must be &ge; 30)
            </label>
            <input
              id="cutoff-cycle-input"
              type="number"
              min={30}
              className="form-control mono"
              value={cutoffCycle}
              onChange={(e) => setCutoffCycle(e.target.value === '' ? '' : parseInt(e.target.value, 10))}
              required
            />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Evaluation will strictly use readings in the cycle range [Cutoff - 29, Cutoff].
            </span>
          </div>
        )}

        {!useCustomCutoff && (
          <div
            style={{
              padding: '0.75rem',
              backgroundColor: 'var(--bg-subtle)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.8125rem',
              color: 'var(--text-secondary)',
            }}
          >
            <strong>Default Cutoff:</strong> Latest stored observation cycle ({latestCycle ? `Cycle ${latestCycle}` : 'Auto-detected'}).
          </div>
        )}

        <div
          style={{
            fontSize: '0.75rem',
            color: 'var(--text-muted)',
            borderTop: '1px solid var(--border-subtle)',
            paddingTop: '0.75rem',
          }}
        >
          <em>Note:</em> Results are deterministically deduplicated via SHA-256 input digests. If the exact window was previously evaluated, the persisted result will be returned.
        </div>
      </form>
    </Modal>
  );
};
