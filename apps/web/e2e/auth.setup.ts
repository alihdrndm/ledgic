import { test as setup } from "@playwright/test";
import { signInAs, VIEWER_STATE } from "./helpers";

// One demo sign-in per run (demo sign-in is rate limited per IP); every viewer test reuses it.
setup("sign in as the demo viewer", async ({ page }) => {
  await signInAs(page, "viewer");
  await page.context().storageState({ path: VIEWER_STATE });
});
