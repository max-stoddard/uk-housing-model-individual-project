import fs from 'node:fs';
import path from 'node:path';
import { compareVersions } from './versioning';
import type { ValidationStatus } from '../../shared/types';

export interface VersionNoteValidation {
  status: ValidationStatus;
  income_diff_pct: number | null;
  housing_wealth_diff_pct: number | null;
  financial_wealth_diff_pct: number | null;
  note?: string;
}

export interface VersionNoteEntry {
  version_id: string;
  snapshot_folder: string;
  validation_dataset: string;
  description: string;
  updated_data_sources: string[];
  calibration_files: string[];
  config_parameters: string[];
  method_variations: VersionNoteMethodVariation[];
  validation: VersionNoteValidation;
}

export interface VersionNoteMethodVariation {
  config_parameters: string[];
  improvement_summary: string;
  why_changed: string;
  method_chosen?: string;
  decision_logic?: string;
}

interface VersionNotesDocument {
  author: string;
  schema_version: number;
  description: string;
  entries: VersionNoteEntry[];
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function assertString(value: unknown, field: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new Error(`Invalid version notes schema: ${field} must be a non-empty string`);
  }
  return value;
}

function assertStringArray(value: unknown, field: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) {
    throw new Error(`Invalid version notes schema: ${field} must be a string array`);
  }
  return value;
}

function assertNullableNumber(value: unknown, field: string): number | null {
  if (value === null) {
    return null;
  }
  if (typeof value !== 'number' || Number.isNaN(value)) {
    throw new Error(`Invalid version notes schema: ${field} must be a number or null`);
  }
  return value;
}

function parseValidation(value: unknown, field: string): VersionNoteValidation {
  if (!isObject(value)) {
    throw new Error(`Invalid version notes schema: ${field} must be an object`);
  }

  const status = value.status;
  if (status !== 'complete' && status !== 'in_progress') {
    throw new Error(`Invalid version notes schema: ${field}.status must be 'complete' or 'in_progress'`);
  }

  const note = value.note;
  if (note !== undefined && typeof note !== 'string') {
    throw new Error(`Invalid version notes schema: ${field}.note must be a string when provided`);
  }

  return {
    status,
    income_diff_pct: assertNullableNumber(value.income_diff_pct, `${field}.income_diff_pct`),
    housing_wealth_diff_pct: assertNullableNumber(value.housing_wealth_diff_pct, `${field}.housing_wealth_diff_pct`),
    financial_wealth_diff_pct: assertNullableNumber(value.financial_wealth_diff_pct, `${field}.financial_wealth_diff_pct`),
    note
  };
}

function parseEntry(value: unknown, index: number): VersionNoteEntry {
  if (!isObject(value)) {
    throw new Error(`Invalid version notes schema: entries[${index}] must be an object`);
  }

  const methodVariations = value.method_variations;
  if (!Array.isArray(methodVariations)) {
    throw new Error(`Invalid version notes schema: entries[${index}].method_variations must be an array`);
  }

  return {
    version_id: assertString(value.version_id, `entries[${index}].version_id`),
    snapshot_folder: assertString(value.snapshot_folder, `entries[${index}].snapshot_folder`),
    validation_dataset: assertString(value.validation_dataset, `entries[${index}].validation_dataset`),
    description: assertString(value.description, `entries[${index}].description`),
    updated_data_sources: assertStringArray(value.updated_data_sources, `entries[${index}].updated_data_sources`),
    calibration_files: assertStringArray(value.calibration_files, `entries[${index}].calibration_files`),
    config_parameters: assertStringArray(value.config_parameters, `entries[${index}].config_parameters`),
    method_variations: methodVariations.map((variation, variationIndex) =>
      parseMethodVariation(variation, index, variationIndex)
    ),
    validation: parseValidation(value.validation, `entries[${index}].validation`)
  };
}

function parseMethodVariation(value: unknown, entryIndex: number, variationIndex: number): VersionNoteMethodVariation {
  if (!isObject(value)) {
    throw new Error(
      `Invalid version notes schema: entries[${entryIndex}].method_variations[${variationIndex}] must be an object`
    );
  }

  const methodChosen = value.method_chosen;
  if (methodChosen !== undefined && typeof methodChosen !== 'string') {
    throw new Error(
      `Invalid version notes schema: entries[${entryIndex}].method_variations[${variationIndex}].method_chosen must be a string when provided`
    );
  }

  const decisionLogic = value.decision_logic;
  if (decisionLogic !== undefined && typeof decisionLogic !== 'string') {
    throw new Error(
      `Invalid version notes schema: entries[${entryIndex}].method_variations[${variationIndex}].decision_logic must be a string when provided`
    );
  }

  return {
    config_parameters: assertStringArray(
      value.config_parameters,
      `entries[${entryIndex}].method_variations[${variationIndex}].config_parameters`
    ),
    improvement_summary: assertString(
      value.improvement_summary,
      `entries[${entryIndex}].method_variations[${variationIndex}].improvement_summary`
    ),
    why_changed: assertString(value.why_changed, `entries[${entryIndex}].method_variations[${variationIndex}].why_changed`),
    method_chosen: methodChosen,
    decision_logic: decisionLogic
  };
}

function parseDocument(value: unknown): VersionNotesDocument {
  if (!isObject(value)) {
    throw new Error('Invalid version notes schema: root must be an object');
  }

  const entriesValue = value.entries;
  if (!Array.isArray(entriesValue)) {
    throw new Error('Invalid version notes schema: entries must be an array');
  }

  const document: VersionNotesDocument = {
    author: assertString(value.author, 'author'),
    schema_version: Number(value.schema_version),
    description: assertString(value.description, 'description'),
    entries: entriesValue.map((entry, index) => parseEntry(entry, index))
  };

  if (!Number.isFinite(document.schema_version)) {
    throw new Error('Invalid version notes schema: schema_version must be a number');
  }

  return document;
}

export function getVersionNotesPath(repoRoot: string): string {
  return path.join(repoRoot, 'input-data-versions', 'version-notes.json');
}

export function loadVersionNotes(repoRoot: string): VersionNoteEntry[] {
  const notesPath = getVersionNotesPath(repoRoot);
  if (!fs.existsSync(notesPath)) {
    throw new Error(`Missing version notes file: ${path.relative(repoRoot, notesPath)}`);
  }

  let raw: unknown;
  try {
    raw = JSON.parse(fs.readFileSync(notesPath, 'utf-8'));
  } catch (error) {
    throw new Error(`Invalid version notes JSON: ${(error as Error).message}`);
  }

  const document = parseDocument(raw);

  return [...document.entries].sort((a, b) => {
    const folderCompare = compareVersions(a.snapshot_folder, b.snapshot_folder);
    if (folderCompare !== 0) {
      return folderCompare;
    }
    return a.version_id.localeCompare(b.version_id);
  });
}
