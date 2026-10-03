import { defineStore } from "pinia";
import { ref } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { safeActionUrl } from "@/components/notifications/typeMeta";
import { useNotificationStore } from "@/stores/notificationStore";
import { useUserStore } from "@/stores/userStore";
import { useTourStore } from "@/stores/tourStore";
import {
	DAILY_KEY,
	QUOTA_KEY,
	announcementContent,
	cycleStart,
	localDate,
	pickAnnouncement,
	quotaContent,
	quotaThreshold,
	storage,
} from "@/components/spotlight/spotlightRules";

export const useSpotlightStore = defineStore("spotlight", () => {
	const current = ref(null);
	let shownThisLoad = false;
	let blockedShownThisLoad = false;
	let quotaStatus = null;
	let quotaState = "idle"; // idle | pending | done

	async function fetchQuota() {
		try {
			const status = await api.billing.getQuotaStatus();
			return status && status.success !== false ? status : null;
		} catch (err) {
			logger.error("Spotlight quota fetch failed:", err);
			return null;
		}
	}

	async function evaluate() {
		const user = useUserStore();
		if (shownThisLoad || current.value || useTourStore().isOpen || user.registrationStatus !== "ready") return;
		const who = user.user;

		if (user.isAdmin && quotaState === "pending") return; // the in-flight check decides first
		if (user.isAdmin && quotaState === "idle") {
			quotaState = "pending";
			const status = await fetchQuota();
			quotaState = "done";
			if (shownThisLoad || current.value) return;
			quotaStatus = status;
			const threshold = quotaThreshold(quotaStatus);
			if (threshold && !storage.get(QUOTA_KEY(who, cycleStart(quotaStatus), threshold))) {
				current.value = quotaContent(quotaStatus);
				shownThisLoad = true;
				return;
			}
		}

		const announcement = pickAnnouncement(useNotificationStore().notifications);
		if (announcement && storage.get(DAILY_KEY(who)) !== localDate()) {
			current.value = announcementContent(announcement);
			storage.set(DAILY_KEY(who), localDate());
			shownThisLoad = true;
		}
	}

	async function onQuotaExhausted() {
		if (!useUserStore().isAdmin || blockedShownThisLoad) return;
		blockedShownThisLoad = true;
		quotaStatus = { ...((await fetchQuota()) || {}), credits_exhausted: true };
		current.value = quotaContent(quotaStatus);
		shownThisLoad = true;
	}

	function dismiss() {
		const content = current.value;
		if (!content) return;
		if (content.kind === "quota") {
			storage.set(QUOTA_KEY(useUserStore().user, cycleStart(quotaStatus), content.threshold), "1");
		} else {
			useNotificationStore().dismiss(content.id);
		}
		current.value = null;
	}

	function go(target, router) {
		if (!target) return;
		if (target.route) {
			router.push(target.route);
		} else if (target.url) {
			const safe = safeActionUrl(target.url);
			if (safe) window.open(safe, "_blank", "noopener");
		}
	}

	function primary(router) {
		const target = current.value?.primary;
		dismiss();
		go(target, router);
	}

	function secondary(router) {
		const target = current.value?.secondary;
		dismiss();
		go(target, router);
	}

	return { current, evaluate, onQuotaExhausted, dismiss, primary, secondary };
});
