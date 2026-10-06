import { useCallback, useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { CSS2DRenderer, CSS2DObject } from "three/examples/jsm/renderers/CSS2DRenderer.js";
import { useWorld } from "../ws/store";
import type { LocationT, Citizen } from "../ws/store";

// ── Palette: readable by day, moody by night ────────────────────────────────
const CELL = 2.4;

type BuildingDef = {
  wall: number; accent: number; height: number; label: string; kind: string; blurb: string;
};
const BUILDING_DEF: Record<string, BuildingDef> = {
  home:        { wall: 0x6f8fb0, accent: 0x7fb0dc, height: 1.5, label: "#8cc0ea", kind: "Home",        blurb: "where citizens live" },
  workplace:   { wall: 0xa88458, accent: 0xe0a448, height: 2.7, label: "#e8b560", kind: "Workplace",   blurb: "daytime jobs" },
  commons:     { wall: 0x4f8f6c, accent: 0x58c488, height: 1.2, label: "#76d6a0", kind: "Public space", blurb: "where people meet" },
  institution: { wall: 0x7a6fc4, accent: 0xa597ff, height: 4.2, label: "#b4a8ff", kind: "Council",     blurb: "debates crises" },
};

// ── helpers ──────────────────────────────────────────────────────────────────
const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const smooth = (a: number, b: number, v: number) => {
  const t = clamp01((v - a) / (b - a));
  return t * t * (3 - 2 * t);
};

/** 0 = deep night, 1 = full day, from the sim's 0..1 day progress (0 = midnight). */
function daylightAt(dayProgress: number) {
  const h = (((dayProgress % 1) + 1) % 1) * 24;
  const day = smooth(5.5, 8, h) * (1 - smooth(17, 19.5, h));
  const warm = Math.exp(-Math.pow(h - 6.8, 2) / 1.6) + Math.exp(-Math.pow(h - 18.4, 2) / 1.8);
  return { day, warm: clamp01(warm) };
}

function fearColor(fear: number): THREE.Color {
  const c = new THREE.Color();
  if (fear < 0.4)
    c.lerpColors(new THREE.Color(0x7cc4f0), new THREE.Color(0xf0cc7c), fear / 0.4);
  else
    c.lerpColors(new THREE.Color(0xf0cc7c), new THREE.Color(0xf07c7c), (fear - 0.4) / 0.6);
  return c;
}

function hashHue(id: string): number {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return (h % 360) / 360;
}

function gridToWorld(gx: number, gy: number, gw: number, gh: number) {
  return { x: (gx - (gw - 1) / 2) * CELL, z: (gy - (gh - 1) / 2) * CELL };
}

// ── Citizen runtime state ─────────────────────────────────────────────────────
type CitizenObj = {
  id: string; name: string; occupation: string; action: string; fear: number;
  body: THREE.Mesh; head: THREE.Mesh; shadow: THREE.Mesh; ring: THREE.Mesh;
  selRing: THREE.Mesh; hit: THREE.Mesh; speech: string;
  label: CSS2DObject; bubble: CSS2DObject; bubbleEl: HTMLDivElement; nameEl: HTMLDivElement;
  dispX: number; dispZ: number; tgtX: number; tgtZ: number; moving: number;
};

// ── Sky dome with a day-night gradient driven by uniforms ────────────────────
function makeSkyDome() {
  const geo = new THREE.SphereGeometry(120, 32, 16);
  const mat = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: {
      top:    { value: new THREE.Color(0x0b1630) },
      bottom: { value: new THREE.Color(0x1a2a48) },
    },
    vertexShader: `varying float vY; void main(){ vY = normalize(position).y; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
    fragmentShader: `uniform vec3 top; uniform vec3 bottom; varying float vY;
      void main(){ float t = smoothstep(-0.05, 0.75, vY); gl_FragColor = vec4(mix(bottom, top, t), 1.0); }`,
  });
  return { mesh: new THREE.Mesh(geo, mat), mat };
}

function makeStars() {
  const N = 900;
  const pos = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(1 - Math.random() * 0.9);
    const r = 110;
    pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    pos[i * 3 + 1] = r * Math.cos(phi);
    pos[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({
    color: 0xe8eeff, size: 0.5, sizeAttenuation: true, transparent: true, opacity: 0.7,
    depthWrite: false, fog: false,
  });
  return { points: new THREE.Points(geo, mat), mat };
}

// Window grid used as an emissive map so towers read as buildings, and glow at night.
function makeWindowTexture(): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = 64; c.height = 64;
  const g = c.getContext("2d")!;
  g.fillStyle = "#000";
  g.fillRect(0, 0, 64, 64);
  for (let y = 0; y < 2; y++) {
    for (let x = 0; x < 2; x++) {
      const lit = Math.random() > 0.25;
      g.fillStyle = lit ? "#ffd9a0" : "#40342a";
      g.fillRect(8 + x * 28, 10 + y * 28, 14, 16);
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

function makeGridLines(gw: number, gh: number): THREE.LineSegments {
  const pts: number[] = [];
  const hw = (gw * CELL) / 2, hh = (gh * CELL) / 2;
  for (let gx = 0; gx <= gw; gx++) {
    const x = gx * CELL - hw;
    pts.push(x, 0.012, -hh, x, 0.012, hh);
  }
  for (let gz = 0; gz <= gh; gz++) {
    const z = gz * CELL - hh;
    pts.push(-hw, 0.012, z, hw, 0.012, z);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(pts), 3));
  return new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: 0x5a6f8c, transparent: true, opacity: 0.16 }));
}

// ── Component ────────────────────────────────────────────────────────────────
type Hover = { x: number; y: number; title: string; sub: string; accent: string } | null;

export default function CityStage3D() {
  const containerRef = useRef<HTMLDivElement>(null);
  const flashRef     = useRef<HTMLDivElement>(null);
  const resetViewRef = useRef<() => void>(() => {});
  const [hover, setHover] = useState<Hover>(null);
  const [legendOpen, setLegendOpen] = useState(() => {
    try { return !localStorage.getItem("civOS_legend_seen_v1"); } catch { return true; }
  });
  useEffect(() => {
    if (!legendOpen) return;
    try { localStorage.setItem("civOS_legend_seen_v1", "1"); } catch { /* ignore */ }
  }, [legendOpen]);
  const [ready, setReady] = useState(false);

  const resetView = useCallback(() => resetViewRef.current(), []);

  useEffect(() => {
    const el      = containerRef.current;
    const flashEl = flashRef.current;
    if (!el) return;

    // ── Renderer ────────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.toneMapping         = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.setClearColor(0x0b1020, 1);
    renderer.shadowMap.enabled   = true;
    renderer.shadowMap.type      = THREE.PCFShadowMap;
    renderer.domElement.style.cssText = "position:absolute;inset:0;width:100%;height:100%;touch-action:none";
    renderer.setSize(el.offsetWidth || 800, el.offsetHeight || 600);
    el.appendChild(renderer.domElement);

    const labelRenderer = new CSS2DRenderer();
    labelRenderer.setSize(el.offsetWidth || 800, el.offsetHeight || 600);
    labelRenderer.domElement.style.cssText = "position:absolute;inset:0;pointer-events:none";
    el.appendChild(labelRenderer.domElement);

    // ── Scene ────────────────────────────────────────────────────────────────
    const scene = new THREE.Scene();
    const fog = new THREE.FogExp2(0x1a2a48, 0.006);
    scene.fog = fog;

    const sky = makeSkyDome();
    scene.add(sky.mesh);
    const stars = makeStars();
    scene.add(stars.points);

    // Ground: matte, no metalness (a metallic surface with no environment map renders black)
    const baseMat = new THREE.MeshStandardMaterial({ color: 0x27354a, roughness: 0.95, metalness: 0 });
    const base = new THREE.Mesh(new THREE.PlaneGeometry(220, 220), baseMat);
    base.rotation.x = -Math.PI / 2;
    base.position.y = -0.03;
    base.receiveShadow = true;
    scene.add(base);

    // ── Lighting ─────────────────────────────────────────────────────────────
    const hemi = new THREE.HemisphereLight(0x9db8e0, 0x2a3140, 0.8);
    scene.add(hemi);
    const key = new THREE.DirectionalLight(0xffffff, 2);
    key.position.set(16, 30, 14);
    key.castShadow = true;
    key.shadow.camera.near = 1;
    key.shadow.camera.far = 90;
    key.shadow.camera.left = -40;
    key.shadow.camera.right = 40;
    key.shadow.camera.top = 28;
    key.shadow.camera.bottom = -28;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.bias = -0.0004;
    key.shadow.normalBias = 0.03;
    scene.add(key);

    // ── Camera ────────────────────────────────────────────────────────────────
    const W0 = el.offsetWidth || 800, H0 = el.offsetHeight || 600;
    const camera = new THREE.PerspectiveCamera(40, W0 / H0, 0.1, 400);
    const viewDir = new THREE.Vector3(0, 0.62, 0.78).normalize();
    const target = new THREE.Vector3(0, 0.6, 1);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minPolarAngle = 0.2;
    controls.maxPolarAngle = Math.PI / 2.12;
    controls.minDistance   = 7;
    controls.target.copy(target);
    controls.zoomSpeed = 0.8;

    let gridW = 0, gridH = 0, built = false;
    let fitDist = 50;
    let flyT = 0, flyActive = true;          // intro / reset fly-in progress (seconds)
    let flyFrom = 1.5;
    let userMoved = false;

    function computeFit() {
      const aspect = camera.aspect || 1.5;
      const tanV = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
      const W = (gridW || 24) * CELL, D = (gridH || 16) * CELL;
      const needW = (W / 2) * 1.2 / (tanV * aspect);
      const needH = (D / 2 * 0.66 + 4.2) / tanV;
      fitDist = Math.max(needW, needH);
      controls.maxDistance = fitDist * 1.5;
    }

    function placeCamera(distMul: number, elevBoost: number) {
      const dir = viewDir.clone();
      dir.y += elevBoost;
      dir.normalize();
      camera.position.copy(target).addScaledVector(dir, fitDist * distMul);
      controls.update();
    }

    function startFly(from: number) {
      flyFrom = from; flyT = 0; flyActive = true; userMoved = false;
      controls.enabled = false;
    }
    resetViewRef.current = () => {
      controls.target.copy(target);
      startFly(1.12);
    };
    controls.addEventListener("start", () => { userMoved = true; flyActive = false; controls.enabled = true; });

    // ── Post-processing ───────────────────────────────────────────────────────
    const composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    const bloom = new UnrealBloomPass(new THREE.Vector2(W0, H0), 0.32, 0.55, 0.78);
    composer.addPass(bloom);
    composer.addPass(new OutputPass());

    // ── Groups ────────────────────────────────────────────────────────────────
    const groundGroup   = new THREE.Group();
    const buildingGroup = new THREE.Group();
    const crisisGroup   = new THREE.Group();
    const citizenGroup  = new THREE.Group();
    const labelGroup    = new THREE.Group();
    scene.add(groundGroup, buildingGroup, crisisGroup, citizenGroup, labelGroup);

    // ── Shared geo ───────────────────────────────────────────────────────────
    const bodyGeo   = new THREE.CapsuleGeometry(0.27, 0.55, 4, 10);
    const headGeo   = new THREE.SphereGeometry(0.23, 14, 10);
    const shadowGeo = new THREE.CircleGeometry(0.4, 20);
    const ringGeo   = new THREE.RingGeometry(0.46, 0.56, 32);
    const selGeo    = new THREE.RingGeometry(0.82, 0.92, 40);
    const hitGeo    = new THREE.CylinderGeometry(0.6, 0.6, 2.1, 10);
    const hitMat    = new THREE.MeshBasicMaterial({ visible: false });
    const windowTex = makeWindowTexture();

    // ── Runtime maps ─────────────────────────────────────────────────────────
    const citizens    = new Map<string, CitizenObj>();
    const buildings   = new Map<string, {
      loc: LocationT; body: THREE.Mesh; roof: THREE.Mesh; light: THREE.PointLight;
      beacon: THREE.Mesh; windows: THREE.MeshStandardMaterial[]; px: number; pz: number;
    }>();
    const groundTiles = new Map<string, THREE.Mesh>();
    const clickable   : THREE.Object3D[] = [];
    const buildingMeshes: THREE.Object3D[] = [];
    let prevCrises = 0, flashUntil = 0;
    let daylight = { day: 0, warm: 0 };
    let hoverId: string | null = null;

    // ── Pointer: select + hover ─────────────────────────────────────────────
    const raycaster = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    function pick(e: PointerEvent) {
      const rect = renderer.domElement.getBoundingClientRect();
      ndc.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
      raycaster.setFromCamera(ndc, camera);
      return { hits: raycaster.intersectObjects([...clickable, ...buildingMeshes], false), rect };
    }
    let downX = 0, downY = 0;
    renderer.domElement.addEventListener("pointerdown", (e: PointerEvent) => { downX = e.clientX; downY = e.clientY; });
    renderer.domElement.addEventListener("pointerup", (e: PointerEvent) => {
      // a drag is an orbit, not a click
      if (Math.hypot(e.clientX - downX, e.clientY - downY) > 5) return;
      const hit = pick(e).hits.find(h => h.object.userData.citizenId);
      if (hit) useWorld.getState().select(hit.object.userData.citizenId as string);
    });
    let hoverRaf = 0;
    renderer.domElement.addEventListener("pointermove", (e: PointerEvent) => {
      if (e.buttons) return;
      if (hoverRaf) return;
      hoverRaf = requestAnimationFrame(() => {
        hoverRaf = 0;
        const { hits, rect } = pick(e);
        const h = hits[0];
        const cid = h?.object.userData.citizenId as string | undefined;
        const bid = h?.object.userData.buildingId as string | undefined;
        hoverId = cid ?? null;
        renderer.domElement.style.cursor = cid ? "pointer" : "grab";
        const px = e.clientX - rect.left, py = e.clientY - rect.top;
        if (cid) {
          const c = citizens.get(cid);
          if (c) {
            setHover({ x: px, y: py, title: c.name, sub: `${c.occupation} - ${c.action}`, accent: "#" + fearColor(c.fear).getHexString() });
            return;
          }
        }
        if (bid) {
          const b = buildings.get(bid);
          if (b) {
            const def = BUILDING_DEF[b.loc.type] ?? BUILDING_DEF.home;
            const w = useWorld.getState().world;
            const n = w?.citizens.filter(c => c.location_id === bid).length ?? 0;
            const down = w?.closed_locations?.includes(bid);
            const sub = down ? "CLOSED by a crisis" : `${def.kind} - ${n} ${n === 1 ? "person" : "people"} here`;
            setHover({ x: px, y: py, title: b.loc.name, sub, accent: def.label });
            return;
          }
        }
        setHover(null);
      });
    });
    renderer.domElement.addEventListener("pointerleave", () => { hoverId = null; setHover(null); });

    // ── Build ground tiles ───────────────────────────────────────────────────
    function buildGround(gw: number, gh: number) {
      groundGroup.clear();
      groundTiles.clear();
      const geo = new THREE.PlaneGeometry(CELL - 0.1, CELL - 0.1);
      for (let gx = 0; gx < gw; gx++) {
        for (let gy = 0; gy < gh; gy++) {
          const col = (gx + gy) % 2 === 0 ? 0x33445c : 0x2c3b52;
          const mat = new THREE.MeshStandardMaterial({ color: col, roughness: 0.9, metalness: 0, emissive: 0x000000, emissiveIntensity: 0 });
          const m = new THREE.Mesh(geo, mat);
          m.rotation.x = -Math.PI / 2;
          const p = gridToWorld(gx, gy, gw, gh);
          m.position.set(p.x, 0.002, p.z);
          m.receiveShadow = true;
          groundGroup.add(m);
          groundTiles.set(`${gx},${gy}`, m);
        }
      }
      groundGroup.add(makeGridLines(gw, gh));
    }

    // ── Build buildings ──────────────────────────────────────────────────────
    function windowMat(def: BuildingDef, w: number, h: number) {
      const t = windowTex.clone();
      t.needsUpdate = true;
      t.repeat.set(Math.max(1, Math.round(w / 0.45)), Math.max(1, Math.round(h / 0.55)));
      return new THREE.MeshStandardMaterial({
        color: def.wall, roughness: 0.78, metalness: 0.05,
        emissive: new THREE.Color(0xffc880), emissiveMap: t, emissiveIntensity: 0.1,
      });
    }

    function buildBuildings(locs: LocationT[], gw: number, gh: number) {
      buildingGroup.clear(); crisisGroup.clear(); labelGroup.clear();
      buildings.clear(); buildingMeshes.length = 0;

      for (const loc of locs) {
        const def = BUILDING_DEF[loc.type] ?? BUILDING_DEF.home;
        const p   = gridToWorld(loc.x, loc.y, gw, gh);
        const bw  = CELL * 0.56;
        const windows: THREE.MeshStandardMaterial[] = [];
        const tag = (m: THREE.Mesh) => { m.userData.buildingId = loc.id; buildingMeshes.push(m); };

        // District pad under every building: tells you what kind of place it is even from far away
        const pad = new THREE.Mesh(
          new THREE.BoxGeometry(CELL * 0.94, 0.06, CELL * 0.94),
          new THREE.MeshStandardMaterial({ color: def.accent, emissive: def.accent, emissiveIntensity: 0.1, roughness: 0.85, transparent: true, opacity: 0.38 }),
        );
        pad.position.set(p.x, 0.03, p.z);
        pad.receiveShadow = true;
        buildingGroup.add(pad);

        // Main body
        const wm = windowMat(def, bw, def.height);
        windows.push(wm);
        const body = new THREE.Mesh(new THREE.BoxGeometry(bw, def.height, bw), wm);
        body.position.set(p.x, def.height / 2 + 0.06, p.z);
        body.castShadow = body.receiveShadow = true;
        tag(body);
        buildingGroup.add(body);

        // Roof cap (emissive accent strip - turns red when the building is closed)
        const roof = new THREE.Mesh(
          new THREE.BoxGeometry(bw + 0.1, 0.07, bw + 0.1),
          new THREE.MeshStandardMaterial({ color: def.accent, emissive: def.accent, emissiveIntensity: 0.7, roughness: 0.4 }),
        );
        roof.position.set(p.x, def.height + 0.1, p.z);
        roof.castShadow = true;
        buildingGroup.add(roof);

        // Per-type silhouette so the map is readable without labels
        const trim = new THREE.MeshStandardMaterial({ color: def.accent, roughness: 0.6, metalness: 0.1 });
        if (loc.type === "home") {
          const pitched = new THREE.Mesh(new THREE.ConeGeometry(bw * 0.78, 0.55, 4), new THREE.MeshStandardMaterial({ color: 0x8a5a4a, roughness: 0.85 }));
          pitched.rotation.y = Math.PI / 4;
          pitched.position.set(p.x, def.height + 0.06 + 0.3, p.z);
          pitched.castShadow = true;
          buildingGroup.add(pitched);
        } else if (loc.type === "workplace") {
          const tower = new THREE.Mesh(new THREE.BoxGeometry(bw * 0.45, 0.6, bw * 0.45), wm);
          tower.position.set(p.x - bw * 0.15, def.height + 0.4, p.z - bw * 0.1);
          tower.castShadow = true;
          buildingGroup.add(tower);
          const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.9, 6), trim);
          mast.position.set(p.x + bw * 0.25, def.height + 0.55, p.z + bw * 0.2);
          buildingGroup.add(mast);
        } else if (loc.type === "commons") {
          const treeMat = new THREE.MeshStandardMaterial({ color: 0x3f9a62, roughness: 0.9 });
          const trunkMat = new THREE.MeshStandardMaterial({ color: 0x6b4a32, roughness: 0.9 });
          const spots: [number, number, number][] = [[-0.5, -0.5, 1], [0.52, -0.45, 0.85], [-0.52, 0.48, 0.9], [0.5, 0.55, 1.05]];
          for (const [dx, dz, s] of spots) {
            const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.05, 0.28 * s, 6), trunkMat);
            trunk.position.set(p.x + dx * CELL * 0.4, 0.2 * s, p.z + dz * CELL * 0.4);
            const crown = new THREE.Mesh(new THREE.ConeGeometry(0.22 * s, 0.55 * s, 8), treeMat);
            crown.position.set(trunk.position.x, 0.58 * s, trunk.position.z);
            crown.castShadow = true;
            buildingGroup.add(trunk, crown);
          }
        } else {
          // institution: stepped tower + spire
          const upper = new THREE.Mesh(new THREE.BoxGeometry(bw * 0.62, 0.9, bw * 0.62), windowMat(def, bw * 0.62, 0.9));
          windows.push(upper.material as THREE.MeshStandardMaterial);
          upper.position.set(p.x, def.height + 0.06 + 0.5, p.z);
          upper.castShadow = true;
          buildingGroup.add(upper);
          const spire = new THREE.Mesh(new THREE.CylinderGeometry(0.01, 0.035, 1.1, 6), trim);
          spire.position.set(p.x, def.height + 0.06 + 0.9 + 0.55, p.z);
          buildingGroup.add(spire);
          const base = new THREE.Mesh(new THREE.BoxGeometry(bw * 1.25, 0.28, bw * 1.25), new THREE.MeshStandardMaterial({ color: 0x4c4688, roughness: 0.8 }));
          base.position.set(p.x, 0.2, p.z);
          base.castShadow = base.receiveShadow = true;
          buildingGroup.add(base);
        }

        // Label chip
        const div = document.createElement("div");
        div.textContent = loc.name;
        div.style.cssText = [
          `color:${def.label}`,
          "font-size:10.5px", "font-weight:600",
          "font-family:Inter,ui-sans-serif,system-ui,sans-serif",
          "letter-spacing:0.04em", "white-space:nowrap", "pointer-events:none",
          "padding:1px 6px", "border-radius:4px",
          "background:rgba(8,12,22,0.62)", `border:1px solid ${def.label}44`,
          "text-shadow:0 1px 2px rgba(0,0,0,0.8)",
        ].join(";");
        const labelObj = new CSS2DObject(div);
        const topY = def.height + (loc.type === "institution" ? 2.5 : 1.0);
        labelObj.position.set(p.x, topY, p.z);
        labelGroup.add(labelObj);

        // Crisis: a red pulsing beam + point light (off until closed)
        const light = new THREE.PointLight(0xff4a4a, 0, CELL * 4);
        light.position.set(p.x, def.height + 1, p.z);
        crisisGroup.add(light);
        const beacon = new THREE.Mesh(
          new THREE.CylinderGeometry(0.16, 0.16, 7, 12, 1, true),
          new THREE.MeshBasicMaterial({ color: 0xff4a4a, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide }),
        );
        beacon.position.set(p.x, def.height + 3.5, p.z);
        beacon.visible = false;
        crisisGroup.add(beacon);

        buildings.set(loc.id, { loc, body, roof, light, beacon, windows, px: p.x, pz: p.z });
      }
    }

    // ── Update buildings (closed state) ──────────────────────────────────────
    function updateBuildings(locs: LocationT[], closed: string[]) {
      for (const loc of locs) {
        const b = buildings.get(loc.id);
        if (!b) continue;
        const def    = BUILDING_DEF[loc.type] ?? BUILDING_DEF.home;
        const isDown = closed.includes(loc.id);
        const rm     = b.roof.material as THREE.MeshStandardMaterial;
        for (const wmat of b.windows) wmat.color.setHex(isDown ? 0x6a3434 : def.wall);
        rm.color.setHex(isDown ? 0xff4a4a : def.accent);
        rm.emissive.setHex(isDown ? 0xff4a4a : def.accent);
        rm.emissiveIntensity = isDown ? 1.1 : 0.7;
        b.beacon.visible = isDown;
      }
    }

    function updateCrisisFx(closed: string[], t: number) {
      for (const [id, b] of buildings) {
        const isDown = closed.includes(id);
        b.light.intensity = isDown ? 6 + 2.4 * Math.sin(t * 3) : 0;
        if (isDown) (b.beacon.material as THREE.MeshBasicMaterial).opacity = 0.22 + 0.12 * Math.sin(t * 3);
      }
    }

    // ── Ground fear heatmap ──────────────────────────────────────────────────
    function updateHeat(citizenData: Citizen[], locs: LocationT[]) {
      const fearMap = new Map<string, number>();
      for (const c of citizenData)
        if ((c.fear ?? 0) > 0.1 && c.location_id)
          fearMap.set(c.location_id, Math.max(fearMap.get(c.location_id) ?? 0, c.fear));
      const locAt = new Map(locs.map(l => [`${l.x},${l.y}`, l]));
      for (const [k, tile] of groundTiles) {
        const loc = locAt.get(k);
        const mat = tile.material as THREE.MeshStandardMaterial;
        if (loc) {
          const f = fearMap.get(loc.id) ?? 0;
          mat.emissive.copy(fearColor(f));
          mat.emissiveIntensity = f * 0.45;
        } else {
          mat.emissiveIntensity = 0;
        }
      }
    }

    // ── Citizen factory ──────────────────────────────────────────────────────
    function getCitizen(c: Citizen): CitizenObj {
      const ex = citizens.get(c.id);
      if (ex) return ex;

      const hue = hashHue(c.id);
      const bodyMat = new THREE.MeshStandardMaterial({ color: new THREE.Color().setHSL(hue, 0.5, 0.62), roughness: 0.6, metalness: 0.05 });
      const headMat = new THREE.MeshStandardMaterial({ color: 0xe9d8c8, roughness: 0.55, metalness: 0.02, emissive: new THREE.Color(0x7cc4f0), emissiveIntensity: 0.18 });
      const shadowMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.3, depthWrite: false });
      const ringMat = new THREE.MeshBasicMaterial({ color: 0x7cc4f0, transparent: true, opacity: 0.85, depthWrite: false, side: THREE.DoubleSide });
      const selMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide });

      const body = new THREE.Mesh(bodyGeo, bodyMat);
      body.castShadow = true; body.userData.citizenId = c.id;
      const head = new THREE.Mesh(headGeo, headMat);
      head.castShadow = true; head.userData.citizenId = c.id;
      const shadow = new THREE.Mesh(shadowGeo, shadowMat);
      shadow.rotation.x = -Math.PI / 2;
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = -Math.PI / 2;
      const selRing = new THREE.Mesh(selGeo, selMat);
      selRing.rotation.x = -Math.PI / 2;
      // generous invisible hit volume: the visible capsule is only a few pixels wide from far away
      const hit = new THREE.Mesh(hitGeo, hitMat);
      hit.userData.citizenId = c.id;

      const nameEl = document.createElement("div");
      nameEl.textContent = c.name.split(" ")[0];
      const baseLabel = [
        "color:rgba(226,236,250,0.92)", "font-size:10px", "font-weight:600",
        "font-family:Inter,ui-sans-serif,system-ui,sans-serif", "letter-spacing:0.03em",
        "white-space:nowrap", "pointer-events:none", "padding:0 5px", "border-radius:3px",
        "background:rgba(8,12,22,0.55)", "text-shadow:0 1px 2px rgba(0,0,0,0.9)",
      ];
      nameEl.style.cssText = baseLabel.join(";");
      const label = new CSS2DObject(nameEl);

      const bubbleEl = document.createElement("div");
      bubbleEl.style.cssText = [
        "background:rgba(10,15,26,0.92)", "color:rgba(228,238,252,0.96)", "font-size:11px",
        "font-family:Inter,ui-sans-serif,system-ui,sans-serif",
        "border:1px solid rgba(124,196,240,0.4)", "border-radius:8px", "padding:5px 9px",
        "max-width:150px", "line-height:1.4", "pointer-events:none",
        "white-space:pre-wrap", "box-shadow:0 4px 14px rgba(0,0,0,0.45)",
      ].join(";");
      const bubble = new CSS2DObject(bubbleEl);

      citizenGroup.add(body, head, shadow, ring, selRing, hit, label, bubble);
      clickable.push(hit);

      const obj: CitizenObj = {
        id: c.id, name: c.name, occupation: c.occupation, action: c.action, fear: c.fear ?? 0,
        body, head, shadow, ring, selRing, hit, speech: "", label, bubble, bubbleEl, nameEl,
        dispX: 0, dispZ: 0, tgtX: 0, tgtZ: 0, moving: 0,
      };
      // spawn at the target on first sight (no slide-in from the origin)
      citizens.set(c.id, obj);
      return obj;
    }

    // Citizens who share a building stand in a row in front of it instead of inside it.
    function slotsFor(cd: Citizen[], gw: number, gh: number) {
      const groups = new Map<string, Citizen[]>();
      for (const c of cd) {
        const k = c.location_id || `${c.x},${c.y}`;
        const g = groups.get(k); if (g) g.push(c); else groups.set(k, [c]);
      }
      const out = new Map<string, { x: number; z: number }>();
      for (const [, g] of groups) {
        g.sort((a, b) => a.id.localeCompare(b.id));
        const p = gridToWorld(g[0].x, g[0].y, gw, gh);
        const perRow = 4;
        g.forEach((c, i) => {
          const row = Math.floor(i / perRow);
          const inRow = Math.min(perRow, g.length - row * perRow);
          const col = i % perRow;
          out.set(c.id, { x: p.x + (col - (inRow - 1) / 2) * 0.72, z: p.z + CELL * 0.5 + 0.18 + row * 0.62 });
        });
      }
      return out;
    }

    function updateCitizen(c: Citizen, slot: { x: number; z: number }, selected: string | null) {
      const first = !citizens.has(c.id);
      const obj = getCitizen(c);
      obj.tgtX = slot.x; obj.tgtZ = slot.z;
      if (first) { obj.dispX = slot.x; obj.dispZ = slot.z; }
      obj.name = c.name; obj.occupation = c.occupation; obj.action = c.action;
      const fear = c.fear ?? 0;
      obj.fear = fear;
      const fc = fearColor(fear);

      const hm = obj.head.material as THREE.MeshStandardMaterial;
      hm.emissive.copy(fc);
      hm.emissiveIntensity = 0.16 + fear * 0.6 + (selected === c.id ? 0.5 : 0);

      (obj.ring.material as THREE.MeshBasicMaterial).color.copy(fc);

      if (c.speech) {
        const raw = c.speech;
        const ci  = raw.indexOf(": ");
        const full = ci !== -1 ? raw.slice(ci + 2) : raw;
        const txt = full.slice(0, 64);
        obj.speech = txt.length < full.length ? txt + "..." : txt;
        obj.bubbleEl.textContent = obj.speech;
      } else {
        obj.speech = "";
      }
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
        computeFit();
        startFly(1.5);
        setReady(true);
      }

      daylight = daylightAt(w.day_progress ?? 0.5);
      updateBuildings(locations, closed_locations ?? []);
      updateHeat(cd, locations);

      if ((active_crises?.length ?? 0) > prevCrises && flashEl)
        flashUntil = performance.now() + 900;
      prevCrises = active_crises?.length ?? 0;

      const sel = useWorld.getState().selectedId;
      const slots = slotsFor(cd, gridW, gridH);
      const seen = new Set<string>();
      for (const c of cd) {
        seen.add(c.id);
        updateCitizen(c, slots.get(c.id)!, sel);
      }
      for (const [id, obj] of citizens) {
        if (!seen.has(id)) {
          citizenGroup.remove(obj.body, obj.head, obj.shadow, obj.ring, obj.selRing, obj.hit, obj.label, obj.bubble);
          const hi = clickable.indexOf(obj.hit); if (hi !== -1) clickable.splice(hi, 1);
          citizens.delete(id);
        }
      }
    }

    const unsub = useWorld.subscribe(sync);
    sync();
    if (!built) {
      // before the first world message: sit at a sensible default so nothing flashes
      computeFit();
      target.set(0, 0.6, 1);
      placeCamera(1.5, 0.2);
    }

    // ── Lighting follows the sim clock (smoothed so phase changes fade, not pop) ──
    const cur = { day: 0.5, warm: 0 };
    const cTop = new THREE.Color(), cBot = new THREE.Color(), tmp = new THREE.Color();
    const NIGHT_TOP = new THREE.Color(0x0a1430), NIGHT_BOT = new THREE.Color(0x1c2c4c);
    const DAY_TOP = new THREE.Color(0x3c6aa8),  DAY_BOT = new THREE.Color(0x9cc0de);
    const WARM = new THREE.Color(0xf0a070);
    const KEY_NIGHT = new THREE.Color(0x8fa8d8), KEY_DAY = new THREE.Color(0xfff2dc);
    const HEMI_SKY_NIGHT = new THREE.Color(0x3a4c78), HEMI_SKY_DAY = new THREE.Color(0xb4cff0);
    const GROUND_NIGHT = new THREE.Color(0x27354a), GROUND_DAY = new THREE.Color(0x4a5c78);

    function applyLighting(dt: number) {
      const k = 1 - Math.exp(-dt * 1.6);
      cur.day  += (daylight.day  - cur.day)  * k;
      cur.warm += (daylight.warm - cur.warm) * k;
      const d = cur.day;
      cTop.lerpColors(NIGHT_TOP, DAY_TOP, d);
      cBot.lerpColors(NIGHT_BOT, DAY_BOT, d);
      cBot.lerp(WARM, cur.warm * 0.55);
      cTop.lerp(tmp.copy(WARM).multiplyScalar(0.5), cur.warm * 0.18);
      (sky.mat.uniforms.top.value as THREE.Color).copy(cTop);
      (sky.mat.uniforms.bottom.value as THREE.Color).copy(cBot);
      fog.color.copy(cBot).multiplyScalar(0.92);
      renderer.setClearColor(cBot, 1);
      stars.mat.opacity = 0.75 * (1 - d);
      key.color.lerpColors(KEY_NIGHT, KEY_DAY, d).lerp(WARM, cur.warm * 0.4);
      key.intensity = 0.9 + d * 1.9;
      key.position.set(16 - d * 6 + cur.warm * 10, 18 + d * 14, 14);
      hemi.color.lerpColors(HEMI_SKY_NIGHT, HEMI_SKY_DAY, d);
      hemi.intensity = 0.75 + d * 0.55;
      baseMat.color.lerpColors(GROUND_NIGHT, GROUND_DAY, d);
      renderer.toneMappingExposure = 1.0 + (1 - d) * 0.08;
      const winGlow = 0.12 + (1 - d) * 1.0;
      for (const [id, b] of buildings) {
        const closed = (useWorld.getState().world?.closed_locations ?? []).includes(id);
        for (const wm of b.windows) wm.emissiveIntensity = closed ? 0.05 : winGlow;
      }
    }

    // ── Animation loop ───────────────────────────────────────────────────────
    const clock = new THREE.Clock();
    let raf = 0;
    const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

    function animate() {
      raf = requestAnimationFrame(animate);
      const dt = Math.min(clock.getDelta(), 0.1);
      const t = clock.elapsedTime;

      // intro / reset fly-in (cancelled the moment the user touches the controls)
      if (flyActive && built) {
        flyT += dt;
        const k = easeOut(clamp01(flyT / 1.8));
        placeCamera(flyFrom + (1 - flyFrom) * k, 0.25 * (1 - k));
        if (k >= 1) { flyActive = false; controls.enabled = true; }
      } else {
        controls.update();
      }
      void userMoved;

      applyLighting(dt);

      // Citizens: frame-rate independent glide, walking bob, rings
      const kMove = 1 - Math.exp(-dt * 5.5);
      const selected = useWorld.getState().selectedId;
      // At most 3 ambient speech bubbles at once; hovering or selecting a citizen always shows theirs.
      const talkers = new Set<string>();
      for (const [id, o] of citizens) { if (o.speech && talkers.size < 3) talkers.add(id); }
      for (const [id, obj] of citizens) {
        const dx = obj.tgtX - obj.dispX, dz = obj.tgtZ - obj.dispZ;
        obj.dispX += dx * kMove;
        obj.dispZ += dz * kMove;
        const speed = Math.hypot(dx, dz);
        obj.moving += ((speed > 0.08 ? 1 : 0) - obj.moving) * (1 - Math.exp(-dt * 8));
        const bob = obj.moving * Math.abs(Math.sin(t * 9 + obj.dispX * 3)) * 0.07 + 0.012 * Math.sin(t * 1.6 + obj.dispX);
        obj.body.position.set(obj.dispX, 0.66 + bob, obj.dispZ);
        obj.head.position.set(obj.dispX, 1.3 + bob, obj.dispZ);
        obj.shadow.position.set(obj.dispX, 0.012, obj.dispZ);
        obj.ring.position.set(obj.dispX, 0.02, obj.dispZ);
        obj.selRing.position.set(obj.dispX, 0.025, obj.dispZ);
        obj.hit.position.set(obj.dispX, 1.05, obj.dispZ);
        obj.label.position.set(obj.dispX, 1.78 + bob, obj.dispZ);
        obj.bubble.position.set(obj.dispX, 2.4 + bob, obj.dispZ);

        const pulse = obj.fear > 0.55 ? 1 + 0.18 * Math.sin(t * 5 + obj.dispX) : 1;
        obj.ring.scale.setScalar((1 + obj.fear * 0.35) * pulse);
        (obj.ring.material as THREE.MeshBasicMaterial).opacity = 0.35 + obj.fear * 0.5;
        (obj.shadow.material as THREE.MeshBasicMaterial).opacity = 0.28;

        const isSel = selected === id;
        const isHov = hoverId === id;
        const sm = obj.selRing.material as THREE.MeshBasicMaterial;
        sm.opacity += ((isSel ? 0.95 : isHov ? 0.55 : 0) - sm.opacity) * (1 - Math.exp(-dt * 12));
        obj.selRing.rotation.z = t * 0.9;
        const s = 1 + 0.06 * Math.sin(t * 3.2);
        obj.selRing.scale.setScalar(isSel ? s : 1);
        obj.bubble.visible = !!obj.speech && (isSel || isHov || talkers.has(id));
        obj.nameEl.style.color = isSel ? "#ffffff" : "rgba(226,236,250,0.92)";
        obj.nameEl.style.background = isSel ? "rgba(110,168,254,0.55)" : "rgba(8,12,22,0.55)";
      }

      const w = useWorld.getState().world;
      if (built && w) updateCrisisFx(w.closed_locations ?? [], t);

      if (flashEl) {
        const now = performance.now();
        flashEl.style.opacity = now < flashUntil ? String(((flashUntil - now) / 900) * 0.2) : "0";
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
      computeFit();
      if (!userMoved && !flyActive) placeCamera(1, 0);
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(el);

    // ── Cleanup ──────────────────────────────────────────────────────────────
    return () => {
      cancelAnimationFrame(raf);
      if (hoverRaf) cancelAnimationFrame(hoverRaf);
      ro.disconnect();
      unsub();
      controls.dispose();
      composer.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode      === el) el.removeChild(renderer.domElement);
      if (labelRenderer.domElement.parentNode === el) el.removeChild(labelRenderer.domElement);
    };
  }, []);

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", position: "relative", cursor: "grab" }}>
      <div ref={flashRef} style={{
        position: "absolute", inset: 0, background: "#c0392b",
        opacity: 0, pointerEvents: "none", zIndex: 5,
      }} />

      {!ready && (
        <div className="stage-loading">
          <div className="spinner" />
          <div>Connecting to the city...</div>
          <div className="muted xsmall">The free server sleeps when idle; the first load can take about 25 seconds.</div>
        </div>
      )}

      {hover && (
        <div className="stage-tip" style={{ left: hover.x + 14, top: hover.y + 14, borderColor: hover.accent }}>
          <div className="stage-tip-title" style={{ color: hover.accent }}>{hover.title}</div>
          <div className="stage-tip-sub">{hover.sub}</div>
        </div>
      )}

      <div className="stage-legend">
        <button className="legend-toggle" onClick={() => setLegendOpen(o => !o)} aria-expanded={legendOpen}>
          {legendOpen ? "Map key  -" : "Map key  +"}
        </button>
        {legendOpen && (
          <div className="legend-body">
            {Object.values(BUILDING_DEF).map(d => (
              <div key={d.kind} className="legend-row">
                <span className="legend-dot" style={{ background: d.label }} />
                <b>{d.kind}</b><span className="muted">{d.blurb}</span>
              </div>
            ))}
            <div className="legend-row">
              <span className="legend-grad" />
              <b>Fear</b><span className="muted">calm to afraid (ring under each person)</span>
            </div>
            <div className="legend-row"><span className="legend-dot legend-red" /><b>Red beam</b><span className="muted">building closed by a crisis</span></div>
            <div className="legend-help">Drag to rotate. Scroll to zoom. Click a person to read their mind.</div>
            <button className="legend-reset" onClick={resetView}>Reset view</button>
          </div>
        )}
      </div>
    </div>
  );
}
