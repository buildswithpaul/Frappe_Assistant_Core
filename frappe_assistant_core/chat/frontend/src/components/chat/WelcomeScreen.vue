<template>
	<div class="welcome-screen">
		<div class="welcome-inner">
			<WelcomeHeader :greeting="greeting" :display-name="displayName" />

			<AttentionLine
				class="welcome-att"
				:attention="attention"
				@review="$emit('navigate', '/agents')"
				@dismiss="dismissAttention"
			/>

			<!-- The REAL InputArea renders here on the empty state (hero slot) -->
			<div class="welcome-composer-slot">
				<slot name="composer" />
			</div>

			<div
				class="welcome-lower"
				:class="{ 'no-continue': !resumeSessions.length, 'no-tiles': suggestionStore.suggestionsDisabled }"
			>
				<ContinueList
					v-if="resumeSessions.length"
					:sessions="resumeSessions"
					@open="(id) => $emit('open-session', id)"
				/>
				<SuggestionTiles
					v-if="!suggestionStore.suggestionsDisabled"
					:tiles="tiles"
					@pick="(d) => $emit('suggestion', d)"
				/>
			</div>

			<PackNudge
				v-if="showZeroPackBanner"
				:count="eligiblePackCount"
				@enable="$emit('navigate', '/settings/packs')"
				@dismiss="dismissBanner"
			/>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { storeToRefs } from "pinia";
import { useUserStore } from "@/stores/userStore";
import { useSuggestionStore } from "@/stores/suggestionStore";
import { usePacksStore } from "@/stores/packsStore";
import { useChatStore } from "@/stores/chatStore";
import { greetingForHour, displayNameFromUser } from "@/components/chat/welcomeGreeting";
import { selectWelcomeTiles } from "@/components/chat/welcome/welcomeRelevance";
import { useAttention } from "@/composables/useAttention";
import WelcomeHeader from "@/components/chat/welcome/WelcomeHeader.vue";
import AttentionLine from "@/components/chat/welcome/AttentionLine.vue";
import ContinueList from "@/components/chat/welcome/ContinueList.vue";
import SuggestionTiles from "@/components/chat/welcome/SuggestionTiles.vue";
import PackNudge from "@/components/chat/welcome/PackNudge.vue";

defineEmits(["suggestion", "navigate", "open-session"]);

const userStore = useUserStore();
const suggestionStore = useSuggestionStore();
const packsStore = usePacksStore();
const chatStore = useChatStore();
const { allSuggestions } = storeToRefs(suggestionStore);

const greeting = computed(() => greetingForHour(new Date().getHours()));
const displayName = computed(() => displayNameFromUser(userStore.user));

// Resume: top 2 sessions, already loaded at boot — zero new requests.
const resumeSessions = computed(() => chatStore.sortedSessions.slice(0, 2));

const tiles = computed(() =>
	selectWelcomeTiles({
		suggestions: allSuggestions.value,
		resumePreviews: resumeSessions.value.map((s) => s.preview || ""),
	})
);

// Attention line: capability-gated, post-paint, fail-silent (spec §5).
const { attention, loadAttention, dismiss: dismissAttention } = useAttention();

// Zero-pack nudge (demoted): admins only, dismissible, same storage key.
const bannerDismissed = ref(localStorage.getItem("faco.zero_pack_banner_dismissed") === "1");
const eligiblePackCount = computed(() => packsStore.items.filter((p) => p.eligible).length);
const enabledPackCount = computed(() => packsStore.items.filter((p) => p.enabled).length);
const showZeroPackBanner = computed(
	() =>
		userStore.isAdmin &&
		!bannerDismissed.value &&
		!packsStore.loading &&
		eligiblePackCount.value > 0 &&
		enabledPackCount.value === 0
);
function dismissBanner() {
	localStorage.setItem("faco.zero_pack_banner_dismissed", "1");
	bannerDismissed.value = true;
}

onMounted(() => {
	loadAttention();
	if (userStore.isAdmin && !packsStore.items.length && !packsStore.loading) {
		packsStore.load();
	}
});
</script>

<style scoped>
.welcome-screen {
	display: flex;
	justify-content: center;
	/* A homepage anchors its content in the optical upper third and lets the
	   canvas breathe below — dead-centering (plus a boxed card) reads as an
	   onboarding dialog, not a place you live in. */
	align-items: flex-start;
	min-height: 100%;
	overflow-y: auto;
	padding: clamp(48px, 13vh, 132px) 48px 56px;
	background: var(--ql-bg);
}
.welcome-inner {
	position: relative;
	width: 100%;
	/* Wider column fills the canvas and removes the ~240px side gutters that a
	   700px column left on a ~1180px canvas. */
	max-width: 840px;
	display: flex;
	flex-direction: column;
	gap: 18px;
}
.welcome-att { margin-top: 2px; }
.welcome-composer-slot { width: 100%; }
/* The docked composer carries large horizontal padding (gradient inset + edge
   breathing room). In the hero it must sit flush with the header rule and the
   lower cards, which span the full welcome column — so strip the composer's own
   horizontal padding here and let it fill the slot. */
.welcome-composer-slot :deep(.input-area-container) {
	padding-left: 0;
	padding-right: 0;
	padding-top: 0.25rem;
}
/* The composer is the hero of this page — the first blank line of the ledger.
   Give it real presence: a gold "start-tick" on the leading edge that reads as
   "begin writing here" (echoes the masthead rule's gold segment), a warmer
   resting lift, and the gold accent on focus. Scoped to the hero instance only;
   the docked composer keeps its calmer treatment. */
.welcome-composer-slot :deep(.input-box) {
	position: relative;
	box-shadow: 0 1px 2px rgba(43, 38, 28, 0.05), 0 6px 16px -10px rgba(43, 38, 28, 0.18);
	transition: border-color 0.18s ease, box-shadow 0.18s ease;
}
.welcome-composer-slot :deep(.input-box)::before {
	content: "";
	position: absolute;
	top: 12px;
	bottom: 12px;
	left: 0;
	width: 3px;
	border-radius: 0 2px 2px 0;
	background: var(--ql-gold);
	opacity: 0.9;
	transition: opacity 0.18s ease, top 0.18s ease, bottom 0.18s ease;
}
.welcome-composer-slot :deep(.input-box:focus-within) {
	border-color: var(--ql-gold);
	box-shadow:
		0 1px 2px rgba(43, 38, 28, 0.05),
		0 8px 22px -10px rgba(43, 38, 28, 0.22),
		inset 0 0 0 1px var(--ql-gold-soft);
}
.welcome-composer-slot :deep(.input-box:focus-within)::before {
	top: 8px;
	bottom: 8px;
	opacity: 1;
}
.welcome-lower {
	display: grid;
	/* minmax(0, …) lets the tracks shrink below their content's intrinsic
	   min-width so the inner ellipsis/line-clamp takes over — without it a
	   1fr track refuses to shrink past min-content and the grid overflows the
	   column. */
	grid-template-columns: minmax(0, 0.92fr) minmax(0, 1.08fr);
	gap: 20px;
	margin-top: 10px;
	min-width: 0;
}
.welcome-lower.no-continue,
.welcome-lower.no-tiles { grid-template-columns: minmax(0, 1fr); }

/* Authored entrance: contents surface in the reading order a person would
   follow — masthead, then the writing line, then the day's entries.
   Staggered, brief, and disabled for reduced-motion. */
.welcome-inner > * {
	animation: content-surface 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.welcome-inner > :nth-child(1) { animation-delay: 0.05s; }
.welcome-inner > :nth-child(2) { animation-delay: 0.12s; }
.welcome-inner > :nth-child(3) { animation-delay: 0.2s; }
.welcome-inner > :nth-child(4) { animation-delay: 0.28s; }
@keyframes content-surface {
	from { opacity: 0; transform: translateY(6px); }
	to { opacity: 1; transform: translateY(0); }
}

:global([data-theme="dark"]) .welcome-composer-slot :deep(.input-box) {
	box-shadow: 0 6px 18px -12px rgba(0, 0, 0, 0.6);
}

/* Tablet tab-mode (768–1023) still used the desktop 13vh top pad, which shoved
   the hero composer below the fold when the transcript could not scroll. */
@media (max-width: 1023px) {
	.welcome-screen { padding: 40px 32px 24px; }
}
@media (max-width: 719px) {
	.welcome-screen { padding: 32px 16px 24px; }
	.welcome-lower { grid-template-columns: 1fr; }
	/* Let the single-column cards shrink below their content's intrinsic width so
	   long titles wrap instead of forcing a horizontal page scroll. */
	.welcome-lower > * { min-width: 0; }
	.welcome-lower :deep(*) { overflow-wrap: anywhere; }
}
@media (prefers-reduced-motion: reduce) {
	.welcome-inner > * { animation: none; }
}
</style>
