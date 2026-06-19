// Isometric projection helpers + palette for the city renderer.

export const TILE_W = 40;
export const TILE_H = 20;

/** Grid cell (gx, gy) -> screen-space center point (before container offset). */
export function toScreen(gx: number, gy: number): { sx: number; sy: number } {
  return {
    sx: (gx - gy) * (TILE_W / 2),
    sy: (gx + gy) * (TILE_H / 2),
  };
}

export const LOCATION_COLORS: Record<string, number> = {
  home: 0x3b4a5a,
  workplace: 0x4a6fa5,
  commons: 0x3f7d5a,
  institution: 0x8a6d3b,
};

// Stable per-citizen color from a hash of the id, so each person is recognizable.
export function citizenColor(id: string): number {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  const palette = [
    0xff6b6b, 0xffd166, 0x06d6a0, 0x4cc9f0, 0xb388ff,
    0xf78c6b, 0x80ed99, 0x90e0ef, 0xf9c74f, 0xff8fab,
  ];
  return palette[h % palette.length];
}

/** Blend citizen base color toward red based on fear level (0-1). */
export function citizenColorWithFear(id: string, fear: number): number {
  const base = citizenColor(id);
  if (fear < 0.05) return base;
  const r0 = (base >> 16) & 0xff;
  const g0 = (base >> 8) & 0xff;
  const b0 = base & 0xff;
  // Blend toward #f87171 (red-ish fear color)
  const t = Math.min(1, fear * 1.2);
  const r = Math.round(r0 + (0xf8 - r0) * t);
  const g = Math.round(g0 + (0x71 - g0) * t);
  const b = Math.round(b0 + (0x71 - b0) * t);
  return (r << 16) | (g << 8) | b;
}

/** Night/day overlay alpha from day_progress (0..1). Darkest pre-dawn, bright midday. */
export function nightAlpha(dayProgress: number): number {
  // smooth bell that is high at night (0 and 1) and ~0 at midday (0.5)
  const dist = Math.abs(dayProgress - 0.5) * 2; // 0 at noon, 1 at midnight
  return Math.min(0.6, dist * dist * 0.6);
}
