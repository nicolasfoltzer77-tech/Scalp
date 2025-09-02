async function fetchQuotes(symbols) {
  const url = `/api/quotes?symbols=${symbols.join(",")}`;
  const r = await fetch(url);
  return await r.json(); // [{symbol, price}]
}

function computePnl(position, priceNow) {
  const side = (position.side || position.direction || "").toUpperCase();
  const entry = Number(position.entry_price || position.entry || 0);
  const qty   = Number(position.qty || position.quantity_usdt || 0);
  if (!entry || !qty || !priceNow) return null;
  const diff = (priceNow - entry) * (side === "SHORT" ? -1 : 1);
  return diff * (qty / entry); // qty en USDT => converti en nombre de bases
}

export async function enrichPositionsWithPnl(rows) {
  if (!rows || !rows.length) return [];
  const symbols = [...new Set(rows.map(r => r.symbol || r.sym))];
  const quotes = await fetchQuotes(symbols);
  const px = Object.fromEntries(quotes.map(q => [q.symbol, q.price]));
  return rows.map(r => {
    const sym = (r.symbol || r.sym || "").toUpperCase();
    const pnow = px[sym];
    const pnl = computePnl(r, pnow);
    return {...r, price_now: pnow, pnl_live: pnl};
  });
}
