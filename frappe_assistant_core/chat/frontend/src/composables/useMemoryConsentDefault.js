import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

/**
 * Memory consent's starting state on the first-run tour (spec §8.1, F4).
 *
 * A pre-ticked box is not valid GDPR consent, so the switch starts OFF and
 * turns ON only for an explicit "Opt-Out" workspace policy. Opt-In, a missing
 * policy, a failed request and the loading state all leave it off, and a
 * choice the user makes before the policy arrives is never overwritten.
 * `policySettled` stays false until the request resolves either way.
 */
function policyEnablesConsent(config) {
	const policy = config?.default_memory_consent ?? config?.tenant?.default_memory_consent;
	return policy === "Opt-Out";
}

export function useMemoryConsentDefault() {
	const memoryConsent = ref(false);
	const policySettled = ref(false);
	let userChose = false;

	function setMemoryConsent(value) {
		userChose = true;
		memoryConsent.value = value;
	}

	onMounted(async () => {
		try {
			const enabled = policyEnablesConsent(await api.privacy.getConfig());
			if (!userChose) memoryConsent.value = enabled;
		} catch (err) {
			logger.warn("Workspace consent policy unavailable; memory stays off:", err);
		} finally {
			policySettled.value = true;
		}
	});

	return { memoryConsent, policySettled, setMemoryConsent };
}
