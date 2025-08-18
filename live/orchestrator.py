import asyncio
from typing import Any, Callable, Dict, Iterable, Optional, Tuple


async def _maybe_await(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Run *func* which may be sync or async and return its result."""
    result = func(*args, **kwargs)
    if asyncio.iscoroutine(result) or isinstance(result, asyncio.Future):
        return await result
    return result


async def compute_for_pair_tf(
    pair: str,
    tf: str,
    cfg: Dict[str, Any],
    semaphore: Optional[asyncio.Semaphore] = None,
) -> Tuple[str, str, Any]:
    """Fetch data and generate a trading signal for ``pair``/``tf``.

    ``cfg`` must provide at least ``fetch_ohlcv`` and ``generate_signal`` callables.
    ``compute_indicators`` is optional.  Functions may be synchronous or
    asynchronous.  The return value is a tuple ``(pair, tf, signal)`` where
    ``signal`` is the output of ``generate_signal``.
    """

    fetch_ohlcv = cfg.get("fetch_ohlcv")
    if fetch_ohlcv is None:
        raise ValueError("fetch_ohlcv callable missing from cfg")

    compute_indic = cfg.get("compute_indicators")
    gen_signal = cfg.get("generate_signal")
    if gen_signal is None:
        raise ValueError("generate_signal callable missing from cfg")

    if semaphore is not None:
        async with semaphore:
            ohlcv = await _maybe_await(fetch_ohlcv, pair, tf, cfg)
    else:
        ohlcv = await _maybe_await(fetch_ohlcv, pair, tf, cfg)

    indics = (
        await _maybe_await(compute_indic, pair, tf, ohlcv, cfg)
        if compute_indic
        else None
    )

    signal = await _maybe_await(gen_signal, pair, tf, ohlcv, indics, cfg)
    return pair, tf, signal


async def pipeline(
    pairs: Iterable[str],
    tfs: Iterable[str],
    cfg: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Orchestrate computation of signals for all ``pairs`` and ``tfs``.

    ``cfg`` may specify ``max_connections`` to limit concurrent HTTP requests.
    Results are returned as ``{pair: {tf: signal}}``.
    """

    max_conn = cfg.get("max_connections")
    semaphore: Optional[asyncio.Semaphore] = None
    if max_conn is not None:
        semaphore = asyncio.Semaphore(int(max_conn))

    tasks = [
        compute_for_pair_tf(pair, tf, cfg, semaphore)
        for pair in pairs
        for tf in tfs
    ]

    results = await asyncio.gather(*tasks)
    out: Dict[str, Dict[str, Any]] = {}
    for pair, tf, sig in results:
        out.setdefault(pair, {})[tf] = sig
    return out


__all__ = ["compute_for_pair_tf", "pipeline"]
