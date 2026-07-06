import { describe, it, expect, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { OpinionForm, useOpinionForm, OpinionFormOutput } from '@/components/project';
import { createProjectWithRole, createOpinion } from '@tests/factories/project';
import type { Opinion } from '@/types/api';

/**
 * OpinionForm receives its react-hook-form instance from the page container
 * (the form renders twice there — desktop column and mobile tab — and both
 * copies share one set of values). This harness recreates that wiring.
 */
function Harness({
  myOpinion,
  isSaving = false,
  onSubmit = vi.fn(),
  onDelete = vi.fn(),
}: {
  myOpinion?: Opinion;
  isSaving?: boolean;
  onSubmit?: (values: OpinionFormOutput) => Promise<void>;
  onDelete?: () => void;
}) {
  const project = createProjectWithRole({ scale_min: 0, scale_max: 100, scale_unit: '%' });
  const form = useOpinionForm(project, myOpinion);

  return (
    <OpinionForm
      form={form}
      project={project}
      myOpinion={myOpinion}
      isSaving={isSaving}
      onSubmit={onSubmit}
      onDelete={onDelete}
    />
  );
}

const existingOpinion = () =>
  createOpinion({
    user_id: 'user-1',
    position: 'Manager',
    lower_bound: 20,
    peak: 50,
    upper_bound: 80,
  });

describe('OpinionForm - Save/Update Button', () => {
  it('shows save button when no opinion exists', () => {
    render(<Harness />);

    expect(screen.getByRole('button', { name: 'Save Opinion' })).toBeInTheDocument();
  });

  it('shows update button when user has existing opinion', () => {
    render(<Harness myOpinion={existingOpinion()} />);

    expect(screen.getByRole('button', { name: 'Update Opinion' })).toBeInTheDocument();
  });

  it('disables update button when opinion values unchanged', () => {
    render(<Harness myOpinion={existingOpinion()} />);

    expect(screen.getByRole('button', { name: 'Update Opinion' })).toBeDisabled();
  });

  it('enables update button after editing a value', async () => {
    const user = userEvent.setup();
    render(<Harness myOpinion={existingOpinion()} />);

    const peakInput = screen.getByLabelText(/peak/i);
    await user.clear(peakInput);
    await user.type(peakInput, '55');

    expect(screen.getByRole('button', { name: 'Update Opinion' })).toBeEnabled();
  });

  it('disables save button when position is empty', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByLabelText(/lower/i), '20');
    await user.type(screen.getByLabelText(/peak/i), '50');
    await user.type(screen.getByLabelText(/upper/i), '80');

    expect(screen.getByRole('button', { name: 'Save Opinion' })).toBeDisabled();
  });
});

describe('OpinionForm - Submission', () => {
  it('passes parsed numeric values to onSubmit', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<Harness onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText('Position'), 'Director');
    await user.type(screen.getByLabelText(/lower/i), '20');
    await user.type(screen.getByLabelText(/peak/i), '50');
    await user.type(screen.getByLabelText(/upper/i), '80');
    await user.click(screen.getByRole('button', { name: 'Save Opinion' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        { position: 'Director', lower: 20, peak: 50, upper: 80 },
        expect.anything()
      );
    });
  });

  it('does not call onSubmit when ordering is invalid', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<Harness onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText('Position'), 'Director');
    await user.type(screen.getByLabelText(/lower/i), '60');
    await user.type(screen.getByLabelText(/peak/i), '50');
    await user.type(screen.getByLabelText(/upper/i), '80');
    await user.click(screen.getByRole('button', { name: 'Save Opinion' }));

    await waitFor(() => {
      expect(screen.getByText('Values must satisfy: lower ≤ peak ≤ upper')).toBeInTheDocument();
    });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('shows a scale-range error for out-of-range values', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<Harness onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText('Position'), 'Director');
    await user.type(screen.getByLabelText(/lower/i), '10');
    await user.type(screen.getByLabelText(/peak/i), '50');
    await user.type(screen.getByLabelText(/upper/i), '150');
    await user.click(screen.getByRole('button', { name: 'Save Opinion' }));

    await waitFor(() => {
      expect(screen.getByText('Values must be within scale range: 0 — 100')).toBeInTheDocument();
    });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('marks the invalid field with aria-invalid', async () => {
    const user = userEvent.setup();
    render(<Harness onSubmit={vi.fn().mockResolvedValue(undefined)} />);

    await user.type(screen.getByLabelText('Position'), 'Director');
    await user.type(screen.getByLabelText(/lower/i), '60');
    await user.type(screen.getByLabelText(/peak/i), '50');
    await user.type(screen.getByLabelText(/upper/i), '80');
    await user.click(screen.getByRole('button', { name: 'Save Opinion' }));

    await waitFor(() => {
      expect(screen.getByLabelText(/peak/i)).toHaveAttribute('aria-invalid', 'true');
    });
  });
});

describe('OpinionForm - Delete Opinion Link', () => {
  it('shows delete opinion link when user has opinion', () => {
    render(<Harness myOpinion={createOpinion({ user_id: 'user-1' })} />);

    expect(screen.getByText('Delete my opinion')).toBeInTheDocument();
  });

  it('does not show delete opinion link when user has no opinion', () => {
    render(<Harness />);

    expect(screen.queryByText('Delete my opinion')).not.toBeInTheDocument();
  });

  it('calls onDelete when the link is clicked', async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<Harness myOpinion={createOpinion({ user_id: 'user-1' })} onDelete={onDelete} />);

    await user.click(screen.getByText('Delete my opinion'));

    expect(onDelete).toHaveBeenCalled();
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

  it('pre-fills fields from the existing opinion', () => {
    render(<Harness myOpinion={existingOpinion()} />);

    expect(screen.getByLabelText('Position')).toHaveValue('Manager');
    expect(screen.getByLabelText(/lower/i)).toHaveValue(20);
    expect(screen.getByLabelText(/peak/i)).toHaveValue(50);
    expect(screen.getByLabelText(/upper/i)).toHaveValue(80);
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
    render(<Harness myOpinion={existingOpinion()} />);

    expect(screen.getByText('No changes to save')).toBeInTheDocument();
  });
});
