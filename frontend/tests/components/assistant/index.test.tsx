import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';

describe('components/assistant build gate', () => {
  beforeEach(() => {
    // A fresh module instance per test: every export below is computed once
    // from `enabled` at module scope, so re-reading any of them after
    // vi.stubEnv requires re-evaluating the module, exactly like
    // frontend/tests/lib/turnstile.test.ts does for VITE_TURNSTILE_SITE_KEY.
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  describe('AssistantEntry', () => {
    it('is null when VITE_ASSISTANT_ENABLED is not set', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', '');

      const { AssistantEntry } = await import('@/components/assistant');

      expect(AssistantEntry).toBeNull();
    });

    it('is a lazy component when VITE_ASSISTANT_ENABLED is exactly "true"', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      const { AssistantEntry } = await import('@/components/assistant');

      expect(AssistantEntry).not.toBeNull();
    });

    it('stays null for any value other than the literal string "true"', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'TRUE');

      const { AssistantEntry } = await import('@/components/assistant');

      expect(AssistantEntry).toBeNull();
    });
  });

  describe('AssistantProvider', () => {
    it('is a plain passthrough when disabled: renders children, is not AssistantUIProvider', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', '');

      const { AssistantProvider } = await import('@/components/assistant');
      const { AssistantUIProvider } = await import('@/contexts/AssistantUIContext');

      expect(AssistantProvider).not.toBe(AssistantUIProvider);
      render(<AssistantProvider><div>child content</div></AssistantProvider>);
      expect(screen.getByText('child content')).toBeInTheDocument();
    });

    it('is the real AssistantUIProvider when enabled', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      const { AssistantProvider } = await import('@/components/assistant');
      const { AssistantUIProvider } = await import('@/contexts/AssistantUIContext');

      expect(AssistantProvider).toBe(AssistantUIProvider);
    });
  });

  describe('AssistantHeaderSlot / AssistantResultSlot', () => {
    it('render nothing when disabled', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', '');

      const { AssistantHeaderSlot, AssistantResultSlot } = await import('@/components/assistant');
      const { container: header } = render(<AssistantHeaderSlot />);
      const { container: result } = render(<AssistantResultSlot projectId="p1" />);

      expect(header).toBeEmptyDOMElement();
      expect(result).toBeEmptyDOMElement();
    });

    it('mount a Suspense boundary around a lazy component when enabled', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      const { AssistantHeaderSlot, AssistantResultSlot } = await import('@/components/assistant');

      expect(() => render(<AssistantHeaderSlot />)).not.toThrow();
      expect(() => render(<AssistantResultSlot projectId="p1" />)).not.toThrow();
    });
  });
});
