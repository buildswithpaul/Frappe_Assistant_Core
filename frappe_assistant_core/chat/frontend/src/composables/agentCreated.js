import { ref } from "vue";

/**
 * How many agents this user created in this tab: a new blank one, from a template, a copy, or by
 * asking in chat. Your FAC ticks Agents from it; AR's agent list is the whole site's, so it cannot
 * say who made one. A plain ref, so the Desk widget's chat can bump it without loading any store.
 */
export const agentsCreated = ref(0);

export function noteAgentCreated() {
	agentsCreated.value += 1;
}
