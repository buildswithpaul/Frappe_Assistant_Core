<template>
	<div class="input-area-container">
		<div class="input-column">
			<!-- File Previews (above input) -->
			<AttachedFilePreview :files="attachedFiles" @remove="removeFile" />

			<!-- Markdown Preview (shown when toggle is on AND markdown is detected) -->
			<MarkdownPreviewPanel
				:visible="showMarkdownPreview && hasMarkdown"
				:html="renderedMarkdown"
			/>

			<!-- Input Box: two rows (textarea, toolbar) -->
			<div class="input-box-wrapper">
				<SlashMenu
					ref="slashMenuRef"
					:open="slashOpen"
					:query="slashQuery"
					@pick="handleSlashPick"
					@browse-all="handleBrowseAll"
				/>
				<ComposerPlusMenu
					:open="plusOpen"
					:web-search-available="webSearchAvailable"
					:web-search="modes.webSearch"
					:thinking="modes.thinking"
					:thinking-available="modelStore.thinkingHonoured"
					@attach="onMenuAttach"
					@toggle-web-search="composerModesStore.toggle(chatStore.currentSessionId, 'webSearch')"
					@toggle-thinking="composerModesStore.toggle(chatStore.currentSessionId, 'thinking')"
					@close="plusOpen = false"
				/>
				<div class="input-box">
					<!-- Hidden File Input -->
					<input
						ref="fileInput"
						type="file"
						multiple
						:accept="UPLOAD_ACCEPT_ATTR"
						class="hidden-file-input"
						@change="handleFileSelect"
					/>

					<!-- Row 1: Textarea -->
					<textarea
						ref="textInput"
						v-model="message"
						@keydown="handleKeydown"
						@input="autoResize"
						@paste="handlePaste"
						@focus="robotMoodStore.setAttentive(true)"
						@blur="robotMoodStore.setAttentive(false)"
						:placeholder="placeholderText"
						rows="1"
						class="input-textarea"
					></textarea>

					<!-- Row 2: Toolbar -->
					<InputToolbar
						:is-streaming="isStreaming"
						:can-send="canSend"
						:has-markdown="hasMarkdown"
						:show-markdown-preview="showMarkdownPreview"
						:context="context"
						:plus-open="plusOpen"
						:web-search="modes.webSearch"
						:thinking="modes.thinking"
						:thinking-available="modelStore.thinkingHonoured"
						:web-search-available="webSearchAvailable"
						@toggle-plus="plusOpen = !plusOpen"
						@toggle-web-search="composerModesStore.toggle(chatStore.currentSessionId, 'webSearch')"
						@toggle-thinking="composerModesStore.toggle(chatStore.currentSessionId, 'thinking')"
						@transcribed="onTranscribed"
						@voice-error="onVoiceError"
						@toggle-markdown="showMarkdownPreview = !showMarkdownPreview"
						@send="sendMessage"
						@stop="handleStop"
					/>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, nextTick, watch, onMounted, onBeforeUnmount, defineAsyncComponent } from "vue";
import SlashMenu from "@/components/chat/SlashMenu.vue";
import ComposerPlusMenu from "@/components/chat/ComposerPlusMenu.vue";
import AttachedFilePreview from "@/components/chat/AttachedFilePreview.vue";
import InputToolbar from "@/components/chat/InputToolbar.vue";
import {
	useComposerAttachments,
	UPLOAD_ACCEPT_ATTR,
} from "@/composables/useComposerAttachments";
import { useRobotMoodStore } from "@/stores/robotMoodStore";
import { useComposerModesStore } from "@/stores/composerModesStore";
import { useChatStore } from "@/stores/chatStore";
import { useUserStore } from "@/stores/userStore";
import { useModelStore } from "@/stores/modelStore";
import { renderMarkdown, ensureHljs } from "@/utils/markdown.js";
import { useToast } from "@/composables/useToast";

// MarkdownPreviewPanel is opt-in (user clicks the preview toggle). Lazy-load
// to keep it (and the hljs it triggers) out of the eager input bundle.
const MarkdownPreviewPanel = defineAsyncComponent(
	() => import("@/components/chat/MarkdownPreviewPanel.vue"),
);

const { showError } = useToast();
const robotMoodStore = useRobotMoodStore();
const composerModesStore = useComposerModesStore();
const chatStore = useChatStore();
const userStore = useUserStore();
const modelStore = useModelStore();

const props = defineProps({
	disabled: { type: Boolean, default: false },
	isStreaming: { type: Boolean, default: false },
	context: { type: Object, default: null },
	initialMessage: { type: String, default: "" },
	interactionMode: { type: String, default: null },
});

const emit = defineEmits(["send", "file-upload", "abort", "pick-template", "browse-templates"]);

const MAX_TEXTAREA_HEIGHT = 240;

const {
	attachedFiles,
	fileInput,
	triggerFileInput,
	handleFileSelect,
	handlePaste,
	removeFile,
	clearAttachments,
} = useComposerAttachments(emit);

const message = ref("");
const textInput = ref(null);
const showMarkdownPreview = ref(false);
const slashMenuRef = ref(null);

// Sticky per-conversation composer toggles (Web search, Thinking). Held in
// composerModesStore, not a local ref, because this component is destroyed
// and recreated when composerInHero flips at first send.
const plusOpen = ref(false);
const modes = computed(() => composerModesStore.modesFor(chatStore.currentSessionId));
const webSearchAvailable = computed(() => userStore.capabilities?.features?.web_search === true);

function onMenuAttach() {
	triggerFileInput();
	plusOpen.value = false;
}

// Slash-command detection: cursor must be inside a leading "/query" token —
// i.e. the slash is at position 0 (or preceded only by a linebreak/space) and
// the query contains no whitespace. Match in any new line.
const slashMatch = computed(() => {
	const text = message.value;
	if (!text || text[0] !== "/") {
		// Support slash on a new line too (e.g. after Shift+Enter, next line starts with /)
		// but only if the *first* character of the message is `/`. We keep the trigger strict
		// to avoid firing on things like "tell me about /api".
		return null;
	}
	// Query is everything from position 1 up to the first whitespace, if any.
	const afterSlash = text.slice(1);
	const wsIdx = afterSlash.search(/\s/);
	if (wsIdx !== -1) return null;
	return afterSlash;
});

const slashOpen = computed(() => slashMatch.value !== null);
const slashQuery = computed(() => slashMatch.value || "");

const canSend = computed(
	() => !props.disabled && (message.value.trim() || attachedFiles.value.length > 0)
);

// A pending interaction card overrides the generic streaming placeholder —
// question regime routes Enter to the card's answer; approval regime routes
// it to abort-then-send (see resolveComposerRoute in the chat store).
const placeholderText = computed(() => {
	if (props.interactionMode === "question") return "Type your answer…";
	if (props.isStreaming) return "Assistant is responding — Enter queues your message";
	return "Ask me anything…";
});

const hasMarkdown = computed(() => {
	const text = message.value;
	if (!text || text.length < 2) return false;
	const patterns = [
		/\*\*.+\*\*/,
		/\*.+\*/,
		/__.+__/,
		/_.+_/,
		/~~.+~~/,
		/^#{1,6}\s/m,
		/\[.+\]\(.+\)/,
		/!\[.*\]\(.+\)/,
		/^>\s/m,
		/^[-*+]\s/m,
		/^\d+\.\s/m,
		/`[^`]+`/,
		/```[\s\S]*```/,
		/\|.+\|/,
	];
	return patterns.some((p) => p.test(text));
});

const hljsReady = ref(0);
watch(showMarkdownPreview, (open) => {
	if (open) {
		ensureHljs().then(() => {
			hljsReady.value++;
		});
	}
});

const renderedMarkdown = computed(() => {
	if (!hasMarkdown.value) return "";
	// eslint-disable-next-line no-unused-expressions
	hljsReady.value;
	return renderMarkdown(message.value);
});

watch(hasMarkdown, (present) => {
	if (!present) showMarkdownPreview.value = false;
});

watch(
	() => props.initialMessage,
	(newValue) => {
		if (newValue) {
			message.value = newValue;
			nextTick(() => {
				autoResize();
				textInput.value?.focus();
			});
		}
	}
);

function autoResize() {
	nextTick(() => {
		if (textInput.value) {
			textInput.value.style.height = "auto";
			textInput.value.style.height =
				Math.min(textInput.value.scrollHeight, MAX_TEXTAREA_HEIGHT) + "px";
		}
	});
}

function handleKeydown(event) {
	if (slashOpen.value) {
		if (event.key === "ArrowDown") {
			event.preventDefault();
			slashMenuRef.value?.move(1);
			return;
		}
		if (event.key === "ArrowUp") {
			event.preventDefault();
			slashMenuRef.value?.move(-1);
			return;
		}
		if (event.key === "Enter" && !event.shiftKey) {
			event.preventDefault();
			slashMenuRef.value?.pickActive();
			return;
		}
		if (event.key === "Escape") {
			event.preventDefault();
			message.value = "";
			autoResize();
			return;
		}
		if (event.key === "Tab") {
			event.preventDefault();
			slashMenuRef.value?.pickActive();
			return;
		}
	}

	if (event.key === "Enter" && !event.shiftKey) {
		event.preventDefault();
		sendMessage();
	}
}

function handleSlashPick(template) {
	message.value = "";
	autoResize();
	emit("pick-template", template);
}

function handleBrowseAll() {
	message.value = "";
	autoResize();
	emit("browse-templates");
}

function sendMessage() {
	if (!canSend.value) return;
	emit("send", {
		message: message.value.trim(),
		files: attachedFiles.value,
	});
	message.value = "";
	clearAttachments();
	showMarkdownPreview.value = false;
	nextTick(() => {
		if (textInput.value) textInput.value.style.height = "auto";
	});
}

function onTranscribed(text) {
	// Auto-send the transcribed text via the normal send path.
	message.value = text;
	sendMessage();
}

function onVoiceError(code) {
	const messages = {
		"permission-denied": "Microphone access denied. Enable it in your browser settings.",
		"no-mic": "No microphone found.",
		"too-short": "Didn't catch that.",
		"empty": "Didn't catch that.",
		"transcribe-failed": "Couldn't transcribe — try again or type instead.",
		"recorder-error": "Couldn't start recording — try again.",
	};
	const msg = messages[code] || "Voice error.";
	// Frappe Desk's show_alert is available when the SPA renders behind Frappe;
	// standalone, the SPA's own toast carries the message instead of dropping it.
	if (window.frappe && typeof window.frappe.show_alert === "function") {
		window.frappe.show_alert({ message: msg, indicator: code === "too-short" || code === "empty" ? "orange" : "red" });
	} else {
		showError(msg);
	}
}

function onGlobalKeydown(e) {
	if (e.ctrlKey && e.shiftKey && (e.key === " " || e.code === "Space")) {
		const t = e.target;
		const isChatInput = t === textInput.value;
		const isOtherInput = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA") && !isChatInput;
		if (isOtherInput) return;
		e.preventDefault();
		const btn = document.querySelector(".mic-btn");
		if (btn) btn.click();
	}
}

onMounted(() => document.addEventListener("keydown", onGlobalKeydown));
onBeforeUnmount(() => document.removeEventListener("keydown", onGlobalKeydown));

function handleStop() {
	emit("abort");
}
</script>

<style scoped>
/* Outer container — gradient fade below messages */
.input-area-container {
	flex-shrink: 0;
	padding: 1rem 1.5rem max(1.25rem, env(safe-area-inset-bottom, 0px));
	background: linear-gradient(to bottom, transparent 0%, var(--ql-bg) 40%);
}

@media (min-width: 768px) {
	.input-area-container {
		padding: 1rem 2.5rem max(1.25rem, env(safe-area-inset-bottom, 0px));
	}
}

@media (min-width: 1024px) {
	.input-area-container {
		padding: 1rem 4rem max(1.25rem, env(safe-area-inset-bottom, 0px));
	}
}

/* Centered composer column. Width is capped by the parent for the docked
   instance (to match the message reading column); the hero instance fills its
   wider welcome column. See ChatView .chat-area > .composer-dock-enter. */
.input-column {
	width: 100%;
	margin-inline: auto;
}

/* Wrapper positions the slash menu as an absolute popover above the input */
.input-box-wrapper {
	position: relative;
}

/* The input box itself — rectangle, two rows stacked */
.input-box {
	display: flex;
	flex-direction: column;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.875rem;
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
	overflow: hidden;
}

.input-box:focus-within {
	border-color: var(--ql-accent);
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), inset 0 0 0 1px var(--ql-accent);
}

.hidden-file-input {
	display: none;
}

/* Textarea row */
.input-textarea {
	width: 100%;
	background: transparent;
	border: none;
	outline: none;
	resize: none;
	color: var(--ql-text);
	font-size: 0.9375rem;
	line-height: 1.55;
	padding: 0.875rem 1rem 0.5rem;
	min-height: 2.75rem;
	max-height: 15rem; /* ~10 lines */
	overflow-y: auto;
	font-family: inherit;
}

.input-textarea::placeholder {
	color: var(--ql-text-muted);
}

.input-textarea:disabled {
	cursor: not-allowed;
	opacity: 0.7;
}

/* Scrollbar styling for textarea (subtle) */
.input-textarea::-webkit-scrollbar {
	width: 6px;
}
.input-textarea::-webkit-scrollbar-thumb {
	background: var(--ql-border);
	border-radius: 3px;
}

/* Keyboard hint reveal — :focus-within lives on the parent's .input-box, so the
 * reveal rule stays here. The .kbd-hint element itself is inside InputToolbar,
 * so we pierce the child's scope with :deep() to keep the hover-to-reveal hint. */
.input-box:focus-within :deep(.kbd-hint) {
	opacity: 1;
}

/* Dark-mode tweaks */
[data-theme="dark"] .input-area-container {
	background: linear-gradient(to bottom, transparent 0%, var(--ql-bg) 50%);
}

[data-theme="dark"] .input-box {
	border-color: rgba(255, 255, 255, 0.1);
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

[data-theme="dark"] .input-box:focus-within {
	border-color: var(--ql-accent);
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2), inset 0 0 0 1px var(--ql-accent);
}
</style>
