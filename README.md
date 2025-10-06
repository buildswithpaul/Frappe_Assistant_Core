# Frappe Assistant Core

🔧 **LLM Integration Platform for ERPNext** - Give any Large Language Model the power to interact with your ERPNext system through standardized tools and protocols.

---

## 🌟 What is Frappe Assistant Core?

**Infrastructure that connects LLMs to ERPNext.** Frappe Assistant Core works with the Model Context Protocol (MCP) to expose ERPNext functionality to any compatible Language Model, enabling:

- **🔌 LLM-Agnostic Integration**: Works with Claude, GPT, custom models, or any MCP-compatible system
- **📁 One-Click Claude Setup**: Generate DXT files for instant Claude Desktop integration  
- **🔒 Enterprise Security**: ERPNext permissions, audit logging, and role-based access control
- **🛠️ 20+ Built-in Tools**: Document operations, search, reporting, analytics, and visualization
- **🚀 Plugin Architecture**: Extensible framework for custom business logic and integrations
- **🆓 Open Source**: AGPL-3.0 licensed - transparent, community-driven development

---

## ⚡ Quick Installation

Get up and running in 3 steps:

```bash
# 1. Get the app
cd frappe-bench
bench get-app https://github.com/buildswithpaul/Frappe_Assistant_Core

# 2. Install on your site  
bench --site [site-name] install-app frappe_assistant_core

# 3. Enable the assistant
bench --site [site-name] set-config assistant_enabled 1
```

**That's it!** Your ERPNext system is now accessible to any MCP-compatible LLM.

---

## 🎯 Core Components

### 🔧 **MCP Server Infrastructure**
Robust protocol handler that exposes ERPNext functionality through standardized tools.

### 📦 **Client Integration Packages** 
Ready-to-use integrations including DXT file generation for Claude Desktop setup.

### 🛠️ **21 Built-in Tools**
Document CRUD, search, reporting, analytics, Python execution, and visualization capabilities.

![Available Tools](screenshots/tools-available.png)
*Comprehensive tool set for complete ERPNext integration*

### 🔌 **Plugin Architecture**
Extensible framework for custom tools, external app integration, and business-specific logic.

![Admin Interface](screenshots/admin-interface.png)
*Professional admin interface for plugin management and configuration*

### 🔐 **OAuth 2.0 / OIDC Authentication**
Full OAuth 2.0 and OpenID Connect implementation with Dynamic Client Registration (RFC 7591), PKCE support, and standardized discovery endpoints for seamless integration with MCP Inspector and third-party tools.

### 🔒 **Enterprise Security Layer**
Authentication, ERPNext permissions integration, audit logging, and role-based access.

![Audit Trail](screenshots/audit-trail.png)
*Complete audit logging tracks all LLM interactions with your ERP data*

### 🌐 **LLM-Agnostic Design**
Compatible with any MCP-enabled system - not locked to specific AI providers.

### Architecture Overview

```mermaid
graph TB
    subgraph "LLM Layer"
        Claude[Claude Desktop]
        GPT[GPT/Custom LLM]
        API[LLM via API]
        Future[Future LLMs]
    end

    subgraph "Integration Layer"
        MCP[MCP Protocol<br/>JSON-RPC 2.0]
        DXT[DXT File Generator<br/>One-Click Setup]
        Bridge[STDIO Bridge]
    end

    subgraph "Frappe Assistant Core"
        Server[MCP Server<br/>API Handler]
        Registry[Tool Registry<br/>20+ Tools]
        
        subgraph "Plugin System"
            CorePlugin[Core Plugin<br/>Always Enabled]
            DataSci[Data Science<br/>Plugin]
            Viz[Visualization<br/>Plugin]
            Custom[Custom<br/>Plugins]
        end
        
        Security[Security Layer<br/>Auth & Permissions]
        Audit[Audit Trail<br/>Logging System]
    end

    subgraph "ERPNext/Frappe"
        Database[(ERPNext<br/>Database)]
        Docs[Documents<br/>Customers, Sales, etc.]
        Reports[Reports<br/>Analytics]
        Workflows[Workflows<br/>Business Logic]
    end

    %% Connections
    Claude --> MCP
    GPT --> MCP
    API --> MCP
    Future --> MCP
    
    Claude -.->|One-Click| DXT
    DXT --> Bridge
    Bridge --> Server
    
    MCP --> Server
    Server --> Registry
    Registry --> CorePlugin
    Registry --> DataSci
    Registry --> Viz
    Registry --> Custom
    
    Server --> Security
    Server --> Audit
    
    CorePlugin --> Database
    DataSci --> Database
    Viz --> Database
    Custom --> Database
    
    Database --> Docs
    Database --> Reports
    Database --> Workflows

    %% Styling
    classDef llm fill:#e1f5fe,stroke:#0277bd,stroke-width:2px
    classDef integration fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef core fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef plugin fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef erp fill:#fce4ec,stroke:#c2185b,stroke-width:2px

    class Claude,GPT,API,Future llm
    class MCP,DXT,Bridge integration
    class Server,Registry,Security,Audit core
    class CorePlugin,DataSci,Viz,Custom plugin
    class Database,Docs,Reports,Workflows erp
```

## Data Flow Architecture

```mermaid
sequenceDiagram
    participant U as User
    participant C as Claude/LLM
    participant M as MCP Server
    participant T as Tool Registry  
    participant P as Plugin
    participant E as ERPNext DB

    U->>C: "Create customer Acme Corp"
    C->>M: MCP Request: create_document
    M->>T: Get tool: create_document
    T->>P: Execute Core Plugin Tool
    P->>E: frappe.get_doc().insert()
    E-->>P: Document Created
    P-->>T: Success Response
    T-->>M: Tool Result
    M-->>C: MCP Response
    C-->>U: "Customer created successfully"
    
    Note over M,E: All operations logged in audit trail
    Note over M: Security & permissions enforced
```

## Plugin Architecture Detail

```mermaid
graph LR
    subgraph "External Apps"
        App1[Custom Frappe App]
        App2[Industry-Specific App]
        App3[Third-Party App]
    end
    
    subgraph "Tool Discovery"
        Hooks[hooks.py<br/>assistant_tools]
        Scanner[Plugin Scanner]
        Registry[Tool Registry]
    end
    
    subgraph "Core Plugins"
        CoreP[Core Plugin<br/>Document Operations]
        DataP[Data Science Plugin<br/>Python Execution]
        VizP[Visualization Plugin<br/>Charts & Dashboards]
    end
    
    subgraph "Runtime Management"
        Manager[Plugin Manager]
        Config[Plugin Configuration]
        State[Enable/Disable State]
    end

    App1 --> Hooks
    App2 --> Hooks  
    App3 --> Hooks
    
    Hooks --> Scanner
    Scanner --> Registry
    
    CoreP --> Registry
    DataP --> Registry
    VizP --> Registry
    
    Registry --> Manager
    Manager --> Config
    Manager --> State

    classDef external fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef discovery fill:#f1f8e9,stroke:#388e3c,stroke-width:2px
    classDef plugins fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    classDef management fill:#fce4ec,stroke:#c2185b,stroke-width:2px

    class App1,App2,App3 external
    class Hooks,Scanner,Registry discovery
    class CoreP,DataP,VizP plugins
    class Manager,Config,State management
```

## Security & Permissions Flow

```mermaid
graph TD
    Request[LLM Request] --> Auth{Authenticated?}
    Auth -->|No| Reject[Reject Request]
    Auth -->|Yes| UserCheck{User Enabled?}
    UserCheck -->|No| Reject
    UserCheck -->|Yes| RoleCheck{Has Assistant Role?}
    RoleCheck -->|No| Reject
    RoleCheck -->|Yes| ToolPerm{Tool Allowed?}
    ToolPerm -->|No| Reject
    ToolPerm -->|Yes| DocPerm{ERPNext Permissions?}
    DocPerm -->|No| Reject
    DocPerm -->|Yes| Execute[Execute Tool]
    Execute --> AuditLog[Log to Audit Trail]
    Execute --> Response[Return Response]

    classDef security fill:#ffebee,stroke:#d32f2f,stroke-width:2px
    classDef success fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef reject fill:#fafafa,stroke:#757575,stroke-width:2px

    class Auth,UserCheck,RoleCheck,ToolPerm,DocPerm security
    class Execute,AuditLog,Response success
    class Reject reject
```

## Integration Patterns

```mermaid
graph LR
    subgraph "Pattern 1: Direct Claude Desktop"
        CD[Claude Desktop]
        DXT[DXT File]
        STDIO[STDIO Bridge]
        CD --> DXT --> STDIO
    end
    
    subgraph "Pattern 2: API Integration"
        CustomLLM[Custom LLM App]
        HTTP[HTTP API]
        MCP_API[MCP Endpoint]
        CustomLLM --> HTTP --> MCP_API
    end
    
    subgraph "Pattern 3: Webhook/Event"
        External[External System]
        Webhook[Webhook Endpoint]
        Queue[Background Queue]
        External --> Webhook --> Queue
    end
    
    subgraph "Frappe Assistant Core"
        Core[MCP Server]
    end
    
    STDIO --> Core
    MCP_API --> Core
    Queue --> Core

    classDef pattern1 fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef pattern2 fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px  
    classDef pattern3 fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef core fill:#fce4ec,stroke:#c2185b,stroke-width:2px

    class CD,DXT,STDIO pattern1
    class CustomLLM,HTTP,MCP_API pattern2
    class External,Webhook,Queue pattern3
    class Core core
```
*Plugin-based architecture supports any MCP-compatible LLM*

---

## 🚀 Getting Started

### Option 1: Claude Desktop (One-Click Setup)

Generate a DXT file for instant Claude Desktop integration:

```bash
# Generate DXT file for your site
bench --site yoursite execute frappe_assistant_core.client_packages.generate_dxt_file

# Install the generated .dxt file in Claude Desktop
# Double-click the file or drag to Claude Desktop
```

![DXT File Generation](screenshots/dxt-generation-demo.png)
*One command generates a complete Claude Desktop integration file*

### Option 2: Manual MCP Configuration

Add to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "frappe-assistant": {
      "command": "python",
      "args": ["/path/to/frappe_assistant_stdio_bridge.py"],
      "env": {
        "FRAPPE_SITE": "your-site.localhost", 
        "FRAPPE_API_KEY": "your-api-key",
        "FRAPPE_API_SECRET": "your-api-secret"
      }
    }
  }
}
```

### Option 3: Custom LLM Integration

For other LLMs or custom applications:

```python
# Connect via MCP protocol
import mcp_client

client = mcp_client.connect("http://yoursite.com/api/method/frappe_assistant_core.api.mcp.handle_request")
tools = client.list_tools()
result = client.call_tool("list_documents", {"doctype": "Customer"})
```

### Test Your Integration

Once connected, try these commands with any compatible LLM:

> "List all customers in the system"

> "Create a new customer called Acme Corp with email test@acme.com"

> "Show me sales data from this month and create a chart"

![Claude Desktop Integration](screenshots/claude-integration-demo.png)
*Natural language commands create real ERPNext documents and generate insights*

The LLM will interact directly with your ERPNext data through the MCP tools.

---

## 📚 Documentation

### Quick Start Guides
| Guide | Description |
|-------|-------------|
| [🚀 Getting Started](docs/GETTING_STARTED.md) | New to AI + ERP? Start here |
| [⚡ Claude Desktop Setup](docs/QUICK_START_CLAUDE_DESKTOP.md) | One-click integration with Claude |
| [🔐 OAuth Quick Start](docs/oauth/oauth_quick_start.md) | OAuth 2.0 setup in 2 minutes |

### Technical Documentation
| Guide | Description |
|-------|-------------|
| [🏗️ Architecture](docs/ARCHITECTURE.md) | System design and plugin architecture |
| [🔧 Tool Reference](docs/TOOL_REFERENCE.md) | Complete list of 21 available tools |
| [📖 API Reference](docs/API_REFERENCE.md) | MCP and OAuth API documentation |
| [🔐 OAuth Setup Guide](docs/oauth/oauth_setup_guide.md) | Comprehensive OAuth configuration |
| [🔒 Security Guide](docs/COMPREHENSIVE_SECURITY_GUIDE.md) | Security features and best practices |

### Development & Advanced
| Guide | Description |
|-------|-------------|
| [🚀 Development Guide](docs/DEVELOPMENT_GUIDE.md) | Create custom tools and plugins |
| [📦 Plugin Development](docs/PLUGIN_DEVELOPMENT.md) | Build your own plugins |
| [⚡ Performance Guide](docs/PERFORMANCE.md) | Optimization and monitoring |
| [📋 Release Notes v2.1.1](RELEASE_2.1.1.md) | Latest version features and improvements |

---

## 🏢 Integration Scenarios

- **Business Users + Claude**: Natural language ERP operations through Claude Desktop
- **Developers + Custom LLMs**: Build AI-powered business applications with ERPNext data
- **System Integrators**: Deploy LLM-ERP solutions for clients across industries
- **AI Companies**: Add ERPNext capabilities to existing AI products and services
- **Enterprise Teams**: Create department-specific AI tools with custom plugins

---

## 🌟 Why Choose Frappe Assistant Core?

✅ **LLM-Agnostic** - Not locked to any specific AI provider or model  
✅ **Production Ready** - Enterprise-grade security, permissions, and audit logging  
✅ **One-Click Setup** - DXT file generation for instant Claude Desktop integration  
✅ **20+ Built-in Tools** - Comprehensive ERPNext functionality out of the box  
✅ **Plugin Architecture** - Unlimited extensibility for custom business logic  
✅ **Open Source** - AGPL-3.0 licensed with transparent, community-driven development  

---

## 🤝 Contributing

We welcome contributions! This is an open source project under AGPL-3.0.

1. Fork the repository
2. Create a feature branch  
3. Add tests for new functionality
4. Submit a pull request

See [Contributing Guidelines](Contributing.md) for detailed instructions.

---

## 📄 License & Support

**License**: AGPL-3.0 - Free for commercial use with source code transparency

**Community Support**: [GitHub Issues](https://github.com/buildswithpaul/Frappe_Assistant_Core/issues) and [Discussions](https://github.com/buildswithpaul/Frappe_Assistant_Core/discussions)

**Enterprise Support**: Need custom development or priority support? Contact us at jypaulclinton@gmail.com

---

**🚀 Ready to give LLMs access to your ERPNext data? [Get started now!](#-quick-installation)**

*Built with ❤️ by the community, for developers and businesses integrating AI with ERP systems.*