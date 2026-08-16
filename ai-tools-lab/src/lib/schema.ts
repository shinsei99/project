/**
 * サイト全体のコンテンツ型。**ここが唯一の定義**。
 *
 * コンテンツは人だけでなくAI・自動化スクリプトも書き換える前提なので、
 * 「読めればいい」ではなく zod で検証してビルド前に落とす（`npm run validate`）。
 * 型を増やすときは、必ずこのファイル → source.ts → 表示側 の順で広げること。
 */
import { z } from "zod";

/** ツールの分類。増やすときはここと content/categories.json の両方を直す */
export const TOOL_CATEGORIES = [
  "agent", // 自律型エージェント（Claude Code など）
  "assistant", // エディタ補完・チャット型の開発支援
  "build", // アプリを丸ごと作る系（v0, Bolt など）
  "learn", // 学習・教材
  "ops", // 運用・自動化
] as const;

/** 料金体系。比較テーブルの絞り込みに使う */
export const PRICING_MODELS = ["free", "freemium", "subscription", "usage"] as const;

/** 想定読者。初心者向けか玄人向けかで見せる順番を変える */
export const AUDIENCES = ["beginner", "developer", "sidejob", "team"] as const;

/**
 * 比較の評価軸。**全ツール共通**にすることで、表・カード・詳細ページが同じ型を読める。
 * 0〜5 の 0.5 刻み。根拠なく点を付けないこと（`review.basis` に実際に試した内容を書く）。
 */
export const scoresSchema = z.object({
  autonomy: z.number().min(0).max(5), // 自律性（どこまで任せられるか）
  codeQuality: z.number().min(0).max(5), // 出力の質
  costEfficiency: z.number().min(0).max(5), // 費用対効果
  learningCurve: z.number().min(0).max(5), // 習得しやすさ（高いほど易しい）
  japanese: z.number().min(0).max(5), // 日本語の扱い
});

export const toolSchema = z.object({
  slug: z.string().regex(/^[a-z0-9-]+$/, "slugは半角英数とハイフンのみ"),
  name: z.string().min(1),
  vendor: z.string().min(1),
  category: z.enum(TOOL_CATEGORIES),
  /** 一覧カードと比較テーブルに出る1行。40〜80字を目安に */
  summary: z.string().min(10).max(160),
  pricing: z.object({
    model: z.enum(PRICING_MODELS),
    /** 「$20/月」「従量」など、表にそのまま出す短い表記 */
    label: z.string().min(1),
    freeTier: z.boolean(),
  }),
  audiences: z.array(z.enum(AUDIENCES)).min(1),
  scores: scoresSchema,
  strengths: z.array(z.string()).min(1).max(5),
  weaknesses: z.array(z.string()).min(1).max(5),
  /** 公式サイト。アフィリエイトに差し替える場合もこのフィールドを経由させる */
  url: z.string().url(),
  /** 編集部イチオシ。トップの比較テーブルで強調表示される。多用しない */
  featured: z.boolean().default(false),
  review: z
    .object({
      /** 何をどれだけ触って評価したのか。ここが空の点数は載せない */
      basis: z.string().min(10),
      updatedAt: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
    })
    .optional(),
});

export const articleSchema = z.object({
  slug: z.string().regex(/^[a-z0-9-]+$/),
  title: z.string().min(1),
  description: z.string().min(10).max(200),
  /** 記事の性格。トップでの見せ方を変える */
  kind: z.enum(["review", "compare", "howto", "feature", "log"]),
  publishedAt: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  updatedAt: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  tags: z.array(z.string()).default([]),
  /** 関連ツールのslug。詳細ページで相互リンクする */
  tools: z.array(z.string()).default([]),
  featured: z.boolean().default(false),
  draft: z.boolean().default(false),
  readingMinutes: z.number().int().positive().optional(),
});

/**
 * 制作記録（ビルドログ）。**出すのは成果物ではなく「作り方」**。
 *
 * 載せるのは ①最初に投げたプロンプト ②できあがった機能 ③完成までの過程
 * ④その後の改善過程（症状→原因→直し方）の4点。
 * アプリ本体・画面・顧客データは公開しない。だから社内業務アプリでも記事にできる。
 *
 * **`visibility` は必須。** `internal` は本数の集計にだけ使い、本文はページに出さない
 * （source 側で落とす）。プロンプト本文に会社名・物件名・氏名が混ざりやすいので、
 * `public` にする前に必ず伏せ字にすること（検証スクリプトでも警告する）。
 */
export const workSchema = z.object({
  slug: z.string().regex(/^[a-z0-9-]+$/),
  /** 記録のタイトル。アプリ名そのままでなく「何を作った話か」でよい */
  name: z.string().min(1),
  visibility: z.enum(["public", "internal"]),
  category: z.enum(["realestate", "tool", "game", "media"]),
  summary: z.string().min(10).max(200),
  stack: z.array(z.string()).min(1),
  year: z.number().int().min(2020).max(2100),
  /** 着手から動くまでの実測。「AIなら一瞬」と言わないための数字 */
  buildTime: z.string().min(1).optional(),

  /**
   * 外部媒体へ出した転載記事。**本体を先に公開してから**URLを入れる
   * （後追いにすると検索で自分の転載に負ける）。
   * ここに入れた分だけ詳細ページに相互リンクが出る。
   */
  links: z
    .array(
      z.object({
        /** 媒体名。そのまま表示ラベルになる（「Zenn」「note」） */
        label: z.string().min(1),
        url: z.string().url(),
        /** 「技術的な詳細」など、どちらを読めばいいかの一言 */
        note: z.string().min(1).optional(),
      }),
    )
    .default([]),

  /** ① 実際に投げたプロンプト。取り繕わず、そのままの文言を載せる価値がある */
  prompts: z
    .array(
      z.object({
        phase: z.enum(["kickoff", "feature", "fix", "refactor"]),
        /** 何を狙って投げたのか */
        intent: z.string().min(5),
        /**
         * 投げた文面。**体裁と語調は整えてよい**（句読点・表記の統一・です／ます調へ）。
         *
         * ただし**内容と粒度は変えない**こと。実際には一言で済ませた指示を、
         * 条件を並べた長い依頼へ書き直してはいけない。
         * 「この短さでも通る」ことが読者にとっての情報なので、
         * 情報量を足した時点で記録の価値が消える。
         * 固有名詞は伏せる。
         */
        text: z.string().min(10),
        /** 返ってきたもの・効いた点／効かなかった点 */
        result: z.string().min(5).optional(),
      }),
    )
    .default([]),

  /** ② 構築後の機能 */
  features: z.array(z.string()).default([]),

  /** ③ 構築にいたるまでの過程 */
  process: z
    .array(
      z.object({
        step: z.string().min(1), // 「1日目」「Stage 2」など
        title: z.string().min(1),
        detail: z.string().min(5),
      }),
    )
    .default([]),

  /**
   * ④ 改善過程。既存アプリの SESSION_LOG.md「症状 → 原因 → 直し方」を
   * そのまま移せる形にしてある。原因が未特定なら `cause` に「未特定」と正直に書く。
   */
  improvements: z
    .array(
      z.object({
        symptom: z.string().min(5),
        cause: z.string().min(2),
        fix: z.string().min(5),
        /** 測った値があれば（「4.2秒 → 1.1秒」）。憶測の改善幅は書かない */
        metric: z.string().optional(),
      }),
    )
    .default([]),

  featured: z.boolean().default(false),
});

export const categorySchema = z.object({
  id: z.enum(TOOL_CATEGORIES),
  label: z.string().min(1),
  description: z.string().min(1),
});

export type Tool = z.infer<typeof toolSchema>;
export type Article = z.infer<typeof articleSchema>;
export type Work = z.infer<typeof workSchema>;
export type Category = z.infer<typeof categorySchema>;
export type Scores = z.infer<typeof scoresSchema>;
export type ToolCategory = (typeof TOOL_CATEGORIES)[number];
export type PricingModel = (typeof PRICING_MODELS)[number];
export type Audience = (typeof AUDIENCES)[number];

/** 5軸の平均。比較テーブルの既定の並び順に使う */
export function overallScore(scores: Scores): number {
  const values = Object.values(scores);
  return Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 10) / 10;
}
