# CivilizationOS — 3D Playground Transformation Plan

**Goal:** Replace the PixiJS 2D isometric city canvas with a full Three.js 3D scene —
free orbit camera, neon-cyberpunk aesthetic, emissive/bloom materials, animated citizens.
Inspired by arturitu.github.io/the-delegation.

**What stays 100% unchanged:** FastAPI backend, WebSocket, all sidebar panels, store,
Chronicle, StatsPanel, Inspector, CouncilChamber, ScenarioLauncher, ToastStack.
Only `CityStage.tsx` is replaced.

---

## 1. Install Dependencies

```bash
cd web
npm install three
npm install -D @types/three
```

Three.js includes everything needed (OrbitControls, EffectComposer, CSS2DRenderer)
under `three/examples/jsm/` — no extra packages required.

---

## 2. New File to Create

### `web/src/city/CityStage3D.tsx`

This is the ONLY new file. ~420 lines. Full spec below.

### `web/src/App.tsx` — one-line change

```tsx
// Replace:
import CityStage from "./city/CityStage";
// With:
import CityStage3D as CityStage from "./city/CityStage3D";
```

Keep `CityStage.tsx` intact as fallback.

---

## 3. Scene Architecture

```
THREE.WebGLRenderer (antialias, ACESFilmic tone mapping, exposure 1.2)
  └─ scene (bg: 0x070a0f, Fog 30→80)
       ├─ AmbientLight 0x0d1220 intensity 3.0
       ├─ DirectionalLight 0x6ea8fe intensity 0.6 @ (10,20,10)
       ├─ groundGroup  ← PlaneGeometry tiles (10×10), emissive fear heatmap
       ├─ buildingGroup ← BoxGeometry per location + roof-edge glow
       ├─ crisisLights  ← PointLight per location (hidden until closed)
       └─ citizenGroup  ← CapsuleGeometry body + SphereGeometry head per citizen

THREE.PerspectiveCamera(45, aspect, 0.1, 200)
  initial position: (0, 22, 26) looking at (0,0,0)

OrbitControls (damping 0.06, polar 0.2..PI/2.2, distance 8..60)

EffectComposer
  ├─ RenderPass
  └─ UnrealBloomPass (strength: 0.75, radius: 0.4, threshold: 0.1)

CSS2DRenderer (overlay, pointer-events: none)
  └─ CSS2DObject per citizen: name label + speech bubble div
```

---

## 4. Coordinate System

Grid cell size `CELL = 2.4` world units.

```typescript
function gridToWorld(gx, gy, gw, gh) {
  return {
    x: (gx - (gw - 1) / 2) * CELL,
    z: (gy - (gh - 1) / 2) * CELL,
  };
}
```

---

## 5. Visual Spec

### Ground tiles
- Alternating shades: `0x10161e` / `0x0c1018`
- Fear heatmap: emissive color lerped from `0x000000` → fear color, intensity 0–0.24
- PlaneGeometry `(CELL - 0.08, CELL - 0.08)`, rotated -90° on X

### Buildings (BoxGeometry per location)
| Type        | Color    | Emissive | Emissive Intensity | Height |
|-------------|----------|----------|--------------------|--------|
| home        | 0x1e2d3d | 0x1e293b | 0.04               | 1.6    |
| workplace   | 0x1a2940 | 0xfbbf24 | 0.06               | 2.2    |
| commons     | 0x1a3329 | 0x34d399 | 0.08               | 1.2    |
| institution | 0x1a1f3a | 0x6ea8fe | 0.10               | 3.6    |

- Width/depth: `CELL * 0.55`
- Roof edge: thin `BoxGeometry(CELL*0.57, 0.06, CELL*0.57)` with emissive intensity 0.6
- Crisis (closed) override: emissive `0xf87171`, intensity 0.35
- Location name: CSS2DObject above roof

### Citizens (CapsuleGeometry + SphereGeometry)
- Body: `CapsuleGeometry(0.22, 0.5, 4, 8)` at y=0.55
- Head: `SphereGeometry(0.18, 8, 6)` at y=1.15
- Emissive color = `fearColor(fear)` (lerp: blue → amber → red)
- Emissive intensity: body `0.2 + fear * 0.8`, head `0.3 + fear * 0.9`
- Fear aura: `CircleGeometry(0.6, 16)` flat on ground, emissive color, opacity 0 → 0.45
- Gentle float: `position.y = 0.015 * sin(t * 1.8 + tgtX)`
- Position interpolates: `pos += (target - pos) * 0.12`

```typescript
function fearColor(fear: number): THREE.Color {
  const c = new THREE.Color();
  if (fear < 0.35)
    c.lerpColors(new THREE.Color(0x6ea8fe), new THREE.Color(0xfbbf24), fear / 0.35);
  else
    c.lerpColors(new THREE.Color(0xfbbf24), new THREE.Color(0xf87171), (fear - 0.35) / 0.65);
  return c;
}
```

### Crisis PointLights
- One `PointLight(0xf87171, 0, CELL * 3)` per location at `(locX, height+1, locZ)`
- When closed: intensity = `2.0 + 0.8 * sin(t * 3.2)` (pulsing)
- When open: intensity = 0

### Crisis screen flash
- DOM `<div>` absolutely positioned over scene
- On new crisis (active_crises count increase): opacity fades 0.22 → 0 over 900ms

---

## 6. Interactivity

### Click to select citizen
```typescript
const raycaster = new THREE.Raycaster();
renderer.domElement.addEventListener("pointerdown", (e) => {
  // convert to NDC, raycast against body+head meshes
  // on hit: useWorld.getState().select(citizenId)
});
```

### OrbitControls
- Left-drag: orbit
- Right-drag / two-finger: pan
- Scroll: zoom

---

## 7. Animation Loop (requestAnimationFrame)

```typescript
function animate() {
  frameId = requestAnimationFrame(animate);
  const t = clock.getElapsedTime();
  controls.update();

  // 1. Interpolate citizen positions
  // 2. Pulse crisis PointLights (sin wave)
  // 3. Pulse citizen aura scale
  // 4. Flash overlay opacity decay
  // 5. composer.render()        ← bloom
  // 6. labelRenderer.render()   ← CSS2D labels
}
```

---

## 8. CSS2DRenderer Setup

```typescript
const labelRenderer = new CSS2DRenderer();
labelRenderer.setSize(el.clientWidth, el.clientHeight);
labelRenderer.domElement.style.position = "absolute";
labelRenderer.domElement.style.top = "0";
labelRenderer.domElement.style.pointerEvents = "none";
el.appendChild(labelRenderer.domElement);
```

CSS2DObjects:
- Citizen name: `<div>` gray `#94a3b8`, 9px monospace
- Speech bubble: `<div>` white bg, dark text, border-radius, display none until `c.speech`

---

## 9. Store Integration

```typescript
let unsub: (() => void) | undefined;

function sync() {
  const w = useWorld.getState().world;
  if (!w) return;
  // Build scene on first sync
  // Update buildings (crisis emissive)
  // Update crisis lights
  // Update ground tile fear heatmap
  // Update/create citizens (fear color, aura, bubble)
  // Remove gone citizens
  // Detect new crisis → trigger flash
}

unsub = useWorld.subscribe(sync);
sync(); // immediate first render
```

---

## 10. Cleanup (useEffect return)

```typescript
return () => {
  cancelAnimationFrame(frameId);
  window.removeEventListener("resize", onResize);
  renderer.domElement.removeEventListener("pointerdown", onPointerDown);
  unsub?.();
  controls.dispose();
  renderer.dispose();
  composer.dispose();
  // remove domElements from container
};
```

---

## 11. TypeScript Notes

- `@types/three` is included in `three` package v0.170+
- Import path for addons: `three/examples/jsm/controls/OrbitControls.js`
- All geometry/material types are explicit — no `any` except for the world snapshot fields
  (which are already typed via the store)

---

## 12. Implementation Order (for a clean session)

1. `cd web && npm install three` — confirm output has no errors
2. Create `web/src/city/CityStage3D.tsx` — full file, ~420 lines
3. Update `App.tsx` — swap import (1 line change)
4. `npx tsc --noEmit` — fix any type errors
5. Start dev server and verify:
   - City renders in 3D
   - Citizens move and glow
   - Fear colors update live
   - OrbitControls work
   - Click selects citizen
   - Crisis buildings glow red
   - Bloom effect visible on emissive surfaces
6. Commit: `feat: Phase 12 - Three.js 3D city with orbit camera, bloom, neon cyberpunk`

---

## 13. Expected Visual Result

- Dark background with fog at edges
- City sits at center, institutional buildings tower over homes
- Glowing roof edges outline every building in its type color
- Citizens float and breathe with emissive glow that shifts from blue → red as fear rises
- Fear aura rings pulse outward on frightened citizens
- Crisis locations flood red with point lights that strobe
- Full-screen red flash when new crisis fires
- OrbitControls let you fly around the city at any angle
- Bloom makes all emissive surfaces bleed light into the darkness

---

*Written 2026-06-25 | Resume this plan in a new session to implement Phase 12*
