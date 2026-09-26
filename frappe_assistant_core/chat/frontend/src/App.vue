<template>
	<div
		ref="appRootRef"
		:class="{ dark: isDark }"
		:data-theme="effectiveTheme"
		class="app-root flex flex-col bg-ql-bg text-ql-text transition-colors duration-200"
	>
		<!-- Email verification overlay — owner returned from the verify link.
		     Sits above the normal router-view so the registration deep-link is
		     handled regardless of which route the SPA otherwise lands on. -->
		<div v-if="verifyToken" class="verification-overlay">
			<EmailVerificationPending
				mode="verifying"
				:verification-token="verifyToken"
				@verified="onVerified"
				@verify-failed="onVerifyFailed"
			/>
		</div>

		<!-- Show loading while checking auth -->
		<div v-else-if="isCheckingAuth" class="auth-loading">
			<FacoRobot size="md" static-idle float show-arms show-shadow />
			<p class="loading-text">Loading...</p>
		</div>

		<!-- Show app when authenticated -->
		<template v-else>
			<NotificationHost />
			<div class="app-route">
				<router-view />
			</div>
		</template>

		<!-- Global toast notifications (success/error/info from useToast()) -->
		<ToastContainer />

		<!-- Global tour modal — opens via tourStore.open() from anywhere -->
		<TourPlayer />
	</div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useVisualViewportFrame } from "@/composables/useVisualViewportFrame";
import { useThemeStore } from "@/stores/themeStore";
import { useUserStore } from "@/stores/userStore";
import { useTourStore } from "@/stores/tourStore";
import { useChatStore } from "@/stores/chatStore";
import { useApprovalAttention } from "@/composables/useApprovalAttention";
import { useCheckoutReturn } from "@/composables/useCheckoutReturn";
import { logger } from "@/utils/logger";
import { storeToRefs } from "pinia";
import FacoRobot from "@/components/common/FacoRobot.vue";
import EmailVerificationPending from "@/components/onboarding/EmailVerificationPending.vue";
import ToastContainer from "@/components/ui/ToastContainer.vue";
import TourPlayer from "@/components/onboarding/TourPlayer.vue";
import NotificationHost from "@/components/notifications/NotificationHost.vue";

const router = useRouter();
const themeStore = useThemeStore();
const userStore = useUserStore();
const tourStore = useTourStore();
const { isDark, effectiveTheme } = storeToRefs(themeStore);

// Flashes the tab title while an approval waits and the tab is hidden.
useApprovalAttention(useChatStore());

// A purchase returns to whichever page it started from, so the return from
// FAC Cloud's checkout page is handled here rather than on the billing page.
const checkoutReturn = useCheckoutReturn({ router, userStore });

const appRootRef = ref(null);
useVisualViewportFrame(appRootRef);

const isCheckingAuth = ref(true);
// Token was captured + URL stripped in main.js before vue-router booted.
// Read it once here; the global is single-use so a refresh doesn't replay.
const verifyToken = ref(window.__facoVerifyToken || null);
if (window.__facoVerifyToken) {
	delete window.__facoVerifyToken;
}

async function onVerified() {
	// Tenant is active. Refresh registration state so OnboardingScreen
	// disappears and ChatStagePicker advances to UserSetup / chat.
	verifyToken.value = null;
	await userStore.refreshRegistrationStatus();
}

function onVerifyFailed() {
	// Surface remains on the overlay's error card with its own retry button.
	// No-op here — keep the token so retries work.
}

onMounted(async () => {
	themeStore.initThemeWatcher();

	// Check authentication
	await userStore.init();

	// If user is Guest, redirect to login
	if (!userStore.user || userStore.user === "Guest") {
		// Redirect to Frappe login page with return URL
		const currentUrl = window.location.pathname + window.location.search;
		window.location.href = `/login?redirect-to=${encodeURIComponent(currentUrl)}`;
		return;
	}

	// The router beforeEach guard only fires on navigations; on a hard
	// deep-link the initial route resolves while registrationStatus is still
	// "checking", so it passes through. Re-check now that init() has the
	// authoritative status and redirect a non-member off any protected route.
	if (userStore.registrationStatus === "no_role" && router.currentRoute.value.path !== "/chat") {
		await router.replace("/chat");
	}

	isCheckingAuth.value = false;

	checkoutReturn.run().catch((err) => logger.error("Checkout return failed:", err));

	// Auto-play the reel for returning users on a new tour version.
	// First-time users hit the inline onboarding wizard instead.
	tourStore.init();
});
</script>

<style scoped>
/* Pin the shell to the visible viewport. Nested route roots must fill this
   box (`height: 100%`) instead of using 100vh — on phones 100vh is taller
   than the visual viewport, so the composer sat below the fold. */
.app-root {
	position: fixed;
	inset: 0;
	box-sizing: border-box;
	width: 100%;
	/* svh = visible area with browser chrome showing. dvh/vh are taller on
	   phones, which hid the composer toolbar (attach, voice) below the fold. */
	height: 100%;
	height: -webkit-fill-available;
	height: 100svh;
	max-height: 100svh;
	min-height: 0;
	overflow: hidden;
	padding-bottom: env(safe-area-inset-bottom, 0px);
}
.app-route {
	flex: 1;
	min-height: 0;
	overflow: hidden;
	display: flex;
	flex-direction: column;
}
.app-route > * {
	flex: 1;
	min-height: 0;
	height: 100%;
}

.auth-loading {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	height: 100%;
	gap: 1.5rem;
}

.loading-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
}

.verification-overlay {
	display: flex;
	align-items: center;
	justify-content: center;
	height: 100%;
	padding: 2rem;
}
</style>
