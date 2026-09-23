// Frappe Assistant Copilot - Powered by FAC Cloud - Widget Tooltips Module
// Handles tooltip rotation and positioning for the FACO widget toggle button

/**
 * Widget Tooltips Module
 * Responsible for displaying and rotating tooltip messages when the widget is closed
 */
window.FACOWidgetTooltips = {
	/**
	 * Start showing rotating tooltip messages when widget is closed
	 * @param {Object} widget - Widget instance
	 */
	start_tooltip_animation(widget) {
		if (widget.is_open || !widget.$widget) return;

		// One bounded cycle per launch: nudge through each message once, then
		// fall silent. Re-opening/closing the widget starts a fresh cycle.
		widget.tooltip_shown_count = 0;

		// Show first tooltip after 3 seconds
		setTimeout(() => {
			this.show_tooltip(widget);
		}, 3000);

		// Rotate tooltips every 8 seconds
		widget.tooltip_interval = setInterval(() => {
			if (!widget.is_open) {
				this.show_tooltip(widget);
			}
		}, 8000);
	},

	/**
	 * Display a tooltip message with animation
	 * @param {Object} widget - Widget instance
	 */
	show_tooltip(widget) {
		if (widget.is_open) return;

		// Cycle already complete — stay silent regardless of caller. The interval
		// is cleared on auto-stop, but this guards any stray/future direct call.
		if ((widget.tooltip_shown_count || 0) >= widget.tooltip_messages.length) return;

		// Idle-gate: skip this tick while the user is typing/scrolling
		// (signal published by FACOWidgetAutofade). Don't advance the index —
		// just wait for the next idle tick so no message is silently burned.
		if (widget._userActive) return;

		const message = widget.tooltip_messages[widget.current_tooltip_index];
		const $tooltip = widget.$widget.find(".faco-tooltip");
		const $icon = $tooltip.find(".faco-tooltip-icon");
		const $text = $tooltip.find(".faco-tooltip-text");
		const $toggleBtn = widget.$widget.find(".faco-toggle-btn");

		// Update content
		$icon.text(message.icon);
		$text.text(message.text);

		// Position tooltip dynamically based on actual widget position
		this.position_tooltip($tooltip, $toggleBtn);

		// Show tooltip with animation
		$tooltip.addClass("faco-show");

		// Hide after 5 seconds
		setTimeout(() => {
			$tooltip.removeClass("faco-show");
		}, 5000);

		// Move to next message
		widget.current_tooltip_index =
			(widget.current_tooltip_index + 1) % widget.tooltip_messages.length;

		// One full cycle shown — fall silent so the launcher stops nagging.
		widget.tooltip_shown_count = (widget.tooltip_shown_count || 0) + 1;
		if (widget.tooltip_shown_count >= widget.tooltip_messages.length) {
			this.stop_tooltip_animation(widget);
		}
	},

	/**
	 * Dynamically position tooltip based on widget's actual screen position
	 * @param {jQuery} $tooltip - Tooltip element
	 * @param {jQuery} $toggleBtn - Toggle button element
	 */
	position_tooltip($tooltip, $toggleBtn) {
		const btnRect = $toggleBtn[0].getBoundingClientRect();
		const tooltipWidth = $tooltip.outerWidth();
		const viewportWidth = window.innerWidth;

		// Clear previous positioning classes/styles
		$tooltip.css({
			left: "",
			right: "",
			top: "",
			bottom: "",
		});

		// Check if there's space on the left side of the button
		const spaceOnLeft = btnRect.left;

		// Position tooltip based on available space
		if (spaceOnLeft >= tooltipWidth + 20) {
			// Show tooltip on the left of the button
			$tooltip.css({
				right: viewportWidth - btnRect.left + 15 + "px",
				left: "auto",
				top: btnRect.top + btnRect.height / 2 - $tooltip.outerHeight() / 2 + "px",
				bottom: "auto",
			});
			$tooltip.attr("data-arrow", "right");
		} else {
			// Show tooltip on the right of the button
			$tooltip.css({
				left: btnRect.right + 15 + "px",
				right: "auto",
				top: btnRect.top + btnRect.height / 2 - $tooltip.outerHeight() / 2 + "px",
				bottom: "auto",
			});
			$tooltip.attr("data-arrow", "left");
		}
	},

	/**
	 * Stop the tooltip animation and hide immediately
	 * @param {Object} widget - Widget instance
	 */
	stop_tooltip_animation(widget) {
		if (widget.tooltip_interval) {
			clearInterval(widget.tooltip_interval);
			widget.tooltip_interval = null;
		}

		// Hide tooltip immediately
		if (widget.$widget) {
			widget.$widget.find(".faco-tooltip").removeClass("faco-show");
		}
	},
};
