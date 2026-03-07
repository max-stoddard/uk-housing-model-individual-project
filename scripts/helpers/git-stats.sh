#!/usr/bin/env bash
set -euo pipefail

base_commit="4e89f5e277cdba4b4ef0c08254e5731e19bd51c3"
source_file_pathspecs=(
  '*.java'
  '*.cpp'
  '*.cc'
  '*.cxx'
  '*.hpp'
  '*.hh'
  '*.hxx'
  '*.ts'
  '*.tsx'
  '*.py'
  '*.sh'
)

git diff --shortstat "$base_commit" HEAD -- "${source_file_pathspecs[@]}"
