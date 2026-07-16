"use client";

import { useEffect, useRef } from "react";

// Le « son des fourmis au travail » — ambiance sonore procédurale (Web Audio, zéro asset).
// Deux couches : une nappe grave de fourmilière (bruit filtré passe-bas) + un grésillement de
// petits pas/mandibules (grains de bruit band-pass) dont la densité suit le nombre d'agents
// en état "working". Rien n'est joué au repos (aucune fourmi active → silence).

type Engine = { setIntensity: (v: number) => void; dispose: () => void };

// Buffer de bruit blanc réutilisable (nappe + grains).
function makeNoiseBuffer(ctx: AudioContext, seconds: number): AudioBuffer {
  const len = Math.max(1, Math.floor(ctx.sampleRate * seconds));
  const buf = ctx.createBuffer(1, len, ctx.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
  return buf;
}

function createEngine(): Engine | null {
  if (typeof window === "undefined") return null;
  const AC: typeof AudioContext | undefined =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AC) return null;

  const ctx = new AC();
  // Le clic du toggle compte comme geste utilisateur — sauf si `enabled` vient d'être
  // réhydraté depuis localStorage au montage (rechargement de page, pas de clic réel) :
  // les navigateurs (surtout Safari) laissent alors le contexte `suspended`. On retente
  // au premier vrai geste utilisateur plutôt que de rester silencieux indéfiniment.
  const retryResumeOnGesture = () => {
    if (ctx.state !== "running") void ctx.resume().catch(() => {});
  };
  const gestureEvents = ["pointerdown", "keydown"] as const;
  gestureEvents.forEach((ev) => window.addEventListener(ev, retryResumeOnGesture));
  void ctx.resume().catch(() => {});

  const master = ctx.createGain();
  master.gain.value = 0;
  master.connect(ctx.destination);

  // Couche 1 — nappe « fourmilière » : bruit grave en boucle, très discret.
  const bed = ctx.createBufferSource();
  bed.buffer = makeNoiseBuffer(ctx, 2);
  bed.loop = true;
  const bedLp = ctx.createBiquadFilter();
  bedLp.type = "lowpass";
  bedLp.frequency.value = 220;
  const bedGain = ctx.createGain();
  bedGain.gain.value = 0.06;
  bed.connect(bedLp).connect(bedGain).connect(master);
  bed.start();

  // Couche 2 — grains (petits pas) : un buffer partagé relu à des offsets aléatoires.
  const grainBuf = makeNoiseBuffer(ctx, 1);

  let intensity = 0;
  const setIntensity = (v: number) => {
    intensity = Math.max(0, Math.min(1, v));
    master.gain.cancelScheduledValues(ctx.currentTime);
    // Silence au repos, volume qui monte avec l'activité de la flotte.
    const target = intensity === 0 ? 0 : 0.18 + 0.5 * intensity;
    master.gain.setTargetAtTime(target, ctx.currentTime, 0.4);
  };

  const spawnGrain = (t: number) => {
    const src = ctx.createBufferSource();
    src.buffer = grainBuf;
    src.playbackRate.value = 0.8 + Math.random() * 0.8;
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 1800 + Math.random() * 4200;
    bp.Q.value = 6 + Math.random() * 8;
    const g = ctx.createGain();
    const peak = 0.05 + Math.random() * 0.07;
    const dur = 0.02 + Math.random() * 0.05;
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(peak, t + 0.002);
    g.gain.exponentialRampToValueAtTime(0.0005, t + dur);
    src.connect(bp).connect(g).connect(master);
    src.start(t, Math.random() * 0.9, dur + 0.03);
  };

  // Ordonnanceur look-ahead : programme les grains ~200 ms à l'avance.
  let next = ctx.currentTime + 0.1;
  const timer = window.setInterval(() => {
    if (intensity <= 0) { next = ctx.currentTime + 0.1; return; }
    const ahead = ctx.currentTime + 0.2;
    const base = 0.16 - 0.12 * intensity; // intervalle moyen : 0.16 s → 0.04 s
    while (next < ahead) {
      spawnGrain(next);
      next += base * (0.5 + Math.random());
    }
  }, 80);

  const dispose = () => {
    gestureEvents.forEach((ev) => window.removeEventListener(ev, retryResumeOnGesture));
    window.clearInterval(timer);
    try { bed.stop(); } catch { /* déjà arrêté */ }
    master.gain.setTargetAtTime(0, ctx.currentTime, 0.1);
    window.setTimeout(() => { void ctx.close(); }, 300);
  };

  return { setIntensity, dispose };
}

// Hook : monte/démonte le moteur selon `enabled`, ajuste l'intensité en continu.
export function useAntColonySound(enabled: boolean, intensity: number) {
  const ref = useRef<Engine | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const engine = createEngine();
    if (!engine) return;
    ref.current = engine;
    engine.setIntensity(intensity);
    return () => { engine.dispose(); ref.current = null; };
    // intensity géré par l'effet ci-dessous — ne pas recréer le moteur à chaque variation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);
  useEffect(() => {
    ref.current?.setIntensity(intensity);
  }, [intensity]);
}
