import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import { ValidationChecklist, Requirement } from '@/components/forms/ValidationChecklist';

describe('ValidationChecklist', () => {
  const baseRequirements: Requirement[] = [
    { label: 'At least 8 characters', met: false },
    { label: 'Contains uppercase letter', met: true },
    { label: 'Contains number', met: false },
  ];

  it('renders nothing when show is false', () => {
    const { container } = render(
      <ValidationChecklist requirements={baseRequirements} show={false} />
    );

    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when all requirements are met', () => {
    const allMet: Requirement[] = [
      { label: 'Requirement 1', met: true },
      { label: 'Requirement 2', met: true },
    ];

    const { container } = render(
      <ValidationChecklist requirements={allMet} show={true} />
    );

    expect(container.firstChild).toBeNull();
  });

  it('renders title when provided', () => {
    render(
      <ValidationChecklist
        title="Password requirements:"
        requirements={baseRequirements}
        show={true}
      />
    );

    expect(screen.getByText('Password requirements:')).toBeInTheDocument();
  });

  it('renders all requirements', () => {
    render(<ValidationChecklist requirements={baseRequirements} show={true} />);

    expect(screen.getByText('At least 8 characters')).toBeInTheDocument();
    expect(screen.getByText('Contains uppercase letter')).toBeInTheDocument();
    expect(screen.getByText('Contains number')).toBeInTheDocument();
  });

  it('shows checkmark icon for met requirements', () => {
    const requirements: Requirement[] = [{ label: 'Met requirement', met: true }];

    render(
      <ValidationChecklist
        requirements={[...requirements, { label: 'Unmet', met: false }]}
        show={true}
      />
    );

    // Met requirements have success color
    const metItem = screen.getByText('Met requirement').parentElement;
    expect(metItem).toHaveClass('text-success');
  });

  it('shows X icon for unmet requirements', () => {
    render(<ValidationChecklist requirements={baseRequirements} show={true} />);

    const unmetItem = screen.getByText('At least 8 characters').parentElement;
    expect(unmetItem).toHaveClass('text-muted-foreground');
  });

  it('defaults show to true', () => {
    render(<ValidationChecklist requirements={baseRequirements} />);

    expect(screen.getByText('At least 8 characters')).toBeInTheDocument();
  });
});
