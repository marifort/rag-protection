import { useEffect, useState } from 'react';

import { looksLikeJwt } from '../auth/tokens';
import { useToast } from './ToastContext';

export type BearerTokenFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  title?: string;
};

/**
 * Demo tokens stay visible and editable. JWTs (IdP Sign-in or paste) are
 * masked and read-only until Reveal, with Copy for curl / jwt.io.
 */
export function BearerTokenField({
  label,
  value,
  onChange,
  placeholder,
  title,
}: BearerTokenFieldProps) {
  const jwt = looksLikeJwt(value);
  const [revealed, setRevealed] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    if (!jwt) setRevealed(false);
  }, [jwt]);

  async function copyToken() {
    try {
      await navigator.clipboard.writeText(value);
      toast('Access token copied.');
    } catch {
      toast('Could not copy access token.', 'err');
    }
  }

  const jwtTitle = revealed
    ? title
    : 'IdP access token (masked). Reveal to inspect or replace; Copy for curl / jwt.io.';

  return (
    <label>
      {label}
      <div className={jwt ? 'bearer-token-row' : undefined}>
        <input
          type={jwt && !revealed ? 'password' : 'text'}
          value={value}
          readOnly={jwt && !revealed}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          data-1p-ignore="true"
          data-lpignore="true"
          placeholder={placeholder}
          title={jwt ? jwtTitle : title}
          aria-label={label}
          onChange={(event) => onChange(event.target.value)}
        />
        {jwt ? (
          <span className="bearer-token-actions">
            <button type="button" onClick={() => setRevealed((open) => !open)}>
              {revealed ? 'Hide' : 'Reveal'}
            </button>
            <button type="button" onClick={() => void copyToken()}>
              Copy
            </button>
          </span>
        ) : null}
      </div>
    </label>
  );
}
