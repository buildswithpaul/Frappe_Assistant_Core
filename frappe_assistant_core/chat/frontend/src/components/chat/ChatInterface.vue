<template>
	<div class="ql-chat-doc">
		<template v-for="(message, index) in messages" :key="index">
			<!-- Context Summarized Divider -->
			<div v-if="message.role === 'divider'" class="context-divider">
				<div class="divider-line"></div>
				<span class="divider-text">{{ message.content }}</span>
				<div class="divider-line"></div>
			</div>

			<!-- Regular Message Bubble -->
			<MessageBubble
				v-else
				:message="message"
				:message-index="index"
				:is-streaming="isStreaming && index === lastAssistantIndex"
				:is-latest="index === lastAssistantIndex"
				@toggle-block="(msgIdx, blockId) => $emit('toggleBlock', msgIdx, blockId)"
				@approve="(blockId, responses) => $emit('approve', blockId, responses)"
				@reject="(blockId, responses) => $emit('reject', blockId, responses)"
				@preview-document="onPreviewDocument"
				@continue="(messageId) => $emit('continue', messageId)"
				@pin="(messageId) => $emit('pin', messageId)"
				@unqueue="(id) => $emit('unqueue', id)"
			/>
		</template>

		<!-- Document Preview: opens when user clicks a citation pill's "Open
         document" link or a source card's Open button. DocumentPreviewPanel
         auto-fetches via documents.getContentUrl when given just document_id.
         Non-critical decorative fields (file_size_mb, visibility, is_owner)
         render as empty when absent — no extra fetch required. -->
		<DocumentPreviewPanel v-if="previewDoc" :doc="previewDoc" @close="previewDoc = null" />
	</div>
</template>

<script setup>
import { ref, computed } from "vue";
import MessageBubble from "./MessageBubble.vue";
import DocumentPreviewPanel from "@/components/knowledge/DocumentPreviewPanel.vue";
import { api } from "@/api/client";

const props = defineProps({
	messages: {
		type: Array,
		default: () => [],
	},
	isStreaming: {
		type: Boolean,
		default: false,
	},
});

defineEmits(["toggleBlock", "approve", "reject", "continue", "pin", "unqueue"]);

// The active turn's own index, not "last item in the array" — a queued
// message (or a context-summary divider) can trail the live assistant
// bubble, and streaming/continue affordances must stay pinned to it.
const lastAssistantIndex = computed(() => {
	for (let i = props.messages.length - 1; i >= 0; i--) {
		if (props.messages[i]?.role === "assistant") return i;
	}
	return -1;
});

const previewDoc = ref(null);

async function onPreviewDocument(sourceItem) {
	if (!sourceItem) return;

	// Generated documents (PDFs from generate_document) carry only file_url —
	// they live in Frappe's File doctype, not AR Document, so api.documents.get
	// would 404. Hand them straight to the preview panel which knows to fall
	// back to file_url when document_id is absent.
	if (!sourceItem.document_id && sourceItem.file_url) {
		previewDoc.value = {
			file_url: sourceItem.file_url,
			file_name: sourceItem.file_name,
			document_type: sourceItem.document_type || "PDF",
		};
		return;
	}

	if (!sourceItem.document_id) return;

	try {
		const doc = await api.documents.get(sourceItem.document_id);
		previewDoc.value = doc;
	} catch {
		// Fallback: use the partial info we have from the sources payload
		previewDoc.value = {
			document_id: sourceItem.document_id,
			document_type: sourceItem.document_type,
			file_name: sourceItem.document_name,
		};
	}
}
</script>

<style scoped>
/* Single centered reading column (Quiet Ledger §3.1) */
.ql-chat-doc {
	max-width: var(--ql-read-width);
	width: 100%;
	margin: 0 auto;
	padding: 22px var(--ql-read-pad-x) 32px;
	font-family: var(--ql-font-ui);
}

.context-divider {
	display: flex;
	align-items: center;
	gap: 12px;
	margin: 24px 0;
	user-select: none;
}

.divider-line {
	flex: 1;
	height: 1px;
	background: var(--ql-border);
}

.divider-text {
	font-size: 12px;
	color: var(--ql-text-muted);
	white-space: nowrap;
}
</style>
