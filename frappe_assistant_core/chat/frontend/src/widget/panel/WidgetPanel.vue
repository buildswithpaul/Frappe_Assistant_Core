<template>
	<div class="widget-panel" @click.capture="interceptDeskLinks">
		<header class="wp-header">
			<span class="wp-brand">FACO</span>
			<div class="wp-actions">
				<button
					type="button"
					data-test="hide"
					:title="t('Hide assistant (you can re-enable in My Preferences)')"
					@click="hideWidget"
				>
					⤓
				</button>
				<button type="button" data-test="expand" :title="t('Open Full Assistant')" @click="expand">⤢</button>
				<button type="button" data-test="close" :title="t('Close')" @click="bridge.emit('close')">✕</button>
			</div>
		</header>
		<ConnectionBanners
			:connection-visible="chatStore.connectionVisible"
			:socket-error="chatStore.socketError"
			:error="chatStore.error"
			:error-code="chatStore.errorCode"
			:is-admin="userStore.isAdmin"
			:needs-reconnect="userStore.needsReconnect"
			:reconnecting="reconnecting"
			@retry="retryConnection"
			@dismiss-error="chatStore.clearError()"
			@reconnect="reconnectServer"
		/>
		<div ref="scroller" class="wp-messages">
			<WidgetWelcome v-if="chatStore.messages.length === 0" />
			<ChatInterface
				v-else
				:messages="chatStore.messages"
				:is-streaming="chatStore.isStreaming"
				@toggle-block="chatStore.toggleBlockExpansion"
				@approve="onDecision"
				@reject="onDecision"
				@continue="chatStore.continueMessage"
				@unqueue="chatStore.unqueueMessage"
			/>
			<BrowserToolConfirm
				v-for="c in confirms"
				:key="c.id"
				:request="c.request"
				@decide="(decision) => settleConfirm(c, decision)"
			/>
		</div>
		<OverageNotice
			v-if="overageVisible"
			:credit-balance="Number(userStore.quotaInfo?.credit_balance) || 0"
			@dismiss="dismissOverage"
		/>
		<InputArea
			:is-streaming="chatStore.isStreaming"
			:interaction-mode="chatStore.pendingInteractionBlock?.regime || null"
			@send="onSend"
			@file-upload="handleFileUpload"
			@abort="chatStore.abortStream"
		/>
		<CreditMeter />
	</div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useChatStore } from "@/stores/chatStore";
import { useUserStore } from "@/stores/userStore";
import { useSpotlightStore } from "@/stores/spotlightStore";
import { resolveComposerRoute } from "@/stores/chat/composerRouting";
import { useMessageFileUpload } from "@/composables/useMessageFileUpload";
import { useAutoScroll } from "@/composables/useAutoScroll";
import { reconnectSocket } from "@/composables/useStreaming";
import ChatInterface from "@/components/chat/ChatInterface.vue";
import InputArea from "@/components/chat/InputArea.vue";
import ConnectionBanners from "@/components/chat/ConnectionBanners.vue";
import CreditMeter from "@/components/chat/CreditMeter.vue";
import WidgetWelcome from "./WidgetWelcome.vue";
import BrowserToolConfirm from "./BrowserToolConfirm.vue";
import OverageNotice from "./OverageNotice.vue";
import { bridge } from "../bridge.js";
import { handOffToFullPage } from "../desk/session.js";
import { isBlocked, overageNoticeDue, markOverageNoticeShown } from "../desk/quotaGate.js";
import { confirms, settleConfirm } from "./confirmQueue.js";
import { t } from "./i18n.js";
import { deskRouteFor } from "./deskLinks.js";
import { logger } from "@/utils/logger";

const chatStore = useChatStore();
const userStore = useUserStore();
const spotlight = useSpotlightStore();
const { handleFileUpload, consumeUploadedFiles } = useMessageFileUpload();
const scroller = ref(null);
useAutoScroll(
	scroller,
	computed(() => chatStore.messages),
	computed(() => chatStore.isStreaming)
);

const deskUser = () => window.frappe?.session?.user || "";

// The boot payload carries the plan quota but not the admission flags the gate and the overage
// notice need (credits_exhausted, in_overage, credit_balance), so read the full status once.
const overageDismissed = ref(false);
const overageVisible = computed(
	() => !overageDismissed.value && overageNoticeDue(userStore.quotaInfo, deskUser())
);
function dismissOverage() {
	markOverageNoticeShown(userStore.quotaInfo, deskUser());
	overageDismissed.value = true;
}

// Same routing as ChatView.handleSendMessage: answer a pending question, abandon a card, or send.
async function onSend({ message }) {
	// Only an admin gets the Spotlight that explains a block; a member who is refused would just lose
	// their text, so theirs goes through and the server's own error shows inline.
	if (isBlocked(userStore.quotaInfo) && userStore.quotaInfo.is_admin) {
		spotlight.onQuotaExhausted();
		return;
	}
	const route = resolveComposerRoute({
		isStreaming: chatStore.isStreaming,
		pendingInteraction: chatStore.pendingInteractionBlock,
	});
	if (route === "answer") {
		consumeUploadedFiles();
		await chatStore.answerPendingQuestion(message);
		return;
	}
	if (route === "abort-then-send") await chatStore.abortPendingInteraction();
	await chatStore.sendMessage(message, consumeUploadedFiles(), null, null, null, {
		skipQueue: route === "abort-then-send",
	});
}

// Same mapping as ChatView.handleApprovalResponse.
async function onDecision(blockId, responses) {
	if (!responses?.length) return;
	const first = responses[0].response;
	const resolution =
		first === "trust" ? "trusted" : first === "rejected" ? "rejected" : first === "approve" ? "approved" : "answered";
	await chatStore.submitInterruptDecision({ blockId, resolution, userResponse: first, response: first });
}

const reconnecting = ref(false);
function retryConnection() {
	chatStore.clearSocketError();
	reconnectSocket();
}
async function reconnectServer() {
	reconnecting.value = true;
	try {
		await userStore.reconnectServer();
	} finally {
		reconnecting.value = false;
	}
}

function expand() {
	handOffToFullPage(chatStore.currentSessionId || bridge.state.sessionId);
	bridge.emit("close");
	window.location.assign("/copilot");
}

async function hideWidget() {
	const response = await window.frappe.call({
		method: "frappe_assistant_core.chat.api.settings.widget.update_user_preference",
		args: { field: "hide_widget", value: "1" },
	});
	// The endpoint answers 200 {success:false} on a validation error: not saved, so do not hide.
	if (response?.message?.success === false) {
		logger.error("[FAC widget] hide not saved", response.message.message);
		return;
	}
	bridge.emit("close");
	bridge.emit("hide");
}

// Desk links in answers go through Desk's router: a full navigation would reload the page
// and lose the conversation. A modified click keeps its browser meaning (new tab).
function interceptDeskLinks(event) {
	if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
	const a = event.composedPath().find((el) => el.tagName === "A");
	const href = a && a.getAttribute("href");
	const route = deskRouteFor(href);
	if (!route) return;
	event.preventDefault();
	window.frappe.set_route(...route);
}

// The launcher owns Ctrl+Shift+Space (it must work before this panel exists) and asks for the mic
// through the bridge: a flag for a request made before we mounted, an event for later ones.
function toggleMic() {
	bridge.state.micRequested = false;
	scroller.value?.getRootNode().querySelector(".mic-btn")?.click();
}
// The launcher emits "open" just before "mic"; the panel only becomes visible a tick later.
const onMicRequest = () => setTimeout(toggleMic, 0);
const stopMic = bridge.on("mic", onMicRequest);
onMounted(() => {
	if (bridge.state.micRequested) toggleMic();
	userStore.loadQuota();
});
onUnmounted(stopMic);
</script>

<style scoped>
.widget-panel {
	flex: 1;
	min-height: 0;
	display: flex;
	flex-direction: column;
}
.wp-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 10px 12px;
	border-bottom: 1px solid var(--ql-border);
	background: var(--ql-surface);
}
.wp-brand {
	font-family: var(--ql-font-display);
	font-weight: 600;
	letter-spacing: 0.04em;
	color: var(--ql-text);
}
.wp-actions {
	display: flex;
	gap: 4px;
}
.wp-actions button {
	width: 28px;
	height: 28px;
	border: none;
	border-radius: 6px;
	background: transparent;
	color: var(--ql-text-secondary);
	font-size: 14px;
	cursor: pointer;
}
.wp-actions button:hover {
	background: var(--ql-accent-soft);
	color: var(--ql-text);
}
.wp-messages {
	flex: 1;
	min-height: 0;
	overflow-y: auto;
	position: relative;
}
</style>
