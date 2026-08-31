import * as React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useAuth as useAuthFromContext } from '../auth/AuthContext';
import { useToast as useToastFromContext } from '../layout/ToastContext';
import { useWorkspaceNav as useWorkspaceNavFromContext } from '../layout/WorkspaceNavContext';
import { loadEnterpriseUi, probeEnterpriseInstalled } from '../enterprise/loadEnterpriseUi';
import { exposeConsoleRuntime } from '../runtime/expose';
import { registerWorkspace } from '../workspace/registry';

type EnterpriseBootstrapProps = {
  baseUrl: string;
  onLoaded: () => void;
  onUnavailable: () => void;
};

function EnterpriseBootstrap({ baseUrl, onLoaded, onUnavailable }: EnterpriseBootstrapProps) {
  const onLoadedRef = useRef(onLoaded);
  const onUnavailableRef = useRef(onUnavailable);
  onLoadedRef.current = onLoaded;
  onUnavailableRef.current = onUnavailable;

  useEffect(() => {
    exposeConsoleRuntime();
    let cancelled = false;

    void (async () => {
      const installed = await probeEnterpriseInstalled(baseUrl);
      if (cancelled) return;
      if (!installed) {
        onUnavailableRef.current();
        return;
      }
      const module = await loadEnterpriseUi({ baseUrl });
      if (cancelled) return;
      if (!module) {
        onUnavailableRef.current();
        return;
      }
      module.registerEeWorkspaces({
        registerWorkspace,
        React,
        useAuth: useAuthFromContext,
        useToast: useToastFromContext,
        useWorkspaceNav: useWorkspaceNavFromContext,
      });
      onLoadedRef.current();
    })();

    return () => {
      cancelled = true;
    };
  }, [baseUrl]);

  return null;
}

export type EnterpriseBootstrapSlotProps = {
  baseUrl: string;
  onLoaded: () => void;
  onUnavailable: () => void;
};

export function EnterpriseBootstrapSlot(props: EnterpriseBootstrapSlotProps) {
  return React.createElement(EnterpriseBootstrap, props);
}

export type UseEnterpriseEditionOptions = {
  initialEdition?: 'ce' | 'ee' | 'all';
  bootstrapEnterprise?: boolean;
  baseUrl?: string;
};

export function useEnterpriseEdition({
  initialEdition = 'ce',
  bootstrapEnterprise = false,
  baseUrl = '',
}: UseEnterpriseEditionOptions) {
  const [edition, setEdition] = useState<'ce' | 'ee' | 'all'>(initialEdition);
  const [status, setStatus] = useState<'idle' | 'loading' | 'loaded' | 'unavailable'>(
    bootstrapEnterprise ? 'loading' : 'idle',
  );

  const onLoaded = useCallback(() => {
    setEdition('all');
    setStatus('loaded');
  }, []);

  const onUnavailable = useCallback(() => {
    setStatus('unavailable');
  }, []);

  const bootstrap = useMemo(
    () =>
      bootstrapEnterprise && baseUrl
        ? React.createElement(EnterpriseBootstrap, { baseUrl, onLoaded, onUnavailable })
        : null,
    [bootstrapEnterprise, baseUrl, onLoaded, onUnavailable],
  );

  const subtitleSuffix =
    status === 'loading'
      ? 'Loading Enterprise workspaces…'
      : status === 'loaded'
        ? 'Enterprise workspaces loaded.'
        : status === 'unavailable'
          ? 'Enterprise Edition not detected — CE workspaces only.'
          : '';

  return { edition, bootstrap, subtitleSuffix };
}
