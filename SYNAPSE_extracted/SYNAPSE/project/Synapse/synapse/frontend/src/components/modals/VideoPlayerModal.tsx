'use client';

/**
 * VideoPlayerModal — Full-featured in-app YouTube player.
 *
 * Features:
 *  - Double-click / double-tap → toggle fullscreen
 *  - Keyboard: Esc=close, ↑↓=volume, F=fullscreen, I=mini, M=mute
 *  - Mini floating PiP — scroll page while watching
 *  - End screen with Replay + Watch on YouTube
 *  - Volume slider in top bar and mini player
 */

import React, { useEffect, useRef, useCallback, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, ExternalLink, Eye, ThumbsUp, Youtube,
  RotateCcw, Clock, Minimize2, Maximize2, Volume2, VolumeX,
} from 'lucide-react';
import type { Video } from '@/components/cards/VideoCard';

interface VideoPlayerModalProps {
  video: Video | null;
  onClose: () => void;
}

type PlayerMode = 'normal' | 'fullscreen' | 'mini';

function fmtCount(n?: number): string {
  if (!n) return '0';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return n.toString();
}

function fmtDuration(s?: number): string {
  if (!s) return '';
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  return `${m}:${String(sec).padStart(2, '0')}`;
}

function ytCmd(iframe: HTMLIFrameElement | null, func: string, args: unknown[] = []) {
  iframe?.contentWindow?.postMessage(
    JSON.stringify({ event: 'command', func, args }),
    '*'
  );
}

export function VideoPlayerModal({ video, onClose }: VideoPlayerModalProps) {
  const [mode,       setMode]       = useState<PlayerMode>('normal');
  const [volume,     setVolume]     = useState(80);
  const [muted,      setMuted]      = useState(false);
  const [videoEnded, setVideoEnded] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const closeRef  = useRef<HTMLButtonElement>(null);
  const lastTap   = useRef(0);

  const isOpen = !!video;

  // Reset state when a new video opens
  useEffect(() => {
    if (video) { setMode('normal'); setVideoEnded(false); }
  }, [video?.id]);

  // Body scroll lock (not in mini mode)
  useEffect(() => {
    document.body.style.overflow = (isOpen && mode !== 'mini') ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [isOpen, mode]);

  // Auto-focus close button
  useEffect(() => {
    if (isOpen && mode !== 'mini') {
      const id = requestAnimationFrame(() => closeRef.current?.focus());
      return () => cancelAnimationFrame(id);
    }
  }, [isOpen, video?.id, mode]);

  // Sync volume to YouTube iframe
  useEffect(() => {
    ytCmd(iframeRef.current, 'setVolume', [muted ? 0 : volume]);
  }, [volume, muted]);

  // Detect video ended via YouTube postMessage API
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      try {
        const d = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;
        if (
          (d?.event === 'infoDelivery' && d?.info?.playerState === 0) ||
          (d?.event === 'onStateChange' && d?.info === 0)
        ) setVideoEnded(true);
      } catch {}
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);

  // Keyboard controls
  const onKey = useCallback((e: KeyboardEvent) => {
    if (!isOpen) return;
    const tag = (document.activeElement as HTMLElement)?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

    switch (e.key) {
      case 'Escape':
        e.preventDefault();
        if (mode === 'mini') setMode('normal');
        else onClose();
        break;
      case 'ArrowUp':
        e.preventDefault();
        setMuted(false);
        setVolume(v => Math.min(100, v + 10));
        break;
      case 'ArrowDown':
        e.preventDefault();
        setVolume(v => { const next = Math.max(0, v - 10); if (next === 0) setMuted(true); return next; });
        break;
      case 'f': case 'F':
        e.preventDefault();
        setMode(m => m === 'fullscreen' ? 'normal' : 'fullscreen');
        break;
      case 'i': case 'I':
        e.preventDefault();
        setMode(m => m === 'mini' ? 'normal' : 'mini');
        break;
      case 'm': case 'M':
        e.preventDefault();
        setMuted(v => !v);
        break;
    }
  }, [isOpen, mode, onClose]);

  useEffect(() => {
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onKey]);

  // Double-click / double-tap → fullscreen toggle
  const onDblClick = useCallback(() => {
    setMode(m => m === 'fullscreen' ? 'normal' : 'fullscreen');
  }, []);

  const onTouchEnd = useCallback(() => {
    const now = Date.now();
    if (now - lastTap.current < 300) setMode(m => m === 'fullscreen' ? 'normal' : 'fullscreen');
    lastTap.current = now;
  }, []);

  if (typeof document === 'undefined' || !video) return null;

  const embedUrl = `https://www.youtube.com/embed/${video.youtube_id}?autoplay=1&rel=0&modestbranding=1&enablejsapi=1&origin=${window.location.origin}`;
  const isFullscreen = mode === 'fullscreen';

  // ── Mini floating player ────────────────────────────────────────────────────
  if (mode === 'mini') {
    return createPortal(
      <motion.div
        initial={{ opacity: 0, scale: 0.85, y: 40 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.85, y: 40 }}
        transition={{ duration: 0.2 }}
        className="fixed bottom-6 right-6 z-[9999] w-80 rounded-2xl overflow-hidden shadow-2xl ring-1 ring-white/20 bg-slate-900"
        style={{ maxWidth: 'calc(100vw - 24px)' }}
      >
        <div className="flex items-center justify-between px-3 py-2 bg-slate-800 border-b border-white/10">
          <p className="text-xs text-white truncate max-w-[160px] font-medium">{video.title}</p>
          <div className="flex items-center gap-1">
            <button onClick={() => setMode('normal')} aria-label="Expand player"
              className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-white/10 transition">
              <Maximize2 size={14} />
            </button>
            <button onClick={onClose} aria-label="Close player"
              className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-white/10 transition">
              <X size={14} />
            </button>
          </div>
        </div>
        <div className="relative w-full bg-black" style={{ paddingBottom: '56.25%' }}>
          <iframe
            key={video.id}
            ref={iframeRef}
            src={embedUrl}
            title={video.title}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className="absolute inset-0 w-full h-full border-none"
          />
        </div>
        <div className="flex items-center gap-2 px-3 py-2 bg-slate-900">
          <button onClick={() => setMuted(v => !v)} aria-label={muted ? 'Unmute' : 'Mute'}
            className="text-slate-400 hover:text-white transition shrink-0">
            {muted || volume === 0 ? <VolumeX size={13} /> : <Volume2 size={13} />}
          </button>
          <input type="range" min={0} max={100} value={muted ? 0 : volume}
            onChange={e => { const v = +e.target.value; setVolume(v); setMuted(v === 0); }}
            className="flex-1 h-1 accent-red-500" aria-label="Volume" />
          <span className="text-[10px] text-slate-500 w-7 text-right">{muted ? 0 : volume}%</span>
        </div>
      </motion.div>,
      document.body
    );
  }

  // ── Normal / Fullscreen player ──────────────────────────────────────────────
  return createPortal(
    <AnimatePresence>
      {video && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className={`fixed inset-0 z-[9999] flex ${isFullscreen ? '' : 'items-center justify-center p-4'} bg-black/85 backdrop-blur-md`}
          onClick={onClose}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="vpm-title"
            initial={{ opacity: 0, scale: 0.93, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.93, y: 16 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className={`relative bg-slate-900 shadow-2xl ring-1 ring-white/10 flex flex-col
              ${isFullscreen ? 'w-full h-full rounded-none' : 'w-full max-w-3xl rounded-2xl overflow-hidden'}`}
            onClick={e => e.stopPropagation()}
          >
            {/* ── Top bar ── */}
            <div className="flex items-center justify-between gap-2 px-4 py-2.5 bg-slate-800/90 border-b border-white/10 shrink-0">
              <div className="flex items-center gap-2 min-w-0">
                <Youtube size={15} className="text-red-500 shrink-0" />
                <h2 id="vpm-title" className="text-sm font-semibold text-white truncate">{video.title}</h2>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {/* Volume control */}
                <div className="hidden sm:flex items-center gap-1.5 mr-1">
                  <button onClick={() => setMuted(v => !v)} aria-label={muted ? 'Unmute' : 'Mute'}
                    className="text-slate-400 hover:text-white transition">
                    {muted || volume === 0 ? <VolumeX size={14} /> : <Volume2 size={14} />}
                  </button>
                  <input type="range" min={0} max={100} value={muted ? 0 : volume}
                    onChange={e => { const v = +e.target.value; setVolume(v); setMuted(v === 0); }}
                    className="w-20 h-1 accent-red-500" aria-label="Volume" />
                  <span className="text-[10px] text-slate-500 w-6">{muted ? 0 : volume}%</span>
                </div>
                {/* Mini PiP */}
                <button onClick={() => setMode('mini')} aria-label="Mini player"
                  title="Mini player — keep watching while you scroll (I)"
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition">
                  <Minimize2 size={15} />
                </button>
                {/* Fullscreen */}
                <button onClick={() => setMode(m => m === 'fullscreen' ? 'normal' : 'fullscreen')}
                  aria-label={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
                  title={isFullscreen ? 'Exit fullscreen (F)' : 'Fullscreen (F)'}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition">
                  {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
                </button>
                {/* YouTube link */}
                <a href={video.url} target="_blank" rel="noopener noreferrer" title="Watch on YouTube"
                  className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white hover:bg-white/10 transition">
                  <ExternalLink size={12} /> YT
                </a>
                {/* Close */}
                <button ref={closeRef} onClick={onClose} aria-label="Close player"
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition">
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* ── Embed area ── */}
            <div
              className="relative w-full bg-black"
              style={{ paddingBottom: isFullscreen ? undefined : '56.25%', flex: isFullscreen ? 1 : undefined }}
              onDoubleClick={onDblClick}
              onTouchEnd={onTouchEnd}
            >
              <iframe
                key={video.id}
                ref={iframeRef}
                src={embedUrl}
                title={video.title}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                className="absolute inset-0 w-full h-full border-none"
              />

              {/* ── End screen overlay ── */}
              {videoEnded && (
                <div className="absolute inset-0 bg-black/90 backdrop-blur-sm flex flex-col items-center justify-center gap-6 p-6">
                  <div className="flex flex-col items-center gap-2 text-center">
                    <Youtube size={40} className="text-red-500" />
                    <p className="text-white text-lg font-semibold">Video ended</p>
                    <p className="text-slate-400 text-sm line-clamp-1">{video.title}</p>
                  </div>
                  <div className="flex items-center gap-3 flex-wrap justify-center">
                    <button
                      onClick={() => setVideoEnded(false)}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white text-slate-900 text-sm font-semibold hover:bg-slate-100 transition shadow-lg"
                    >
                      <RotateCcw size={15} /> Replay
                    </button>
                    <a
                      href={video.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white text-sm font-semibold transition shadow-lg"
                    >
                      <Youtube size={15} /> Watch on YouTube
                    </a>
                  </div>
                  <p className="text-slate-600 text-xs">
                    Press <kbd className="bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded">Esc</kbd> to close
                  </p>
                </div>
              )}
            </div>

            {/* ── Metadata footer (hidden in fullscreen) ── */}
            {!isFullscreen && (
              <div className="px-4 py-3 bg-slate-900 border-t border-white/10 shrink-0">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-white font-semibold text-sm leading-snug line-clamp-1">{video.title}</h3>
                    {video.channel_name && (
                      <p className="text-red-400 text-xs mt-0.5 font-medium">{video.channel_name}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-slate-400 shrink-0">
                    {video.view_count > 0 && <span className="flex items-center gap-1"><Eye size={11}/>{fmtCount(video.view_count)}</span>}
                    {video.like_count > 0 && <span className="flex items-center gap-1"><ThumbsUp size={11}/>{fmtCount(video.like_count)}</span>}
                    {video.duration_seconds > 0 && <span className="flex items-center gap-1"><Clock size={11}/>{fmtDuration(video.duration_seconds)}</span>}
                  </div>
                </div>
                {video.summary && (
                  <p className="text-slate-400 text-xs leading-relaxed line-clamp-2 mt-2 pt-2 border-t border-white/10">
                    {video.summary}
                  </p>
                )}
                <p className="text-[10px] text-slate-600 text-center mt-2">
                  <kbd className="bg-slate-800 text-slate-400 px-1 rounded">↑</kbd>
                  <kbd className="bg-slate-800 text-slate-400 px-1 rounded ml-0.5">↓</kbd> volume ·{' '}
                  <kbd className="bg-slate-800 text-slate-400 px-1 rounded">F</kbd> fullscreen ·{' '}
                  <kbd className="bg-slate-800 text-slate-400 px-1 rounded">I</kbd> mini ·{' '}
                  <kbd className="bg-slate-800 text-slate-400 px-1 rounded">M</kbd> mute ·{' '}
                  <kbd className="bg-slate-800 text-slate-400 px-1 rounded">Esc</kbd> close
                </p>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}
