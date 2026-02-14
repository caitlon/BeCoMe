import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render, framerMotionMock } from '@tests/utils';
import { HeroSection } from '@/components/layout/HeroSection';

vi.mock('framer-motion', () => framerMotionMock);

describe('HeroSection', () => {
  it('renders the title in an h1 element', () => {
    render(<HeroSection title="Test Title" subtitle="sub" />);

    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading).toHaveTextContent('Test Title');
  });

  it('renders the subtitle in a paragraph', () => {
    render(<HeroSection title="t" subtitle="Test Subtitle" />);

    const subtitle = screen.getByText('Test Subtitle');
    expect(subtitle.tagName).toBe('P');
  });

  it('wraps content in a section element', () => {
    const { container } = render(<HeroSection title="t" subtitle="s" />);

    expect(container.querySelector('section')).not.toBeNull();
  });
});
