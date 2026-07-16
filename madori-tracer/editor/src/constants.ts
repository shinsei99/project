import type { Part, PartCategory, PartType } from './types'

// グリッド線は910mm(半間)を表す。SNAPはその半分(455mm)刻みでスナップする。
export const GRID_PX = 40
export const SNAP = GRID_PX / 2
export const CANVAS_W = 1600
export const CANVAS_H = 1000
export const MIN_SIZE = 20

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
  room: { category: 'room', label: '洋室', defaultW: 120, defaultH: 120, resizable: true, rotatable: false, defaultLabel: '洋室' },
  washitsu: { category: 'room', label: '和室', defaultW: 120, defaultH: 120, resizable: true, rotatable: false, defaultLabel: '和室' },
  genkan: { category: 'room', label: '玄関', defaultW: 80, defaultH: 80, resizable: true, rotatable: true, defaultLabel: '玄関' },
  hallway: { category: 'room', label: '廊下', defaultW: 160, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '廊下' },
  storage: { category: 'room', label: '収納', defaultW: 80, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '収納' },
  terrace: { category: 'room', label: 'テラス/バルコニー', defaultW: 120, defaultH: 40, resizable: true, rotatable: true, defaultLabel: 'テラス' },
  wall: { category: 'room', label: '壁', defaultW: 120, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  pillar: { category: 'room', label: '柱', defaultW: 20, defaultH: 20, resizable: true, rotatable: false, defaultLabel: '' },
  'door-hinged': { category: 'opening', label: '片開き戸', defaultW: 40, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  'door-sliding': { category: 'opening', label: '引き戸', defaultW: 80, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  'door-double': { category: 'opening', label: '両開き戸', defaultW: 80, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  'door-bifold': { category: 'opening', label: '折れ戸', defaultW: 60, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  window: { category: 'opening', label: '窓', defaultW: 80, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  toilet: { category: 'fixture', label: 'トイレ', defaultW: 40, defaultH: 60, resizable: true, rotatable: true, defaultLabel: 'トイレ' },
  shower: { category: 'fixture', label: 'シャワー', defaultW: 40, defaultH: 40, resizable: true, rotatable: true, defaultLabel: 'シャワー' },
  washbasin: { category: 'fixture', label: '洗面台', defaultW: 60, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '洗面' },
  bathtub: { category: 'fixture', label: '浴槽', defaultW: 60, defaultH: 90, resizable: true, rotatable: true, defaultLabel: '浴槽' },
  kitchen: { category: 'fixture', label: 'システムキッチン', defaultW: 120, defaultH: 40, resizable: true, rotatable: true, defaultLabel: 'キッチン' },
  refrigerator: { category: 'fixture', label: '冷蔵庫', defaultW: 40, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  'washing-machine': { category: 'fixture', label: '洗濯機', defaultW: 40, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  'dining-table': { category: 'fixture', label: 'ダイニングテーブル', defaultW: 100, defaultH: 60, resizable: true, rotatable: true, defaultLabel: '' },
  bed: { category: 'fixture', label: 'ベッド', defaultW: 80, defaultH: 120, resizable: true, rotatable: true, defaultLabel: '' },
  sofa: { category: 'fixture', label: 'ソファ', defaultW: 100, defaultH: 40, resizable: true, rotatable: true, defaultLabel: '' },
  aircon: { category: 'fixture', label: 'エアコン', defaultW: 40, defaultH: 20, resizable: true, rotatable: true, defaultLabel: '' },
  stairs: { category: 'fixture', label: '階段(UP矢印)', defaultW: 80, defaultH: 120, resizable: true, rotatable: true, defaultLabel: '' },
  text: { category: 'text', label: 'テキスト', defaultW: 80, defaultH: 20, resizable: false, rotatable: true, defaultLabel: 'テキスト' },
}

export const Z_ORDER: Record<PartCategory, number> = { room: 0, opening: 1, fixture: 2, text: 3 }

export const partZ = (p: Part) => Z_ORDER[PART_DEFS[p.type].category]
