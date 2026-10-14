<template>
	<section class="project-chats" :aria-label="__('Chats')">
		<div class="composer">
			<textarea
				ref="inputRef"
				v-model="draft"
				class="composer-input"
				data-test="project-chat-input"
				rows="2"
				:placeholder="placeholder"
				:aria-label="placeholder"
				:disabled="sending"
				@input="autogrow"
				@keydown.enter="onEnter"
			></textarea>
			<div class="composer-footer">
				<span class="composer-hint">{{ __("Uses this project's instructions, documents and memory") }}</span>
				<button
					type="button"
					class="send-btn"
					data-test="new-project-chat"
					:aria-label="__('Send')"
					:title="__('Send')"
					:disabled="!canSend"
					@click="send"
				>
					<svg class="send-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M13 6l6 6-6 6" />
					</svg>
				</button>
			</div>
		</div>

		<h2 class="chats-title" data-test="project-chats-count">
			{{ __("Chats") }}<span v-if="chats.length" class="count"> · {{ chats.length }}</span>
		</h2>

		<p v-if="!loading && !chats.length" class="empty" data-test="project-empty">
			{{ __("No chats in this project yet") }}
		</p>
		<div v-else class="chat-list">
			<ChatRow
				v-for="chat in chats"
				:key="chat.session_id"
				:session="chat"
				:projects="projects"
				:active="chat.session_id === currentSessionId"
				:show-project="false"
				show-time
				:allow-new-project="false"
				:deleting="deletingId === chat.session_id"
				@select="router.push('/chat/' + chat.session_id)"
				@rename="(t) => renameChat(chat.session_id, t)"
				@move="(pid) => moveChat(chat.session_id, pid)"
				@archive="archiveChat(chat.session_id)"
			/>
		</div>
	</section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import ChatRow from "@/components/layout/ChatRow.vue";
import { api } from "@/api/client";
import { useChatStore } from "@/stores/chatStore";
import { useConversationsStore } from "@/stores/conversationsStore";
import { useProjectsStore } from "@/stores/projectsStore";
import { useToast } from "@/composables/useToast";
import { __ } from "@/utils/i18n";

const PROJECT_CHATS_LIMIT = 100;
const MAX_INPUT_HEIGHT_PX = 192;

const props = defineProps({
	projectId: { type: String, required: true },
	projectTitle: { type: String, default: "" },
});

const router = useRouter();
const chatStore = useChatStore();
const conversationsStore = useConversationsStore();
const { currentSessionId } = storeToRefs(chatStore);
const { projects } = storeToRefs(useProjectsStore());
const { showError } = useToast();

const draft = ref("");
const sending = ref(false);
const inputRef = ref(null);
const loading = ref(true);
const chats = ref([]);
const deletingId = ref(null);

const placeholder = computed(() => __("Start a chat in {0}…", [props.projectTitle]));
const canSend = computed(() => !sending.value && draft.value.trim().length > 0);

function notifyFailure(err) {
	showError(err?.message || __("Something went wrong"));
}

async function loadChats(projectId) {
	loading.value = true;
	chats.value = [];
	try {
		const rows = await api.chat.getSessions({ limit: PROJECT_CHATS_LIMIT, project: projectId });
		if (projectId === props.projectId) chats.value = rows || [];
	} catch (err) {
		if (projectId === props.projectId) notifyFailure(err);
	} finally {
		if (projectId === props.projectId) loading.value = false;
	}
}

watch(() => props.projectId, loadChats, { immediate: true });

function autogrow() {
	const el = inputRef.value;
	if (!el) return;
	el.style.height = "auto";
	el.style.height = `${Math.min(el.scrollHeight, MAX_INPUT_HEIGHT_PX)}px`;
}

function onEnter(event) {
	if (event.shiftKey || event.isComposing) return;
	event.preventDefault();
	send();
}

// ChatView sends the queued text once the new chat has loaded (chatStore.takeFirstMessage).
async function send() {
	const text = draft.value.trim();
	if (!text || sending.value) return;
	sending.value = true;
	try {
		const sessionId = await chatStore.startChatInProject(props.projectId);
		if (!sessionId) throw new Error(__("Couldn't start a chat. Try again."));
		chatStore.queueFirstMessage(sessionId, text);
		draft.value = "";
		router.push("/chat/" + sessionId);
	} catch (err) {
		notifyFailure(err);
	} finally {
		sending.value = false;
	}
}

function patchChat(sessionId, patch) {
	chats.value = chats.value.map((c) => (c.session_id === sessionId ? { ...c, ...patch } : c));
}

async function renameChat(sessionId, title) {
	try {
		await conversationsStore.renameSession(sessionId, title);
		patchChat(sessionId, { title, preview: title });
	} catch (err) {
		notifyFailure(err);
	}
}

async function moveChat(sessionId, projectId) {
	try {
		await conversationsStore.moveSession(sessionId, projectId);
		if (projectId !== props.projectId) {
			chats.value = chats.value.filter((c) => c.session_id !== sessionId);
		}
	} catch (err) {
		notifyFailure(err);
	}
}

async function archiveChat(sessionId) {
	deletingId.value = sessionId;
	try {
		await api.chat.deleteSession(sessionId);
		chatStore.removeSession(sessionId);
		chats.value = chats.value.filter((c) => c.session_id !== sessionId);
	} catch (err) {
		notifyFailure(err);
	} finally {
		deletingId.value = null;
	}
}
</script>

<style scoped>
.project-chats {
	display: flex;
	flex-direction: column;
	gap: 0.875rem;
	min-width: 0;
}

.composer {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	padding: 0.75rem 0.875rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	background: var(--ql-surface);
	transition: border-color 0.15s ease;
}

.composer:focus-within {
	border-color: var(--ql-accent);
}

.composer-input {
	width: 100%;
	font: inherit;
	font-size: 0.9375rem;
	color: var(--ql-text);
	background: transparent;
	border: none;
	outline: none;
	resize: none;
	line-height: 1.5;
}

.composer-footer {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.75rem;
}

.composer-hint {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.send-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 2.25rem;
	height: 2.25rem;
	flex-shrink: 0;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
}

.send-btn:hover:not(:disabled) {
	background: var(--ql-accent-hover);
}

.send-btn:disabled {
	opacity: 0.45;
	cursor: not-allowed;
}

.send-icon {
	width: 1.125rem;
	height: 1.125rem;
}

.chats-title {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
}

.count {
	text-transform: none;
}

.empty {
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}
</style>
