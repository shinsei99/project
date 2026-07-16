import type { Part } from './types'

// 各パーツをローカル座標(0,0)-(w,h)で描画する。回転・移動は呼び出し側のtransformで行う。
export function PartSymbol({ part }: { part: Part }) {
  const { id, type, w, h, label } = part

  switch (type) {
    case 'room':
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="none" stroke="black" strokeWidth={3} />
          {label && (
            <text x={w / 2} y={h / 2} textAnchor="middle" dominantBaseline="middle" fontSize={13} fill="black">
              {label}
            </text>
          )}
        </>
      )

    case 'washitsu': {
      const cols = Math.max(1, Math.round(w / 40))
      const rows = Math.max(1, Math.round(h / 40))
      const cw = w / cols
      const rh = h / rows
      const dividers = []
      for (let r = 0; r < rows; r++) {
        const offset = r % 2 === 1 ? cw / 2 : 0
        for (let c = 0; c <= cols; c++) {
          const x = offset + c * cw
          if (x <= 0 || x >= w) continue
          dividers.push(<line key={`v${r}-${c}`} x1={x} y1={r * rh} x2={x} y2={(r + 1) * rh} stroke="black" strokeWidth={0.75} />)
        }
      }
      for (let r = 1; r < rows; r++) {
        dividers.push(<line key={`h${r}`} x1={0} y1={r * rh} x2={w} y2={r * rh} stroke="black" strokeWidth={0.75} />)
      }
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="none" stroke="black" strokeWidth={3} />
          {dividers}
          {label && (
            <text x={w / 2} y={h / 2} textAnchor="middle" dominantBaseline="middle" fontSize={13} fill="black" stroke="white" strokeWidth={3} paintOrder="stroke">
              {label}
            </text>
          )}
        </>
      )
    }

    case 'genkan': {
      const stepY = h * 0.3
      const clipId = `genkan-clip-${id}`
      const hatchCount = Math.ceil((w + stepY) / 8)
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="none" stroke="black" strokeWidth={3} />
          <defs>
            <clipPath id={clipId}>
              <rect x={0} y={0} width={w} height={stepY} />
            </clipPath>
          </defs>
          <g clipPath={`url(#${clipId})`}>
            {Array.from({ length: hatchCount }).map((_, i) => {
              const x = i * 8 - stepY
              return <line key={i} x1={x} y1={0} x2={x + stepY} y2={stepY} stroke="black" strokeWidth={0.5} />
            })}
          </g>
          <line x1={0} y1={stepY} x2={w} y2={stepY} stroke="black" strokeWidth={1.5} />
          {label && (
            <text x={w / 2} y={(stepY + h) / 2} textAnchor="middle" dominantBaseline="middle" fontSize={12} fill="black">
              {label}
            </text>
          )}
        </>
      )
    }

    case 'hallway':
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="none" stroke="black" strokeWidth={2} />
          {label && (
            <text x={w / 2} y={h / 2} textAnchor="middle" dominantBaseline="middle" fontSize={11} fill="black">
              {label}
            </text>
          )}
        </>
      )

    case 'wall':
      return <rect x={0} y={0} width={w} height={h} fill="black" stroke="none" />

    case 'pillar':
      return <rect x={0} y={0} width={w} height={h} fill="black" stroke="none" />

    case 'storage':
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="white" stroke="black" strokeWidth={1.5} />
          <line x1={0} y1={0} x2={w} y2={h} stroke="black" strokeWidth={1} />
          <line x1={w} y1={0} x2={0} y2={h} stroke="black" strokeWidth={1} />
          {label && (
            <text x={w / 2} y={h / 2} textAnchor="middle" dominantBaseline="middle" fontSize={10} fill="black">
              {label}
            </text>
          )}
        </>
      )

    case 'terrace':
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="none" stroke="black" strokeWidth={2} />
          <rect x={4} y={4} width={Math.max(w - 8, 0)} height={Math.max(h - 8, 0)} fill="none" stroke="black" strokeWidth={1} />
          {label && (
            <text x={w / 2} y={h / 2} textAnchor="middle" dominantBaseline="middle" fontSize={11} fill="black">
              {label}
            </text>
          )}
        </>
      )

    case 'door-hinged': {
      const r = Math.min(w, h) || 1
      return (
        <>
          <line x1={0} y1={h} x2={w} y2={h} stroke="black" strokeWidth={2} />
          <line x1={0} y1={h} x2={0} y2={Math.max(h - r, 0)} stroke="black" strokeWidth={1.5} />
          <path d={`M 0 ${Math.max(h - r, 0)} A ${r} ${r} 0 0 1 ${w} ${h}`} fill="none" stroke="black" strokeWidth={1} strokeDasharray="3,2" />
        </>
      )
    }

    case 'door-sliding':
      return (
        <>
          <line x1={0} y1={h} x2={w} y2={h} stroke="black" strokeWidth={2} />
          <rect x={w * 0.05} y={0} width={w * 0.42} height={Math.max(h, 3)} fill="none" stroke="black" strokeWidth={1.2} />
          <rect x={w * 0.53} y={0} width={w * 0.42} height={Math.max(h, 3)} fill="none" stroke="black" strokeWidth={1.2} />
        </>
      )

    case 'door-double': {
      const half = w / 2
      const r = Math.min(half, h) || 1
      return (
        <>
          <line x1={0} y1={h} x2={w} y2={h} stroke="black" strokeWidth={2} />
          <line x1={0} y1={h} x2={0} y2={Math.max(h - r, 0)} stroke="black" strokeWidth={1.5} />
          <path d={`M 0 ${Math.max(h - r, 0)} A ${r} ${r} 0 0 1 ${half} ${h}`} fill="none" stroke="black" strokeWidth={1} strokeDasharray="3,2" />
          <line x1={w} y1={h} x2={w} y2={Math.max(h - r, 0)} stroke="black" strokeWidth={1.5} />
          <path d={`M ${w} ${Math.max(h - r, 0)} A ${r} ${r} 0 0 0 ${half} ${h}`} fill="none" stroke="black" strokeWidth={1} strokeDasharray="3,2" />
        </>
      )
    }

    case 'door-bifold':
      return (
        <>
          <line x1={0} y1={h} x2={w} y2={h} stroke="black" strokeWidth={2} />
          <path
            d={`M 0 ${h} L ${w * 0.25} ${0} L ${w * 0.5} ${h} L ${w * 0.75} 0 L ${w} ${h}`}
            fill="none"
            stroke="black"
            strokeWidth={1.2}
          />
        </>
      )

    case 'window':
      return (
        <>
          <line x1={0} y1={h * 0.25} x2={w} y2={h * 0.25} stroke="black" strokeWidth={1.5} />
          <line x1={0} y1={h * 0.75} x2={w} y2={h * 0.75} stroke="black" strokeWidth={1.5} />
        </>
      )

    case 'toilet': {
      const cx = w / 2
      return (
        <>
          <rect x={w * 0.15} y={0} width={w * 0.7} height={h * 0.2} fill="none" stroke="black" strokeWidth={1.5} />
          <path
            d={`M ${cx - w * 0.3} ${h * 0.28} Q ${cx - w * 0.35} ${h * 0.9} ${cx} ${h * 0.97} Q ${cx + w * 0.35} ${h * 0.9} ${cx + w * 0.3} ${h * 0.28} Z`}
            fill="none"
            stroke="black"
            strokeWidth={1.5}
          />
        </>
      )
    }

    case 'shower':
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="none" stroke="black" strokeWidth={1.5} />
          <line x1={0} y1={0} x2={w} y2={h} stroke="black" strokeWidth={0.75} />
          <line x1={w} y1={0} x2={0} y2={h} stroke="black" strokeWidth={0.75} />
          <circle cx={w / 2} cy={h / 2} r={Math.min(w, h) * 0.08} fill="none" stroke="black" strokeWidth={1} />
        </>
      )

    case 'washbasin':
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="none" stroke="black" strokeWidth={1.5} />
          <ellipse cx={w / 2} cy={h * 0.55} rx={w * 0.38} ry={h * 0.32} fill="none" stroke="black" strokeWidth={1.2} />
          <circle cx={w / 2} cy={h * 0.15} r={2} fill="black" />
        </>
      )

    case 'bathtub': {
      const r = Math.min(w, h) * 0.15
      return (
        <>
          <rect x={0} y={0} width={w} height={h} rx={r} ry={r} fill="none" stroke="black" strokeWidth={1.5} />
          <rect x={w * 0.12} y={h * 0.08} width={w * 0.76} height={h * 0.7} rx={r * 0.8} ry={r * 0.8} fill="none" stroke="black" strokeWidth={1} />
          <circle cx={w / 2} cy={h * 0.92} r={Math.min(w, h) * 0.05} fill="none" stroke="black" strokeWidth={1} />
        </>
      )
    }

    case 'kitchen':
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="none" stroke="black" strokeWidth={1.5} />
          <rect x={w * 0.08} y={h * 0.2} width={w * 0.3} height={h * 0.6} fill="none" stroke="black" strokeWidth={1} />
          <circle cx={w * 0.62} cy={h * 0.5} r={h * 0.22} fill="none" stroke="black" strokeWidth={1} />
          <circle cx={w * 0.85} cy={h * 0.5} r={h * 0.22} fill="none" stroke="black" strokeWidth={1} />
        </>
      )

    case 'refrigerator':
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="none" stroke="black" strokeWidth={1.5} />
          <line x1={0} y1={h * 0.3} x2={w} y2={h * 0.3} stroke="black" strokeWidth={1} />
          <line x1={w * 0.5} y1={0} x2={w * 0.5} y2={h * 0.3} stroke="black" strokeWidth={0.75} />
        </>
      )

    case 'washing-machine':
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="none" stroke="black" strokeWidth={1.5} />
          <circle cx={w / 2} cy={h / 2} r={Math.min(w, h) * 0.32} fill="none" stroke="black" strokeWidth={1.2} />
          <circle cx={w / 2} cy={h / 2} r={Math.min(w, h) * 0.18} fill="none" stroke="black" strokeWidth={0.75} />
        </>
      )

    case 'dining-table': {
      const chairR = Math.min(w, h) * 0.12
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="none" stroke="black" strokeWidth={1.5} />
          <circle cx={w * 0.2} cy={-chairR * 0.6} r={chairR} fill="none" stroke="black" strokeWidth={1} />
          <circle cx={w * 0.5} cy={-chairR * 0.6} r={chairR} fill="none" stroke="black" strokeWidth={1} />
          <circle cx={w * 0.8} cy={-chairR * 0.6} r={chairR} fill="none" stroke="black" strokeWidth={1} />
          <circle cx={w * 0.2} cy={h + chairR * 0.6} r={chairR} fill="none" stroke="black" strokeWidth={1} />
          <circle cx={w * 0.5} cy={h + chairR * 0.6} r={chairR} fill="none" stroke="black" strokeWidth={1} />
          <circle cx={w * 0.8} cy={h + chairR * 0.6} r={chairR} fill="none" stroke="black" strokeWidth={1} />
        </>
      )
    }

    case 'bed':
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="none" stroke="black" strokeWidth={1.5} />
          <rect x={w * 0.1} y={h * 0.04} width={w * 0.8} height={h * 0.16} fill="none" stroke="black" strokeWidth={1} />
          <line x1={0} y1={h * 0.3} x2={w} y2={h * 0.3} stroke="black" strokeWidth={0.75} />
        </>
      )

    case 'sofa':
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="none" stroke="black" strokeWidth={1.5} />
          <rect x={0} y={0} width={w} height={h * 0.25} fill="none" stroke="black" strokeWidth={1} />
          <rect x={0} y={0} width={w * 0.08} height={h} fill="none" stroke="black" strokeWidth={1} />
          <rect x={w * 0.92} y={0} width={w * 0.08} height={h} fill="none" stroke="black" strokeWidth={1} />
        </>
      )

    case 'aircon':
      return <rect x={0} y={0} width={w} height={h} fill="white" stroke="black" strokeWidth={1.2} />

    case 'stairs': {
      const steps = 6
      const lines = []
      for (let i = 1; i < steps; i++) {
        const y = (h / steps) * i
        lines.push(<line key={i} x1={0} y1={y} x2={w} y2={y} stroke="black" strokeWidth={1} />)
      }
      return (
        <>
          <rect x={0} y={0} width={w} height={h} fill="none" stroke="black" strokeWidth={1.5} />
          {lines}
          <line x1={w / 2} y1={h * 0.92} x2={w / 2} y2={h * 0.12} stroke="black" strokeWidth={1.5} markerEnd="url(#arrow-up)" />
          <text x={w / 2 + 8} y={h * 0.22} fontSize={11} fill="black">UP</text>
        </>
      )
    }

    case 'text':
      return (
        <text x={0} y={h * 0.8} fontSize={16} fill="black">
          {label}
        </text>
      )

    default:
      return null
  }
}
