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

// ── Constants ──────────────────────────────────────────────────────────────
const CELL = 2.4;

const BUILDING_SPEC: Record<string, { color: number; emissive: number; emissiveIntensity: number; height: number }> = {
  home:        { color: 0x1e2d3d, emissive: 0x1e293b, emissiveIntensity: 0.04, height: 1.6 },
  workplace:   { color: 0x1a2940, emissive: 0xfbbf24, emissiveIntensity: 0.06, height: 2.2 },
  commons:     { color: 0x1a3329, emissive: 0x34d399, emissiveIntensity: 0.08, height: 1.2 },
  institution: { color: 0x1a1f3a, emissive: 0x6ea8fe, emissiveIntensity: 0.10, height: 3.6 },
};

function gridToWorld(gx: number, gy: number, gw: number, gh: number) {
  return {
    x: (gx - (gw - 1) / 2) * CELL,
    z: (gy - (gh - 1) / 2) * CELL,
  };
}

function fearColor(fear: number): THREE.Color {
  const c = new THREE.Color();
  if (fear < 0.35)
    c.lerpColors(new THREE.Color(0x6ea8fe), new THREE.Color(0xfbbf24), fear / 0.35);
  else
    c.lerpColors(new THREE.Color(0xfbbf24), new THREE.Color(0xf87171), (fear - 0.35) / 0.65);
  return c;
}

// ── Citizen state ──────────────────────────────────────────────────────────
type CitizenObj = {
  body: THREE.Mesh;
  head: THREE.Mesh;
  aura: THREE.Mesh;
  label: CSS2DObject;
  bubble: CSS2DObject;
  bubbleEl: HTMLDivElement;
  dispX: number;
  dispZ: number;
  tgtX: number;
  tgtZ: number;
};

// ── Main component ─────────────────────────────────────────────────────────
export default function CityStage3D() {
  const containerRef = useRef<HTMLDivElement>(null);
  const flashRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    const flashEl = flashRef.current;
    if (!el) return;

    // ── Renderer ─────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    renderer.setClearColor(0x070a0f, 1);
    // Fill container absolutely so it resizes with the layout
    renderer.domElement.style.position = "absolute";
    renderer.domElement.style.inset = "0";
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.setSize(el.offsetWidth || 800, el.offsetHeight || 600);
    el.appendChild(renderer.domElement);

    // ── CSS2D overlay ────────────────────────────────────────────────────
    const labelRenderer = new CSS2DRenderer();
    labelRenderer.setSize(el.offsetWidth || 800, el.offsetHeight || 600);
    labelRenderer.domElement.style.position = "absolute";
    labelRenderer.domElement.style.inset = "0";
    labelRenderer.domElement.style.pointerEvents = "none";
    el.appendChild(labelRenderer.domElement);

    // ── Scene ────────────────────────────────────────────────────────────
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x070a0f);
    scene.fog = new THREE.Fog(0x070a0f, 30, 80);

    scene.add(new THREE.AmbientLight(0x0d1220, 3.0));
    const dirLight = new THREE.DirectionalLight(0x6ea8fe, 0.6);
    dirLight.position.set(10, 20, 10);
    scene.add(dirLight);

    // ── Camera & controls ─────────────────────────────────────────────
    const camera = new THREE.PerspectiveCamera(45, (el.offsetWidth || 800) / (el.offsetHeight || 600), 0.1, 200);
    camera.position.set(0, 22, 26);
    camera.lookAt(0, 0, 0);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.minPolarAngle = 0.2;
    controls.maxPolarAngle = Math.PI / 2.2;
    controls.minDistance = 8;
    controls.maxDistance = 60;

    // ── Post-processing (bloom) ───────────────────────────────────────
    const w0 = el.offsetWidth || 800, h0 = el.offsetHeight || 600;
    const composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    const bloom = new UnrealBloomPass(new THREE.Vector2(w0, h0), 0.75, 0.4, 0.1);
    composer.addPass(bloom);
    composer.addPass(new OutputPass());

    // ── Scene groups ─────────────────────────────────────────────────
    const groundGroup = new THREE.Group();
    const buildingGroup = new THREE.Group();
    const crisisLightsGroup = new THREE.Group();
    const citizenGroup = new THREE.Group();
    scene.add(groundGroup, buildingGroup, crisisLightsGroup, citizenGroup);

    // ── Shared geometries ─────────────────────────────────────────────
    const bodyGeo = new THREE.CapsuleGeometry(0.22, 0.5, 4, 8);
    const headGeo = new THREE.SphereGeometry(0.18, 8, 6);
    const auraGeo = new THREE.CircleGeometry(0.6, 16);

    // ── Runtime state ─────────────────────────────────────────────────
    const citizens = new Map<string, CitizenObj>();
    const buildings = new Map<string, THREE.Mesh>();
    const roofEdges = new Map<string, THREE.Mesh>();
    const crisisLights = new Map<string, THREE.PointLight>();
    const groundTiles = new Map<string, THREE.Mesh>();
    let gridW = 0, gridH = 0;
    let built = false;
    let prevCrisisCount = 0;
    let flashUntil = 0;

    // ── Raycaster for click-to-select ────────────────────────────────
    const raycaster = new THREE.Raycaster();
    const clickableMeshes: THREE.Mesh[] = [];

    const onPointerDown = (e: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      const ndc = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1,
      );
      raycaster.setFromCamera(ndc, camera);
      const hits = raycaster.intersectObjects(clickableMeshes);
      if (hits.length) {
        const id = hits[0].object.userData.citizenId as string | undefined;
        if (id) useWorld.getState().select(id);
      }
    };
    renderer.domElement.addEventListener("pointerdown", onPointerDown);

    // ── Build ground ─────────────────────────────────────────────────
    function buildGround(gw: number, gh: number) {
      groundGroup.clear();
      groundTiles.clear();
      const geo = new THREE.PlaneGeometry(CELL - 0.08, CELL - 0.08);
      for (let gx = 0; gx < gw; gx++) {
        for (let gy = 0; gy < gh; gy++) {
          const shade = (gx + gy) % 2 === 0 ? 0x10161e : 0x0c1018;
          const mat = new THREE.MeshStandardMaterial({
            color: shade,
            emissive: new THREE.Color(0x000000),
            emissiveIntensity: 0,
            roughness: 0.9,
          });
          const mesh = new THREE.Mesh(geo, mat);
          mesh.rotation.x = -Math.PI / 2;
          const pos = gridToWorld(gx, gy, gw, gh);
          mesh.position.set(pos.x, 0, pos.z);
          groundGroup.add(mesh);
          groundTiles.set(`${gx},${gy}`, mesh);
        }
      }
    }

    // ── Build buildings ───────────────────────────────────────────────
    function buildBuildings(locs: LocationT[], gw: number, gh: number) {
      buildingGroup.clear();
      crisisLightsGroup.clear();
      buildings.clear();
      roofEdges.clear();
      crisisLights.clear();
      clickableMeshes.length = 0;

      for (const loc of locs) {
        const spec = BUILDING_SPEC[loc.type] ?? BUILDING_SPEC.home;
        const pos = gridToWorld(loc.x, loc.y, gw, gh);

        // Building body
        const bw = CELL * 0.55;
        const geo = new THREE.BoxGeometry(bw, spec.height, bw);
        const mat = new THREE.MeshStandardMaterial({
          color: spec.color,
          emissive: new THREE.Color(spec.emissive),
          emissiveIntensity: spec.emissiveIntensity,
          roughness: 0.7,
          metalness: 0.2,
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(pos.x, spec.height / 2, pos.z);
        buildingGroup.add(mesh);
        buildings.set(loc.id, mesh);

        // Roof edge glow
        const roofGeo = new THREE.BoxGeometry(CELL * 0.57, 0.06, CELL * 0.57);
        const roofMat = new THREE.MeshStandardMaterial({
          color: spec.emissive,
          emissive: new THREE.Color(spec.emissive),
          emissiveIntensity: 0.6,
        });
        const roofMesh = new THREE.Mesh(roofGeo, roofMat);
        roofMesh.position.set(pos.x, spec.height + 0.03, pos.z);
        buildingGroup.add(roofMesh);
        roofEdges.set(loc.id, roofMesh);

        // Location name label
        const labelDiv = document.createElement("div");
        labelDiv.textContent = loc.name;
        labelDiv.style.cssText = "color:#94a3b8;font-size:9px;font-family:monospace;white-space:nowrap;pointer-events:none;";
        const labelObj = new CSS2DObject(labelDiv);
        labelObj.position.set(pos.x, spec.height + 0.3, pos.z);
        scene.add(labelObj);

        // Crisis point light (hidden by default)
        const light = new THREE.PointLight(0xf87171, 0, CELL * 3);
        light.position.set(pos.x, spec.height + 1, pos.z);
        crisisLightsGroup.add(light);
        crisisLights.set(loc.id, light);
      }
    }

    // ── Update buildings for crisis state ────────────────────────────
    function updateBuildings(locs: LocationT[], closed: string[]) {
      for (const loc of locs) {
        const mesh = buildings.get(loc.id);
        const roofMesh = roofEdges.get(loc.id);
        if (!mesh) continue;
        const mat = mesh.material as THREE.MeshStandardMaterial;
        const spec = BUILDING_SPEC[loc.type] ?? BUILDING_SPEC.home;
        const isClosed = closed.includes(loc.id);
        if (isClosed) {
          mat.emissive.setHex(0xf87171);
          mat.emissiveIntensity = 0.35;
          if (roofMesh) {
            const rm = roofMesh.material as THREE.MeshStandardMaterial;
            rm.emissive.setHex(0xf87171);
          }
        } else {
          mat.emissive.setHex(spec.emissive);
          mat.emissiveIntensity = spec.emissiveIntensity;
          if (roofMesh) {
            const rm = roofMesh.material as THREE.MeshStandardMaterial;
            rm.emissive.setHex(spec.emissive);
          }
        }
      }
    }

    // ── Update ground fear heatmap ────────────────────────────────────
    function updateGroundHeat(citizenData: Citizen[], locs: LocationT[], gw: number, gh: number) {
      const fearByLoc = new Map<string, number>();
      for (const c of citizenData) {
        if ((c.fear ?? 0) > 0.08 && c.location_id) {
          fearByLoc.set(c.location_id, Math.max(fearByLoc.get(c.location_id) ?? 0, c.fear));
        }
      }
      for (const [key, tile] of groundTiles) {
        const [gxStr, gyStr] = key.split(",");
        const gx = parseInt(gxStr), gy = parseInt(gyStr);
        const loc = locs.find(l => l.x === gx && l.y === gy);
        const mat = tile.material as THREE.MeshStandardMaterial;
        if (loc) {
          const f = fearByLoc.get(loc.id) ?? 0;
          const fc = fearColor(f);
          mat.emissive.copy(fc);
          mat.emissiveIntensity = f * 0.24;
        } else {
          mat.emissive.setHex(0x000000);
          mat.emissiveIntensity = 0;
        }
        void gw; void gh;
      }
    }

    // ── Create/update citizens ────────────────────────────────────────
    function getCitizen(id: string, name: string): CitizenObj {
      const existing = citizens.get(id);
      if (existing) return existing;

      const bodyMat = new THREE.MeshStandardMaterial({ color: 0x334155, emissive: new THREE.Color(0x6ea8fe), emissiveIntensity: 0.2, roughness: 0.6 });
      const headMat = new THREE.MeshStandardMaterial({ color: 0x475569, emissive: new THREE.Color(0x6ea8fe), emissiveIntensity: 0.3, roughness: 0.5 });
      const auraMat = new THREE.MeshStandardMaterial({ color: 0x6ea8fe, emissive: new THREE.Color(0x6ea8fe), emissiveIntensity: 1.0, transparent: true, opacity: 0, side: THREE.DoubleSide });

      const body = new THREE.Mesh(bodyGeo, bodyMat);
      body.userData.citizenId = id;
      body.position.y = 0.55;

      const head = new THREE.Mesh(headGeo, headMat);
      head.userData.citizenId = id;
      head.position.y = 1.15;

      const aura = new THREE.Mesh(auraGeo, auraMat);
      aura.rotation.x = -Math.PI / 2;
      aura.position.y = 0.01;

      // Name label
      const labelDiv = document.createElement("div");
      labelDiv.textContent = name.split(" ")[0];
      labelDiv.style.cssText = "color:#94a3b8;font-size:9px;font-family:monospace;white-space:nowrap;pointer-events:none;";
      const label = new CSS2DObject(labelDiv);
      label.position.set(0, 1.5, 0);

      // Speech bubble
      const bubbleEl = document.createElement("div");
      bubbleEl.style.cssText = `
        background:#f2f6ff;color:#0b0e14;font-size:10px;font-family:monospace;
        border-radius:6px;padding:5px 8px;max-width:130px;line-height:1.4;
        pointer-events:none;display:none;white-space:pre-wrap;
      `;
      const bubble = new CSS2DObject(bubbleEl);
      bubble.position.set(0, 2.0, 0);

      citizenGroup.add(body, head, aura, label, bubble);
      clickableMeshes.push(body, head);

      const obj: CitizenObj = { body, head, aura, label, bubble, bubbleEl, dispX: 0, dispZ: 0, tgtX: 0, tgtZ: 0 };
      citizens.set(id, obj);
      return obj;
    }

    function updateCitizen(c: Citizen, gw: number, gh: number, selected: string | null) {
      const obj = getCitizen(c.id, c.name);
      const pos = gridToWorld(c.x, c.y, gw, gh);
      obj.tgtX = pos.x;
      obj.tgtZ = pos.z;

      const fear = c.fear ?? 0;
      const fc = fearColor(fear);

      const bodyMat = obj.body.material as THREE.MeshStandardMaterial;
      bodyMat.emissive.copy(fc);
      bodyMat.emissiveIntensity = 0.2 + fear * 0.8;

      const headMat = obj.head.material as THREE.MeshStandardMaterial;
      headMat.emissive.copy(fc);
      headMat.emissiveIntensity = 0.3 + fear * 0.9;

      const auraMat = obj.aura.material as THREE.MeshStandardMaterial;
      auraMat.color.copy(fc);
      auraMat.emissive.copy(fc);
      auraMat.opacity = fear > 0.12 ? Math.min(0.45, fear * 0.6) : 0;

      // Selection ring — boost emissive
      if (selected === c.id) {
        bodyMat.emissiveIntensity = Math.min(1.5, bodyMat.emissiveIntensity + 0.5);
      }

      // Speech bubble
      if (c.speech) {
        const raw = c.speech;
        const colon = raw.indexOf(": ");
        const text = colon !== -1 ? raw.slice(colon + 2) : raw;
        obj.bubbleEl.textContent = text.length > 60 ? text.slice(0, 59) + "..." : text;
        obj.bubbleEl.style.display = "block";
      } else {
        obj.bubbleEl.style.display = "none";
      }
    }

    // ── Main sync from store ──────────────────────────────────────────
    function sync() {
      const w = useWorld.getState().world;
      if (!w) return;

      const { grid, locations, citizens: citizenData, closed_locations, active_crises } = w;

      if (!built) {
        gridW = grid.w;
        gridH = grid.h;
        buildGround(gridW, gridH);
        buildBuildings(locations, gridW, gridH);
        built = true;
      }

      updateBuildings(locations, closed_locations ?? []);
      updateGroundHeat(citizenData, locations, gridW, gridH);

      const crisisCount = active_crises?.length ?? 0;
      if (crisisCount > prevCrisisCount && flashEl) {
        flashUntil = performance.now() + 900;
      }
      prevCrisisCount = crisisCount;

      const selected = useWorld.getState().selectedId;
      const seen = new Set<string>();
      for (const c of citizenData) {
        seen.add(c.id);
        updateCitizen(c, gridW, gridH, selected);
      }

      // Remove gone citizens
      for (const [id, obj] of citizens) {
        if (!seen.has(id)) {
          citizenGroup.remove(obj.body, obj.head, obj.aura, obj.label, obj.bubble);
          const bodyIdx = clickableMeshes.indexOf(obj.body);
          if (bodyIdx !== -1) clickableMeshes.splice(bodyIdx, 1);
          const headIdx = clickableMeshes.indexOf(obj.head);
          if (headIdx !== -1) clickableMeshes.splice(headIdx, 1);
          citizens.delete(id);
        }
      }
    }

    const unsub = useWorld.subscribe(sync);
    sync();

    // ── Animation loop ────────────────────────────────────────────────
    const clock = new THREE.Clock();
    let frameId = 0;

    function animate() {
      frameId = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();
      controls.update();

      // Interpolate citizen positions + gentle float
      for (const [, obj] of citizens) {
        obj.dispX += (obj.tgtX - obj.dispX) * 0.12;
        obj.dispZ += (obj.tgtZ - obj.dispZ) * 0.12;
        const floatY = 0.015 * Math.sin(t * 1.8 + obj.tgtX);
        obj.body.position.set(obj.dispX, 0.55 + floatY, obj.dispZ);
        obj.head.position.set(obj.dispX, 1.15 + floatY, obj.dispZ);
        obj.aura.position.set(obj.dispX, 0.01, obj.dispZ);

        // Aura pulse scale
        const auraMat = obj.aura.material as THREE.MeshStandardMaterial;
        const pulseScale = 1 + 0.08 * Math.sin(t * 2.4 + obj.tgtZ);
        if (auraMat.opacity > 0.01) obj.aura.scale.setScalar(pulseScale);

        // Sync CSS2D label/bubble position
        obj.label.position.set(obj.dispX, 1.5 + floatY, obj.dispZ);
        obj.bubble.position.set(obj.dispX, 2.1 + floatY, obj.dispZ);
      }

      // Pulse crisis lights
      for (const [locId, light] of crisisLights) {
        const w = useWorld.getState().world;
        const closed = w?.closed_locations ?? [];
        if (closed.includes(locId)) {
          light.intensity = 2.0 + 0.8 * Math.sin(t * 3.2);
        } else {
          light.intensity = 0;
        }
      }

      // Crisis flash overlay
      if (flashEl) {
        const now = performance.now();
        if (now < flashUntil) {
          const frac = (flashUntil - now) / 900;
          flashEl.style.opacity = String(frac * 0.22);
        } else {
          flashEl.style.opacity = "0";
        }
      }

      composer.render();
      labelRenderer.render(scene, camera);
    }

    animate();

    // ── Resize — use ResizeObserver so layout changes also trigger ───────
    const onResize = () => {
      if (!el) return;
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

    // ── Cleanup ───────────────────────────────────────────────────────
    return () => {
      cancelAnimationFrame(frameId);
      ro.disconnect();
      window.removeEventListener("resize", onResize);
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      unsub();
      controls.dispose();
      renderer.dispose();
      composer.dispose();
      if (renderer.domElement.parentNode === el) el.removeChild(renderer.domElement);
      if (labelRenderer.domElement.parentNode === el) el.removeChild(labelRenderer.domElement);
    };
  }, []);

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", position: "relative" }}>
      <div
        ref={flashRef}
        style={{
          position: "absolute", inset: 0, background: "#f87171",
          opacity: 0, pointerEvents: "none", zIndex: 5,
          transition: "opacity 0.05s",
        }}
      />
    </div>
  );
}
