<template>
	<header class="top-bar">
		<div class="top-bar-content">
			<!-- Left Section -->
			<div class="top-bar-left">
				<button
					@click="onHamburger(() => $emit('toggle-sidebar'))"
					class="sidebar-toggle-btn"
					aria-label="Toggle navigation"
				>
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M4 6h16M4 12h16M4 18h16"
						/>
					</svg>
				</button>
				<div class="chat-title">
					<template v-if="project">
						<RouterLink
							data-test="crumb-project"
							:to="'/chat/project/' + project.name"
							class="crumb"
						>
							📁 {{ project.title }}
						</RouterLink>
						<span class="crumb-sep">/</span>
					</template>
					<input
						v-if="editing"
						ref="inputRef"
						v-model="draft"
						class="title-input"
						data-test="title-input"
						:maxlength="TITLE_MAX_LENGTH"
						:aria-label="__('Rename chat')"
						@keydown.enter.prevent="commit"
						@keydown.esc.stop.prevent="cancel"
						@blur="commit"
					/>
					<button
						v-else
						class="title-btn"
						data-test="chat-title"
						:disabled="!renamable"
						:title="renamable ? __('Rename chat') : undefined"
						@click="start"
					>
						{{ title }}
					</button>
				</div>
			</div>

			<!-- Right Section - Actions (hidden when user has no access) -->
			<div class="top-bar-actions" v-if="showActions">
				<NotificationBell />

				<!-- Model Selector -->
				<ModelSelector v-if="showModelSelector" />

				<!-- Running credit balance (all roles; billing pages are admin-only) -->
				<CreditMeter />

				<!-- Help & Feedback -->
				<button
					@click="openHelp"
					class="action-btn"
					aria-label="Help and feedback"
					title="Help & feedback"
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
						/>
					</svg>
				</button>

				<!-- New Chat Button -->
				<button @click="$emit('new-chat')" class="action-btn primary">
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M12 4v16m8-8H4"
						/>
					</svg>
					<span class="btn-text">New Chat</span>
				</button>

				<!-- Custom actions slot -->
				<slot name="actions"></slot>
			</div>
		</div>
	</header>
</template>

<script setup>
import ModelSelector from "@/components/common/ModelSelector.vue";
import CreditMeter from "@/components/chat/CreditMeter.vue";
import NotificationBell from "@/components/notifications/NotificationBell.vue";
import { useSupportStore } from "@/stores/supportStore";
import { useChatStore } from "@/stores/chatStore";
import { useNavToggle } from "@/composables/useNavToggle";
import { useInlineTitleEdit, TITLE_MAX_LENGTH } from "@/composables/useInlineTitleEdit";
import { __ } from "@/utils/i18n";

const supportStore = useSupportStore();
const chatStore = useChatStore();
const { onHamburger } = useNavToggle();

function openHelp() {
	supportStore.open({ mode: "issue", conversationId: chatStore.currentSessionId || null });
}

const props = defineProps({
	project: {
		type: Object,
		default: null,
	},
	renamable: {
		type: Boolean,
		default: false,
	},
	title: {
		type: String,
		default: "Chat",
	},
	showModelSelector: {
		type: Boolean,
		default: true,
	},
	showActions: {
		type: Boolean,
		default: true,
	},
});

const emit = defineEmits(["toggle-sidebar", "new-chat", "rename"]);

const { editing, draft, inputRef, start, commit, cancel } = useInlineTitleEdit(
	() => props.title,
	(title) => emit("rename", title)
);
</script>

<style scoped>
.top-bar {
	background: var(--ql-surface);
	border-bottom: 1px solid var(--ql-border);
	height: var(--ql-topbar-height,56px);
	flex-shrink: 0;
	position: sticky;
	top: 0;
	z-index: 20;
}

.top-bar-content {
	height: 100%;
	padding: 0 1rem;
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 1rem;
}

.top-bar-left {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	flex: 1;
	min-width: 0;
}

.top-bar-actions {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.sidebar-toggle-btn {
	flex-shrink: 0;
	padding: 0.5rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.sidebar-toggle-btn:hover {
	background-color: var(--ql-subtle);
	color: var(--ql-text);
}

.chat-title {
	font-size: 1rem;
	font-weight: 600;
	color: var(--ql-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.crumb {
	color: var(--ql-text-muted);
	text-decoration: none;
}

.crumb:hover {
	color: var(--ql-text);
}

.crumb-sep {
	margin: 0 0.375rem;
	color: var(--ql-text-muted);
}

.title-btn {
	font: inherit;
	color: inherit;
	background: none;
	border: none;
	padding: 0;
	max-width: 100%;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	cursor: text;
}

.title-btn:disabled {
	cursor: default;
}

.title-input {
	font: inherit;
	color: var(--ql-text);
	background: var(--ql-surface);
	border: 1px solid var(--ql-accent);
	border-radius: 0.25rem;
	padding: 0 0.25rem;
	min-width: 12rem;
	outline: none;
}

.action-btn {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.75rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.action-btn:hover {
	background-color: var(--ql-border-hover);
}

.action-btn.primary {
	color: white;
	background-color: var(--ql-accent);
}

.action-btn.primary:hover {
	background-color: var(--ql-accent-hover);
}

.btn-text {
	display: none;
}

@media (min-width: 640px) {
	.btn-text {
		display: inline;
	}
}
</style>
