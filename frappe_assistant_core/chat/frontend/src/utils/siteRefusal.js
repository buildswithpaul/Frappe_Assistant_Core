import { api } from "@/api/client";
import { logger } from "@/utils/logger";

/**
 * Why FAC Cloud cannot call this site back as the current user, or null.
 *
 * Connecting proves only that the site answers a ping. This asks FAC Cloud to
 * make its real, authenticated call, which a firewall blocking FAC Cloud
 * refuses even when the ping passes. Run it after connect returns, as its own
 * request: the call back needs a free worker on this site.
 *
 * Only a definite refusal is reported. A check that could not run says nothing
 * about the connection, and must not strand a user whose chat may well work.
 *
 * @returns {Promise<string|null>}
 */
export async function siteRefusal() {
	try {
		const result = await api.user.verifySiteConnection();
		return result?.success === false && result.error ? result.error : null;
	} catch (err) {
		logger.warn("Site connection check could not run:", err);
		return null;
	}
}
