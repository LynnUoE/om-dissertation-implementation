#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 server for LitFinder (see docs/deploy-ec2.md):
# swap, Docker Engine + Compose from Docker's apt repository, a firewall and
# automatic security updates. Safe to run again.
#
#   sudo bash deploy/setup-server.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run it with sudo: sudo bash deploy/setup-server.sh" >&2
    exit 1
fi
user="${SUDO_USER:-ubuntu}"

echo "== Swap (2 GB): PyTorch and the build need more than the instance's 2 GB of RAM"
if ! swapon --show | grep -q /swapfile; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
echo 'vm.swappiness=10' > /etc/sysctl.d/99-litfinder.conf
sysctl --quiet --system

echo "== Packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q ca-certificates curl git ufw unattended-upgrades

echo "== Docker Engine and Compose (Docker's official apt repository)"
if ! command -v docker >/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    . /etc/os-release
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -q
    apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
usermod -aG docker "$user"  # Takes effect at the user's next login

echo "== Firewall: SSH, HTTP and HTTPS only"
# Docker-published ports bypass ufw, which is why the production compose file publishes only Caddy's
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

echo "== Automatic security updates"
dpkg-reconfigure -f noninteractive unattended-upgrades

echo
echo "Done. Log out and back in so '$user' can run docker without sudo, then:"
echo "  cp backend/.env.example backend/.env && nano backend/.env && chmod 600 backend/.env"
echo "  cp deploy/.env.example deploy/.env && nano deploy/.env && chmod 600 deploy/.env"
echo "  deploy/deploy.sh"
