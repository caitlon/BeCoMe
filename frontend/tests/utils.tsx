import { ReactElement, ReactNode } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { MemoryRouter, MemoryRouterProps } from 'react-router-dom'
import { I18nextProvider } from 'react-i18next'
import i18n from '@/i18n'
import { User } from '@/types/api'

/**
 * Mock AuthContext value for testing.
 * Allows controlling auth state in component tests.
 */
export interface MockAuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: ReturnType<typeof import('vitest').vi.fn>;
  register: ReturnType<typeof import('vitest').vi.fn>;
  logout: ReturnType<typeof import('vitest').vi.fn>;
  refreshUser: ReturnType<typeof import('vitest').vi.fn>;
}

/**
 * Extended render options for testing.
 */
export interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  initialEntries?: MemoryRouterProps['initialEntries'];
  wrapper?: RenderOptions['wrapper'];
}

function AllTheProviders({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <I18nextProvider i18n={i18n}>
        {children}
      </I18nextProvider>
    </MemoryRouter>
  )
}

/**
 * Creates a wrapper with custom router initial entries.
 */
function createWrapper(initialEntries?: MemoryRouterProps['initialEntries']) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter
        initialEntries={initialEntries}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <I18nextProvider i18n={i18n}>
          {children}
        </I18nextProvider>
      </MemoryRouter>
    )
  }
}

/**
 * Custom render function with providers.
 * Use initialEntries to set the initial route.
 */
const customRender = (
  ui: ReactElement,
  options?: CustomRenderOptions
) => {
  const { initialEntries, ...renderOptions } = options ?? {}
  const wrapper = renderOptions.wrapper ?? (initialEntries ? createWrapper(initialEntries) : AllTheProviders)
  return render(ui, { wrapper, ...renderOptions })
}

/**
 * Filters out framer-motion props from a component's props.
 * Used in framer-motion mocks to prevent React warnings about unknown DOM props.
 * Preserves all non-motion props including aria-*, data-*, etc.
 */
export const filterMotionProps = (props: Record<string, unknown>) => {
  const motionProps = new Set(['initial', 'animate', 'exit', 'variants', 'transition', 'whileHover', 'whileTap', 'whileInView', 'viewport', 'custom', 'layout', 'layoutId', 'onAnimationComplete']);
  const filtered: Record<string, unknown> = {};
  for (const key of Object.keys(props)) {
    if (!motionProps.has(key)) {
      filtered[key] = props[key];
    }
  }
  return filtered;
};

/**
 * Shared framer-motion mock factory.
 * Usage: vi.mock('framer-motion', () => framerMotionMock);
 *
 * Covers all motion elements used across the app:
 * div, section, nav, span, h1, h2, p, polygon, circle, line.
 */
const makeMotionComponent = (Tag: string) => {
  const Component = ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
    const filtered = filterMotionProps(props);
    return <Tag {...filtered}>{children}</Tag>;
  };
  Component.displayName = `motion.${Tag}`;
  return Component;
};

const makeMotionVoidComponent = (Tag: string) => {
  const Component = (props: Record<string, unknown>) => {
    const filtered = filterMotionProps(props);
    return <Tag {...filtered} />;
  };
  Component.displayName = `motion.${Tag}`;
  return Component;
};

export const framerMotionMock = {
  motion: {
    div: makeMotionComponent('div'),
    section: makeMotionComponent('section'),
    nav: makeMotionComponent('nav'),
    span: makeMotionComponent('span'),
    h1: makeMotionComponent('h1'),
    h2: makeMotionComponent('h2'),
    p: makeMotionComponent('p'),
    polygon: makeMotionVoidComponent('polygon'),
    circle: makeMotionVoidComponent('circle'),
    line: makeMotionVoidComponent('line'),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren<object>) => <>{children}</>,
};

export * from '@testing-library/react'
export { customRender as render }
