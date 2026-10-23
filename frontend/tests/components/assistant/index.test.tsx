import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, renderHook, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Hoisted so the same spy survives vi.resetModules() and reaches the re-imported assistant module.
const sentry = vi.hoisted(() => ({ captureException: vi.fn() }));
vi.mock('@sentry/react', () => sentry);

// The slots import ./triggers lazily; a stand-in with a real button makes
// "the slot rendered its lazy child" observable instead of "did not throw".
const triggers = vi.hoisted(() => ({ throws: false, guideLoads: 0, guideFails: false }));
vi.mock('@/components/assistant/triggers', () => ({
  HeaderTrigger: () => {
    if (triggers.throws) throw new Error('chunk failed');
    return <button type="button">header trigger</button>;
  },
  ResultTrigger: ({ projectId }: { projectId: string }) => {
    if (triggers.throws) throw new Error('chunk failed');
    return <button type="button">result trigger {projectId}</button>;
  },
}));

vi.mock('@/components/assistant/AssistantPrivacyCard', () => ({
  AssistantPrivacyCard: () => {
    if (triggers.throws) throw new Error('chunk failed');
    return <p>privacy card</p>;
  },
}));

describe('components/assistant build gate', () => {
  beforeEach(() => {
    triggers.throws = false;
    triggers.guideLoads = 0;
    triggers.guideFails = false;
    sentry.captureException.mockClear();
    // A fresh module instance per test: every export below is computed once
    // from `enabled` at module scope, so re-reading any of them after
    // vi.stubEnv requires re-evaluating the module, exactly like
    // frontend/tests/lib/turnstile.test.ts does for VITE_TURNSTILE_SITE_KEY.
    vi.resetModules();
    // Registered per test, not hoisted: a hoisted factory runs once per file,
    // and these tests count and fail the import of the guide.
    vi.doMock('@/components/assistant/AssistantGuide', () => {
      triggers.guideLoads += 1;
      if (triggers.guideFails) throw new Error('chunk failed');
      return {
        AssistantDocsSection: () => <p>docs section</p>,
        AssistantDocsNavLabel: () => <>docs nav label</>,
      };
    });
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

  describe('AssistantProfileSlot', () => {
    it('renders nothing when disabled', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', '');

      const { AssistantProfileSlot } = await import('@/components/assistant');
      const { container } = render(<AssistantProfileSlot />);

      expect(container).toBeEmptyDOMElement();
    });

    it('renders nothing for any value other than the literal string "true"', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'TRUE');

      const { AssistantProfileSlot } = await import('@/components/assistant');
      const { container } = render(<AssistantProfileSlot />);

      expect(container).toBeEmptyDOMElement();
    });

    it('mounts the lazy privacy card inside a Suspense boundary when enabled', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      const { AssistantProfileSlot } = await import('@/components/assistant');
      render(<AssistantProfileSlot />);

      expect(await screen.findByText('privacy card')).toBeInTheDocument();
    });
  });

  describe('useAssistantGuide', () => {
    it.each(['', 'TRUE', undefined])('returns null and never loads the guide when VITE_ASSISTANT_ENABLED is "%s"', async (value) => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', value);

      const { useAssistantGuide } = await import('@/components/assistant');
      const { result } = renderHook(() => useAssistantGuide());
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      expect(result.current).toBeNull();
      expect(triggers.guideLoads).toBe(0);
    });

    it('returns null while the chunk loads, then the guide module', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      const { useAssistantGuide } = await import('@/components/assistant');
      const { result } = renderHook(() => useAssistantGuide());

      expect(result.current).toBeNull();
      await waitFor(() => expect(result.current).not.toBeNull());
      expect(result.current).toHaveProperty('AssistantDocsSection');
      expect(result.current).toHaveProperty('AssistantDocsNavLabel');
    });

    it('loads the chunk once however many callers ask', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      const { useAssistantGuide } = await import('@/components/assistant');
      const first = renderHook(() => useAssistantGuide());
      const second = renderHook(() => useAssistantGuide());

      await waitFor(() => expect(first.result.current).not.toBeNull());
      await waitFor(() => expect(second.result.current).toBe(first.result.current));
      expect(triggers.guideLoads).toBe(1);
    });

    it('stays null when the chunk fails to load, and reports it once', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      triggers.guideFails = true;
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { useAssistantGuide } = await import('@/components/assistant');
      const first = renderHook(() => useAssistantGuide());
      const second = renderHook(() => useAssistantGuide());
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      expect(first.result.current).toBeNull();
      expect(second.result.current).toBeNull();
      expect(consoleError).toHaveBeenCalledTimes(1);
      expect(consoleError).toHaveBeenCalledWith('[ERROR] Assistant guide failed to load', {
        error: expect.any(String),
      });
      expect(sentry.captureException).toHaveBeenCalledTimes(1);
      expect(sentry.captureException).toHaveBeenCalledWith(expect.any(Error));
      consoleError.mockRestore();
    });

    it('reports a failure that lands after the hook unmounted', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      triggers.guideFails = true;
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { useAssistantGuide } = await import('@/components/assistant');
      const { unmount } = renderHook(() => useAssistantGuide());
      unmount();
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      expect(sentry.captureException).toHaveBeenCalledTimes(1);
      consoleError.mockRestore();
    });

    it('tries the import again on the next mount after a failed load', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      triggers.guideFails = true;
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { useAssistantGuide } = await import('@/components/assistant');
      const failed = renderHook(() => useAssistantGuide());
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });
      expect(failed.result.current).toBeNull();
      failed.unmount();

      triggers.guideFails = false;
      const retried = renderHook(() => useAssistantGuide());
      await waitFor(() => expect(retried.result.current).not.toBeNull());

      expect(triggers.guideLoads).toBe(2);
      expect(sentry.captureException).toHaveBeenCalledTimes(1);
      consoleError.mockRestore();
    });

    it('hands a remount the loaded module on its first render', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');

      const { useAssistantGuide } = await import('@/components/assistant');
      const first = renderHook(() => useAssistantGuide());
      await waitFor(() => expect(first.result.current).not.toBeNull());
      first.unmount();

      const seen: unknown[] = [];
      renderHook(() => {
        const guide = useAssistantGuide();
        seen.push(guide);
        return guide;
      });

      expect(seen[0]).not.toBeNull();
      expect(seen.every((guide) => guide !== null)).toBe(true);
    });
  });

  describe('a slot whose chunk fails', () => {
    it('renders nothing and leaves the page around it alone', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      triggers.throws = true;
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
      const { AssistantHeaderSlot, AssistantResultSlot, AssistantProfileSlot } = await import(
        '@/components/assistant'
      );

      render(
        <>
          <p>page content</p>
          <AssistantHeaderSlot />
          <AssistantResultSlot projectId="p1" />
          <AssistantProfileSlot />
        </>
      );
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      expect(screen.getByText('page content')).toBeInTheDocument();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
      consoleError.mockRestore();
    });
  });

  describe('useAssistantProjectScope', () => {
    async function importHarness() {
      const { AssistantProvider, useAssistantProjectScope } = await import('@/components/assistant');
      const { useAssistantUI } = await import('@/contexts/AssistantUIContext');

      function Reader() {
        const { projectId, openAssistant, closeAssistant } = useAssistantUI();
        return (
          <>
            <span data-testid="panel-project">{projectId ?? 'none'}</span>
            <button onClick={() => openAssistant()}>open</button>
            <button onClick={closeAssistant}>close</button>
          </>
        );
      }
      function ScopedChild({ id }: { id: string | undefined }) {
        useAssistantProjectScope(id);
        return null;
      }
      function Harness({ scoped, id }: { scoped: boolean; id: string | undefined }) {
        return (
          <AssistantProvider>
            <Reader />
            {scoped && <ScopedChild id={id} />}
          </AssistantProvider>
        );
      }
      return Harness;
    }

    it('lets the header open the panel for the page project, and forgets it when the page unmounts', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      const Harness = await importHarness();
      const user = userEvent.setup();

      const { rerender } = render(<Harness scoped id="project-9" />);
      await user.click(screen.getByText('open'));
      expect(screen.getByTestId('panel-project')).toHaveTextContent('project-9');

      await user.click(screen.getByText('close'));
      rerender(<Harness scoped={false} id="project-9" />);
      await user.click(screen.getByText('open'));
      expect(screen.getByTestId('panel-project')).toHaveTextContent('none');
    });

    it('follows the page project as it changes and clears it when the id goes away', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
      const Harness = await importHarness();
      const user = userEvent.setup();

      const { rerender } = render(<Harness scoped id="project-1" />);
      rerender(<Harness scoped id="project-2" />);
      await user.click(screen.getByText('open'));
      expect(screen.getByTestId('panel-project')).toHaveTextContent('project-2');

      await user.click(screen.getByText('close'));
      rerender(<Harness scoped id={undefined} />);
      await user.click(screen.getByText('open'));
      expect(screen.getByTestId('panel-project')).toHaveTextContent('none');
    });

    it('is a no-op when disabled', async () => {
      vi.stubEnv('VITE_ASSISTANT_ENABLED', '');

      const { useAssistantProjectScope } = await import('@/components/assistant');

      expect(() => renderHook(() => useAssistantProjectScope('project-9'))).not.toThrow();
    });
  });
});
