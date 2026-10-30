import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { predictionsApi } from '../services/api';
import { FileText, Download, CheckCircle, ShieldCheck } from 'lucide-react';

export const ReportsPage: React.FC = () => {
  const { activeTenant } = useAuth();
  const [isExporting, setIsExporting] = useState(false);
  const [downloadMsg, setDownloadMsg] = useState<string | null>(null);

  const handleExportCsv = async () => {
    if (!activeTenant) return;
    setIsExporting(true);
    try {
      const res = await predictionsApi.getMaintenancePriorities(activeTenant.id, { limit: 100 });
      const items = res.items || [];
      const headers = ['Rank', 'Asset_Code', 'Machine_Name', 'Machine_Type', 'Estimated_RUL_Cycles', 'Priority_Band', 'Cutoff_Cycle', 'Explanation'];
      const rows = items.map((item, idx) => [
        idx + 1,
        `"${item.asset_code}"`,
        `"${item.machine_name || 'Turbofan Engine'}"`,
        `"${item.machine_type}"`,
        item.rul_cycles !== null ? item.rul_cycles.toFixed(2) : '',
        `"${item.priority_band}"`,
        item.prediction_cutoff_cycle || '',
        `"${item.explanation || ''}"`,
      ]);

      const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
      const encodedUri = encodeURI(csvContent);
      const link = document.createElement('a');
      link.setAttribute('href', encodedUri);
      link.setAttribute('download', `fleet_maintenance_report_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setDownloadMsg('Fleet Maintenance Priority Report downloaded successfully.');
    } catch (err: any) {
      setDownloadMsg('Failed to generate CSV export.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
          Maintenance &amp; Compliance Reports
        </h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
          Audit logs, fleet condition exports, and predictive maintenance performance documentation.
        </p>
      </div>

      {downloadMsg && (
        <div style={{ padding: '0.75rem 1rem', borderRadius: '6px', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <CheckCircle size={16} />
          <span>{downloadMsg}</span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
        {/* Report 1 */}
        <div className="card" style={{ padding: '1.5rem', backgroundColor: '#ffffff', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <FileText size={20} color="#2563eb" />
              <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0, color: 'var(--text-primary)' }}>
                Fleet Maintenance Priority Export (CSV)
              </h2>
            </div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', margin: 0 }}>
              Complete dataset containing ranked machine IDs, estimated Remaining Useful Life (RUL) in cycles, priority classifications, cutoff flight cycles, and maintenance explanations.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleExportCsv}
            disabled={isExporting}
            style={{ marginTop: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
          >
            <Download size={15} />
            <span>{isExporting ? 'Generating Report...' : 'Download Fleet CSV'}</span>
          </button>
        </div>

        {/* Report 2 */}
        <div className="card" style={{ padding: '1.5rem', backgroundColor: '#ffffff', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <ShieldCheck size={20} color="#16a34a" />
              <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0, color: 'var(--text-primary)' }}>
                Model Verification &amp; Evaluation Digest
              </h2>
            </div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', margin: 0 }}>
              Audit manifest verifying model integrity hashes (SHA-256), causal trailing window configuration (W=30), training and test split boundaries, and evaluation metrics (MAE / RMSE).
            </p>
          </div>
          <div style={{ marginTop: '1.25rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Available under the Model &amp; Monitoring tab for detailed parameter tracking.
          </div>
        </div>
      </div>
    </div>
  );
};
