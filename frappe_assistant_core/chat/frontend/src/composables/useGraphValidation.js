import { ref, computed } from "vue";
import { validateGraph as validateGraphLocally } from "@/components/workflows/graphUtils";

/**
 * Graph validation for the builder, client-first.
 *
 * `graphUtils.validateGraph` names the actual problem — which task has no
 * prompt, which node nothing reaches — and needs no round trip, so it runs
 * before the save. The server's validator still runs after, because it is the
 * one the engine obeys.
 *
 * @param {object} deps - { workflowStore, nodes, edges, toGraphJson }
 */
export function useGraphValidation({ workflowStore, nodes, edges, toGraphJson }) {
	const validationMessage = ref("");
	const validationClass = ref("");
	const validationErrors = ref([]);
	// The problem list is loud, so it only appears once the author has asked for
	// something the graph cannot do — not on every autosave of a half-built graph.
	const detailVisible = ref(false);
	const visibleErrors = computed(() => (detailVisible.value ? validationErrors.value : []));

	/** Local check. Returns true when the graph is worth sending. */
	function checkLocally() {
		const result = validateGraphLocally(nodes.value, edges.value);
		validationErrors.value = result.errors;
		if (result.valid) {
			validationMessage.value = "Graph valid";
			validationClass.value = "status-valid";
			detailVisible.value = false;
		} else {
			validationMessage.value = result.errors[0];
			validationClass.value = "status-error";
		}
		return result.valid;
	}

	/** The run path is the only one loud enough to open the problem list. */
	function checkBeforeRun() {
		const valid = checkLocally();
		detailVisible.value = !valid;
		return valid;
	}

	/** Server check — authoritative, run after a successful save. */
	async function checkOnServer() {
		const result = await workflowStore.validateGraph(toGraphJson());
		if (result.valid) {
			validationErrors.value = [];
			validationMessage.value = "Graph valid";
			validationClass.value = "status-valid";
		} else {
			validationErrors.value = [result.error || "Validation error"];
			validationMessage.value = result.error || "Validation error";
			validationClass.value = "status-error";
		}
		return result.valid;
	}

	function clear() {
		validationMessage.value = "";
		validationClass.value = "";
		validationErrors.value = [];
		detailVisible.value = false;
	}

	return {
		validationMessage,
		validationClass,
		validationErrors,
		visibleErrors,
		checkLocally,
		checkBeforeRun,
		checkOnServer,
		clear,
	};
}
