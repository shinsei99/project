/** ページ幅の統一。ここ以外で max-w を直書きしない */
export function Container({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`mx-auto w-full max-w-6xl px-5 sm:px-8 ${className}`}>{children}</div>
  );
}
