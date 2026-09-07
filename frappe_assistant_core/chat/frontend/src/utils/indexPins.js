const keyFor = (sessionId) => `faco_index_pins_${sessionId || "default"}`;

export function loadPins(sessionId) {
	try {
		const raw = localStorage.getItem(keyFor(sessionId));
		const parsed = raw ? JSON.parse(raw) : [];
		return Array.isArray(parsed) ? parsed : [];
	} catch {
		return [];
	}
}

export function togglePin(sessionId, pin) {
	const pins = loadPins(sessionId);
	const next = pins.some((p) => p.messageId === pin.messageId)
		? pins.filter((p) => p.messageId !== pin.messageId)
		: [...pins, pin];
	try {
		localStorage.setItem(keyFor(sessionId), JSON.stringify(next));
	} catch {
		// private mode — session-only pins
	}
	return next;
}
