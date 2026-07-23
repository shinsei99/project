import { useCallback, useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent, ChangeEvent } from 'react'
import { RotateCw, Trash2, Upload, Undo2, BoxSelect, ZoomIn, ZoomOut, Download } from 'lucide-react'
import {
  PART_DEFS,
  snap,
  partZ,
  CANVAS_W,
  CANVAS_H,
  MIN_SIZE,
  SNAP,
  GRID_PX,
  TATAMI_LAYOUTS,
  TATAMI_JOU_LABELS,
  DEFAULT_WALL_WIDTH,
  DEFAULT_FONT_SIZE,
  FONT_STACK_DEFAULT,
  FONT_FAMILY_OPTIONS,
  WALL_TYPES,
} from './constants'
import type { Part, PartType, BgImage, ResizeHandle, PartCategory, TatamiJou } from './types'
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
  {
    cat: 'opening',
    types: [
      'door-hinged',
      'door-double',
      'door-parent-child',
      'door-sliding',
      'door-sliding-single',
      'door-pocket',
      'door-accordion',
      'door-bifold',
      'door-bifold-double',
      'window',
    ],
  },
  {
    cat: 'fixture',
    types: ['toilet', 'shower', 'washbasin', 'bathtub', 'kitchen', 'refrigerator', 'washing-machine', 'dining-table', 'bed', 'sofa', 'aircon', 'stairs'],
  },
  { cat: 'text', types: ['text'] },
]

const TATAMI_JOU_OPTIONS: TatamiJou[] = ['4.5', '6-h', '6-v', '8', '10']

// クリックとドラッグ(範囲選択)を区別するための最小移動量(svg座標系のpx)
const MARQUEE_THRESHOLD = 4
const HISTORY_LIMIT = 30

interface Rect {
  x: number
  y: number
  w: number
  h: number
}

interface Snapshot {
  parts: Part[]
  bg: BgImage | null
}

const normalizeRect = (x0: number, y0: number, x1: number, y1: number): Rect => ({
  x: Math.min(x0, x1),
  y: Math.min(y0, y1),
  w: Math.abs(x1 - x0),
  h: Math.abs(y1 - y0),
})

const rectsIntersect = (a: Rect, b: Rect) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y

type DragState =
  | { mode: 'move'; id: string; startX: number; startY: number; origX: number; origY: number }
  | { mode: 'resize'; id: string; handle: ResizeHandle; startX: number; startY: number; orig: { x: number; y: number; w: number; h: number } }
  | { mode: 'bg-move'; startX: number; startY: number; origX: number; origY: number }
  | { mode: 'bg-resize'; handle: ResizeHandle; startX: number; startY: number; orig: { x: number; y: number; w: number; h: number } }
  | { mode: 'marquee'; startX: number; startY: number }
  | null

export default function FloorPlanEditor() {
  const [parts, setParts] = useState<Part[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [bg, setBg] = useState<BgImage | null>(null)
  const [bgOpacity, setBgOpacity] = useState(50)
  const [bgSelected, setBgSelected] = useState(false)
  const [selectMode, setSelectMode] = useState(false)

  // 四角く囲って複数選択したパーツ／下絵の範囲（ドラッグ中はライブプレビューを兼ねる）
  const [rectSelection, setRectSelection] = useState<Rect | null>(null)
  const [rectIds, setRectIds] = useState<Set<string>>(new Set())
  const [rectHitsBg, setRectHitsBg] = useState(false)

  const [history, setHistory] = useState<Snapshot[]>([])

  const svgRef = useRef<SVGSVGElement>(null)
  const dragRef = useRef<DragState>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const partsRef = useRef<Part[]>(parts)

  useEffect(() => {
    partsRef.current = parts
  }, [parts])

  const toSvgPoint = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current
    if (!svg) return { x: 0, y: 0 }
    const rect = svg.getBoundingClientRect()
    return { x: clientX - rect.left, y: clientY - rect.top }
  }, [])

  const updatePart = (id: string, patch: Partial<Part>) => {
    setParts((ps) => ps.map((p) => (p.id === id ? { ...p, ...patch } : p)))
  }

  const clearRectSelection = () => {
    setRectSelection(null)
    setRectIds(new Set())
    setRectHitsBg(false)
  }

  // 直前の1操作前の状態に戻せるよう、破壊的な変更の直前にスナップショットを積む。
  const pushHistory = (snapshotParts: Part[], snapshotBg: BgImage | null) => {
    setHistory((h) => [...h, { parts: snapshotParts, bg: snapshotBg }].slice(-HISTORY_LIMIT))
  }

  const undo = () => {
    setHistory((h) => {
      if (h.length === 0) return h
      const prev = h[h.length - 1]
      setParts(prev.parts)
      setBg(prev.bg)
      setSelectedId(null)
      setBgSelected(false)
      clearRectSelection()
      return h.slice(0, -1)
    })
  }

  // 配置済みパーツ・下絵をすべて含む範囲（+余白）を求める。何もなければキャンバス全体。
  const computeContentBBox = (): Rect => {
    const boxes: Rect[] = parts.map((p) => ({ x: p.x, y: p.y, w: p.w, h: p.h }))
    if (bg) boxes.push(bg)
    if (boxes.length === 0) return { x: 0, y: 0, w: CANVAS_W, h: CANVAS_H }
    const minX = Math.min(...boxes.map((b) => b.x))
    const minY = Math.min(...boxes.map((b) => b.y))
    const maxX = Math.max(...boxes.map((b) => b.x + b.w))
    const maxY = Math.max(...boxes.map((b) => b.y + b.h))
    const pad = 40
    const x = Math.max(0, minX - pad)
    const y = Math.max(0, minY - pad)
    return { x, y, w: Math.min(CANVAS_W, maxX + pad) - x, h: Math.min(CANVAS_H, maxY + pad) - y }
  }

  // 現在の図面をPNG画像として書き出し、ダウンロードさせる。
  // グリッド線・選択枠・リサイズハンドルなどのUI要素は含めず、パーツ・下絵の内容のみを出力する。
  const exportPng = () => {
    const svg = svgRef.current
    if (!svg) return
    setSelectedId(null)
    setBgSelected(false)
    clearRectSelection()

    // 選択解除がDOMに反映されるのを待ってからクローン・書き出しする。
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const clone = svg.cloneNode(true) as SVGSVGElement
        clone.querySelector('rect[fill="url(#grid)"]')?.remove()
        clone.querySelector('#grid')?.remove()

        const whiteBg = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
        whiteBg.setAttribute('x', '0')
        whiteBg.setAttribute('y', '0')
        whiteBg.setAttribute('width', String(CANVAS_W))
        whiteBg.setAttribute('height', String(CANVAS_H))
        whiteBg.setAttribute('fill', 'white')
        clone.insertBefore(whiteBg, clone.firstChild)

        const svgStr = new XMLSerializer().serializeToString(clone)
        const svgDataUrl = 'data:image/svg+xml;charset=utf-8;base64,' + btoa(unescape(encodeURIComponent(svgStr)))

        const bbox = computeContentBBox()
        const scale = 2
        const img = new Image()
        img.onload = () => {
          const canvas = document.createElement('canvas')
          canvas.width = bbox.w * scale
          canvas.height = bbox.h * scale
          const ctx = canvas.getContext('2d')
          if (!ctx) return
          ctx.drawImage(img, bbox.x, bbox.y, bbox.w, bbox.h, 0, 0, canvas.width, canvas.height)
          const a = document.createElement('a')
          a.href = canvas.toDataURL('image/png')
          a.download = 'floor-plan-edit.png'
          a.click()
        }
        img.src = svgDataUrl
      })
    })
  }

  const addPart = (type: PartType) => {
    pushHistory(parts, bg)
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
    clearRectSelection()
  }

  const deleteSelected = useCallback(() => {
    pushHistory(parts, bg)
    setSelectedId((id) => {
      if (id) setParts((ps) => ps.filter((p) => p.id !== id))
      return null
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parts, bg])

  const rotateSelected = () => {
    if (!selectedId) return
    pushHistory(parts, bg)
    setParts((ps) =>
      ps.map((p) => (p.id === selectedId ? { ...p, rotation: (((p.rotation + 90) % 360) as Part['rotation']) } : p)),
    )
  }

  // 畳数を指定すると、その帖数の標準的な敷き方に合わせて部屋のサイズも変更する（中心位置は維持）。
  const setTatamiJou = (jou: TatamiJou | null) => {
    if (!selectedId) return
    pushHistory(parts, bg)
    if (jou === null) {
      updatePart(selectedId, { tatamiJou: undefined })
      return
    }
    const layout = TATAMI_LAYOUTS[jou]
    const newW = layout.cols * GRID_PX
    const newH = layout.rows * GRID_PX
    setParts((ps) =>
      ps.map((p) => {
        if (p.id !== selectedId) return p
        const x = snap(p.x + (p.w - newW) / 2)
        const y = snap(p.y + (p.h - newH) / 2)
        return { ...p, x, y, w: newW, h: newH, tatamiJou: jou }
      }),
    )
  }

  // 選択中のパーツを拡大・縮小する（回転していても中心を保ったままw/hを直接変更するので、
  // 回転後は角ハンドルでリサイズできないという既存の制約を回避できる）。
  const scalePart = (factor: number) => {
    if (!selectedPart) return
    pushHistory(parts, bg)
    const newW = Math.max(MIN_SIZE, Math.round(selectedPart.w * factor))
    const newH = Math.max(MIN_SIZE, Math.round(selectedPart.h * factor))
    const x = selectedPart.x + (selectedPart.w - newW) / 2
    const y = selectedPart.y + (selectedPart.h - newH) / 2
    updatePart(selectedPart.id, { x, y, w: newW, h: newH })
  }

  const setWallWidth = (v: number) => {
    if (!selectedId || Number.isNaN(v)) return
    updatePart(selectedId, { wallWidth: v })
  }

  const setFontSize = (v: number) => {
    if (!selectedId || Number.isNaN(v)) return
    updatePart(selectedId, { fontSize: v })
  }

  const setFontFamily = (v: string) => {
    if (!selectedId) return
    pushHistory(parts, bg)
    updatePart(selectedId, { fontFamily: v })
  }

  // 下敷き画像の指定範囲を透明にくり抜く（JPEGでもcanvas経由でPNG化することで透過を実現）
  const eraseRectFromBg = useCallback((rect: Rect) => {
    setBg((b) => {
      if (!b || !rectsIntersect(rect, b)) return b
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        canvas.width = img.naturalWidth
        canvas.height = img.naturalHeight
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        ctx.drawImage(img, 0, 0)
        const scaleX = img.naturalWidth / b.w
        const scaleY = img.naturalHeight / b.h
        const ex = Math.max(0, (rect.x - b.x) * scaleX)
        const ey = Math.max(0, (rect.y - b.y) * scaleY)
        const ew = Math.min(canvas.width - ex, rect.w * scaleX)
        const eh = Math.min(canvas.height - ey, rect.h * scaleY)
        if (ew <= 0 || eh <= 0) return
        ctx.clearRect(ex, ey, ew, eh)
        setBg((cur) => (cur ? { ...cur, dataUrl: canvas.toDataURL('image/png') } : cur))
      }
      img.src = b.dataUrl
      return b
    })
  }, [])

  const deleteRectSelection = useCallback(() => {
    pushHistory(parts, bg)
    setParts((ps) => ps.filter((p) => !rectIds.has(p.id)))
    if (rectHitsBg && rectSelection) eraseRectFromBg(rectSelection)
    clearRectSelection()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parts, bg, rectIds, rectHitsBg, rectSelection, eraseRectFromBg])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault()
        undo()
        return
      }

      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (rectIds.size > 0 || rectHitsBg) {
          e.preventDefault()
          deleteRectSelection()
        } else if (selectedId) {
          e.preventDefault()
          deleteSelected()
        }
        return
      }

      if (selectedId && (e.key === 'ArrowUp' || e.key === 'ArrowDown' || e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
        e.preventDefault()
        const step = e.shiftKey ? SNAP : 1
        const dx = e.key === 'ArrowLeft' ? -step : e.key === 'ArrowRight' ? step : 0
        const dy = e.key === 'ArrowUp' ? -step : e.key === 'ArrowDown' ? step : 0
        setParts((ps) => ps.map((p) => (p.id === selectedId ? { ...p, x: p.x + dx, y: p.y + dy } : p)))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, deleteSelected, rectIds, rectHitsBg, deleteRectSelection])

  const onPartPointerDown = (e: ReactPointerEvent, part: Part) => {
    e.stopPropagation()
    const pt = toSvgPoint(e.clientX, e.clientY)
    // 範囲選択モード中、またはShiftを押しながらのドラッグは、パーツの上から始めても範囲選択(marquee)として扱う。
    if (selectMode || e.shiftKey) {
      dragRef.current = { mode: 'marquee', startX: pt.x, startY: pt.y }
      return
    }
    pushHistory(parts, bg)
    setSelectedId(part.id)
    setBgSelected(false)
    clearRectSelection()
    dragRef.current = { mode: 'move', id: part.id, startX: pt.x, startY: pt.y, origX: part.x, origY: part.y }
  }

  const onHandlePointerDown = (e: ReactPointerEvent, part: Part, handle: ResizeHandle) => {
    e.stopPropagation()
    pushHistory(parts, bg)
    const pt = toSvgPoint(e.clientX, e.clientY)
    dragRef.current = { mode: 'resize', id: part.id, handle, startX: pt.x, startY: pt.y, orig: { x: part.x, y: part.y, w: part.w, h: part.h } }
  }

  const onBgPointerDown = (e: ReactPointerEvent) => {
    if (!bg) return
    e.stopPropagation()
    const pt = toSvgPoint(e.clientX, e.clientY)
    // 範囲選択モード中、またはShiftを押しながらのドラッグは、下絵の上から始めても範囲選択(marquee)として扱う。
    // これにより、下絵で覆われた範囲でも「パーツも下絵も含めて」四角く囲って消せる。
    if (selectMode || e.shiftKey) {
      dragRef.current = { mode: 'marquee', startX: pt.x, startY: pt.y }
      return
    }
    pushHistory(parts, bg)
    setBgSelected(true)
    setSelectedId(null)
    clearRectSelection()
    dragRef.current = { mode: 'bg-move', startX: pt.x, startY: pt.y, origX: bg.x, origY: bg.y }
  }

  const onBgHandlePointerDown = (e: ReactPointerEvent, handle: ResizeHandle) => {
    if (!bg) return
    e.stopPropagation()
    pushHistory(parts, bg)
    const pt = toSvgPoint(e.clientX, e.clientY)
    dragRef.current = { mode: 'bg-resize', handle, startX: pt.x, startY: pt.y, orig: { x: bg.x, y: bg.y, w: bg.w, h: bg.h } }
  }

  // 空のキャンバス上でのpointerdownは即座に選択解除せず、範囲選択(marquee)ドラッグとして開始する。
  // 実際にはドラッグせずクリックだけだった場合は、pointerup側で選択解除にフォールバックする。
  const onCanvasPointerDown = (e: ReactPointerEvent) => {
    const pt = toSvgPoint(e.clientX, e.clientY)
    dragRef.current = { mode: 'marquee', startX: pt.x, startY: pt.y }
  }

  const loadBgFromDataUrl = useCallback((dataUrl: string) => {
    const img = new Image()
    img.onload = () => {
      const maxW = CANVAS_W * 0.8
      const maxH = CANVAS_H * 0.8
      const ratio = Math.min(maxW / img.width, maxH / img.height, 1)
      const w = img.width * ratio
      const h = img.height * ratio
      setBg((prevBg) => {
        pushHistory(partsRef.current, prevBg)
        return { dataUrl, x: (CANVAS_W - w) / 2, y: (CANVAS_H - h) / 2, w, h }
      })
    }
    img.src = dataUrl
  }, [])

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => loadBgFromDataUrl(reader.result as string)
    reader.readAsDataURL(file)
    e.target.value = ''
  }

  // Streamlit本体の「この画像を編集に送る」ボタンから ?bg=<画像URL> 付きで開かれた場合、
  // そのURLの画像を取得してトレース背景として自動読み込みする。
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const bgUrl = params.get('bg')
    if (!bgUrl) return
    window.history.replaceState({}, '', window.location.pathname)
    fetch(bgUrl)
      .then((res) => res.blob())
      .then((blob) => {
        const reader = new FileReader()
        reader.onload = () => loadBgFromDataUrl(reader.result as string)
        reader.readAsDataURL(blob)
      })
      .catch((err) => console.error('トレース背景の自動読み込みに失敗しました', err))
  }, [loadBgFromDataUrl])

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
      // デフォルトは1px単位の細かい移動・リサイズ。Altキーを押している間だけグリッドにスナップする。
      const fine = !e.altKey
      if (drag.mode === 'move') {
        updatePart(drag.id, fine ? { x: drag.origX + dx, y: drag.origY + dy } : { x: snap(drag.origX + dx), y: snap(drag.origY + dy) })
      } else if (drag.mode === 'resize') {
        updatePart(drag.id, resizeRect(drag.orig, drag.handle, dx, dy, !fine))
      } else if (drag.mode === 'bg-move') {
        setBg((b) => (b ? { ...b, x: drag.origX + dx, y: drag.origY + dy } : b))
      } else if (drag.mode === 'bg-resize') {
        setBg((b) => (b ? { ...b, ...resizeRect(drag.orig, drag.handle, dx, dy, false) } : b))
      } else if (drag.mode === 'marquee') {
        const rect = normalizeRect(drag.startX, drag.startY, pt.x, pt.y)
        setRectSelection(rect)
        setRectIds(new Set(parts.filter((p) => rectsIntersect(rect, { x: p.x, y: p.y, w: p.w, h: p.h })).map((p) => p.id)))
        setRectHitsBg(bg ? rectsIntersect(rect, bg) : false)
      }
    }

    const onUp = (e: PointerEvent) => {
      const drag = dragRef.current
      if (drag?.mode === 'marquee') {
        const pt = toSvgPoint(e.clientX, e.clientY)
        const dist = Math.hypot(pt.x - drag.startX, pt.y - drag.startY)
        if (dist < MARQUEE_THRESHOLD) {
          setSelectedId(null)
          setBgSelected(false)
          clearRectSelection()
        } else {
          const rect = normalizeRect(drag.startX, drag.startY, pt.x, pt.y)
          const ids = new Set(parts.filter((p) => rectsIntersect(rect, { x: p.x, y: p.y, w: p.w, h: p.h })).map((p) => p.id))
          const hitsBg = bg ? rectsIntersect(rect, bg) : false
          if (ids.size === 0 && !hitsBg) {
            clearRectSelection()
          } else {
            setSelectedId(null)
            setBgSelected(false)
            setRectSelection(rect)
            setRectIds(ids)
            setRectHitsBg(hitsBg)
          }
        }
      }
      dragRef.current = null
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
  }, [toSvgPoint, parts, bg])

  const editLabel = (part: Part) => {
    if (PART_DEFS[part.type].category === 'opening') return
    const next = window.prompt('ラベルを入力', part.label)
    if (next !== null) {
      pushHistory(parts, bg)
      updatePart(part.id, { label: next })
    }
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

        <button type="button" className="export-button" onClick={exportPng} title="現在の図面をPNG画像として保存">
          <Download size={15} /> PNG画像として保存
        </button>

        <div className="toolbar-row">
          <button type="button" onClick={undo} disabled={history.length === 0} title="1つ前の状態に戻す（Cmd/Ctrl+Zでも可）">
            <Undo2 size={14} /> 元に戻す
          </button>
          <button
            type="button"
            className={selectMode ? 'active' : ''}
            onClick={() => setSelectMode((v) => !v)}
            title="ドラッグで四角く囲んで、パーツ・下絵をまとめて削除"
          >
            <BoxSelect size={14} /> 範囲選択
          </button>
        </div>
        <p className="hint">
          {selectMode
            ? '範囲選択モード：ドラッグで囲んで削除（パーツ・下絵とも）'
            : 'Shift+ドラッグでも範囲選択できます'}
        </p>

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
                  pushHistory(parts, bg)
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
          style={selectMode ? { cursor: 'crosshair' } : undefined}
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
            <g onPointerDown={onBgPointerDown} style={{ cursor: selectMode ? 'crosshair' : 'move' }}>
              <image href={bg.dataUrl} x={bg.x} y={bg.y} width={bg.w} height={bg.h} opacity={bgOpacity / 100} preserveAspectRatio="none" />
              {bgSelected && (
                <>
                  <rect x={bg.x} y={bg.y} width={bg.w} height={bg.h} fill="none" stroke="#3b82f6" strokeWidth={1} strokeDasharray="4,3" />
                  {renderHandles(bg.x, bg.y, bg.w, bg.h, 0, onBgHandlePointerDown)}
                </>
              )}
              {!bgSelected && rectHitsBg && (
                <rect x={bg.x} y={bg.y} width={bg.w} height={bg.h} fill="none" stroke="#3b82f6" strokeWidth={1} strokeDasharray="4,3" />
              )}
            </g>
          )}

          {sortedParts.map((part) => {
            const isSelected = part.id === selectedId || rectIds.has(part.id)
            return (
              <g
                key={part.id}
                transform={`translate(${part.x} ${part.y}) rotate(${part.rotation} ${part.w / 2} ${part.h / 2})`}
                onPointerDown={(e) => onPartPointerDown(e, part)}
                onDoubleClick={() => editLabel(part)}
                style={{ cursor: selectMode ? 'crosshair' : 'move' }}
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

          {rectSelection && (
            <rect
              x={rectSelection.x}
              y={rectSelection.y}
              width={rectSelection.w}
              height={rectSelection.h}
              fill="rgba(59,130,246,0.08)"
              stroke="#3b82f6"
              strokeWidth={1}
              strokeDasharray="4,3"
              pointerEvents="none"
            />
          )}
        </svg>

        {toolbarTarget && (
          <div
            className="floating-toolbar"
            style={{
              left: toolbarTarget.x,
              top: Math.max(0, toolbarTarget.y - 52),
            }}
          >
            {selectedPart && selectedPart.type === 'washitsu' && (
              <select
                value={selectedPart.tatamiJou ?? ''}
                onChange={(e) => setTatamiJou(e.target.value ? (e.target.value as TatamiJou) : null)}
                title="畳数を指定すると標準的な敷き方で自動レイアウトします"
              >
                <option value="">自由サイズ</option>
                {TATAMI_JOU_OPTIONS.map((j) => (
                  <option key={j} value={j}>
                    {TATAMI_JOU_LABELS[j]}
                  </option>
                ))}
              </select>
            )}
            {selectedPart && PART_DEFS[selectedPart.type].category !== 'opening' && WALL_TYPES.has(selectedPart.type) && (
              <input
                type="number"
                min={1}
                max={30}
                className="num-input"
                value={selectedPart.wallWidth ?? DEFAULT_WALL_WIDTH[selectedPart.type] ?? 5}
                onFocus={() => pushHistory(parts, bg)}
                onChange={(e) => setWallWidth(Number(e.target.value))}
                title="壁線の太さ"
              />
            )}
            {selectedPart && PART_DEFS[selectedPart.type].category !== 'opening' && (
              <input
                type="number"
                min={6}
                max={60}
                className="num-input"
                value={selectedPart.fontSize ?? DEFAULT_FONT_SIZE[selectedPart.type] ?? 13}
                onFocus={() => pushHistory(parts, bg)}
                onChange={(e) => setFontSize(Number(e.target.value))}
                title="文字の大きさ"
              />
            )}
            {selectedPart && PART_DEFS[selectedPart.type].category !== 'opening' && (
              <select value={selectedPart.fontFamily ?? FONT_STACK_DEFAULT} onChange={(e) => setFontFamily(e.target.value)} title="フォント">
                {FONT_FAMILY_OPTIONS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            )}
            {selectedPart && PART_DEFS[selectedPart.type].resizable && (
              <>
                <button type="button" onClick={() => scalePart(1 / 1.15)} title="縮小">
                  <ZoomOut size={16} />
                </button>
                <button type="button" onClick={() => scalePart(1.15)} title="拡大">
                  <ZoomIn size={16} />
                </button>
              </>
            )}
            {selectedPart && PART_DEFS[selectedPart.type].rotatable && (
              <button type="button" onClick={rotateSelected} title="90度回転">
                <RotateCw size={16} /> 回転
              </button>
            )}
            <button
              type="button"
              onClick={
                selectedPart
                  ? deleteSelected
                  : () => {
                      pushHistory(parts, bg)
                      setBg(null)
                      setBgSelected(false)
                    }
              }
              title="削除"
            >
              <Trash2 size={16} /> 削除
            </button>
          </div>
        )}

        {rectSelection && (rectIds.size > 0 || rectHitsBg) && (
          <div
            className="floating-toolbar"
            style={{
              left: rectSelection.x,
              top: Math.max(0, rectSelection.y - 52),
            }}
          >
            <button type="button" onClick={deleteRectSelection} title="選択範囲を削除（パーツ・下絵とも）">
              <Trash2 size={16} /> 選択範囲を削除
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
