import { render, screen, waitFor } from '@tests/utils'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { DeleteConfirmModal } from '@/components/modals/DeleteConfirmModal'

describe('DeleteConfirmModal', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    title: 'Delete Project',
    description: 'Are you sure you want to delete this project?',
    onConfirm: vi.fn().mockResolvedValue(undefined),
  }

  it('renders title and description', () => {
    render(<DeleteConfirmModal {...defaultProps} />)

    expect(screen.getByText('Delete Project')).toBeInTheDocument()
    expect(screen.getByText('Are you sure you want to delete this project?')).toBeInTheDocument()
  })

  it('renders details list when provided', () => {
    render(
      <DeleteConfirmModal
        {...defaultProps}
        details={['All opinions will be deleted', 'All invitations will be cancelled']}
      />
    )

    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveTextContent('All opinions will be deleted')
    expect(items[1]).toHaveTextContent('All invitations will be cancelled')
  })

  it('calls onOpenChange with false when cancel button is clicked', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()

    render(<DeleteConfirmModal {...defaultProps} onOpenChange={onOpenChange} />)

    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('calls onConfirm when confirm button is clicked', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn().mockResolvedValue(undefined)

    render(<DeleteConfirmModal {...defaultProps} onConfirm={onConfirm} />)

    await user.click(screen.getByRole('button', { name: /delete/i }))

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalled()
    })
  })

  it('shows loading state during confirmation', async () => {
    const user = userEvent.setup()
    let resolveConfirm: () => void
    const onConfirm = vi.fn().mockImplementation(
      () => new Promise((resolve) => { resolveConfirm = resolve })
    )

    render(
      <DeleteConfirmModal
        {...defaultProps}
        onConfirm={onConfirm}
        loadingText="Deleting..."
      />
    )

    await user.click(screen.getByRole('button', { name: /delete/i }))

    expect(screen.getByText('Deleting...')).toBeInTheDocument()

    resolveConfirm!()

    await waitFor(() => {
      expect(screen.queryByText('Deleting...')).not.toBeInTheDocument()
    })
  })
})
