import { describe, expect, it, vi } from 'vitest';

import { exposeConsoleRuntime } from '../runtime/expose';
import { probeEnterpriseInstalled } from './loadEnterpriseUi';

describe('exposeConsoleRuntime', () => {
  it('sets window bridge for EE bundles', () => {
    const runtime = exposeConsoleRuntime();
    expect(window.__RP_CONSOLE__).toBe(runtime);
    expect(runtime.React).toBeTruthy();
    expect(runtime.registerWorkspace).toBeTypeOf('function');
  });
});

describe('probeEnterpriseInstalled', () => {
  it('returns true when health reports enterprise_installed', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ enterprise_installed: true }),
      }),
    );
    await expect(probeEnterpriseInstalled('http://localhost:8090')).resolves.toBe(true);
  });

  it('returns false when health is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    await expect(probeEnterpriseInstalled('http://localhost:8090')).resolves.toBe(false);
  });
});
