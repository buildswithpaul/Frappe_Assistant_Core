import { createApp } from "vue";
import { createPinia } from "pinia";
import router from "./router";
import App from "./App.vue";

// Quiet Ledger styles — single token system.
// Order matters: fonts (@font-face) → tailwind (base/components/utilities) →
// quiet-ledger (tokens, set on :root) → robot (mascot animations).
import "./styles/fonts.css";
import "./styles/tailwind.css";
import "./styles/quiet-ledger.css";
import "./styles/robot.css";

// NOTE: The `?action=verify_email&verify_token=...` deep link is captured
// and stripped from the URL by an inline <script> in index.html that runs
// before this module loads — vue-router's initial history snapshot must
// not see the token, otherwise its `/` → `/chat` redirect copies the query
// through. App.vue reads the captured token from `window.__facoVerifyToken`.

const app = createApp(App);

app.use(createPinia());
app.use(router);

app.mount("#app");
