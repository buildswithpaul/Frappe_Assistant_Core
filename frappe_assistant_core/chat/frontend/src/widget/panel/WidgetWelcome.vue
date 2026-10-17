<template>
	<div class="ww">
		<HomeHeader
			:greeting-line="greetingLine"
			:display-name="displayName"
			:lens-label="lensLabel || ''"
			:company="company || ''"
			:first-run="dayOne"
		/>
		<PageAsks
			v-if="filledAsks.length"
			:doctype="pageContext.doctype"
			:name="savedName"
			:asks="filledAsks"
			@pick="(text) => $emit('suggestion', text)"
		/>
		<NeedsYou
			:items="items"
			:loaded="loaded"
			:failed="failed"
			:empty-text="dayOne ? __('Approvals, assignments and overdue items for you will appear here.') : ''"
			variant="list"
			@ask="(prompt) => $emit('suggestion', prompt)"
			@navigate="openInChat"
			@dismiss="dismiss"
		/>
		<template v-if="!suggestionStore.suggestionsDisabled">
			<FirstRunStarters v-if="dayOne && !isForm" :tiles="firstRunTiles" @pick="(d) => $emit('suggestion', d)" />
			<template v-else-if="!dayOne">
				<ContinueList
					v-if="resumeSessions.length"
					:sessions="resumeSessions"
					@open="(id) => $emit('open-session', id)"
				/>
				<HomeStarters v-if="!isForm" :tiles="tiles" :area="area" @pick="(d) => $emit('suggestion', d)" />
			</template>
		</template>
	</div>
</template>

<script setup>
import { computed, ref, onMounted, watch } from "vue";
import { storeToRefs } from "pinia";
import { useUserStore } from "@/stores/userStore";
import { useChatStore } from "@/stores/chatStore";
import { useSuggestionStore } from "@/stores/suggestionStore";
import { greetingLineForHour, displayNameFromUser } from "@/components/chat/welcomeGreeting";
import { selectWelcomeTiles } from "@/components/chat/welcome/welcomeRelevance";
import { fillPageAsk } from "@/components/chat/welcome/pageAskFill";
import { useHomeSignals } from "@/composables/useHomeSignals";
import { __ } from "@/utils/i18n";
import HomeHeader from "@/components/chat/welcome/HomeHeader.vue";
import PageAsks from "@/components/chat/welcome/PageAsks.vue";
import NeedsYou from "@/components/chat/welcome/NeedsYou.vue";
import ContinueList from "@/components/chat/welcome/ContinueList.vue";
import HomeStarters from "@/components/chat/welcome/HomeStarters.vue";
import FirstRunStarters from "@/components/chat/welcome/FirstRunStarters.vue";
import { usePageContext } from "../usePageContext.js";

defineEmits(["suggestion", "open-session"]);

const NEEDS_YOU_CAP = 3;
const NEEDS_YOU_CAP_ON_FORM = 2;

const userStore = useUserStore();
const chatStore = useChatStore();
const suggestionStore = useSuggestionStore();
const { allSuggestions } = storeToRefs(suggestionStore);

const displayName = computed(() => displayNameFromUser(userStore.user));
const greetingLine = computed(() => greetingLineForHour(new Date().getHours(), displayName.value));

// The panel can open before the session list has loaded; an empty list only means a
// first-time user once it has.
const sessionsLoaded = ref(chatStore.sessions.length > 0);
const dayOne = computed(() => sessionsLoaded.value && chatStore.sortedSessions.length === 0);

// The widget is narrow, so it offers one session to continue where the SPA offers two.
const resumeSessions = computed(() =>
	chatStore.sortedSessions.filter((s) => s.session_id !== chatStore.currentSessionId).slice(0, 1)
);

const starterSuggestions = computed(() => allSuggestions.value.filter((s) => s.source !== "page"));
const tiles = computed(() =>
	selectWelcomeTiles({
		suggestions: starterSuggestions.value,
		resumePreviews: resumeSessions.value.map((s) => s.preview || ""),
	})
);
const firstRunTiles = computed(() => {
	const starters = starterSuggestions.value.filter((s) => s.description);
	return starters.length ? starters : tiles.value;
});

// The document name stays in this browser: the server only ever sees {type, doctype}.
const { pageContext } = usePageContext();
const isForm = computed(() => pageContext.value.type === "Form");
// An unsaved form only has Frappe's temporary "new-…" name, which names nothing the user can ask about.
const savedName = computed(() => {
	const { name, is_new: isNew } = pageContext.value;
	return isForm.value && name && !isNew && !name.startsWith("new-") ? name : "";
});
const filledAsks = computed(() => {
	// Until the new page's set has arrived, the old page's asks would name the wrong thing.
	if (suggestionStore.suggestionsDisabled || suggestionStore.isLoading || !["Form", "List"].includes(pageContext.value.type)) return [];
	return allSuggestions.value
		.filter((s) => s.source === "page")
		.map((s) =>
			fillPageAsk(s.description, {
				doctype: pageContext.value.doctype && __(pageContext.value.doctype),
				name: savedName.value,
			})
		)
		.filter(Boolean);
});

const { items, lensLabel, area, company, loaded, failed, dismiss } = useHomeSignals({
	cap: computed(() => (isForm.value ? NEEDS_YOU_CAP_ON_FORM : NEEDS_YOU_CAP)),
});

// The widget has no pages of its own: signal links open FAC Chat.
function openInChat(href) {
	window.open("/copilot" + href, "_blank", "noopener");
}

// The endpoint ranks templates by the page's type and doctype; the name never goes to the server.
// The curated asks differ per DocType, so a Desk navigation fetches the new page's set.
const suggestionContext = computed(() => {
	const { type, doctype } = pageContext.value;
	return doctype ? { type, doctype } : { type };
});
watch(suggestionContext, (context) => suggestionStore.loadSuggestions(context), { deep: true });
onMounted(async () => {
	suggestionStore.loadSuggestions(suggestionContext.value);
	if (!chatStore.sessions.length) await chatStore.loadSessions();
	sessionsLoaded.value = true;
});
</script>

<style scoped>
.ww {
	display: flex;
	flex-direction: column;
	gap: 16px;
	padding: 22px 18px 16px;
}
/* FAC Chat's masthead is sized for a page; its clamp() reads the browser viewport, not the panel. */
.ww :deep(.hh-greeting) {
	font-size: 22px;
}
.ww :deep(.hh-sub) {
	font-size: 13px;
}
.ww > * {
	animation: ww-surface 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ww > :nth-child(2) {
	animation-delay: 0.06s;
}
.ww > :nth-child(3) {
	animation-delay: 0.12s;
}
.ww > :nth-child(4) {
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
