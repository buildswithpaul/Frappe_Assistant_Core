<template>
	<div class="kb-empty">
		<div class="empty-hero">
			<FacoRobot size="sm" float show-arms />
		</div>
		<h3 class="empty-title">Your knowledge base is empty</h3>
		<p class="empty-description">
			Upload documents and FACO will use them to give you smarter, more contextual answers.
		</p>
		<button class="empty-upload-btn" @click="$emit('upload')">
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
				/>
			</svg>
			Upload your first document
		</button>
		<p class="empty-hint">Supports PDF, Markdown, and Text files up to 10 MB</p>
		<p class="empty-drop-hint">or drag and drop files anywhere on this page</p>
	</div>
</template>

<script setup>
import FacoRobot from "@/components/common/FacoRobot.vue";

defineEmits(["upload"]);
</script>

<style scoped>
.kb-empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 4rem 2rem;
	text-align: center;
	min-height: 400px;
}

.empty-hero {
	margin-bottom: 1.5rem;
}

.empty-title {
	font-size: 1.25rem;
	font-weight: 700;
	color: var(--ql-text);
	margin: 0 0 0.5rem;
}

.empty-description {
	font-size: 0.9375rem;
	color: var(--ql-text-secondary);
	max-width: 400px;
	line-height: 1.6;
	margin: 0 0 1.5rem;
}

.empty-upload-btn {
	display: inline-flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.75rem 1.5rem;
	font-size: 0.9375rem;
	font-weight: 600;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.75rem;
	cursor: pointer;
	transition: all 0.2s ease;
}

.empty-upload-btn:hover {
	background: var(--ql-accent-hover);
	transform: translateY(-1px);
	box-shadow: 0 4px 12px rgba(15, 110, 92, 0.2);
}

.empty-hint {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-top: 0.75rem;
}

.empty-drop-hint {
	margin-top: 0.375rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	opacity: 0.6;
}

.w-4 {
	width: 1rem;
	height: 1rem;
}
</style>
