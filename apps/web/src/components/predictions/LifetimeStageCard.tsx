import { useEffect, useState } from 'react';
import { classificationApi } from '../../services/api';

export function LifetimeStageCard({ tenantId, machineId }: { tenantId: string; machineId: string }) {
  const [result, setResult] = useState<Awaited<ReturnType<typeof classificationApi.get>> | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setResult(null); setError('');
    classificationApi.get(tenantId, machineId).then(value => {
      if (active) setResult(value);
    }).catch(() => { if (active) setError('Classification unavailable. Check ingested observations and model availability.'); });
    return () => { active = false; };
  }, [tenantId, machineId]);
  return <section className="card" aria-label="Lifetime-stage classification">
    <h2>Random Forest · Lifetime stage</h2>
    {error ? <p role="status">{error}</p> : result ? <>
      <p><strong>{result.lifetime_stage.replace(/_/g, ' ')}</strong> · source cycle {result.source_cycle}</p>
      <p>Model: {result.model_version} · NASA replay</p>
      <p>{result.interpretation}</p>
    </> : <p>Loading classification…</p>}
    <small>Trained across FD001–FD004. Benchmark accuracy: 90.25%. This assessment is computed on demand; RUL and maintenance review remain separate.</small>
  </section>;
}
