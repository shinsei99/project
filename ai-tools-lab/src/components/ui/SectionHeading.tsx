import { Container } from "./Container";

/** セクション見出し。右側に一覧ページへの導線を置ける */
export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <Container className="mb-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-2xl">
          {eyebrow ? (
            <p className="mb-2 text-sm font-semibold tracking-wide text-accent">{eyebrow}</p>
          ) : null}
          <h2 className="text-2xl font-bold sm:text-3xl">{title}</h2>
          {description ? <p className="mt-3 text-muted">{description}</p> : null}
        </div>
        {action}
      </div>
    </Container>
  );
}
