import asyncio
import logging
from typing import Any, Callable, Coroutine

logger = logging.getLogger("sahayai.async")


async def run_parallel(*tasks: Coroutine, timeout: float = 25.0) -> list[Any]:
    """
    Run multiple async tasks in parallel with a timeout.
    Returns results in the same order as inputs.
    If any task fails, its result is the exception (not raised).
    This way one slow LLM call doesn't kill the whole pipeline.
    
    Usage:
        user_resp, cg_alert, cct = await run_parallel(
            assistance_agent(state),
            caregiver_agent(state),
            score_cct(state),
        )
    """
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=timeout,
        )
        # Log any failures but don't crash
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Parallel task {i} failed: {result}")
        return results
    except asyncio.TimeoutError:
        logger.error(f"Parallel tasks timed out after {timeout}s")
        return [TimeoutError(f"Timed out after {timeout}s")] * len(tasks)


async def run_with_fallback(
    primary: Coroutine,
    fallback_value: Any,
    task_name: str = "task",
    timeout: float = 15.0,
) -> Any:
    """
    Run a single async task with a timeout and fallback.
    If it fails or times out, return the fallback value silently.
    Perfect for "nice to have" operations like CCT scoring where
    failure shouldn't block the user's response.
    """
    try:
        return await asyncio.wait_for(primary, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"{task_name} timed out after {timeout}s — using fallback")
        return fallback_value
    except Exception as e:
        logger.warning(f"{task_name} failed: {e} — using fallback")
        return fallback_value