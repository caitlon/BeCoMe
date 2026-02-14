import { describe, it, expect, vi } from 'vitest';
import { SPECIAL_CHAR_REGEX, getPasswordRequirements } from '@/lib/validation';

describe('SPECIAL_CHAR_REGEX', () => {
  it.each(['!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '-', '_', '=', '+', '[', ']', '{', '}', '|', '\\', ';', "'", ':', '"', ',', '.', '<', '>', '/', '?', '`', '~'])(
    'matches special character: %s',
    (char) => {
      expect(SPECIAL_CHAR_REGEX.test(char)).toBe(true);
    }
  );

  it.each(['a', 'Z', '5', ' '])('does not match: %s', (char) => {
    expect(SPECIAL_CHAR_REGEX.test(char)).toBe(false);
  });
});

describe('getPasswordRequirements', () => {
  const t = vi.fn((key: string) => key);

  it('returns 5 requirements', () => {
    const reqs = getPasswordRequirements('', t);
    expect(reqs).toHaveLength(5);
    reqs.forEach((r) => {
      expect(r).toHaveProperty('label');
      expect(r).toHaveProperty('met');
    });
  });

  it('calls translator with correct keys', () => {
    getPasswordRequirements('', t);
    expect(t).toHaveBeenCalledWith('passwordRequirements.minLength');
    expect(t).toHaveBeenCalledWith('passwordRequirements.uppercase');
    expect(t).toHaveBeenCalledWith('passwordRequirements.lowercase');
    expect(t).toHaveBeenCalledWith('passwordRequirements.number');
    expect(t).toHaveBeenCalledWith('passwordRequirements.specialChar');
  });

  it('all requirements unmet for empty password', () => {
    const reqs = getPasswordRequirements('', t);
    expect(reqs.every((r) => !r.met)).toBe(true);
  });

  it('all requirements met for strong password', () => {
    const reqs = getPasswordRequirements('StrongPass12!', t);
    expect(reqs.every((r) => r.met)).toBe(true);
  });

  it('minLength requires 12+ characters', () => {
    const short = getPasswordRequirements('Abcdefgh1!a', t);
    expect(short[0].met).toBe(false);

    const exact = getPasswordRequirements('Abcdefgh1!ab', t);
    expect(exact[0].met).toBe(true);
  });

  it('detects uppercase', () => {
    const noUpper = getPasswordRequirements('abcdefgh12!a', t);
    expect(noUpper[1].met).toBe(false);

    const withUpper = getPasswordRequirements('Abcdefgh12!a', t);
    expect(withUpper[1].met).toBe(true);
  });

  it('detects lowercase', () => {
    const noLower = getPasswordRequirements('ABCDEFGH12!A', t);
    expect(noLower[2].met).toBe(false);

    const withLower = getPasswordRequirements('ABCDEFGh12!A', t);
    expect(withLower[2].met).toBe(true);
  });

  it('detects digits', () => {
    const noDigit = getPasswordRequirements('Abcdefghijk!', t);
    expect(noDigit[3].met).toBe(false);

    const withDigit = getPasswordRequirements('Abcdefghij1!', t);
    expect(withDigit[3].met).toBe(true);
  });

  it('detects special characters', () => {
    const noSpecial = getPasswordRequirements('Abcdefghij12', t);
    expect(noSpecial[4].met).toBe(false);

    const withSpecial = getPasswordRequirements('Abcdefghij1!', t);
    expect(withSpecial[4].met).toBe(true);
  });
});
