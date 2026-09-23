<template>
	<div class="processing-indicator">
		<div class="processing-status">
			<span class="processing-dot"></span>
			<span class="processing-text">{{ statusMessage }}</span>
		</div>

		<!-- Tip/Quote shown after delay -->
		<transition name="fade">
			<div v-if="showTip" class="processing-tip">
				{{ currentTip }}
			</div>
		</transition>
	</div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { storeToRefs } from "pinia";
import { useChatStore } from "@/stores/chatStore";

const props = defineProps({
	blocks: {
		type: Array,
		default: () => [],
	},
	lastBlockType: {
		type: String,
		default: null,
	},
});

const chatStore = useChatStore();
const { lastActivityTime } = storeToRefs(chatStore);

// Tips and quotes collection
const tips = [
	"Tip: Use Shift+Enter for multi-line messages",
	"Tip: You can attach files for context-aware assistance",
	"Tip: Click on thinking or tool blocks to see details",
	"Tip: Use the Stop button to cancel a long-running request",
	'"The best way to predict the future is to create it." — Alan Kay',
	'"Simplicity is the ultimate sophistication." — Leonardo da Vinci',
	'"First, solve the problem. Then, write the code." — John Johnson',
	'"Any fool can write code that a computer can understand. Good programmers write code that humans can understand." — Martin Fowler',
];

// Time tracking
const elapsedSeconds = ref(0);
const currentTipIndex = ref(Math.floor(Math.random() * tips.length));
let elapsedTimer = null;
let tipRotationTimer = null;

// Contextual status message based on last block type
const statusMessage = computed(() => {
	if (!props.blocks || props.blocks.length === 0) {
		return "Processing your request...";
	}

	const lastBlock = props.blocks[props.blocks.length - 1];

	if (lastBlock.type === "thinking" && !lastBlock.isStreaming) {
		return "Analyzing results...";
	}

	if (lastBlock.type === "tool_call") {
		if (lastBlock.status === "success") {
			return "Preparing response...";
		}
		if (lastBlock.status === "error") {
			return "Handling error...";
		}
		if (lastBlock.status === "cancelled") {
			return "Processing...";
		}
	}

	return "Working on it...";
});

// Show tip after 5 seconds
const showTip = computed(() => elapsedSeconds.value >= 5);

// Current tip
const currentTip = computed(() => tips[currentTipIndex.value]);

// Start elapsed time tracking
function startElapsedTimer() {
	elapsedTimer = setInterval(() => {
		const now = Date.now();
		const lastActivity = lastActivityTime.value || now;
		elapsedSeconds.value = Math.floor((now - lastActivity) / 1000);
	}, 1000);
}

// Rotate tips every 8 seconds
function startTipRotation() {
	tipRotationTimer = setInterval(() => {
		currentTipIndex.value = (currentTipIndex.value + 1) % tips.length;
	}, 8000);
}

// Reset elapsed time when activity happens
watch(lastActivityTime, () => {
	elapsedSeconds.value = 0;
});

onMounted(() => {
	startElapsedTimer();
	startTipRotation();
});

onUnmounted(() => {
	if (elapsedTimer) {
		clearInterval(elapsedTimer);
	}
	if (tipRotationTimer) {
		clearInterval(tipRotationTimer);
	}
});
</script>

<style scoped>
.processing-indicator {
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
	padding: 0.75rem 0;
}

.processing-status {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.processing-dot {
	width: 0.5rem;
	height: 0.5rem;
	background-color: var(--ql-accent);
	border-radius: 50%;
	animation: processing-pulse 1.5s ease-in-out infinite;
}

.processing-text {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
	font-style: italic;
}

.processing-tip {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	padding-left: 1rem;
	border-left: 2px solid var(--ql-border);
	line-height: 1.5;
}

/* Animation */
@keyframes processing-pulse {
	0%,
	100% {
		opacity: 0.4;
		transform: scale(0.9);
	}
	50% {
		opacity: 1;
		transform: scale(1.1);
	}
}

/* Fade transition for tips */
.fade-enter-active,
.fade-leave-active {
	transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
	opacity: 0;
}
</style>
