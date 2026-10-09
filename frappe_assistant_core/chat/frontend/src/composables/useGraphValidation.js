import { ref, computed, watch } from "vue";
import { validateGraph as validateGraphLocally } from "@/components/workflows/graphUtils";
import { __ } from "@/utils/i18n";

/**
 * Graph validation for the builder, client-first and live.
 *
 * `graphUtils.validateGraph` names the actual problem — which task has no
 * prompt, which node nothing reaches — and needs no round trip, so it runs on
 * every change. The server's validator still runs after a save, because it is
 * the one the engine obeys; its rejection keeps Run blocked until the next
 * server check passes.
 *
 * @param {object} deps - { workflowStore, nodes, edges, toGraphJson, sync } — `sync`
 * ({ updateNodeData }) carries a marker change to the canvas's own node copy.
 */
export function useGraphValidation({ workflowStore, nodes, edges, toGraphJson, sync = null }) {
	const validationMessage = ref("");
	const validationClass = ref("");
	const serverError = ref("");

	const liveValidation = computed(() => validateGraphLocally(nodes.value, edges.value));
	const visibleErrors = computed(() => {
		const errors = liveValidation.value.errors;
		return serverError.value && !errors.includes(serverError.value)
			? [...errors, serverError.value]
			: errors;
	});
	const canRun = computed(() => visibleErrors.value.length === 0);
	const runBlockReason = computed(() => visibleErrors.value[0] || "");

	// Issues live on node.data so every node component can mark itself. Vue Flow
	// only re-renders on a new `data` object, so a changed list replaces it —
	// on the canvas's copy too, which the builder's array does not reach.
	// vueFlowToGraphJson serialises only label and config, so they never save.
	watch(
		() => liveValidation.value.issues,
		(issues) => {
			const byNode = new Map();
			for (const issue of issues) {
				if (!issue.nodeId) continue;
				byNode.set(issue.nodeId, [...(byNode.get(issue.nodeId) || []), issue.message]);
			}
			for (const n of nodes.value) {
				const next = byNode.get(n.id) || [];
				const prev = n.data?.issues || [];
				if (next.join("\n") === prev.join("\n")) continue;
				n.data = { ...n.data, issues: next };
				sync?.updateNodeData(n.id, { issues: next });
			}
		},
		{ immediate: true },
	);

	/** Local check. Returns true when the graph is worth sending. */
	function checkLocally() {
		const result = liveValidation.value;
		if (result.valid) {
			validationMessage.value = __("Graph valid");
			validationClass.value = "status-valid";
		} else {
			validationMessage.value = result.errors[0];
			validationClass.value = "status-error";
		}
		return result.valid;
	}

	/** True when nothing, local or from the last server check, blocks a run. */
	function checkBeforeRun() {
		checkLocally();
		return canRun.value;
	}

	/** Server check — authoritative, run after a successful save. */
	async function checkOnServer() {
		const result = await workflowStore.validateGraph(toGraphJson());
		if (result.transport) {
			validationMessage.value = result.error || __("Could not reach the server");
			validationClass.value = "status-error";
			return false;
		}
		if (result.valid) {
			serverError.value = "";
			validationMessage.value = __("Graph valid");
			validationClass.value = "status-valid";
		} else {
			serverError.value = result.error || __("Validation error");
			validationMessage.value = serverError.value;
			validationClass.value = "status-error";
		}
		return result.valid;
	}

	function clear() {
		validationMessage.value = "";
		validationClass.value = "";
		serverError.value = "";
	}

	return {
		validationMessage,
		validationClass,
		liveValidation,
		visibleErrors,
		canRun,
		runBlockReason,
		checkLocally,
		checkBeforeRun,
		checkOnServer,
		clear,
	};
}
