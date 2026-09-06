import { createRef } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, screen, waitFor } from '@testing-library/react';
import { render } from '@tests/utils';
import { TurnstileField, TurnstileFieldHandle } from '@/components/forms/TurnstileField';
import type { TurnstileRenderOptions } from '@/lib/turnstile';

const mockGetTurnstileSiteKey = vi.fn<() => string>();
const mockLoadTurnstileScript = vi.fn();

vi.mock('@/lib/turnstile', () => ({
  getTurnstileSiteKey: () => mockGetTurnstileSiteKey(),
  loadTurnstileScript: () => mockLoadTurnstileScript(),
}));

function makeFakeApi() {
  return { render: vi.fn(), reset: vi.fn(), remove: vi.fn() };
}

describe('TurnstileField', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetTurnstileSiteKey.mockReturnValue('test-site-key');
  });

  it('renders nothing, and never touches the Turnstile script, when the build has no sitekey', () => {
    mockGetTurnstileSiteKey.mockReturnValue('');
    const onToken = vi.fn();

    const { container } = render(<TurnstileField action="login" onToken={onToken} />);

    expect(container).toBeEmptyDOMElement();
    expect(mockLoadTurnstileScript).not.toHaveBeenCalled();
  });

  it('renders the widget for the action it was given', async () => {
    const api = makeFakeApi();
    api.render.mockReturnValue('widget-1');
    mockLoadTurnstileScript.mockResolvedValue(api);
    const onToken = vi.fn();

    render(<TurnstileField action="register" onToken={onToken} />);

    await waitFor(() => expect(api.render).toHaveBeenCalledTimes(1));

    // The exact defect this guards against: a widget rendered without its
    // action mints a token whose action Cloudflare never reports back, and the
    // API refuses every one of them as an action_mismatch (see
    // api/services/turnstile_service.py).
    const [, options] = api.render.mock.calls[0] as [HTMLElement, TurnstileRenderOptions];
    expect(options.action).toBe('register');
    expect(options.sitekey).toBe('test-site-key');
  });

  it('reports the token the widget mints', async () => {
    const api = makeFakeApi();
    api.render.mockReturnValue('widget-1');
    mockLoadTurnstileScript.mockResolvedValue(api);
    const onToken = vi.fn();

    render(<TurnstileField action="login" onToken={onToken} />);
    await waitFor(() => expect(api.render).toHaveBeenCalledTimes(1));

    const [, options] = api.render.mock.calls[0] as [HTMLElement, TurnstileRenderOptions];
    act(() => options.callback('a-fresh-token'));

    expect(onToken).toHaveBeenLastCalledWith('a-fresh-token');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('clears the token and starts a fresh challenge when asked to reset', async () => {
    const api = makeFakeApi();
    api.render.mockReturnValue('widget-1');
    mockLoadTurnstileScript.mockResolvedValue(api);
    const onToken = vi.fn();
    const ref = createRef<TurnstileFieldHandle>();

    render(<TurnstileField ref={ref} action="login" onToken={onToken} />);
    await waitFor(() => expect(api.render).toHaveBeenCalledTimes(1));

    act(() => ref.current?.reset());

    expect(onToken).toHaveBeenLastCalledWith(null);
    expect(api.reset).toHaveBeenCalledWith('widget-1');
  });

  it('resets itself when the token expires before the form is submitted', async () => {
    const api = makeFakeApi();
    api.render.mockReturnValue('widget-1');
    mockLoadTurnstileScript.mockResolvedValue(api);
    const onToken = vi.fn();

    render(<TurnstileField action="login" onToken={onToken} />);
    await waitFor(() => expect(api.render).toHaveBeenCalledTimes(1));

    const [, options] = api.render.mock.calls[0] as [HTMLElement, TurnstileRenderOptions];
    act(() => options['expired-callback']());

    expect(onToken).toHaveBeenLastCalledWith(null);
    expect(api.reset).toHaveBeenCalledWith('widget-1');
  });

  it('shows a translated error and clears the token when Cloudflare reports one', async () => {
    const api = makeFakeApi();
    api.render.mockReturnValue('widget-1');
    mockLoadTurnstileScript.mockResolvedValue(api);
    const onToken = vi.fn();

    render(<TurnstileField action="login" onToken={onToken} />);
    await waitFor(() => expect(api.render).toHaveBeenCalledTimes(1));

    const [, options] = api.render.mock.calls[0] as [HTMLElement, TurnstileRenderOptions];
    act(() => options['error-callback']());

    expect(onToken).toHaveBeenLastCalledWith(null);
    expect(
      screen.getByText("We couldn't confirm you are human. Reload the page and try again.")
    ).toBeInTheDocument();
  });

  it('shows the same error when Cloudflare refuses to render a widget at all', async () => {
    const api = makeFakeApi();
    api.render.mockReturnValue(undefined);
    mockLoadTurnstileScript.mockResolvedValue(api);

    render(<TurnstileField action="login" onToken={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('shows the error when the Turnstile script itself fails to load', async () => {
    mockLoadTurnstileScript.mockRejectedValue(new Error('network down'));

    render(<TurnstileField action="login" onToken={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('does not draw a widget into a container that unmounted while the script was still loading', async () => {
    let resolveScript!: (api: ReturnType<typeof makeFakeApi>) => void;
    mockLoadTurnstileScript.mockReturnValue(
      new Promise((resolve) => {
        resolveScript = resolve;
      })
    );
    const api = makeFakeApi();

    const { unmount } = render(<TurnstileField action="login" onToken={vi.fn()} />);
    unmount();
    await act(async () => {
      resolveScript(api);
    });

    expect(api.render).not.toHaveBeenCalled();
  });

  it('tears the widget down on unmount instead of leaking it for the page', async () => {
    const api = makeFakeApi();
    api.render.mockReturnValue('widget-1');
    mockLoadTurnstileScript.mockResolvedValue(api);
    const onToken = vi.fn();

    const { unmount } = render(<TurnstileField action="login" onToken={onToken} />);
    await waitFor(() => expect(api.render).toHaveBeenCalledTimes(1));

    unmount();

    expect(api.remove).toHaveBeenCalledWith('widget-1');
    expect(onToken).toHaveBeenLastCalledWith(null);
  });
});
