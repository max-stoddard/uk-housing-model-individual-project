import type { ComponentType } from 'react';
import type { ExperimentType } from './types';
import { ManualRunSetupPanel } from './run/ManualRunSetupPanel';
import { SensitivityRunSetupPanel } from './run/SensitivityRunSetupPanel';
import type { ExperimentRunController } from './run/useExperimentRunController';
import { ManualResultsView } from './view/ManualResultsView';
import { SensitivityResultsView } from './view/SensitivityResultsView';

export interface ExperimentRunRendererProps {
  controller: ExperimentRunController;
  runActionsDisabled: boolean;
}

export interface ExperimentViewRendererProps {
  canWrite: boolean;
  requestedRunId: string;
  requestedExperimentId: string;
  onFocusedRunIdChange: (runId: string) => void;
  onSelectedExperimentIdChange: (experimentId: string) => void;
  sidebarSubtitle: string;
}

interface ExperimentTypeDefinition {
  label: string;
  viewSidebarSubtitle: string;
  RunSetupComponent: ComponentType<ExperimentRunRendererProps>;
  ViewComponent: ComponentType<ExperimentViewRendererProps>;
}

const ManualViewRenderer: ComponentType<ExperimentViewRendererProps> = ({
  canWrite,
  requestedRunId,
  onFocusedRunIdChange,
  sidebarSubtitle
}) => (
  <ManualResultsView
    canWrite={canWrite}
    requestedRunId={requestedRunId}
    onFocusedRunIdChange={onFocusedRunIdChange}
    sidebarSubtitle={sidebarSubtitle}
  />
);

const SensitivityViewRenderer: ComponentType<ExperimentViewRendererProps> = ({
  requestedExperimentId,
  onSelectedExperimentIdChange,
  sidebarSubtitle
}) => (
  <SensitivityResultsView
    requestedExperimentId={requestedExperimentId}
    onSelectedExperimentIdChange={onSelectedExperimentIdChange}
    sidebarSubtitle={sidebarSubtitle}
  />
);

export const experimentTypeRegistry: Record<ExperimentType, ExperimentTypeDefinition> = {
  manual: {
    label: 'Manual Parameters',
    viewSidebarSubtitle: 'Model Runs',
    RunSetupComponent: ManualRunSetupPanel,
    ViewComponent: ManualViewRenderer
  },
  sensitivity: {
    label: 'Sensitivity',
    viewSidebarSubtitle: 'Experiments',
    RunSetupComponent: SensitivityRunSetupPanel,
    ViewComponent: SensitivityViewRenderer
  }
};
