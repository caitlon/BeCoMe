import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, framerMotionMock } from '@tests/utils';
import { ResultsSection } from '@/components/project';
import {
  createProjectWithRole,
  createOpinion,
  createCalculationResult,
} from '@tests/factories/project';

const { mockApi, mockToast, mockDownloadBlob } = vi.hoisted(() => ({
  mockApi: {
    exportProjectResult: vi.fn(),
  },
  mockToast: vi.fn(),
  mockDownloadBlob: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    api: mockApi,
    HttpError: actual.HttpError,
  };
});

vi.mock('@/lib/download', () => ({
  downloadBlob: mockDownloadBlob,
  downloadJson: vi.fn(),
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

vi.mock('framer-motion', () => framerMotionMock);

const setup = () => {
  const project = createProjectWithRole({ id: 'project-1', name: 'Test Project' });
  const opinions = [createOpinion({ user_id: 'other' })];
  return { project, opinions };
};

describe('ResultsSection - Empty State', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows "no results" message when no opinions', () => {
    const { project } = setup();

    render(<ResultsSection result={null} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={[]} />);

    expect(screen.getByText(/results will appear once experts submit/i)).toBeInTheDocument();
  });
});

describe('ResultsSection - Results Display', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('displays calculation results when available', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('Best Compromise')).toBeInTheDocument();
  });

  it('shows agreement badge with results', () => {
    // max_error=12.5, scale 0-100, errorPercent=12.5% → "High agreement"
    const { project, opinions } = setup();
    const result = createCalculationResult({ max_error: 12.5 });

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('High agreement')).toBeInTheDocument();
  });

  it('shows moderate agreement for medium error', () => {
    // max_error=30, scale 0-100, errorPercent=30% → "Moderate agreement"
    const { project, opinions } = setup();
    const result = createCalculationResult({ max_error: 30 });

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('Moderate agreement')).toBeInTheDocument();
  });

  it('shows low agreement for high error', () => {
    // max_error=50, scale 0-100, errorPercent=50% → "Low agreement"
    const { project, opinions } = setup();
    const result = createCalculationResult({ max_error: 50 });

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByText('Low agreement')).toBeInTheDocument();
  });

  it('toggles individual opinions visibility via checkbox', async () => {
    const user = userEvent.setup();
    const { project, opinions } = setup();
    const result = createCalculationResult();
    const setShowIndividual = vi.fn();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={setShowIndividual} opinions={opinions} />);

    const checkbox = screen.getByRole('checkbox', { name: /individual/i });
    expect(checkbox).not.toBeChecked();

    await user.click(checkbox);
    expect(setShowIndividual).toHaveBeenCalledWith(true);
  });

  it('renders visualization tabs (Triangle and Centroid)', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByRole('tab', { name: /triangle/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /centroid/i })).toBeInTheDocument();
  });
});

describe('ResultsSection - Result Export', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the export dropdown trigger when results are available', () => {
    const { project, opinions } = setup();
    const result = createCalculationResult();

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument();
  });

  it('exports the result as PDF and downloads the file', async () => {
    const user = userEvent.setup();
    const { project, opinions } = setup();
    const result = createCalculationResult();
    mockApi.exportProjectResult.mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' }));

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    await user.click(screen.getByRole('button', { name: /export/i }));
    const pdfItem = await screen.findByRole('menuitem', { name: /pdf report/i });
    await user.click(pdfItem);

    expect(mockApi.exportProjectResult).toHaveBeenCalledWith('project-1', 'pdf', 'en');
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'test-project-results.pdf');
    expect(mockToast).toHaveBeenCalledWith({ title: 'Export downloaded' });
  });

  it('shows an error toast when the export fails', async () => {
    const user = userEvent.setup();
    const { project, opinions } = setup();
    const result = createCalculationResult();
    mockApi.exportProjectResult.mockRejectedValue(new Error('Export boom'));

    render(<ResultsSection result={result} project={project} showIndividual={false} setShowIndividual={vi.fn()} opinions={opinions} />);

    await user.click(screen.getByRole('button', { name: /export/i }));
    const csvItem = await screen.findByRole('menuitem', { name: /csv data/i });
    await user.click(csvItem);

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Error',
        description: 'Export boom',
        variant: 'destructive',
      }),
    );
  });
});
