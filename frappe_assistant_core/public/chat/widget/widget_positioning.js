// Frappe Assistant Copilot - Powered by FAC Cloud - Widget Positioning Module
// Handles drag, resize, and custom position persistence for the FACO widget

/**
 * Widget Positioning Module
 * Responsible for drag-to-move, viewport constraint, and position persistence
 */
window.FACOWidgetPositioning = {
	/**
	 * Set up drag handlers on header and toggle button
	 * @param {Object} widget - Widget instance
	 */
	setup_drag_handlers(widget) {
		const $header = widget.$widget.find(".faco-header");
		const $toggleBtn = widget.$widget.find(".faco-toggle-btn");
		let isDragging = false;
		let startX, startY, startLeft, startTop;
		const DRAG_THRESHOLD = 5;

		widget._hasDragged = false;

		const startDrag = (e) => {
			if ($(e.target).closest(".faco-close-btn").length) return;
			if (widget.is_open) return;

			isDragging = true;
			widget._hasDragged = false;

			const rect = widget.$widget[0].getBoundingClientRect();
			startX = e.clientX;
			startY = e.clientY;
			startLeft = rect.left;
			startTop = rect.top;

			$header.css("cursor", "grabbing");
			$toggleBtn.css("cursor", "grabbing");
			widget.$widget.addClass("faco-dragging");

			e.preventDefault();
		};

		$header.on("mousedown", startDrag);
		$toggleBtn.on("mousedown", startDrag);

		$(document).on("mousemove", (e) => {
			if (!isDragging) return;

			const deltaX = e.clientX - startX;
			const deltaY = e.clientY - startY;

			if (Math.abs(deltaX) > DRAG_THRESHOLD || Math.abs(deltaY) > DRAG_THRESHOLD) {
				widget._hasDragged = true;
			}

			let newLeft = startLeft + deltaX;
			let newTop = startTop + deltaY;

			const widgetRect = widget.$widget[0].getBoundingClientRect();
			const viewportWidth = window.innerWidth;
			const viewportHeight = window.innerHeight;

			newLeft = Math.max(0, Math.min(newLeft, viewportWidth - widgetRect.width));
			newTop = Math.max(0, Math.min(newTop, viewportHeight - widgetRect.height));

			this.apply_custom_position(widget, newLeft, newTop);
		});

		$(document).on("mouseup", (e) => {
			if (!isDragging) return;

			isDragging = false;
			$header.css("cursor", "grab");
			$toggleBtn.css("cursor", "grab");
			widget.$widget.removeClass("faco-dragging");

			if (widget._hasDragged) {
				const rect = widget.$widget[0].getBoundingClientRect();
				this.save_custom_position(widget, rect.left, rect.top);
			}
		});

		$header.css("cursor", "grab");
		$toggleBtn.css("cursor", "grab");
	},

	/**
	 * Load saved position from localStorage
	 * @returns {Object|null} Saved position or null
	 */
	load_custom_position() {
		try {
			const saved = localStorage.getItem("faco_custom_position");
			return saved ? JSON.parse(saved) : null;
		} catch (error) {
			return null;
		}
	},

	/**
	 * Save position to localStorage using anchor-based format
	 * @param {Object} widget - Widget instance
	 * @param {number} left - Left position
	 * @param {number} top - Top position
	 */
	save_custom_position(widget, left, top) {
		try {
			const viewportWidth = window.innerWidth;
			const viewportHeight = window.innerHeight;
			const rect = widget.$widget[0].getBoundingClientRect();

			const centerX = left + rect.width / 2;
			const centerY = top + rect.height / 2;
			const anchorRight = centerX > viewportWidth / 2;
			const anchorBottom = centerY > viewportHeight / 2;

			const position = {
				anchorRight,
				anchorBottom,
				offsetX: anchorRight ? viewportWidth - left - rect.width : left,
				offsetY: anchorBottom ? viewportHeight - top - rect.height : top,
			};

			widget.custom_position = position;
			localStorage.setItem("faco_custom_position", JSON.stringify(position));
		} catch (error) {
			// Silently fail
		}
	},

	/**
	 * Apply position to widget (supports anchor-based and absolute formats)
	 * @param {Object} widget - Widget instance
	 * @param {Object|number} leftOrPosition - Anchor position object or left px value
	 * @param {number} [top] - Top px value (only when first arg is a number)
	 */
	apply_custom_position(widget, leftOrPosition, top) {
		if (typeof leftOrPosition === "object" && leftOrPosition !== null) {
			const position = leftOrPosition;
			const css = { position: "fixed" };

			if (position.anchorRight) {
				css.right = position.offsetX + "px";
				css.left = "auto";
			} else {
				css.left = position.offsetX + "px";
				css.right = "auto";
			}

			if (position.anchorBottom) {
				css.bottom = position.offsetY + "px";
				css.top = "auto";
			} else {
				css.top = position.offsetY + "px";
				css.bottom = "auto";
			}

			widget.$widget.css(css);
		} else {
			widget.$widget.css({
				position: "fixed",
				left: leftOrPosition + "px",
				top: top + "px",
				right: "auto",
				bottom: "auto",
			});
		}
	},

	/**
	 * Set up debounced resize handler
	 * @param {Object} widget - Widget instance
	 */
	setup_resize_handler(widget) {
		let resizeTimeout;
		$(window).on("resize", () => {
			clearTimeout(resizeTimeout);
			resizeTimeout = setTimeout(() => {
				this.reposition_on_resize(widget);
			}, 100);
		});
	},

	/**
	 * Re-apply position on viewport resize
	 * @param {Object} widget - Widget instance
	 */
	reposition_on_resize(widget) {
		if (widget.custom_position && typeof widget.custom_position.anchorRight !== "undefined") {
			this.apply_custom_position(widget, widget.custom_position);
		}

		this.constrain_to_viewport(widget);

		if (widget.is_open) {
			const $toggleBtn = widget.$widget.find(".faco-toggle-btn");
			const $chatWindow = widget.$widget.find(".faco-chat-window");
			FACOWidgetUI.position_chat_window(widget.$widget, $toggleBtn, $chatWindow);
		}
	},

	/**
	 * Ensure widget stays within viewport bounds
	 * @param {Object} widget - Widget instance
	 */
	constrain_to_viewport(widget) {
		const rect = widget.$widget[0].getBoundingClientRect();
		const viewportWidth = window.innerWidth;
		const viewportHeight = window.innerHeight;

		let needsUpdate = false;
		let newLeft = rect.left;
		let newTop = rect.top;

		if (rect.right > viewportWidth) {
			newLeft = Math.max(0, viewportWidth - rect.width);
			needsUpdate = true;
		}
		if (rect.bottom > viewportHeight) {
			newTop = Math.max(0, viewportHeight - rect.height);
			needsUpdate = true;
		}
		if (rect.left < 0) {
			newLeft = 0;
			needsUpdate = true;
		}
		if (rect.top < 0) {
			newTop = 0;
			needsUpdate = true;
		}

		if (needsUpdate) {
			widget.$widget.css({
				position: "fixed",
				left: newLeft + "px",
				top: newTop + "px",
				right: "auto",
				bottom: "auto",
			});
			this.save_custom_position(widget, newLeft, newTop);
		}
	},
};
