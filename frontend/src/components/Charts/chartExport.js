/**
 * Chart export utilities.
 *
 * Implements chart download as PNG or SVG images (Req 4.8):
 * - PNG export uses the live ECharts instance's `getDataURL` at 2x pixel ratio.
 * - SVG export renders the same option through a temporary off-screen ECharts
 *   instance created with the `svg` renderer, reads `renderToSVGString()`, then
 *   disposes the instance and triggers a download of an `.svg` blob.
 */
import * as echarts from 'echarts';
/** Strip characters that are unsafe for filenames and append an extension. */
export function toSafeFilename(name, extension) {
    const trimmed = (name || 'chart').trim();
    // Replace path separators and reserved characters with underscores.
    const safe = trimmed.replace(/[\\/:*?"<>|]+/g, '_').slice(0, 120) || 'chart';
    const ext = extension.startsWith('.') ? extension : `.${extension}`;
    return safe.endsWith(ext) ? safe : `${safe}${ext}`;
}
/**
 * Trigger a browser download for the given data URL or Blob.
 *
 * Accepts either a `data:`/object URL string or a `Blob`; in the Blob case an
 * object URL is created and revoked after the download is dispatched.
 */
export function downloadFile(filename, dataUrlOrBlob) {
    if (typeof document === 'undefined') {
        return;
    }
    const isBlob = dataUrlOrBlob instanceof Blob;
    const href = isBlob ? URL.createObjectURL(dataUrlOrBlob) : dataUrlOrBlob;
    const anchor = document.createElement('a');
    anchor.href = href;
    anchor.download = filename;
    anchor.rel = 'noopener';
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    if (isBlob) {
        // Revoke on the next tick so the download has a chance to start.
        setTimeout(() => URL.revokeObjectURL(href), 0);
    }
}
/**
 * Export a chart instance to PNG and trigger a download (Req 4.8).
 *
 * @param instance live ECharts instance (from {@link EChartHandle.getInstance})
 * @param filename desired file name (extension is normalized to `.png`)
 * @param backgroundColor background fill for the exported image
 */
export function exportChartToPng(instance, filename, backgroundColor = '#ffffff') {
    const dataUrl = instance.getDataURL({
        type: 'png',
        pixelRatio: 2,
        backgroundColor,
    });
    downloadFile(toSafeFilename(filename, '.png'), dataUrl);
}
/**
 * Export an ECharts option to SVG and trigger a download (Req 4.8).
 *
 * Renders the option through a temporary off-screen instance using the SVG
 * renderer (the on-screen chart uses the canvas renderer), reads the SVG
 * string, disposes the temporary instance, and downloads an `.svg` blob.
 *
 * @param option the (themed) ECharts option to render
 * @param filename desired file name (extension is normalized to `.svg`)
 * @param size off-screen render size; defaults to 800x500
 */
export function exportOptionToSvg(option, filename, size = { width: 800, height: 500 }) {
    if (typeof document === 'undefined') {
        return;
    }
    const container = document.createElement('div');
    container.style.position = 'absolute';
    container.style.left = '-99999px';
    container.style.top = '-99999px';
    container.style.width = `${size.width}px`;
    container.style.height = `${size.height}px`;
    document.body.appendChild(container);
    const instance = echarts.init(container, undefined, {
        renderer: 'svg',
        width: size.width,
        height: size.height,
    });
    try {
        instance.setOption(option);
        const svg = instance.renderToSVGString();
        const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
        downloadFile(toSafeFilename(filename, '.svg'), blob);
    }
    finally {
        instance.dispose();
        document.body.removeChild(container);
    }
}
