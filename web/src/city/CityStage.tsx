import { useEffect, useRef } from "react";
import { Application, Circle, Container, Graphics, Text, TextStyle } from "pixi.js";
import { useWorld } from "../ws/store";
import {
  TILE_W,
  TILE_H,
  toScreen,
  LOCATION_COLORS,
  citizenColor,
  nightAlpha,
} from "./iso";

type CitizenSprite = {
  container: Container;
  dot: Graphics;
  ring: Graphics;
  bubble: Container;
  bubbleText: Text;
  dispX: number;
  dispY: number;
  tgtX: number;
  tgtY: number;
};

const nameStyle = new TextStyle({ fill: 0xe6edf3, fontSize: 11, fontWeight: "600" });
const labelStyle = new TextStyle({ fill: 0xb8c4d4, fontSize: 10, fontWeight: "700" });
const speechStyle = new TextStyle({ fill: 0x0b0e14, fontSize: 11, wordWrap: true, wordWrapWidth: 150 });

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
      const locLayer = new Container();
      const peopleLayer = new Container();
      const night = new Graphics();
      world.addChild(ground, locLayer, peopleLayer);
      app.stage.addChild(night);

      let built = false;

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

      const drawLocations = (locs: ReturnType<typeof useWorld.getState>["world"]) => {
        locLayer.removeChildren();
        for (const l of locs!.locations) {
          const { sx, sy } = toScreen(l.x, l.y);
          const color = LOCATION_COLORS[l.type] ?? 0x444444;
          const g = new Graphics();
          // a little iso "building" block
          const bw = 22, bh = 26;
          g.poly([sx, sy - bh, sx + bw / 2, sy - bh + 10, sx, sy - bh + 20, sx - bw / 2, sy - bh + 10])
            .fill({ color });
          g.rect(sx - bw / 2, sy - bh + 10, bw, 16).fill({ color, alpha: 0.85 });
          locLayer.addChild(g);
          const label = new Text({ text: l.name, style: labelStyle });
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
        container.hitArea = new Circle(0, 0, 14); // generous, easy-to-click target
        container.on("pointertap", () => useWorld.getState().select(id));

        const ring = new Graphics();
        ring.circle(0, 0, 9).stroke({ width: 2, color: 0xffffff, alpha: 0 });
        const dot = new Graphics();
        dot.circle(0, 0, 6).fill({ color: citizenColor(id) }).stroke({ width: 1.5, color: 0x0b0e14 });

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
        (bubble as any)._bg = bubbleBg;

        container.addChild(ring, dot, nameText, bubble);
        peopleLayer.addChild(container);
        return { container, dot, ring, bubble, bubbleText, dispX: 0, dispY: 0, tgtX: 0, tgtY: 0 };
      };

      const sync = () => {
        const w = useWorld.getState().world;
        if (!w) return;
        if (!built) {
          fitWorld(w.grid.w, w.grid.h);
          drawGround(w.grid.w, w.grid.h);
          drawLocations(w);
          built = true;
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
          // selection ring
          s.ring.alpha = selected === c.id ? 1 : 0;
          // speech bubble
          if (c.speech) {
            const text = c.speech.length > 80 ? c.speech.slice(0, 79) + "…" : c.speech;
            s.bubbleText.text = text;
            const bg = (s.bubble as any)._bg as Graphics;
            bg.clear();
            bg.roundRect(0, 0, s.bubbleText.width + 16, s.bubbleText.height + 10, 6).fill({ color: 0xf2f6ff });
            s.bubble.x = -(s.bubbleText.width + 16) / 2;
            s.bubble.y = -34;
            s.bubble.visible = true;
          } else {
            s.bubble.visible = false;
          }
        }
        // remove stale
        for (const [id, s] of sprites) {
          if (!seen.has(id)) {
            s.container.destroy();
            sprites.delete(id);
          }
        }
        // night overlay
        night.clear();
        night.rect(0, 0, app.renderer.width, app.renderer.height).fill({ color: 0x05070d, alpha: nightAlpha(w.day_progress) });
      };

      app.ticker.add(() => {
        for (const s of sprites.values()) {
          s.dispX += (s.tgtX - s.dispX) * 0.15;
          s.dispY += (s.tgtY - s.dispY) * 0.15;
          // depth sort: lower on screen drawn on top
          s.container.x = s.dispX;
          s.container.y = s.dispY;
          s.container.zIndex = s.dispY;
        }
        peopleLayer.sortableChildren = true;
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
