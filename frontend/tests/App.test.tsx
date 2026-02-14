import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import * as AuthContext from '@/contexts/AuthContext';

// Hoisted route control for BrowserRouter → MemoryRouter replacement
const routeRef = vi.hoisted(() => ({ value: '/' }));

// --- Mocks ---

// 1. Replace BrowserRouter with MemoryRouter for route control
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    BrowserRouter: ({ children }: { children: ReactNode }) => (
      <actual.MemoryRouter initialEntries={[routeRef.value]}>
        {children}
      </actual.MemoryRouter>
    ),
  };
});

// 2. Mock all 13 lazy-loaded pages as synchronous stubs
vi.mock('@/pages/Landing', () => ({ default: () => <div data-testid="landing" /> }));
vi.mock('@/pages/Login', () => ({ default: () => <div data-testid="login" /> }));
vi.mock('@/pages/Register', () => ({ default: () => <div data-testid="register" /> }));
vi.mock('@/pages/Projects', () => ({ default: () => <div data-testid="projects" /> }));
vi.mock('@/pages/ProjectDetail', () => ({ default: () => <div data-testid="project-detail" /> }));
vi.mock('@/pages/Profile', () => ({ default: () => <div data-testid="profile" /> }));
vi.mock('@/pages/CaseStudies', () => ({ default: () => <div data-testid="case-studies" /> }));
vi.mock('@/pages/CaseStudy', () => ({ default: () => <div data-testid="case-study" /> }));
vi.mock('@/pages/About', () => ({ default: () => <div data-testid="about" /> }));
vi.mock('@/pages/Documentation', () => ({ default: () => <div data-testid="documentation" /> }));
vi.mock('@/pages/FAQ', () => ({ default: () => <div data-testid="faq" /> }));
vi.mock('@/pages/Onboarding', () => ({ default: () => <div data-testid="onboarding" /> }));
vi.mock('@/pages/NotFound', () => ({ default: () => <div data-testid="not-found" /> }));

// 3. Mock AuthContext: passthrough provider + controllable useAuth
vi.mock('@/contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useAuth: vi.fn(),
}));

// 4. Mock UI providers as no-ops
vi.mock('@/components/ui/toaster', () => ({ Toaster: () => null }));
vi.mock('@/components/ui/sonner', () => ({ Toaster: () => null }));
vi.mock('@/components/ui/tooltip', () => ({
  TooltipProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));
vi.mock('@/components/RouteAnnouncer', () => ({ RouteAnnouncer: () => null }));

// 5. Mock i18next and lucide-react for PageLoader
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
vi.mock('lucide-react', () => ({ Loader2: () => null }));

import App from '@/App';

const mockUseAuth = vi.mocked(AuthContext.useAuth);

const unauthenticatedAuth = {
  isLoading: false,
  isAuthenticated: false,
  user: null,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  refreshUser: vi.fn(),
};

const authenticatedAuth = {
  isLoading: false,
  isAuthenticated: true,
  user: {
    id: '1',
    email: 'test@example.com',
    first_name: 'Test',
    last_name: null,
    photo_url: null,
    created_at: '2024-01-01T00:00:00Z',
  },
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  refreshUser: vi.fn(),
};

describe('App - public routes', () => {
  beforeEach(() => {
    routeRef.value = '/';
    mockUseAuth.mockReturnValue(unauthenticatedAuth);
  });

  it('renders Landing page at /', async () => {
    routeRef.value = '/';
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('landing')).toBeInTheDocument();
    });
  });

  it('renders About page at /about', async () => {
    routeRef.value = '/about';
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('about')).toBeInTheDocument();
    });
  });

  it('renders Login page at /login', async () => {
    routeRef.value = '/login';
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('login')).toBeInTheDocument();
    });
  });

  it('renders Register page at /register', async () => {
    routeRef.value = '/register';
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('register')).toBeInTheDocument();
    });
  });

  it('renders Documentation page at /docs', async () => {
    routeRef.value = '/docs';
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('documentation')).toBeInTheDocument();
    });
  });

  it('renders FAQ page at /faq', async () => {
    routeRef.value = '/faq';
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('faq')).toBeInTheDocument();
    });
  });

  it('renders CaseStudies page at /case-studies', async () => {
    routeRef.value = '/case-studies';
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('case-studies')).toBeInTheDocument();
    });
  });

  it('renders CaseStudy page at /case-study/:id', async () => {
    routeRef.value = '/case-study/1';
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('case-study')).toBeInTheDocument();
    });
  });

  it('renders NotFound for unknown routes', async () => {
    routeRef.value = '/unknown-path';
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('not-found')).toBeInTheDocument();
    });
  });
});

describe('App - protected routes', () => {
  it('redirects to login when unauthenticated', async () => {
    mockUseAuth.mockReturnValue(unauthenticatedAuth);
    routeRef.value = '/projects';
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('login')).toBeInTheDocument();
    });
  });

  it('renders protected page when authenticated', async () => {
    mockUseAuth.mockReturnValue(authenticatedAuth);
    routeRef.value = '/projects';
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('projects')).toBeInTheDocument();
    });
  });

  it('renders ProjectDetail when authenticated', async () => {
    mockUseAuth.mockReturnValue(authenticatedAuth);
    routeRef.value = '/projects/1';
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('project-detail')).toBeInTheDocument();
    });
  });

  it('renders Profile when authenticated', async () => {
    mockUseAuth.mockReturnValue(authenticatedAuth);
    routeRef.value = '/profile';
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('profile')).toBeInTheDocument();
    });
  });

  it('renders Onboarding when authenticated', async () => {
    mockUseAuth.mockReturnValue(authenticatedAuth);
    routeRef.value = '/onboarding';
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('onboarding')).toBeInTheDocument();
    });
  });
});
