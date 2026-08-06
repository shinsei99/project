/**
 * 目標カロリー・PFC目標の計算（純関数のみ。クライアント／サーバー双方から利用可）。
 */

export type Sex = "male" | "female";
export type Goal = "lose" | "keep" | "gain";

export type Profile = {
  sex: Sex;
  age: number;
  /** cm */
  height: number;
  /** kg */
  weight: number;
  /** 身体活動レベル係数 */
  activity: number;
  goal: Goal;
  /** 目標体重（kg） */
  targetWeight: number;
  /** 1日の目標摂取カロリー（kcal）。autoTarget=false のとき手入力値を保持 */
  targetKcal: number;
  /** true なら体重などの変更に追従して targetKcal を再計算する */
  autoTarget: boolean;
};

export const ACTIVITY_LEVELS: { value: number; label: string; hint: string }[] = [
  { value: 1.2, label: "ほとんど運動しない", hint: "デスクワーク中心" },
  { value: 1.375, label: "軽い運動", hint: "週1〜3回の運動・散歩" },
  { value: 1.55, label: "中程度の運動", hint: "週3〜5回の運動" },
  { value: 1.725, label: "激しい運動", hint: "週6〜7回／肉体労働" },
];

export const GOALS: { value: Goal; label: string; rate: number; hint: string }[] = [
  { value: "lose", label: "減量", rate: -0.15, hint: "消費より15%少なく" },
  { value: "keep", label: "維持", rate: 0, hint: "今の体重をキープ" },
  { value: "gain", label: "増量", rate: 0.1, hint: "消費より10%多く" },
];

/**
 * 基礎代謝量（ハリス・ベネディクト方程式・改良版）。
 * 男性: 88.362 + 13.397×kg + 4.799×cm − 5.677×age
 * 女性: 447.593 + 9.247×kg + 3.098×cm − 4.330×age
 */
export function calcBmr(p: Pick<Profile, "sex" | "age" | "height" | "weight">): number {
  const v =
    p.sex === "male"
      ? 88.362 + 13.397 * p.weight + 4.799 * p.height - 5.677 * p.age
      : 447.593 + 9.247 * p.weight + 3.098 * p.height - 4.33 * p.age;
  return Math.max(0, Math.round(v));
}

/** 1日の総消費カロリー（基礎代謝 × 活動レベル）。 */
export function calcTdee(p: Pick<Profile, "sex" | "age" | "height" | "weight" | "activity">): number {
  return Math.round(calcBmr(p) * p.activity);
}

/** 目標に応じた1日の目標摂取カロリー。極端な低カロリーにならないよう下限を設ける。 */
export function calcTargetKcal(
  p: Pick<Profile, "sex" | "age" | "height" | "weight" | "activity" | "goal">
): number {
  const rate = GOALS.find((g) => g.value === p.goal)?.rate ?? 0;
  const raw = calcTdee(p) * (1 + rate);
  const floor = Math.max(1200, calcBmr(p)); // 基礎代謝と1200kcalを下回らない
  return Math.round(Math.max(raw, floor) / 10) * 10;
}

/* ---------- BMI ---------- */

/** BMI = 体重kg ÷ (身長m)^2。小数第1位まで。 */
export function calcBmi(weight: number, height: number): number {
  if (!(height > 0)) return 0;
  const m = height / 100;
  return Math.round((weight / (m * m)) * 10) / 10;
}

/** 標準体重（BMI22。統計上もっとも病気になりにくいとされる体重）。 */
export function standardWeight(height: number): number {
  const m = height / 100;
  return Math.round(22 * m * m * 10) / 10;
}

/** 日本肥満学会の判定基準にもとづくBMIの区分。 */
export function bmiCategory(bmi: number): { label: string; color: string } {
  if (bmi < 18.5) return { label: "低体重", color: "text-sky-400" };
  if (bmi < 25) return { label: "普通体重", color: "text-emerald-400" };
  if (bmi < 30) return { label: "肥満（1度）", color: "text-amber-400" };
  if (bmi < 35) return { label: "肥満（2度）", color: "text-orange-400" };
  if (bmi < 40) return { label: "肥満（3度）", color: "text-red-400" };
  return { label: "肥満（4度）", color: "text-red-500" };
}

export type Pfc = { protein: number; fat: number; carbs: number };

/**
 * PFC目標（g）。
 * タンパク質は体重1kgあたり1.6g、脂質は総カロリーの25%、残りを炭水化物に割り当てる。
 */
export function calcPfcTargets(targetKcal: number, weight: number): Pfc {
  const protein = Math.round(weight * 1.6);
  const fat = Math.round((targetKcal * 0.25) / 9);
  const rest = targetKcal - protein * 4 - fat * 9;
  return { protein, fat, carbs: Math.max(0, Math.round(rest / 4)) };
}
