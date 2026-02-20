import { describe, it, expect, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@tests/utils';
import { SidebarNav } from '@/components/layout/SidebarNav';
import { BookOpen, Calculator } from 'lucide-react';

const items = [
  { id: 'section-1', label: 'First Section', icon: BookOpen },
  { id: 'section-2', label: 'Second Section', icon: Calculator },
];

describe('SidebarNav', () => {
  it('renders navigation with correct aria-label', () => {
    render(
      <SidebarNav title="Contents" items={items} activeId="section-1" onNavigate={vi.fn()} />
    );

    expect(screen.getByRole('navigation', { name: 'Contents' })).toBeInTheDocument();
  });

  it('renders a button for each item', () => {
    render(
      <SidebarNav title="Contents" items={items} activeId="section-1" onNavigate={vi.fn()} />
    );

    const nav = screen.getByRole('navigation');
    const buttons = within(nav).getAllByRole('button');
    expect(buttons).toHaveLength(2);
  });

  it('sets aria-current on active item', () => {
    render(
      <SidebarNav title="Contents" items={items} activeId="section-1" onNavigate={vi.fn()} />
    );

    const activeButton = screen.getByRole('button', { name: /First Section/i });
    expect(activeButton).toHaveAttribute('aria-current', 'true');
  });

  it('does not set aria-current on inactive items', () => {
    render(
      <SidebarNav title="Contents" items={items} activeId="section-1" onNavigate={vi.fn()} />
    );

    const inactiveButton = screen.getByRole('button', { name: /Second Section/i });
    expect(inactiveButton).not.toHaveAttribute('aria-current');
  });

  it('calls onNavigate with item id when button clicked', async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();

    render(
      <SidebarNav title="Contents" items={items} activeId="section-1" onNavigate={onNavigate} />
    );

    await user.click(screen.getByRole('button', { name: /Second Section/i }));

    expect(onNavigate).toHaveBeenCalledWith('section-2');
  });

  it('renders title text', () => {
    render(
      <SidebarNav title="Contents" items={items} activeId="section-1" onNavigate={vi.fn()} />
    );

    expect(screen.getByText('Contents')).toBeInTheDocument();
  });
});
