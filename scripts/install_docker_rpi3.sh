#!/bin/bash
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
    echo "Lancer ce script avec un utilisateur standard disposant de sudo, pas en root direct."
    exit 1
fi

ARCH="$(dpkg --print-architecture)"
CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"

if [ "$ARCH" != "armhf" ]; then
    echo "Architecture detectee: $ARCH"
    echo "Ce script cible Raspberry Pi OS 32-bit sur Raspberry Pi 3 (armhf)."
    exit 1
fi

if [ "$CODENAME" != "bookworm" ] && [ "$CODENAME" != "bullseye" ]; then
    echo "Distribution detectee: $CODENAME"
    echo "Ce script supporte Bookworm ou Bullseye."
    exit 1
fi

echo "[1/8] Suppression des paquets en conflit"
for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do
    sudo apt-get remove -y "$pkg" >/dev/null 2>&1 || true
done

echo "[2/8] Installation des prerequis"
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

echo "[3/8] Preparation du keyring Docker"
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/raspbian/gpg -o /tmp/docker.asc
sudo mv /tmp/docker.asc /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "[4/8] Configuration du depot Docker officiel"
echo \
  "deb [arch=armhf signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/raspbian ${CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

echo "[5/8] Actualisation des index APT"
sudo apt-get update

echo "[6/8] Recherche d'une version Docker 28.x compatible armhf"
DOCKER_VERSION="$(apt-cache madison docker-ce | awk '$3 ~ /^5:28\./ {print $3; exit}')"

if [ -z "${DOCKER_VERSION}" ]; then
    echo "Aucune version Docker 28.x n'a ete trouvee dans le depot officiel."
    echo "Verifier manuellement avec: apt-cache madison docker-ce"
    exit 1
fi

echo "Version retenue: ${DOCKER_VERSION}"

echo "[7/8] Installation de Docker Engine, Buildx et Compose"
sudo apt-get install -y \
    "docker-ce=${DOCKER_VERSION}" \
    "docker-ce-cli=${DOCKER_VERSION}" \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

echo "[8/8] Activation et test du service Docker"
sudo systemctl enable docker
sudo systemctl restart docker
sudo docker run --rm hello-world
sudo usermod -aG docker "$USER"

echo
echo "Installation terminee."
echo "Reconnecte-toi a la session pour utiliser Docker sans sudo."
echo "Verification apres reconnexion:"
echo "  docker --version"
echo "  docker compose version"
