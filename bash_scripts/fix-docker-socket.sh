#!/bin/bash
# Nuclear fix for Docker socket issues on lenovo_server with proper cleanup
set -e

echo "🔧 NUCLEAR DOCKER FIX for lenovo_server with Cleanup"
echo "===================================================="

# Function to check if Docker is responding
check_docker_health() {
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to cleanup shutdown Portainer agents
cleanup_portainer_agents() {
    echo "🧹 Cleaning up shutdown Portainer agents..."
    
    if command -v docker >/dev/null 2>&1; then
        # Remove all stopped Portainer agent containers
        echo "Removing stopped Portainer agent containers..."
        docker ps -a --filter "name=portainer" --filter "status=exited" --format "{{.ID}}" | \
            xargs -r docker rm -f 2>/dev/null || true
        
        # Remove orphaned Portainer agent containers
        docker ps -a --filter "ancestor=portainer/agent" --filter "status=exited" --format "{{.ID}}" | \
            xargs -r docker rm -f 2>/dev/null || true
        
        # Clean up any dangling Portainer agent containers
        docker container ls -a --filter "label=io.portainer.agent" --filter "status=exited" --format "{{.ID}}" | \
            xargs -r docker rm -f 2>/dev/null || true
        
        echo "✅ Portainer agent cleanup completed"
    fi
}

# Function to gracefully handle existing services
handle_existing_services() {
    echo "🔄 Handling existing Docker services gracefully..."
    
    if command -v docker >/dev/null 2>&1; then
        # Get list of running Portainer agents before shutdown
        echo "Detecting existing Portainer agents..."
        docker ps --filter "name=portainer" --format "{{.Names}}" > /tmp/portainer_agents.txt 2>/dev/null || true
        
        # Gracefully stop services instead of killing
        echo "Gracefully stopping Docker services..."
        systemctl stop docker.socket 2>/dev/null || true
        sleep 2
        systemctl stop docker.service 2>/dev/null || true
        sleep 3
        
        # Only kill if graceful stop failed
        if pgrep -f dockerd >/dev/null; then
            echo "Graceful stop failed, force killing Docker processes..."
            pkill -TERM -f dockerd 2>/dev/null || true
            sleep 2
            pkill -KILL -f dockerd 2>/dev/null || true
        fi
        
        if pgrep -f containerd >/dev/null; then
            echo "Force killing containerd processes..."
            pkill -TERM -f containerd 2>/dev/null || true
            sleep 2
            pkill -KILL -f containerd 2>/dev/null || true
        fi
    fi
}

# Check if Docker is already working properly
echo "🔍 Checking current Docker status..."
if check_docker_health && [ -S /var/run/docker.sock ]; then
    echo "✅ Docker is already working properly!"
    echo "ℹ️  Running cleanup check anyway..."
    cleanup_portainer_agents
    echo "🎉 NO FIX NEEDED - Docker is healthy!"
    exit 0
fi

echo "⚠️  Docker socket issue detected, proceeding with fix..."

# Cleanup any existing shutdown agents first
cleanup_portainer_agents

# Handle existing services gracefully
handle_existing_services

# Clean up socket files
echo "🧹 Cleaning up socket files..."
rm -rf /var/run/docker.sock
rm -rf /var/run/docker.pid
rm -rf /var/run/docker

# Ensure containerd is running
echo "🔄 Starting containerd..."
systemctl start containerd
systemctl enable containerd
sleep 2

# Create Docker configuration
echo "⚙️  Creating Docker daemon configuration..."
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
echo "⚙️  Creating systemd service override..."
mkdir -p /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd --containerd=/run/containerd/containerd.sock
Environment=
KillMode=mixed
Restart=always
RestartSec=5
EOF

# Reload and start
echo "🔄 Reloading systemd and starting Docker..."
systemctl daemon-reload
systemctl enable docker.service
systemctl start docker.service

# Wait for socket with better feedback
echo "⏳ Waiting for Docker socket..."
timeout=60
count=0
while [ ! -S /var/run/docker.sock ] && [ $count -lt $timeout ]; do
    if [ $((count % 10)) -eq 0 ]; then
        echo "   Still waiting... ($count/$timeout seconds)"
    fi
    sleep 1
    count=$((count + 1))
done

if [ -S /var/run/docker.sock ]; then
    echo "✅ Docker socket created successfully!"
    
    # Fix permissions
    chown root:docker /var/run/docker.sock
    chmod 660 /var/run/docker.sock
    
    # Wait a moment for Docker daemon to fully initialize
    echo "⏳ Waiting for Docker daemon to initialize..."
    sleep 5
    
    # Test Docker with retries
    docker_ready=false
    for i in {1..10}; do
        if docker info > /dev/null 2>&1; then
            docker_ready=true
            break
        fi
        echo "   Docker not ready yet, attempt $i/10..."
        sleep 2
    done
    
    if [ "$docker_ready" = true ]; then
        echo "✅ Docker daemon is responding!"
        echo "Docker version: $(docker --version)"
        
        # Final cleanup of any remaining shutdown agents
        echo "🧹 Final cleanup of shutdown agents..."
        cleanup_portainer_agents
        
        # Restart Docker Swarm services if they exist
        echo "🔄 Checking for Swarm services to restart..."
        if docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null | grep -q "active"; then
            echo "   Swarm is active, services should restart automatically"
            # Give services time to restart
            sleep 10
            cleanup_portainer_agents
        fi
        
        # Show final status
        echo ""
        echo "📊 Final Docker Status:"
        echo "   Containers running: $(docker ps --format '{{.Names}}' | wc -l)"
        echo "   Swarm status: $(docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null || echo 'inactive')"
        echo ""
        echo "🎉 NUCLEAR FIX SUCCESSFUL!"
        exit 0
    else
        echo "❌ Docker socket exists but daemon not responding after retries"
        exit 1
    fi
else
    echo "❌ Failed to create Docker socket after $timeout seconds"
    exit 1
fi