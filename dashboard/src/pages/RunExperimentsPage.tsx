import { Navigate } from 'react-router-dom';

export function RunExperimentsPage() {
  return <Navigate to="/experiments?type=manual&mode=run" replace />;
}
