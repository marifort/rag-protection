import { useEffect, useState } from 'react';

import { useAuth, type HealthResponse } from '@rag-protection/console-core';

import { useRefresh } from '../refresh/RefreshContext';
import { fmtCount } from './format';

type AuditStatus = NonNullable<HealthResponse['audit']>;

export function AuditHistoryBanner() {
  const { api } = useAuth();
  const { tick } = useRefresh();
  const [auditStatus, setAuditStatus] = useState<AuditStatus | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const body = await api.health();
        if (!cancelled) setAuditStatus(body.audit ?? null);
      } catch {
        if (!cancelled) setAuditStatus(null);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [api, tick]);

  if (!auditStatus || auditStatus.file_sink) return null;

  const bufferMax = Number(auditStatus.buffer_max) || 0;
  const bufferCount = Number(auditStatus.buffer_count) || 0;

  return (
    <div className="audit-history-banner">
      <strong>Limited history</strong> — no durable JSONL audit sink is configured (
      <code>RAG_AUDIT_FILE</code>). Charts and exports reflect the in-memory ring buffer only (
      {fmtCount(bufferCount)} of {fmtCount(bufferMax)} events). Enable <code>audit.retention_days</code> + file
      sink (E4.3) for multi-day POC history.
    </div>
  );
}
