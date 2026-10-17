// F16 Photo quality feedback — client-side pre-check (F16; owners worker 16, web 19).
//
// Mirrors the worker's assess_photo heuristic so the customer gets INSTANT retake guidance in
// the browser before any upload or paid vision call. It decodes the image locally and reports
// only observable facts (dimensions) and named quality issues — never a fabricated OCR
// confidence percentage, and never a browser-authored compatibility fact. The server-side
// worker check remains authoritative; this is advisory UX only.

export interface F16Request {
  image_bytes: ArrayBuffer;
  media_type: string;
}

export interface F16Result {
  readable: boolean;
  issues: string[];
  width: number;
  height: number;
}

const ALLOWED = new Set(["image/jpeg", "image/png", "image/webp"]);
const RECOMMENDED_MIN_EDGE = 600;
const DARK_MEAN_MAX = 50;
const BLUR_VAR_MIN = 15;

// Issue codes blocking the paid call; everything else is advisory guidance only.
export const BLOCKING_ISSUES = new Set(["unsupported_format", "undecodable_image", "image_too_large"]);

export async function assessPhoto(request: F16Request): Promise<F16Result> {
  if (!ALLOWED.has(request.media_type)) {
    return { readable: false, issues: ["unsupported_format"], width: 0, height: 0 };
  }
  const blob = new Blob([request.image_bytes], { type: request.media_type });
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(blob);
  } catch {
    return { readable: false, issues: ["undecodable_image"], width: 0, height: 0 };
  }
  const width = bitmap.width;
  const height = bitmap.height;
  const issues: string[] = [];
  const stats = sampleLuminance(bitmap);
  bitmap.close?.();

  if (min(width, height) < RECOMMENDED_MIN_EDGE) issues.push("low_resolution");
  if (stats !== null && stats.mean < DARK_MEAN_MAX) issues.push("too_dark");
  if (stats !== null && stats.variance < BLUR_VAR_MIN) issues.push("possible_blur");
  return { readable: true, issues, width, height };
}

function min(a: number, b: number): number {
  return a < b ? a : b;
}

// Draw to a canvas and compute mean luminance and a cheap neighbour-gradient variance (a blur
// proxy). Returns null where no 2D canvas is available (e.g. jsdom) so guidance degrades to
// dimension-only rather than throwing.
function sampleLuminance(bitmap: ImageBitmap): { mean: number; variance: number } | null {
  try {
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(bitmap, 0, 0);
    const { data, width } = ctx.getImageData(0, 0, canvas.width, canvas.height);
    let sum = 0;
    let gradientSum = 0;
    let gradientSumSq = 0;
    let gradientCount = 0;
    const pixels = data.length / 4;
    for (let i = 0; i < pixels; i += 1) {
      const o = i * 4;
      const luma = 0.299 * data[o] + 0.587 * data[o + 1] + 0.114 * data[o + 2];
      sum += luma;
      if (i % width !== 0) {
        const po = (i - 1) * 4;
        const prev = 0.299 * data[po] + 0.587 * data[po + 1] + 0.114 * data[po + 2];
        const g = Math.abs(luma - prev);
        gradientSum += g;
        gradientSumSq += g * g;
        gradientCount += 1;
      }
    }
    const mean = sum / pixels;
    const gMean = gradientCount ? gradientSum / gradientCount : 0;
    const variance = gradientCount ? gradientSumSq / gradientCount - gMean * gMean : 0;
    return { mean, variance };
  } catch {
    return null;
  }
}
