export function KeyValue({
  label,
  value,
  raw,
}: {
  label: string;
  value: string;
  raw?: string | null;
}) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 break-words text-sm text-slate-800">{value}</dd>
      {raw && raw !== value ? <dd className="mt-0.5 text-xs text-slate-500">{raw}</dd> : null}
    </div>
  );
}
