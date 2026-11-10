import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { useUserStore } from "@/stores/userStore";
import { usePagesStore } from "@/stores/pagesStore";
import { localDate, storage } from "@/components/spotlight/spotlightRules";
import {
	DISCOVERY_KEY,
	availableFeatures,
	emptyState,
	featureById,
	featureForPath,
	parseState,
	pickTip,
	previewContent,
} from "@/components/discover/featureCatalog";

/**
 * Feature discovery on Home: the Discover row, the weekly tip, the dots on
 * features not opened yet, and the 3-stop "where things are" tour.
 *
 * State lives in this browser, per user, like the Spotlight and tour stamps:
 * losing it only means a dot or a tip shows once more.
 */
export const useDiscoveryStore = defineStore("discovery", () => {
	const state = ref(emptyState());
	const loadedFor = ref(null);
	const preview = ref(null);
	const coachOpen = ref(false);
	const coachRequested = ref(false);
	// ChatView owns the template browser; it watches this counter.
	const templatesRequested = ref(0);

	function ensureLoaded() {
		const user = useUserStore().user;
		if (!user || loadedFor.value === user) return;
		state.value = parseState(storage.get(DISCOVERY_KEY(user)));
		loadedFor.value = user;
	}

	function save() {
		const user = useUserStore().user;
		if (user) storage.set(DISCOVERY_KEY(user), JSON.stringify(state.value));
	}

	function update(changes) {
		ensureLoaded();
		state.value = { ...state.value, ...changes };
		save();
	}

	const features = computed(() => {
		const user = useUserStore();
		return availableFeatures({ workflowsEnabled: user.workflowsEnabled, memoryEnabled: user.memoryEnabled });
	});

	// Computeds never load state (no writes while rendering): components call ensureLoaded() first.
	function isTried(id) {
		if (state.value.seen.includes(id)) return true;
		// Someone with saved Pages has used Pages, even before this browser knew.
		return id === "pages" && usePagesStore().hasPages === true;
	}

	const untried = computed(() => features.value.filter((f) => !isTried(f.id)));

	/** The Discover row shows every available feature until the user hides it or has tried them all. */
	const showRow = computed(() => !state.value.rowHidden && untried.value.length > 0);

	/** A quiet dot on a rail item whose feature this user has never opened. */
	function showDot(id) {
		if (coachOpen.value) return false;
		return features.value.some((f) => f.id === id) && !isTried(id);
	}

	function markSeen(id) {
		ensureLoaded();
		if (!featureById(id) || state.value.seen.includes(id)) return;
		update({ seen: [...state.value.seen, id] });
	}

	function markRoute(path) {
		const id = featureForPath(path);
		if (id) markSeen(id);
	}

	function hideRow() {
		update({ rowHidden: true });
	}

	/**
	 * The weekly tip. It only shows once the Discover row is gone (hidden by the
	 * user), so Home never shows the same feature twice.
	 */
	const tipId = ref(null);
	function refreshTip(now = new Date()) {
		ensureLoaded();
		if (showRow.value) {
			tipId.value = null;
			return;
		}
		const { tip, state: next } = pickTip({
			state: state.value,
			candidates: untried.value.map((f) => f.id),
			today: localDate(now),
		});
		if (next !== state.value) update({ tip: next.tip });
		tipId.value = tip;
	}

	function dismissTip(id) {
		ensureLoaded();
		if (!state.value.dismissedTips.includes(id)) {
			update({ dismissedTips: [...state.value.dismissedTips, id] });
		}
		if (tipId.value === id) tipId.value = null;
	}

	function openPreview(id) {
		const feature = featureById(id);
		if (feature) preview.value = previewContent(feature);
	}

	function closePreview() {
		preview.value = null;
	}

	/** "Give it a try": counts as opened, then goes where the feature lives. */
	function tryPreview(router) {
		const feature = preview.value && featureById(preview.value.feature);
		preview.value = null;
		if (!feature) return;
		markSeen(feature.id);
		if (tipId.value === feature.id) tipId.value = null;
		const target = feature.tryIt;
		if (target.templates) {
			templatesRequested.value++;
		} else if (target.prompt) {
			router.push({ path: "/chat", query: { prompt: target.prompt() } });
		} else if (target.route) {
			router.push(target.route);
		}
	}

	// ── 3-stop tour ──────────────────────────────────────────────────────────
	/** Auto-start once, for a first-time user who just finished onboarding. */
	function maybeStartCoach({ dayOne }) {
		ensureLoaded();
		if (coachRequested.value) return true;
		return dayOne && !state.value.coachDone;
	}

	/** Settings → Help → "Show me around" asks for the tour again. */
	function requestCoach() {
		coachRequested.value = true;
	}

	function setCoachOpen(open) {
		coachOpen.value = open;
	}

	function finishCoach() {
		coachOpen.value = false;
		coachRequested.value = false;
		update({ coachDone: true });
	}

	return {
		state,
		features,
		untried,
		showRow,
		tipId,
		preview,
		coachOpen,
		coachRequested,
		templatesRequested,
		ensureLoaded,
		isTried,
		showDot,
		markSeen,
		markRoute,
		hideRow,
		refreshTip,
		dismissTip,
		openPreview,
		closePreview,
		tryPreview,
		maybeStartCoach,
		requestCoach,
		setCoachOpen,
		finishCoach,
	};
});
