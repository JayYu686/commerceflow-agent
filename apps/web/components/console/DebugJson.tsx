type DebugJsonProps = {
  title?: string;
  data: unknown;
};

export function DebugJson({ title = "调试 JSON", data }: DebugJsonProps) {
  return (
    <details className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4">
      <summary className="cursor-pointer text-sm font-semibold text-slate-700">{title}</summary>
      <pre className="mt-4 max-h-96 overflow-auto rounded-md bg-slate-950 p-4 text-xs leading-5 text-slate-100">
        {JSON.stringify(data, null, 2)}
      </pre>
    </details>
  );
}
