#!/bin/bash
set -e

echo "Running post-create setup..."

echo "Fixing npm cache ownership..."
mkdir -p "$HOME/.npm" "$HOME/.cache" "$HOME/.config" "$HOME/.npm-global/bin"
sudo chown -R "$(id -u)":"$(id -g)" "$HOME/.npm" "$HOME/.cache" "$HOME/.config" "$HOME/.npm-global"


# Install Claude Code
echo "Installing Claude Code..."
npm install -g @anthropic-ai/claude-code
npm install -g @modelcontextprotocol/inspector
npm install -g @upstash/context7-mcp

# Add other setup commands here as needed
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
else
  echo "requirements.txt not found; skipping pip install."
  # If you want to hard-fail instead, uncomment:
  # exit 1
fi
#go mod download

echo "Post-create setup complete!"
