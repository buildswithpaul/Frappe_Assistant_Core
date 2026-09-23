/** @type {import('tailwindcss').Config} */
export default {
	content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
	darkMode: ["class", '[data-theme="dark"]'],
	theme: {
		extend: {
			colors: {
				// ---- Quiet Ledger tokens (canonical) ----
				"ql-bg": "var(--ql-bg)",
				"ql-surface": "var(--ql-surface)",
				"ql-subtle": "var(--ql-subtle)",
				"ql-border": "var(--ql-border)",
				"ql-border-hover": "var(--ql-border-hover)",
				"ql-text": "var(--ql-text)",
				"ql-text-secondary": "var(--ql-text-secondary)",
				"ql-text-muted": "var(--ql-text-muted)",
				"ql-accent": "var(--ql-accent)",
				"ql-accent-hover": "var(--ql-accent-hover)",
				"ql-accent-soft": "var(--ql-accent-soft)",
				"ql-gold": "var(--ql-gold)",
				"ql-gold-soft": "var(--ql-gold-soft)",
				"ql-success": "var(--ql-success)",
				"ql-warning": "var(--ql-warning)",
				"ql-danger": "var(--ql-danger)",

				// ---- primary aliased to brand accent (drops sky-blue scale) ----
				primary: {
					DEFAULT: "var(--ql-accent)",
					50: "var(--ql-accent-soft)",
					500: "var(--ql-accent)",
					600: "var(--ql-accent)",
					700: "var(--ql-accent-hover)",
					hover: "var(--ql-accent-hover)",
				},

			},

			// Workspace spacing scale
			spacing: {
				// Quiet Ledger 4px scale (§2.3)
				"ql-1": "4px",
				"ql-2": "8px",
				"ql-3": "12px",
				"ql-4": "16px",
				"ql-6": "24px",
				"ql-8": "32px",
				"ql-12": "48px",
				// legacy aliases (kept; map onto the same scale)
				xs: "4px",
				sm: "8px",
				md: "16px",
				lg: "24px",
				xl: "32px",
				"2xl": "48px",
				// layout metrics (Quiet Ledger tokens)
				nav: "var(--ql-nav-width)",
				"nav-collapsed": "var(--ql-nav-collapsed-width)",
				topbar: "var(--ql-topbar-height)",
			},

			// Border radius from design system
			borderRadius: {
				sm: "6px",
				md: "8px",
				lg: "10px",
				xl: "12px",
				"2xl": "14px",
			},

			// Box shadows from design system
			boxShadow: {
				sm: "0 1px 2px 0 rgb(0 0 0 / 0.05)",
				md: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
				lg: "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)",
				message: "0 1px 3px 0 rgb(0 0 0 / 0.05)",
			},

			// Centered chat reading column (Quiet Ledger §3.1)
			maxWidth: {
				"ql-read": "var(--ql-read-width)",
			},

			// Font family
			fontFamily: {
				sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
				serif: ["Source Serif 4", "Georgia", "Times New Roman", "serif"],
				mono: ["ui-monospace", "SF Mono", "SFMono-Regular", "Menlo", "Monaco", "Cascadia Code", "Roboto Mono", "Consolas", "monospace"],
				"ql-ui": "var(--ql-font-ui)",
				"ql-display": "var(--ql-font-display)",
				"ql-mono": "var(--ql-font-mono)",
			},

			// Animations
			animation: {
				float: "float 3s ease-in-out infinite",
				"pulse-slow": "pulse 3s ease-in-out infinite",
				blink: "blink 0.8s infinite",
				"fade-in-up": "fade-in-up 0.3s ease-out",
				"slide-down": "slide-down 0.3s ease-out",
				"thinking-pulse": "thinking-pulse 1.4s ease-in-out infinite",
				"loading-bounce": "loading-bounce 1.4s ease-in-out infinite",
			},

			keyframes: {
				float: {
					"0%, 100%": { transform: "translateY(0)" },
					"50%": { transform: "translateY(-5px)" },
				},
				blink: {
					"0%, 100%": { opacity: "1" },
					"50%": { opacity: "0" },
				},
				"fade-in-up": {
					from: { opacity: "0", transform: "translateY(10px)" },
					to: { opacity: "1", transform: "translateY(0)" },
				},
				"slide-down": {
					from: { opacity: "0", maxHeight: "0", transform: "translateY(-5px)" },
					to: { opacity: "1", maxHeight: "500px", transform: "translateY(0)" },
				},
				"thinking-pulse": {
					"0%, 80%, 100%": { opacity: "0.3", transform: "scale(0.8)" },
					"40%": { opacity: "1", transform: "scale(1)" },
				},
				"loading-bounce": {
					"0%, 80%, 100%": { transform: "scale(0)" },
					"40%": { transform: "scale(1)" },
				},
			},

			// Z-index scale
			zIndex: {
				dropdown: "1000",
				sticky: "1020",
				fixed: "1030",
				"modal-backdrop": "1040",
				modal: "1050",
				popover: "1060",
				tooltip: "1070",
			},
		},
	},
	plugins: [],
};
