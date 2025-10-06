# Quick Start: Claude Desktop + Frappe Assistant Core

🚀 **Get Claude Desktop connected to your Frappe/ERPNext system in under 5 minutes!**

## Step 1: Install Frappe Assistant Core App

First, install the server-side app on your Frappe instance:

```bash
# On your Frappe server
bench get-app https://github.com/buildswithpaul/Frappe_Assistant_Core
bench --site [site-name] install-app frappe_assistant_core
bench restart
```

## Step 2: Get Your API Credentials

1. **Log into your Frappe/ERPNext instance**
2. **Go to Settings → Integrations → API**
3. **Click "Generate Keys"** for your user
4. **Copy both the API Key and API Secret** (you'll need these in step 4)

## Step 3: Download & Install Claude Desktop Extension

### Download the Extension
**Click here to download:** [claude-for-frappe.dxt](https://github.com/buildswithpaul/Frappe_Assistant_Core/releases/download/v2.1.1/claude-for-frappe.dxt)

### Install the Extension

**Windows:**
1. Download the `.dxt` file
2. Double-click `claude-for-frappe.dxt` to install
3. Claude Desktop will automatically install the extension

**macOS:**
1. Download the `.dxt` file
2. Double-click `claude-for-frappe.dxt` in Finder
3. Claude Desktop will automatically install the extension

**Linux:**
1. Download the `.dxt` file
2. Double-click the file in your file manager
3. Or run: `claude-desktop --install-extension claude-for-frappe.dxt`

## Step 4: Configure the Extension

1. **Open Claude Desktop**
2. **Go to Settings → Extensions**
3. **Find "Claude for Frappe ERP"**
4. **Click "Configure"**
5. **Fill in your settings:**
   - **Server URL**: `https://your-frappe-instance.com`
   - **API Key**: `paste your API key from step 2`
   - **API Secret**: `paste your API secret from step 2`
   - **Debug Mode**: Leave unchecked (unless troubleshooting)

## Step 5: Test the Connection

1. **Restart Claude Desktop**
2. **Start a new conversation**
3. **Type:** `Test my Frappe connection`

You should see a response confirming the connection and listing available tools!

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

## 🆘 Having Issues?

### Common Problems & Solutions

**❌ "Connection failed"**
- ✅ Verify your Server URL includes `https://` and no trailing slash
- ✅ Check that your API credentials are correctly copied
- ✅ Ensure your Frappe server is accessible from your computer

**❌ "Authentication failed"**
- ✅ Regenerate your API key and secret in Frappe
- ✅ Make sure your user has API access enabled
- ✅ Verify you have the required permissions in Frappe

**❌ "Extension won't install"**
- ✅ Make sure you have the latest version of Claude Desktop
- ✅ Try downloading the DXT file again
- ✅ Check if antivirus software is blocking the installation

**❌ "Python not found"**
- ✅ Install Python 3.8+ and make sure it's in your system PATH
- ✅ On Windows, try using "python" instead of "python3" in config

### Get Help

- 🐛 **Report Issues**: [GitHub Issues](https://github.com/buildswithpaul/Frappe_Assistant_Core/issues)
- 💬 **Ask Questions**: [GitHub Discussions](https://github.com/buildswithpaul/Frappe_Assistant_Core/discussions)
- 📧 **Email Support**: jypaulclinton@gmail.com

### Advanced Setup

For advanced configuration options, multiple servers, or manual JSON setup, see the [Complete Setup Guide](CLAUDE_DESKTOP_SETUP_GUIDE.md).

---

## 🎉 Transform Your Business Data Analysis with AI!

Once connected, you can:

- **📊 Analyze Business Data** - Get insights from your ERP data using natural language
- **📈 Generate Reports** - Run financial, sales, and custom reports instantly
- **📋 Manage Documents** - Create, update, and search through your business documents
- **🔍 Explore Your Data** - Ask questions about your business and get intelligent answers
- **📊 Create Visualizations** - Generate charts and graphs from your data
- **⚡ Run Custom Analysis** - Execute Python code for advanced analytics

**Start asking Claude about your business data today!** 🚀

---

**Version:** v2.1.1 | **Last Updated:** January 2025 | **License:** MIT