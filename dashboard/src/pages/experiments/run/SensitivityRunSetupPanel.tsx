import { SensitivitySetupCard } from '../../run-experiments/SensitivitySetupCard';
import type { ExperimentRunController } from './useExperimentRunController';

interface SensitivityRunSetupPanelProps {
  controller: ExperimentRunController;
  runActionsDisabled: boolean;
}

export function SensitivityRunSetupPanel({ controller, runActionsDisabled }: SensitivityRunSetupPanelProps) {
  return (
    <SensitivitySetupCard
      executionDisabled={runActionsDisabled}
      isLoadingOptions={controller.isLoadingOptions || !controller.options}
      selectedBaseline={controller.selectedBaseline}
      onBaselineChange={controller.onBaselineChange}
      snapshots={controller.options?.snapshots ?? []}
      numericParameters={controller.numericSensitivityParameters}
      parameterKey={controller.sensitivityParameterKey}
      onParameterKeyChange={(value) => {
        controller.setSensitivityParameterKey(value);
      }}
      minValue={controller.sensitivityMin}
      maxValue={controller.sensitivityMax}
      onMinValueChange={(value) => {
        controller.setSensitivityMin(value);
      }}
      onMaxValueChange={(value) => {
        controller.setSensitivityMax(value);
      }}
      title={controller.sensitivityTitle}
      onTitleChange={controller.setSensitivityTitle}
      retainFullOutput={controller.sensitivityRetainFullOutput}
      onRetainFullOutputChange={controller.setSensitivityRetainFullOutput}
      selectedParameter={controller.selectedSensitivityParameter}
      warnings={controller.sensitivityWarnings}
      isSubmitting={controller.isSubmittingSensitivity}
      isCanceling={controller.isCancelingSensitivity}
      sensitivitySubmissionLockedByManual={controller.sensitivitySubmissionLockedByManual}
      lockMessage={
        controller.sensitivitySubmissionLockedByManual
          ? `Sensitivity experiments are locked while manual job ${controller.lockManualId} is active.`
          : null
      }
      hasActiveSensitivityJob={controller.hasActiveSensitivityJob}
      onSubmit={(confirmWarnings) => {
        void controller.onSubmitSensitivity(confirmWarnings);
      }}
      onCancelActive={() => {
        void controller.onCancelActiveSensitivity();
      }}
    />
  );
}
