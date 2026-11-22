import { describe, it, expect, afterEach } from 'vitest';
import { isHydrating, setHydrating } from '@/lib/hydration';

describe('hydration flag', () => {
  afterEach(() => setHydrating(false));

  it('is off until the client entry sets it', () => {
    expect(isHydrating()).toBe(false);
  });

  it('can be set and cleared', () => {
    setHydrating(true);
    expect(isHydrating()).toBe(true);

    setHydrating(false);
    expect(isHydrating()).toBe(false);
  });
});
