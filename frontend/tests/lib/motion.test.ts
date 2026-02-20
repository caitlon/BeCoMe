import { describe, it, expect } from 'vitest';
import { fadeInUp } from '@/lib/motion';

describe('fadeInUp', () => {
  it('has initial, animate, and transition properties', () => {
    expect(fadeInUp).toHaveProperty('initial');
    expect(fadeInUp).toHaveProperty('animate');
    expect(fadeInUp).toHaveProperty('transition');
  });

  it('initial state has zero opacity and positive y offset', () => {
    expect(fadeInUp.initial).toEqual({ opacity: 0, y: 20 });
  });

  it('animate state has full opacity and zero y offset', () => {
    expect(fadeInUp.animate).toEqual({ opacity: 1, y: 0 });
  });

  it('transition has 0.5s duration', () => {
    expect(fadeInUp.transition).toEqual({ duration: 0.5 });
  });
});
