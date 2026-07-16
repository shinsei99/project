export type PartCategory = 'room' | 'opening' | 'fixture' | 'text'

export type PartType =
  | 'room'
  | 'washitsu'
  | 'genkan'
  | 'hallway'
  | 'storage'
  | 'terrace'
  | 'wall'
  | 'pillar'
  | 'door-hinged'
  | 'door-sliding'
  | 'door-double'
  | 'door-bifold'
  | 'window'
  | 'toilet'
  | 'shower'
  | 'washbasin'
  | 'bathtub'
  | 'kitchen'
  | 'refrigerator'
  | 'washing-machine'
  | 'dining-table'
  | 'bed'
  | 'sofa'
  | 'aircon'
  | 'stairs'
  | 'text'

export interface Part {
  id: string
  type: PartType
  x: number
  y: number
  w: number
  h: number
  rotation: 0 | 90 | 180 | 270
  label: string
}

export interface BgImage {
  dataUrl: string
  x: number
  y: number
  w: number
  h: number
}

export type ResizeHandle = 'nw' | 'ne' | 'sw' | 'se'
