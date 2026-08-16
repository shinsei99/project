/**
 * カードの表紙ビジュアル。
 *
 * **slug から決定的に生成するSVG**で、外部画像に一切依存しない。
 * 理由: フリー素材のホスト側が落ちる／URLが変わる／読み込み待ちで
 * レイアウトが揺れる、のいずれもサイト全体の見栄えを壊すため。
 * 写真を使いたい記事だけ `image` を渡せば、そちらが優先される
 * （Unsplash / Openverse などのURLは next.config.ts で許可済み）。
 *
 * 同じ slug なら毎回同じ絵が出るので、記事の見分けがつく。
 */

/** 文字列 → 安定した整数。ビルドごとに変わらないこと（Math.random を使わない）が要件 */
function hash(input: string): number {
  let h = 2166136261;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

export function CoverArt({
  seed,
  label,
  image,
  className = "",
}: {
  seed: string;
  /** 絵の上に重ねる短い文字（種別など）。長い文字は入れない */
  label?: string;
  /** 写真を使う場合のURL。指定するとSVGの代わりにこちらを表示する */
  image?: string;
  className?: string;
}) {
  const h = hash(seed);
  // 色相を2つ取る。60〜100度ずらして、単色べた塗りにならないようにする
  const hueA = h % 360;
  const hueB = (hueA + 60 + (h % 40)) % 360;
  const id = `cover-${h.toString(36)}`;

  if (image) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- 外部フリー素材の比率が不定のため最適化を通さない
      <img
        src={image}
        alt=""
        aria-hidden
        loading="lazy"
        className={`h-32 w-full rounded-lg object-cover ${className}`}
      />
    );
  }

  return (
    <div className={`relative h-32 w-full overflow-hidden rounded-lg ${className}`} aria-hidden>
      <svg viewBox="0 0 400 160" preserveAspectRatio="none" className="h-full w-full">
        <defs>
          <linearGradient id={`${id}-bg`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={`oklch(62% 0.16 ${hueA})`} />
            <stop offset="100%" stopColor={`oklch(48% 0.14 ${hueB})`} />
          </linearGradient>
          <radialGradient id={`${id}-glow`} cx="30%" cy="20%" r="70%">
            <stop offset="0%" stopColor="white" stopOpacity="0.42" />
            <stop offset="100%" stopColor="white" stopOpacity="0" />
          </radialGradient>
          <pattern id={`${id}-grid`} width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M20 0H0V20" fill="none" stroke="white" strokeOpacity="0.14" strokeWidth="1" />
          </pattern>
        </defs>

        <rect width="400" height="160" fill={`url(#${id}-bg)`} />
        <rect width="400" height="160" fill={`url(#${id}-grid)`} />

        {/* 弧を3本。seed で位置と曲がり方を変える */}
        {[0, 1, 2].map((i) => {
          const y = 40 + ((h >> (i * 3)) % 80);
          const bend = 30 + ((h >> (i * 5)) % 70);
          return (
            <path
              key={i}
              d={`M-20 ${y} Q 120 ${y - bend} 200 ${y} T 420 ${y - bend / 2}`}
              fill="none"
              stroke="white"
              strokeOpacity={0.3 - i * 0.07}
              strokeWidth={2 - i * 0.4}
            />
          );
        })}

        <circle cx={60 + (h % 240)} cy={40 + (h % 60)} r={26 + (h % 20)} fill="white" fillOpacity="0.1" />
        <rect width="400" height="160" fill={`url(#${id}-glow)`} />
      </svg>

      {label ? (
        <span className="absolute bottom-2 left-3 rounded bg-black/35 px-2 py-0.5 text-[11px] font-semibold text-white backdrop-blur-sm">
          {label}
        </span>
      ) : null}
    </div>
  );
}
