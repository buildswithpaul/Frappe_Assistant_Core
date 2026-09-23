<template>
	<div class="unreachable-panel" data-test="site-unreachable-panel">
		<p class="eyebrow">Can't reach this site</p>
		<h2 class="title">Cloud chat needs a site it can call back</h2>

		<p class="message" data-test="unreachable-message">{{ message }}</p>

		<!-- Door 1: the option that always works on a local machine. -->
		<div class="door door-primary">
			<h3 class="door-title">Use the built-in MCP server</h3>
			<p class="door-text">
				Free, and no cloud account needed. Your AI client — Claude Desktop, Cursor,
				ChatGPT desktop — runs on this machine, so it reaches this site fine. You
				bring your own LLM key and keep every tool this app exposes.
			</p>
			<p class="door-hint">
				Start in <strong>Desk → FAC Admin</strong> and copy the MCP Endpoint URL.
			</p>
			<a
				class="door-cta"
				data-test="unreachable-mcp-cta"
				href="https://docs.assistantcore.cloud/getting-started/quick-start"
				target="_blank"
				rel="noopener noreferrer"
			>
				Set up the local MCP server
			</a>
		</div>

		<!-- Door 2: for anyone who can actually expose the site. -->
		<div class="door door-secondary">
			<button
				type="button"
				class="door-toggle"
				data-test="unreachable-tunnel-toggle"
				:aria-expanded="tunnelOpen ? 'true' : 'false'"
				@click="tunnelOpen = !tunnelOpen"
			>
				<span>My site can be reached publicly</span>
				<span class="chevron" :class="{ open: tunnelOpen }" aria-hidden="true">›</span>
			</button>

			<div v-if="tunnelOpen" class="tunnel-steps" data-test="unreachable-tunnel-steps">
				<ol>
					<li>
						Expose your bench through a tunnel:
						<code>cloudflared tunnel --url http://localhost:8000</code>
						(or <code>ngrok http 8000</code>).
					</li>
					<li>
						Tell Frappe its public address — add
						<code>"host_name": "https://your-tunnel-host"</code> to
						<code>sites/{{ siteName }}/site_config.json</code>. Without this step the
						site keeps reporting its local address, so registration sends that
						instead of the tunnel and fails exactly as it just did.
					</li>
					<li>
						Reload the config: <code>bench --site {{ siteName }} clear-cache</code>.
					</li>
					<li>Come back here and try again.</li>
				</ol>
				<p class="tunnel-note">
					A tunnel that shuts down later takes cloud chat down with it — we call your
					site back on every action. For anything beyond a trial, host the site
					somewhere with a stable public address.
				</p>
				<a
					class="tunnel-docs"
					data-test="unreachable-local-docs"
					href="https://docs.assistantcore.cloud/fac-chat/local-sites"
					target="_blank"
					rel="noopener noreferrer"
				>
					Full walkthrough for local and private sites
				</a>
			</div>
		</div>

		<button
			type="button"
			class="retry-link"
			data-test="unreachable-retry"
			:disabled="retrying"
			@click="$emit('retry')"
		>
			{{ retrying ? "Checking…" : "Try Again" }}
		</button>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
	// AR's own SITE_UNREACHABLE copy. It names the URL we failed to reach, so it
	// is shown verbatim rather than restated.
	message: {
		type: String,
		default: "",
	},
	retrying: {
		type: Boolean,
		default: false,
	},
});

defineEmits(["retry"]);

const tunnelOpen = ref(false);

// The SPA is served from the site itself, so the host is the site name the
// bench commands need. Falls back to a placeholder for non-browser contexts.
const siteName = computed(() => window?.location?.hostname || "your-site");
</script>

<style scoped>
.unreachable-panel {
	display: flex;
	flex-direction: column;
	align-items: stretch;
	text-align: left;
	max-width: 480px;
	width: 100%;
	margin: 0 auto;
	padding: 1.5rem 1.25rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-xl);
}

.eyebrow {
	margin: 0 0 0.35rem;
	font-size: 0.75rem;
	font-weight: 600;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	color: var(--ql-danger);
}

.title {
	margin: 0 0 0.6rem;
	font-size: 1.25rem;
	font-weight: 700;
	color: var(--ql-text);
}

.message {
	margin: 0 0 1.25rem;
	font-size: 0.875rem;
	line-height: 1.55;
	color: var(--ql-text-secondary);
}

.door {
	padding: 1rem;
	border-radius: var(--ql-radius-lg);
	border: 1px solid var(--ql-border);
}

.door-primary {
	background: var(--ql-accent-soft);
	border-color: var(--ql-accent);
	margin-bottom: 0.75rem;
}

.door-title {
	margin: 0 0 0.4rem;
	font-size: 0.9375rem;
	font-weight: 700;
	color: var(--ql-text);
}

.door-text {
	margin: 0 0 0.5rem;
	font-size: 0.8125rem;
	line-height: 1.5;
	color: var(--ql-text-secondary);
}

.door-hint {
	margin: 0 0 0.85rem;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}

.door-cta {
	display: block;
	width: 100%;
	padding: 0.6rem 1rem;
	text-align: center;
	font-size: 0.875rem;
	font-weight: 600;
	text-decoration: none;
	color: #fff;
	background: var(--ql-accent);
	border-radius: var(--ql-radius-md);
	transition: background 0.15s ease;
}

.door-cta:hover {
	background: var(--ql-accent-hover);
}

.door-secondary {
	margin-bottom: 1rem;
	padding: 0;
	overflow: hidden;
}

.door-toggle {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
	width: 100%;
	padding: 0.75rem 1rem;
	font-size: 0.875rem;
	font-weight: 600;
	text-align: left;
	color: var(--ql-text);
	background: transparent;
	border: none;
	cursor: pointer;
}

.door-toggle:hover {
	background: var(--ql-subtle);
}

.chevron {
	font-size: 1.1rem;
	color: var(--ql-text-muted);
	transition: transform 0.15s ease;
}

.chevron.open {
	transform: rotate(90deg);
}

.tunnel-steps {
	padding: 0 1rem 1rem;
	border-top: 1px solid var(--ql-border);
}

.tunnel-steps ol {
	margin: 0.75rem 0 0;
	padding-left: 1.25rem;
}

.tunnel-steps li {
	margin-bottom: 0.6rem;
	font-size: 0.8125rem;
	line-height: 1.55;
	color: var(--ql-text-secondary);
}

.tunnel-steps code {
	display: inline-block;
	padding: 0.1rem 0.35rem;
	font-family: var(--ql-font-mono);
	font-size: 0.75rem;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
	word-break: break-all;
}

.tunnel-note {
	margin: 0.75rem 0 0.85rem;
	padding: 0.6rem 0.75rem;
	font-size: 0.75rem;
	line-height: 1.5;
	color: var(--ql-text-secondary);
	background: var(--ql-gold-soft);
	border-radius: var(--ql-radius-md);
}

.tunnel-docs,
.retry-link {
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-accent);
	background: transparent;
	border: none;
	cursor: pointer;
}

.retry-link {
	align-self: center;
	padding: 0.4rem 0.75rem;
}

.retry-link:disabled {
	color: var(--ql-text-muted);
	cursor: not-allowed;
}
</style>
