## syntax=docker/dockerfile:1
FROM mcr.microsoft.com/devcontainers/base:ubuntu

# Add anything you ALWAYS want baked in (keep minimal)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git vim net-tools gnupg bash-completion unzip


RUN install -m 0755 -d /etc/apt/keyrings; \
  curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.30/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg; \
  echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.30/deb/ /" > /etc/apt/sources.list.d/kubernetes.list; \
  apt-get update && apt-get install -y --no-install-recommends kubectl; \
  kubectl completion bash > /etc/bash_completion.d/kubectl

# helm (official APT repo via Buildkite)
RUN install -m 0755 -d /etc/apt/keyrings && \
  curl -fsSL https://packages.buildkite.com/helm-linux/helm-debian/gpgkey \
    | gpg --dearmor -o /etc/apt/keyrings/helm.gpg && \
  echo "deb [signed-by=/etc/apt/keyrings/helm.gpg] https://packages.buildkite.com/helm-linux/helm-debian/any/ any main" \
    > /etc/apt/sources.list.d/helm-stable-debian.list && \
  apt-get update && apt-get install -y --no-install-recommends helm && \
  helm completion bash > /etc/bash_completion.d/helm

RUN KUBELOGIN_VERSION=v1.28.1 && \
  curl -LO "https://github.com/int128/kubelogin/releases/download/${KUBELOGIN_VERSION}/kubelogin_linux_amd64.zip" && \
  unzip kubelogin_linux_amd64.zip && \
  mv kubelogin /usr/local/bin/kubectl-oidc_login && \
  chmod +x /usr/local/bin/kubectl-oidc_login && \
  rm kubelogin_linux_amd64.zip

# The base image already has user `vscode` with passwordless sudo.
USER vscode
ENV HOME=/home/vscode
ENV PATH=/home/vscode/.local/bin:/home/vscode/go/bin:$PATH
