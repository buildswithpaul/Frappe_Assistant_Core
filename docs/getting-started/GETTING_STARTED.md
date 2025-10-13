# Getting Started with Frappe Assistant Core

Welcome to Frappe Assistant Core! This guide will walk you through everything you need to know to start using AI with your ERPNext system.

## 📋 What You'll Learn

- How to install and configure Frappe Assistant Core
- Connect with Claude Desktop or other AI tools
- Basic usage patterns and commands
- Advanced features and customization
- Troubleshooting common issues

## 🎯 Prerequisites

Before we begin, make sure you have:

- **ERPNext/Frappe**: Version 15+ installed and running
- **Python**: Version 3.11+ 
- **Database**: MariaDB or MySQL properly configured
- **Admin Access**: Ability to install apps and modify configurations
- **AI Tool**: Claude Desktop, Claude API access, or other MCP-compatible AI

## 🚀 Step 1: Installation

### Quick Installation

The fastest way to get started:

```bash
# Navigate to your Frappe bench directory
cd /path/to/your/frappe-bench

# Download the app
bench get-app https://github.com/buildswithpaul/Frappe_Assistant_Core

# Install on your site (replace 'yoursite' with your actual site name)
bench --site yoursite install-app frappe_assistant_core

# Run database migrations
bench --site yoursite migrate
```

### Verify Installation

Check that everything installed correctly:

```bash
# Check if app is installed
bench --site yoursite list-apps

# Start your site
bench start
```

You should see `frappe_assistant_core` in the list of installed apps.

## ⚙️ Step 2: Configuration

### Enable the Assistant

```bash
# Enable the assistant system
bench --site yoursite set-config assistant_enabled 1

# Restart your site to apply changes
bench restart
```

### Set Up User Permissions

1. **Login to ERPNext** as Administrator
2. **Go to User Management**: Desk → Users → [Your User]
3. **Add Roles**: Assign "Assistant User" or "Assistant Admin" role
4. **Enable Assistant**: Check the "Assistant Enabled" field for the user
5. **Save** the user record

### Generate API Credentials

For secure authentication, generate API keys:

1. **Go to your User Profile**
2. **API Access section**
3. **Generate Keys** - Note down the API Key and API Secret
4. **Keep these secure** - You'll need them for AI integration

## 🤖 Step 3: Connect with AI

### Option A: Claude Desktop with OAuth (Recommended)

Connect Claude Desktop using modern OAuth 2.0 authentication:

#### 1. Enable OAuth in Assistant Core Settings

- **Login to ERPNext** as Administrator
- **Go to**: Setup → Integrations → Assistant Core Settings
- **OAuth Tab:**
  - ✅ Check "Show Authorization Server Metadata"
  - ✅ Check "Enable Dynamic Client Registration"
  - ✅ Check "Show Protected Resource Metadata"
- **Save**

#### 2. Configure Claude Desktop

Edit your Claude Desktop configuration file:

**File Locations:**
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

**Add this configuration:**

```json
{
  "mcpServers": {
    "frappe-assistant": {
      "url": "https://your-site.com/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp",
      "transport": "streamablehttp",
      "oauth": {
        "discoveryUrl": "https://your-site.com/.well-known/openid-configuration",
        "clientName": "Claude Desktop"
      }
    }
  }
}
```

**Replace `your-site.com` with your actual Frappe site URL.**

#### 3. Authorize Claude Desktop

1. **Restart Claude Desktop**
2. **Start a new conversation**
3. **When prompted**, Claude will open your browser
4. **Login to Frappe** and authorize Claude Desktop
5. **Return to Claude Desktop** - you're connected!

**What Happens Behind the Scenes:**
- Claude discovers your OAuth configuration automatically
- Registers as an OAuth client (if dynamic registration enabled)
- Requests your authorization
- Stores and manages access tokens
- Automatically refreshes tokens when they expire

**[📖 See detailed OAuth flow documentation](../architecture/MCP_STREAMABLEHTTP_GUIDE.md)**

### Option B: MCP Inspector for Testing

Test your setup with the MCP Inspector tool:

#### 1. Enable Browser-Based Clients

- **Go to**: Assistant Core Settings → OAuth Tab
- **Add to "Allowed Public Client Origins"**: `http://localhost:6274`
- **Save**

#### 2. Use MCP Inspector

1. **Open**: http://localhost:6274/
2. **Select**: "Streamable HTTP" transport
3. **Enter URL**: `https://your-site.com/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp`
4. **Click**: "Open Auth Settings"
5. **Click**: "Quick OAuth Flow"
6. **Authorize** when prompted

You can now test tools and see MCP requests/responses!

### Option C: Custom Application Integration

For custom applications or other MCP clients, see the complete OAuth integration example in our [MCP StreamableHTTP Guide](../architecture/MCP_STREAMABLEHTTP_GUIDE.md#option-3-custom-application-integration).

**Quick Example:**

```python
import requests

# 1. Discover OAuth endpoints
config = requests.get(
    "https://your-site.com/.well-known/openid-configuration"
).json()

# 2. Perform OAuth flow (see full example in guide)
# ... authorization code flow with PKCE ...

# 3. Make authenticated MCP requests
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

response = requests.post(
    config["mcp_endpoint"],
    headers=headers,
    json={
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": 1
    }
)
print(response.json())
```

### 🔄 Migrating from STDIO Bridge?

If you're upgrading from an older version that used the STDIO bridge, see our [Migration Guide](MIGRATION_GUIDE.md) for step-by-step instructions.

## 🎉 Step 4: Test Your Setup

### Basic Test Commands

Once connected, try these commands with your AI:

#### 1. Check Connection
> "Can you connect to my ERPNext system? Show me the server status."

#### 2. Simple Document Query
> "How many customers do I have in the system?"

#### 3. Create a Test Document
> "Create a test customer called 'AI Test Customer' with email 'test@ai.com'"

#### 4. Data Analysis
> "Show me a summary of sales invoices from this month"

### Expected Responses

If everything is working, you should see:

✅ **Connection Successful**: AI responds with system information  
✅ **Data Access**: AI can read your ERPNext data  
✅ **Document Creation**: AI can create and modify documents  
✅ **Analysis Capabilities**: AI can analyze and report on your data  

## 🎯 Understanding Core Capabilities

### Document Operations

```
📝 CREATE: "Create a new customer named Acme Corp"
📖 READ: "Show me customer details for CUST-00001"
✏️ UPDATE: "Update the customer's phone number to +1234567890"
🗑️ DELETE: "Delete the test customer record"
📋 LIST: "List all customers created this week"
```

### Search & Discovery

```
🔍 GLOBAL SEARCH: "Find all documents mentioning 'bulk order'"
🎯 TARGETED SEARCH: "Search for sales orders above $10,000"
📊 FILTERED SEARCH: "Show me pending purchase orders from this month"
```

### Analytics & Reporting

```
📊 CHARTS: "Create a bar chart of monthly sales"
📈 ANALYSIS: "Analyze our top 10 customers by revenue"
📋 REPORTS: "Run the Sales Analytics report for Q4"
🔢 CALCULATIONS: "Calculate total revenue for this year"
```

### Advanced Features

```
🐍 PYTHON CODE: "Execute Python code to analyze inventory trends"
📊 DASHBOARDS: "Create a dashboard showing key sales metrics"
🔄 WORKFLOWS: "Submit all pending sales orders for approval"
```

## 🔧 Customization Options

### Plugin Management

Access the admin interface to manage plugins:

```
URL: https://yoursite.com/desk#/fac-admin
```

Available plugins:
- **Core** (always enabled): Document operations, search, reports
- **Data Science**: Python execution, statistical analysis
- **Visualization**: Charts, dashboards, KPIs
- **Batch Processing**: Bulk operations

### Custom Tools

Create your own tools for specific business needs:

1. **External App Tools** (Recommended): Add tools to your existing Frappe apps
2. **Plugin Development**: Create internal plugins within the core system

See [Development Guide](../development/DEVELOPMENT_GUIDE.md) for details.

## 🚨 Troubleshooting

### Common Issues

#### Connection Problems

**Problem**: AI can't connect to ERPNext
**Solution**: 
- Check API credentials are correct
- Verify site URL is accessible
- Ensure `assistant_enabled = 1` in configuration
- Check firewall settings

#### Permission Errors

**Problem**: "Access denied" or "Permission denied"
**Solution**:
- Add "Assistant User" role to your user
- Enable "Assistant Enabled" field on user record
- Check DocType permissions are properly configured

#### Tool Not Found Errors

**Problem**: "Tool 'xyz' not found"
**Solution**:
- Check which plugins are enabled
- Verify plugin contains the required tool
- Restart system after enabling plugins

#### Performance Issues

**Problem**: Slow responses or timeouts
**Solution**:
- Check database performance
- Enable caching in Frappe configuration
- Consider upgrading server resources
- Review plugin configurations

### Getting Help

If you're still having issues:

1. **Check Documentation**: Review [Technical Documentation](../architecture/TECHNICAL_DOCUMENTATION.md)
2. **Community Support**: Post in [GitHub Discussions](https://github.com/buildswithpaul/Frappe_Assistant_Core/discussions)
3. **Report Bugs**: Use [GitHub Issues](https://github.com/buildswithpaul/Frappe_Assistant_Core/issues)
4. **Enterprise Support**: Contact jypaulclinton@gmail.com for priority support

## 🎓 Next Steps

Now that you're up and running:

1. **Explore Tools**: Try different commands and see what the AI can do
2. **Learn Advanced Features**: Check out [Tool Reference](../api/TOOL_REFERENCE.md)
3. **Customize**: Create custom tools for your specific business needs
4. **Monitor**: Set up audit logging and monitoring
5. **Scale**: Consider performance optimization as you grow

## 💡 Tips for Success

### Best Practices

- **Start Simple**: Begin with basic document operations before complex analytics
- **Use Specific Commands**: Clear, specific requests get better results
- **Test Thoroughly**: Always verify AI-generated data and operations
- **Monitor Usage**: Keep an eye on audit logs and system performance
- **Stay Updated**: Regular updates bring new features and improvements

### Common Use Cases

- **Sales Team**: Customer management, opportunity tracking, quote generation
- **Finance**: Invoice processing, payment tracking, financial reporting
- **Operations**: Inventory management, purchase order automation
- **Management**: Dashboard creation, KPI monitoring, executive reporting
- **IT**: Custom workflows, data integration, system monitoring

---

**🎉 Congratulations!** You're now ready to transform your ERP operations with AI assistance.

**Questions?** Check our [comprehensive documentation](README.md#-documentation) or reach out to the community.

*Happy AI-powered ERPing!* 🚀