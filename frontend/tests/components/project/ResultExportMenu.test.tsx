import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { ResultExportMenu } from '@/components/project';
import { createProjectWithRole } from '@tests/factories/project';
import i18n from '@/i18n';

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

const setup = () => createProjectWithRole({ id: 'project-1', name: 'Test Project' });

describe('ResultExportMenu', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the export dropdown trigger', () => {
    const project = setup();

    render(<ResultExportMenu project={project} />);

    expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument();
  });

  it('exports the result as PDF and downloads the file', async () => {
    const user = userEvent.setup();
    const project = setup();
    mockApi.exportProjectResult.mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' }));

    render(<ResultExportMenu project={project} />);

    await user.click(screen.getByRole('button', { name: /export/i }));
    const pdfItem = await screen.findByRole('menuitem', { name: /pdf report/i });
    await user.click(pdfItem);

    expect(mockApi.exportProjectResult).toHaveBeenCalledWith('project-1', 'pdf', 'en');
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'test-project-results.pdf');
    expect(mockToast).toHaveBeenCalledWith({ title: 'Export downloaded' });
  });

  it('exports the result as CSV and downloads the file', async () => {
    const user = userEvent.setup();
    const project = setup();
    mockApi.exportProjectResult.mockResolvedValue(new Blob(['csv'], { type: 'text/csv' }));

    render(<ResultExportMenu project={project} />);

    await user.click(screen.getByRole('button', { name: /export/i }));
    const csvItem = await screen.findByRole('menuitem', { name: /csv data/i });
    await user.click(csvItem);

    expect(mockApi.exportProjectResult).toHaveBeenCalledWith('project-1', 'csv', 'en');
    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'test-project-results.csv');
    expect(mockToast).toHaveBeenCalledWith({ title: 'Export downloaded' });
  });

  it('shows an error toast when the export fails with an Error', async () => {
    const user = userEvent.setup();
    const project = setup();
    mockApi.exportProjectResult.mockRejectedValue(new Error('Export boom'));

    render(<ResultExportMenu project={project} />);

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

  it('exports using the Czech language code when the UI language is Czech', async () => {
    const user = userEvent.setup();
    const project = setup();
    mockApi.exportProjectResult.mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' }));

    await i18n.changeLanguage('cs');
    try {
      render(<ResultExportMenu project={project} />);

      await user.click(screen.getByRole('button', { name: /export/i }));
      const pdfItem = await screen.findByRole('menuitem', { name: /pdf/i });
      await user.click(pdfItem);

      expect(mockApi.exportProjectResult).toHaveBeenCalledWith('project-1', 'pdf', 'cs');
    } finally {
      await i18n.changeLanguage('en');
    }
  });

  it('falls back to a generic filename when the project name has no alphanumeric characters', async () => {
    const user = userEvent.setup();
    const project = createProjectWithRole({ id: 'project-1', name: '!!!' });
    mockApi.exportProjectResult.mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' }));

    render(<ResultExportMenu project={project} />);

    await user.click(screen.getByRole('button', { name: /export/i }));
    const pdfItem = await screen.findByRole('menuitem', { name: /pdf report/i });
    await user.click(pdfItem);

    expect(mockDownloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'project-results.pdf');
  });

  it('shows a generic error message when the export rejects with a non-Error value', async () => {
    const user = userEvent.setup();
    const project = setup();
    mockApi.exportProjectResult.mockRejectedValue('boom');

    render(<ResultExportMenu project={project} />);

    await user.click(screen.getByRole('button', { name: /export/i }));
    const pdfItem = await screen.findByRole('menuitem', { name: /pdf report/i });
    await user.click(pdfItem);

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Error',
        description: 'Failed to export results',
        variant: 'destructive',
      }),
    );
  });
});
