import api from '../api/client';

let cachedLogoDataUrl: string | null | undefined;

/** Rasterize an SVG blob into a PNG data URL (jsPDF doesn't support SVG). */
async function rasterizeSvg(blob: Blob): Promise<string> {
  const svgText = await blob.text();
  const img = new Image();
  const svgUrl = URL.createObjectURL(new Blob([svgText], { type: 'image/svg+xml' }));

  return new Promise<string>((resolve, reject) => {
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth || 200;
      canvas.height = img.naturalHeight || 60;
      const ctx = canvas.getContext('2d')!;
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(svgUrl);
      resolve(canvas.toDataURL('image/png'));
    };
    img.onerror = () => {
      URL.revokeObjectURL(svgUrl);
      reject(new Error('Failed to rasterize SVG'));
    };
    img.src = svgUrl;
  });
}

/**
 * Fetch the branding logo from the API and return it as a base64 data URL.
 * Caches the result in memory (one fetch per session).
 * Returns null if no logo is configured.
 */
export async function getLogoDataUrl(): Promise<string | null> {
  if (cachedLogoDataUrl !== undefined) return cachedLogoDataUrl;

  try {
    const resp = await api.get('/branding/logo', { responseType: 'blob' });
    const blob: Blob = resp.data;

    if (blob.type.includes('svg')) {
      cachedLogoDataUrl = await rasterizeSvg(blob);
    } else {
      cachedLogoDataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
    }
  } catch {
    cachedLogoDataUrl = null;
  }

  return cachedLogoDataUrl;
}
