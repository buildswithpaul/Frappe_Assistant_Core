import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { __ } from "@/utils/i18n";
import { useToast } from "@/composables/useToast";
import { useUserStore } from "@/stores/userStore";
import { usePagesStore } from "@/stores/pagesStore";
import { useChatStore } from "@/stores/chatStore";
import { useTemplateStore } from "@/stores/templateStore";
import { useWorkflowStore } from "@/stores/workflowStore";
import { useNotificationStore } from "@/stores/notificationStore";
import { useTourStore } from "@/stores/tourStore";
import { localDate } from "@/components/spotlight/spotlightRules";
import { availableFeatures, featureById, featureForPath, previewContent } from "@/components/discover/featureCatalog";
import { TIP_ORDER, dailyTips } from "@/components/discover/dailyTips";
import {
	availablePowers,
	emptyState,
	isPowerUsed,
	liveTips,
	parseState,
	pickDailyTip,
	progressOf,
	tipContent,
	unseenStory,
} from "@/components/discover/discoveryRules";

const SAVE_DELAY_MS = 800;
const LOAD_QUIET_MS = 4000;

/**
 * Feature discovery in the full FAC Chat (/copilot): the daily Did you know tip, What's new
 * stories, the Your FAC ring, the rail dots and the 3-stop tour.
 *
 * Tips ship with FAC (dailyTips.js). AR decides the rest: stories are AR notifications, powers
 * come from capabilities. This store decides when, from what the user really did, and keeps
 * that on the user's preferences so it follows them across browsers.
 *
 * Nothing runs until App.vue calls init(): the Desk widget shares some stores with this
 * one and must stay a plain chat.
 */
export const useDiscoveryStore = defineStore("discovery", () => {
	const state = ref(emptyState());
	const started = ref(false);
	const switches = ref({ show_tips: true, show_whats_new: true, show_progress: true });
	const preview = ref(null);
	// Lives on the tour store so the Spotlight can see it; read and set here for Home and the rail.
	const coachOpen = computed(() => useTourStore().coachOpen);
	const coachRequested = ref(false);
	// ChatView owns the template browser; it watches this counter.
	const templatesRequested = ref(0);
	const story = ref(null);
	const panelOpen = ref(false);
	const justUnlocked = ref(null);
	let saveTimer = null;
	// Unlocks found while the app loads are old news; only later ones get a toast.
	let celebrate = false;

	// ── State ───────────────────────────────────────────────────────────
	function save() {
		clearTimeout(saveTimer);
		saveTimer = setTimeout(() => {
			api.home.saveDiscoveryState(state.value).catch((err) => logger.warn("Discovery state not saved:", err));
		}, SAVE_DELAY_MS);
	}

	function update(changes) {
		state.value = { ...state.value, ...changes };
		if (started.value) save();
	}

	function addTo(key, id) {
		if (state.value[key].includes(id)) return false;
		update({ [key]: [...state.value[key], id] });
		return true;
	}

	/** Called once by App.vue after boot. Kept separate so the widget never starts it. */
	function init() {
		if (started.value) return;
		const prefs = useUserStore().discoveryPrefs;
		if (prefs) {
			switches.value = {
				show_tips: prefs.show_tips !== false,
				show_whats_new: prefs.show_whats_new !== false,
				show_progress: prefs.show_progress !== false,
			};
		}
		state.value = parseState(prefs && prefs.state);
		started.value = true;
		if (!state.value.first_day) update({ first_day: localDate() });
		watchUsage();
		// What the checks find while the app loads (chats, Pages) was done before: no toast for it.
		setTimeout(() => {
			celebrate = true;
		}, LOAD_QUIET_MS);
	}

	/** Settings → Home changed a switch. */
	function setSwitches(patch) {
		const next = { ...switches.value };
		for (const key of Object.keys(next)) if (key in patch) next[key] = patch[key] !== false;
		switches.value = next;
		if (!next.show_whats_new) story.value = null;
		if (!next.show_progress) panelOpen.value = false;
	}

	// ── Opened (rail dots) ──────────────────────────────────────────────
	const features = computed(() => {
		const user = useUserStore();
		return availableFeatures({ workflowsEnabled: user.workflowsEnabled, memoryEnabled: user.memoryEnabled });
	});

	function isOpened(id) {
		return state.value.seen.includes(id) || state.value.used.includes(id);
	}

	/** A quiet dot on a rail item whose feature this user has never opened. */
	function showDot(id) {
		if (!started.value || coachOpen.value) return false;
		return features.value.some((f) => f.id === id) && !isOpened(id);
	}

	function markSeen(id) {
		if (featureById(id)) addTo("seen", id);
	}

	function markRoute(path) {
		const id = featureForPath(path);
		if (id) markSeen(id);
	}

	// ── Used (real data) ────────────────────────────────────────────────
	function markUsed(id) {
		if (!started.value || !addTo("used", id)) return;
		if (state.value.celebrated.includes(id)) return;
		update({ celebrated: [...state.value.celebrated, id] });
		if (!celebrate) return;
		const power = powers.value.find((p) => p.id === id);
		if (!power || !showProgress.value) return;
		justUnlocked.value = id;
		const { done, total } = progress.value;
		useToast().showSuccess(__("Unlocked: {0} · {1} of {2}", [power.label, done, total]));
		setTimeout(() => {
			if (justUnlocked.value === id) justUnlocked.value = null;
		}, 2400);
	}

	// What each power's "used" means. Checked from data the app already loads; the panel asks for the rest.
	function watchUsage() {
		const when = (source, id) => watch(source, (yes) => yes && markUsed(id), { immediate: true });
		when(() => useChatStore().sortedSessions.length > 0, "ask");
		when(() => usePagesStore().hasPages, "pages");
		when(() => useWorkflowStore().hasWorkflows, "agents");
		when(() => useTemplateStore().pinnedNames.length > 0, "templates");
	}

	/** Knowledge has no store; its page reports what it loaded. */
	function reportKnowledgeCount(count) {
		if (count > 0) markUsed("knowledge");
	}

	/** Opening the panel checks the powers not used yet, once each, at one item per call. */
	const checked = new Set();
	async function checkUnused() {
		const checks = {
			agents: async () => ((await api.workflows.list(null, 0, 1))?.workflows || []).length > 0,
			knowledge: async () => ((await api.documents.list({ limit: 1 }))?.documents || []).length > 0,
			pages: async () => {
				await usePagesStore().ensureLoaded();
				return usePagesStore().hasPages;
			},
			templates: async () => {
				await useTemplateStore().loadTemplates();
				return useTemplateStore().pinnedNames.length > 0;
			},
		};
		await Promise.all(
			powers.value
				.filter((p) => !isPowerUsed(p.id, state.value.used) && checks[p.id] && !checked.has(p.id))
				.map(async (p) => {
					checked.add(p.id);
					try {
						if (await checks[p.id]()) markUsed(p.id);
					} catch (err) {
						logger.warn(`Could not check ${p.id}:`, err);
					}
				})
		);
	}

	// ── Your FAC ────────────────────────────────────────────────────────
	const powers = computed(() => {
		const user = useUserStore();
		return availablePowers(user.capabilities, {
			workflowsEnabled: user.workflowsEnabled,
			memoryEnabled: user.memoryEnabled,
		});
	});
	const progress = computed(() => progressOf(powers.value, state.value.used));
	const showProgress = computed(() => started.value && switches.value.show_progress && powers.value.length > 0);

	function openPanel() {
		panelOpen.value = true;
		checkUnused();
	}

	function closePanel() {
		panelOpen.value = false;
	}

	/** "Try" in the panel: AR's route, else where that feature's own "Give it a try" goes. */
	function tryPower(id, router) {
		panelOpen.value = false;
		const power = powers.value.find((p) => p.id === id);
		if (power && power.tryRoute) return router.push(power.tryRoute);
		if (id === "ask") return router.push("/chat");
		const feature = featureById(id);
		if (feature) goTo(feature, router);
	}

	// ── Did you know ────────────────────────────────────────────────────
	const notifications = computed(() => useNotificationStore().notifications);
	const siteTips = () => {
		const user = useUserStore();
		return dailyTips({ workflowsEnabled: user.workflowsEnabled, memoryEnabled: user.memoryEnabled });
	};
	const isDismissed = (n) => useNotificationStore().isDismissed(n);

	const tip = ref(null);
	/** Home asks once per visit, so a tip never changes under the user's eyes. */
	function refreshTip({ dayOne = false, now = new Date() } = {}) {
		if (!started.value || !switches.value.show_tips) {
			tip.value = null;
			return;
		}
		const tips = liveTips(siteTips(), { used: state.value.used, dismissed: state.value.tips_dismissed });
		const picked = pickDailyTip({ tips, state: state.value, today: localDate(now), dayOne, order: TIP_ORDER });
		if (picked.state !== state.value) update({ tip: picked.state.tip });
		tip.value = picked.tip;
	}

	/** × : not today. */
	function hideTipToday() {
		tip.value = null;
		update({ tip_hidden_on: localDate() });
	}

	/** "Don't show this tip again": kept on the user's preferences, so it stays gone on every device. */
	function neverShowTip(id) {
		tip.value = null;
		addTo("tips_dismissed", id);
	}

	function showTip(n) {
		preview.value = tipContent(n);
	}

	// ── What's new ──────────────────────────────────────────────────────
	const waitingStory = computed(() => {
		if (!started.value || !switches.value.show_whats_new) return null;
		return unseenStory(notifications.value, { seen: state.value.stories_seen, isDismissed });
	});

	function openStory(id) {
		const n = id ? notifications.value.find((x) => x.id === id) : waitingStory.value;
		if (n) story.value = n;
	}

	/** Watched to the end or closed: seen, here and on AR. */
	function closeStory() {
		const n = story.value;
		story.value = null;
		if (!n) return;
		addTo("stories_seen", n.id);
		if (n.dismissible === true && !isDismissed(n)) useNotificationStore().dismiss(n.id);
	}

	// ── Show me pop-up (tips) ───────────────────────────────────────────
	function openPreview(id) {
		const feature = featureById(id);
		if (feature) preview.value = previewContent(feature);
	}

	function closePreview() {
		preview.value = null;
	}

	function goTo(feature, router) {
		markSeen(feature.id);
		const target = feature.tryIt;
		if (target.templates) {
			templatesRequested.value++;
			router.push("/chat");
		} else if (target.prompt) {
			router.push({ path: "/chat", query: { prompt: target.prompt() } });
		} else if (target.route) {
			router.push(target.route);
		}
	}

	/** The pop-up's main button: the tip's route when it has one, else the feature's own try. */
	function tryPreview(router) {
		const content = preview.value;
		preview.value = null;
		if (!content) return;
		if (content.kind === "tip") tip.value = null;
		const feature = content.feature && featureById(content.feature);
		if (content.primary && content.primary.route) {
			if (feature) markSeen(feature.id);
			router.push(content.primary.route);
		} else if (feature) {
			goTo(feature, router);
		}
	}

	// ── 3-stop tour ─────────────────────────────────────────────────────
	/** Auto-start once, for a first-time user who just finished onboarding. */
	function maybeStartCoach({ dayOne }) {
		if (coachRequested.value) return true;
		return started.value && dayOne && !state.value.coach_done;
	}

	/** Settings → Help → "Show me around" asks for the tour again. */
	function requestCoach() {
		coachRequested.value = true;
	}

	function setCoachOpen(open) {
		useTourStore().setCoachOpen(open);
	}

	function finishCoach() {
		useTourStore().setCoachOpen(false);
		coachRequested.value = false;
		update({ coach_done: true });
	}

	return {
		state,
		started,
		switches,
		features,
		powers,
		progress,
		showProgress,
		tip,
		waitingStory,
		story,
		panelOpen,
		justUnlocked,
		preview,
		coachOpen,
		coachRequested,
		templatesRequested,
		init,
		setSwitches,
		showDot,
		markSeen,
		markRoute,
		markUsed,
		reportKnowledgeCount,
		openPanel,
		closePanel,
		tryPower,
		refreshTip,
		hideTipToday,
		neverShowTip,
		showTip,
		openStory,
		closeStory,
		openPreview,
		closePreview,
		tryPreview,
		maybeStartCoach,
		requestCoach,
		setCoachOpen,
		finishCoach,
	};
});
