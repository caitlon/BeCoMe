import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '@/i18n';
import { Toast, ToastClose, ToastProvider, ToastTitle, ToastViewport } from '@/components/ui/toast';

function renderToast() {
  return render(
    <I18nextProvider i18n={i18n}>
      <ToastProvider>
        <Toast open>
          <ToastTitle>Saved</ToastTitle>
          <ToastClose />
        </Toast>
        <ToastViewport />
      </ToastProvider>
    </I18nextProvider>,
  );
}

describe('Toast accessible names', () => {
  it('names the close button and the region in English', () => {
    renderToast();

    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Notifications (F8)' })).toBeInTheDocument();
  });

  it('names the close button and the region in Czech', async () => {
    await i18n.changeLanguage('cs');
    try {
      const { unmount } = renderToast();

      expect(screen.getByRole('button', { name: 'Zavřít' })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: 'Oznámení (F8)' })).toBeInTheDocument();

      // Unmount before reverting the language so the change below does not
      // re-render this already-asserted toast outside act().
      unmount();
    } finally {
      await i18n.changeLanguage('en');
    }
  });
});
