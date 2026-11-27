import { describe, it, expect, afterEach } from 'vitest';
import { render, screen } from '@tests/utils';
import i18n from '@/i18n';
import { AssistantMessage } from '@/components/assistant/AssistantMessage';
import type { AssistantMessage as Message } from '@/components/assistant/useAssistantChat';
import '@/components/assistant/i18n';

const base: Message = {
  id: 'm1',
  role: 'assistant',
  content: 'The answer is 42.',
  status: 'done',
  createdAt: 1,
};

const passing = { citations_valid: true, numbers_grounded: true, ungrounded_numbers: [] };

function renderChecks(checks: unknown) {
  return render(
    <AssistantMessage message={{ ...base, checks: checks as Message['checks'] }} projectScoped />
  );
}

describe('AssistantMessage name-number lines', () => {
  afterEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('shows one line per list with its numbers', () => {
    renderChecks({ ...passing, project_name_numbers: ['2026', '3'], expert_name_numbers: ['7'] });

    expect(screen.getByText('From the project name, not the data: 2026, 3')).toBeInTheDocument();
    expect(screen.getByText("From an expert's name, not the data: 7")).toBeInTheDocument();
  });

  it('shows only the list that is not empty', () => {
    renderChecks({ ...passing, project_name_numbers: ['2026'], expert_name_numbers: [] });

    expect(screen.getByText('From the project name, not the data: 2026')).toBeInTheDocument();
    expect(screen.queryByText(/From an expert's name/)).not.toBeInTheDocument();
  });

  it.each([
    ['absent', {}],
    ['empty', { project_name_numbers: [], expert_name_numbers: [] }],
    ['not arrays', { project_name_numbers: '2026', expert_name_numbers: { 0: '7' } }],
    ['null', { project_name_numbers: null, expert_name_numbers: null }],
  ])('renders no name-number line when the lists are %s', (_label, lists) => {
    renderChecks({ ...passing, ...lists });

    expect(screen.queryByText(/not the data/)).not.toBeInTheDocument();
  });

  it('keeps the warning line next to the name-number lines', () => {
    renderChecks({
      citations_valid: true,
      numbers_grounded: false,
      ungrounded_numbers: ['17'],
      project_name_numbers: ['2026'],
      expert_name_numbers: ['7'],
    });

    expect(screen.getByText('Numbers not confirmed by the sources: 17')).toBeInTheDocument();
    expect(screen.getByText('From the project name, not the data: 2026')).toBeInTheDocument();
    expect(screen.getByText("From an expert's name, not the data: 7")).toBeInTheDocument();
  });

  it('does not style the lines as warnings', () => {
    renderChecks({
      citations_valid: false,
      numbers_grounded: false,
      ungrounded_numbers: ['17'],
      project_name_numbers: ['2026'],
      expert_name_numbers: ['7'],
    });

    const warning = screen.getByText('Numbers not confirmed by the sources: 17').closest('p');
    expect(warning).toHaveClass('text-warning');
    for (const text of ['From the project name, not the data: 2026', "From an expert's name, not the data: 7"]) {
      const line = screen.getByText(text).closest('p');
      expect(line).toHaveClass('text-foreground');
      expect(line).not.toHaveClass('text-warning');
      expect(line).not.toHaveClass('text-muted-foreground');
      expect(line?.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    }
  });

  it('shows the lines in Czech', async () => {
    await i18n.changeLanguage('cs');
    renderChecks({ ...passing, project_name_numbers: ['2026'], expert_name_numbers: ['7'] });

    expect(screen.getByText('Z názvu projektu, ne z dat: 2026')).toBeInTheDocument();
    expect(screen.getByText('Z jména experta, ne z dat: 7')).toBeInTheDocument();
  });
});
