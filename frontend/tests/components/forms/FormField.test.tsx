import { render, screen } from '@tests/utils'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { FormField, FormTextarea } from '@/components/forms/FormField'

describe('FormField', () => {
  it('renders label and input with correct association', () => {
    render(<FormField label="Email" name="email" />)

    const input = screen.getByLabelText('Email')
    expect(input).toBeInTheDocument()
    expect(input).toHaveAttribute('name', 'email')
  })

  it('displays error message and sets aria-invalid', () => {
    render(
      <FormField
        label="Email"
        name="email"
        error={{ type: 'required', message: 'Email is required' }}
      />
    )

    expect(screen.getByText('Email is required')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true')
  })

  it('displays description when no error', () => {
    render(
      <FormField
        label="Email"
        name="email"
        description="Enter your work email"
      />
    )

    expect(screen.getByText('Enter your work email')).toBeInTheDocument()
  })

  it('hides description when error is present', () => {
    render(
      <FormField
        label="Email"
        name="email"
        description="Enter your work email"
        error={{ type: 'required', message: 'Email is required' }}
      />
    )

    expect(screen.queryByText('Enter your work email')).not.toBeInTheDocument()
    expect(screen.getByText('Email is required')).toBeInTheDocument()
  })

  it('calls onChange when user types', async () => {
    const user = userEvent.setup()
    const handleChange = vi.fn()

    render(<FormField label="Email" name="email" onChange={handleChange} />)

    await user.type(screen.getByLabelText('Email'), 'test@example.com')

    expect(handleChange).toHaveBeenCalled()
  })
})

describe('FormField - aria-describedby', () => {
  it('sets aria-describedby to description id when only description is present', () => {
    render(
      <FormField
        label="Email"
        name="email"
        description="Enter your email"
      />
    )

    const input = screen.getByLabelText('Email')
    const describedBy = input.getAttribute('aria-describedby')
    expect(describedBy).toContain('description')
  })

  it('sets aria-describedby to error id when only error is present', () => {
    render(
      <FormField
        label="Email"
        name="email"
        error={{ type: 'required', message: 'Required' }}
      />
    )

    const input = screen.getByLabelText('Email')
    const describedBy = input.getAttribute('aria-describedby')
    expect(describedBy).toContain('error')
  })

  it('sets aria-describedby to error id when both description and error are present', () => {
    render(
      <FormField
        label="Email"
        name="email"
        description="Enter your email"
        error={{ type: 'required', message: 'Required' }}
      />
    )

    const input = screen.getByLabelText('Email')
    const describedBy = input.getAttribute('aria-describedby')
    expect(describedBy).toContain('error')
  })

  it('uses id prop for field identification when provided', () => {
    render(
      <FormField
        label="Email"
        id="custom-email-id"
        name="email"
      />
    )

    const input = screen.getByLabelText('Email')
    expect(input).toHaveAttribute('id', 'custom-email-id')
  })

  it('falls back to name for field identification when id not provided', () => {
    render(
      <FormField
        label="Email"
        name="email-field"
      />
    )

    const input = screen.getByLabelText('Email')
    expect(input).toHaveAttribute('id', 'email-field')
  })

  it('generates id when neither id nor name provided', () => {
    render(
      <FormField
        label="Email"
      />
    )

    const input = screen.getByLabelText('Email')
    expect(input).toHaveAttribute('id')
    expect(input.id).toBeTruthy()
  })
})

describe('FormTextarea', () => {
  it('renders textarea with label', () => {
    render(<FormTextarea label="Description" name="description" />)

    expect(screen.getByLabelText('Description')).toBeInTheDocument()
  })

  it('displays error message', () => {
    render(
      <FormTextarea
        label="Description"
        name="description"
        error={{ type: 'required', message: 'Description is required' }}
      />
    )

    expect(screen.getByText('Description is required')).toBeInTheDocument()
  })

  it('sets aria-describedby for description', () => {
    render(
      <FormTextarea
        label="Description"
        name="description"
        description="Write a detailed description"
      />
    )

    const textarea = screen.getByLabelText('Description')
    const describedBy = textarea.getAttribute('aria-describedby')
    expect(describedBy).toContain('description')
  })

  it('generates id when neither id nor name provided', () => {
    render(
      <FormTextarea
        label="Description"
      />
    )

    const textarea = screen.getByLabelText('Description')
    expect(textarea).toHaveAttribute('id')
    expect(textarea.id).toBeTruthy()
  })
})
