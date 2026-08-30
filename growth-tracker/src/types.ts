/** アプリ全体で使う型。localStorage に入るものはすべてここに書く */

export type Gender = 'boy' | 'girl'

/** プロフィール（初回設定・あとから変更可） */
export interface Profile {
  name: string
  birthday: string          // YYYY-MM-DD
  gender: Gender
  targetHeight: number | null   // cm（任意）
}

/** 1日1件の記録。同じ日に入れ直したら上書きする */
export interface GrowthRecord {
  date: string    // YYYY-MM-DD
  height: number  // cm（小数1桁）
  weight: number  // kg（小数1桁）
  memo: string
}

/** くらべる画面で使う家族 */
export interface FamilyMember {
  id: string
  name: string
  height: number  // cm
}

/** 獲得したバッジ（id と獲得日を持つ） */
export interface EarnedBadge {
  id: string      // 'grow-1' / 'streak-7' など
  date: string    // 獲得した日 YYYY-MM-DD
}
