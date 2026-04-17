#!/usr/bin/env bash
set -euo pipefail

# Navigate to the script's folder, then UP one level to the project root
cd "$(dirname "$0")/.." || exit

npx --yes @mermaid-js/mermaid-cli -i docs/images/architecture_overview.mmd -o docs/images/architecture_overview.png
npx --yes @mermaid-js/mermaid-cli -i docs/images/experimental_workflow.mmd -o docs/images/experimental_workflow.png

echo "Mermaid diagrams exported successfully."
