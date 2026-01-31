# Docker Commands Cheat Sheet

A comprehensive reference for essential Docker commands, organized by category for quick lookup and practical use.

---

## Table of Contents

1. [General Commands](#general-commands)
2. [Image Management](#image-management)
3. [Container Management](#container-management)
4. [Container Execution & Interaction](#container-execution--interaction)
5. [Container Inspection & Logs](#container-inspection--logs)
6. [Network Management](#network-management)
7. [Volume Management](#volume-management)
8. [Docker Compose](#docker-compose)
9. [Cleanup & System Maintenance](#cleanup--system-maintenance)
10. [Dockerfile Instructions](#dockerfile-instructions)
11. [Useful Aliases](#useful-aliases)

---

## General Commands

| Command | Description |
|---------|-------------|
| `docker --version` | Display Docker version |
| `docker --help` | Display help information |
| `docker info` | Display system-wide information |
| `docker login -u <username>` | Login to Docker Hub or registry |
| `docker logout` | Logout from Docker registry |

---

## Image Management

### Building Images

| Command | Description |
|---------|-------------|
| `docker build -t <image_name> .` | Build image from Dockerfile in current directory |
| `docker build -t <image_name>:<tag> .` | Build image with custom tag |
| `docker build -f <dockerfile_path> -t <image_name> .` | Build from specific Dockerfile |
| `docker build --no-cache -t <image_name> .` | Build without using cached layers |
| `docker build --build-arg <key>=<value> -t <image_name> .` | Pass build arguments |
| `docker build --pull -t <image_name> .` | Pull latest base image before building |

### Pulling, Pushing & Searching

| Command | Description |
|---------|-------------|
| `docker pull <image_name>` | Download image from Docker Hub |
| `docker pull <registry>/<image_name>:<tag>` | Pull from custom registry |
| `docker push <username>/<image_name>` | Push image to Docker Hub |
| `docker push <registry>/<image_name>` | Push to custom registry |
| `docker search <image_name>` | Search Docker Hub for images |
| `docker search <image_name> --stars=3` | Search with minimum stars filter |

### Image Information

| Command | Description |
|---------|-------------|
| `docker images` | List all local images |
| `docker images -a` | List all images (including intermediate layers) |
| `docker images --filter dangling=true` | Show dangling images |
| `docker image ls` | Alternative command to list images |
| `docker history <image_name>` | Show image build history |
| `docker inspect <image_name>` | Inspect image details |
| `docker tag <image_name> <new_tag>` | Create tag/alias for image |

### Removing Images

| Command | Description |
|---------|-------------|
| `docker rmi <image_name>` | Remove image by name |
| `docker rmi <image_id>` | Remove image by ID |
| `docker rmi -f <image_name>` | Force remove image |
| `docker image rm <image_name>` | Remove image (alternative syntax) |
| `docker image prune` | Remove unused images |
| `docker image prune -a` | Remove all unused images |

---

## Container Management

### Creating & Running Containers

| Command | Description |
|---------|-------------|
| `docker run <image_name>` | Create and run container in foreground |
| `docker run -d <image_name>` | Run container in detached mode (background) |
| `docker run -it <image_name> bash` | Run interactive container with terminal |
| `docker run --name <container_name> <image_name>` | Run with custom container name |
| `docker run -p <host_port>:<container_port> <image_name>` | Map ports (host:container) |
| `docker run -P <image_name>` | Publish all exposed ports |
| `docker run -e <VAR>=<value> <image_name>` | Set environment variables |
| `docker run -v <host_path>:<container_path> <image_name>` | Mount volume |
| `docker run -v <volume_name>:<container_path> <image_name>` | Mount named volume |
| `docker run --network <network_name> <image_name>` | Connect to network |
| `docker run --restart unless-stopped <image_name>` | Set restart policy |
| `docker run --privileged <image_name>` | Run with elevated privileges |
| `docker run --cpus=1.5 -m 512m <image_name>` | Set CPU and memory limits |
| `docker run -w <workdir> <image_name>` | Set working directory |
| `docker run --hostname <hostname> <image_name>` | Set container hostname |
| `docker create <image_name>` | Create container without running |

### Container Lifecycle

| Command | Description |
|---------|-------------|
| `docker start <container_name>` | Start a stopped container |
| `docker stop <container_name>` | Stop a running container |
| `docker restart <container_name>` | Restart a container |
| `docker pause <container_name>` | Pause container processes |
| `docker unpause <container_name>` | Resume paused container |
| `docker kill <container_name>` | Force stop container (SIGKILL) |
| `docker kill -s HUP <container_name>` | Send specific signal to container |
| `docker wait <container_name>` | Block until container stops |

### Container Information

| Command | Description |
|---------|-------------|
| `docker ps` | List running containers |
| `docker ps -a` | List all containers (running and stopped) |
| `docker ps -l` | Show last created container |
| `docker ps -s` | List containers with size |
| `docker ps -q` | Show only container IDs |
| `docker ps --filter status=running` | Filter containers by status |
| `docker ps --filter ancestor=<image_name>` | Show containers from specific image |

### Container Modification

| Command | Description |
|---------|-------------|
| `docker rename <old_name> <new_name>` | Rename container |
| `docker rm <container_name>` | Remove stopped container |
| `docker rm -f <container_name>` | Force remove running container |
| `docker commit <container_name> <image_name>` | Create image from container |
| `docker update --restart unless-stopped <container_name>` | Update container restart policy |
| `docker update --cpus=2 -m 1g <container_name>` | Update resource limits |

---

## Container Execution & Interaction

| Command | Description |
|---------|-------------|
| `docker exec -it <container_name> bash` | Open bash shell in container |
| `docker exec -it <container_name> sh` | Open sh shell in container |
| `docker exec <container_name> <command>` | Execute command in container |
| `docker exec -d <container_name> <command>` | Execute command in background |
| `docker exec -u root <container_name> <command>` | Execute as specific user |
| `docker attach <container_name>` | Attach to running container |
| `docker cp <file_path> <container_name>:<dest_path>` | Copy file to container |
| `docker cp <container_name>:<src_path> <dest_path>` | Copy file from container |
| `docker cp -a <container_name>:/app . ` | Copy directory with ownership preserved |

---

## Container Inspection & Logs

| Command | Description |
|---------|-------------|
| `docker logs <container_name>` | View container logs |
| `docker logs -f <container_name>` | Follow container logs (tail -f) |
| `docker logs -n 100 <container_name>` | Show last 100 log lines |
| `docker logs --since 2025-01-20 <container_name>` | Show logs after specific date |
| `docker logs --until 2025-01-27 <container_name>` | Show logs before specific date |
| `docker logs -t <container_name>` | Show logs with timestamps |
| `docker inspect <container_name>` | View detailed container information |
| `docker inspect --format='{{json .}}' <container_name>` | Pretty print container JSON |
| `docker inspect -f '{{.NetworkSettings.IPAddress}}' <container_name>` | Get container IP |
| `docker top <container_name>` | List processes running in container |
| `docker stats <container_name>` | Display container resource usage |
| `docker stats --no-stream` | One-time resource usage snapshot |
| `docker events <container_name>` | Display container events |
| `docker port <container_name>` | Show port mappings |
| `docker diff <container_name>` | Show filesystem changes |
| `docker export <container_name> > file.tar` | Export container filesystem |

---

## Network Management

### Creating & Removing Networks

| Command | Description |
|---------|-------------|
| `docker network create <network_name>` | Create bridge network |
| `docker network create -d bridge <network_name>` | Create bridge network (explicit) |
| `docker network create -d overlay <network_name>` | Create overlay network |
| `docker network rm <network_name>` | Remove network |
| `docker network create --subnet=192.168.0.0/16 <network_name>` | Create with subnet |
| `docker network create --gateway=192.168.0.1 <network_name>` | Create with gateway |

### Network Information

| Command | Description |
|---------|-------------|
| `docker network ls` | List networks |
| `docker network inspect <network_name>` | View network details |
| `docker network inspect --format='{{json .Containers}}'` | List connected containers |

### Container Network Operations

| Command | Description |
|---------|-------------|
| `docker run --network <network_name> <image_name>` | Connect container at start |
| `docker network connect <network_name> <container_name>` | Connect running container to network |
| `docker network disconnect <network_name> <container_name>` | Disconnect container from network |

---

## Volume Management

### Creating & Removing Volumes

| Command | Description |
|---------|-------------|
| `docker volume create <volume_name>` | Create named volume |
| `docker volume rm <volume_name>` | Remove volume |
| `docker volume create --driver local <volume_name>` | Create with specific driver |

### Volume Information

| Command | Description |
|---------|-------------|
| `docker volume ls` | List all volumes |
| `docker volume ls -f dangling=true` | List unused volumes |
| `docker volume inspect <volume_name>` | View volume details |

### Using Volumes

| Command | Description |
|---------|-------------|
| `docker run -v <volume_name>:<container_path> <image_name>` | Mount named volume |
| `docker run -v <host_path>:<container_path> <image_name>` | Mount bind volume |
| `docker run -v <host_path>:<container_path>:ro <image_name>` | Mount read-only volume |
| `docker volume prune` | Remove unused volumes |

---

## Docker Compose

| Command | Description |
|---------|-------------|
| `docker-compose up` | Create and start services |
| `docker-compose up -d` | Start services in detached mode |
| `docker-compose down` | Stop and remove services, networks, volumes |
| `docker-compose ps` | List running services |
| `docker-compose logs` | View service logs |
| `docker-compose logs -f <service_name>` | Follow service logs |
| `docker-compose build` | Build services |
| `docker-compose rebuild` | Rebuild all services |
| `docker-compose exec <service_name> bash` | Execute command in service |
| `docker-compose stop` | Stop services |
| `docker-compose start` | Start stopped services |
| `docker-compose restart <service_name>` | Restart service |
| `docker-compose pause` | Pause services |
| `docker-compose unpause` | Resume paused services |
| `docker-compose config` | Validate and view compose file |
| `docker-compose pull` | Pull latest images for services |

---

## Cleanup & System Maintenance

### Individual Cleanup

| Command | Description |
|---------|-------------|
| `docker container prune` | Remove stopped containers |
| `docker image prune` | Remove dangling images |
| `docker image prune -a` | Remove all unused images |
| `docker volume prune` | Remove unused volumes |
| `docker network prune` | Remove unused networks |

### Batch Operations

| Command | Description |
|---------|-------------|
| `docker stop $(docker ps -a -q)` | Stop all containers |
| `docker rm $(docker ps -a -q)` | Remove all containers |
| `docker rm -f $(docker ps -a -q)` | Force remove all containers |
| `docker rmi $(docker images -q)` | Remove all images |
| `docker rmi -f $(docker images -q)` | Force remove all images |

### System-wide Cleanup

| Command | Description |
|---------|-------------|
| `docker system prune` | Remove dangling images, containers, networks, volumes |
| `docker system prune -a` | Remove all unused images and containers |
| `docker system prune -a --volumes` | Remove all unused resources including volumes |
| `docker system df` | Display disk usage by images, containers, volumes |
| `docker system events` | Monitor Docker system events |

---

## Dockerfile Instructions

Essential instructions for building Docker images:

| Instruction | Description | Example |
|-------------|-------------|---------|
| `FROM` | Set base image | `FROM ubuntu:22.04` |
| `RUN` | Execute command during build | `RUN apt-get update && apt-get install -y curl` |
| `COPY` | Copy files from host to image | `COPY . /app` |
| `ADD` | Copy with archive extraction | `ADD app.tar.gz /app` |
| `WORKDIR` | Set working directory | `WORKDIR /app` |
| `ENV` | Set environment variables | `ENV NODE_ENV=production` |
| `EXPOSE` | Document exposed ports | `EXPOSE 8080` |
| `CMD` | Default command to run | `CMD ["npm", "start"]` |
| `ENTRYPOINT` | Configure container as executable | `ENTRYPOINT ["python", "app.py"]` |
| `MAINTAINER` | Set image maintainer | `MAINTAINER john@example.com` |
| `LABEL` | Add metadata | `LABEL version="1.0"` |
| `VOLUME` | Mount point for volumes | `VOLUME ["/data"]` |
| `USER` | Set user for running commands | `USER appuser` |
| `ARG` | Build-time variables | `ARG BUILD_VERSION=1.0` |
| `HEALTHCHECK` | Container health check | `HEALTHCHECK CMD curl http://localhost/health` |

### Dockerfile Best Practices

```dockerfile
# Use specific base image versions
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Set user (security best practice)
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8080/health || exit 1

# Run application
CMD ["python", "app.py"]
```

---

## Useful Aliases

Add these to your `.bashrc`, `.zshrc`, or equivalent:

```bash
# Container shortcuts
alias dps='docker ps'
alias dpsa='docker ps -a'
alias dstart='docker start'
alias dstop='docker stop'
alias drm='docker rm'
alias drmf='docker rm -f'
alias dex='docker exec -it'
alias dlogs='docker logs -f'
alias dinspect='docker inspect'

# Image shortcuts
alias di='docker images'
alias drmi='docker rmi'
alias dbuild='docker build -t'
alias dpush='docker push'
alias dpull='docker pull'

# Compose shortcuts
alias dcup='docker-compose up -d'
alias dcdown='docker-compose down'
alias dcps='docker-compose ps'
alias dclogs='docker-compose logs -f'
alias dcexec='docker-compose exec'

# Cleanup shortcuts
alias dclean='docker system prune -af'
alias dcleanv='docker system prune -af --volumes'

# Combined operations
alias drmall='docker rm -f $(docker ps -a -q)'
alias driall='docker rmi -f $(docker images -q)'
```

---

## Advanced Usage Examples

### Debugging a Container

```bash
# View recent logs
docker logs --tail 50 my-container

# Follow logs in real-time
docker logs -f my-container

# Get logs from specific time
docker logs --since 2025-01-20T10:00:00 my-container

# Open shell in running container
docker exec -it my-container /bin/bash

# View container resource usage
docker stats my-container

# Inspect container configuration
docker inspect my-container | jq .
```

### Building with Build Arguments

```bash
# Build with arguments
docker build \
  --build-arg NODE_VERSION=18 \
  --build-arg ENV=production \
  -t myapp:1.0 .

# In Dockerfile:
# ARG NODE_VERSION=16
# FROM node:${NODE_VERSION}
```

### Multi-stage Build Example

```dockerfile
FROM python:3.11 as builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["python", "app.py"]
```

### Port Mapping Examples

```bash
# Map single port
docker run -p 8080:3000 myapp

# Map multiple ports
docker run -p 8080:3000 -p 8443:443 myapp

# Map to random port
docker run -p 3000 myapp

# Map specific host interface
docker run -p 127.0.0.1:8080:3000 myapp
```

### Volume Management Examples

```bash
# Named volume
docker run -v myvolume:/data myapp

# Bind mount (host path:container path)
docker run -v /home/user/data:/data myapp

# Read-only volume
docker run -v myvolume:/data:ro myapp

# Multiple volumes
docker run -v vol1:/data1 -v vol2:/data2 myapp
```

---

## Tips & Best Practices

1. **Always use image tags**: Avoid relying on `:latest` in production
2. **Minimize layers**: Combine RUN commands to reduce image size
3. **Use .dockerignore**: Exclude unnecessary files from build context
4. **Run as non-root**: Use USER instruction for security
5. **Health checks**: Implement HEALTHCHECK for production containers
6. **Resource limits**: Set CPU and memory limits to prevent resource exhaustion
7. **Logging**: Configure proper logging drivers for container logs
8. **Secrets management**: Never hardcode secrets; use environment variables or Docker secrets
9. **Versioning**: Tag images with semantic versioning (v1.2.3)
10. **Cleanup regularly**: Use `docker system prune` to free up resources

---

## Common Workflows

### Deploy from GitHub

```bash
# Clone repo
git clone https://github.com/username/repo.git
cd repo

# Build image
docker build -t myapp:1.0 .

# Run container
docker run -d -p 8080:3000 --name myapp myapp:1.0
```

### Local Development with Docker Compose

```bash
# Start development environment
docker-compose up -d

# View logs
docker-compose logs -f

# Execute commands
docker-compose exec web bash

# Stop environment
docker-compose down
```

### Push to Docker Hub

```bash
# Login
docker login

# Tag image
docker tag myapp:1.0 username/myapp:1.0

# Push
docker push username/myapp:1.0
```

---

## Resource Limits & Performance

```bash
# CPU limits
docker run --cpus=2.0 myapp              # 2 CPUs
docker run --cpus=0.5 myapp              # Half CPU

# Memory limits
docker run -m 512m myapp                 # 512 MB
docker run -m 1g myapp                   # 1 GB

# Combined
docker run --cpus=1.5 -m 1g myapp
```

---

## Networking Examples

```bash
# Create custom network
docker network create my-net

# Run container on network
docker run -d --network my-net --name web nginx
docker run -d --network my-net --name db postgres

# Containers can communicate by name (web, db)
docker exec web curl http://db:5432

# Connect existing container to network
docker network connect my-net existing-container
```

---

## References

- [Docker Documentation](https://docs.docker.com)
- [Docker CLI Reference](https://docs.docker.com/engine/reference/commandline/docker/)
- [Docker Hub](https://hub.docker.com)
- [Best Practices](https://docs.docker.com/develop/dev-best-practices/)

---

**Last Updated**: January 2026  
**Docker Version**: 25.0+
