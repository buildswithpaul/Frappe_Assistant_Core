<template>
	<div class="file-drop-overlay" data-test="file-drop-overlay" aria-hidden="true">
		<div class="file-drop-card">
			<svg class="file-drop-icon" viewBox="0 0 24 24" width="28" height="28" fill="none">
				<path
					d="M21 11.5 12.6 19.9a5.5 5.5 0 0 1-7.8-7.8l8.5-8.5a3.7 3.7 0 0 1 5.2 5.2l-8.5 8.5a1.8 1.8 0 0 1-2.6-2.6l7.8-7.8"
					stroke="currentColor"
					stroke-width="1.8"
					stroke-linecap="round"
					stroke-linejoin="round"
				/>
			</svg>
			<span class="file-drop-title">Drop files to attach</span>
			<span class="file-drop-hint">PDF, images, CSV, Excel, text, JSON or XML</span>
		</div>
	</div>
</template>

<style scoped>
/* Covers the chat area (its parent is position: relative) while files are dragged over it.
   pointer-events: none keeps the drag events on the area underneath, which owns them. */
.file-drop-overlay {
	position: absolute;
	inset: 0;
	z-index: 50;
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 16px;
	background: color-mix(in srgb, var(--ql-bg) 82%, transparent);
	pointer-events: none;
}
.file-drop-card {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 6px;
	padding: 28px 36px;
	border: 2px dashed var(--ql-accent);
	border-radius: 14px;
	background: var(--ql-surface);
	color: var(--ql-text);
	text-align: center;
}
.file-drop-icon {
	color: var(--ql-accent);
}
.file-drop-title {
	font-size: 16px;
	font-weight: 600;
}
.file-drop-hint {
	font-size: 13px;
	color: var(--ql-text-muted);
}
</style>
