import { APIError } from './api';
export const label = (value: string) => value.replaceAll('_', ' ');
export const date = (seconds: number) => new Date(seconds * 1000).toLocaleString();
export const errorMessage = (error: unknown) => error instanceof APIError ? error.message : 'The request could not be completed. Retry safely.';
