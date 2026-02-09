import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@tests/utils';
import { SubmitButton } from '@/components/forms/SubmitButton';

describe('SubmitButton', () => {
  it('renders children as button text', () => {
    render(<SubmitButton>Submit Form</SubmitButton>);

    expect(screen.getByRole('button', { name: 'Submit Form' })).toBeInTheDocument();
  });

  it('has type submit by default', () => {
    render(<SubmitButton>Submit</SubmitButton>);

    expect(screen.getByRole('button')).toHaveAttribute('type', 'submit');
  });

  it('shows spinner when isLoading', () => {
    render(<SubmitButton isLoading>Submit</SubmitButton>);

    expect(screen.getByRole('button').querySelector('svg')).toBeInTheDocument();
  });

  it('shows loadingText when provided and isLoading', () => {
    render(
      <SubmitButton isLoading loadingText="Saving...">
        Submit
      </SubmitButton>
    );

    expect(screen.getByText('Saving...')).toBeInTheDocument();
  });

  it('shows children when isLoading but no loadingText', () => {
    render(<SubmitButton isLoading>Submit</SubmitButton>);

    expect(screen.getByText('Submit')).toBeInTheDocument();
  });

  it('is disabled when isLoading', () => {
    render(<SubmitButton isLoading>Submit</SubmitButton>);

    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('is disabled when disabled prop is true', () => {
    render(<SubmitButton disabled>Submit</SubmitButton>);

    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('has aria-busy when isLoading', () => {
    render(<SubmitButton isLoading>Submit</SubmitButton>);

    expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'true');
  });
});
