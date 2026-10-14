"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, useTransition } from "react";
import styles from "./operations.module.css";

export interface PeriodOption {
  key: string;
  label: string;
}

export interface PeriodMenuProps {
  /** Visible trigger text, e.g. "July 2026, month to date". */
  label: string;
  current: string;
  options: PeriodOption[];
}

/** Top-bar context period selector → ?period=mtd|qtd|l30. */
export function PeriodMenu({ label, current, options }: PeriodMenuProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [, startTransition] = useTransition();
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLUListElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!menuRef.current?.contains(t) && !btnRef.current?.contains(t)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        btnRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    menuRef.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus();
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function toggle() {
    const r = btnRef.current?.getBoundingClientRect();
    if (r) setPos({ top: r.bottom + 8, left: r.left });
    setOpen((o) => !o);
  }

  function choose(key: string) {
    setOpen(false);
    startTransition(() => router.replace(`${pathname}?period=${key}`, { scroll: false }));
  }

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        className={styles.periodBtn}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={toggle}
      >
        {label}
      </button>
      {open ? (
        <ul ref={menuRef} id={menuId} role="menu" aria-label="Period" className={styles.periodMenu} style={pos}>
          {options.map((o) => (
            <li key={o.key} role="none">
              <button
                type="button"
                role="menuitemradio"
                aria-checked={o.key === current}
                className={styles.periodItem}
                onClick={() => choose(o.key)}
              >
                {o.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </>
  );
}
