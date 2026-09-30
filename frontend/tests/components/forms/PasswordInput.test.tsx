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

  it('is a plain button that never submits the surrounding form', () => {
    render(<PasswordInput label="Password" name="password" />)

    const toggleButton = screen.getByRole('button', { name: /show|hide/i })
    expect(toggleButton).toHaveAttribute('type', 'button')
  })

  it('reflects visibility state via aria-pressed and updates the aria-label on toggle', async () => {
    const user = userEvent.setup()
    render(<PasswordInput label="Password" name="password" />)

    const toggleButton = screen.getByRole('button', { name: 'Show password' })
    expect(toggleButton).toHaveAttribute('aria-pressed', 'false')

    await user.click(toggleButton)
    expect(toggleButton).toHaveAttribute('aria-pressed', 'true')
    expect(toggleButton).toHaveAccessibleName('Hide password')

    await user.click(toggleButton)
    expect(toggleButton).toHaveAttribute('aria-pressed', 'false')
    expect(toggleButton).toHaveAccessibleName('Show password')
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

  it('lists an extra described-by id next to the error id', () => {
    render(
      <PasswordInput
        label="Password"
        name="password"
        aria-describedby="rules"
        error={{ type: 'required', message: 'Required' }}
      />
    )

    expect(screen.getByLabelText('Password')).toHaveAttribute(
      'aria-describedby',
      'password-error rules'
    )
  })

  it('lists an extra described-by id when there is no error', () => {
    render(<PasswordInput label="Password" name="password" aria-describedby="rules" />)

    expect(screen.getByLabelText('Password')).toHaveAttribute('aria-describedby', 'rules')
  })

  it('has no aria-describedby when there is neither an error nor an extra id', () => {
    render(<PasswordInput label="Password" name="password" />)

    expect(screen.getByLabelText('Password')).not.toHaveAttribute('aria-describedby')
  })

  it('exposes the required state', () => {
    render(<PasswordInput label="Password" name="password" />)

    expect(screen.getByLabelText('Password')).toHaveAttribute('aria-required', 'true')
  })
})
