import { computed, ref, shallowRef, watch } from "vue";

import { derivePageChips } from "@/utils/pageChips";

/** The page dock takes half the chat shell, and never less than this. */
export const PAGE_DOCK_MIN_WIDTH = 420;

export const pageDockWidth = (shellWidth) => Math.max(PAGE_DOCK_MIN_WIDTH, shellWidth / 2);

// One panel per SPA: a chip deep in the message tree and the dock beside the chat share it.
const openName = ref(null);
const refreshKey = ref(0);
const chips = shallowRef([]);
// How many PageDocks are mounted: the SPA has one, the Desk widget none.
const docks = ref(0);
const dockMounted = computed(() => docks.value > 0);

/** Called by a mounted PageDock; returns the call that unregisters it. */
function registerDock() {
	docks.value++;
	let registered = true;
	return () => {
		if (registered) docks.value--;
		registered = false;
	};
}

// The page the panel shows, for FACO's screenshot: its element, whether it is a draft's frame, and
// the refreshKey it was drawn for.
const pageView = shallowRef(null);

/** Called by a mounted PageView; returns the call that withdraws it. */
function showPageView({ element, draft }) {
	const view = { element, draft, refreshKey: refreshKey.value };
	pageView.value = view;
	return () => {
		if (pageView.value === view) pageView.value = null;
	};
}

// Drawn, with no write to it in flight and none landed since it was drawn.
function pageSettled() {
	const view = pageView.value;
	const chip = chips.value.find((c) => c.name === openName.value);
	return Boolean(view) && !chip?.pending && view.refreshKey === refreshKey.value;
}

/** Resolves true once the open page is settled, or false after `timeoutMs`. */
function whenPageSettled(timeoutMs) {
	if (pageSettled()) return Promise.resolve(true);
	return new Promise((resolve) => {
		const finish = (settled) => {
			clearTimeout(timer);
			stop();
			resolve(settled);
		};
		const timer = setTimeout(() => finish(false), timeoutMs);
		const stop = watch(pageSettled, (settled) => settled && finish(true));
	});
}

function open(name) {
	openName.value = name || null;
}

function close() {
	openName.value = null;
}

function trackPageWrites(messages) {
	const conversationChips = computed(() =>
		derivePageChips((messages.value || []).flatMap((message) => message?.blocks || [])),
	);
	watch(conversationChips, (value) => (chips.value = value), { immediate: true });

	const openVersion = computed(
		() => conversationChips.value.find((chip) => chip.name === openName.value)?.version ?? 0,
	);
	// Refetch when a write to the page already open lands, not when another page is opened.
	watch([openName, openVersion], ([name, version], [previousName, previousVersion]) => {
		if (name && name === previousName && version !== previousVersion) refreshKey.value++;
	});
}

/**
 * The page panel's state: which page is open, and a key that changes when it must be refetched.
 *
 * @param {import('vue').Ref<Array>} [messages] the conversation; the dock passes it so writes to
 *   the open page refresh it and `chips` carries every page's version and pending state.
 */
export function usePagePanel(messages) {
	if (messages) trackPageWrites(messages);
	return {
		openName,
		refreshKey,
		chips,
		dockMounted,
		registerDock,
		open,
		close,
		pageView,
		showPageView,
		whenPageSettled,
	};
}
