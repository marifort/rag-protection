import { describe, expect, it, vi } from 'vitest';

import { clearWorkspacesForTests, listWorkspaces, registerWorkspace, subscribeWorkspaces } from './registry';

function StubPane() {
  return null;
}

describe('workspace registry', () => {
  it('registers and sorts workspaces', () => {
    clearWorkspacesForTests();
    registerWorkspace({ id: 'b', label: 'B', edition: 'ce', order: 2, component: StubPane });
    registerWorkspace({ id: 'a', label: 'A', edition: 'ce', order: 1, component: StubPane });
    expect(listWorkspaces('ce').map((w) => w.id)).toEqual(['a', 'b']);
    clearWorkspacesForTests();
  });

  it('notifies subscribers when workspaces change', () => {
    clearWorkspacesForTests();
    const listener = vi.fn();
    const unsubscribe = subscribeWorkspaces(listener);
    registerWorkspace({ id: 'x', label: 'X', edition: 'ee', order: 1, component: StubPane });
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
    registerWorkspace({ id: 'y', label: 'Y', edition: 'ee', order: 2, component: StubPane });
    expect(listener).toHaveBeenCalledTimes(1);
    clearWorkspacesForTests();
  });
});
