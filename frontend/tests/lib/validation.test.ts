import { describe, it, expect, vi } from 'vitest';
import type { FieldError } from 'react-hook-form';
import {
  SPECIAL_CHAR_REGEX,
  buildEmailSchema,
  buildPasswordSchema,
  getPasswordRequirements,
  visibleEmailError,
} from '@/lib/validation';

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

describe('buildPasswordSchema', () => {
  const t = vi.fn((key: string) => key);
  const schema = buildPasswordSchema(t);

  it('accepts a password satisfying every rule', () => {
    expect(schema.safeParse('StrongPass12!').success).toBe(true);
  });

  it.each([
    ['too short', 'Sp12!aa', 'passwordRequirements.minLength'],
    ['no uppercase', 'weakpassword12!', 'passwordRequirements.uppercase'],
    ['no lowercase', 'WEAKPASSWORD12!', 'passwordRequirements.lowercase'],
    ['no digit', 'WeakPassword!!!!', 'passwordRequirements.number'],
    ['no special char', 'WeakPassword1234', 'passwordRequirements.specialChar'],
  ])('rejects a password that is %s', (_label, password, expectedKey) => {
    const result = schema.safeParse(password);
    expect(result.success).toBe(false);
    expect(result.error?.issues.map((issue) => issue.message)).toContain(expectedKey);
  });

  it('rejects a password over the maximum length', () => {
    const result = schema.safeParse(`Aa1!${'x'.repeat(128)}`);
    expect(result.success).toBe(false);
    expect(result.error?.issues[0].message).toBe('validation.passwordMaxLength');
  });

  it('mirrors the checklist rules exactly', () => {
    const password = 'Abcdefghij1!';
    const checklist = getPasswordRequirements(password, t);
    expect(checklist.every((req) => req.met)).toBe(schema.safeParse(password).success);
  });
});

describe('buildEmailSchema', () => {
  const t = (key: string) => key;
  const schema = buildEmailSchema(t);

  it('accepts a well-formed address', () => {
    expect(schema.safeParse('user@example.com').success).toBe(true);
  });

  it('reports only the required message for an empty string', () => {
    const result = schema.safeParse('');
    expect(result.error?.issues.map((issue) => [issue.code, issue.message])).toEqual([
      ['too_small', 'validation.emailRequired'],
    ]);
  });

  it.each(['x', 'user@', 'user@example', 'a b@example.com'])(
    'reports only the format message for %j',
    (value) => {
      const result = schema.safeParse(value);
      expect(result.error?.issues.map((issue) => issue.message)).toEqual([
        'validation.emailInvalid',
      ]);
    }
  );

  it('uses the given message keys', () => {
    const custom = buildEmailSchema(t, 'invite.validation.emailInvalid', 'invite.validation.emailRequired');
    expect(custom.safeParse('').error?.issues[0].message).toBe('invite.validation.emailRequired');
    expect(custom.safeParse('x').error?.issues[0].message).toBe('invite.validation.emailInvalid');
  });

  it('lets callers chain further string checks without losing the empty-string rule', () => {
    const chained = schema.max(10, 'too long');
    expect(chained.safeParse('').error?.issues.map((issue) => issue.message)).toEqual([
      'validation.emailRequired',
    ]);
    expect(chained.safeParse('user@example.com').error?.issues.map((issue) => issue.message)).toEqual([
      'too long',
    ]);
  });
});

describe('visibleEmailError', () => {
  const required: FieldError = { type: 'too_small', message: 'Email is required' };
  const invalid: FieldError = { type: 'invalid_format', message: 'Invalid email address' };

  it('hides the empty-field error until the form was submitted', () => {
    expect(visibleEmailError(required, false)).toBeUndefined();
  });

  it('shows the empty-field error after a submit attempt', () => {
    expect(visibleEmailError(required, true)).toBe(required);
  });

  it('always shows a format error', () => {
    expect(visibleEmailError(invalid, false)).toBe(invalid);
    expect(visibleEmailError(invalid, true)).toBe(invalid);
  });

  it('passes through no error', () => {
    expect(visibleEmailError(undefined, false)).toBeUndefined();
  });
});
