#!/usr/bin/env bash
set -euo pipefail

vscode_project_root="${1:?vscode_project_root required}"

claude_dir="${vscode_project_root}/claude"
mkdir -p "${claude_dir}/.claude"
touch "${claude_dir}/.claude.json"
touch "${claude_dir}/.claude.json.backup"

codex_dir="${vscode_project_root}/codex"
mkdir -p "${codex_dir}"
touch "${codex_dir}/config.toml"

touch "${vscode_project_root}/local.env"
touch "${vscode_project_root}/kube-config"
mkdir -p "${vscode_project_root}/kube-cache"

echo "Ensured:"
echo " - ${claude_dir}/.claude"
echo " - ${claude_dir}/.claude.json"
echo " - ${claude_dir}/.claude.json.backup"
echo " - ${codex_dir}/config.toml"
echo " - ${vscode_project_root}/local.env"
echo " - ${vscode_project_root}/kube-config"
