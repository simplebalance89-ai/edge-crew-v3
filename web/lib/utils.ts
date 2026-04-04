import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatGrade(grade: string): string {
  return grade;
}

export function getGradeColor(grade: string): string {
  if (grade.startsWith('A')) return 'emerald';
  if (grade.startsWith('B')) return 'amber';
  if (grade.startsWith('C')) return 'orange';
  return 'red';
}
