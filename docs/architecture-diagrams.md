# BMC AMI DevX Code Pipeline MCP Server - Architecture Diagrams

## 🚀 **FastMCP Server Initialization Flow**

```mermaid
sequenceDiagram
    participant Server as OpenAPIMCPServer
    participant Config as Configuration
    participant Auth as Auth Provider
    participant OpenAPI as OpenAPI Spec
    participant FastMCP as FastMCP Engine

    Server->>Config: Load Configuration
    Config-->>Server: Settings & Environment

    Server->>Auth: Create Auth Provider
    Auth-->>Server: JWT/GitHub/Google/WorkOS

    Server->>OpenAPI: Load OpenAPI Specification
    OpenAPI-->>Server: BMC ISPW API Schema

    Server->>FastMCP: Initialize FastMCP Server
    FastMCP->>FastMCP: Mount OpenAPI Tools
    FastMCP->>FastMCP: Add Custom Tools
    FastMCP->>FastMCP: Add Custom Routes
    FastMCP->>FastMCP: Add Resource Templates
    FastMCP->>FastMCP: Add Prompts
    FastMCP-->>Server: Ready Server

    Server-->>Server: Server Ready ✅
```

## 🔐 **Multi-Provider Authentication Flow**

```mermaid
flowchart TD
    Client[MCP Client] --> AuthCheck{Authentication Required?}

    AuthCheck -->|No| DirectAccess[Direct Tool Access]
    AuthCheck -->|Yes| AuthProvider{Auth Provider Type}

    AuthProvider -->|JWT| JWT_Flow[JWT Token Validation]
    AuthProvider -->|GitHub| GitHub_Flow[GitHub OAuth Flow]
    AuthProvider -->|Google| Google_Flow[Google OAuth Flow]
    AuthProvider -->|WorkOS| WorkOS_Flow[WorkOS AuthKit Flow]

    JWT_Flow --> JWKS[JWKS Validation]
    JWKS --> TokenValid{Token Valid?}

    GitHub_Flow --> GitHub_API[GitHub API Validation]
    GitHub_API --> TokenValid

    Google_Flow --> Google_API[Google API Validation]
    Google_API --> TokenValid

    WorkOS_Flow --> WorkOS_API[WorkOS API Validation]
    WorkOS_API --> TokenValid

    TokenValid -->|Valid| ToolAccess[Tool Access Granted]
    TokenValid -->|Invalid| AuthError[401 Authentication Error]

    DirectAccess --> ToolExecution[Tool Execution]
    ToolAccess --> ToolExecution
    AuthError --> ClientResponse[Error Response]
    ToolExecution --> ClientResponse[Success Response]
```

## 🔧 **OpenAPI Tool Generation Process**

```mermaid
flowchart TD
    subgraph "Initialization Phase"
        OpenAPI_Spec[config/openapi.json] --> Parser[OpenAPI Parser]
        Parser --> Schema_Validation[Schema Validation]
        Schema_Validation --> Tool_Generation[Auto Tool Generation]
    end

    subgraph "Tool Creation"
        Tool_Generation --> Assignment_Tools[Assignment Management Tools]
        Tool_Generation --> Release_Tools[Release Operation Tools]
        Tool_Generation --> Package_Tools[Package Management Tools]
        Tool_Generation --> Build_Tools[Build & Deployment Tools]
        Tool_Generation --> Source_Tools[Source Code Management Tools]
    end

    subgraph "FastMCP Integration"
        Assignment_Tools --> FastMCP_Mount[FastMCP.mount()]
        Release_Tools --> FastMCP_Mount
        Package_Tools --> FastMCP_Mount
        Build_Tools --> FastMCP_Mount
        Source_Tools --> FastMCP_Mount

        FastMCP_Mount --> Server_Ready[20+ OpenAPI Tools Available]
    end

    subgraph "Custom Extensions"
        Server_Ready --> Custom_Tools[8 Custom Management Tools]
        Server_Ready --> Elicitation_Tools[3 Interactive Elicitation Tools]
        Server_Ready --> Custom_Routes[4 Custom HTTP Routes]
        Server_Ready --> Resource_Templates[Resource Templates]
        Server_Ready --> Prompt_System[Prompt System]
    end

    Custom_Tools --> Production_Server[Production-Ready Server]
    Elicitation_Tools --> Production_Server
    Custom_Routes --> Production_Server
    Resource_Templates --> Production_Server
    Prompt_System --> Production_Server
```

## 💬 **User Elicitation Interaction Flow**

```mermaid
sequenceDiagram
    participant User
    participant MCP_Client
    participant FastMCP_Server
    participant Elicitation_Tool
    participant BMC_API

    User->>MCP_Client: Request Interactive Tool
    MCP_Client->>FastMCP_Server: Call elicitation tool
    FastMCP_Server->>Elicitation_Tool: Execute with context

    Elicitation_Tool->>User: ctx.info("Starting workflow...")

    loop Multi-Step Input Collection
        Elicitation_Tool->>User: ctx.elicit("Input prompt", type)
        User-->>Elicitation_Tool: AcceptedElicitation(data)

        alt User Accepts
            Elicitation_Tool->>Elicitation_Tool: Store input & continue
        else User Declines
            Elicitation_Tool-->>FastMCP_Server: DeclinedElicitation error
        else User Cancels
            Elicitation_Tool-->>FastMCP_Server: CancelledElicitation error
        end
    end

    Elicitation_Tool->>User: ctx.elicit("Confirm: [summary]", None)
    User-->>Elicitation_Tool: AcceptedElicitation()

    Elicitation_Tool->>BMC_API: Execute actual operation
    BMC_API-->>Elicitation_Tool: Operation result

    Elicitation_Tool-->>FastMCP_Server: Success response with data
    FastMCP_Server-->>MCP_Client: Tool result
    MCP_Client-->>User: Operation completed ✅
```

## 🌊 **Request Processing Pipeline**

```mermaid
flowchart TD
    subgraph "Request Entry"
        HTTP[HTTP Request] --> Transport[FastMCP Transport]
        WebSocket[WebSocket Request] --> Transport
    end

    subgraph "Security Layer"
        Transport --> Rate_Limiter[Rate Limiter Check]
        Rate_Limiter --> Auth_Middleware[Authentication Middleware]
        Auth_Middleware --> Input_Validation[Input Validation]
    end

    subgraph "Routing & Processing"
        Input_Validation --> Request_Router[Request Router]
        Request_Router --> Tool_Dispatcher{Tool Type}

        Tool_Dispatcher -->|OpenAPI| Generated_Tool[Generated Tool]
        Tool_Dispatcher -->|Custom| Custom_Tool[Custom Tool]
        Tool_Dispatcher -->|Elicitation| Interactive_Tool[Elicitation Tool]
    end

    subgraph "Tool Execution"
        Generated_Tool --> BMC_API_Call[BMC API Call]
        Custom_Tool --> Internal_Operations[Internal Operations]
        Interactive_Tool --> User_Interaction[User Interaction]

        BMC_API_Call --> Cache_Layer[Cache Layer]
        Internal_Operations --> Metrics_System[Metrics System]
        User_Interaction --> Context_Management[Context Management]
    end

    subgraph "Response Processing"
        Cache_Layer --> Response_Builder[Response Builder]
        Metrics_System --> Response_Builder
        Context_Management --> Response_Builder

        Response_Builder --> Error_Handler[Error Handler]
        Error_Handler --> Output_Formatter[Output Formatter]
        Output_Formatter --> Audit_Logger[Audit Logger]
    end

    subgraph "Response Delivery"
        Audit_Logger --> Transport_Response[Transport Response]
        Transport_Response --> HTTP_Response[HTTP Response]
        Transport_Response --> WebSocket_Response[WebSocket Response]
    end
```

## 🔄 **Caching & Performance Architecture**

```mermaid
flowchart LR
    subgraph "Request Flow"
        Client_Request[Client Request] --> Cache_Check{Cache Hit?}

        Cache_Check -->|Hit| Cache_Response[Cached Response]
        Cache_Check -->|Miss| API_Call[BMC API Call]

        API_Call --> API_Response[API Response]
        API_Response --> Cache_Store[Store in Cache]
        Cache_Store --> Client_Response[Response to Client]
        Cache_Response --> Client_Response
    end

    subgraph "Cache Management"
        Cache_Store --> TTL_Check[TTL Management]
        TTL_Check --> LRU_Eviction[LRU Eviction]
        LRU_Eviction --> Memory_Optimization[Memory Optimization]
    end

    subgraph "Performance Monitoring"
        Client_Request --> Request_Counter[Request Counter]
        API_Call --> Performance_Timer[Performance Timer]
        Cache_Response --> Cache_Hit_Counter[Cache Hit Counter]

        Request_Counter --> Metrics_Dashboard[Metrics Dashboard]
        Performance_Timer --> Metrics_Dashboard
        Cache_Hit_Counter --> Metrics_Dashboard
    end
```

## 🏭 **Production Deployment Flow**

```mermaid
flowchart TD
    subgraph "Development"
        Dev_Code[Source Code] --> Git_Push[Git Push]
        Git_Push --> CI_Pipeline[CI Pipeline]
    end

    subgraph "Build & Test"
        CI_Pipeline --> Unit_Tests[Unit Tests]
        Unit_Tests --> Integration_Tests[Integration Tests]
        Integration_Tests --> Docker_Build[Docker Build]
        Docker_Build --> Security_Scan[Security Scan]
    end

    subgraph "Container Registry"
        Security_Scan --> Registry_Push[Push to Registry]
        Registry_Push --> Image_Tag[Tagged Image]
    end

    subgraph "Kubernetes Deployment"
        Image_Tag --> K8s_Deploy[Kubernetes Deployment]
        K8s_Deploy --> ConfigMap[ConfigMap]
        K8s_Deploy --> Secrets[Secrets]
        K8s_Deploy --> Service[Service]
        K8s_Deploy --> Ingress[Ingress]
    end

    subgraph "Production Environment"
        Ingress --> Load_Balancer[Load Balancer]
        Load_Balancer --> Pod_Instances[Pod Instances 1-N]
        Pod_Instances --> Health_Checks[Health Checks]
        Health_Checks --> Monitoring[Monitoring & Alerts]
    end

    subgraph "External Integration"
        Pod_Instances --> BMC_Production[BMC Production API]
        Pod_Instances --> Auth_Provider[Auth Provider]
        Monitoring --> Prometheus[Prometheus]
        Prometheus --> Grafana[Grafana Dashboard]
    end
```

## 📊 **Monitoring & Observability Flow**

```mermaid
flowchart TB
    subgraph "Data Collection"
        App_Metrics[Application Metrics] --> Prometheus[Prometheus]
        System_Metrics[System Metrics] --> Prometheus
        Custom_Metrics[Custom Business Metrics] --> Prometheus

        App_Logs[Application Logs] --> Log_Aggregator[Log Aggregator]
        Error_Logs[Error Logs] --> Log_Aggregator
        Audit_Logs[Audit Logs] --> Log_Aggregator
    end

    subgraph "Processing & Storage"
        Prometheus --> Time_Series_DB[Time Series Database]
        Log_Aggregator --> Log_Storage[Log Storage]

        Time_Series_DB --> Alert_Rules[Alert Rules]
        Log_Storage --> Log_Analysis[Log Analysis]
    end

    subgraph "Visualization & Alerting"
        Time_Series_DB --> Grafana[Grafana Dashboard]
        Alert_Rules --> Alert_Manager[Alert Manager]

        Grafana --> Health_Dashboard[Health Dashboard]
        Grafana --> Performance_Dashboard[Performance Dashboard]
        Grafana --> Business_Dashboard[Business Metrics Dashboard]

        Alert_Manager --> Email_Alerts[Email Notifications]
        Alert_Manager --> Slack_Alerts[Slack Notifications]
        Alert_Manager --> PagerDuty[PagerDuty Integration]
    end

    subgraph "Response Actions"
        Email_Alerts --> Operations_Team[Operations Team]
        Slack_Alerts --> Development_Team[Development Team]
        PagerDuty --> On_Call_Engineer[On-Call Engineer]

        Operations_Team --> Incident_Response[Incident Response]
        Development_Team --> Bug_Fix[Bug Fix & Deploy]
        On_Call_Engineer --> Emergency_Response[Emergency Response]
    end
```

## 🔒 **Security & Compliance Architecture**

```mermaid
flowchart TD
    subgraph "Network Security"
        Internet[Internet] --> WAF[Web Application Firewall]
        WAF --> DDoS_Protection[DDoS Protection]
        DDoS_Protection --> Load_Balancer[Load Balancer]
    end

    subgraph "Application Security"
        Load_Balancer --> TLS_Termination[TLS Termination]
        TLS_Termination --> Auth_Layer[Authentication Layer]
        Auth_Layer --> RBAC[Role-Based Access Control]
        RBAC --> Input_Sanitization[Input Sanitization]
    end

    subgraph "Data Protection"
        Input_Sanitization --> Encryption_Transit[Encryption in Transit]
        Encryption_Transit --> FastMCP_Server[FastMCP Server]
        FastMCP_Server --> Encryption_Rest[Encryption at Rest]
        Encryption_Rest --> Secure_Storage[Secure Storage]
    end

    subgraph "Monitoring & Compliance"
        FastMCP_Server --> Security_Audit[Security Audit Logs]
        Security_Audit --> SIEM[SIEM Integration]
        SIEM --> Threat_Detection[Threat Detection]
        Threat_Detection --> Incident_Response[Security Incident Response]

        FastMCP_Server --> Compliance_Reports[Compliance Reporting]
        Compliance_Reports --> Audit_Trail[Audit Trail]
        Audit_Trail --> Regulatory_Compliance[Regulatory Compliance]
    end
```

## 🔧 **Configuration Management Flow**

```mermaid
flowchart LR
    subgraph "Configuration Sources"
        Env_Vars[Environment Variables]
        Config_Files[Config Files]
        Secrets[K8s Secrets]
        ConfigMaps[K8s ConfigMaps]
    end

    subgraph "Configuration Loading"
        Env_Vars --> Config_Loader[Configuration Loader]
        Config_Files --> Config_Loader
        Secrets --> Config_Loader
        ConfigMaps --> Config_Loader

        Config_Loader --> Validation[Schema Validation]
        Validation --> Hierarchy[Configuration Hierarchy]
    end

    subgraph "Runtime Configuration"
        Hierarchy --> FastMCP_Config[FastMCP Configuration]
        Hierarchy --> Auth_Config[Authentication Config]
        Hierarchy --> BMC_Config[BMC API Configuration]
        Hierarchy --> Cache_Config[Cache Configuration]
        Hierarchy --> Monitor_Config[Monitoring Configuration]
    end

    subgraph "Configuration Updates"
        FastMCP_Config --> Hot_Reload[Hot Reload Support]
        Hot_Reload --> Config_Watcher[Configuration Watcher]
        Config_Watcher --> Update_Trigger[Update Trigger]
        Update_Trigger --> Graceful_Restart[Graceful Restart]
    end
```

These comprehensive architecture diagrams provide detailed visual representation of all aspects of the BMC AMI DevX Code Pipeline MCP Server implementation using FastMCP 2.x standards.
