/**
 * Client-side validation helpers.
 *
 * Mirror the backend rules in `backend/app/core/security.py` so users get
 * immediate feedback before submitting:
 * - Email format (Req 8.2).
 * - Password complexity: >= 8 chars, upper, lower, digit, special (Req 8.4).
 *
 * Client-side checks are a UX convenience; the backend remains the source of
 * truth for validation.
 */
const EMAIL_REGEX = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;
export const PASSWORD_MIN_LENGTH = 8;
export function isValidEmail(email) {
    return email.length <= 255 && EMAIL_REGEX.test(email);
}
export function checkPassword(password) {
    return {
        length: password.length >= PASSWORD_MIN_LENGTH,
        uppercase: /[A-Z]/.test(password),
        lowercase: /[a-z]/.test(password),
        digit: /\d/.test(password),
        special: /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?~`]/.test(password),
    };
}
export function isPasswordComplex(password) {
    const checks = checkPassword(password);
    return checks.length && checks.uppercase && checks.lowercase && checks.digit && checks.special;
}
/** Derive a coarse strength rating from how many complexity rules pass. */
export function passwordStrength(password) {
    const checks = checkPassword(password);
    const passed = Object.values(checks).filter(Boolean).length;
    if (passed <= 2) {
        return 'weak';
    }
    if (passed <= 4) {
        return 'medium';
    }
    return 'strong';
}
