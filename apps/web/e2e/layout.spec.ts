import { expect, test, type Page } from "@playwright/test";
import { ORG, SCREENS, VIEWER_STATE, invoiceHref, matchHrefFor } from "./helpers";

test.use({ storageState: VIEWER_STATE });

/**
 * Layout audit: nothing on any screen may extend past the right edge of the viewport (the shell clips
 * horizontal overflow, so a too-wide child silently hides columns and controls instead of scrolling).
 * Set E2E_SHOTS=<dir> to also save a full-page screenshot of every page × width.
 */
const WIDTHS = process.env.E2E_WIDTHS ? process.env.E2E_WIDTHS.split(",").map(Number) : [1280, 1440, 1920];
const SHOTS = process.env.E2E_SHOTS;

async function overflow(page: Page) {
  return page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    const scrollsX = (el: Element) => {
      for (let p = el.parentElement; p; p = p.parentElement) {
        const ox = getComputedStyle(p).overflowX;
        if ((ox === "auto" || ox === "scroll") && p.getBoundingClientRect().right <= vw + 1) return true;
      }
      return false;
    };
    const visible = (el: Element) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
    };
    const out: string[] = [];
    for (const el of Array.from(document.querySelectorAll("body *"))) {
      if (!visible(el) || el.closest("[aria-hidden=true], [role=dialog]")) continue;
      const r = el.getBoundingClientRect();
      if (r.right <= vw + 1 || scrollsX(el)) continue;
      const parent = el.parentElement;
      if (parent && parent.getBoundingClientRect().right > vw + 1 && !scrollsX(parent)) continue; // report outermost only
      const cls = typeof el.className === "string" ? el.className.split(" ").filter(Boolean).slice(0, 3).join(".") : "";
      out.push(`${el.tagName.toLowerCase()}${cls ? "." + cls : ""} right=${Math.round(r.right)} (vw ${vw}) "${(el.textContent ?? "").trim().slice(0, 40)}"`);
    }
    return { vw, scrollWidth: document.documentElement.scrollWidth, offenders: out.slice(0, 10) };
  });
}

async function pages(page: Page): Promise<{ name: string; path: string }[]> {
  const list: { name: string; path: string }[] = SCREENS.map((s) => ({ name: s.path, path: `/o/${ORG}/${s.path}` }));
  const hrefs = new Map<string, string>();
  for (const inv of ["PS-88214", "PR-2214", "NV-0001"]) {
    const href = await invoiceHref(page, inv);
    if (href) hrefs.set(inv, href);
  }
  // Plus the first few rows of the invoice list (any vendor, any outcome).
  await page.goto(`/o/${ORG}/invoices`);
  const listed = await page.locator(`a[href*="/o/${ORG}/invoices/"]`).evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? ""));
  for (const href of listed.slice(0, 3)) hrefs.set(href.split("/").pop()!.slice(0, 8), href);
  for (const [name, href] of hrefs) {
    for (const tab of ["lines", "document", "timeline", "audit"]) list.push({ name: `invoice-${name}-${tab}`, path: `${href}?tab=${tab}` });
    list.push({ name: `match-${name}`, path: matchHrefFor(href) });
  }
  return list;
}

test("no screen overflows the viewport horizontally", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop-1600", "the test sweeps its own widths");
  test.setTimeout(600_000);
  await page.goto(`/o/${ORG}/pipeline`);
  const targets = await pages(page);
  const failures: string[] = [];
  for (const w of WIDTHS) {
    await page.setViewportSize({ width: w, height: 900 });
    for (const t of targets) {
      await page.goto(t.path);
      await page.getByRole("heading", { level: 1 }).first().waitFor();
      await page.waitForLoadState("networkidle").catch(() => {});
      const r = await overflow(page);
      if (r.offenders.length || r.scrollWidth > r.vw + 1) failures.push(`${t.name} @${w}: scrollWidth ${r.scrollWidth}\n    ${r.offenders.join("\n    ")}`);
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/${t.name}-${w}.png`, fullPage: true });
    }
  }
  expect(failures, failures.join("\n")).toEqual([]);
});
