import { useEffect, useRef } from "react";
import { Application, Circle, Container, Graphics, Text, TextStyle } from "pixi.js";
import { useWorld } from "../ws/store";
import {
  TILE_W,
  TILE_H,
  toScreen,
  LOCATION_COLORS,
  citizenColorWithFear,
  nightAlpha,
  closedLocationColor,
} from "./iso";

type CitizenSprite = {
  container: Container;
  dot: Graphics;
  ring: Graphics;
  fearAura: Graphics;
  bubble: Container;
  bubbleText: Text;
  dispX: number;
  dispY: number;
  tgtX: number;
  tgtY: number;
};

const nameStyle = new TextStyle({ fill: 0xe6edf3, fontSize: 11, fontWeight: "600" });
const labelStyle = new TextStyle({ fill: 0xb8c4d4, fontSize: 10, fontWeight: "700" });
const closedLabelStyle = new TextStyle({ fill: 0xf87171, fontSize: 10, fontWeight: "700" });
const speechStyle = new TextStyle({ fill: 0x0b0e14, fontSize: 11, wordWrap: true, wordWrapWidth: 120 });

export default function CityStage() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let destroyed = false;
    const app = new Application();
    const sprites = new Map<string, CitizenSprite>();
    let unsub: (() => void) | undefined;

    (async () => {
      await app.init({ background: 0x0b0e14, antialias: true, resizeTo: ref.current! });
      if (destroyed || !ref.current) {
        app.destroy(true);
        return;
      }
      ref.current.appendChild(app.canvas);

      const world = new Container();
      app.stage.addChild(world);
      const ground = new Graphics();
      const heatLayer = new Graphics();
      const pulseLayer = new Graphics();  // crisis location pulse rings (animated in ticker)
      const locLayer = new Container();
      const peopleLayer = new Container();
      const flashLayer = new Graphics();  // full-screen red flash on crisis injection
      const night = new Graphics();
      world.addChild(ground, heatLayer, pulseLayer, locLayer, peopleLayer);
      app.stage.addChild(flashLayer, night);

      let built = false;
      let closedPos: Array<{ sx: number; sy: number }> = [];
      let prevCrisisCount = 0;
      let crisisFlashUntil = 0;

      const fitWorld = (w: number, h: number) => {
        const corners = [toScreen(0, 0), toScreen(w - 1, 0), toScreen(0, h - 1), toScreen(w - 1, h - 1)];
        const minSx = Math.min(...corners.map((c) => c.sx));
        const maxSx = Math.max(...corners.map((c) => c.sx));
        const minSy = Math.min(...corners.map((c) => c.sy));
        world.x = (app.renderer.width - (minSx + maxSx)) / 2;
        world.y = 56 - minSy;
      };

      const drawGround = (w: number, h: number) => {
        ground.clear();
        for (let gx = 0; gx < w; gx++) {
          for (let gy = 0; gy < h; gy++) {
            const { sx, sy } = toScreen(gx, gy);
            const shade = (gx + gy) % 2 === 0 ? 0x121823 : 0x0f141d;
            ground
              .poly([sx, sy - TILE_H / 2, sx + TILE_W / 2, sy, sx, sy + TILE_H / 2, sx - TILE_W / 2, sy])
              .fill({ color: shade })
              .stroke({ width: 1, color: 0x1b2430, alpha: 0.5 });
          }
        }
      };

      const drawLocations = (
        locs: NonNullable<ReturnType<typeof useWorld.getState>["world"]>,
        closed: string[],
      ) => {
        locLayer.removeChildren();
        for (const l of locs.locations) {
          const { sx, sy } = toScreen(l.x, l.y);
          const isClosed = closed.includes(l.id);
          const color = isClosed ? closedLocationColor(l.type) : (LOCATION_COLORS[l.type] ?? 0x444444);
          const g = new Graphics();
          const bw = 22, bh = 26;
          g.poly([sx, sy - bh, sx + bw / 2, sy - bh + 10, sx, sy - bh + 20, sx - bw / 2, sy - bh + 10])
            .fill({ color });
          g.rect(sx - bw / 2, sy - bh + 10, bw, 16).fill({ color, alpha: isClosed ? 0.5 : 0.85 });

          if (isClosed) {
            // Red ✕ overlay on closed buildings
            const cx = new Graphics();
            cx.circle(0, 0, 9).fill({ color: 0x7f1d1d, alpha: 0.85 });
            cx.x = sx;
            cx.y = sy - bh + 3;
            locLayer.addChild(cx);
            const xt = new Text({ text: "✕", style: new TextStyle({ fill: 0xff6b6b, fontSize: 10 }) });
            xt.anchor.set(0.5);
            xt.x = sx;
            xt.y = sy - bh + 3;
            locLayer.addChild(xt);
          }

          locLayer.addChild(g);
          const style = isClosed ? closedLabelStyle : labelStyle;
          const label = new Text({ text: isClosed ? `${l.name} ⛔` : l.name, style });
          label.anchor.set(0.5, 1);
          label.x = sx;
          label.y = sy - bh - 2;
          locLayer.addChild(label);
        }
      };

      const makeSprite = (id: string, name: string): CitizenSprite => {
        const container = new Container();
        container.eventMode = "static";
        container.cursor = "pointer";
        container.hitArea = new Circle(0, 0, 14);
        container.on("pointertap", () => useWorld.getState().select(id));

        const fearAura = new Graphics();
        const ring = new Graphics();
        ring.circle(0, 0, 9).stroke({ width: 2, color: 0xffffff, alpha: 0 });
        const dot = new Graphics();
        dot.circle(0, 0, 6).fill({ color: citizenColorWithFear(id, 0) }).stroke({ width: 1.5, color: 0x0b0e14 });

        const nameText = new Text({ text: name.split(" ")[0], style: nameStyle });
        nameText.anchor.set(0.5, 0);
        nameText.y = 8;

        const bubble = new Container();
        const bubbleBg = new Graphics();
        const bubbleText = new Text({ text: "", style: speechStyle });
        bubbleText.x = 8;
        bubbleText.y = 5;
        bubble.addChild(bubbleBg, bubbleText);
        bubble.visible = false;
        (bubble as unknown as { _bg: Graphics })._bg = bubbleBg;

        container.addChild(fearAura, ring, dot, nameText, bubble);
        peopleLayer.addChild(container);
        return { container, dot, ring, fearAura, bubble, bubbleText, dispX: 0, dispY: 0, tgtX: 0, tgtY: 0 };
      };

      const sync = () => {
        const w = useWorld.getState().world;
        if (!w) return;
        const closed = w.closed_locations ?? [];
        if (!built) {
          fitWorld(w.grid.w, w.grid.h);
          drawGround(w.grid.w, w.grid.h);
          built = true;
        }
        drawLocations(w, closed);

        // Track closed building screen positions for pulse animation
        closedPos = w.locations
          .filter(l => closed.includes(l.id))
          .map(l => toScreen(l.x, l.y));

        // Red flash when a new crisis is injected
        const crisisCount = w.active_crises?.length ?? 0;
        if (crisisCount > prevCrisisCount) crisisFlashUntil = performance.now() + 1000;
        prevCrisisCount = crisisCount;

        // Fear heatmap — semi-transparent tile overlays at each location
        const fearByLoc = new Map<string, number>();
        for (const c of w.citizens) {
          if ((c.fear ?? 0) > 0.08 && c.location_id) {
            fearByLoc.set(c.location_id, Math.max(fearByLoc.get(c.location_id) ?? 0, c.fear));
          }
        }
        heatLayer.clear();
        for (const loc of w.locations) {
          const locFear = fearByLoc.get(loc.id) ?? 0;
          if (locFear < 0.1) continue;
          const { sx, sy } = toScreen(loc.x, loc.y);
          const heatColor = locFear > 0.65 ? 0xf87171 : locFear > 0.35 ? 0xfbbf24 : 0xa3e635;
          const alpha = 0.10 + locFear * 0.28;
          heatLayer
            .poly([sx, sy - TILE_H / 2, sx + TILE_W / 2, sy, sx, sy + TILE_H / 2, sx - TILE_W / 2, sy])
            .fill({ color: heatColor, alpha });
        }

        const selected = useWorld.getState().selectedId;
        const seen = new Set<string>();
        for (const c of w.citizens) {
          seen.add(c.id);
          let s = sprites.get(c.id);
          const { sx, sy } = toScreen(c.x, c.y);
          if (!s) {
            s = makeSprite(c.id, c.name);
            s.dispX = sx;
            s.dispY = sy;
            sprites.set(c.id, s);
          }
          s.tgtX = sx;
          s.tgtY = sy;
          s.dot.clear();
          s.dot.circle(0, 0, 6)
            .fill({ color: citizenColorWithFear(c.id, c.fear ?? 0) })
            .stroke({ width: 1.5, color: 0x0b0e14 });
          s.ring.alpha = selected === c.id ? 1 : 0;

          // Fear aura — glowing halo behind dot for frightened citizens
          s.fearAura.clear();
          const fear = c.fear ?? 0;
          if (fear > 0.12) {
            const auraColor = fear > 0.65 ? 0xf87171 : fear > 0.35 ? 0xfbbf24 : 0xa3e635;
            s.fearAura.circle(0, 0, 8 + fear * 10).fill({ color: auraColor, alpha: 0.15 + fear * 0.30 });
          }
          if (c.speech) {
            // Strip "Name: " prefix — name is already shown in the label below
            const raw = c.speech;
            const colonIdx = raw.indexOf(": ");
            const dialogue = colonIdx !== -1 ? raw.slice(colonIdx + 2) : raw;
            const display = dialogue.length > 50 ? dialogue.slice(0, 49) + "…" : dialogue;
            s.bubbleText.text = display;

            const bg = (s.bubble as unknown as { _bg: Graphics })._bg;
            bg.clear();
            const bw = s.bubbleText.width + 16;
            const bh = s.bubbleText.height + 10;
            // Bubble body
            bg.roundRect(0, 0, bw, bh, 6).fill({ color: 0xf2f6ff });
            // Downward pointer triangle centred at bottom
            const px = bw / 2;
            bg.poly([px - 5, bh, px + 5, bh, px, bh + 7]).fill({ color: 0xf2f6ff });

            s.bubble.x = -(bw / 2);
            s.bubble.y = -(bh + 7 + 18); // 18px gap above the dot top
            s.bubble.visible = true;
          } else {
            s.bubble.visible = false;
          }
        }
        for (const [id, s] of sprites) {
          if (!seen.has(id)) {
            s.container.destroy();
            sprites.delete(id);
          }
        }
        night.clear();
        night.rect(0, 0, app.renderer.width, app.renderer.height)
          .fill({ color: 0x05070d, alpha: nightAlpha(w.day_progress) });
      };

      app.ticker.add(() => {
        for (const s of sprites.values()) {
          s.dispX += (s.tgtX - s.dispX) * 0.15;
          s.dispY += (s.tgtY - s.dispY) * 0.15;
          s.container.x = s.dispX;
          s.container.y = s.dispY;
          s.container.zIndex = s.dispY;
        }
        peopleLayer.sortableChildren = true;

        // Pulsing red rings over crisis-closed buildings
        pulseLayer.clear();
        if (closedPos.length) {
          const t = performance.now() / 1000;
          const alpha = 0.20 + 0.28 * (0.5 + 0.5 * Math.sin(t * 2.8));
          const r = 13 + 5 * (0.5 + 0.5 * Math.sin(t * 2.8));
          for (const { sx, sy } of closedPos) {
            pulseLayer.circle(sx, sy - 16, r).fill({ color: 0xf87171, alpha });
          }
        }

        // Full-screen red flash on new crisis injection
        flashLayer.clear();
        const nowMs = performance.now();
        if (nowMs < crisisFlashUntil) {
          const frac = (crisisFlashUntil - nowMs) / 1000;
          flashLayer
            .rect(0, 0, app.renderer.width, app.renderer.height)
            .fill({ color: 0xf87171, alpha: frac * 0.20 });
        }
      });

      unsub = useWorld.subscribe(sync);
      sync();
    })();

    return () => {
      destroyed = true;
      unsub?.();
      try {
        app.destroy(true, { children: true });
      } catch {
        /* not yet initialized */
      }
    };
  }, []);

  return <div ref={ref} style={{ width: "100%", height: "100%" }} />;
}
