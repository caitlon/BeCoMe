import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import i18n from '@/i18n';
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

  describe('state in words', () => {
    const itemText = (label: string) => screen.getByText(label).parentElement;

    it('says in English whether each requirement is met', () => {
      render(<ValidationChecklist requirements={baseRequirements} />);

      expect(itemText('At least 8 characters')).toHaveTextContent(
        'At least 8 characters not met'
      );
      expect(itemText('Contains uppercase letter')).toHaveTextContent(
        'Contains uppercase letter met'
      );
    });

    it('says in Czech whether each requirement is met', async () => {
      await i18n.changeLanguage('cs');
      try {
        const { unmount } = render(<ValidationChecklist requirements={baseRequirements} />);

        expect(itemText('At least 8 characters')).toHaveTextContent(
          'At least 8 characters nesplněno'
        );
        expect(itemText('Contains uppercase letter')).toHaveTextContent(
          'Contains uppercase letter splněno'
        );

        // Unmount before reverting the language so the change below does not
        // re-render this already-asserted list outside act().
        unmount();
      } finally {
        await i18n.changeLanguage('en');
      }
    });

    it('switches an item from not met to met when the rule becomes met', () => {
      const { rerender } = render(<ValidationChecklist requirements={baseRequirements} />);

      expect(itemText('Contains number')).toHaveTextContent('Contains number not met');

      rerender(
        <ValidationChecklist
          requirements={baseRequirements.map((req) =>
            req.label === 'Contains number' ? { ...req, met: true } : req
          )}
        />
      );

      expect(itemText('Contains number')).toHaveTextContent('Contains number met');
      expect(itemText('Contains number')).not.toHaveTextContent('not met');
    });

    it('keeps the state text out of sight', () => {
      render(<ValidationChecklist requirements={baseRequirements} />);

      const state = itemText('Contains number')?.querySelector('.sr-only');
      expect(state).toHaveTextContent('not met');
    });
  });

  it('puts the given id on the list so a field can reference it', () => {
    render(<ValidationChecklist id="rules" requirements={baseRequirements} />);

    expect(document.getElementById('rules')).toContainElement(
      screen.getByText('Contains number')
    );
  });
});
