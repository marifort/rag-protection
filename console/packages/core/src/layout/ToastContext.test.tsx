import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider, useToast } from './ToastContext';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function ToastProbe({ message, kind }: { message: string; kind?: 'ok' | 'err' }) {
  const { toast } = useToast();
  return (
    <button type="button" onClick={() => toast(message, kind)}>
      fire toast
    </button>
  );
}

describe('ToastProvider', () => {
  it('shows a success toast with role=status', () => {
    render(
      <ToastProvider>
        <ToastProbe message="Saved." />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'fire toast' }));
    const toast = screen.getByText('Saved.');
    expect(toast).toHaveAttribute('role', 'status');
    expect(toast.className).toContain('show');
    expect(toast.className).not.toContain('err');
  });

  it('applies the err class for error toasts', () => {
    render(
      <ToastProvider>
        <ToastProbe message="Request failed" kind="err" />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'fire toast' }));
    const toast = screen.getByText('Request failed');
    expect(toast.className).toContain('err');
  });

  it('auto-dismisses after four seconds', () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <ToastProbe message="Transient" />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'fire toast' }));
    expect(screen.getByText('Transient')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.getByText('Transient').className).not.toContain('show');
  });
});
