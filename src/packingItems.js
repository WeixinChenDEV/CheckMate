/** Parse assistant lists without importing guidance or follow-up questions. */
export function extractPackingItems(text) {
  const items = [];
  const byText = new Map();
  let section = null;
  let guidance = false;

  for (const raw of String(text || '').split('\n')) {
    const line = raw.trim();
    if (!line) continue;
    const heading = line.replace(/^#{1,6}\s*/, '').replace(/\*\*|__/g, '')
      .replace(/[:：]+$/, '').trim();
    // Check guidance first: "建议" can also occur in an optional-items heading.
    if (/^(trip\s*note\b|tips?\b|follow[ -]?up\b|questions?\b|提示|补充|補充|追问|追問|后续|後續|旅行说明|旅行說明)/i.test(heading)) {
      section = null;
      guidance = true;
      continue;
    }
    if (/^(critical(?: items)?|must bring|must-have|必带(?:物品)?|必備(?:物品)?|重要(?:物品)?|关键(?:物品)?|關鍵(?:物品)?)$/i.test(heading)) {
      section = 'critical';
      guidance = false;
      continue;
    }
    if (/^(normal(?: items)?|optional(?: items)?|recommended(?: items)?|推荐(?:物品)?|建議(?:物品)?|建议(?:物品)?|可选(?:物品)?|清单|行李)$/i.test(heading)) {
      section = 'normal';
      guidance = false;
      continue;
    }
    if (guidance) continue;
    const bullet = line.match(/^(?:[-*•]\s+|\d+[.)、]\s*)(?:\[[ xX]\]\s*)?(.+)$/);
    if (!bullet) continue;
    const candidate = bullet[1].replace(/\*\*|__/g, '').trim();
    if (!candidate || /[?？]$/.test(candidate)) continue;
    if (/^(which|what|when|how|any|say|try|avoid|use|keep|add|for example|e\.g\.)\b/i.test(candidate)) continue;
    if (/^(请问|是否|幾天|几天|什么时候|何時|哪天|哪個|哪个|例如|比如|建议|建議|請|请)/.test(candidate)) continue;
    const key = candidate.toLowerCase().replace(/\s+/g, ' ');
    if (byText.has(key)) {
      if (section === 'critical') byText.get(key).critical = true;
      continue;
    }
    const item = { text: candidate, critical: section === 'critical', assignedTo: 'me' };
    byText.set(key, item);
    items.push(item);
  }
  return items;
}
