<template>
	<div class="app-layout" :class="{ 'onboarding-mode': isOnboarding }">
		<!-- Navigation Sidebar (hidden during onboarding). Owns its own mobile
		     drawer, scrim, and scroll-lock. -->
		<NavigationSidebar
			v-if="!isOnboarding"
			:sessions="sortedSessions"
			:archived-sessions="archivedSessions"
			:active-session-id="currentSessionId"
			:collapsed="sidebarCollapsed"
			:loading="isLoading"
			@session-selected="handleSessionSelect"
			@new-chat="handleNewChat"
			@delete-session="handleDeleteSession"
			@continue-archived="handleContinueArchived"
			@load-archived="chatStore.loadArchivedSessions()"
			@open-settings="router.push('/settings')"
			@toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
		/>

		<!-- Main Content Area -->
		<main class="main-content">
			<!-- Top Bar (hidden during onboarding) -->
			<TopBar
				v-if="!isOnboarding"
				:title="currentChatTitle"
				:show-actions="registrationStatus === 'ready' && isUserSetupComplete"
				@toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
				@new-chat="handleNewChat"
			/>

			<!-- Chat Area + adaptive context rail -->
			<div class="chat-shell" ref="chatShellRef" :style="readWidthStyle">
			<aside
				v-if="indexMode !== 'hidden'"
				class="index-dock"
				:class="{ 'index-dock-spine': indexMode === 'spine' }"
			>
				<LedgerIndex
					:entries="indexEntries"
					:active-index="indexActiveIndex"
					:mode="indexMode"
					:pinned="pinnedEntries"
					@jump="onIndexJump"
					@jump-pin="onPinJump"
					@unpin="unpinMessage"
					@collapse="toggleIndexCollapsed"
				/>
			</aside>
			<div class="chat-area">
				<!-- Connection + error banners -->
				<ConnectionBanners
					:connection-visible="connectionVisible"
					:socket-error="socketError"
					:error="error"
					:needs-reconnect="needsReconnect"
					:reconnecting="reconnecting"
					@retry="retryConnection"
					@dismiss-error="chatStore.clearError()"
					@reconnect="handleReconnect"
				/>

				<!-- Messages / onboarding stages / welcome screen -->
				<div
					class="messages-container"
					ref="messagesContainer"
					@scroll.passive="indexUpdateActive(messagesContainer)"
				>
					<ChatStagePicker
						:registration-status="registrationStatus"
						:is-admin="isAdmin"
						:needs-user-setup="needsUserSetup"
						:is-user-setup-complete="isUserSetupComplete"
						:privacy-consent-complete="privacyConsentComplete"
						:user-not-registered="userNotRegistered"
						:terms-acceptance-required="termsAcceptanceRequired"
						:messages="messages"
						:is-loading="isLoading"
						:is-streaming="isStreaming"
						@registration-complete="handleRegistrationComplete"
						@user-connected="handleUserConnected"
						@feature-tour-complete="handleFeatureTourComplete"
						@suggestion="handleSuggestion"
						@navigate="handleNavigate"
						@open-session="handleSessionSelect"
						@toggle-block="handleToggleBlock"
						@approve="handleApprovalResponse"
						@reject="handleApprovalResponse"
						@continue="handleContinueResponse"
						@pin="pinMessage"
						@unqueue="handleUnqueue"
					>
						<template #composer>
							<InputArea v-if="composerInHero" v-bind="composerBindings" />
						</template>
					</ChatStagePicker>
				</div>

				<transition name="fade">
					<button
						v-if="!isFollowing && isStreaming"
						class="latest-pill"
						@click="resumeFollow"
					>
						↓ Latest · streaming
					</button>
				</transition>

				<button
					v-if="railShowTab && railMode === 'sheet' && !railVisible"
					class="rail-sheet-handle"
					@click="toggleRail"
				>
					Context {{ activeArtifacts.approval ? "· 1 approval" : "" }} ▲
				</button>

				<!-- Input Area - bottom dock once a conversation exists -->
				<InputArea
					v-if="
						registrationStatus === 'ready' &&
						isUserSetupComplete &&
						privacyConsentComplete &&
						!composerInHero
					"
					v-bind="composerBindings"
					class="composer-dock-enter"
				/>
			</div>

			<!-- Docked rail (>=1280px) — collapsible to reclaim the reading width -->
			<aside v-if="railMode === 'rail' && railVisible" class="rail-dock">
				<ContextRail
					:artifacts="activeArtifacts"
					:live="activeTurnIsLive"
					collapsible
					@review-approval="handleRailReviewApproval"
					@collapse="collapseRailDock"
				/>
			</aside>
			<!-- Slim reopen tab once the docked rail is collapsed -->
			<button
				v-if="railShowDockReopen"
				class="rail-tab"
				aria-label="Show context"
				@click="expandRailDock"
			>
				<span class="rail-tab-text">Context</span>
				<span v-if="activeArtifacts.approval" class="rail-tab-badge" aria-hidden="true"></span>
			</button>

			<!-- Slim tab (768–1279px) — slides the rail open as an overlay -->
			<button
				v-if="railShowTab && railMode === 'tab' && !railVisible"
				class="rail-tab"
				@click="openRail"
			>
				<span class="rail-tab-text">Context</span>
				<span v-if="activeArtifacts.approval" class="rail-tab-badge" aria-hidden="true"></span>
			</button>
			<transition name="rail-slide">
				<aside v-if="railMode === 'tab' && railVisible" class="rail-overlay">
					<button class="rail-overlay-close" aria-label="Close context" @click="closeRail">×</button>
					<ContextRail
						:artifacts="activeArtifacts"
						:live="activeTurnIsLive"
						@review-approval="handleRailReviewApproval"
					/>
				</aside>
			</transition>

			<transition name="rail-sheet">
				<div v-if="railMode === 'sheet' && railVisible" class="rail-sheet-layer">
					<div class="rail-sheet-scrim" @click="closeRail"></div>
					<div
						class="rail-sheet"
						:class="{ dragging: sheetDragging }"
						:style="sheetDragStyle"
					>
						<div class="rail-sheet-chrome">
							<button
								type="button"
								class="rail-sheet-grab-hit"
								aria-label="Dismiss context"
								@click="closeRail"
								@pointerdown="onSheetPointerDown"
								@pointermove="onSheetPointerMove"
								@pointerup="onSheetPointerUp"
								@pointercancel="onSheetPointerUp"
							>
								<span class="rail-sheet-grab" aria-hidden="true"></span>
							</button>
						</div>
						<ContextRail
						:artifacts="activeArtifacts"
						:live="activeTurnIsLive"
						@review-approval="handleRailReviewApproval"
					/>
					</div>
				</div>
			</transition>
			</div>
		</main>

		<!-- Template Browser Modal -->
		<TemplateBrowserModal
			:is-open="showTemplateBrowser"
			@close="closeTemplateBrowser"
			@use-template="useTemplate"
		/>

		<!-- Parameter Modal -->
		<ParameterModal
			:is-open="showParameterModal"
			:template="selectedTemplate"
			@close="closeParameterModal"
			@submit="submitParameters"
		/>

		<!-- Help & Feedback modal (self-gates on supportStore.isOpen) -->
		<SupportModal />
	</div>
</template>

<script setup>
import { ref, computed, watch, defineAsyncComponent } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useChatStore } from "@/stores/chatStore";
import { useUserStore } from "@/stores/userStore";
import { useModelStore } from "@/stores/modelStore";
import { useSuggestionStore } from "@/stores/suggestionStore";
import { resolveComposerRoute } from "@/stores/chat/composerRouting";
import { useToast } from "@/composables/useToast";
import { storeToRefs } from "pinia";
import NavigationSidebar from "@/components/layout/NavigationSidebar.vue";
import TopBar from "@/components/layout/TopBar.vue";
import InputArea from "@/components/chat/InputArea.vue";
import ConnectionBanners from "@/components/chat/ConnectionBanners.vue";
import ChatStagePicker from "@/components/chat/ChatStagePicker.vue";
import SupportModal from "@/components/support/SupportModal.vue";

// Modals + nudge only render on user action — lazy keeps them out of the
// initial chat bundle.
const TemplateBrowserModal = defineAsyncComponent(
	() => import("@/components/templates/TemplateBrowserModal.vue"),
);
const ParameterModal = defineAsyncComponent(
	() => import("@/components/templates/ParameterModal.vue"),
);
import { useStreaming, reconnectSocket } from "@/composables/useStreaming";
import { useAutoScroll } from "@/composables/useAutoScroll";
import { useTemplateExecution } from "@/composables/useTemplateExecution";
import { useChatViewInit } from "@/composables/useChatViewInit";
import { useMessageFileUpload } from "@/composables/useMessageFileUpload";
import { useChatSessionActions } from "@/composables/useChatSessionActions";
import { useRobotMoodWiring } from "@/composables/useRobotMoodWiring";
import { useContextRail } from "@/composables/useContextRail";
import { useSheetDismiss } from "@/composables/useSheetDismiss";
import { deriveArtifacts } from "@/utils/contextArtifacts";
import ContextRail from "@/components/chat/ContextRail.vue";
import { logger } from "@/utils/logger";
import { usePreferences } from "@/composables/usePreferences";
import { resolveReadWidth } from "@/utils/chatWidth";
import LedgerIndex from "@/components/chat/index/LedgerIndex.vue";
import { useLedgerIndex } from "@/composables/useLedgerIndex";
import { loadPins, togglePin } from "@/utils/indexPins.js";

useRobotMoodWiring();

const route = useRoute();
const router = useRouter();
const chatStore = useChatStore();
const userStore = useUserStore();
const modelStore = useModelStore();
const suggestionStore = useSuggestionStore();
const { showError } = useToast();

const {
	currentSessionId,
	messages,
	isLoading,
	isStreaming,
	sortedSessions,
	currentSession,
	socketError,
	connectionVisible,
	error,
	archivedSessions,
} = storeToRefs(chatStore);

const {
	registrationStatus,
	isAdmin,
	needsUserSetup,
	needsReconnect,
	isUserSetupComplete,
	userAuthStatus,
	privacyConsentComplete,
	termsAcceptanceRequired,
} = storeToRefs(userStore);

// Initialize streaming listener for realtime events
useStreaming();

function retryConnection() {
	chatStore.clearSocketError();
	reconnectSocket();
}

const reconnecting = ref(false);
async function handleReconnect() {
	reconnecting.value = true;
	try {
		await userStore.reconnectServer();
	} finally {
		reconnecting.value = false;
	}
}

const sidebarCollapsed = ref(false);
const messagesContainer = ref(null);
const currentContext = ref(null);

// Template execution flow (browser modal + parameter modal + rendered prompt)
const {
	showTemplateBrowser,
	showParameterModal,
	selectedTemplate,
	pendingPrompt,
	openTemplateBrowser,
	closeTemplateBrowser,
	useTemplate,
	submitParameters,
	closeParameterModal,
} = useTemplateExecution();

// File pre-upload flow (matches widget — upload on select, attach on send)
const { handleFileUpload, consumeUploadedFiles } = useMessageFileUpload();

// True during onboarding screens (registration, user setup, feature tour) — hides sidebar & topbar
const isOnboarding = computed(() => {
	if (registrationStatus.value === "not_registered") return true;
	if (registrationStatus.value === "no_role") return true;
	if (registrationStatus.value === "checking") return true;
	if (registrationStatus.value === "ready" && needsUserSetup.value) return true;
	if (
		registrationStatus.value === "ready" &&
		isUserSetupComplete.value &&
		!privacyConsentComplete.value
	)
		return true;
	return false;
});

// Non-admin user who isn't registered in AR — needs admin to add them
const userNotRegistered = computed(() => {
	if (registrationStatus.value !== "ready") return false;
	if (isAdmin.value) return false;
	if (!userAuthStatus.value) return false;
	return !userAuthStatus.value.user_registered && !userAuthStatus.value.ready;
});

const currentChatTitle = computed(() => {
	if (currentSession.value?.preview) {
		return (
			currentSession.value.preview.slice(0, 50) +
			(currentSession.value.preview.length > 50 ? "..." : "")
		);
	}
	return messages.value.length > 0 ? "Chat" : "New Chat";
});

// Artifacts come from the most recent assistant turn's blocks. The rail mirrors
// what the AI just produced/touched — not the whole conversation history.
const activeAssistantMessage = computed(() => {
	const list = messages.value || [];
	for (let i = list.length - 1; i >= 0; i--) {
		if (list[i]?.role === "assistant") return list[i];
	}
	return null;
});

const activeArtifacts = computed(() => deriveArtifacts(activeAssistantMessage.value?.blocks));

// Drives whether the rail still presents work as in flight. A hydrated message
// carries no isStreaming flag, so a reloaded conversation reads as finished.
const activeTurnIsLive = computed(() => Boolean(activeAssistantMessage.value?.isStreaming));

const railHasArtifacts = computed(() => activeArtifacts.value.hasArtifacts);
const {
	mode: railMode,
	isVisible: railVisible,
	showAffordance: railShowTab,
	showDockReopen: railShowDockReopen,
	open: openRail,
	close: closeRail,
	toggle: toggleRail,
	collapseDock: collapseRailDock,
	expandDock: expandRailDock,
} = useContextRail(railHasArtifacts);

const {
	style: sheetDragStyle,
	dragging: sheetDragging,
	onPointerDown: onSheetPointerDown,
	onPointerMove: onSheetPointerMove,
	onPointerUp: onSheetPointerUp,
} = useSheetDismiss(() => closeRail());

const { preferences } = usePreferences();
const readWidthStyle = computed(() => ({
	"--ql-read-width": resolveReadWidth(preferences.chatWidth),
}));

// Conversation index (left gutter) — mirrors the rail's docked/tab/hidden
// pattern but keyed off available width rather than viewport tier alone.
const chatShellRef = ref(null);
const railDocked = computed(() => railMode.value === "rail" && railVisible.value);
const columnWidth = computed(() => parseInt(resolveReadWidth(preferences.chatWidth), 10));
const {
	entries: indexEntries,
	mode: indexMode,
	collapsed: indexCollapsed,
	toggleCollapsed: toggleIndexCollapsed,
	activeIndex: indexActiveIndex,
	jumpTo: indexJumpTo,
	updateActive: indexUpdateActive,
} = useLedgerIndex({ messages, chatShellRef, railDocked, columnWidth });

function onIndexJump(index) {
	indexJumpTo(index);
}

const pinnedEntries = ref([]);
watch(
	() => chatStore.currentSessionId,
	(id) => {
		pinnedEntries.value = loadPins(id);
	},
	{ immediate: true },
);

function pinMessage(messageId) {
	const entry = indexEntries.value.find(
		(e) => e.kind === "exchange" && e.messageId === messageId,
	);
	pinnedEntries.value = togglePin(chatStore.currentSessionId, {
		messageId,
		heading: entry?.heading || "Pinned answer",
	});
}
function unpinMessage(messageId) {
	pinnedEntries.value = togglePin(chatStore.currentSessionId, { messageId, heading: "" });
}
function onPinJump(messageId) {
	const i = (messages.value || []).findIndex((m) => m?.message_id === messageId);
	if (i >= 0) indexJumpTo(i);
}

// Clicking "Review & approve" in the rail scrolls the matching in-thread
// interaction card into view (the card itself owns the approve/reject buttons).
function handleRailReviewApproval(blockId) {
	closeRail();
	const el = document.querySelector(`[data-interaction-id="${blockId}"]`);
	if (el && typeof el.scrollIntoView === "function") {
		el.scrollIntoView({ behavior: "smooth", block: "center" });
	}
}

// Mount-time initialization + route watcher (sessions hydrate, suggestions/models,
// widget handoff, billing deep-link). Extracted for clarity — see composable.
useChatViewInit(
	{ chatStore, userStore, modelStore, suggestionStore },
	{ route, router },
	{ registrationStatus, isUserSetupComplete }
);

// Auto-scroll to bottom on new messages / streaming chunks
const { isFollowing, scrollToBottom } = useAutoScroll(messagesContainer, messages, isStreaming);

function resumeFollow() {
	isFollowing.value = true;
	scrollToBottom();
}

// --- Handlers ---

async function handleRegistrationComplete() {
	await userStore.refreshRegistrationStatus();
	if (registrationStatus.value === "ready") {
		await userStore.checkUserAuth();
		if (isUserSetupComplete.value) {
			await chatStore.loadSessions();
		}
	}
}

async function handleUserConnected() {
	if (isUserSetupComplete.value) {
		await chatStore.loadSessions();
		// Stagger to avoid Gunicorn worker deadlock (AR calls back to FACO for MCP)
		suggestionStore.loadSuggestions({}, { force: true });
		setTimeout(() => modelStore.loadModels(), 500);
	}
}

async function handleFeatureTourComplete(payload) {
	// Only treat the tour as done in-session when consent actually saved. If it
	// failed, leave the flag unset so the tour reappears to retry — matching the
	// server, which likewise did not set privacy_consent_complete on failure.
	if (payload?.consentSaved !== false) {
		userStore.privacyConsentComplete = true;
	}
	if (payload?.seedPrompt) {
		pendingPrompt.value = payload.seedPrompt;
	}
	// Fresh-from-onboarding users often hit empty lists (models, sidebar menus
	// gated by capabilities, etc.) because the initial fetches ran before AR
	// had fully provisioned the subscription. Re-fetch everything now that
	// the tour is done and the tenant is guaranteed to be ready.
	await userStore.loadCapabilities();
	chatStore.loadSessions();
	suggestionStore.loadSuggestions({}, { force: true });
	setTimeout(() => modelStore.loadModels(), 500);
}

function handleNavigate(target) {
	router.push(target);
}

async function handleNewChat() {
	const sessionId = await chatStore.createSession();
	if (sessionId) {
		router.push(`/chat/${sessionId}`);
	}
}

// Session lifecycle — select, delete (recurses into handleNewChat when list empties),
// continue-archived. Extracted to keep ChatView under its size budget.
const { handleSessionSelect, handleDeleteSession, handleContinueArchived } = useChatSessionActions(
	{ chatStore, router, handleNewChat }
);

// One InputArea instance: hero slot on the empty state, bottom dock in a
// conversation. The swap happens at first send, when the draft is empty, so
// component re-creation is harmless (spec §4).
const composerInHero = computed(
	() =>
		messages.value.length === 0 &&
		!isLoading.value &&
		registrationStatus.value === "ready" &&
		isUserSetupComplete.value &&
		privacyConsentComplete.value
);

// Shared bindings so hero and dock are guaranteed identical. camelCase on*
// keys are treated as listeners by v-bind.
const composerBindings = computed(() => ({
	isStreaming: isStreaming.value,
	interactionMode: chatStore.pendingInteractionBlock?.regime || null,
	context: currentContext.value,
	initialMessage: pendingPrompt.value,
	onSend: handleSendMessage,
	onFileUpload: handleFileUpload,
	onAbort: handleAbortStream,
	onPickTemplate: useTemplate,
	onBrowseTemplates: openTemplateBrowser,
}));

async function handleSendMessage({ message }) {
	pendingPrompt.value = "";
	const route = resolveComposerRoute({
		isStreaming: isStreaming.value,
		pendingInteraction: chatStore.pendingInteractionBlock,
	});
	if (route === "answer") {
		// The resume wire format has no attachment slot — staged files can't
		// ride along with a card answer, so drop them and say so rather than
		// silently losing what the user just uploaded.
		const staged = consumeUploadedFiles();
		if (staged.length) {
			showError("Attachments can't be sent with a card answer — they were removed.");
		}
		await chatStore.answerPendingQuestion(message);
		return;
	}
	if (route === "abort-then-send") {
		await chatStore.abortPendingInteraction();
	}
	const modelId = modelStore.currentModelId;
	const files = consumeUploadedFiles();
	// Abandoning a card means "send this now" — isStreaming can still read true
	// at this point (see chatStore.sendMessage), so route the same signal that
	// picked this branch straight through rather than letting it get queued.
	await chatStore.sendMessage(message, files, currentContext.value, modelId, null, {
		skipQueue: route === "abort-then-send",
	});
}

function handleAbortStream() {
	chatStore.abortStream();
}

function handleSuggestion(suggestion) {
	handleSendMessage({ message: suggestion, files: [] });
}

function handleToggleBlock(messageIndex, blockId) {
	chatStore.toggleBlockExpansion(messageIndex, blockId);
}

// HITL approval/rejection handler.
// Delegates to chatStore.submitInterruptDecision which records the user's
// decision on this card and batches the actual resume_interrupt HTTP call
// until every pending interaction card on this turn has been decided. See
// the action in chatStore.js for why batching is required.
async function handleApprovalResponse(blockId, responses) {
	if (!responses?.length) return;

	const firstResponse = responses[0].response;

	let resolution;
	if (firstResponse === "trust") resolution = "trusted";
	else if (firstResponse === "rejected") resolution = "rejected";
	else if (firstResponse === "approve") resolution = "approved";
	else resolution = "answered"; // question-type responses (string, array, etc.)

	await chatStore.submitInterruptDecision({
		blockId,
		resolution,
		userResponse: firstResponse,
		response: firstResponse,
	});
}

function handleContinueResponse(messageId) {
	chatStore.continueMessage(messageId);
}

function handleUnqueue(queueId) {
	chatStore.unqueueMessage(queueId);
}
</script>

<style scoped>
.app-layout {
	display: flex;
	height: 100%;
	min-height: 0;
	overflow: hidden;
	background-color: var(--ql-bg);
}

.main-content {
	flex: 1;
	display: flex;
	flex-direction: column;
	min-width: 0;
	min-height: 0;
	overflow: hidden;
}

.chat-area {
	position: relative;
	flex: 1;
	display: flex;
	flex-direction: column;
	min-width: 0;
	min-height: 0;
	overflow: hidden;
}

.messages-container {
	flex: 1;
	min-height: 0;
	overflow-y: auto;
	-webkit-overflow-scrolling: touch;
	scrollbar-width: thin;
	scrollbar-color: var(--ql-border) transparent;
}

.messages-container::-webkit-scrollbar {
	width: 6px;
}

.messages-container::-webkit-scrollbar-track {
	background: transparent;
}

.messages-container::-webkit-scrollbar-thumb {
	background-color: var(--ql-border);
	border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
	background-color: var(--ql-text-muted);
}

.latest-pill {
	position: absolute;
	left: 50%;
	transform: translateX(-50%);
	bottom: 132px;
	z-index: 15;
	font-size: 12px;
	font-weight: 500;
	color: var(--ql-text-secondary);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 999px;
	padding: 7px 16px;
	box-shadow: 0 1px 3px rgb(0 0 0 / 0.05);
	cursor: pointer;
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* At <1024 the sidebar is a fixed off-canvas drawer. Keep the shell as a
   column flex so .messages-container still gets a bounded height and can
   scroll. Switching to display:block used to let the transcript grow past
   the viewport while ancestors clipped it — the thread looked frozen.
   min-height: 0 on the column is set on the base rules so tablet *tab mode*
   (768–1279, including iPad landscape at 1024) can scroll too — not only phones. */
@media (max-width: 1023px) {
	.app-layout {
		position: relative;
	}
	.main-content,
	.chat-shell,
	.chat-area {
		width: 100%;
	}
	/* App shell already has padding-bottom: env(safe-area-inset-bottom). The
	   dock repeating that inset left a home-indicator-sized gap under the
	   textarea. Keep a short breath so it sits on the bottom, not in it. */
	.chat-area > .composer-dock-enter :deep(.input-area-container) {
		padding-bottom: 0.5rem;
	}
}

/* Let the chat column shrink below its content's intrinsic width on phones so
   long cards/titles wrap instead of forcing a horizontal page scroll. */
@media (max-width: 767px) {
	.chat-shell,
	.chat-area,
	.main-content {
		min-width: 0;
	}
}

.chat-shell {
	position: relative; /* anchors the absolutely-positioned tab/overlay/sheet siblings of .chat-area */
	display: flex;
	flex-direction: row;
	align-items: stretch;
	flex: 1;
	min-height: 0;
	min-width: 0;
	overflow: hidden;
}
.chat-shell > * {
	min-height: 0;
}
.index-dock {
	width: 240px;
	flex-shrink: 0;
	height: 100%;
	overflow: hidden;
}
.index-dock-spine {
	width: 28px;
}
/* Reading column stays calm at ~720px and re-centers when no rail is shown.
   Targets ChatInterface's real root (.ql-chat-doc) — the messages-container's
   reading column — so it stays capped and centered with or without the rail. */
.messages-container :deep(.ql-chat-doc) {
	max-width: var(--ql-read-width, 720px);
	margin-inline: auto;
	width: 100%;
}
/* Dock the composer to the same reading width as the message column so the
   input box lines up with the conversation instead of overhanging it. The
   hero (welcome-screen) composer keeps its own wider column. */
.chat-area > .composer-dock-enter :deep(.input-column) {
	max-width: var(--ql-read-width, 720px);
}
.rail-dock {
	width: 300px;
	flex-shrink: 0;
	height: 100%;
	overflow: hidden;
}
/* Slim tab on laptop */
.rail-tab {
	position: absolute;
	top: 50%;
	right: 0;
	transform: translateY(-50%);
	writing-mode: vertical-rl;
	padding: 14px 6px;
	background: var(--ql-surface, #ffffff);
	border: 1px solid var(--ql-border, #ece9e3);
	border-right: none;
	border-radius: 8px 0 0 8px;
	font-size: 11px;
	letter-spacing: 0.08em;
	text-transform: uppercase;
	color: var(--ql-text-secondary, #57534c);
	cursor: pointer;
	z-index: 20;
}
.rail-tab-badge {
	display: inline-block;
	width: 7px;
	height: 7px;
	margin-top: 6px;
	border-radius: 50%;
	background: var(--ql-gold, #c9a227);
}
.rail-overlay {
	position: absolute;
	top: 0;
	right: 0;
	bottom: 0;
	width: 300px;
	background: var(--ql-surface, #ffffff);
	box-shadow: -8px 0 24px rgba(0, 0, 0, 0.12);
	z-index: 30;
}
.rail-overlay-close {
	position: absolute;
	top: 8px;
	right: 10px;
	font-size: 18px;
	line-height: 1;
	background: none;
	border: none;
	color: var(--ql-text-muted, #8a857c);
	cursor: pointer;
	z-index: 31;
}
.rail-slide-enter-active,
.rail-slide-leave-active {
	transition: transform 0.2s ease;
}
.rail-slide-enter-from,
.rail-slide-leave-to {
	transform: translateX(100%);
}
/* Bottom sheet on mobile — in-flow above the composer, not overlaying it */
.rail-sheet-handle {
	flex-shrink: 0;
	align-self: center;
	padding: 8px 18px;
	background: var(--ql-surface, #ffffff);
	border: 1px solid var(--ql-border, #ece9e3);
	border-bottom: none;
	border-radius: 10px 10px 0 0;
	font-size: 12px;
	color: var(--ql-text-secondary, #57534c);
	cursor: pointer;
	z-index: 20;
}
.rail-sheet-layer {
	position: absolute;
	inset: 0;
	z-index: 30;
	display: flex;
	flex-direction: column;
	justify-content: flex-end;
}
.rail-sheet-scrim {
	position: absolute;
	inset: 0;
	background: rgba(0, 0, 0, 0.35);
}
.rail-sheet {
	position: relative;
	max-height: 70%;
	background: var(--ql-surface, #ffffff);
	border-top: 1px solid var(--ql-border, #ece9e3);
	border-radius: 14px 14px 0 0;
	box-shadow: 0 -8px 24px rgba(0, 0, 0, 0.16);
	overflow-y: auto;
	padding-bottom: env(safe-area-inset-bottom, 0px);
}
.rail-sheet.dragging {
	transition: none;
}
.rail-sheet-chrome {
	position: sticky;
	top: 0;
	z-index: 1;
	display: flex;
	align-items: center;
	gap: 8px;
	min-height: 44px;
	padding: 4px 8px 6px;
	background: var(--ql-surface, #ffffff);
}
.rail-sheet-grab-hit {
	flex: 1;
	display: flex;
	align-items: center;
	justify-content: center;
	min-height: 44px;
	padding: 0;
	border: none;
	background: transparent;
	touch-action: none;
	cursor: grab;
}
.rail-sheet-grab {
	display: block;
	width: 40px;
	height: 4px;
	border-radius: 2px;
	background: var(--ql-border-hover, #dedad2);
}
.rail-sheet-enter-active,
.rail-sheet-leave-active {
	transition: transform 0.22s ease;
}
.rail-sheet-enter-from,
.rail-sheet-leave-to {
	transform: translateY(100%);
}
.composer-dock-enter {
	flex-shrink: 0;
	animation: composer-dock-fade 0.2s ease;
}
@keyframes composer-dock-fade {
	from { opacity: 0; transform: translateY(8px); }
	to { opacity: 1; transform: translateY(0); }
}
</style>
