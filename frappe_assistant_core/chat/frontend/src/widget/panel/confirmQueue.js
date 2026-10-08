import { ref } from "vue";
import { bridge } from "../bridge.js";

/**
 * Browser-tool confirmations asked by the launcher. The queue lives outside the
 * chat component so a confirmation that arrives while the panel is still
 * bootstrapping is kept, not dropped (a dropped one would never resolve).
 */
export const confirms = ref([]);
let nextId = 0;

export function listenForConfirms() {
	return bridge.on("confirm", ({ request, resolve }) => {
		confirms.value.push({ id: ++nextId, request, resolve });
	});
}

export function settleConfirm(entry, decision) {
	confirms.value = confirms.value.filter((x) => x !== entry);
	entry.resolve(decision);
}

export function resetConfirms() {
	confirms.value = [];
}
