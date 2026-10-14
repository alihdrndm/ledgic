"use client";

import { useActionState } from "react";
import { Button } from "@/components/ui";
import { openDemo, sendSignInLink, type LoginState } from "@/app/login/actions";
import styles from "./login.module.css";

const idle: LoginState = { status: "idle" };

export function SignInForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState(sendSignInLink, idle);
  return (
    <form action={action} className={styles.block} noValidate>
      <h1 className={`section-label ${styles.blockLabel}`}>Sign in</h1>
      <input type="hidden" name="next" value={next} />
      <label htmlFor="login-email" className="field-label">
        Email
      </label>
      <input
        id="login-email"
        name="email"
        type="email"
        className={`input ${styles.input}`}
        autoComplete="email"
        inputMode="email"
        required
        aria-describedby="login-email-note"
        aria-invalid={state.status === "error" || undefined}
      />
      <Button type="submit" variant="ink" loading={pending} className={styles.tall} block>
        Send sign-in link
      </Button>
      <p id="login-email-note" className={styles.note}>
        We&apos;ll email you a one-time link.
      </p>
      <p className={state.status === "error" ? styles.error : styles.status} role="status" aria-live="polite">
        {state.message ?? ""}
      </p>
    </form>
  );
}

export function DemoAccess({ next }: { next: string }) {
  const [state, action, pending] = useActionState(openDemo, idle);
  return (
    <form action={action} className={styles.block}>
      <input type="hidden" name="next" value={next} />
      <h2 className={styles.demoTitle}>Explore the demo</h2>
      <p className={styles.demoText}>Read-only access to a synthetic tenant.</p>
      <div className={styles.demoActions}>
        <Button type="submit" name="persona" value="viewer" variant="ink" disabled={pending} className={styles.tall} block>
          Open the demo
        </Button>
        <Button type="submit" name="persona" value="elena" variant="outline" disabled={pending} className={styles.tall} block>
          Try as Elena (AP manager)
        </Button>
      </div>
      <p className={styles.note}>As Elena, your approvals and short-pays are real decisions; the demo resets nightly.</p>
      <p className={state.status === "error" ? styles.error : styles.status} role="status" aria-live="polite">
        {pending ? "Signing in…" : (state.message ?? "")}
      </p>
    </form>
  );
}
