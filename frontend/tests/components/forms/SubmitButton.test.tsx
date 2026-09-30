import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

  it('is aria-disabled but not disabled when isLoading', () => {
    render(<SubmitButton isLoading>Submit</SubmitButton>);

    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-disabled', 'true');
    expect(button).not.toBeDisabled();
  });

  it('is not aria-disabled when idle', () => {
    render(<SubmitButton>Submit</SubmitButton>);

    expect(screen.getByRole('button')).not.toHaveAttribute('aria-disabled');
  });

  it('keeps focus when isLoading starts', () => {
    const { rerender } = render(<SubmitButton>Submit</SubmitButton>);
    const button = screen.getByRole('button');
    button.focus();

    rerender(<SubmitButton isLoading>Submit</SubmitButton>);

    expect(button).toHaveFocus();
  });

  it('ignores a click and Enter while isLoading', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    const onSubmit = vi.fn((event: React.FormEvent) => event.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <SubmitButton isLoading onClick={onClick}>
          Submit
        </SubmitButton>
      </form>
    );
    const button = screen.getByRole('button');

    await user.click(button);
    button.focus();
    await user.keyboard('{Enter}');

    expect(onClick).not.toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
    expect(button).toHaveFocus();
  });

  it('submits and calls onClick when idle', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    const onSubmit = vi.fn((event: React.FormEvent) => event.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <SubmitButton onClick={onClick}>Submit</SubmitButton>
      </form>
    );

    await user.click(screen.getByRole('button'));

    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledTimes(1);
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
