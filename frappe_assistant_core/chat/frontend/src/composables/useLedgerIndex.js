import { ref, computed, onMounted, onUnmounted } from "vue";
import { deriveIndexEntries, completedExchangeCount } from "@/utils/indexEntries.js";

export const INDEX_FULL_WIDTH = 240;
export const INDEX_SPINE_WIDTH = 28;
export const INDEX_MIN_VIEWPORT = 1280;
export const INDEX_MIN_EXCHANGES = 3;
export const INDEX_COL_PAD = 48;
const COLLAPSE_KEY = "faco_index_collapsed";
const FLASH_MS = 1500;
const SPY_THROTTLE_MS = 200;

export function resolveIndexMode({ viewportWidth, shellWidth, railDockWidth, columnWidth, completedExchanges, collapsed }) {
	if (viewportWidth < INDEX_MIN_VIEWPORT) return "hidden";
	if (completedExchanges < INDEX_MIN_EXCHANGES) return "hidden";
	const leftover = shellWidth - railDockWidth - columnWidth - INDEX_COL_PAD;
	if (leftover >= INDEX_FULL_WIDTH) return collapsed ? "spine" : "full";
	if (leftover >= INDEX_SPINE_WIDTH) return "spine";
	return "hidden";
}

function loadCollapsed() {
	try {
		return localStorage.getItem(COLLAPSE_KEY) === "1";
	} catch {
		return false;
	}
}

export function useLedgerIndex({ messages, chatShellRef, railDocked, columnWidth }) {
	const viewportWidth = ref(typeof window !== "undefined" ? window.innerWidth : 1280);
	const shellWidth = ref(0);
	const collapsed = ref(loadCollapsed());
	const activeIndex = ref(-1);

	const entries = computed(() => deriveIndexEntries(messages.value));
	const mode = computed(() =>
		resolveIndexMode({
			viewportWidth: viewportWidth.value,
			shellWidth: shellWidth.value,
			railDockWidth: railDocked.value ? 300 : 0,
			columnWidth: columnWidth.value,
			completedExchanges: completedExchangeCount(entries.value),
			collapsed: collapsed.value,
		})
	);

	function toggleCollapsed() {
		collapsed.value = !collapsed.value;
		try {
			localStorage.setItem(COLLAPSE_KEY, collapsed.value ? "1" : "0");
		} catch {
			// private mode — non-fatal
		}
	}

	function jumpTo(index) {
		const el = document.querySelector(`[data-turn-index="${index}"]`);
		if (!el) return;
		el.scrollIntoView({ behavior: "smooth", block: "start" });
		el.classList.remove("ql-jump-flash");
		void el.offsetWidth;
		el.classList.add("ql-jump-flash");
		setTimeout(() => el.classList.remove("ql-jump-flash"), FLASH_MS);
		activeIndex.value = index;
	}

	let spyTimer = null;
	function updateActive(scroller) {
		if (spyTimer || !scroller) return;
		spyTimer = setTimeout(() => {
			spyTimer = null;
			const top = scroller.getBoundingClientRect().top;
			const band = top + scroller.clientHeight * 0.35;
			let current = -1;
			for (const e of entries.value) {
				if (e.kind !== "exchange") continue;
				const el = scroller.querySelector(`[data-turn-index="${e.index}"]`);
				if (el && el.getBoundingClientRect().top <= band) current = e.index;
			}
			if (current >= 0) activeIndex.value = current;
		}, SPY_THROTTLE_MS);
	}

	let resizeObserver = null;
	const onWindowResize = () => {
		viewportWidth.value = window.innerWidth;
		if (chatShellRef.value) shellWidth.value = chatShellRef.value.clientWidth;
	};
	onMounted(() => {
		window.addEventListener("resize", onWindowResize, { passive: true });
		if (typeof ResizeObserver !== "undefined" && chatShellRef.value) {
			resizeObserver = new ResizeObserver(() => {
				shellWidth.value = chatShellRef.value?.clientWidth || 0;
			});
			resizeObserver.observe(chatShellRef.value);
		}
		onWindowResize();
	});
	onUnmounted(() => {
		window.removeEventListener("resize", onWindowResize);
		if (resizeObserver) resizeObserver.disconnect();
		if (spyTimer) clearTimeout(spyTimer);
	});

	return { entries, mode, collapsed, toggleCollapsed, activeIndex, jumpTo, updateActive };
}
