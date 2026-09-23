<template>
	<!-- Onboarding for unregistered FACO (site not registered) -->
	<OnboardingScreen
		v-if="registrationStatus === 'not_registered'"
		:is-admin="isAdmin"
		@registered="$emit('registration-complete')"
	/>

	<!-- Access Denied (user not added by admin, or missing role) -->
	<AccessDeniedScreen
		v-else-if="
			registrationStatus === 'no_role' ||
			(registrationStatus === 'ready' && needsUserSetup && userNotRegistered)
		"
	/>

	<!-- AR is refusing gated features (chat AND models) until the tenant
	     re-accepts terms. Sits after the access checks so a non-member still
	     gets the more actionable "ask to be added" message, and before user
	     setup because no amount of connecting fixes a tenant-level block. -->
	<TermsGate v-else-if="termsAcceptanceRequired" />

	<!-- User Setup Screen (site registered, but user not connected) -->
	<UserSetupScreen
		v-else-if="registrationStatus === 'ready' && needsUserSetup"
		@connected="$emit('user-connected')"
	/>

	<!-- Feature Tour (after user setup, before first chat) -->
	<FeatureTour
		v-else-if="
			registrationStatus === 'ready' && isUserSetupComplete && !privacyConsentComplete
		"
		@complete="$emit('feature-tour-complete', $event)"
	/>

	<!-- Welcome screen for new chats -->
	<WelcomeScreen
		v-else-if="
			messages.length === 0 &&
			!isLoading &&
			registrationStatus === 'ready' &&
			isUserSetupComplete
		"
		@suggestion="(s) => $emit('suggestion', s)"
		@navigate="(r) => $emit('navigate', r)"
		@open-session="(id) => $emit('open-session', id)"
	>
		<template #composer>
			<slot name="composer" />
		</template>
	</WelcomeScreen>

	<!-- Chat interface -->
	<ChatInterface
		v-else-if="registrationStatus === 'ready' && isUserSetupComplete"
		:messages="messages"
		:is-streaming="isStreaming"
		@toggle-block="(mi, bi) => $emit('toggle-block', mi, bi)"
		@approve="(blockId, responses) => $emit('approve', blockId, responses)"
		@reject="(blockId, responses) => $emit('reject', blockId, responses)"
		@continue="(messageId) => $emit('continue', messageId)"
		@pin="(messageId) => $emit('pin', messageId)"
		@unqueue="(id) => $emit('unqueue', id)"
	/>

	<!-- Loading state while checking registration -->
	<ChatLoadingState v-else-if="registrationStatus === 'checking'" />
</template>

<script setup>
import { defineAsyncComponent } from "vue";
import ChatInterface from "@/components/chat/ChatInterface.vue";
import ChatLoadingState from "@/components/chat/ChatLoadingState.vue";

// Onboarding screens are shown at most once per user — lazy so returning
// users (the common case) don't pay the bundle cost.
const OnboardingScreen = defineAsyncComponent(
	() => import("@/components/onboarding/OnboardingScreen.vue"),
);
const UserSetupScreen = defineAsyncComponent(
	() => import("@/components/onboarding/UserSetupScreen.vue"),
);
const FeatureTour = defineAsyncComponent(
	() => import("@/components/onboarding/FeatureTour.vue"),
);
const AccessDeniedScreen = defineAsyncComponent(
	() => import("@/components/onboarding/AccessDeniedScreen.vue"),
);
const TermsGate = defineAsyncComponent(() => import("@/components/onboarding/TermsGate.vue"));
const WelcomeScreen = defineAsyncComponent(() => import("@/components/chat/WelcomeScreen.vue"));

defineProps({
	registrationStatus: { type: String, required: true },
	isAdmin: { type: Boolean, default: false },
	needsUserSetup: { type: Boolean, default: false },
	isUserSetupComplete: { type: Boolean, default: false },
	privacyConsentComplete: { type: Boolean, default: false },
	userNotRegistered: { type: Boolean, default: false },
	termsAcceptanceRequired: { type: Boolean, default: false },
	messages: { type: Array, default: () => [] },
	isLoading: { type: Boolean, default: false },
	isStreaming: { type: Boolean, default: false },
});

defineEmits([
	"registration-complete",
	"user-connected",
	"feature-tour-complete",
	"suggestion",
	"navigate",
	"open-session",
	"toggle-block",
	"approve",
	"reject",
	"continue",
	"pin",
	"unqueue",
]);
</script>
