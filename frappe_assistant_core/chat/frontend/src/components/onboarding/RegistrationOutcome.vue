<template>
	<!-- Shown briefly after registration -->
	<template v-if="kind === 'success'">
		<div class="success-state">
			<FacoRobot
				size="lg"
				mood="excited"
				show-arms
				show-shadow
				extra-class="robot-celebrate"
			/>

			<div class="success-content">
				<div class="success-icon">
					<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M5 13l4 4L19 7"
						/>
					</svg>
				</div>
				<h1 class="success-title">Connected!</h1>
				<p class="success-message">FACO is ready to help you.</p>
			</div>
		</div>
	</template>

	<!-- Registration is at capacity; the applicant is queued -->
	<template v-else>
		<div class="waitlist-state" data-test="waitlist-state">
			<FacoRobot size="lg" mood="attentive" show-arms show-shadow />
			<div class="waitlist-content">
				<h1 class="waitlist-title">You're on the waitlist</h1>
				<p v-if="waitlistPosition" class="waitlist-position">
					Position <strong>#{{ waitlistPosition }}</strong> in the queue
				</p>
				<p class="waitlist-message">
					Registration is at capacity right now. We'll email
					<strong>{{ ownerEmail }}</strong> the moment a slot opens — just
					click the link in that email to finish setting up.
				</p>
			</div>
		</div>
	</template>
</template>

<script setup>
import FacoRobot from "@/components/common/FacoRobot.vue";

defineProps({
	kind: {
		type: String,
		required: true,
		validator: (v) => ["success", "waitlist"].includes(v),
	},
	waitlistPosition: { type: Number, default: null },
	ownerEmail: { type: String, default: "" },
});
</script>

<style scoped>
.success-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	min-height: 100%;
	animation: success-fade-in 0.5s ease;
}

.success-content {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.5rem;
	margin-top: 1.5rem;
}

.success-icon {
	width: 3rem;
	height: 3rem;
	color: var(--ql-success);
	background: rgba(34, 197, 94, 0.1);
	border-radius: 50%;
	padding: 0.5rem;
	animation: success-pop 0.5s ease 0.2s both;
}

.success-icon svg {
	width: 100%;
	height: 100%;
}

.success-title {
	font-family: var(--ql-font-serif);
	font-size: 1.75rem;
	font-weight: 700;
	color: var(--ql-success);
	animation: success-slide-up 0.5s ease 0.3s both;
}

.success-message {
	font-size: 1rem;
	color: var(--ql-text-muted);
	animation: success-slide-up 0.5s ease 0.4s both;
}

.waitlist-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	min-height: 100%;
	animation: success-fade-in 0.5s ease;
}

.waitlist-content {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.5rem;
	margin-top: 1.5rem;
	max-width: 28rem;
	text-align: center;
}

.waitlist-title {
	font-family: var(--ql-font-serif);
	font-size: 1.75rem;
	font-weight: 700;
	color: var(--ql-text);
}

.waitlist-position {
	font-size: 1rem;
	color: var(--ql-accent);
}

.waitlist-message {
	font-size: 0.9375rem;
	color: var(--ql-text-muted);
	line-height: 1.5;
}

/* Robot celebrate animation — preserves the .faco-robot-lg base scale(1.2).
   If we only wrote scale(1) here, the keyframe would override the base
   transform and the robot would shrink mid-animation, snapping back at the
   end. Multiplying through 1.2 keeps the size coherent. */
.robot-celebrate {
	animation: robot-celebrate 1s ease-in-out;
}

@keyframes robot-celebrate {
	0%,
	100% {
		transform: scale(1.2) rotate(0deg);
	}
	25% {
		transform: scale(1.32) rotate(-5deg);
	}
	50% {
		transform: scale(1.38) rotate(5deg);
	}
	75% {
		transform: scale(1.32) rotate(-3deg);
	}
}

@keyframes success-fade-in {
	from {
		opacity: 0;
	}
	to {
		opacity: 1;
	}
}

@keyframes success-pop {
	from {
		transform: scale(0);
		opacity: 0;
	}
	to {
		transform: scale(1);
		opacity: 1;
	}
}

@keyframes success-slide-up {
	from {
		transform: translateY(20px);
		opacity: 0;
	}
	to {
		transform: translateY(0);
		opacity: 1;
	}
}
</style>
