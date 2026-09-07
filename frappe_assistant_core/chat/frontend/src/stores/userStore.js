import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

export const useUserStore = defineStore("user", () => {
	// State
	const user = ref(null);
	const isLoading = ref(false);
	const isAdmin = ref(false);
	const quotaInfo = ref(null);
	// The caller's own credit cap, when their admin set one. A capped member is
	// blocked by this — not by the team pool in `quotaInfo` — so the meter has
	// to track it separately. Null until loaded, or when AR is unreachable.
	const myCreditStatus = ref(null);
	const registrationStatus = ref("checking"); // checking | ready | not_registered | no_role | disabled | error

	// Per-user authentication state
	const userAuthStatus = ref(null); // Full auth status from AR
	const mcpServers = ref([]); // User's MCP server configurations
	const isUserSetupComplete = ref(false); // true when user can use streaming

	// Backend capabilities
	const capabilities = ref(null);
	const billingEnabled = ref(true); // default true for backward compat
	const memoryEnabled = ref(false); // default false — no onboarding without memory app
	const workflowsEnabled = ref(false); // default false — no workflows without workflows app
	const privacyConsentComplete = ref(false); // default false — must complete privacy consent screen

	// AR's terms gate. Blocks stream_chat AND list_available_models, so this is
	// app-level rather than a model-picker concern. Defaults to "not blocked":
	// the backend already fails soft on an unreachable AR, and walling off a
	// working site over a lookup blip is worse than the clear error AR returns
	// on the next real request.
	const termsState = ref({ acceptance_required: false, can_accept: false });

	// App-level zero-retention flag. Not a capability — arrives on the first
	// stream_start socket event of the session (capabilities can't carry a
	// per-app flag). Read-only display in PrivacySettings.
	const zeroRetention = ref(false);

	// Pre-fetched data from initialize_spa (consumed once by ChatView)
	const _initialSessions = ref(null);

	// Getters
	const isAuthenticated = computed(() => !!user.value && user.value !== "Guest");
	const userInitial = computed(() => {
		if (!user.value) return "?";
		return user.value.charAt(0).toUpperCase();
	});

	// Check if user needs to complete setup (connect account)
	const needsUserSetup = computed(() => {
		// Site must be registered first
		if (registrationStatus.value !== "ready") return false;
		// If we haven't checked auth status yet, assume setup needed
		// (this prevents showing chat UI before auth check completes)
		if (!userAuthStatus.value) return true;
		// User needs setup if not ready for streaming
		return !userAuthStatus.value.ready;
	});

	// Check if user needs to reconnect (tokens expired)
	const needsReconnect = computed(() => {
		return userAuthStatus.value?.needs_reconnect || false;
	});

	// AR is refusing gated features until the tenant re-accepts terms. Only
	// meaningful once the site itself is registered — an unregistered site has
	// no tenant to accept for, and must finish onboarding first.
	const termsAcceptanceRequired = computed(() => {
		if (registrationStatus.value !== "ready") return false;
		return termsState.value?.acceptance_required === true;
	});

	// Marketplace user-publishing kill switch. When `true`, regular users may
	// publish their workflows / upload templates to the marketplace. When
	// `false` (default), the publish/upload UI is hidden. Backend wrappers
	// (publish_workflow, upload_listing_from_json) gate on the same flag —
	// this is purely a UX hide so users don't see buttons that do nothing.
	const userPublishingEnabled = computed(() => {
		return capabilities.value?.marketplace?.user_publishing_enabled === true;
	});

	// Actions
	let inflight = null;

	async function loadUser() {
		try {
			isLoading.value = true;
			registrationStatus.value = "checking";
			const result = await api.user.getCurrent();
			if (result) {
				user.value = result.user;
				isAdmin.value = result.is_admin || false;
				registrationStatus.value = result.status || "ready";
			}
		} catch (err) {
			logger.error("Failed to load user:", err);
			registrationStatus.value = "error";
		} finally {
			isLoading.value = false;
		}
	}

	/**
	 * Resolve once we actually know who this is.
	 *
	 * `isAdmin` starts false and is only true after `loadUser` returns, so
	 * anything that reads it synchronously on a cold load — a router guard,
	 * for one — sees a non-admin and acts on it. That never showed while every
	 * admin page was reached by in-app navigation, with the store long since
	 * populated; it bites on a deep link, such as the return from checkout.
	 *
	 * Shares one in-flight request rather than racing App.vue's own load.
	 */
	function ensureLoaded() {
		if (registrationStatus.value !== "checking" && !isLoading.value) {
			return Promise.resolve();
		}
		if (!inflight) {
			inflight = loadUser().finally(() => {
				inflight = null;
			});
		}
		return inflight;
	}

	async function refreshRegistrationStatus() {
		try {
			const result = await api.user.getCurrent();
			if (result) {
				registrationStatus.value = result.status || "ready";
				isAdmin.value = result.is_admin || false;
			}
		} catch (err) {
			logger.error("Failed to refresh registration status:", err);
		}
	}

	/**
	 * Clear the terms gate locally after a successful acceptance.
	 *
	 * AR is authoritative and re-validates the version on accept, so a local
	 * clear is safe: if acceptance did not really land, the next gated request
	 * fails and the next boot re-raises the gate.
	 */
	function clearTermsGate() {
		termsState.value = { ...termsState.value, acceptance_required: false, error_code: null };
	}

	async function loadQuota() {
		try {
			const result = await api.billing.getQuotaStatus();
			if (result) {
				quotaInfo.value = result;
			}
		} catch (err) {
			logger.error("Failed to load quota:", err);
		}
	}

	/**
	 * Load the caller's own credit cap so the meter can show what will actually
	 * block them. Fails soft: with no result the meter falls back to the team
	 * pool, which is the right number for members who share it.
	 */
	async function loadMyCreditStatus() {
		try {
			const result = await api.users.getMyCreditStatus();
			myCreditStatus.value = result && !result.error ? result : null;
		} catch (err) {
			logger.warn("Failed to load personal credit status:", err);
			myCreditStatus.value = null;
		}
	}

	/**
	 * Fold the counters that ride on stream_complete into the cached quota so
	 * the credit meter moves as the user chats. The relay reads them from the
	 * same snapshot loadQuota() would fetch, so this needs no extra request.
	 * A total of -1 means unlimited; leave the cache alone in that case.
	 *
	 * `quota_used`/`quota_total` are tenant-wide. A capped member's meter must
	 * never inherit them, so this turn's `credits_used` is folded into the
	 * personal counter on its own — same event, separate scope.
	 */
	function applyQuotaFromStream({ quota_used, quota_total, quota_remaining, credits_used }) {
		const spent = Number(credits_used) || 0;
		if (spent > 0 && myCreditStatus.value?.has_individual_limit) {
			myCreditStatus.value = {
				...myCreditStatus.value,
				credits_used_this_month:
					Number(myCreditStatus.value.credits_used_this_month || 0) + spent,
			};
		}

		if (quota_total === undefined || quota_total === null || quota_total <= 0) return;
		const used = Number(quota_used) || 0;
		quotaInfo.value = {
			...(quotaInfo.value || {}),
			quota_total,
			quota_used: used,
			quota_remaining:
				quota_remaining !== undefined && quota_remaining !== null
					? quota_remaining
					: Math.max(0, quota_total - used),
			percentage_used: quota_total ? Math.min(100, (used / quota_total) * 100) : 0,
		};
	}

	/**
	 * Check user's per-user authentication status with AR.
	 * This determines if the user can use FACO streaming.
	 */
	async function checkUserAuth() {
		try {
			const result = await api.user.getAuthStatus();
			userAuthStatus.value = result;

			if (result.success) {
				isUserSetupComplete.value = result.ready;
				return result.ready;
			}

			isUserSetupComplete.value = false;
			return false;
		} catch (err) {
			logger.error("Failed to check user auth status:", err);
			userAuthStatus.value = { success: false, error: err.message };
			isUserSetupComplete.value = false;
			return false;
		}
	}

	/**
	 * Connect user's account to FACO (register + connect MCP server).
	 * This is the main onboarding action for users.
	 */
	async function connectAccount() {
		try {
			isLoading.value = true;

			// Connect FAC MCP server (this also registers the user if needed)
			const result = await api.user.connectFACServer();

			if (result.success) {
				// Refresh auth status
				await checkUserAuth();
				return { success: true, message: result.message };
			}

			// AR enriches "not authorized to add users" / seat-limit errors
			// with tenant_owner_user_id so we can render a mailto link
			// instead of leaving the blocked admin guessing who to contact.
			return {
				success: false,
				error: result.error,
				tenantOwnerUserId: result.tenant_owner_user_id || null,
			};
		} catch (err) {
			logger.error("Failed to connect account:", err);
			return { success: false, error: err.message };
		} finally {
			isLoading.value = false;
		}
	}

	/**
	 * Load user's MCP server configurations.
	 */
	async function loadMCPServers() {
		try {
			const result = await api.user.getMCPServers();
			if (result.success) {
				mcpServers.value = result.mcp_servers || [];
			}
		} catch (err) {
			logger.error("Failed to load MCP servers:", err);
		}
	}

	/**
	 * Reconnect an MCP server (refresh tokens).
	 */
	async function reconnectServer(serverName = "Main Frappe Site") {
		try {
			isLoading.value = true;
			const result = await api.user.reconnectServer(serverName);

			if (result.success) {
				// Refresh auth status and servers in parallel
				await Promise.all([checkUserAuth(), loadMCPServers()]);
				return { success: true, message: result.message };
			}

			return { success: false, error: result.error };
		} catch (err) {
			logger.error("Failed to reconnect server:", err);
			return { success: false, error: err.message };
		} finally {
			isLoading.value = false;
		}
	}

	/**
	 * Disconnect an MCP server.
	 */
	async function disconnectServer(serverName = "Main Frappe Site") {
		try {
			isLoading.value = true;
			const result = await api.user.disconnectServer(serverName);

			if (result.success) {
				// Refresh auth status and servers in parallel
				await Promise.all([checkUserAuth(), loadMCPServers()]);
				return { success: true, message: result.message };
			}

			return { success: false, error: result.error };
		} catch (err) {
			logger.error("Failed to disconnect server:", err);
			return { success: false, error: err.message };
		} finally {
			isLoading.value = false;
		}
	}

	/**
	 * Load backend capabilities including billing availability.
	 */
	async function loadCapabilities() {
		try {
			const result = await api.capabilities.get();
			capabilities.value = result;
			billingEnabled.value = result?.features?.billing !== false;
			memoryEnabled.value = result?.features?.memory === true;
			workflowsEnabled.value = result?.features?.workflows === true;
			return result;
		} catch (err) {
			logger.warn("Failed to load capabilities:", err);
			// Default to true if capabilities call fails (backward compat)
			billingEnabled.value = true;
			memoryEnabled.value = false;
			workflowsEnabled.value = false;
			return null;
		}
	}

	async function init() {
		// Single combined endpoint — replaces 4 sequential calls with 1 request.
		// The backend parallelizes AR calls via ThreadPoolExecutor.
		try {
			isLoading.value = true;
			registrationStatus.value = "checking";

			const data = await api.init.initialize();

			if (!data) {
				registrationStatus.value = "error";
				return;
			}

			// Hydrate access state
			const access = data.access;
			user.value = access.user;
			isAdmin.value = access.is_admin || false;
			registrationStatus.value = access.status || "ready";

			// Hydrate quota
			if (data.quota) {
				quotaInfo.value = data.quota;
			}

			// Hydrate capabilities
			if (data.capabilities) {
				capabilities.value = data.capabilities;
				billingEnabled.value = data.capabilities?.features?.billing !== false;
				memoryEnabled.value = data.capabilities?.features?.memory === true;
				workflowsEnabled.value = data.capabilities?.features?.workflows === true;
			}

			// Hydrate privacy consent state from preferences
			if (access.preferences) {
				privacyConsentComplete.value =
					access.preferences.privacy_consent_complete || false;
			}

			// Hydrate user auth
			if (data.user_auth) {
				userAuthStatus.value = data.user_auth;
				isUserSetupComplete.value = data.user_auth.ready || false;
			}

			// Hydrate AR terms gate
			if (data.terms) {
				termsState.value = data.terms;
			}

			// Store pre-fetched sessions for ChatView to consume
			_initialSessions.value = data.sessions;

			// Off the critical path: the meter renders from the hydrated team
			// quota straight away and narrows to the personal cap once this
			// lands, so boot never waits on the extra AR round trip.
			loadMyCreditStatus();
		} catch (err) {
			logger.error("Failed to initialize:", err);
			registrationStatus.value = "error";
		} finally {
			isLoading.value = false;
		}
	}

	/**
	 * Set the app-level zero-retention flag. Called from the stream_start
	 * socket handler when the event carries `zero_retention`.
	 */
	function setZeroRetention(v) {
		zeroRetention.value = !!v;
	}

	/**
	 * Get and clear pre-fetched sessions (one-time consumption by ChatView).
	 */
	function getAndClearInitialSessions() {
		const data = _initialSessions.value;
		_initialSessions.value = null;
		return data;
	}

	return {
		// State
		user,
		isLoading,
		isAdmin,
		quotaInfo,
		myCreditStatus,
		registrationStatus,
		userAuthStatus,
		mcpServers,
		isUserSetupComplete,
		capabilities,
		billingEnabled,
		memoryEnabled,
		workflowsEnabled,
		privacyConsentComplete,
		zeroRetention,
		termsState,

		// Getters
		termsAcceptanceRequired,
		isAuthenticated,
		userInitial,
		needsUserSetup,
		needsReconnect,
		userPublishingEnabled,

		// Actions
		loadUser,
		ensureLoaded,
		loadQuota,
		loadMyCreditStatus,
		applyQuotaFromStream,
		refreshRegistrationStatus,
		checkUserAuth,
		connectAccount,
		loadMCPServers,
		reconnectServer,
		disconnectServer,
		loadCapabilities,
		setZeroRetention,
		clearTermsGate,
		init,
		getAndClearInitialSessions,
	};
});
