<template>
	<div
		class="faco-robot"
		:class="[sizeClass, { 'robot-float': float }, extraClass]"
		:data-mood="effectiveMood"
		:data-track="track ? '1' : null"
		:style="trackStyle"
	>
		<div class="robot-antenna">
			<div class="robot-antenna-tip"></div>
		</div>
		<div v-if="showArms" class="robot-arm robot-arm-left"></div>
		<div v-if="showArms" class="robot-arm robot-arm-right"></div>
		<div class="robot-head">
			<div class="robot-screen">
				<div class="robot-brow robot-brow-left"></div>
				<div class="robot-brow robot-brow-right"></div>
				<div class="robot-eye robot-eye-left"></div>
				<div class="robot-eye robot-eye-right"></div>
				<div class="robot-mouth"></div>
			</div>
		</div>
		<div v-if="showBody" class="robot-body"></div>
		<div v-if="showShadow" class="robot-shadow"></div>
	</div>
</template>

<script>
// Module-level ref count for the global mousemove listener.
// Multiple FacoRobot instances with track=true share one listener.
let _trackingRefCount = 0;
let _moveHandler = null;
</script>

<script setup>
import { computed, onBeforeUnmount, onMounted } from "vue";
import { storeToRefs } from "pinia";
import { useRobotMoodStore } from "@/stores/robotMoodStore";

const props = defineProps({
	// Size variant: xs | sm | md | lg
	size: { type: String, default: "md" },
	// Override mood (e.g. message-bubble avatars freeze a mood). When set,
	// the global mood store is ignored.
	mood: { type: String, default: null },
	// Pin to "idle" regardless of global signals. Used for static decorative
	// renders like the auth-loading splash.
	staticIdle: { type: Boolean, default: false },
	// Animate floating up/down (the existing robot-float class).
	float: { type: Boolean, default: false },
	// Render the body block. Some sites (header brand mark) only want the head.
	showBody: { type: Boolean, default: true },
	// Render the arms. Off by default because most sites only show the head.
	showArms: { type: Boolean, default: false },
	// Render the soft shadow underneath.
	showShadow: { type: Boolean, default: false },
	// Apply cursor pupil tracking. Only meaningful on the prominent
	// welcome/onboarding robot — multiple tracking robots on one screen
	// look comical.
	track: { type: Boolean, default: false },
	// Pass-through wrapper class for site-specific tweaks
	extraClass: { type: String, default: "" },
});

const store = useRobotMoodStore();
const { activeMood, eyeX, eyeY } = storeToRefs(store);

const sizeClass = computed(() => `faco-robot-${props.size}`);

const effectiveMood = computed(() => {
	if (props.staticIdle) return "idle";
	if (props.mood) return props.mood;
	return activeMood.value;
});

const trackStyle = computed(() => {
	if (!props.track) return undefined;
	return {
		"--eye-x": `${eyeX.value}px`,
		"--eye-y": `${eyeY.value}px`,
	};
});

// Global mousemove handler — install once per page, even if multiple
// FacoRobot instances mount with track=true. The reference count and
// handler reference live at module scope (declared in the plain <script>
// block above) so they're shared across instances.

function _onMouseMove(event) {
	const x = event.clientX / window.innerWidth - 0.5; // -0.5..0.5
	const y = event.clientY / window.innerHeight - 0.5;
	store.setEyeOffset(x * 3, y * 3); // scale into the clamp range
}

function _attachTracking() {
	if (typeof window === "undefined") return;
	if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
	if (_trackingRefCount === 0) {
		_moveHandler = _onMouseMove;
		window.addEventListener("mousemove", _moveHandler, { passive: true });
	}
	_trackingRefCount++;
}

function _detachTracking() {
	if (typeof window === "undefined") return;
	_trackingRefCount = Math.max(0, _trackingRefCount - 1);
	if (_trackingRefCount === 0 && _moveHandler) {
		window.removeEventListener("mousemove", _moveHandler);
		_moveHandler = null;
	}
}

onMounted(() => {
	if (props.track) _attachTracking();
});

onBeforeUnmount(() => {
	if (props.track) _detachTracking();
});
</script>
