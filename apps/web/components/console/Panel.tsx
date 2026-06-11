import type { ReactNode } from "react";

type PanelProps = {
  title: string;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
};

export function Panel({ title, eyebrow, action, children }: PanelProps) {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          {eyebrow ? (
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{eyebrow}</p>
          ) : null}
          <h2 className="text-base font-semibold text-ink">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
