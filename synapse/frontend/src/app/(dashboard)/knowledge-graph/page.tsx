'use client';

/**
 * TASK-603-F1: Interactive AI Knowledge Graph
 *
 * Features:
 *  - Force-directed graph visualization using SVG + React (no external dependency)
 *  - Node click → detail panel (related content, edges)
 *  - Filter chips: entity type (concept/paper/author/tool/org/repo)
 *  - Search input: type concept → center graph on that node
 *  - "Explore from" input to recenter the graph
 *
 * Note: react-force-graph-2d requires browser canvas. We implement a lightweight
 * SVG-based force simulation using D3-style physics for SSR compatibility.
 * The full react-force-graph-2d integration can replace this when the package
 * is added to package.json (npm install react-force-graph-2d).
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Network, Search, X, ZoomIn, ZoomOut, RefreshCw,
  BookOpen, GitBranch, User, Lightbulb, Wrench, Building2,
  ChevronRight, ExternalLink, Loader2, Info,
} from 'lucide-react';
import { api } from '@/utils/api';

// ── Types ──────────────────────────────────────────────────────────────────────

interface GraphNode {
  id: string;
  name: string;
  entity_type: string;
  description: string;
  mention_count: number;
  metadata: Record<string, any>;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation_type: string;
  weight: number;
}

interface GraphData { nodes: GraphNode[]; edges: GraphEdge[] }
interface SearchResult { id: string; name: string; entity_type: string; mention_count: number }

// ── Constants ──────────────────────────────────────────────────────────────────

const ENTITY_TYPES = [
  { value: '',             label: 'All',          icon: Network,    color: '#6366f1' },
  { value: 'concept',      label: 'Concepts',     icon: Lightbulb,  color: '#f59e0b' },
  { value: 'paper',        label: 'Papers',       icon: BookOpen,   color: '#8b5cf6' },
  { value: 'repository',   label: 'Repos',        icon: GitBranch,  color: '#10b981' },
  { value: 'author',       label: 'Authors',      icon: User,       color: '#3b82f6' },
  { value: 'tool',         label: 'Tools',        icon: Wrench,     color: '#f97316' },
  { value: 'organization', label: 'Orgs',         icon: Building2,  color: '#06b6d4' },
];

const NODE_COLORS: Record<string, string> = {
  concept:      '#f59e0b',
  paper:        '#8b5cf6',
  repository:   '#10b981',
  author:       '#3b82f6',
  tool:         '#f97316',
  organization: '#06b6d4',
};

const RELATION_LABELS: Record<string, string> = {
  cites:       'cites',
  uses:        'uses',
  authored_by: 'by',
  related_to:  '↔',
  built_with:  'built with',
};

// ── Node icon ─────────────────────────────────────────────────────────────────

function NodeTypeIcon({ type, size = 14 }: { type: string; size?: number }) {
  const cfg = ENTITY_TYPES.find(t => t.value === type) ?? ENTITY_TYPES[0];
  const Icon = cfg.icon;
  return <Icon size={size} style={{ color: cfg.color }} />;
}

// ── Graph visualization (lightweight SVG force-directed) ───────────────────────

function GraphCanvas({
  data, selectedId, onSelect,
}: { data: GraphData; selectedId: string | null; onSelect: (id: string) => void }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});
  const [zoom, setZoom] = useState(1);
  const [pan, setPan]   = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState<string | null>(null);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0, px: 0, py: 0 });

  const W = 800, H = 600;

  // Initialize positions
  useEffect(() => {
    const pos: Record<string, { x: number; y: number }> = {};
    const cx = W / 2, cy = H / 2;
    const r  = Math.min(W, H) * 0.35;
    data.nodes.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / Math.max(data.nodes.length, 1);
      pos[node.id] = {
        x: cx + r * Math.cos(angle) * (0.5 + Math.random() * 0.5),
        y: cy + r * Math.sin(angle) * (0.5 + Math.random() * 0.5),
      };
    });
    setPositions(pos);
  }, [data.nodes.length]);

  // Simple force simulation
  useEffect(() => {
    if (Object.keys(positions).length === 0) return;
    let frameId: number;
    let pos = { ...positions };

    const simulate = () => {
      const newPos = { ...pos };
      const nodeIds = data.nodes.map(n => n.id);

      // Repulsion
      for (let i = 0; i < nodeIds.length; i++) {
        for (let j = i + 1; j < nodeIds.length; j++) {
          const a = newPos[nodeIds[i]];
          const b = newPos[nodeIds[j]];
          if (!a || !b) continue;
          const dx = b.x - a.x, dy = b.y - a.y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const force = 3000 / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          newPos[nodeIds[i]] = { x: a.x - fx * 0.1, y: a.y - fy * 0.1 };
          newPos[nodeIds[j]] = { x: b.x + fx * 0.1, y: b.y + fy * 0.1 };
        }
      }

      // Attraction along edges
      for (const edge of data.edges) {
        const a = newPos[edge.source], b = newPos[edge.target];
        if (!a || !b) continue;
        const dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const targetDist = 120;
        const force = (dist - targetDist) * 0.05;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        newPos[edge.source] = { x: a.x + fx, y: a.y + fy };
        newPos[edge.target] = { x: b.x - fx, y: b.y - fy };
      }

      // Center gravity
      for (const id of nodeIds) {
        const p = newPos[id];
        if (!p) continue;
        newPos[id] = {
          x: p.x + (W / 2 - p.x) * 0.01,
          y: p.y + (H / 2 - p.y) * 0.01,
        };
      }

      pos = newPos;
      setPositions({ ...newPos });
    };

    let count = 0;
    const tick = () => {
      simulate();
      count++;
      if (count < 80) frameId = requestAnimationFrame(tick);
    };
    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, [data.nodes.length, data.edges.length]);

  const nodeMap = Object.fromEntries(data.nodes.map(n => [n.id, n]));

  return (
    <div className="relative w-full h-full bg-slate-950/60 rounded-xl overflow-hidden border border-slate-800">
      {/* Zoom controls */}
      <div className="absolute top-3 right-3 z-10 flex flex-col gap-1">
        <button onClick={() => setZoom(z => Math.min(z + 0.2, 3))}
          className="w-8 h-8 bg-slate-800 hover:bg-slate-700 rounded-lg flex items-center justify-center text-slate-300">
          <ZoomIn size={14} />
        </button>
        <button onClick={() => setZoom(z => Math.max(z - 0.2, 0.3))}
          className="w-8 h-8 bg-slate-800 hover:bg-slate-700 rounded-lg flex items-center justify-center text-slate-300">
          <ZoomOut size={14} />
        </button>
        <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}
          className="w-8 h-8 bg-slate-800 hover:bg-slate-700 rounded-lg flex items-center justify-center text-slate-300">
          <RefreshCw size={14} />
        </button>
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-full cursor-grab active:cursor-grabbing"
        onMouseMove={e => {
          if (dragging) {
            const dx = e.clientX - dragStart.x;
            const dy = e.clientY - dragStart.y;
            setPositions(prev => ({
              ...prev,
              [dragging]: { x: dragStart.px + dx / zoom, y: dragStart.py + dy / zoom },
            }));
          }
        }}
        onMouseUp={() => setDragging(null)}
        onMouseLeave={() => setDragging(null)}
      >
        <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
          {/* Edges */}
          {data.edges.map(edge => {
            const a = positions[edge.source];
            const b = positions[edge.target];
            if (!a || !b) return null;
            const isSelected = selectedId === edge.source || selectedId === edge.target;
            return (
              <g key={edge.id}>
                <line
                  x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke={isSelected ? '#6366f1' : '#334155'}
                  strokeWidth={isSelected ? 1.5 : 0.8}
                  strokeOpacity={0.7}
                />
                {isSelected && (
                  <text
                    x={(a.x + b.x) / 2} y={(a.y + b.y) / 2}
                    fill="#6366f1" fontSize={9} textAnchor="middle" dy={-3}
                  >
                    {RELATION_LABELS[edge.relation_type] ?? edge.relation_type}
                  </text>
                )}
              </g>
            );
          })}

          {/* Nodes */}
          {data.nodes.map(node => {
            const p = positions[node.id];
            if (!p) return null;
            const color = NODE_COLORS[node.entity_type] ?? '#6366f1';
            const isSelected = selectedId === node.id;
            const r = Math.max(8, Math.min(20, 8 + Math.log2(node.mention_count + 1) * 2));
            return (
              <g
                key={node.id}
                transform={`translate(${p.x},${p.y})`}
                style={{ cursor: 'pointer' }}
                onClick={() => onSelect(node.id)}
                onMouseDown={e => {
                  e.preventDefault();
                  setDragging(node.id);
                  setDragStart({ x: e.clientX, y: e.clientY, px: p.x, py: p.y });
                }}
              >
                {/* Glow for selected */}
                {isSelected && (
                  <circle r={r + 6} fill={color} opacity={0.2} />
                )}
                <circle
                  r={r}
                  fill={color}
                  opacity={isSelected ? 1 : 0.75}
                  stroke={isSelected ? '#fff' : color}
                  strokeWidth={isSelected ? 2 : 0}
                />
                {/* Label */}
                <text
                  x={0} y={r + 10}
                  fill="#e2e8f0"
                  fontSize={9}
                  textAnchor="middle"
                  className="select-none pointer-events-none"
                >
                  {node.name.length > 18 ? node.name.slice(0, 16) + '…' : node.name}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      {/* Legend */}
      <div className="absolute bottom-3 left-3 flex flex-wrap gap-2 max-w-xs">
        {ENTITY_TYPES.slice(1).map(t => (
          <div key={t.value} className="flex items-center gap-1 text-[10px] text-slate-400">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: t.color }} />
            {t.label}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Detail panel ───────────────────────────────────────────────────────────────

function NodeDetailPanel({ nodeId, onClose }: { nodeId: string; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['knowledge-node', nodeId],
    queryFn:  () => api.get(`/knowledge-graph/nodes/${nodeId}/`).then(r => r.data?.data),
    staleTime: 60_000,
  });

  if (isLoading) return (
    <div className="flex items-center justify-center h-32">
      <Loader2 size={20} className="animate-spin text-indigo-400" />
    </div>
  );
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <NodeTypeIcon type={data.entity_type} />
            <span className="text-xs text-slate-400 capitalize">{data.entity_type}</span>
          </div>
          <h3 className="text-base font-bold text-slate-100">{data.name}</h3>
          {data.description && (
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">{data.description}</p>
          )}
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-slate-700 transition-colors flex-shrink-0">
          <X size={14} className="text-slate-400" />
        </button>
      </div>

      <div className="text-xs text-slate-400">
        <span className="font-medium text-slate-300">{data.mention_count}</span> mentions in content
      </div>

      {/* Connections */}
      {data.outgoing_edges?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Connects to</p>
          <div className="space-y-1.5">
            {data.outgoing_edges.slice(0, 8).map((e: any) => (
              <div key={e.id} className="flex items-center gap-2 text-xs">
                <span className="text-indigo-400 font-mono text-[10px] flex-shrink-0">{RELATION_LABELS[e.relation_type] ?? e.relation_type}</span>
                <NodeTypeIcon type={e.target_type} size={11} />
                <span className="text-slate-300 truncate">{e.target_name}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.incoming_edges?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Referenced by</p>
          <div className="space-y-1.5">
            {data.incoming_edges.slice(0, 6).map((e: any) => (
              <div key={e.id} className="flex items-center gap-2 text-xs">
                <NodeTypeIcon type={e.source_type} size={11} />
                <span className="text-slate-300 truncate">{e.source_name}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.metadata?.url && (
        <a
          href={data.metadata.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300"
        >
          <ExternalLink size={11} /> View source
        </a>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function KnowledgeGraphPage() {
  const [selectedId, setSelectedId]   = useState<string | null>(null);
  const [centerNode, setCenterNode]   = useState<string | null>(null);
  const [entityType, setEntityType]   = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [depth, setDepth]             = useState(2);

  // Main graph data
  const { data: graphData, isLoading, refetch } = useQuery({
    queryKey: ['knowledge-graph', centerNode, depth, entityType],
    queryFn:  () => api.get('/knowledge-graph/', {
      params: {
        ...(centerNode ? { center: centerNode } : {}),
        depth,
        ...(entityType ? { type: entityType } : {}),
        limit: 60,
      },
    }).then(r => r.data?.data as GraphData),
    staleTime: 2 * 60_000,
  });

  // Search
  const { data: searchResults } = useQuery({
    queryKey: ['kg-search', searchQuery],
    queryFn:  () => api.get('/knowledge-graph/search/', {
      params: { q: searchQuery, limit: 8 },
    }).then(r => r.data?.data as SearchResult[]),
    enabled: searchQuery.trim().length >= 2,
    staleTime: 30_000,
  });

  const graph = graphData ?? { nodes: [], edges: [] };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* ── Header ── */}
      <div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-slate-800">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2">
              <Network size={24} className="text-violet-400" />
              Knowledge Graph
            </h1>
            <p className="text-slate-400 text-sm mt-0.5">
              AI-extracted entity relationships — {graph.nodes.length} nodes, {graph.edges.length} edges
            </p>
          </div>

          {/* Depth control */}
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <span>Depth:</span>
            {[1, 2, 3].map(d => (
              <button key={d} onClick={() => setDepth(d)}
                className={`w-7 h-7 rounded-lg text-xs font-bold transition-colors ${
                  depth === d ? 'bg-violet-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                }`}>
                {d}
              </button>
            ))}
          </div>
        </div>

        {/* Entity type filter + search */}
        <div className="flex items-center gap-3 mt-4 flex-wrap">
          {ENTITY_TYPES.map(t => (
            <button key={t.value} onClick={() => setEntityType(t.value)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                entityType === t.value
                  ? 'bg-violet-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}>
              <t.icon size={11} />
              {t.label}
            </button>
          ))}

          {/* Search */}
          <div className="relative flex-1 min-w-48 max-w-xs ml-auto">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              className="w-full pl-8 pr-8 py-1.5 text-xs bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
              placeholder="Search nodes…"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery('')} className="absolute right-2 top-1/2 -translate-y-1/2">
                <X size={12} className="text-slate-500" />
              </button>
            )}
          </div>
        </div>

        {/* Search results dropdown */}
        {searchResults && searchResults.length > 0 && searchQuery.length >= 2 && (
          <div className="absolute z-20 mt-1 bg-slate-900 border border-slate-700 rounded-xl shadow-xl max-w-xs w-full overflow-hidden">
            {searchResults.map(r => (
              <button
                key={r.id}
                onClick={() => { setCenterNode(r.id); setSelectedId(r.id); setSearchQuery(''); }}
                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-800 text-left text-sm text-slate-300"
              >
                <NodeTypeIcon type={r.entity_type} size={12} />
                <span className="flex-1 truncate">{r.name}</span>
                <span className="text-xs text-slate-500">{r.mention_count}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Main content ── */}
      <div className="flex-1 flex overflow-hidden bg-slate-950">

        {/* Graph canvas */}
        <div className="flex-1 p-4">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <Loader2 size={32} className="animate-spin text-violet-400 mx-auto mb-3" />
                <p className="text-slate-400 text-sm">Building knowledge graph…</p>
              </div>
            </div>
          ) : graph.nodes.length === 0 ? (
            <div className="flex items-center justify-center h-full text-center">
              <div>
                <Network size={48} className="text-slate-700 mx-auto mb-4" />
                <p className="text-slate-400 font-medium">No knowledge graph data yet</p>
                <p className="text-slate-600 text-sm mt-1">
                  The graph is built daily at 05:00 UTC from scraped content.
                </p>
                <div className="flex items-center gap-2 mt-3 text-xs text-slate-500 justify-center">
                  <Info size={12} />
                  Trigger manually: celery -A config call apps.core.tasks.build_knowledge_graph
                </div>
              </div>
            </div>
          ) : (
            <GraphCanvas
              data={graph}
              selectedId={selectedId}
              onSelect={id => setSelectedId(id === selectedId ? null : id)}
            />
          )}
        </div>

        {/* Detail panel */}
        {selectedId && (
          <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900 p-5 overflow-y-auto">
            <NodeDetailPanel nodeId={selectedId} onClose={() => setSelectedId(null)} />
            {centerNode !== selectedId && (
              <button
                onClick={() => setCenterNode(selectedId)}
                className="mt-4 w-full flex items-center justify-center gap-2 px-3 py-2 bg-violet-600 hover:bg-violet-700 text-white text-xs font-medium rounded-lg transition-colors"
              >
                <ChevronRight size={13} />
                Explore from this node
              </button>
            )}
            {centerNode && (
              <button
                onClick={() => { setCenterNode(null); setSelectedId(null); }}
                className="mt-2 w-full flex items-center justify-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition-colors"
              >
                <RefreshCw size={13} />
                Reset to overview
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
