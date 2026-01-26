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
    const toggleButton = screen.getByRole('button')

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
})
