import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, renderHook, screen } from '@testing-library/react';
import type { ReactNode } from 'react';

// The slots import ./triggers lazily; a stand-in with a real button makes
// "the slot rendered its lazy child" observable instead of "did not throw".
vi.mock('@/components/assistant/triggers', () => ({
  HeaderTrigger: () => <button type="button">header trigger</button>,
  ResultTrigger: ({ projectId }: { projectId: string }) => <button type="button">result trigger {projectId}</button>,
}));

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

    it('is null when VITE_ASSISTANT_ENABLED is absent from the environment altogether', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', undefined);

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

    it('is a passthrough for any value other than the literal string "true"', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'TRUE');

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

    it('render nothing for any value other than the literal string "true"', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'TRUE');

      const { AssistantHeaderSlot, AssistantResultSlot } = await import('@/components/assistant');
      const { container: header } = render(<AssistantHeaderSlot />);
      const { container: result } = render(<AssistantResultSlot projectId="p1" />);

      expect(header).toBeEmptyDOMElement();
      expect(result).toBeEmptyDOMElement();
    });

    it('mount the lazy trigger inside a Suspense boundary when enabled', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      const { AssistantHeaderSlot, AssistantResultSlot } = await import('@/components/assistant');
      // One at a time: React Testing Library drops the retry of a second root
      // that suspends while the first one is still pending.
      render(<AssistantHeaderSlot />);
      expect(await screen.findByRole('button', { name: 'header trigger' })).toBeInTheDocument();

      render(<AssistantResultSlot projectId="p1" />);
      expect(await screen.findByRole('button', { name: 'result trigger p1' })).toBeInTheDocument();
    });
  });

  describe('useAssistantProjectScope', () => {
    it('registers the project with the UI context and clears it on unmount when enabled', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      const { AssistantProvider, useAssistantProjectScope } = await import('@/components/assistant');
      const { useAssistantUI } = await import('@/contexts/AssistantUIContext');
      const wrapper = ({ children }: { children: ReactNode }) => <AssistantProvider>{children}</AssistantProvider>;
      const { result, rerender } = renderHook(
        ({ id }: { id: string | undefined }) => {
          useAssistantProjectScope(id);
          return useAssistantUI();
        },
        { wrapper, initialProps: { id: 'project-9' as string | undefined } }
      );

      expect(result.current.projectId).toBe('project-9');

      rerender({ id: undefined });
      expect(result.current.projectId).toBeNull();
    });

    it('is a no-op when disabled', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', '');

      const { useAssistantProjectScope } = await import('@/components/assistant');

      expect(() => renderHook(() => useAssistantProjectScope('project-9'))).not.toThrow();
    });
  });
});
