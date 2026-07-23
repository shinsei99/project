import type { Part, PartCategory, PartType, TatamiJou } from './types'

// グリッド線は910mm(半間)を表す。SNAPはその半分(455mm)刻みでスナップする。
export const GRID_PX = 40
export const SNAP = GRID_PX / 2
export const CANVAS_W = 1600
export const CANVAS_H = 1000
export const MIN_SIZE = 4

export const snap = (v: number) => Math.round(v / SNAP) * SNAP

interface PartDef {
  category: PartCategory
  label: string
  defaultW: number
  defaultH: number
  resizable: boolean
  rotatable: boolean
  defaultLabel: string
}

export const PART_DEFS: Record<PartType, PartDef> = {
  room: { category: 'room', label: '洋室', defaultW: 120, defaultH: 120, resizable: true, rotatable: false, defaultLabel: '' },
  washitsu: { category: 'room', label: '和室', defaultW: 120, defaultH: 120, resizable: true, rotatable: false, defaultLabel: '' },
  genkan: { category: 'room', label: '玄関', defaultW: 80, defaultH: 80, resizable: true, rotatable: true, defaultLabel: '' },
  hallway: { category: 'room', label: '廊下', defaultW: 160, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  storage: { category: 'room', label: '収納', defaultW: 80, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  terrace: { category: 'room', label: 'テラス/バルコニー', defaultW: 120, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  wall: { category: 'room', label: '壁', defaultW: 120, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  pillar: { category: 'room', label: '柱', defaultW: 20, defaultH: 20, resizable: true, rotatable: false, defaultLabel: '' },
  'door-hinged': { category: 'opening', label: '片開き戸', defaultW: 40, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  'door-sliding': { category: 'opening', label: '引違い戸', defaultW: 80, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  'door-double': { category: 'opening', label: '両開き戸', defaultW: 80, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  'door-parent-child': { category: 'opening', label: '親子扉', defaultW: 80, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  'door-sliding-single': { category: 'opening', label: '片引き戸', defaultW: 80, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  'door-pocket': { category: 'opening', label: '引込み戸', defaultW: 80, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  'door-accordion': { category: 'opening', label: 'アコーディオンカーテン', defaultW: 80, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  'door-bifold': { category: 'opening', label: '折れ戸', defaultW: 60, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  'door-bifold-double': { category: 'opening', label: '2枚折戸', defaultW: 100, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  window: { category: 'opening', label: '窓', defaultW: 80, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  toilet: { category: 'fixture', label: 'トイレ', defaultW: 40, defaultH: 60, resizable: true, rotatable: true, defaultLabel: '' },
  shower: { category: 'fixture', label: 'シャワー', defaultW: 40, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  washbasin: { category: 'fixture', label: '洗面台', defaultW: 60, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  bathtub: { category: 'fixture', label: '浴槽', defaultW: 60, defaultH: 90, resizable: true, rotatable: true, defaultLabel: '' },
  kitchen: { category: 'fixture', label: 'システムキッチン', defaultW: 120, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  refrigerator: { category: 'fixture', label: '冷蔵庫', defaultW: 40, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  'washing-machine': { category: 'fixture', label: '洗濯機', defaultW: 40, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  'dining-table': { category: 'fixture', label: 'ダイニングテーブル', defaultW: 100, defaultH: 60, resizable: true, rotatable: true, defaultLabel: '' },
  bed: { category: 'fixture', label: 'ベッド', defaultW: 80, defaultH: 120, resizable: true, rotatable: true, defaultLabel: '' },
  sofa: { category: 'fixture', label: 'ソファ', defaultW: 100, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  aircon: { category: 'fixture', label: 'エアコン', defaultW: 40, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  stairs: { category: 'fixture', label: '階段(UP矢印)', defaultW: 80, defaultH: 120, resizable: true, rotatable: true, defaultLabel: '' },
  text: { category: 'text', label: 'テキスト', defaultW: 80, defaultH: 20, resizable: false, rotatable: true, defaultLabel: '' },
}

export const Z_ORDER: Record<PartCategory, number> = { room: 0, opening: 1, fixture: 2, text: 3 }

export const partZ = (p: Part) => Z_ORDER[PART_DEFS[p.type].category]

// 間取り図トレーサー（Gemini生成）のラベル文字に近い、太めのゴシック体をデフォルトに使う。
export const FONT_STACK_DEFAULT = "'Noto Sans JP', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', Meiryo, sans-serif"

export const FONT_FAMILY_OPTIONS: { value: string; label: string }[] = [
  { value: FONT_STACK_DEFAULT, label: '標準（生成画像に近い）' },
  { value: "'Yu Gothic', sans-serif", label: '游ゴシック' },
  { value: "'Hiragino Kaku Gothic ProN', sans-serif", label: 'ヒラギノ角ゴ' },
  { value: "'Meiryo', sans-serif", label: 'メイリオ' },
  { value: "sans-serif", label: 'ブラウザ標準' },
]

// 部屋の壁線・ラベル文字サイズのデフォルト値（パーツごとにpart.wallWidth/fontSizeで上書き可能）。
export const DEFAULT_WALL_WIDTH: Partial<Record<PartType, number>> = {
  room: 10,
  washitsu: 10,
  genkan: 10,
  hallway: 7,
  storage: 3,
  terrace: 7,
}

export const DEFAULT_FONT_SIZE: Partial<Record<PartType, number>> = {
  room: 14,
  washitsu: 13,
  genkan: 12,
  hallway: 11,
  storage: 10,
  terrace: 11,
  text: 16,
}

// 「壁線の太さ」設定の対象になる、外枠(壁)を持つパーツ種別。
export const WALL_TYPES = new Set<PartType>(['room', 'washitsu', 'genkan', 'hallway', 'storage', 'terrace'])

// 畳の敷き方（祝儀敷き＝十字に4枚の角が集まる箇所が無い配置）。
// 単位は半畳(GRID_PXの1マス=910mm)。x,y,w,hはすべてマス数（半畳グリッドの座標）。
interface TatamiLayout {
  cols: number
  rows: number
  mats: { x: number; y: number; w: number; h: number }[]
  halfMat?: { x: number; y: number }
}

export const TATAMI_LAYOUTS: Record<TatamiJou, TatamiLayout> = {
  '4.5': {
    cols: 3,
    rows: 3,
    mats: [
      { x: 0, y: 0, w: 2, h: 1 },
      { x: 2, y: 0, w: 1, h: 2 },
      { x: 1, y: 2, w: 2, h: 1 },
      { x: 0, y: 1, w: 1, h: 2 },
    ],
    halfMat: { x: 1, y: 1 },
  },
  '6-h': {
    cols: 4,
    rows: 3,
    mats: [
      { x: 0, y: 0, w: 2, h: 1 },
      { x: 2, y: 0, w: 2, h: 1 },
      { x: 0, y: 1, w: 1, h: 2 },
      { x: 3, y: 1, w: 1, h: 2 },
      { x: 1, y: 1, w: 2, h: 1 },
      { x: 1, y: 2, w: 2, h: 1 },
    ],
  },
  '6-v': {
    cols: 3,
    rows: 4,
    mats: [
      { x: 0, y: 0, w: 1, h: 2 },
      { x: 0, y: 2, w: 1, h: 2 },
      { x: 1, y: 0, w: 2, h: 1 },
      { x: 1, y: 3, w: 2, h: 1 },
      { x: 1, y: 1, w: 1, h: 2 },
      { x: 2, y: 1, w: 1, h: 2 },
    ],
  },
  '8': {
    cols: 4,
    rows: 4,
    mats: [
      { x: 0, y: 0, w: 2, h: 1 },
      { x: 2, y: 0, w: 2, h: 1 },
      { x: 0, y: 1, w: 1, h: 2 },
      { x: 3, y: 1, w: 1, h: 2 },
      { x: 1, y: 1, w: 2, h: 1 },
      { x: 1, y: 2, w: 2, h: 1 },
      { x: 0, y: 3, w: 2, h: 1 },
      { x: 2, y: 3, w: 2, h: 1 },
    ],
  },
  '10': {
    cols: 5,
    rows: 4,
    mats: [
      { x: 0, y: 0, w: 2, h: 1 },
      { x: 2, y: 0, w: 2, h: 1 },
      { x: 0, y: 1, w: 1, h: 2 },
      { x: 3, y: 1, w: 1, h: 2 },
      { x: 1, y: 1, w: 2, h: 1 },
      { x: 1, y: 2, w: 2, h: 1 },
      { x: 0, y: 3, w: 2, h: 1 },
      { x: 2, y: 3, w: 2, h: 1 },
      { x: 4, y: 0, w: 1, h: 2 },
      { x: 4, y: 2, w: 1, h: 2 },
    ],
  },
}

export const TATAMI_JOU_LABELS: Record<TatamiJou, string> = {
  '4.5': '4.5畳',
  '6-h': '6畳(横)',
  '6-v': '6畳(縦)',
  '8': '8畳',
  '10': '10畳',
}
