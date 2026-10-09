import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { HeaderTrigger, ResultTrigger } from '@/components/assistant/triggers';

const mockOpenAssistant = vi.fn();
let mockState = { isAvailable: true, projectId: null as string | null };

vi.mock('@/contexts/AssistantUIContext', () => ({
  useAssistantUI: () => ({ ...mockState, openAssistant: mockOpenAssistant }),
}));

describe('triggers', () => {
  beforeEach(() => {
    mockOpenAssistant.mockReset();
    mockState = { isAvailable: true, projectId: null };
  });

  it('HeaderTrigger opens the panel with no project when the page has none', async () => {
    const user = userEvent.setup();
    render(<HeaderTrigger />);

    const button = screen.getByRole('button', { name: 'Assistant' });
    await user.click(button);

    expect(button).toHaveAttribute('title', 'Assistant');
    expect(mockOpenAssistant).toHaveBeenCalledWith(undefined);
  });

  it('HeaderTrigger opens the panel for the project the page registered', async () => {
    mockState.projectId = 'project-42';
    const user = userEvent.setup();
    render(<HeaderTrigger />);

    await user.click(screen.getByRole('button', { name: 'Assistant' }));

    expect(mockOpenAssistant).toHaveBeenCalledWith('project-42');
  });

  it('ResultTrigger opens the panel with the given project id', async () => {
    const user = userEvent.setup();
    render(<ResultTrigger projectId="project-42" />);

    await user.click(screen.getByRole('button', { name: 'Explain this result' }));

    expect(mockOpenAssistant).toHaveBeenCalledWith('project-42');
  });

  it('render nothing while the backend is unavailable', () => {
    mockState.isAvailable = false;

    const { container: header } = render(<HeaderTrigger />);
    const { container: result } = render(<ResultTrigger projectId="p1" />);

    expect(header).toBeEmptyDOMElement();
    expect(result).toBeEmptyDOMElement();
  });
});
