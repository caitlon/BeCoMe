import { describe, it, expect } from 'vitest';
import { scaleToX, trianglePoints, type TriangleScale } from '@/components/project/triangle-geometry';

describe('scaleToX', () => {
  const scale: TriangleScale = { scaleMin: 0, scaleMax: 100, x0: 10, width: 180 };

  it('maps a value at scaleMin to x0', () => {
    expect(scaleToX(0, scale)).toBe(10);
  });

  it('maps a value at scaleMax to x0 + width', () => {
    expect(scaleToX(100, scale)).toBe(190);
  });

  it('maps the midpoint value to the middle of the coordinate span', () => {
    expect(scaleToX(50, scale)).toBe(100);
  });

  it('maps a value using a non-zero scaleMin and a different coordinate span', () => {
    const offsetScale: TriangleScale = { scaleMin: 40, scaleMax: 360, x0: 40, width: 320 };
    expect(scaleToX(40, offsetScale)).toBe(40);
    expect(scaleToX(360, offsetScale)).toBe(360);
    expect(scaleToX(200, offsetScale)).toBe(200);
  });
});

describe('trianglePoints', () => {
  const scale: TriangleScale = { scaleMin: 0, scaleMax: 100, x0: 10, width: 180 };

  it('formats the three vertices as an SVG polygon points string', () => {
    expect(trianglePoints(20, 50, 80, 50, 10, scale)).toBe('46,50 100,10 154,50');
  });

  it('places the lower and upper vertices on the shared base y-coordinate', () => {
    const points = trianglePoints(0, 50, 100, 160, 30, scale);
    const [lowerVertex, peakVertex, upperVertex] = points.split(' ');
    expect(lowerVertex).toBe('10,160');
    expect(peakVertex).toBe('100,30');
    expect(upperVertex).toBe('190,160');
  });
});
