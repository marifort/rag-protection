import { describe, expect, it, vi } from 'vitest';

import { ApiError, fetchJson } from './client';

describe('fetchJson', () => {
  it('throws ApiError with status and detail on HTTP errors', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      text: async () => JSON.stringify({ detail: 'admin token required' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(fetchJson('/admin/policy-config', { baseUrl: 'http://localhost:8090' })).rejects.toMatchObject({
      name: 'ApiError',
      status: 403,
      message: 'admin token required',
    });
  });
});

describe('ApiError', () => {
  it('stores response body', () => {
    const error = new ApiError('blocked', 400, { detail: 'blocked' });
    expect(error.body).toEqual({ detail: 'blocked' });
  });
});
