import { useCallback, useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent, ChangeEvent } from 'react'
import { RotateCw, Trash2, Upload } from 'lucide-react'
import { PART_DEFS, snap, partZ, CANVAS_W, CANVAS_H, MIN_SIZE } from './constants'
import type { Part, PartType, BgImage, ResizeHandle, PartCategory } from './types'
import { PartSymbol } from './PartSymbol'
import './editor.css'

let idCounter = 0
const newId = () => `part_${Date.now()}_${idCounter++}`

const CATEGORY_LABELS: Record<PartCategory, string> = {
  room: '部屋・領域',
  opening: '建具',
  fixture: '設備・家具',
  text: 'テキスト',
}

const CATEGORY_GROUPS: { cat: PartCategory; types: PartType[] }[] = [
  { cat: 'room', types: ['room', 'washitsu', 'genkan', 'hallway', 'storage', 'terrace', 'wall', 'pillar'] },
  { cat: 'opening', types: ['door-hinged', 'door-sliding', 'door-double', 'door-bifold', 'window'] },
  {
    cat: 'fixture',
    types: ['toilet', 'shower', 'washbasin', 'bathtub', 'kitchen', 'refrigerator', 'washing-machine', 'dining-table', 'bed', 'sofa', 'aircon', 'stairs'],
  },
  { cat: 'text', types: ['text'] },
]

type DragState =
  | { mode: 'move'; id: string; startX: number; startY: number; origX: number; origY: number }
  | { mode: 'resize'; id: string; handle: ResizeHandle; startX: number; startY: number; orig: { x: number; y: number; w: number; h: number } }
  | { mode: 'bg-move'; startX: number; startY: number; origX: number; origY: number }
  | { mode: 'bg-resize'; handle: ResizeHandle; startX: number; startY: number; orig: { x: number; y: number; w: number; h: number } }
  | null

export default function FloorPlanEditor() {
  const [parts, setParts] = useState<Part[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [bg, setBg] = useState<BgImage | null>(null)
  const [bgOpacity, setBgOpacity] = useState(50)
  const [bgSelected, setBgSelected] = useState(false)

  const svgRef = useRef<SVGSVGElement>(null)
  const dragRef = useRef<DragState>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const toSvgPoint = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current
    if (!svg) return { x: 0, y: 0 }
    const rect = svg.getBoundingClientRect()
    return { x: clientX - rect.left, y: clientY - rect.top }
  }, [])

  const updatePart = (id: string, patch: Partial<Part>) => {
    setParts((ps) => ps.map((p) => (p.id === id ? { ...p, ...patch } : p)))
  }

  const addPart = (type: PartType) => {
    const def = PART_DEFS[type]
    const id = newId()
    const part: Part = {
      id,
      type,
      x: snap(CANVAS_W / 2 - def.defaultW / 2),
      y: snap(CANVAS_H / 2 - def.defaultH / 2),
      w: def.defaultW,
      h: def.defaultH,
      rotation: 0,
      label: def.defaultLabel,
    }
    setParts((p) => [...p, part])
    setSelectedId(id)
    setBgSelected(false)
  }

  const deleteSelected = useCallback(() => {
    setSelectedId((id) => {
      if (id) setParts((ps) => ps.filter((p) => p.id !== id))
      return null
    })
  }, [])

  const rotateSelected = () => {
    if (!selectedId) return
    setParts((ps) =>
      ps.map((p) => (p.id === selectedId ? { ...p, rotation: (((p.rotation + 90) % 360) as Part['rotation']) } : p)),
    )
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId) {
        const target = e.target as HTMLElement
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
        e.preventDefault()
        deleteSelected()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selectedId, deleteSelected])

  const onPartPointerDown = (e: ReactPointerEvent, part: Part) => {
    e.stopPropagation()
    setSelectedId(part.id)
    setBgSelected(false)
    const pt = toSvgPoint(e.clientX, e.clientY)
    dragRef.current = { mode: 'move', id: part.id, startX: pt.x, startY: pt.y, origX: part.x, origY: part.y }
  }

  const onHandlePointerDown = (e: ReactPointerEvent, part: Part, handle: ResizeHandle) => {
    e.stopPropagation()
    const pt = toSvgPoint(e.clientX, e.clientY)
    dragRef.current = { mode: 'resize', id: part.id, handle, startX: pt.x, startY: pt.y, orig: { x: part.x, y: part.y, w: part.w, h: part.h } }
  }

  const onBgPointerDown = (e: ReactPointerEvent) => {
    if (!bg) return
    e.stopPropagation()
    setBgSelected(true)
    setSelectedId(null)
    const pt = toSvgPoint(e.clientX, e.clientY)
    dragRef.current = { mode: 'bg-move', startX: pt.x, startY: pt.y, origX: bg.x, origY: bg.y }
  }

  const onBgHandlePointerDown = (e: ReactPointerEvent, handle: ResizeHandle) => {
    if (!bg) return
    e.stopPropagation()
    const pt = toSvgPoint(e.clientX, e.clientY)
    dragRef.current = { mode: 'bg-resize', handle, startX: pt.x, startY: pt.y, orig: { x: bg.x, y: bg.y, w: bg.w, h: bg.h } }
  }

  useEffect(() => {
    const resizeRect = (orig: { x: number; y: number; w: number; h: number }, handle: ResizeHandle, dx: number, dy: number, doSnap: boolean) => {
      let { x, y, w, h } = orig
      const s = (v: number) => (doSnap ? snap(v) : v)
      if (handle === 'se') {
        w = Math.max(MIN_SIZE, s(orig.w + dx))
        h = Math.max(MIN_SIZE, s(orig.h + dy))
      } else if (handle === 'ne') {
        w = Math.max(MIN_SIZE, s(orig.w + dx))
        const nh = Math.max(MIN_SIZE, s(orig.h - dy))
        y = orig.y + orig.h - nh
        h = nh
      } else if (handle === 'sw') {
        const nw = Math.max(MIN_SIZE, s(orig.w - dx))
        x = orig.x + orig.w - nw
        w = nw
        h = Math.max(MIN_SIZE, s(orig.h + dy))
      } else if (handle === 'nw') {
        const nw = Math.max(MIN_SIZE, s(orig.w - dx))
        const nh = Math.max(MIN_SIZE, s(orig.h - dy))
        x = orig.x + orig.w - nw
        y = orig.y + orig.h - nh
        w = nw
        h = nh
      }
      return { x, y, w, h }
    }

    const onMove = (e: PointerEvent) => {
      const drag = dragRef.current
      if (!drag) return
      const pt = toSvgPoint(e.clientX, e.clientY)
      const dx = pt.x - drag.startX
      const dy = pt.y - drag.startY
      if (drag.mode === 'move') {
        updatePart(drag.id, { x: snap(drag.origX + dx), y: snap(drag.origY + dy) })
      } else if (drag.mode === 'resize') {
        updatePart(drag.id, resizeRect(drag.orig, drag.handle, dx, dy, true))
      } else if (drag.mode === 'bg-move') {
        setBg((b) => (b ? { ...b, x: drag.origX + dx, y: drag.origY + dy } : b))
      } else if (drag.mode === 'bg-resize') {
        setBg((b) => (b ? { ...b, ...resizeRect(drag.orig, drag.handle, dx, dy, false) } : b))
      }
    }
    const onUp = () => {
      dragRef.current = null
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
  }, [toSvgPoint])

  const onCanvasPointerDown = () => {
    setSelectedId(null)
    setBgSelected(false)
  }

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = reader.result as string
      const img = new Image()
      img.onload = () => {
        const maxW = CANVAS_W * 0.8
        const maxH = CANVAS_H * 0.8
        const ratio = Math.min(maxW / img.width, maxH / img.height, 1)
        const w = img.width * ratio
        const h = img.height * ratio
        setBg({ dataUrl, x: (CANVAS_W - w) / 2, y: (CANVAS_H - h) / 2, w, h })
      }
      img.src = dataUrl
    }
    reader.readAsDataURL(file)
    e.target.value = ''
  }

  const editLabel = (part: Part) => {
    if (PART_DEFS[part.type].category === 'opening') return
    const next = window.prompt('ラベルを入力', part.label)
    if (next !== null) updatePart(part.id, { label: next })
  }

  const selectedPart = parts.find((p) => p.id === selectedId) || null

  const renderHandles = (
    x: number,
    y: number,
    w: number,
    h: number,
    rotation: number,
    onDown: (e: ReactPointerEvent, handle: ResizeHandle) => void,
  ) => {
    if (rotation !== 0) return null
    const corners: { k: ResizeHandle; px: number; py: number; cursor: string }[] = [
      { k: 'nw', px: x, py: y, cursor: 'nwse-resize' },
      { k: 'ne', px: x + w, py: y, cursor: 'nesw-resize' },
      { k: 'sw', px: x, py: y + h, cursor: 'nesw-resize' },
      { k: 'se', px: x + w, py: y + h, cursor: 'nwse-resize' },
    ]
    return corners.map((c) => (
      <rect
        key={c.k}
        x={c.px - 5}
        y={c.py - 5}
        width={10}
        height={10}
        fill="#3b82f6"
        stroke="white"
        strokeWidth={1}
        style={{ cursor: c.cursor }}
        onPointerDown={(e) => onDown(e, c.k)}
      />
    ))
  }

  const sortedParts = [...parts].sort((a, b) => partZ(a) - partZ(b))
  const toolbarTarget = selectedPart ?? (bgSelected ? bg : null)

  return (
    <div className="editor-root">
      <aside className="palette">
        <h1>間取りエディタ</h1>

        <div className="bg-section">
          <h2>トレース背景</h2>
          <button type="button" onClick={() => fileInputRef.current?.click()}>
            <Upload size={14} /> 画像を読み込む
          </button>
          <input ref={fileInputRef} type="file" accept="image/*" hidden onChange={onFileChange} />
          {bg && (
            <>
              <label className="opacity-row">
                不透明度
                <input type="range" min={0} max={100} value={bgOpacity} onChange={(e) => setBgOpacity(Number(e.target.value))} />
              </label>
              <button
                type="button"
                onClick={() => {
                  setBg(null)
                  setBgSelected(false)
                }}
              >
                <Trash2 size={14} /> 背景を削除
              </button>
            </>
          )}
        </div>

        {CATEGORY_GROUPS.map((group) => (
          <div key={group.cat} className="palette-group">
            <h2>{CATEGORY_LABELS[group.cat]}</h2>
            <div className="palette-items">
              {group.types.map((type) => {
                const def = PART_DEFS[type]
                return (
                  <button key={type} type="button" className="palette-item" onClick={() => addPart(type)}>
                    <svg width={44} height={44} viewBox={`-4 -4 ${def.defaultW + 8} ${def.defaultH + 8}`}>
                      <PartSymbol part={{ id: 'preview', type, x: 0, y: 0, w: def.defaultW, h: def.defaultH, rotation: 0, label: def.defaultLabel }} />
                    </svg>
                    <span>{def.label}</span>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </aside>

      <div className="canvas-wrap">
        <svg
          ref={svgRef}
          width={CANVAS_W}
          height={CANVAS_H}
          viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`}
          onPointerDown={onCanvasPointerDown}
        >
          <defs>
            <pattern id="grid" width={40} height={40} patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#dde3ea" strokeWidth={1} />
            </pattern>
            <marker id="arrow-up" markerWidth={8} markerHeight={8} refX={4} refY={0} orient="auto">
              <path d="M0,6 L4,0 L8,6 Z" fill="black" />
            </marker>
          </defs>
          <rect x={0} y={0} width={CANVAS_W} height={CANVAS_H} fill="url(#grid)" />

          {bg && (
            <g onPointerDown={onBgPointerDown} style={{ cursor: 'move' }}>
              <image href={bg.dataUrl} x={bg.x} y={bg.y} width={bg.w} height={bg.h} opacity={bgOpacity / 100} preserveAspectRatio="none" />
              {bgSelected && (
                <>
                  <rect x={bg.x} y={bg.y} width={bg.w} height={bg.h} fill="none" stroke="#3b82f6" strokeWidth={1} strokeDasharray="4,3" />
                  {renderHandles(bg.x, bg.y, bg.w, bg.h, 0, onBgHandlePointerDown)}
                </>
              )}
            </g>
          )}

          {sortedParts.map((part) => {
            const isSelected = part.id === selectedId
            return (
              <g
                key={part.id}
                transform={`translate(${part.x} ${part.y}) rotate(${part.rotation} ${part.w / 2} ${part.h / 2})`}
                onPointerDown={(e) => onPartPointerDown(e, part)}
                onDoubleClick={() => editLabel(part)}
                style={{ cursor: 'move' }}
              >
                <rect x={-4} y={-4} width={part.w + 8} height={part.h + 8} fill="transparent" />
                <PartSymbol part={part} />
                {isSelected && <rect x={0} y={0} width={part.w} height={part.h} fill="none" stroke="#3b82f6" strokeWidth={1.5} strokeDasharray="4,3" />}
              </g>
            )
          })}

          {selectedPart &&
            PART_DEFS[selectedPart.type].resizable &&
            renderHandles(selectedPart.x, selectedPart.y, selectedPart.w, selectedPart.h, selectedPart.rotation, (e, h) =>
              onHandlePointerDown(e, selectedPart, h),
            )}
        </svg>

        {toolbarTarget && (
          <div
            className="floating-toolbar"
            style={{
              left: toolbarTarget.x,
              top: Math.max(0, toolbarTarget.y - 36),
            }}
          >
            {selectedPart && PART_DEFS[selectedPart.type].rotatable && (
              <button type="button" onClick={rotateSelected} title="90度回転">
                <RotateCw size={16} />
              </button>
            )}
            <button
              type="button"
              onClick={
                selectedPart
                  ? deleteSelected
                  : () => {
                      setBg(null)
                      setBgSelected(false)
                    }
              }
              title="削除"
            >
              <Trash2 size={16} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
