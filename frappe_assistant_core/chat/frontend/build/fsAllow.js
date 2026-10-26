import { resolve } from "path";
import { searchForWorkspaceRoot } from "vite";

const PROJECT_ROOT = resolve(import.meta.dirname, "..");

// MockupFrame imports the mockup kit from the app's public/css, outside this project, so the
// dev server and vitest must be allowed to read that folder as well as the project.
export const fsAllow = [searchForWorkspaceRoot(PROJECT_ROOT), resolve(PROJECT_ROOT, "../../public/css")];
