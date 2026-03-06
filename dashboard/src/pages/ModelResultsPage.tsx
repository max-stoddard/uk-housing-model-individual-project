import { Navigate } from 'react-router-dom';

export function ModelResultsPage() {
  return <Navigate to="/experiments?type=manual&mode=view" replace />;
}
