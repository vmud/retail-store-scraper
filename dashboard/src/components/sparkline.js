/**
 * Sparkline Component - Mini trend visualization charts
 * Canvas-based lightweight sparkline renderer
 */

/**
 * Default sparkline options
 */
const defaultOptions = {
  width: 100,
  height: 24,
  lineColor: '#3b82f6',
  lineWidth: 2,
  fillColor: null, // Set to add area fill under line
  glowColor: null, // Set to add glow effect
  dotColor: null,  // Set to show end dot
  dotRadius: 3,
  padding: 2
};

/**
 * Draw a sparkline chart on a canvas element
 * @param {HTMLCanvasElement} canvas - Canvas element to draw on
 * @param {number[]} data - Array of numeric values
 * @param {object} options - Drawing options
 */
export function drawSparkline(canvas, data, options = {}) {
  if (!canvas || !data || data.length < 2) return;

  const ctx = canvas.getContext('2d');
  const opts = { ...defaultOptions, ...options };

  // Set canvas size
  canvas.width = opts.width;
  canvas.height = opts.height;

  // Calculate drawing dimensions
  const { width, height, padding, lineWidth } = opts;
  const drawWidth = width - padding * 2;
  const drawHeight = height - padding * 2;

  // Calculate data bounds
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  // Calculate points
  const step = drawWidth / (data.length - 1);
  const points = data.map((val, i) => ({
    x: padding + i * step,
    y: padding + drawHeight - ((val - min) / range) * drawHeight
  }));

  // Clear canvas
  ctx.clearRect(0, 0, width, height);

  // Draw fill area if specified
  if (opts.fillColor) {
    ctx.beginPath();
    ctx.moveTo(points[0].x, height - padding);
    points.forEach(point => {
      ctx.lineTo(point.x, point.y);
    });
    ctx.lineTo(points[points.length - 1].x, height - padding);
    ctx.closePath();

    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, opts.fillColor);
    gradient.addColorStop(1, 'transparent');
    ctx.fillStyle = gradient;
    ctx.fill();
  }

  // Draw line
  ctx.beginPath();
  ctx.strokeStyle = opts.lineColor;
  ctx.lineWidth = lineWidth;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  points.forEach((point, i) => {
    if (i === 0) {
      ctx.moveTo(point.x, point.y);
    } else {
      ctx.lineTo(point.x, point.y);
    }
  });

  ctx.stroke();

  // Add glow effect if specified
  if (opts.glowColor) {
    ctx.shadowColor = opts.glowColor;
    ctx.shadowBlur = 4;
    ctx.stroke();
    ctx.shadowBlur = 0;
  }

  // Draw end dot if specified
  if (opts.dotColor) {
    const lastPoint = points[points.length - 1];
    ctx.beginPath();
    ctx.arc(lastPoint.x, lastPoint.y, opts.dotRadius, 0, Math.PI * 2);
    ctx.fillStyle = opts.dotColor;
    ctx.fill();
  }
}

/**
 * Create a sparkline element
 * @param {number[]} data - Data points
 * @param {object} options - Sparkline options
 * @returns {HTMLCanvasElement} Canvas element with sparkline
 */
export function createSparkline(data, options = {}) {
  const canvas = document.createElement('canvas');
  canvas.className = 'sparkline';
  drawSparkline(canvas, data, options);
  return canvas;
}

/**
 * Update an existing sparkline with new data
 * @param {HTMLCanvasElement} canvas - Existing canvas element
 * @param {number[]} data - New data points
 * @param {object} options - Drawing options
 */
export function updateSparkline(canvas, data, options = {}) {
  drawSparkline(canvas, data, options);
}

/**
 * Generate mock trend data for demo purposes
 * @param {number} points - Number of data points
 * @param {number} base - Base value
 * @param {number} variance - Variance amount
 * @returns {number[]} Generated data array
 */
export function generateMockData(points = 20, base = 100, variance = 20) {
  const data = [];
  let current = base;

  for (let i = 0; i < points; i++) {
    current += (Math.random() - 0.5) * variance;
    current = Math.max(0, current);
    data.push(Math.round(current));
  }

  return data;
}

/**
 * Retailer-specific sparkline colors
 */
export const RETAILER_COLORS = {
  verizon: { line: '#cd040b', glow: 'rgba(205, 4, 11, 0.3)' },
  att: { line: '#00a8e0', glow: 'rgba(0, 168, 224, 0.3)' },
  target: { line: '#cc0000', glow: 'rgba(204, 0, 0, 0.3)' },
  tmobile: { line: '#e20074', glow: 'rgba(226, 0, 116, 0.3)' },
  walmart: { line: '#0071ce', glow: 'rgba(0, 113, 206, 0.3)' },
  bestbuy: { line: '#0046be', glow: 'rgba(0, 70, 190, 0.3)' }
};

export default {
  drawSparkline,
  createSparkline,
  updateSparkline,
  generateMockData,
  RETAILER_COLORS
};
