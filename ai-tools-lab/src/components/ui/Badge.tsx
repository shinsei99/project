/** 小さなラベル。tone で意味づけを変える */
export function Badge({
  children,
  tone = "default",
}: {
  children: React.ReactNode;
  tone?: "default" | "accent" | "outline";
}) {
  const tones = {
    default: "bg-surface-2 text-muted border-border",
    accent: "bg-accent-soft text-accent border-transparent",
    outline: "bg-transparent text-muted border-border",
  } as const;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
