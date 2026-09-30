import { toLocalDateTimeInput } from './tripDates';

test('formats local hours rather than UTC hours', () => {
  expect(toLocalDateTimeInput(new Date(2030, 0, 2, 9, 5))).toBe('2030-01-02T09:05');
});

test('handles invalid dates', () => {
  expect(toLocalDateTimeInput(new Date('invalid'))).toBe('');
});
