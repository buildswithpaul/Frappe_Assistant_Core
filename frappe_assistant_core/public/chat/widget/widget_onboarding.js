// Frappe Assistant Copilot - Powered by FAC Cloud - Widget Onboarding Module
// Simplified: all onboarding happens in the SPA. Widget just shows a redirect screen.

/**
 * Widget Onboarding Module
 * Shows a "Complete setup" screen that redirects to the SPA for all onboarding.
 * The widget only shows the chat interface when setup + consent are fully complete.
 */
window.FACOWidgetOnboarding = {
	/**
	 * Show setup-required screen with a button to open the SPA.
	 * Replaces all previous inline onboarding (registration, user connect, onboarding chat).
	 *
	 * @param {Object} widget - Widget instance
	 * @param {'not_registered'|'needs_setup'|'needs_consent'} context - Why setup is needed
	 */
	show_setup_required(widget, context) {
		const $messages = widget.$widget.find(".faco-messages");
		const $inputArea = widget.$widget.find(".faco-input-area");

		// Hide chat elements
		$inputArea.hide();

		const messages = {
			not_registered: {
				title: __("Welcome to FACO!"),
				subtitle: __("Your AI copilot for Frappe and ERPNext"),
				admin_action: __("Get Started Free"),
				admin_hint: __("Opens FACO Assistant to complete setup."),
				no_admin: __("Please ask your administrator to enable FACO for this site."),
			},
			needs_setup: {
				title: __("Connect Your Account"),
				subtitle: __("Your site is connected. Complete setup to start chatting."),
				admin_action: __("Complete Setup"),
				admin_hint: __("Opens FACO Assistant to connect your account."),
			},
			needs_consent: {
				title: __("Almost There!"),
				subtitle: __("Complete a quick setup to start chatting."),
				admin_action: __("Complete Setup"),
				admin_hint: __("Takes less than a minute."),
			},
		};

		const msg = messages[context] || messages.needs_consent;
		// Connecting the site is the only step here that belongs to an admin.
		// The other two belong to the person in front of us: needs_setup is
		// reached only when can_use is true, and can_use IS the membership
		// check, so they already hold a seat; consent is their own to give.
		// Gating those on the System Manager role told real members to go ask
		// their administrator while the SPA offered them the connect screen.
		const showButton = widget.is_admin || context !== "not_registered";

		const html = `
			<div class="faco-onboarding">
				<div class="faco-onboarding-header">
					<div class="faco-robot faco-robot-large">
						<div class="robot-antenna">
							<div class="robot-antenna-tip"></div>
						</div>
						<div class="robot-arm robot-arm-left"></div>
						<div class="robot-arm robot-arm-right"></div>
						<div class="robot-head">
							<div class="robot-screen">
								<div class="robot-brow robot-brow-left"></div>
								<div class="robot-brow robot-brow-right"></div>
								<div class="robot-eye robot-eye-left"></div>
								<div class="robot-eye robot-eye-right"></div>
								<div class="robot-mouth"></div>
							</div>
						</div>
						<div class="robot-body"></div>
					</div>
					<h2>${msg.title}</h2>
					<p>${msg.subtitle}</p>
				</div>

				${
					showButton
						? `
					<div class="faco-setup-section">
						<button class="btn btn-primary btn-lg faco-setup-btn">
							${msg.admin_action}
						</button>
						<p class="faco-setup-hint">${msg.admin_hint}</p>
					</div>
				`
						: `
					<div class="faco-contact-admin">
						<p>${msg.no_admin}</p>
					</div>
				`
				}
			</div>
		`;

		$messages.html(html);

		if (showButton) {
			widget.$widget.find(".faco-setup-btn").on("click", () => {
				this.open_spa();
			});
		}
	},

	/**
	 * Open the SPA for onboarding.
	 */
	open_spa() {
		window.open("/copilot", "_blank");
	},

	/**
	 * Check if the current user has completed per-user AR registration.
	 * @param {Object} widget - Widget instance
	 */
	async check_user_auth(widget) {
		try {
			const response = await frappe.call({
				method: "frappe_assistant_core.chat.api.auth.get_user_auth_status",
				type: "GET",
			});
			const result = response.message;
			if (result && result.success && result.ready) {
				widget.user_setup_complete = true;
			} else {
				widget.user_setup_complete = false;
			}
		} catch (error) {
			FACOLogger.warn("Failed to check user auth status:", error);
			widget.user_setup_complete = false;
		}
	},

	/**
	 * Transition to the normal chat interface after all setup is complete.
	 * @param {Object} widget - Widget instance
	 */
	show_chat_interface(widget) {
		const $messages = widget.$widget.find(".faco-messages");
		const $inputArea = widget.$widget.find(".faco-input-area");

		$messages.empty();

		$messages.html(`
			<div class="faco-welcome">
				<div class="faco-avatar">
					<div class="faco-robot faco-robot-welcome">
						<div class="robot-antenna">
							<div class="robot-antenna-tip"></div>
						</div>
						<div class="robot-arm robot-arm-left"></div>
						<div class="robot-arm robot-arm-right"></div>
						<div class="robot-head">
							<div class="robot-screen">
								<div class="robot-brow robot-brow-left"></div>
								<div class="robot-brow robot-brow-right"></div>
								<div class="robot-eye robot-eye-left"></div>
								<div class="robot-eye robot-eye-right"></div>
								<div class="robot-mouth"></div>
							</div>
						</div>
						<div class="robot-body"></div>
					</div>
				</div>
				<h3>${__("Hi! I'm FACO")}</h3>
				<p>${__("Your Frappe Assistant Copilot. I can help you with:")}</p>
				<ul>
					<li>${__("Understanding forms and data")}</li>
					<li>${__("Creating and managing documents")}</li>
					<li>${__("Answering questions about Frappe")}</li>
					<li>${__("Navigating the system")}</li>
				</ul>
			</div>
		`);

		$inputArea.show();

		widget.$widget.find(".faco-input").focus();
		widget.update_context();
	},
};
