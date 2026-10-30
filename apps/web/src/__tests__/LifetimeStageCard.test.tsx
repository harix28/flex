import { render, screen, waitFor } from '@testing-library/react';
import { vi, test, expect } from 'vitest';
import { LifetimeStageCard } from '../components/predictions/LifetimeStageCard';
import { classificationApi } from '../services/api';
vi.mock('../services/api', () => ({ classificationApi: { get: vi.fn() } }));

test('shows lifetime stage separately from diagnosis and clears on tenant change', async () => {
  vi.mocked(classificationApi.get).mockResolvedValueOnce({ lifetime_stage: 'late_lifetime', source_cycle: 95,
    model_version: 'combined-rf-20261030-v1', interpretation: 'Not a physical health diagnosis.' });
  const { rerender } = render(<LifetimeStageCard tenantId="a" machineId="one" />);
  expect(await screen.findByText('late lifetime')).toBeInTheDocument();
  expect(screen.getByText('Not a physical health diagnosis.')).toBeInTheDocument();
  vi.mocked(classificationApi.get).mockRejectedValueOnce(new Error('denied'));
  rerender(<LifetimeStageCard tenantId="b" machineId="two" />);
  await waitFor(() => expect(screen.queryByText('late lifetime')).not.toBeInTheDocument());
  expect(await screen.findByRole('status')).toHaveTextContent('Classification unavailable');
});
