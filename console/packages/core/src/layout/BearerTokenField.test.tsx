import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { BearerTokenField } from './BearerTokenField';
import { ToastProvider } from './ToastContext';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const JWT =
  'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbGljZS5lbmdpbmVlciJ9.signature-part-aaaaaaaaaaaaaaaa';

function renderField(value: string, onChange = vi.fn()) {
  return render(
    <ToastProvider>
      <BearerTokenField label="User bearer token" value={value} onChange={onChange} />
    </ToastProvider>,
  );
}

describe('BearerTokenField', () => {
  it('keeps demo tokens visible and editable', () => {
    const onChange = vi.fn();
    renderField('employee-demo-token', onChange);

    const input = screen.getByLabelText('User bearer token');
    expect(input).toHaveAttribute('type', 'text');
    expect(input).not.toHaveAttribute('readonly');
    expect(screen.queryByRole('button', { name: 'Reveal' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Copy' })).not.toBeInTheDocument();

    fireEvent.change(input, { target: { value: 'hr-demo-token' } });
    expect(onChange).toHaveBeenCalledWith('hr-demo-token');
  });

  it('masks JWTs as read-only until Reveal', () => {
    renderField(JWT);

    const input = screen.getByLabelText('User bearer token');
    expect(input).toHaveAttribute('type', 'password');
    expect(input).toHaveAttribute('readonly');
    expect(screen.getByRole('button', { name: 'Reveal' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy' })).toBeInTheDocument();
  });

  it('reveals a JWT for inspect or replace, then hides again', () => {
    const onChange = vi.fn();
    renderField(JWT, onChange);

    fireEvent.click(screen.getByRole('button', { name: 'Reveal' }));
    const input = screen.getByLabelText('User bearer token');
    expect(input).toHaveAttribute('type', 'text');
    expect(input).not.toHaveAttribute('readonly');
    expect(screen.getByRole('button', { name: 'Hide' })).toBeInTheDocument();

    fireEvent.change(input, { target: { value: 'employee-demo-token' } });
    expect(onChange).toHaveBeenCalledWith('employee-demo-token');
  });

  it('copies the access token to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });

    renderField(JWT);
    fireEvent.click(screen.getByRole('button', { name: 'Copy' }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(JWT);
    });
    expect(await screen.findByRole('status')).toHaveTextContent('Access token copied.');
  });
});
