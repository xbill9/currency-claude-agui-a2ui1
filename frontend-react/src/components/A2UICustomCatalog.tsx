import React from "react";
import { z } from "zod";
import { createCatalog } from "@copilotkit/a2ui-renderer";

const customCatalogDefinitions = {
  Card: {
    description: "A card container",
    props: z.object({
      title: z.string().optional(),
      child: z.string().optional(),
      children: z.array(z.string()).optional(),
    }),
  },
  Text: {
    description: "A text element",
    props: z.object({
      value: z.string().optional(),
      text: z.string().optional(),
      variant: z.string().optional(),
    }),
  },
  Column: {
    description: "A column layout container",
    props: z.object({
      child: z.string().optional(),
      children: z.array(z.string()).optional(),
    }),
  },
  Row: {
    description: "A row layout container",
    props: z.object({
      children: z.array(z.string()).optional(),
    }),
  },
  Table: {
    description: "A table element",
    props: z.object({
      headers: z.array(z.any()).optional(),
      rows: z.array(z.any()).optional(),
    }),
  },
  BarChart: {
    description: "A vertical bar chart for showing rates",
    props: z.object({
      title: z.string().optional(),
      labels: z.array(z.string()),
      values: z.array(z.number()),
      color: z.string().optional(),
    }),
  },
  LineChart: {
    description: "An SVG line chart with gradients for showing historical rates",
    props: z.object({
      title: z.string().optional(),
      labels: z.array(z.string()),
      values: z.array(z.number()),
      color: z.string().optional(),
    }),
  },
};

const customCatalogRenderers = {
  Card: ({ props, children }: any) => {
    return (
      <div className="bg-slate-800/90 border border-slate-700/80 rounded-xl p-4 my-2 shadow-xl text-white w-full">
        {props.title && (
          <h4 className="text-sm font-bold border-b border-slate-700/50 pb-2 mb-3 tracking-wide flex items-center gap-2">
            {props.title}
          </h4>
        )}
        {props.child && children(props.child)}
        {props.children && props.children.map((id: string) => (
          <React.Fragment key={id}>{children(id)}</React.Fragment>
        ))}
      </div>
    );
  },
  Text: ({ props }: any) => {
    const textVal = props.value || props.text || "";
    const variant = props.variant || "body";
    if (variant === "h2") {
      return <h2 className="text-xl font-extrabold text-emerald-400 my-1">{textVal}</h2>;
    }
    if (variant === "h3") {
      return <h3 className="text-lg font-bold text-white my-1">{textVal}</h3>;
    }
    if (variant === "h4") {
      return <h4 className="text-base font-semibold text-white my-1">{textVal}</h4>;
    }
    if (variant === "caption") {
      return <p className="text-xs text-slate-400 my-1">{textVal}</p>;
    }
    return <p className="text-sm text-slate-300 my-1">{textVal}</p>;
  },
  Column: ({ props, children }: any) => {
    return (
      <div className="flex flex-col gap-2 w-full">
        {props.child && children(props.child)}
        {props.children && props.children.map((id: string) => (
          <React.Fragment key={id}>{children(id)}</React.Fragment>
        ))}
      </div>
    );
  },
  Row: ({ props, children }: any) => {
    return (
      <div className="flex flex-row items-center gap-3 w-full">
        {props.children && props.children.map((id: string) => (
          <React.Fragment key={id}>{children(id)}</React.Fragment>
        ))}
      </div>
    );
  },
  Table: ({ props }: any) => {
    const headers = props.headers || [];
    const rows = props.rows || [];
    return (
      <div className="bg-slate-900 border border-slate-700/50 rounded-xl p-2 my-2 overflow-x-auto w-full">
        <table className="w-full text-xs text-left border-collapse">
          {headers.length > 0 && (
            <thead>
              <tr className="border-b border-slate-700">
                {headers.map((h: any, idx: number) => (
                  <th key={idx} className="p-2 text-slate-400 font-semibold">
                    {typeof h === "string" ? h : h.value || ""}
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {rows.map((row: any, rIdx: number) => {
              const cells = Array.isArray(row) ? row : row.cells || [];
              return (
                <tr key={rIdx} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                  {cells.map((cell: any, cIdx: number) => (
                    <td key={cIdx} className="p-2 text-slate-300">
                      {typeof cell === "string" ? cell : cell.value || ""}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  },
  BarChart: ({ props }: any) => {
    const { title, labels, values, color = "#10b981" } = props;
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal;
    const baseline = range > 1e-5 ? (minVal - range * 0.15) : 0;
    const denom = maxVal - baseline > 0 ? (maxVal - baseline) : 1;

    return (
      <div className="bg-slate-900/50 border border-slate-700/50 rounded-xl p-4 mt-2 w-full">
        {title && <h5 className="m-0 mb-3 text-white text-sm font-semibold">{title}</h5>}
        <div className="flex items-end justify-around h-[140px] py-2 border-b border-slate-700">
          {labels.map((label: string, idx: number) => {
            const val = values[idx] ?? 0;
            const heightPercent = range > 0 ? (((val - baseline) / denom) * 100) : 100;
            return (
              <div key={idx} className="flex flex-col items-center flex-1 gap-2">
                <span className="text-[10px] text-white font-medium">{val.toFixed(4)}</span>
                <div
                  style={{
                    height: `${heightPercent}%`,
                    backgroundColor: color,
                  }}
                  className="w-5 rounded-t transition-all duration-500 ease-out"
                  title={`${val}`}
                />
                <span className="text-[10px] text-slate-400">{label}</span>
              </div>
            );
          })}
        </div>
      </div>
    );
  },
  LineChart: ({ props }: any) => {
    const { title, labels, values, color = "#3b82f6" } = props;
    if (labels.length < 2 || values.length < 2) {
      return <p className="text-red-400 text-xs">Not enough data points for line chart.</p>;
    }

    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal;
    const baseline = range > 1e-5 ? (minVal - range * 0.15) : (minVal * 0.9);
    const denom = maxVal - baseline > 0 ? (maxVal - baseline) : 1;

    const width = 350;
    const height = 150;
    const padX = 25;
    const padY = 20;

    const points: { x: number; y: number }[] = [];
    labels.forEach((label: string, idx: number) => {
      const val = values[idx] || 0;
      const pctY = (val - baseline) / denom;
      const x = padX + (idx / (labels.length - 1)) * (width - 2 * padX);
      const y = height - padY - pctY * (height - 2 * padY);
      points.push({ x, y });
    });

    let areaD = `M ${points[0].x} ${height - padY}`;
    points.forEach((p) => {
      areaD += ` L ${p.x} ${p.y}`;
    });
    areaD += ` L ${points[points.length - 1].x} ${height - padY} Z`;

    let lineD = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      lineD += ` L ${points[i].x} ${points[i].y}`;
    }

    const gradId = `glow-grad-${Math.random().toString(36).substring(2, 9)}`;

    return (
      <div className="bg-slate-900/50 border border-slate-700/50 rounded-xl p-4 mt-2 w-full">
        {title && <h5 className="m-0 mb-3 text-white text-sm font-semibold">{title}</h5>}
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-[150px] overflow-visible">
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.25" />
              <stop offset="100%" stopColor={color} stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 1, 2, 3].map((i) => {
            const gridY = padY + (i / 3) * (height - 2 * padY);
            return (
              <line
                key={i}
                x1={padX}
                y1={gridY}
                x2={width - padX}
                y2={gridY}
                stroke="rgba(255,255,255,0.05)"
                strokeDasharray="2,2"
              />
            );
          })}

          <path d={areaD} fill={`url(#${gradId})`} />

          <path
            d={lineD}
            stroke={color}
            strokeWidth="2.5"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {points.map((p, idx) => (
            <g key={idx}>
              <circle
                cx={p.x}
                cy={p.y}
                r="4"
                fill="#fff"
                stroke={color}
                strokeWidth="2"
              />
              <text
                x={p.x}
                y={height - 5}
                textAnchor="middle"
                fill="rgba(255,255,255,0.4)"
                fontSize="8px"
              >
                {labels[idx]}
              </text>
              <text
                x={p.x}
                y={p.y - 7}
                textAnchor="middle"
                fill="#fff"
                fontSize="8px"
                fontWeight="500"
              >
                {values[idx].toFixed(4)}
              </text>
            </g>
          ))}
        </svg>
      </div>
    );
  },
};

export const customCatalog = createCatalog(customCatalogDefinitions as any, customCatalogRenderers as any, {
  catalogId: "https://a2ui.org/specification/v0_9/basic_catalog.json"
});


