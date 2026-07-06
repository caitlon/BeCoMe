import { useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { OpinionForm } from '@/components/project';
import { createProjectWithRole, createOpinion } from '@tests/factories/project';
import type { Opinion } from '@/types/api';

/**
 * OpinionForm is fully controlled: it receives `position`/`lower`/`peak`/`upper`
 * plus their setters as props. This harness owns the state so the component can
 * be exercised in isolation, the same way ProjectDetail owns it in production.
 */
function Harness({
  myOpinion,
  isSaving = false,
  onSave = vi.fn(),
  onDelete = vi.fn(),
  initialPosition = '',
  initialLower = '',
  initialPeak = '',
  initialUpper = '',
}: {
  myOpinion?: Opinion;
  isSaving?: boolean;
  onSave?: () => void;
  onDelete?: () => void;
  initialPosition?: string;
  initialLower?: string;
  initialPeak?: string;
  initialUpper?: string;
}) {
  const [position, setPosition] = useState(initialPosition);
  const [lower, setLower] = useState(initialLower);
  const [peak, setPeak] = useState(initialPeak);
  const [upper, setUpper] = useState(initialUpper);
  const project = createProjectWithRole({ scale_min: 0, scale_max: 100, scale_unit: '%' });

  return (
    <OpinionForm
      position={position}
      setPosition={setPosition}
      lower={lower}
      setLower={setLower}
      peak={peak}
      setPeak={setPeak}
      upper={upper}
      setUpper={setUpper}
      project={project}
      myOpinion={myOpinion}
      isSaving={isSaving}
      onSave={onSave}
      onDelete={onDelete}
    />
  );
}

describe('OpinionForm - Save/Update Button', () => {
  it('shows save button when no opinion exists', () => {
    render(<Harness />);

    expect(screen.getByRole('button', { name: 'Save Opinion' })).toBeInTheDocument();
  });

  it('shows update button when user has existing opinion', () => {
    const myOpinion = createOpinion({
      user_id: 'user-1',
      lower_bound: 20,
      peak: 50,
      upper_bound: 80,
      position: 'Manager',
    });

    render(
      <Harness
        myOpinion={myOpinion}
        initialPosition="Manager"
        initialLower="20"
        initialPeak="50"
        initialUpper="80"
      />
    );

    expect(screen.getByRole('button', { name: 'Update Opinion' })).toBeInTheDocument();
  });

  it('disables update button when opinion values unchanged', () => {
    const myOpinion = createOpinion({
      user_id: 'user-1',
      position: 'Manager',
      lower_bound: 20,
      peak: 50,
      upper_bound: 80,
    });

    render(
      <Harness
        myOpinion={myOpinion}
        initialPosition="Manager"
        initialLower="20"
        initialPeak="50"
        initialUpper="80"
      />
    );

    expect(screen.getByRole('button', { name: 'Update Opinion' })).toBeDisabled();
  });

  it('disables save button when position is empty', () => {
    render(<Harness initialLower="20" initialPeak="50" initialUpper="80" />);

    expect(screen.getByRole('button', { name: 'Save Opinion' })).toBeDisabled();
  });
});

describe('OpinionForm - Delete Opinion Link', () => {
  it('shows delete opinion link when user has opinion', () => {
    const myOpinion = createOpinion({ user_id: 'user-1' });

    render(<Harness myOpinion={myOpinion} />);

    expect(screen.getByText('Delete my opinion')).toBeInTheDocument();
  });

  it('does not show delete opinion link when user has no opinion', () => {
    render(<Harness />);

    expect(screen.queryByText('Delete my opinion')).not.toBeInTheDocument();
  });
});

describe('OpinionForm - Form Inputs', () => {
  it('updates position input value on change', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const positionInput = screen.getByLabelText('Position');
    await user.type(positionInput, 'Director');

    expect(positionInput).toHaveValue('Director');
  });

  it('updates lower bound input value on change', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const lowerInput = screen.getByLabelText(/lower/i);
    await user.type(lowerInput, '25');

    expect(lowerInput).toHaveValue(25);
  });

  it('updates peak input value on change', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const peakInput = screen.getByLabelText(/peak/i);
    await user.type(peakInput, '50');

    expect(peakInput).toHaveValue(50);
  });

  it('updates upper bound input value on change', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const upperInput = screen.getByLabelText(/upper/i);
    await user.type(upperInput, '75');

    expect(upperInput).toHaveValue(75);
  });
});

describe('OpinionForm - Hint Messages', () => {
  it('shows position required hint when position is empty', () => {
    render(<Harness />);

    expect(screen.getByText('Enter your position to save')).toBeInTheDocument();
  });

  it('shows fill fields hint when position filled but values empty', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByLabelText('Position'), 'Manager');

    expect(screen.getByText('Fill in all estimate fields')).toBeInTheDocument();
  });

  it('shows no changes hint when existing opinion values unchanged', () => {
    const myOpinion = createOpinion({
      user_id: 'user-1',
      position: 'Manager',
      lower_bound: 20,
      peak: 50,
      upper_bound: 80,
    });

    render(
      <Harness
        myOpinion={myOpinion}
        initialPosition="Manager"
        initialLower="20"
        initialPeak="50"
        initialUpper="80"
      />
    );

    expect(screen.getByText('No changes to save')).toBeInTheDocument();
  });
});
