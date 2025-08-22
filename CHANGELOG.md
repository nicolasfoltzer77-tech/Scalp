# Changelog

## Unreleased

- Trigger trade entries via `strategy.generate_signal` with weighted scoring and
  signal levels.
- Dynamic risk management adapting `risk_pct` and leverage based on signal and
  user risk level.
- Notional and margin caps with available balance check to avoid Bitget error
  `40762`.
- Risk notifications with green/yellow/red indicators for terminal and
  Telegram.
