import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import { FolderPlus } from 'lucide-react';
import { StepHeader } from '@/components/onboarding/StepHeader';

vi.mock('framer-motion', () => framerMotionMock);

describe('StepHeader', () => {
  it('renders heading with translated title', () => {
    render(
      <StepHeader
        icon={FolderPlus}
        titleKey="steps.createProject.title"
        descriptionKey="steps.createProject.description"
      />
    );

    expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument();
  });

  it('renders description paragraph', () => {
    render(
      <StepHeader
        icon={FolderPlus}
        titleKey="steps.createProject.title"
        descriptionKey="steps.createProject.description"
      />
    );

    expect(screen.getByRole('paragraph')).toBeInTheDocument();
  });

  it('renders icon SVG', () => {
    const { container } = render(
      <StepHeader
        icon={FolderPlus}
        titleKey="steps.createProject.title"
        descriptionKey="steps.createProject.description"
      />
    );

    expect(container.querySelector('svg')).toBeInTheDocument();
  });
});
