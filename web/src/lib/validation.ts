import { z } from 'zod'

export const credentialsSchema = z.object({
  email: z.string().trim().toLowerCase().email('Enter a valid email address').max(254),
  password: z.string().min(8, 'Password must be at least 8 characters').max(128),
})

export const registerSchema = credentialsSchema.extend({
  name: z.string().trim().max(80).optional(),
})

/** First validation message, for a single error line in the UI. */
export function firstIssue(error: z.ZodError): string {
  return error.issues[0]?.message ?? 'Invalid input'
}
