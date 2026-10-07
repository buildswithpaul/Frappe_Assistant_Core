const SOCKET_POLL_MS = 500;
const SOCKET_POLL_MAX = 20;

/**
 * Events for the current session that arrive before the lazy panel exists would be dropped, because
 * only the panel's useStreaming listens. Watch the session room from the launcher and, on the first
 * event, mount the panel so its own listeners (and its hydrate-on-mount) take over; an approval also
 * raises attention. Once the panel is mounted this does nothing.
 *
 * The launcher never leaves the room: the panel's useStreaming joins the same one.
 */
export function startStreamWatch({ getSessionId, isMounted, ensurePanel, onApproval }) {
	let stopped = false;
	let pollTimer = null;
	let attached = false;
	let mounting = false;

	const trigger = (data, isApproval) => {
		if (stopped || isMounted() || !data || data.session_id !== getSessionId()) return;
		if (!mounting) {
			mounting = true;
			// A failed load is retried by the next event.
			Promise.resolve(ensurePanel()).catch(() => (mounting = false));
		}
		if (isApproval) onApproval(data);
	};
	const onStream = (data) => trigger(data, data && data.event === "approval_required");
	const onInterrupt = (data) => trigger(data, false);

	const subscribe = () => {
		const sid = getSessionId();
		const realtime = window.frappe && window.frappe.realtime;
		if (!sid || !realtime || !realtime.task_subscribe) return;
		try {
			realtime.task_subscribe(sid);
		} catch {
			// The socket is not up yet; the connect handler subscribes.
		}
	};

	const attach = () => {
		const realtime = window.frappe && window.frappe.realtime;
		realtime.on("faco_message_stream", onStream);
		realtime.on("ar_interrupt_event", onInterrupt);
		realtime.on("connect", subscribe);
		attached = true;
		subscribe();
	};

	// realtime.on() is a silent no-op until the socket exists, so wait for it.
	let polls = 0;
	const tick = () => {
		pollTimer = null;
		if (stopped) return;
		const realtime = window.frappe && window.frappe.realtime;
		if (realtime && realtime.socket) return attach();
		if (++polls < SOCKET_POLL_MAX) pollTimer = setTimeout(tick, SOCKET_POLL_MS);
	};
	tick();

	function stop() {
		stopped = true;
		clearTimeout(pollTimer);
		const realtime = window.frappe && window.frappe.realtime;
		if (attached && realtime && realtime.off) {
			realtime.off("faco_message_stream", onStream);
			realtime.off("ar_interrupt_event", onInterrupt);
			realtime.off("connect", subscribe);
		}
	}
	stop.resubscribe = subscribe;
	return stop;
}
