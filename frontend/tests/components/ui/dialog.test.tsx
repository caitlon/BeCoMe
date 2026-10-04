import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '@/i18n';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';

function renderDialog() {
  return render(
    <I18nextProvider i18n={i18n}>
      <Dialog open>
        <DialogContent>
          <DialogTitle>Title</DialogTitle>
          <DialogDescription>Description</DialogDescription>
        </DialogContent>
      </Dialog>
    </I18nextProvider>,
  );
}

describe('DialogContent close button', () => {
  it('is named "Close" in English', () => {
    renderDialog();

    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
  });

  it('is named "Zavřít" in Czech', async () => {
    await i18n.changeLanguage('cs');
    try {
      const { unmount } = renderDialog();

      expect(screen.getByRole('button', { name: 'Zavřít' })).toBeInTheDocument();

      // Unmount before reverting the language so the change below does not
      // re-render this already-asserted dialog outside act().
      unmount();
    } finally {
      await i18n.changeLanguage('en');
    }
  });
});
