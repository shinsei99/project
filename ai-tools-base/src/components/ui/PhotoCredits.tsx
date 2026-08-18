import { getRequiredCredits } from "@/lib/content/photos";

/**
 * 写真の出典表示。**CC BY / BY-SA は表示が義務**なので消さないこと。
 * 表示しないまま使うとライセンス違反になる。
 */
export function PhotoCredits() {
  const credits = getRequiredCredits();
  if (credits.length === 0) return null;

  return (
    <div className="mt-6 border-t border-border pt-4 text-xs leading-relaxed text-muted">
      <p className="mb-1 font-semibold">写真クレジット</p>
      <ul className="flex flex-wrap gap-x-4 gap-y-1">
        {credits.map((c) => (
          <li key={c.slug}>
            {c.source ? (
              <a href={c.source} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
                {c.title || "写真"}
              </a>
            ) : (
              <span>{c.title || "写真"}</span>
            )}
            {" / "}
            {c.creator} / {c.license}（{c.provider} 経由）
          </li>
        ))}
      </ul>
    </div>
  );
}
