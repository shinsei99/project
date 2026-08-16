/** カードの外枠。ホバーの挙動もここに集約する */
export function Card({
  children,
  as: Tag = "div",
  className = "",
  interactive = false,
}: {
  children: React.ReactNode;
  as?: React.ElementType;
  className?: string;
  interactive?: boolean;
}) {
  return (
    <Tag
      className={`rounded-xl border border-border bg-surface p-5 ${
        interactive
          ? "transition-colors hover:border-accent/60 focus-within:border-accent/60"
          : ""
      } ${className}`}
    >
      {children}
    </Tag>
  );
}
