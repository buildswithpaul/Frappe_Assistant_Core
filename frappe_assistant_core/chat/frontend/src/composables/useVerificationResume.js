import { ref, watch, onBeforeUnmount } from "vue";
import { api } from "@/api/client";

const POLL_INTERVAL_MS = 5000;

export function connectionErrorMessage(err) {
	const message = err?.message || "";

	if (message.includes("Failed to fetch") || message.includes("NetworkError")) {
		return "Cannot connect to the server. Please check your internet connection.";
	}
	if (message.includes("timeout") || message.includes("Timeout")) {
		return "Connection timed out. The server may be temporarily unavailable.";
	}
	if (message.includes("500") || message.includes("Internal")) {
		return "The server encountered an error. Please try again in a few moments.";
	}
	if (message.includes("401") || message.includes("403")) {
		return "Authentication failed. Please refresh and try again.";
	}
	return message || "Failed to connect to the server. Please try again.";
}

// Reconnecting re-registers the site; AR then mails the stored owner, never
// the address typed here, so no owner email is needed.
export async function requestReconnectLink(ownerEmail = null) {
	const terms = await api.registration.getTerms();
	if (!terms?.version) throw new Error("No terms available");
	return api.registration.register(ownerEmail, terms.version);
}

/**
 * The "Check your email" state: resuming it after a reload, resend,
 * change-email, and noticing when another tab finished verification.
 *
 * A pending screen can stand for two things. A new signup waits on a tenant
 * AR has never verified, and resend asks AR for a new link. A reconnect waits
 * on a tenant AR verified long ago, so AR has nothing to resend and the new
 * link comes from registering again.
 */
export function useVerificationResume({ onVerified }) {
	const verificationPending = ref(false);
	const reconnectMode = ref(false);
	const pendingEmail = ref("");
	const pendingNotice = ref("");

	function enterPending({ email = "", reconnect = false } = {}) {
		if (email) pendingEmail.value = email;
		reconnectMode.value = reconnect;
		pendingNotice.value = "";
		verificationPending.value = true;
	}

	// Returns whether the boot lookup put the screen back on "Check your email".
	function resume(state) {
		pendingEmail.value = state?.owner_email_masked || "";
		if (state?.status === "Pending Email Verification") {
			enterPending();
			return true;
		}
		if (state?.exists && state?.reregistration && state?.local_status === "Pending Email Verification") {
			enterPending({ reconnect: true });
			return true;
		}
		return false;
	}

	async function sendReconnectLink(preface = "") {
		const result = await requestReconnectLink();
		if (result?.success && result?.verification_pending) {
			reconnectMode.value = true;
			pendingNotice.value = `${preface}We sent a new link to ${pendingEmail.value || "the owner's inbox"}.`;
		} else {
			pendingNotice.value = result?.error || "Could not send the email.";
		}
	}

	async function resend(done) {
		pendingNotice.value = "";
		try {
			if (reconnectMode.value) {
				await sendReconnectLink();
				return;
			}
			const result = await api.registration.resendVerification();
			if (result?.owner_email_masked) pendingEmail.value = result.owner_email_masked;
			if (result?.reconnect_required) {
				const preface = result.already_verified
					? "This site is already verified, so this is a reconnect link. "
					: "";
				await sendReconnectLink(preface);
			} else if (result?.success) {
				pendingNotice.value = "Email resent. Check your inbox.";
			} else if (result?.retry_after) {
				pendingNotice.value = `Wait ${result.retry_after}s before sending again.`;
			} else {
				pendingNotice.value = result?.error || "Could not resend the email.";
			}
		} catch (err) {
			pendingNotice.value = connectionErrorMessage(err);
		} finally {
			if (typeof done === "function") done();
		}
	}

	// Corrects the address in place. `done(true)` closes the form; on failure
	// it stays open with the address the admin typed.
	async function changeEmail(address, done) {
		pendingNotice.value = "";
		let changed = false;
		try {
			const result = await api.registration.changePendingEmail(address);
			if (result?.success) {
				changed = true;
				pendingEmail.value = result.owner_email_masked || address;
				pendingNotice.value = "Verification email sent to the new address.";
			} else if (result?.retry_after) {
				pendingNotice.value = `Wait ${result.retry_after}s before sending again.`;
			} else {
				pendingNotice.value = result?.error || "Could not change the email.";
			}
		} catch (err) {
			pendingNotice.value = connectionErrorMessage(err);
		} finally {
			if (typeof done === "function") done(changed);
		}
	}

	// Reads this site's own status. AR is asked only on an explicit action, so
	// a waiting tab never spends the lookup budget other sites on the same
	// hosting IP share.
	let timer = null;

	async function checkVerificationLanded() {
		if (!verificationPending.value || document.hidden) return;
		try {
			const status = await api.registration.getLocalStatus();
			if (verificationPending.value && status?.registration_status === "Registered") {
				stopPolling();
				onVerified();
			}
		} catch (_) {
			// A failed check just waits for the next one.
		}
	}

	function stopPolling() {
		if (timer) clearInterval(timer);
		timer = null;
		window.removeEventListener("focus", checkVerificationLanded);
		document.removeEventListener("visibilitychange", checkVerificationLanded);
	}

	watch(verificationPending, (pending) => {
		stopPolling();
		if (!pending) return;
		timer = setInterval(checkVerificationLanded, POLL_INTERVAL_MS);
		window.addEventListener("focus", checkVerificationLanded);
		document.addEventListener("visibilitychange", checkVerificationLanded);
	});

	onBeforeUnmount(stopPolling);

	return {
		verificationPending,
		reconnectMode,
		pendingEmail,
		pendingNotice,
		enterPending,
		resume,
		resend,
		changeEmail,
	};
}
