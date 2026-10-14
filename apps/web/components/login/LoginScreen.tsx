import { Wordmark } from "./Wordmark";
import { DemoAccess, SignInForm } from "./LoginForms";
import styles from "./login.module.css";

export interface LoginScreenProps {
  next: string;
  error: string | null;
  signedInAs: string | null;
  repoUrl: string;
}

export function LoginScreen({ next, error, signedInAs, repoUrl }: LoginScreenProps) {
  return (
    <div className={styles.page}>
      <section className={styles.brand} aria-label="Ledgic">
        <Wordmark size={58} />
        <p className={styles.tagline}>Accounts-payable automation for multi-location operators.</p>
      </section>

      <main className={styles.formSide}>
        <div className={styles.formCol}>
          {signedInAs ? (
            <p className={styles.signedIn}>
              Signed in as {signedInAs} ·{" "}
              <a className={styles.inkLink} href={next}>
                Continue
              </a>
            </p>
          ) : null}
          {error ? (
            <p className={styles.error} role="alert">
              {error}
            </p>
          ) : null}

          <SignInForm next={next} />

          <hr className={styles.rule} />

          <DemoAccess next={next} />

          <footer className={styles.footer}>
            <span>Open-source portfolio project</span>
            <span aria-hidden="true">·</span>
            <a className={styles.inkLink} href={repoUrl} rel="noopener noreferrer" target="_blank">
              Source on GitHub
            </a>
          </footer>
        </div>
      </main>
    </div>
  );
}
