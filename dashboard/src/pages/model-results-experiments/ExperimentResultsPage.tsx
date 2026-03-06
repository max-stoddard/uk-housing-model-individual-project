import { Navigate } from 'react-router-dom';

export function ExperimentResultsPage() {
  return <Navigate to="/experiments?type=sensitivity&mode=view" replace />;
}
