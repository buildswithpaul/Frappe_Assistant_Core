/**
 * Which client the shared chat stores are running in. FAC Chat and the Desk
 * widget use the same stores; the few wire-level differences live here so
 * neither surface forks store logic.
 *
 * clientType is load-bearing: the server only offers browser tools to
 * "widget", and a resume that changes it makes AR rebuild the paused agent.
 */
const DEFAULT = Object.freeze({
	name: "spa",
	clientType: "spa",
	modelId: null,
	spotlightSurface: "spa",
	clientSignals: null,
});

let current = DEFAULT;

export function configureSurface(overrides = {}) {
	current = Object.freeze({ ...DEFAULT, ...overrides });
}

export function getSurface() {
	return current;
}

export function resetSurface() {
	current = DEFAULT;
}

/** The surface's diagnostics counts, or null. Never throws. */
export function surfaceClientSignals() {
	try {
		return current.clientSignals ? current.clientSignals() : null;
	} catch {
		return null;
	}
}
