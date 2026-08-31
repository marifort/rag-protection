import * as React from 'react';

import { registerWorkspace } from '../workspace/registry';

export type ConsoleRuntime = {
  React: typeof React;
  registerWorkspace: typeof registerWorkspace;
};

declare global {
  interface Window {
    __RP_CONSOLE__?: ConsoleRuntime;
  }
}

export function exposeConsoleRuntime(): ConsoleRuntime {
  const runtime: ConsoleRuntime = { React, registerWorkspace };
  window.__RP_CONSOLE__ = runtime;
  return runtime;
}

export function getConsoleRuntime(): ConsoleRuntime {
  const runtime = window.__RP_CONSOLE__;
  if (!runtime) {
    throw new Error('Console runtime not exposed — load CE shell before EE bundle');
  }
  return runtime;
}
