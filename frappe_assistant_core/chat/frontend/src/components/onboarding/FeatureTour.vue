<template>
	<div class="feature-tour">
		<!-- Welcome celebration — shown briefly when user finishes onboarding. -->
		<WelcomeStage :visible="showWelcome" />

		<template v-if="!showWelcome">
			<OnboardingProgress v-if="phase !== 'reel'" :phase="progressPhase" />

			<FeatureReel v-if="phase === 'reel'" @complete="onReelComplete" />

			<PlanCard
				v-else-if="phase === 'plan'"
				@continue="onPlanContinue"
				@see-plans="onSeePlans"
			/>

			<div v-else-if="phase === 'setup'" class="tour-card">
				<button v-if="!isLastCard" type="button" class="skip-link" @click="goToLastCard">
					Skip
					<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M9 5l7 7-7 7"
						/>
					</svg>
				</button>

				<div class="carousel" ref="carouselRef">
					<div
						class="carousel-track"
						:style="{ transform: `translateX(-${currentIndex * 100}%)` }"
						@touchstart="onTouchStart"
						@touchmove="onTouchMove"
						@touchend="onTouchEnd"
					>
						<template v-for="(card, i) in cards" :key="card.id">
							<ProfileCard
								v-if="card.type === 'profile'"
								:is-active="i === currentIndex"
								:title="card.title"
								:description="card.description"
								v-model:job-title="profileJobTitle"
								v-model:department="profileDepartment"
								v-model:instructions="profileInstructions"
								:saving="profileSaving"
								:error="profileError"
							/>
							<PrivacyCard
								v-else
								:is-active="i === currentIndex"
								:title="card.title"
								:description="card.description"
								v-model:memory-consent="memoryConsent"
							/>
						</template>
					</div>
				</div>

				<div class="tour-nav">
					<button
						v-if="currentIndex > 0"
						type="button"
						class="nav-arrow"
						aria-label="Previous"
						@click="prev"
					>
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M15 19l-7-7 7-7"
							/>
						</svg>
					</button>
					<div v-else class="nav-spacer"></div>

					<div class="tour-dots">
						<button
							v-for="(card, i) in cards"
							:key="card.id"
							type="button"
							class="dot"
							:class="{ active: i === currentIndex }"
							:aria-label="`Go to slide ${i + 1}`"
							@click="goTo(i)"
						></button>
					</div>

					<button
						v-if="!isLastCard"
						type="button"
						class="nav-arrow"
						aria-label="Next"
						@click="next"
					>
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M9 5l7 7-7 7"
							/>
						</svg>
					</button>
					<div v-else class="nav-spacer"></div>
				</div>

				<button
					v-if="isLastCard"
					type="button"
					class="get-started-btn"
					:disabled="saving"
					@click="handleGetStarted"
				>
					<template v-if="saving">
						<span class="spinner"></span>
						Saving...
					</template>
					<template v-else> Get Started </template>
				</button>
			</div>
		</template>
	</div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { useUserStore } from "@/stores/userStore";
import WelcomeStage from "./WelcomeStage.vue";
import FeatureReel from "@/components/onboarding/FeatureReel.vue";
import PlanCard from "@/components/onboarding/PlanCard.vue";
import OnboardingProgress from "@/components/onboarding/OnboardingProgress.vue";
import ProfileCard from "./tour/ProfileCard.vue";
import PrivacyCard from "./tour/PrivacyCard.vue";

const emit = defineEmits(["complete"]);

const router = useRouter();
const userStore = useUserStore();

const currentIndex = ref(0);
const memoryConsent = ref(true);
const saving = ref(false);
const showWelcome = ref(false);
const WELCOME_DURATION_MS = 1800;

/** reel → plan → setup */
const phase = ref("reel");

const progressPhase = computed(() => {
	if (phase.value === "reel") return "features";
	if (phase.value === "plan") return "plan";
	return "setup";
});

function onReelComplete() {
	phase.value = "plan";
}

function onPlanContinue() {
	phase.value = "setup";
}

function onSeePlans() {
	// Admins can open billing after onboarding; stash intent and finish setup first.
	try {
		sessionStorage.setItem("faco_open_billing_after_onboarding", "1");
	} catch {
		/* private mode */
	}
	phase.value = "setup";
}

const profileJobTitle = ref("");
const profileDepartment = ref("");
const profileInstructions = ref("");
const profileSaving = ref(false);
const profileError = ref(null);

let touchStartX = 0;
let touchDelta = 0;

const cards = computed(() => [
	{
		id: "profile",
		type: "profile",
		title: "About You",
		description:
			"A few details help FACO respond in your context. Skip anytime — you can fill these in later from Settings.",
	},
	{
		id: "privacy",
		type: "privacy",
		title: "Your Privacy",
		description: "You're in control of your data.",
	},
]);

const isLastCard = computed(() => currentIndex.value === cards.value.length - 1);

onMounted(async () => {
	try {
		const config = await api.privacy.getConfig();
		if (config?.tenant?.default_memory_consent === "Opt-In") {
			memoryConsent.value = false;
		}
	} catch {
		// Leave default ON
	}
});

function next() {
	if (currentIndex.value < cards.value.length - 1) {
		currentIndex.value++;
	}
}

function prev() {
	if (currentIndex.value > 0) {
		currentIndex.value--;
	}
}

function goTo(i) {
	currentIndex.value = i;
}

function goToLastCard() {
	currentIndex.value = cards.value.length - 1;
}

function onTouchStart(e) {
	touchStartX = e.touches[0].clientX;
	touchDelta = 0;
}

function onTouchMove(e) {
	touchDelta = e.touches[0].clientX - touchStartX;
}

function onTouchEnd() {
	if (Math.abs(touchDelta) > 50) {
		if (touchDelta < 0) next();
		else prev();
	}
	touchDelta = 0;
}

async function saveProfileIfFilled() {
	const fields = {};
	if (profileJobTitle.value.trim()) fields.job_title = profileJobTitle.value.trim();
	if (profileDepartment.value.trim()) fields.department = profileDepartment.value.trim();
	if (profileInstructions.value.trim())
		fields.custom_instructions = profileInstructions.value.trim();
	if (Object.keys(fields).length === 0) return;

	profileSaving.value = true;
	profileError.value = null;
	try {
		await api.profile.update(fields);
	} catch (err) {
		logger.error("Failed to save profile during onboarding:", err);
	} finally {
		profileSaving.value = false;
	}
}

async function handleGetStarted() {
	saving.value = true;
	let consentSaved = false;
	try {
		await saveProfileIfFilled();
		await api.privacy.saveInitialConsent(memoryConsent.value);
		consentSaved = true;
	} catch (err) {
		logger.error("Failed to save consent:", err);
	} finally {
		saving.value = false;
	}
	showWelcome.value = true;
	setTimeout(() => {
		const openBilling = (() => {
			try {
				return sessionStorage.getItem("faco_open_billing_after_onboarding") === "1";
			} catch {
				return false;
			}
		})();
		if (openBilling) {
			try {
				sessionStorage.removeItem("faco_open_billing_after_onboarding");
			} catch {
				/* ignore */
			}
		}
		emit("complete", {
			memoryConsent: memoryConsent.value,
			consentSaved,
			seedPrompt: "What can you help me with on this site?",
			openBilling,
		});
		if (openBilling) {
			router.push("/settings/billing");
		}
	}, WELCOME_DURATION_MS);
}
</script>

<style scoped>
.feature-tour {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	min-height: 100%;
	padding: 2rem 1.25rem;
}

.tour-card {
	position: relative;
	max-width: 480px;
	width: 100%;
	background: var(--ql-surface);
	border-radius: 1rem;
	padding: 2rem 1.5rem 1.5rem;
	box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
	overflow: hidden;
}

.skip-link {
	position: absolute;
	top: 1rem;
	right: 1rem;
	display: flex;
	align-items: center;
	gap: 0.25rem;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	cursor: pointer;
	z-index: 2;
	transition: color 0.15s;
}

.skip-link:hover {
	color: var(--ql-text);
}

.carousel {
	overflow: hidden;
}

.carousel-track {
	display: flex;
	transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.tour-nav {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-top: 1.25rem;
	padding: 0 0.5rem;
}

.nav-arrow {
	width: 36px;
	height: 36px;
	display: flex;
	align-items: center;
	justify-content: center;
	border-radius: 50%;
	border: 1px solid var(--ql-border);
	background: none;
	color: var(--ql-text);
	cursor: pointer;
	transition: all 0.15s;
}

.nav-arrow:hover {
	background: var(--ql-bg);
	border-color: var(--ql-accent);
	color: var(--ql-accent);
}

.nav-spacer {
	width: 36px;
}

.tour-dots {
	display: flex;
	gap: 0.5rem;
}

.dot {
	width: 8px;
	height: 8px;
	border-radius: 50%;
	border: none;
	background: var(--ql-border);
	cursor: pointer;
	padding: 0;
	transition: all 0.2s ease;
}

.dot.active {
	background: var(--ql-accent);
	width: 24px;
	border-radius: 4px;
}

.get-started-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	width: 100%;
	margin-top: 1rem;
	padding: 0.75rem;
	font-size: 0.9375rem;
	font-weight: 500;
	color: white;
	background-color: var(--ql-accent);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.get-started-btn:hover:not(:disabled) {
	opacity: 0.9;
}

.get-started-btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}

.spinner {
	display: inline-block;
	width: 14px;
	height: 14px;
	border: 2px solid rgba(255, 255, 255, 0.3);
	border-top-color: white;
	border-radius: 50%;
	animation: spin 0.6s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}
</style>
