import { AppShell, registerWorkspace } from '../index';
import '../theme/tokens.css';
import { createRoot } from 'react-dom/client';

function OverviewPane() {
  return <p>Overview workspace (demo)</p>;
}

registerWorkspace({
  id: 'overview',
  label: 'Overview',
  edition: 'ce',
  order: 0,
  component: OverviewPane,
});

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(
    <AppShell defaultBaseUrl={window.location.origin} edition="ce" />,
  );
}

export { AppShell };
