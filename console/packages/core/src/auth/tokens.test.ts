import { describe, expect, it } from 'vitest';

import {
  clearPersistedIdpEmail,
  isReplaceableAdminToken,
  isStaticDemoAdminToken,
  loadPersistedIdpEmail,
  looksLikeJwt,
  persistIdpEmail,
} from './tokens';

/** Minimal three-segment string that passes looksLikeJwt. */
const JWT_A =
  'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLWEifQ.signature-part-aaaaaaaaaaaaaaaa';
const JWT_B =
  'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLWIifQ.signature-part-bbbbbbbbbbbbbbbb';

describe('looksLikeJwt', () => {
  it('accepts three non-empty segments', () => {
    expect(looksLikeJwt(JWT_A)).toBe(true);
  });

  it('rejects demo tokens', () => {
    expect(looksLikeJwt('employee-demo-token')).toBe(false);
  });
});

describe('isStaticDemoAdminToken', () => {
  it('accepts shipped demo operator keys including scoped keys', () => {
    expect(isStaticDemoAdminToken('rag-admin-demo-key')).toBe(true);
    expect(isStaticDemoAdminToken('rag-policy-admin-key')).toBe(true);
    expect(isStaticDemoAdminToken('acme-ingest-admin')).toBe(true);
    expect(isStaticDemoAdminToken('globex-audit-reader')).toBe(true);
  });

  it('rejects person tokens and JWTs', () => {
    expect(isStaticDemoAdminToken('employee-demo-token')).toBe(false);
    expect(isStaticDemoAdminToken('hr-demo-token')).toBe(false);
    expect(isStaticDemoAdminToken(JWT_A)).toBe(false);
  });
});

describe('isReplaceableAdminToken', () => {
  it('treats empty, placeholder, and demo keys as replaceable', () => {
    expect(isReplaceableAdminToken('')).toBe(true);
    expect(isReplaceableAdminToken('   ')).toBe(true);
    expect(isReplaceableAdminToken('RAG_ADMIN_API_KEY')).toBe(true);
    expect(isReplaceableAdminToken('rag-admin-demo-key')).toBe(true);
  });

  it('does not replace a custom break-glass key or a JWT', () => {
    expect(isReplaceableAdminToken('my-private-admin-key')).toBe(false);
    expect(isReplaceableAdminToken(JWT_A)).toBe(false);
  });
});

describe('persistIdpEmail / loadPersistedIdpEmail', () => {
  it('restores email for the matching JWT after reload', () => {
    persistIdpEmail(JWT_A, 'marina@example.com');
    expect(loadPersistedIdpEmail(JWT_A)).toBe('marina@example.com');
  });

  it('does not return email for a different JWT', () => {
    persistIdpEmail(JWT_A, 'marina@example.com');
    expect(loadPersistedIdpEmail(JWT_B)).toBe('');
  });

  it('clears persisted email', () => {
    persistIdpEmail(JWT_A, 'marina@example.com');
    clearPersistedIdpEmail();
    expect(loadPersistedIdpEmail(JWT_A)).toBe('');
  });

  it('recovers email from OIDC ticket sessionStorage cache', () => {
    sessionStorage.setItem(
      'ragProtectionOidcTicket:abc',
      JSON.stringify({ token: JWT_A, email: 'from-ticket@example.com' }),
    );
    expect(loadPersistedIdpEmail(JWT_A)).toBe('from-ticket@example.com');
    // Promoted into localStorage for subsequent reloads.
    expect(localStorage.getItem('ragProtectionUiIdpEmail')).toBe('from-ticket@example.com');
  });
});
