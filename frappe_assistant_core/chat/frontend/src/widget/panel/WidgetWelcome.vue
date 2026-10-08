<template>
	<div class="ww">
		<WelcomeHeader :greeting="greeting" :display-name="displayName" />
		<p v-if="contextLine" class="ww-context" :title="contextLine">{{ contextLine }}</p>
		<ContinueList
			v-if="resumeSessions.length"
			:sessions="resumeSessions"
			@open="(id) => $emit('open-session', id)"
		/>
		<SuggestionTiles
			v-if="!suggestionStore.suggestionsDisabled"
			:tiles="tiles"
			@pick="(text) => $emit('suggestion', text)"
		/>
	</div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from "vue";
import { storeToRefs } from "pinia";
import { useUserStore } from "@/stores/userStore";
import { useChatStore } from "@/stores/chatStore";
import { useSuggestionStore } from "@/stores/suggestionStore";
import { greetingForHour, displayNameFromUser } from "@/components/chat/welcomeGreeting";
import { selectWelcomeTiles } from "@/components/chat/welcome/welcomeRelevance";
import WelcomeHeader from "@/components/chat/welcome/WelcomeHeader.vue";
import ContinueList from "@/components/chat/welcome/ContinueList.vue";
import SuggestionTiles from "@/components/chat/welcome/SuggestionTiles.vue";
import { detectContext, contextDisplayText } from "../desk/pageContext.js";

defineEmits(["suggestion", "open-session"]);

const userStore = useUserStore();
const chatStore = useChatStore();
const suggestionStore = useSuggestionStore();
const { allSuggestions } = storeToRefs(suggestionStore);

const greeting = computed(() => greetingForHour(new Date().getHours()));
const displayName = computed(() => displayNameFromUser(userStore.user));

const resumeSessions = computed(() =>
	chatStore.sortedSessions.filter((s) => s.session_id !== chatStore.currentSessionId).slice(0, 2)
);
const tiles = computed(() =>
	selectWelcomeTiles({
		suggestions: allSuggestions.value,
		resumePreviews: resumeSessions.value.map((s) => s.preview || ""),
	})
);

const contextLine = ref("");
const update = () => (contextLine.value = contextDisplayText(detectContext()) || "");
onMounted(() => {
	update();
	window.frappe?.router?.on("change", update);
	if (!chatStore.sessions.length) chatStore.loadSessions();
	// The endpoint ranks templates by the page's type and doctype; nothing else from the page is sent.
	const { type, doctype } = detectContext() || {};
	suggestionStore.loadSuggestions(doctype ? { type, doctype } : { type });
});
onUnmounted(() => window.frappe?.router?.off?.("change", update));
</script>

<style scoped>
.ww {
	display: flex;
	flex-direction: column;
	gap: 16px;
	padding: 22px 18px 16px;
}
/* FAC Chat's masthead is sized for a page; its clamp() reads the browser viewport, not the panel. */
.ww :deep(.wh-greeting) {
	font-size: 26px;
}
.ww :deep(.wh-sub) {
	font-size: 14px;
}
/* The column's gap already spaces the rule. */
.ww :deep(.wh-rule) {
	margin-top: 0;
}
.ww-context {
	align-self: flex-start;
	max-width: 100%;
	margin: -4px 0 0;
	padding: 4px 10px;
	border-radius: 999px;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
	font-size: 12px;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}
.ww > * {
	animation: ww-surface 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
}
/* WelcomeHeader renders the masthead and its rule as two children. */
.ww > :nth-child(3) {
	animation-delay: 0.06s;
}
.ww > :nth-child(4) {
	animation-delay: 0.12s;
}
.ww > :nth-child(5) {
	animation-delay: 0.18s;
}
@keyframes ww-surface {
	from {
		opacity: 0;
		transform: translateY(6px);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}
@media (prefers-reduced-motion: reduce) {
	.ww > * {
		animation: none;
	}
}
</style>
