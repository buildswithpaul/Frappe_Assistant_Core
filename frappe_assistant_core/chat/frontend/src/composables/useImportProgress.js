/**
 * Live import progress (#34416), shared by the progress block under start_import and the side
 * panel's Import card. The server says where each session stands (once on load, so a reopened
 * conversation shows it as it is now); Frappe's data_import_progress events move the bar while
 * the import runs. No model call: the model doesn't poll an import any more.
 */
import { onBeforeUnmount, reactive, unref, watch } from "vue";
import { api } from "@/api/client";
import { onSpaSocketEvent } from "@/composables/useStreaming";
import { logger } from "@/utils/logger";

const EVENT = "data_import_progress";
// While an import runs, the server is asked again this often: a missed event, or an opening
// import (which sends none), still moves on.
export const REFRESH_MS = 15000;

const state = reactive({ sessions: {}, steps: [] });
let users = 0;
let unsubscribe = null;
let timer = null;

/** Frappe's realtime in Desk, the SPA's own socket on /copilot. */
function subscribe(fn) {
	const realtime = window.frappe?.realtime;
	if (realtime && typeof realtime.on === "function") {
		realtime.on(EVENT, fn);
		return () => realtime.off?.(EVENT, fn);
	}
	return onSpaSocketEvent(EVENT, fn);
}

export async function refresh(names) {
	const wanted = (names || []).filter(Boolean);
	if (!wanted.length) return;
	try {
		const reply = await api.imports.progress(wanted);
		for (const session of reply?.sessions || []) {
			// what the server says now replaces the live bar: it counted the rows itself
			state.sessions[session.session] = { ...session, live: null };
		}
		if (reply?.steps?.length) state.steps = reply.steps;
	} catch (error) {
		logger.warn("import progress:", error);
	}
	schedule();
}

function importing() {
	return Object.values(state.sessions).filter((s) => s.importing).map((s) => s.session);
}

function schedule() {
	clearTimeout(timer);
	timer = null;
	const running = importing();
	if (running.length && users) timer = setTimeout(() => refresh(running), REFRESH_MS);
}

/** A data_import_progress event: the bar of the session whose Data Import it is moves. */
export function onProgress(payload) {
	const session = Object.values(state.sessions).find((s) => s.data_import && s.data_import === payload?.data_import);
	if (!session) return;
	const live = { current: Number(payload.current) || 0, total: Number(payload.total) || session.total || 0 };
	if (payload.inserted !== undefined) live.created = Number(payload.inserted) + Number(payload.updated || 0);
	if (payload.failed !== undefined) live.failed = Number(payload.failed);
	session.live = live;
	// the last row: the server has the end, its counts and the session's status
	if (live.total && live.current >= live.total) setTimeout(() => refresh([session.session]), 1500);
}

/** What the block or the card shows for a session: done of total, created, failed. */
export function figures(session) {
	if (!session) return null;
	const live = session.live || {};
	const total = live.total || session.total || 0;
	const done = session.ended ? total || session.created + session.failed : live.current || session.created + session.failed;
	return {
		total,
		done: total ? Math.min(done, total) : done,
		created: live.created ?? session.created,
		failed: live.failed ?? session.failed,
		percent: total ? Math.min(100, Math.round((Math.min(done, total) / total) * 100)) : session.ended ? 100 : 0,
	};
}

export function useImportProgress(names) {
	users += 1;
	if (!unsubscribe) unsubscribe = subscribe(onProgress);
	watch(() => [...(unref(names) || [])], (list) => refresh(list), { immediate: true });
	onBeforeUnmount(() => {
		users -= 1;
		if (!users) {
			unsubscribe?.();
			unsubscribe = null;
			clearTimeout(timer);
			timer = null;
		}
	});
	return { state };
}

// for tests
export function _reset() {
	state.sessions = {};
	state.steps = [];
	users = 0;
	unsubscribe?.();
	unsubscribe = null;
	clearTimeout(timer);
	timer = null;
}
