# BMC AMI DevX Code Pipeline MCP Server - Architecture

## 🏗️ **System Overview**

The BMC AMI DevX Code Pipeline MCP Server is a production-ready FastMCP 2.x compliant server that provides comprehensive mainframe DevOps integration through the Model Context Protocol.

```mermaid
graph TB
    subgraph "Client Layer"
        C1[MCP Clients]
        C2[IDE Extensions]
        C3[CLI Tools]
    end
    
    subgraph "FastMCP Server"
        direction TB
        
        subgraph "Transport Layer"
            HTTP[HTTP/REST Transport]
            WS[WebSocket Transport]
        end
        
        subgraph "Authentication & Security"
            AUTH[Multi-Provider Auth]
            JWT[JWT Verifier]
            GITHUB[GitHub OAuth]
            GOOGLE[Google OAuth]
            WORKOS[WorkOS SSO]
        end
        
        subgraph "Core Engine"
            FASTMCP[FastMCP 2.x Engine]
            ROUTER[Request Router]
            CONTEXT[Context Manager]
        end
        
        subgraph "Advanced Features"
            OPENAPI[OpenAPI Integration]
            ELICIT[User Elicitation]
            ROUTES[Custom Routes]
            RESOURCES[Resource Templates]
            PROMPTS[Prompt System]
        end
        
        subgraph "Tool Layer"
            direction LR
            GENERATED[20 OpenAPI Tools]
            CUSTOM[8 Custom Tools]
            INTERACTIVE[3 Elicitation Tools]
        end
        
        subgraph "Infrastructure"
            CACHE[Intelligent Cache]
            RATE[Rate Limiter]
            METRICS[Metrics Engine]
            HEALTH[Health Monitor]
            CONFIG[Configuration Manager]
        end
    end
    
    subgraph "External APIs"
        BMC[BMC ISPW API]
        AUTH_PROVIDER[Auth Providers]
    end
    
    C1 --> HTTP
    C2 --> WS
    C3 --> HTTP
    
    HTTP --> FASTMCP
    WS --> FASTMCP
    
    FASTMCP --> AUTH
    AUTH --> JWT
    AUTH --> GITHUB
    AUTH --> GOOGLE
    AUTH --> WORKOS
    
    FASTMCP --> OPENAPI
    FASTMCP --> ELICIT
    FASTMCP --> ROUTES
    FASTMCP --> RESOURCES
    FASTMCP --> PROMPTS
    
    OPENAPI --> GENERATED
    ELICIT --> INTERACTIVE
    ROUTES --> CUSTOM
    
    GENERATED --> BMC
    CUSTOM --> CACHE
    CUSTOM --> METRICS
    
    AUTH --> AUTH_PROVIDER
```

## 🔧 **Component Architecture**

### **1. Transport Layer**
- **HTTP/REST Transport**: Primary MCP communication protocol
- **WebSocket Support**: Real-time streaming for long-running operations
- **Health Endpoints**: `/health`, `/status`, `/metrics`, `/ready`

### **2. Authentication & Security**
- **Multi-Provider Authentication**: JWT, GitHub, Google, WorkOS
- **Token Validation**: JWKS-based JWT verification
- **Rate Limiting**: Token bucket algorithm with per-user limits
- **Security Headers**: CORS, content security policies

### **3. FastMCP Engine**
- **Request Routing**: Intelligent request distribution
- **Context Management**: User context and session handling
- **Error Handling**: Comprehensive error recovery
- **Configuration Management**: Environment-based settings

### **4. Advanced Features**

#### **OpenAPI Integration**
- **Automatic Tool Generation**: 20+ tools from BMC ISPW API spec
- **Type-Safe Parameters**: Schema-based validation
- **Always in Sync**: API changes automatically reflected
- **Complete Coverage**: All BMC ISPW operations available

#### **User Elicitation System**
- **Interactive Workflows**: Multi-step user input collection
- **3 Elicitation Tools**: Assignment creation, deployment, troubleshooting
- **Response Handling**: Accept/Decline/Cancel pattern matching
- **Safety Features**: Production deployment warnings

#### **Custom Routes**
- **Health Monitoring**: Real-time server status
- **Metrics Endpoint**: Performance and usage statistics
- **Status Dashboard**: System health visualization
- **Readiness Probes**: Container orchestration support

#### **Resource Templates**
- **Parameterized Access**: `bmc://assignments/{srid}`
- **Template System**: Reusable resource definitions
- **Dynamic Content**: Context-aware resource generation

#### **Prompt System**
- **LLM Guidance**: Reusable templates for AI assistants
- **Analysis Prompts**: Assignment status analysis
- **Planning Prompts**: Deployment planning guidance
- **Troubleshooting Prompts**: Diagnostic guidance

### **5. Tool Architecture**

```mermaid
graph TD
    subgraph "Tool Categories"
        subgraph "OpenAPI Generated (20 tools)"
            A1[Assignment Management]
            A2[Release Operations]
            A3[Package Management]
            A4[Build Operations]
            A5[Deployment Control]
        end
        
        subgraph "Custom Management (8 tools)"
            M1[Server Metrics]
            M2[Health Status]
            M3[Cache Management]
            M4[Configuration]
            M5[Monitoring Tools]
        end
        
        subgraph "Interactive Elicitation (3 tools)"
            E1[Assignment Creation]
            E2[Release Deployment]
            E3[Issue Troubleshooting]
        end
    end
    
    A1 --> BMC_API[BMC ISPW API]
    A2 --> BMC_API
    A3 --> BMC_API
    A4 --> BMC_API
    A5 --> BMC_API
    
    M1 --> INTERNAL[Internal Systems]
    M2 --> INTERNAL
    M3 --> CACHE_SYS[Cache System]
    
    E1 --> USER_INPUT[User Interface]
    E2 --> USER_INPUT
    E3 --> USER_INPUT
```

## 🔄 **Request Flow Architecture**

```mermaid
sequenceDiagram
    participant Client
    participant Transport
    participant Auth
    participant Router
    participant Tool
    participant Cache
    participant BMC_API
    
    Client->>Transport: MCP Request
    Transport->>Auth: Validate Token
    Auth-->>Transport: Token Valid
    
    Transport->>Router: Route Request
    Router->>Cache: Check Cache
    
    alt Cache Hit
        Cache-->>Router: Cached Response
        Router-->>Transport: Response
    else Cache Miss
        Router->>Tool: Execute Tool
        Tool->>BMC_API: API Call
        BMC_API-->>Tool: API Response
        Tool-->>Cache: Store Result
        Tool-->>Router: Tool Response
        Router-->>Transport: Response
    end
    
    Transport-->>Client: MCP Response
```

## 🎯 **Elicitation Architecture**

```mermaid
stateDiagram-v2
    [*] --> Started: ctx.info("Starting...")
    Started --> Step1: First Input
    
    Step1 --> Accepted1: User Accepts
    Step1 --> Declined1: User Declines
    Step1 --> Cancelled: User Cancels
    
    Accepted1 --> Step2: Next Input
    Step2 --> Accepted2: User Accepts
    Step2 --> Declined2: User Declines
    Step2 --> Cancelled: User Cancels
    
    Accepted2 --> Confirmation: Final Confirmation
    Confirmation --> Success: User Confirms
    Confirmation --> Cancelled: User Cancels
    
    Declined1 --> Error: Requirement Missing
    Declined2 --> Error: Requirement Missing
    
    Success --> [*]
    Error --> [*]
    Cancelled --> [*]
```

## 📊 **Data Flow Architecture**

```mermaid
flowchart LR
    subgraph "Input Sources"
        USER[User Requests]
        CONFIG[Configuration]
        OPENAPI_SPEC[OpenAPI Spec]
    end
    
    subgraph "Processing Pipeline"
        PARSER[Request Parser]
        VALIDATOR[Schema Validator]
        TRANSFORMER[Data Transformer]
        EXECUTOR[Tool Executor]
    end
    
    subgraph "Storage & Caching"
        CACHE_LAYER[Cache Layer]
        METRICS_STORE[Metrics Store]
        CONFIG_STORE[Config Store]
    end
    
    subgraph "External Systems"
        BMC_ISPW[BMC ISPW API]
        AUTH_SVC[Auth Services]
    end
    
    subgraph "Output Destinations"
        CLIENT[MCP Client]
        LOGS[System Logs]
        METRICS_OUT[Metrics Export]
    end
    
    USER --> PARSER
    CONFIG --> CONFIG_STORE
    OPENAPI_SPEC --> VALIDATOR
    
    PARSER --> VALIDATOR
    VALIDATOR --> TRANSFORMER
    TRANSFORMER --> EXECUTOR
    
    EXECUTOR <--> CACHE_LAYER
    EXECUTOR --> METRICS_STORE
    EXECUTOR <--> BMC_ISPW
    EXECUTOR <--> AUTH_SVC
    
    EXECUTOR --> CLIENT
    EXECUTOR --> LOGS
    METRICS_STORE --> METRICS_OUT
```

## 🔐 **Security Architecture**

```mermaid
graph TD
    subgraph "Security Layers"
        subgraph "Transport Security"
            TLS[TLS/HTTPS]
            CORS[CORS Policies]
            HEADERS[Security Headers]
        end
        
        subgraph "Authentication"
            MULTI_AUTH[Multi-Provider Auth]
            JWT_VERIFY[JWT Verification]
            TOKEN_CACHE[Token Cache]
        end
        
        subgraph "Authorization"
            ROLE_CHECK[Role Validation]
            SCOPE_CHECK[Scope Validation]
            RATE_LIMIT[Rate Limiting]
        end
        
        subgraph "Data Protection"
            INPUT_VALIDATE[Input Validation]
            OUTPUT_SANITIZE[Output Sanitization]
            AUDIT_LOG[Audit Logging]
        end
    end
    
    CLIENT[Client Request] --> TLS
    TLS --> CORS
    CORS --> MULTI_AUTH
    MULTI_AUTH --> JWT_VERIFY
    JWT_VERIFY --> TOKEN_CACHE
    TOKEN_CACHE --> ROLE_CHECK
    ROLE_CHECK --> SCOPE_CHECK
    SCOPE_CHECK --> RATE_LIMIT
    RATE_LIMIT --> INPUT_VALIDATE
    INPUT_VALIDATE --> TOOL_EXECUTION[Tool Execution]
    TOOL_EXECUTION --> OUTPUT_SANITIZE
    OUTPUT_SANITIZE --> AUDIT_LOG
    AUDIT_LOG --> RESPONSE[Secure Response]
```

## 🏭 **Deployment Architecture**

### **Development Environment**
```mermaid
graph TD
    DEV[Development Machine] --> DOCKER_COMPOSE[Docker Compose]
    DOCKER_COMPOSE --> FASTMCP_CONTAINER[FastMCP Container]
    FASTMCP_CONTAINER --> LOCAL_CONFIG[Local Config]
    FASTMCP_CONTAINER --> DEV_BMC[Dev BMC Instance]
```

### **Production Environment**
```mermaid
graph TD
    subgraph "Kubernetes Cluster"
        INGRESS[Ingress Controller]
        
        subgraph "FastMCP Namespace"
            SVC[Service]
            DEPLOY[Deployment]
            PODS[Pods 1-N]
            CM[ConfigMap]
            SECRET[Secrets]
        end
        
        subgraph "Monitoring"
            PROMETHEUS[Prometheus]
            GRAFANA[Grafana]
            ALERTS[AlertManager]
        end
    end
    
    subgraph "External Systems"
        LOAD_BALANCER[Load Balancer]
        BMC_PROD[BMC Production]
        AUTH_PROD[Auth Provider]
    end
    
    LOAD_BALANCER --> INGRESS
    INGRESS --> SVC
    SVC --> DEPLOY
    DEPLOY --> PODS
    PODS --> CM
    PODS --> SECRET
    
    PODS --> BMC_PROD
    PODS --> AUTH_PROD
    
    PROMETHEUS --> PODS
    GRAFANA --> PROMETHEUS
    ALERTS --> PROMETHEUS
```

## 📈 **Performance Architecture**

### **Caching Strategy**
- **Multi-Level Caching**: Request, response, and metadata caching
- **TTL Management**: Time-based cache invalidation
- **LRU Eviction**: Memory-efficient cache management
- **Cache Warming**: Proactive cache population

### **Rate Limiting**
- **Token Bucket Algorithm**: Smooth rate limiting
- **Per-User Limits**: Individual user quotas
- **Burst Handling**: Short-term burst allowance
- **Graceful Degradation**: Proper rate limit responses

### **Connection Management**
- **Connection Pooling**: Efficient HTTP connections
- **Keep-Alive**: Persistent connections
- **Timeout Management**: Request timeout handling
- **Circuit Breaker**: Failure protection

## 🔍 **Monitoring Architecture**

```mermaid
graph TD
    subgraph "Metrics Collection"
        REQUEST_METRICS[Request Metrics]
        PERFORMANCE_METRICS[Performance Metrics]
        ERROR_METRICS[Error Metrics]
        BUSINESS_METRICS[Business Metrics]
    end
    
    subgraph "Storage & Processing"
        METRICS_STORE[Metrics Store]
        AGGREGATOR[Data Aggregator]
        ALERTING[Alert Engine]
    end
    
    subgraph "Visualization & Alerting"
        DASHBOARD[Monitoring Dashboard]
        ALERTS_UI[Alert Dashboard]
        NOTIFICATIONS[Notifications]
    end
    
    REQUEST_METRICS --> METRICS_STORE
    PERFORMANCE_METRICS --> METRICS_STORE
    ERROR_METRICS --> METRICS_STORE
    BUSINESS_METRICS --> METRICS_STORE
    
    METRICS_STORE --> AGGREGATOR
    AGGREGATOR --> ALERTING
    AGGREGATOR --> DASHBOARD
    
    ALERTING --> ALERTS_UI
    ALERTING --> NOTIFICATIONS
```

## 🎛️ **Configuration Architecture**

- **Environment-Based Configuration**: Development, staging, production configs
- **Hierarchical Settings**: Global, environment, and local overrides
- **Secret Management**: Secure credential handling
- **Hot Reloading**: Dynamic configuration updates
- **Validation**: Configuration schema validation

## 🔄 **Integration Architecture**

The server integrates seamlessly with:
- **BMC ISPW API**: Complete mainframe DevOps operations
- **Authentication Providers**: JWT, GitHub, Google, WorkOS
- **Container Orchestration**: Docker, Kubernetes
- **Monitoring Systems**: Prometheus, Grafana
- **CI/CD Pipelines**: GitHub Actions, GitLab CI
- **Development Tools**: VSCode, IntelliJ, CLI tools

This architecture provides a robust, scalable, and maintainable foundation for mainframe DevOps integration through the Model Context Protocol using FastMCP 2.x standards.