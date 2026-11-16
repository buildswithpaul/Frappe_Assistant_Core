import { ref } from "vue";

/**
 * What this user did in this tab that Your FAC counts but no list can tell: an agent they created
 * (AR's agent list is the whole site's, with no creator) and a prompt template they used (not only
 * pinned). Plain refs, so the Desk widget's chat can bump them without loading any store.
 */
export const agentsCreated = ref(0);
export const templatesUsed = ref(0);

/** A new blank agent, one from a template, a copy, or one made by asking in chat. */
export function noteAgentCreated() {
	agentsCreated.value += 1;
}

/** A prompt template rendered into the ask box: the user picked it to ask its question. */
export function noteTemplateUsed() {
	templatesUsed.value += 1;
}
