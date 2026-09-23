import { baseCall, getCall } from "../_core";

const BASE = "frappe_assistant_core.chat.api.connections";

export const connections = {
	list: () => getCall(`${BASE}.list_connections`),

	add: (payload) => baseCall(`${BASE}.add_connection`, payload),

	remove: (server_name) => baseCall(`${BASE}.remove_connection`, { server_name }),

	setEnabled: (server_name, enabled) =>
		baseCall(`${BASE}.set_connection_enabled`, {
			server_name,
			enabled: enabled ? 1 : 0,
		}),

	test: (server_name) => baseCall(`${BASE}.test_connection`, { server_name }),

	setToolVisibility: (server_name, blocked_tools) =>
		baseCall(`${BASE}.set_tool_visibility`, { server_name, blocked_tools }),

	beginConnect: (endpoint_url, client_id = null, client_secret = null) =>
		baseCall(`${BASE}.begin_connect`, { endpoint_url, client_id, client_secret }),

	getConnectSession: (handle) => getCall(`${BASE}.get_connect_session`, { handle }),

	commitConnect: (handle, server_name) =>
		baseCall(`${BASE}.commit_connect`, { handle, server_name }),

	abandonConnect: (handle) => baseCall(`${BASE}.abandon_connect`, { handle }),

	beginReauth: (server_name) => baseCall(`${BASE}.begin_reauth`, { server_name }),
};
