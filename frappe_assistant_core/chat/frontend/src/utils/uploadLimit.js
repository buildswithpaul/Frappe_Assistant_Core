/**
 * The largest chat attachment the site takes, in bytes, as initialize_spa reports it (#33987):
 * null until then, or where nothing reported it. Frappe refuses a larger request before FACO's
 * own check can say why, so the composer checks first.
 */
let limit = null;

export function setUploadLimit(bytes) {
	const value = Number(bytes);
	limit = value > 0 ? value : null;
}

export const uploadLimit = () => limit;

/** "25 MB", for the message a file over the limit gets. */
export const megabytes = (bytes) => `${Math.round((bytes / 1048576) * 10) / 10} MB`;
