import { baseCall, getCall } from "../_core";

export const user = {
	getCurrent: () =>
		getCall("frappe_assistant_core.chat.api.can_use_faco"),

	// Per-user registration and MCP server management
	getAuthStatus: () =>
		getCall("frappe_assistant_core.chat.api.get_user_auth_status"),

	connectFACServer: () =>
		baseCall("frappe_assistant_core.chat.api.connect_fac_mcp_server"),

	getMCPServers: () =>
		getCall("frappe_assistant_core.chat.api.get_user_mcp_servers"),

	reconnectServer: (serverName = "Main Frappe Site") =>
		baseCall("frappe_assistant_core.chat.api.reconnect_mcp_server", {
			server_name: serverName,
		}),

	disconnectServer: (serverName = "Main Frappe Site") =>
		baseCall("frappe_assistant_core.chat.api.disconnect_mcp_server", {
			server_name: serverName,
		}),

	listTools: () =>
		getCall("frappe_assistant_core.chat.api.list_user_tools"),
};
