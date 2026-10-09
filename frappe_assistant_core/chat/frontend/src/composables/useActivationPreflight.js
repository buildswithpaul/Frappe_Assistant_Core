import { ref } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { directiveKey, healToolName } from "@/components/workflows/config/toolDirectives";

/**
 * Every tool the graph can call, with the label of the node that calls it and
 * the user whose tools that node gets (its own override, else the workflow's).
 */
export function collectDirectives(nodes = [], defaultUser = null) {
	const out = [];
	for (const n of nodes) {
		const config = n.data?.config || {};
		const node_label = n.data?.label || n.id;
		const user = config.user_id || defaultUser || null;
		if (n.type === "agent" || n.type === "loop") {
			for (const d of config.tool_directives || []) {
				if (d?.tool_name) out.push({ ...d, node_label, user });
			}
		}
		if (n.type === "tool" && config.tool_name) {
			const d = { tool_name: config.tool_name, capability: config.tool_name, node_label, user };
			if (config.server) d.server = config.server;
			out.push(d);
		}
	}
	return out;
}

const sameTool = (directive, entry) =>
	healToolName(directive.tool_name) === healToolName(entry.tool_name) &&
	(!directive.server || directive.server === entry.server);

function groupByUser(directives, isAdmin) {
	const groups = new Map();
	for (const { node_label, user, ...directive } of directives) {
		// Only a System Manager may name another user; anyone else resolves as themselves.
		const key = isAdmin ? user : null;
		if (!groups.has(key)) groups.set(key, { directives: new Map(), labelled: [] });
		const group = groups.get(key);
		group.directives.set(directiveKey(directive), directive);
		group.labelled.push({ ...directive, node_label });
	}
	return groups;
}

/**
 * Before an agent starts running unattended: which of its write tools would the
 * approval hook refuse for the user each node runs as? Only a tool the server
 * resolved and says is not pre-approved is a warning — a missing tool, or an
 * entry that says nothing about approval, is not. The check is advisory and
 * fails open.
 */
export function useActivationPreflight({ nodes, currentWorkflow, isAdmin }) {
	const checking = ref(false);
	const checked = ref(false);
	const warnings = ref([]);
	const error = ref(null);

	async function resolveGroup(user, group) {
		const result = await api.workflows.resolveWorkflowTools([...group.directives.values()], user);
		const found = [];
		for (const entry of result?.resolved || []) {
			if (entry?.status !== "resolved" || entry.runs_unattended !== false) continue;
			const server = entry.server || entry.server_name || "";
			found.push({
				tool: healToolName(entry.tool_name),
				server,
				user: user || "",
				nodes: group.labelled.filter((d) => sameTool(d, { ...entry, server })).map((d) => d.node_label),
			});
		}
		return found;
	}

	async function check() {
		const directives = collectDirectives(nodes.value, currentWorkflow.value?.default_user_id);
		error.value = null;
		if (!directives.length) {
			warnings.value = [];
			checked.value = true;
			return warnings.value;
		}
		checking.value = true;
		try {
			const groups = groupByUser(directives, !!isAdmin.value);
			const settled = await Promise.allSettled(
				[...groups].map(([user, group]) => resolveGroup(user, group))
			);
			const failed = settled.find((r) => r.status === "rejected");
			const seen = new Set();
			warnings.value = settled
				.filter((r) => r.status === "fulfilled")
				.flatMap((r) => r.value)
				.filter((w) => {
					const key = `${w.user}|${directiveKey({ server: w.server, tool_name: w.tool })}`;
					if (seen.has(key)) return false;
					seen.add(key);
					return true;
				});
			if (failed) {
				logger.error("Activation preflight failed:", failed.reason);
				error.value = failed.reason?.message || String(failed.reason);
			}
			checked.value = !failed;
		} catch (err) {
			logger.error("Activation preflight failed:", err);
			error.value = err.message || String(err);
			checked.value = false;
			warnings.value = [];
		} finally {
			checking.value = false;
		}
		return warnings.value;
	}

	return { checking, checked, warnings, error, check };
}
