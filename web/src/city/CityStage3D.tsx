import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { SSAOPass } from "three/examples/jsm/postprocessing/SSAOPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { CSS2DRenderer, CSS2DObject } from "three/examples/jsm/renderers/CSS2DRenderer.js";
import { useWorld } from "../ws/store";
import type { LocationT, Citizen } from "../ws/store";

// A daylight model town. Every label is opt-in: the narrator names one thing at a time,
// hover names what is under the pointer, and nothing else is written on the map.

const CELL = 2.4;
// Streets run on cell borders the server's hand-laid map leaves empty (see api/sim/world.py):
// an avenue in front of the council row, two cross streets, and three north-south streets.
const STREET_ROWS = [2.5, 7.5, 12.5];
const STREET_COLS = [4.5, 8.5, 16.5];
const STREET_W = 0.78;

const MOOD_CALM = new THREE.Color(0x3f9a5b), MOOD_WORRIED = new THREE.Color(0xe8b03a), MOOD_AFRAID = new THREE.Color(0xd64535);
const COUNCIL_FLAG: Record<string, number> = {
  inst_gov: 0x2f5d8a, inst_media: 0x7a5aa6, inst_police: 0x1f4e8c, inst_economy: 0x2f7d4f, inst_health: 0xd64535,
};
const KIND_WORDS: Record<LocationT["type"], string> = {
  home: "Home", workplace: "Workplace", commons: "Public space", institution: "Council hall",
};

function moodColor(fear: number) {
  return fear < 0.35 ? MOOD_CALM : fear < 0.6 ? MOOD_WORRIED : MOOD_AFRAID;
}

function hashOf(id: string) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  // Final avalanche: neighbouring ids ("plot:3:4", "plot:3:5") must not get neighbouring values.
  h ^= h >>> 16; h = Math.imul(h, 0x45d9f3b); h ^= h >>> 16; h = Math.imul(h, 0x45d9f3b); h ^= h >>> 16;
  return h >>> 0;
}

function gridToWorld(gx: number, gy: number, gw: number, gh: number) {
  return { x: (gx - (gw - 1) / 2) * CELL, z: (gy - (gh - 1) / 2) * CELL };
}

// ── Materials and facades ────────────────────────────────────────────────────
const matCache = new Map<string, THREE.MeshStandardMaterial>();
function solid(color: number, roughness = 0.85, metalness = 0.02) {
  const key = `${color}:${roughness}:${metalness}`;
  let m = matCache.get(key);
  if (!m) { m = new THREE.MeshStandardMaterial({ color, roughness, metalness }); matCache.set(key, m); }
  return m;
}

type FacadeKind = "office" | "house" | "civic" | "brick";
// Painted canvases give walls windows, mortar and doors without loading any texture files.
function facade(kind: FacadeKind, base: string) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  const paint = canvas.getContext("2d")!;
  paint.fillStyle = base;
  paint.fillRect(0, 0, 128, 128);
  if (kind === "office") {
    for (let y = 6; y < 128; y += 20) for (let x = 6; x < 128; x += 20) {
      paint.fillStyle = (x * 7 + y * 3) % 11 === 0 ? "#d6e6f2" : "#56778f";
      paint.fillRect(x, y, 15, 13);
      paint.fillStyle = "rgba(255,255,255,0.22)";
      paint.fillRect(x, y, 15, 3);
    }
  } else if (kind === "brick") {
    paint.fillStyle = "rgba(0,0,0,0.16)";
    for (let y = 0; y < 128; y += 6) {
      paint.fillRect(0, y, 128, 1);
      for (let x = (y / 6) % 2 ? 0 : 8; x < 128; x += 16) paint.fillRect(x, y, 1, 6);
    }
    for (let row = 0; row < 2; row++) for (let col = 0; col < 3; col++) {
      paint.fillStyle = "#f2ede4"; paint.fillRect(10 + col * 40, 16 + row * 56, 28, 36);
      paint.fillStyle = "#6f8fa8"; paint.fillRect(13 + col * 40, 19 + row * 56, 22, 30);
    }
  } else if (kind === "civic") {
    for (let col = 0; col < 4; col++) {
      paint.fillStyle = "#4f6b82";
      paint.fillRect(10 + col * 30, 22, 16, 34);
      paint.fillRect(10 + col * 30, 78, 16, 34);
    }
  } else {
    paint.fillStyle = "rgba(0,0,0,0.1)";
    for (let y = 0; y < 128; y += 6) paint.fillRect(0, y, 128, 1);
    paint.fillStyle = "#ffffff"; paint.fillRect(16, 34, 30, 30); paint.fillRect(82, 34, 30, 30);
    paint.fillStyle = "#7d9cb4"; paint.fillRect(19, 37, 24, 24); paint.fillRect(85, 37, 24, 24);
    paint.fillStyle = "#5b3a29"; paint.fillRect(54, 76, 20, 52);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  return texture;
}

function shaded<T extends THREE.Mesh>(mesh: T) {
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

// ── Building shapes, one per location type ──────────────────────────────────
function makeHouse(id: string) {
  const g = new THREE.Group();
  const h = hashOf(id);
  const walls = ["#d9c6a5", "#c98d6b", "#e2d6c0", "#cfb79a", "#e6dccb", "#c4876a"][h % 6];
  const roofs = [0x7b4a3a, 0x5e4136, 0x6d4c41, 0x4f5b66][(h >>> 3) % 4];
  const body = shaded(new THREE.Mesh(new THREE.BoxGeometry(1.5, 1.15, 1.35),
    new THREE.MeshStandardMaterial({ map: facade("house", walls), roughness: 0.85 })));
  body.position.y = 0.575;
  g.add(body);
  const gable = new THREE.Shape();
  gable.moveTo(-0.88, 0); gable.lineTo(0, 0.7); gable.lineTo(0.88, 0); gable.lineTo(-0.88, 0);
  const roof = shaded(new THREE.Mesh(new THREE.ExtrudeGeometry(gable, { depth: 1.55, bevelEnabled: false }), solid(roofs, 0.9)));
  roof.position.set(0, 1.15, -0.775);
  g.add(roof);
  const chimney = shaded(new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.45, 0.18), solid(0x8c5a46)));
  chimney.position.set(0.4, 1.6, 0.25);
  g.add(chimney);
  return { group: g, height: 1.9, body };
}

function makeOffice(id: string) {
  const g = new THREE.Group();
  const h = hashOf(id);
  const height = 2.6 + (h % 4) * 0.7;
  const width = 1.5;
  const wall = ["#6f8ba3", "#7d97ad", "#6a879f", "#8099ae"][h % 4];
  const front = facade(id === "clinic" ? "brick" : "office", id === "clinic" ? "#e7e1d6" : wall);
  front.repeat.set(1, Math.max(1, Math.round(height / 1.3)));
  const sideMat = new THREE.MeshStandardMaterial({ map: front, roughness: 0.75 });
  const roofMat = solid(0x8a8f96);
  const body = shaded(new THREE.Mesh(new THREE.BoxGeometry(width, height, width), [sideMat, sideMat, roofMat, roofMat, sideMat, sideMat]));
  body.position.y = height / 2;
  g.add(body);
  const parapet = shaded(new THREE.Mesh(new THREE.BoxGeometry(width + 0.08, 0.12, width + 0.08), solid(0x9a9fa6)));
  parapet.position.y = height + 0.06;
  g.add(parapet);
  const aircon = shaded(new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.28, 0.35), solid(0xb9bec4)));
  aircon.position.set(0.25, height + 0.26, -0.2);
  g.add(aircon);
  if (id === "clinic") {
    const crossMat = new THREE.MeshStandardMaterial({ color: 0xd64535, emissive: 0xd64535, emissiveIntensity: 0.25 });
    for (const [w, hh] of [[0.5, 0.15], [0.15, 0.5]] as const) {
      const arm = new THREE.Mesh(new THREE.BoxGeometry(w, hh, 0.04), crossMat);
      arm.position.set(0, height * 0.72, width / 2 + 0.03);
      g.add(arm);
    }
  }
  return { group: g, height: height + 0.3, body };
}

function makeCouncilHall(id: string) {
  const g = new THREE.Group();
  const width = 1.9, height = 2.2, depth = 1.5;
  const front = facade("civic", "#ece6da");
  const wallMat = new THREE.MeshStandardMaterial({ map: front, roughness: 0.8 });
  const body = shaded(new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), [wallMat, wallMat, solid(0x8a8f96), solid(0x8a8f96), wallMat, wallMat]));
  body.position.y = height / 2 + 0.15;
  g.add(body);
  const podium = shaded(new THREE.Mesh(new THREE.BoxGeometry(width + 0.4, 0.15, depth + 0.5), solid(0xd8d2c6)));
  podium.position.y = 0.075;
  g.add(podium);
  const pediment = new THREE.Shape();
  pediment.moveTo(-width / 2 - 0.1, 0); pediment.lineTo(0, 0.45); pediment.lineTo(width / 2 + 0.1, 0); pediment.lineTo(-width / 2 - 0.1, 0);
  const roof = shaded(new THREE.Mesh(new THREE.ExtrudeGeometry(pediment, { depth: depth + 0.1, bevelEnabled: false }), solid(0xe4ddd0)));
  roof.position.set(0, height + 0.15, -(depth + 0.1) / 2);
  g.add(roof);
  const columnMat = solid(0xf6f2ea, 0.6);
  for (let i = 0; i < 5; i++) {
    const column = shaded(new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.08, height * 0.9, 10), columnMat));
    column.position.set(-width * 0.4 + i * width * 0.2, height * 0.45 + 0.15, depth / 2 + 0.12);
    g.add(column);
  }
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.9, 6), solid(0xcccccc, 0.4, 0.4));
  pole.position.set(width * 0.38, height + 0.85, 0);
  g.add(pole);
  const flag = new THREE.Mesh(new THREE.PlaneGeometry(0.42, 0.26),
    new THREE.MeshStandardMaterial({ color: COUNCIL_FLAG[id] ?? 0x2f5d8a, side: THREE.DoubleSide, roughness: 0.8 }));
  flag.position.set(width * 0.38 + 0.22, height + 1.15, 0);
  g.add(flag);
  g.userData.flag = flag;
  return { group: g, height: height + 1.4, body };
}

const leafDark = solid(0x4f7d3a), leafLight = solid(0x5f8f45), bark = solid(0x6b4f35);
leafDark.flatShading = leafLight.flatShading = true;
function makeTree(size: number, seed: number) {
  const g = new THREE.Group();
  const trunk = shaded(new THREE.Mesh(new THREE.CylinderGeometry(0.05 * size, 0.08 * size, 0.6 * size, 6), bark));
  trunk.position.y = 0.3 * size;
  const crown = shaded(new THREE.Mesh(new THREE.IcosahedronGeometry(0.5 * size, 1), seed % 2 ? leafDark : leafLight));
  crown.position.y = 0.9 * size;
  const top = shaded(new THREE.Mesh(new THREE.IcosahedronGeometry(0.33 * size, 1), seed % 2 ? leafLight : leafDark));
  top.position.set(0.18 * size, 1.25 * size, -0.12 * size);
  g.add(trunk, crown, top);
  return g;
}

function makeCommons(id: string) {
  const g = new THREE.Group();
  const lawn = shaded(new THREE.Mesh(new THREE.BoxGeometry(CELL * 0.92, 0.06, CELL * 0.92), solid(id === "park" ? 0x6f9a4c : 0xddd5c6, 0.95)));
  lawn.position.y = 0.03;
  g.add(lawn);
  if (id === "park") {
    [[-0.6, -0.55, 1.1], [0.55, -0.45, 0.9], [-0.5, 0.55, 1], [0.6, 0.6, 1.2]].forEach(([x, z, s], i) => {
      const tree = makeTree(s, i); tree.position.set(x, 0.06, z); g.add(tree);
    });
  } else if (id === "plaza") {
    const basin = shaded(new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.68, 0.22, 28), solid(0xd8d2c6)));
    basin.position.y = 0.17;
    const water = new THREE.Mesh(new THREE.CircleGeometry(0.55, 28), solid(0x6fa4c8, 0.15, 0.25));
    water.rotation.x = -Math.PI / 2; water.position.y = 0.285;
    g.add(basin, water);
  } else if (id === "market") {
    [0xc0503f, 0xe0b04a, 0x3d7a8a].forEach((color, i) => {
      const stall = shaded(new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.45, 0.45), solid(0xb89a74)));
      stall.position.set(-0.65 + i * 0.65, 0.29, 0);
      const awning = shaded(new THREE.Mesh(new THREE.BoxGeometry(0.65, 0.05, 0.6), solid(color)));
      awning.position.set(-0.65 + i * 0.65, 0.6, 0.06);
      awning.rotation.x = 0.18;
      g.add(stall, awning);
    });
  } else {
    const cafe = shaded(new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.95, 0.9), new THREE.MeshStandardMaterial({ map: facade("brick", "#c98d6b"), roughness: 0.85 })));
    cafe.position.set(0, 0.53, -0.35);
    const awning = shaded(new THREE.Mesh(new THREE.BoxGeometry(1.25, 0.05, 0.45), solid(0x2f6b4f)));
    awning.position.set(0, 0.85, 0.2); awning.rotation.x = 0.25;
    g.add(cafe, awning);
    [-0.4, 0.4].forEach((x) => {
      const table = shaded(new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.04, 14), solid(0xf2f2f2)));
      table.position.set(x, 0.4, 0.65);
      g.add(table);
    });
  }
  return { group: g, height: 1.6, body: lawn };
}

// ── People ──────────────────────────────────────────────────────────────────
const SKIN = [0xe2b48c, 0xc68e64, 0x8d5a3b, 0xf0c9a6];
const SHIRT = [0x3d6fa8, 0xc76b4a, 0x5b8a5e, 0xe0b04a, 0x7b5ea7, 0x4a8fa8, 0xa84a6b, 0x8a8a8a, 0x2f4f6f, 0xb07a3a];

function limb(length: number, radius: number, material: THREE.Material, pivotY: number, x: number) {
  const pivot = new THREE.Group();
  pivot.position.set(x, pivotY, 0);
  const part = shaded(new THREE.Mesh(new THREE.CapsuleGeometry(radius, length, 4, 8), material));
  part.position.y = -length / 2 - radius;
  pivot.add(part);
  return pivot;
}

type Person = {
  id: string; name: string; occupation: string; action: string; fear: number; speech: string;
  root: THREE.Group; legL: THREE.Group; legR: THREE.Group; armL: THREE.Group; armR: THREE.Group;
  moodRing: THREE.Mesh; selRing: THREE.Mesh; hit: THREE.Mesh;
  nameTag: CSS2DObject; nameEl: HTMLDivElement; bubble: CSS2DObject; bubbleEl: HTMLDivElement;
  dispX: number; dispZ: number; tgtX: number; tgtZ: number; moving: number; heading: number;
};

const hitGeo = new THREE.CylinderGeometry(0.4, 0.4, 1.3, 8);
const hitMat = new THREE.MeshBasicMaterial({ visible: false });

function makePerson(c: Citizen): Person {
  const h = hashOf(c.id);
  const shirt = solid(SHIRT[h % SHIRT.length], 0.7);
  const trousers = solid(0x2d3440, 0.8);
  const root = new THREE.Group();
  const legL = limb(0.2, 0.045, trousers, 0.33, -0.055), legR = limb(0.2, 0.045, trousers, 0.33, 0.055);
  const armL = limb(0.17, 0.034, shirt, 0.64, -0.14), armR = limb(0.17, 0.034, shirt, 0.64, 0.14);
  const torso = shaded(new THREE.Mesh(new THREE.CapsuleGeometry(0.1, 0.2, 4, 10), shirt));
  torso.position.y = 0.5;
  const head = shaded(new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 12), solid(SKIN[(h >>> 4) % SKIN.length], 0.75)));
  head.position.y = 0.76;
  const hair = shaded(new THREE.Mesh(new THREE.SphereGeometry(0.094, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2.2), solid((h >>> 2) % 3 ? 0x2a1d14 : 0x6b4a2b)));
  hair.position.y = 0.775;
  const moodRing = new THREE.Mesh(new THREE.RingGeometry(0.18, 0.25, 28),
    new THREE.MeshBasicMaterial({ color: MOOD_CALM, transparent: true, opacity: 0.9, depthWrite: false }));
  moodRing.rotation.x = -Math.PI / 2; moodRing.position.y = 0.02;
  const selRing = new THREE.Mesh(new THREE.RingGeometry(0.3, 0.36, 32),
    new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthWrite: false }));
  selRing.rotation.x = -Math.PI / 2; selRing.position.y = 0.025;
  const hit = new THREE.Mesh(hitGeo, hitMat);
  hit.position.y = 0.6;
  hit.userData.citizenId = c.id;
  root.add(legL, legR, armL, armR, torso, head, hair, moodRing, selRing, hit);

  const nameEl = document.createElement("div");
  nameEl.className = "map-tag";
  const nameTag = new CSS2DObject(nameEl);
  nameTag.position.y = 1.15;
  nameTag.visible = false;
  const bubbleEl = document.createElement("div");
  bubbleEl.className = "map-bubble";
  const bubble = new CSS2DObject(bubbleEl);
  bubble.position.y = 1.6;
  bubble.visible = false;
  root.add(nameTag, bubble);
  // Slightly larger than true scale so a person is still visible from the overview camera.
  root.scale.setScalar(1.5);
  nameTag.position.y = 1.15 / 1.5 + 0.2;
  bubble.position.y = 1.6 / 1.5 + 0.2;

  return {
    id: c.id, name: c.name, occupation: c.occupation, action: c.action, fear: c.fear ?? 0, speech: "",
    root, legL, legR, armL, armR, moodRing, selRing, hit, nameTag, nameEl, bubble, bubbleEl,
    dispX: 0, dispZ: 0, tgtX: 0, tgtZ: 0, moving: 0, heading: 0,
  };
}

// People who share a place stand in a ring around it, front first, instead of inside it.
function standingSpots(citizensNow: Citizen[], gw: number, gh: number) {
  const groups = new Map<string, Citizen[]>();
  for (const c of citizensNow) {
    const key = c.location_id || `${c.x},${c.y}`;
    const group = groups.get(key);
    if (group) group.push(c); else groups.set(key, [c]);
  }
  const spots = new Map<string, { x: number; z: number }>();
  for (const [, group] of groups) {
    group.sort((a, b) => a.id.localeCompare(b.id));
    const centre = gridToWorld(group[0].x, group[0].y, gw, gh);
    group.forEach((c, i) => {
      const angle = Math.PI / 2 + (i - (group.length - 1) / 2) * 0.5;
      spots.set(c.id, { x: centre.x + Math.cos(angle) * 1.0, z: centre.z + Math.sin(angle) * 1.0 });
    });
  }
  return spots;
}

// ── Component ────────────────────────────────────────────────────────────────
type Hover = { x: number; y: number; title: string; sub: string } | null;

export default function CityStage3D() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<Hover>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.95;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.domElement.style.cssText = "position:absolute;inset:0;width:100%;height:100%;touch-action:none";
    renderer.setSize(el.offsetWidth || 800, el.offsetHeight || 600);
    el.appendChild(renderer.domElement);

    const labelRenderer = new CSS2DRenderer();
    labelRenderer.setSize(el.offsetWidth || 800, el.offsetHeight || 600);
    labelRenderer.domElement.style.cssText = "position:absolute;inset:0;pointer-events:none";
    el.appendChild(labelRenderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0xd6e4ee, 70, 140);
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = 0.35;

    const skyMat = new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: { horizon: { value: new THREE.Color(0xdbe7f2) }, zenith: { value: new THREE.Color(0x6b9ed9) } },
      vertexShader: "varying float vY; void main(){ vY = normalize(position).y; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }",
      fragmentShader: "uniform vec3 horizon; uniform vec3 zenith; varying float vY; void main(){ float t = clamp(vY*1.6,0.0,1.0); gl_FragColor = vec4(mix(horizon, zenith, t), 1.0); }",
    });
    scene.add(new THREE.Mesh(new THREE.SphereGeometry(180, 32, 16), skyMat));

    const hemi = new THREE.HemisphereLight(0xe4efff, 0x6f7f5a, 1.0);
    scene.add(hemi);
    const sun = new THREE.DirectionalLight(0xfff1dc, 2.6);
    sun.position.set(22, 34, 16);
    sun.castShadow = true;
    sun.shadow.mapSize.set(4096, 4096);
    Object.assign(sun.shadow.camera, { left: -36, right: 36, top: 26, bottom: -26, near: 1, far: 110 });
    sun.shadow.bias = -0.0003;
    sun.shadow.normalBias = 0.02;
    scene.add(sun);

    const camera = new THREE.PerspectiveCamera(36, (el.offsetWidth || 800) / (el.offsetHeight || 600), 0.1, 500);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minPolarAngle = 0.25;
    controls.maxPolarAngle = Math.PI / 2.3;
    controls.minDistance = 6;
    controls.maxDistance = 110;

    const composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    const ssao = new SSAOPass(scene, camera, el.offsetWidth || 800, el.offsetHeight || 600);
    ssao.kernelRadius = 0.6;
    ssao.minDistance = 0.0008;
    ssao.maxDistance = 0.04;
    composer.addPass(ssao);
    composer.addPass(new OutputPass());

    const groundGroup = new THREE.Group(), buildingGroup = new THREE.Group(), peopleGroup = new THREE.Group(), trafficGroup = new THREE.Group();
    scene.add(groundGroup, buildingGroup, peopleGroup, trafficGroup);

    type Place = { loc: LocationT; x: number; z: number; height: number; body: THREE.Mesh; cordon: THREE.Mesh; flag?: THREE.Object3D };
    const places = new Map<string, Place>();
    const people = new Map<string, Person>();
    const hitTargets: THREE.Object3D[] = [];
    const buildingTargets: THREE.Object3D[] = [];
    const cars: { model: THREE.Group; along: "x" | "z"; dir: number; speed: number; min: number; max: number }[] = [];
    let gridW = 24, gridH = 16, built = false;
    let hoverId: string | null = null;

    // Focus label: the narrator names one place or person at a time.
    const focusEl = document.createElement("div");
    focusEl.className = "map-tag map-tag-focus";
    const focusTag = new CSS2DObject(focusEl);
    focusTag.visible = false;
    scene.add(focusTag);

    // ── Ground: grass, sidewalks, asphalt, lane marks, crosswalks ────────────
    function buildGround(gw: number, gh: number) {
      groundGroup.clear();
      const span = { w: gw * CELL, d: gh * CELL };
      const grass = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), solid(0x7ea25a, 1));
      grass.rotation.x = -Math.PI / 2;
      grass.receiveShadow = true;
      groundGroup.add(grass);

      const toX = (gx: number) => (gx - (gw - 1) / 2) * CELL;
      const toZ = (gy: number) => (gy - (gh - 1) / 2) * CELL;
      const asphalt = solid(0x4c4f54, 0.95), kerb = solid(0xc9c5bc, 0.95);
      const lanePaint = new THREE.MeshBasicMaterial({ color: 0xf1f1ec });
      const zMin = toZ(2.5), zMax = toZ(gh - 0.5);

      // Council square: one stone plaza in front of all five halls.
      const square = shaded(new THREE.Mesh(new THREE.BoxGeometry(span.w * 0.82, 0.05, CELL * 1.7), solid(0xddd5c6, 0.9)));
      square.position.set(toX((gw - 1) / 2) + CELL * 0.5, 0.025, toZ(1.15));
      groundGroup.add(square);

      const street = (cx: number, cz: number, w: number, d: number, horizontal: boolean) => {
        const pavement = shaded(new THREE.Mesh(new THREE.BoxGeometry(w + (horizontal ? 0 : 0.5), 0.08, d + (horizontal ? 0.5 : 0)), kerb));
        pavement.position.set(cx, 0.04, cz);
        const surface = new THREE.Mesh(new THREE.PlaneGeometry(w, d), asphalt);
        surface.rotation.x = -Math.PI / 2;
        surface.position.set(cx, 0.085, cz);
        surface.receiveShadow = true;
        groundGroup.add(pavement, surface);
        const length = horizontal ? w : d;
        for (let t = -length / 2 + 0.6; t < length / 2 - 0.4; t += 1.1) {
          const dash = new THREE.Mesh(new THREE.PlaneGeometry(horizontal ? 0.5 : 0.05, horizontal ? 0.05 : 0.5), lanePaint);
          dash.rotation.x = -Math.PI / 2;
          dash.position.set(horizontal ? cx + t : cx, 0.09, horizontal ? cz : cz + t);
          groundGroup.add(dash);
        }
      };
      for (const row of STREET_ROWS) street(0, toZ(row), span.w, STREET_W, true);
      for (const col of STREET_COLS) street(toX(col), (zMin + zMax) / 2, STREET_W, zMax - zMin, false);
      for (const row of STREET_ROWS) for (const col of STREET_COLS) {
        for (let i = -2; i <= 2; i++) {
          const stripe = new THREE.Mesh(new THREE.PlaneGeometry(0.12, 0.5), lanePaint);
          stripe.rotation.x = -Math.PI / 2;
          stripe.position.set(toX(col) + i * 0.16, 0.091, toZ(row) + STREET_W / 2 + 0.45);
          groundGroup.add(stripe);
        }
      }

      // Street lamps along the council avenue.
      const lampMetal = solid(0x3a3f45, 0.5, 0.4);
      const lampGlass = new THREE.MeshStandardMaterial({ color: 0xfff4d6, emissive: 0xfff0c8, emissiveIntensity: 0.35 });
      for (let x = -span.w / 2 + 2; x < span.w / 2; x += 4.8) {
        const post = shaded(new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.035, 1.3, 8), lampMetal));
        post.position.set(x, 0.73, toZ(2.5) - STREET_W / 2 - 0.15);
        const lamp = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.05, 0.1), lampGlass);
        lamp.position.set(x, 1.38, post.position.z);
        groundGroup.add(post, lamp);
      }
    }

    // Street trees: planted in rows along the kerbs, the way a town plants them, never at random.
    function plantTrees(locs: LocationT[], gw: number, gh: number) {
      const taken = new Set(locs.map((l) => `${l.x},${l.y}`));
      const kerb = STREET_W / 2 + 0.55;
      for (const row of STREET_ROWS) {
        for (let gx = 0; gx < gw; gx += 2) {
          if (taken.has(`${gx},${Math.floor(row)}`) || taken.has(`${gx},${Math.ceil(row)}`)) continue;
          if (STREET_COLS.some((col) => Math.abs(gx - col) < 1)) continue;
          const p = gridToWorld(gx, row, gw, gh);
          const h = hashOf(`${gx}:${row}`);
          const tree = makeTree(0.85 + (h % 4) * 0.08, h);
          tree.position.set(p.x, 0, p.z + (row === STREET_ROWS[0] ? kerb : -kerb));
          groundGroup.add(tree);
        }
      }
    }

    function buildTraffic(gw: number, gh: number) {
      trafficGroup.clear();
      cars.length = 0;
      const half = (gw * CELL) / 2;
      const colors = [0xc0392b, 0xf2f2f2, 0x2c5e8f, 0x9aa3ad];
      STREET_ROWS.forEach((row, i) => {
        const model = new THREE.Group();
        const body = shaded(new THREE.Mesh(new THREE.BoxGeometry(0.85, 0.24, 0.42), solid(colors[i % colors.length], 0.35, 0.2)));
        body.position.y = 0.24;
        const cabin = shaded(new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.2, 0.38), solid(0x2b3440, 0.2)));
        cabin.position.set(-0.04, 0.45, 0);
        model.add(body, cabin);
        const dir = i % 2 ? -1 : 1;
        const z = gridToWorld(0, row, gw, gh).z + dir * 0.17;
        model.position.set(-half + i * 9, 0.09, z);
        if (dir < 0) model.rotation.y = Math.PI;
        trafficGroup.add(model);
        cars.push({ model, along: "x", dir, speed: 2 + i * 0.4, min: -half, max: half });
      });
    }

    // Background neighbours on empty plots, matched to each district, so the town is not a
    // lawn with a few buildings. They carry no buildingId: hover and the narrator ignore them.
    function fillEmptyPlots(locs: LocationT[], gw: number, gh: number) {
      const taken = new Set(locs.map((l) => `${l.x},${l.y}`));
      for (let gx = 0; gx < gw; gx++) for (let gy = 3; gy < gh - 1; gy++) {
        if (taken.has(`${gx},${gy}`)) continue;
        const h = hashOf(`plot:${gx}:${gy}`);
        const residential = gx <= 6, downtown = gx >= 18, shops = gx >= 9 && gx <= 15;
        const chance = residential ? 50 : downtown ? 30 : shops ? 18 : 10;
        if (h % 100 >= chance) continue;
        const made = downtown ? makeOffice(`filler-${gx}-${gy}`) : makeHouse(`filler-${gx}-${gy}`);
        const p = gridToWorld(gx, gy, gw, gh);
        made.group.position.set(p.x, 0, p.z);
        made.group.rotation.y = ((h >>> 6) % 4) * (Math.PI / 2);
        made.group.scale.setScalar(downtown ? 0.85 : 0.9);
        groundGroup.add(made.group);
      }
    }

    function buildPlaces(locs: LocationT[], gw: number, gh: number) {
      buildingGroup.clear();
      places.clear();
      buildingTargets.length = 0;
      for (const loc of locs) {
        const p = gridToWorld(loc.x, loc.y, gw, gh);
        const made = loc.type === "home" ? makeHouse(loc.id)
          : loc.type === "workplace" ? makeOffice(loc.id)
          : loc.type === "institution" ? makeCouncilHall(loc.id)
          : makeCommons(loc.id);
        made.group.position.set(p.x, 0, p.z);
        made.group.traverse((o) => { if ((o as THREE.Mesh).isMesh) { o.userData.buildingId = loc.id; buildingTargets.push(o); } });
        buildingGroup.add(made.group);
        // A red cordon around a building that a crisis has closed; hidden until then.
        const cordon = new THREE.Mesh(new THREE.TorusGeometry(1.25, 0.04, 6, 48), new THREE.MeshBasicMaterial({ color: 0xd64535 }));
        cordon.rotation.x = -Math.PI / 2;
        cordon.position.set(p.x, 0.35, p.z);
        cordon.visible = false;
        buildingGroup.add(cordon);
        places.set(loc.id, { loc, x: p.x, z: p.z, height: made.height, body: made.body, cordon, flag: made.group.userData.flag });
      }
    }

    // ── Camera: an overview, and a glide to whatever the narrator names ─────
    const overviewTarget = new THREE.Vector3(0, 0, -2);
    const overviewDir = new THREE.Vector3(0.32, 0.72, 0.62).normalize();
    let overviewDist = 62;
    const camGoal = { target: overviewTarget.clone(), dist: overviewDist };
    let userHeldUntil = 0;
    controls.addEventListener("start", () => { userHeldUntil = performance.now() + 15000; });

    function fitOverview() {
      const tanV = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
      const needW = (gridW * CELL * 0.44) / (tanV * camera.aspect);
      const needD = (gridH * CELL * 0.34 + 3) / tanV;
      overviewDist = Math.max(needW, needD);
    }

    function focusPoint() {
      const f = useWorld.getState().focus;
      if (!f) return null;
      if (f.kind === "location") {
        const place = places.get(f.id);
        return place ? { point: new THREE.Vector3(place.x, 0.6, place.z), dist: 22, label: place.loc.name, top: place.height + 0.4 } : null;
      }
      const person = people.get(f.id);
      return person ? { point: new THREE.Vector3(person.dispX, 0.5, person.dispZ), dist: 14, label: person.name.split(" ")[0], top: 1.25 } : null;
    }

    camera.position.copy(overviewTarget).addScaledVector(overviewDir, overviewDist * 1.3);
    controls.target.copy(overviewTarget);

    // ── Pointer: hover names a thing, click selects a person ────────────────
    const raycaster = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    function pick(e: PointerEvent) {
      const rect = renderer.domElement.getBoundingClientRect();
      ndc.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
      raycaster.setFromCamera(ndc, camera);
      return { hits: raycaster.intersectObjects([...hitTargets, ...buildingTargets], false), rect };
    }
    let downX = 0, downY = 0;
    const onDown = (e: PointerEvent) => { downX = e.clientX; downY = e.clientY; };
    const onUp = (e: PointerEvent) => {
      if (Math.hypot(e.clientX - downX, e.clientY - downY) > 5) return;
      const hit = pick(e).hits.find((h) => h.object.userData.citizenId);
      if (hit) useWorld.getState().select(hit.object.userData.citizenId as string);
    };
    let hoverRaf = 0;
    const onMove = (e: PointerEvent) => {
      if (e.buttons || hoverRaf) return;
      hoverRaf = requestAnimationFrame(() => {
        hoverRaf = 0;
        const { hits, rect } = pick(e);
        const first = hits[0];
        const cid = first?.object.userData.citizenId as string | undefined;
        const bid = first?.object.userData.buildingId as string | undefined;
        hoverId = cid ?? null;
        renderer.domElement.style.cursor = cid ? "pointer" : "grab";
        const x = e.clientX - rect.left, y = e.clientY - rect.top;
        const person = cid ? people.get(cid) : undefined;
        if (person) {
          const mood = person.fear < 0.35 ? "calm" : person.fear < 0.6 ? "worried" : "afraid";
          setHover({ x, y, title: person.name, sub: `${person.occupation}, ${mood}. Click to read their mind.` });
          return;
        }
        const place = bid ? places.get(bid) : undefined;
        if (place) {
          const closed = useWorld.getState().world?.closed_locations?.includes(place.loc.id);
          setHover({ x, y, title: place.loc.name, sub: closed ? "Closed by a crisis" : KIND_WORDS[place.loc.type] });
          return;
        }
        setHover(null);
      });
    };
    const onLeave = () => { hoverId = null; setHover(null); };
    renderer.domElement.addEventListener("pointerdown", onDown);
    renderer.domElement.addEventListener("pointerup", onUp);
    renderer.domElement.addEventListener("pointermove", onMove);
    renderer.domElement.addEventListener("pointerleave", onLeave);

    // ── Light follows the sim clock, softly: night is a blue dusk, never too dark to read ──
    const LIGHT = {
      day:   { sun: new THREE.Color(0xfff1dc), sunI: 2.6, hemiI: 1.0, horizon: new THREE.Color(0xdbe7f2), zenith: new THREE.Color(0x6b9ed9), exposure: 0.95 },
      warm:  { sun: new THREE.Color(0xffb27a), sunI: 2.0, hemiI: 0.9, horizon: new THREE.Color(0xf3c9a4), zenith: new THREE.Color(0x7a8fc4), exposure: 0.95 },
      night: { sun: new THREE.Color(0x9fb4e0), sunI: 0.9, hemiI: 0.65, horizon: new THREE.Color(0x5d6f96), zenith: new THREE.Color(0x1f2d55), exposure: 0.85 },
    };
    const lightNow = { day: 1, warm: 0 };
    function lightGoal() {
      const progress = useWorld.getState().world?.day_progress ?? 0.5;
      const hour = (((progress % 1) + 1) % 1) * 24;
      const ramp = (a: number, b: number, v: number) => Math.min(1, Math.max(0, (v - a) / (b - a)));
      const day = ramp(5.5, 8, hour) * (1 - ramp(18, 20.5, hour));
      const warm = Math.max(0, 1 - Math.abs(hour - 7) / 1.5) + Math.max(0, 1 - Math.abs(hour - 18.8) / 1.5);
      return { day, warm: Math.min(1, warm) };
    }
    function applyLight(dt: number) {
      const goal = lightGoal();
      const k = 1 - Math.exp(-dt * 0.8);
      lightNow.day += (goal.day - lightNow.day) * k;
      lightNow.warm += (goal.warm - lightNow.warm) * k;
      const { day, warm } = lightNow;
      const mix = (a: number, b: number) => a + (b - a) * day;
      sun.color.copy(LIGHT.night.sun).lerp(LIGHT.day.sun, day).lerp(LIGHT.warm.sun, warm * 0.6);
      sun.intensity = mix(LIGHT.night.sunI, LIGHT.day.sunI) * (1 - warm * 0.2);
      hemi.intensity = mix(LIGHT.night.hemiI, LIGHT.day.hemiI);
      (skyMat.uniforms.horizon.value as THREE.Color).copy(LIGHT.night.horizon).lerp(LIGHT.day.horizon, day).lerp(LIGHT.warm.horizon, warm * 0.7);
      (skyMat.uniforms.zenith.value as THREE.Color).copy(LIGHT.night.zenith).lerp(LIGHT.day.zenith, day).lerp(LIGHT.warm.zenith, warm * 0.4);
      (scene.fog as THREE.Fog).color.copy(skyMat.uniforms.horizon.value as THREE.Color);
      renderer.toneMappingExposure = mix(LIGHT.night.exposure, LIGHT.day.exposure);
    }

    // ── Store sync ───────────────────────────────────────────────────────────
    function sync() {
      const w = useWorld.getState().world;
      if (!w) return;
      if (!built) {
        gridW = w.grid.w; gridH = w.grid.h;
        buildGround(gridW, gridH);
        buildPlaces(w.locations, gridW, gridH);
        plantTrees(w.locations, gridW, gridH);
        fillEmptyPlots(w.locations, gridW, gridH);
        buildTraffic(gridW, gridH);
        fitOverview();
        Object.assign(lightNow, lightGoal());
        built = true;
        setReady(true);
      }
      const closed = new Set(w.closed_locations ?? []);
      for (const [id, place] of places) place.cordon.visible = closed.has(id);

      const spots = standingSpots(w.citizens, gridW, gridH);
      const seen = new Set<string>();
      for (const c of w.citizens) {
        seen.add(c.id);
        let person = people.get(c.id);
        const spot = spots.get(c.id)!;
        if (!person) {
          person = makePerson(c);
          person.dispX = person.tgtX = spot.x;
          person.dispZ = person.tgtZ = spot.z;
          people.set(c.id, person);
          peopleGroup.add(person.root);
          hitTargets.push(person.hit);
        }
        person.tgtX = spot.x; person.tgtZ = spot.z;
        person.name = c.name; person.occupation = c.occupation; person.action = c.action;
        person.fear = c.fear ?? 0;
        (person.moodRing.material as THREE.MeshBasicMaterial).color.copy(moodColor(person.fear));
        const speakerEnd = c.speech ? c.speech.indexOf(": ") : -1;
        const said = c.speech ? (speakerEnd === -1 ? c.speech : c.speech.slice(speakerEnd + 2)) : "";
        person.speech = said.length > 70 ? said.slice(0, 70) + "..." : said;
        person.bubbleEl.textContent = person.speech;
        person.nameEl.textContent = c.name.split(" ")[0];
      }
      for (const [id, person] of people) {
        if (seen.has(id)) continue;
        peopleGroup.remove(person.root);
        const at = hitTargets.indexOf(person.hit);
        if (at !== -1) hitTargets.splice(at, 1);
        people.delete(id);
      }
    }
    const unsub = useWorld.subscribe(sync);
    sync();

    // ── Animation ────────────────────────────────────────────────────────────
    const clock = new THREE.Clock();
    let raf = 0;
    const lookTarget = controls.target;
    function animate() {
      raf = requestAnimationFrame(animate);
      const dt = Math.min(clock.getDelta(), 0.1);
      const t = clock.elapsedTime;

      applyLight(dt);
      const focus = built ? focusPoint() : null;
      if (performance.now() > userHeldUntil) {
        camGoal.target.copy(focus ? focus.point : overviewTarget);
        camGoal.dist = focus ? focus.dist : overviewDist;
        const k = 1 - Math.exp(-dt * 1.4);
        lookTarget.lerp(camGoal.target, k);
        const offset = camera.position.clone().sub(lookTarget);
        const dist = offset.length() + (camGoal.dist - offset.length()) * k;
        const dir = offset.normalize().lerp(overviewDir, k * 0.6).normalize();
        camera.position.copy(lookTarget).addScaledVector(dir, dist);
      }
      controls.update();

      focusTag.visible = !!focus;
      if (focus) {
        focusEl.textContent = focus.label;
        focusTag.position.set(focus.point.x, focus.top, focus.point.z);
      }

      const selected = useWorld.getState().selectedId;
      const kMove = 1 - Math.exp(-dt * 3.5);
      for (const [id, person] of people) {
        const dx = person.tgtX - person.dispX, dz = person.tgtZ - person.dispZ;
        person.dispX += dx * kMove;
        person.dispZ += dz * kMove;
        const speed = Math.hypot(dx, dz);
        person.moving += ((speed > 0.05 ? 1 : 0) - person.moving) * (1 - Math.exp(-dt * 6));
        if (speed > 0.05) person.heading = Math.atan2(dx, dz);
        person.root.rotation.y += (((person.heading - person.root.rotation.y + Math.PI * 3) % (Math.PI * 2)) - Math.PI) * (1 - Math.exp(-dt * 8));
        const stride = Math.sin(t * 8 + hashOf(id) % 7) * person.moving;
        person.legL.rotation.x = stride * 0.55; person.legR.rotation.x = -stride * 0.55;
        person.armL.rotation.x = -stride * 0.45; person.armR.rotation.x = stride * 0.45;
        person.root.position.set(person.dispX, 0.09 + Math.abs(stride) * 0.02, person.dispZ);

        const isSel = selected === id, isHov = hoverId === id;
        const ringMat = person.selRing.material as THREE.MeshBasicMaterial;
        ringMat.opacity += ((isSel ? 0.95 : isHov ? 0.5 : 0) - ringMat.opacity) * (1 - Math.exp(-dt * 12));
        person.nameTag.visible = isSel;
        person.bubble.visible = !!person.speech && (isSel || isHov);
      }

      for (const car of cars) {
        car.model.position.x += car.dir * car.speed * dt;
        if (car.model.position.x > car.max) car.model.position.x = car.min;
        if (car.model.position.x < car.min) car.model.position.x = car.max;
      }
      let flagIndex = 0;
      for (const [, place] of places) {
        if (place.flag) place.flag.rotation.y = Math.sin(t * 2.6 + flagIndex++) * 0.25;
        if (place.cordon.visible) place.cordon.scale.setScalar(1 + Math.sin(t * 2.4) * 0.04);
      }

      composer.render();
      labelRenderer.render(scene, camera);
    }
    animate();

    const onResize = () => {
      const w = el.offsetWidth, h = el.offsetHeight;
      if (!w || !h) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
      composer.setSize(w, h);
      ssao.setSize(w, h);
      labelRenderer.setSize(w, h);
      fitOverview();
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(el);

    return () => {
      cancelAnimationFrame(raf);
      if (hoverRaf) cancelAnimationFrame(hoverRaf);
      ro.disconnect();
      unsub();
      renderer.domElement.removeEventListener("pointerdown", onDown);
      renderer.domElement.removeEventListener("pointerup", onUp);
      renderer.domElement.removeEventListener("pointermove", onMove);
      renderer.domElement.removeEventListener("pointerleave", onLeave);
      controls.dispose();
      composer.dispose();
      pmrem.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === el) el.removeChild(renderer.domElement);
      if (labelRenderer.domElement.parentNode === el) el.removeChild(labelRenderer.domElement);
    };
  }, []);

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", position: "relative", cursor: "grab" }}>
      {!ready && (
        <div className="stage-loading">
          <div className="spinner" />
          <div>Waking up the city...</div>
          <div className="muted xsmall">The free server sleeps when idle; the first load can take about 25 seconds.</div>
        </div>
      )}
      {hover && (
        <div className="stage-tip" style={{ left: hover.x + 14, top: hover.y + 14 }}>
          <div className="stage-tip-title">{hover.title}</div>
          <div className="stage-tip-sub">{hover.sub}</div>
        </div>
      )}
    </div>
  );
}
