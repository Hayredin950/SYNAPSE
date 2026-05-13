'use client'

/**
 * TopicPieChart — Topic distribution pie chart for dashboard.
 * Phase 7.1 — Design System & Animations (Week 19)
 */

import React, { useState } from 'react'
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer, Sector,
} from 'recharts'
import { SkeletonChart } from '@/components/ui/SkeletonLoader'
import { clsx } from 'clsx'

interface TopicDataPoint {
  topic: string
  count: number
}

interface TopicPieChartProps {
  data?:      TopicDataPoint[]
  height?:    number
  className?: string
  loading?:   boolean
  title?:     string
}

const COLORS = [
  '#6366f1', '#06b6d4', '#8b5cf6', '#22c55e',
  '#f59e0b', '#ef4444', '#ec4899', '#14b8a6',
  '#f97316', '#64748b',
]

function ActiveShape(props: any) {
  const {
    cx, cy, innerRadius, outerRadius, startAngle, endAngle,
    fill, payload, percent, value,
  } = props
  return (
    <g>
      <text x={cx} y={cy - 10} textAnchor="middle" fill={fill} className="text-sm font-semibold" fontSize={13}>
        {payload.topic}
      </text>
      <text x={cx} y={cy + 10} textAnchor="middle" fill="#94a3b8" fontSize={11}>
        {value} · {(percent * 100).toFixed(0)}%
      </text>
      <Sector cx={cx} cy={cy} innerRadius={innerRadius} outerRadius={outerRadius + 6}
        startAngle={startAngle} endAngle={endAngle} fill={fill} />
      <Sector cx={cx} cy={cy} innerRadius={outerRadius + 10} outerRadius={outerRadius + 13}
        startAngle={startAngle} endAngle={endAngle} fill={fill} />
    </g>
  )
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 shadow-lg text-sm">
      <p className="font-semibold text-slate-900 dark:text-white">{payload[0].name}</p>
      <p style={{ color: payload[0].fill }}>Count: <strong>{payload[0].value}</strong></p>
    </div>
  )
}

const DEFAULT_DATA: TopicDataPoint[] = [
  { topic: 'AI/ML',       count: 45 },
  { topic: 'Web Dev',     count: 32 },
  { topic: 'DevOps',      count: 21 },
  { topic: 'Security',    count: 18 },
  { topic: 'Data Eng.',   count: 15 },
  { topic: 'Mobile',      count: 12 },
  { topic: 'Other',       count: 8  },
]

export function TopicPieChart({
  data    = DEFAULT_DATA,
  height  = 280,
  className,
  loading = false,
  title   = 'Topic Distribution',
}: TopicPieChartProps) {
  const [activeIndex, setActiveIndex] = useState<number | undefined>(undefined)

  if (loading) return <SkeletonChart height={height} className={className} />

  return (
    <div className={clsx('w-full', className)}>
      {title && (
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">{title}</h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={data}
            cx="50%" cy="50%"
            innerRadius={60} outerRadius={90}
            dataKey="count"
            nameKey="topic"
            activeIndex={activeIndex}
            activeShape={<ActiveShape />}
            onMouseEnter={(_, index) => setActiveIndex(index)}
            onMouseLeave={() => setActiveIndex(undefined)}
            animationBegin={0}
            animationDuration={800}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="transparent" />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
          <Legend
            iconType="circle" iconSize={8}
            formatter={(v) => <span className="text-xs text-slate-400">{v}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

export default TopicPieChart
