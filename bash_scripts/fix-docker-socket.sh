#!/bin/bash
# Nuclear fix for Docker socket issues on lenovo_server
set -e

echo "🔧 NUCLEAR DOCKER FIX for lenovo_server"
echo "========================================"

# Kill everything Docker-related
echo "Stopping all Docker processes..."
systemctl stop docker.socket docker.service 2>/dev/null || true
pkill -f dockerd || true
pkill -f containerd || true
sleep 3

# Clean up socket files
echo "Cleaning up socket files..."
rm -rf /var/run/docker.sock
rm -rf /var/run/docker.pid
rm -rf /var/run/docker

# Ensure containerd is running
echo "Starting containerd..."
systemctl start containerd
systemctl enable containerd
sleep 2

# Create Docker configuration
echo "Creating Docker daemon configuration..."
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << 'EOF'
{
  "hosts": [
    "unix:///var/run/docker.sock"
  ],
  "data-root": "/var/lib/docker",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
EOF

# Create systemd override
echo "Creating systemd service override..."
mkdir -p /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd --containerd=/run/containerd/containerd.sock
Environment=
EOF

# Reload and start
echo "Reloading systemd and starting Docker..."
systemctl daemon-reload
systemctl enable docker.service
systemctl start docker.service

# Wait for socket
echo "Waiting for Docker socket..."
timeout=30
count=0
while [ ! -S /var/run/docker.sock ] && [ $count -lt $timeout ]; do
    sleep 1
    count=$((count + 1))
done

if [ -S /var/run/docker.sock ]; then
    echo "✅ Docker socket created successfully!"
    
    # Fix permissions
    chown root:docker /var/run/docker.sock
    chmod 660 /var/run/docker.sock
    
    # Test Docker
    if docker info > /dev/null 2>&1; then
        echo "✅ Docker daemon is responding!"
        echo "Docker version: $(docker --version)"
        echo "🎉 NUCLEAR FIX SUCCESSFUL!"
        exit 0
    else
        echo "❌ Docker socket exists but daemon not responding"
        exit 1
    fi
else
    echo "❌ Failed to create Docker socket after $timeout seconds"
    exit 1
fi