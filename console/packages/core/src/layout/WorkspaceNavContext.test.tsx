import * as React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { WorkspaceNavProvider, useWorkspaceNav } from './WorkspaceNavContext';

function NavSuite() {
  const { navigateTo, consumePendingAction } = useWorkspaceNav();
  const [last, setLast] = React.useState('unset');

  return (
    <div>
      <button type="button" onClick={() => navigateTo('audit', { type: 'open-trace' })}>
        go
      </button>
      <button
        type="button"
        onClick={() => {
          const action = consumePendingAction('audit');
          setLast(action ? JSON.stringify(action) : 'none');
        }}
      >
        consume
      </button>
      <span data-testid="last">{last}</span>
    </div>
  );
}

describe('WorkspaceNavProvider', () => {
  it('stores and consumes a pending workspace action once', () => {
    render(
      <WorkspaceNavProvider activeWorkspaceId="query" onActiveWorkspaceChange={() => undefined}>
        <NavSuite />
      </WorkspaceNavProvider>,
    );

    expect(screen.getByTestId('last')).toHaveTextContent('unset');
    fireEvent.click(screen.getByRole('button', { name: 'go' }));
    fireEvent.click(screen.getByRole('button', { name: 'consume' }));
    expect(screen.getByTestId('last')).toHaveTextContent('open-trace');
    fireEvent.click(screen.getByRole('button', { name: 'consume' }));
    expect(screen.getByTestId('last')).toHaveTextContent('none');
  });
});
