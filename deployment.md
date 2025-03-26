# One-Click Agent Deployment with Vistara Hypercore

Vistara Hypercore provides a seamless deployment experience for AI agents and microservices through its advanced Hypervisor Abstraction Layer. This document outlines the deployment capabilities and the significant benefits in terms of scalability, fault tolerance, and operational efficiency.

## Deployment Capabilities

### One-Click Agent Deployment

Vistara Hypercore enables true one-click deployment of AI agents and services:

- **Hardware-as-Code Deployment**: Define your AI agent's infrastructure requirements in a simple `hac.toml` file, specifying resources, networking, and image references.
- **Multi-Provider Support**: Deploy agents on any supported hypervisor (Firecracker, Cloud Hypervisor, etc.) without changing configuration.
- **Declarative Configuration**: Define once, deploy anywhere with the same configuration regardless of underlying infrastructure.

```toml
# Example hac.toml configuration for agent deployment
[spacecore]
name = "Market Intelligence Agent"
description = "AI agent for real-time market analysis"

[hardware]
cores = 2
memory = 2048
kernel = "/path/to/vmlinux-kernel"
drive = "/path/to/rootfs.img"
ref = "docker.io/my-org/market-intelligence-agent:latest"
interface = "eth0"
```

### Cluster-Aware Deployment

```bash
# Deploy an agent to the cluster with specific resource requirements
$ ./bin/hypercore cluster spawn --cpu 2 --mem 2048 --image-ref docker.io/my-org/market-intelligence-agent:latest --ports 8080:8080
```

- **Automatic Placement**: Intelligent placement of agents across the cluster based on available resources.
- **Resource Constraints**: Specify CPU, memory, and networking requirements for optimal agent performance.
- **Port Mapping**: Expose specific ports for agent communication while maintaining isolation.
- **Environment Configuration**: Pass environment variables to customize agent behavior at deployment time.

## Scalability Benefits

Vistara Hypercore's architecture provides exceptional scalability for agent deployments:

### Horizontal Scaling

- **Cluster Expansion**: Seamlessly add new nodes to the cluster to increase capacity.
- **Distributed Workloads**: Automatic distribution of agents across all available nodes.
- **Resource-Aware Scheduling**: Agents are placed on nodes with sufficient resources:

```go
// Resource capacity check before scheduling
if (vcpuUsed + int(payload.GetCores())) > max(runtime.NumCPU(), 10) {
    return nil, fmt.Errorf("cannot spawn container: have capacity for %d vCPUs, already in use: %d, requested: %d", 
        runtime.NumCPU(), vcpuUsed, payload.GetCores())
}

if (memUsed + int(payload.GetMemory())) > int(availableMem) {
    return nil, fmt.Errorf("cannot spawn container: have capacity for %d MB, already in use: %d MB, requested: %d MB", 
        availableMem, memUsed, payload.GetMemory())
}
```

### Vertical Scaling

- **Fine-grained Resource Control**: Allocate precise CPU and memory resources to each agent.
- **Hardware Isolation**: Each agent runs in its own microVM with dedicated resources.
- **On-demand Scaling**: Adjust resources based on agent workload requirements.

### Performance Efficiency

- **Lightweight Virtualization**: MicroVMs provide near-native performance with minimal overhead.
- **Fast Startup**: Agents can be deployed in milliseconds compared to traditional VMs.
- **Optimized Resource Utilization**: Only allocate what's needed for each agent.

## Fault Tolerance and High Availability

Vistara Hypercore includes robust fault tolerance mechanisms:

### Automatic Recovery

- **Node Failure Detection**: Cluster continuously monitors the health of all nodes.
- **Workload Rescheduling**: Automatically reschedules agents from failed nodes to healthy ones.

```go
// Key code for workload monitoring and rescheduling
if time.Since(update.receivedAt) > (WorkloadBroadcastPeriod * 3) {
    // Node hasn't reported in 3 periods, consider it failed
    for _, service := range update.update.GetWorkloads() {
        // Respawn each service on a healthy node
        if resp, err := a.SpawnRequest(service.GetSourceRequest()); err != nil {
            a.logger.WithError(err).Errorf("failed to respawn service %s", service.GetId())
        } else {
            a.logger.Infof("successfully respawned service %s: %+v", service.GetId(), resp)
        }
    }
}
```

### Isolation and Security

- **MicroVM Isolation**: Each agent runs in a separate microVM, preventing failure propagation.
- **Resource Limits**: Prevent resource exhaustion and noisy neighbor problems.
- **Network Isolation**: Agents receive their own network stack with controlled connectivity.

### State Management

- **Service Discovery**: Automatically track and expose services as nodes join or leave.
- **Persistent Storage**: Optional persistent storage for stateful agents.
- **Centralized Logging**: Capture agent logs for debugging and auditing.

```bash
# Retrieve logs from a specific agent
$ ./bin/hypercore cluster logs --id <agent-id>
```

## Operational Benefits

### Unified Management

- **Single Control Plane**: Manage all agents through a unified API regardless of their location.
- **Consistent Tooling**: Same commands and workflows for all deployment scenarios.
- **Observability**: Monitor agent health, resource usage, and performance metrics.

### API-Driven Automation

- **RESTful and gRPC APIs**: Integrate with existing CI/CD pipelines and management systems.
- **Programmatic Control**: Create, manage, and monitor agents programmatically:

```http
POST /spawn
Content-Type: application/json

{
  "cores": 2,
  "memory": 2048,
  "image_ref": "docker.io/my-org/market-intelligence-agent:latest",
  "ports": {"8080": 8080},
  "env": ["API_KEY=secret", "LOG_LEVEL=info"]
}
```

### Cost Efficiency

- **Right-sizing**: Allocate only the resources each agent needs.
- **High Density**: Run more agents per host than traditional VMs.
- **Fast Scaling**: Quickly deploy or terminate agents based on demand.

## Real-World Benefits for AI Agent Deployment

Deploying AI agents via Vistara Hypercore offers significant advantages:

1. **Resource Optimization**: Each agent receives precisely the resources it needs, maximizing hardware utilization.
2. **Isolation**: Agents operate in separate environments, preventing interference and enhancing security.
3. **Fast Deployment**: Deploy new agent types or versions in seconds rather than minutes.
4. **Predictable Performance**: Resource guarantees ensure consistent agent performance under varying loads.
5. **Resilience**: Automatic recovery from hardware or node failures without manual intervention.
6. **Simplified Operations**: Uniform deployment model regardless of underlying infrastructure.

## Getting Started with Agent Deployment

1. **Define your agent infrastructure**:
   ```bash
   # Create a hac.toml file defining resource requirements
   $ nano hac.toml
   ```

2. **Deploy to a single node**:
   ```bash
   $ ./bin/hypercore spawn --provider firecracker
   ```

3. **Or deploy to the cluster**:
   ```bash
   $ ./bin/hypercore cluster spawn --cpu 2 --mem 2048 --image-ref docker.io/my-org/market-intelligence-agent:latest
   ```

4. **Monitor your deployment**:
   ```bash
   $ ./bin/hypercore cluster list
   $ ./bin/hypercore cluster logs --id <agent-id>
   ```

Vistara Hypercore brings the operational benefits of modern cloud infrastructure to AI agent deployment, allowing you to focus on agent functionality while the platform handles distribution, scaling, and resilience.
