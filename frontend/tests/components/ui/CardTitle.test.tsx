import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CardTitle } from '@/components/ui/card';

describe('CardTitle', () => {
  it('renders as h3 by default', () => {
    render(<CardTitle>Title</CardTitle>);

    const heading = screen.getByRole('heading', { level: 3, name: 'Title' });
    expect(heading).toBeInTheDocument();
  });

  it('renders as h1 with as="h1"', () => {
    render(<CardTitle as="h1">Title</CardTitle>);

    const heading = screen.getByRole('heading', { level: 1, name: 'Title' });
    expect(heading).toBeInTheDocument();
  });

  it('renders as h2 with as="h2"', () => {
    render(<CardTitle as="h2">Title</CardTitle>);

    const heading = screen.getByRole('heading', { level: 2, name: 'Title' });
    expect(heading).toBeInTheDocument();
  });

  it('renders as h4 with as="h4"', () => {
    render(<CardTitle as="h4">Title</CardTitle>);

    const heading = screen.getByRole('heading', { level: 4, name: 'Title' });
    expect(heading).toBeInTheDocument();
  });
});
