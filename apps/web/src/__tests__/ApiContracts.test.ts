import { afterEach, describe, expect, it, vi } from 'vitest';
import { authApi, workOrdersApi } from '../services/api';

afterEach(() => vi.unstubAllGlobals());

describe('backend response contracts', () => {
  it.each(['outdated_evidence', 'version_conflict', 'forbidden', 'authentication_required'])(
    'preserves backend %s code and request id', async (code) => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
        JSON.stringify({ error: { code }, request_id: 'request-123' }),
        { status: 409, headers: { 'Content-Type': 'application/json' } }
      )));
      await expect(workOrdersApi.getWorkOrder('tenant', 'order')).rejects.toMatchObject({
        code, status: 409, requestId: 'request-123'
      });
    }
  );

  it('loads eligible assignees from the scoped endpoint across bounded pages', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ user_id: 'u1' }], next_offset: 100 }),
        { headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ user_id: 'u2' }], next_offset: null }),
        { headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    expect((await authApi.getEligibleAssignees('tenant')).items).toHaveLength(2);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/organizations/tenant/work-order-assignees?offset=0');
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/organizations/tenant/work-order-assignees?offset=100');
  });
});
