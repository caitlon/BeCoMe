/**
 * Shared SVG coordinate math for rendering fuzzy triangle numbers.
 *
 * Both the opinion-form preview and the results triangle chart map a value on
 * the project's scale to an x-coordinate inside an SVG viewBox, then draw a
 * triangle polygon from a (lower, peak, upper) triple. This module centralizes
 * that math so both call sites stay in sync.
 */

export interface TriangleScale {
  scaleMin: number;
  scaleMax: number;
  x0: number;
  width: number;
}

/**
 * Maps a value on the project's scale to an x-coordinate within the SVG viewBox.
 *
 * :param value: The scale value to map (e.g. a lower/peak/upper bound).
 * :param scale: The scale range and target coordinate span.
 * :return: The x-coordinate, where `scaleMin` maps to `x0` and `scaleMax` maps to `x0 + width`.
 */
export function scaleToX(value: number, scale: TriangleScale): number {
  const { scaleMin, scaleMax, x0, width } = scale;
  return x0 + ((value - scaleMin) / (scaleMax - scaleMin)) * width;
}

/**
 * Builds the SVG polygon `points` string for a fuzzy triangle number.
 *
 * :param lower: The triangle's lower bound (left base vertex).
 * :param peak: The triangle's peak value (apex vertex).
 * :param upper: The triangle's upper bound (right base vertex).
 * :param baseY: The y-coordinate shared by the lower and upper vertices.
 * :param peakY: The y-coordinate of the peak vertex.
 * :param scale: The scale range and target coordinate span used to map each value to x.
 * :return: A polygon points string of the form "x1,y1 x2,y2 x3,y3".
 */
export function trianglePoints(
  lower: number,
  peak: number,
  upper: number,
  baseY: number,
  peakY: number,
  scale: TriangleScale,
): string {
  return `${scaleToX(lower, scale)},${baseY} ${scaleToX(peak, scale)},${peakY} ${scaleToX(upper, scale)},${baseY}`;
}
