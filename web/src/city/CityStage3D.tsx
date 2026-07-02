import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { CSS2DRenderer, CSS2DObject } from "three/examples/jsm/renderers/CSS2DRenderer.js";
import { useWorld } from "../ws/store";
import type { LocationT, Citizen } from "../ws/store";

// ── Palette - delegation-inspired: rich, muted jewel tones, clean geometry ──
const BG   = 0x080c14;
const CELL = 2.4;

type BuildingDef = { color: number; accent: number; height: number; label: string };
const BUILDING_DEF: Record<string, BuildingDef> = {
  home:        { color: 0x1c2b3a, accent: 0x4b7fa8, height: 1.5,  label: "#4b7fa8" },
  workplace:   { color: 0x2a1f14, accent: 0xb07d3a, height: 2.6,  label: "#b07d3a" },
  commons:     { color: 0x122318, accent: 0x3a8a5c, height: 1.3,  label: "#3a8a5c" },
  institution: { color: 0x16122a, accent: 0x6b5db8, height: 4.0,  label: "#6b5db8" },
};

// ── fear → clean pastel gradient ─────────────────────────────────────────────
function fearColor(fear: number): THREE.Color {
  const c = new THREE.Color();
  if (fear < 0.4)
    c.lerpColors(new THREE.Color(0x7cb4e0), new THREE.Color(0xe0c47c), fear / 0.4);
  else
    c.lerpColors(new THREE.Color(0xe0c47c), new THREE.Color(0xe07c7c), (fear - 0.4) / 0.6);
  return c;
}

function gridToWorld(gx: number, gy: number, gw: number, gh: number) {
  return { x: (gx - (gw - 1) / 2) * CELL, z: (gy - (gh - 1) / 2) * CELL };
}

// ── Citizen runtime state ─────────────────────────────────────────────────────
type CitizenObj = {
  body: THREE.Mesh; head: THREE.Mesh; shadow: THREE.Mesh;
  label: CSS2DObject; bubble: CSS2DObject; bubbleEl: HTMLDivElement;
  dispX: number; dispZ: number; tgtX: number; tgtZ: number;
};

// ── Sky gradient via large sphere ─────────────────────────────────────────────
function makeSkyDome(): THREE.Mesh {
  const geo = new THREE.SphereGeometry(90, 32, 16);
  geo.scale(-1, 1, 1); // invert normals
  const canvas = document.createElement("canvas");
  canvas.width = 2; canvas.height = 256;
  const ctx = canvas.getContext("2d")!;
  const grad = ctx.createLinearGradient(0, 0, 0, 256);
  grad.addColorStop(0,    "#0b1428"); // zenith  - deep midnight blue
  grad.addColorStop(0.55, "#0d1520"); // mid
  grad.addColorStop(1,    "#060a10"); // horizon - almost black
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 2, 256);
  const tex = new THREE.CanvasTexture(canvas);
  tex.needsUpdate = true;
  const mat = new THREE.MeshBasicMaterial({ map: tex, depthWrite: false, fog: false });
  return new THREE.Mesh(geo, mat);
}

// ── Scattered star points ────────────────────────────────────────────────────
function makeStars(): THREE.Points {
  const N = 1400;
  const pos = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi   = Math.acos(2 * Math.random() - 1) * 0.48; // upper hemisphere only
    const r     = 82 + Math.random() * 6;
    pos[i*3]   = r * Math.sin(phi) * Math.cos(theta);
    pos[i*3+1] = r * Math.sin(phi) * Math.sin(theta);
    pos[i*3+2] = r * Math.cos(phi);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({
    color: 0xe8eeff, size: 0.18, sizeAttenuation: true,
    transparent: true, opacity: 0.55, depthWrite: false,
  });
  return new THREE.Points(geo, mat);
}

// ── Extended reflective ground plane ────────────────────────────────────────
function makeBasePlane(): THREE.Mesh {
  const geo = new THREE.PlaneGeometry(140, 140);
  const mat = new THREE.MeshStandardMaterial({
    color: 0x06090f, roughness: 0.08, metalness: 0.85,
  });
  const m = new THREE.Mesh(geo, mat);
  m.rotation.x = -Math.PI / 2;
  m.position.y = -0.015;
  m.receiveShadow = true;
  return m;
}

// ── Grid lines on ground (thin emissive lines) ───────────────────────────────
function makeGridLines(gw: number, gh: number): THREE.LineSegments {
  const pts: number[] = [];
  const cx = ((gw - 1) / 2) * CELL, cz = ((gh - 1) / 2) * CELL;
  const pad = CELL / 2;
  for (let gx = 0; gx <= gw; gx++) {
    const x = (gx - (gw - 1) / 2) * CELL - pad + CELL / 2;
    pts.push(x, 0.005, -cz - pad, x, 0.005, cz + pad);
  }
  for (let gz = 0; gz <= gh; gz++) {
    const z = (gz - (gh - 1) / 2) * CELL - pad + CELL / 2;
    pts.push(-cx - pad, 0.005, z, cx + pad, 0.005, z);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(pts), 3));
  const mat = new THREE.LineBasicMaterial({ color: 0x1a2535, transparent: true, opacity: 0.6 });
  return new THREE.LineSegments(geo, mat);
}

// ── Component ────────────────────────────────────────────────────────────────
export default function CityStage3D() {
  const containerRef = useRef<HTMLDivElement>(null);
  const flashRef     = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el      = containerRef.current;
    const flashEl = flashRef.current;
    if (!el) return;

    // ── Renderer ────────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping          = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure  = 1.18;
    renderer.setClearColor(BG, 1);
    renderer.shadowMap.enabled    = true;
    renderer.shadowMap.type       = THREE.PCFSoftShadowMap;
    renderer.domElement.style.cssText = "position:absolute;inset:0;width:100%;height:100%";
    renderer.setSize(el.offsetWidth || 800, el.offsetHeight || 600);
    el.appendChild(renderer.domElement);

    // ── CSS2D overlay ────────────────────────────────────────────────────────
    const labelRenderer = new CSS2DRenderer();
    labelRenderer.setSize(el.offsetWidth || 800, el.offsetHeight || 600);
    labelRenderer.domElement.style.cssText = "position:absolute;inset:0;pointer-events:none";
    el.appendChild(labelRenderer.domElement);

    // ── Scene ────────────────────────────────────────────────────────────────
    const scene = new THREE.Scene();
    scene.fog   = new THREE.FogExp2(BG, 0.014);

    // Sky + stars (behind everything)
    scene.add(makeSkyDome());
    scene.add(makeStars());
    scene.add(makeBasePlane());

    // ── Lighting (delegation-style: strong key + subtle fill) ────────────────
    // Key light: cool-white from upper-right, casts soft shadows
    const keyLight = new THREE.DirectionalLight(0xd0dcf0, 1.6);
    keyLight.position.set(14, 28, 16);
    keyLight.castShadow           = true;
    keyLight.shadow.camera.near   = 1;
    keyLight.shadow.camera.far    = 80;
    keyLight.shadow.camera.left   = -20;
    keyLight.shadow.camera.right  = 20;
    keyLight.shadow.camera.top    = 20;
    keyLight.shadow.camera.bottom = -20;
    keyLight.shadow.mapSize.set(2048, 2048);
    keyLight.shadow.radius        = 3;
    scene.add(keyLight);

    // Warm fill from low-left (bounce light off ground)
    const fillLight = new THREE.DirectionalLight(0x2a1a08, 0.35);
    fillLight.position.set(-10, 4, -12);
    scene.add(fillLight);

    // Subtle ambient
    scene.add(new THREE.AmbientLight(0x0d1525, 6.0));

    // ── Camera ────────────────────────────────────────────────────────────────
    const W0 = el.offsetWidth || 800, H0 = el.offsetHeight || 600;
    const camera = new THREE.PerspectiveCamera(40, W0 / H0, 0.1, 200);
    camera.position.set(0, 22, 26);
    camera.lookAt(0, 0, 0);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping  = true;
    controls.dampingFactor  = 0.06;
    controls.minPolarAngle  = 0.18;
    controls.maxPolarAngle  = Math.PI / 2.15;
    controls.minDistance    = 6;
    controls.maxDistance    = 55;

    // ── Post-processing - very subtle bloom only for accent glows ────────────
    const composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    const bloom = new UnrealBloomPass(new THREE.Vector2(W0, H0), 0.28, 0.6, 0.55);
    composer.addPass(bloom);
    composer.addPass(new OutputPass());

    // ── Groups ────────────────────────────────────────────────────────────────
    const groundGroup   = new THREE.Group();
    const buildingGroup = new THREE.Group();
    const crisisGroup   = new THREE.Group();
    const citizenGroup  = new THREE.Group();
    scene.add(groundGroup, buildingGroup, crisisGroup, citizenGroup);

    // ── Shared geo ───────────────────────────────────────────────────────────
    const bodyGeo   = new THREE.CapsuleGeometry(0.21, 0.46, 4, 8);
    const headGeo   = new THREE.SphereGeometry(0.175, 10, 8);
    const shadowGeo = new THREE.CircleGeometry(0.32, 16);

    // ── Runtime maps ─────────────────────────────────────────────────────────
    const citizens    = new Map<string, CitizenObj>();
    const buildings   = new Map<string, { body: THREE.Mesh; roof: THREE.Mesh; light: THREE.PointLight }>();
    const groundTiles = new Map<string, THREE.Mesh>();
    const clickable   : THREE.Mesh[] = [];
    let gridW = 0, gridH = 0, built = false;
    let prevCrises = 0, flashUntil = 0;

    // ── Raycaster ────────────────────────────────────────────────────────────
    const raycaster = new THREE.Raycaster();
    renderer.domElement.addEventListener("pointerdown", (e: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      raycaster.setFromCamera(
        new THREE.Vector2(
          ((e.clientX - rect.left) / rect.width)  * 2 - 1,
          -((e.clientY - rect.top)  / rect.height) * 2 + 1,
        ), camera,
      );
      const hit = raycaster.intersectObjects(clickable)[0];
      if (hit) {
        const id = hit.object.userData.citizenId as string | undefined;
        if (id) useWorld.getState().select(id);
      }
    });

    // ── Build ground tiles ───────────────────────────────────────────────────
    function buildGround(gw: number, gh: number) {
      groundGroup.clear();
      groundTiles.clear();
      const geo = new THREE.PlaneGeometry(CELL - 0.12, CELL - 0.12);
      for (let gx = 0; gx < gw; gx++) {
        for (let gy = 0; gy < gh; gy++) {
          const col = (gx + gy) % 2 === 0 ? 0x0c1520 : 0x091019;
          const mat = new THREE.MeshStandardMaterial({ color: col, roughness: 0.25, metalness: 0.6, emissive: 0x000000, emissiveIntensity: 0 });
          const m = new THREE.Mesh(geo, mat);
          m.rotation.x = -Math.PI / 2;
          m.position.y = 0.001;
          m.receiveShadow = true;
          const p = gridToWorld(gx, gy, gw, gh);
          m.position.set(p.x, 0.001, p.z);
          groundGroup.add(m);
          groundTiles.set(`${gx},${gy}`, m);
        }
      }
      groundGroup.add(makeGridLines(gw, gh));
    }

    // ── Build buildings ──────────────────────────────────────────────────────
    function buildBuildings(locs: LocationT[], gw: number, gh: number) {
      buildingGroup.clear(); crisisGroup.clear(); buildings.clear(); clickable.length = 0;

      for (const loc of locs) {
        const def = BUILDING_DEF[loc.type] ?? BUILDING_DEF.home;
        const p   = gridToWorld(loc.x, loc.y, gw, gh);
        const bw  = CELL * 0.50;

        // Body - clean matte, casts + receives shadow
        const bodyGeo = new THREE.BoxGeometry(bw, def.height, bw);
        const bodyMat = new THREE.MeshStandardMaterial({
          color: def.color, roughness: 0.72, metalness: 0.18,
        });
        const body = new THREE.Mesh(bodyGeo, bodyMat);
        body.position.set(p.x, def.height / 2, p.z);
        body.castShadow = body.receiveShadow = true;
        buildingGroup.add(body);

        // Thin roof accent - slight emissive glow (not neon, just a hint)
        const roofGeo = new THREE.BoxGeometry(bw + 0.07, 0.045, bw + 0.07);
        const roofMat = new THREE.MeshStandardMaterial({
          color: def.accent, emissive: new THREE.Color(def.accent),
          emissiveIntensity: 0.55, roughness: 0.4,
        });
        const roof = new THREE.Mesh(roofGeo, roofMat);
        roof.position.set(p.x, def.height + 0.022, p.z);
        buildingGroup.add(roof);

        // Name label - minimal, appears above building
        const div = document.createElement("div");
        div.textContent = loc.name;
        div.style.cssText = [
          `color:${def.label}`,
          "font-size:8.5px",
          "font-family:'SF Mono',ui-monospace,monospace",
          "letter-spacing:0.06em",
          "text-transform:uppercase",
          "white-space:nowrap",
          "pointer-events:none",
          "opacity:0.8",
        ].join(";");
        const labelObj = new CSS2DObject(div);
        labelObj.position.set(p.x, def.height + 0.5, p.z);
        scene.add(labelObj);

        // Crisis point-light (off by default)
        const light = new THREE.PointLight(0xd94040, 0, CELL * 3.5);
        light.position.set(p.x, def.height + 1, p.z);
        crisisGroup.add(light);

        buildings.set(loc.id, { body, roof, light });
      }
    }

    // ── Update buildings ─────────────────────────────────────────────────────
    function updateBuildings(locs: LocationT[], closed: string[]) {
      for (const loc of locs) {
        const b = buildings.get(loc.id);
        if (!b) continue;
        const def    = BUILDING_DEF[loc.type] ?? BUILDING_DEF.home;
        const isDown = closed.includes(loc.id);
        const bm     = b.body.material as THREE.MeshStandardMaterial;
        const rm     = b.roof.material as THREE.MeshStandardMaterial;
        if (isDown) {
          bm.color.setHex(0x2a1010);
          rm.color.setHex(0xd94040);
          rm.emissive.setHex(0xd94040);
          rm.emissiveIntensity = 0.9;
        } else {
          bm.color.setHex(def.color);
          rm.color.setHex(def.accent);
          rm.emissive.setHex(def.accent);
          rm.emissiveIntensity = 0.55;
        }
      }
    }

    // ── Update crisis lights ─────────────────────────────────────────────────
    function updateCrisisLights(locs: LocationT[], closed: string[], t: number) {
      for (const loc of locs) {
        const b = buildings.get(loc.id);
        if (!b) continue;
        b.light.intensity = closed.includes(loc.id) ? 2.0 + 0.7 * Math.sin(t * 2.8) : 0;
      }
    }

    // ── Ground fear heatmap ──────────────────────────────────────────────────
    function updateHeat(citizenData: Citizen[], locs: LocationT[]) {
      const fearMap = new Map<string, number>();
      for (const c of citizenData)
        if ((c.fear ?? 0) > 0.1 && c.location_id)
          fearMap.set(c.location_id, Math.max(fearMap.get(c.location_id) ?? 0, c.fear));

      for (const [key, tile] of groundTiles) {
        const [xs, ys] = key.split(",");
        const loc = locs.find(l => l.x === +xs && l.y === +ys);
        const mat = tile.material as THREE.MeshStandardMaterial;
        if (loc) {
          const f = fearMap.get(loc.id) ?? 0;
          mat.emissive.copy(fearColor(f));
          mat.emissiveIntensity = f * 0.14;
        } else {
          mat.emissive.set(0, 0, 0);
          mat.emissiveIntensity = 0;
        }
      }
    }

    // ── Citizen factory ──────────────────────────────────────────────────────
    function getCitizen(id: string, name: string): CitizenObj {
      const ex = citizens.get(id);
      if (ex) return ex;

      // Clean matte white-ish body, head tinted by fear
      const bodyMat = new THREE.MeshStandardMaterial({ color: 0xe8eef5, roughness: 0.65, metalness: 0.05 });
      const headMat = new THREE.MeshStandardMaterial({ color: 0xccd8e8, roughness: 0.55, metalness: 0.05,
        emissive: new THREE.Color(0x7cb4e0), emissiveIntensity: 0.12 });

      // Faint blob shadow on ground
      const shadowMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.22, depthWrite: false });

      const body   = new THREE.Mesh(bodyGeo, bodyMat);
      body.castShadow = true;
      body.userData.citizenId = id;
      body.position.y = 0.53;

      const head   = new THREE.Mesh(headGeo, headMat);
      head.castShadow = true;
      head.userData.citizenId = id;
      head.position.y = 1.1;

      const shadow = new THREE.Mesh(shadowGeo, shadowMat);
      shadow.rotation.x = -Math.PI / 2;
      shadow.position.y = 0.003;

      // Citizen label - first name only, ultra minimal
      const nameDiv = document.createElement("div");
      nameDiv.textContent = name.split(" ")[0];
      nameDiv.style.cssText = [
        "color:rgba(180,200,225,0.55)",
        "font-size:7px",
        "font-family:'SF Mono',ui-monospace,monospace",
        "letter-spacing:0.12em",
        "text-transform:uppercase",
        "white-space:nowrap",
        "pointer-events:none",
      ].join(";");
      const label = new CSS2DObject(nameDiv);
      label.position.set(0, 1.45, 0);

      // Speech bubble - clean dark glass
      const bubbleEl = document.createElement("div");
      bubbleEl.style.cssText = [
        "background:rgba(6,10,18,0.82)",
        "color:rgba(210,225,245,0.9)",
        "font-size:9.5px",
        "font-family:ui-sans-serif,system-ui,sans-serif",
        "border:1px solid rgba(75,127,168,0.28)",
        "border-radius:6px",
        "padding:5px 9px",
        "max-width:130px",
        "line-height:1.45",
        "pointer-events:none",
        "display:none",
        "white-space:pre-wrap",
        "letter-spacing:0.01em",
      ].join(";");
      const bubble = new CSS2DObject(bubbleEl);
      bubble.position.set(0, 1.95, 0);

      citizenGroup.add(body, head, shadow, label, bubble);
      clickable.push(body, head);

      const obj: CitizenObj = { body, head, shadow, label, bubble, bubbleEl,
        dispX: 0, dispZ: 0, tgtX: 0, tgtZ: 0 };
      citizens.set(id, obj);
      return obj;
    }

    function updateCitizen(c: Citizen, gw: number, gh: number, selected: string | null, t: number) {
      const obj = getCitizen(c.id, c.name);
      const p   = gridToWorld(c.x, c.y, gw, gh);
      obj.tgtX = p.x; obj.tgtZ = p.z;

      const fear = c.fear ?? 0;
      const fc   = fearColor(fear);

      const hm = obj.head.material as THREE.MeshStandardMaterial;
      hm.emissive.copy(fc);
      hm.emissiveIntensity = 0.10 + fear * 0.55;
      // Body tints slightly toward fear color at high fear
      const bm = obj.body.material as THREE.MeshStandardMaterial;
      bm.color.lerpColors(new THREE.Color(0xe8eef5), fc, fear * 0.28);

      // Selection: brighter head
      if (selected === c.id) hm.emissiveIntensity = Math.min(1.2, hm.emissiveIntensity + 0.6);

      // Shadow scales with fear (fear makes you stand out more)
      const sm = obj.shadow.material as THREE.MeshBasicMaterial;
      sm.opacity = 0.18 + fear * 0.12;
      const ss = 1 + fear * 0.4;
      obj.shadow.scale.set(ss, ss, ss);

      // Speech bubble
      if (c.speech) {
        const raw = c.speech;
        const ci  = raw.indexOf(": ");
        const txt = (ci !== -1 ? raw.slice(ci + 2) : raw).slice(0, 58);
        obj.bubbleEl.textContent    = txt.length < raw.length - ci - 2 ? txt + "…" : txt;
        obj.bubbleEl.style.display  = "block";
      } else {
        obj.bubbleEl.style.display  = "none";
      }
      void t;
    }

    // ── Store sync ───────────────────────────────────────────────────────────
    function sync() {
      const w = useWorld.getState().world;
      if (!w) return;
      const { grid, locations, citizens: cd, closed_locations, active_crises } = w;

      if (!built) {
        gridW = grid.w; gridH = grid.h;
        buildGround(gridW, gridH);
        buildBuildings(locations, gridW, gridH);
        built = true;
      }

      updateBuildings(locations, closed_locations ?? []);
      updateHeat(cd, locations);

      if ((active_crises?.length ?? 0) > prevCrises && flashEl)
        flashUntil = performance.now() + 800;
      prevCrises = active_crises?.length ?? 0;

      const sel = useWorld.getState().selectedId;
      const seen = new Set<string>();
      for (const c of cd) {
        seen.add(c.id);
        updateCitizen(c, gridW, gridH, sel, 0);
      }
      for (const [id, obj] of citizens) {
        if (!seen.has(id)) {
          citizenGroup.remove(obj.body, obj.head, obj.shadow, obj.label, obj.bubble);
          const bi = clickable.indexOf(obj.body); if (bi !== -1) clickable.splice(bi, 1);
          const hi = clickable.indexOf(obj.head); if (hi !== -1) clickable.splice(hi, 1);
          citizens.delete(id);
        }
      }
    }

    const unsub = useWorld.subscribe(sync);
    sync();

    // ── Animation loop ───────────────────────────────────────────────────────
    const clock = new THREE.Clock();
    let raf = 0;

    function animate() {
      raf = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();
      controls.update();

      // Citizen position lerp + subtle float
      for (const [, obj] of citizens) {
        obj.dispX += (obj.tgtX - obj.dispX) * 0.11;
        obj.dispZ += (obj.tgtZ - obj.dispZ) * 0.11;
        const fy = 0.014 * Math.sin(t * 1.5 + obj.tgtX * 0.8);
        obj.body.position.set(obj.dispX, 0.53 + fy, obj.dispZ);
        obj.head.position.set(obj.dispX, 1.1  + fy, obj.dispZ);
        obj.shadow.position.set(obj.dispX, 0.003, obj.dispZ);
        obj.label.position.set(obj.dispX, 1.45 + fy, obj.dispZ);
        obj.bubble.position.set(obj.dispX, 1.95 + fy, obj.dispZ);
      }

      // Crisis lights
      if (built) {
        const w = useWorld.getState().world;
        if (w) updateCrisisLights(w.locations, w.closed_locations ?? [], t);
      }

      // Flash overlay
      if (flashEl) {
        const now = performance.now();
        flashEl.style.opacity = now < flashUntil
          ? String(((flashUntil - now) / 800) * 0.16) : "0";
      }

      composer.render();
      labelRenderer.render(scene, camera);
    }
    animate();

    // ── Resize ───────────────────────────────────────────────────────────────
    const onResize = () => {
      const w = el.offsetWidth, h = el.offsetHeight;
      if (!w || !h) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
      composer.setSize(w, h);
      labelRenderer.setSize(w, h);
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(el);
    window.addEventListener("resize", onResize);

    // ── Cleanup ──────────────────────────────────────────────────────────────
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      window.removeEventListener("resize", onResize);
      unsub();
      controls.dispose();
      renderer.dispose();
      composer.dispose();
      if (renderer.domElement.parentNode    === el) el.removeChild(renderer.domElement);
      if (labelRenderer.domElement.parentNode === el) el.removeChild(labelRenderer.domElement);
    };
  }, []);

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", position: "relative" }}>
      <div ref={flashRef} style={{
        position: "absolute", inset: 0, background: "#c0392b",
        opacity: 0, pointerEvents: "none", zIndex: 5,
      }} />
    </div>
  );
}
