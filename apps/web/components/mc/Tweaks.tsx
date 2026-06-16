"use client";

import { useI18n } from "@/lib/i18n";

export type Tweaks = {
  dark: boolean;
  accent: string;
  density: "compact" | "regular" | "comfy";
  aurora: "off" | "subtile" | "vif";
  auroraSpeed: "calme" | "normal" | "rapide";
  glow: "off" | "doux" | "fort";
  radius: "net" | "normal" | "rond";
  shadow: "plate" | "normale" | "prononcée";
  // Ambiance sonore : le « son des fourmis au travail » (suit les agents actifs).
  antSound: boolean;
};

export const TWEAK_DEFAULTS: Tweaks = {
  dark: true, accent: "#d97757", density: "regular", aurora: "subtile",
  auroraSpeed: "normal", glow: "doux", radius: "normal", shadow: "normale",
  antSound: false,
};

const DENS = { compact: 0.84, regular: 1, comfy: 1.16 };
const AUR = { off: 0, subtile: 0.85, vif: 1.4 };
const GLOW = { off: 0, doux: 1, fort: 1.9 };
const ASPEED = { calme: "44s", normal: "28s", rapide: "15s" };
const RADIUS = { net: 0.5, normal: 1, rond: 1.5 };
const SHADOW = { plate: 0.4, normale: 1, prononcée: 1.6 };

export const PRESETS: Record<string, Partial<Tweaks>> = {
  Sobre: { dark: true, accent: "#d97757", aurora: "off", auroraSpeed: "calme", glow: "off", radius: "normal", shadow: "plate", density: "regular" },
  Néon: { dark: true, accent: "#5b8def", aurora: "vif", auroraSpeed: "rapide", glow: "fort", radius: "rond", shadow: "prononcée", density: "regular" },
  Présentation: { dark: true, accent: "#d97757", aurora: "subtile", auroraSpeed: "normal", glow: "doux", radius: "rond", shadow: "normale", density: "comfy" },
  Clair: { dark: false, accent: "#d97757", aurora: "subtile", auroraSpeed: "calme", glow: "doux", radius: "normal", shadow: "normale", density: "regular" },
  Infinity: { dark: true, accent: "#ffd400", aurora: "subtile", auroraSpeed: "normal", glow: "fort", radius: "normal", shadow: "normale", density: "regular" },
};

export function applyTweaks(t: Tweaks) {
  const r = document.documentElement;
  r.dataset.theme = t.dark ? "dark" : "light";
  r.style.setProperty("--accent", t.accent);
  r.style.setProperty("--density", String(DENS[t.density] ?? 1));
  r.style.setProperty("--aurora", String(AUR[t.aurora] ?? 0.85));
  r.style.setProperty("--glow", String(GLOW[t.glow] ?? 1));
  r.style.setProperty("--aurora-speed", ASPEED[t.auroraSpeed] ?? "28s");
  r.style.setProperty("--radius-scale", String(RADIUS[t.radius] ?? 1));
  r.style.setProperty("--shadow-scale", String(SHADOW[t.shadow] ?? 1));
}

const ACCENTS = ["#d97757", "#5b8def", "#1f8a5b", "#7a5ae0", "#ffd400"];

function Seg<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: T[]; onChange: (v: T) => void }) {
  return (
    <div className="twk-row">
      <div className="twk-lbl"><span>{label}</span></div>
      <div className="twk-seg">
        {options.map((o) => (
          <button key={o} type="button" data-on={value === o ? "1" : "0"} onClick={() => onChange(o)}>{o}</button>
        ))}
      </div>
    </div>
  );
}

export function TweaksPanel({
  open,
  onClose,
  t,
  set,
}: {
  open: boolean;
  onClose: () => void;
  t: Tweaks;
  set: (patch: Partial<Tweaks>) => void;
}) {
  const { t: tr } = useI18n();
  if (!open) return null;
  return (
    <div className="twk-panel">
      <div className="twk-hd">
        <b>{tr("tw_title")}</b>
        <button className="twk-x" onClick={onClose} aria-label="Fermer">✕</button>
      </div>
      <div className="twk-body">
        <div className="twk-sect">{tr("tw_ambiances")}</div>
        <div className="twk-presets">
          {Object.keys(PRESETS).map((name) => (
            <button key={name} className="twk-btn" onClick={() => set(PRESETS[name])}>{name}</button>
          ))}
        </div>

        <div className="twk-sect">{tr("tw_theme")}</div>
        <div className="twk-row twk-row-h">
          <div className="twk-lbl"><span>{tr("tw_dark")}</span></div>
          <button className="twk-toggle" data-on={t.dark ? "1" : "0"} onClick={() => set({ dark: !t.dark })}><i /></button>
        </div>
        <div className="twk-row">
          <div className="twk-lbl"><span>{tr("tw_accent")}</span></div>
          <div className="twk-chips">
            {ACCENTS.map((c) => (
              <button key={c} className="twk-chip" data-on={t.accent === c ? "1" : "0"} style={{ background: c }} onClick={() => set({ accent: c })} aria-label={c} />
            ))}
          </div>
        </div>

        <div className="twk-sect">{tr("tw_display")}</div>
        <Seg label={tr("tw_density")} value={t.density} options={["compact", "regular", "comfy"]} onChange={(v) => set({ density: v })} />
        <Seg label={tr("tw_radius")} value={t.radius} options={["net", "normal", "rond"]} onChange={(v) => set({ radius: v })} />
        <Seg label={tr("tw_shadow")} value={t.shadow} options={["plate", "normale", "prononcée"]} onChange={(v) => set({ shadow: v })} />

        <div className="twk-sect">{tr("tw_aurora_glow")}</div>
        <Seg label={tr("tw_aurora")} value={t.aurora} options={["off", "subtile", "vif"]} onChange={(v) => set({ aurora: v })} />
        <Seg label={tr("tw_speed")} value={t.auroraSpeed} options={["calme", "normal", "rapide"]} onChange={(v) => set({ auroraSpeed: v })} />
        <Seg label={tr("tw_glow")} value={t.glow} options={["off", "doux", "fort"]} onChange={(v) => set({ glow: v })} />

        <div className="twk-sect">{tr("tw_sound")}</div>
        <div className="twk-row twk-row-h">
          <div className="twk-lbl"><span>{tr("tw_sound_ants")}</span></div>
          <button className="twk-toggle" data-on={t.antSound ? "1" : "0"} onClick={() => set({ antSound: !t.antSound })}><i /></button>
        </div>
      </div>
    </div>
  );
}
