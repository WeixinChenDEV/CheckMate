import { extractPackingItems } from './packingItems';

test('imports markdown headings, numbered lists and checkboxes', () => {
  expect(extractPackingItems('### **Critical Items:**\n1. Passport\n- [ ] Tickets\n### Normal Items：\n* Socks'))
    .toEqual([
      { text: 'Passport', critical: true, assignedTo: 'me' },
      { text: 'Tickets', critical: true, assignedTo: 'me' },
      { text: 'Socks', critical: false, assignedTo: 'me' },
    ]);
});

test('excludes trip notes, tips and follow-up questions', () => {
  const text = 'Trip note: London\n- Rain is likely\nCritical Items\n- Passport\nTips:\n- Check the forecast\nFollow-up:\n- How long?';
  expect(extractPackingItems(text).map((x) => x.text)).toEqual(['Passport']);
});

test('handles Chinese headings without importing instructions', () => {
  const text = '必带物品：\n- 护照\n推荐物品：\n- 雨伞\n- 请检查天气\n提示：\n- 提前到机场';
  expect(extractPackingItems(text).map((x) => [x.text, x.critical]))
    .toEqual([['护照', true], ['雨伞', false]]);
});

test('deduplicates items and preserves critical priority', () => {
  const text = 'Normal Items\n- Passport\n- WATER  bottle\nCritical Items\n- passport\n- Water bottle';
  expect(extractPackingItems(text)).toHaveLength(2);
  expect(extractPackingItems(text).every((x) => x.critical)).toBe(true);
});

test('accepts plain bullet lists and ignores questions', () => {
  expect(extractPackingItems('- Charger\n- Which bag?\n- 你要去哪里？').map((x) => x.text))
    .toEqual(['Charger']);
  expect(extractPackingItems(null)).toEqual([]);
});
