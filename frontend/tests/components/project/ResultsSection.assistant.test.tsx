import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, framerMotionMock } from '@tests/utils';
import { createProjectWithRole, createCalculationResult, createOpinion } from '@tests/factories/project';

vi.mock('framer-motion', () => framerMotionMock);

const mockOpenAssistant = vi.fn();

vi.mock('@/contexts/AssistantUIContext', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/contexts/AssistantUIContext')>()),
  useAssistantUI: () => ({
    isAvailable: true, isOpen: false, projectId: null,
    setAvailable: vi.fn(), setProjectScope: vi.fn(), openAssistant: mockOpenAssistant, closeAssistant: vi.fn(),
  }),
}));

async function renderResults() {
  const { ResultsSection } = await import('@/components/project');
  return render(
    <ResultsSection
      result={createCalculationResult()}
      project={createProjectWithRole({ id: 'project-42' })}
      showIndividual={false}
      setShowIndividual={vi.fn()}
      opinions={[createOpinion()]}
    />
  );
}

describe('ResultsSection assistant trigger (real slot + lazy chunk)', () => {
  beforeEach(() => {
    vi.resetModules();
    mockOpenAssistant.mockReset();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('renders no trigger in a build without the flag', async () => {
    vi.stubEnv('VITE_ASSISTANT_ENABLED', '');

    await renderResults();

    expect(screen.queryByRole('button', { name: 'Explain this result' })).not.toBeInTheDocument();
  });

  it("opens with this project's id once the lazy chunk resolves in a build with the flag", async () => {
    vi.stubEnv('VITE_ASSISTANT_ENABLED', 'true');
    const user = userEvent.setup();

    await renderResults();
    await user.click(await screen.findByRole('button', { name: 'Explain this result' }));

    expect(mockOpenAssistant).toHaveBeenCalledWith('project-42');
  });
});
