<template>
	<div v-if="state === 'checking'" class="wsg" role="status" aria-live="polite">
		<span class="wsg-spinner" aria-hidden="true"></span>
		<p class="wsg-hint">{{ t("Loading…") }}</p>
	</div>
	<div v-else-if="state === 'error'" class="wsg" role="status" aria-live="polite">
		<p>{{ t("FACO is unavailable right now. Try again later.") }}</p>
	</div>
	<div v-else class="wsg">
		<h2>{{ copy.title }}</h2>
		<p>{{ copy.subtitle }}</p>
		<div v-if="showButton" class="wsg-action">
			<button type="button" class="wsg-btn" @click="openFullAssistant">{{ copy.action }}</button>
			<p class="wsg-hint">{{ copy.hint }}</p>
		</div>
		<p v-else class="wsg-hint">{{ copy.noAdmin }}</p>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { t } from "./i18n.js";

const props = defineProps({
	status: { type: String, default: "checking" },
	isAdmin: { type: Boolean, default: false },
	userSetupComplete: { type: Boolean, default: false },
	privacyConsentComplete: { type: Boolean, default: false },
});

// Connecting the site is the only step that belongs to an admin. The other two
// belong to the person in front of us: this gate is reached only when can_use is
// true, and can_use IS the membership check, so they already hold a seat.
// "checking" is the userStore default until initialize_spa resolves; "error" is a failed
// access call. Neither says anything about registration, so neither may show its copy.
const state = computed(() => {
	if (props.status === "checking") return "checking";
	if (props.status === "error") return "error";
	if (props.status !== "ready") return "not_registered";
	if (!props.userSetupComplete) return "needs_user_auth";
	return "needs_consent";
});

const copy = computed(
	() =>
		({
			not_registered: {
				title: t("Welcome to FACO!"),
				subtitle: t("Your AI copilot for Frappe and ERPNext"),
				action: t("Get Started Free"),
				hint: t("Opens FACO Assistant to complete setup."),
				noAdmin: t("Please ask your administrator to enable FACO for this site."),
			},
			needs_user_auth: {
				title: t("Connect Your Account"),
				subtitle: t("Your site is connected. Complete setup to start chatting."),
				action: t("Complete Setup"),
				hint: t("Opens FACO Assistant to connect your account."),
			},
			needs_consent: {
				title: t("Almost There!"),
				subtitle: t("Complete a quick setup to start chatting."),
				action: t("Complete Setup"),
				hint: t("Takes less than a minute."),
			},
		})[state.value]
);

const showButton = computed(() => props.isAdmin || state.value !== "not_registered");

function openFullAssistant() {
	window.open("/copilot", "_blank");
}
</script>

<style scoped>
.wsg {
	flex: 1;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: 8px;
	padding: 32px 24px;
	text-align: center;
}
h2 {
	margin: 0;
	font-family: var(--ql-font-display);
	font-size: 20px;
	font-weight: 600;
	color: var(--ql-text);
}
p {
	margin: 0;
	color: var(--ql-text-secondary);
}
.wsg-action {
	margin-top: 16px;
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 8px;
}
.wsg-btn {
	padding: 8px 20px;
	border: none;
	border-radius: 8px;
	background: var(--ql-accent);
	color: #fff;
	font: inherit;
	font-weight: 500;
	cursor: pointer;
}
.wsg-btn:hover {
	background: var(--ql-accent-hover);
}
.wsg-spinner {
	width: 18px;
	height: 18px;
	border: 2px solid var(--ql-border, var(--ql-text-muted));
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: wsg-spin 0.8s linear infinite;
}
@keyframes wsg-spin {
	to {
		transform: rotate(360deg);
	}
}
@media (prefers-reduced-motion: reduce) {
	.wsg-spinner {
		animation: none;
	}
}
.wsg-hint {
	font-size: 12px;
	color: var(--ql-text-muted);
}
</style>
