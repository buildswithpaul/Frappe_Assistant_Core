<script setup>
// The Desk widget's Spotlight: the same content as SpotlightModal, as a card inside the open
// panel. The widget shares the page with the user's Desk form, so it never overlays it.
import { computed, ref, watch } from "vue";
import { renderNotificationMarkdown } from "@/utils/markdown";
import SpotlightMedia from "./SpotlightMedia.vue";
import SpotlightQuotaArt from "./SpotlightQuotaArt.vue";

const props = defineProps({ content: { type: Object, default: null } });
const emit = defineEmits(["primary", "secondary", "dismiss"]);

const mediaFailed = ref(false);
const bodyHtml = computed(() => (props.content?.body ? renderNotificationMarkdown(props.content.body) : ""));
const hasMedia = computed(() => !!props.content?.media && !mediaFailed.value);

watch(
	() => props.content?.id,
	() => (mediaFailed.value = false)
);
</script>

<template>
	<section
		v-if="content"
		class="spot-card"
		data-test="spotlight-card"
		role="region"
		:aria-label="content.title"
	>
		<div v-if="hasMedia" class="spot-visual">
			<SpotlightQuotaArt v-if="content.media.art === 'quota'" :percent="content.threshold || 80" />
			<SpotlightMedia v-else :media="content.media" @failed="mediaFailed = true" />
		</div>
		<div class="spot-text">
			<span v-if="content.eyebrow" class="spot-eyebrow">{{ content.eyebrow }}</span>
			<h3 class="spot-title">{{ content.title }}</h3>
			<div v-if="bodyHtml" class="spot-body" v-html="bodyHtml"></div>
			<ul v-if="content.highlights?.length" class="spot-highlights">
				<li v-for="(h, i) in content.highlights" :key="i" data-test="spotlight-highlight">
					<span class="spot-hl-icon" aria-hidden="true">✦</span><span>{{ h }}</span>
				</li>
			</ul>
			<div class="spot-actions">
				<button class="spot-primary" data-test="spotlight-primary" @click="emit('primary')">
					{{ content.primary.label }}
				</button>
				<button
					v-if="content.secondary"
					class="spot-secondary"
					data-test="spotlight-secondary"
					@click="emit('secondary')"
				>
					{{ content.secondary.label }}
				</button>
			</div>
		</div>
		<button class="spot-close" data-test="spotlight-dismiss" aria-label="Dismiss" @click="emit('dismiss')">
			✕
		</button>
	</section>
</template>

<style scoped>
.spot-card {
	position: relative;
	margin: 12px 12px 4px;
	border: 1px solid var(--ql-border);
	border-radius: 14px;
	background: var(--ql-surface);
	color: var(--ql-text);
	overflow: hidden;
}
.spot-visual {
	height: 96px;
	overflow: hidden;
}
.spot-text {
	display: flex;
	flex-direction: column;
	gap: 8px;
	padding: 12px 14px 14px;
}
.spot-eyebrow {
	align-self: flex-start;
	padding: 3px 8px;
	border-radius: 999px;
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
	font-size: 11px;
	font-weight: 600;
}
.spot-title {
	margin: 0;
	padding-right: 24px;
	font-family: var(--ql-font-display, inherit);
	font-size: 17px;
	line-height: 1.25;
	font-weight: 600;
	color: var(--ql-text);
}
.spot-body {
	font-size: 13px;
	line-height: 1.5;
	color: var(--ql-text-muted);
}
.spot-body :deep(p) { margin: 0 0 6px; }
.spot-body :deep(p:last-child) { margin-bottom: 0; }
.spot-body :deep(a) { color: var(--ql-accent); }
.spot-body :deep(strong) { color: var(--ql-text); }
.spot-highlights {
	list-style: none;
	margin: 0;
	padding: 0;
	border: 1px solid var(--ql-border);
	border-radius: 10px;
	overflow: hidden;
}
.spot-highlights li {
	display: flex;
	gap: 8px;
	align-items: flex-start;
	padding: 6px 10px;
	font-size: 12.5px;
	color: var(--ql-text);
}
.spot-highlights li + li { border-top: 1px solid var(--ql-border); }
.spot-hl-icon { color: var(--ql-accent); }
.spot-actions {
	display: flex;
	gap: 8px;
}
.spot-primary,
.spot-secondary {
	flex: 1;
	padding: 8px 12px;
	border: 0;
	border-radius: 10px;
	font-size: 13px;
	font-weight: 600;
	cursor: pointer;
}
.spot-primary { background: var(--ql-text); color: var(--ql-bg); }
.spot-primary:hover { opacity: 0.9; }
.spot-secondary { background: var(--ql-subtle); color: var(--ql-text-secondary); }
.spot-secondary:hover { color: var(--ql-text); }
.spot-primary:focus-visible,
.spot-secondary:focus-visible,
.spot-close:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
}
.spot-close {
	position: absolute;
	top: 8px;
	right: 8px;
	width: 28px;
	height: 28px;
	border: 0;
	border-radius: 50%;
	background: var(--ql-surface);
	color: var(--ql-text);
	font-size: 13px;
	cursor: pointer;
	box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}
</style>
