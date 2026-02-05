#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") <version>" >&2
  echo "Example: $(basename "$0") v0" >&2
}

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

version="$1"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
input_dir="${repo_root}/input-data-versions/${version}"
resources_dir="${repo_root}/src/main/resources"

if [[ ! -d "${input_dir}" ]]; then
  echo "Input data version not found: ${input_dir}" >&2
  usage
  exit 1
fi

removed_count="$(find "${resources_dir}" -maxdepth 1 -type f | wc -l | tr -d ' ')"
copied_count="$(find "${input_dir}" -maxdepth 1 -type f | wc -l | tr -d ' ')"

# Remove only top-level files from resources (keep directories intact).
find "${resources_dir}" -maxdepth 1 -type f -exec rm -f {} +

# Copy new version files into resources.
shopt -s nullglob
files=( "${input_dir}"/* )
shopt -u nullglob
if (( ${#files[@]} > 0 )); then
  cp -a "${files[@]}" "${resources_dir}/"
fi

echo "Switched resources to '${version}': removed ${removed_count} files, copied ${copied_count} files."
