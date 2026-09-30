import { Suspense, use } from 'react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@tests/utils'
import { PageLoader } from '@/components/PageLoader'

function Page() {
  return (
    <main id="main-content" tabIndex={-1}>
      <h1>The page</h1>
    </main>
  )
}

function LazyPage({ loaded }: { readonly loaded: Promise<void> }) {
  use(loaded)
  return <Page />
}

const nextFrame = () => new Promise((resolve) => requestAnimationFrame(resolve))

describe('PageLoader', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders a focusable main#main-content around the spinner', () => {
    render(<PageLoader />)

    const main = screen.getByRole('main')
    expect(main).toHaveAttribute('id', 'main-content')
    expect(main).toHaveAttribute('tabindex', '-1')
    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument()
  })

  it('gives up the id while Suspense keeps it hidden, and takes it back when shown again', async () => {
    let release: () => void = () => {}
    const pending = new Promise<void>((resolve) => {
      release = resolve
    })
    function Slow() {
      use(pending)
      return <p>Loaded</p>
    }
    const tree = (withSlow: boolean) => (
      <Suspense fallback={<p>Fallback</p>}>
        <PageLoader />
        {withSlow && <Slow />}
      </Suspense>
    )

    const { rerender, container } = render(tree(false))
    expect(container.querySelector('main#main-content')).toBeInTheDocument()

    // The boundary already shows content, so it hides it rather than unmounting it.
    await act(async () => {
      rerender(tree(true))
    })
    await act(() => new Promise((resolve) => setTimeout(resolve, 400)))
    expect(screen.getByText('Fallback')).toBeInTheDocument()
    expect(container.querySelector('main')).not.toBeVisible()
    expect(container.querySelector('main#main-content')).not.toBeInTheDocument()

    await act(async () => {
      release()
    })
    expect(await screen.findByText('Loaded')).toBeInTheDocument()
    expect(container.querySelector('main#main-content')).toBeVisible()
  })

  it('hands focus to the new main when it is replaced while it holds focus', async () => {
    const { rerender } = render(<PageLoader />)
    act(() => screen.getByRole('main').focus())
    expect(screen.getByRole('main')).toHaveFocus()

    rerender(<Page />)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'The page' }).parentElement).toHaveFocus()
    })
  })

  it('hands focus over when Suspense hides the placeholder instead of removing it', async () => {
    let finishLoading = () => {}
    const loaded = new Promise<void>((resolve) => {
      finishLoading = resolve
    })
    const { rerender } = render(
      <Suspense fallback={<PageLoader />}>
        <PageLoader />
      </Suspense>,
    )
    act(() => screen.getByRole('main').focus())

    // The content already on screen suspends, so React hides it and shows the fallback.
    await act(async () => {
      rerender(
        <Suspense fallback={<PageLoader />}>
          <LazyPage loaded={loaded} />
        </Suspense>,
      )
    })
    await act(nextFrame)
    await act(async () => finishLoading())

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'The page' }).parentElement).toHaveFocus()
    })
  })

  it('does not move focus when it did not hold focus', async () => {
    const focus = vi.spyOn(HTMLElement.prototype, 'focus')
    const { rerender } = render(<PageLoader />)

    rerender(<Page />)
    await act(nextFrame)

    expect(focus).not.toHaveBeenCalled()
    expect(document.body).toHaveFocus()
  })

  it('leaves focus alone when the user moved it elsewhere before the swap settled', async () => {
    const { rerender } = render(
      <>
        <button>Elsewhere</button>
        <PageLoader />
      </>,
    )
    act(() => screen.getByRole('main').focus())

    rerender(
      <>
        <button>Elsewhere</button>
        <Page />
      </>,
    )
    act(() => screen.getByRole('button', { name: 'Elsewhere' }).focus())
    await act(nextFrame)

    expect(screen.getByRole('button', { name: 'Elsewhere' })).toHaveFocus()
  })
})
