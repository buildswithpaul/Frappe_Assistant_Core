# Quick Start: Claude Desktop + Frappe Assistant Core

🚀 **Get Claude Desktop connected to your Frappe/ERPNext system in under 5 minutes with OAuth 2.0!**

## Step 1: Install Frappe Assistant Core

First, install the server-side app on your Frappe instance:

```bash
# On your Frappe server
bench get-app https://github.com/buildswithpaul/Frappe_Assistant_Core
bench --site [site-name] install-app frappe_assistant_core
bench restart
```

## Step 2: Enable OAuth Authentication

1. **Log into your Frappe/ERPNext instance** as Administrator
2. **Go to**: Setup → Integrations → Assistant Core Settings
3. **OAuth Tab:**
   - ✅ Check "Show Authorization Server Metadata"
   - ✅ Check "Enable Dynamic Client Registration"
   - ✅ Check "Show Protected Resource Metadata"
4. **Save**

![OAuth Settings](screenshots/oauth-settings.png)
*Enable OAuth features in Assistant Core Settings*

## Step 3: Configure Claude Desktop

Edit your Claude Desktop configuration file:

**Configuration File Locations:**
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

**Important:** Replace `your-site.com` with your actual Frappe site URL (e.g., `erp.mycompany.com`)

![Claude Config](screenshots/claude-config.png)
*Add Frappe Assistant Core to Claude Desktop configuration*

## Step 4: Authorize Claude Desktop

1. **Restart Claude Desktop**
2. **Start a new conversation**
3. **Claude will detect the new MCP server** and prompt for authorization
4. **Click "Authorize"** - your browser will open
5. **Log into Frappe** (if not already logged in)
6. **Review permissions** and click "Approve"
7. **Return to Claude Desktop** - you're connected!

![OAuth Authorization](screenshots/oauth-authorization-flow.png)
*OAuth authorization flow in browser*

**What happens behind the scenes:**
- Claude Desktop discovers OAuth endpoints automatically
- Registers as an OAuth client (dynamic client registration)
- Requests your authorization via browser
- Stores and manages access tokens securely
- Automatically refreshes tokens when they expire

## Step 5: Test the Connection

Try these commands in Claude Desktop:

## Quick Test Commands

Try these commands to verify everything is working:

```
List all customers in my system
```

```
What reports are available?
```

```
Show me recent sales invoices
```

```
What fields are available in the Item DocType?
```

## ✅ Success! What's Next?

- **Explore Tools**: Ask "What tools are available?" to see all 21+ available tools
- **Try Analytics**: "Analyze my sales data for last quarter"
- **Create Reports**: "Run the Sales Invoice report for this month"
- **Document Management**: "Create a new customer named Acme Corp"
- **Data Visualization**: "Create a chart showing top products by revenue"

## 🆘 Troubleshooting

### Common Issues & Solutions

**❌ "Failed to discover OAuth metadata"**

**Solution:**
- Verify OAuth is enabled in Assistant Core Settings
- Check your site URL is correct (include `https://`)
- Test discovery endpoint: `curl https://your-site.com/.well-known/openid-configuration`
- Ensure Frappe server is accessible from your computer

**❌ "Authorization failed" or "CORS error"**

**Solution:**
- Make sure "Enable Dynamic Client Registration" is checked in settings
- Verify you're using the correct site URL
- Check browser console for detailed errors
- Try clearing browser cache and cookies

**❌ "Token expired" errors**

**Solution:**
- This is normal! Tokens expire after 1 hour
- Claude Desktop should automatically refresh tokens
- If it doesn't, restart Claude Desktop
- Check that refresh tokens are enabled (default: yes)

**❌ "Permission denied" when using tools**

**Solution:**
- Verify your user has the "Assistant User" or "Assistant Admin" role
- Check that `assistant_enabled = 1` for your user
- Ensure you have permissions for the DocTypes you're accessing
- Check Frappe error log for detailed permission errors

### Get Help

- 🐛 **Report Issues**: [GitHub Issues](https://github.com/buildswithpaul/Frappe_Assistant_Core/issues)
- 💬 **Ask Questions**: [GitHub Discussions](https://github.com/buildswithpaul/Frappe_Assistant_Core/discussions)
- 📧 **Email Support**: jypaulclinton@gmail.com

### Need More Help?

**📚 Documentation:**
- [MCP StreamableHTTP Guide](../architecture/MCP_STREAMABLEHTTP_GUIDE.md) - Complete OAuth integration guide
- [Getting Started Guide](GETTING_STARTED.md) - Comprehensive setup guide
- [Migration Guide](MIGRATION_GUIDE.md) - Migrating from STDIO bridge
- [OAuth Setup Guide](oauth/oauth_setup_guide.md) - Detailed OAuth configuration

**🔧 Advanced Topics:**
- Multiple Frappe sites configuration
- Custom OAuth client setup
- Token lifecycle management
- Performance optimization

---

## 🎉 What You Can Do Now

Once connected, you can use Claude to:

### 📊 Business Intelligence
- **Analyze Data**: "Show me sales trends for Q4 2024"
- **Generate Reports**: "Run the Customer Analytics report"
- **Create Dashboards**: "Create a dashboard showing top products"

### 📋 Document Management
- **Create Records**: "Create a new customer named Acme Corp"
- **Update Documents**: "Update customer CUST-00001 phone to +1234567890"
- **Search**: "Find all pending sales orders above $10,000"

### 🔍 Data Exploration
- **Query**: "How many open projects do we have?"
- **Insights**: "What are our top 5 customers by revenue?"
- **Trends**: "Show me monthly sales growth"

### 📈 Advanced Analytics
- **Python Analysis**: "Analyze inventory turnover rates"
- **Visualizations**: "Create a bar chart of sales by region"
- **Statistics**: "Calculate average order value by customer type"

### 🔄 Workflow Automation
- **Bulk Operations**: "Submit all draft invoices from this week"
- **Approvals**: "What documents are pending my approval?"
- **Status Updates**: "Update all overdue tasks to high priority"

**Start transforming your business with AI-powered ERP operations!** 🚀

---

## 🔐 Security Notes

**Your data is secure:**
- ✅ OAuth 2.0 industry-standard authentication
- ✅ Tokens expire automatically (1 hour)
- ✅ All Frappe permissions enforced
- ✅ Complete audit trail of all operations
- ✅ Tokens can be revoked anytime
- ✅ HTTPS encryption for all communication

**Best practices:**
- Only authorize Claude on trusted devices
- Review OAuth tokens regularly in Frappe
- Revoke unused tokens
- Use role-based permissions appropriately

---

**Version:** 2.0.0+ | **Protocol:** MCP 2025-03-26 with OAuth 2.0
**Last Updated:** January 2025 | **License:** AGPL-3.0