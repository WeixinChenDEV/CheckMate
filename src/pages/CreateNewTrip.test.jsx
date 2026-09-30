import React from 'react';
import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { Simulate } from 'react-dom/test-utils';
import CreateNewTrip from './CreateNewTrip';

global.IS_REACT_ACT_ENVIRONMENT = true;
let container;
let root;
beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
  jest.restoreAllMocks();
});

const draft = {
  name: 'Weekend',
  items: [{ id: 'passport', text: 'Passport' }],
  trip_start_at: '2099-06-01T09:00',
  trip_end_at: '2099-06-03T18:00',
};
const saveButton = () => [...container.querySelectorAll('button')].find((b) => b.textContent === 'Save');

test('shows return input without an error and includes both dates on save', async () => {
  const onSave = jest.fn();
  act(() => root.render(<CreateNewTrip theme={{}} initialTrip={draft} onSave={onSave} />));
  expect(container.querySelector('[aria-label="Return (optional)"]').value).toBe(draft.trip_end_at);
  await act(async () => Simulate.click(saveButton()));
  expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
    trip_start_at: draft.trip_start_at, trip_end_at: draft.trip_end_at,
  }));
});

test('rejects return before departure', async () => {
  const onSave = jest.fn();
  const alert = jest.spyOn(window, 'alert').mockImplementation(() => {});
  act(() => root.render(<CreateNewTrip theme={{}} initialTrip={{ ...draft, trip_end_at: '2099-05-01T09:00' }} onSave={onSave} />));
  await act(async () => Simulate.click(saveButton()));
  expect(onSave).not.toHaveBeenCalled();
  expect(alert).toHaveBeenCalled();
});

test('departure alone remains valid', async () => {
  const onSave = jest.fn();
  act(() => root.render(<CreateNewTrip theme={{}} initialTrip={{ ...draft, trip_end_at: null }} onSave={onSave} />));
  await act(async () => Simulate.click(saveButton()));
  expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ trip_end_at: null }));
});
