<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from "vue";
import { useUserStore } from "@/stores/userStore";
import FacoRobot from "@/components/common/FacoRobot.vue";
import IntroMockup from "@/components/onboarding/scenes/IntroMockup.vue";
import KnowledgeMockup from "@/components/onboarding/scenes/KnowledgeMockup.vue";
import VoiceMockup from "@/components/onboarding/scenes/VoiceMockup.vue";
import PrivacyMockup from "@/components/onboarding/scenes/PrivacyMockup.vue";
import OutroMockup from "@/components/onboarding/scenes/OutroMockup.vue";

// Minimum scene count required to play the reel. Defaults to 2 — if capability
// gating leaves fewer scenes than this, we emit complete immediately and skip
// the reel. Tests pass a high value to force the bail-out branch.
const props = defineProps({
	minScenesRequired: { type: Number, default: 2 },
});
const emit = defineEmits(["complete"]);

const userStore = useUserStore();

const MOCKUPS = {
	intro: IntroMockup,
	knowledge: KnowledgeMockup,
	voice: VoiceMockup,
	privacy: PrivacyMockup,
	outro: OutroMockup,
};

// Keep the reel short (~25s). Voice stays — native-language ask is a hook.
// Team / Workflows stay out (in-product tips). `capability` gates optional scenes.
const ALL_SCENES = [
	{
		id: "intro",
		icon: "💬",
		title: "Meet FACO",
		subtitle: "Your team's AI, with memory.",
		mockup: "intro",
		durationMs: 4500,
		capability: null,
	},
	{
		id: "knowledge",
		icon: "📚",
		title: "Knowledge that grows with you",
		subtitle: "Drop a doc. Ask anything. FACO remembers.",
		mockup: "knowledge",
		durationMs: 5500,
		capability: "memoryEnabled",
	},
	{
		id: "voice",
		icon: "🎙️",
		title: "Speak your language",
		subtitle:
			"Tap the mic and talk — hindi, tamil, kannada, español, العربية. Set your language in Settings → Profile.",
		mockup: "voice",
		durationMs: 5500,
		capability: null,
	},
	{
		id: "privacy",
		icon: "🔒",
		title: "Your conversations stay yours",
		subtitle:
			"Chats live on your machine — never retained on our servers. Zero-retention by design.",
		mockup: "privacy",
		durationMs: 5000,
		capability: null,
	},
	{
		id: "outro",
		icon: "🚀",
		title: "Let's go",
		subtitle: "A quick look at your Free plan, then you're in.",
		mockup: "outro",
		durationMs: 4000,
		capability: null,
	},
];

const scenes = computed(() =>
	ALL_SCENES.filter((s) => s.capability === null || userStore[s.capability] === true)
);

const reducedMotion = ref(
	typeof window !== "undefined"
		? window.matchMedia("(prefers-reduced-motion: reduce)").matches
		: false
);
const currentIndex = ref(0);
const paused = ref(false);
let timerId = null;
let timerStartedAt = 0;
let remainingMs = 0;

const currentScene = computed(() => scenes.value[currentIndex.value] || null);
const isLast = computed(() => currentIndex.value >= scenes.value.length - 1);

function scheduleAdvance(ms) {
	clearTimeout(timerId);
	timerStartedAt = Date.now();
	remainingMs = ms;
	timerId = setTimeout(() => {
		if (isLast.value) {
			finish();
		} else {
			currentIndex.value++;
			startCurrentScene();
		}
	}, ms);
}

function startCurrentScene() {
	if (!currentScene.value) return;
	scheduleAdvance(currentScene.value.durationMs);
}

function pause() {
	if (paused.value) return;
	paused.value = true;
	clearTimeout(timerId);
	remainingMs = Math.max(0, remainingMs - (Date.now() - timerStartedAt));
}

function resume() {
	if (!paused.value) return;
	paused.value = false;
	scheduleAdvance(remainingMs > 0 ? remainingMs : (currentScene.value?.durationMs ?? 0));
}

function togglePause() {
	paused.value ? resume() : pause();
}

function next() {
	if (isLast.value) finish();
	else {
		currentIndex.value++;
		startCurrentScene();
	}
}

function finish() {
	clearTimeout(timerId);
	emit("complete");
}

function onKeydown(e) {
	if (reducedMotion.value) return;
	if (e.code === "Space") { e.preventDefault(); togglePause(); }
	else if (e.code === "ArrowRight") { e.preventDefault(); next(); }
	else if (e.code === "Escape") { e.preventDefault(); finish(); }
}

onMounted(() => {
	// Bail early if too few scenes (either real gating or test override).
	if (scenes.value.length < props.minScenesRequired) {
		finish();
		return;
	}

	if (!reducedMotion.value) {
		window.addEventListener("keydown", onKeydown);
		startCurrentScene();
	}
});

onBeforeUnmount(() => {
	clearTimeout(timerId);
	window.removeEventListener("keydown", onKeydown);
});
</script>

<template>
	<!-- Reduced-motion fallback: static stack of every scene + one Continue button. -->
	<div v-if="reducedMotion" data-static-stack class="reel reel-static">
		<div v-for="s in scenes" :key="s.id" class="scene scene-static">
			<FacoRobot v-if="s.id === 'intro' || s.id === 'outro'" size="md" static-idle show-arms />
			<div v-else class="icon" aria-hidden="true">{{ s.icon }}</div>
			<h3>{{ s.title }}</h3>
			<p class="subtitle">{{ s.subtitle }}</p>
			<component :is="MOCKUPS[s.mockup]" />
		</div>
		<button class="primary" @click="finish">Continue</button>
	</div>

	<!-- Animated reel — full-screen cinematic -->
	<div v-else class="reel" @click="next">
		<!-- Layered ambient backdrop: deep gradient + drifting color blobs + vignette -->
		<div class="bg-base" aria-hidden="true"></div>
		<div class="bg-blob bg-blob-a" aria-hidden="true"></div>
		<div class="bg-blob bg-blob-b" aria-hidden="true"></div>
		<div class="bg-vignette" aria-hidden="true"></div>

		<button data-skip class="skip" aria-label="Skip intro" @click.stop="finish">Skip intro →</button>

		<Transition name="cinematic" mode="out-in">
			<div v-if="currentScene" :key="currentScene.id" class="scene">
				<!-- Intro + outro use the actual FACO robot for warmth.
				     Other scenes use a glowing medallion with the scene's emoji. -->
				<div v-if="currentScene.id === 'intro' || currentScene.id === 'outro'" class="hero-robot" aria-hidden="true">
					<FacoRobot
						size="lg"
						:mood="currentScene.id === 'outro' ? 'happy' : 'idle'"
						float
						show-arms
						show-shadow
					/>
				</div>
				<div v-else class="hero-icon" aria-hidden="true">
					<div class="hero-ring hero-ring-outer"></div>
					<div class="hero-ring hero-ring-inner"></div>
					<span class="hero-icon-glyph">{{ currentScene.icon }}</span>
				</div>
				<h3>{{ currentScene.title }}</h3>
				<p class="subtitle">{{ currentScene.subtitle }}</p>
				<div class="mockup-frame">
					<component :is="MOCKUPS[currentScene.mockup]" />
				</div>
			</div>
		</Transition>

		<div class="timeline">
			<span
				v-for="(s, i) in scenes"
				:key="s.id"
				:data-scene-pill="true"
				:data-scene-id="s.id"
				class="pill"
				:class="{ 'pill-active': i === currentIndex, 'pill-past': i < currentIndex }"
			></span>
		</div>

		<div class="controls">
			<button data-pause class="ghost" :aria-label="paused ? 'Resume' : 'Pause'" @click.stop="togglePause">
				{{ paused ? "▶ Resume" : "⏸ Pause" }}
			</button>
			<span class="dot">·</span>
			<button class="ghost ghost-primary" :class="{ 'ghost-commit': isLast }" @click.stop="next">{{ isLast ? "Let's go →" : "Continue →" }}</button>
		</div>
	</div>
</template>

<style scoped>
/* ----------------- Full-screen cinematic stage ----------------- */
.reel {
	position: fixed;
	inset: 0;
	z-index: 50;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 64px 32px;
	cursor: pointer;
	overflow: hidden;
	isolation: isolate;
	color: var(--ql-text);
	/* Warm paper base — covers the underlying app before the gradient + washes paint. */
	background: var(--ql-bg);
}

/* Base layer — soft paper gradient (surface → bg) that anchors the stage. */
.bg-base {
	position: absolute;
	inset: 0;
	z-index: -3;
	background: radial-gradient(ellipse at 50% 0%, var(--ql-surface) 0%, var(--ql-bg) 70%);
}

/* Two faint teal washes drift on the paper — warmth, not a galaxy. */
.bg-blob {
	position: absolute;
	z-index: -2;
	border-radius: 50%;
	filter: blur(130px);
	opacity: 0.4;
	pointer-events: none;
	will-change: transform;
	background: radial-gradient(circle, var(--ql-accent-soft), transparent 70%);
}
.bg-blob-a {
	width: 620px;
	height: 620px;
	left: -160px;
	top: -120px;
	animation: drift-a 20s ease-in-out infinite alternate;
}
.bg-blob-b {
	width: 540px;
	height: 540px;
	right: -120px;
	bottom: -140px;
	animation: drift-b 24s ease-in-out infinite alternate;
}
/* .bg-blob-c removed — two washes are enough on paper. */

/* Subtle vignette to focus the eye to center. */
.bg-vignette {
	position: absolute;
	inset: 0;
	z-index: -1;
	background: radial-gradient(ellipse 80% 60% at 50% 50%, transparent 0%, var(--ql-bg) 92%);
	pointer-events: none;
}

/* ----------------- Skip / counter / controls (top + bottom rails) ----------------- */
.skip {
	position: absolute;
	top: 28px;
	right: 32px;
	z-index: 2;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	color: var(--ql-text-muted);
	font-size: 13px;
	font-weight: 500;
	cursor: pointer;
	padding: 8px 14px;
	border-radius: 999px;
	transition: background 180ms ease, color 180ms ease, transform 180ms ease, border-color 180ms ease;
}
.skip:hover {
	background: var(--ql-subtle);
	border-color: var(--ql-border-hover);
	color: var(--ql-text);
	transform: translateY(-1px);
}

/* ----------------- Scene block — large, center-stage ----------------- */
.scene {
	text-align: center;
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 20px;
	width: min(720px, 100%);
}

/* Hero icon — glowing orb with rotating rings.
   The hero stops being "an emoji" and becomes the establishing shot. */
.hero-icon {
	position: relative;
	width: 132px;
	height: 132px;
	display: flex;
	align-items: center;
	justify-content: center;
	margin-bottom: 8px;
}
.hero-icon::before {
	content: "";
	position: absolute;
	inset: 16px;
	border-radius: 50%;
	background: radial-gradient(circle at 35% 30%, var(--ql-surface), var(--ql-accent-soft) 60%, transparent 85%);
	border: 1px solid var(--ql-border);
	box-shadow:
		inset 0 1px 1px rgba(255, 255, 255, 0.4),
		0 0 50px var(--ql-accent-soft),
		0 18px 40px -18px rgba(0, 0, 0, 0.25);
}
.hero-ring {
	position: absolute;
	border-radius: 50%;
	border: 1px dashed var(--ql-accent);
	opacity: 0.45;
	pointer-events: none;
}
.hero-ring-outer {
	inset: 0;
	animation: spin-cw 22s linear infinite;
}
.hero-ring-inner {
	inset: 8px;
	border-style: solid;
	border-color: var(--ql-accent-soft);
	opacity: 0.6;
	animation: spin-ccw 30s linear infinite;
}
.hero-icon-glyph {
	position: relative;
	font-size: 60px;
	line-height: 1;
	z-index: 1;
	filter: drop-shadow(0 4px 14px var(--ql-accent-soft));
}

/* FACO robot lands in intro + outro — center him with a soft glow. */
.hero-robot {
	margin-bottom: 16px;
	filter: drop-shadow(0 8px 26px var(--ql-accent-soft));
}

.scene .icon { font-size: 48px; } /* static-stack fallback */
.scene h3 {
	font-family: var(--ql-font-serif);
	font-size: clamp(34px, 5vw, 52px);
	font-weight: 600;
	margin: 0;
	letter-spacing: -0.02em;
	line-height: 1.08;
	color: var(--ql-text);
}
.scene .subtitle {
	color: var(--ql-text-secondary);
	font-family: var(--ql-font-sans);
	margin: 0;
	font-size: clamp(15px, 1.4vw, 18px);
	max-width: 540px;
	line-height: 1.55;
}

/* Mockup tray — paper card so it reads as a window into the product. */
.mockup-frame {
	width: 100%;
	max-width: 480px;
	padding: 24px;
	margin-top: 12px;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-lg);
	display: flex;
	justify-content: center;
	box-shadow: 0 1px 0 rgba(255, 255, 255, 0.6) inset, 0 20px 44px -20px rgba(0, 0, 0, 0.25);
}

/* ----------------- Timeline + bottom controls ----------------- */
.timeline {
	display: flex;
	gap: 8px;
	margin-top: 44px;
}
.pill {
	width: 28px;
	height: 3px;
	background: var(--ql-border);
	border-radius: 2px;
	transition: background 220ms ease, width 280ms ease, box-shadow 220ms ease;
}
.pill-past {
	background: var(--ql-accent-soft);
}
.pill-active {
	background: var(--ql-accent);
	width: 44px;
	box-shadow: 0 0 10px var(--ql-accent-soft);
}

.controls {
	margin-top: 20px;
	display: flex;
	gap: 12px;
	align-items: center;
	font-size: 13px;
}
.ghost {
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	font-size: 13px;
	font-weight: 500;
	cursor: pointer;
	padding: 6px 12px;
	border-radius: 999px;
	transition: color 150ms ease, background 150ms ease;
}
.ghost:hover {
	color: var(--ql-text);
	background: var(--ql-subtle);
}
.ghost-primary { color: var(--ql-accent); }
.ghost-primary:hover { color: var(--ql-accent-hover); background: var(--ql-accent-soft); }
/* The outro is a commit moment — the one sanctioned gold use in the reel. */
.ghost-commit { color: var(--ql-gold); }
.ghost-commit:hover { color: var(--ql-gold); background: var(--ql-gold-soft); }
.dot { color: var(--ql-text-muted); }

/* ----------------- Static fallback (reduced-motion users) ----------------- */
.reel-static {
	position: static;
	color: var(--ql-text);
	background: var(--ql-bg);
	padding: 32px 24px;
	gap: 32px;
	cursor: default;
	min-height: 100vh;
	overflow: visible;
	isolation: auto;
}
.scene-static { padding: 16px; border-bottom: 1px solid var(--ql-border); }
.scene-static:last-of-type { border-bottom: none; }
.primary {
	margin-top: 8px;
	padding: 10px 20px;
	background: var(--ql-accent);
	color: #fff;
	border: none;
	border-radius: 8px;
	font-size: 14px;
	font-weight: 600;
	cursor: pointer;
}
.primary:hover { background: var(--ql-accent-hover); }

/* ----------------- Scene transition — horizontal "cut" like a teaser ----------------- */
.cinematic-enter-active, .cinematic-leave-active {
	transition: opacity 600ms cubic-bezier(0.22, 1, 0.36, 1), transform 600ms cubic-bezier(0.22, 1, 0.36, 1);
}
.cinematic-enter-from { opacity: 0; transform: translateX(40px); }
.cinematic-leave-to   { opacity: 0; transform: translateX(-40px); }

/* ----------------- Keyframes ----------------- */
@keyframes drift-a {
	0%   { transform: translate(0, 0) scale(1); }
	100% { transform: translate(80px, 60px) scale(1.1); }
}
@keyframes drift-b {
	0%   { transform: translate(0, 0) scale(1); }
	100% { transform: translate(-100px, -80px) scale(1.15); }
}
@keyframes spin-cw  { from { transform: rotate(0deg); }   to { transform: rotate(360deg); } }
@keyframes spin-ccw { from { transform: rotate(360deg); } to { transform: rotate(0deg);   } }

@media (prefers-reduced-motion: reduce) {
	.bg-blob, .hero-ring { animation: none; }
}
</style>
