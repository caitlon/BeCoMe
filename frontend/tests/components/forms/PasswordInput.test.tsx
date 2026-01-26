import { render, screen } from '@tests/utils'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import { PasswordInput } from '@/components/forms/PasswordInput'

describe('PasswordInput', () => {
  it('renders with password type by default', () => {
    render(<PasswordInput label="Password" name="password" />)

    const input = screen.getByLabelText('Password')
    expect(input).toHaveAttribute('type', 'password')
  })

  it('toggles password visibility on button click', async () => {
    const user = userEvent.setup()
    render(<PasswordInput label="Password" name="password" />)

    const input = screen.getByLabelText('Password')
    const toggleButton = screen.getByRole('button', { name: /show|hide/i })

    expect(input).toHaveAttribute('type', 'password')

    await user.click(toggleButton)
    expect(input).toHaveAttribute('type', 'text')

    await user.click(toggleButton)
    expect(input).toHaveAttribute('type', 'password')
  })

  it('displays error message', () => {
    render(
      <PasswordInput
        label="Password"
        name="password"
        error={{ type: 'minLength', message: 'Password too short' }}
      />
    )

    expect(screen.getByText('Password too short')).toBeInTheDocument()
  })

  it('generates id when neither id nor name provided', () => {
    render(<PasswordInput label="Password" />)

    const input = screen.getByLabelText('Password')
    expect(input).toHaveAttribute('id')
    expect(input.id).toBeTruthy()
  })

  it('uses id prop when provided', () => {
    render(<PasswordInput label="Password" id="custom-password-id" />)

    const input = screen.getByLabelText('Password')
    expect(input).toHaveAttribute('id', 'custom-password-id')
  })

  it('sets aria-describedby when error is present', () => {
    render(
      <PasswordInput
        label="Password"
        name="password"
        error={{ type: 'required', message: 'Required' }}
      />
    )

    const input = screen.getByLabelText('Password')
    expect(input).toHaveAttribute('aria-describedby')
    expect(input).toHaveAttribute('aria-invalid', 'true')
  })
})
