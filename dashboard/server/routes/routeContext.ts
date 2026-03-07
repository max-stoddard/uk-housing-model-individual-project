import type express from 'express';
import type { RuntimeDependencyStatus } from '../lib/runtimeDeps';
import type { WriteAuthController } from '../lib/writeAuth';

export interface RuntimePolicy {
  devBypassActive: boolean;
  modelRunsConfigured: boolean;
  modelRunsEnabled: boolean;
  modelRunsDisabledReason: string | null;
  writeAuthConfigurationError: string | null;
}

export interface RouteContext {
  repoRoot: string;
  modelRunsConfiguredFromEnv: boolean;
  writeAuth: WriteAuthController;
  getRuntimeDependencies: () => RuntimeDependencyStatus;
  resolveRuntimePolicy: (req: express.Request) => RuntimePolicy;
  requireWriteAccess: (req: express.Request, res: express.Response) => boolean;
  requireExperimentsFeature: (req: express.Request, res: express.Response) => boolean;
  withMemoryLogging: (label: string, handler: express.RequestHandler) => express.RequestHandler;
}
