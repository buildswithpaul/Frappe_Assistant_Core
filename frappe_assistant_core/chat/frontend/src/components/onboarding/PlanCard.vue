<template>
	<div class="plan-card" data-test="plan-card">
		<FacoRobot size="lg" mood="happy" float show-arms show-shadow extra-class="mb-4" />

		<p class="eyebrow">You're all set</p>
		<h1 class="title">{{ title }}</h1>
		<p class="subtitle">{{ subtitle }}</p>

		<div v-if="showQuota" class="quota-pill" data-test="plan-quota">
			<span class="quota-value">{{ quotaValue }}</span>
			<span class="quota-label">{{ quotaLabel }}</span>
		</div>

		<ul class="perks">
			<li v-for="perk in perks" :key="perk">{{ perk }}</li>
		</ul>

		<button type="button" class="continue-btn" data-test="plan-continue" @click="$emit('continue')">
			Continue
		</button>

		<button
			v-if="canSeePlans"
			type="button"
			class="plans-link"
			data-test="plan-see-plans"
			@click="$emit('see-plans')"
		>
			See plans
		</button>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useUserStore } from "@/stores/userStore";
import { useCreditScope } from "@/composables/useCreditScope";
import FacoRobot from "@/components/common/FacoRobot.vue";

defineEmits(["continue", "see-plans"]);

const userStore = useUserStore();
const canSeePlans = computed(() => userStore.isAdmin);

const scope = useCreditScope();

// The team pool is hydrated at boot but the personal cap lands on its own
// round trip. Holding the figure back until both settle keeps a capped member
// from watching the team pool flash up and then shrink to their own limit.
const ready = ref(false);

const plan = computed(() => userStore.quotaInfo?.plan || "");
const isFree = computed(() => plan.value.toLowerCase() === "free");

const title = computed(() =>
	plan.value ? `You're on the ${plan.value} plan` : "Your workspace is ready"
);

const subtitle = computed(() => {
	if (isFree.value) {
		return "No credit card required. Start chatting now — upgrade anytime from Settings.";
	}
	if (plan.value) {
		return "Your team's plan is active. Start chatting now — manage it from Settings.";
	}
	return "Start chatting now — your plan details are in Settings.";
});

const isUnlimited = computed(() => !scope.value.isPersonal && scope.value.total === -1);

const showQuota = computed(() => ready.value && (isUnlimited.value || scope.value.total > 0));

const quotaValue = computed(() =>
	isUnlimited.value ? "Unlimited" : scope.value.total.toLocaleString()
);

const quotaLabel = computed(() =>
	scope.value.isPersonal ? "credits / month · your limit" : "credits / month"
);

const perks = computed(() => [
	"Full chat with your site’s data and permissions",
	"Credits refresh every billing cycle",
	scope.value.isPersonal
		? "Your admin sets how much of the team pool you can use"
		: "Upgrade when your team needs more",
]);

// Onboarding must never block on billing: both loaders swallow their own
// errors, so an unreachable AR simply leaves the quota pill hidden.
onMounted(async () => {
	await Promise.all([
		userStore.quotaInfo ? Promise.resolve() : userStore.loadQuota(),
		userStore.myCreditStatus ? Promise.resolve() : userStore.loadMyCreditStatus(),
	]);
	ready.value = true;
});
</script>

<style scoped>
.plan-card {
	display: flex;
	flex-direction: column;
	align-items: center;
	text-align: center;
	max-width: 420px;
	width: 100%;
	margin: 0 auto;
	padding: 1.5rem 1.25rem;
}

.eyebrow {
	margin: 0 0 0.35rem;
	font-size: 0.75rem;
	font-weight: 600;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	color: var(--ql-accent);
}

.title {
	margin: 0 0 0.5rem;
	font-size: 1.5rem;
	font-weight: 700;
	color: var(--ql-text);
}

.subtitle {
	margin: 0 0 1.25rem;
	font-size: 0.9375rem;
	line-height: 1.5;
	color: var(--ql-text-muted);
}

.quota-pill {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.15rem;
	width: 100%;
	padding: 1rem 1.25rem;
	margin-bottom: 1.25rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
}

.quota-value {
	font-size: 1.75rem;
	font-weight: 700;
	color: var(--ql-text);
	font-variant-numeric: tabular-nums;
}

.quota-label {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}

.perks {
	list-style: none;
	margin: 0 0 1.5rem;
	padding: 0;
	width: 100%;
	text-align: left;
}

.perks li {
	position: relative;
	padding: 0.4rem 0 0.4rem 1.5rem;
	font-size: 0.875rem;
	line-height: 1.45;
	color: var(--ql-text);
}

.perks li::before {
	content: "";
	position: absolute;
	left: 0;
	top: 0.7rem;
	width: 0.5rem;
	height: 0.5rem;
	border-radius: 50%;
	background: var(--ql-accent);
}

.continue-btn {
	width: 100%;
	padding: 0.75rem 1.25rem;
	font-size: 0.9375rem;
	font-weight: 600;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: opacity 0.15s ease;
}

.continue-btn:hover {
	opacity: 0.92;
}

.plans-link {
	margin-top: 0.75rem;
	padding: 0.25rem;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	cursor: pointer;
	text-decoration: underline;
	text-underline-offset: 2px;
}

.plans-link:hover {
	color: var(--ql-text);
}
</style>
