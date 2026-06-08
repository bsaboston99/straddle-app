export const tickers = {
  NVDA: {
    name: "NVIDIA Corporation", price: "$924.60", change: "+2.14%", dir: "up",
    earnInfo: "Earnings Jun 9 — 3 days away", earnDate: "Jun 9, 2026 (3 days)",
    front: "$48.30", frontPct: "5.22% of price",
    back: "$61.80", backPct: "6.69% of price",
    epr: "2.51x", spyNorm: "+3.14%",
    wk52: "$462.00 – $974.00", iv: "62.4%", ivr: "78 / 100", hist: "±4.8% avg",
    earnBadge: "Jun 9", earnSub: "Earnings in 3 days",
    pct_a: 82, pct_b: 74, pct_ep: 21,
    sig_a: "RICH", sig_b: "NORMAL", sig_ep: "CHEAP",
    adj_a: "RICH (stock-specific)", adj_b: "NORMAL", adj_ep: "CHEAP (stock-specific)",
    composite: "MIXED / NORMAL",
    signal: { type: "green", label: "Elevated premium signal", text: "Front/back ratio suggests market pricing in outsized move. EPR above 2.0x historically favors straddle sellers post-earnings." }
  },
  ORCL: {
    name: "Oracle Corporation", price: "$137.45", change: "-0.87%", dir: "down",
    earnInfo: "Earnings Jun 10 — 4 days away", earnDate: "Jun 10, 2026 (4 days)",
    front: "$9.15", frontPct: "6.66% of price",
    back: "$11.40", backPct: "8.29% of price",
    epr: "3.20x", spyNorm: "+4.58%",
    wk52: "$98.40 – $163.00", iv: "71.2%", ivr: "85 / 100", hist: "±5.2% avg",
    earnBadge: "Jun 10", earnSub: "Earnings in 4 days",
    pct_a: 91, pct_b: 88, pct_ep: 78,
    sig_a: "RICH", sig_b: "RICH", sig_ep: "RICH",
    adj_a: "RICH (market-driven)", adj_b: "RICH (market-driven)", adj_ep: "RICH (stock-specific)",
    composite: "RICH (3/3 metrics)",
    signal: { type: "warn", label: "High EPR — elevated risk", text: "EPR of 3.20x is well above historical median. Back-month premium is 24% wider than front." }
  },
  ADBE: {
    name: "Adobe Inc.", price: "$488.20", change: "+0.53%", dir: "up",
    earnInfo: "Earnings Jun 12 — 6 days away", earnDate: "Jun 12, 2026 (6 days)",
    front: "$27.40", frontPct: "5.61% of price",
    back: "$34.10", backPct: "6.98% of price",
    epr: "2.70x", spyNorm: "+3.53%",
    wk52: "$380.00 – $638.00", iv: "58.8%", ivr: "71 / 100", hist: "±4.6% avg",
    earnBadge: "Jun 12", earnSub: "Earnings in 6 days",
    pct_a: 58, pct_b: 52, pct_ep: 44,
    sig_a: "NORMAL", sig_b: "NORMAL", sig_ep: "NORMAL",
    adj_a: "NORMAL", adj_b: "NORMAL", adj_ep: "NORMAL",
    composite: "MIXED / NORMAL",
    signal: { type: "green", label: "Within historical range", text: "Implied move of 5.61% aligns closely with the ±4.6% historical average." }
  },
  TSLA: {
    name: "Tesla, Inc.", price: "$182.30", change: "-1.44%", dir: "down",
    earnInfo: "Earnings Jul 17", earnDate: "Jul 17, 2026",
    front: "$18.75", frontPct: "10.28% of price",
    back: "$23.50", backPct: "12.89% of price",
    epr: "4.94x", spyNorm: "+8.20%",
    wk52: "$138.80 – $299.00", iv: "84.3%", ivr: "91 / 100", hist: "±8.1% avg",
    earnBadge: null, earnSub: "Jul 17",
    pct_a: 18, pct_b: 22, pct_ep: 12,
    sig_a: "CHEAP", sig_b: "CHEAP", sig_ep: "CHEAP",
    adj_a: "CHEAP (stock-specific)", adj_b: "CHEAP (stock-specific)", adj_ep: "CHEAP (stock-specific)",
    composite: "CHEAP (3/3 metrics)",
    signal: { type: "warn", label: "Very high EPR — extreme premium", text: "EPR of 4.94x is in the top decile historically. IV rank of 91 suggests options are expensive." }
  },
  AMZN: {
    name: "Amazon.com, Inc.", price: "$186.55", change: "+0.91%", dir: "up",
    earnInfo: "Earnings Jul 31", earnDate: "Jul 31, 2026",
    front: "$12.60", frontPct: "6.75% of price",
    back: "$15.90", backPct: "8.52% of price",
    epr: "3.25x", spyNorm: "+4.67%",
    wk52: "$151.00 – $242.00", iv: "45.1%", ivr: "62 / 100", hist: "±5.0% avg",
    earnBadge: null, earnSub: "Jul 31",
    pct_a: 34, pct_b: 41, pct_ep: 29,
    sig_a: "NORMAL", sig_b: "NORMAL", sig_ep: "CHEAP",
    adj_a: "NORMAL", adj_b: "NORMAL", adj_ep: "CHEAP (stock-specific)",
    composite: "MIXED / NORMAL",
    signal: { type: "green", label: "Moderate signal", text: "Implied move of 6.75% slightly above ±5.0% historical avg." }
  },
  META: {
    name: "Meta Platforms, Inc.", price: "$504.10", change: "+1.22%", dir: "up",
    earnInfo: "Earnings Jul 30", earnDate: "Jul 30, 2026",
    front: "$29.85", frontPct: "5.92% of price",
    back: "$37.20", backPct: "7.38% of price",
    epr: "2.85x", spyNorm: "+3.84%",
    wk52: "$414.00 – $612.00", iv: "51.6%", ivr: "68 / 100", hist: "±5.3% avg",
    earnBadge: null, earnSub: "Jul 30",
    pct_a: 61, pct_b: 55, pct_ep: 48,
    sig_a: "NORMAL", sig_b: "NORMAL", sig_ep: "NORMAL",
    adj_a: "NORMAL", adj_b: "NORMAL", adj_ep: "NORMAL",
    composite: "MIXED / NORMAL",
    signal: { type: "green", label: "Near fair value", text: "Implied move close to historical average. EPR of 2.85x is moderate." }
  },
  SPY: {
    name: "SPDR S&P 500 ETF (Benchmark)", price: "$537.80", change: "+0.34%", dir: "up",
    earnInfo: "SPY benchmark — no earnings", earnDate: "N/A (ETF)",
    front: "$11.20", frontPct: "2.08% of price",
    back: "$14.60", backPct: "2.71% of price",
    epr: "1.00x", spyNorm: "Baseline",
    wk52: "$472.00 – $613.00", iv: "14.2%", ivr: "42 / 100", hist: "±1.2% avg",
    earnBadge: null, earnSub: "Benchmark",
    pct_a: 50, pct_b: 48, pct_ep: 50,
    sig_a: "NORMAL", sig_b: "NORMAL", sig_ep: "NORMAL",
    adj_a: "NORMAL", adj_b: "NORMAL", adj_ep: "NORMAL",
    composite: "MIXED / NORMAL",
    signal: { type: "green", label: "Benchmark reference", text: "All straddle values and EPR ratios are normalized against SPY." }
  }
};

export const WATCHLIST = Object.keys(tickers);
export const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";