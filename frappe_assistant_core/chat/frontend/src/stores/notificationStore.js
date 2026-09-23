import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { OUTAGE_TYPES } from "@/components/notifications/typeMeta";

const POLL_INTERVAL_MS = 120_000;

function loadSet(key) {
	try {
		const v = JSON.parse(localStorage.getItem(key) || "[]");
		return new Set(Array.isArray(v) ? v : []);
	} catch {
		return new Set();
	}
}

function saveSet(key, set) {
	localStorage.setItem(key, JSON.stringify([...set]));
}

export const useNotificationStore = defineStore("notifications", () => {
	const notifications = ref([]);
	const isLoading = ref(false);
	const currentUser = ref("");
	const seenIds = ref(new Set());
	const localDismissedIds = ref(new Set());
	let pollTimer = null;

	const seenKey = () => `fac_notif_seen:${currentUser.value}`;
	const dismissedKey = () => `fac_notif_dismissed:${currentUser.value}`;

	function isDismissed(n) {
		return Boolean(n.dismissed) || localDismissedIds.value.has(n.id);
	}

	const activeNotifications = computed(() => notifications.value.filter((n) => !isDismissed(n)));
	const outageNotifications = computed(() =>
		activeNotifications.value.filter((n) => OUTAGE_TYPES.has(n.type))
	);
	const bannerNotification = computed(
		() =>
			activeNotifications.value.find(
				(n) => n.priority === "high" && !OUTAGE_TYPES.has(n.type)
			) || null
	);
	const unreadCount = computed(
		() => activeNotifications.value.filter((n) => !seenIds.value.has(n.id)).length
	);

	function _setUser(user) {
		if (!user || user === currentUser.value) return;
		currentUser.value = user;
		seenIds.value = loadSet(seenKey());
		localDismissedIds.value = loadSet(dismissedKey());
	}

	function _prune() {
		const ids = new Set(notifications.value.map((n) => n.id));
		let changed = false;
		for (const s of [seenIds.value, localDismissedIds.value]) {
			for (const id of [...s]) {
				if (!ids.has(id)) {
					s.delete(id);
					changed = true;
				}
			}
		}
		if (changed && currentUser.value) {
			saveSet(seenKey(), seenIds.value);
			saveSet(dismissedKey(), localDismissedIds.value);
		}
	}

	async function refresh() {
		if (isLoading.value) return;
		isLoading.value = true;
		try {
			const result = await api.notifications.get();
			if (result && Array.isArray(result.notifications)) {
				_setUser(result.user);
				notifications.value = result.notifications;
				// A degraded response (AR unreachable: stale/truncated cron
				// fallback, or empty) is not AR's authoritative list — pruning
				// against it would delete locally seen/dismissed ids the
				// outage just happens not to mention, up to wiping both sets
				// outright on an empty fallback.
				if (!result.degraded) _prune();
			}
		} catch (err) {
			logger.error("Failed to load notifications:", err);
			// keep the previous list — a transient error must not hide an outage
		} finally {
			isLoading.value = false;
		}
	}

	function markAllSeen() {
		for (const n of activeNotifications.value) seenIds.value.add(n.id);
		if (currentUser.value) saveSet(seenKey(), seenIds.value);
	}

	async function dismiss(notificationId) {
		const n = notifications.value.find((x) => x.id === notificationId);
		if (n && n.dismissible !== true) return;
		localDismissedIds.value.add(notificationId);
		if (currentUser.value) saveSet(dismissedKey(), localDismissedIds.value);
		if (n) n.dismissed = true;
		try {
			await api.notifications.dismiss(notificationId);
		} catch (err) {
			logger.error("Failed to dismiss notification:", err);
			// local dismissal stands; server state reconciles on next poll
		}
	}

	function _onVisibility() {
		if (document.visibilityState === "visible") refresh();
	}

	function startPolling() {
		stopPolling();
		pollTimer = setInterval(refresh, POLL_INTERVAL_MS);
		document.addEventListener("visibilitychange", _onVisibility);
		refresh();
	}

	function stopPolling() {
		if (pollTimer) clearInterval(pollTimer);
		pollTimer = null;
		document.removeEventListener("visibilitychange", _onVisibility);
	}

	return {
		notifications,
		isLoading,
		isDismissed,
		activeNotifications,
		outageNotifications,
		bannerNotification,
		unreadCount,
		refresh,
		dismiss,
		markAllSeen,
		startPolling,
		stopPolling,
	};
});
